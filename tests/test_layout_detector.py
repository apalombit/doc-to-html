"""The layout pass as a detector rather than a model.

`tools/detector_probe.py` measured *whether* a trained detector describes these
pages — `debug/runs/65-detector-bakeoff`, two candidates, five fixtures, nine
confidences. This pins the parts that measurement cannot: that the flag off
changes nothing, that a detector's boxes become Zones the rest of the pipeline
recognises, and that the one post-pass the bakeoff proved necessary does what it
says.

**No weights, no ONNX Runtime, no download.** Every test here runs against a
fake `Detector`, because a suite that needs a 171MB file is a suite that does
not run on a fresh clone. What the real models return is what the probe is for.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from doc_to_html.config import (
    DEFAULT_DETECTOR_CONFIDENCE,
    DEFAULT_LAYOUT_DETECTOR,
    Settings,
    load,
)
from doc_to_html.engines.base import LayoutEngine as LayoutEngineProtocol
from doc_to_html.engines.detector import (
    CONTAINED,
    CONTAINER_HEIGHT,
    HEADING_GAP,
    HEADING_GAP_MAX,
    HEADING_GAP_RATIO,
    Detection,
    DetectorUnavailable,
    LayoutEngine,
    attach_headings,
    attach_trailing_rows,
    prefer_container,
    from_name,
    outermost,
    split_containers,
    without_enclosed,
    without_overreaching_pictures,
)
from doc_to_html.ir import Kind, Role
from doc_to_html.orchestrator import default_engines
from doc_to_html.wire import validate_bands


def box(left: float, top: float, right: float, bottom: float,
        label: str = "text", score: float = 0.9) -> Detection:
    return Detection(left=left, top=top, right=right, bottom=bottom,
                     label=label, score=score)


class Fake:
    """A detector returning a fixed answer, so the adapter can be tested alone."""

    name = "fake"
    license = "n/a"
    confidence = 0.5

    def __init__(self, found: list[Detection]) -> None:
        self.found = found
        self.images: list[np.ndarray] = []

    def detect(self, image: np.ndarray) -> list[Detection]:
        self.images.append(image)
        return self.found


def page(marks: list[tuple[int, int, int, int]]) -> np.ndarray:
    """A white page with ink where it is asked for, so snapping has a target."""
    image = np.full((400, 600, 3), 250, dtype=np.uint8)
    for left, top, right, bottom in marks:
        image[top:bottom, left:right] = 15
    return image


class TestKeepingTheContainerAndDroppingWhatItContains:
    """`outermost` is the change that made either detector usable.

    Raw, `heron` returns 137 to 231 boxes for pages holding 6 and 10 regions.
    The ink view says why that is not a detection failure: on `invoice_0002`
    **no ink is unclaimed**, while a third of it sits under two boxes at every
    confidence. The level is wrong, not the location, so no threshold reaches it.
    """

    def test_a_box_inside_another_is_dropped(self) -> None:
        panel = box(0.1, 0.1, 0.9, 0.9, "form")
        row = box(0.2, 0.2, 0.8, 0.3, "text")
        assert outermost([panel, row]) == [panel]

    def test_the_container_survives_however_they_are_ordered(self) -> None:
        """Sorted by area rather than by arrival, so a detector that happens to
        report the inside first cannot invert the rule."""
        panel = box(0.1, 0.1, 0.9, 0.9, "form")
        row = box(0.2, 0.2, 0.8, 0.3, "text")
        assert outermost([row, panel]) == [panel]

    def test_two_zones_side_by_side_both_survive(self) -> None:
        """The case a symmetric overlap test would destroy.

        Two Zones in one Band can share a slice of their area without either
        containing the other, which is why `_covered_by` divides by the *inner*
        box and `CONTAINED` sits at 0.70 rather than 0.50.
        """
        left = box(0.05, 0.1, 0.48, 0.4)
        right = box(0.52, 0.1, 0.95, 0.4)
        assert outermost([left, right]) == [left, right]

    def test_a_box_mostly_but_not_wholly_inside_is_still_dropped(self) -> None:
        """Detector edges disagree by a few pixels on boxes that plainly nest, so
        the test is a share and not containment."""
        panel = box(0.1, 0.1, 0.9, 0.9, "form")
        overhanging = box(0.08, 0.2, 0.8, 0.3)
        assert _share_inside(overhanging, panel) > CONTAINED
        assert outermost([panel, overhanging]) == [panel]

    def test_boxes_that_merely_touch_are_both_kept(self) -> None:
        above = box(0.1, 0.1, 0.9, 0.3)
        below = box(0.1, 0.3, 0.9, 0.5)
        assert outermost([above, below]) == [above, below]

    def test_nothing_in_gives_nothing_out(self) -> None:
        assert outermost([]) == []


class TestDroppingWhatAUnionSwallowed:
    """`outermost` runs first, and the unions after it can undo it.

    `attach_trailing_rows` and `attach_headings` replace two boxes with one
    larger one, and on three corpus documents that box swallowed a neighbour
    which was then read twice and printed twice — `statement_0006`'s two
    totals, `menu_0012`'s `To begin`, `cv_0013`'s `Senior Structural
    Engineer`. See `detector.without_enclosed`.
    """

    def test_a_box_wholly_inside_another_is_dropped(self) -> None:
        table = box(0.03, 0.13, 0.97, 0.935, "table")
        amount = box(0.64, 0.927, 0.70, 0.935)
        assert without_enclosed([table, amount]) == [table]

    def test_an_edge_shared_with_the_container_is_still_inside(self) -> None:
        """`cv_0013`'s heading starts on the same left edge as the block
        around it, and its bottom edge is the table's in `statement_0006`."""
        block = box(0.377, 0.039, 0.584, 0.132)
        heading = box(0.377, 0.086, 0.568, 0.106, "section_header")
        assert without_enclosed([heading, block]) == [block]

    def test_a_box_mostly_but_not_wholly_inside_is_kept(self) -> None:
        """`nonlatin_0014`'s shape, and the reason this is not `CONTAINED`:
        0.696 of its pairs box lies inside the full-width box below, and the
        rest holds `ΤΠΥ = 2026/0417`, which no other crop has. Dropping a box
        is safe only when all of it is inside another."""
        wide = box(0.034, 0.074, 0.966, 0.145, "key_value_region")
        pairs = box(0.827, 0.044, 0.966, 0.137, "section_header")
        assert 0.6 < _share_inside(pairs, wide) < 1.0
        assert without_enclosed([pairs, wide]) == [pairs, wide]

    def test_two_zones_side_by_side_both_survive(self) -> None:
        left = box(0.05, 0.1, 0.48, 0.4)
        right = box(0.52, 0.1, 0.95, 0.4)
        assert without_enclosed([left, right]) == [left, right]

    def test_one_region_found_twice_is_kept_once(self) -> None:
        """Two identical boxes each lie inside the other; dropping both would
        lose the region outright."""
        first = box(0.1, 0.1, 0.9, 0.3, "text")
        second = box(0.1, 0.1, 0.9, 0.3, "list")
        assert without_enclosed([first, second]) == [first]

    def test_nothing_in_gives_nothing_out(self) -> None:
        assert without_enclosed([]) == []

    def test_the_summary_row_union_leaves_one_valid_zone(self) -> None:
        """End to end, `statement_0006`'s shape: the table takes the strip
        under it and, with it, an amount printed on the same line. Without
        this rule the page came back as two Zones in one Band, one inside the
        other, and `wire.validate_bands` refused it."""
        engine = LayoutEngine(Fake([
            box(0.05, 0.30, 0.95, 0.80, "table"),
            box(0.05, 0.82, 0.60, 0.85, "key_value_region"),
            box(0.70, 0.82, 0.80, 0.85, "text"),
        ]))
        zones = engine.detect_zones(page([(30, 120, 570, 320),
                                          (30, 328, 360, 340),
                                          (420, 328, 480, 340)]))

        assert len(zones) == 1
        validate_bands(zones)


