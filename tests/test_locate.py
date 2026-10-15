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
                            Source, Unclaimed, Zone, cell)
from doc_to_html.locate import (Word, _between, _from_grid, _from_pairs, fold, leaders,
                                place, unclaimed)
from doc_to_html.preprocess import PAD_X
from doc_to_html.render import render
from doc_to_html.report import flagged

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

    def test_touching_lines_one_cell_counts_as_one_line(self) -> None:
        # Spec 0013 step 3c, `pricing_0017`'s `£12 / user / month`: its
        # figure, set three times its unit's size, is parted at the valleys
        # of its own ink into three lines with no blank row between them.
        lines = [(0, 12), (13, 19), (20, 30), (40, 48)]
        placed: list[BBox | None] = [None, BBox(0.1, 0.40, 0.9, 0.48)]
        assert _between(lines, placed, 0, 100) == [(0, (0, 30))]


class TestCutCopies:
    """Spec 0013 step 3d — `pricing_0017`'s toggle read a third item, `Sav`,
    located on the first letters of `Save 20% with annual billing`, which
    the Zone beside it prints whole."""

    def toggle(self, last: str = "Sav") -> Document:
        items = [cell("Monthly"), cell("Annual"), cell(last)]
        for item, left in zip(items, (136, 172, 200)):
            item.bbox = at(left, 74, left + 20, 80)
        toggle = Zone(kind=Kind.LIST, bbox=at(136, 70, 195, 87), complete=True,
                      blocks=[Block(kind="item", lines=[item]) for item in items])
        save = cell("Save 20% with annual billing")
        save.bbox = at(200, 74, 263, 82)
        beside = Zone(kind=Kind.PROSE, bbox=at(200, 74, 263, 82), complete=True,
                      blocks=[Block(kind="paragraph", lines=[save])])
        return Document(source=Source(path="x.png", sha256="0", width=SIDE,
                                      height=SIDE), zones=[toggle, beside])

    def test_a_cut_copy_of_the_line_it_lies_on_goes(self) -> None:
        document = self.toggle()
        assert locate.without_cut_copies(document) == [(0, "Sav")]
        assert [b.lines[0].text for b in document.zones[0].blocks] == ["Monthly", "Annual"]

    def test_a_cell_that_does_not_start_the_line_stays(self) -> None:
        document = self.toggle("Yearly")
        assert locate.without_cut_copies(document) == []
        assert len(document.zones[0].blocks) == 3


def sure(text: str, left: int, top: int, line: int, confidence: float = 95.0) -> Word:
    found = word(text, left, top, line)
    return Word(found.text, found.box, found.line, confidence)


