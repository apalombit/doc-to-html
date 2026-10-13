"""What in the render draws each piece of furniture — spec 0012, G3a.

`furniture.find` says what the page draws that is not type, and where. This
says which element of the render each record is a border of, so it is drawn
in the flow with the thing it belongs to and never placed by coordinates
(ADR 0002, 0005). Each record goes to the first of these that holds it:

- **A frame round the whole page** is the page's border — `certificate_0021`.
- **A frame the render already draws** — a card's, a frame Zones share —
  gives that border its measured width, style and colour; **a frame round
  one Zone it fills** becomes that Zone's border — `form_0007`'s
  `OFFICE USE`.
- **A rule beside a lane's edge, down a `columns` Region**, is the lane's
  left border — `newsletter_0008`'s and `paper_0018`'s column rules.
- **A short vertical rule just left of a Zone**, alongside it, is its side
  bar — `statement_0006`'s tiles, `TL;DR` — or its Title's, where it runs
  beside the Title only — `form_0007`'s heads. **Inside a table**, the
  bar is the left border of the cell it stands beside — `timetable_0019`'s
  lessons.
- **A rule inside a Zone that spans it** is a border of what it lies
  between: under the Title — `cv_0013`'s headings — above or below the
  Zone's entries, or above the Block or pair it stands over. Inside a
  table it is the top border of the cells it runs over, where `looks` has
  not drawn the line under the row above — `invoice_0001`'s rule over
  `Total`. **One that does not span the Zone is not drawn**: it is a link's
  underline, which the run draws.
- **A rule between Zones** is drawn between the rows of the stack that
  holds it — the page's, a lane's, a frame's — at the height the page draws
  it, as wide as the page draws it: the letterhead's rule, the abstract's,
  the signature lines.
- **A hatched fill** over the top of a Zone is drawn there — `catalogue_0015`'s
  pictures — and behind a table's rows, the rows it covers.

**Never drawn, because something else already draws it:** anything inside a
figure, which is drawn from its pixels; a rule along a drawn box's edge; a
field's box or line (`fields`); a table's lines between rows and its row
fills (`looks`); a plain fill, which `style.chrome` measured as a Zone's
fill, Title bar or header bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ir import BBox, Document, Flow, Furniture, Kind, Region, Zone

PAGE_FRAME = 0.8
"""How much of the page a frame encloses to be the page's own border."""

FILLS = 0.5
"""How much of a frame the one Zone inside it covers, to be drawn as that
Zone's border: `form_0007`'s `OFFICE USE` Zone is its frame's box exactly.
A field's box holds no Zone's middle at all."""

EDGE = 3.0
"""How near, in source pixels, a rule lies to a drawn box's edge to be that
edge."""

SPANS = 2.0
"""How near, in body ems, a rule inside a Zone reaches each of its edges to
span it. `cv_0013`'s heading rules run past the Zone's right edge; a link's
underline in `sample_semantic_0005` starts 2.4 ems in from its Zone's left."""

SIDE = 2.5
"""How far left of a Zone's ink, in body ems, its side bar stands at most:
`sample_semantic_0005`'s TL;DR bar stands 0.9 ems from its type, inside the
aside's padding."""

ALONG = 0.5
"""How much of a side bar's height runs alongside its Zone."""

SPLIT = 0.03
"""How near a `columns` Region's split, as a share of the page's width, a
rule down it stands to be the lanes' divider."""

DOWN = 0.5
"""How much of a `columns` Region's height that divider runs."""

SPANNED = 0.8
"""How much of a table's width a rule over a row runs to be drawn over
every cell of it."""

UNDER = 0.4
"""How far below a Zone's ink, in body ems, a rule that does not span the
Zone is that ink's underline."""


@dataclass
class Anchors:
    """Each record by what draws it. Zones, rows, Blocks, pairs and cells are
    by index into the Document."""

    page: Furniture | None = None
    boxes: dict[int, Furniture] = field(default_factory=dict)
    frames: dict[BBox, Furniture] = field(default_factory=dict)
    sides: dict[int, Furniture] = field(default_factory=dict)
    title_sides: dict[int, Furniture] = field(default_factory=dict)
    under_title: dict[int, Furniture] = field(default_factory=dict)
    tops: dict[int, Furniture] = field(default_factory=dict)
    bottoms: dict[int, Furniture] = field(default_factory=dict)
    blocks: dict[tuple[int, int], Furniture] = field(default_factory=dict)
    pairs: dict[tuple[int, int], Furniture] = field(default_factory=dict)
    cell_lefts: dict[tuple[int, int, int], Furniture] = field(default_factory=dict)
    cell_tops: dict[tuple[int, int, int], Furniture] = field(default_factory=dict)
    hatches: dict[int, Furniture] = field(default_factory=dict)
    rows: dict[tuple[int, int], Furniture] = field(default_factory=dict)
    lanes: list[tuple[Region, int, Furniture]] = field(default_factory=list)
    between: list[Furniture] = field(default_factory=list)