def _share_inside(inner: Detection, outer: Detection) -> float:
    wide = min(inner.right, outer.right) - max(inner.left, outer.left)
    tall = min(inner.bottom, outer.bottom) - max(inner.top, outer.top)
    area = (inner.right - inner.left) * (inner.bottom - inner.top)
    return (wide * tall) / area


class TestFoldingAHeadingIntoWhatItNames:
    """Run 67 is why this exists.

    With every heading standing as its own Zone, `invoice_0002` reported all five
    panel titles as `None` — `_classify` reads a Zone's title off that Zone's own
    crop, and the crop no longer held it. This is not tidying the zone count; it
    is putting the title back in the picture the classifier is shown.
    """

    def test_a_heading_absorbs_the_region_below_it(self) -> None:
        heading = box(0.05, 0.10, 0.30, 0.13, "section_header")
        body = box(0.05, 0.16, 0.90, 0.40, "key_value_region")
        merged = attach_headings([heading, body])

        assert len(merged) == 1
        assert (merged[0].top, merged[0].bottom) == (0.10, 0.40)
        assert merged[0].right == 0.90, "the union spans both"

    def test_a_heading_far_above_its_neighbour_stays_separate(self) -> None:
        """The false case in the corpus: a heading whose own panel is empty, so
        the nearest box below belongs to the next section."""
        heading = box(0.05, 0.10, 0.30, 0.13, "section_header")
        far = box(0.05, 0.13 + HEADING_GAP * 2, 0.90, 0.60)
        assert len(attach_headings([heading, far])) == 2

    def test_the_nearest_box_below_is_the_only_candidate(self) -> None:
        """A heading too far from its neighbour does not reach past it.

        Worth pinning because the distance test used to sit inside the search
        rather than after it, where a filtered-out neighbour left the *next* box
        down as the nearest survivor. It never fired — a farther box has a larger
        gap, so it fails any test the nearer one failed — but only for the two
        tests in this file, and the relative rule divides by a different number
        for every heading.
        """
        heading = box(0.05, 0.10, 0.30, 0.13, "section_header")
        near = box(0.05, 0.13 + HEADING_GAP * 2, 0.90, 0.40)
        far = box(0.05, 0.45, 0.90, 0.60)
        assert len(attach_headings([heading, near, far])) == 3

    def test_a_heading_does_not_absorb_another_heading(self) -> None:
        first = box(0.05, 0.10, 0.30, 0.13, "section_header")
        second = box(0.05, 0.15, 0.30, 0.18, "section_header")
        assert len(attach_headings([first, second])) == 2

    def test_two_headings_cannot_claim_the_same_region(self) -> None:
        """Without this, two captions stacked in a column both swallow the block
        beneath them and one of them vanishes."""
        upper = box(0.05, 0.10, 0.30, 0.13, "section_header")
        lower = box(0.05, 0.15, 0.30, 0.18, "section_header")
        body = box(0.05, 0.20, 0.90, 0.40)
        merged = attach_headings([upper, lower, body])
        assert len(merged) == 2, "one heading merges, the other stands alone"

    def test_a_heading_beside_rather_than_above_is_left_alone(self) -> None:
        heading = box(0.05, 0.10, 0.30, 0.13, "section_header")
        elsewhere = box(0.60, 0.14, 0.95, 0.40)
        assert len(attach_headings([heading, elsewhere])) == 2

    def test_both_vocabularies_are_covered(self) -> None:
        """`section_header` is heron's word, `title` DocStructBench's."""
        for name in ("section_header", "title", "caption", "table_caption"):
            merged = attach_headings([box(0.05, 0.10, 0.30, 0.13, name),
                                      box(0.05, 0.16, 0.90, 0.40)])
            assert len(merged) == 1, f"{name} should attach"


