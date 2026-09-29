"""Ask the Kind question twice about the same Zone, at two resolutions.

    python tools/classify_probe.py [--label 18-classify-probe] [--repeats 3]

The blocking experiment of `docs/specs/0003-classify-from-the-crop.md`. That spec
proposes splitting the layout pass so each Zone's Kind is decided from its
full-resolution crop rather than from the 384px page. The proposal rests on one
untested premise: **that the model gets the Kind right when it is shown the
Zone's own pixels.** If it does not, the defect is the model's grasp of the
distinction rather than the pixels it was shown, and the spec is void.

Two Zones of `example/invoice.png` have been wrong for four measured prompt
attempts (runs 11, 12, 13, 16, with 17 reproducing 16 exactly):

    zone 1  expected pairs, got prose    73x33px at layout scale
    zone 4  expected table, got pairs   342x55px at layout scale

Each is asked about twice, against the same model with the same prompt and the
same schema:

    crop      the Zone's own pixels, as the Extractor takes them seconds later
    layout    the same Zone as the 384px layout pass sees it — the control

Only the pixel count differs, so a difference in the answers is attributable to
resolution and nothing else. Both images reach the model unresized:
`resize_long_edge` is a ceiling and never enlarges, and both are under it.

**It asks with the shipped `CLASSIFY_PROMPT`, not a wording of its own.** Four
attempts to fix these two Zones by rewording have already failed, so an
experiment carrying a fifth wording could not separate a resolution effect from a
prompt effect.

`--model` and `--conditions` are what make it answer the second question too:
narrowed to one condition it stops being about resolution and compares models,
and it says so in the summary rather than printing a verdict about a comparison
it did not run.

Writes every raw answer, every image it asked about, the exact prompt and the
schema to `debug/runs/<label>/`, beside the run whose crops it reuses.

**Runs 18, 19 and 20 were taken before `CLASSIFY_PROMPT` existed**, when these
definitions lived only in the vision layout prompt. Each carries the prompt it actually
used; a re-run now measures different words, so its numbers stand beside theirs
rather than replacing them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.engines.ollama import CLASSIFY_PROMPT, OllamaEngine  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import ImageArray, crop  # noqa: E402
from doc_to_html.wire import ClassifyResponse, schema_of  # noqa: E402

SOURCE_RUN = REPO / "debug" / "runs" / "15-join-split-heading-repeat"
"""The run whose crops and layout image this reuses.

Reusing them rather than re-cropping from scratch is the point: these are the
pixels a real `qwen3-vl:4b` was handed when it gave the two wrong answers, cut
with the production padding by the diagnostic that draws them.
"""


@dataclass(frozen=True)
class Case:
    """One Zone under test, with what the page says it is.

    `crop_file` names the Kind run 15 answered, so what went wrong is legible
    without a second field to hold it: `zone_01_prose.png` is the Zone the model
    called `prose` and `expected` says is `pairs`.
    """

    index: int
    expected: str
    bbox: BBox
    crop_file: str


CASES = (
    Case(1, "pairs", BBox(0.75, 0.10, 0.94, 0.23), "zone_01_prose.png"),
    Case(4, "table", BBox(0.05, 0.41, 0.94, 0.63), "zone_04_pairs.png"),
)
"""The two Zones, with the boxes run 15's model actually returned.

