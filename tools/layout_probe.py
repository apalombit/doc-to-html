"""Ask the geometry question three ways, to two models, and score the boxes.

    python tools/layout_probe.py [--label 26-layout-frame] [--repeats 2]

Runs 24 and 25 measured `qwen3.5:4b` on the layout pass and found boxes that are
schema-valid and describe a different page — mean best IoU 0.22 and 0.21 against
`qwen3-vl:4b`'s 0.56. Run 24's coordinates land on an exact 800x650 grid while
the image it was shown is 384x251, so the model located its boxes on a canvas it
assumed rather than the one it was given.

That produced a hypothesis and an objection, and this settles which is right.

**The hypothesis.** `LAYOUT_PROMPT` never states the image's pixel dimensions and
never shows a worked coordinate, so a model without box-grounding training has to
invent the frame. Told the frame explicitly, it might use it — which would make
the pass robust across models rather than dependent on one model's training.

**The objection.** A frame instruction that helps a model which infers boxes
could perturb one that emits them natively. So `qwen3-vl:4b` is measured on every
arm too, and a change that fixes `qwen3.5:4b` while costing the shipped model is
a change this project does not want.

Three arms, differing only by text appended to the shipped prompt:

    shipped   `LAYOUT_PROMPT` verbatim — the control
    dims      + the exact pixel dimensions of the image being shown
    anchored  + dims, and one worked example dividing x by width and y by height

The control is byte-identical to production, so any difference is attributable to
the appended text and nothing else.

**Scored against the expected IR, not by eye.** Mean best IoU over the model's
boxes is the same number `tools/inspect_run.py` prints, so a probe result and a
run's contact sheet are comparable. `_validate_bands` is run too: run 25 taught
that passing validation and being right are independent, and a prompt that buys
legality while keeping the boxes wrong is a worse outcome than an honest refusal.

Two repeats per cell by default because one sample cannot separate a prompt
effect from sampling. Every raw answer, the exact prompt and the score land in
`debug/runs/<label>/`.

**Timings here are noise.** Two models alternate, so each cell may pay a model
load. What they answer is unaffected, which is the only thing this asks about.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.engines.ollama import LAYOUT_PROMPT, OllamaEngine  # noqa: E402
from doc_to_html.geometry_score import expected_boxes, mean_best_iou  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import rectify, resize_long_edge  # noqa: E402
from doc_to_html.wire import (  # noqa: E402
    LayoutResponse,
    MappingError,
    schema_of,
    zones_from_layout,
)

FIXTURE = REPO / "tests" / "fixtures" / "invoice_0001.expected.json"
SOURCE = REPO / "example" / "invoice.png"


DIMS = """

The image you are looking at is exactly {width} pixels wide and {height} pixels
high. It has no other size. Do not assume a square page or a standard page
shape: measure against the image in front of you.

To convert a position you have found in pixels, divide an x pixel by {width} and
a y pixel by {height}. These are different numbers, so a region's height as a
fraction is not its height in pixels divided by the width."""

EXAMPLE = """

Worked example, on a different image that is 400 pixels wide and 200 pixels
high. A region whose ink runs from 40px to 360px across, and from 30px to 70px
down, is reported as:

    left   = 40 / 400  = 0.1
    top    = 30 / 200  = 0.15
    right  = 360 / 400 = 0.9
    bottom = 70 / 200  = 0.35

