"""The marks a page draws for its entries to be written in — spec 0011, step 3.

**Why it exists.** `form_0007` is a grid of fields: a label over a box, a
row of boxes one digit each, tick boxes beside their options, values written
on rules and signature lines over their captions. The IR had none of it, so
the renderer drew a two-column list of labels and plain values. Everything
here is measured from pixels — ADR 0005, never asked — and attached to the
Cells step 2 placed (`locate`). **Nothing is invented or dropped**: every
word drawn is a word the model read; a mark is drawn, never a word.

**Found page-wide, then attached.** A field's rule can lie outside its Zone:
the Zone is snapped onto its content ink, and an empty rule under a label is
not content — `form_0007`'s medical field's two rules sit below its Zone, and
spec 0009 had read them as separators. So the marks are taken off the whole
page once (`find`), and a mark joins a pair only by its geometry against that
pair's own Cells (`read`), in glyph heights of the body.

What `find` reports, measured over the fifteen documents on 2026-10-12: boxes
of field size only on `form_0007` (29: eight comb boxes, eight tick boxes, 13
value boxes) and one 17×12 shape inside a `catalogue_0015` card that touches
no Cell; rules on eleven pages, each of which attaches only where it starts
under a pair's own label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .ir import BBox, Cell, Document, Kind, Mark, Pair, Zone, cell
from .preprocess import ImageArray, _cv2
from .style import body_glyph

BOX, COMB, TICK, LINE = "box", "comb", "tick", "line"

INK = 60
"""Grey levels from the page's ground at which a pixel is ink. `form_0007`'s
boxes are drawn in `#767676` on white, 137 away; its fills, `#ececec` and
`#fdfdfd`, 19 and 2."""

RULE_THICK = 0.35
"""A rule is no thicker than this many glyph heights (3px at least)."""

RULE_LONG = 4.0
"""...and at least this many long. A dash, a hyphen and a letter are not."""

EDGE_RUN = 0.8
"""How much of each of its four edges a box's own outline inks."""

HOLLOW = 0.5
"""How much of its inside a box's outline may ink — an outline, not a blob."""

BOX_LOW, BOX_HIGH = 1.2, 4.0
"""A field's box is this many glyph heights tall, from a tick box (1.4 on
`form_0007`) to a value box (2.7). A letter is at most 1.0 at body size; a
card or a panel is taller."""

TICK_SIDE = 1.8
"""A tick box is square and no wider than this many glyph heights."""

SQUARE = 0.25
"""How far from square a tick box may be, as a share of its side."""

COMB_LEAST = 3
"""How many equal boxes in a row make a comb."""

COMB_GAP = 0.5
"""A comb's boxes stand closer than this share of one box's width."""

VALUE_LEAST = 3.0
"""A value box is at least this many glyph heights wide."""

TICKED = 0.1
"""A tick box holds a mark when ink covers more of its inside than this.
Measured over the corpus's eight tick boxes, inside the 1px outline: empty
0.00 on all four, ticked 0.27-0.28 on all four. The threshold sits in the
gap, nearer the empty side because an empty box has no ink at all."""

BESIDE = 2.0
"""A tick box stands within this many glyph heights left of its option's
placed words: 0.5 on `form_0007`, and 1.2 where tesseract missed a leading
`I` and the option's box starts at `can`."""

UNDER = 1.0
"""A rule a value is written on lies within this many glyph heights below
it; a box or a rule for an empty value, below its label."""

SAME_LEFT = 1.0
"""A mark belongs to a field when it starts within this many glyph heights
of the field's label or value."""

MORE_LINES = 6.0
"""A second rule under the first, as far down as this many glyph heights,
is the same field's next line — `form_0007`'s medical field draws two."""


def _ground(grey: ImageArray) -> int:
    values, counts = np.unique(grey, return_counts=True)
    return int(values[counts.argmax()])