class TestUnclaimedLines:
    """Spec 0012, G9 — a printed line no Cell claims is reported."""

    def timetable(self) -> Zone:
        zone = table((RowRole.HEADER, ["Time", "Monday", "Tuesday"]),
                     (RowRole.DATA, ["09:00", "Mathematics", "English"]))
        for index, (left, right) in enumerate([(0, 40), (60, 160), (200, 260)]):
            zone.rows[1].cells[index].bbox = at(left, 20, right, 30)
        return zone

    def test_a_row_nobody_read_is_a_line_no_cell_claims(self) -> None:
        zone = self.timetable()
        found = [sure("09:00", 0, 20, 1), sure("Mathematics", 60, 20, 1),
                 sure("English", 200, 20, 1),
                 sure("10:00", 0, 60, 2), sure("Science", 60, 60, 2),
                 sure("English", 200, 60, 2)]
        boxes = [c.bbox for row in zone.rows for c in row.cells if c.bbox]
        lines = unclaimed(zone, found, boxes)
        assert [(round(box.top * SIDE), count) for box, count, _ in lines] == [(60, 3)]

    def test_a_word_tesseract_is_unsure_of_does_not_count(self) -> None:
        zone = self.timetable()
        found = [sure("Studio", 0, 60, 2, 20.0), sure("Varga", 60, 60, 2, 30.0)]
        assert unclaimed(zone, found, []) == []

    def test_one_word_alone_is_a_line(self) -> None:
        """Spec 0015, step 1: `Tags:`, `Lunch`, a note's last word."""
        lines = unclaimed(self.timetable(), [sure("Lunch", 60, 60, 2)], [])
        assert [count for _, count, _ in lines] == [1]

    def test_a_cell_claims_a_line_by_whole_words_only(self) -> None:
        """By letters, `osl` is inside `oslogardermoen`."""
        zone = prose("OSLO GARDERMOEN")
        assert len(unclaimed(zone, [sure("OSL", 0, 60, 2)], [])) == 1
        assert unclaimed(zone, [sure("Gardermoen", 0, 60, 2)], []) == []

    def test_a_cell_claims_a_line_by_half_its_letters_not_half_its_words(self) -> None:
        """`ticket_0020`'s gate note, `gate` and `before` left unclaimed:
        the Cell `GATE` spells one word of two, four letters of ten."""
        zone = prose("GATE", "C14")
        found = [sure("Gate", 0, 60, 2), sure("before", 120, 60, 2)]
        assert [count for _, count, _ in unclaimed(zone, found, [])] == [2]

    def test_one_long_word_does_not_claim_a_line_of_three(self) -> None:
        """`timetable_0019`'s legend: `Mathematics` is eleven letters of
        twenty, and one word of three."""
        zone = table((RowRole.DATA, ["Mathematics", "Science"]))
        found = [sure("Mathematics", 0, 60, 2), sure("Science", 100, 60, 2),
                 sure("PE", 170, 60, 2)]
        assert len(unclaimed(zone, found, [])) == 1

    def test_a_cell_placed_on_the_wrong_ink_still_claims_its_line(self) -> None:
        zone = prose("Gate closes 20 minutes before departure")
        found = [sure("Gate", 0, 60, 2), sure("close", 40, 60, 2),
                 sure("minutes", 100, 60, 2)]
        assert unclaimed(zone, found, []) == []

    def test_a_title_with_a_word_left_out_still_claims_its_line(self) -> None:
        zone = table((RowRole.HEADER, ["Περιγραφή", "Ώρες"]))
        zone.title = "Ανάλυση παρεχόμενων υπηρεσιών"
        found = [sure("Ανάλυση", 0, 10, 1), sure("υπηρεσιών", 120, 10, 1)]
        assert unclaimed(zone, found, []) == []

    def test_a_word_twice_is_one_word(self) -> None:
        zone = table((RowRole.DATA, ["English"]))
        found = [sure("12:20", 0, 60, 2), sure("Art", 50, 60, 2),
                 sure("English", 100, 60, 2), sure("PE", 180, 60, 2),
                 sure("English", 220, 60, 2)]
        assert [count for _, count, _ in unclaimed(zone, found, [])] == [5]

    def test_it_is_read_from_its_box_padded_as_a_crop_is(self) -> None:
        zone = self.timetable()
        [(box, _, reach)] = unclaimed(zone, [sure("Lunch", 60, 60, 2)], [])
        assert reach == BBox(box.left - PAD_X, box.top,
                             box.right + PAD_X, box.bottom)

    def test_its_crop_stops_halfway_to_a_claimed_word_of_its_line(self) -> None:
        """Padded whole, `13:20 Lunch` brings `13:20` into the crop and the
        reading repeats it."""
        zone = self.timetable()
        found = [sure("13:20", 30, 60, 2), sure("Lunch", 80, 60, 2),
                 sure("Hall", 130, 60, 2)]
        claimed = [at(30, 60, 70, 70), at(130, 60, 162, 70)]
        [(box, count, reach)] = unclaimed(zone, found, claimed)
        assert count == 1
        assert reach.left == pytest.approx((70 / SIDE + box.left) / 2)
        assert reach.right == pytest.approx((130 / SIDE + box.right) / 2)
        assert (reach.top, reach.bottom) == (box.top, box.bottom)

    def test_they_are_reported_with_their_share_and_survive_the_json(self) -> None:
        document = Document(source=Source(path="x", sha256="0" * 64, width=100,
                                          height=100),
                            zones=[self.timetable()],
                            unclaimed=[Unclaimed(zone_index=0, bbox=at(0, 160, 300, 172),
                                                 words=14, ink_share=0.023,
                                                 reach=at(0, 160, 310, 172)),
                                       Unclaimed(zone_index=0, bbox=at(0, 180, 300, 192),
                                                 words=6, ink_share=0.009)])
        back = Document.from_json(document.to_json())
        assert back.unclaimed == document.unclaimed
        html = flagged(back)
        assert ("Zone 0 (<code>table</code>) has 2 printed lines no Cell claims, "
                "20 words between 40% and 48% down the page, 3% of the page") in html