The boxes are the model's own, not the expected IR's, because the crop a
classification pass would take is cut from the geometry pass's answer — testing
against a hand-authored box would measure a pass that does not exist.
"""


def prompt_for() -> str:
    """The shipped classification prompt, verbatim.

    Asking exactly what the pipeline asks is the whole discipline here: four
    prompt rewordings have already failed on these two Zones, so a fifth one
    hiding in this script would make any result meaningless.

    This used to cut the Kind definitions out of the vision layout prompt, because when
    runs 18-20 were taken that was the only place they existed. `CLASSIFY_PROMPT`
    is their home now, and those runs carry the prompt they actually used in
    their own `prompt.txt` — a re-run after this change is measuring different
    words and its numbers are not comparable with theirs.
    """
    return CLASSIFY_PROMPT


def ask(engine: OllamaEngine, image: ImageArray, prompt: str,
        schema: dict) -> tuple[str, float]:
    """One classification call, timed. Production settings, production transport."""
    started = time.perf_counter()
    content = engine.ask("classify", prompt, image, schema)
    return content, time.perf_counter() - started


def kind_of(content: str) -> str:
    """The Kind out of a schema-valid answer, or a marker of what went wrong."""
    try:
        return ClassifyResponse.model_validate_json(content).kind
    except Exception as error:  # noqa: BLE001 — any failure is a datum here
        return f"UNPARSEABLE ({type(error).__name__})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="18-classify-probe")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument(
        "--conditions", default="crop,layout",
        help="which views to ask about. Narrow this to `crop` when the question "
             "is no longer about resolution but about which model to use.",
    )
    args = parser.parse_args(argv)
    conditions = [name.strip() for name in args.conditions.split(",") if name.strip()]

    out = REPO / "debug" / "runs" / args.label
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out} — pick a new label")
    out.mkdir(parents=True)

    settings = load()
    engine = OllamaEngine.from_settings(settings, args.model)
    schema = schema_of(ClassifyResponse)
    prompt = prompt_for()

    layout_page = cv2.imread(str(SOURCE_RUN / "01_layout_input.png"))
    if layout_page is None:
        raise SystemExit(f"no layout image in {SOURCE_RUN}")

    (out / "prompt.txt").write_text(prompt)
    (out / "schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "host.txt").write_text(f"{settings.ollama_host}\n{args.model}\n")
    (out / "source_run.txt").write_text(f"{SOURCE_RUN.name}\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, cwd=REPO)
    (out / "commit.txt").write_text(commit.stdout)

    print(f"=> {args.label}: {args.model}, {args.repeats} repeats per condition")
    print(f"   {len(CASES)} zones x {len(conditions)} condition(s) x "
          f"{args.repeats} = {len(CASES) * len(conditions) * args.repeats} calls\n")

    results: dict[tuple[int, str], list[str]] = {}
    rows: list[dict[str, object]] = []

    for case in CASES:
        available = {
            "crop": cv2.imread(str(SOURCE_RUN / case.crop_file)),
            # Cut from the already-downscaled page rather than cropped and then
            # shrunk, because that is the order the layout pass does it in and
            # the two are not the same picture: resampling a region on its own
            # keeps detail that resampling the whole page throws away.
            "layout": crop(layout_page, case.bbox),
        }
        if available["crop"] is None:
            raise SystemExit(f"no {case.crop_file} in {SOURCE_RUN}")
        views = {name: available[name] for name in conditions}

        for condition, image in views.items():
            height, width = image.shape[:2]
            cv2.imwrite(str(out / f"zone_{case.index:02d}_{condition}.png"), image)
            answers: list[str] = []

            for attempt in range(1, args.repeats + 1):
                content, seconds = ask(engine, image, prompt, schema)
                kind = kind_of(content)
                answers.append(kind)
                (out / f"zone_{case.index:02d}_{condition}_{attempt}.json").write_text(
                    content + "\n"
                )
                mark = "ok " if kind == case.expected else "   "
                print(f"  {mark}zone {case.index} {condition:6} "
                      f"{width:4}x{height:<4} attempt {attempt}: {kind:8} "
                      f"({seconds:.1f}s)")
                rows.append({
                    "zone": case.index, "condition": condition,
                    "attempt": attempt, "width": width, "height": height,
                    "kind": kind, "expected": case.expected,
                    "seconds": round(seconds, 2),
                })

            results[(case.index, condition)] = answers

    (out / "answers.json").write_text(json.dumps(rows, indent=2) + "\n")
    report = summarise(results)
    (out / "summary.txt").write_text(report)
    print(f"\n{report}")
    print(f"raw answers and images in {out}")
    return 0


def summarise(results: dict[tuple[int, str], list[str]]) -> str:
    """The verdict, in the terms the spec asks for.

    The premise holds only if the crop is right *and* the layout view is wrong:
    a crop that answers correctly while the layout view does too says the
    resolution was never the problem for that Zone.
    """
    lines = ["zone  expected  at layout scale        at crop scale",
             "-" * 62]
    verdicts = []
    for case in CASES:
        layout = results.get((case.index, "layout"), [])
        cropped = results.get((case.index, "crop"), [])
        lines.append(
            f"{case.index:>4}  {case.expected:8}  {_show(layout, case.expected):22}"
            f"  {_show(cropped, case.expected)}"
        )
        verdicts.append((case, layout, cropped))

    asked = {
        condition for case in CASES for condition in ("layout", "crop")
        if results.get((case.index, condition))
    }
    if asked != {"layout", "crop"}:
        # Only one condition was run, so nothing below can speak to resolution:
        # the comparison the verdict is about was never made. Report what was
        # measured and stop, rather than naming a condition that was not asked
        # about — the one habit this whole spec exists to correct.
        only = next(iter(asked), "nothing")
        lines.append("")
        lines.append(
            f"One condition only ({only}) — this run cannot speak to resolution. "
            "It says which Kinds this model gets right on these pixels."
        )
        for case in CASES:
            answers = results.get((case.index, only), [])
            state = "right" if _all(answers, case.expected) else "WRONG"
            lines.append(f"  zone {case.index}: {state}, answered "
                         f"{_show(answers, case.expected)}")
        return "\n".join(lines) + "\n"

    lines.append("")
    moved = [
        case.index for case, layout, cropped in verdicts
        if not _all(layout, case.expected) and _all(cropped, case.expected)
    ]
    fixed_anyway = [
        case.index for case, layout, _ in verdicts if _all(layout, case.expected)
    ]
    still_wrong = [
        case.index for case, _, cropped in verdicts
        if not _all(cropped, case.expected)
    ]

    if len(moved) == len(CASES):
        lines.append(
            "PREMISE HOLDS. Every Zone is wrong at layout scale and right at its "
            "crop. Resolution is the variable, and the split is worth building."
        )
    elif still_wrong and not moved:
        lines.append(
            "PREMISE FAILS. The crop does not fix "
            f"{'zone ' + ', '.join(map(str, still_wrong))}. Showing the model the "
            "pixels does not buy the answer, so the defect is its grasp of the "
            "distinction and not the resolution. Spec 0003 is void; the next move "
            "is a different model, not a different pass."
        )
    else:
        lines.append(
            f"MIXED. Fixed by the crop: {moved or 'none'}. Already right at layout "
            f"scale: {fixed_anyway or 'none'}. Still wrong at the crop: "
            f"{still_wrong or 'none'}. Read the per-attempt answers before "
            "concluding anything — a Zone that was already right at layout scale "
            "is not evidence for the split."
        )
    return "\n".join(lines) + "\n"


def _all(answers: list[str], expected: str) -> bool:
    """Every repeat agreed on the expected Kind.

    Unanimity rather than a majority: an answer that is right two times in three
    is a coin flip that landed well, and building a pass on it would be building
    on noise.
    """
    return bool(answers) and all(answer == expected for answer in answers)


def _show(answers: list[str], expected: str) -> str:
    if not answers:
        return "not asked"
    unique = sorted(set(answers))
    body = unique[0] if len(unique) == 1 else "/".join(unique)
    return f"{body} {'✓' if _all(answers, expected) else '✗'}"


if __name__ == "__main__":
    raise SystemExit(main())
