"""One ruler for geometry, so a probe row and a run's contact sheet agree.

Every geometry number this project has recorded — runs 24 through 32, three
prompt arms, two models, four resolutions, a morphology sweep — is a mean best
IoU against the rectangles in an expected IR. Until now that number was computed
in three places: the layout probe carried an `iou` and a fixture loader, the
contact sheet's geometry report carried its own on a different box type, and the
CV probe wrapped the first in a third mean. They agreed, but only because someone
kept them agreeing.

Spec 0004 is about to add four ink-aware fields to that score. Adding them to
three copies is how the numbers before the change stop being comparable with the
numbers after it, which would cost the one thing those run directories exist to
provide. So the copies are collapsed here first, with nothing else changed:
this module is a move, not a new measurement.

**Coverage is asymmetric and IoU is not**, and the difference carries the
interesting cases. A box with low IoU and high coverage is half of a Zone the
model cut in two. A box with low IoU and low coverage is one it made up. Ranked
by IoU alone the two look the same, which is how spec 0001 came to record a Zone
as "invented" when it held the last line item and the total.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .ir import BBox
from .preprocess import ImageArray, _cv2, content_ink


def area(box: BBox) -> float:
    """The rectangle's area, never negative.

    Clamped rather than trusted: a layout answer whose `right` is left of its
    `left` is rejected upstream, but this module also scores hand-built boxes and
    a negative area would silently turn an IoU into nonsense rather than zero.
    """
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def iou(a: BBox, b: BBox) -> float:
    """Intersection over union — how much two rectangles are the same rectangle."""
    wide = min(a.right, b.right) - max(a.left, b.left)
    tall = min(a.bottom, b.bottom) - max(a.top, b.top)
    if wide <= 0 or tall <= 0:
        return 0.0
    overlap = wide * tall
    return overlap / (area(a) + area(b) - overlap)


def covered_by(inner: BBox, outer: BBox) -> float:
    """How much of `inner` sits inside `outer`, as a fraction of `inner`.

    The asymmetric half of the pair. Read it as a question about the first
    argument: "how much of this box is accounted for by that one?"
    """
    return inner.overlap_ratio(outer)


def best_match(got: BBox, want: Sequence[BBox]) -> tuple[int, float]:
    """The reference box this one matches best, and how well.

    Returns `(-1, 0.0)` when there is nothing to match against, so a caller
    scoring a run with no expected IR gets a number rather than an exception.
    Ties go to the earliest reference, which keeps report ordering stable.
    """
    if not want:
        return -1, 0.0
    scores = [iou(got, reference) for reference in want]
    best = max(range(len(scores)), key=lambda i: scores[i])
    return best, scores[best]


def mean_best_iou(got: Sequence[BBox], want: Sequence[BBox]) -> float:
    """Mean best IoU **per produced box** — the number runs 24-32 report.

    Per produced box, not per reference box, so a method that finds one Zone
    perfectly and misses the other five scores 1.0. That is a real hole and it is
    left open on purpose: `zones` is reported beside this number everywhere it
    appears, and spec 0004 adds `covered` for exactly the case this cannot see.
    Closing it by averaging over the references instead would swap one blind spot
    for another and silently break comparison with every run already recorded.
    """
    if not got:
        return 0.0
    return statistics.fmean(best_match(box, want)[1] for box in got)


DOUBLE_GAP_FACTOR = 3.0
"""How many times a box's own median line gap a band of whitespace must exceed
before the box is holding two separate things rather than one.

A ratio against the box's own leading rather than a fraction of the page, so a
dense table and an airy address block are judged by their own spacing. A page
constant would have to be wrong for one of them whatever value it took.

Sits in the middle of a measured gap between the two failure modes rather than
being picked. On `invoice_0001` the highest ratio reached by any box that should
*not* fire is 1.19 — the model's Zone 5, gaps of 22, 19, 18 and 18 against a
median of 18.5 — so false positives begin only below about 1.2. On the synthetic
page in the tests, a column strip welding three paragraphs together reaches 12.0,
gaps of 60 against a median of 5. Anything from roughly 1.2 to 12 separates them
on the evidence available; 3.0 is central in log terms and near neither edge.