left and right are divided by the width; top and bottom by the height. That
region occupies 80% of the image's width and 20% of its height, and the four
fractions say so."""


def prompt_for(arm: str, width: int, height: int) -> str:
    """The shipped prompt, plus this arm's addition.

    Appended rather than woven in, so the control is byte-identical to production
    and the diff between arms is exactly the text under test. A prompt edit that
    also reflowed the shipped wording would confound the two.
    """
    text = LAYOUT_PROMPT
    if arm in ("dims", "anchored"):
        text += DIMS.format(width=width, height=height)
    if arm == "anchored":
        text += EXAMPLE
    return text


ARMS = ("shipped", "dims", "anchored")


@dataclass(frozen=True)
class Scored:
    """What one layout call was worth."""

    mean_iou: float
    zones: int
    valid: bool
    detail: str


def score(content: str, want: list[BBox]) -> Scored:
    """Mean best IoU over the model's boxes, and whether the Bands validate.

    Both numbers, because run 25 produced geometry that validated and scored
    0.21: legality and correctness move independently here, and a summary that
    reported only one of them would have called that run a success.
    """
    try:
        parsed = LayoutResponse.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 - any parse failure is one outcome
        return Scored(0.0, 0, False, f"unparseable: {type(exc).__name__}")

    valid, detail = True, "ok"
    try:
        zones = zones_from_layout(parsed)
    except MappingError as exc:
        valid, detail = False, f"MappingError: {exc}"
        zones = []

    got = [
        BBox(z.left, z.top, z.right, z.bottom)
        for z in parsed.zones
    ]
    if not got:
        return Scored(0.0, 0, valid, detail)
    return Scored(mean_best_iou(got, want), len(got), valid, detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="26-layout-frame")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--models", default="qwen3-vl:4b,qwen3.5:4b")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument(
        "--long-edges", default="",
        help="comma-separated layout long edges to sweep, e.g. 384,512,768. "
             "Empty uses the configured one. The image is never enlarged, so an "
             "edge above the source's 862 measures the same pixels as 862.",
    )
    args = parser.parse_args()

    out = REPO / "debug" / "runs" / args.label
    if out.exists():
        print(f"refusing to overwrite {out} — pick a new label", file=sys.stderr)
        return 1
    out.mkdir(parents=True)

    settings = load()
    rectified = rectify(SOURCE)
    want = expected_boxes(FIXTURE)

    edges = (
        [int(e) for e in args.long_edges.split(",") if e]
        or [settings.layout_long_edge]
    )
    models = [m for m in args.models.split(",") if m]
    arms = [a for a in args.arms.split(",") if a]

    results: dict[tuple[str, str, int], list[Scored]] = {}
    for edge in edges:
        shown = resize_long_edge(rectified.image, edge)
        height, width = shown.shape[:2]
        print(f"long edge {edge}: image as shown is {width}x{height}",
              file=sys.stderr)
        for arm in arms:
            (out / f"prompt_{arm}_{edge}.txt").write_text(
                prompt_for(arm, width, height))

        for model in models:
            engine = OllamaEngine.from_settings(settings, model)
            for arm in arms:
                prompt = prompt_for(arm, width, height)
                for run in range(args.repeats):
                    started = time.perf_counter()
                    try:
                        content = engine.ask(
                            "layout", prompt, rectified.image,
                            schema_of(LayoutResponse), long_edge=edge,
                        )
                    except Exception as exc:  # noqa: BLE001
                        content = ""
                        scored = Scored(
                            0.0, 0, False, f"{type(exc).__name__}: {exc}")
                    else:
                        scored = score(content, want)
                    took = time.perf_counter() - started
                    stem = f"{model.replace(':', '_')}__{arm}__{edge}__{run}"
                    (out / f"{stem}.json").write_text(content)
                    results.setdefault((model, arm, edge), []).append(scored)
                    print(f"  {model:12s} {arm:9s} edge {edge:4d} #{run}  "
                          f"IoU {scored.mean_iou:.3f}  zones {scored.zones}  "
                          f"{'valid' if scored.valid else 'INVALID'}  "
                          f"{took:5.1f}s", file=sys.stderr)

    lines = [
        f"layout probe — {args.repeats} repeats, long edges {edges}",
        "",
        f"{'model':13s}{'arm':10s}{'edge':>6s}{'mean IoU':>10s}"
        f"{'zones':>7s}{'valid':>7s}",
    ]
    for model in models:
        for arm in arms:
            for edge in edges:
                cells = results.get((model, arm, edge), [])
                if not cells:
                    continue
                mean = statistics.fmean(c.mean_iou for c in cells)
                zones = statistics.fmean(c.zones for c in cells)
                valid = sum(c.valid for c in cells)
                lines.append(
                    f"{model:13s}{arm:10s}{edge:6d}{mean:10.3f}{zones:7.1f}"
                    f"{valid:>4d}/{len(cells)}"
                )
    lines += ["", "detail:"]
    for (model, arm, edge), cells in results.items():
        for i, c in enumerate(cells):
            if c.detail != "ok":
                lines.append(f"  {model} {arm} edge {edge} #{i}: {c.detail}")

    report = "\n".join(lines)
    (out / "summary.txt").write_text(report + "\n")
    print()
    print(report)
    print(f"\nraw answers and prompts in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
