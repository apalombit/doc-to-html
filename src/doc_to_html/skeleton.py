"""The page's skeleton, top-down: its parts before its Zones — spec 0025, step 2 (③a).

GLM-OCR hands over the page's smallest blocks in a learned reading order
and no structure (`docs/glm-ocr.md` §3). Today's adapter builds structure
bottom-up, two blocks at a time (`adapter.groups_of`), and one wrong join
spreads. This reads it the other way: **the page is cut into parts, one
cut at a time, the page first**, from three signals checked against each
other: the boxes the page draws, the empty gaps between its blocks, and
the parser's reading order.

At each part:

1. **Drawn containers are units.** A frame or fill holding two blocks or
   more (by their centres) is one piece at this level, never cut through,
   and cut again inside (`Part.kind` "box").
2. **The gaps.** Across: a stretch of the part's height no unit reaches.
   Down: a stretch of its width no unit reaches, at least `GUTTER` lines
   wide. Measured on each block's ink (`snapped`): the layout model's
   boxes are generous. Where no gutter is clean, one that a single block
   crosses is a candidate too, the block **lifted** to the side its
   neighbour in the parser's order stands on: a last resort, taken only
   where every clean cut sets blocks against the order.
3. **The order chooses.** Each candidate cut is scored by the pairs of
   blocks it sets against the parser's order (a block of the first part
   read after one of the second), as a share of the pairs it makes; the
   fewest wins, the wider gap on a tie. **A cut down must set no more
   pairs against the order than reading the part by position does**:
   rows of label | value read across are never cut into a column of
   labels and a column of values. A cut across is taken even against the
   order: the parser errs locally on 91 of 228 dev pages (spec 0025,
   step 1), and a gap across is the page's.
4. **The roles bind.** At the page, `header` and `number` blocks above
   every other block are its top row and `footer` and `number` blocks
   below every other its bottom row, unless a drawn box holds them with the body; a
   `figure_title` is never set in another column
   than the figure, table or chart it captions.
5. **Stop** at one unit; or where no cut is taken: the part is kept
   **flat** (several blocks, today's grouping inside it) and the reason
   recorded. A run of rows each cut into the same columns, or of columns
   each cut into the same rows, every cell of three blocks or fewer, is a
   **grid** (a form's fields).

Then `check`: every block in exactly one leaf; no two sibling parts
overlapping on the blocks' ink; no column set against the order more
than the position sort; every drawn container of two blocks a part. A
part that fails is kept flat and recorded, so the worst case is today's
grouping. Constants are in lines (`adapter.line_height`), never in pixels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .adapter import FIGURES, Region, line_height
from .ir import BBox

PAGE_SHARE = 0.80
"""A drawn box covering more of the page than this is the page, not a
container (`adapter.PAGE_SHARE`)."""

GUTTER = 0.5
"""How wide a gap down a part must be, in lines, to part two columns: wider
than the space between two words, so fragments of one printed line part
only where the page sets them apart."""

GRID_CELL = 3
"""The most blocks a cell of a grid holds: a field's number, its label
and its value."""

CAPTIONED = frozenset({"image", "chart", "table", "header_image", "footer_image"})
"""What a `figure_title` captions."""


@dataclass
class Part:
    """One part of the page: its kind, its box (the union of its blocks' and
    containers' boxes, 0-1 of the picture), the parser's indices of every
    block it holds, in the parser's order, and its parts, in reading order.

    kind: "page", "rows", "columns", "grid", "box" (a drawn container),
    "block" (one of the parser's regions), "flat" (several blocks no cut
    was taken in: today's grouping inside it)."""

    kind: str
    box: BBox
    blocks: tuple[int, ...]
    children: list[Part] = field(default_factory=list)
    drawn: BBox | None = None
    note: str = ""

    def walk(self) -> list[Part]:
        out = [self]
        for child in self.children:
            out += child.walk()
        return out

    def describe(self, depth: int = 0) -> str:
        b = self.box
        line = (f"{'  ' * depth}{self.kind} ({b.left:.2f},{b.top:.2f},{b.right:.2f},"
                f"{b.bottom:.2f}) {list(self.blocks)}" + (f"  [{self.note}]" if self.note else ""))
        return "\n".join([line] + [c.describe(depth + 1) for c in self.children])


@dataclass
class _Unit:
    """A piece one cut never passes through: a block, or a drawn container
    with what it holds."""

    box: BBox
    blocks: tuple[int, ...]
    drawn: BBox | None = None
    held: list[_Unit] = field(default_factory=list)


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def _centre_in(outer: BBox, box: BBox) -> bool:
    x, y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    return outer.left <= x <= outer.right and outer.top <= y <= outer.bottom


def snapped(regions: Sequence[Region], ink: Any | None) -> dict[int, BBox]:
    """Each region's box drawn in to the ink inside it: the layout model's
    boxes are generous, and two that overlap may stand apart on the page.
    A picture keeps its box; so does a box with no ink in it."""
    out = {r.index: r.box for r in regions}
    if ink is None:
        return out
    mask = np.asarray(ink) > 0
    height, width = mask.shape[:2]
    for region in regions:
        if region.label in FIGURES:
            continue
        b = region.box
        x0, x1 = max(0, int(b.left * width)), min(width, int(np.ceil(b.right * width)))
        y0, y1 = max(0, int(b.top * height)), min(height, int(np.ceil(b.bottom * height)))
        if x1 <= x0 or y1 <= y0:
            continue
        crop = mask[y0:y1, x0:x1]
        rows, cols = np.flatnonzero(crop.any(axis=1)), np.flatnonzero(crop.any(axis=0))
        if rows.size and cols.size:
            out[region.index] = BBox((x0 + cols[0]) / width, (y0 + rows[0]) / height,
                                     (x0 + cols[-1] + 1) / width, (y0 + rows[-1] + 1) / height)
    return out


def _held(box: BBox, block: BBox) -> bool:
    """Whether a drawn box holds a block: its centre inside, or the block
    set on the box's top edge within its width, as a fieldset's legend is
    (c0093's `SIGN HERE`, its centre just above the frame's top rule)."""
    if _centre_in(box, block):
        return True
    return (block.top < box.top < block.bottom and block.left >= box.left
            and block.right <= box.right)


def _containers(regions: Sequence[Region], drawn: Sequence[BBox], boxes: Mapping[int, BBox]
                ) -> tuple[dict[tuple[int, ...], BBox], list[BBox]]:
    """The drawn boxes that hold two blocks or more, by the set they hold
    (the tightest box for each set), and those dropped because they cross
    another's set without holding it or being held by it."""
    sets: dict[tuple[int, ...], BBox] = {}
    for box in drawn:
        if (box.right - box.left) * (box.bottom - box.top) >= PAGE_SHARE:
            continue
        held = tuple(sorted(r.index for r in regions if _held(box, boxes[r.index])))
        if len(held) < 2:
            continue
        area = (box.right - box.left) * (box.bottom - box.top)
        if held not in sets or area < _area(sets[held]):
            sets[held] = box
    dropped: list[BBox] = []
    for held in sorted(sets, key=len, reverse=True):
        if held not in sets:
            continue
        mine = set(held)
        for other in [o for o in sets if o != held and len(o) <= len(held)]:
            theirs = set(other)
            if mine & theirs and not theirs <= mine:
                dropped.append(sets.pop(other))
    return sets, dropped


def _area(box: BBox) -> float:
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def _units(blocks: Sequence[int], sets: Mapping[tuple[int, ...], BBox],
           boxes: Mapping[int, BBox]) -> list[_Unit]:
    """A part's units: its outermost containers, each holding its own, and
    the blocks no container holds. A container holding every block of the
    part is its one unit (a page drawn inside a frame)."""
    mine = set(blocks)
    inside = [s for s in sets if set(s) <= mine]
    outer = [s for s in inside if not any(set(s) < set(o) for o in inside)]
    units = []
    for held in outer:
        drawn = sets[held]
        units.append(_Unit(box=_union([drawn] + [boxes[i] for i in held]), blocks=held,
                           drawn=drawn))
    taken = {i for s in outer for i in s}
    units += [_Unit(box=boxes[i], blocks=(i,)) for i in blocks if i not in taken]
    return units


@dataclass
class _Cut:
    across: bool
    first: list[_Unit]
    second: list[_Unit]
    gap: float
    """In pixels."""
    against: int
    """Pairs of blocks set against the parser's order."""
    lifted: tuple[int, ...] = ()

    @property
    def share(self) -> float:
        pairs = sum(len(u.blocks) for u in self.first) * sum(len(u.blocks) for u in self.second)
        return self.against / max(pairs, 1)


def _against(first: Sequence[_Unit], second: Sequence[_Unit]) -> int:
    later = [i for u in first for i in u.blocks]
    earlier = [i for u in second for i in u.blocks]
    return sum(1 for a in later for b in earlier if a > b)


def _by_position(units: Sequence[_Unit], boxes: Mapping[int, BBox]) -> int:
    """Pairs of a part's blocks a top-to-bottom, left-to-right reading sets
    against the parser's order."""
    blocks = sorted((i for u in units for i in u.blocks),
                    key=lambda i: (boxes[i].top, boxes[i].left))
    return sum(1 for n, a in enumerate(blocks) for b in blocks[n + 1:] if a > b)


def _gaps(spans: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """The empty stretches between sorted, merged spans."""
    out = []
    reach = None
    for start, end in sorted(spans):
        if reach is not None and start > reach:
            out.append((reach, start))
        reach = end if reach is None else max(reach, end)
    return out


def _captions(regions: Sequence[Region], boxes: Mapping[int, BBox], line: float
              ) -> dict[int, int]:
    """Each `figure_title` and the figure, table or chart it captions: the
    nearest above or below that it overlaps across."""
    out = {}
    for caption in (r for r in regions if r.label == "figure_title"):
        c = boxes[caption.index]
        best = None
        for other in regions:
            if other.label not in CAPTIONED:
                continue
            o = boxes[other.index]
            shared = min(c.right, o.right) - max(c.left, o.left)
            if shared < 0.5 * min(c.right - c.left, o.right - o.left):
                continue
            gap = max(o.top - c.bottom, c.top - o.bottom)
            if gap <= 2 * line and (best is None or gap < best[0]):
                best = (gap, other.index)
        if best is not None:
            out[caption.index] = best[1]
    return out


class _Cutter:
    def __init__(self, regions: Sequence[Region], boxes: Mapping[int, BBox],
                 sets: Mapping[tuple[int, ...], BBox], size: tuple[int, int]) -> None:
        self.boxes = boxes
        self.sets = sets
        self.width, self.height = size
        self.line = line_height(regions) * self.height
        self.captions = _captions(regions, boxes, line_height(regions))

    # -- candidates ------------------------------------------------------------

    def _cuts(self, units: list[_Unit]) -> list[_Cut]:
        cuts = []
        for across in (True, False):
            scale = self.height if across else self.width

            def span(u: _Unit, across: bool = across) -> tuple[float, float]:
                return (u.box.top, u.box.bottom) if across else (u.box.left, u.box.right)
            for start, end in _gaps([span(u) for u in units]):
                if not across and (end - start) * scale < GUTTER * self.line:
                    continue
                if across and (end - start) * scale < 1:
                    continue
                first = [u for u in units if span(u)[1] <= start]
                second = [u for u in units if span(u)[0] >= end]
                cuts.append(_Cut(across, first, second, (end - start) * scale,
                                 _against(first, second)))
            if across or len(units) < 3:
                continue
            for lifted in units:
                if lifted.drawn is not None:
                    continue
                rest = [u for u in units if u is not lifted]
                for start, end in _gaps([span(u) for u in rest]):
                    if (end - start) * scale < GUTTER * self.line:
                        continue
                    if not (lifted.box.left < start and lifted.box.right > end):
                        continue
                    first = [u for u in rest if span(u)[1] <= start]
                    second = [u for u in rest if span(u)[0] >= end]
                    if not first or not second:
                        continue
                    (first if self._side(lifted, first, second) else second).append(lifted)
                    cuts.append(_Cut(False, first, second, (end - start) * scale,
                                     _against(first, second), lifted=lifted.blocks))
        return cuts

    def _side(self, unit: _Unit, first: list[_Unit], second: list[_Unit]) -> bool:
        """Whether a lifted block goes with the first side: the side its
        neighbour in the parser's order stands on, the block before it
        first."""
        me = unit.blocks[0]
        left = {i for u in first for i in u.blocks}
        right = {i for u in second for i in u.blocks}
        before = [i for i in left | right if i < me]
        if before:
            return max(before) in left
        after = [i for i in left | right if i > me]
        if after:
            return min(after) in left
        x = (unit.box.left + unit.box.right) / 2
        return x < (_union([u.box for u in second]).left)

    def _parts_captions(self, cut: _Cut) -> bool:
        """Whether a cut down sets a caption in another column than its figure."""
        if cut.across:
            return False
        first = {i for u in cut.first for i in u.blocks}
        second = {i for u in cut.second for i in u.blocks}
        return any((c in first and f in second) or (c in second and f in first)
                   for c, f in self.captions.items())

    # -- the cut ---------------------------------------------------------------

    def part(self, units: list[_Unit], drawn: BBox | None = None) -> Part:
        blocks = tuple(sorted(i for u in units for i in u.blocks))
        box = _union([u.box for u in units] + ([drawn] if drawn else []))
        if drawn is not None:
            inner = self.part(units) if len(units) > 1 else self._leaf(units[0])
            return Part("box", box, blocks, [inner], drawn=drawn)
        if len(units) == 1:
            return self._leaf(units[0])
        # A lifted block is a last resort: only where every clean cut sets
        # blocks against the order (a figure straddling two columns' gutter).
        cuts = sorted(self._cuts(units),
                      key=lambda c: (c.share > 0, bool(c.lifted), c.share, -c.gap))
        position = _by_position(units, self.boxes)
        refused = []
        for cut in cuts:
            if self._parts_captions(cut):
                refused.append("a caption from its figure")
                continue
            if not cut.across and cut.against > position:
                refused.append(f"down against the order ({cut.against} > {position})")
                continue
            kind = "rows" if cut.across else "columns"
            children = []
            for side in (cut.first, cut.second):
                child = self.part(side)
                children += child.children if child.kind == kind and not child.note else [child]
            note = f"lifted {list(cut.lifted)}" if cut.lifted else ""
            return Part(kind, box, blocks, children, note=note)
        return Part("flat", box, blocks,
                    note="no cut" + (f": {refused[0]}" if refused else ""))

    def _leaf(self, unit: _Unit) -> Part:
        if unit.drawn is not None:
            inner = _units(unit.blocks, {s: b for s, b in self.sets.items()
                                         if set(s) < set(unit.blocks)}, self.boxes)
            return self.part(inner, drawn=unit.drawn)
        return Part("block", unit.box, unit.blocks)


def _grids(part: Part, across: float, down: float) -> None:
    """A run of rows each cut into the same columns, every cell of
    `GRID_CELL` blocks or fewer, is a grid; so is a run of columns each cut
    into the same rows (c0511's four fields, read column by column).
    `across` and `down` are a line's height as a share of the page's width
    and of its height: a column's cells start or end within half a line of
    each other, and so do a row's, as a form's fields do (c0511's `Venue`
    is read with its label, `Date` without: their tops differ, their feet
    meet); two lists side by side, their items wrapped differently, do not
    (c0511's ADMISSION and GETTING HERE)."""
    for child in part.children:
        _grids(child, across, down)
    if part.kind not in ("rows", "columns") or len(part.children) < 2:
        return
    inner = "columns" if part.kind == "rows" else "rows"
    runs = part.children
    if not all(r.kind == inner and len(r.children) == len(runs[0].children) >= 2 for r in runs):
        return
    if any(len(cell.blocks) > GRID_CELL for r in runs for cell in r.children):
        return
    slack = 0.5 * (across if inner == "columns" else down)
    for n in range(len(runs[0].children)):
        cells = [r.children[n].box for r in runs]
        starts = [c.left if inner == "columns" else c.top for c in cells]
        ends = [c.right if inner == "columns" else c.bottom for c in cells]
        if min(max(starts) - min(starts), max(ends) - min(ends)) > slack:
            return
    part.kind = "grid"


def skeleton(regions: Sequence[Region], drawn: Sequence[BBox] = (), ink: Any | None = None,
             size: tuple[int, int] = (1000, 1000)) -> Part:
    """The page's parts, top-down. `drawn` is every box the page draws
    (`parser_first.containers`); `ink` the page's content ink, rules
    removed and fills read against their own ground; `size` the picture's
    width and height, which turn the boxes' shares into pixels."""
    boxes = snapped(regions, ink)
    sets, dropped = _containers(regions, drawn, boxes)
    cutter = _Cutter(regions, boxes, sets, size)
    every = [r.index for r in regions]
    page = BBox(0.0, 0.0, 1.0, 1.0)
    if not every:
        return Part("page", page, ())
    edges = ("header", "header_image", "footer", "footer_image", "number")
    body = [r for r in regions if r.label not in edges]
    top = min((boxes[r.index].top for r in body), default=1.0)
    foot = max((boxes[r.index].bottom for r in body), default=0.0)
    # A drawn box holding a body block keeps its page-edge blocks with it.
    boxed = {i for s in sets if any(r.index in s and r.label not in edges for r in regions)
             for i in s}
    heads = [r.index for r in regions if r.label in ("header", "header_image", "number")
             and boxes[r.index].bottom <= top and r.index not in boxed]
    feet = [r.index for r in regions if r.label in ("footer", "footer_image", "number")
            and boxes[r.index].top >= foot and r.index not in boxed and r.index not in heads]
    middle = [i for i in every if i not in heads and i not in feet]
    rows = [cutter.part(_units(group, sets, boxes)) for group in (heads, middle, feet) if group]
    root = Part("page", _union([p.box for p in rows]), tuple(sorted(every)), rows)
    root.note = f"{len(dropped)} drawn boxes crossing another dropped" if dropped else ""
    _grids(root, cutter.line / size[0], cutter.line / size[1])
    return check(root, regions, boxes, sets)


# ---- the check ------------------------------------------------------------------

def problems(part: Part, boxes: Mapping[int, BBox]) -> list[str]:
    """What is wrong with one part's own cut: two of its parts overlapping
    on their blocks' ink, or a column set against the order more than
    reading by position."""
    found = []
    if part.kind in ("rows", "columns", "grid"):
        spans = [_union([boxes[i] for i in c.blocks]) for c in part.children]
        lifted = "lifted" in part.note
        for n, a in enumerate(spans):
            for b in spans[n + 1:]:
                if (not lifted and min(a.right, b.right) > max(a.left, b.left)
                        and min(a.bottom, b.bottom) > max(a.top, b.top)):
                    found.append("two parts overlap")
        if part.kind == "columns":
            units = [_Unit(box=s, blocks=c.blocks) for s, c in zip(spans, part.children)]
            against = sum(_against(units[n:n + 1], units[m:m + 1])
                          for n in range(len(units)) for m in range(n + 1, len(units)))
            if against > _by_position(units, boxes):
                found.append("columns against the order")
    return found


def check(root: Part, regions: Sequence[Region], boxes: Mapping[int, BBox],
          sets: Mapping[tuple[int, ...], BBox]) -> Part:
    """The skeleton checked: each failing part kept flat, the reason
    recorded. Every block in exactly one leaf, and every drawn container of
    two blocks a part, or the page itself is flat."""
    def mend(part: Part) -> Part:
        wrong = problems(part, boxes)
        if wrong:
            return Part("flat", part.box, part.blocks, note="check: " + ", ".join(sorted(set(wrong))))
        part.children = [mend(c) for c in part.children]
        return part

    root = mend(root)
    leaves = [i for p in root.walk() if not p.children for i in p.blocks]
    every = sorted(r.index for r in regions)
    if sorted(leaves) != every:
        return Part("flat", root.box, root.blocks, note="check: a block not in exactly one leaf")
    held = {p.blocks for p in root.walk() if p.kind == "box"}
    flat = [p for p in root.walk() if p.kind == "flat"]
    for blocks in sets:
        if blocks not in held and not any(set(blocks) <= set(f.blocks) for f in flat):
            root.note = (root.note + "; " if root.note else "") + f"container {list(blocks)} not a part"
    return root
