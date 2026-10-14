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

**4c — the lines between rows and the rows' grounds**, on `Row.under` and
`Row.fill`, for every table whose rows are placed:

- **A line** in the gap under a row is a run of pixel rows, no thicker than
  `THIN` of a glyph, that stand off the gap's own ground across the Zone:
  `solid` where it is one colour across `SOLID` of the width and differs
  from the rows on both sides, `dashed` where it is `DASHES` or more equal
  dashes spanning `DASH_SPAN` of it, `double` where two solid lines lie
  within `DOUBLE` of a glyph. A thicker run is a row's fill reaching into
  the gap — `statement_0006`'s dark header bar.
  The gap under the last row is read to `LAST` glyphs below it.
- **A row's fill** is the ground of its own band, where it is not its
  Zone's: a header bar, a zebra stripe.
- **A row's gap** (4e) is from the lowest ink of the row before it to its
  own highest, where that row is also the one before it in the table.
- **A Block's gap** (4e) is the same between the Blocks of a prose or list
  Zone — paragraphs, headings, items — where the Block starts below the one
  before it rather than beside it. It needs no pixels: the Cells' boxes are
  their ink.

The lines are read on a photographed page too — `receipt_0010`'s dashed
rules are its structure — but not their colour.

**4d — leaders**, on `Row.leader`: a line of `DOTS` or more evenly spaced
marks along the lower half of a row's first line, from its first entry to
the next on that line, spanning `DASH_SPAN` of the gap — `menu_0012`'s
dots from each dish to its price, 70 to 111 one-pixel dots spanning 94-97%
of it. Nothing else in the corpus has one.

**4f — the page's face**, on `Style.face`, one for the whole page, from
its body-size lines of eight characters or more:
- **mono** where the letters of a line stand on a lattice: the gaps
  between their centres are whole multiples of one pitch, within 12% of it.
  It holds for a median 0.89 of each line's gaps on `receipt_0010`, and at
  most 0.60 on every other page. `MONO`.
- **serif** where most stems stand on a foot: the run of ink a stem ends in
  on the baseline is at least twice as wide as the stem at half the
  x-height. It holds for 0.83-0.98 of the stems on the four serif pages and
  at most 0.51 on the sans ones — `nonlatin_0014`'s Greek the highest. `SERIF`.
- **sans** otherwise.

Per Zone it is not clearly right: the serif pages' footers and subtitles
fall to 0.63, and the sans pages' Zones reach 0.58. `report_0011`'s table,
set in Arial on a Palatino page, is one face with its page.

**Highlights — spec 0012, G2.** A `mark` run the inline-runs pass returned
is kept only where the page draws a fill behind part of its Cell's line;
otherwise it is plain text (`unmarked`). The words never change.

Every threshold sits in the gap of its distribution, measured on 2026-10-12
over the placed Cells of the eleven pages whose picture is its own HTML,
each labelled with the size, weight, style and colour Chrome computed for the
source text it lands on — 658 for 4a, 650 for colour.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

import numpy as np

from .ir import (BBox, Cell, Document, Furniture, Kind, Look, RowRole, Run, Stroke,
                 Style, Zone)
from .locate import cells_of
from .preprocess import ImageArray, _cv2, crop_origin
from .style import SAME_COLOUR, body_glyph, dominant, type_lines, type_mask

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

THIN = 0.3
"""A line is no thicker than this many glyphs, nor than 2px: `statement_0006`'s
header bar reaches 6px into the gap under it on a 9px glyph; every rule in
the corpus is 1 or 2px."""

SOLID = 0.9
"""A solid line covers this share of the Zone's width; a row of text never
does."""

DASHES, DASH_SPAN = 3, 0.6
"""A dashed line is at least this many dashes, spanning this share of the
width — `receipt_0010`'s are sixty of 3-4px over 300."""

DOTS = 5
"""A leader is at least this many marks, their starts evenly spaced — the
spacing's spread under `EVEN` of its mean."""

EVEN = 0.3

LAST = 1.5
"""How many glyphs under the last row its line is looked for: a rule sits
a cell's padding below the words, and needs ground after it to be one."""

DOUBLE = 0.4
"""Two solid lines within this many glyphs of each other are one double
line."""

MONO = 0.75
"""The share of a page's lines' letter gaps that fall on one pitch above
which the page is set in a mono face — between 0.60 and 0.89."""

FOOT = 2.0
"""How many times as wide as its stem a stem's run on the baseline is when
it stands on a foot."""

SERIF = 2 / 3
"""The share of a page's stems standing on a foot above which its face is a
serif — between 0.51 and 0.83."""

FACE_LINES, FACE_STEMS = 6, 50
"""Fewer measured lines, or stems, leave the face unread."""

CHIP_APART = 45
"""Channel-sum by which the ground on both sides must differ from the Cell's
for it to stand on a chip. Over every placed Cell of the fourteen
screenshots: 0 for a ground that goes on, bar `darkdeck_0009`'s `184` at 31
on a KPI card near its edge; 61 and over for the corpus's fifteen chips —
seven SKU tags, two NEW badges, six pills."""

