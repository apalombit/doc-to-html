"""Raised marks — spec 0019, B2.

**What the IR could not say.** A footnote or affiliation mark is printed
small and raised after its word. `paper_0018`'s model reads `Solberg¹`,
`Achterberg²` and `common.¹` as Unicode superscripts, drawn inline as
part of the word and scored as `solberg1`; `report_0011`'s drops two marks,
`side by side.¹` and `basin.²`, and sets the third apart as a line of its
own, `3`, drawn `2027. 3`.

**(i) A superscript character is its own Run**, kind `sup`, so it is
drawn raised and apart from its word. The characters are not changed.

**(ii) A mark the reading dropped or set apart is read off the page.** A
small raised glyph after a word: on its line, its bottom above the
baseline by half an x-height or more, its top above the x-height, as tall
as a small letter or more and no taller than `TALL` of the line's tallest
letters. Read on its own crop, digits only, it is a mark where tesseract is
sure of it (`locate.CONFIDENT`), or where the line the reading set apart
right after it holds only digits — the model's own reading of it. That
line then folds into the line before it.

**Measured, 2026-10-20.** The spec bounds a mark at under 0.7 of the
line's x-height; the corpus's marks are 0.8-1.2 of it — `report_0011`'s 7px
on an x-height of 6, `paper_0018`'s 5-6px on 6 — and 0.67-0.78 of the
line's tallest letters. Over the twenty-one pages, the glyphs of that shape
are `report_0011`'s three marks, read `1`, `2`, `3` at 66-79, and nine
others: Greek accents, a pound sign's bar, paper's marks already read and a
two-column line's neighbour, each read under 60 or not after a word or not
the last ink on its line.

**Only at the end of a line's text.** Each of the corpus's dropped marks
ends its paragraph, so a mark joins the Cell only where it is the last ink
on the Cell's last printed line. A mark inside a line would need the word
under it read and matched, which nothing here measures.

**Never a word the page does not print.** The one character added is the
digit read off the page's own glyph; a Cell already holding a mark is left
as it is, so a second reading adds nothing.
"""

from __future__ import annotations

import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Iterator

import numpy as np

from .ir import Cell, Document, Reading, Run, Zone
from .locate import CONFIDENT, TESSERACT, available
from .preprocess import _cv2

ImageArray = np.ndarray

RAISED = 0.5
"""How far above the baseline, in x-heights, a glyph's bottom must sit to
be raised. An `i`'s dot sits higher, and is too small to be a mark."""

SMALL = 0.75
"""How tall, in x-heights, a mark is at least: an apostrophe, a quote or a
degree sign is less — `menu_0012`'s raised comma 4px on 4 sat at 1.0, but
was read as no digit."""

TALL = 0.8
"""How tall, as a share of the line's tallest letters, a mark is at most:
`report_0011`'s 7 on 9-10, `paper_0018`'s 5-6 on 8-9."""

BESIDE = 0.5
"""How near, in x-heights, the mark stands to the glyph before it: it is
set against its word, where a word starts a space further on."""

SCALE = 6
"""How much a mark's crop is enlarged to be read: 7px to 42, near
`locate.TARGET_GLYPH`."""

MARGIN = 2.0
"""How far, in x-heights, past a Cell's box its mark may stand: `locate`
places a line from tesseract's words, and the mark may be no word to it."""


def superscript(character: str) -> bool:
    """A superscript digit or sign, `¹` or `⁺` — not a letter: `™` and `ª`
    are drawn raised already, and are words."""
    decomposition = unicodedata.decomposition(character)
    if not decomposition.startswith("<super>"):
        return False
    base = chr(int(decomposition.split()[1], 16))
    return not base.isalpha()


def split(runs: list[Run]) -> list[Run]:
    """(i): each stretch of superscript characters its own `sup` Run, every
    other stretch kept in the Run it was in. The characters are the same."""
    out: list[Run] = []
    for run in runs:
        if run.kind != "text":
            out.append(run)
            continue
        start = 0
        for at in range(1, len(run.text) + 1):
            if (at == len(run.text)
                    or superscript(run.text[at]) != superscript(run.text[start])):
                part = run.text[start:at]
                out.append(Run(text=part, kind="sup" if superscript(part[0]) else "text"))
                start = at
    return out


def _cells(zone: Zone) -> Iterator[Cell]:
    for row in zone.rows:
        for cell in row.cells:
            yield cell
            yield from cell.below
    for pair in zone.pairs:
        yield pair.label
        yield pair.value
    for block in list(zone.blocks) + list(zone.extra):
        yield from block.lines


def _marked(cell: Cell, runs: list[Run]) -> None:
    """Set the Cell's runs, the text unchanged."""
    reading = cell.readings[0]
    cell.readings[0] = Reading(engine=reading.engine, text=reading.text,
                               model=reading.model,
                               prompt_version=reading.prompt_version, runs=runs)