class TestJudgingTheGapAgainstTheGapAbove:
    """`DTH_HEADING_RULE=relative` — a heading is closer to what it names than
    to what it follows.

    `HEADING_GAP` asks how far down the page a gap is, which is a question about
    these five fixtures. Re-derived pre-snap against the fixture builders' Zone
    contents, it answers 4 of 14 heading cases wrongly, and neither relative
    measure spec 0006 proposed does better. The ratio against the gap *above*
    does: every true merge in the corpus sits at 1.293 or less, the nearest false
    one at 2.89.
    """

    def test_a_heading_nearer_its_body_than_its_neighbour_merges(self) -> None:
        above = box(0.05, 0.05, 0.90, 0.20)
        heading = box(0.05, 0.40, 0.30, 0.43, "section_header")
        body = box(0.05, 0.46, 0.90, 0.70)

        assert len(attach_headings([above, heading, body], relative=True)) == 2

    def test_a_heading_nearer_what_it_follows_stays_separate(self) -> None:
        """The shape the absolute rule cannot see: both gaps are small, and it
        is their *ratio* that says this heading belongs to neither box."""
        above = box(0.05, 0.05, 0.90, 0.40)
        heading = box(0.05, 0.41, 0.30, 0.44, "section_header")
        far_body = box(0.05, 0.44 + 0.01 * HEADING_GAP_RATIO * 2, 0.90, 0.80)

        assert len(attach_headings([above, heading, far_body], relative=True)) == 3

    def test_the_same_gap_is_read_differently_by_the_two_rules(self) -> None:
        """The point of the flag, in one page.

        A 0.06 gap below a heading with 0.30 of white space above it: past
        `HEADING_GAP`, so the absolute rule leaves it, and comfortably inside the
        ratio, so the relative rule merges it. This is `sample_css_0004`'s card,
        which is the whole of the difference between the two arms.
        """
        page = [box(0.05, 0.05, 0.90, 0.10),
                box(0.05, 0.40, 0.30, 0.44, "section_header"),
                box(0.05, 0.50, 0.90, 0.75)]

        assert len(attach_headings(page)) == 3, "absolute: 0.06 exceeds 0.05"
        assert len(attach_headings(page, relative=True)) == 2

    def test_nothing_above_measures_to_the_top_of_the_page(self) -> None:
        """Otherwise the rule is not total.

        Four of the corpus's fourteen headings have no box above them that
        overlaps horizontally, and their gaps below are non-monotonic — a merge
        at 0.044 sits between leaves at 0.032 and 0.081 — so no absolute
        threshold orders them. A panel title 0.40 down the page with its body
        0.04 beneath it is that case.
        """
        heading = box(0.05, 0.40, 0.30, 0.43, "section_header")
        body = box(0.05, 0.47, 0.90, 0.70)

        assert len(attach_headings([heading, body], relative=True)) == 1

    def test_a_box_beside_the_heading_is_not_above_it(self) -> None:
        """`invoice_0002`'s `Customer Details` is why. It sits in the right-hand
        column with the logo up and to the left of it, which shares no x with it
        — so the white space above it runs to the top of the page, not to the
        bottom of something in another column."""
        beside = box(0.60, 0.05, 0.95, 0.38)
        heading = box(0.05, 0.40, 0.30, 0.43, "section_header")
        body = box(0.05, 0.47, 0.55, 0.70)

        assert len(attach_headings([beside, heading, body], relative=True)) == 2

    def test_the_outer_bound_catches_what_the_ratio_would_admit(self) -> None:
        """`Services / Products`: an empty panel, so the nearest box below the
        heading is the next section's body at a gap of 0.147. Enough white space
        above it and the ratio alone lets that through."""
        heading = box(0.05, 0.50, 0.30, 0.53, "section_header")
        next_section = box(0.05, 0.53 + HEADING_GAP_MAX * 1.5, 0.90, 0.95)

        assert len(attach_headings([heading, next_section], relative=True)) == 2


