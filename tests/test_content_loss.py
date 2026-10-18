"""The three ways a document lost content whole — spec 0007 Phase A-1.

Each of the three was established by looking at a render beside its source, and
each has an exact cause rather than a suspicion. This pins the cause, not the
symptom, because the symptom is a number from a run and a run is not evidence
here.

| cause | document | what it was |
|---|---|---|
| a table read then discarded | `statement_0006` | one row disagreed with the header on cell count and the Zone was abandoned — 36 rows the model had read correctly |
| ink outside every box, dropped | `nonlatin_0014` | the document's own title, 3.7% of the page's ink, in no Zone at all |
| the whole page as one Zone | `darkdeck_0009` | light ink on dark ground, read as one mass of ink, no finding at all |

The first is pinned in `test_table_extraction.py`, where the mapper's tests
already live. The other two are here, with the honesty rule's own detector.

**One correction to the scoping, measured here on 2026-09-19 and not inherited.**
Cause 2 was scoped naming `receipt_0010` as its worst case, on 77 of 103 tokens
lost. On the shipped configuration the detector *does* cover that page — three
Zones spanning it, the middle one holding 50% of its ink — and the only ink
outside them is a dotted rule 1px tall. So the receipt's loss is not content
nobody covered; it is content covered and then read short, which is what
`shortfall` catches and what the honesty rule requires it to declare. The
documents where cause 2 is real are `nonlatin_0014` and `form_0007`, and on
`form_0007` the title's ink lies inside a neighbouring Zone's padded crop, so
it too is a reading fault wearing a coverage fault's clothes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from doc_to_html.corpus import SOURCES
from doc_to_html.ir import BBox, Block, Cell, Kind, Reading, Row, RowRole, Zone
from doc_to_html.orchestrator import (
    MAX_RECOVERED,
    read_lines,
    recovered_zones,
    shortfall,
)
from doc_to_html.preprocess import (
    count_regions,
    ground_is_dark,
    ground_level,
    hard_lines,
    printed_lines,
    rectify,
    uncovered_regions,
    with_dark_ink,
)

REPO = Path(__file__).resolve().parent.parent


def page(colour: int, marks: list[tuple[int, int, int, int]],
         ink: int) -> np.ndarray:
    """A flat page of one colour with rectangles of another drawn on it."""
    image = np.full((200, 200, 3), colour, dtype=np.uint8)
    for left, top, right, bottom in marks:
        image[top:bottom, left:right] = ink
    return image


class TestInkPolarity:
    """Cause 3. Every binarisation in `preprocess` reads dark as ink, which is a
    claim about the page rather than about printing."""

    def test_a_dark_page_is_recognised_as_one(self) -> None:
        dark = page(20, [(20, 20, 180, 40), (20, 60, 180, 80)], 230)
        assert ground_level(dark) < 128
        assert ground_is_dark(dark)

    def test_a_light_page_is_left_alone(self) -> None:
        light = page(245, [(20, 20, 180, 40)], 10)
        assert not ground_is_dark(light)
        assert np.array_equal(with_dark_ink(light), light)

    def test_a_dark_page_is_turned_over_so_its_ink_is_dark(self) -> None:
        dark = page(20, [(20, 20, 180, 40)], 230)
        turned = with_dark_ink(dark)
        assert turned[0, 0, 0] > 128, "the ground is now light"
        assert turned[30, 100, 0] < 128, "and the mark is now dark"

    def test_an_image_with_no_dominant_level_is_left_alone(self) -> None:
        """What the majority guard actually buys, stated as the test.

        It cannot tell a dark page from a crop that is mostly ink — nothing in a
        histogram can, which is why `rectify` settles polarity once for the
        whole page. What it *can* do is decline when no level dominates, so a
        noisy image is never inverted on the strength of a mode that is a coin
        toss between neighbouring buckets.
        """
        noisy = np.random.default_rng(0).integers(
            0, 256, size=(200, 200, 3), dtype=np.uint8
        )
        assert not ground_is_dark(noisy)

    def test_the_dark_deck_stops_reading_as_one_region(self) -> None:
        """The measurement this change was made on, re-taken here.

        `darkdeck_0009` has ten regions and used to measure **one**, because
        96.2% of it is below mid-grey and every one of those pixels read as ink.
        A page that measures one region gives grouping nothing to work with,
        which is how the document converted as a single Zone.
        """
        rectified = rectify(SOURCES["darkdeck_0009"].png_path(REPO))

        assert rectified.inverted, "the page was turned over"
        assert count_regions(rectified.image) > 1

    def test_a_light_document_is_not_turned_over(self) -> None:
        """The control. A change to the rectifier that fired on ordinary pages
        would change every document in the corpus at once."""
        rectified = rectify(SOURCES["invoice_0001"].png_path(REPO))
        assert not rectified.inverted


class TestRecoveringInkNoBoxCovers:
    """Cause 2. `uncovered_ink` could always see this; nothing read it."""

    def zones(self, *boxes: tuple[float, float, float, float]) -> list[Zone]:
        return [Zone(kind=Kind.PROSE, bbox=BBox(*box)) for box in boxes]

    def test_a_block_no_box_covers_becomes_a_zone(self) -> None:
        image = page(245, [(10, 10, 190, 40), (10, 120, 190, 180)], 10)
        detected = self.zones((0.05, 0.05, 0.95, 0.2))

        recovered = recovered_zones(image, detected)

        assert len(recovered) == 2
        found = recovered[1].bbox
        assert found is not None and found.top > 0.4, "the lower block"

    def test_a_page_the_detector_covered_gains_nothing(self) -> None:
        """The normal answer, and the one all five original documents give:
        `covered` was 1.00 on every one of them."""
        image = page(245, [(10, 10, 190, 40)], 10)
        detected = self.zones((0.02, 0.02, 0.98, 0.25))

        assert recovered_zones(image, detected) == detected

    def test_a_recovered_box_that_would_break_a_band_is_dropped(self) -> None:
        """A Zone recovered at the cost of the page's whole Band structure is
        not a repair. The refusal is what keeps this from trading one silent
        loss for a louder one."""
        image = page(245, [(10, 10, 190, 40), (10, 120, 190, 180)], 10)
        # A detected box enclosing the whole page horizontally *and* the
        # uncovered ink vertically: anything recovered inside it overlaps it.
        detected = self.zones((0.0, 0.0, 1.0, 0.3))
        recovered = recovered_zones(image, detected)

        # Either it was placed legally or it was refused — never both, and never
        # an invalid Band.
        from doc_to_html.wire import validate_bands

        validate_bands(recovered)

    def test_a_sliver_of_ink_is_not_a_region(self) -> None:
        """A box two pixels tall is the overflow of glyphs whose bodies sit in a
        neighbouring Zone's padded crop, not a block nobody read. Promoting it
        would crop two pixels of paper and ask a vision model what it says —
        which is the question `empty_zone` exists to refuse, arriving by a new
        route. Measured on `form_0007`, whose only uncovered ink is 2px tall.
        """
        image = page(245, [(10, 10, 190, 40), (10, 120, 190, 122)], 10)
        detected = self.zones((0.05, 0.03, 0.95, 0.22))

        assert recovered_zones(image, detected) == detected

    def test_no_page_may_gain_more_than_the_ceiling(self) -> None:
        marks = [(10, 20 * i + 5, 190, 20 * i + 15) for i in range(10)]
        image = page(245, marks, 10)
        detected = self.zones((0.0, 0.0, 0.05, 0.05))

        recovered = recovered_zones(image, detected)

        assert len(recovered) - len(detected) <= MAX_RECOVERED

    def test_a_zone_with_no_geometry_stops_the_step_rather_than_guessing(
        self,
    ) -> None:
        """With a box missing there is nothing to subtract, so nothing here can
        honestly be called uncovered."""
        image = page(245, [(10, 120, 190, 180)], 10)
        detected = [Zone(kind=Kind.PROSE, bbox=None)]

        assert recovered_zones(image, detected) == detected


def sheet(marks: list[tuple[int, int, int, int]], ink: int,
          size: int = 800) -> np.ndarray:
    """`page` at a corpus page's size, where a panel is wider than a stroke.

    `_without_panels` is sized for a page 800px on its long edge, and at
    `page`'s 200px a solid 2px square is a panel, so a stroke would be one."""
    image = np.full((size, size, 3), 245, dtype=np.uint8)
    for left, top, right, bottom in marks:
        image[top:bottom, left:right] = ink
    return image