@dataclass(frozen=True)
class _Scale:
    """Source pixels per unit of a normalised box, and the body's size."""

    x: float
    y: float
    body: float


def anchor(document: Document) -> Anchors:
    """Where the render draws each of `document.furniture`."""
    out = Anchors()
    if not document.furniture:
        return out
    scale = _scale(document)
    zones = document.zones
    figures = [z.bbox for z in zones if z.kind is Kind.FIGURE and z.bbox is not None]
    counts: dict[BBox, int] = {}
    for zone in zones:
        if zone.frame is not None:
            counts[zone.frame] = counts.get(zone.frame, 0) + 1
    drawn = [frame for frame, count in counts.items() if count > 1]
    drawn += [z.frame for z in zones if z.boxed and z.frame is not None]
    marks = [mark.bbox for z in zones for pair in z.pairs for mark in pair.marks]

    for item in document.furniture:
        box = item.bbox
        if any(_holds(figure, box, scale) for figure in figures):
            continue
        if item.kind == "frame":
            _frame(item, document, counts, out)
        elif item.kind == "fill":
            if item.style == "hatched":
                _hatch(item, document, out)
        elif any(_on_edge(item, frame, scale) for frame in drawn):
            continue
        elif item.vertical:
            _vertical(item, document, scale, out)
        elif not any(_marks(item, mark, scale) for mark in marks):
            _horizontal(item, document, scale, out)
    return out


def _scale(document: Document) -> _Scale:
    source = document.source
    wide = source.rectified_width or source.width
    tall = source.rectified_height or source.height
    ratio = source.width / wide if wide else 1.0
    body = (document.style.body_px if document.style is not None
            and document.style.body_px else 16.0)
    return _Scale(x=float(source.width), y=tall * ratio, body=body)


def _holds(outer: BBox, box: BBox, scale: _Scale) -> bool:
    """Whether `box`'s middle lies inside `outer`, a pixel's slack round it."""
    slack_x, slack_y = 1 / scale.x, 1 / scale.y
    middle_x, middle_y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    return (outer.left - slack_x <= middle_x <= outer.right + slack_x
            and outer.top - slack_y <= middle_y <= outer.bottom + slack_y)


def _area(box: BBox) -> float:
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _same_box(one: BBox, other: BBox, scale: _Scale) -> bool:
    return (abs(one.left - other.left) * scale.x <= EDGE
            and abs(one.right - other.right) * scale.x <= EDGE
            and abs(one.top - other.top) * scale.y <= EDGE
            and abs(one.bottom - other.bottom) * scale.y <= EDGE)


def _frame(item: Furniture, document: Document, counts: dict[BBox, int],
           out: Anchors) -> None:
    box = item.bbox
    if _area(box) >= PAGE_FRAME:
        if out.page is None or _area(box) > _area(out.page.bbox):
            out.page = item
        return
    scale = _scale(document)
    for index, zone in enumerate(document.zones):
        if zone.frame is not None and _same_box(zone.frame, box, scale):
            if counts.get(zone.frame, 0) > 1:
                out.frames[zone.frame] = item
            elif zone.boxed:
                out.boxes[index] = item
            return
    inside = [index for index, zone in enumerate(document.zones)
              if zone.bbox is not None and _holds(box, zone.bbox, scale)]
    if len(inside) == 1:
        zone = document.zones[inside[0]]
        assert zone.bbox is not None
        if not zone.boxed and _area(zone.bbox) >= FILLS * _area(box):
            out.boxes[inside[0]] = item


def _hatch(item: Furniture, document: Document, out: Anchors) -> None:
    """Behind the table rows it covers, or across the top of the Zone whose
    box or frame it opens — `catalogue_0015`'s pictures, a card's SKU
    printed over each."""
    box = item.bbox
    for index, zone in enumerate(document.zones):
        if zone.bbox is None:
            continue
        if zone.kind is Kind.TABLE and _overlap(box.top, box.bottom, zone.bbox.top,
                                                zone.bbox.bottom) > 0:
            for position, row in enumerate(zone.rows):
                tops = [c.bbox for c in row.cells if c.bbox is not None]
                if tops and all(box.top <= (b.top + b.bottom) / 2 <= box.bottom
                                for b in tops):
                    out.rows[(index, position)] = item
            continue
        holder = zone.frame or zone.bbox
        if (holder.left - 0.005 <= box.left and box.right <= holder.right + 0.005
                and abs(box.top - holder.top) <= 0.01 and box.bottom < holder.bottom):
            out.hatches[index] = item
            return


