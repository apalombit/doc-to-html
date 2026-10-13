"""The page's rhythm: what it draws round its Zones, which Zones continue one
another, and how each one's lines sit — spec 0011, step 1.

**Why it exists.** Since spec 0008 the IR knows where every Zone sits, and the
renderer still put one fixed gap between any two and drew every line at the
left. `newsletter_0008`'s columns broke into chunks 40px apart where the page
sets its paragraphs 13–16px apart; `darkdeck_0009`'s OPEN RISKS panel came
apart into six lists, because six Zones claim its rectangle and
`style.boxes_for` gives a rectangle to one Zone or none; the newsletter's,
the menu's and the receipt's mastheads drew at the left.

**What it reads.** Boxes and pixels only, after every model call — so it moves
no answer, and `tools/rederive.py` re-derives it over a frozen sweep.

- `frames` — the rectangle each Zone is drawn inside: its own, or one it
  shares with the run of Zones beside it that the rectangle holds;
- `groups` — each Continuation: Zones that continue one another down a
  lane;
- `alignment` and `title_alignment` — left, centre or right, from the lines'
  own edges or from where a one-line Zone sits in its row.

The gaps themselves are not recorded: they are a fact about the boxes the IR
already carries, and `render` reads them off it.

**Every threshold is in glyph heights** — the page's body glyph, as
`style.body_glyph` reads it — and each sits in an empty band of the
distribution measured over all fifteen documents of `tests/frozen/s5-result/`
on 2026-10-12, not on a round number; each constant says where its band is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .ir import BBox, Document, Flow, Kind, Region, Zone
from .style import body_glyph, box_around, boxes_for, type_lines, type_mask
from .preprocess import ImageArray, crop_origin

LEFT, CENTRE, RIGHT, JUSTIFY = "left", "centre", "right", "justify"

LINE_EDGE = 0.3
"""How far, in glyph heights, a block's line edges may spread and still agree.

