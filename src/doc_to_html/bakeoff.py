"""Run real models over the corpus and write out what they produced.

    python -m doc_to_html.bakeoff                     # every candidate
    python -m doc_to_html.bakeoff --models qwen3-vl:2b
    python -m doc_to_html.bakeoff --fixtures invoice_0001
    python -m doc_to_html.bakeoff --fixtures sweep    # all fifteen

**It no longer scores anything.** It used to compare each converted IR against
a hand-typed reference with `acceptance.compare()` and print a mismatch total,
and spec 0007 retired that: the measure is now `scoring.score_document()`,
which compares the *rendered page* against the *source page*, and the review
surface is `report.html`. What is left here is what was always underneath — a
harness that converts every document with a real model, times every pass, and
writes the artefacts. Timing and failure are its output; the verdict is
somebody else's.

The evidence the whole slice exists to produce. Everything else in this project
is tested against recorded responses, which exercises the pipeline and says
nothing whatever about whether a model can read a page. This is where that gets
measured.

**Opt-in, and not part of the suite.** It needs a running Ollama with the models
pulled, and it takes minutes rather than milliseconds. `pyproject.toml` confines
pytest to `tests/`, and the logic here is covered there against a fake transport —
so a formatting mistake is caught in a millisecond rather than after ten minutes
of model calls.

Three questions have been settled by argument so far and belong to measurement:

*Is a 4B model adequate, or does this need Ollama Cloud?* Accuracy and latency
per model, below.

*Is the 2B model good enough that it and an audit model could stay resident
together in 8 GB?* Resident size is reported where Ollama will say, and the two
have to fit under the ceiling together.

*What accuracy would tesseract have to beat?* This slice is vision-only and is
therefore the control condition. Whatever number comes out here is the bar.

The audit model is measured as a candidate *reader* rather than as an auditor,
because the Coverage Audit is not built. Its accuracy is beside the point; its
resident size is the number that decides whether it can share memory with an
extraction model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import Settings, configure_logging, load
from .corpus import SOURCES, names
from .engines.base import LayoutEngine
from .engines.ollama import OllamaEngine
from .engines.transport import OllamaTransport, Response, Transport
from .orchestrator import Conversion, EngineSet, _layout_engine
from .render import render
from .trace import Call, Trace

CANDIDATES = ("qwen3-vl:4b", "qwen3-vl:2b", "granite3.2-vision:latest")
"""The models `docs/status.md` has open questions about.

