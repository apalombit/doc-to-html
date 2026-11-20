"""A tick box at the start of a line, put back from the pixels — spec 0024,
part two, direction 7 (`checkboxes`).

A synthetic page: lines drawn with `cv2.putText`, each with what the page
prints just left of it — an open box, a ticked one, a crossed one, one
with a two-pixel anti-aliased border, a solid square, a round bullet, or
nothing. The dev pages are the sheets.
"""

from __future__ import annotations

import cv2
import numpy as np

from doc_to_html import checkboxes
from doc_to_html.ir import (BBox, Block, Cell, Document, Kind, Reading, Row, Run, Source, Zone,
                            cell)

WIDTH, HEIGHT = 400, 60
TEXT_X, BASE = 40, 34


def line(before: str | None, text: str = "Single", *, runs: list[Run] | None = None
         ) -> tuple[np.ndarray, Document, Cell]:
    """One line of type at `TEXT_X`, and `before` drawn left of it: `open`,
    `tick`, `cross`, `thick` (a two-pixel border, anti-aliased inside),
    `solid`, `dot`, `letter` (a box with a letter's stem just left of it),
    `heavy` (a square drawn with a three-pixel stroke) or None."""
    grey = np.full((HEIGHT, WIDTH), 255, np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    (wide, tall), base = cv2.getTextSize(text, font, 0.5, 1)
    cv2.putText(grey, text, (TEXT_X, BASE), font, 0.5, 0, 1, cv2.LINE_AA)
    x, y, size = TEXT_X - 16, BASE - 10, 10
    if before in ("open", "tick", "cross", "solid"):
        cv2.rectangle(grey, (x, y), (x + size, y + size), 60, -1 if before == "solid" else 1)
    if before == "thick":
        cv2.rectangle(grey, (x, y), (x + size, y + size), 100, 1)
        cv2.rectangle(grey, (x + 1, y + 1), (x + size - 1, y + size - 1), 195, 1)
    if before == "tick":
        cv2.line(grey, (x + 2, y + 5), (x + 4, y + 8), 40, 1)
        cv2.line(grey, (x + 4, y + 8), (x + 8, y + 2), 40, 1)
    if before == "cross":
        cv2.line(grey, (x + 2, y + 2), (x + 8, y + 8), 40, 1)
        cv2.line(grey, (x + 8, y + 2), (x + 2, y + 8), 40, 1)
    if before == "dot":
        cv2.circle(grey, (x + 5, y + 5), 5, 60, 1)
    if before == "letter":
        # A letter just before the box: `GO` before `BLAZE`, `Saturday`
        # before `$45`.
        cv2.rectangle(grey, (x, y), (x + size, y + size), 60, 1)
        cv2.line(grey, (x - 3, y + 2), (x - 3, y + size), 60, 2)
    if before == "heavy":
        # A heavy display face's `O`: square, into its corners, a thick stroke.
        cv2.rectangle(grey, (x, y), (x + size, y + size), 30, 3)
    entry = cell(text)
    if runs is not None:
        entry.readings = [Reading(engine="glm-ocr", text=text, runs=runs)]
    entry.bbox = BBox((TEXT_X - 1) / WIDTH, (BASE - tall - 1) / HEIGHT,
                      (TEXT_X + wide + 1) / WIDTH, (BASE + base) / HEIGHT)
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True,
                blocks=[Block(kind="paragraph", lines=[entry])])
    document = Document(source=Source(path="x.png", sha256="0", width=WIDTH, height=HEIGHT),
                        zones=[zone])
    return grey, document, entry


def restored(before: str | None, text: str = "Single") -> str:
    grey, document, entry = line(before, text)
    checkboxes.restore(grey, document)
    return entry.text


class TestTheBoxAStartingLinePrints:
    def test_an_open_box_is_put_back_open(self) -> None:
        assert restored("open") == "☐ Single"

    def test_a_ticked_box_is_put_back_ticked(self) -> None:
        assert restored("tick") == "☑ Single"

    def test_a_crossed_box_is_put_back_crossed(self) -> None:
        """A cross is as symmetric left to right as top to bottom; a tick is neither."""
        assert restored("cross") == "☒ Single"

    def test_a_two_pixel_border_is_not_a_mark(self) -> None:
        """c0012's open `Petrol` box: its border anti-aliased two pixels
        deep, the inner pixel light grey. Read as ink, it was a cross."""
        assert restored("thick") == "☐ Single"


class TestWhatIsLeftAsRead:
    def test_a_line_with_nothing_before_it(self) -> None:
        assert restored(None) == "Single"

    def test_a_line_whose_box_the_reader_read(self) -> None:
        assert restored("open", "☐ Yes") == "☐ Yes"

    def test_a_solid_square_may_be_a_bullet(self) -> None:
        assert restored("solid") == "Single"

    def test_a_round_mark_is_not_a_box(self) -> None:
        assert restored("dot") == "Single"

    def test_a_box_with_ink_just_before_it_is_a_letter(self) -> None:
        assert restored("letter") == "Single"

    def test_a_square_of_heavy_strokes_is_a_letter(self) -> None:
        assert restored("heavy") == "Single"

    def test_a_box_the_reader_typed(self) -> None:
        assert restored("open", "[ ] I consent") == "[ ] I consent"


class TestABoxTheReaderReadInItsOwnColumn:
    def test_the_cell_beside_it_takes_no_second_mark(self) -> None:
        """c0066's release column: the reader read the box into a cell of
        its own, and the line beside it took a second mark."""
        grey, document, entry = line("open")
        box = cell("☐")
        document.zones[0] = Zone(kind=Kind.TABLE, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True,
                                 rows=[Row(cells=[box, entry])])
        checkboxes.restore(grey, document)
        assert (box.text, entry.text) == ("☐", "Single")


class TestTheReadersStandIn:
    def test_a_dash_written_for_the_box_is_replaced(self) -> None:
        """c0044's `- Glycosidic` where the page prints `☐ Glycosidic`."""
        assert restored("open", "- Glycosidic") == "☐ Glycosidic"


class TestTheLineKeepsItsMarking:
    def test_the_runs_still_spell_the_text(self) -> None:
        grey, document, entry = line("open", "Bold rest",
                                     runs=[Run(text="Bold", kind="strong"), Run(text=" rest")])
        checkboxes.restore(grey, document)
        assert entry.text == "☐ Bold rest"
        assert [(run.text, run.kind) for run in entry.runs] == [
            ("☐ ", "text"), ("Bold", "strong"), (" rest", "text")]
