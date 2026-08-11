"""The ink-aware half of the ruler, on pages built pixel by pixel.

`iou` answers "are these the same rectangles?" and cannot answer "is this the
same page?". Morphology scored 0.475 on `invoice_0001` by welding every row into
two full-height column strips — geometry that describes a different document and
loses to the model by a tenth of a point. A bake-off ranking on IoU alone would
have to be told, by a person, that the runner-up was nonsense.

So this file's centre is the last test: two column strips over a row-structured
page, asserting the number that catches them. Everything above it builds up the
pieces.

Synthetic pages rather than fixtures, following `test_layout_guards.py`: the
properties here are about ink and rectangles, and a page whose every pixel is
known is a better witness than a photograph whose ink nobody has counted.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from doc_to_html.geometry_score import expected_boxes, score_geometry
from doc_to_html.ir import BBox
from doc_to_html.preprocess import rectify

REPO = Path(__file__).resolve().parent.parent

HEIGHT, WIDTH = 600, 800

LEFT_COLUMN = (50, 350)
RIGHT_COLUMN = (450, 750)
"""Two columns with a 100px gutter, in pixels across."""

BLOCKS = ((50, 105), (165, 220), (280, 335))
"""Three blocks down the page, 60px of whitespace between them.

Each is four 10px lines separated by 5px of leading, which is the whole point:
`doubles` measures a gap against the box's *own* median line gap, so a box
holding one block sees only 5px gaps and a box holding three sees 60px gaps
against a 5px median. A block drawn as one solid rectangle would have no
internal leading to take a median of, and would prove nothing.
"""


def paper() -> np.ndarray:
    """Blank paper, at the level `equalise` leaves the Rectified Image at."""
    return np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)


def print_block(page: np.ndarray, block: tuple[int, int],
                column: tuple[int, int]) -> None:
    """Four lines of 10px, 5px apart — a paragraph, near enough for ink."""
    top, _ = block
    left, right = column
    for line in range(4):
        start = top + line * 15
        page[start:start + 10, left:right] = 30


def printed_page() -> np.ndarray:
    """Six paragraphs: three Bands of two columns, the invoice's own shape."""
    page = paper()
    for block in BLOCKS:
        for column in (LEFT_COLUMN, RIGHT_COLUMN):
            print_block(page, block, column)
    return page


def box(left: int, top: int, right: int, bottom: int) -> BBox:
    """A rectangle given in pixels, stored the way the IR stores it."""
    return BBox(left / WIDTH, top / HEIGHT, right / WIDTH, bottom / HEIGHT)


def perfect_boxes() -> list[BBox]:
    """One box per paragraph, tight against its ink."""
    return [
        box(column[0], block[0], column[1], block[1])
        for block in BLOCKS
        for column in (LEFT_COLUMN, RIGHT_COLUMN)
    ]


def column_strips() -> list[BBox]:
    """The morphology failure: two full-height strips, one per column."""
    return [
        box(column[0], BLOCKS[0][0], column[1], BLOCKS[-1][1])
        for column in (LEFT_COLUMN, RIGHT_COLUMN)
    ]


class TestGeometryThatIsRight:
    """The floor every other case is read against."""

    def test_perfect_boxes_account_for_every_mark_on_the_page(self) -> None:
        score = score_geometry(perfect_boxes(), perfect_boxes(), printed_page())

        assert score.zones == 6
        assert score.iou == pytest.approx(1.0)
        assert score.covered == pytest.approx(1.0)
        assert score.splits == 0
        assert score.doubles == 0

    def test_a_box_tight_against_one_paragraph_holds_one_mass(self) -> None:
        """Four lines 5px apart are one block of text, not four findings."""
        one = [box(LEFT_COLUMN[0], BLOCKS[0][0], LEFT_COLUMN[1], BLOCKS[0][1])]
        score = score_geometry(one, perfect_boxes(), printed_page())

        assert score.doubles == 0