class TestSplittingAPictureFromWhatStandsBesideIt:
    """`invoice_0002`'s ACME tile, `picture` 0.76, and the address beside it,
    `text` 0.44, both inside a third box — `picture` 0.72 — which `outermost`
    kept, so the tile was read as part of a prose Zone and scored as lost.
    See `detector.without_overreaching_pictures`.

    Page 600x400. Coordinates are the corpus shapes, scaled.
    """

    def ink(self, marks: list[tuple[int, int, int, int]]) -> np.ndarray:
        mask = np.zeros((400, 600), dtype=np.uint8)
        for left, top, right, bottom in marks:
            mask[top:bottom, left:right] = 255
        return mask

    def test_a_picture_round_a_surer_picture_and_its_neighbour_goes(
            self) -> None:
        outer = box(0.60, 0.05, 0.90, 0.30, "picture", 0.72)
        tile = box(0.60, 0.05, 0.70, 0.29, "picture", 0.76)
        address = box(0.72, 0.06, 0.90, 0.30, "text", 0.44)
        mask = self.ink([(360, 20, 420, 116), (432, 24, 540, 120)])

        kept = without_overreaching_pictures([outer, tile, address], mask)
        assert kept == [tile, address]
        assert outermost(kept) == [tile, address]

    def test_a_picture_that_is_only_surer_pictures_stays(self) -> None:
        """`darkdeck_0009`'s row of four KPI cards: every inner picture
        scores higher, and there is no ink outside them. A group of cards is
        a different question from a figure beside its text."""
        outer = box(0.05, 0.20, 0.95, 0.30, "picture", 0.50)
        cards = [box(0.05 + i * 0.23, 0.20, 0.26 + i * 0.23, 0.30,
                     "picture", 0.80) for i in range(4)]
        mask = self.ink([(36 + i * 138, 84, 150 + i * 138, 116)
                         for i in range(4)])

        assert without_overreaching_pictures([outer, *cards], mask) == (
            [outer, *cards])

    def test_a_logo_surer_than_its_own_icon_stays_whole(self) -> None:
        """`invoice_0001`'s logo: `picture` 0.80 round its icon at 0.58 and a
        wordmark the detector also reads as text. Without the score test the
        logo is cut in two."""
        logo = box(0.05, 0.08, 0.40, 0.15, "picture", 0.80)
        icon = box(0.05, 0.08, 0.07, 0.15, "picture", 0.58)
        wordmark = box(0.09, 0.09, 0.40, 0.14, "text", 0.70)
        mask = self.ink([(30, 32, 42, 60), (54, 36, 240, 56)])

        assert without_overreaching_pictures([logo, icon, wordmark], mask) == (
            [logo, icon, wordmark])

    def test_only_a_picture_is_ever_taken_apart(self) -> None:
        """A panel round a surer box is every panel on every page: `outermost`
        keeping the container is the rule that made the detector usable."""
        panel = box(0.60, 0.05, 0.90, 0.30, "key_value_region", 0.50)
        tile = box(0.60, 0.05, 0.70, 0.29, "picture", 0.76)
        mask = self.ink([(360, 20, 420, 116), (432, 24, 540, 120)])

        assert without_overreaching_pictures([panel, tile], mask) == [panel, tile]

    def test_end_to_end_the_tile_and_its_address_share_a_band(self) -> None:
        engine = LayoutEngine(Fake([
            box(0.60, 0.05, 0.90, 0.30, "picture", 0.72),
            box(0.60, 0.05, 0.70, 0.29, "picture", 0.76),
            box(0.72, 0.06, 0.90, 0.30, "text", 0.54),
        ]))
        zones = engine.detect_zones(page([(360, 20, 420, 116),
                                          (432, 24, 540, 120)]))

        assert [(z.band, z.column) for z in zones] == [(0, 0), (0, 1)]
        validate_bands(zones)


