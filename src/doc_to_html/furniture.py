"""Everything the page draws that is not type — spec 0012, G3.

**Why it exists.** Six readers each saw part of what a page draws, and none
recorded it: `preprocess.content_ink` deleted thin long components so type
could be measured, `structure._rules` read rules on the page's ground only and
kept the vertical ones as column dividers, `structure.separators` kept the
*heights* of wide rules between Zones and nothing else, `style.rectangles`
found boxes, and `looks` and `fields` drew rules inside tables and forms. No
record held a rule's extent, thickness, colour or style, and nothing saw a side
bar, a hatched fill or a rule on a dark fill — so `letter_0016`'s 3px green
letterhead was drawn as the house's thin grey line, `cv_0013`'s heading rules
and `newsletter_0008`'s column rules not at all.

**What it finds**, all from pixels, each a `Furniture` record:

- **A rule** is a run of pixel rows — or columns, for a vertical one — no
  thicker than `THICKEST` glyphs, one colour along its length, that stands
  off the pixels on *both* sides of it by `OFF`. Both sides, so the edge of a
  fill is not one; in whatever ground it sits on, so `cv_0013`'s rules on its
  dark sidebar are. Its colour may not lie between its two sides' — that is a
  resampled edge, a ramp — and may not be the page's ground, which is the
  space between two lines. Pieces of one line — a resampled page's blended
  rows, its slight tilt — are joined. A horizontal rule is at least `LONG`
  glyphs; a vertical one at least `SPAN` times the tallest line of type beside
  it, which is what tells a side bar from the stem of a heading's `l`.
- **Double**: two parallel lines of one colour, as long as each other, closer
  than `DOUBLE_GAP` of their own width. **Dashed**: `DASHES` or more equal
  short pieces in a line, evenly spaced.
- **A frame** is four rules that close a rectangle.
- **A fill** is an area of one colour off the page's ground, at least `FILL`
  glyphs across both ways once type is opened away — a strip, a seal, a tile;
  **hatched** where it is two colours in diagonal stripes.

The records are found once, on the whole page, before anything is measured
from its type: `style.measure` then reads the page's ink with them masked out
(`mask`), so a certificate's gold frame is not its ink. `place` says which
Zone holds each one once the Zones are final; the renderer draws them.

Every threshold is in glyph heights — `glyph`, the median height of the
page's ink components, about its x-height — and was set from the
distribution over all twenty-one pages; each constant says where its gap is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .ir import BBox, Furniture, Kind, Zone
from .preprocess import (INK_LEVEL, PAD_X, PAD_Y, Drawn, ImageArray, _cv2, content_ink,
                         crop_origin)
from .style import dominant

OFF = 40
"""Channel-sum by which a line stands off the pixels on each side of it.
`catalogue_0015`'s `#efece7` card rules sit 59 off its white; the corpus's
faintest rule."""

SAME = 30
"""Channel-sum within which a line's own rows, or columns, agree."""

GROUND_SAME = 36
"""Channel-sum within which a line's colour is the page's ground: the space
between the two lines of a double rule, not a rule."""

BLEND = 12.0
"""How near, in RGB, a colour must lie to the straight line between two
others to be a blend of them — a fill's edge resampled, a line's
anti-aliased row. A blend is a linear mix, so it lies on that line to
within rounding; `timetable_0019`'s grey cell border lies 20 off the line
from its blue lesson bar to white, and is not one."""

COVER = 0.8
"""How much of a solid rule's length its pieces must cover. A line of
serif feet joined across its letters' gaps covers less: `paper_0018`'s
footnote baseline."""

THICKEST = 0.75
"""The thickest line, in glyphs. The corpus's thickest is `cv_0013`'s 4px
skill bars and `form_0007`'s 4px head bars, at 0.5-0.57 of their glyph."""

PIECE = 2.0
"""The shortest piece of a line kept to be joined, in glyphs."""

JOIN = 2.0
"""How far apart, in glyphs, two pieces of one line may lie along it and
still be joined: a resampled page's tilt steps a 1px line across rows."""

LONG = 4.0
"""The shortest horizontal rule, in glyphs. Type's own strokes — crossbars,
dashes — reach 3.1 (`paper_0018`'s), and the shortest rule the corpus draws
is `form_0007`'s `Ref.` underline at 8.4."""

SPAN = 1.5
"""How many times the tallest line of type beside it a vertical rule must
stand. A stem stands as tall as its own line, 1.0; `statement_0006`'s tile
bars stand 2.9 times theirs, `form_0007`'s head bars 3.2."""

TYPE_LINE = 4.0
"""The tallest line of type, in glyphs: inked rows running taller beside a
vertical rule are another rule — `certificate_0021`'s inner frame beside
its outer — not type."""

BESIDE = 6.0
"""How far either side of a vertical rule, in glyphs, its type is looked for."""

DOUBLE_GAP = 2.5
"""How far apart two lines may be, in their own widths, to be one double
rule: `newsletter_0008`'s masthead 1px apart at 1px, `certificate_0021`'s
frame 2px apart at 2px."""

DASH = 1.0
"""The longest dash, in glyphs: a dashed border's dashes are three times its
width — `ticket_0020`'s, resampled, 7px at a glyph of 8."""

CLEAR = 0.05
"""How much of the band one glyph either side of a dashed rule may be ink:
the tops of a line of letters are evenly spaced short pieces too, and have
their letters under them."""

DASHES = 8
"""The fewest dashes that make a dashed rule."""

EVEN = 0.3
"""How far a dash's spacing may stray from the line's median period, as a
share of it; its length, twice that from the median length."""

STEADY = 0.8
"""How many of a dashed rule's dashes must keep its period and length."""

