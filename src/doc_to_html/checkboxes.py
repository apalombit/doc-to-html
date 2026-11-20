"""A tick box printed at the start of a line, put back from the pixels — arm D2.

Spec 0024, part two, direction 7. GLM-OCR does not read a tick box: on
`L5-F13`'s dev pages 250 boxes were printed and not drawn (`☐` 112, `☑`
112, `☒` 26), and on c0004 each lies inside the parser's text region,
left of the line it names, while the region's text starts at the word
after it. So the reader is not asked again; the box is found where the line
starts, in the pixels, and its mark put in front of the line's text.

**Only a box the line starts with.** A box between two words of a line
(`☐ Owner ☐ Tenant ☐ Other`) would need where each word sits in the line,
which the parser does not say; it is left as read. **Only a box drawn
open**: a solid square at the start of a line is as often a bullet as a
filled box, so it is never turned into `■`.

What is in the box is read from its inside, at the sizes these pages print
it, 6-14 pixels: empty is `☐`; a mark symmetric left to right or top to
bottom is a cross, `☒`; any other mark is a tick, `☑` (`SYMMETRIC`).

Model-free, and D2's alone: `parser_first.measure` calls it last, after
`looks.read`, so the Cell's measured looks are its words' and nothing of
today's pipeline runs it.
"""

from __future__ import annotations

import re
from dataclasses import replace

import numpy as np

from .ir import BBox, Document, Run
from .locate import cells_of
from .preprocess import _cv2

OPEN, TICK, CROSS = "☐", "☑", "☒"

ALREADY = frozenset("☐☑☒□■▢▣✓✔✕✖✗✘√×")
"""Marks a line already starts with: the reader read its box."""

STAND_IN = re.compile(r"[-*•·] ")
"""A list marker the reader wrote where the page prints a box: c0044's
`- Glycosidic` under a `☐`. Replaced by the box, not kept after it."""

TYPED = re.compile(r"\[[ xX✓✗]?\]")
"""A box the reader typed: form_0007's `[ ] I consent to photographs`."""

REACH = 2.6
"""How far left of a line's first ink a box is looked for, in the line's
heights. Over the 127 boxes found on fifteen dev pages, a box starts
0.78-2.34 heights left of its line's first ink, 1.25 the median."""

LEAST, MOST = 0.45, 1.3
"""A box's height against its line's: smaller is a dot, larger is a frame."""

SQUARE = 0.75
"""A box's narrower side over its wider, at least."""

APART = 0.3
"""A box stands apart: no other ink this many line heights left of it. A
letter does not: c0574's `y` of `Saturday` left of `$45 per visit` was
read as a cross. form_0007's boxes stand about one line height after
the option before them."""

SIDES = 0.8
"""Each side of a box is drawn along this share of its length or more; a
round mark's are not."""

DARK = 0.55
"""A pixel inside the box is a mark where it is darker than the ground by
this share of the way to the box's own darkest ink. c0012's open `Petrol`
box, anti-aliased two pixels deep, has its inner border at 193-200 on a
ground of 250 and ink of 101: lighter than 168, so not a mark."""

MARKED = 0.08
"""The share of a box's inside that is mark, at least, for it to be ticked."""

THIN = 0.25
"""A box's border is this share of its height or less. Over the dev pages'
boxes it is one pixel, 0.07-0.17 of the box; c0571's heavy `O` of `GO
BLAZE`, square enough to pass every other test, is 0.31."""

SOLID = 0.5
"""A box whose inside is this much mark or more is not a tick box: a solid
square, a bullet, a logo or a picture in a frame (above). On the dev pages
a tick or a cross covers 0.10-0.34 of its box's inside, inside its border;
c0157's logo 0.66 and c0409's picture 0.73."""

SYMMETRIC = 0.5
"""A mark this symmetric, darkness-weighted, about either axis is a cross.
Over the 58 marked boxes found on fifteen dev pages, ticks score 0.18-0.43
and crosses 0.63-0.93."""