HIGHLIGHT = 1.2
"""How wide, in the Cell's own line heights, a band of columns filled edge
to edge in another colour than the Cell's ground must be for the page to
draw a highlight there — spec 0012, G2. Measured 2026-10-13 over all 1032
placed Cells of the twenty-one: type alone fills a column for at most
**0.71** of a line height (`receipt_0010`'s blurred `Castleton CT9 2BN`,
`cv_0013`'s letter-spaced `INTERESTS`), and the one fill behind part of a
line, `sample_css_0004`'s `<style>` code span, is **4.59**. A highlighted
word of three letters is about 1.5."""

FILLED = 0.9
"""The share of a column's pixels off the Cell's ground for it to count as
filled edge to edge."""


ASCENDS = frozenset("bdhkl")
"""Lowercase letters that stand above the x-height in every face. Not `t`,
which an italic stands short, nor `f`, which an italic hangs below."""

DESCENDS = frozenset("gjpqy")
"""Lowercase letters that hang below the baseline."""

CAPITAL = 0.85
"""How tall, of its line's capitals, a letter must stand to reach their
height."""

HANGS = 0.15
"""How far below the baseline, in its capitals' height, a letter must hang
to descend."""

SCRIPT_JOINED = 0.6
"""Connected pieces per letter under which a line's letters are joined —
spec 0012, G7. Over the twenty-one's italic entries of 1.1 ems and more:
the signatures and the certificate's name 0.20-0.57, the newsletter's pull
quote 0.90-1.03."""

SCRIPT_SIZE = 1.1
"""How large, in ems of the body, an entry must be to be read as script:
small italic type joins its letters by blur — the menu's dish notes measure
0.33-0.44."""

SCRIPT_LETTERS = 0.8
"""The share of an entry's characters that must be letters: pricing's
`2 / user / month` joins its digits and slashes, 0.56."""

ZONE_STEMS = 30
"""Stems a Zone's regular body-size type must stand on before its own face
is read — spec 0012, G7."""

OTHER_FACE = 0.25
"""How far, as a share of stems standing on a foot, a Zone must sit from its
page's face to be set in the other: on a serif page at most this share, on a
sans page at least one less it. Over every Zone of thirty stems: the serif
pages' 0.38-1.00, but `report_0011`'s sans table at 0.20; the sans pages'
0.03-0.58."""


def _standing(ink: ImageArray, text: str) -> tuple[list[tuple[int, int]], int, float, float] | None:
    """One printed line's pieces, its baseline, its capitals' height and
    its small letters' — the median of what stands on the baseline below
    the capitals — in pixels. None for a line with no capital."""
    cv2 = _cv2()
    capitals = sum(1 for letter in text if letter.isupper())
    lines = _lines(ink)
    if not capitals or len(lines) != 1:
        return None
    top, bottom = lines[0]
    stats = cv2.connectedComponentsWithStats(ink[top:bottom + 1].astype(np.uint8),
                                             connectivity=8)[2][1:]
    pieces = [(int(y), int(y + h)) for _, y, _, h, _ in stats if h >= 2]
    if len(pieces) < 3:
        return None
    baseline = int(np.argmax(np.bincount([end for _, end in pieces])))
    standing = sorted((end - start for start, end in pieces if abs(end - baseline) <= 1),
                      reverse=True)
    if len(standing) <= capitals:
        return None
    return (pieces, baseline, float(np.median(standing[:capitals])),
            float(np.median(standing[capitals:])))


def _small_caps(ink: ImageArray, text: str) -> tuple[bool, float] | None:
    """Whether one printed line of a head is set in small capitals, with its
    capitals' height in pixels — spec 0012, G7. None where its text cannot
    say: no capital, no lowercase letter, or none of `ASCENDS` or
    `DESCENDS`.

    **Counted, not measured.** A face's x-height stands at about 0.7 of its
    capitals, which is where small capitals stand too, so a height ratio
    cannot tell them apart; what can is that a lowercase `b` rises to the
    capitals and a `g` hangs below the line, and a small capital does
    neither. Over every head, header row and Title of the twenty-one, those
    in small capitals — the menu's and the newsletter's mastheads, `To
    begin`, `From the grill`, the paper's `I. Introduction` — show none of
    their risers and hangers, and every other shows one at least.
    """
    capitals = sum(1 for letter in text if letter.isupper())
    expected = sum(1 for letter in text if letter in ASCENDS or letter in DESCENDS)
    measured = _standing(ink, text)
    if measured is None or not expected or not any(letter.islower() for letter in text):
        return None
    pieces, baseline, height, _ = measured
    risen = sum(1 for start, end in pieces
                if abs(end - baseline) <= 1 and end - start >= CAPITAL * height) - capitals
    hung = sum(1 for _, end in pieces if end - baseline >= HANGS * height)
    return max(0, risen) + hung <= expected // 4, height