FILL = 3.0
"""The narrowest fill, in glyphs, both ways."""

ENDS = 2.0
"""How far past each end of a horizontal line, in glyphs, type is looked
for."""

TYPED = 0.15
"""How much of the band past an end must be type for the line to run on
as type."""

HATCH_FILL = 2.0
"""The narrowest hatch, in glyphs, both ways: narrower than a plain fill,
because its stripes are evidence a plain fill does not carry —
`timetable_0019`'s lunch row is 2.8 glyphs tall."""

HATCH_EDGE = 10
"""Channel-sum by which two neighbouring pixels differ across a hatch's
stripes: `catalogue_0015`'s and `timetable_0019`'s two colours are 31 and
33 apart."""

HATCH_ACROSS = 0.04
"""How often, at least, a hatch's pixels change along one diagonal ..."""

HATCH_ALONG = 0.005
"""... and how seldom, at most, along the other."""

LETTER = 6.0
"""The widest a heavy letter is, in glyphs: `ticket_0020`'s 46px `R`,
opened, leaves a block of the page's ink 3.6 glyphs wide. Its longer side,
since spec 0012's step U: a letter is small both ways, and a band in the
type's colour long one way and short the other is a fill — the dark header
of `timetable_0019`'s table, 4.9 glyphs tall and 128 across, and of
`statement_0006`'s, and pricing's `Annual` toggle."""

FILLED = 0.75
"""How much of its box a fill covers: a round seal, pi over four, and not a
large letter's strokes — `ticket_0020`'s `OSL` covers half its box. Measured
by its outline, holes filled, since spec 0012's step U: `certificate_0021`'s
seal, unwarped, covers 0.72 of its box with the `GUILD GTE 2026` printed on
it punched out, and 0.785 by its outline."""

BARS = 4
"""The fewest parallel lines, each within `BAR_GAP` of the next, that are
a texture — a barcode's bars — rather than rules: `receipt_0010`'s barcode
is 24 lines at most 5px apart. A table's or a timetable's grid lines are
a column apart."""

BAR_GAP = 1.5
"""How far apart, in glyphs, a texture's lines are at most."""

FRAME_SLACK = 1.5
"""How far, in glyphs, a frame's sides may stop short of its corners — a
rounded corner's radius."""

EDGE = 0.25
"""How far past a fill's outline, in glyphs, its blended edge is looked for
— `grounded`. A resampled page blends a fill into its ground over a pixel
or two: `ticket_0020`'s strip over rows 40-42, at a glyph of 8."""


@dataclass
class _Line:
    """A line found on the page, in pixels: `at` is its first row (column,
    for a vertical one), `width` its thickness, `start`/`end` its extent."""

    vertical: bool
    at: int
    width: int
    start: int
    end: int
    color: tuple[int, int, int]
    style: str = "solid"
    period: float | None = None

    @property
    def length(self) -> int:
        return self.end - self.start


def find(image: ImageArray, *, inverted: bool = False,
         read: ImageArray | None = None) -> list[Furniture]:
    """Every rule, frame and fill on the page, top to bottom.

    `image` is `Rectified.plain`, BGR; `inverted` is `Rectified.inverted`,
    undone so every colour is the page's own. `read` is the equalised
    `Rectified.image`, which says which pixels are type — the same split
    `style.measure` makes."""
    pixels = np.asarray(image)
    if pixels.ndim != 3 or pixels.shape[0] < 8 or pixels.shape[1] < 8:
        return []
    rgb = np.asarray(255 - pixels if inverted else pixels, dtype=np.int64)[:, :, ::-1]
    ink = _type(read if read is not None else image)
    unit = glyph(ink)
    ground = dominant(rgb.astype(np.uint8))
    height, width = rgb.shape[:2]
    thickest = max(2, int(round(THICKEST * unit)))

    hatched = _hatched(rgb, unit)
    fills = _fills(rgb, ground, ink, unit, hatched)
    across = [line for line in _lines(rgb, ground, thickest, unit, vertical=False)
              if line.length >= LONG * unit]
    down = _lines(rgb, ground, thickest, unit, vertical=True)
    # Type, for the tests below, is ink that is neither a fill —
    # `content_ink` reads a dark sidebar as ink end to end — nor a line:
    # a box's edge beside another box's is not a line of type.
    bare = ink.copy()
    for fill in fills + hatched:
        bare[fill.top:fill.bottom, fill.left:fill.right] = False
    for line in across + down:
        if line.vertical:
            bare[line.start:line.end, max(0, line.at - 1):line.at + line.width + 1] = False
        else:
            bare[max(0, line.at - 1):line.at + line.width + 1, line.start:line.end] = False
    lines = across + [line for line in down if _stands(line, bare, unit)]
    lines = [line for line in lines if not _fill_coloured(line, fills + hatched)]
    lines = _untextured(lines, unit)
    lines = _doubled(lines, unit)
    lines = _rejoined(lines + _dashed(rgb, ground, ink, unit), unit)
    lines = _bridged(lines, rgb, unit)

    frames, loose = _frames(lines, unit)
    loose = [line for line in loose if line.vertical or not _in_type(line, bare, unit)]
    found = [_record(line, width, height) for line in loose]
    found += [_frame_record(frame, width, height) for frame in frames]
    found += [_fill_record(fill, width, height) for fill in fills + hatched]
    return sorted(found, key=lambda f: (round(f.bbox.top, 4), f.bbox.left))


def glyph(ink: Any) -> float:
    """The page's glyph, in pixels: the median height of its ink's components,
    about its x-height. 10 where there is no ink to measure."""
    cv2 = _cv2()
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        ink.astype(np.uint8), connectivity=8)
    tall, wide = stats[1:, 3], stats[1:, 2]
    keep = (tall >= 3) & (tall <= ink.shape[0] * 0.1) & (wide <= 3 * tall)
    return float(np.median(tall[keep])) if keep.any() else 10.0


