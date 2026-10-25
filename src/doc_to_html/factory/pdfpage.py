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
pixels. Both are then grouped into lines by the same `lines`:
- a word joins a row when its middle lies inside the row's band;
- a row is cut wherever the gap between two words exceeds `GAP_EM` times
  their size, which is where a column, a cell or a tab stop begins.

A line is therefore a run of words a reader reads together, on both sides
alike.

**The gate**, all three or the page is not admitted:
- *words*: the twin's words equal the text layer's, as a multiset, after
  `normalise` (NFKC, which unfolds ligatures; soft hyphens dropped;
  case folded, as the scorer folds it);
- *lines*: every PDF line's word sequence is one line of the twin;
- *geometry*: each matched line's top and left lie within `GEOMETRY` of
  the page's width of the PDF's.

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
GEOMETRY = 0.015
WIDTH = 1000
"""The width a page is rendered at, unless its card says otherwise; the
spec allows 900–1100."""


@dataclass(frozen=True)
class Word:
    """One word with its box, in the render's pixels, and its type size."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float


@dataclass(frozen=True)
class Line:
    """Words a reader reads together, left to right."""

    words: tuple[str, ...]
    left: float
    top: float
    right: float
    bottom: float

    def key(self) -> tuple[str, ...]:
        return tuple(normalise(word) for word in self.words)


def normalise(text: str) -> str:
    """A word as the gate compares it."""
    folded = unicodedata.normalize("NFKC", text).replace("­", "")
    return " ".join(folded.split()).casefold()


def lines(words: Sequence[Word]) -> list[Line]:
    """Words grouped into rows by their bands, rows cut at wide gaps."""
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        middle = (word.top + word.bottom) / 2
        for row in rows:
            top = min(w.top for w in row)
            bottom = max(w.bottom for w in row)
            if top <= middle <= bottom:
                row.append(word)
                break
        else:
            rows.append([word])
    found: list[Line] = []
    for row in rows:
        row.sort(key=lambda w: w.x0)
        run = [row[0]]
        for word in row[1:]:
            gap = word.x0 - run[-1].x1
            if gap > GAP_EM * max(word.size, run[-1].size):
                found.append(_line(run))
                run = [word]
            else:
                run.append(word)
        found.append(_line(run))
    return sorted(found, key=lambda line: (line.top, line.left))


def _line(words: Sequence[Word]) -> Line:
    return Line(tuple(w.text for w in words), min(w.x0 for w in words),
                min(w.top for w in words), max(w.x1 for w in words),
                max(w.bottom for w in words))


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
        return [Word(w["text"], w["x0"] * scale, w["top"] * scale, w["x1"] * scale,
                     w["bottom"] * scale, float(w.get("size", 10.0)) * scale)
                for w in page.extract_words(extra_attrs=["size"])
                if w["text"].strip()]


def pdf_faces(pdf: Path) -> Counter[str]:
    """Characters per font in the text layer, subset prefixes dropped."""
    import pdfplumber

    with pdfplumber.open(str(pdf)) as document:
        return Counter(char["fontname"].split("+")[-1] for char in document.pages[0].chars)


_WORDS = r"""
(() => {
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE']);
  const words = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName)) continue;
    const size = parseFloat(getComputedStyle(parent).fontSize);
    const text = node.textContent;
    const pattern = /\S+/g;
    let match;
    while ((match = pattern.exec(text))) {
      const range = document.createRange();
      range.setStart(node, match.index);
      range.setEnd(node, match.index + match[0].length);
      const rect = range.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      words.push([match[0], rect.left, rect.top, rect.right, rect.bottom, size]);
    }
  }
  return words;
})()
"""


def twin_words(html: str, width: int) -> list[Word]:
    """The twin's words as the browser lays them out at `width`."""
    found: list[list[Any]] = browser.evaluate(html, _WORDS, width=width)
    return [Word(str(t), float(a), float(b), float(c), float(d), float(s))
            for t, a, b, c, d, s in found]


@dataclass
class Gate:
    """What the gate found between a PDF page and its twin."""

    failures: dict[str, list[str]] = field(default_factory=dict)
    lines: int = 0
    matched: int = 0
    worst_top: float = 0.0
    worst_left: float = 0.0

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, check: str, message: str) -> None:
        self.failures.setdefault(check, []).append(message)


def gate(pdf_lines: Sequence[Line], twin_lines: Sequence[Line], width: int) -> Gate:
    """The three tests of §P, step 6."""
    result = Gate(lines=len(pdf_lines))
    pdf_bag = Counter(word for line in pdf_lines for word in line.key())
    twin_bag = Counter(word for line in twin_lines for word in line.key())
    for word, count in sorted((pdf_bag - twin_bag).items()):
        result.fail("words", f"the twin lacks {word!r}" + (f" ×{count}" if count > 1 else ""))
    for word, count in sorted((twin_bag - pdf_bag).items()):
        result.fail("words", f"the twin adds {word!r}" + (f" ×{count}" if count > 1 else ""))

    tolerance = GEOMETRY * width
    unused = list(twin_lines)
    for line in pdf_lines:
        same = [other for other in unused if other.key() == line.key()]
        if not same:
            result.fail("lines", f"no twin line reads {' '.join(line.words)[:60]!r} "
                                 f"(at {line.left:.0f},{line.top:.0f})")
            continue
        nearest = min(same, key=lambda o: abs(o.top - line.top) + abs(o.left - line.left))
        unused.remove(nearest)
        result.matched += 1
        off_top, off_left = abs(nearest.top - line.top), abs(nearest.left - line.left)
        result.worst_top = max(result.worst_top, off_top)
        result.worst_left = max(result.worst_left, off_left)
        if off_top > tolerance or off_left > tolerance:
            result.fail("geometry", f"{' '.join(line.words)[:40]!r} is {off_left:.0f} px "
                                    f"across and {off_top:.0f} px down from the PDF's")
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
