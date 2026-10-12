"""What each entry looks like, from its own pixels — spec 0011, step 4.

**Why it exists.** Every entry was drawn in the house style for its kind: a
paragraph at the body size, a value upright and regular. `catalogue_0015`
prints its prices half as large again and bold, `menu_0012` sets each dish's
note small and italic, `statement_0006` its four summary figures large. Step 2
placed every Cell (`locate`), so each one's own ink can be measured — never
asked (ADR 0005).

**4a — size, weight, slant**, recorded on `Cell.look`:

- **Size** is the Cell's glyph height in ems of the page's body
  (`style.body_glyph`): from each line's baseline to the top of the letters
  standing on it (`_glyph`), and only where the model's text says one
  reaches the cap height — `each` is three x-height letters and an `h`. A
  Cell's lines are split at empty rows only: `style.type_lines` splits a
  word as short as `CRD` at the waist of its letters. A crop more than
  `CHIP` ink is a chip the type is knocked out of, and gets no size.
- **Weight** is the Cell's stem — the median ink mass of a horizontal run
  through its strokes, from anti-aliased coverage — less `BLUR`, over its
  glyph height, against the page's body median. Bold at `BOLD` or more.
  **Not read on a photographed page**: `receipt_0010`'s stems are print
  density and focus, and six of its regular lines measured bold while its
  bold `TOTAL` did not.
- **Slant** is the shear that makes the Cell's ink most upright — the angle
  that sharpens its vertical coverage profile most — against the page's
  median. Italic at `ITALIC` degrees or more, on a Cell of at least
  `LETTERS` letters.

**4b — colour and chip**, on the same `Look`:

- **Colour** is the entry's ink: the median of its pixels furthest from its
  own ground, the top `INK_SHARE` per cent — thin serif strokes rarely reach
  full ink, and the 92nd percentile read `menu_0012`'s body 50 levels light.
  Kept only where the Cell's ground is the one the render draws under it,
  so a light word is never drawn light on a ground we do not draw, and not
  read on a Cell holding a link: `Contact: editor@example.com` measured the
  link's blue for the whole line.
- **A chip** is a ground the Cell stands on that stops before `REACH` body
  glyphs out on either side — a badge, a pill, a code tag — where a shaded
  row or a filled card goes on. Its box is where its ground ends, and its
  corner radius comes from how far in its top row starts.

Neither is read on a photographed page: print and light set its colours.

Every threshold sits in the gap of its distribution, measured on 2026-10-12
over the placed Cells of the eleven pages whose picture is its own HTML,
each labelled with the size, weight, style and colour Chrome computed for the
source text it lands on — 658 for 4a, 650 for colour.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .ir import BBox, Cell, Document, Kind, Look, RowRole, Style, Zone
from .locate import cells_of
from .preprocess import ImageArray, _cv2, crop_origin
from .style import body_glyph, dominant, type_mask

TALL = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZbdfhklt0123456789")
"""Letters that reach the cap height or above. A short line without one is
all x-height and its height says nothing about its size."""

CHIP = 0.45
"""A crop more than this share ink is a chip with its type knocked out."""

BLUR = 0.6
"""Pixels anti-aliasing adds to every stem, whatever the size: the intercept
of stem against glyph height fitted over the regular Cells, `stem = 0.080 x
glyph + 0.60`. Without it a small regular Cell measures as heavy as a bold
one — every small capital on `newsletter_0008` did."""

BOLD = 1.4
"""A Cell is bold when its stem, less `BLUR`, over its glyph height, is this
many times the page's body median. Over the labelled Cells: regular
0.65-1.30 bar seven, bold 1.40-2.50 bar one. The seven are letter-spaced
capitals, small grey type and one display headline; the one, a white
header on a dark bar."""

ITALIC = 6.0
"""Degrees of slant beyond the page's median at which a Cell is italic.
Over the labelled Cells: italic 8-14, upright within 3 of the median bar
eight, nothing between. The eight are digits and three-letter words."""

LETTERS = 4
"""A Cell needs this many letters before its slant is read."""

SHEARS = range(-20, 21)
"""The slants tried, in degrees, on the Cell's coverage scaled three times."""

