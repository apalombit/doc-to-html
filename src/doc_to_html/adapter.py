"""GLM-OCR's regions -> the IR: Zones, Blocks, Cells and Rows, each with its box.

Spec 0023, arm D2. GLM-OCR's own pipeline cuts the page into regions and
reads each one (`tools/glmocr_parse.py`); this maps what it returned into
the IR, so today's style record, looks and renderer can draw it. **It reads
nothing off the page but the boxes of what the page draws** (its frames and
fills, `containers`): the words, the regions, their labels and their order
are the parser's.

A region is one block of the page as the layout model cut it: a paragraph,
a title, a table, a picture, and on a designed page often one line or one
fragment of a line. The renderer draws a Zone as one block of the page, so
fragments are grouped first:

- **a column stack**: text regions set one under the other in one column
  (their left or middle edges lined up), no further apart than about a
  line, with nothing between them, are one Zone;
- **a container**: a box the page draws round two or more text regions (a
  card, a panel) bounds the stacks: regions in different boxes never join.
  A box no wider than a card (`CARD`) is one Zone, all of it: its frame
  and its fill are one box, and a card split into several Zones is drawn
  as several boxes. A box round one region is that region's look (a
  chip, a button), and the region joins no stack.

A title over the stack or the table it heads is that Zone's Title (the Zone
convention, `CLAUDE.md`). Fragments on one printed line are one Block, one
Cell each. Everything else keeps the parser's region as its Zone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from statistics import median
from typing import Any

from .ir import (BBox, Block, Cell, Document, Kind, Reading, Role, Row, RowRole,
                 Source, Zone)
from .wire import bands_from_boxes

ENGINE = "glm-ocr"
"""The `Reading.engine` of every Cell the adapter writes."""

FIGURES = frozenset({"image", "chart", "header_image", "footer_image"})
TITLES = frozenset({"doc_title", "paragraph_title"})
FORMULAS = frozenset({"display_formula", "inline_formula"})
ROLES = {"header": Role.HEADER, "footer": Role.FOOTER, "header_image": Role.HEADER,
         "footer_image": Role.FOOTER, "number": Role.FOOTER}

BULLET = re.compile(r"^[-•·▪◦*]\s+")
"""A line the reader opens with a bullet; it writes a printed bullet as `- `."""

PAGE_SHARE = 0.80
"""A drawn box covering more of the page than this is the page, not a container."""

CARD = 0.45
"""A container no wider than this share of the page is a card, one Zone;
a wider one (a form's panel holding two sections) only bounds its stacks."""

STACK_GAP = 1.2
"""How far below a region the next may start, in lines, and still be its
column's next block."""

HEADING_GAP = 2.0
"""The same below a heading, which a page sets further from what it heads
than one line from the next: the datasheet's KEY FEATURES, 1.2 lines over
its first item."""

ALIGNED = 0.01
"""How far apart two left edges may be, as a share of the page's width, and
still start one column."""

LINE = 0.025
"""A line's height as a share of the page's, where the page has no region of
one line to measure it by."""

_LATEX = [(r"\^\{\\circ\}", "°"), (r"\\circ", "°"), (r"\\times", "×"), (r"\\pm", "±"),
          (r"\\mathrm\{([^}]*)\}", r"\1"), (r"\\text\{([^}]*)\}", r"\1"),
          (r"\\mathbf\{([^}]*)\}", r"\1"), (r"\\%", "%"), (r"\\leq?", "≤"),
          (r"\\geq?", "≥"), (r"\\cdot", "·"), (r"\\approx", "≈"), (r"\\rightarrow", "→"),
          (r"\\to\b", "→"), (r"\\mu", "µ"), (r"\\Omega", "Ω"), (r"\\#", "#"),
          (r"\\&", "&"), (r"\\_", "_")]
_MARKS = {r"\checkmark": "✓", r"\bigcirc": "○", r"\square": "☐", r"\blacksquare": "■",
          r"\times": "×", r"\cdot": "·", r"\bullet": "•", r"\star": "★"}
_SUP = str.maketrans("0123456789+-−()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁽⁾ⁿ")
_SUB = str.maketrans("0123456789+-()", "₀₁₂₃₄₅₆₇₈₉₊₋₍₎")


def plain(text: str) -> str:
    """The reader's text as the page prints it.

    It writes a mark inside a line as inline LaTeX (`$200^{\\circ}$`), a
    printed mark it has a name for as a bare command (`\\checkmark`), and a
    raised or lowered run as `<sup>`/`<sub>`. Each is set back as the
    characters the page prints: 200°, ✓, H₂. Nothing it read is dropped."""
    def maths(match: re.Match[str]) -> str:
        # Spaces mean nothing in maths, except inside `\text{}`.
        body = re.sub(r"\\text\{([^}]*)\}", lambda m: m.group(1).replace(" ", "\0"),
                      match.group(1))
        body = re.sub(r"(\\[A-Za-z]+)\s+(?=[A-Za-z])", "\\1\x01", body)
        body = re.sub(r"\s+", "", body).replace("\x01", " ").replace("\0", " ")
        for pattern, repl in _LATEX:
            body = re.sub(pattern, repl, body)
        body = re.sub(r"\^\{([^{}]+)\}", lambda m: _raised(m.group(1)), body)
        body = re.sub(r"\^(\w)", lambda m: _raised(m.group(1)), body)
        body = re.sub(r"_\{([^{}]+)\}", lambda m: _lowered(m.group(1)), body)
        body = re.sub(r"_(\w)", lambda m: _lowered(m.group(1)), body)
        body = re.sub(r"(?<=\d) (?=\d)", "", body)
        return body.replace("{", "").replace("}", "").strip()

    # A raised or lowered run is set against the word before it: `CO $_2$`.
    text = re.sub(r"(\w)\s+\$\s*(?=[_^])", r"\1$", text)
    text = re.sub(r"(\$[^$]+\$)\s+(?=[,.;:])", r"\1", text)
    text = re.sub(r"\$\s*(.+?)\s*\$", maths, text)
    for command, mark in _MARKS.items():
        text = re.sub(re.escape(command) + r"(?![A-Za-z])\s*", mark + " ", text)
    text = re.sub(r"<sup>(.*?)</sup>", lambda m: _raised(m.group(1)), text)
    text = re.sub(r"(?<=\d)\^(\d{1,3})\b", lambda m: _raised(m.group(1)), text)
    text = re.sub(r"<sub>(.*?)</sub>", lambda m: _lowered(m.group(1)), text)
    text = text.replace("（", "(").replace("）", ")")
    return re.sub(r"[ \t]+", " ", text).strip()


def _raised(text: str) -> str:
    out = text.translate(_SUP)
    return out if out != text or not text.strip() else "^" + text


def _lowered(text: str) -> str:
    out = text.translate(_SUB)
    return out if out != text or not text.strip() else "_" + text


@dataclass(frozen=True)
class Region:
    """One region as the parser returned it."""

    index: int
    label: str
    box: BBox
    content: str

    @property
    def role(self) -> Role:
        return ROLES.get(self.label, Role.BODY)

    @property
    def text_like(self) -> bool:
        return self.label not in FIGURES and self.label not in FORMULAS and self.label != "table"

    @property
    def lines(self) -> list[str]:
        return [line for line in (plain(part) for part in self.content.split("\n")) if line]


def regions_of(raw: Sequence[Mapping[str, Any]]) -> list[Region]:
    """The parser's regions in its reading order, each box on 0-1 of the
    picture. A region with nothing read in it is dropped unless it is a
    picture, which has no text by nature."""
    out = []
    for item in sorted(raw, key=lambda r: int(r.get("index", 0))):
        left, top, right, bottom = (float(v) / 1000 for v in item["bbox_2d"])
        region = Region(int(item.get("index", 0)), str(item.get("label", "text")),
                        BBox(left, top, right, bottom), str(item.get("content") or ""))
        if region.label in FIGURES or region.content.strip():
            out.append(region)
    return out


def _cell(text: str, box: BBox | None = None) -> Cell:
    return Cell(bbox=box, readings=[Reading(engine=ENGINE, text=text)])


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def _holds(outer: BBox, box: BBox) -> bool:
    x, y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    return outer.left <= x <= outer.right and outer.top <= y <= outer.bottom


def _area(box: BBox) -> float:
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def _across(a: BBox, b: BBox) -> float:
    """How much of the narrower of two boxes the other covers across."""
    shared = min(a.right, b.right) - max(a.left, b.left)
    return max(0.0, shared) / max(min(a.right - a.left, b.right - b.left), 1e-6)


def _one_line(a: BBox, b: BBox) -> bool:
    """Whether two boxes sit on one printed line: each covers most of the other's height."""
    shared = min(a.bottom, b.bottom) - max(a.top, b.top)
    return shared >= 0.5 * min(a.bottom - a.top, b.bottom - b.top)


def line_height(regions: Sequence[Region]) -> float:
    """The page's line, as a share of its height: the median height of its
    regions of one line."""
    single = [r.box.bottom - r.box.top for r in regions
              if r.text_like and len(r.lines) == 1 and r.box.bottom - r.box.top < 0.08]
    return median(single) if single else LINE


# ---- tables -------------------------------------------------------------------

class _Table(HTMLParser):
    """A table as the reader writes it: rows of cells, each with its spans."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, int, int, bool]]] = []
        self.head = False
        self.cell: list[str] | None = None
        self.attrs: dict[str, str] = {}
        self.th = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "thead":
            self.head = True
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self.cell, self.attrs = [], {k: v or "" for k, v in attrs}
            self.th = tag == "th" or self.head
        elif tag == "br" and self.cell is not None:
            self.cell.append("\n")
        elif tag in ("sup", "sub") and self.cell is not None:
            self.cell.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "thead":
            self.head = False
        elif tag in ("sup", "sub") and self.cell is not None:
            self.cell.append(f"</{tag}>")
        elif tag in ("td", "th") and self.cell is not None:
            if not self.rows:
                self.rows.append([])
            self.rows[-1].append(("".join(self.cell), _count(self.attrs.get("rowspan")),
                                  _count(self.attrs.get("colspan")), self.th))
            self.cell = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)


def _count(value: str | None) -> int:
    try:
        return max(1, int(value or 1))
    except ValueError:
        return 1


def rows_of(content: str) -> list[Row]:
    """A table's rows on the IR's grid: a cell spanning others stands at its
    first slot with its span, and the slots it covers hold empty Cells
    (`Cell.span`, as `render._table` draws it). A row of header cells only
    is a header row. A cell's own line ends are kept: each line after its
    first is one of `Cell.below`."""
    parsed = _Table()
    parsed.feed(content)
    grid: dict[tuple[int, int], Cell] = {}
    heads: dict[int, bool] = {}
    for r, cells in enumerate(parsed.rows):
        c = 0
        for text, down, across, th in cells:
            while (r, c) in grid:
                c += 1
            lines = [line for line in map(plain, text.split("\n")) if line]
            cell = _cell(lines[0] if lines else "")
            # A label printed over its value in one cell: the value is a line
            # below it (`Cell.below`), never run on after it.
            cell.below = [_cell(line) for line in lines[1:]]
            if down > 1 or across > 1:
                cell.span = (down, across)
            grid[(r, c)] = cell
            for dr in range(down):
                for dc in range(across):
                    if dr or dc:
                        grid[(r + dr, c + dc)] = _cell("")
            heads[r] = heads.get(r, True) and th
            c += across
    width = max((c for _, c in grid), default=-1) + 1
    height = max((r for r, _ in grid), default=-1) + 1
    return [Row(cells=[grid.get((r, c), _cell("")) for c in range(width)],
                role=RowRole.HEADER if heads.get(r) else RowRole.DATA)
            for r in range(height)]


# ---- grouping -----------------------------------------------------------------

def _containers(regions: Sequence[Region], boxes: Sequence[BBox]
                ) -> tuple[dict[int, BBox], set[int]]:
    """Each text region's container, the smallest box the page draws that
    holds it and at least one other text region; and the text regions
    alone in a box of their own (a chip, a button, a boxed note)."""
    texts = [r for r in regions if r.text_like]
    inside = [box for box in boxes if _area(box) < PAGE_SHARE]
    counts = {box: sum(1 for r in texts if _holds(box, r.box)) for box in inside}
    out: dict[int, BBox] = {}
    alone: set[int] = set()
    for region in texts:
        holding = [box for box in inside if _holds(box, region.box)]
        shared = [box for box in holding if counts[box] >= 2]
        if shared:
            out[region.index] = min(shared, key=_area)
        elif holding:
            alone.add(region.index)
    return out, alone


def _aligned(a: BBox, b: BBox) -> bool:
    """Whether two boxes start or centre one column: their left or middle
    edges within `ALIGNED`. Overlapping is not enough (a chip over a
    heading overlaps it), and neither are right edges: a paragraph's ragged
    end meets a chip's by chance (the recipe's subtitle and `SERVES 4`)."""
    return (abs(a.left - b.left) <= ALIGNED
            or abs((a.left + a.right) - (b.left + b.right)) / 2 <= ALIGNED)


def _between(upper: BBox, lower: BBox, others: Sequence[Region]) -> bool:
    """Whether another region lies between two, across their column."""
    for other in others:
        middle = (other.box.top + other.box.bottom) / 2
        if upper.bottom <= middle <= lower.top and (
                _across(other.box, upper) > 0 or _across(other.box, lower) > 0):
            return True
    return False


def groups_of(regions: Sequence[Region], boxes: Sequence[BBox]) -> list[list[Region]]:
    """The regions grouped into what becomes one Zone each, in the
    parser's order of each group's first region. See the module's
    docstring for the rules."""
    held, alone = _containers(regions, boxes)
    line = line_height(regions)
    groups: list[list[Region]] = []
    stacks: dict[BBox | None, list[list[Region]]] = {}
    for region in sorted(regions, key=lambda r: (r.box.top, r.box.left)):
        if not region.text_like or region.index in alone:
            groups.append([region])
            continue
        box = held.get(region.index)
        if box is not None and box.right - box.left <= CARD:
            # A card is one Zone, whatever its gaps: its frame and fill are
            # one box, and split per Zone each part is drawn a box of its own.
            if box not in stacks:
                stacks[box] = [[]]
                groups.append(stacks[box][0])
            stacks[box][0].append(region)
            continue
        best = None
        # A heading begins a block: it opens a stack and never joins one.
        for stack in [] if region.label in TITLES else stacks.setdefault(box, []):
            last = stack[-1]
            gap = region.box.top - last.box.bottom
            reach = HEADING_GAP if last.label in TITLES and len(stack) == 1 else STACK_GAP
            if (last.role is region.role and -0.5 * line <= gap <= reach * line
                    and _aligned(last.box, region.box)
                    and not _between(last.box, region.box,
                                     [r for r in regions if r is not last and r is not region])):
                if best is None or gap < best[0]:
                    best = (gap, stack)
        if best is not None:
            best[1].append(region)
        else:
            stacks.setdefault(box, []).append([region])
            groups.append(stacks[box][-1])
    return sorted(groups, key=lambda g: min(r.index for r in g))


# ---- one Zone -----------------------------------------------------------------

def _printed_lines(group: Sequence[Region]) -> list[list[Region]]:
    """A group's regions by the printed line they sit on, top to bottom,
    each line left to right."""
    lines: list[list[Region]] = []
    for region in sorted(group, key=lambda r: (r.box.top, r.box.left)):
        for line in lines:
            if all(_one_line(region.box, other.box) for other in line):
                line.append(region)
                break
        else:
            lines.append([region])
    return [sorted(line, key=lambda r: r.box.left) for line in lines]


def _blocks(line: Sequence[Region]) -> list[Block]:
    """The Blocks of one printed line: fragments side by side are one Block,
    a Cell each; a region of several lines keeps them as the page sets them
    (the reader joins a paragraph's wrapped lines itself, so a line end in
    its text is one the page sets)."""
    if len(line) > 1 and all(len(r.lines) == 1 for r in line):
        return [Block(kind="paragraph", lines=[_cell(r.lines[0], r.box) for r in line])]
    out = []
    for region in line:
        lines = region.lines
        if region.label in TITLES:
            out.append(Block(kind="heading", lines=[_cell(" ".join(lines), region.box)]))
        elif lines and all(BULLET.match(text) for text in lines):
            out += [Block(kind="item", lines=[_cell(BULLET.sub("", text))]) for text in lines]
        elif len(lines) > 1:
            out.append(Block(kind="address", lines=[_cell(text) for text in lines]))
        elif lines:
            out.append(Block(kind="paragraph", lines=[_cell(lines[0], region.box)]))
    return out


def zone_of(group: Sequence[Region]) -> Zone:
    """One group's Zone, the box of all it holds."""
    first = group[0]
    box = _union([r.box for r in group])
    role = first.role if all(r.role is first.role for r in group) else Role.BODY
    if first.label in FIGURES:
        return Zone(kind=Kind.FIGURE, role=role, bbox=box, complete=True,
                    graphic_kind="chart" if first.label == "chart" else "logo")
    if first.label == "table" and "<t" in first.content:
        return Zone(kind=Kind.TABLE, role=role, bbox=box, complete=True,
                    rows=rows_of(first.content))
    if first.label in FORMULAS or first.label == "table":
        return Zone(kind=Kind.PROSE, role=role, bbox=box, complete=True,
                    blocks=[Block(kind="address", lines=[_cell(t) for t in first.lines])])
    blocks = [block for line in _printed_lines(group) for block in _blocks(line)]
    title = None
    if len(blocks) > 1 and blocks[0].kind == "heading":
        title = blocks.pop(0).lines[0].text
    kind = Kind.LIST if blocks and all(b.kind == "item" for b in blocks) else Kind.PROSE
    return Zone(kind=kind, role=role, bbox=box, title=title, blocks=blocks, complete=True)


