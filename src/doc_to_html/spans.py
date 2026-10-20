"""Cells that span — spec 0019, B1.

**What the IR could not say.** A table was rows of cells, one cell to a slot.
`timetable_0019` draws a ruled grid in which a lesson two periods long is one
drawn cell over two slots, `Registration and tutor time` one cell across the
five days, and `Lunch` one across the whole grid; and each lesson prints its
room under its subject. The model's table answer gives each printed line as a
row — the subject, then the room — so a lesson running two slots is text in
the first slot and blanks in the next. Drawn one cell to a slot, the render
clipped Monday's `Mathematics`, set Tuesday's `Science` across two columns,
and drew `Lunch` under the grid.

**What it reads: the grid's own rules.** Where a table's vertical rules stand
at exactly as many places as its columns have edges, and it draws horizontal
rules too, the rules are its grid. A slot boundary the grid draws elsewhere
and not here is no boundary here:

- **(i)** a row whose key column is empty, its lines inside the drawn cells
  of the row above — no rule between them — is that row's second printed
  line, and each line joins the cell above it as `Cell.below`;
- **(iii)** a line read on its own (`Zone.extra`) that the page prints inside
  an empty drawn cell is that cell's text;
- **(ii)** an entry whose drawn cell covers the empty slots beside or below
  it — no rule between them — spans them, `Cell.span`; one that spans to its
  left moves to the first slot it covers.

A line's lane is where its box lies when the box lies in one lane, and its
column in the answer otherwise: `locate` gives the two `B04 · Ms Ilves` of one
row a single box from Wednesday to Friday.

**Only a ruled grid.** Over the twenty-one pages only the timetable draws
one: the only other table with vertical rules is `statement_0006`'s tiles,
three dividers and no horizontal rule. A table drawn without rules says
nothing about where a cell ends, so every other table is left as it is.

Run last of the steps that write the IR, after `looks.read`: each line keeps
the look measured on its own ink wherever it goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from statistics import median
from typing import Sequence

from .ir import Block, Cell, Document, Furniture, Kind, Row, RowRole, Zone

TOGETHER = 0.008
"""How near, as a share of the page's width, two vertical rules stand to be
one edge of the grid: the grid's line and the coloured bar a lesson draws
inside it, `timetable_0019`'s 0.109 and 0.110-0.115, are one edge. The
grid's edges stand 0.17 apart."""

ONE_LANE = 0.9
"""How much of a line's box must lie in one lane for the box to say which
lane it is in."""


@dataclass
class _Edge:
    """One vertical edge of the grid: the rules standing at it."""

    rules: list[Furniture] = field(default_factory=list)

    @property
    def left(self) -> float:
        return min(rule.bbox.left for rule in self.rules)

    @property
    def right(self) -> float:
        return max(rule.bbox.right for rule in self.rules)

    def drawn_at(self, y: float) -> bool:
        return any(rule.bbox.top <= y <= rule.bbox.bottom for rule in self.rules)


@dataclass
class _Grid:
    edges: list[_Edge]
    across: list[Furniture]
    """The horizontal rules."""

    def lane_of(self, cell: Cell, column: int) -> int:
        box = cell.bbox
        if box is None or box.right <= box.left:
            return column
        for lane in range(len(self.edges) - 1):
            left, right = self.edges[lane].right, self.edges[lane + 1].left
            inside = max(0.0, min(box.right, right) - max(box.left, left))
            if inside >= ONE_LANE * (box.right - box.left):
                return lane
        return column

    def middle(self, lane: int) -> float:
        return (self.edges[lane].right + self.edges[lane + 1].left) / 2

    def ruled_between(self, upper: float, lower: float, lane: int | None = None) -> bool:
        """Whether a horizontal rule stands between two heights — across
        `lane`, or anywhere when it is None."""
        return any(upper < (rule.bbox.top + rule.bbox.bottom) / 2 < lower
                   and (lane is None
                        or rule.bbox.left <= self.middle(lane) <= rule.bbox.right)
                   for rule in self.across)

    def ruled_beside(self, lane: int, y: float) -> bool:
        """Whether the edge on `lane`'s right is drawn at height `y`."""
        return self.edges[lane + 1].drawn_at(y)


def _grid(zone: Zone, index: int, furniture: Sequence[Furniture]) -> _Grid | None:
    """The table's ruled grid, or None where it draws none."""
    width = max((len(row.cells) for row in zone.rows), default=0)
    rules = [item for item in furniture if item.kind == "rule" and item.zone == index]
    down = sorted((rule for rule in rules if rule.vertical),
                  key=lambda rule: (rule.bbox.left + rule.bbox.right) / 2)
    across = [rule for rule in rules if not rule.vertical]
    edges: list[_Edge] = []
    for rule in down:
        centre = (rule.bbox.left + rule.bbox.right) / 2
        if edges and centre - (edges[-1].rules[-1].bbox.left
                               + edges[-1].rules[-1].bbox.right) / 2 <= TOGETHER:
            edges[-1].rules.append(rule)
        else:
            edges.append(_Edge([rule]))
    if width < 2 or not across or len(edges) != width + 1:
        return None
    return _Grid(edges, across)


def _height(row: Row) -> float | None:
    """The middle of a row's printed lines, from its Cells' boxes."""
    middles = [(cell.bbox.top + cell.bbox.bottom) / 2 for cell in row.cells
               if cell.bbox is not None and cell.text.strip()]
    return median(middles) if middles else None


