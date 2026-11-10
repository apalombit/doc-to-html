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
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from statistics import median
from typing import Any

from .ir import (BBox, Block, Cell, Document, Kind, Reading, Role, Row, RowRole,
                 Run, Source, Zone)
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

INDENT = 0.05
"""How far in from its column's left edge a block may start, as a share of
the page's width, and still be the column's next block: c0573's sub-items,
0.02 in, each a region of its own. Spec 0024, B."""

_SYMBOLS = {"circ": "°", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "cdot": "·",
            "approx": "≈", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "neq": "≠",
            "ne": "≠", "rightarrow": "→", "to": "→", "leftarrow": "←", "infty": "∞",
            "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ",
            "epsilon": "ε", "varepsilon": "ε", "eta": "η", "theta": "θ", "lambda": "λ",
            "mu": "µ", "nu": "ν", "pi": "π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ",
            "tau": "τ", "phi": "φ", "varphi": "φ", "omega": "ω", "Omega": "Ω",
            "%": "%", "#": "#", "&": "&", "_": "_", "$": "$", "left": "", "right": "",
            ",": "", ";": "", "!": "", "quad": "", "qquad": ""}
"""The commands the reader writes inside maths, as the characters the page
prints. `\\left(` is the bracket alone."""

_FUNCTIONS = ("sin", "cos", "tan", "log", "ln", "exp", "lim", "max", "min")
"""Named functions, set as words: c0404's `n₁ sin θ₁`."""

_TEXT_GROUP = re.compile(r"\\(?:text|mathrm|mathbf|textbf|mathit|textit|operatorname)"
                         r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}")
"""A run of words inside maths: `\\text {w e i g h t}`, `\\mathrm{kg}`."""

_MARKS = {r"\checkmark": "✓", r"\bigcirc": "○", r"\square": "☐", r"\blacksquare": "■",
          r"\times": "×", r"\cdot": "·", r"\bullet": "•", r"\star": "★"}
_SUP = str.maketrans("0123456789+-−()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁽⁾ⁿ")
_SUB = str.maketrans("0123456789+-()", "₀₁₂₃₄₅₆₇₈₉₊₋₍₎")

_OPEN = {"sup": "\ue000", "strong": "\ue002"}
_SHUT = "\ue001"
"""Where a marked run opens and closes inside the text `_marked` returns:
private-use characters, which no reader writes, read back into Runs by
`runs_of`. Spec 0024, A."""

_BOLD = re.compile(r"(?<!\*)\*\*(?=[^\s*])(.+?)(?<=[^\s*])\*\*(?!\*)"
                   r"|<(strong|b)>(.*?)</(?:strong|b)>")
"""Bold as the reader writes it: Markdown's `**year**` (c0024) and HTML's
`<strong>` (c0010's section rows). A `**` with a space on its inner side
is printed, not markup: c0024's Python `2 ** 3 ** 2`; and so is a run of
three stars or more: c0105's `Card:***********4419`."""


def _is_maths(body: str) -> bool:
    """Whether what stands between two `$` is the reader's inline maths:
    it holds a LaTeX sign (`\\`, `^`, `_`, braces), or it is letters alone,
    a variable (paper_0018's `$F$`). Otherwise the two `$` are printed: on
    dev, nine spans between two dollar amounts on five pages (c0075's
    `$250 or $500`, c0275, c0345, c0349, c0434), closed up into one word
    when taken for maths. Spec 0024, A."""
    return bool(re.search(r"[\\^_{}]", body) or re.fullmatch(r"\s*[A-Za-z]+\s*", body))


