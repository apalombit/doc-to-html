"""What a Conversion did, step by step, so a run can explain itself.

Diagnostics, not IR. Nothing here reaches the rendered document, and — the
property everything else rests on — **nothing in the pipeline ever reads a Trace
back**. The Orchestrator appends to it and no branch anywhere asks it a question,
so an Event that is wrong, or missing, still leaves a byte-identical Document.
The Trace cannot steer a Conversion.

**Why this exists.** `debug/runs/<label>/index.html` is the project's primary
diagnostic, and it had fallen a long way behind the pipeline. On run 46 — a
conversion of fourteen model calls — the sheet showed one prompt and six answers,
and those six were the *classification* verdicts rather than the content, under a
heading reading "What each crop returned". Every extraction answer was absent.

The cause was not the tool. The dump wrote `NN_<pass>.json` in call order and
nothing more, so which Zone a call belonged to had to be guessed from position,
and the guess broke the moment #15 put a classify call in front of every Zone.
`zones_used.json` already exists for the same class of mistake — run 39 converted
on snapped geometry while its contact sheet drew the raw layout answer — and the
lesson it carries applies here unchanged: *a tool reading a run cannot be expected
to know what the Orchestrator did; the run has to say.*

**Data, never sentences.** An Event holds primitives — a Kind before and after, a
count, `str(exc)` — and every human-readable phrase in the contact sheet is
composed by `tools/inspect_run.py` when it reads the trace back. That is a safety
property rather than a matter of taste: appending to a list cannot fail, but
building the string you append can, and an f-string meeting an unexpected `None`
inside `_extract` would abort a real conversion in order to serve a diagnostic.
Plain field assignment has no such failure mode.

The test every field is chosen against: **could someone troubleshoot this step
from the trace alone, without re-running anything?** Where a step consumed pixels,
the Event says which pixels; where it judged, it says against what threshold;
where it changed the Document, it says what it changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

TRACE_VERSION = 1
"""Bumped when a reader could misinterpret an older trace.

`inspect_run.py` routes anything it does not recognise to the fallback path,
which reconstructs what it can and says so, rather than half-rendering a shape it
half-understands.
"""


class Stage(str, Enum):
    """The pipeline stages, in the order a Conversion runs them.

    Declaration order is the display order, so the sheet's numbering comes from
    here rather than from a second list that could disagree with it.
    """

    RECTIFY = "rectify"
    LAYOUT = "layout"
    SNAP = "snap"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    PROBE = "probe"
    AUDIT = "audit"
    RENDER = "render"


class Disposition(str, Enum):
    """What was done with a step's input. Required on every Event.

    A closed set, because the sheet renders it as one fixed line and a free-text
    field would drift into prose that says nothing. Required rather than optional
    because an Event that cannot say what became of its input is precisely the
    gap this module exists to close — three separate investigations in this
    project ended at "the model answered correctly and the content vanished", and
    each one was a disposition nobody had written down.
    """

    ACCEPTED = "accepted"
    """The answer went into the Document unchanged."""

    REPAIRED = "repaired"
    """Changed on the way in, and `data` names the repair and its before/after.

    The split-header join and the empty-row drop both live here. Both are
    deliberate and both are invisible in the answer they produce, which is why
    they need saying out loud."""

    REJECTED = "rejected"
    """Refused, and `data` carries the rule and the message verbatim."""

    REROUTED = "re-routed"
    """The step's own answer diagnosed a wrong question, and another was asked."""

    SKIPPED = "skipped"
    """Not attempted, and `data` says on what evidence."""

    OVERRIDDEN = "overridden"
    """A value the Engine produced was replaced by the Orchestrator — the snap."""

    KEPT = "kept"
    """A change was computed, checked, and discarded in favour of what was there."""


@dataclass
class Call:
    """One model call, self-contained.

    Everything the sheet needs about a call lives here, so it never has to open
    `NN_<pass>.prompt.txt` or infer anything from a filename. That coupling is
    what produced the wrong pairing this module was written to fix, and a record
    that still required it would have moved the bug rather than removed it.
    """

    pass_name: str
    model: str
    prompt: str
    answer: str = ""
    thinking: str = ""
    """The reasoning channel. Recorded because Ollama routes `qwen3-vl`'s
    structured output here and leaves `content` empty, so a run where the answer
    looks missing is often a run where it arrived on the other channel."""

    truncated: bool = False
    retried: bool = False
    """A truncated pass is retried once with a doubled budget. Both calls are
    recorded; this marks the second, so a reader is not left wondering why one
    Zone cost two calls."""

    num_ctx: int = 0
    seconds: float = 0.0
    error: str | None = None
    """Set when the call raised. Recorded rather than dropped: a run that reports
    only its successes cannot explain a gap in its own numbering."""

    asked: dict[str, str] = field(default_factory=dict)
    """What was put to the model, as a short hash of each part — `prompt`,
    `picture` and `schema`. See `asked_of`.

    Recorded so a replay can say when today's code asks a call differently
    from the run it serves answers from — spec 0012 §4b. A replay serves by
    pass and order, so a crop moved or a grid hint of 8 rows where the run
    asked 4 is otherwise served the old answer and reads as a change that
    did nothing. Empty on a trace written before 2026-10-13."""