def _type(image: ImageArray) -> Any:
    return np.asarray(content_ink(image)) > 0


def _between(colour: Any, one: Any, other: Any) -> bool:
    """Whether `colour` is a blend of `one` and `other`: within `BLEND` of the
    straight line between them in RGB, and between its ends."""
    a, b, c = (np.asarray(v, dtype=float) for v in (one, other, colour))
    path = b - a
    length = float(path @ path)
    if length == 0.0:
        return bool(np.linalg.norm(c - a) <= BLEND)
    share = float((c - a) @ path) / length
    if not 0.0 <= share <= 1.0:
        return False
    return bool(np.linalg.norm(c - (a + share * path)) <= BLEND)


def _pieces(rgb: Any, ground: tuple[int, int, int], thickest: int,
            shortest: int) -> list[_Line]:
    """Every run of rows, `thickest` or thinner, one colour along it and off
    both its sides, at least `shortest` long — horizontal; transpose for
    vertical."""
    height = rgb.shape[0]
    base = np.array(ground)
    found: list[_Line] = []
    for thick in range(1, thickest + 1):
        if height < thick + 3:
            break
        span = height - thick - 1
        first = rgb[1:1 + span]
        same = np.ones(first.shape[:2], bool)
        for row in range(1, thick):
            same &= np.abs(rgb[1 + row:1 + row + span] - first).sum(axis=2) <= SAME
        last = rgb[thick:thick + span]
        above, below = rgb[0:span], rgb[thick + 1:thick + 1 + span]
        on = (same & (np.abs(first - above).sum(axis=2) > OFF)
              & (np.abs(last - below).sum(axis=2) > OFF))
        padded = np.zeros((on.shape[0], on.shape[1] + 2), bool)
        padded[:, 1:-1] = on
        step = np.diff(padded.astype(np.int8), axis=1)
        rows, starts = np.nonzero(step == 1)
        _, ends = np.nonzero(step == -1)
        for row, start, end in zip(rows, starts, ends):
            if end - start < shortest:
                continue
            top = row + 1
            core = np.median(rgb[top:top + thick, start:end].reshape(-1, 3), axis=0)
            if np.abs(core - base).sum() <= GROUND_SAME:
                continue
            up = np.median(rgb[top - 1, start:end], axis=0)
            down = np.median(rgb[top + thick, start:end], axis=0)
            if _between(core, up, down) and np.abs(up - down).sum() > OFF:
                continue
            found.append(_Line(False, int(top), thick, int(start), int(end),
                               (int(core[0]), int(core[1]), int(core[2]))))
    return found


def _alike(one: tuple[int, int, int], other: tuple[int, int, int],
           ground: tuple[int, int, int]) -> bool:
    """One colour, or one a blend of the other into the ground."""
    a, b, g = np.array(one), np.array(other), np.array(ground)
    return bool(np.abs(a - b).sum() <= 2 * SAME
                or _between(a, b, g) or _between(b, a, g))


def _lines(rgb: Any, ground: tuple[int, int, int], thickest: int,
           unit: float, *, vertical: bool) -> list[_Line]:
    """The page's lines in one direction, their pieces joined: rows touching
    across the line, and pieces along it no more than `JOIN` glyphs apart."""
    turned = np.transpose(rgb, (1, 0, 2)) if vertical else rgb
    pieces = sorted(_pieces(turned, ground, thickest, int(PIECE * unit)),
                    key=lambda p: (p.at, p.start))
    reach = JOIN * unit
    groups: list[list[_Line]] = []
    for piece in pieces:
        for group in groups:
            top = min(p.at for p in group)
            bottom = max(p.at + p.width for p in group)
            start = min(p.start for p in group)
            end = max(p.end for p in group)
            if (piece.at <= bottom and piece.at + piece.width >= top - 1
                    and piece.start <= end + reach and piece.end >= start - reach
                    and _alike(piece.color, group[0].color, ground)):
                group.append(piece)
                break
        else:
            groups.append([piece])
    out: list[_Line] = []
    for group in groups:
        core = max(group, key=lambda p: (np.abs(np.array(p.color) - np.array(ground)).sum(),
                                         p.length))
        top = min(p.at for p in group)
        start, end = min(p.start for p in group), max(p.end for p in group)
        covered = np.zeros(end - start, bool)
        for piece in group:
            covered[piece.start - start:piece.end - start] = True
        if covered.mean() < COVER:
            continue
        out.append(_Line(vertical, top, max(p.at + p.width for p in group) - top,
                         start, end, core.color))
    return out


def _stands(line: _Line, ink: Any, unit: float) -> bool:
    """Whether a vertical line stands `SPAN` times taller than the tallest
    line of type beside it — or has no type beside it at all."""
    height, width = ink.shape
    reach = int(BESIDE * unit)
    top, bottom = max(0, line.start - int(unit)), min(height, line.end + int(unit))
    tallest = 0
    for left, right in ((max(0, line.at - reach), max(0, line.at - 1)),
                        (min(width, line.at + line.width + 1),
                         min(width, line.at + line.width + 1 + reach))):
        if right <= left:
            continue
        rows = ink[top:bottom, left:right].any(axis=1)
        run = 0
        for inked in list(rows) + [False]:
            if inked:
                run += 1
                continue
            if run <= TYPE_LINE * unit:
                tallest = max(tallest, run)
            run = 0
    return tallest == 0 or line.length >= SPAN * tallest