INK_SHARE = 98
"""The percentile of distance from its ground at which a Cell's ink starts.
Over the 650 labelled Cells the colour is exact nine times in ten; the rest
are thin italics and serifs read up to 40 levels light."""

GROUND_SAME = 36
"""Channel-sum within which two grounds are one. Twice `style.SAME_COLOUR`:
one side is a Cell's few hundred pixels, not a Zone's thousands."""

REACH = 1.5
"""How many body glyphs out from a Cell its ground is looked for again. A
chip's padding is under one — `catalogue_0015`'s SKU tags 6px, `darkdeck_0009`'s
pills 8px, on glyphs of 9 and 10."""

CHIP_APART = 45
"""Channel-sum by which the ground on both sides must differ from the Cell's
for it to stand on a chip. Over every placed Cell of the fourteen
screenshots: 0 for a ground that goes on, bar `darkdeck_0009`'s `184` at 31
on a KPI card near its edge; 61 and over for the corpus's fifteen chips —
seven SKU tags, two NEW badges, six pills."""


def _lines(ink: ImageArray) -> list[tuple[int, int]]:
    """Runs of rows with ink, split only at rows with none."""
    rows = ink.any(axis=1)
    out, start = [], None
    for index, inked in enumerate(list(rows) + [False]):
        if inked and start is None:
            start = index
        elif not inked and start is not None:
            out.append((start, index - 1))
            start = None
    return out


def _glyph(ink: ImageArray, text: str) -> float | None:
    """The Cell's glyph height in pixels: line by line, from its baseline to
    the top of the letters standing on it, and only where the model's text
    says a letter reaches the cap height.

    **Not the tallest component.** At a glyph of ten pixels a bold-ish face
    runs letters into each other and into their descenders: `darkdeck_0009`'s
    `Ingest gateway` is seven components, one of them `ateway` with the `y`'s
    tail, 12px tall on a 10px cap. The baseline is where most of the line's
    ink ends; a component ending below it — a descender, a merged tail, a
    bracket — or above it — an accent, a quote — says nothing of the size.
    """
    cv2 = _cv2()
    if not any(letter in TALL for letter in text):
        return None
    heights: list[float] = []
    for top, bottom in _lines(ink):
        strip = ink[top:bottom + 1].astype(np.uint8)
        stats = cv2.connectedComponentsWithStats(strip, connectivity=8)[2][1:]
        # A solid block as wide as half its height is a bullet or a chip's
        # edge; a narrower one is a stem — `Invoice`'s `I` is 2 by 12.
        glyphs = [(int(y), int(y + h), int(w)) for _, y, w, h, area in stats
                  if h >= 2 and w <= 4 * h
                  and not (area > 0.85 * w * h and h > 6 and 2 * w >= h)]
        if not glyphs:
            continue
        # Most glyphs end on the baseline; counted, not weighted by width,
        # since the widest component is the likeliest to be letters run
        # together with a tail.
        baseline = int(np.argmax(np.bincount([end for _, end, _ in glyphs])))
        standing = [start for start, end, _ in glyphs if abs(end - baseline) <= 1]
        if standing:
            heights.append(float(baseline - min(standing)))
    return float(np.median(heights)) if heights else None