def _titled(zones: list[Zone], line: float) -> list[Zone]:
    """A heading standing alone right above a table, across it, is the
    table's Title, and the table's box reaches up to it. Found by where the
    two sit, not by their order: the payslip's EARNINGS is followed in the
    reading order by the block beside it, then by its table."""
    heads = [z for z in zones if z.kind is Kind.PROSE and z.title is None and z.bbox
             and len(z.blocks) == 1 and z.blocks[0].kind == "heading"]
    taken: set[int] = set()
    for heading in heads:
        assert heading.bbox is not None
        below = [z for z in zones if z.kind is Kind.TABLE and z.title is None and z.bbox
                 and 0 <= z.bbox.top - heading.bbox.bottom <= HEADING_GAP * line
                 and _across(heading.bbox, z.bbox) >= 0.5]
        if below:
            table = min(below, key=lambda z: z.bbox.top)  # type: ignore[union-attr]
            assert table.bbox is not None
            table.title = heading.blocks[0].lines[0].text
            table.bbox = _union([heading.bbox, table.bbox])
            taken.add(id(heading))
    return [z for z in zones if id(z) not in taken]


def _inset(box: BBox, line: float) -> BBox:
    """A box drawn in by up to half a line top and bottom, for banding only.
    The layout model's boxes are generous, and a sliver of overlap put the
    lab report's header block, its table and the block beside it in one
    Band (`wire.bands_from_boxes` met the same hair from the detector)."""
    by = min(0.5 * line, 0.25 * (box.bottom - box.top))
    return BBox(box.left, box.top + by, box.right, box.bottom - by)


def document_of(raw: Sequence[Mapping[str, Any]], source: Source,
                containers: Sequence[BBox] = ()) -> Document:
    """The page as the IR: the parser's regions grouped into Zones, their
    Bands and columns worked out from the boxes (`wire.bands_from_boxes`)."""
    regions = regions_of(raw)
    line = line_height(regions)
    zones = _titled([zone_of(group) for group in groups_of(regions, containers)], line)
    for zone, (band, column) in zip(zones, bands_from_boxes(
            [_inset(z.bbox, line) for z in zones if z.bbox is not None])):
        zone.band, zone.column = band, column
    return Document(source=source, zones=zones)