def _words(group: str, display: bool) -> str:
    """A text group's words, its spaces kept through maths (`\0`): letters
    the reader spaced one by one joined (`\\text {w e i g h t}`,
    `\\mathrm{S p O_{2}}`, c0276's `\\mathrm{kg / m^{3}}`), a space between
    two words or more kept (c0488's `\\mathbf{Star point chart …}`), one at either end kept (`20\\text{ A}`,
    `54 \\mathrm{~m}`); in a display formula a word stands apart."""
    inner = group.replace("~", " ")
    tokens = inner.split()
    # The reader spaces a group's every sign; only words make its spaces real.
    words = [t for t in tokens if len(re.sub(r"[_^](\{[^{}]*\}|\w)|[^A-Za-zÀ-ÿ]", "", t)) >= 2]
    body = " ".join(tokens) if len(words) >= 2 else "".join(tokens)
    lead = " " if inner[:1].isspace() or (display and len(body) > 1) else ""
    trail = " " if inner[-1:].isspace() or (display and len(body) > 1) else ""
    return (lead + body + trail).replace(" ", "\0")


def _maths(body: str, display: bool = False) -> str:
    """Inline or display maths as the characters the page prints."""
    # `\x03` ends a command the words follow: `\\mu\\mathrm{mol}` is µmol.
    body = _TEXT_GROUP.sub(lambda m: "\x03" + _words(m.group(1), display), body)
    body = body.replace("~", "\0")
    body = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "°", body)
    body = re.sub(r"\\(" + "|".join(_FUNCTIONS) + r")(?![A-Za-z])",
                  lambda m: "\0" + m.group(1) + "\0", body)
    body = re.sub(r"\\sqrt\s*\{([^{}]*)\}", lambda m: "\0√" + m.group(1), body)
    body = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", body)
    body = re.sub(r"\\textcircled\s*\{?\s*(\w{1,2})\s*\}?", lambda m: _circled(m.group(1)), body)
    body = re.sub(r"\\([A-Za-z]+|[%#&_$,;!])(?![A-Za-z])",
                  lambda m: _SYMBOLS.get(m.group(1), m.group(0)), body)
    # An unknown command keeps the space that ends it.
    body = re.sub(r"(\\[A-Za-z]+)\s+(?=[A-Za-z])", "\\1\x01", body)
    body = re.sub(r"\s+", "", body).replace("\x01", " ")
    body = re.sub(r"\^\{([^{}]+)\}", lambda m: _raised(m.group(1)), body)
    body = re.sub(r"\^(\w)", lambda m: _raised(m.group(1)), body)
    body = re.sub(r"_\{([^{}]+)\}", lambda m: _lowered(m.group(1)), body)
    body = re.sub(r"_(\w)", lambda m: _lowered(m.group(1)), body)
    body = body.replace("{", "").replace("}", "").replace("\x03", "")
    body = _spaced(body, display)
    # A word's space after it stands after its raised run (`height² (m²)`),
    # and none before a `/` that joins two units (`kg/m²`).
    body = re.sub(r"\0+(\ue000[^\ue001]*\ue001)", "\\1\0", body)
    body = re.sub(r"(?<=[A-Za-z]{2})\0+/", "/", body)
    body = re.sub(r"\0+", " ", body)
    body = re.sub(r"(?<=\()\s+|\s+(?=[),.;:\ue000])", "", body)
    return re.sub(r"\s{2,}", " ", body).strip()


def _spaced(body: str, display: bool) -> str:
    """Maths' relations set apart, as print sets them (`I = 20 A`); in a
    display formula its operators too (c0298's `(M + S) ÷ N = …`), and a
    `/` but between a unit and the next (`kg/m²`). Never inside a raised
    run; an inline `×` or `-` stays where it stands (`×10⁹/L`)."""
    def outside(part: str) -> str:
        if not display:
            return re.sub(r"\s*([=≈≤≥≠])\s*", "\0\\1\0", part)
        part = re.sub(r"\s*([=+−×÷≈≤≥≠→±]|(?<=[\w)\]])-(?=[\w(]))\s*", "\0\\1\0", part)
        return re.sub(r"(?<![A-Za-z]{2})(?<![A-Za-z]{2}\0)/", "\0/\0", part)
    pieces = re.split(r"(\ue000.*?\ue001)", body)
    return "".join(p if p.startswith("\ue000") else outside(p) for p in pieces)


