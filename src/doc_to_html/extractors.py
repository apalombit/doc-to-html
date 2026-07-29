"""Extractors: one per structural Kind, and no more.

An Extractor turns one Zone into part of the IR. It has no autonomy — it does not
decide whether its own output is good enough, does not retry, and does not choose
an Engine. All of that lives in the Orchestrator, so there is exactly one place
that knows about Escalation rather than five that each think they're clever.

There is one Extractor per Kind and never one per document type: an invoice's
line items and an inventory's stock list are both TABLE. See docs/adr/0001.
"""

from __future__ import annotations

from typing import Protocol

from .engines.base import VisionEngine
from .ir import Kind, Zone
# `zone_pixels` and its `NoGeometry` live in `preprocess` now, beside the `crop`
# they use, so the classification pass can cut a Zone out with the same padding
# an Extractor does without importing the Extractors.
from .preprocess import (
    MODEL_INPUT_LONG_EDGE,
    ImageArray,
    over_input_budget,
    slice_points,
    zone_pixels,
)


class Extractor(Protocol):
    kind: Kind

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone: ...


def resolution_caveat(image: ImageArray, zone: Zone) -> str | None:
    """Whether this Zone had to be read below the resolution it deserved.

    Slice stitching is not built, so a Zone taller than the model's input budget
    is read whole at reduced resolution rather than in overlapping strips. That
    can drop rows. Returning a degraded reading as though it were an ordinary one
    is the failure mode worth preventing, so the caveat is recorded and shown.

    The test is on *height* specifically, because that is what slicing addresses:
    slices are horizontal bands. A Zone that is merely wider than the budget
    loses a few percent of scale and no rows, and flagging that would bury a real
    finding in noise — every full-width Zone of a 1200px page would carry one.
    """
    height = over_input_budget(image, zone)
    if height is None:
        return None
    slices = len(slice_points(height, budget=MODEL_INPUT_LONG_EDGE))
    return (
        f"read at reduced resolution: {height}px tall is over the model's "
        f"{MODEL_INPUT_LONG_EDGE}px input budget and would need {slices} "
        "overlapping slices, which are planned but not yet stitched"
    )


class CropAndRead:
    """Cut the Zone out of the Rectified Image, hand it to the Engine.

    Every Extractor's body, because the difference between Kinds is which
    question gets asked and not how the pixels are obtained — and the question
    belongs to the Engine, which owns the prompts. What varies per Kind is any
    *decomposition* it needs, which is why `TableExtractor` has more here than
    the others and nobody else has any.

    An Extractor never chooses an Engine and never retries. If one starts
    deciding a result was poor and having another go, it has crossed into the
    Orchestrator's job and there are now two places that know about Escalation.
    """

    kind: Kind

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        return engine.extract_zone(zone_pixels(image, zone), zone, hint)


class TableExtractor(CropAndRead):
    """Reads a grid, tagging each row header / data / summary.

    Row roles are what keep a summary row out of a column sum. They exist only
    here: a Zone of any other Kind has no rows and never carries them.

    A Zone too tall to read at the model's input resolution is sliced with an
    overlap and stitched by matching the repeated rows across the seam.
    """

    kind = Kind.TABLE

    @staticmethod
    def plan_slices(crop_height: int) -> list[tuple[int, int]]:
        return slice_points(crop_height, budget=MODEL_INPUT_LONG_EDGE)

    @staticmethod
    def stitch(slices: list[Zone]) -> Zone:
        """Join slice results, matching the overlapping rows.

        Rows that agree across a seam are merged and de-duplicated. Rows that
        disagree are the finding: they become disputed and enter the Ladder,
        which makes the overlap a free consistency check rather than pure cost.
        """
        raise NotImplementedError("slice stitching not yet wired")


class PairsExtractor(CropAndRead):
    """Reads label -> value bindings. A totals block is this Kind with Role SUMMARY."""

    kind = Kind.PAIRS


class ProseExtractor(CropAndRead):
    """Reads headings, paragraphs and addresses. The whole of a doctor's note."""

    kind = Kind.PROSE


class ListExtractor(CropAndRead):
    kind = Kind.LIST


class FigureExtractor(CropAndRead):
    """Records a Graphic's position without reconstructing it.

    Text *written on* a graphic is document content and is captured: a chart's
    title and axis labels, a PAID stamp, a signature's presence. What is never
    attempted is inferring a chart's data from the geometry of its bars.
    """

    kind = Kind.FIGURE


REGISTRY: dict[Kind, Extractor] = {
    extractor.kind: extractor
    for extractor in (
        TableExtractor(),
        PairsExtractor(),
        ProseExtractor(),
        ListExtractor(),
        FigureExtractor(),
    )
}


def for_kind(kind: Kind) -> Extractor:
    return REGISTRY[kind]