Measured over every multi-line prose, list and pairs Zone: the right-aligned
blocks (`invoice_0001`'s two, `statement_0006`'s, `nonlatin_0014`'s and
`form_0007`'s office-use box) spread **0.00-0.11** at the right, and the next
right edge is **0.56** — `newsletter_0008`'s justified, drop-capped first
paragraph. The centred blocks (`menu_0012`'s footer, `receipt_0010`'s
header and its tail) spread **0.00-0.07** at the centre, and the next is
**0.60**, a bulleted list. One figure sits in both empty bands."""

PLACE_SLACK = 1.5
"""How close, in glyph heights, a Zone's two sides of free room must be for it
to sit centred in its row, and how close to an edge it must sit to be flush
with it.

Measured over every Zone outside a grid: the centred ones (the three
mastheads, the dateline, both footers, the receipt's barcode) are within
**0.56** of centre, and the next is **3.11**, `nonlatin_0014`'s remarks
block; the flush-right ones sit **0.00-1.08** from the edge. The Titles
over their Zones measure the same way: centred **0.00-0.27**, and the next,
a Title as wide as its Zone, at 0.50 with both sides under one glyph — which
is spanning, not centred."""

RAGGED = 4.0
"""How far short of its Zone's widest line, in glyph heights, a line may end
and still be a ragged line rather than a paragraph's last — spec 0012, G6.

Measured over every prose Zone of three printed lines or more: the
justified ones (the letter's body, the newsletter's columns, the paper's
abstract and columns) end every line but a paragraph's last within
`LINE_EDGE` of the edge, the newsletter's drop-capped paragraph one at
0.6; a paragraph's last line ends 7.0 short or more, but for one at 3.4 on
the broken pricing page. The ragged ones (the letter's addresses, the
newsletter's pull quote, the paper's title block) end lines 1.2-8.3
short."""

CONTINUES = 1.6
"""How many of the upper Zone's line pitches the gap may be for the lower
Zone to continue it — the spec's figure, and it lands in the gap of the
measurement: the pairs that pass every other test sit at **0.10-1.11**
pitches, and the pairs that do not continue one another at **2.0** and
above. `sample_css_0004`'s heading over its introduction is the one between,
at 1.59, and continues: a Continuation keeps the page's gap between its
members, so a borderline one changes no spacing."""

LEFT_EDGE = 1.0
"""How far apart, in glyph heights, two Zones' left edges may be and still
start one column. The continuing pairs measure **0.00-0.70**; the nearest
that does not, 1.25."""

GROUPS = (Kind.PROSE, Kind.LIST)
"""The Kinds a Continuation is made of. Figures and tables stand alone: `cv_0013`'s
two skill bars 2px apart are two pictures, and `invoice_0001`'s two tables
are two tables."""


def container(regions: Sequence[Region], box: BBox) -> tuple[int, int] | None:
    """The region and lane a box is read in, or None in a grid or outside
    every region — a grid's cells are placed by the grid, not by their gaps."""
    for index, region in enumerate(regions):
        if region.holds(box):
            if region.flow is Flow.GRID:
                return None
            lane = region.lane_of(box) if region.flow is Flow.COLUMNS else 0
            return index, lane
    return None


def frames(zones: Sequence[Zone], drawn: tuple[BBox, ...],
           regions: Sequence[Region]) -> list[BBox | None]:
    """The rectangle each Zone is drawn inside, or None.

    **Its own**, as `style.boxes_for` gives it, when it is the only Zone the
    rectangle holds. **Shared** when several Zones claim it and they are a
    run of one lane — every Zone of that lane between the first and the last
    of them, and no other. That is `darkdeck_0009`'s OPEN RISKS panel: six
    Zones, one card. `boxes_for` refuses it because `ir.Zone` never nests and
    giving the panel to each would draw six; a run of one lane is drawn once,
    around the run, so the IR can now say "these six share a box" without
    nesting. Anything else several Zones claim stays nobody's.
    """
    own = boxes_for([zone.bbox for zone in zones], drawn)
    out: list[BBox | None] = list(own)
    claims: dict[BBox, list[int]] = {}
    for index, zone in enumerate(zones):
        if zone.bbox is None or own[index] is not None:
            continue
        claim = box_around(zone.bbox, drawn)
        if claim is not None:
            claims.setdefault(claim, []).append(index)
    for box, members in claims.items():
        held = [b for i in members if (b := zones[i].bbox) is not None]
        homes = {container(regions, b) for b in held}
        if len(members) < 2 or len(homes) != 1 or None in homes:
            continue
        (home,) = homes
        top = min(b.top for b in held)
        bottom = max(b.bottom for b in held)
        run = {j for j, zone in enumerate(zones)
               if zone.bbox is not None and container(regions, zone.bbox) == home
               and top <= zone.bbox.top <= bottom}
        if run == set(members):
            for index in members:
                out[index] = box
    return out


@dataclass(frozen=True)
class _Line:
    top: int
    bottom: int
    left: int
    right: int


def _lines(image: ImageArray, zone: Zone) -> list[_Line]:
    """Each printed line of a Zone, in the Rectified Image's pixels."""
    assert zone.bbox is not None
    mask = np.asarray(type_mask(image, zone)) > 0
    x0, y0 = crop_origin(image, zone.bbox)
    found = []
    for top, bottom in type_lines(mask):
        columns = np.where(mask[top:bottom + 1].any(axis=0))[0]
        if len(columns):
            found.append(_Line(y0 + top, y0 + bottom,
                               x0 + int(columns.min()), x0 + int(columns.max())))
    return found


def _pitch(lines: list[_Line]) -> float | None:
    if len(lines) < 2:
        return None
    return float(np.median(np.diff([line.top for line in lines])))


def _body_lines(zone: Zone, lines: list[_Line]) -> list[_Line]:
    """The lines under the Title, which the caption pass took off the first."""
    return lines[1:] if zone.title else lines


def _overlap(a: BBox, b: BBox) -> float:
    return min(a.right, b.right) - max(a.left, b.left)


def _beside(a: BBox, b: BBox) -> bool:
    """Whether two boxes share a row: they overlap vertically by half the
    shorter of them."""
    shared = min(a.bottom, b.bottom) - max(a.top, b.top)
    return shared > 0.5 * min(a.bottom - a.top, b.bottom - b.top)


def groups(image: ImageArray, zones: Sequence[Zone], regions: Sequence[Region],
           separators: Sequence[float], *, body: float) -> list[int | None]:
    """For each Zone, the index of the first Zone of its Continuation.

    A Zone continues the one above it in its lane when all of these hold —
    the spec's five tests, and two the corpus added:

    - it carries no Title — a Title starts a Continuation, which keeps DECISIONS
      WANTED a list under its own heading inside the card OPEN RISKS opens;
    - it is the same Kind, prose or list (`GROUPS`), with the same fill and
      inside the same frame;
    - their left edges agree (`LEFT_EDGE`);
    - the gap between them is at most `CONTINUES` line pitches of the upper
      Zone — the lower one's when the upper prints one line, the page's when
      neither prints two;
    - **neither shares its row with another Zone**: `newsletter_0008`'s
      `VOL. CLII` sits in the dateline beside the date, and continuing it
      into `RIVERSIDE` below would take it out of that row;
    - **no rule the page draws lies between them**.

    The upper Zone is the one whose bottom is lowest among those above it in
    its lane, overlapping it by half the narrower of the two.
    """
    height, width = image.shape[:2]
    homes = [container(regions, z.bbox) if z.bbox is not None else None
             for z in zones]
    pitches: list[float | None] = []
    for zone in zones:
        if zone.bbox is None or zone.kind not in GROUPS:
            pitches.append(None)
            continue
        pitches.append(_pitch(_body_lines(zone, _lines(image, zone))))
    known = [p for p in pitches if p]
    page_pitch = float(np.median(known)) if known else 2.1 * body

    def alone(index: int) -> bool:
        box = zones[index].bbox
        assert box is not None
        return not any(j != index and other.bbox is not None
                       and homes[j] == homes[index] and _beside(box, other.bbox)
                       for j, other in enumerate(zones))

    first: list[int | None] = [None] * len(zones)
    # Top to bottom, so a Zone's upper neighbour has joined its Continuation
    # first.
    order = sorted((i for i, z in enumerate(zones) if z.bbox is not None),
                   key=lambda i: zones[i].bbox.top)  # type: ignore[union-attr]
    for lower in order:
        zone = zones[lower]
        box, home = zone.bbox, homes[lower]
        if box is None or home is None or zone.kind not in GROUPS or zone.title:
            continue
        above = [j for j, other in enumerate(zones)
                 if j != lower and homes[j] == home and other.bbox is not None
                 and other.bbox.top < box.top
                 and other.bbox.bottom <= box.top + 0.5 * body / height
                 and _overlap(other.bbox, box) >= 0.5 * min(
                     other.bbox.right - other.bbox.left, box.right - box.left)]
        if not above:
            continue
        upper = max(above, key=lambda j: zones[j].bbox.bottom)  # type: ignore[union-attr]
        other = zones[upper]
        assert other.bbox is not None
        gap = (box.top - other.bbox.bottom) * height
        pitch = pitches[upper] or pitches[lower] or page_pitch
        if (other.kind is zone.kind and other.fill == zone.fill
                and other.frame == zone.frame
                and abs(box.left - other.bbox.left) * width <= LEFT_EDGE * body
                and gap <= CONTINUES * pitch
                and alone(upper) and alone(lower)
                and not any(other.bbox.bottom <= y <= box.top for y in separators)):
            first[lower] = first[upper] if first[upper] is not None else upper
            first[upper] = first[lower]
    return first


def _by_lines(lines: list[_Line], body: float) -> str | None:
    """How a block's lines align, when two or more say so."""
    if len(lines) < 2:
        return None

    def spread(values: list[float]) -> float:
        return (max(values) - min(values)) / body

    lefts = spread([line.left for line in lines])
    rights = spread([line.right for line in lines])
    centres = spread([(line.left + line.right) / 2 for line in lines])
    if lefts <= LINE_EDGE:
        return LEFT
    if rights <= LINE_EDGE:
        return RIGHT
    if centres <= LINE_EDGE and rights > LINE_EDGE:
        return CENTRE
    return None


SPANS = "spans"


def _by_place(index: int, zones: Sequence[Zone],
              homes: Sequence[tuple[int, int] | None], width: int,
              body: float) -> str:
    """Where a Zone sits in its row: between the Zones beside it, or the
    edges of its lane's content when nothing is."""
    box, home = zones[index].bbox, homes[index]
    assert box is not None
    mates = [z.bbox for j, z in enumerate(zones)
             if z.bbox is not None and homes[j] == home]
    low = min(b.left for b in mates)
    high = max(b.right for b in mates)
    beside = [b for j, z in enumerate(zones) if j != index and homes[j] == home
              and (b := z.bbox) is not None
              and min(b.bottom, box.bottom) - max(b.top, box.top) > 0]
    low = max([b.right for b in beside if b.right <= box.left] + [low])
    high = min([b.left for b in beside if b.left >= box.right] + [high])
    room_left = (box.left - low) * width / body
    room_right = (high - box.right) * width / body
    if room_left <= PLACE_SLACK and room_right <= PLACE_SLACK:
        return SPANS
    if abs(room_left - room_right) <= PLACE_SLACK and min(room_left, room_right) > PLACE_SLACK:
        return CENTRE
    if room_right <= PLACE_SLACK:
        return RIGHT
    return LEFT


def _justified(lines: list[_Line], body: float) -> bool:
    """Whether a Zone's printed lines are set justified: most start at one
    left edge, and its lines end at one right edge but for a paragraph's
    last — two such lines and no ragged one, or three and a ragged one in
    four. See `RAGGED`."""
    if len(lines) < 3:
        return False
    left = min(line.left for line in lines)
    right = max(line.right for line in lines)
    if 2 * sum(1 for line in lines if line.left - left <= LINE_EDGE * body) <= len(lines):
        return False
    short = [(right - line.right) / body for line in lines]
    full = sum(1 for each in short if each <= LINE_EDGE)
    ragged = sum(1 for each in short if LINE_EDGE < each <= RAGGED)
    return (full >= 3 and ragged <= full // 4) or (full >= 2 and not ragged)


def alignment(image: ImageArray, zones: Sequence[Zone],
              regions: Sequence[Region], *, body: float) -> list[str | None]:
    """For each Zone, how its lines sit — or None for a table, a grid's cell,
    or a Zone with no box.

    **The lines decide when they can**: left edges agreeing is left whatever
    the place; right edges agreeing is right, and centres agreeing is
    centre, when the Zone also sits that way in its row or spans it. A Zone
    of one line — `Q3 2026 · INTERNAL`, `PRICE 80P`, `THANK YOU – PLEASE
    CALL AGAIN` — or a picture says nothing by its lines, and **where it
    sits decides**.

    **Only then.** A Zone of several lines that do not agree — a list, its
    wrapped lines indented past their bullets; a pairs list, its labels set
    flush right against left-set values — is left, wherever it sits, and so
    is a card of its own: where a card stands says nothing about how its
    text sits. Found by the suite, not the corpus: `invoice_0002`'s
    Customer Details card, flush right in its row in the recorded geometry,
    was drawn as right-set lines.

    **A left-set prose Zone whose lines are justified is `justify`** —
    spec 0012, G6, `_justified`: the letter's and the paper's body text.
    """
    width = image.shape[1]
    homes = [container(regions, z.bbox) if z.bbox is not None else None
             for z in zones]
    out: list[str | None] = []
    for index, zone in enumerate(zones):
        if zone.bbox is None or homes[index] is None or zone.kind is Kind.TABLE:
            out.append(None)
            continue
        place = _by_place(index, zones, homes, width, body)
        printed = ([] if zone.kind is Kind.FIGURE
                   else _body_lines(zone, _lines(image, zone)))
        lines = _by_lines(printed, body)
        if zone.kind is Kind.PROSE and lines in (None, LEFT) and _justified(printed, body):
            out.append(JUSTIFY)
        elif lines is None and (len(printed) > 1 or zone.boxed):
            out.append(LEFT)
        elif lines == LEFT:
            out.append(LEFT)
        elif lines == RIGHT:
            out.append(RIGHT if place in (RIGHT, SPANS) else LEFT)
        elif lines == CENTRE:
            out.append(CENTRE if place in (CENTRE, SPANS) else LEFT)
        else:
            out.append(LEFT if place == SPANS else place)
    return out


def title_alignment(image: ImageArray, zones: Sequence[Zone], *,
                    body: float) -> list[str | None]:
    """For each titled Zone, where its Title line sits over the lines under
    it: centred when its two sides of room agree and one of them is wider
    than `PLACE_SLACK` — the menu's `To begin` over its column, or a
    masthead over a narrower line, which leaves negative room on both sides
    — and right when it is flush right with room on its left."""
    out: list[str | None] = []
    for zone in zones:
        if zone.bbox is None or not zone.title:
            out.append(None)
            continue
        lines = _lines(image, zone)
        if len(lines) < 2:
            out.append(None)
            continue
        title, rest = lines[0], lines[1:]
        room_left = (title.left - min(line.left for line in rest)) / body
        room_right = (max(line.right for line in rest) - title.right) / body
        if (abs(room_left - room_right) <= PLACE_SLACK
                and max(abs(room_left), abs(room_right)) > PLACE_SLACK):
            out.append(CENTRE)
        elif room_right <= PLACE_SLACK < room_left:
            out.append(RIGHT)
        else:
            out.append(LEFT)
    return out


def read(image: ImageArray, document: Document) -> None:
    """Set every Zone's `group`, `align` and `title_align` — after the
    frames, which `Conversion._measure_chrome` sets with the rest of the
    chrome. `image` is `Rectified.plain`, which `style.type_mask` reads in
    each Zone's own polarity."""
    body = body_glyph(image, document.zones)
    zones = document.zones
    if not body or not document.regions:
        for zone in zones:
            zone.group = zone.align = zone.title_align = None
        return
    for zone, first in zip(zones, groups(image, zones, document.regions,
                                         document.separators, body=body)):
        zone.group = first
    for zone, align in zip(zones, alignment(image, zones, document.regions,
                                            body=body)):
        zone.align = align
    for zone, align in zip(zones, title_alignment(image, zones, body=body)):
        zone.title_align = align
