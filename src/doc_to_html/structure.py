"""The page's structure: which parts of it are columns read down, and which are
a grid of copies read across — spec 0008, step 1.

**Why it exists.** Nothing else in the converter decides what the page's layout
is. `wire.bands_from_boxes` turns boxes into rows, and a row can only say what
is *beside* what, never which way a region is read — the gap
`specs/0007-a2-measurements.md` §4 named. `cv_0013`'s sidebar items are each
paired with whichever main-column item sits at their height, because a Band is
a row and the sidebar is not one.

**What it returns.** The page top to bottom as `Region`s, each `single` (read
down — today's Bands, and the default), `columns` (lanes side by side, each read
top to bottom) or `grid` (identical drawn boxes in rows and columns, read
across). Nothing deeper than page → region → lane.

**What it reads.** The page's own pixels and the Zones' boxes, nothing else.
Two kinds of evidence, both *drawn*:

- a **grid** is a full lattice of rectangles of one size, from
  `style.rectangles` — `catalogue_0015`'s nine cards, `darkdeck_0009`'s four
  tiles;
- a **column** needs a drawn divider — a panel's side (`darkdeck_0009`'s
  aside), the edge of a fill running the page's height (`cv_0013`'s sidebar),
  or a vertical rule (`newsletter_0008`), dashed ones too (`ticket_0020`'s
  perforation, spec 0012) — with the content on its two sides
  stacked independently: some block on one side stands beside two stacked
  blocks on the other. That is exactly the shape a Band cannot hold, and a
  float is not it — `sample_semantic_0005`'s TL;DR panel stands beside one
  block, and so does each of `invoice_0002`'s unequal panels.

**A whitespace gutter alone is never a column.** `menu_0012`'s body is two
columns with nothing drawn between them, and A2 §7 measured three times that
its gutter cannot be told from a two-column table's. So the menu stays
`single` here — the pixels cannot decide — and step 3 asks the model one
closed question about it instead.

`Conversion._read_structure` sets `Document.regions` from it once the boxes are
final (step 2), and step 3 lets it shape them: `cut_at_edges` cuts a Zone that
crosses the edge of a grid or a column region, and `alike` reads a grid's copies
as one Kind.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .ir import BBox, Flow, Furniture, Kind, Region, Role, Zone
from .preprocess import (MIN_GAP_THICKNESS, MIN_ZONE_INK, SEPARATOR_ASPECT,
                         ImageArray, _cv2, ink_fraction, snap_to_ink, zone_pixels)
from .style import CONTAINED, SAME_COLOUR, rectangles
from .wire import bands_from_boxes, validate_bands


SAME_SIZE = 0.01
"""How far apart, as a share of the page, two drawn boxes' widths, heights or
positions may be and still be copies of one design.