def _outlined(mask: ImageArray) -> bool:
    """Whether a component's own pixels draw a box: every edge inked, the
    inside hollow."""
    def edge(rows: ImageArray) -> float:
        return float(max(rows[k].mean() for k in range(min(2, len(rows)))))
    if min(edge(mask), edge(mask[::-1]), edge(mask.T), edge(mask.T[::-1])) < EDGE_RUN:
        return False
    inside = mask[3:-3, 3:-3]
    return bool(inside.size) and float(inside.mean()) <= HOLLOW


def find(image: ImageArray, glyph: float) -> list[Mark]:
    """Every field mark on the page, top to bottom: rules, value boxes,
    combs and tick boxes, with each tick box's state."""
    cv2 = _cv2()
    grey = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3
            else image).astype(np.int32)
    height, width = grey.shape
    ink = np.abs(grey - _ground(grey)) > INK
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        ink.astype(np.uint8), connectivity=8)

    def box(x: int, y: int, w: int, h: int) -> BBox:
        return BBox(x / width, y / height, (x + w) / width, (y + h) / height)

    marks: list[Mark] = []
    outlines: list[tuple[int, int, int, int]] = []
    for index in range(1, count):
        x, y, w, h, _ = (int(v) for v in stats[index])
        if h <= max(3.0, RULE_THICK * glyph) and w >= RULE_LONG * glyph:
            marks.append(Mark(kind=LINE, bbox=box(x, y, w, h)))
        elif (BOX_LOW * glyph <= h <= BOX_HIGH * glyph and w >= BOX_LOW * glyph
              and _outlined(labels[y:y + h, x:x + w] == index)):
            outlines.append((x, y, w, h))

    outlines.sort(key=lambda o: (o[1], o[0]))
    used: set[int] = set()
    for first, (x, y, w, h) in enumerate(outlines):
        if first in used:
            continue
        run = [first]
        for later in range(first + 1, len(outlines)):
            lx, ly, lw, lh = outlines[later]
            px, _, pw, _ = outlines[run[-1]]
            if (abs(ly - y) <= 2 and abs(lw - w) <= 2 and abs(lh - h) <= 2
                    and 0 <= lx - (px + pw) < COMB_GAP * w):
                run.append(later)
        if len(run) >= COMB_LEAST:
            used.update(run)
            last = outlines[run[-1]]
            marks.append(Mark(kind=COMB, count=len(run),
                              bbox=box(x, y, last[0] + last[2] - x, h)))
            continue
        used.add(first)
        if abs(w - h) <= SQUARE * max(w, h) and max(w, h) <= TICK_SIDE * glyph:
            inside = ink[y + 2:y + h - 2, x + 2:x + w - 2]
            marks.append(Mark(kind=TICK, bbox=box(x, y, w, h),
                              ticked=bool(inside.size) and float(inside.mean()) > TICKED))
        elif w >= VALUE_LEAST * glyph:
            marks.append(Mark(kind=BOX, bbox=box(x, y, w, h)))
    return sorted(marks, key=lambda m: (round(m.bbox.top, 4), m.bbox.left))


@dataclass
class _Fit:
    """The page's scale for one document, for comparing boxes in glyphs."""

    glyph_y: float
    glyph_x: float

    def below(self, upper: BBox, lower: BBox, reach: float) -> bool:
        """`lower` starts under `upper`'s bottom, within `reach` glyphs."""
        gap = (lower.top - upper.bottom) / self.glyph_y
        return -0.3 <= gap <= reach

    def flush(self, a: BBox, b: BBox) -> bool:
        return abs(a.left - b.left) / self.glyph_x <= SAME_LEFT


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def _inside(inner: BBox, outer: BBox) -> bool:
    return inner.overlap_ratio(outer) >= 0.8


def _middle(box: BBox) -> float:
    return (box.top + box.bottom) / 2


def _empty(value: Cell) -> bool:
    return not value.text.strip() or value.bbox is None


