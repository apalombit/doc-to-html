"""Engines: sources of readings from pixels.

An Engine is interchangeable behind an Extractor. Which one runs on a given Zone
is the Orchestrator's routing decision, not the Extractor's — and the same
Orchestrator batches work by model, because two vision models resident at once
does not fit in 8GB and alternating between them costs a reload each time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir import BBox, Reading, Zone
from ..preprocess import ImageArray


@runtime_checkable
class LayoutEngine(Protocol):
    """Whatever finds the Zones. Narrower than `VisionEngine` on purpose.

    The layout pass has been reduced to a box detector and this Protocol is
    where that becomes visible in the types. It reports rectangles; the `Kind` it
    also carries is discarded, because `_classify` overwrites every one from the
    Zone's own crop moments later.

    Split out so `engines.detector.LayoutEngine` — a trained ONNX detector with
    no prompt, no model call and no other pass to offer — can fill the role
    without pretending to `classify_zone` or `read_cell`. `OllamaEngine`
    satisfies this structurally, so nothing that already worked moved.
    """

    name: str
    model: str

    def detect_zones(self, image: ImageArray, hint: str | None = None,
                     region_ceiling: int | None = None) -> list[Zone]:
        """Zones with Band, column, Role and bbox — no contents."""
        ...


@runtime_checkable
class VisionEngine(Protocol):
    """A vision model reached through Ollama, local or hosted."""

    name: str
    model: str

    def detect_zones(self, image: ImageArray, hint: str | None = None,
                     region_ceiling: int | None = None) -> list[Zone]:
        """Zones with Band, column, Kind, Role and bbox — no contents.

        Run on a downscaled page: a coarse task that small models handle well.

        `region_ceiling` is an upper bound on how many regions the page holds,
        measured from the ink by the caller rather than asked of a model. `None`
        means unmeasured, and an Engine that has no use for it may ignore it.
        """
        ...

    def read_caption(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        """Fill in one Zone's Title from its own crop, or leave it unset.

        Its own pass because it wants the opposite pixels from `classify_zone`:
        the Title needs the caption band in frame, and the Kind is measurably
        wrong while that band is visible. One call cannot show both.
        """
        ...

    def classify_zone(self, image: ImageArray, zone: Zone,
                      hint: str | None = None, *, skip_rows: int = 0) -> Zone:
        """Decide one Zone's Kind, and the fields that depend on reading it.

        `skip_rows` drops the leading crop rows a caption occupies, when one has
        already been read off them. See `ollama.OllamaEngine.classify_zone`.

        **Takes the whole Rectified Image and crops the Zone out itself** — the
        opposite way round from `extract_zone`, which is handed a crop an
        Extractor already cut. The asymmetry is deliberate: an Extractor owns
        decomposition because a table may need slicing, while classification
        always wants exactly the Zone, so putting the cut here keeps it identical
        to the one the Extractor makes later. A classifier judging a
        differently-padded image could name a Kind for one picture while the
        Extractor reads another.

        Separate from `detect_zones` because the two answer different questions
        about different pixels, and measurably so — see `CLASSIFY_PROMPT` and
        issue #13. Separate from `extract_zone` because the Kind this returns is
        what routes the Zone to an Extractor in the first place.
        """
        ...

    def extract_zone(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        """Fill in a Zone's contents from a full-resolution crop of it."""
        ...

    def read_cell(self, image: ImageArray, bbox: BBox,
                  hint: str | None = None) -> Reading:
        """Re-read one cell from an upscaled crop. A rung on the Ladder."""
        ...

    def audit_coverage(self, image: ImageArray, zones: list[Zone]) -> list[BBox]:
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

    def word_boxes(self, image: ImageArray) -> list[tuple[BBox, str]]: ...