def _glued(before: str, after: str) -> bool:
    """Whether a raised or lowered run is set against what stands before
    it, as a page prints it: against a word always (`CO₂`, `parties¹`);
    against a mark of punctuation unless a sentence follows it, which the
    run then opens (c0364's `controlo.¹` and c0181's `tax)¹`, but c0457's
    `month. ¹ Provisional`); against a currency sign never (c0595's
    `€ HT`). Fitted on dev's sources, 2026-11-10: of 200 raised marks, 113
    printed against a word and 3 apart; after punctuation, 21 against and
    the 4 apart each opening a footnote. Spec 0024, A."""
    if not re.search(r"\S\s+$", before):
        return False
    last = before.rstrip()[-1]
    if last.isalnum():
        return True
    if unicodedata.category(last) == "Sc":
        return False
    return not re.match(r"\s*[A-ZÀ-Þ]", after)


def _dollars(text: str) -> str:
    """Each `$…$` span of the reader's inline maths set as characters
    (`_maths`); every other `$` is printed and stays (`_is_maths`)."""
    out, at = [], 0
    while True:
        opened = text.find("$", at)
        shut = text.find("$", opened + 1) if opened >= 0 else -1
        if shut < 0:
            out.append(text[at:])
            return "".join(out)
        body = text[opened + 1:shut]
        if not _is_maths(body):
            out.append(text[at:opened + 1])
            at = opened + 1
            continue
        before = text[at:opened]
        if body.lstrip()[:1] in ("_", "^") and _glued(before, text[shut + 1:]):
            before = before.rstrip()
        out += [before, _maths(body)]
        at = shut + 1
        # Nor is a mark set apart from the punctuation after it.
        rest = text[at:]
        if re.match(r"\s+[,.;:]", rest):
            at += len(rest) - len(rest.lstrip())


_UNSHUT = re.compile(r"<(strong|b|sup|sub|em|i|u)\s+(?![\w-]+\s*=)")
"""An inline tag the reader opened and never closed, its words taken for
attributes: c0010's `<strong B. Clinic visits</strong>`, two section rows
lost. Spec 0024, A."""


def _tags(text: str) -> str:
    """The reader's HTML with each unclosed inline tag closed (`_UNSHUT`)."""
    return _UNSHUT.sub(r"<\1>", text)


def _marked(text: str) -> str:
    """The reader's text as the page prints it, its raised and bold runs
    marked (`_OPEN`, `_SHUT`).

    It writes a mark inside a line as inline LaTeX (`$200^{\\circ}$`), a
    printed mark it has a name for as a bare command (`\\checkmark`), a
    raised or lowered run as `<sup>`/`<sub>`, and bold as `**…**` or
    `<strong>`. Each is set back as the characters the page prints (200°,
    ✓, H₂), a raised run and a bold run marked as such. Nothing it read is
    dropped; an underline it writes (`<u>`, sample_semantic_0005's links)
    is not drawn."""
    text = _dollars(_tags(text))
    for command, mark in _MARKS.items():
        text = re.sub(re.escape(command) + r"(?![A-Za-z])\s*", mark + " ", text)
    text = re.sub(r"<sup>(.*?)</sup>", lambda m: _raised(m.group(1)), text)
    text = re.sub(r"(?<=\d)\^(\d{1,3})\b", lambda m: _raised(m.group(1)), text)
    text = re.sub(r"<sub>(.*?)</sub>", lambda m: _lowered(m.group(1)), text)
    text = re.sub(r"</?u>", "", text)
    text = _BOLD.sub(lambda m: _OPEN["strong"] + (m.group(1) or m.group(3) or "") + _SHUT,
                     text)
    text = text.replace("（", "(").replace("）", ")")
    return re.sub(r"[ \t]+", " ", text).strip()


