"""Moving a box onto the ink it was drawn around, safely.

The layout pass cannot produce metric coordinates — runs 26-28 measured that at
three resolutions and under two framings — so the boxes arrive on a coarse mental
grid and the page is asked where the edges really are.

This is the first change in the project's history that alters geometry after the
model returns it, so most of this file is about what the snap must never do
rather than what it does. A deterministic repair that silently costs a Conversion
is worse than no repair, because nobody would look for it.
"""

from __future__ import annotations

import numpy as np
import pytest

from dataclasses import replace
from pathlib import Path

from doc_to_html.geometry_score import iou
from doc_to_html.ir import BBox, Document, Kind, Role, Source, Zone
from doc_to_html.orchestrator import Conversion, EngineSet, snapped_or_original
from doc_to_html.preprocess import MAX_SNAP_GROWTH, Rectified, snap_to_ink

HEIGHT, WIDTH = 600, 800


def paper() -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)


def box(left: int, top: int, right: int, bottom: int) -> BBox:
    return BBox(left / WIDTH, top / HEIGHT, right / WIDTH, bottom / HEIGHT)


def pixels(b: BBox) -> tuple[int, int, int, int]:
    return (round(b.left * WIDTH), round(b.top * HEIGHT),
            round(b.right * WIDTH), round(b.bottom * HEIGHT))


def page_with_one_block(top: int = 240, bottom: int = 280,
                        left: int = 100, right: int = 500) -> np.ndarray:
    """One paragraph-sized block.

    Deliberately small relative to the page. `MAX_SNAP_GROWTH` is 5%, which is
    30px here, and it is sized against what real repairs need — the worst edge on
    `invoice.png` has to travel about 3% of the page. A block spanning a third of
    the sheet would need a bigger repair than any measured document has ever
    asked for, and a test built on one would be arguing with the constant rather
    than exercising the behaviour.
    """
    page = paper()
    page[top:bottom, left:right] = 30
    return page


class TestTrimming:
    def test_a_box_with_blank_margins_shrinks_to_the_ink(self) -> None:
        page = page_with_one_block()
        loose = box(50, 200, 600, 340)

        assert pixels(snap_to_ink(page, [loose])[0]) == (100, 240, 500, 280)

    def test_a_box_already_tight_is_returned_unchanged(self) -> None:
        """The snap has to be invisible where geometry is right.

        If it moves a correct box it is not a repair, it is a second source of
        geometry, and the run directories stop comparing.
        """
        page = page_with_one_block()
        tight = box(100, 240, 500, 280)

        assert snap_to_ink(page, [tight]) == [tight]


class TestGrowing:
    def test_a_box_cutting_a_block_grows_to_contain_it(self) -> None:
        """Zone 0's failure: a band through a logo, ending mid-ink."""
        page = page_with_one_block()
        through = box(100, 255, 500, 268)

        grown = snap_to_ink(page, [through])[0]

        assert pixels(grown) == (100, 240, 500, 280)

    def test_growth_stops_at_the_first_blank_line(self) -> None:
        """It reaches the rest of its own block and not the next one."""
        page = page_with_one_block()
        page[300:340, 100:500] = 30           # a second block, 20px below

        grown = snap_to_ink(page, [box(100, 255, 500, 268)])[0]

        assert pixels(grown)[3] == 280, "grew past the blank band into a neighbour"

    def test_growth_is_capped_on_a_page_that_is_ink_all_the_way_down(self) -> None:
        """Run 25's shape: a sliver inside a dense region, every row inked.

        Without a cap this grows until it meets its neighbours and turns a
        visible failure into a plausible-looking one.
        """
        page = paper()
        page[:, 100:500] = 30
        sliver = box(100, 300, 500, 302)

        grown = snap_to_ink(page, [sliver])[0]
        left, top, right, bottom = pixels(grown)

        assert top >= 300 - MAX_SNAP_GROWTH * HEIGHT - 1
        assert bottom <= 302 + MAX_SNAP_GROWTH * HEIGHT + 1


