"""Real PDF pages, and the gate that keeps them honest — spec 0020 §P.

**What a PDF page is in the corpus.** Its picture is the PDF's own render,
so the converter meets real typography. Its ground truth is an HTML
**twin** that redraws the page: the words, lines and structure the scorer
reads. A twin is admitted only through `gate`, so a real page never
misleads development. (Unrelated to `tools/twins.py`'s photographed
copies, spec 0018.)

**The PDF is never edited.** `one_page` copies a single page out of its
source into `corpus/pdf/<id>.pdf`; `render` draws it; `pdf_words` reads its
text layer. Only the twin is revised.

**One function, both sides.** The PDF's words come from pdfplumber and the
twin's from the browser, each word with its box and size in the render's
pixels. Both are then grouped the same way, by `rows`:
- a word joins a row when its middle lies inside the row's band;
- a row's *pieces* begin wherever the gap between two words exceeds
  `GAP_EM` times their size; where a column, a cell or a tab stop
  begins, the gap exceeds `MERGE_EM` times it.

**The text is compared as a reader reads it, not as the text layer spells
it.** A text layer gets white space wrong more often than not, and the
pilot found it on five of its first seven pages: HMRC's form holds
`Whenyoumakeaclaimasanindividual,`, LaTeX's captions run their words
together, Brazil's form reads `1.IDENTIFICAÇÃO` and `P esquisa`, and
accents come apart (`Brynjarsd´ottir`, `λˆ`). A twin that copied those
would mark a converter wrong for reading the picture right. So `normalise`
drops all white space, accents and accent marks and format characters,
and unfolds compatibility forms (ligatures, 𝔼); the twin spaces its words
as the picture shows them.

**The gate**, all three or the page is not admitted:
- *words*: the twin's characters equal the text layer's, as a multiset,
  after `normalise` — text set at an angle included, which takes part in
  this test only (`turned`);
- *rows*: every PDF row's text is one row of the twin. Within it, the
  twin must break wherever the PDF has a gap wider than `MERGE_EM`, and
  may keep or break a narrower one: a justified line's wide word spaces,
  or column heads the text layer runs together;
- *geometry*: each matched row's top, and the left of each of the twin's
  pieces, lie within `GEOMETRY` of the page's width of where the PDF
  sets the same text.

**Rendering.** pypdfium2 draws the page content without annotations or
form widgets: neither is in the text layer pdfplumber reads, so a picture
that showed them would show words the ground truth lacks.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from doc_to_html.factory import browser

GAP_EM = 1.5
MERGE_EM = 3.0
GEOMETRY = 0.015
WIDTH = 1000
"""The width a page is rendered at, unless its card says otherwise; the
spec allows 900–1100."""


@dataclass(frozen=True)
class Word:
    """One word with its box, in the render's pixels, and its type size.
    A word set at an angle is not `upright`; see `turned`."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float
    upright: bool = True


_DROPPED = frozenset({"Mn", "Me", "Lm", "Sk", "Cf", "Cc", "Zs", "Zl", "Zp"})
"""Unicode categories the gate ignores: combining marks, accent and
modifier marks, format characters (soft hyphen, zero-width space),
controls and white space."""


def normalise(text: str) -> str:
    """Text as the gate compares it: compatibility forms unfolded, then
    every character of `_DROPPED` taken out, case folded."""
    return "".join(char for char in unicodedata.normalize("NFKD", text)
                   if unicodedata.category(char) not in _DROPPED).casefold()


def _bands(words: Sequence[Word]) -> list[list[Word]]:
    """Upright words grouped into rows by their bands, each left to right."""
    rows: list[list[Word]] = []
    for word in sorted((w for w in words if w.upright), key=lambda w: (w.top, w.x0)):
        middle = (word.top + word.bottom) / 2
        for row in rows:
            top = min(w.top for w in row)
            bottom = max(w.bottom for w in row)
            if top <= middle <= bottom:
                row.append(word)
                break
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