def restore(plain: np.ndarray, document: Document) -> int:
    """Put a mark in front of each placed line that starts with a box it
    does not spell. Returns how many were put back."""
    cv2 = _cv2()
    grey = plain if plain.ndim == 2 else cv2.cvtColor(plain, cv2.COLOR_BGR2GRAY)
    height, width = grey.shape
    restored = 0
    for zone in document.zones:
        # A table's cell whose neighbour on the left is a mark alone: the
        # reader read the box into a column of its own (c0066's release
        # column, `☑ | Marrowfield Regional Medical Center`).
        beside = {id(right) for row in zone.rows for left, right in zip(row.cells, row.cells[1:])
                  if left.text.strip() and all(ch in ALREADY or ch.isspace() for ch in left.text)}
        for cell, _ in cells_of(zone):
            text = cell.text
            if (cell.bbox is None or not text.strip() or text.lstrip()[0] in ALREADY
                    or TYPED.match(text.lstrip()) or id(cell) in beside):
                continue
            mark = box_before(grey, cell.bbox, width, height)
            if mark is None:
                continue
            prefix = f"{mark} "
            typed = STAND_IN.match(text)
            cut = typed.end() if typed else 0
            reading = cell.readings[0]
            runs = cell.runs
            if cut and runs and runs[0].text.startswith(text[:cut]):
                runs = [replace(runs[0], text=runs[0].text[cut:])] + runs[1:]
            cell.readings[0] = replace(
                reading, text=prefix + text[cut:],
                runs=[Run(text=prefix)] + [run for run in runs if run.text] if reading.runs else [])
            if cell.look is not None and cell.look.sizes:
                cell.look = replace(cell.look, sizes=tuple(
                    (0 if at == 0 else at + len(prefix) - cut, size)
                    for at, size in cell.look.sizes))
            restored += 1
    return restored


def box_before(grey: np.ndarray, bbox: BBox, width: int, height: int) -> str | None:
    """The mark of the open box printed just left of a line, or None."""
    cv2 = _cv2()
    top, bottom, left = bbox.top * height, bbox.bottom * height, bbox.left * width
    line = bottom - top
    if line <= 0:
        return None
    y0, y1 = max(0, int(top - 0.35 * line)), min(height, int(bottom + 0.35 * line) + 1)
    x0, x1 = max(0, int(left - REACH * line)), int(left - 0.05 * line)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    strip = grey[y0:y1, x0:x1]
    _, ink = cv2.threshold(strip, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats((ink > 0).astype(np.uint8), 8)
    ground = float(np.percentile(strip, 90))
    found: tuple[int, str] | None = None
    for index in range(1, count):
        x, y, w, h = (int(v) for v in stats[index][:4])
        if not (LEAST * line <= h <= MOST * line and h >= 5
                and min(w, h) >= SQUARE * max(w, h)):
            continue
        before = labels[y:y + h, max(0, x - int(np.ceil(APART * line))):x]
        if ((before > 0) & (before != index)).any():
            continue
        mark = _inside(labels[y:y + h, x:x + w] == index, strip[y:y + h, x:x + w], ground)
        if mark is not None and (found is None or x > found[0]):
            found = (x, mark)
    return None if found is None else found[1]


def _inside(shape: np.ndarray, pixels: np.ndarray, ground: float) -> str | None:
    """What an open box holds, or None where `shape` is not an open box."""
    h, w = shape.shape
    edge = max(1, round(h * 0.18))
    sides = (shape[:edge].any(0).mean(), shape[-edge:].any(0).mean(),
             shape[:, :edge].any(1).mean(), shape[:, -edge:].any(1).mean())
    if min(sides) < SIDES:
        return None
    # The border's own depth, from each side's middle.
    def depth(run: np.ndarray) -> int:
        stop = np.flatnonzero(~run)
        return int(stop[0]) if stop.size else len(run)
    border = max(1, min(depth(shape[h // 2]), depth(shape[h // 2, ::-1]),
                        depth(shape[:, w // 2]), depth(shape[::-1, w // 2]), h // 3))
    if border > THIN * h:
        return None
    inner = pixels[border:h - border, border:w - border].astype(float)
    if inner.size == 0:
        return None
    darkest = float(pixels.min())
    cut = ground - DARK * (ground - darkest)
    if float((inner < cut).mean()) >= SOLID:
        return None
    # Whether anything is in it, one pixel further in where the box has
    # room, so an anti-aliased border is not a mark: c0039's open orange
    # boxes, two pixels deep, read as crosses.
    deep = (pixels[border + 1:h - border - 1, border + 1:w - border - 1]
            if min(h, w) - 2 * (border + 1) >= 2 else inner)
    if float((deep < cut).mean()) < MARKED:
        return OPEN
    dark = np.clip(ground - inner, 0, None)

    def symmetry(mirror: np.ndarray) -> float:
        return float(np.minimum(dark, mirror).sum() / max(1e-6, np.maximum(dark, mirror).sum()))

    return CROSS if max(symmetry(dark[:, ::-1]), symmetry(dark[::-1])) >= SYMMETRIC else TICK

