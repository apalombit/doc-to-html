"""Engines: sources of readings from pixels.

An Engine is interchangeable behind an Extractor. Which one runs on a given Zone
is the Orchestrator's routing decision, not the Extractor's — and the same
Orchestrator batches work by model, because two vision models resident at once
does not fit in 8GB and alternating between them costs a reload each time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir import BBox, Reading, Zone


@runtime_checkable
class VisionEngine(Protocol):
    """A vision model reached through Ollama, local or hosted."""

    name: str
    model: str

    def detect_zones(self, image: object, hint: str | None = None) -> list[Zone]:
        """Zones with Band, column, Kind, Role and bbox — no contents.

        Run on a downscaled page: a coarse task that small models handle well.
        """
        ...

    def extract_zone(self, image: object, zone: Zone, hint: str | None = None) -> Zone:
        """Fill in a Zone's contents from a full-resolution crop of it."""
        ...

    def read_cell(self, image: object, bbox: BBox, hint: str | None = None) -> Reading:
        """Re-read one cell from an upscaled crop. A rung on the Ladder."""
        ...

    def audit_coverage(self, image: object, zones: list[Zone]) -> list[BBox]:
        """Regions carrying content that no Zone covers.

        Run by a *different model family* from the one that produced the layout.
        Asking the model that missed a block whether it missed a block shares the
        blind spot that caused the miss.
        """
        ...


@runtime_checkable
class BoxEngine(Protocol):
    """Something that reports where text is, without a vision model.

    Whether this earns a place at all is deliberately unsettled — it is an
    empirical question the first end-to-end slice answers, since that slice runs
    vision-only and is therefore the control condition.
    """

    name: str

    def word_boxes(self, image: object) -> list[tuple[BBox, str]]: ...