def type_at(left: int, top: int, right: int, lines: int = 3
            ) -> list[tuple[int, int, int, int]]:
    """Strokes 2px wide and 12px tall, 5px apart, a few lines of them: ink
    that reads as type to the eye and to `_without_panels` alike."""
    return [(x, top + 20 * line, x + 2, top + 20 * line + 12)
            for line in range(lines) for x in range(left, right, 5)]


class TestInkThatIsNotContent:
    """N2, 2026-09-30. "Content nothing read" fired on ink that is not type:
    `cv_0013`'s dark sidebar, which `equalise` blows out into halos round every
    item, 26.1% of the page's ink between the Zone boxes; and `receipt_0010`'s
    paper edge, a 2px frame the warp keeps, 23.0%. The Gap audit reads the ink
    with both taken out; recovering Zones does not."""

    FRAME = [(0, 0, 800, 2), (0, 798, 800, 800), (0, 0, 2, 800),
             (798, 0, 800, 800)]
    PANEL = [(0, 0, 280, 800)]

    def test_the_pages_own_edge_is_not_content(self) -> None:
        image = sheet(self.FRAME + type_at(100, 100, 500), 180)
        boxes = [BBox(0.1, 0.1, 0.65, 0.2)]

        assert uncovered_regions(image, boxes), "read as it always was"
        assert uncovered_regions(image, boxes, type_only=True) == []

    def test_type_that_touches_the_edge_is_not_the_edge(self) -> None:
        """A page's edge is ink along most of its length; a line of type
        cropped tight to the top of the page is not."""
        image = sheet(type_at(100, 0, 300, lines=1), 10)

        assert uncovered_regions(image, [], type_only=True)

    def test_a_panels_fill_between_its_items_is_not_content(self) -> None:
        image = sheet(self.PANEL, 40)
        boxes = [BBox(0.0, 0.1, 0.35, 0.2), BBox(0.0, 0.4, 0.35, 0.5)]

        assert uncovered_regions(image, boxes), "read as it always was"
        assert uncovered_regions(image, boxes, type_only=True) == []

    def test_type_beside_a_panel_is_still_found(self) -> None:
        image = sheet(self.PANEL + type_at(450, 400, 700), 40)
        boxes = [BBox(0.0, 0.0, 0.35, 1.0)]

        (box, share), = uncovered_regions(image, boxes, type_only=True)

        assert box.left * 800 == pytest.approx(450, abs=2)
        assert share > 0.0