Measured alongside whatever is configured, because the questions are about these
specific models and a configuration that happens not to name one of them would
otherwise leave its question unanswered.
"""


def models_to_measure(settings: Settings) -> list[str]:
    """Every configured model, then the candidates, in order and without repeats.

    The configured models come first because they are what a Conversion would
    actually use, and a bake-off whose first answer is about a model nobody has
    selected buries the useful number.
    """
    return list(dict.fromkeys(
        [settings.layout_model, settings.extract_model, settings.audit_model]
        + list(CANDIDATES)
    ))


@dataclass(frozen=True)
class PassTiming:
    """How long one call to a model took, and which pass it was."""

    pass_name: str
    seconds: float


@dataclass
class TimingTransport:
    """Wraps the real transport and times each call.

    A wrapper rather than instrumentation inside the Engine: the transport seam
    already exists, so measurement costs nothing in the code that ships.

    The pass name comes from the Engine rather than from the schema's title,
    because `prose` and `list` share one schema — reading the title reports both as
    "Blocks" and quietly averages two different jobs together.
    """

    inner: Transport
    timings: list[PassTiming] = field(default_factory=list)
    answers: list[tuple[str, str, str]] = field(default_factory=list)
    """(pass name, raw answer, the prompt that produced it) in order.

    Kept so `--dump` can write out what the model actually said — a run that
    reports only "MappingError" throws away the one thing needed to fix the
    prompt. The prompt travels with the answer because iterating means comparing
    runs, and a dump that records only the answer leaves you inferring which
    wording produced it from the shell history."""

    trace: Trace | None = None
    """Where each call is recorded as a `Call`, when a Conversion is tracing.

    The same seam, used for the same reason: this already sees the model, the
    prompt, the answer and the clock. What it adds over `answers` is that a Call
    is appended **once per call, in a `finally`, carrying an optional error** —
    so it holds the failed calls too. `answers` appends only on success while
    `timings` appends always, which means those two desynchronise the moment a
    pass raises, and a reader pairing them up gets a prompt attached to somebody
    else's answer. Left as they are because the report reads them positionally
    within a pass; the Trace is the record that does not have the flaw."""

    def __call__(self, *, model: str, pass_name: str, prompt: str,
                 images: list[bytes], schema: dict[str, Any],
                 num_ctx: int) -> Response:
        started = time.perf_counter()
        call = Call(pass_name=pass_name, model=model, prompt=prompt,
                    num_ctx=num_ctx)
        reply = None
        try:
            reply = self.inner(
                model=model, pass_name=pass_name, prompt=prompt, images=images,
                schema=schema, num_ctx=num_ctx,
            )
            self.answers.append((pass_name, reply.answer, prompt))
            return reply
        except Exception as error:
            call.error = f"{type(error).__name__}: {error}"
            raise
        finally:
            seconds = time.perf_counter() - started
            self.timings.append(
                PassTiming(pass_name=pass_name, seconds=seconds)
            )
            if self.trace is not None:
                call.seconds = seconds
                if reply is not None:
                    call.answer = reply.answer
                    call.thinking = reply.thinking
                    call.truncated = reply.truncated
                # `ask` retries a truncated pass once with a doubled budget, so
                # the same pass appears twice. Marked here rather than left for a
                # reader to spot, because an unexplained second call to the same
                # pass reads as a bug in the loop above it.
                previous = self.trace.calls[-1] if self.trace.calls else None
                call.retried = (
                    previous is not None
                    and previous.pass_name == pass_name
                    and previous.truncated
                )
                self.trace.record_call(call)


@dataclass
class Attempt:
    """One model's go at one document."""

    fixture: str
    model: str
    timings: list[PassTiming] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    """Zones the Conversion could not read at all, in its own words.

    Not a score. A Zone that raised is a Zone with no content, and that is a
    fact about the run rather than a judgement about the output — the
    judgement is `scoring.score_document()`'s and appears in `report.html`."""

    caveats: list[str] = field(default_factory=list)
    answers: list[tuple[str, str, str]] = field(default_factory=list)
    html: str | None = None
    """The document as it actually rendered, when the Conversion got that far.

    Kept so `--dump` can write it out. Every other artefact of a run describes an
    intermediate stage; this is the thing a reader would have been handed, and
    judging structural fidelity by eye against the Source Image is what
    docs/adr/0002 asks for."""

    zones_used: str | None = None
    """The geometry the Conversion actually ran on, as JSON.

    Not the same thing as the layout answer in `answers`, and the difference is
    the point. The dump records what the model *said*; anything the Orchestrator
    does to those boxes afterwards — snapping them onto the ink, for instance —
    happens downstream of it. Run 39 converted on snapped geometry while the
    contact sheet drew and scored the raw answer, so its diagnostic described a
    document that had not been produced. A tool reading a run cannot be expected
    to know which passes rewrite geometry; the run has to say."""

    trace: Trace | None = None
    """Every step this Conversion took, model call or decision. See `trace.py`.

    Written to the dump as `trace.json`, which is what lets a contact sheet show
    the pipeline in the order it ran instead of pairing Zone *i* with answer *i*
    and hoping. That pairing is how run 46's sheet came to show six classify
    verdicts under a heading reading "What each crop returned"."""

    resident_mb: float | None = None
    error: str | None = None

    @property
    def seconds(self) -> float:
        return sum(timing.seconds for timing in self.timings)

    @property
    def verdict(self) -> str:
        """Whether the Conversion finished, which is all this can say now.

        Deliberately not a quality word. "match" used to appear here and it is
        exactly the word that let `sample_table_0003` look fine while missing
        every column header of its only table.
        """
        if self.error:
            return "error"
        if self.failures:
            return f"{len(self.failures)} zone(s) unread"
        return "converted"