class TestWhatItMustNeverDo:
    def test_snapping_twice_is_snapping_once(self) -> None:
        page = page_with_one_block()
        once = snap_to_ink(page, [box(50, 150, 600, 400)])

        assert snap_to_ink(page, once) == once

    def test_it_cannot_make_two_boxes_overlap(self) -> None:
        """Both boxes want the same ink; neither may cross the midpoint.

        A layout that satisfied `validate_bands` before the snap has to satisfy
        it afterwards, or a deterministic improvement has cost a Conversion.
        """
        page = paper()
        page[:, 100:500] = 30                 # ink everywhere, so both will grow

        upper = box(100, 200, 500, 260)
        lower = box(100, 300, 500, 360)
        first, second = snap_to_ink(page, [upper, lower])

        assert first.bottom <= second.top
        assert iou(first, second) == 0.0

    def test_a_blank_zone_is_left_to_the_empty_crop_guard(self) -> None:
        """One failure, one owner.

        A box on white paper is `MIN_ZONE_INK`'s finding. Repairing it here would
        move it somewhere it was never asked to be and hide the fact that the
        layout pass invented it.
        """
        page = page_with_one_block()
        nowhere = box(600, 400, 780, 550)

        assert snap_to_ink(page, [nowhere]) == [nowhere]

    def test_a_separator_does_not_attract_growth(self) -> None:
        """A rule is ink and is explicitly not content.

        Growing onto one would stretch a Zone to a panel border and hand the
        Extractor a crop framed by furniture.
        """
        page = page_with_one_block()
        page[300:303, 60:760] = 30            # a rule 20px below the block

        grown = snap_to_ink(page, [box(100, 240, 500, 295)])[0]

        assert pixels(grown)[3] == 280

    def test_a_box_with_no_area_survives_untouched(self) -> None:
        assert snap_to_ink(page_with_one_block(), [box(300, 260, 300, 260)]) == [
            box(300, 260, 300, 260)]

    def test_no_boxes_is_not_a_crash(self) -> None:
        assert snap_to_ink(page_with_one_block(), []) == []


class TestSideBySideZones:
    def test_a_neighbouring_column_does_not_cap_vertical_growth(self) -> None:
        """Only boxes that could actually be grown into may cap an edge.

        A Zone in the next column cannot be reached by moving downward, and
        letting it cap the growth pins every box in a two-column Band to its
        neighbour's height.
        """
        page = paper()
        page[240:300, 100:300] = 30           # tall block, left column
        page[240:270, 500:700] = 30           # short block, right column

        tall, short = snap_to_ink(
            page, [box(100, 250, 300, 290), box(500, 240, 700, 270)])

        assert pixels(tall) == (100, 240, 300, 300)
        assert pixels(short) == (500, 240, 700, 270)


class TestTheMeasuredAnswers:
    """Run 32/33/34's six boxes and run 25's slivers, replayed as literals."""

    SHIPPED = [
        BBox(0.05, 0.10, 0.38, 0.14),
        BBox(0.75, 0.10, 0.94, 0.23),
        BBox(0.05, 0.24, 0.38, 0.39),
        BBox(0.75, 0.24, 0.94, 0.39),
        BBox(0.05, 0.41, 0.94, 0.63),
        BBox(0.05, 0.64, 0.94, 0.92),
    ]

    def invoice(self) -> np.ndarray:
        from pathlib import Path

        from doc_to_html.preprocess import rectify

        return rectify(Path(__file__).resolve().parent.parent
                       / "example" / "invoice.png").image

    def test_the_sliced_logo_box_gets_taller(self) -> None:
        """Zone 0 is a 336x34px band through a ~62px logo."""
        page = self.invoice()
        before = self.SHIPPED[0]
        after = snap_to_ink(page, list(self.SHIPPED))[0]

        assert after.bottom - after.top > before.bottom - before.top

    def test_no_box_is_left_overlapping_another(self) -> None:
        page = self.invoice()
        snapped = snap_to_ink(page, list(self.SHIPPED))

        for i, first in enumerate(snapped):
            for second in snapped[i + 1:]:
                assert iou(first, second) == pytest.approx(0.0, abs=1e-9)

    def test_it_is_idempotent_on_the_real_page(self) -> None:
        page = self.invoice()
        once = snap_to_ink(page, list(self.SHIPPED))

        assert snap_to_ink(page, once) == once