def _joined(ink: ImageArray, text: str) -> bool:
    """Whether an entry's letters are joined, as handwriting's are: few
    connected pieces of any height per letter. See `SCRIPT_JOINED`."""
    cv2 = _cv2()
    letters = sum(1 for letter in text if letter.isalpha())
    shown = [letter for letter in text if not letter.isspace()]
    if letters < LETTERS or letters < SCRIPT_LETTERS * len(shown):
        return False
    stats = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)[2][1:]
    tallest = max((int(h) for *_, h, _ in stats), default=0)
    pieces = sum(1 for *_, h, _ in stats if h >= 0.4 * tallest)
    return pieces < SCRIPT_JOINED * letters


def _title_caps(image: ImageArray, document: Document, body: float) -> None:
    """Small capitals on a Zone's Title, and its size at its capitals' —
    spec 0012, G7. A Title whose letters cannot say — menu's `Main
    courses`, with no riser or hanger — is set as a Title of its page in
    small capitals is, where its small letters stand as tall, within a
    pixel, and its colour is that one's."""
    found: list[tuple[bool, float] | None] = []
    small: list[float | None] = []
    for zone in document.zones:
        zone.title_caps = False
        found.append(None)
        small.append(None)
        if not zone.title or zone.bbox is None:
            continue
        mask = np.asarray(type_mask(image, zone)) > 0
        lines = type_lines(mask)
        if not lines:
            continue
        top, bottom = lines[0]
        ink = mask[top:bottom + 1]
        columns = np.where(ink.any(axis=0))[0]
        if not len(columns):
            continue
        ink = ink[:, columns.min():columns.max() + 1]
        found[-1] = _small_caps(ink, zone.title)
        measured = _standing(ink, zone.title)
        small[-1] = None if measured is None else measured[3]
    styles: list[tuple[float, tuple[int, int, int] | None, float]] = []
    for zone, verdict, letters in zip(document.zones, found, small):
        if verdict is not None and verdict[0]:
            zone.title_caps = True
            zone.title_size = round(verdict[1] / body, 2)
            if letters is not None:
                styles.append((letters, zone.title_color, zone.title_size))

    def alike(one: tuple[int, int, int] | None, other: tuple[int, int, int] | None) -> bool:
        if one is None or other is None:
            return one is other
        return _apart(one, other) <= SAME_COLOUR

    for zone, verdict, letters in zip(document.zones, found, small):
        if not zone.title or verdict is not None or letters is None:
            continue
        match = next((size for height, colour, size in styles
                      if abs(height - letters) <= 1 and alike(colour, zone.title_color)), None)
        if match is not None:
            zone.title_caps = True
            zone.title_size = match


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


TWO_SIZES = 2.0
"""How many times another's size one part of an entry is set at, at least,
to be a size of its own and not noise in the measure — spec 0013, step 3c.
Measured over all twenty-one at `S9-3b`: within one Block the lines' sizes
stand at most 1.25 apart (`paper_0018`'s justified lines), and
`pricing_0017`'s `£0` stands 3.0 times its `/ month`; within one line a
capital stands about 1.4 times a lowercase letter, and `£29` 3.0 times its
`/ user / month`. Nothing lies between 1.25 and 3.0."""


def _two_sizes(ink: ImageArray, text: str,
               body: float) -> tuple[tuple[int, float], ...] | None:
    """Where one printed line is set in two sizes — a price's figure large
    and its unit small, `pricing_0017`'s `£29 / user / month` — each part's
    first character and its size in ems of the body; None for one size.

    The large part is the stretch from the first to the last glyph standing
    on the baseline more than half as tall as the tallest, and everything
    else on the line, to one side of it, is the small part. Glyphs are not
    letters — a bold face runs two together, `%` is three — so the large
    part is matched to whole words, the words whose letters its glyphs count
    nearest; the spaces between go with the small part. The small part is
    sized as `_glyph` sizes a line: it must hold a letter that reaches the
    cap height, so a closing full stop is no part of its own."""
    cv2 = _cv2()
    lines = _lines(ink)
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if len(lines) != 1 or len(words) < 2:
        return None
    top, bottom = lines[0]
    strip = ink[top:bottom + 1].astype(np.uint8)
    stats = cv2.connectedComponentsWithStats(strip, connectivity=8)[2][1:]
    glyphs = sorted((int(x), int(y), int(y + h)) for x, y, _, h, _ in stats if h >= 2)
    if len(glyphs) < 2:
        return None
    baseline = int(np.argmax(np.bincount([end for *_, end in glyphs])))
    standing = [end - start for _, start, end in glyphs if abs(end - baseline) <= 1]
    if not standing:
        return None
    tallest = max(standing)
    large = [i for i, height in enumerate(standing) if height * TWO_SIZES > tallest]
    first, last = large[0], large[-1]
    before, after = standing[:first], standing[last + 1:]
    if bool(before) == bool(after):
        return None
    letters = [end - start for start, end in words]
    count = last - first + 1
    if after:
        taken = min(range(1, len(words)), key=lambda w: abs(sum(letters[:w]) - count))
        cut, small_text, rest = words[taken - 1][1], text[words[taken - 1][1]:], after
    else:
        taken = min(range(1, len(words)), key=lambda w: abs(sum(letters[w:]) - count))
        cut, small_text, rest = words[taken][0], text[:words[taken][0]], before
    if not any(letter in TALL for letter in small_text):
        return None
    if not (_counts_as(count, text[:cut] if after else text[cut:])
            and _counts_as(len(rest), small_text)):
        return None
    large_size, small_size = round(tallest / body, 2), round(max(rest) / body, 2)
    return (((0, large_size), (cut, small_size)) if after
            else ((0, small_size), (cut, large_size)))


