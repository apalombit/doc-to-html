"""Engines: sources of readings from pixels.

An Engine is interchangeable behind an Extractor. Which one runs on a given Zone
is the Orchestrator's routing decision, not the Extractor's — and the same
Orchestrator batches work by model, because two vision models resident at once
does not fit in 8GB and alternating between them costs a reload each time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir import BBox, Reading, Zone
from ..preprocess import ImageArray, TableGrid


@runtime_checkable
class LayoutEngine(Protocol):
    """Whatever finds the Zones. Separate from `VisionEngine` on purpose.

    The layout pass has been reduced to a box detector and this Protocol is
    where that becomes visible in the types. It reports rectangles; the `Kind` it
    also carries is discarded, because `_classify` overwrites every one from the
    Zone's own crop moments later.

    Filled by `engines.detector.LayoutEngine` — a trained ONNX detector with no
    prompt, no model call and no other pass to offer — in every Conversion, and
    by the recorded-response suite's `FixedLayout`. `OllamaEngine` used to
    satisfy it too, through a vision layout prompt that spec 0007's queue
    deleted in Q4.
    """

    name: str
    model: str

    def detect_zones(self, image: ImageArray,
                     hint: str | None = None) -> list[Zone]:
        """Zones with Band, column, Role and bbox — no contents."""
        ...


@runtime_checkable
class VisionEngine(Protocol):
    """A vision model reached through Ollama, local or hosted."""

    name: str
    model: str

    def read_caption(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        """Fill in one Zone's Title from its own crop, or leave it unset.

        Its own pass because it wants the opposite pixels from `classify_zone`:
        the Title needs the caption band in frame, and the Kind is measurably
        wrong while that band is visible. One call cannot show both.
        """
        ...

    def read_runs(self, image: ImageArray, zone: Zone,
                  hint: str | None = None) -> Zone:
        """Mark which spans of one Zone are set apart — links, code, emphasis.

        Its own pass because asking for this inside the Extractor prompts was
        measured and it cost content: see `config.DEFAULT_INLINE_PASS`. Asking
        separately leaves every extraction answer untouched, so an Engine that
        cannot do it may return the Zone unchanged and lose only the marking.
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

        Separate from finding the Zones because the two answer different
        questions about different pixels, and measurably so — see
        `CLASSIFY_PROMPT` and issue #13. Separate from `extract_zone` because the Kind this returns is
        what routes the Zone to an Extractor in the first place.
        """
        ...

    def extract_zone(self, image: ImageArray, zone: Zone,
                     hint: str | None = None, grid: TableGrid | None = None) -> Zone:
        """Fill in a Zone's contents from a full-resolution crop of it.
        `grid` is a table's grid as the caller measured it, with what the
        page draws known — spec 0012, G3b; None measures the crop alone."""
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
