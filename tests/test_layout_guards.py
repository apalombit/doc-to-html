"""Checks that read the pixels back, rather than the model's answer again.

Every other safeguard in the project compares one part of the model's answer to
another — `validate_bands` puts boxes against boxes, Probes put a column sum
against a stated total, the Pairs Extractor puts extracted content against its
Zone's Kind. None of them looks at the page. So geometry that places a Zone where
nothing is printed satisfies all of them, reaches an Extractor, and the Extractor
answers, because a question with no true answer still gets an answer.

`qwen3.5:4b` at long edge 768 is that failure, measured: six boxes that passed
`validate_bands`, two of them blank, and a rendered document containing
`1 | 20` and "The following is a sample paragraph" read out of white paper —
with the line-item table missing entirely and nothing anywhere noticing.

Two guards, tested against geometry written out as literals. The run directories
those numbers came from are gone, and they were never in the repository to begin
with: `debug/` is gitignored, so a test that read one passed on one machine and
failed on every other.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from doc_to_html.ir import BBox, Kind, Role, Zone
from doc_to_html.orchestrator import empty_zone
from doc_to_html.preprocess import (
    MIN_ZONE_INK,
    ink_fraction,
    rectify,
    uncovered_ink,
)

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"

GOOD_GEOMETRY = [
    BBox(0.05, 0.10, 0.38, 0.14),
    BBox(0.75, 0.10, 0.94, 0.23),
    BBox(0.05, 0.24, 0.38, 0.39),
    BBox(0.75, 0.24, 0.94, 0.39),
    BBox(0.05, 0.41, 0.94, 0.63),
    BBox(0.05, 0.64, 0.94, 0.92),
]
"""`qwen3-vl:4b`'s answer for `invoice.png`, six Zones, byte-identical across
every run that has produced it. Written out rather than read from a run
directory: `debug/` is not in the repository, so a test that reads one passes
only on the machine that took it and fails on a fresh clone."""

SLIVER_GEOMETRY = [
    BBox(0.05, 0.02, 0.94, 0.03),
    BBox(0.05, 0.05, 0.94, 0.06),
    BBox(0.05, 0.29, 0.38, 0.30),
    BBox(0.75, 0.29, 0.94, 0.30),
    BBox(0.05, 0.51, 0.94, 0.52),
    BBox(0.05, 0.56, 0.94, 0.57),
]
"""The sliver failure's shape: regions collapsed to a line, the first two of them
over the top margin where nothing is printed.

`qwen3.5:4b` produced this class of answer at long edge 768 — six boxes that
satisfied `validate_bands`, two of them carrying 0.0% ink, and a rendered
document containing `1 | 20` read out of white paper with the line-item table
missing entirely. These coordinates are reconstructed to that shape rather than
copied from the run, which is no longer on disk. What the guards must do about a
blank box does not depend on which model drew it."""


def blank(height: int = 40, width: int = 400, noise: float = 0.0) -> np.ndarray:
    """Paper with nothing printed on it, optionally photographed."""
    page = np.full((height, width, 3), 245, dtype=np.int16)
    if noise:
        rng = np.random.default_rng(0)
        page = page + rng.normal(0, noise, page.shape).astype(np.int16)
    return np.clip(page, 0, 255).astype(np.uint8)


def with_text(height: int = 40, width: int = 400) -> np.ndarray:
    """The same paper with a band of dark pixels standing in for a line."""
    page = blank(height, width)
    page[15:25, 20:200] = 30
    return page


def recorded_zones(boxes: list[BBox]) -> list[Zone]:
    """The measured geometry as Zones, in the Band order it was returned in."""
    return [
        Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, band=index, column=0)
        for index, box in enumerate(boxes)
    ]


class TestInkFraction:
    def test_blank_paper_carries_no_ink(self) -> None:
        assert ink_fraction(blank()) == 0.0

    def test_printed_paper_does(self) -> None:
        assert ink_fraction(with_text()) > MIN_ZONE_INK

    @pytest.mark.parametrize("noise", [2.0, 8.0, 20.0])
    def test_photographed_blank_paper_stays_under_the_threshold(
        self, noise: float
    ) -> None:
        """The regression that decided this uses an absolute cut, not Otsu.

        Otsu splits a histogram into two classes whether or not the second one
        exists, so on blank paper it splits sensor noise and calls half of it
        ink: measured at 30.2% for sigma 2 and 47.0% for sigma 8. A guard built
        on it would rate an empty crop as the densest Zone on the page and pass
        exactly the case it exists to catch.
        """
        assert ink_fraction(blank(noise=noise)) < MIN_ZONE_INK

    def test_an_empty_array_is_not_a_crash(self) -> None:
        assert ink_fraction(np.zeros((0, 0, 3), dtype=np.uint8)) == 0.0


class TestEmptyZoneGuard:
    def zone_at(self, box: BBox) -> Zone:
        return Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, band=0, column=0)

    def test_a_blank_crop_is_rejected(self) -> None:
        page = blank(600, 800)
        found = empty_zone(page, self.zone_at(BBox(0.2, 0.2, 0.8, 0.5)))
        assert found is not None
        assert "blank" in str(found)

    def test_a_printed_crop_is_not(self) -> None:
        page = blank(600, 800)
        page[120:300, 160:640] = 30
        assert empty_zone(page, self.zone_at(BBox(0.2, 0.2, 0.8, 0.5))) is None

    def test_a_zone_without_geometry_is_left_to_nogeometry(self) -> None:
        """Not this guard's finding to report. `zone_pixels` says it better."""
        naked = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=None, band=0, column=0)
        assert empty_zone(blank(600, 800), naked) is None