def _counts_as(glyphs: int, text: str) -> bool:
    """Whether a part's glyphs count like its letters, within half: a full
    stop alone does not count as `credits.` — measured over all twenty-one,
    every line `_two_sizes` took wrongly without this was a closing stop or
    a stray mark matched to a whole word."""
    letters = sum(1 for letter in text if not letter.isspace())
    return abs(glyphs - letters) <= max(1, letters // 2)


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


def _pitch(ink: ImageArray) -> float | None:
    """The share of one line's letter gaps that are whole multiples of a
    single pitch — near 1 where every letter stands the same width apart.
    Letters are runs of inked columns; None for fewer than eight."""
    letters = _spans(list(ink.any(axis=0)))
    if len(letters) < 8:
        return None
    gaps = np.diff([(start + end) / 2 for start, end in letters])
    best = 0.0
    for pitch in np.arange(max(2.0, 0.8 * float(np.percentile(gaps, 10))),
                           1.3 * float(np.percentile(gaps, 60)), 0.1):
        times = np.round(gaps / pitch)
        best = max(best, float(((times >= 1)
                                & (np.abs(gaps - times * pitch) <= 0.12 * pitch)).mean()))
    return best


def _feet(cover: ImageArray, ink: ImageArray) -> list[float]:
    """For each stem of a Cell's lines, how many times as wide as itself is
    the run of ink it ends in on the baseline. A stem is a run at half the
    x-height no wider than 0.3 of it, under exactly one baseline run, so a
    bowl's two sides — one run below two — are not one."""
    cv2 = _cv2()
    widths: list[float] = []
    for top, bottom in _lines(ink):
        strip = ink[top:bottom + 1].astype(np.uint8)
        stats = cv2.connectedComponentsWithStats(strip, connectivity=8)[2][1:]
        ends = [int(y + h) for _, y, _, h, _ in stats if h >= 3]
        if len(ends) < 4:
            continue
        base = top + int(np.argmax(np.bincount(ends))) - 1
        standing = [int(h) for _, y, _, h, _ in stats
                    if abs(int(y + h) + top - 1 - base) <= 1]
        x_height = float(np.percentile(standing, 30)) if standing else 0.0
        if x_height < 4:
            continue
        middle = _spans(list(cover[int(round(base - x_height / 2))] >= 0.5))
        for start, end in _spans(list(cover[base] >= 0.5)):
            over = [(a, b) for a, b in middle if a < end and b > start]
            if len(over) == 1 and over[0][1] - over[0][0] <= 0.3 * x_height:
                widths.append((end - start) / (over[0][1] - over[0][0]))
    return widths


def _face(pitches: Sequence[float], feet: Sequence[float]) -> str | None:
    """The page's face from its lines' pitch fits and its stems' feet."""
    if len(pitches) >= FACE_LINES and float(np.median(pitches)) >= MONO:
        return "mono"
    if len(feet) < FACE_STEMS:
        return None
    return "serif" if float(np.mean(np.asarray(feet) >= FOOT)) >= SERIF else "sans"


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


def _spans(on: Sequence[bool]) -> list[tuple[int, int]]:
    """Runs of True, as [start, end)."""
    out, start = [], None
    for index, value in enumerate(list(on) + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            out.append((start, index))
            start = None
    return out


def _solid(pixels: ImageArray, thin: int) -> list[tuple[int, int, tuple[int, int, int]]]:
    """Solid lines across a gap: runs of pixel rows, no thicker than `thin`,
    one colour across `SOLID` of the width, and that colour different from
    the rows on both sides of it. The edge of a fill differs on one side only:
    `statement_0006`'s `#e6ebef` rules sit 61 from its white rows and 36 from
    its stripes, and the stripe's own edge is neither."""
    runs: list[list[Any]] = []
    for y in range(pixels.shape[0]):
        colour = dominant(pixels[y:y + 1])
        if runs and _apart(runs[-1][2], colour) <= SAME_COLOUR:
            runs[-1][1] = y + 1
        else:
            runs.append([y, y + 1, colour])
    ground = dominant(pixels)
    found = []
    for before, (top, bottom, colour), after in zip(runs, runs[1:], runs[2:]):
        if (bottom - top <= thin and _apart(colour, ground) > SAME_COLOUR
                and _apart(colour, before[2]) > SAME_COLOUR
                and _apart(colour, after[2]) > SAME_COLOUR):
            share = (np.abs(pixels[top:bottom] - np.array(colour)).sum(axis=2)
                     <= SAME_COLOUR).mean()
            if share >= SOLID:
                found.append((top, bottom, colour))
    return found


def _stroke(band: ImageArray, glyph: float, height: int,
            coloured: bool) -> Stroke:
    """The line drawn across a gap between two rows, or a Stroke of kind
    `none`. `band` is the gap's pixels, RGB, the Zone's width."""
    pixels = np.asarray(band, dtype=np.int64)
    if pixels.shape[0] < 3 or pixels.shape[1] < 4:
        return Stroke(kind="none")
    thin = max(2, round(THIN * glyph))
    solid = _solid(pixels, thin)
    if solid:
        top, bottom, colour = solid[0]
        kind = "solid"
        # Runs that touch are one line in two shades — a photograph's blur,
        # or a pale rule under a row meeting a dark one over the next; the
        # darker, as the eye reads it. Two with ground between are double.
        for following in solid[1:]:
            if following[0] == bottom and kind == "solid":
                bottom = following[1]
                if sum(following[2]) < sum(colour):
                    colour = following[2]
            elif following[0] - bottom <= DOUBLE * glyph and kind == "solid":
                kind, bottom = "double", following[1]
        return Stroke(kind=kind, color=colour if coloured else None,
                      width=round((bottom - top) / height, 5))
    # A dashed line: far from the gap's ground by half the most anything
    # stands off it, so a photograph's blur between two dashes is not a dash.
    ground = np.array(dominant(pixels))
    apart = np.abs(pixels - ground).sum(axis=2)
    far = apart > max(SAME_COLOUR, 0.5 * float(np.percentile(apart, 99)))
    cover = far.mean(axis=1)
    for top, bottom in _spans(list(cover >= 0.3)):
        if bottom - top > thin:
            continue
        dashes = _spans(list(far[top + int(np.argmax(cover[top:bottom]))]))
        lengths = np.array([end - start for start, end in dashes], dtype=float)
        if (len(dashes) >= DASHES
                and (dashes[-1][1] - dashes[0][0]) / pixels.shape[1] >= DASH_SPAN
                and float(lengths.std()) <= 0.5 * float(lengths.mean())):
            drawn = None
            if coloured:
                middle = np.median(pixels[top:bottom][far[top:bottom]], axis=0)
                drawn = (int(middle[0]), int(middle[1]), int(middle[2]))
            return Stroke(kind="dashed", color=drawn,
                          width=round((bottom - top) / height, 5))
    return Stroke(kind="none")


def _blocks(document: Document) -> None:
    """Set `Block.gap` in every prose and list Zone whose Blocks are placed."""
    for zone in document.zones:
        if zone.kind not in (Kind.PROSE, Kind.LIST):
            continue
        above: float | None = None
        for block in zone.blocks:
            block.gap = None
            boxes = [c.bbox for c in block.lines
                     if c.bbox is not None and c.text.strip()]
            if not boxes:
                above = None
                continue
            top = min(box.top for box in boxes)
            # A Block starting above the last one's lowest ink stands beside
            # it — `sample_semantic_0005`'s menu, one item after another.
            if above is not None and top >= above:
                block.gap = round(top - above, 5)
            above = max(box.bottom for box in boxes)


def _rows(rgb: ImageArray, document: Document, glyph: float,
          coloured: bool) -> None:
    """Set `Row.under` and `Row.fill` on every table whose rows are placed."""
    height, width = rgb.shape[:2]
    style = document.style or Style()
    for zone in document.zones:
        if zone.kind is not Kind.TABLE or zone.bbox is None:
            continue
        left = max(0, int(zone.bbox.left * width))
        right = min(width, int(np.ceil(zone.bbox.right * width)))
        placed: list[tuple[int, int, int]] = []
        for index, row in enumerate(zone.rows):
            row.under, row.fill, row.gap = None, None, None
            boxes = [c.bbox for c in row.cells if c.bbox is not None and c.text.strip()]
            if boxes:
                placed.append((int(min(b.top for b in boxes) * height),
                               int(np.ceil(max(b.bottom for b in boxes) * height)), index))
        placed.sort()
        drawn = zone.fill or style.page_bg
        for number, (top, bottom, index) in enumerate(placed):
            row = zone.rows[index]
            # Only from the row before it in the table: across a row not
            # placed — `receipt_0010`'s `AID` — the gap holds that row too.
            if number and placed[number - 1][2] == index - 1:
                row.gap = round(max(0, top - placed[number - 1][1]) / height, 5)
            if coloured and bottom > top:
                ground = dominant(rgb[top:bottom, left:right])
                if _apart(ground, drawn) > SAME_COLOUR:
                    row.fill = ground
            below = (placed[number + 1][0] if number + 1 < len(placed)
                     else min(height, bottom + int(round(LAST * glyph))))
            if below > bottom:
                row.under = _stroke(rgb[bottom:below, left:right], glyph, height, coloured)


def _leaders(rgb: ImageArray, document: Document, coloured: bool) -> None:
    """Set `Row.leader` on every table row whose first line runs a leader
    from its first entry to the next — spec 0011, step 4d."""
    height, width = rgb.shape[:2]
    for zone in document.zones:
        if zone.kind is not Kind.TABLE:
            continue
        for row in zone.rows:
            row.leader = None
            cells = [c for c in row.cells if c.bbox is not None and c.text.strip()]
            if len(cells) < 2:
                continue
            top = min(cells, key=lambda c: c.bbox.top if c.bbox else 1.0)
            assert top.bbox is not None
            middle = (top.bbox.top + top.bbox.bottom) / 2
            line = sorted((c for c in cells if c.bbox is not None
                           and c.bbox.top <= middle <= c.bbox.bottom),
                          key=lambda c: c.bbox.left if c.bbox else 0.0)
            if len(line) < 2:
                continue
            first, after = line[0].bbox, line[1].bbox
            assert first is not None and after is not None
            left, right = int(first.right * width) + 2, int(after.left * width) - 2
            upper = int(middle * height)
            lower = min(height, int(np.ceil(first.bottom * height)) + 2)
            if right - left < 10 or lower <= upper:
                continue
            strip = np.asarray(rgb[upper:lower, left:right], dtype=np.int64)
            apart = np.abs(strip - np.array(dominant(strip))).sum(axis=2)
            far = apart > max(SAME_COLOUR, 0.5 * float(np.percentile(apart, 99)))
            marked = []
            for y in range(far.shape[0]):
                marks = _spans(list(far[y]))
                starts = np.diff([start for start, _ in marks])
                if (len(marks) >= DOTS
                        and (marks[-1][1] - marks[0][0]) / far.shape[1] >= DASH_SPAN
                        and float(starts.std()) <= EVEN * float(starts.mean())):
                    marked.append(y)
            if not marked:
                continue
            rows = far[marked[0]:marked[-1] + 1]
            lengths = [end - start for start, end in _spans(list(rows.any(axis=0)))]
            thick = marked[-1] + 1 - marked[0]
            kind = "dotted" if float(np.median(lengths)) <= 2.5 * thick else "dashed"
            colour = None
            if coloured:
                inked = strip[marked[0]:marked[-1] + 1][rows]
                middle_ink = np.median(inked, axis=0)
                colour = (int(middle_ink[0]), int(middle_ink[1]), int(middle_ink[2]))
            row.leader = Stroke(kind=kind, color=colour, width=round(thick / height, 5))


def _titles(rgb: ImageArray, document: Document, style: Style) -> None:
    """Each Title's ink — spec 0012, G3a: the first printed line in the band
    from its Zone's top to its first placed entry, or to a rule or fill the
    page draws under it — `nonlatin_0014`'s table header bar — measured as
    an entry is (`_ink`), where its ground is the one the render draws
    under it. The first line only, as a Title is one: `darkdeck_0009`'s
    tile labels stand over a value placed no higher than its own line. A
    Zone with no placed entry, or a Title beside its entries rather than
    over them, keeps None."""
    height, width = rgb.shape[:2]
    for zone in document.zones:
        box = zone.bbox
        if not zone.title or box is None:
            continue
        tops = [cell.bbox.top for cell, _ in cells_of(zone) if cell.bbox is not None]
        if not tops:
            continue
        under = zone.title_fill or zone.fill or style.page_bg
        bottom = min([min(tops)] + [
            item.bbox.top for item in document.furniture
            if (item.kind == "fill" or (item.kind == "rule" and not item.vertical))
            and box.top < item.bbox.top < min(tops)
            and item.bbox.left < box.right and item.bbox.right > box.left
            and _apart(item.color, under) > GROUND_SAME])
        pixels = rgb[int(box.top * height):int(bottom * height),
                     int(box.left * width):int(np.ceil(box.right * width))]
        if pixels.size < 60:
            continue
        ground = dominant(pixels)
        if _apart(ground, under) > GROUND_SAME:
            continue
        far = (np.abs(np.asarray(pixels, dtype=np.int64) - np.array(ground)).sum(axis=2)
               > GROUND_SAME).any(axis=1)
        lines = [(a, b) for a, b in _spans(list(far)) if b - a >= 3]
        if not lines:
            continue
        top, end = lines[0]
        line = pixels[top:end]
        if line.size >= 60:
            zone.title_color = _ink(line, ground)


def _drawn_ground(zone: Zone, row: int | None, style: Style, box: BBox,
                  fills: list[Furniture]) -> tuple[int, int, int]:
    """The ground the render draws under one of the Zone's Cells.

    **A drawn fill under the Cell too** — spec 0013, step 7.
    `statement_0006`'s transaction header is printed white on a dark band,
    `(22, 32, 43)`, which `furniture` finds and the render draws; the Zone
    had no `header_fill`. Asked only the Zone's ground, white, the six
    header Cells' white was measured and dropped, and they took the page's
    ink — the band's own colour. A header's `header_fill` is asked first.

    **Not a row's measured fill.** That reaches every table row on a tint
    and was measured to: on `timetable_0019` it kept `B04 · Ms Ilves` teal
    beside the blue bar of its lesson, where the page prints it grey."""
    if (row is not None and zone.header_fill is not None
            and zone.rows[row].role is RowRole.HEADER):
        return zone.header_fill
    middle_x, middle_y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    for fill in fills:
        if (fill.bbox.left <= middle_x <= fill.bbox.right
                and fill.bbox.top <= middle_y <= fill.bbox.bottom):
            return fill.color
    return zone.fill or style.page_bg


def _highlighted(rgb: ImageArray, box: BBox) -> bool:
    """Whether the page draws a fill behind part of this Cell's line: a band
    of columns filled edge to edge, `HIGHLIGHT` line heights wide, in another
    colour than the Cell's own ground. A chip behind the whole Cell is its
    ground, so it does not count."""
    height, width = rgb.shape[:2]
    left, top = max(0, int(box.left * width)), max(0, int(box.top * height))
    right = min(width, int(np.ceil(box.right * width)))
    bottom = min(height, int(np.ceil(box.bottom * height)))
    pixels = np.asarray(rgb[top:bottom, left:right], dtype=np.int64)
    if pixels.size < 60:
        return False
    off = np.abs(pixels - np.array(dominant(rgb[top:bottom, left:right]))
                 ).sum(axis=2) > GROUND_SAME
    widest = max((end - start for start, end in
                  _spans(list(off.mean(axis=0) >= FILLED))), default=0)
    return bool(widest >= HIGHLIGHT * (bottom - top))


def unmarked(image: ImageArray, document: Document, *,
             inverted: bool = False) -> int:
    """Make a `mark` run plain text wherever the page draws no highlight
    behind its Cell — spec 0012, G2. Returns how many runs it unmarked.

    **None of the twenty-one sources prints a highlight**, and the inline-
    runs pass returned six `mark` runs on four of them — `cv_0013`'s
    `native`, `nonlatin_0014`'s `myDATA`, `letter_0016`'s `08812274`,
    `pricing_0017`'s `POPULAR`, `£144` and `14-day` — each drawn as a yellow
    band the page does not have. Whether a word is highlighted is
    perception, and the pixels are in hand, so the page decides, the way
    colour is measured rather than asked.

    A Cell not placed has no pixels to show a highlight, and its marks go:
    the six measured were wrong six times, so a kept mark must be seen.
    Only the run's kind changes — **marking may never change the words** —
    and a neighbouring plain run is joined to it, so the Cell reads as one
    run where nothing else is marked."""
    pixels = np.asarray(image)
    if pixels.ndim == 2:
        pixels = np.repeat(pixels[:, :, None], 3, axis=2)
    rgb = (255 - pixels if inverted else pixels)[:, :, ::-1]
    count = 0
    for zone in document.zones:
        for cell, _ in cells_of(zone):
            if not cell.readings or not any(run.kind == "mark"
                                            for run in cell.readings[0].runs):
                continue
            if cell.bbox is not None and _highlighted(rgb, cell.bbox):
                continue
            joined: list[Run] = []
            for run in cell.readings[0].runs:
                kind = "text" if run.kind == "mark" else run.kind
                count += run.kind == "mark"
                if joined and kind == "text" and joined[-1].kind == "text":
                    joined[-1] = Run(text=joined[-1].text + run.text)
                else:
                    joined.append(Run(text=run.text, kind=kind))
            cell.readings[0].runs = joined
    return count


def read(image: ImageArray, document: Document, *, photographed: bool = False,
         inverted: bool = False) -> None:
    """Set `Cell.look` on every placed Cell — spec 0011, step 4. `image`
    is `Rectified.plain`; `inverted` is `Rectified.inverted`, undone for
    colour; `photographed` is `Rectified.warped`, and leaves every weight
    and colour unread. A Cell not placed, or not measurable, keeps None."""
    cv2 = _cv2()
    for zone in document.zones:
        zone.title_color = None
        zone.title_caps, zone.face = False, None
        for cell, _ in cells_of(zone):
            cell.look = None
    if document.style is not None:
        document.style.face = None
    unmarked(image, document, inverted=inverted)
    _blocks(document)
    body = body_glyph(image, document.zones)
    if not body:
        return
    grey = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image)
    height, width = image.shape[:2]
    rgb = None
    if image.ndim == 3:
        true = np.asarray(255 - image if inverted else image)[:, :, ::-1]
        _rows(true, document, body, coloured=not photographed)
        _leaders(true, document, coloured=not photographed)
        rgb = None if photographed else true
    style = document.style or Style()
    if rgb is not None:
        _titles(rgb, document, style)
    _title_caps(image, document, body)
    heads = {id(cell) for zone in document.zones for block in zone.blocks
             if block.kind == "heading" for cell in block.lines}
    heads |= {id(cell) for zone in document.zones for row in zone.rows
              if row.role is RowRole.HEADER for cell in row.cells}
    shaped: dict[int, tuple[bool | None, bool]] = {}
    stems: dict[int, list[tuple[Cell, list[float]]]] = {}
    measured: list[tuple[Cell, float | None, float | None, float | None]] = []
    parted: dict[int, tuple[tuple[int, float], ...]] = {}
    pitches: list[float] = []
    feet: list[float] = []
    colours: dict[int, tuple[tuple[int, int, int], tuple[int, int, int] | None,
                             tuple[BBox, float] | None]] = {}
    fills = [item for item in document.furniture
             if item.kind == "fill" and item.style == "solid"]
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
                    elif _apart(ground, _drawn_ground(zone, row, style, box,
                                                      fills)) <= GROUND_SAME:
                        colours[id(cell)] = (_ink(pixels, ground), None, None)
            left = max(0, int(box.left * width) - x0 - 1)
            top = max(0, int(box.top * height) - y0 - 1)
            # Kept to the Zone's crop, so the page's pixels and the mask cut
            # alike: a box `locate` drew a pixel past its Zone's crop stops
            # `pricing_0017` with a 13 by 22 patch over a 13 by 21 mask.
            right = min(mask.shape[1], int(np.ceil(box.right * width)) - x0 + 1)
            bottom = min(mask.shape[0], int(np.ceil(box.bottom * height)) - y0 + 1)
            zoned = mask[top:bottom, left:right]
            if not zoned.any() or float(zoned.mean()) > CHIP:
                measured.append((cell, None, None, None))
                continue
            patch = grey[y0 + top:y0 + bottom, x0 + left:x0 + right]
            patch = 255 - patch if turned else patch
            ink = _own_ink(patch, zoned)
            glyph = _glyph(ink, cell.text)
            if glyph and (parts := _two_sizes(ink, cell.text, body)) is not None:
                parted[id(cell)] = parts
            cover = _cover(patch.astype(float), ink)
            stem = _stem(cover, glyph) if cover is not None and glyph else None
            weight = (stem - BLUR) / glyph if stem is not None and glyph else None
            letters = sum(1 for letter in cell.text if letter.isalpha())
            slant = _slant(cover) if cover is not None and letters >= LETTERS else None
            measured.append((cell, glyph / body if glyph else None, weight, slant))
            # Spec 0012, G7: small capitals on a head, joined letters.
            small = _small_caps(ink, cell.text) if id(cell) in heads else None
            shaped[id(cell)] = (None if small is None else small[0], _joined(ink, cell.text))
            if cover is not None and (not glyph or 0.85 <= glyph / body <= 1.15):
                own_feet = _feet(cover, ink)
                stems.setdefault(id(zone), []).append((cell, own_feet))
                if len(cell.text.strip()) >= 8:
                    if len(_lines(ink)) == 1 and (fit := _pitch(ink)) is not None:
                        pitches.append(fit)
                    feet.extend(own_feet)

    def median(values: Sequence[float | None]) -> float | None:
        known = [v for v in values if v is not None]
        return float(np.median(known)) if known else None

    regular = median([w for _, size, w, _ in measured
                      if size is not None and 0.9 <= size <= 1.1])
    upright = median([s for *_, s in measured])
    for cell, size, weight, slant in measured:
        colour, fill, chip = colours.get(id(cell), (None, None, None))
        italic = (None if slant is None or upright is None
                  else upright - slant >= ITALIC)
        caps, joined = shaped.get(id(cell), (None, False))
        cell.look = Look(
            size=None if size is None else round(size, 2),
            bold=(None if weight is None or not regular or photographed
                  else weight / regular >= BOLD),
            italic=italic,
            color=colour, fill=fill,
            chip=None if chip is None else chip[0],
            radius=None if chip is None else chip[1],
            caps=caps or None,
            face=("script" if italic and joined and size is not None and size >= SCRIPT_SIZE
                  else None),
            sizes=parted.get(id(cell)))
    face = _face(pitches, feet)
    if document.style is not None:
        document.style.face = face
    _zone_faces(document, stems, face, regular, photographed)
    # A head in small capitals is drawn at its capitals' size, which its
    # lines measure; its Block's size was taken over its small letters.
    for zone in document.zones:
        for block in zone.blocks:
            looks = [cell.look for cell in block.lines if cell.look is not None]
            if (block.kind == "heading" and looks and all(look.caps for look in looks)
                    and all(look.size is not None for look in looks)):
                block.size = round(float(np.median([look.size for look in looks
                                                    if look.size is not None])), 2)


def _zone_faces(document: Document, stems: dict[int, list[tuple[Cell, list[float]]]],
                page: str | None, regular: float | None, photographed: bool) -> None:
    """A Zone's own face where its regular body-size type stands otherwise
    than its page's — spec 0012, G7, `OTHER_FACE`. Bold type is left out:
    its stems are wide for their feet, and the paper's bold serif title
    reads 0.11. Not on a photographed page, whose weights are unread."""
    for zone in document.zones:
        zone.face = None
        if page not in ("serif", "sans") or photographed or not regular:
            continue
        feet = [foot for cell, own in stems.get(id(zone), [])
                if cell.look is None or not cell.look.bold for foot in own]
        if len(feet) < ZONE_STEMS:
            continue
        share = float(np.mean(np.asarray(feet) >= FOOT))
        if page == "serif" and share <= OTHER_FACE:
            zone.face = "sans"
        elif page == "sans" and share >= 1 - OTHER_FACE:
            zone.face = "serif"