Measured over every rectangle `style.rectangles` finds on the corpus: the
copies differ by at most 0.002 (`catalogue_0015`'s cards) and 0.004
(`sample_css_0004`'s two stacked cards), and the nearest pair that is not
copies — `invoice_0002`'s Company Details and Payment Method panels, equal in
width — differs in height by 0.029.
"""

FULL_HEIGHT = 0.9
"""How much of a pixel column a fill must cover to run the page's height.

`cv_0013`'s sidebar covers all of it, light type and all, because the type is
no more the page's ground than the fill is. No other column on the corpus
reaches 0.5 wider than a page-edge hairline.
"""


def structure(image: ImageArray, boxes: Sequence[BBox], *,
              ground: tuple[int, int, int],
              inverted: bool = False,
              furniture: Sequence[Furniture] = ()) -> list[Region]:
    """The page's regions, top to bottom, covering it from 0 to 1.

    `image` and `ground` are what `style.rectangles` takes — the plain
    Rectified Image and the measured page ground — and `boxes` are the Zones'.
    `furniture` is `Document.furniture`, for the broken rules (`_broken`).
    """
    drawn = rectangles(image, ground=ground, inverted=inverted)
    marked = _marked(image, ground, inverted)
    containers = list(drawn) + _strips(marked, boxes)
    found = _grids(drawn) + _columns(boxes, containers,
                                     _rules(marked) + _broken(furniture))

    regions: list[Region] = []
    cursor = 0.0
    for region in sorted(found, key=lambda r: r.top):
        if region.top < cursor:
            continue
        if region.top > cursor:
            regions.append(Region(cursor, region.top))
        regions.append(region)
        cursor = region.bottom
    if cursor < 1.0:
        regions.append(Region(cursor, 1.0))
    return regions


WIDE_RULE = 0.5
"""How much of the page's width a horizontal rule must span to part what is
above it from what is below — spec 0009, step D, 4b. The spec's measure: 24
such rules lie between Zones across the corpus."""


def separators(image: ImageArray, zones: Sequence[Zone], *,
               ground: tuple[int, int, int],
               inverted: bool = False) -> list[float]:
    """Where the page draws a wide horizontal rule between its Zones, top to
    bottom, as page fractions — spec 0009, step D, 4b.

    Thirteen pages draw them and no render did: a masthead's rule, the rule
    above a footer. A rule inside a Zone is that Zone's own — a table's row
    rules, an underlined heading — and is left to it.

    **A table's own border is not one.** `sample_table_0003`, `darkdeck_0009`
    and `report_0011` each end their table on a rule just below the snapped
    box, which sits on the table's content ink. It is told from a separator
    by the table's own row rules: as wide as those, to `SAME_SIZE`, and
    within one of their pitches of the table's box — 0.012, 0.011 and 0.005
    of the page, against pitches of 0.051, 0.036 and 0.021. Width alone is
    not enough: `nonlatin_0014`'s masthead and footer rules are exactly as
    wide as its table's rows, and sit 0.25 and 0.16 away. `statement_0006`'s
    table holds no row rules, and both rules beside it are the page's. Over
    the corpus that leaves 21 of the 24, on eleven pages.
    """
    rules = [rule for rule in _rules(_marked(image, ground, inverted))
             if not rule.vertical and rule.right - rule.left >= WIDE_RULE]
    boxed = [zone for zone in zones if zone.bbox is not None]

    def inside(rule: _Rule, zone: Zone) -> bool:
        box = zone.bbox
        assert box is not None
        return (box.top < rule.top < box.bottom
                and box.left < rule.right and rule.left < box.right)

    def border(rule: _Rule, zone: Zone) -> bool:
        box = zone.bbox
        assert box is not None
        own = sorted((r for r in rules if inside(r, zone)), key=lambda r: r.top)
        if len(own) < 2:
            return False
        pitch = float(np.median([b.top - a.top for a, b in zip(own, own[1:])]))
        return (_near(rule.left, own[0].left) and _near(rule.right, own[0].right)
                and min(abs(rule.top - box.bottom), abs(box.top - rule.bottom)) <= pitch)

    return sorted(
        (rule.top + rule.bottom) / 2 for rule in rules
        if not any(inside(rule, zone) for zone in boxed)
        and not any(border(rule, zone) for zone in boxed if zone.kind is Kind.TABLE))


def _marked(image: ImageArray, ground: tuple[int, int, int],
            inverted: bool) -> Any:
    """Every pixel that is not the page's ground — the mask `rectangles` reads.

    Not `content_ink`: that one is cut at a fixed grey level, and
    `newsletter_0008`'s column rules and `darkdeck_0009`'s footer rule are too
    faint for it, while `cv_0013`'s light sidebar type punches holes in the
    fill it sits on.
    """
    pixels = np.asarray(image, dtype=np.int64)
    if inverted:
        pixels = 255 - pixels
    return np.abs(pixels[:, :, ::-1] - np.array(ground)).sum(axis=2) > SAME_COLOUR


def _strips(marked: Any, boxes: Sequence[BBox]) -> list[BBox]:
    """Fills running the page's height that hold a Zone — a sidebar.

    Thicker than a rule, so a page-edge hairline is not one, and holding a Zone,
    so a border round a photographed page is not one either.
    """
    height, width = marked.shape
    full = np.flatnonzero(marked.mean(axis=0) >= FULL_HEIGHT)
    found: list[BBox] = []
    for run in np.split(full, np.flatnonzero(np.diff(full) > 1) + 1):
        if len(run) < MIN_GAP_THICKNESS * min(width, height):
            continue
        rows = np.flatnonzero(marked[:, run].mean(axis=1) >= 0.5)
        strip = BBox(run[0] / width, rows[0] / height,
                     (run[-1] + 1) / width, (rows[-1] + 1) / height)
        if any(box.overlap_ratio(strip) >= CONTAINED for box in boxes):
            found.append(strip)
    return found


@dataclass(frozen=True)
class _Rule:
    x: float
    top: float
    bottom: float
    left: float
    right: float
    vertical: bool


def _rules(marked: Any) -> list[_Rule]:
    """Every Separator on the page — thin, and long for its thickness.

    `preprocess.content_ink`'s test, applied to `_marked` rather than to ink.
    """
    cv2 = _cv2()
    height, width = marked.shape
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        marked.astype(np.uint8) * 255, connectivity=8)
    found: list[_Rule] = []
    for index in range(1, count):
        x, y, w, h, _ = stats[index]
        thin = min(w, h) < MIN_GAP_THICKNESS * min(width, height)
        if thin and max(w, h) >= SEPARATOR_ASPECT * max(1, min(w, h)):
            found.append(_Rule(x=(x + w / 2) / width, top=y / height,
                               bottom=(y + h) / height, left=x / width,
                               right=(x + w) / width, vertical=h > w))
    return found


def _broken(furniture: Sequence[Furniture]) -> list[_Rule]:
    """The page's dashed and dotted vertical rules — spec 0012, G3b.

    `_rules` reads one connected stroke, and a dashed rule is many short
    ones, so `ticket_0020`'s perforation between the pass and its stub was
    never a divider and the stub was drawn under the pass. `furniture`
    joins the dashes into one rule; a solid rule `_rules` already sees."""
    return [_Rule(x=(item.bbox.left + item.bbox.right) / 2, top=item.bbox.top,
                  bottom=item.bbox.bottom, left=item.bbox.left,
                  right=item.bbox.right, vertical=True)
            for item in furniture
            if item.kind == "rule" and item.vertical and item.style in ("dashed", "dotted")]


EMPHASIS = 0.1
"""How much larger, both ways, a drawn box may be than its row's copies and
still be one of them, emphasised — spec 0012, step U. `pricing_0017`'s
middle card is 3.7% taller and 3.1% wider than the two beside it, for its
2px accent border and its ribbon, and centred on their row. Measured over
every pair of side-by-side boxes centred on one row across the corpus:
copies differ by at most 0.5%, and the nearest pair that is not copies,
`invoice_0002`'s panels, by 43%."""


def _emphasised(box: BBox, group: list[BBox]) -> bool:
    """Whether `box` is a copy of the group's, drawn larger — centred on a
    member's row, and larger both ways by no more than `EMPHASIS`."""
    wide, tall = group[0].right - group[0].left, group[0].bottom - group[0].top
    middle = (box.top + box.bottom) / 2
    return (wide <= box.right - box.left <= wide * (1 + EMPHASIS)
            and tall <= box.bottom - box.top <= tall * (1 + EMPHASIS)
            and any(_near(middle, (b.top + b.bottom) / 2) for b in group))


def _as_copy(box: BBox, like: BBox) -> BBox:
    """`box` at `like`'s size, about its own centre."""
    x, y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    wide, tall = (like.right - like.left) / 2, (like.bottom - like.top) / 2
    return BBox(x - wide, y - tall, x + wide, y + tall)


def _grids(drawn: Sequence[BBox]) -> list[Region]:
    """Each full lattice of same-size drawn boxes at least two columns wide.

    A full lattice — every row holding a box in every column — so that
    `form_0007`'s input boxes, eleven of one size scattered among labels and
    full-width fields, are not one.

    **Spec 0012, step U, two rules.** A box larger than its row's copies by
    a border, a shadow or a ribbon is still one of them (`EMPHASIS`), and is
    placed in the lattice at their size. And a split that would cross a
    drawn box is no grid's: `pricing_0017`'s outer cards alone made a grid
    of two whose split ran through the middle card, and its Zones were cut
    there — `MOST POPUL` and `OST POPULAR`.
    """
    groups: list[list[BBox]] = []
    for box in drawn:
        for group in groups:
            if (_near(box.right - box.left, group[0].right - group[0].left)
                    and _near(box.bottom - box.top, group[0].bottom - group[0].top)):
                group.append(box)
                break
        else:
            groups.append([box])
    whole = {id(group): list(group) for group in groups}
    for group in [g for g in groups if len(g) >= 2]:
        for other in [g for g in groups if len(g) == 1 and g[0] not in group]:
            if other and _emphasised(other[0], group):
                whole[id(group)].append(other[0])
                group.append(_as_copy(other[0], group[0]))
                other.clear()

    found: list[Region] = []
    for group in groups:
        if not group:
            continue
        lefts = _clusters([box.left for box in group])
        tops = _clusters([box.top for box in group])
        if len(lefts) < 2 or len(lefts) * len(tops) != len(group):
            continue
        cells = {(_index(lefts, box.left), _index(tops, box.top)) for box in group}
        if len(cells) != len(group):
            continue
        rights = [max(box.right for box in group if _near(box.left, left))
                  for left in lefts]
        splits = tuple(float(right + left) / 2
                       for right, left in zip(rights, lefts[1:]))
        members = whole[id(group)]
        top = float(min(box.top for box in members))
        bottom = float(max(box.bottom for box in members))
        if any(box.left < x < box.right and box.top < bottom and box.bottom > top
               and not any(member.overlap_ratio(box) >= CONTAINED
                           or box.overlap_ratio(member) >= CONTAINED for member in members)
               for box in drawn for x in splits):
            continue
        found.append(Region(top=top, bottom=bottom, flow=Flow.GRID,
                            splits=splits, rows=len(tops)))
    return found


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= SAME_SIZE


def _clusters(values: list[float]) -> list[float]:
    """The distinct positions among `values`, each the first of its cluster."""
    found: list[float] = []
    for value in sorted(values):
        if not found or not _near(value, found[-1]):
            found.append(value)
    return found


def _index(clusters: list[float], value: float) -> int:
    return next(i for i, at in enumerate(clusters) if _near(value, at))


def _columns(boxes: Sequence[BBox], containers: Sequence[BBox],
             rules: Sequence[_Rule]) -> list[Region]:
    """Each stretch of the page a drawn divider splits into independent lanes.

    The blocks are the Zones' boxes, except that a box inside a drawn container
    is the container: `darkdeck_0009`'s aside holds six list Zones and stands
    beside the main column as one thing.
    """
    blocks = [box for box in boxes
              if not any(box.overlap_ratio(c) >= CONTAINED for c in containers)]
    blocks += list(containers)

    dividers = [(c.left, c.top, c.bottom) for c in containers]
    dividers += [(c.right, c.top, c.bottom) for c in containers]
    dividers += [(r.x, r.top, r.bottom) for r in rules if r.vertical]

    found: list[tuple[float, float, set[float]]] = []
    for x, top, bottom in dividers:
        near = [b for b in blocks if b.top < bottom and b.bottom > top]
        if not near or any(b.left < x < b.right for b in near):
            continue
        left = [b for b in near if b.right <= x]
        right = [b for b in near if b.left >= x]
        if _independent(left, right) or _independent(right, left):
            found.append((min(top, *(b.top for b in near)),
                          max(bottom, *(b.bottom for b in near)), {x}))

    merged: list[tuple[float, float, set[float]]] = []
    for top, bottom, splits in sorted(found, key=lambda f: f[0]):
        if merged and top < merged[-1][1]:
            last = merged[-1]
            merged[-1] = (last[0], max(last[1], bottom), last[2] | splits)
        else:
            merged.append((top, bottom, splits))

    horizontal = [r for r in rules if not r.vertical]
    regions: list[Region] = []
    for top, bottom, splits in merged:
        top, bottom = _extended(top, bottom, sorted(splits), blocks, horizontal)
        regions.append(Region(float(top), float(bottom), Flow.COLUMNS,
                              tuple(float(x) for x in sorted(splits))))
    return regions


def _independent(one: list[BBox], other: list[BBox]) -> bool:
    """Whether a block on one side stands beside two stacked blocks on the other."""
    for block in one:
        beside = [b for b in other if b.top < block.bottom and b.bottom > block.top]
        if any(a.bottom <= b.top or b.bottom <= a.top
               for i, a in enumerate(beside) for b in beside[i + 1:]):
            return True
    return False


def _extended(top: float, bottom: float, splits: list[float],
              blocks: Sequence[BBox], rules: Sequence[_Rule]) -> tuple[float, float]:
    """The region grown up and down to the nearest block or rule that crosses a
    split, taking in every block between that sits in one lane.

    `darkdeck_0009`'s `What Q4 commits to` sits below the aside and in the main
    column's lane, and the footer's rule is what ends the column above the
    footer line, which on its own would also fit in that lane. Bounded by the
    *nearest* crossing rather than walked block by block, because the tile row
    above the aside has tiles clear of the split beside the one that crosses it.
    """
    def crosses(left: float, right: float) -> bool:
        return any(left < x < right for x in splits)

    edges = [(b.top, b.bottom) for b in blocks if crosses(b.left, b.right)]
    edges += [(r.top, r.bottom) for r in rules if crosses(r.left, r.right)]
    ceiling = max((low for high, low in edges if low <= top), default=0.0)
    floor = min((high for high, low in edges if high >= bottom), default=1.0)
    between = [b for b in blocks if not crosses(b.left, b.right)
               and b.top >= ceiling and b.bottom <= floor]
    return (min([top] + [b.top for b in between]),
            max([bottom] + [b.bottom for b in between]))


def cut_at_edges(image: ImageArray, zones: list[Zone],
                 regions: Sequence[Region]) -> list[Zone]:
    """The Zones with each one that crosses the edge of a grid or a column
    region cut there — the same list when none does. Spec 0008, step 3.

    `catalogue_0015`'s first card box runs from the page title down through the
    first card, so the title was read as part of a card and never printed. The
    grid's top is where the cards begin, drawn on the page; a box straddling it
    holds two things. Each part is moved onto its own ink with `snap_to_ink`,
    which caps growth at the midpoint to a neighbour, and a part carrying less
    than `MIN_ZONE_INK` is no Zone. The Bands are derived again, and Band 0 is
    the header, as `_cover_the_page` has it.

    **A part a grid holds is also cut at the grid's lane splits** — spec 0009,
    step B. `darkdeck_0009`'s four metric tiles are a 1×4 grid of drawn boxes,
    and the detector gave them one box across all four, so they were read as
    one four-column table. The splits are where the drawn boxes meet, so a cut
    there falls between tiles, never through one. Measured on the corpus's
    other two grids, no box crosses a split: `catalogue_0015`'s nine cards and
    `nonlatin_0014`'s two panels each sit inside one lane.

    Raises `MappingError` when the parts cannot sit in valid Bands; the caller
    keeps the uncut boxes.
    """
    edges = sorted({edge for region in regions if region.flow is not Flow.SINGLE
                    for edge in (region.top, region.bottom)} - {0.0, 1.0})
    grids = [region for region in regions if region.flow is Flow.GRID]
    pieces: dict[int, list[BBox]] = {}
    for index, zone in enumerate(zones):
        box = zone.bbox
        if box is None:
            continue
        cuts = [box.top, *(edge for edge in edges if box.top < edge < box.bottom),
                box.bottom]
        parts = [part for upper, lower in zip(cuts, cuts[1:])
                 for part in _across_lanes(
                     BBox(box.left, upper, box.right, lower), grids)]
        if len(parts) > 1:
            pieces[index] = parts
    if not pieces:
        return zones

    new = [part for index in sorted(pieces) for part in pieces[index]]
    kept = [zone.bbox for index, zone in enumerate(zones)
            if index not in pieces and zone.bbox is not None]
    snapped = iter(snap_to_ink(image, new + kept)[:len(new)])

    cut: list[Zone] = []
    for index, zone in enumerate(zones):
        if index not in pieces:
            cut.append(zone)
            continue
        for _ in pieces[index]:
            part = replace(zone, bbox=next(snapped))
            if ink_fraction(zone_pixels(image, part)) >= MIN_ZONE_INK:
                cut.append(part)

    placed = bands_from_boxes([zone.bbox for zone in cut if zone.bbox is not None])
    renumbered = [
        replace(zone, band=band, column=column,
                role=(Role.HEADER if band == 0 else
                      Role.BODY if zone.role is Role.HEADER else zone.role))
        for zone, (band, column) in zip(cut, placed)
    ]
    validate_bands(renumbered)
    return renumbered


def _across_lanes(box: BBox, grids: Sequence[Region]) -> list[BBox]:
    """`box` cut at the lane splits of the grid that holds it, left to right;
    `[box]` when no grid holds it or it sits inside one lane."""
    grid = next((region for region in grids if region.holds(box)), None)
    splits = [x for x in grid.splits if box.left < x < box.right] if grid else []
    cuts = [box.left, *splits, box.right]
    return [BBox(left, box.top, right, box.bottom)
            for left, right in zip(cuts, cuts[1:])]


def alike(zones: Sequence[Zone], regions: Sequence[Region],
          skip: frozenset[int] = frozenset()) -> dict[int, Kind]:
    """Which Zones change Kind so that a grid's copies are read alike — spec
    0008, step 3.

    `catalogue_0015`'s nine cards are one design drawn nine times, and were
    classified one at a time as five `pairs`, three `table` and a `prose`; the
    three tables lost most of their words. Within each `grid` Region every Zone
    takes the Kind most of them were given. A tie names no majority and changes
    nothing; `skip` is the Zones that have no Kind to vote with.
    """
    changes: dict[int, Kind] = {}
    for region in regions:
        if region.flow is not Flow.GRID:
            continue
        held = [index for index, zone in enumerate(zones)
                if zone.bbox is not None and region.holds(zone.bbox)
                and index not in skip]
        ranked = Counter(zones[index].kind for index in held).most_common()
        if len(held) < 2 or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
            continue
        kind = ranked[0][0]
        changes.update({index: kind for index in held
                        if zones[index].kind is not kind})
    return changes
