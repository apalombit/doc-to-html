"""Measure real models against the acceptance set.

    python -m doc_to_html.bakeoff                     # every candidate
    python -m doc_to_html.bakeoff --models qwen3-vl:2b
    python -m doc_to_html.bakeoff --fixtures invoice_0001

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

from .acceptance import Mismatch, compare
from .config import Settings, configure_logging, load
from .engines.ollama import OllamaEngine
from .engines.transport import OllamaTransport, Response, Transport
from .ir import Document
from .orchestrator import Conversion, EngineSet

ACCEPTANCE_SET = Path("tests/fixtures")
"""Where the committed expected IR lives. Each file names its own Source Image."""

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

    def __call__(self, *, model: str, pass_name: str, prompt: str,
                 images: list[bytes], schema: dict[str, Any],
                 num_ctx: int) -> Response:
        started = time.perf_counter()
        try:
            return self.inner(
                model=model, pass_name=pass_name, prompt=prompt, images=images,
                schema=schema, num_ctx=num_ctx,
            )
        finally:
            self.timings.append(
                PassTiming(pass_name=pass_name,
                           seconds=time.perf_counter() - started)
            )


@dataclass
class Attempt:
    """One model's go at one document."""

    fixture: str
    model: str
    timings: list[PassTiming] = field(default_factory=list)
    mismatches: list[Mismatch] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    resident_mb: float | None = None
    error: str | None = None

    @property
    def seconds(self) -> float:
        return sum(timing.seconds for timing in self.timings)

    @property
    def verdict(self) -> str:
        if self.error:
            return "error"
        return "match" if not self.mismatches else f"{len(self.mismatches)} off"


def load_acceptance_set(root: Path) -> dict[str, tuple[Path, Document]]:
    """The committed expected IR, keyed by fixture name.

    Read from the JSON rather than from the Python builders so that nothing in the
    package imports the test suite. Each file records its own Source Image path,
    which is what makes it portable.
    """
    found = {}
    for path in sorted((root / ACCEPTANCE_SET).glob("*.expected.json")):
        document = Document.from_json(path.read_text())
        found[path.name.removesuffix(".expected.json")] = (
            root / document.source.path,
            document,
        )
    if not found:
        raise SystemExit(f"no expected IR found under {root / ACCEPTANCE_SET}")
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
    """One model in every role.

    A bake-off asks how a single model does at the whole job, so layout and
    extraction share it — which is also how the Orchestrator runs, because two
    vision models cannot stay resident in 8 GB.
    """
    def engine() -> OllamaEngine:
        return OllamaEngine.from_settings(settings, model, transport=transport)

    return EngineSet(layout=engine(), extract=engine(), audit=engine())


TransportFor = Callable[[str, str], Transport]
"""Builds the transport for one (model, fixture) pair. Injected by the tests."""


def ollama_transport_for(settings: Settings) -> TransportFor:
    def build(model: str, fixture: str) -> Transport:
        return OllamaTransport(
            OllamaEngine.from_settings(settings, model).client_kwargs()
        )

    return build


def run(models: Iterable[str], acceptance: dict[str, tuple[Path, Document]],
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
        for name, (image, expected) in acceptance.items():
            timing = TimingTransport(inner=build(model, name))
            attempt = Attempt(fixture=name, model=model)
            try:
                conversion = Conversion(
                    source=image,
                    engines=engines_for(model, settings, timing),
                )
                actual = conversion.run()
                attempt.mismatches = compare(expected, actual)
                for failure in actual.failures:
                    attempt.mismatches.append(
                        Mismatch(f"zone {failure.zone_index}", "extraction",
                                 "content", failure.reason)
                    )
                # Caveats deliberately do not count against a model. A table too
                # tall for the model's input was read at reduced resolution because
                # slice stitching is not built, which is this project's limitation
                # and not the model's.
                attempt.caveats = [c.note for c in actual.caveats]
            except Exception as error:
                attempt.error = f"{type(error).__name__}: {error}"
            attempt.timings = timing.timings
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
        ["model", "document", "structure", "passes", "total s", "slowest pass"],
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
        ["model", "documents", "matched", "mean s", "resident MB"],
        [
            [
                model,
                str(len(group)),
                str(sum(1 for a in group if not a.mismatches and not a.error)),
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
        + "".join(f"\n  - {mismatch}" for mismatch in attempt.mismatches)
        for attempt in attempts
        if attempt.mismatches or attempt.error
    ]

    caveats = [
        f"  - {attempt.model} / {attempt.fixture}: {note}"
        for attempt in attempts
        for note in attempt.caveats
    ]

    return "\n\n".join(
        ["Per document", per_document, "Per pass", per_pass, "Per model", summary]
        + (["What did not match", "".join(details).strip()] if details else [])
        + (["Read with a caveat (this project's limitation, not the model's)",
            "\n".join(caveats)] if caveats else [])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m doc_to_html.bakeoff",
        description="Measure real models against the acceptance set. Needs Ollama.",
    )
    parser.add_argument("--models", default="",
                       help="comma-separated model names; default is every "
                            "configured model plus the open questions' candidates")
    parser.add_argument("--fixtures", default="",
                       help="comma-separated fixture names; default is all")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                       help="repository root, for finding the acceptance set")
    parser.add_argument("--json", action="store_true",
                       help="emit machine-readable results as well as the table")
    args = parser.parse_args(argv)

    settings = load()
    configure_logging(settings)
    acceptance = load_acceptance_set(args.root)
    if args.fixtures:
        wanted = args.fixtures.split(",")
        missing = [name for name in wanted if name not in acceptance]
        if missing:
            raise SystemExit(f"unknown fixture(s): {', '.join(missing)}")
        acceptance = {name: acceptance[name] for name in wanted}

    models = (
        [model.strip() for model in args.models.split(",") if model.strip()]
        or models_to_measure(settings)
    )
    print(
        f"{len(models)} model(s) over {len(acceptance)} document(s) "
        f"against {settings.ollama_host}\n",
        file=sys.stderr,
    )

    attempts = run(models, acceptance, settings)
    print(report(attempts))

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
                    "mismatches": [str(m) for m in a.mismatches],
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
