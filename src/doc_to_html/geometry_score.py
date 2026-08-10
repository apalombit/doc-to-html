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

from .ir import BBox


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