def read(image: ImageArray | None, document: Document) -> int:
    """Mark every superscript, and read the marks the reading lost.
    Returns how many marks (ii) added. `image` is `Rectified.plain`, or None
    to do (i) alone."""
    for zone in document.zones:
        for cell in _cells(zone):
            if not cell.readings or not any(superscript(c) for c in cell.text):
                continue
            runs = split(cell.runs)
            if runs != cell.runs:
                _marked(cell, runs)
    if image is None or not available():
        return 0
    added = 0
    for zone in document.zones:
        for block in list(zone.blocks) + list(zone.extra):
            kept: list[Cell] = []
            skip = False
            for at, line in enumerate(block.lines):
                if skip:
                    skip = False
                    continue
                kept.append(line)
                apart = block.lines[at + 1] if at + 1 < len(block.lines) else None
                digit = _dropped(image, line, apart)
                if digit is None:
                    continue
                reading = line.readings[0]
                line.readings[0] = Reading(
                    engine=reading.engine, text=reading.text + digit, model=reading.model,
                    prompt_version=reading.prompt_version,
                    runs=[*line.runs, Run(text=digit, kind="sup")])
                added += 1
                skip = apart is not None and apart.text.strip() == digit
            block.lines = kept
    return added


def _dropped(image: ImageArray, line: Cell, apart: Cell | None) -> str | None:
    """The digit of a mark printed at the end of `line` that its reading
    does not hold, or None."""
    if (line.bbox is None or not line.readings or not line.text.strip()
            or any(run.kind == "sup" for run in line.runs)):
        return None
    glyph = _last_raised(image, line)
    if glyph is None:
        return None
    read_, sure = _read_digits(glyph)
    told = apart.text.strip() if apart is not None else ""
    if told.isdigit() and (not read_ or read_ == told):
        return told
    return read_ if read_ and sure >= CONFIDENT else None


def _last_raised(image: ImageArray, line: Cell) -> ImageArray | None:
    """The crop of a small raised glyph that is the last ink on the Cell's
    last printed line, set against the glyph before it — dark on light, as
    tesseract reads it — or None."""
    cv2 = _cv2()
    assert line.bbox is not None
    height, width = image.shape[:2]
    box = line.bbox
    top = max(0, int(box.top * height) - 3)
    bottom = min(height, int(np.ceil(box.bottom * height)) + 3)
    left = max(0, int(box.left * width) - 2)
    edge = int(np.ceil(box.right * width))

    def ink_of(right: int) -> tuple[ImageArray, ImageArray, int, np.ndarray]:
        pixels = image[top:bottom, left:right]
        grey = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY) if pixels.ndim == 3 else pixels
        threshold, _ = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if float((grey <= threshold).mean()) > 0.5:
            grey, threshold = 255 - grey, 255 - threshold
        ink = (grey <= threshold).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        return grey, ink, count, stats

    if edge - left < 2 or bottom - top < 2:
        return None
    # The last printed line inside the Cell's own box; then the box widened
    # by a few x-heights of that line, where a mark no word holds may stand.
    _, ink, count, stats = ink_of(edge)
    measured = None
    for band in reversed(_bands(ink)):
        if (measured := _measured(stats, count, band)) is not None:
            break
    if measured is None:
        return None
    grey, ink, count, stats = ink_of(min(width, edge + int(MARGIN * measured[1])))
    (start, end), x_height, base, tallest = measured
    mine = [tuple(int(v) for v in stats[i][:4]) for i in range(1, count)
            if stats[i][4] >= 2 and start <= stats[i][1] + stats[i][3] / 2 < end]
    last = max(mine, key=lambda c: c[0] + c[2])
    x, y, w, h = last
    if not (base - (y + h) >= RAISED * x_height and y <= base - x_height
            and SMALL * x_height <= h <= TALL * tallest):
        return None
    before = [c for c in mine if c is not last and c[0] + c[2] <= x + 1
              and abs(c[1] + c[3] - base) <= 1]
    if not before or x - max(c[0] + c[2] for c in before) > BESIDE * x_height:
        return None
    if any(c is not last and c[0] + c[2] > x + 1 for c in mine):
        return None
    pad = 2
    return grey[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]


def _bands(ink: ImageArray) -> list[tuple[int, int]]:
    """A crop's printed lines, as runs of rows holding ink."""
    rows = list(ink.sum(axis=1) > 0) + [False]
    bands, start = [], None
    for y, inked in enumerate(rows):
        if inked and start is None:
            start = y
        elif not inked and start is not None:
            bands.append((start, y))
            start = None
    return bands


def _measured(stats: np.ndarray, count: int, band: tuple[int, int]
              ) -> tuple[tuple[int, int], float, float, float] | None:
    """A printed line's rows, x-height, baseline and tallest letters, from
    the glyphs whose middles lie in it; None for a band of too few."""
    start, end = band
    mine = [stats[i] for i in range(1, count)
            if stats[i][4] >= 2 and start <= stats[i][1] + stats[i][3] / 2 < end]
    if len(mine) < 4:
        return None
    base = float(np.median([s[1] + s[3] for s in mine]))
    sitting = [int(s[3]) for s in mine if abs(s[1] + s[3] - base) <= 1]
    if not sitting:
        return None
    small = [h for h in sitting if h <= np.percentile(sitting, 60)]
    return band, float(np.median(small)), base, float(np.percentile(sitting, 90))


def _read_digits(crop: ImageArray) -> tuple[str, float]:
    """The digits tesseract reads in one mark's crop, and how sure it is."""
    cv2 = _cv2()
    big = cv2.resize(crop, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "mark.png"
        cv2.imwrite(str(path), big)
        out = subprocess.run(
            ["env", "OMP_THREAD_LIMIT=1", TESSERACT, str(path), "stdout", "--psm", "8",
             "-c", "tessedit_char_whitelist=0123456789", "tsv"],
            capture_output=True, text=True, check=False).stdout
    for row in out.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) >= 12 and cols[11].strip().isdigit():
            return cols[11].strip(), float(cols[10])
    return "", 0.0