def load_corpus(root: Path, wanted: Iterable[str]) -> dict[str, Path]:
    """The Source Image of each named document, keyed by name.

    A name and a picture, and nothing else. There used to be an expected
    `Document` beside each one and a comparison at the end; `doc_to_html.corpus`
    now says what the corpus is and `doc_to_html.scoring` says how it is judged.
    """
    found = {}
    for name in wanted:
        source = SOURCES[name]
        png = source.png_path(root)
        if not png.is_file():
            raise SystemExit(
                f"{name}: no Source Image at {source.png} — run "
                f"tools/shoot_corpus.py"
            )
        found[name] = png
    if not found:
        raise SystemExit("no documents selected")
    return found


ResidentFor = Callable[[str], "float | None"]
"""How much memory a model occupies, or None if it cannot be told."""


def ollama_resident_for(settings: Settings) -> ResidentFor:
    """Ask Ollama how much memory *this* model occupies, or None.

    The constraint being tested is an 8 GB ceiling, so this is the number the whole
    "could 2b and an audit model share memory" question rests on. Two things it has
    to get right, both of which are easy to get wrong:

    It matches the loaded model by name. Ollama keeps recently used models resident,
    so the largest thing loaded is routinely a *previous* candidate — reporting that
    attributes an evicted 4B model's footprint to the 2B one being measured.

    It prefers `size_vram` over `size`. What matters is what is resident, not what
    the weights occupy on disk once mapped.

    Best-effort: an older Ollama will not answer, and that is not a reason to lose a
    run. Injectable, and injected by the suite, because this is a second route to
    the server — the transport is meant to be the only one, and the suite asserts it.
    """
    def measure(model: str) -> float | None:
        try:
            import ollama

            client = ollama.Client(
                **OllamaEngine.from_settings(settings, model).client_kwargs()
            )
            for loaded in client.ps().models:
                if getattr(loaded, "model", None) != model:
                    continue
                resident = getattr(loaded, "size_vram", 0) or getattr(loaded, "size", 0)
                return float(resident) / 1e6 if resident else None
        except Exception:
            return None
        return None

    return measure


def engines_for(model: str, settings: Settings,
                transport: Transport) -> EngineSet:
    """One model in every role, classification included.

    A bake-off asks how a single model does at the whole job, so every role
    shares it — which currently matches the shipped defaults, so a bake-off run
    and a production run make the same calls to the same model.

    That correspondence ends the moment any role is pointed elsewhere:
    `--models a,b` names one model at a time and cannot express "a for geometry,
    b for classification". Measuring a combination is issue #19's job, and it
    needs a way to say so that does not exist here yet.

    **Geometry is the one exception, and it has to be.** It comes from a
    trained ONNX detector rather than from `model`, and this is the only path
    `tools/iterate.sh` runs — so ignoring `DTH_LAYOUT_DETECTOR` here would mean
    a detector setting could be measured by a probe and never by a Conversion,
    which is the thing it exists to make possible. The other three roles still
    share `model`, and `--models` still means what it says about them.

    **Every detector setting has to be forwarded, not just the name**, and this
    is written down because it has already gone wrong once. `DTH_HEADING_RULE`
    was added, reached `Settings`, was recorded into `dth_env.txt`, and never
    reached the detector — because this function assembled its own arguments to
    `from_name` and simply did not know about the new one. The run announced
    itself as the arm it was not, and its answers came back byte-identical to the
    baseline it was supposed to differ from, which reads as "the change does
    nothing" rather than "the change did not run".

    So the settings travel as one object. A detector setting added to
    `Settings` and forwarded by `orchestrator._layout_engine` is now carried here
    by construction; the two paths cannot drift apart one argument at a time.
    """
    def engine() -> OllamaEngine:
        return OllamaEngine.from_settings(settings, model, transport=transport)

    layout: LayoutEngine = _layout_engine(settings)

    return EngineSet(layout=layout, classify=engine(), extract=engine(),
                     audit=engine())


TransportFor = Callable[[str, str], Transport]
"""Builds the transport for one (model, fixture) pair. Injected by the tests."""


def ollama_transport_for(settings: Settings) -> TransportFor:
    def build(model: str, fixture: str) -> Transport:
        return OllamaTransport(
            OllamaEngine.from_settings(settings, model).client_kwargs()
        )

    return build