class TestHowMuchAFindingSays:
    """A finding about missing content has to say how much, and the share has
    to be of the page rather than of the finding."""

    def test_the_share_is_of_the_pages_ink_not_of_what_is_uncovered(
        self,
    ) -> None:
        """Measured on `form_0007`, and it is the whole reason this is a test.

        Dividing by the uncovered ink made every region a large share of a small
        thing: a 2px sliver came back as **1.000**, and a finding reading "100%
        of this page's printed ink is in here" over a sliver is a lie in the one
        direction Phase A-1 exists to prevent.
        """
        image = page(245, [(10, 10, 190, 100), (10, 150, 190, 156)], 10)
        covered = [BBox(0.02, 0.02, 0.98, 0.55)]

        regions = uncovered_regions(image, covered)

        assert regions, "the lower mark is uncovered"
        _, share = regions[0]
        assert 0.0 < share < 0.2, share

    def test_a_region_is_bounded_to_its_ink_and_not_to_the_dilation(
        self,
    ) -> None:
        """The grouping kernel spreads ink by 2% across and 4% down before
        components are taken. A box drawn round that spread overlaps whatever
        sits within the margin, which is how the one region worth recovering on
        `form_0007` and `nonlatin_0014` became the one region refused."""
        image = page(245, [(60, 150, 140, 158)], 10)

        (box, _), = uncovered_regions(image, [])

        assert box.top * 200 == pytest.approx(150, abs=2)
        assert box.bottom * 200 == pytest.approx(158, abs=2)
        assert box.left * 200 == pytest.approx(60, abs=2)