class TestTakingARegionApartAgain:
    """The split `outermost` discarded.

    On `invoice_0001` heron reports `table` at 0.95 over both printed tables and
    *also* reports each of them, at 0.22 and 0.32. Keeping the container threw
    the second pair away, and run 67 shows the cost: one Zone with two header
    rows, and the column-sum Probe reconciling nothing where it had said 385.00.
    """

    def ink(self, marks: list[tuple[int, int, int, int]]) -> np.ndarray:
        mask = np.zeros((400, 600), dtype=np.uint8)
        for left, top, right, bottom in marks:
            mask[top:bottom, left:right] = 255
        return mask

    def test_a_table_holding_tables_that_tile_it_becomes_them(self) -> None:
        parent = box(0.05, 0.10, 0.95, 0.90, "table", 0.95)
        upper = box(0.05, 0.10, 0.95, 0.45, "table", 0.32)
        lower = box(0.05, 0.55, 0.95, 0.90, "table", 0.22)
        mask = self.ink([(30, 40, 570, 180), (30, 220, 570, 360)])

        split = split_containers([parent], [parent, upper, lower], mask)
        assert split == [upper, lower]

    def test_parts_that_leave_ink_behind_do_not_replace_the_whole(self) -> None:
        """`sample_table_0003`: two low-confidence guesses inside one real table,
        carrying 0.46 of its ink. That is fragments, not a split."""
        parent = box(0.05, 0.10, 0.95, 0.90, "table", 0.99)
        sliver = box(0.05, 0.10, 0.95, 0.20, "table", 0.11)
        other = box(0.05, 0.80, 0.95, 0.90, "table", 0.10)
        mask = self.ink([(30, 40, 570, 360)])

        assert split_containers([parent], [parent, sliver, other], mask) == [parent]

    def test_prose_is_never_split_into_its_lines(self) -> None:
        """The whole reason only `table` is splittable. Swept with no class
        restriction the rule fires on `text` holding `text` — which is exactly
        the failure `outermost` exists to prevent."""
        parent = box(0.05, 0.10, 0.95, 0.90, "text", 0.96)
        lines = [box(0.05, 0.10 + i * 0.27, 0.95, 0.30 + i * 0.27, "text", 0.5)
                 for i in range(3)]
        mask = self.ink([(30, 40, 570, 360)])

        assert split_containers([parent], [parent, *lines], mask) == [parent]

    def test_a_region_with_no_parts_proposed_is_left_alone(self) -> None:
        parent = box(0.05, 0.10, 0.95, 0.90, "table", 0.95)
        mask = self.ink([(30, 40, 570, 360)])
        assert split_containers([parent], [parent], mask) == [parent]


class TestGivingATableItsSummaryRowBack:
    """`invoice_0001`'s total is set below the line-item rules and heron reports
    it separately, so the table Zone reached 0.883 where the reference reaches
    0.932. `probes.py` reconciles a table's SUMMARY rows against its DATA rows,
    and both have to be in one Zone — which is why run 67 lost the 385.00."""

    def test_a_short_strip_under_a_table_joins_it(self) -> None:
        table = box(0.05, 0.30, 0.95, 0.80, "table")
        total = box(0.70, 0.82, 0.95, 0.85, "key_value_region")
        merged = attach_trailing_rows([table, total])

        assert len(merged) == 1
        assert merged[0].bottom == 0.85
        assert merged[0].label == "table"

    def test_a_table_under_a_table_is_the_next_table(self) -> None:
        """The one false candidate in the corpus, and the class test alone rules
        it out — two stacked tables are two regions, not one with a summary."""
        first = box(0.05, 0.10, 0.95, 0.30, "table")
        second = box(0.05, 0.32, 0.95, 0.80, "table")
        assert len(attach_trailing_rows([first, second])) == 2

    def test_a_tall_block_below_is_its_own_region(self) -> None:
        table = box(0.05, 0.10, 0.95, 0.30, "table")
        paragraph = box(0.05, 0.32, 0.95, 0.70, "text")
        assert len(attach_trailing_rows([table, paragraph])) == 2

    def test_a_strip_far_below_is_its_own_region(self) -> None:
        table = box(0.05, 0.10, 0.95, 0.30, "table")
        distant = box(0.70, 0.60, 0.95, 0.63, "key_value_region")
        assert len(attach_trailing_rows([table, distant])) == 2

    def test_nothing_attaches_under_a_region_that_is_not_a_table(self) -> None:
        prose = box(0.05, 0.10, 0.95, 0.30, "text")
        strip = box(0.70, 0.31, 0.95, 0.34, "key_value_region")
        assert len(attach_trailing_rows([prose, strip])) == 2

    def test_a_heading_under_a_table_is_never_its_summary_row(self) -> None:
        """The fix for a content loss the T1 ratchet caught — spec 0007 A0.

        `darkdeck_0009` prints `<h2>What Q4 commits to</h2>` directly under its
        component table, and heron reports it as its own `section_header`. It is
        short and it is close, so it met every other test here and was folded
        into the table — and `attach_headings`, which runs after this, then had
        nothing left to attach to the paragraph below. The heading stopped being
        printed at all.

        A heading names the region *beneath* it rather than being one. So it can
        never be the last row of the region above, whatever its proportions.
        """
        table = box(0.05, 0.30, 0.95, 0.80, "table")
        heading = box(0.05, 0.82, 0.40, 0.84, "section_header")

        assert len(attach_trailing_rows([table, heading])) == 2

    def test_every_heading_class_is_refused_not_just_section_header(
        self,
    ) -> None:
        """`report_0011`'s absorbed heading is a table caption, and the two
        detectors spell that differently — heron's `caption` against
        DocStructBench's `table_caption`. The guard is on the whole vocabulary
        `attach_headings` claims, or it fixes one detector and not the other."""
        table = box(0.05, 0.30, 0.95, 0.80, "table")

        for label in ("section_header", "title", "caption",
                      "table_caption", "figure_caption"):
            heading = box(0.05, 0.82, 0.40, 0.84, label)
            assert len(attach_trailing_rows([table, heading])) == 2, label

    def test_the_total_it_exists_for_still_attaches(self) -> None:
        """Narrowing the rule must not narrow what it already caught: two runs
        lost `invoice_0001`'s table and its 385.00 Probe to this."""
        table = box(0.05, 0.30, 0.95, 0.80, "table")
        total = box(0.70, 0.82, 0.95, 0.85, "key_value_region")

        assert len(attach_trailing_rows([table, total])) == 1


