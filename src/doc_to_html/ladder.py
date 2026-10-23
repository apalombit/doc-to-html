"""The third reading, where the two are near — spec 0019, D2.

D1 keeps the words tesseract read to place a Cell as its second reading.
Over `s13-result/`'s placed Cells the two differ on 80; on 14 of them
tesseract is right, and **confidence does not separate those** —
tesseract is at 90 or above on 9 of the 14 and on 13 of the model's 72.
**Distance does:** 13 of the 14 are 1–4 characters from the model's
reading, folded. The fourteenth, `nonlatin_0014`'s footer, names another
company 20 characters away, and no near-miss rule reaches it (D3).

So a Cell whose two readings are `NEAR` is read a third time, by the
model on the Cell's own crop — one call, as `_read_unclaimed` reads a
line — and what two of the three agree on, folded, stands:

- a majority makes the Cell `RESOLVED`, the majority's text first: the
  third reading where it sides with tesseract, the model's own where it
  sides with the model;
- no majority makes it `DISPUTED`, the model's text drawn and the others
  kept, which the render titles.

Measured on the spec's 59 Cells within 3: six of the twelve true misreads
repaired, none of the 41 the model had right changed, and five read anew
wrongly (`tempost`, `cheru`), where the model's reading stands.
"""

from __future__ import annotations

from .ir import Cell, CellState, Reading, Zone
from .locate import SECOND, fold, unraised

NEAR = 4
"""How many characters, folded, two readings of a Cell differ by at most to
be read a third time: 13 of the 14 true misreads, and 58 Cells in all over
`s13-result/` rederived at D1."""


def distance(one: str, other: str) -> int:
    """Characters inserted, deleted or changed to turn one into the other."""
    previous = list(range(len(other) + 1))
    for i, a in enumerate(one, 1):
        current = [i]
        for j, b in enumerate(other, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def second(cell: Cell) -> Reading | None:
    """The Cell's second reading, tesseract's, where D1 kept one."""
    return next((r for r in cell.readings[1:] if r.engine == SECOND), None)


def due(cell: Cell) -> bool:
    """Whether a Cell is read a third time: placed, settled by nothing yet,
    and its two readings apart by 1 to `NEAR` characters, folded."""
    other = second(cell)
    if cell.state is not CellState.AGREED or cell.bbox is None or other is None:
        return False
    # By its words: its raised marks are read apart (`locate.unraised`).
    apart = distance(fold(unraised(cell)), fold(other.text))
    return 0 < apart <= NEAR


def beside_caps(zone: Zone) -> set[int]:
    """The lines a drop cap is set into, by id: each holds the cap's ink in
    its box, so no reading of the box alone is a reading of the line —
    `newsletter_0008`'s `he stretch` is read `whe` by tesseract and `The`
    on its own crop, and disputed, it split `The` in the drawn page."""
    return {id(line) for block in zone.blocks
            for before, line in zip(block.lines, block.lines[1:]) if before.display == "cap"}


def settle(cell: Cell, third: Reading) -> bool:
    """The Cell settled by its third reading, in place. Returns whether its
    text changed. It sides with the model by the model's words as `due`
    compares them, its raised marks left out: `paper_0018`'s footnote
    `²Delta … Delft` read a third time without its `²` was disputed."""
    first, other = cell.readings[0], second(cell)
    assert other is not None
    rest = [r for r in cell.readings[1:] if r is not other]
    agreed = fold(third.text)
    if agreed in (fold(first.text), fold(unraised(cell))):
        cell.state = CellState.RESOLVED
        cell.readings = [first, other, *rest, third]
        return False
    if agreed == fold(other.text):
        cell.state = CellState.RESOLVED
        cell.readings = [third, first, other, *rest]
        return third.text != first.text
    cell.state = CellState.DISPUTED
    cell.readings = [first, other, *rest, third]
    return False