class TestTheOrchestratorKeepsWhatWorks:
    """Wiring, and the promise attached to it.

    The snap cannot create an overlap by construction, but "cannot" is an
    argument and a Conversion is a document someone is waiting for. So the
    Orchestrator re-validates and keeps the Engine's own geometry if the snapped
    Zones no longer pass — the worst case is exactly what shipped before.
    """

    def zones(self, boxes: list[BBox]) -> list[Zone]:
        return [
            Zone(kind=Kind.PROSE, role=Role.BODY, bbox=b, band=i, column=0)
            for i, b in enumerate(boxes)
        ]

    def test_good_geometry_is_snapped_onto_its_ink(self) -> None:
        page = page_with_one_block()
        loose = self.zones([box(50, 200, 600, 340)])

        moved = snapped_or_original(page, loose)

        assert moved[0].bbox is not None
        assert pixels(moved[0].bbox) == (100, 240, 500, 280)

    def test_geometry_that_would_stop_validating_is_kept_as_it_was(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The snap is forced to misbehave, because by construction it cannot.

        Overlap is impossible through the midpoint cap, so there is no page that
        provokes this naturally. The policy is still worth a test: it is the
        promise that a deterministic step can never cost a Conversion, and a
        promise nothing exercises is a comment.
        """
        page = page_with_one_block()
        original = self.zones([box(100, 240, 500, 280),
                               box(100, 300, 500, 340)])
        original[1] = replace(original[1], band=1)

        def swaps_the_bands(image: np.ndarray,
                            boxes: list[BBox]) -> list[BBox]:
            return list(reversed(boxes))

        monkeypatch.setattr("doc_to_html.orchestrator.snap_to_ink",
                            swaps_the_bands)

        kept = snapped_or_original(page, original)

        assert kept == original, "a layout that validated before must survive"

    def test_a_zone_without_geometry_leaves_every_box_alone(self) -> None:
        """One Zone with no bbox cannot be snapped, and must not silently drop
        the others by shifting them onto the wrong Zones."""
        page = page_with_one_block()
        mixed = self.zones([box(50, 200, 600, 340)])
        mixed.append(Zone(kind=Kind.PROSE, role=Role.BODY, bbox=None,
                          band=1, column=0))

        assert snapped_or_original(page, mixed) == mixed

    def test_no_zones_is_not_a_crash(self) -> None:
        assert snapped_or_original(page_with_one_block(), []) == []


class TestTheFlagDecidesWhetherItRunsAtAll:
    """`DTH_SNAP_ZONES`, and the fact that off means untouched.

    The snap shipped once without a way to turn it off, cost the document, and
    was reverted by deleting the call. This is that call back with a switch on
    it, so the pair that matters is: on, the boxes move; off, they are the
    Engine's own coordinates, bit for bit. The second is the one worth a test —
    a flag that leaks when unset is how run 39 happens twice.
    """

    class OneAnswer:
        """A layout Engine that returns a fixed answer and records the call."""

        def __init__(self, zones: list[Zone]) -> None:
            self.zones = zones
            self.calls = 0

        def detect_zones(self, image: np.ndarray, hint: str | None) -> list[Zone]:
            self.calls += 1
            return list(self.zones)

    def conversion(self, engine: OneAnswer, *, snap: bool) -> Conversion:
        engines = EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                            extract=engine, audit=engine)
        return Conversion(source=Path("unused.png"), engines=engines,
                          snap_zones=snap)

    def loose(self) -> list[Zone]:
        """One box drawn well outside the block it surrounds."""
        return [Zone(kind=Kind.PROSE, role=Role.BODY,
                     bbox=box(50, 200, 600, 340), band=0, column=0)]

    def source(self) -> Source:
        return Source(path="unused.png", sha256="0" * 64, width=WIDTH, height=HEIGHT)

    def rectified(self, page: np.ndarray) -> Rectified:
        return Rectified(image=page, source=self.source())

    def test_off_leaves_the_engines_coordinates_exactly_as_they_arrived(self) -> None:
        engine = self.OneAnswer(self.loose())
        document = Document(source=self.source())

        self.conversion(engine, snap=False)._layout(
            self.rectified(page_with_one_block()), document
        )

        assert document.zones == self.loose(), "unset must mean untouched"

    def test_on_moves_the_boxes_onto_the_ink(self) -> None:
        engine = self.OneAnswer(self.loose())
        document = Document(source=self.source())

        self.conversion(engine, snap=True)._layout(
            self.rectified(page_with_one_block()), document
        )

        assert document.zones[0].bbox is not None
        assert pixels(document.zones[0].bbox) == (100, 240, 500, 280)

    def test_the_flag_is_read_from_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Resolved per Conversion, so setting the variable is enough.

        Read at import instead, a bake-off arm that exports it would silently get
        the default and the run directory would record an arm that never ran.
        """
        monkeypatch.setenv("DTH_SNAP_ZONES", "1")
        assert Conversion(source=Path("unused.png"),
                          engines=None).snap_zones is True  # type: ignore[arg-type]

        monkeypatch.delenv("DTH_SNAP_ZONES")
        assert Conversion(source=Path("unused.png"),
                          engines=None).snap_zones is False  # type: ignore[arg-type]