def _own(pair: Pair, marks: Sequence[Mark], free: set[int],
         fit: _Fit) -> tuple[list[int], list[int]]:
    """The first pass: the marks a pair's own placed Cells sit in, on or
    beside — and, set aside unattached, a rule on the label's own line that
    the model read as the value's characters. Returns (taken, set aside)."""
    label, value = pair.label.bbox, pair.value.bbox
    assert label is not None
    for i in sorted(free):
        mark = marks[i]
        gap = (label.left - mark.bbox.right) / fit.glyph_x
        if (mark.kind == TICK and -0.2 <= gap <= BESIDE
                and mark.bbox.top <= _middle(label) <= mark.bbox.bottom):
            return [i], []
    if value is not None and pair.value.text.strip():
        for i in sorted(free):
            mark = marks[i]
            if mark.kind in (BOX, COMB) and _inside(value, mark.bbox):
                return [i], []
        for i in sorted(free):
            mark = marks[i]
            if (mark.kind == LINE and fit.below(value, mark.bbox, UNDER)
                    and (fit.flush(mark.bbox, label) or fit.flush(mark.bbox, value))
                    and mark.bbox.right >= value.right):
                return [i], []
    if pair.value.text.strip() and value is None:
        # `form_0007`'s `Ref. ____`: the value the model read is the rule.
        # Printed as read, so nothing is drawn for it — but it is this
        # pair's, and `Date stamp`, centred under it, must not take it as a
        # signature line.
        for i in sorted(free):
            mark = marks[i]
            if (mark.kind == LINE and mark.bbox.left >= label.right
                    and label.top <= mark.bbox.bottom <= label.bottom + UNDER * fit.glyph_y):
                return [], [i]
    return [], []


def _under(pair: Pair, marks: Sequence[Mark], free: set[int],
           fit: _Fit) -> list[int]:
    """The second pass, for a value the page leaves blank or the model left
    unplaced: a box under the label, or the rules under it — one or more."""
    label = pair.label.bbox
    assert label is not None
    for i in sorted(free):
        mark = marks[i]
        if (mark.kind in (BOX, COMB) and fit.below(label, mark.bbox, UNDER)
                and fit.flush(mark.bbox, label)):
            return [i]
    taken: list[int] = []
    for i in sorted(free, key=lambda i: marks[i].bbox.top):
        mark = marks[i]
        if mark.kind != LINE or not fit.flush(mark.bbox, label):
            continue
        above = label if not taken else marks[taken[-1]].bbox
        reach = 3.0 * UNDER if not taken else MORE_LINES
        wide = mark.bbox.right - mark.bbox.left
        if fit.below(above, mark.bbox, reach) and (not taken or abs(
                wide - (marks[taken[0]].bbox.right - marks[taken[0]].bbox.left))
                / fit.glyph_x <= SAME_LEFT):
            taken.append(i)
    return taken


def _over(pair: Pair, marks: Sequence[Mark], free: set[int],
          fit: _Fit) -> list[int]:
    """The last pass: a signature line, its caption printed under it."""
    label = pair.label.bbox
    assert label is not None
    for i in sorted(free):
        mark = marks[i]
        if (mark.kind == LINE and fit.flush(mark.bbox, label)
                and fit.below(mark.bbox, label, UNDER)):
            return [i]
    return []


def _claim(pairs: Sequence[Pair], marks: Sequence[Mark],
           free: set[int], fit: _Fit) -> list[list[int]]:
    """Each pair's marks, claimed in three passes over all the pairs — what
    a pair's own Cells sit in first, then what lies under a blank value's
    label, then a signature line over its caption — so that a rule one
    pair writes on is never another's signature line. `free` loses every
    mark claimed or set aside."""
    taken: list[list[int]] = [[] for _ in pairs]
    open_ = [i for i, pair in enumerate(pairs) if pair.label.bbox is not None]
    for i in open_:
        taken[i], aside = _own(pairs[i], marks, free, fit)
        free.difference_update(taken[i] + aside)
    blank = [i for i in open_ if not taken[i]
             and (not pairs[i].value.text.strip() or pairs[i].value.bbox is None)]
    for i in blank:
        taken[i] = _under(pairs[i], marks, free, fit)
        free.difference_update(taken[i])
    for i in blank:
        if not taken[i]:
            taken[i] = _over(pairs[i], marks, free, fit)
            free.difference_update(taken[i])
    return taken