def _entries(zone: Zone) -> list[BBox]:
    """The boxes of everything the Zone holds that `locate` placed."""
    cells = [line for block in zone.blocks for line in block.lines]
    cells += [cell for pair in zone.pairs for cell in (pair.label, pair.value)]
    cells += [cell for row in zone.rows for cell in row.cells]
    return [cell.bbox for cell in cells if cell.bbox is not None]


def _on_edge(item: Furniture, frame: BBox, scale: _Scale) -> bool:
    """Whether a rule lies along one of `frame`'s edges, over half of it."""
    box = item.bbox
    if item.vertical:
        along = _overlap(box.top, box.bottom, frame.top, frame.bottom)
        return along >= 0.5 * (box.bottom - box.top) and min(
            abs(box.left - frame.left), abs(box.right - frame.right)) * scale.x <= EDGE
    along = _overlap(box.left, box.right, frame.left, frame.right)
    return along >= 0.5 * (box.right - box.left) and min(
        abs(box.top - frame.top), abs(box.bottom - frame.bottom)) * scale.y <= EDGE


def _marks(item: Furniture, mark: BBox, scale: _Scale) -> bool:
    """Whether a rule is a field's mark — its line, or an edge of its box."""
    box = item.bbox
    along = _overlap(box.left, box.right, mark.left, mark.right)
    return (along >= 0.5 * (box.right - box.left)
            and (box.top - EDGE / scale.y <= mark.bottom
                 and mark.top <= box.bottom + EDGE / scale.y))


def _vertical(item: Furniture, document: Document, scale: _Scale,
              out: Anchors) -> None:
    box = item.bbox
    middle = (box.left + box.right) / 2
    tall = box.bottom - box.top
    for region in document.regions:
        if region.flow is not Flow.COLUMNS:
            continue
        down = _overlap(box.top, box.bottom, region.top, region.bottom)
        for lane, split in enumerate(region.splits, start=1):
            if abs(middle - split) <= SPLIT and down >= DOWN * (region.bottom - region.top):
                out.lanes.append((region, lane, item))
                return

    side = SIDE * scale.body / scale.x
    for index, zone in enumerate(document.zones):
        holder = zone.bbox
        if holder is None or zone.kind is not Kind.TABLE:
            continue
        if not (holder.left - side <= box.left <= holder.right
                and _overlap(box.top, box.bottom, holder.top, holder.bottom) > 0):
            continue
        for position, row in enumerate(zone.rows):
            beside = [(cell.bbox.left - box.right, number)
                      for number, cell in enumerate(row.cells)
                      if cell.bbox is not None
                      and -1 / scale.x <= cell.bbox.left - box.right <= side
                      and _overlap(box.top, box.bottom, cell.bbox.top, cell.bbox.bottom) > 0]
            if beside:
                out.cell_lefts[(index, position, min(beside)[1])] = item
        return

    best: tuple[float, int] | None = None
    for index, zone in enumerate(document.zones):
        holder = zone.bbox
        if holder is None or zone.kind in (Kind.TABLE, Kind.FIGURE):
            continue
        gap = holder.left - box.right
        alongside = _overlap(box.top, box.bottom, holder.top, holder.bottom)
        # Left of the Zone's ink, or on its left edge: `form_0007`'s head
        # bars open the shaded Title bar the Zone's box starts at.
        edge = -(box.right - box.left) - 1 / scale.x
        if (edge <= gap <= side and alongside >= ALONG * tall
                and (best is None or gap < best[0])):
            best = (gap, index)
    if best is None:
        return
    index = best[1]
    zone = document.zones[index]
    assert zone.bbox is not None
    if (zone.title and _entries(zone)
            and box.bottom <= min(b.top for b in _entries(zone))):
        out.title_sides[index] = item
    else:
        out.sides[index] = item


def _spans(item: Furniture, zone: Zone, scale: _Scale) -> bool:
    assert zone.bbox is not None
    reach = SPANS * scale.body / scale.x
    return (item.bbox.left <= zone.bbox.left + reach
            and item.bbox.right >= zone.bbox.right - reach)