@dataclass(frozen=True)
class Row:
    """One band of words, its text run together as the gate compares it.

    `starts` are the offsets in `text` where a piece begins (a gap over
    `GAP_EM`), and `wide` those after a gap over `MERGE_EM`. `spans` is
    each word's box with the offsets its text covers."""

    text: str
    shown: str
    left: float
    top: float
    starts: tuple[int, ...]
    wide: frozenset[int]
    spans: tuple[tuple[int, int, float, float], ...]

    def x_at(self, offset: int) -> float:
        """Where the character at `offset` begins, along its word's box."""
        for start, end, x0, x1 in self.spans:
            if start <= offset < end:
                return x0 + (x1 - x0) * (offset - start) / (end - start)
        return self.spans[-1][3] if self.spans else self.left

    def piece(self, offset: int) -> str:
        later = [start for start in self.starts if start > offset]
        return self.text[offset:min(later) if later else len(self.text)]


def rows(words: Sequence[Word]) -> list[Row]:
    """Words grouped into rows, both sides alike; rows with no text that
    `normalise` keeps are left out."""
    found: list[Row] = []
    for band in _bands(words):
        text = ""
        spans: list[tuple[int, int, float, float]] = []
        starts: list[int] = []
        wide: set[int] = set()
        previous: Word | None = None
        pending = 0.0
        for word in band:
            gap = 0.0 if previous is None else word.x0 - previous.x1
            size = word.size if previous is None else max(word.size, previous.size)
            pending = max(pending, gap / size if size else 0.0)
            previous = word
            folded = normalise(word.text)
            if not folded:
                continue
            offset = len(text)
            if not starts or pending > GAP_EM:
                starts.append(offset)
            if starts and offset and pending > MERGE_EM:
                wide.add(offset)
            pending = 0.0
            spans.append((offset, offset + len(folded), word.x0, word.x1))
            text += folded
        if text:
            found.append(Row(text, " ".join(w.text for w in band), band[0].x0,
                             min(w.top for w in band), tuple(starts), frozenset(wide),
                             tuple(spans)))
    return sorted(found, key=lambda row: (row.top, row.left))


def turned(words: Sequence[Word]) -> str:
    """The text set at an angle, run together in the order it comes.

    A margin's rotated line (BOE's `cve: BOE-A-2025-6771 Verificable en
    https://www.boe.es`, the W-9's `Print or type.`) has no rows a
    horizontal reading can compare: its words' boxes stand on end and
    interleave with the rows beside them. So it is compared by its
    characters alone, and never by rows or geometry."""
    return "".join(w.text for w in words if not w.upright)


def listing(words: Sequence[Word]) -> list[str]:
    """The rows as a twin's writer works from them: each row's top and
    height, then its pieces as the text layer spells them, each at its
    left. `‖` comes before a piece the twin must set apart (a gap over
    `MERGE_EM`), `|` before one it may run on or set apart."""
    found: list[tuple[float, float, str]] = []
    for band in _bands(words):
        top = min(w.top for w in band)
        height = max(w.bottom for w in band) - top
        text = f"{band[0].x0:.0f} {band[0].text}"
        for previous, word in zip(band, band[1:]):
            ratio = (word.x0 - previous.x1) / max(word.size, previous.size, 1e-9)
            if ratio > MERGE_EM:
                text += f"  ‖ {word.x0:.0f} {word.text}"
            elif ratio > GAP_EM:
                text += f"  | {word.x0:.0f} {word.text}"
            else:
                text += f" {word.text}"
        found.append((top, band[0].x0, f"{top:7.1f} {height:5.1f}  {text}"))
    return [line for _, _, line in sorted(found)]


def one_page(source: Path, page: int, target: Path) -> None:
    """Copy page `page` (1-based) of `source` into a one-page PDF."""
    import pypdfium2 as pdfium

    whole = pdfium.PdfDocument(str(source))
    single = pdfium.PdfDocument.new()
    single.import_pages(whole, [page - 1])
    target.parent.mkdir(parents=True, exist_ok=True)
    single.save(str(target))


def page_size(pdf: Path) -> tuple[float, float]:
    import pypdfium2 as pdfium

    width, height = pdfium.PdfDocument(str(pdf))[0].get_size()
    return float(width), float(height)


