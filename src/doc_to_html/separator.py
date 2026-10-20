"""A pair's separator, as printed — spec 0019, B4.

**What the IR could not say.** `invoice_0001` prints `Created:` and `Due:`,
and `invoice_0002` prints `NO: 554775/R1 | Date: 01/01/2015`. The model
returns a pair's label without its colon, and nothing held the bar between
two pairs, so the render drew `Created January 1, 2023` and
`NO 554775/R1 Date 01/01/2015`.

**Read off the page, by tesseract, as printed.** `locate.Word.raw` keeps
what tesseract printed before folding. For each pair whose label is placed:

- **`Pair.separator`** — a mark of `SEPARATORS` that ends the last word
  tesseract reads on the label's line inside its box, or stands on its own
  between the label and its value, and that the label does not already end
  with: `letter_0016`'s model reads `Our ref:` whole;
- **`Pair.divider`** — a mark of `DIVIDERS` standing on its own between a
  pair's value and the next pair's label on the same line.

**The corpus, 2026-10-20.** Tesseract ends six labels with a colon, each
one the source prints: the invoices' `Created`, `Due`, `NO` and `Date`,
`nonlatin_0014`'s `Ημερομηνία` and `Λήξη` — read as `Huepounvia:` and
`Ann:`, the colon whatever the letters — and `catalogue_0015`'s `Orders`.
No label the source prints bare gains one. The one bar is `invoice_0002`'s,
read at 95.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .ir import BBox, Document, Kind, Pair, Zone
from .locate import GREEK, Word, available, cells_of, words
from .style import body_glyph

ImageArray = np.ndarray

SEPARATORS = ":"
"""The marks a label may end with."""

DIVIDERS = "|"
"""The marks that may stand between two pairs on one line."""

REACH = 0.002
"""How far, as a share of the page's width, past a label's box a word may
start or end and still be the label's."""


def _same_line(word: BBox, box: BBox) -> bool:
    """Whether a word's box shares more than half a box's height."""
    shared = min(word.bottom, box.bottom) - max(word.top, box.top)
    return shared > 0.5 * (box.bottom - box.top)


def _between(word: BBox, left: BBox, right: BBox | None) -> bool:
    """Whether a word stands on `left`'s line after it, and before `right`."""
    return (_same_line(word, left) and word.left >= left.right - REACH
            and (right is None or word.right <= right.left + REACH))


def _separator(pair: Pair, found: Sequence[Word]) -> str | None:
    label, value = pair.label, pair.value
    box = label.bbox
    text = label.text.rstrip()
    if box is None or not text or not value.text.strip():
        return None
    inside = sorted((word for word in found if word.text and _same_line(word.box, box)
                     and word.box.left < box.right + REACH
                     and word.box.right > box.left - REACH),
                    key=lambda word: word.box.left)
    alone = [word for word in found if not word.text and word.raw in SEPARATORS
             and _between(word.box, box, value.bbox)]
    ends = inside[-1].raw[-1:] if inside else ""
    mark = ends if ends and ends in SEPARATORS else (alone[0].raw if alone else "")
    if not mark or text.endswith(mark):
        return None
    return mark


def _divider(pair: Pair, following: Pair, found: Sequence[Word]) -> str | None:
    value, label = pair.value.bbox, following.label.bbox
    if value is None or label is None or not _same_line(label, value):
        return None
    marks = [word.raw for word in found if not word.text and word.raw in DIVIDERS
             and _between(word.box, value, label)]
    return marks[0] if marks else None


def read(image: ImageArray, document: Document) -> tuple[int, int]:
    """Set every pair's printed separator and divider. Returns how many of
    each. `image` is `Rectified.plain`."""
    glyph = body_glyph(image, document.zones)
    zones = [zone for zone in document.zones
             if zone.pairs and zone.bbox is not None and zone.complete
             and zone.kind is not Kind.FIGURE
             and any(pair.label.bbox is not None for pair in zone.pairs)]
    if not zones or not glyph or not available():
        return 0, 0
    separators = dividers = 0
    for zone in zones:
        found = words(image, zone, glyph=glyph, languages=_language(zone), marks=True)
        for position, pair in enumerate(zone.pairs):
            if pair.separator is None and (mark := _separator(pair, found)):
                pair.separator = mark
            if (pair.divider is None and position + 1 < len(zone.pairs)
                    and (mark := _divider(pair, zone.pairs[position + 1], found))):
                pair.divider = mark
            separators += pair.separator is not None
            dividers += pair.divider is not None
    return separators, dividers


def _language(zone: Zone) -> str:
    """As `locate.locate` reads the Zone."""
    greek = any(GREEK.search(cell.text) for cell, _ in cells_of(zone))
    return "ell+eng" if greek else "eng"