def _in_type(line: _Line, ink: Any, unit: float) -> bool:
    """Whether a horizontal line runs on as type past both its ends: a line
    of serif feet or of letters' tops, joined, not a rule. A rule ends in
    space, or at a rule `content_ink` has already taken out of the type."""
    height, width = ink.shape
    reach = int(round(ENDS * unit))
    top = max(0, line.at - int(round(0.6 * unit)))
    bottom = min(height, line.at + line.width + int(round(0.6 * unit)))
    ends = (ink[top:bottom, max(0, line.start - reach):max(0, line.start - 1)],
            ink[top:bottom, min(width, line.end + 1):min(width, line.end + reach)])
    return all(end.size and end.mean() >= TYPED for end in ends)


def _fill_coloured(line: _Line, fills: list[_Fill]) -> bool:
    """Whether a line is the colour of a fill it lies in — the space between
    two light letters on a dark sidebar, not a rule."""
    for fill in fills:
        if (fill.left <= line.start and line.end <= fill.right if not line.vertical
                else fill.top <= line.start and line.end <= fill.bottom):
            across = (fill.top <= line.at <= fill.bottom if not line.vertical
                      else fill.left <= line.at <= fill.right)
            if across and np.abs(np.array(line.color) - np.array(fill.color)).sum() <= GROUND_SAME:
                return True
    return False


def _untextured(lines: list[_Line], unit: float) -> list[_Line]:
    """Without the lines that are a texture: `BARS` or more parallel lines
    of one extent, each within `BAR_GAP` of the next."""
    gap = BAR_GAP * unit
    texture: set[int] = set()
    for vertical in (False, True):
        order = sorted((i for i, line in enumerate(lines) if line.vertical == vertical),
                       key=lambda i: lines[i].at)
        run: list[int] = []
        for i in order:
            last = lines[run[-1]] if run else None
            line = lines[i]
            if (last is not None and line.at - (last.at + last.width) <= gap
                    and min(line.end, last.end) - max(line.start, last.start)
                    >= 0.8 * max(line.length, last.length)):
                run.append(i)
                continue
            if len(run) >= BARS:
                texture.update(run)
            run = [i]
        if len(run) >= BARS:
            texture.update(run)
    return [line for i, line in enumerate(lines) if i not in texture]


def _doubled(lines: list[_Line], unit: float) -> list[_Line]:
    """Two parallel lines of one colour and one extent, close: one double."""
    used: set[int] = set()
    out: list[_Line] = []
    order = sorted(range(len(lines)), key=lambda i: (lines[i].vertical, lines[i].at))
    for position, i in enumerate(order):
        if i in used:
            continue
        one = lines[i]
        for j in order[position + 1:]:
            other = lines[j]
            if j in used or other.vertical != one.vertical:
                continue
            gap = other.at - (one.at + one.width)
            if gap > DOUBLE_GAP * max(one.width, other.width):
                break
            if (gap >= 1 and abs(one.start - other.start) <= unit
                    and abs(one.end - other.end) <= unit
                    and np.abs(np.array(one.color) - np.array(other.color)).sum() <= 2 * SAME):
                used.update((i, j))
                out.append(_Line(one.vertical, one.at, other.at + other.width - one.at,
                                 min(one.start, other.start), max(one.end, other.end),
                                 one.color, style="double"))
                break
        else:
            pass
        if i not in used:
            out.append(one)
    return out


def _dashed(rgb: Any, ground: tuple[int, int, int], ink: Any,
            unit: float) -> list[_Line]:
    """Dashed rules: `DASHES` or more short pieces in one line, alike and
    evenly spaced, each no longer than `DASH` glyphs, with no type beside.
    A dash may sit a pixel off the one before it — `ticket_0020`'s divider,
    on a page straightened to within a degree, steps five columns down it."""
    out: list[_Line] = []
    longest = max(2, int(round(DASH * unit)))
    band = max(2, int(round(unit)))
    for vertical in (False, True):
        turned = np.transpose(rgb, (1, 0, 2)) if vertical else rgb
        typed = np.transpose(ink) if vertical else ink
        dashes: list[_Line] = []
        for piece in sorted(_pieces(turned, ground, 3, 2), key=lambda p: (p.start, p.at)):
            # A blurred dash can come back as two pieces a pixel apart.
            near = next((d for d in reversed(dashes[-8:]) if abs(d.at - piece.at) <= 1
                         and 0 <= piece.start - d.end <= 2), None)
            if near is not None:
                near.end = max(near.end, piece.end)
            else:
                dashes.append(_Line(piece.vertical, piece.at, piece.width,
                                    piece.start, piece.end, piece.color))
        chains: list[list[_Line]] = []
        for piece in (d for d in dashes if d.length <= longest):
            for chain in chains:
                last = chain[-1]
                gap = piece.start - last.end
                if (abs(piece.at - last.at) <= 1 and 1 <= gap <= 2 * longest
                        and np.abs(np.array(piece.color) - np.array(last.color)).sum() <= 2 * SAME):
                    chain.append(piece)
                    break
            else:
                chains.append([piece])
        for chain in chains:
            if len(chain) < DASHES:
                continue
            gaps = np.diff([p.start for p in chain]).astype(float)
            lengths = np.array([p.length for p in chain], dtype=float)
            period = float(np.median(gaps))
            # A dash lost under a blur doubles one gap; it is still the line.
            steady = np.minimum(np.abs(gaps / period - 1), np.abs(gaps / period - 2))
            if ((steady <= EVEN).mean() < STEADY
                    or (np.abs(lengths / np.median(lengths) - 1) <= 2 * EVEN).mean() < STEADY):
                continue
            if any(_beside(p, typed, band) > CLEAR for p in chain):
                continue
            # Drawn straight, at the line's median, as wide as its dashes.
            at = int(np.median([p.at for p in chain]))
            colour = tuple(int(c) for c in np.median([p.color for p in chain], axis=0))
            out.append(_Line(vertical, at, max(p.width for p in chain),
                             chain[0].start, chain[-1].end,
                             (colour[0], colour[1], colour[2]),
                             style="dashed", period=period))
    return out