That band is wide because it is measured on one page. `invoice_0001` is the only
document whose geometry has ever been scored, and a factor this far from either
edge is a bet that the other four fixtures do not narrow the band dramatically.
The fixture sweep is where that is checked.
"""


@dataclass(frozen=True)
class GeometryScore:
    """What one method's geometry was worth, in six numbers reported together.

    Never collapsed into one. Morphology reached IoU 0.475 on `invoice_0001` by
    welding the page into two full-height column strips — a description of a
    different document that a single-number ranking places just behind the model.
    `covered` and `doubles` are what separate "roughly the right regions with
    sloppy edges" from "confidently the wrong page", and they only do that while
    they are still visible beside the IoU.
    """

    zones: int
    """How many boxes the method produced."""

    iou: float
    """Mean best IoU per produced box — the number runs 24-32 already report."""

    covered: float
    """Fraction of the page's content ink inside **exactly one** box.

    Exactly one, so a segmenter that blankets the page in overlapping rectangles
    is penalised as hard as one that misses half of it. Both have failed to say
    where anything is.
    """

    splits: int
    """Connected masses of ink that some box's edge cuts through."""

    doubles: int
    """Boxes holding two masses parted by more whitespace than their own leading."""

    valid: bool | None = None
    """Whether Band validation accepted the answer, or `None` if nobody asked.

    Carried rather than computed: it is a property of the layout answer's Bands
    and columns, and this scores rectangles, which no longer carry either. The
    caller that parsed the answer is the one that knows.
    """


def _pixel_rect(box: BBox, width: int, height: int) -> tuple[int, int, int, int]:
    """A normalised box as half-open pixel bounds, clipped to the page.

    Rounded rather than truncated, which `crop` can afford to do and a ruler
    cannot: truncation pulls every edge inward by up to a pixel, so a box sitting
    exactly on its ink comes back having sliced a row off it. Measured on the
    synthetic page in the tests, truncation invented two splits and lost 0.8% of
    `covered` on geometry that was correct to the pixel.
    """
    left = min(max(round(box.left * width), 0), width)
    right = min(max(round(box.right * width), 0), width)
    top = min(max(round(box.top * height), 0), height)
    bottom = min(max(round(box.bottom * height), 0), height)
    return left, top, right, bottom


def _covered_share(mask: ImageArray, boxes: Sequence[BBox]) -> float:
    """Share of the ink that exactly one box claims.

    Boxes are counted **unpadded**, unlike `uncovered_ink`, which widens them by
    the same margin `crop` adds. The two are asking different questions: that one
    asks what an Extractor was shown, this one asks what the model drew. Padding
    here would also make every pair of adjacent Zones overlap by construction and
    collapse the "exactly one" test into noise about `PAD_X`.
    """
    ink = mask > 0
    total = int(ink.sum())
    if total == 0:
        return 0.0

    height, width = mask.shape[:2]
    claims = np.zeros((height, width), dtype=np.int32)
    for box in boxes:
        left, top, right, bottom = _pixel_rect(box, width, height)
        claims[top:bottom, left:right] += 1
    return float(np.logical_and(ink, claims == 1).sum()) / total


def _split_count(mask: ImageArray, boxes: Sequence[BBox]) -> int:
    """Masses of ink with pixels both inside and outside the same box.

    Counted per mass rather than per box, so a rule of text that three boxes all
    clip is one wounded piece of content, which is what a reader would see.
    """
    cv2 = _cv2()
    height, width = mask.shape[:2]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return 0

    areas = stats[:, cv2.CC_STAT_AREA]
    cut: set[int] = set()
    for box in boxes:
        left, top, right, bottom = _pixel_rect(box, width, height)
        inside = np.bincount(labels[top:bottom, left:right].ravel(),
                             minlength=count)
        partial = np.nonzero((inside > 0) & (inside < areas))[0]
        cut.update(int(label) for label in partial if label != 0)
    return len(cut)


def _gaps_down(mask: ImageArray) -> list[int]:
    """Heights of the blank bands between the first and last inked row."""
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size < 2:
        return []

    steps = np.diff(rows)
    return [int(step) - 1 for step in steps if step > 1]


