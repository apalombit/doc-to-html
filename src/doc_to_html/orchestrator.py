"""Sequences Extractors, routes Engines, owns every retry decision.

Retry logic lives here and nowhere else. An Extractor never decides to have
another go; a Probe never triggers its own re-read. One place knows about
Escalation, which is the difference between a system you can debug and one you
cannot.

A Conversion is a session rather than a function call, because a human may be
consulted partway through. Unattended callers pass NullHandler and get exactly
one round.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import probes as probe_module
from .checkpoints import Answer, CheckpointHandler, NullHandler, Question
from .config import Settings, load
from .engines.base import VisionEngine
from .engines.ollama import OllamaEngine
from .extractors import for_kind
from .ir import Document, Failure
from .preprocess import Rectified, rectify
from .render import render

MAX_ROUNDS = 5
"""A backstop, not a control.

Termination comes from every unresolved item exhausting its Ladder. If this cap
ever fires, a Rung is being retried when it should not be — that is a defect
report, not a normal outcome.
"""


class Rung(str, Enum):
    """One step on a Ladder, each tried at most once per item.

    Ordered by cost. Because nothing is ever retried identically, a Conversion
    terminates by exhausting Ladders rather than by counting rounds.
    """

    READ = "read"
    """Normal read, at the resolution the Extractor chose."""

    UPSCALE = "upscale"
    """Re-crop from the Rectified Image at full resolution and enlarge."""

    OTHER_ENGINE = "other-engine"
    """Put it to a different model family."""

    ASK_HUMAN = "ask-human"
    """Last resort, and only where a CheckpointHandler is present."""


@dataclass
class EngineSet:
    """Which model does what.

    Layout and audit default to different families so the auditor does not share
    the blind spot that caused a miss. The Orchestrator batches by model: all
    layout and extraction work finishes before the auditor loads, because two
    vision models resident at once does not fit in 8GB.
    """

    layout: VisionEngine
    extract: VisionEngine
    audit: VisionEngine


def default_engines(settings: Settings | None = None) -> EngineSet:
    """The Engines the resolved configuration asks for.

    Which model fills which role is configuration, not code — that is what lets
    a bake-off across models, or a move to Ollama Cloud, happen without an edit
    here. See `config` and `.env.example`.
    """
    resolved = settings or load()

    def engine(model: str) -> OllamaEngine:
        return OllamaEngine(
            model=model,
            host=resolved.ollama_host,
            api_key=resolved.ollama_api_key,
            num_ctx=resolved.num_ctx,
            timeout_s=resolved.timeout_s,
        )

    return EngineSet(
        layout=engine(resolved.layout_model),
        extract=engine(resolved.extract_model),
        audit=engine(resolved.audit_model),
    )


@dataclass
class Conversion:
    """One run over one Source Image.

    Multi-page is deliberately out of scope: a Conversion is strictly one image.
    Admitting page 2 later means growing the IR a `pages` array and revising
    every fixture — a known, accepted cost rather than an oversight.
    """

    source: Path
    engines: EngineSet = field(default_factory=default_engines)
    handler: CheckpointHandler = field(default_factory=NullHandler)
    document: Document | None = None

    def run(self) -> Document:
        """Rectify, lay out, extract, probe, audit, refine until Ladders run dry."""
        rectified = rectify(self.source)
        hint = self._ask_opening()

        document = Document(source=rectified.source, hint=hint)
        self.document = document

        for _ in range(MAX_ROUNDS):
            self._layout(rectified, document)
            self._extract(rectified, document)

            document.probes = probe_module.run(document)
            self._audit(rectified, document)
            self._climb_ladders(rectified, document)

            answer = self._ask_convergence(document)
            if answer.is_empty:
                # Nothing new entered the system. Re-running identical passes
                # over identical pixels would reproduce the Draft as it stands.
                break
            self._apply(answer, document)
        else:
            raise RuntimeError(
                "round cap reached: a Rung is being retried. See MAX_ROUNDS."
            )

        return document

    def _ask_opening(self) -> str | None:
        """Collect a Hint: prose for prompts that branches no code path.

        If an answer here ever starts selecting an Extractor or a template, ADR
        0001 has been reversed by accident.
        """
        answer = self.handler.ask(
            Question(
                kind="opening",
                text="Anything I should know about this document?",
            )
        )
        return answer.note or None

    def _layout(self, rectified: Rectified, document: Document) -> None:
        """Detect Zones — Band, column, Kind, Role, bbox — on a downscaled page.

        Run once per Conversion, not once per round. A later round refines what
        is *in* the Zones; re-detecting them would discard everything extracted
        so far in exchange for a near-identical answer from a near-deterministic
        model.
        """
        if document.zones:
            return
        document.zones = self.engines.layout.detect_zones(
            rectified.image, document.hint
        )

    def _extract(self, rectified: Rectified, document: Document) -> None:
        """Fill each incomplete Zone from a full-resolution crop of it.

        Partial output is the useful output. A Zone that cannot be read is
        recorded as a Failure and left incomplete — it renders as a skeleton,
        which is unmistakably "this did not work" in a way that silently absent
        content is not — and the remaining Zones are still extracted.
        """
        document.failures = []
        for index, zone in enumerate(document.zones):
            if zone.complete:
                continue
            try:
                for_kind(zone.kind).extract(
                    rectified.image, zone, self.engines.extract, document.hint
                )
            except Exception as error:
                document.failures.append(
                    Failure(
                        zone_index=index,
                        kind=zone.kind.value,
                        reason=f"{type(error).__name__}: {error}",
                    )
                )

    def _audit(self, rectified: Rectified, document: Document) -> None:
        """Find content no Zone covers.

        Every other safeguard catches content that is *wrong*. This is the only
        one that catches content that is *absent* — a failure which otherwise
        leaves the IR internally consistent and every Probe passing.

        Not run yet, and deliberately not faked: an audit is only worth anything
        from a *different model family*, because asking the model that missed a
        block whether it missed a block shares the blind spot that caused the
        miss. Until a second family is wired, content the layout pass never saw
        goes unnoticed. That is the known blind spot of the vision-only slice and
        the strongest argument for building this next.
        """
        return

    def _climb_ladders(self, rectified: Rectified, document: Document) -> None:
        """Advance every unresolved item one Rung.

        Probe findings are used here to decide *which* cells to look at again,
        at what resolution, with which Engine. Their expected values never reach
        a prompt: a failed Probe cannot distinguish a misread line item from a
        misread total, so supplying the expected value would force agreement
        with whichever number happened to be wrong. See docs/adr/0004.

        Nothing to climb yet. Only one Engine reads each cell in this slice, so
        no two readings can disagree, so no cell is ever Disputed. Escalation
        arrives with a second Engine and not before.
        """
        _implicated = probe_module.implicated_zones(document.probes)
        return

    def _ask_convergence(self, document: Document) -> Answer:
        """Show a Draft beside the Source Image and ask whether it is converging."""
        return self.handler.ask(
            Question(
                kind="convergence",
                text="Does this match the document?",
                options=["looks right", "keep refining"],
                draft_html=render(document),
            )
        )

    def _apply(self, answer: Answer, document: Document) -> None:
        """Fold a structured answer into the IR; carry a note into the next prompt.

        A note is appended to the Hint rather than interpreted. That is the whole
        of it for now: interpreting prose is a later milestone, and when it
        arrives its job is to map prose onto the structured `choice` values, not
        to edit the IR.
        """
        if answer.note:
            document.hint = (
                f"{document.hint}\n{answer.note}" if document.hint else answer.note
            )


def convert(source: Path | str, *, handler: CheckpointHandler | None = None,
            engines: EngineSet | None = None) -> Document:
    """Convert one Source Image. The library entry point.

    The CLI, the eval harness and any future UI all come through here, so what
    gets measured is what ships.
    """
    conversion = Conversion(
        source=Path(source),
        engines=engines or default_engines(),
        handler=handler or NullHandler(),
    )
    return conversion.run()
