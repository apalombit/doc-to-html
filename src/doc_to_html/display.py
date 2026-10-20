"""Display lines — spec 0019, B3.

**What the IR could not say.** `paper_0018` sets its equation on a line of
its own inside a paragraph, centred, apart above and below, its number
`(1)` flush right. The model reads `Δh = α √F` and `(1)` as lines of their
own, and the render's reflow joined them into the paragraph:
`…We fitted the relation Δh = α √F (1) where Δh is…`.

**The rule.** A line of a flowing paragraph, with lines of the paragraph
before and after it, is a display line where the page prints it

- **centred** in its column — in the room its number leaves, where it has
  one: each side's margin at least `SIDES` of the column, the two within
  `CENTRED` of it;
- **set apart** above and below — both gaps `APART` times the paragraph's
  own gap between its other lines or more.

A line holding only `(n)`, printed flush right on that line, is its number.
`Cell.display`: `line` and `number`.

**Measured on the ink, not on the line's box.** `locate` cannot place
`Δh = α √F` — tesseract reads no Greek in English — so the display line's
extent is the ink on the printed line it shares with its number, or on its
own box's printed line where it has one. On `paper_0018` it runs 0.231 to
0.291 of the page: the middle 0.261 is the middle of the column's 0.060 to
the number's 0.462 to the third decimal, and its gaps are 2.1 and 2.4 of the
paragraph's 0.0106.

**The corpus, 2026-10-20:** of the twenty-one pages, the one line it marks
is paper's equation. No other page sets a centred line apart inside a
paragraph.
"""

from __future__ import annotations

import re
from statistics import median

import numpy as np

from .ir import BBox, Block, Cell, Document, Kind, Zone
from .preprocess import _cv2

ImageArray = np.ndarray

NUMBER = re.compile(r"\(\d+[a-z]?\)")
"""A display line's number: `(1)`, `(2a)`."""

SIDES = 0.1
"""The least margin, as a share of the column, on each side of a centred
line: a paragraph's lines fill their column, and a full one is centred
trivially."""

CENTRED = 0.05
"""How far apart, as a share of the column, a centred line's two margins
may be."""

APART = 1.5
"""How much wider than the paragraph's own line gap the gaps above and
below a display line are."""

FLUSH = 0.02
"""How near, as a share of the column, a number's right edge stands to the
column's to be flush right."""

FLOWS = ("heading", "address")
"""Block kinds whose lines do not flow, so hold no display line."""


def _ink(image: ImageArray, zone: Zone) -> tuple[ImageArray, int, int]:
    """The Zone's ink, and its crop's origin."""
    cv2 = _cv2()
    assert zone.bbox is not None
    height, width = image.shape[:2]
    top, left = int(zone.bbox.top * height), int(zone.bbox.left * width)
    bottom = int(np.ceil(zone.bbox.bottom * height))
    right = int(np.ceil(zone.bbox.right * width))
    pixels = image[top:bottom, left:right]
    grey = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY) if pixels.ndim == 3 else pixels
    threshold, _ = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = grey <= threshold
    if float(ink.mean()) > 0.5:
        ink = ~ink
    return ink, top, left


def _bands(ink: ImageArray) -> list[tuple[int, int]]:
    """The printed lines, as runs of rows holding ink."""
    rows = list(ink.any(axis=1)) + [False]
    bands, start = [], None
    for y, inked in enumerate(rows):
        if inked and start is None:
            start = y
        elif not inked and start is not None:
            bands.append((start, y))
            start = None
    return bands


def _band_at(bands: list[tuple[int, int]], y: float) -> int | None:
    for index, (start, end) in enumerate(bands):
        if start <= y < end:
            return index
    return None


def _number(lines: list[Cell], at: int, zone: Zone) -> Cell | None:
    """The line after `at` where it is a number set flush right."""
    if at + 1 >= len(lines):
        return None
    number = lines[at + 1]
    assert zone.bbox is not None
    column = zone.bbox.right - zone.bbox.left
    if (NUMBER.fullmatch(number.text.strip()) and number.bbox is not None
            and number.bbox.right >= zone.bbox.right - FLUSH * column):
        return number
    return None


def _displayed(image: ImageArray, zone: Zone, block: Block, at: int,
               number: Cell | None, ink: ImageArray, top: int, left: int,
               bands: list[tuple[int, int]]) -> bool:
    assert zone.bbox is not None
    height, width = image.shape[:2]
    line = block.lines[at]
    anchor: BBox | None = number.bbox if number is not None else line.bbox
    if anchor is None:
        return False
    band = _band_at(bands, (anchor.top + anchor.bottom) / 2 * height - top)
    if band is None or band == 0 or band + 1 >= len(bands):
        return False
    start, end = bands[band]
    room = (int(number.bbox.left * width) - left - 1
            if number is not None and number.bbox is not None else ink.shape[1])
    columns = np.flatnonzero(ink[start:end, :max(0, room)].any(axis=0))
    if columns.size == 0:
        return False
    column = ink.shape[1]
    margin_left, margin_right = int(columns[0]), room - 1 - int(columns[-1])
    if (min(margin_left, margin_right) < SIDES * column
            or abs(margin_left - margin_right) > CENTRED * column):
        return False
    # The paragraph's own gap: between its other printed lines.
    placed = [cell.bbox for cell in block.lines if cell.bbox is not None]
    upper = min(box.top for box in placed) * height - top
    lower = max(box.bottom for box in placed) * height - top
    inside = [k for k, (start_, end_) in enumerate(bands) if end_ > upper and start_ < lower]
    others = [bands[k + 1][0] - bands[k][1] for k in inside[:-1]
              if k not in (band - 1, band)]
    if not others:
        return False
    usual = median(others)
    above = start - bands[band - 1][1]
    below = bands[band + 1][0] - end
    return min(above, below) >= APART * usual


def read(image: ImageArray, document: Document) -> int:
    """Flag every display line and its number. Returns how many lines."""
    found = 0
    for zone in document.zones:
        if zone.bbox is None or zone.kind is Kind.FIGURE:
            continue
        measured: tuple[ImageArray, int, int, list[tuple[int, int]]] | None = None
        for block in zone.blocks:
            if block.kind in FLOWS:
                continue
            for at in range(1, len(block.lines)):
                line = block.lines[at]
                if line.display is not None or NUMBER.fullmatch(line.text.strip()):
                    continue
                number = _number(block.lines, at, zone)
                if at + (2 if number is not None else 1) >= len(block.lines):
                    continue
                if measured is None:
                    ink, top, left = _ink(image, zone)
                    measured = (ink, top, left, _bands(ink))
                if _displayed(image, zone, block, at, number, *measured):
                    line.display = "line"
                    if number is not None:
                        number.display = "number"
                    found += 1
    return found
