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
from .preprocess import MODEL_INPUT_LONG_EDGE, ImageArray, crop, slice_points


class Extractor(Protocol):
    kind: Kind

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone: ...


class NoGeometry(ValueError):
    """A Zone with no bounding box cannot be cropped, so it cannot be read."""


def zone_pixels(image: ImageArray, zone: Zone) -> ImageArray:
    """This Zone's own pixels, at the resolution the Rectified Image has them.

    Every Extractor starts here. The layout pass looked at a downscaled page
    because finding regions is coarse work; reading one is not, and this is where
    the resolution that bought is spent.
    """
    if zone.bbox is None:
        raise NoGeometry(
            f"{zone.kind.value} Zone in band {zone.band} has no bounding box"
        )
    return crop(image, zone.bbox)


def resolution_caveat(image: ImageArray, zone: Zone) -> str | None:
    """Whether this Zone had to be read below the resolution it deserved.

    Slice stitching is not built, so a Zone taller than the model's input budget
    is read whole at reduced resolution rather than in overlapping strips. That
    can drop rows. Returning a degraded reading as though it were an ordinary one
    is the failure mode worth preventing, so the caveat is recorded and shown.
    """
    if zone.bbox is None:
        return None
    height, width = zone_pixels(image, zone).shape[:2]
    longest = max(height, width)
    if longest <= MODEL_INPUT_LONG_EDGE:
        return None
    slices = len(slice_points(longest, budget=MODEL_INPUT_LONG_EDGE))
    return (
        f"read at reduced resolution: {longest}px is over the model's "
        f"{MODEL_INPUT_LONG_EDGE}px input budget and would need {slices} "
        "overlapping slices, which are planned but not yet stitched"
    )


class TableExtractor:
    """Reads a grid, tagging each row header / data / summary.

    Row roles are what keep a summary row out of a column sum. They exist only
    here: a Zone of any other Kind has no rows and never carries them.

    A Zone too tall to read at the model's input resolution is sliced with an
    overlap and stitched by matching the repeated rows across the seam.
    """

    kind = Kind.TABLE

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        return engine.extract_zone(zone_pixels(image, zone), zone, hint)

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


class PairsExtractor:
    """Reads label -> value bindings. A totals block is this Kind with Role SUMMARY."""

    kind = Kind.PAIRS

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        raise NotImplementedError("pairs extraction not yet wired")


class ProseExtractor:
    """Reads headings, paragraphs and addresses. The whole of a doctor's note."""

    kind = Kind.PROSE

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        raise NotImplementedError("prose extraction not yet wired")


class ListExtractor:
    kind = Kind.LIST

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        raise NotImplementedError("list extraction not yet wired")


class FigureExtractor:
    """Records a Graphic's position without reconstructing it.

    Text *written on* a graphic is document content and is captured: a chart's
    title and axis labels, a PAID stamp, a signature's presence. What is never
    attempted is inferring a chart's data from the geometry of its bars.
    """

    kind = Kind.FIGURE

    def extract(self, image: ImageArray, zone: Zone, engine: VisionEngine,
                hint: str | None = None) -> Zone:
        raise NotImplementedError("figure handling not yet wired")


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