class TestAZoneReadShort:
    """The honesty rule's last mile: a Zone read, marked complete, and holding a
    fraction of its own crop. Every other check in the system passes it."""

    def table(self, rows: int) -> Zone:
        zone = Zone(kind=Kind.TABLE, bbox=BBox(0.0, 0.0, 1.0, 1.0),
                    complete=True)
        zone.rows = [
            Row(role=RowRole.DATA,
                cells=[Cell(readings=[Reading(engine="t", text=f"row {i}")])])
            for i in range(rows)
        ]
        return zone

    def lined_page(self, lines: int) -> np.ndarray:
        marks = [(10, 14 * i + 4, 190, 14 * i + 12) for i in range(lines)]
        return page(245, marks, 10)

    def test_a_table_that_came_back_with_two_of_its_rows_is_reported(self) -> None:
        """`statement_0006` in miniature — 36 printed rows, 2 returned."""
        image = self.lined_page(12)

        found = shortfall(image, self.table(2), index=0)

        assert found is not None
        assert found.read_lines == 2
        assert found.printed_lines >= 10
        assert found.ink_share > 0.0, "and it says how much"

    def test_a_table_that_came_back_whole_is_not_reported(self) -> None:
        image = self.lined_page(12)

        assert shortfall(image, self.table(12), index=0) is None

    def test_a_figure_is_exempt_because_its_artwork_is_not_read(self) -> None:
        """A logo's wordmark is part of the artwork and is deliberately not
        read. A finding that fires on correct behaviour is how the whole list
        stops being read."""
        image = self.lined_page(12)
        logo = Zone(kind=Kind.FIGURE, bbox=BBox(0.0, 0.0, 1.0, 1.0),
                    complete=True, graphic_kind="logo")

        assert shortfall(image, logo, index=0) is None

    def test_an_incomplete_zone_is_exempt_because_a_failure_already_names_it(
        self,
    ) -> None:
        image = self.lined_page(12)
        zone = self.table(2)
        zone.complete = False

        assert shortfall(image, zone, index=0) is None

    def test_one_line_short_stays_invisible_on_purpose(self) -> None:
        """Printed lines and rows genuinely disagree by one in both directions —
        a wrapped cell is two printed lines in one row — so a finding there
        would fire on correct readings, and a list of findings that includes
        correct readings is a list nobody finishes. Tables and pairs only: a
        prose or list Zone's lines are counted as its Extractor counts them."""
        image = self.lined_page(2)

        assert shortfall(image, self.table(1), index=0) is None

    def text(self, kind: Kind, lines: int) -> Zone:
        """A prose or list Zone read as `lines` lines, with no Title."""
        zone = Zone(kind=kind, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True)
        zone.blocks.append(Block(
            kind="paragraph" if kind is Kind.PROSE else "item",
            lines=[Cell(readings=[Reading(engine="t", text=f"line {i}")])
                   for i in range(lines)]))
        return zone

    def test_a_paragraph_read_whole_is_not_reported(self) -> None:
        """`invoice_0002` Zone 7 and `newsletter_0008` Zone 15 in miniature:
        four printed lines, three running to the right-hand edge, returned as
        one line — which is what `PROSE_PROMPT` asks for, and every word was
        there. Counting printed lines, both were reported read short."""
        image = page(245, [(10, 4, 190, 12), (10, 18, 190, 26),
                           (10, 32, 190, 40), (10, 46, 110, 54)], 10)

        assert printed_lines(image) == 4
        assert hard_lines(image) == 1
        assert shortfall(image, self.text(Kind.PROSE, 1), index=0) is None

    def test_a_heading_lost_above_a_wrapped_entry_is_reported(self) -> None:
        """`darkdeck_0009` Zones 4 and 10: a heading, then one bullet wrapped
        over two lines, returned as the bullet alone. One line short, and the
        line is the heading — so a prose or list Zone reports one line short."""
        image = page(245, [(10, 4, 70, 12), (10, 18, 190, 26),
                           (22, 32, 150, 40)], 10)

        found = shortfall(image, self.text(Kind.LIST, 1), index=0)

        assert found is not None
        assert (found.printed_lines, found.read_lines) == (2, 1)

    def test_a_line_that_stops_short_is_broken_on_purpose(self) -> None:
        """An address: no line reaches the edge the last one sets, so each is
        its own line, as `PROSE_PROMPT` says a three-line address stays."""
        image = page(245, [(10, 4, 120, 12), (10, 18, 100, 26),
                           (10, 32, 150, 40)], 10)

        assert hard_lines(image) == 3
        assert shortfall(image, self.text(Kind.PROSE, 1), index=0) is not None
        assert shortfall(image, self.text(Kind.PROSE, 3), index=0) is None

    @pytest.mark.parametrize("kind,build,expected", [
        (Kind.TABLE, lambda z: z.rows.append(Row(role=RowRole.DATA)), 1),
        (Kind.PROSE,
         lambda z: z.blocks.append(Block(kind="paragraph",
                                         lines=[Cell(), Cell(), Cell()])), 3),
    ])
    def test_lines_are_counted_per_kind(self, kind: Kind, build: object,
                                        expected: int) -> None:
        zone = Zone(kind=kind)
        build(zone)  # type: ignore[operator]
        assert read_lines(zone) == expected

    def test_a_title_counts_as_the_printed_line_it_is(self) -> None:
        """`printed_lines` sees the caption, so a comparison that did not would
        report every captioned Zone as one line short."""
        zone = Zone(kind=Kind.PROSE, title="Summary")
        zone.blocks.append(Block(kind="paragraph", lines=[Cell()]))
        assert read_lines(zone) == 2