def _options(zone: Zone, marks: Sequence[Mark], free: set[int],
             fit: _Fit) -> list[Pair] | None:
    """A list Zone whose every line stands beside a tick box, as one option
    per box: the line the label, an empty value, the box its mark."""
    lines = [line for block in zone.blocks for line in block.lines]
    if not lines or any(line.bbox is None for line in lines):
        return None
    pairs = [Pair(label=line, value=cell("")) for line in lines]
    taken = _claim(pairs, marks, set(free), fit)
    if not all(len(t) == 1 and marks[t[0]].kind == TICK for t in taken):
        return None
    for pair, (i,) in zip(pairs, taken):
        pair.marks = [marks[i]]
    return pairs


def _grid(zone: Zone, marks: Sequence[Mark], free: set[int],
          fit: _Fit) -> list[Pair] | None:
    """A table whose rows go label, value, label, value — every value row's
    cells each in a box under its label — as one field per column per pair
    of rows. `form_0007`'s emergency contact, which the model read as a
    table of four rows."""
    rows = zone.rows
    if len(rows) < 2 or len(rows) % 2:
        return None
    pairs: list[Pair] = []
    for labels, values in zip(rows[0::2], rows[1::2]):
        if len(labels.cells) != len(values.cells):
            return None
        for label, value in zip(labels.cells, values.cells):
            if label.bbox is None or any(
                    _inside(label.bbox, marks[i].bbox)
                    for i in free if marks[i].kind == BOX):
                return None
            pairs.append(Pair(label=label, value=value))
    taken = _claim(pairs, marks, set(free), fit)
    if not all(len(t) == 1 and marks[t[0]].kind == BOX for t in taken):
        return None
    for pair, (i,) in zip(pairs, taken):
        pair.marks = [marks[i]]
    return pairs


def read(image: ImageArray, document: Document) -> None:
    """Attach the page's field marks to the pairs they belong to — spec 0011,
    step 3b. A list of tick options and a table of label rows over value
    boxes become pairs Zones of fields; every other Zone keeps its Kind. A
    rule a field claims stops being a separator. Each mark is claimed once.
    """
    glyph = body_glyph(image, document.zones)
    for zone in document.zones:
        for pair in zone.pairs:
            pair.marks = []
    if not glyph:
        return
    marks = find(image, glyph)
    if not marks:
        return
    height, width = image.shape[:2]
    fit = _Fit(glyph_y=glyph / height, glyph_x=glyph / width)
    free = set(range(len(marks)))
    claimed: set[int] = set()

    def claim(indices: Sequence[int]) -> None:
        free.difference_update(indices)
        claimed.update(indices)

    for zone in document.zones:
        if zone.bbox is None or not zone.complete:
            continue
        if zone.kind is Kind.PAIRS:
            for pair, taken in zip(zone.pairs, _claim(zone.pairs, marks, free, fit)):
                pair.marks = [marks[i] for i in taken]
                claimed.update(taken)
        elif zone.kind is Kind.LIST or zone.kind is Kind.TABLE:
            rebuilt = (_options if zone.kind is Kind.LIST else _grid)(
                zone, marks, free, fit)
            if rebuilt is None:
                continue
            claim([marks.index(m) for pair in rebuilt for m in pair.marks])
            zone.kind, zone.pairs = Kind.PAIRS, rebuilt
            zone.blocks, zone.rows = [], []
        drawn = [mark.bbox for pair in zone.pairs for mark in pair.marks]
        if drawn:
            # A Zone's box is its content's, and a field's marks are its
            # content: the medical field's rules lie below the snapped box,
            # and the gap the renderer draws after the Zone is the page's
            # only if measured from them.
            zone.bbox = _union([zone.bbox, *drawn])
    rules = [marks[i].bbox for i in claimed if marks[i].kind == LINE]
    document.separators = [
        y for y in document.separators
        if not any(abs(y - (rule.top + rule.bottom) / 2) * height <= 3 for rule in rules)]