def _rejoined(lines: list[_Line], unit: float) -> list[_Line]:
    """A dashed rule and the solid pieces in line with it, one dashed rule:
    a blur runs some of a dashed line's dashes together — `receipt_0010`."""
    out: list[_Line] = []
    for line in sorted(lines, key=lambda l: (l.vertical, l.at, l.start)):
        last = out[-1] if out else None
        if (last is not None and last.vertical == line.vertical
                and abs(last.at - line.at) <= 1 and "dashed" in (last.style, line.style)
                and line.style in ("solid", "dashed") and last.style in ("solid", "dashed")
                and line.start - last.end <= JOIN * unit
                and np.abs(np.array(last.color) - np.array(line.color)).sum() <= 2 * SAME):
            dashed = last if last.style == "dashed" else line
            out[-1] = _Line(last.vertical, min(last.at, line.at), max(last.width, line.width),
                            last.start, max(last.end, line.end), dashed.color,
                            style="dashed", period=dashed.period)
            continue
        out.append(line)
    return out


def _bridged(lines: list[_Line], rgb: Any, unit: float) -> list[_Line]:
    """Two pieces of one line, in line, of one colour and thickness, one
    line where the page draws that colour across the gap between them: a
    badge set on a frame's edge — spec 0013 step 3b. `pricing_0017`'s
    `MOST POPULAR` pill, in the blue of Team's frame, cuts its top edge in
    two, x 363–443 and 557–637, and a frame's side must reach both corners.

    Every row, or column, of the gap must hold the line's colour within a
    glyph of it, and within `SAME` — nearer than any line stands off the
    ground (`OFF`), so the ground never bridges. Measured on pricing: the
    pill's 114 columns all do; between Starter's and Business's faint grey
    bottom edges, across Team's card and the ground either side of it,
    0.89 do, and they stay two lines. A gap of another colour — the seal
    between the certificate's signature lines — leaves two lines too."""
    reach = int(round(unit))
    out: list[_Line] = []
    for line in sorted(lines, key=lambda l: (l.vertical, l.at, l.start)):
        last = out[-1] if out else None
        if (last is not None and last.vertical == line.vertical
                and abs(last.at - line.at) <= 1 and last.width == line.width
                and last.style == line.style == "solid" and line.start > last.end
                and np.abs(np.array(last.color) - np.array(line.color)).sum() <= 2 * SAME
                and _drawn_across(rgb, last, line.start, reach)):
            out[-1] = _Line(last.vertical, min(last.at, line.at), last.width,
                            last.start, max(last.end, line.end), last.color)
            continue
        out.append(line)
    return out


def _drawn_across(rgb: Any, line: _Line, to: int, reach: int) -> bool:
    """Whether every row, or column, from `line`'s end to `to` holds its
    colour within `reach` of it."""
    low, high = max(0, line.at - reach), line.at + line.width + reach
    band = (rgb[line.end:to, low:high] if line.vertical
            else rgb[low:high, line.end:to])
    near = np.abs(band - np.array(line.color)).sum(axis=2) <= SAME
    held = near.any(axis=1) if line.vertical else near.any(axis=0)
    return bool(held.size and held.all())


def _beside(piece: _Line, typed: Any, band: int) -> float:
    """How much of the band either side of a dash is type."""
    near = np.concatenate([
        typed[max(0, piece.at - band - 1):max(0, piece.at - 2), piece.start:piece.end],
        typed[piece.at + piece.width + 2:piece.at + piece.width + band + 1,
              piece.start:piece.end]])
    return float(near.mean()) if near.size else 0.0


@dataclass
class _Frame:
    left: int
    top: int
    right: int
    bottom: int
    width: int
    color: tuple[int, int, int]
    style: str


def _frames(lines: list[_Line], unit: float) -> tuple[list[_Frame], list[_Line]]:
    """Four sides closing a rectangle, as frames; the rest left as lines.

    A side may be several pieces of one line — a resampled page breaks a
    long one — and must reach both corners to within `FRAME_SLACK` glyphs,
    so a card's foot rule over its bottom edge is not a frame."""
    slack = FRAME_SLACK * unit
    across = sorted((line for line in lines if not line.vertical), key=lambda l: l.at)
    down = [line for line in lines if line.vertical]
    used: set[int] = set()
    frames: list[_Frame] = []

    def side(x: int, top: int, bottom: int, colour: tuple[int, int, int]) -> list[_Line]:
        pieces = [l for l in down if id(l) not in used and abs(l.at - x) <= slack
                  and l.end > top - slack and l.start < bottom + slack
                  and np.abs(np.array(l.color) - np.array(colour)).sum() <= 2 * SAME]
        if not pieces:
            return []
        start, end = min(l.start for l in pieces), max(l.end for l in pieces)
        covered = sum(min(l.end, bottom) - max(l.start, top) for l in pieces)
        if (abs(start - top) > slack or abs(end - bottom) > slack
                or covered < COVER * (bottom - top)):
            return []
        return pieces

    for top in across:
        if id(top) in used:
            continue
        for bottom in across:
            if (bottom.at <= top.at + top.width + slack or id(bottom) in used
                    or abs(top.start - bottom.start) > slack
                    or abs(top.end - bottom.end) > slack
                    or np.abs(np.array(top.color) - np.array(bottom.color)).sum() > 2 * SAME):
                continue
            low = bottom.at + bottom.width
            left = side(top.start, top.at, low, top.color)
            right = side(top.end - top.width, top.at, low, top.color)
            if not left or not right:
                continue
            used.update(id(l) for l in [top, bottom, *left, *right])
            frames.append(_Frame(min(top.start, *(l.at for l in left)), top.at,
                                 max(top.end, *(l.at + l.width for l in right)),
                                 low, top.width, top.color, top.style))
            break
    return frames, [line for line in lines if id(line) not in used]


