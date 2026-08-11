"""The one ruler every geometry number is measured with.

These are arithmetic tests on hand-built rectangles, deliberately not fixture
tests: the point of the module under test is that a probe row and a run's contact
sheet cannot disagree, and that property is about the arithmetic, not about any
one page.

The asymmetry between `iou` and `covered_by` is what most of this file is about.
IoU cannot tell "the model cut one Zone in two" from "the model invented a Zone",
because both score low. Coverage can, and spec 0004 leans on the difference.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_to_html.geometry_score import (
    area,
    best_match,
    covered_by,
    expected_boxes,
    expected_zones,
    iou,
    mean_best_iou,
)
from doc_to_html.ir import BBox

FIXTURES = Path(__file__).parent / "fixtures"

WHOLE = BBox(0.0, 0.0, 1.0, 1.0)
"""The whole page."""

QUARTER = BBox(0.0, 0.0, 0.5, 0.5)
"""Its top-left quarter: a quarter of the area, wholly inside it."""


def test_a_box_is_identical_to_itself() -> None:
    assert iou(WHOLE, WHOLE) == pytest.approx(1.0)


def test_disjoint_boxes_share_nothing() -> None:
    left = BBox(0.0, 0.0, 0.4, 1.0)
    right = BBox(0.6, 0.0, 1.0, 1.0)
    assert iou(left, right) == 0.0


def test_boxes_that_only_touch_share_nothing() -> None:
    """An edge in common is not an overlap, so the gutter case scores zero."""
    left = BBox(0.0, 0.0, 0.5, 1.0)
    right = BBox(0.5, 0.0, 1.0, 1.0)
    assert iou(left, right) == 0.0


def test_a_box_inside_another_scores_the_area_ratio() -> None:
    """Union is the outer box, intersection is the inner, so IoU is the ratio."""
    assert iou(QUARTER, WHOLE) == pytest.approx(0.25)
    assert iou(WHOLE, QUARTER) == pytest.approx(0.25)


def test_coverage_is_asymmetric_where_iou_is_not() -> None:
    """The whole point: the same pair reads differently in each direction.

    A Zone cut in two gives halves that are fully covered by the reference they
    came from, while scoring badly on IoU. An invented Zone scores badly on both.
    """
    assert covered_by(QUARTER, WHOLE) == pytest.approx(1.0)
    assert covered_by(WHOLE, QUARTER) == pytest.approx(0.25)


def test_coverage_of_a_box_with_no_area_is_zero() -> None:
    """A sliver of zero height is what run 25 produced; it must not divide by it."""
    sliver = BBox(0.2, 0.5, 0.8, 0.5)
    assert covered_by(sliver, WHOLE) == 0.0
    assert area(sliver) == 0.0


def test_best_match_names_the_reference_it_matched() -> None:
    want = [BBox(0.0, 0.0, 0.4, 0.4), BBox(0.6, 0.6, 1.0, 1.0)]
    index, score = best_match(BBox(0.62, 0.62, 1.0, 1.0), want)
    assert index == 1
    # Wholly inside the second reference, so the union is that reference:
    # 0.38 x 0.38 of ink over a 0.4 x 0.4 rectangle.
    assert score == pytest.approx(0.1444 / 0.16)


def test_best_match_against_no_reference_matches_nothing() -> None:
    index, score = best_match(WHOLE, [])
    assert index == -1
    assert score == 0.0


def test_the_mean_is_taken_over_the_boxes_a_method_produced() -> None:
    """Per produced box, not per reference box.

    A method that finds one Zone perfectly and misses five scores 1.0 here. That
    is why `zones` is reported beside it and never collapsed into it — the
    reading spec 0004 pins down.
    """
    want = [BBox(0.0, 0.0, 0.5, 1.0), BBox(0.5, 0.0, 1.0, 1.0)]
    assert mean_best_iou([BBox(0.0, 0.0, 0.5, 1.0)], want) == pytest.approx(1.0)

    half_right = [BBox(0.0, 0.0, 0.5, 1.0), BBox(0.5, 0.0, 1.0, 0.5)]
    assert mean_best_iou(half_right, want) == pytest.approx(0.75)


def test_a_method_that_produced_nothing_scores_zero() -> None:
    assert mean_best_iou([], [WHOLE]) == 0.0


def test_scoring_against_no_reference_scores_zero() -> None:
    assert mean_best_iou([WHOLE], []) == 0.0


def test_the_reference_rectangles_come_off_the_expected_ir() -> None:
    """Read verbatim, whatever they say.

    Not pinned to particular coordinates: `invoice_0001`'s are now derived from
    `example/invoice.html` by `tools/fixture_geometry.py`, and a test asserting
    the old hand-typed numbers would have to be edited every time the truth got
    better, which is the wrong way round.
    """
    path = FIXTURES / "invoice_0001.expected.json"
    boxes = expected_boxes(path)
    written = json.loads(path.read_text())

    assert len(boxes) == len(written["zones"])
    first = written["zones"][0]["bbox"]
    assert boxes[0] == BBox(first["left"], first["top"],
                            first["right"], first["bottom"])


def _fixture_missing_one_box(tmp_path: Path) -> Path:
    """A reference IR whose first Zone was written without a rectangle."""
    written = {
        "zones": [
            {"kind": "prose", "role": "body", "band": 0, "column": 0},
            {"kind": "table", "role": "body", "band": 1, "column": 0,
             "bbox": {"left": 0.1, "top": 0.2, "right": 0.9, "bottom": 0.8}},
        ]
    }
    path = tmp_path / "partial.expected.json"
    path.write_text(json.dumps(written))
    return path


def test_a_reference_zone_keeps_its_kind_and_its_place(tmp_path: Path) -> None:
    """A Zone with no rectangle is still reported, and keeps its own index.

    Dropping it here would renumber every Zone after it, and a report that says
    "want 3" about the reference's Zone 4 is worse than no report. What to do
    about the gap is the caller's decision, not the loader's.
    """
    zones = expected_zones(_fixture_missing_one_box(tmp_path))

    assert [zone.index for zone in zones] == [0, 1]
    assert zones[0].box is None
    assert zones[0].kind == "prose"
    assert zones[1].box == BBox(0.1, 0.2, 0.9, 0.8)
    assert zones[1].band == 1


def test_scoring_refuses_a_reference_with_a_zone_it_cannot_place(
    tmp_path: Path,
) -> None:
    """Loudly, because the quiet version is a number that looks right.

    Six boxes scored against five references produces a perfectly plausible mean
    measured against the wrong page, and nothing downstream could tell it from a
    real result.
    """
    with pytest.raises(ValueError, match="Zone"):
        expected_boxes(_fixture_missing_one_box(tmp_path))


def test_a_box_inverted_on_both_axes_scores_zero_either_way(tmp_path: Path) -> None:
    """The two halves of the ruler agree on nonsense, and both say zero.

    `covered_by` delegates to the domain type's own overlap arithmetic while
    `iou` uses this module's clamped `area`. They clamp differently, so this
    pins the one input where that could show.
    """
    inverted = BBox(0.8, 0.9, 0.2, 0.1)
    assert iou(inverted, WHOLE) == 0.0
    assert covered_by(inverted, WHOLE) == 0.0
    assert mean_best_iou([inverted], [WHOLE]) == 0.0