def formula(content: str) -> str:
    """A display formula region as the page prints it: the reader writes it
    between `$$` lines, as spaced-out LaTeX (c0232's `B M I = \\text {w e i
    g h t} …`); the page prints `BMI = weight (kg) / …`."""
    body = " ".join(line for line in content.split("\n") if line.strip() not in ("$$", ""))
    body = body.strip().removeprefix("$$").removesuffix("$$").strip("$ ")
    return _maths(body, display=True)


def plain(text: str) -> str:
    """The reader's text as the page prints it (`_marked`), unmarked."""
    return "".join(run.text for run in runs_of(_marked(text)))


def runs_of(marked: str) -> list[Run]:
    """A marked text's Runs: each marked stretch a `sup` or `strong` Run,
    the rest `text`; an empty stretch none. The Runs spell the text."""
    out: list[Run] = []
    opens = {mark: name for name, mark in _OPEN.items()}
    kinds: list[str] = []
    start = 0
    for at, char in enumerate(marked):
        if char in opens or char == _SHUT:
            if marked[start:at]:
                out.append(Run(text=marked[start:at], kind=kinds[-1] if kinds else "text"))
            if char in opens:
                kinds.append(opens[char])
            elif kinds:
                kinds.pop()
            start = at + 1
    if marked[start:]:
        out.append(Run(text=marked[start:], kind=kinds[-1] if kinds else "text"))
    return out


def _circled(mark: str) -> str:
    """`\\textcircled{2}` as ②, `{f}` as ⓕ (c0328): the reader's reading,
    set as the character it names."""
    if mark.isdigit() and 1 <= int(mark) <= 20:
        return chr(0x2460 + int(mark) - 1)
    if len(mark) == 1 and mark.isascii() and mark.isalpha():
        return chr((0x24B6 if mark.isupper() else 0x24D0) + ord(mark.lower()) - ord("a"))
    return mark


def _raised(text: str) -> str:
    """A raised run, marked: as superscript characters where every one has
    one (the page's `¹` is one character to a reader), else as written."""
    out = text.translate(_SUP)
    if not text.strip():
        return text
    return _OPEN["sup"] + (out if all(c != o for c, o in zip(text, out)) else text) + _SHUT


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
        return [line for line in (_marked(part) for part in self.content.split("\n")) if line]


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
    """A Cell of a line `_marked` returned: its words, and its Runs where
    any stretch of it is raised or bold."""
    runs = runs_of(text)
    words = "".join(run.text for run in runs)
    marked = runs if any(run.kind != "text" for run in runs) else []
    return Cell(bbox=box, readings=[Reading(engine=ENGINE, text=words, runs=marked)])


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

INLINE_TAGS = ("sup", "sub", "strong", "b")
"""The tags inside a table cell the reader writes and `_marked` reads:
raised, lowered and bold runs (c0010's section rows are `<strong>`)."""


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
        elif tag in INLINE_TAGS and self.cell is not None:
            self.cell.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "thead":
            self.head = False
        elif tag in INLINE_TAGS and self.cell is not None:
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


def _rejoined(cells: list[tuple[str, int, int, bool]]) -> None:
    """A maths span the reader split at a cell's edge, put back: the cell
    ends on its closing `$` with no opening one, and the next starts on an
    opening `$` with no closing one (c0068's `Lampe L<sub>1}$` beside
    `$1,5`, c0219's `SpO<sub>2}$` beside `$96 % RA`). Each `$` is dropped,
    and the raised or lowered run the first left open is closed."""
    for i in range(len(cells) - 1):
        left, right = cells[i][0].rstrip(), cells[i + 1][0].lstrip()
        if (left.endswith("$") and left.count("$") % 2 and right.startswith("$")
                and right.count("$") % 2):
            left = re.sub(r"<(sub|sup)>([^<{}]*)\}?$", r"<\1>\2</\1>", left[:-1].rstrip())
            left = re.sub(r"_\{([^{}]*)\}$", r"<sub>\1</sub>", left)
            left = re.sub(r"\^\{([^{}]*)\}$", r"<sup>\1</sup>", left)
            cells[i] = (left, *cells[i][1:])
            cells[i + 1] = (right[1:].lstrip(), *cells[i + 1][1:])