def asked_of(prompt: str, images: list[bytes],
             schema: dict[str, Any]) -> dict[str, str]:
    """A call's `asked` hashes: its prompt, its picture and its schema.

    Hashes of exactly what the transport is handed — the picture's encoded
    bytes, the schema with its keys sorted — so any change to what the model
    is shown or told is one. Twelve hex digits each: a record to compare,
    not a secret to keep."""
    picture = hashlib.sha256()
    for image in images:
        picture.update(hashlib.sha256(image).digest())
    return {
        "prompt": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        "picture": picture.hexdigest()[:12],
        "schema": hashlib.sha256(json.dumps(schema, sort_keys=True).encode(
            "utf-8")).hexdigest()[:12],
    }


@dataclass
class Change:
    """One field of the Document, before and after.

    What makes cause and effect legible rather than implied. `path` is written
    the way a reader would point at it — `zones[3].kind` — and not parsed by
    anything.
    """

    path: str
    before: Any
    after: Any


@dataclass
class Event:
    """One step of the pipeline, model call or decision.

    Decisions get the same shape as calls, with `call` left None, so a reader
    never has to work out whether something was a judgement or a request. The
    steps that lose content in this project are mostly judgements.
    """

    seq: int
    stage: Stage
    step: str
    """The finer step within the stage — `empty_zone`, `reroute`, `wire_repair`.
    Free-form because stages are stable and their internals are not."""

    disposition: Disposition
    zone_index: int | None = None
    seconds: float = 0.0
    call: int | None = None
    """Index into `Trace.calls`, or None for a step that asked nothing."""

    changed: list[Change] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    """Step-specific primitives. See the module docstring for the standard each
    payload is chosen against."""


@dataclass
class Trace:
    """The ordered account of one Conversion.

    Append-only by construction: `record` and `record_call` are the only ways in,
    and neither takes a sequence number — holding that here is what keeps the
    order true when a step is added somewhere new.
    """

    events: list[Event] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    version: int = TRACE_VERSION

    def record(self, stage: Stage, step: str, disposition: Disposition, *,
               zone_index: int | None = None, seconds: float = 0.0,
               call: int | None = None,
               changed: list[Change] | None = None,
               **data: Any) -> Event:
        """Append one step. Returns the Event so a caller can amend `data` later.

        Amending matters for a step whose outcome is only known after the work:
        `_extract` records that it asked before it knows whether the answer
        mapped, and filling the same Event in beats appending a second one that a
        reader would have to pair up.
        """
        event = Event(
            seq=len(self.events), stage=stage, step=step,
            disposition=disposition, zone_index=zone_index, seconds=seconds,
            call=call, changed=list(changed or []), data=data,
        )
        self.events.append(event)
        return event

    def record_call(self, call: Call) -> int:
        """Append one model call and return its index, for an Event to point at."""
        self.calls.append(call)
        return len(self.calls) - 1

    @property
    def next_call(self) -> int:
        """The index the next recorded call will take.

        Read *before* a pass runs, so the Event can name the call it is about to
        make without the caller threading the index back out of the Engine. The
        Engine records the call; the Orchestrator only has to know where it will
        land.
        """
        return len(self.calls)

    def calls_since(self, mark: int) -> tuple[int | None, int]:
        """(first call index, how many) recorded since `mark`. (None, 0) if none.

        Asked *after* a pass, against a `next_call` taken before it, because a
        step cannot assume it made exactly one call — or any. A truncated answer
        is retried with a doubled budget and shows up here as two, which is how
        the sheet explains a Zone that cost two calls without the reader having
        to notice a gap in the numbering.

        None rather than `mark` when nothing was recorded, and that case is real:
        the calls are recorded by the harness's Transport wrapper, so a plain
        `convert()` produces a Trace whose events are complete and whose `calls`
        are empty. An Event pointing at a call that does not exist would be worse
        than one admitting it has none.
        """
        made = len(self.calls) - mark
        return (mark if made else None), made

    def for_zone(self, index: int) -> list[Event]:
        return [event for event in self.events if event.zone_index == index]

    def in_stage(self, stage: Stage) -> list[Event]:
        return [event for event in self.events if event.stage is stage]

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, default=_encode)

    @classmethod
    def from_json(cls, raw: str) -> Trace:
        """Rebuild a Trace written by `to_json`.

        Imported by `tools/inspect_run.py` rather than reimplemented there, the
        way it already imports `geometry_score` and `wire`. One schema, defined
        once: a reader with its own parser drifts from the writer, and the drift
        shows up as a diagnostic that is quietly wrong, which is the failure this
        whole module is a response to.
        """
        data = json.loads(raw)
        return cls(
            version=data.get("version", 0),
            calls=[Call(**call) for call in data.get("calls", [])],
            events=[
                Event(
                    seq=event["seq"],
                    stage=Stage(event["stage"]),
                    step=event["step"],
                    disposition=Disposition(event["disposition"]),
                    zone_index=event.get("zone_index"),
                    seconds=event.get("seconds", 0.0),
                    call=event.get("call"),
                    changed=[Change(**c) for c in event.get("changed", [])],
                    data=event.get("data", {}),
                )
                for event in data.get("events", [])
            ],
        )


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"not JSON-serialisable: {type(value).__name__}")