class TestBoxesBecomeZones:
    """What the adapter must produce for the rest of the pipeline to work."""

    def test_every_detection_becomes_a_zone(self) -> None:
        engine = LayoutEngine(Fake([box(0.05, 0.05, 0.45, 0.35),
                                    box(0.55, 0.05, 0.95, 0.35)]))
        zones = engine.detect_zones(page([(30, 20, 270, 140),
                                          (330, 20, 570, 140)]))
        assert len(zones) == 2

    def test_the_kind_is_a_placeholder_and_says_so(self) -> None:
        """A detector cannot read a region, and does not pretend to. `_classify`
        overwrites every Kind from the Zone's own crop moments later and scores
        6/6 doing it, so guessing here would be a guess nobody reads."""
        engine = LayoutEngine(Fake([box(0.05, 0.05, 0.95, 0.35, "table")]))
        zones = engine.detect_zones(page([(30, 20, 570, 140)]))
        assert zones[0].kind is Kind.PROSE

    def test_a_running_head_and_a_footer_get_their_roles(self) -> None:
        engine = LayoutEngine(Fake([
            box(0.05, 0.02, 0.95, 0.08, "page_header"),
            box(0.05, 0.30, 0.95, 0.50, "text"),
            box(0.05, 0.90, 0.95, 0.96, "page_footer"),
        ]))
        zones = engine.detect_zones(page([(30, 8, 570, 32),
                                          (30, 120, 570, 200),
                                          (30, 360, 570, 384)]))
        assert [zone.role for zone in zones] == [Role.HEADER, Role.BODY,
                                                 Role.FOOTER]

    def test_the_top_band_is_the_header(self) -> None:
        """What both references say: `invoice_0001` marks its logo and invoice
        numbers `header` and nothing below them, `invoice_0002` its whole first
        Band. Run 67 reported four `role expected header, got body` mismatches
        with everything defaulting to `BODY`; this removes all of
        `invoice_0001`'s.

        It cannot remove all of `invoice_0002`'s — that fixture also calls its
        *second* Band `header`, which no Band index recovers. Role is semantic
        where the class name runs out, and the rule is kept to what the corpus
        supports.
        """
        engine = LayoutEngine(Fake([
            box(0.05, 0.05, 0.45, 0.15, "picture"),
            box(0.55, 0.05, 0.95, 0.15, "key_value_region"),
            box(0.05, 0.40, 0.95, 0.60, "table"),
        ]))
        zones = engine.detect_zones(page([(30, 20, 270, 60),
                                          (330, 20, 570, 60),
                                          (30, 160, 570, 240)]))
        assert [z.role for z in zones] == [Role.HEADER, Role.HEADER, Role.BODY]

    def test_bands_and_columns_are_derived_from_the_boxes(self) -> None:
        """A detector reports no Bands, so there is nothing to choose between.

        The deleted vision layout pass reported Bands of its own that might have
        been believed instead, which was once a flag; this path never had that
        choice, which is why derivation is unconditional here.
        """
        engine = LayoutEngine(Fake([
            box(0.05, 0.05, 0.45, 0.20),
            box(0.55, 0.05, 0.95, 0.20),
            box(0.05, 0.50, 0.95, 0.70),
        ]))
        zones = engine.detect_zones(page([(30, 20, 270, 80),
                                          (330, 20, 570, 80),
                                          (30, 200, 570, 280)]))
        assert [(z.band, z.column) for z in zones] == [(0, 0), (0, 1), (1, 0)]

    def test_the_boxes_are_moved_onto_their_ink(self) -> None:
        """Raw detector edges clip glyphs — 6 split masses on `invoice_0001` and
        44 across the corpus — and snapping takes every one to zero without
        moving coverage. Unconditional for the same reason `DTH_SNAP_ZONES` is
        on by default."""
        engine = LayoutEngine(Fake([box(0.02, 0.02, 0.98, 0.98)]))
        zones = engine.detect_zones(page([(120, 100, 480, 300)]))

        bbox = zones[0].bbox
        assert bbox is not None
        assert bbox.left > 0.02 and bbox.right < 0.98, "should have tightened"
        assert bbox.top > 0.02 and bbox.bottom < 0.98

    def test_low_confidence_detections_are_dropped(self) -> None:
        engine = LayoutEngine(Fake([box(0.05, 0.05, 0.95, 0.35, score=0.9),
                                    box(0.05, 0.50, 0.95, 0.80, score=0.1)]),
                              confidence=0.5)
        assert len(engine.detect_zones(page([(30, 20, 570, 140),
                                             (30, 200, 570, 320)]))) == 1

    def test_the_detectors_own_confidence_is_the_default(self) -> None:
        """Each model's threshold is a property of the model and is recorded on
        its class with what was measured at it — `heron` 0.40, `doclayout_yolo`
        0.15. The pipeline does not have an opinion."""
        assert LayoutEngine(Fake([])).confidence == Fake.confidence

    def test_it_is_shown_the_full_resolution_page(self) -> None:
        """Not the 384px thumbnail the VLM sees — which is the point. A detector
        that were handed the downscale would inherit the resolution ceiling this
        exists to escape."""
        engine = LayoutEngine(Fake([]))
        image = page([(30, 20, 570, 140)])
        engine.detect_zones(image)
        assert engine.detector.images[0].shape == image.shape  # type: ignore[attr-defined]

    def test_the_hint_is_ignored(self) -> None:
        """A Hint is addressed to a language model. A detector has no use for
        it, and accepting it keeps the seam one shape."""
        engine = LayoutEngine(Fake([box(0.05, 0.05, 0.95, 0.35)]))
        marks = [(30, 20, 570, 140)]
        plain = engine.detect_zones(page(marks))
        loaded = engine.detect_zones(page(marks), hint="an invoice")
        assert [z.bbox for z in plain] == [z.bbox for z in loaded]