def run(models: Iterable[str], corpus: dict[str, Path],
        settings: Settings, *,
        transport_for: TransportFor | None = None,
        resident_for: ResidentFor | None = None) -> list[Attempt]:
    """Every model over every document, batched by model.

    Batched by model rather than alternating because a swap costs a reload, which
    would show up as latency belonging to the wrong thing.
    """
    build = transport_for or ollama_transport_for(settings)
    measure = resident_for or ollama_resident_for(settings)
    attempts = []
    for model in models:
        for name, image in corpus.items():
            # One Trace, shared: the Conversion appends its steps, the transport
            # appends the calls those steps made. Built here rather than taken
            # off the Conversion afterwards because the transport is wrapped
            # before the Conversion exists, and an Event naming a call has to be
            # able to find it in the same list.
            trace = Trace()
            timing = TimingTransport(inner=build(model, name), trace=trace)
            attempt = Attempt(fixture=name, model=model, trace=trace)
            try:
                conversion = Conversion(
                    source=image,
                    engines=engines_for(model, settings, timing),
                    trace=trace,
                    # Named rather than left to the field's default, which
                    # resolves `config.load()` against the *process
                    # environment* a second time. Both readings agree when a
                    # variable is exported, which is how `tools/iterate.sh`
                    # runs — so this is not a bug being fixed but a divergence
                    # being closed: the run must convert on the Settings it
                    # resolved and wrote into `dth_env.txt`, not on a
                    # re-resolution that nothing recorded. `DTH_HEADING_RULE`
                    # is what this project already paid to learn that with.
                    caption_pass=settings.caption_pass,
                )
                actual = conversion.run()
                attempt.html = render(actual)
                attempt.zones_used = json.dumps(
                    [
                        {
                            "kind": zone.kind.value, "role": zone.role.value,
                            "band": zone.band, "column": zone.column,
                            "left": zone.bbox.left, "top": zone.bbox.top,
                            "right": zone.bbox.right, "bottom": zone.bbox.bottom,
                        }
                        for zone in actual.zones if zone.bbox is not None
                    ],
                    indent=2,
                )
                attempt.failures = [
                    f"zone {failure.zone_index} ({failure.kind}): "
                    f"{failure.reason}"
                    for failure in actual.failures
                ]
                # Caveats deliberately do not count against a model. A table too
                # tall for the model's input was read at reduced resolution because
                # slice stitching is not built, which is this project's limitation
                # and not the model's.
                attempt.caveats = [c.note for c in actual.caveats]
            except Exception as error:
                attempt.error = f"{type(error).__name__}: {error}"
            attempt.timings = timing.timings
            attempt.answers = timing.answers
            attempt.resident_mb = measure(model)
            attempts.append(attempt)
    return attempts


def _row(cells: list[str], widths: list[int]) -> str:
    return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()


def _table(header: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(header[column]), *(len(row[column]) for row in rows))
        if rows else len(header[column])
        for column in range(len(header))
    ]
    lines = [_row(header, widths), _row(["-" * width for width in widths], widths)]
    lines += [_row(row, widths) for row in rows]
    return "\n".join(lines)