class TestAgainstRecordedGeometry:
    """The measured failures, replayed against the real page."""

    def test_the_sliver_run_loses_its_two_blank_zones(self) -> None:
        image = rectify(INVOICE).image
        zones = recorded_zones(SLIVER_GEOMETRY)
        rejected = [i for i, z in enumerate(zones) if empty_zone(image, z)]
        assert rejected == [0, 1], (
            "Zones 0 and 1 are the crops that produced '1 | 20' and "
            "'The following is a sample paragraph' out of white paper"
        )

    def test_good_geometry_is_untouched(self) -> None:
        """The guard must be invisible on the shipped path.

        The sparsest of these Zones carries 1.5% ink against a 0.1% threshold.
        A change here that starts rejecting one of them is mis-thresholded, not
        stricter.
        """
        image = rectify(INVOICE).image
        zones = recorded_zones(GOOD_GEOMETRY)
        assert [i for i, z in enumerate(zones) if empty_zone(image, z)] == []


class TestUncoveredInk:
    def test_ink_outside_every_box_is_reported(self) -> None:
        page = np.full((600, 800, 3), 245, dtype=np.uint8)
        page[300:420, 100:700] = 30
        assert uncovered_ink(page, []) != []

    def test_ink_inside_a_box_is_not(self) -> None:
        page = np.full((600, 800, 3), 245, dtype=np.uint8)
        page[300:420, 100:700] = 30
        covered = BBox(0.125, 0.5, 0.875, 0.7)
        assert uncovered_ink(page, [covered]) == []

    def test_a_separator_is_not_a_gap(self) -> None:
        """A rule is ink and is explicitly not a Zone.

        Thickness is what tells a rule from a paragraph without reading either,
        which is why `MIN_GAP_THICKNESS` exists. Without it this fires on every
        ruled invoice.
        """
        page = np.full((600, 800, 3), 245, dtype=np.uint8)
        page[299:302, 50:750] = 30
        assert uncovered_ink(page, []) == []

    def test_the_sliver_run_leaves_the_line_item_table_uncovered(self) -> None:
        image = rectify(INVOICE).image
        boxes = [z.bbox for z in recorded_zones(SLIVER_GEOMETRY) if z.bbox]
        gaps = uncovered_ink(image, boxes)
        assert gaps, "the run that lost the entire line-item table found no Gap"
        below = [g for g in gaps if g.top > 0.6]
        assert below, "the missing table sits below 0.6 and nothing was reported"

    def test_good_geometry_leaves_no_gap(self) -> None:
        """The false-positive guard, and the reason the merge kernel is narrow.

        Correct geometry yields no Gap at 0.02 x 0.04 and none at 0.02 x 0.06,
        but one at 0.03 x 0.06 — the horizontal term is what starts welding real
        Zones to their neighbours and inventing findings.
        """
        image = rectify(INVOICE).image
        boxes = [z.bbox for z in recorded_zones(GOOD_GEOMETRY) if z.bbox]
        assert uncovered_ink(image, boxes) == []