def render(pdf: Path, width: int, target: Path) -> tuple[int, int]:
    """Draw the page `width` pixels wide; the picture the converter sees."""
    import pypdfium2 as pdfium

    page = pdfium.PdfDocument(str(pdf))[0]
    points, _ = page.get_size()
    image = page.render(scale=width / points, draw_annots=False,
                        may_draw_forms=False).to_pil().convert("RGB")
    if image.width != width:
        from PIL import Image

        image = image.resize((width, round(image.height * width / image.width)),
                             Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return image.width, image.height


def pdf_words(pdf: Path, width: int) -> list[Word]:
    """The text layer's words, scaled into a `width`-pixel render."""
    import pdfplumber

    with pdfplumber.open(str(pdf)) as document:
        page = document.pages[0]
        scale = width / float(page.width)
        found = [Word(w["text"], w["x0"] * scale, w["top"] * scale, w["x1"] * scale,
                      w["bottom"] * scale, float(w.get("size", 10.0)) * scale)
                 for w in page.extract_words(extra_attrs=["size"])
                 if w["text"].strip() and w["upright"]]
        # pdfplumber spells a turned word's letters in the order of its
        # boxes (`5202` for 2025), so a turned run is taken a character at
        # a time, in the order the page sets them.
        found += [Word(c["text"], c["x0"] * scale, c["top"] * scale, c["x1"] * scale,
                       c["bottom"] * scale, float(c["size"]) * scale, upright=False)
                  for c in page.chars if not c["upright"] and c["text"]]
        return found


def pdf_faces(pdf: Path) -> Counter[str]:
    """Characters per font in the text layer, subset prefixes dropped."""
    import pdfplumber

    with pdfplumber.open(str(pdf)) as document:
        return Counter(char["fontname"].split("+")[-1] for char in document.pages[0].chars)


_WORDS = r"""
(() => {
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE']);
  function turned(element) {
    for (let e = element; e; e = e.parentElement) {
      const style = getComputedStyle(e);
      if (style.writingMode.startsWith('vertical') || style.writingMode.startsWith('sideways')) {
        return true;
      }
      if (style.rotate && style.rotate !== 'none' && parseFloat(style.rotate) % 360 !== 0) {
        return true;
      }
      const matrix = style.transform.match(/^matrix\(([^)]*)\)$/);
      if (matrix && Math.abs(parseFloat(matrix[1].split(',')[1])) > 0.01) return true;
      if (style.transform.startsWith('matrix3d')) return true;
    }
    return false;
  }
  const words = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName)) continue;
    const size = parseFloat(getComputedStyle(parent).fontSize);
    const upright = !turned(parent);
    const text = node.textContent;
    const pattern = /\S+/g;
    let match;
    while ((match = pattern.exec(text))) {
      const range = document.createRange();
      range.setStart(node, match.index);
      range.setEnd(node, match.index + match[0].length);
      const rect = range.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      words.push([match[0], rect.left, rect.top, rect.right, rect.bottom, size, upright]);
    }
  }
  return words;
})()
"""


def twin_words(html: str, width: int) -> list[Word]:
    """The twin's words as the browser lays them out at `width`."""
    found: list[list[Any]] = browser.evaluate(html, _WORDS, width=width)
    return [Word(str(t), float(a), float(b), float(c), float(d), float(s), bool(u))
            for t, a, b, c, d, s, u in found]


_BLOCKS = r"""
(() => {
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE']);
  const isInline = (style) => style.display.startsWith('inline');
  function blockOf(node) {
    let element = node.parentElement;
    while (element && element !== document.body) {
      if (!isInline(getComputedStyle(element))) return element;
      element = element.parentElement;
    }
    return element || document.body;
  }
  const cells = new Map();
  const blocks = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName) || !node.textContent.trim()) continue;
    const block = blockOf(node);
    if (!blocks.has(block)) {
      const cell = block.closest('td, th, li');
      if (cell && !cells.has(cell)) cells.set(cell, cells.size);
      const style = getComputedStyle(block);
      blocks.set(block, {tag: block.tagName.toLowerCase(), cell: cell ? cells.get(cell) : -1,
                         size: parseFloat(style.fontSize), weight: parseInt(style.fontWeight, 10),
                         face: style.fontFamily + (style.fontStyle === 'italic' ? ' italic' : ''),
                         rects: [], text: ''});
    }
    blocks.get(block).text += node.textContent;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      if (rect.width > 0 && rect.height > 0) {
        blocks.get(block).rects.push([rect.left, rect.top, rect.right, rect.bottom]);
      }
    }
  }
  return [...blocks.values()].filter((b) => b.rects.length);
})()
"""


@dataclass(frozen=True)
class TwinBlock:
    """One block of the twin, as the projection takes blocks: the nearest
    ancestor of a text that is not inline. `cell` numbers the table cell
    or list item it lies in (-1 for none); `rows` counts its lines."""

    tag: str
    cell: int
    size: float
    weight: int
    face: str
    left: float
    top: float
    right: float
    rows: int
    text: str = ""


CELLS = frozenset({"td", "th", "li"})
"""Tags that are a block of their own on purpose, one line or not."""


def twin_blocks(html: str, width: int) -> list[TwinBlock]:
    """The twin's blocks in document order, each with its rows counted."""
    found: list[dict[str, Any]] = browser.evaluate(html, _BLOCKS, width=width)
    blocks = []
    for record in found:
        rects = sorted(record["rects"], key=lambda r: r[1])
        tops: list[float] = []
        for rect in rects:
            if not tops or rect[1] - tops[-1] > record["size"] / 2:
                tops.append(rect[1])
        blocks.append(TwinBlock(record["tag"], record["cell"], record["size"],
                                record["weight"], record["face"],
                                min(r[0] for r in rects), min(r[1] for r in rects),
                                max(r[2] for r in rects), len(tops),
                                " ".join(record["text"].split())))
    return blocks


PITCH = 2.0
"""Two one-line blocks set closer than this many times their type size
are lines of one paragraph: a paragraph's line pitch is 1.1–1.7 em, the
gap between paragraphs adds at least half a line."""

MEASURE = 25.0
"""Outside a table cell, a run of one-line blocks is reported only if
every line but its last runs at least this many times its type size: a
line of prose set to its measure. A stack of short lines (an address, a
form's labels, a list of particulars) is a stack of items, and a block
each is a fair reading of it — without this, 42 of the first 200
generated pages were reported."""


def split_paragraphs(blocks: Sequence[TwinBlock]) -> list[str]:
    """Runs of one-line blocks that may be one paragraph cut into lines,
    or one line cut into words.

    A paragraph cut into lines: each block under the last at a line's
    pitch, the same face, size and weight, starting no further right, in
    the same cell (or none) — and, outside a cell, every line but the
    last run to a prose `MEASURE`. A line cut into words: each block on
    the same row as the last, the same face, size and weight, in the same
    cell (or none), after a gap a line may run on (`MERGE_EM`) — what
    a line becomes when its words are placed with `position: absolute`,
    which makes each of them a block. A table cell or a list item is a
    block of its own on purpose and is never counted.

    **A pointer, not a test.** The scorer groups text by its block, so a
    twin that made each line of a paragraph a block would mark a converter
    wrong for keeping the paragraph whole; three of the pilot's first six
    twins did (c0287, c0300, c0406), and a fourth cut a line into words
    (c0073). But a stack of separate items set one long line each reads
    the same to geometry: over the first 200 generated pages the first
    kind reports 12, and every one is footnotes, items or particulars, a
    block each as they should be. Telling them apart is reading the words,
    so each run is listed for whoever reviews the twin, and the gate does
    not fail on it."""
    def alike(one: TwinBlock, other: TwinBlock) -> bool:
        return (other.rows == 1 and other.tag not in CELLS and other.cell == one.cell
                and (other.size, other.weight, other.face) == (one.size, one.weight, one.face))

    def lines(above: TwinBlock, below: TwinBlock) -> bool:
        return (alike(above, below) and 0 < below.top - above.top <= PITCH * below.size
                and below.left <= above.left + 2
                and below.left < above.right and above.left < below.right)

    def words(before: TwinBlock, after: TwinBlock) -> bool:
        return (alike(before, after) and abs(after.top - before.top) <= 2
                and 0 <= after.left - before.right <= MERGE_EM * after.size)

    def paragraph(run: list[TwinBlock]) -> bool:
        return run[0].cell >= 0 or all(b.right - b.left >= MEASURE * b.size for b in run[:-1])

    found: list[str] = []
    for joins, kept, what in [(lines, paragraph, "lines of one paragraph: make them one "
                                                 "block with <br> at each line end"),
                              (words, lambda run: True, "words of one line: set them as "
                                                        "inline text in one block")]:
        run: list[TwinBlock] = []
        for block in [*blocks, None]:
            if block is not None and run and joins(run[-1], block):
                run.append(block)
                continue
            if len(run) >= 2 and kept(run):
                found.append(f"{len(run)} one-line <{run[0].tag}> blocks from "
                             f"{run[0].text[:30]!r} to {run[-1].text[:30]!r} are {what}")
            run = [block] if block is not None and block.rows == 1 \
                and block.tag not in CELLS else []
    return found


@dataclass
class Gate:
    """What the gate found between a PDF page and its twin."""

    failures: dict[str, list[str]] = field(default_factory=dict)
    rows: int = 0
    matched: int = 0
    worst_top: float = 0.0
    worst_left: float = 0.0

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, check: str, message: str) -> None:
        self.failures.setdefault(check, []).append(message)