class TestChoosingTheLayoutEngine:
    """Which engine finds the Zones, and what an empty flag falls back to."""

    def test_the_default_is_the_detector(self) -> None:
        """Measured against each other one flag apart, all five fixtures: the
        vision path raises `MappingError` on three of them and matches none,
        the detector converts all five and matches `invoice_0001`. See
        `config.DEFAULT_LAYOUT_DETECTOR` for the table."""
        assert DEFAULT_LAYOUT_DETECTOR == "heron"
        assert load(env={}).layout_detector == "heron"
        assert isinstance(default_engines(load(env={})).layout, LayoutEngine)

    @pytest.mark.parametrize("spelling", ["none", "off", "NONE", " none "])
    def test_asking_for_the_vision_model_by_name_now_refuses(
        self, spelling: str
    ) -> None:
        """The path is gone, and saying so beats failing somewhere obscure.

        Spec 0007 Thread 0 deleted the vision layout path from every
        Conversion: it raised `MappingError` on three of five documents and
        matched none. A `DTH_LAYOUT_DETECTOR=none` left in somebody's shell or
        dotenv must not be handed to `from_name` as if it were a detector's
        name — it is a stale instruction and it is told so.
        """
        settings = load(env={"DTH_LAYOUT_DETECTOR": spelling})
        with pytest.raises(ValueError, match="retired"):
            default_engines(settings)

    def test_an_empty_flag_in_code_refuses_for_the_same_reason(self) -> None:
        """`Settings(layout_detector="")` used to be how the suite replayed
        recordings. `test_bakeoff.py`'s stub detector is how it does now."""
        with pytest.raises(ValueError, match="retired"):
            default_engines(Settings(layout_detector=""))

    def test_an_empty_environment_variable_still_reads_as_unset(self) -> None:
        """The deliberate rule that an empty variable means "I left this
        alone", meeting a default that is not empty. Asserting it stops someone
        "fixing" `DTH_LAYOUT_DETECTOR=` by loosening that rule for every key."""
        assert load(env={"DTH_LAYOUT_DETECTOR": ""}).layout_detector == "heron"

    def test_the_default_confidence_defers_to_the_detector(self) -> None:
        assert DEFAULT_DETECTOR_CONFIDENCE == 0.0
        assert load(env={}).detector_confidence == 0.0

    def test_naming_a_detector_selects_it(self) -> None:
        settings = load(env={"DTH_LAYOUT_DETECTOR": "heron"})
        engine = default_engines(settings).layout
        assert isinstance(engine, LayoutEngine)
        assert engine.model == "heron"

    def test_the_confidence_can_be_overridden(self) -> None:
        settings = load(env={"DTH_LAYOUT_DETECTOR": "heron",
                             "DTH_DETECTOR_CONFIDENCE": "0.25"})
        engine = default_engines(settings).layout
        assert isinstance(engine, LayoutEngine)
        assert engine.confidence == 0.25

    def test_an_unknown_name_says_which_ones_exist(self) -> None:
        with pytest.raises(DetectorUnavailable, match="heron"):
            from_name("nonesuch")

    def test_a_detector_satisfies_the_layout_seam(self) -> None:
        """The whole reason `LayoutEngine` was split out of `VisionEngine`: a
        detector has no `classify_zone` and no `read_cell` to offer, and should
        not have to pretend otherwise to fill the layout role."""
        assert isinstance(LayoutEngine(Fake([])), LayoutEngineProtocol)

    def test_the_replayed_suite_fills_it_the_same_way(self) -> None:
        """The recorded-response suite hands the layout stage fixed Zones, and
        that stand-in must be held to the Protocol the detector is: a fake of a
        different shape would test a seam production does not have."""
        from .replay import FixedLayout

        assert isinstance(FixedLayout([]), LayoutEngineProtocol)