def report(attempts: list[Attempt]) -> str:
    """A table a human can act on: per document, then per model, then the details.

    Not raw logs. The point of running this is to decide something, and a decision
    needs the numbers beside each other.
    """
    if not attempts:
        return "no attempts"

    per_document = _table(
        ["model", "document", "outcome", "passes", "total s", "slowest pass"],
        [
            [
                attempt.model,
                attempt.fixture,
                attempt.verdict,
                str(len(attempt.timings)),
                f"{attempt.seconds:.1f}",
                (
                    f"{max(attempt.timings, key=lambda t: t.seconds).pass_name} "
                    f"{max(t.seconds for t in attempt.timings):.1f}s"
                    if attempt.timings else "-"
                ),
            ]
            for attempt in attempts
        ],
    )

    by_model: dict[str, list[Attempt]] = {}
    for attempt in attempts:
        by_model.setdefault(attempt.model, []).append(attempt)

    per_pass_rows = []
    for model, group in by_model.items():
        by_pass: dict[str, list[float]] = {}
        for attempt in group:
            for timing in attempt.timings:
                by_pass.setdefault(timing.pass_name, []).append(timing.seconds)
        for pass_name, seconds in by_pass.items():
            per_pass_rows.append([
                model, pass_name, str(len(seconds)),
                f"{sum(seconds) / len(seconds):.1f}",
                f"{max(seconds):.1f}",
            ])
    per_pass = _table(
        ["model", "pass", "calls", "mean s", "worst s"], per_pass_rows
    )

    summary = _table(
        ["model", "documents", "converted", "mean s", "resident MB"],
        [
            [
                model,
                str(len(group)),
                str(sum(1 for a in group if not a.failures and not a.error)),
                f"{sum(a.seconds for a in group) / len(group):.1f}",
                next(
                    (f"{a.resident_mb:.0f}" for a in group
                     if a.resident_mb is not None),
                    "unknown",
                ),
            ]
            for model, group in by_model.items()
        ],
    )

    details = [
        f"\n{attempt.model} / {attempt.fixture}:"
        + (f"\n  error: {attempt.error}" if attempt.error else "")
        + "".join(f"\n  - {failure}" for failure in attempt.failures)
        for attempt in attempts
        if attempt.failures or attempt.error
    ]

    caveats = [
        f"  - {attempt.model} / {attempt.fixture}: {note}"
        for attempt in attempts
        for note in attempt.caveats
    ]

    return "\n\n".join(
        ["Per document", per_document, "Per pass", per_pass, "Per model", summary]
        + (["What did not convert", "".join(details).strip()] if details else [])
        + (["Read with a caveat (this project's limitation, not the model's)",
            "\n".join(caveats)] if caveats else [])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m doc_to_html.bakeoff",
        description="Convert the corpus with real models. Needs Ollama.",
    )
    parser.add_argument("--models", default="",
                       help="comma-separated model names; default is every "
                            "configured model plus the open questions' candidates")
    parser.add_argument("--fixtures", default="iterate",
                       help="a split (iterate, sweep), 'all', or a "
                            "comma-separated list of document names")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                       help="repository root, for finding the Source Images")
    parser.add_argument("--json", action="store_true",
                       help="emit machine-readable results as well as the table")
    parser.add_argument("--dump", type=Path, default=None,
                       help="write every raw model answer here, for iterating on "
                            "a prompt: DIR/<model>/<fixture>/NN_<pass>.json")
    args = parser.parse_args(argv)

    settings = load()
    configure_logging(settings)
    try:
        wanted = names(args.fixtures)
    except KeyError as error:
        raise SystemExit(str(error)) from error
    corpus = load_corpus(args.root, wanted)

    models = (
        [model.strip() for model in args.models.split(",") if model.strip()]
        or models_to_measure(settings)
    )
    print(
        f"{len(models)} model(s) over {len(corpus)} document(s) "
        f"against {settings.ollama_host}\n",
        file=sys.stderr,
    )

    attempts = run(models, corpus, settings)
    print(report(attempts))

    if args.dump:
        for attempt in attempts:
            out = args.dump / attempt.model.replace(":", "_") / attempt.fixture
            out.mkdir(parents=True, exist_ok=True)
            for index, (pass_name, answer, prompt) in enumerate(attempt.answers):
                (out / f"{index:02d}_{pass_name}.json").write_text(answer)
                (out / f"{index:02d}_{pass_name}.prompt.txt").write_text(prompt)
            if attempt.html is not None:
                (out / "document.html").write_text(attempt.html)
            if attempt.zones_used is not None:
                (out / "zones_used.json").write_text(attempt.zones_used)
            if attempt.trace is not None:
                # Written even when the Conversion raised: a run that died
                # halfway is exactly the run whose steps you want to read, and
                # the Trace holds everything up to the point it stopped.
                (out / "trace.json").write_text(attempt.trace.to_json())
        print(f"\nraw answers written to {args.dump}", file=sys.stderr)

    if args.json:
        print(json.dumps(
            [
                {
                    "model": a.model, "fixture": a.fixture,
                    "seconds": round(a.seconds, 3),
                    "passes": [
                        {"pass": t.pass_name, "seconds": round(t.seconds, 3)}
                        for t in a.timings
                    ],
                    "failures": list(a.failures),
                    "resident_mb": a.resident_mb,
                    "error": a.error,
                }
                for a in attempts
            ],
            indent=2,
        ))

    return 1 if any(a.error for a in attempts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