def rows_of(content: str) -> list[Row]:
    """A table's rows on the IR's grid: a cell spanning others stands at its
    first slot with its span, and the slots it covers hold empty Cells
    (`Cell.span`, as `render._table` draws it). A row of header cells only
    is a header row. A cell's own line ends are kept: each line after its
    first is one of `Cell.below`."""
    parsed = _Table()
    parsed.feed(_tags(content))
    for cells in parsed.rows:
        _rejoined(cells)
    grid: dict[tuple[int, int], Cell] = {}
    heads: dict[int, bool] = {}
    for r, cells in enumerate(parsed.rows):
        c = 0
        for text, down, across, th in cells:
            while (r, c) in grid:
                c += 1
            lines = [line for line in map(_marked, text.split("\n")) if line]
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


def _follows(stack: Sequence[Region], region: Region,
             others: Sequence[Region] = ()) -> bool:
    """Whether a region continues a stack's column: it starts or centres
    where a block of the stack does (`_aligned`), or it sits inside the
    stack's width, indented no more than `INDENT` (c0573's sub-items, which
    the parser cuts from their items; spec 0024, B).

    **An indented line stands alone on its line in the column.** One
    sharing its line with another region inside the stack's width is the
    first of a row of chips or tabs, not a sub-item: c0257's `9 URGENT`
    beside `27 ROUTINE`, taken into the headline, and the headline drawn
    a word a line beside the chip left over. Over the dev pages' indent
    joins, 6 share their line so and all 6 are chip or tab rows; the 35
    alone on theirs are sub-items, continuations and values."""
    span = _union([r.box for r in stack])
    if any(_aligned(r.box, region.box) for r in stack):
        return True
    return (span.left - ALIGNED <= region.box.left <= span.left + INDENT
            and region.box.right <= span.right + ALIGNED
            and not any(_one_line(region.box, o.box) and o.box.left < span.right
                        and o.box.right > span.left
                        for o in others if o is not region and o not in stack))


def _crosses(stack: Sequence[Region], region: Region, others: Sequence[Region],
             line: float) -> bool:
    """Whether joining a region to a stack would draw the stack over a
    region beside it: c0402's table caption, wider than its column, set
    column 1 across column 2, and the page's gutters were lost. A region
    inside the column's own width is not beside it (c0011's chip rows,
    between its questions), and an overlap the parser's own boxes already
    make is not the join's."""
    before = _union([r.box for r in stack])
    after = _union([before, region.box])

    def over(a: BBox, b: BBox) -> bool:
        return (min(a.bottom, b.bottom) - max(a.top, b.top) > 0.5 * line
                and min(a.right, b.right) - max(a.left, b.left) > ALIGNED)

    def inside(b: BBox) -> bool:
        return b.left >= before.left - ALIGNED and b.right <= before.right + ALIGNED
    return any(over(after, o.box) and not inside(o.box) and not over(before, o.box)
               and not over(region.box, o.box)
               for o in others if o is not region and o not in stack)


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
                    and _follows(stack, region, regions)
                    and not _between(last.box, region.box,
                                     [r for r in regions if r is not last and r is not region])
                    and not _crosses(stack, region, regions, line)):
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
    if first.label in FORMULAS:
        return Zone(kind=Kind.PROSE, role=role, bbox=box, complete=True,
                    blocks=[Block(kind="address", lines=[_cell(formula(first.content))])])
    if first.label == "table":
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