class TestInkThatNoBoxAccountsFor:
    def test_ink_outside_every_box_is_not_covered(self) -> None:
        """Half the page's paragraphs, so half its ink."""
        left_only = [b for i, b in enumerate(perfect_boxes()) if i % 2 == 0]
        score = score_geometry(left_only, perfect_boxes(), printed_page())

        assert score.covered == pytest.approx(0.5, abs=0.01)

    def test_ink_claimed_by_two_boxes_is_not_covered_either(self) -> None:
        """`covered` counts ink inside *exactly* one box.

        A segmenter that blankets the page in overlapping rectangles accounts
        for everything and has told you nothing about where anything is, so
        double-claiming has to cost the same as missing.
        """
        boxes = perfect_boxes()
        doubled = boxes + [box(LEFT_COLUMN[0], BLOCKS[0][0],
                               LEFT_COLUMN[1], BLOCKS[0][1])]
        score = score_geometry(doubled, boxes, printed_page())

        assert score.covered < 1.0

    def test_a_page_with_nothing_printed_on_it_covers_nothing(self) -> None:
        score = score_geometry([box(0, 0, WIDTH, HEIGHT)], [], paper())

        assert score.covered == 0.0


class TestAnEdgeThroughInk:
    def test_a_box_ending_mid_line_splits_it(self) -> None:
        """Zone 0's failure: a 336x34px band through a ~62px logo."""
        block_top = BLOCKS[0][0]
        through = [box(LEFT_COLUMN[0], block_top, LEFT_COLUMN[1], block_top + 35)]
        score = score_geometry(through, perfect_boxes(), printed_page())

        assert score.splits >= 1

    def test_a_box_that_contains_what_it_touches_splits_nothing(self) -> None:
        score = score_geometry(perfect_boxes(), perfect_boxes(), printed_page())

        assert score.splits == 0

    def test_a_separator_is_not_ink_to_cut_through(self) -> None:
        """A rule is ink and is explicitly not content, per `MIN_GAP_THICKNESS`.

        Without this, every box drawn against a ruled table scores a split on the
        ruling it was correctly drawn around.
        """
        page = printed_page()
        page[140:143, 40:760] = 30

        score = score_geometry(perfect_boxes(), perfect_boxes(), page)

        assert score.splits == 0
        assert score.covered == pytest.approx(1.0)


class TestTwoMassesInOneBox:
    def test_a_box_spanning_two_paragraphs_holds_two_masses(self) -> None:
        """Zone 4's failure: neighbour ink above and below inside the crop."""
        both = [box(LEFT_COLUMN[0], BLOCKS[0][0], LEFT_COLUMN[1], BLOCKS[1][1])]
        score = score_geometry(both, perfect_boxes(), printed_page())

        assert score.doubles == 1

    def test_the_gap_is_judged_against_the_box_own_leading(self) -> None:
        """A dense table and an airy address block are judged by their own.

        The same 60px of whitespace is a paragraph break in 5px-leaded text and
        unremarkable in text leaded at 60px, so a page constant would report one
        of the two wrongly whatever value it took.
        """
        page = paper()
        for line in range(4):
            start = 50 + line * 115
            page[start:start + 55, LEFT_COLUMN[0]:LEFT_COLUMN[1]] = 30

        airy = [box(LEFT_COLUMN[0], 50, LEFT_COLUMN[1], 500)]
        score = score_geometry(airy, airy, page)

        assert score.doubles == 0

    def test_two_masses_and_nothing_else_are_still_two_masses(self) -> None:
        """The literal reading of the field, and the one it could not see.

        A box holding exactly two blocks has exactly one blank band, so that band
        is also its median and the ratio is 1.0 however wide the band is. Judged
        on its own contents this box is structurally invisible; judged against
        the leading of the page's other boxes it is obvious.
        """
        page = paper()
        print_block(page, BLOCKS[0], RIGHT_COLUMN)          # sets the leading
        page[60:100, LEFT_COLUMN[0]:LEFT_COLUMN[1]] = 30    # two solid masses,
        page[260:300, LEFT_COLUMN[0]:LEFT_COLUMN[1]] = 30   # one 160px band

        swallowed = box(LEFT_COLUMN[0], 60, LEFT_COLUMN[1], 300)
        neighbour = box(RIGHT_COLUMN[0], BLOCKS[0][0], RIGHT_COLUMN[1], BLOCKS[0][1])
        score = score_geometry([swallowed, neighbour], [neighbour], page)

        assert score.doubles == 1

    def test_columns_side_by_side_are_not_two_masses(self) -> None:
        """Measured down the page only.

        Ink separated horizontally is what a two-column Band *is*, so counting it
        would report a double on every correct multi-column layout in the corpus.
        """
        band = [box(LEFT_COLUMN[0], BLOCKS[0][0], RIGHT_COLUMN[1], BLOCKS[0][1])]
        score = score_geometry(band, perfect_boxes(), printed_page())

        assert score.doubles == 0