def _horizontal(item: Furniture, document: Document, scale: _Scale,
                out: Anchors) -> None:
    box = item.bbox
    middle = (box.top + box.bottom) / 2
    if item.zone is not None and 0 <= item.zone < len(document.zones):
        index = item.zone
        zone = document.zones[index]
        if zone.kind is Kind.TABLE:
            _in_table(item, index, zone, out)
        elif zone.kind is not Kind.FIGURE and _spans(item, zone, scale):
            _in_zone(item, index, zone, out)
        return

    for zone in document.zones:
        if (zone.kind is Kind.TABLE and zone.bbox is not None and zone.rows
                and zone.rows[-1].under is not None
                and zone.rows[-1].under.kind != "none"
                and 0 <= box.top - zone.bbox.bottom <= 2 * scale.body / scale.y
                and _overlap(box.left, box.right, zone.bbox.left, zone.bbox.right)
                >= 0.5 * (box.right - box.left)):
            return  # the line under the table's last row, which `looks` draws
    under = UNDER * scale.body / scale.y
    above = [(box.top - zone.bbox.bottom, index)
             for index, zone in enumerate(document.zones)
             if zone.bbox is not None and zone.kind is not Kind.FIGURE
             and -1 / scale.y <= box.top - zone.bbox.bottom <= 2 * scale.body / scale.y
             and _overlap(box.left, box.right, zone.bbox.left, zone.bbox.right) > 0]
    for gap, index in above:
        if gap <= under and not _spans(item, document.zones[index], scale):
            return  # a run's underline below the last line of its Zone
    home = container(box, document.regions)
    crossed = any(zone.bbox is not None and zone.bbox.top < middle < zone.bbox.bottom
                  and container(zone.bbox, document.regions) == home
                  for zone in document.zones)
    reach = SPANS * scale.body / scale.x
    starts = [(gap, index) for gap, index in above
              if abs(document.zones[index].bbox.left - box.left) <= reach]  # type: ignore[union-attr]
    if crossed and starts:
        # A Zone beside it reaches below it, so the stack has no gap to draw
        # it in — `form_0007`'s rule under its title, which runs on under
        # `OFFICE USE`: drawn under the Zone it starts under.
        out.bottoms.setdefault(min(starts)[1], item)
        return
    out.between.append(item)


def container(box: BBox, regions: list[Region]) -> tuple[int, int] | None:
    """The `columns` Region and lane `box` is drawn in, by index, or None for
    the page's own stack."""
    middle = (box.top + box.bottom) / 2
    for number, region in enumerate(regions):
        if region.flow is Flow.COLUMNS and region.top <= middle <= region.bottom:
            return number, region.lane_of(box)
    return None


def _in_table(item: Furniture, index: int, zone: Zone, out: Anchors) -> None:
    """The cells a rule runs over, unless `looks` drew it under the row above."""
    box = item.bbox
    middle = (box.top + box.bottom) / 2
    for position, row in enumerate(zone.rows):
        boxes = [c.bbox for c in row.cells if c.bbox is not None]
        if not boxes or min(b.top for b in boxes) < middle:
            continue
        above = zone.rows[position - 1] if position else None
        if above is not None and above.under is not None and above.under.kind != "none":
            return
        # Across the table, over every cell — an empty one has no box to
        # place it by, and `receipt_0010`'s rule broke over its gap.
        across = (zone.bbox is not None and box.right - box.left
                  >= SPANNED * (zone.bbox.right - zone.bbox.left))
        for number, cell in enumerate(row.cells):
            if across or (cell.bbox is not None and box.left
                          <= (cell.bbox.left + cell.bbox.right) / 2 <= box.right):
                out.cell_tops[(index, position, number)] = item
        return


def _in_zone(item: Furniture, index: int, zone: Zone, out: Anchors) -> None:
    """Under the Title, over the first entry, under the last, or over the
    Block or pair it stands above."""
    box = item.bbox
    middle = (box.top + box.bottom) / 2
    if zone.kind is Kind.PAIRS:
        spans = [_union([c.bbox for c in (p.label, p.value) if c.bbox is not None])
                 for p in zone.pairs]
    else:
        spans = [_union([c.bbox for c in b.lines if c.bbox is not None])
                 for b in zone.blocks]
    placed = [(number, span) for number, span in enumerate(spans) if span is not None]
    if not placed:
        return
    if middle <= min(span.top for _, span in placed):
        if zone.title:
            out.under_title.setdefault(index, item)
        else:
            out.tops.setdefault(index, item)
        return
    if middle >= max(span.bottom for _, span in placed):
        out.bottoms.setdefault(index, item)
        return
    for (_, upper), (number, lower) in zip(placed, placed[1:]):
        if upper.bottom <= middle <= lower.top:
            key = (index, number)
            if zone.kind is Kind.PAIRS:
                out.pairs.setdefault(key, item)
            else:
                out.blocks.setdefault(key, item)
            return


def _union(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))
