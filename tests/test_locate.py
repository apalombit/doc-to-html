"""Where every entry sits on the page — spec 0011, step 2.

`place` and the fallbacks are tested on hand-made words, so most of this
runs with no tesseract; the tests that read a picture skip without it. The
corpus check is the overlays — `tools/locate_overlay.py` — not a number.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from doc_to_html import locate
from doc_to_html.ir import (BBox, Block, Document, Kind, Pair, Row, RowRole,
                            Source, Zone, cell)
from doc_to_html.locate import (Word, _between, _from_grid, _from_pairs, fold, leaders,
                                place)
from doc_to_html.render import render

SIDE = 400


def at(left: int, top: int, right: int, bottom: int) -> BBox:
    return BBox(left / SIDE, top / SIDE, right / SIDE, bottom / SIDE)


def word(text: str, left: int, top: int, line: int) -> Word:
    """A word tesseract found: 8px a letter, 10px tall, on line `line`."""
    return Word(fold(text), at(left, top, left + 8 * len(text), top + 10),
                (0, 1001, line))


def prose(*lines: str, **fields: object) -> Zone:
    return Zone(kind=Kind.PROSE, bbox=at(0, 0, SIDE, SIDE), complete=True,
                blocks=[Block(kind="paragraph", lines=[cell(t) for t in lines])],
                **fields)  # type: ignore[arg-type]


def table(*rows: tuple[RowRole, list[str]]) -> Zone:
    return Zone(kind=Kind.TABLE, bbox=at(0, 0, SIDE, SIDE), complete=True,
                rows=[Row(cells=[cell(t) for t in texts], role=role)
                      for role, texts in rows])


class TestFold:
    def test_letters_and_digits_only_case_and_accents_dropped(self) -> None:
        assert fold("At risk") == "atrisk"
        assert fold("1,180.00") == "118000"
        assert fold("Καθαρή αξία") == "καθαρηαξια"
        assert fold("— ·") == ""


class TestLeaders:
    def test_a_dotted_leader_is_found_and_a_full_stop_is_not(self) -> None:
        ink = np.zeros((40, 200), np.uint8)
        for x in range(20, 120, 6):
            ink[20:22, x:x + 2] = 255
        ink[20:22, 150:152] = 255  # one dot, alone
        found = leaders(ink, glyph=10.0)
        assert found[20:22, 20:118].any()
        assert not found[20:22, 150:152].any()

    def test_letters_are_not_leaders(self) -> None:
        ink = np.zeros((40, 200), np.uint8)
        for x in range(20, 120, 10):
            ink[10:20, x:x + 6] = 255
        assert not leaders(ink, glyph=10.0).any()


class TestPlace:
    def test_each_cell_takes_its_own_words(self) -> None:
        zone = prose("Potted brown shrimp", "Ox tongue")
        found = [word("Potted", 10, 10, 1), word("brown", 70, 10, 1),
                 word("shrimp", 120, 10, 1), word("Ox", 10, 40, 2),
                 word("tongue", 30, 40, 2)]
        boxes = place(zone, found)
        assert boxes[0] == at(10, 10, 168, 20)
        assert boxes[1] == at(10, 40, 78, 50)

    def test_a_cell_that_wraps_covers_every_line_it_prints(self) -> None:
        zone = prose("Figures are stated on an accruals basis last year")
        found = [word(w, 10 + 60 * i, 10, 1) for i, w in
                 enumerate("Figures are stated on an accruals basis".split())]
        found += [word("last", 10, 30, 2), word("year", 50, 30, 2)]
        [box] = place(zone, found)
        assert box is not None and box.top == at(0, 10, 0, 0).top
        assert box.bottom == at(0, 0, 0, 40).bottom

    def test_a_heading_line_above_is_not_taken_with_the_paragraph(self) -> None:
        # Tesseract reads the Zone's Title too; a run starting on it matches
        # the paragraph nearly as well, and must not win.
        zone = prose("This review covers the operations")
        found = [word("Purpose", 10, 10, 1), word("and", 80, 10, 1),
                 word("scope", 120, 10, 1)]
        found += [word(w, 10 + 70 * i, 40, 2) for i, w in
                  enumerate("This review covers the operations".split())]
        [box] = place(zone, found)
        assert box is not None and box.top == at(0, 40, 0, 0).top

    def test_digits_must_agree(self) -> None:
        zone = table((RowRole.DATA, ["1,180.00"]))
        assert place(zone, [word("1,238.50", 10, 10, 1)]) == [None]

    def test_repeated_text_goes_to_its_own_row(self) -> None:
        zone = table((RowRole.DATA, ["Ingest", "Healthy"]),
                     (RowRole.DATA, ["Query", "Healthy"]))
        found = [word("Ingest", 10, 10, 1), word("Healthy", 200, 10, 1),
                 word("Query", 10, 40, 2), word("Healthy", 200, 40, 2)]
        boxes = place(zone, found)
        assert boxes[1] is not None and boxes[1].top == at(0, 10, 0, 0).top
        assert boxes[3] is not None and boxes[3].top == at(0, 40, 0, 0).top

    def test_a_cell_whose_own_word_went_unread_takes_no_other_rows(self) -> None:
        # `nonlatin_0014`: `Καθαρή αξία` heads a column in a white header
        # tesseract does not read, and labels a total below, which it does.
        zone = table((RowRole.HEADER, ["Hours", "Net value"]),
                     (RowRole.DATA, ["Survey", "84"]),
                     (RowRole.SUMMARY, ["Net value", "10,030.50"]))
        found = [word("Survey", 10, 40, 2), word("84", 200, 40, 2),
                 word("Net", 10, 70, 3), word("value", 50, 70, 3),
                 word("10,030.50", 200, 70, 3)]
        boxes = place(zone, found)
        assert boxes[1] is None
        assert boxes[4] is not None and boxes[4].top == at(0, 70, 0, 0).top

    def test_a_word_is_claimed_once(self) -> None:
        zone = table((RowRole.DATA, ["BAC"]), (RowRole.DATA, ["BAC"]))
        boxes = place(zone, [word("BAC", 10, 40, 2)])
        assert sum(box is not None for box in boxes) == 1

    def test_nothing_alike_places_nothing(self) -> None:
        assert place(prose("Revit"), [word("Python", 10, 10, 1)]) == [None]


def inked(*rects: tuple[int, int, int, int]) -> np.ndarray:
    """A white page with glyph-sized blocks across each rectangle."""
    image = np.full((SIDE, SIDE, 3), 255, np.uint8)
    for left, top, right, bottom in rects:
        for x in range(left, right - 4, 8):
            image[top:bottom, x:x + 5] = 0
    return image


class TestFallbacks:
    def test_a_table_cell_comes_from_its_row_and_its_column(self) -> None:
        image = inked((20, 20, 100, 30), (200, 20, 260, 30),
                      (20, 60, 100, 70), (200, 60, 260, 70))
        zone = table((RowRole.DATA, ["Potted", "9.50"]),
                     (RowRole.DATA, ["Ox", "10.25"]))
        boxes = _from_grid(image, zone, [at(20, 20, 100, 30), at(200, 20, 260, 30),
                                         at(20, 60, 100, 70), None])
        assert boxes[3] is not None
        assert abs(boxes[3].top * SIDE - 60) <= 1 and abs(boxes[3].left * SIDE - 200) <= 1

    def test_a_value_beside_its_label_comes_from_the_labels_line(self) -> None:
        image = inked((20, 20, 80, 30), (150, 20, 300, 30),
                      (20, 60, 80, 70), (150, 60, 300, 70))
        zone = Zone(kind=Kind.PAIRS, bbox=at(0, 0, SIDE, SIDE), complete=True,
                    pairs=[Pair(cell("Bank"), cell("GR96 0110")),
                           Pair(cell("Tax"), cell("A Piraeus"))])
        boxes = _from_pairs(image, zone, [at(20, 20, 80, 30), None,
                                          at(20, 60, 80, 70), at(150, 60, 300, 70)])
        assert boxes[1] is not None
        assert abs(boxes[1].left * SIDE - 150) <= 1 and abs(boxes[1].top * SIDE - 20) <= 1

    def test_a_value_under_its_label_takes_nothing_from_the_line(self) -> None:
        # A form: the value sits in a box under the label, not beside it.
        image = inked((20, 20, 80, 30), (20, 50, 150, 60), (200, 20, 260, 30))
        zone = Zone(kind=Kind.PAIRS, bbox=at(0, 0, SIDE, SIDE), complete=True,
                    pairs=[Pair(cell("Name"), cell("Whitlock")),
                           Pair(cell("Postcode"), cell("CT9 4RD"))])
        placed = [at(20, 20, 80, 30), at(20, 50, 150, 60), at(200, 20, 260, 30), None]
        assert _from_pairs(image, zone, placed) == placed


def test_the_boxes_change_no_byte_of_the_page_outside_the_ir() -> None:
    def document(boxed: bool) -> Document:
        zone = prose("Potted brown shrimp")
        if boxed:
            zone.blocks[0].lines[0].bbox = at(10, 10, 168, 20)
        return Document(source=Source(path="x.png", sha256="0", width=SIDE,
                                      height=SIDE), zones=[zone])

    ir = re.compile(r'<script type="application/json" id="doc-ir">.*?</script>', re.S)
    plain, boxed = render(document(False)), render(document(True))
    assert plain != boxed
    assert ir.sub("", plain) == ir.sub("", boxed)


@pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")
class TestBetweenPlacedLines:
    """Spec 0012, G8 — a heading on two printed lines held as one Cell."""

    LINES = [(0, 10), (14, 24), (40, 48), (52, 58), (62, 68), (72, 78)]

    def test_unplaced_lines_between_two_placed_ones_take_the_lines_between(self) -> None:
        heading, email = BBox(0.1, 0.0, 0.9, 0.24), BBox(0.3, 0.72, 0.7, 0.78)
        placed: list[BBox | None] = [heading, None, None, None, email]
        assert _between(self.LINES, placed, 0, 100) == [
            (1, (40, 48)), (2, (52, 58)), (3, (62, 68))]

    def test_a_run_counting_otherwise_takes_nothing(self) -> None:
        heading, email = BBox(0.1, 0.0, 0.9, 0.24), BBox(0.3, 0.72, 0.7, 0.78)
        placed: list[BBox | None] = [heading, None, None, email]
        assert _between(self.LINES, placed, 0, 100) == []


class TestOnAPicture:
    @staticmethod
    def page() -> tuple[np.ndarray, Document]:
        import cv2
        image = np.full((300, 600, 3), 255, np.uint8)
        cv2.putText(image, "Potted brown shrimp", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(image, "Lamb cutlets", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
        zone = Zone(kind=Kind.PROSE, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True,
                    blocks=[Block(kind="paragraph",
                                  lines=[cell("Potted brown shrimp"),
                                         cell("Lamb cutlets"), cell("Revit")])])
        zone.blocks[0].lines[2].bbox = BBox(0.1, 0.1, 0.2, 0.2)  # stale
        return image, Document(source=Source(path="x.png", sha256="0",
                                             width=600, height=300), zones=[zone])

    def test_each_line_lands_on_its_own_ink_and_the_rest_is_cleared(self) -> None:
        image, document = self.page()
        placed, cells = locate.locate(image, document)
        first, second, absent = document.zones[0].blocks[0].lines
        assert (placed, cells) == (2, 3)
        assert first.bbox is not None and second.bbox is not None
        assert 30 / 300 < first.bbox.bottom < 70 / 300
        assert 110 / 300 < second.bbox.bottom < 150 / 300
        assert absent.bbox is None

    def test_the_same_picture_places_the_same_boxes(self) -> None:
        image, one = self.page()
        _, two = self.page()
        locate.locate(image, one)
        locate.locate(image, two)
        assert ([c.bbox for c in one.zones[0].blocks[0].lines]
                == [c.bbox for c in two.zones[0].blocks[0].lines])