def _record(line: _Line, width: int, height: int) -> Furniture:
    if line.vertical:
        box = BBox(line.at / width, line.start / height,
                   (line.at + line.width) / width, line.end / height)
    else:
        box = BBox(line.start / width, line.at / height,
                   line.end / width, (line.at + line.width) / height)
    return Furniture(kind="rule", bbox=box, thickness=line.width / width,
                     color=line.color, style=line.style,
                     period=None if line.period is None else line.period / width)


def _frame_record(frame: _Frame, width: int, height: int) -> Furniture:
    return Furniture(kind="frame",
                     bbox=BBox(frame.left / width, frame.top / height,
                               frame.right / width, frame.bottom / height),
                     thickness=frame.width / width, color=frame.color,
                     style=frame.style)


@dataclass
class _Fill:
    left: int
    top: int
    right: int
    bottom: int
    color: tuple[int, int, int]
    second: tuple[int, int, int] | None = None
    period: float | None = None
    angle: int | None = None


def _fills(rgb: Any, ground: tuple[int, int, int], ink: Any, unit: float,
           hatched: list[_Fill]) -> list[_Fill]:
    """Areas of colour off the page's ground, `FILL` glyphs across once type
    is opened away, covering `FILLED` of their box — and not a hatch, nor a
    heavy letter: in the page's ink and no longer than `LETTER` glyphs
    either way."""
    cv2 = _cv2()
    height, width = rgb.shape[:2]
    off = np.abs(rgb - np.array(ground)).sum(axis=2) > GROUND_SAME
    size = max(3, int(round(unit)))
    solid = cv2.morphologyEx(off.astype(np.uint8), cv2.MORPH_OPEN,
                             np.ones((size, size), np.uint8))
    # The type's own colour, from ink no solid area holds: over all ink,
    # `ticket_0020`'s teal strips outweigh its dark type.
    strokes = ink & (solid == 0)
    printed = (dominant(rgb[strokes].reshape(-1, 1, 3).astype(np.uint8))
               if strokes.any() else None)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    found: list[_Fill] = []
    for index in range(1, count):
        x, y, w, h, _ = stats[index]
        if w < FILL * unit or h < FILL * unit or w * h > 0.8 * width * height:
            continue
        # Covered by its outline, holes filled: type printed on a fill is
        # not a gap in it.
        shape = (labels[y:y + h, x:x + w] == index).astype(np.uint8)
        outline, _ = cv2.findContours(shape, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        whole = np.zeros_like(shape)
        cv2.drawContours(whole, outline, -1, 1, thickness=-1)
        if int(whole.sum()) < FILLED * w * h:
            continue
        if any(_inside(x, y, x + w, y + h, hatch) for hatch in hatched):
            continue
        inside = rgb[y:y + h, x:x + w][labels[y:y + h, x:x + w] == index]
        colour = dominant(inside.reshape(-1, 1, 3).astype(np.uint8))
        if (printed is not None and max(w, h) <= LETTER * unit
                and np.abs(np.array(colour) - np.array(printed)).sum() <= GROUND_SAME):
            continue
        found.append(_Fill(int(x), int(y), int(x + w), int(y + h), colour))
    return found


def _inside(left: int, top: int, right: int, bottom: int, fill: _Fill) -> bool:
    across = max(0, min(right, fill.right) - max(left, fill.left))
    down = max(0, min(bottom, fill.bottom) - max(top, fill.top))
    return across * down >= 0.5 * (right - left) * (bottom - top)


def _hatched(rgb: Any, unit: float) -> list[_Fill]:
    """Areas striped diagonally in two colours, `FILL` glyphs across: one
    diagonal neighbour agrees with each pixel, the other changes every few
    pixels. Type changes along both, a fill along neither."""
    cv2 = _cv2()
    height, width = rgb.shape[:2]
    one = np.zeros((height, width), np.float32)
    other = np.zeros((height, width), np.float32)
    one[:-1, :-1] = np.abs(rgb[:-1, :-1] - rgb[1:, 1:]).sum(axis=2) > HATCH_EDGE
    other[:-1, :-1] = np.abs(rgb[:-1, 1:] - rgb[1:, :-1]).sum(axis=2) > HATCH_EDGE
    size = max(5, int(round(2 * unit)) | 1)
    one = cv2.blur(one, (size, size))
    other = cv2.blur(other, (size, size))
    striped = (((one >= HATCH_ACROSS) & (other <= HATCH_ALONG))
               | ((other >= HATCH_ACROSS) & (one <= HATCH_ALONG)))
    bridge = max(3, int(round(2 * unit)))
    striped = cv2.morphologyEx(striped.astype(np.uint8), cv2.MORPH_CLOSE,
                               np.ones((1, bridge), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(striped, connectivity=8)
    found: list[_Fill] = []
    grow = size // 2
    for index in range(1, count):
        x, y, w, h, _ = stats[index]
        if w < HATCH_FILL * unit or h < HATCH_FILL * unit:
            continue
        # The window that found the stripes stops half itself short of
        # their edge; give that back.
        x, y = max(0, x - grow), max(0, y - grow)
        w, h = min(width, x + w + 2 * grow) - x, min(height, y + h + 2 * grow) - y
        block = rgb[y:y + h, x:x + w]
        first = dominant(block.astype(np.uint8))
        flat = block.reshape(-1, 3)
        rest = flat[np.abs(flat - np.array(first)).sum(axis=1) > HATCH_EDGE]
        if len(rest) < 0.2 * len(flat):
            continue
        second = dominant(rest.reshape(-1, 1, 3).astype(np.uint8))
        row = block[h // 2]
        changes = np.flatnonzero(np.abs(np.diff(row, axis=0)).sum(axis=1) > HATCH_EDGE)
        period = float(np.median(np.diff(changes)) * 2) if len(changes) > 2 else None
        # Stripes running down to the right agree with the neighbour below
        # and to the right: CSS's 45deg, whose gradient runs up to the right.
        along = one[y:y + h, x:x + w].mean() < other[y:y + h, x:x + w].mean()
        found.append(_Fill(int(x), int(y), int(x + w), int(y + h), first,
                           second, period, 45 if along else 135))
    return found


def _fill_record(fill: _Fill, width: int, height: int) -> Furniture:
    box = BBox(fill.left / width, fill.top / height, fill.right / width,
               fill.bottom / height)
    if fill.second is not None:
        return Furniture(kind="fill", bbox=box, color=fill.color, style="hatched",
                         second=fill.second,
                         period=None if fill.period is None else fill.period / width,
                         angle=fill.angle)
    return Furniture(kind="fill", bbox=box, color=fill.color)


def mask(furniture: Sequence[Furniture], shape: tuple[int, ...]) -> Any:
    """The pixels the furniture covers, one pixel wider all round: the page
    with its decoration masked out, for measuring its type."""
    height, width = shape[:2]
    out = np.zeros((height, width), bool)
    for item in furniture:
        box = item.bbox
        left = max(0, int(box.left * width) - 1)
        top = max(0, int(box.top * height) - 1)
        right = min(width, int(np.ceil(box.right * width)) + 1)
        bottom = min(height, int(np.ceil(box.bottom * height)) + 1)
        if item.kind == "frame":
            line = max(1, int(np.ceil(item.thickness * width))) + 1
            out[top:top + line, left:right] = True
            out[bottom - line:bottom, left:right] = True
            out[top:bottom, left:left + line] = True
            out[top:bottom, right - line:right] = True
        else:
            out[top:bottom, left:right] = True
    return out


def drawn(furniture: Sequence[Furniture], image: ImageArray, box: BBox) -> Drawn:
    """What the page draws over the crop of `box` — `preprocess.crop`'s
    window on `image` — in the crop's pixels, for the grid count and the
    printed-line count: spec 0012, G3b. See `preprocess.Drawn`.

    A fill is left out of a crop's columns only when it is dark — darker
    than `INK_LEVEL`, so `content_ink` reads it as ink end to end — and
    spans more than half the crop: `timetable_0019`'s header. Its lessons'
    pale tints are no ink, and their type is the columns."""
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, box)
    right_edge = int(min(1.0, box.right + PAD_X) * width)
    bottom_edge = int(min(1.0, box.bottom + PAD_Y) * height)
    wide, tall = right_edge - x0, bottom_edge - y0
    rules = np.zeros((max(0, tall), max(0, wide)), bool)
    across = np.zeros_like(rules)
    edges: list[float] = []
    downs: list[float] = []
    for item in furniture:
        b = item.bbox
        left = max(0, int(b.left * width) - 1 - x0)
        top = max(0, int(b.top * height) - 1 - y0)
        right = min(wide, int(np.ceil(b.right * width)) + 1 - x0)
        bottom = min(tall, int(np.ceil(b.bottom * height)) + 1 - y0)
        if right <= left or bottom <= top:
            continue
        if item.kind == "fill":
            edges += [b.top * height - y0, b.bottom * height - y0]
            grey = 0.299 * item.color[0] + 0.587 * item.color[1] + 0.114 * item.color[2]
            if grey < INK_LEVEL and right - left > 0.5 * wide:
                across[top:bottom, left:right] = True
        elif item.kind == "frame":
            line = max(1, int(np.ceil(item.thickness * width))) + 1
            rules[top:top + line, left:right] = True
            rules[max(top, bottom - line):bottom, left:right] = True
            rules[top:bottom, left:left + line] = True
            rules[top:bottom, max(left, right - line):right] = True
        else:
            rules[top:bottom, left:right] = True
            if item.vertical:
                downs.append((b.left + b.right) / 2 * width - x0)
            else:
                edges.append((b.top + b.bottom) / 2 * height - y0)
    return Drawn(rules=rules, across=across, edges=tuple(edges), downs=tuple(downs))


def place(furniture: Sequence[Furniture], zones: Sequence[Zone]) -> None:
    """Set each rule's `zone`: the Zone it lies inside, if one does — across
    a horizontal rule's middle, over half its length or half the Zone's
    width, whichever is less — `cv_0013`'s heading rules run on past their
    Zone — or down a vertical one's. Frames and fills are left to the
    renderer, `furnish`."""
    for item in furniture:
        item.zone = None
        if item.kind != "rule":
            continue
        box = item.bbox
        middle_y = (box.top + box.bottom) / 2
        middle_x = (box.left + box.right) / 2
        best: tuple[float, int] | None = None
        for index, zone in enumerate(zones):
            holder = zone.bbox
            if holder is None or zone.kind is Kind.FIGURE:
                continue
            if item.vertical:
                inside = (holder.left < middle_x < holder.right
                          and _overlap(box.top, box.bottom, holder.top, holder.bottom)
                          >= 0.5 * min(box.bottom - box.top, holder.bottom - holder.top))
            else:
                inside = (holder.top < middle_y < holder.bottom
                          and _overlap(box.left, box.right, holder.left, holder.right)
                          >= 0.5 * min(box.right - box.left, holder.right - holder.left))
            area = (holder.right - holder.left) * (holder.bottom - holder.top)
            if inside and (best is None or area < best[0]):
                best = (area, index)
        item.zone = None if best is None else best[1]


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


HELD = 0.9
"""How much of a fill must lie inside one Zone's box for the Zone to hold
it — `grounded`. A logo's square, a badge or a table's header bar lies
wholly in its Zone; a strip or a sidebar several Zones stand on lies in
none."""


def grounded(read: ImageArray, plain: ImageArray, furniture: Sequence[Furniture], *,
             inverted: bool = False, held: Sequence[BBox] = ()) -> ImageArray:
    """`read` — `Rectified.image` — with every solid fill the page draws read
    against its own ground: the picture the ink measures take. Spec 0018, A1.

    **Ink is measured against its local ground.** A fill is ground: on the
    plain picture its outline is re-read — its own colour, within
    `GROUND_SAME`, holes filled, so type printed on it is inside — and every
    pixel of it is made paper. **Type on the fill is ink by its contrast with
    the fill**: a pixel inside the outline whose grey stands `255 -
    INK_LEVEL` off the fill's, as type stands off paper, is made ink. **Its
    edge, as far as it is blended, is not ink**: within `EDGE` glyphs past
    the outline, a pixel that is a blend of the fill and the page's ground
    (`BLEND`) is made paper.

    Why: `equalise` takes a fill wider than its kernel for a shadow and
    lifts it, leaving a dark fringe round its letters and along its foot.
    On `ticket_0020` that fringe was ink no box covered, and became a Zone
    read as `The`, twice (§1). Measured on the plain picture, the strip is
    teal from its top to its foot and the fringe is not there.

    **A fill is ground only for the Zones that stand on it.** One lying
    wholly — `HELD` — inside one of the `held` boxes is a thing that Zone
    holds, its extent the Zone's: `invoice_0002`'s logo, a black square
    round three letters, was snapped to the letters as ground, and the
    statement's, nonlatin's and timetable's header bars pulled their tables'
    boxes in to the type. Those are left as `read` has them, and so is a
    fill that holds no type, which is a mark — `paper_0018`'s chart bars.
    Only solid fills: a hatch is two colours, and left as it was."""
    out = np.array(read, copy=True)
    fills = [item for item in furniture if item.kind == "fill" and item.style != "hatched"
             and not any(_holds(box, item.bbox) for box in held)]
    if not fills:
        return out
    cv2 = _cv2()
    pixels = np.asarray(plain)
    rgb = np.asarray(255 - pixels if inverted else pixels, dtype=np.int64)[:, :, ::-1]
    height, width = rgb.shape[:2]
    unit = glyph(_type(read))
    ground = np.array(dominant(rgb.astype(np.uint8)), dtype=float)
    edge = max(2, int(round(EDGE * unit)))
    for item in fills:
        box = item.bbox
        left, top = max(0, int(box.left * width) - edge), max(0, int(box.top * height) - edge)
        right = min(width, int(np.ceil(box.right * width)) + edge)
        bottom = min(height, int(np.ceil(box.bottom * height)) + edge)
        window = rgb[top:bottom, left:right]
        colour = np.array(item.color, dtype=np.int64)
        near = (np.abs(window - colour).sum(axis=2) <= GROUND_SAME).astype(np.uint8)
        outline, _ = cv2.findContours(near, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        whole = np.zeros_like(near)
        cv2.drawContours(whole, [shape for shape in outline
                                 if cv2.contourArea(shape) >= (FILL * unit) ** 2],
                         -1, 1, thickness=-1)
        inside = whole > 0
        typed = inside & (np.abs(_grey(window) - _grey(colour)) >= 255 - INK_LEVEL)
        if not _holds_type(typed, unit):
            continue
        reach = np.ones((2 * edge + 1, 2 * edge + 1), np.uint8)
        rim = (cv2.dilate(whole, reach) > 0) & ~inside
        patch = out[top:bottom, left:right]
        patch[inside] = 255
        patch[typed] = 0
        patch[rim & _blends(window, colour, ground)] = 255
    return out


def _holds(box: BBox, fill: BBox) -> bool:
    """Whether `HELD` of the fill's area lies inside `box`."""
    across = max(0.0, min(box.right, fill.right) - max(box.left, fill.left))
    down = max(0.0, min(box.bottom, fill.bottom) - max(box.top, fill.top))
    area = (fill.right - fill.left) * (fill.bottom - fill.top)
    return area > 0 and across * down >= HELD * area


def _grey(rgb: Any) -> Any:
    rgb = np.asarray(rgb, dtype=float)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _holds_type(typed: Any, unit: float) -> bool:
    """Whether a fill's contrasting pixels hold one mark at least half a
    glyph tall: a letter, not a speck of resampling."""
    cv2 = _cv2()
    count, _, stats, _ = cv2.connectedComponentsWithStats(typed.astype(np.uint8),
                                                          connectivity=8)
    return bool((stats[1:, 3] >= 0.5 * unit).any()) if count > 1 else False


def _blends(window: Any, one: Any, other: Any) -> Any:
    """`_between` over every pixel of `window` at once."""
    a, b = np.asarray(one, dtype=float), np.asarray(other, dtype=float)
    path = b - a
    length = float(path @ path)
    offset = np.asarray(window, dtype=float) - a
    if length == 0.0:
        return np.linalg.norm(offset, axis=2) <= BLEND
    share = (offset @ path) / length
    away = np.linalg.norm(offset - share[..., None] * path, axis=2)
    return (share >= 0.0) & (share <= 1.0) & (away <= BLEND)