def _double_count(mask: ImageArray, boxes: Sequence[BBox]) -> int:
    """Boxes whose contents are parted by far more whitespace than their leading.

    Measured **down the page only**. Ink separated horizontally is what a
    two-column Band is, so counting it would report a double on every correct
    multi-column layout in the corpus.

    A box with a single blank band cannot supply its own leading — the one gap is
    also the median, so the ratio is 1.0 and nothing can ever fire. That is
    exactly the shape this field exists to catch, a box holding two masses and
    nothing else, so those fall back to the leading of the page's other boxes.
    Without the fallback the most literal reading of "two ink masses" is the one
    case the measurement is structurally blind to.
    """
    height, width = mask.shape[:2]
    per_box = [
        _gaps_down(mask[top:bottom, left:right])
        for left, top, right, bottom in
        (_pixel_rect(box, width, height) for box in boxes)
    ]

    # Pooled from the boxes rather than from the whole page, because a page-wide
    # profile counts the wide bands *between* Zones as if they were leading and
    # comes out around twice as large.
    elsewhere = [gap for gaps in per_box if len(gaps) >= 2 for gap in gaps]
    fallback = statistics.median(elsewhere) if elsewhere else None

    found = 0
    for gaps in per_box:
        leading = statistics.median(gaps) if len(gaps) >= 2 else fallback
        if not gaps or leading is None:
            continue
        if max(gaps) > DOUBLE_GAP_FACTOR * leading:
            found += 1
    return found


def score_geometry(got: Sequence[BBox], want: Sequence[BBox], image: ImageArray,
                   *, valid: bool | None = None) -> GeometryScore:
    """Score one method's boxes against the reference **and against the ink**.

    The reference rectangles were typed by hand, so the three ink-aware fields
    are the only ones here that do not inherit the fixture's slop: `covered`,
    `splits` and `doubles` ask the page, not the person who eyeballed it.
    """
    mask = content_ink(image)
    return GeometryScore(
        zones=len(got),
        iou=mean_best_iou(got, want),
        covered=_covered_share(mask, got),
        splits=_split_count(mask, got),
        doubles=_double_count(mask, got),
        valid=valid,
    )


@dataclass(frozen=True)
class ExpectedZone:
    """One Zone of a reference IR, and the rectangle it says that Zone occupies.

    `box` is `None` when the reference IR gives that Zone no rectangle. Such a
    Zone cannot be scored, but it is still reported rather than dropped here: a
    loader that dropped it silently would renumber every Zone after it, and a
    report saying "want 3" about the reference's Zone 4 is worse than no report.
    Deciding what to do about it belongs to the caller.
    """

    index: int
    box: BBox | None
    kind: str
    role: str
    band: int | None = None
    column: int | None = None


def expected_zones(path: Path) -> list[ExpectedZone]:
    """Every Zone of an expected IR, in the order it wrote them.

    The rectangles in every fixture were typed by hand — both builders say they
    are "eyeballed to roughly the right place" — so this is a ruler with unknown
    slop, and spec 0004's Stage 0 exists to measure how much. Nothing here
    pretends otherwise; it only reads what is written.
    """
    data: dict[str, Any] = json.loads(path.read_text())
    found = []
    for index, zone in enumerate(data["zones"]):
        bbox = zone.get("bbox")
        found.append(
            ExpectedZone(
                index=index,
                box=(
                    None if bbox is None
                    else BBox(bbox["left"], bbox["top"],
                              bbox["right"], bbox["bottom"])
                ),
                kind=zone.get("kind", "?"),
                role=zone.get("role", "?"),
                band=zone.get("band"),
                column=zone.get("column"),
            )
        )
    return found


def expected_boxes(path: Path) -> list[BBox]:
    """Just the rectangles, for a caller that scores geometry and nothing else.

    Raises rather than returning a short list when a Zone has no rectangle. A
    probe that quietly scored six boxes against five references would report a
    mean that looks perfectly reasonable and is measured against the wrong page —
    the one failure mode these numbers cannot afford, because nothing downstream
    could tell it from a real result. A caller that wants to tolerate the gap can
    read `expected_zones` and decide for itself, which is what a tool drawing
    pictures of a run does.
    """
    zones = expected_zones(path)
    missing = [zone.index for zone in zones if zone.box is None]
    if missing:
        raise ValueError(
            f"{path.name} gives no bbox to Zone(s) "
            f"{', '.join(str(i) for i in missing)}, so geometry cannot be scored "
            f"against it"
        )
    return [zone.box for zone in zones if zone.box is not None]
