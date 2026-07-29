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
from .extractors import for_kind, resolution_caveat
from .ir import Caveat, Document, Failure, Zone
from .preprocess import (
    MODEL_INPUT_LONG_EDGE,
    ImageArray,
    Rectified,
    long_edge_over_input_budget,
    rectify,
)
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
    the blind spot that caused a miss. Classification is a role of its own so a
    model that locates blocks well and one that reads them well need not be the
    same — though today they are, and `config.DEFAULT_CLASSIFY_MODEL` records
    what that costs and why it is still the right default.

    The Orchestrator batches by model, which is what keeps a mixed set
    affordable: every classification runs together, between all the layout work
    and all the extraction work, so pointing this role at a second model costs
    two model loads for the document rather than one per Zone. Two vision models
    resident at once does not fit in 8GB.
    """

    layout: VisionEngine
    classify: VisionEngine
    extract: VisionEngine
    audit: VisionEngine


def default_engines(settings: Settings | None = None) -> EngineSet:
    """The Engines the resolved configuration asks for.

    Which model fills which role is configuration, not code — that is what lets
    a bake-off across models, or a move to Ollama Cloud, happen without an edit
    here. See `config` and `.env.example`.
    """
    resolved = settings or load()
    return EngineSet(
        layout=OllamaEngine.from_settings(resolved, resolved.layout_model),
        classify=OllamaEngine.from_settings(resolved, resolved.classify_model),
        extract=OllamaEngine.from_settings(resolved, resolved.extract_model),
        audit=OllamaEngine.from_settings(resolved, resolved.audit_model),
    )


def failed(index: int, zone: Zone, error: Exception) -> Failure:
    """Record what went wrong on one Zone, in the form both passes report.

    Classification and extraction fail differently but report identically, and
    that is the contract rather than a coincidence: an operator reading the
    render should not have to know which pass gave up on a Zone to find out that
    one did. Naming the exception type matters — `MappingError` and
    `TruncatedResponse` are different problems with different fixes.
    """
    return Failure(
        zone_index=index,
        kind=zone.kind.value,
        reason=f"{type(error).__name__}: {error}",
    )


def classification_caveat(image: ImageArray, zone: Zone) -> str | None:
    """Whether this Zone's Kind was decided below the resolution it deserved.

    The counterpart of `resolution_caveat`, over the same pixels — but a
    different loss, and therefore a different test. Extraction shrunk past the
    budget can drop rows, so it measures height. A Kind decided on a shrunk crop
    loses the evidence that separates two Kinds — a shaded heading row over a
    data row, against two label/value lines, is a distinction made of a few
    pixels of grey — and that goes just as readily to a horizontal shrink, so
    this measures the long edge. See `long_edge_over_input_budget`: sharing
    extraction's height test here would say nothing about the full-width Zone,
    which is the commonest shape in the project.

    The Zone keeps the Kind either way. A degraded reading beats none, and a
    Zone with no Kind has no Extractor to route it to — so this is a note on an
    answer, not a rejection of one.

    Here rather than beside `resolution_caveat` in `extractors.py` because this
    is not an Extractor's business: the classification pass has no Extractor,
    and each caveat sits with the pass that earns it.
    """
    longest = long_edge_over_input_budget(image, zone)
    if longest is None:
        return None
    return (
        f"classified at reduced resolution: the crop's {longest}px long edge is "
        f"over the model's {MODEL_INPUT_LONG_EDGE}px input budget, so the Kind "
        "was decided on a shrunk crop"
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

    classification_ran: bool = field(init=False, default=False)
    """Whether the classification pass has happened yet. See `_classify`.

    A flag rather than something derived from the Zones, which is how `_layout`
    knows: a Zone carries no mark saying whether it was classified, and the Kind
    it holds cannot say either, since a Zone that failed classification keeps
    whatever Kind it arrived with.

    `init=False` on this and the three below: they are bookkeeping the passes
    write as they go, not something a caller configures.
    """

    unclassified: set[int] = field(init=False, default_factory=set)
    """Zones whose classification call raised, by index.

    Their Kind is unknown, so extraction has no question to ask about them and
    skips them. Held here rather than derived from `document.failures` because
    `_extract` rebuilds that list every round.
    """

    classification_failures: list[Failure] = field(init=False, default_factory=list)
    """Failures classification recorded, kept across rounds.

    Classification runs once and extraction runs every round, so `_extract`
    clearing the Document's Failures would erase these on round two. Keeping
    them here makes classification the owner of its own findings and `_extract`
    merely the thing that puts them back.
    """

    classification_caveats: list[Caveat] = field(init=False, default_factory=list)
    """Caveats classification recorded, kept across rounds. See above.

    Two lists rather than one of `Failure | Caveat`: they are put back into two
    separate fields of the Document, so one list would only be sorted back out
    by type at the other end.
    """

    def run(self) -> Document:
        """Rectify, lay out, classify, extract, probe, audit, refine."""
        rectified = rectify(self.source)
        hint = self._ask_opening()

        document = Document(source=rectified.source, hint=hint)
        self.document = document

        for _ in range(MAX_ROUNDS):
            self._layout(rectified, document)
            self._classify(rectified, document)
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
        """Detect Zones — Band, column, Role, bbox — on a downscaled page.

        It still returns a Kind as well, and that Kind is not used: `_classify`
        overwrites every one of them from the Zone's own crop moments later.
        Deleting it from the prompt and the wire schema is issue #17; until then
        the geometry pass is still paying tokens to guess something discarded.

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

    def _classify(self, rectified: Rectified, document: Document) -> None:
        """Decide each Zone's Kind from that Zone's own crop.

        A pass of its own, between geometry and extraction, because the two
        questions want different pixels: where a block is, is coarse work on a
        downscaled page, while what a block *is* can turn on a shaded heading row
        that the downscale removes. Issue #13 measured both halves — a Zone asked
        about on its own is classified correctly at a resolution where the same
        Zone asked about as one of seven is not, and a Zone needing glyphs needs
        the crop *and* a model able to use it. Hence a separate pass and a
        separate model.

        Once per Conversion, for the same reason `_layout` is: the Kind of a
        block does not change between rounds, and re-asking would spend a call
        per Zone to be told again what the same pixels are.

        A Zone whose call raises is a Failure on that Zone alone, following the
        contract extraction already keeps — one bad crop does not cost the
        document. It is then left out of extraction: with no Kind there is no
        question to ask about it, and asking anyway would route it on geometry's
        guess, which is the guess this pass exists to stop trusting.
        """
        if self.classification_ran:
            return
        self.classification_ran = True

        for index, zone in enumerate(document.zones):
            try:
                document.zones[index] = self.engines.classify.classify_zone(
                    rectified.image, zone, document.hint
                )
            except Exception as error:
                # The Kind recorded here is the one geometry guessed, which this
                # pass exists to distrust — but it is the only one there is, and
                # a Failure saying nothing about what it failed on is worse than
                # one saying "the thing geometry took for a table". #17 removes
                # geometry's guess, and then this becomes the Kind's default.
                self.unclassified.add(index)
                self.classification_failures.append(failed(index, zone, error))
                continue

            classified = document.zones[index]
            note = classification_caveat(rectified.image, classified)
            if note is not None:
                self.classification_caveats.append(
                    Caveat(zone_index=index, kind=classified.kind.value, note=note)
                )

    def _extract(self, rectified: Rectified, document: Document) -> None:
        """Fill each incomplete Zone from a full-resolution crop of it.

        Partial output is the useful output. A Zone that cannot be read is
        recorded as a Failure and left incomplete — it renders as a skeleton,
        which is unmistakably "this did not work" in a way that silently absent
        content is not — and the remaining Zones are still extracted.

        A Zone that *was* read but only at reduced resolution gets a Caveat
        instead, which is a different thing and not a milder Failure: it keeps its
        content, because degraded content beats none, and calling it a failure
        would have the render say a Zone could not be read directly above the
        content it read.

        The lists are rebuilt each round rather than appended to, so a Zone read
        successfully on round two does not keep round one's Failure. What
        classification found is seeded back in, because that pass ran once and
        its findings are as true on round two as they were on round one.
        """
        document.failures = list(self.classification_failures)
        document.caveats = list(self.classification_caveats)
        for index, zone in enumerate(document.zones):
            if zone.complete or index in self.unclassified:
                continue
            try:
                for_kind(zone.kind).extract(
                    rectified.image, zone, self.engines.extract, document.hint
                )
            except Exception as error:
                document.failures.append(failed(index, zone, error))
                continue

            note = resolution_caveat(rectified.image, zone)
            if note is not None:
                document.caveats.append(
                    Caveat(zone_index=index, kind=zone.kind.value, note=note)
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