def _top(cell: Cell) -> float | None:
    return None if cell.bbox is None else cell.bbox.top


def _joined(rows: list[Row], grid: _Grid) -> list[Row]:
    """(i): each second printed line joined to the cell above it."""
    out: list[Row] = []
    for row in rows:
        above = out[-1] if out else None
        if (above is None or row.role is RowRole.HEADER or above.role is RowRole.HEADER
                or not row.cells or row.cells[0].text.strip()
                or not above.cells or not above.cells[0].text.strip()):
            out.append(row)
            continue
        kept = list(row.cells)
        for column, cell in enumerate(row.cells):
            if column == 0 or not cell.text.strip():
                continue
            lane = grid.lane_of(cell, column)
            if lane >= len(above.cells) or not above.cells[lane].text.strip():
                continue
            target = above.cells[lane]
            upper = target.bbox.bottom if target.bbox is not None else _height(above)
            lower = _top(cell) if cell.bbox is not None else _height(row)
            if upper is None or lower is None or grid.ruled_between(upper, lower, lane):
                continue
            target.below.append(_off_its_chip(cell, target))
            kept[column] = Cell()
        if any(cell.text.strip() for cell in kept):
            out.append(Row(cells=kept, role=row.role, under=row.under, fill=row.fill,
                           leader=row.leader, gap=row.gap))
    return out


def _off_its_chip(line: Cell, above: Cell) -> Cell:
    """A second line whose measured chip holds the line above it too: the
    fill is the drawn cell's ground, not a chip round the line. Monday's
    `B04 · Ms Ilves` on `timetable_0019` measured the lesson's blue as its
    chip, and drawn as one it was padded out over `Mathematics`."""
    look, box = line.look, above.bbox
    if (look is not None and look.chip is not None and box is not None
            and look.chip.left <= box.left and look.chip.top <= box.top
            and box.right <= look.chip.right and box.bottom <= look.chip.bottom):
        line.look = replace(look, fill=None, chip=None, radius=None)
    return line


def _placed_extra(zone: Zone, grid: _Grid) -> None:
    """(iii): a line read on its own, printed in an empty drawn cell, is its text."""
    heights = sorted((rule.bbox.top + rule.bbox.bottom) / 2 for rule in grid.across)
    kept: list[Block] = []
    for block in zone.extra:
        lines = []
        for cell in block.lines:
            if not _into_a_slot(zone, grid, heights, cell):
                lines.append(cell)
        if lines:
            block.lines = lines
            kept.append(block)
    zone.extra = kept


def _into_a_slot(zone: Zone, grid: _Grid, heights: list[float], cell: Cell) -> bool:
    if cell.bbox is None or not cell.text.strip():
        return False
    middle = (cell.bbox.top + cell.bbox.bottom) / 2
    above = [y for y in heights if y < middle]
    below = [y for y in heights if y > middle]
    if not above or not below:
        return False
    upper, lower = max(above), min(below)
    if cell.bbox.top < upper or cell.bbox.bottom > lower:
        return False
    lane = grid.lane_of(cell, -1)
    if lane < 0:
        return False
    for row in zone.rows:
        at = _height(row)
        if (row.role is not RowRole.HEADER and at is not None and upper < at < lower
                and lane < len(row.cells) and not row.cells[lane].text.strip()):
            row.cells[lane] = cell
            return True
    return False


def _spanned(rows: list[Row], grid: _Grid) -> None:
    """(ii): each entry over the empty slots its drawn cell covers."""
    covered: set[tuple[int, int]] = set()
    heights = [_height(row) for row in rows]
    for position, row in enumerate(rows):
        y = heights[position]
        if row.role is RowRole.HEADER or y is None:
            continue
        for column, cell in enumerate(list(row.cells)):
            if not cell.text.strip() or (position, column) in covered:
                continue
            first = column
            while (first > 0 and not row.cells[first - 1].text.strip()
                   and (position, first - 1) not in covered
                   and not grid.ruled_beside(first - 1, y)):
                first -= 1
            last = column
            while (last + 1 < len(row.cells) and not row.cells[last + 1].text.strip()
                   and (position, last + 1) not in covered
                   and not grid.ruled_beside(last, y)):
                last += 1
            end = position
            while end + 1 < len(rows):
                lower, upper, at = rows[end + 1], heights[end], heights[end + 1]
                if (lower.role is RowRole.HEADER or at is None or upper is None
                        or not grid.ruled_between(upper, at)
                        or any(lane >= len(lower.cells) or lower.cells[lane].text.strip()
                               or grid.ruled_between(upper, at, lane)
                               for lane in range(first, last + 1))):
                    break
                end += 1
            if (end - position, last - first) == (0, 0):
                continue
            if first != column:
                row.cells[first], row.cells[column] = cell, row.cells[first]
            cell.span = (end - position + 1, last - first + 1)
            covered.update((at, lane) for at in range(position, end + 1)
                           for lane in range(first, last + 1))


def read(document: Document) -> None:
    """Join, place and span the cells of every table that draws a ruled grid."""
    for index, zone in enumerate(document.zones):
        if zone.kind is not Kind.TABLE or not zone.rows:
            continue
        grid = _grid(zone, index, document.furniture)
        if grid is None:
            continue
        zone.rows = _joined(zone.rows, grid)
        _placed_extra(zone, grid)
        _spanned(zone.rows, grid)