class TestTheMorphologyFailure:
    """Why one number was never enough — runs 30 and 31, as a test.

    Two full-height column strips over a row-structured page: a description of a
    different document that IoU alone ranks respectably.
    """

    def test_they_account_for_every_mark_and_cut_none_of_it(self) -> None:
        """The uncomfortable part: on two of the six fields they are perfect.

        Coverage alone would rank this above the model, which scores 0.56 on the
        real page. A strip genuinely does contain all its column's ink, exactly
        once, without clipping any of it.
        """
        score = score_geometry(column_strips(), perfect_boxes(), printed_page())

        assert score.covered == pytest.approx(1.0)
        assert score.splits == 0
        assert score.iou > 0.0

    def test_and_are_caught_anyway(self) -> None:
        score = score_geometry(column_strips(), perfect_boxes(), printed_page())

        assert score.doubles == 2, "each strip welds three paragraphs into one"
        assert score.zones == 2, "against the six the page actually has"


class TestTheMeasuredPage:
    """The invoice itself, with the model's answer replayed as literals.

    The coordinates below are `qwen3-vl:4b`'s six boxes for `invoice_0001`,
    unchanged across runs 32, 33 and 34 — the layout answer is deterministic at
    this temperature. They are written out rather than read from a run directory
    because `debug/` is not in the repository.
    """

    MEASURED = [
        BBox(0.05, 0.10, 0.38, 0.14),
        BBox(0.75, 0.10, 0.94, 0.23),
        BBox(0.05, 0.24, 0.38, 0.39),
        BBox(0.75, 0.24, 0.94, 0.39),
        BBox(0.05, 0.41, 0.94, 0.63),
        BBox(0.05, 0.64, 0.94, 0.92),
    ]

    def page(self) -> np.ndarray:
        return rectify(REPO / "example" / "invoice.png").image

    def reference(self) -> list[BBox]:
        return expected_boxes(REPO / "tests" / "fixtures"
                              / "invoice_0001.expected.json")

    def test_the_reference_is_the_floor_and_it_is_clean(self) -> None:
        """What the fixture's own rectangles score, before anything is read
        against them.

        These are no longer eyeballed: `tools/fixture_geometry.py` reads them off
        `example/invoice.html` as the browser lays it out. Four ink pixels of
        13,850 still fall outside — antialiasing beyond the glyph boxes the
        renderer reports, at corners a single pixel of slack does not reach — so
        this asks for essentially-all rather than exactly-all and says which.
        """
        reference = self.reference()
        score = score_geometry(reference, reference, self.page())

        assert score.covered > 0.999
        assert score.splits == 0
        assert score.doubles == 0

    def test_the_sliced_logo_is_a_number(self) -> None:
        """Zone 0 is a 336x34px band through a ~62px logo.

        Before this, the only way to know was to open the PNG — the box is legal,
        it is on the page, it encloses area, and it scores 0.32 IoU, which is
        low but says nothing about *why*.
        """
        logo_band = score_geometry([self.MEASURED[0]], self.reference(), self.page())

        assert logo_band.splits > 0

    def test_zone_4_holds_one_block_and_whitespace_not_two_blocks(self) -> None:
        """Spec 0004 says this crop carries "stray ink from the blocks above and
        below it". Measured, it does not.

        Its ink is two runs at rows 284-298 and 319-330 — the Payment Method
        block's own two lines. Rows 231-283 and 331-354 are blank. The nearest
        neighbour ink stops 8px above the box and resumes 13px below it. The
        overshoot is into margin, not into content, so the crowding argument does
        not apply to this Zone and its wrong Kind needs another explanation.
        """
        zone_4 = score_geometry([self.MEASURED[4]], self.reference(), self.page())

        assert zone_4.doubles == 0


class TestWhatTheRulerDoesNotDecide:
    def test_band_validity_is_carried_not_computed(self) -> None:
        """`valid` is a property of the layout *answer* — Bands and columns —
        and this scores rectangles, which no longer carry either. The caller
        that parsed the answer knows, so it says.
        """
        boxes = perfect_boxes()
        page = printed_page()

        assert score_geometry(boxes, boxes, page).valid is None
        assert score_geometry(boxes, boxes, page, valid=False).valid is False
