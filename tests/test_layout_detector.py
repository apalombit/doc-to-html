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

import numpy as np
import pytest

from doc_to_html.config import (
    DEFAULT_DETECTOR_CONFIDENCE,
    DEFAULT_LAYOUT_DETECTOR,
    load,
)
from doc_to_html.engines.base import LayoutEngine as LayoutEngineProtocol
from doc_to_html.engines.detector import (
    CONTAINED,
    HEADING_GAP,
    Detection,
    DetectorUnavailable,
    LayoutEngine,
    attach_headings,
    attach_trailing_rows,
    from_name,
    outermost,
    split_containers,
)
from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.ir import Kind, Role
from doc_to_html.orchestrator import default_engines


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

        `DTH_DERIVE_BANDS` exists because the *model* reports Bands of its own
        that might be believed instead; this path has no such choice, which is
        why derivation is unconditional here rather than behind the flag.
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

    def test_the_hint_and_the_ceiling_are_ignored(self) -> None:
        """Both are addressed to a language model. The Protocol already says an
        Engine with no use for `region_ceiling` may ignore it; a detector has no
        use for either, and accepting them keeps the seam one shape."""
        engine = LayoutEngine(Fake([box(0.05, 0.05, 0.95, 0.35)]))
        marks = [(30, 20, 570, 140)]
        plain = engine.detect_zones(page(marks))
        loaded = engine.detect_zones(page(marks), hint="an invoice",
                                     region_ceiling=1)
        assert [z.bbox for z in plain] == [z.bbox for z in loaded]


class TestChoosingTheLayoutEngine:
    """The flag off must mean nothing moved."""

    def test_the_default_is_the_vision_model(self) -> None:
        assert DEFAULT_LAYOUT_DETECTOR == ""
        assert load(env={}).layout_detector == ""
        assert isinstance(default_engines(load(env={})).layout, OllamaEngine)

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

    def test_the_vision_model_still_satisfies_it_too(self) -> None:
        """Structurally, with no edit — which is what makes the narrowing safe."""
        assert isinstance(
            OllamaEngine.from_settings(load(env={}), "qwen3-vl:4b"),
            LayoutEngineProtocol,
        )