class TestAdoptingAContainerTheThresholdDropped:
    """`DTH_PREFER_CONTAINER` — the mirror of `split_containers`.

    That function re-opens a container the threshold kept. This one restores one
    the threshold dropped: five of the corpus's remaining over-splits have their
    container sitting in the pool at 0.05-0.27 against a 0.40 threshold, so
    `outermost` never saw it.
    """

    @staticmethod
    def _mask(rows: list[tuple[float, float]]) -> np.ndarray:
        """A page with ink in the given normalised row bands, full width."""
        mask = np.zeros((200, 200), dtype=np.uint8)
        for top, bottom in rows:
            mask[int(top * 200):int(bottom * 200), 20:180] = 255
        return mask

    def test_a_stack_inside_a_weak_container_becomes_that_container(self) -> None:
        parts = [box(0.10, 0.10, 0.90, 0.13), box(0.10, 0.14, 0.90, 0.17)]
        container = box(0.09, 0.09, 0.91, 0.18, "key_value_region", 0.20)
        mask = self._mask([(0.10, 0.13), (0.14, 0.17)])

        merged = prefer_container(parts, parts + [container], mask, 0.40)

        assert len(merged) == 1
        assert merged[0] is container

    def test_boxes_side_by_side_are_a_band_and_are_left_alone(self) -> None:
        """The one signal that separated every case in the corpus. Stacked
        contents are one region printed as lines; contents side by side are a
        row of the page the detector drew one rectangle around."""
        parts = [box(0.10, 0.10, 0.45, 0.17), box(0.55, 0.10, 0.90, 0.17)]
        container = box(0.09, 0.09, 0.91, 0.18, "key_value_region", 0.20)
        mask = self._mask([(0.10, 0.17)])

        assert len(prefer_container(parts, parts + [container], mask, 0.40)) == 2

    def test_a_container_taller_than_the_bound_is_refused(self) -> None:
        """Without this `invoice_0001` loses its zero-mismatch Conversion: a
        `table` at 0.09 spanning 0.444 of the page reads both printed tables as
        one region, undoing `split_containers`."""
        parts = [box(0.10, 0.10, 0.90, 0.13), box(0.10, 0.60, 0.90, 0.63)]
        tall = box(0.09, 0.09, 0.91, 0.09 + CONTAINER_HEIGHT * 2,
                   "key_value_region", 0.20)
        mask = self._mask([(0.10, 0.13), (0.60, 0.63)])

        assert len(prefer_container(parts, parts + [tall], mask, 0.40)) == 2

    def test_a_page_level_class_is_never_a_zone(self) -> None:
        """`form` is heron's "this is a document". On `sample_css_0004` it spans
        the whole page, so offered the chance it collapses the document."""
        parts = [box(0.10, 0.10, 0.90, 0.13), box(0.10, 0.14, 0.90, 0.17)]
        whole = box(0.09, 0.09, 0.91, 0.18, "form", 0.20)
        mask = self._mask([(0.10, 0.13), (0.14, 0.17)])

        assert len(prefer_container(parts, parts + [whole], mask, 0.40)) == 2

    def test_a_container_at_or_above_the_threshold_is_not_a_candidate(
        self,
    ) -> None:
        """`outermost` has already had its say about those."""
        parts = [box(0.10, 0.10, 0.90, 0.13), box(0.10, 0.14, 0.90, 0.17)]
        strong = box(0.09, 0.09, 0.91, 0.18, "key_value_region", 0.80)
        mask = self._mask([(0.10, 0.13), (0.14, 0.17)])

        assert len(prefer_container(parts, parts + [strong], mask, 0.40)) == 2

    def test_a_container_reaching_past_its_parts_is_refused(self) -> None:
        """It must account for the parts' ink and bring none of its own —
        the test that stops it swallowing a neighbour."""
        parts = [box(0.10, 0.10, 0.90, 0.13), box(0.10, 0.14, 0.90, 0.17)]
        greedy = box(0.09, 0.09, 0.91, 0.24, "key_value_region", 0.20)
        mask = self._mask([(0.10, 0.13), (0.14, 0.17), (0.19, 0.23)])

        assert len(prefer_container(parts, parts + [greedy], mask, 0.40)) == 2

    def test_a_container_never_takes_in_a_picture(self) -> None:
        """`receipt_0010`, re-shot whole: the farewell line, the barcode and
        the three lines under it, gathered by a 0.15 `key_value_region`, were
        read as one prose Zone and the barcode was no longer drawn."""
        parts = [box(0.10, 0.10, 0.90, 0.12),
                 box(0.10, 0.14, 0.90, 0.20, "picture", 0.70),
                 box(0.10, 0.22, 0.90, 0.28)]
        container = box(0.09, 0.09, 0.91, 0.29, "key_value_region", 0.15)
        mask = self._mask([(0.10, 0.12), (0.14, 0.20), (0.22, 0.28)])
        texts = [parts[0], replace(parts[1], label="text"), parts[2]]
        assert len(prefer_container(texts, texts + [container], mask, 0.40)) == 1, (
            "the same stack with no picture in it is adopted, so what refuses "
            "the one below is the picture and nothing else")

        assert len(prefer_container(parts, parts + [container], mask, 0.40)) == 3

    def test_one_box_is_not_a_regrouping(self) -> None:
        part = [box(0.10, 0.10, 0.90, 0.17)]
        container = box(0.09, 0.09, 0.91, 0.18, "key_value_region", 0.20)
        mask = self._mask([(0.10, 0.17)])

        assert prefer_container(part, part + [container], mask, 0.40) == part