def _chars(counts: Counter[str]) -> str:
    return ", ".join(f"{char!r}" + (f" ×{n}" if n > 1 else "")
                     for char, n in sorted(counts.items()))[:300]


def gate(pdf_words: Sequence[Word], twin_words: Sequence[Word], width: int) -> Gate:
    """The three tests of §P, step 6, row by row; text set at an angle
    (`turned`) is in the first test only."""
    pdf_rows, twin_rows = rows(pdf_words), rows(twin_words)
    result = Gate(rows=len(pdf_rows))
    pdf_chars = Counter("".join(row.text for row in pdf_rows) + normalise(turned(pdf_words)))
    twin_chars = Counter("".join(row.text for row in twin_rows)
                         + normalise(turned(twin_words)))
    if pdf_chars - twin_chars:
        result.fail("words", f"the twin lacks {_chars(pdf_chars - twin_chars)}")
    if twin_chars - pdf_chars:
        result.fail("words", f"the twin adds {_chars(twin_chars - pdf_chars)}")

    tolerance = GEOMETRY * width
    unused = list(twin_rows)
    for row in pdf_rows:
        same = [other for other in unused if other.text == row.text]
        if not same:
            result.fail("rows", f"no twin row reads {row.shown[:60]!r} "
                                f"(at {row.left:.0f},{row.top:.0f})")
            continue
        twin = min(same, key=lambda o: abs(o.top - row.top) + abs(o.left - row.left))
        unused.remove(twin)
        result.matched += 1
        off_top = abs(twin.top - row.top)
        result.worst_top = max(result.worst_top, off_top)
        if off_top > tolerance:
            result.fail("geometry", f"{row.shown[:40]!r} is {off_top:.0f} px down "
                                    f"from the PDF's")
        for start in twin.starts:
            off_left = abs(twin.x_at(start) - row.x_at(start))
            result.worst_left = max(result.worst_left, off_left)
            if off_left > tolerance:
                result.fail("geometry", f"{twin.piece(start)[:40]!r} begins {off_left:.0f} "
                                        f"px across from the PDF's")
        for start in sorted(row.wide - set(twin.starts)):
            result.fail("rows", f"the twin runs {row.piece(start)[:40]!r} on from what "
                                f"precedes it; the PDF sets it apart, as a column or a cell")
    return result


def source_record(page_id: str, url: str, licence: str, page: int, source: Path,
                  single: Path, note: str = "") -> dict[str, Any]:
    """`corpus/pdf/<id>.source.json`: where the page came from, and under what."""
    return {
        "id": page_id, "url": url, "licence": licence, "page": page,
        "taken": date.today().isoformat(), "note": note,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "page_sha256": hashlib.sha256(single.read_bytes()).hexdigest(),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