def _own_ink(patch: ImageArray, zoned: ImageArray) -> ImageArray:
    """The Cell's ink split at its own threshold, not its Zone's. The Zone's
    is set by its darkest type: on a `catalogue_0015` card, the name and the
    price put it where the grey `each` loses the anti-aliased stem of its
    `h`, 172 on 255, and measures at its x-height. Kept to where the Zone's
    mask has ink nearby, so a neighbour's edge or a rule does not join."""
    cv2 = _cv2()
    level, _ = cv2.threshold(patch.astype(np.uint8), 0, 255,
                             cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    own = np.asarray(patch) <= level
    near = cv2.dilate(zoned.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return np.asarray(own & near)


def _cover(grey: ImageArray, ink: ImageArray) -> ImageArray | None:
    """How much of each pixel is ink, 0 to 1, from the anti-aliased grey."""
    if ink.sum() < 10 or (~ink).sum() < 4:
        return None
    ground = float(np.median(grey[~ink]))
    dark = float(np.percentile(grey[ink], 5))
    if ground - dark < 30:
        return None
    return np.clip((ground - grey.astype(float)) / (ground - dark), 0.0, 1.0)


def _stem(cover: ImageArray, glyph: float) -> float | None:
    """The median ink mass of a horizontal run through a stroke, in pixels.
    A run as long as half a glyph is a bar, not a stem."""
    masses: list[float] = []
    for row in cover:
        on = row > 0.15
        index = 0
        while index < len(row):
            if not on[index]:
                index += 1
                continue
            end = index
            while end < len(row) and on[end]:
                end += 1
            mass = float(row[index:end].sum())
            if mass < 0.45 * glyph:
                masses.append(mass)
            index = end
    return float(np.median(masses)) if len(masses) >= 8 else None


def _slant(cover: ImageArray) -> float | None:
    """The shear, in degrees, that makes the Cell's ink most upright."""
    cv2 = _cv2()
    big = cv2.resize(cover.astype(np.float32), None, fx=3, fy=3,
                     interpolation=cv2.INTER_CUBIC)
    height = big.shape[0]
    ys, xs = np.nonzero(big > 0.05)
    if len(xs) < 50:
        return None
    weights = big[ys, xs]
    best, angle = -1.0, 0.0
    for degrees in SHEARS:
        moved = xs + (height / 2 - ys) * np.tan(np.radians(degrees))
        profile = np.bincount(np.round(moved - moved.min()).astype(int), weights=weights)
        sharp = float((profile ** 2).sum())
        if sharp > best:
            best, angle = sharp, float(degrees)
    return angle


def _apart(one: Sequence[float], other: Sequence[float]) -> int:
    return int(sum(abs(int(a) - int(b)) for a, b in zip(one, other)))


def _ink(pixels: ImageArray, ground: tuple[int, int, int]) -> tuple[int, int, int]:
    """The Cell's ink: the median of its pixels furthest from its ground."""
    flat = np.asarray(pixels, dtype=np.int64).reshape(-1, 3)
    far = np.abs(flat - np.array(ground)).sum(axis=1)
    core = np.median(flat[far >= np.percentile(far, INK_SHARE)], axis=0)
    return int(core[0]), int(core[1]), int(core[2])


def _chip(rgb: ImageArray, box: tuple[int, int, int, int],
          ground: tuple[int, int, int], glyph: float) -> tuple[BBox, float] | None:
    """The chip the Cell stands on — its box, normalised, and its corner
    radius over its height — or None when its ground goes on."""
    height, width = rgb.shape[:2]
    left, top, right, bottom = box
    reach = int(round(REACH * glyph))
    sides = [dominant(rgb[top:bottom, x0:x0 + 2])
             for x0 in (left - reach - 2, right + reach)
             if x0 >= 0 and x0 + 2 <= width]
    if not sides or any(_apart(side, ground) <= CHIP_APART for side in sides):
        return None
    same = np.abs(np.asarray(rgb, dtype=np.int64) - np.array(ground)).sum(axis=2) <= GROUND_SAME
    row, column = (top + bottom) // 2, (left + right) // 2
    while left > 0 and same[row, left - 1]:
        left -= 1
    while right < width and same[row, right]:
        right += 1
    while top > 0 and same[top - 1, column]:
        top -= 1
    while bottom < height and same[bottom, column]:
        bottom += 1
    # A corner of radius r first meets its top row, half a pixel in, at
    # r - sqrt(r - 1/4) from the side; inverted, r = i + 1/2 + sqrt(i).
    edge = same[top, left:right]
    inset = int(np.argmax(edge)) if edge.any() else 0
    radius = inset + 0.5 + np.sqrt(inset) if inset else 0.0
    return (BBox(left / width, top / height, right / width, bottom / height),
            round(min(0.5, radius / max(1, bottom - top)), 2))


def _drawn_ground(zone: Zone, row: int | None, style: Style) -> tuple[int, int, int]:
    """The ground the render draws under one of the Zone's Cells."""
    if (row is not None and zone.header_fill is not None
            and zone.rows[row].role is RowRole.HEADER):
        return zone.header_fill
    return zone.fill or style.page_bg


def read(image: ImageArray, document: Document, *, photographed: bool = False,
         inverted: bool = False) -> None:
    """Set `Cell.look` on every placed Cell — spec 0011, step 4. `image`
    is `Rectified.plain`; `inverted` is `Rectified.inverted`, undone for
    colour; `photographed` is `Rectified.warped`, and leaves every weight
    and colour unread. A Cell not placed, or not measurable, keeps None."""
    cv2 = _cv2()
    for zone in document.zones:
        for cell, _ in cells_of(zone):
            cell.look = None
    body = body_glyph(image, document.zones)
    if not body:
        return
    grey = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image)
    height, width = image.shape[:2]
    rgb = None
    if image.ndim == 3 and not photographed:
        rgb = np.asarray(255 - image if inverted else image)[:, :, ::-1]
    style = document.style or Style()
    measured: list[tuple[Cell, float | None, float | None, float | None]] = []
    colours: dict[int, tuple[tuple[int, int, int], tuple[int, int, int] | None,
                             tuple[BBox, float] | None]] = {}
    for zone in document.zones:
        if zone.bbox is None or zone.kind is Kind.FIGURE:
            continue
        mask = np.asarray(type_mask(image, zone)) > 0
        x0, y0 = crop_origin(image, zone.bbox)
        own = grey[y0:y0 + mask.shape[0], x0:x0 + mask.shape[1]]
        turned = float((own < 128).mean()) > 0.5
        for cell, row in cells_of(zone):
            box = cell.bbox
            if box is None or not cell.text.strip():
                continue
            # A link's colour is the `<a>`'s to draw; a Cell holding one is
            # two colours, and its far pixels are the link's.
            linked = any(run.kind == "link" for run in cell.runs)
            if rgb is not None and not linked:
                spot = (max(0, int(box.left * width) - 1), max(0, int(box.top * height) - 1),
                        min(width, int(np.ceil(box.right * width)) + 1),
                        min(height, int(np.ceil(box.bottom * height)) + 1))
                pixels = rgb[spot[1]:spot[3], spot[0]:spot[2]]
                if pixels.size >= 60:
                    ground = dominant(pixels)
                    chip = _chip(rgb, spot, ground, body)
                    if chip is not None:
                        colours[id(cell)] = (_ink(pixels, ground), ground, chip)
                    elif _apart(ground, _drawn_ground(zone, row, style)) <= GROUND_SAME:
                        colours[id(cell)] = (_ink(pixels, ground), None, None)
            left = max(0, int(box.left * width) - x0 - 1)
            top = max(0, int(box.top * height) - y0 - 1)
            right = int(np.ceil(box.right * width)) - x0 + 1
            bottom = int(np.ceil(box.bottom * height)) - y0 + 1
            zoned = mask[top:bottom, left:right]
            if not zoned.any() or float(zoned.mean()) > CHIP:
                measured.append((cell, None, None, None))
                continue
            patch = grey[y0 + top:y0 + bottom, x0 + left:x0 + right]
            patch = 255 - patch if turned else patch
            ink = _own_ink(patch, zoned)
            glyph = _glyph(ink, cell.text)
            cover = _cover(patch.astype(float), ink)
            stem = _stem(cover, glyph) if cover is not None and glyph else None
            weight = (stem - BLUR) / glyph if stem is not None and glyph else None
            letters = sum(1 for letter in cell.text if letter.isalpha())
            slant = _slant(cover) if cover is not None and letters >= LETTERS else None
            measured.append((cell, glyph / body if glyph else None, weight, slant))

    def median(values: Sequence[float | None]) -> float | None:
        known = [v for v in values if v is not None]
        return float(np.median(known)) if known else None

    regular = median([w for _, size, w, _ in measured
                      if size is not None and 0.9 <= size <= 1.1])
    upright = median([s for *_, s in measured])
    for cell, size, weight, slant in measured:
        colour, fill, chip = colours.get(id(cell), (None, None, None))
        cell.look = Look(
            size=None if size is None else round(size, 2),
            bold=(None if weight is None or not regular or photographed
                  else weight / regular >= BOLD),
            italic=(None if slant is None or upright is None
                    else upright - slant >= ITALIC),
            color=colour, fill=fill,
            chip=None if chip is None else chip[0],
            radius=None if chip is None else chip[1])
