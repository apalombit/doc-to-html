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
run's contact sheet are comparable. `validate_bands` is run too: run 25 taught
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
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import Settings, load  # noqa: E402
from doc_to_html.engines.ollama import LAYOUT_PROMPT, OllamaEngine  # noqa: E402
from doc_to_html.geometry_score import (  # noqa: E402
    GeometryScore,
    expected_boxes,
    score_geometry,
)
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import (  # noqa: E402
    ImageArray,
    rectify,
    resize_long_edge,
)
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
    """What one layout call was worth, and why if it was worth nothing."""

    geometry: GeometryScore
    detail: str


def nothing_came_back(detail: str, *, valid: bool) -> Scored:
    return Scored(GeometryScore(0, 0.0, 0.0, 0, 0, valid), detail)


def score(content: str, want: list[BBox], image: ImageArray) -> Scored:
    """The shared six-field record, plus whether the Bands validate.

    Both, because run 25 produced geometry that validated and scored 0.21:
    legality and correctness move independently here, and a summary that reported
    only one of them would have called that run a success.

    The record is the same one a run's contact sheet prints, so a row here and a
    line there are the same measurement rather than two that have to be
    reconciled by whoever is reading both.
    """
    try:
        parsed = LayoutResponse.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 - any parse failure is one outcome
        return nothing_came_back(f"unparseable: {type(exc).__name__}", valid=False)

    valid, detail = True, "ok"
    try:
        zones_from_layout(parsed)
    except MappingError as exc:
        valid, detail = False, f"MappingError: {exc}"

    got = [
        BBox(z.left, z.top, z.right, z.bottom)
        for z in parsed.zones
    ]
    if not got:
        return nothing_came_back(detail, valid=valid)
    return Scored(score_geometry(got, want, image, valid=valid), detail)


def sweep_fixtures(out: Path, names: list[str], model: str, repeats: int,
                   edge: int, settings: Settings) -> int:
    """The geometry pass alone, across documents, at one call per repeat.

    Four of the five fixtures have never had their geometry measured by anything.
    Every number spec 0004 rests on comes from `invoice_0001`, and snapping would
    be the first change to geometry in this project's history — it should not
    ship as another finding from one page.

    They do not need Conversions to be measured. Layout is one call, so five
    fixtures at two repeats is ten calls and a few minutes, against roughly four
    minutes for a single full Conversion. Answers are written in the dump layout
    `snap_probe.py` reads, so pricing the snap on them afterwards costs nothing.
    """
    engine = OllamaEngine.from_settings(settings, model)
    lines = [
        f"layout-only sweep — {model}, long edge {edge}, {repeats} repeats",
        "",
        f"{'fixture':24}{'zones':>7}{'iou':>8}{'covered':>10}{'splits':>8}"
        f"{'doubles':>9}{'valid':>7}{'seconds':>9}",
    ]
    for name in names:
        expected = REPO / "tests" / "fixtures" / f"{name}.expected.json"
        source = REPO / json.loads(expected.read_text())["source"]["path"]
        if not source.exists():
            lines.append(f"{name:24}  source missing at {source}")
            continue

        rectified = rectify(source)
        want = expected_boxes(expected)
        for run in range(repeats):
            started = time.perf_counter()
            try:
                content = engine.ask(
                    "layout", LAYOUT_PROMPT, rectified.image,
                    schema_of(LayoutResponse), long_edge=edge,
                )
            except Exception as exc:  # noqa: BLE001
                lines.append(f"{name:24}  {type(exc).__name__}: {exc}")
                continue
            took = time.perf_counter() - started

            dump = out / "dump" / model.replace(":", "_") / name
            dump.mkdir(parents=True, exist_ok=True)
            (dump / f"{run:02d}_layout.json").write_text(content)

            got = score(content, want, rectified.image).geometry
            lines.append(
                f"{name[:23]:24}{got.zones:7d}{got.iou:8.2f}{got.covered:10.2f}"
                f"{got.splits:8d}{got.doubles:9d}"
                f"{'yes' if got.valid else 'NO':>7}{took:9.1f}"
            )
            print(f"  {name:24} zones {got.zones}  covered {got.covered:.2f}  "
                  f"splits {got.splits}  {took:.1f}s", file=sys.stderr)

    report = "\n".join(lines)
    (out / "sweep.txt").write_text(report + "\n")
    print()
    print(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=None,
                        help="comma-separated fixture names, or 'all'. Runs the "
                             "geometry pass only, on the shipped prompt, and "
                             "skips the arm comparison entirely.")
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
    edges = (
        [int(e) for e in args.long_edges.split(",") if e]
        or [settings.layout_long_edge]
    )

    if args.fixtures:
        names = (
            sorted(p.name.replace(".expected.json", "")
                   for p in (REPO / "tests" / "fixtures").glob("*.expected.json"))
            if args.fixtures == "all"
            else [n for n in args.fixtures.split(",") if n]
        )
        model = [m for m in args.models.split(",") if m][0]
        return sweep_fixtures(out, names, model, args.repeats, edges[0], settings)

    rectified = rectify(SOURCE)
    want = expected_boxes(FIXTURE)
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
                        scored = nothing_came_back(
                            f"{type(exc).__name__}: {exc}", valid=False)
                    else:
                        scored = score(content, want, rectified.image)
                    took = time.perf_counter() - started
                    stem = f"{model.replace(':', '_')}__{arm}__{edge}__{run}"
                    (out / f"{stem}.json").write_text(content)
                    results.setdefault((model, arm, edge), []).append(scored)
                    got = scored.geometry
                    print(f"  {model:12s} {arm:9s} edge {edge:4d} #{run}  "
                          f"IoU {got.iou:.3f}  covered {got.covered:.2f}  "
                          f"splits {got.splits:3d}  zones {got.zones}  "
                          f"{'valid' if got.valid else 'INVALID'}  "
                          f"{took:5.1f}s", file=sys.stderr)

    floor = score_geometry(want, want, rectified.image)
    lines = [
        f"layout probe — {args.repeats} repeats, long edges {edges}",
        "",
        f"the reference boxes score covered {floor.covered:.2f}, "
        f"splits {floor.splits}, doubles {floor.doubles} — the floor, and they "
        f"were eyeballed",
        "",
        f"{'model':13s}{'arm':10s}{'edge':>6s}{'mean IoU':>10s}"
        f"{'covered':>9s}{'splits':>8s}{'doubles':>9s}{'zones':>7s}{'valid':>7s}",
    ]
    for model in models:
        for arm in arms:
            for edge in edges:
                cells = results.get((model, arm, edge), [])
                if not cells:
                    continue
                got = [c.geometry for c in cells]
                lines.append(
                    f"{model:13s}{arm:10s}{edge:6d}"
                    f"{statistics.fmean(c.iou for c in got):10.3f}"
                    f"{statistics.fmean(c.covered for c in got):9.2f}"
                    f"{statistics.fmean(c.splits for c in got):8.1f}"
                    f"{statistics.fmean(c.doubles for c in got):9.1f}"
                    f"{statistics.fmean(c.zones for c in got):7.1f}"
                    f"{sum(bool(c.valid) for c in got):>4d}/{len(cells)}"
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