class TestAnExtraLineTakesTheLineItClaims:
    """Spec 0015, 2d: a line read again goes back on the printed line it was
    read from, by `unclaimed`'s own test, where its words do not match run
    for run — the ticket's gate note, read by tesseract as `gate user
    minutes before`."""

    def stub(self) -> Zone:
        zone = Zone(kind=Kind.PAIRS, bbox=at(0, 0, SIDE, SIDE), complete=True,
                    pairs=[Pair(cell("GATE", bbox=at(0, 20, 32, 30)),
                                cell("C14", bbox=at(0, 40, 24, 50)))],
                    extra=[Block(kind="paragraph",
                                 lines=[cell("Gate closes 20 minutes before")])])
        return zone

    def test_it_is_placed_on_the_line_it_claims(self) -> None:
        zone = self.stub()
        found = [sure("Gate", 0, 200, 9), sure("user", 40, 200, 9, 45.0),
                 sure("minutes", 80, 200, 9, 40.0), sure("before", 150, 200, 9)]
        boxes = locate._from_lines(zone, found, [at(0, 20, 32, 30), at(0, 40, 24, 50), None])
        assert boxes[2] == BBox(0.0, 0.5, 198 / SIDE, 210 / SIDE)

    def test_not_on_a_line_it_does_not_claim(self) -> None:
        zone = self.stub()
        found = [sure("Boarding", 0, 200, 9), sure("closes", 80, 200, 9)]
        boxes = locate._from_lines(zone, found, [at(0, 20, 32, 30), at(0, 40, 24, 50), None])
        assert boxes[2] is None


class TestTheDisplayRead:
    """Spec 0015, step 1: the Zone read again for type the first read erased
    as rules, kept only where the first read was sure of nothing."""

    def read(self, monkeypatch: pytest.MonkeyPatch, first: list[Word],
             second: list[Word]) -> list[Word]:
        asked: list[float] = []

        def fake(image: object, zone: Zone, *, glyph: float, languages: str = "eng",
                 inverted: bool = False) -> list[Word]:
            asked.append(glyph)
            return second

        monkeypatch.setattr(locate, "words", fake)
        out = locate.display_words(np.zeros((SIDE, SIDE), np.uint8), prose("x"), first)
        assert asked == [locate.DISPLAY_GLYPH]
        return out

    def test_a_word_where_the_first_read_was_sure_of_nothing_is_kept(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        first = [sure("ry", 0, 60, 2, 38.0), sure("it", 30, 60, 2, 12.0)]
        [kept] = self.read(monkeypatch, first, [sure("OSL", 0, 58, 1, 96.0)])
        assert kept.text == "osl" and kept.line == (2, 1001, 1)

    def test_a_word_the_first_read_was_sure_of_is_not_read_twice(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        first = [sure("Halvorsen", 0, 20, 1)]
        assert self.read(monkeypatch, first, [sure("Halvorsen", 2, 21, 1)]) == []


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
