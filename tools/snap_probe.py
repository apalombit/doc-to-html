"""What snapping does, measured on answers that are already on disk.

    python tools/snap_probe.py --label 35-snap-offline

Two questions, both answered without calling Ollama once.

**Is the ruler straight?** The Zone rectangles in every fixture were typed by
hand — both builders say they are "eyeballed to roughly the right place" — so
some unknown part of the model's 0.56 IoU is the fixture rather than the model.
Snapping the *expected* boxes to their own ink and comparing them with what was
typed puts a number on it. Spec 0004 pre-registers the consequence: **below 0.90
mean IoU, `iou` is demoted to a secondary field** and the gates read `covered`,
`splits` and `doubles` instead. A ruler with 10% slop cannot referee a 10%
improvement.

**Does snapping help?** Every recorded layout answer under `debug/runs/` is a
starting point, and there are two dozen of them for `invoice_0001` alone,
spanning every prompt attempt, both models and four resolutions. A repair that
helps regardless of which wrong answer it starts from is a property of the
method. A repair that helps one is a coincidence.

Both are free. The expensive part was paid when those runs were taken.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.engines.lenient import canonicalise  # noqa: E402
from doc_to_html.geometry_score import (  # noqa: E402
    GeometryScore,
    expected_boxes,
    iou,
    score_geometry,
)
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import rectify, snap_to_ink  # noqa: E402
from doc_to_html.wire import (  # noqa: E402
    LayoutResponse,
    MappingError,
    schema_of,
    zones_from_layout,
)

FIXTURES = REPO / "tests" / "fixtures"
DEMOTION_THRESHOLD = 0.90
"""Pre-registered in spec 0004, before any of these numbers existed."""


@dataclass(frozen=True)
class Answer:
    """One recorded layout answer, and where it came from."""

    run: str
    model: str
    fixture: str
    boxes: list[BBox]
    valid: bool


def fixture_paths() -> dict[str, Path]:
    return {
        path.name.replace(".expected.json", ""): path
        for path in sorted(FIXTURES.glob("*.expected.json"))
    }


def source_of(expected: Path) -> Path:
    return REPO / json.loads(expected.read_text())["source"]["path"]


def recorded_answers(runs: Path, only: str | None = None) -> list[Answer]:
    """Every parseable layout answer under `debug/runs/`, newest run last.

    Takes the last `*_layout.json` that parses in each dump, matching what
    `inspect_run.py` does: `ask` retries a truncated pass and the dump keeps both
    attempts, so the first file can hold an answer the run itself discarded.
    """
    schema = schema_of(LayoutResponse)
    found = []
    for dump in sorted(runs.glob("*/dump/*/*")):
        if not dump.is_dir():
            continue
        fixture = dump.name
        if only and fixture != only:
            continue
        for path in sorted(dump.glob("*_layout.json"), reverse=True):
            try:
                parsed = LayoutResponse.model_validate_json(
                    canonicalise(path.read_text(), schema))
            except Exception:  # noqa: BLE001 - unparseable is one outcome
                continue
            if not parsed.zones:
                continue
            valid = True
            try:
                zones_from_layout(parsed)
            except MappingError:
                valid = False
            found.append(Answer(
                run=dump.parents[2].name,
                model=dump.parent.name,
                fixture=fixture,
                boxes=[BBox(z.left, z.top, z.right, z.bottom)
                       for z in parsed.zones],
                valid=valid,
            ))
            break
    return found


def calibrate(out: Path) -> float:
    """Score the reference boxes, then snap them and see how far they moved."""
    lines = [
        "CALIBRATION — is the ruler straight?",
        "",
        "The reference rectangles were typed by hand. Snapping them to their own",
        "ink says how far 'roughly the right place' actually is.",
        "",
        f"{'fixture':24}{'IoU typed vs snapped':>22}{'worst box':>11}"
        f"{'covered':>9}{'splits':>8}",
    ]
    means = []
    for name, expected in fixture_paths().items():
        source = source_of(expected)
        if not source.exists():
            lines.append(f"{name:24}  source missing at {source}")
            continue
        image = rectify(source).image
        want = expected_boxes(expected)
        snapped = snap_to_ink(image, list(want))
        ious = [iou(a, b) for a, b in zip(want, snapped)]
        floor = score_geometry(want, want, image)
        means.append(statistics.fmean(ious))
        lines.append(
            f"{name:24}{statistics.fmean(ious):22.3f}{min(ious):11.2f}"
            f"{floor.covered:9.2f}{floor.splits:8d}"
        )

    overall = statistics.fmean(means) if means else 0.0
    demote = overall < DEMOTION_THRESHOLD
    lines += [
        "",
        f"mean IoU, typed against snapped, over five fixtures: {overall:.3f}",
        f"pre-registered threshold: {DEMOTION_THRESHOLD}",
        "",
        f"VERDICT: {'DEMOTE iou' if demote else 'iou stands'}",
    ]
    if demote:
        lines += [
            "",
            "`iou` is a secondary field for the rest of spec 0004. Every gate",
            "reads `covered`, `splits` and `doubles`.",
            "",
            "Read this carefully before concluding the model is worse than it is.",
            "The reference is not wrong — it is loose. It was never built to be",
            "pixel-exact, and ADR 0003's claim that a generated document's",
            "expected IR 'is exact and costs nothing' holds for text and does not",
            "hold for geometry. What it means is that the model's IoU has been",
            "scored against rectangles that are themselves about 30% away from",
            "the ink, so neither its absolute value nor a 0.10 improvement in it",
            "can be trusted to mean what it appears to mean.",
        ]
    (out / "calibration.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return overall


def rescore(out: Path, answers: list[Answer]) -> None:
    """Raw versus snapped, for every recorded answer."""
    fixtures = fixture_paths()
    images: dict[str, object] = {}
    wants: dict[str, list[BBox]] = {}

    lines = [
        "RE-SCORING — what snapping does to answers already on disk",
        "",
        f"{len(answers)} recorded layout answers, no Ollama calls.",
        "",
        f"{'run':34}{'fixture':16}{'zones':>6}"
        f"{'iou':>13}{'covered':>15}{'splits':>13}{'doubles':>13}",
    ]
    worse_splits, changed_zones, improved, degraded = [], [], [], []

    for answer in answers:
        expected = fixtures.get(answer.fixture)
        if expected is None:
            continue
        if answer.fixture not in images:
            source = source_of(expected)
            if not source.exists():
                continue
            images[answer.fixture] = rectify(source).image
            wants[answer.fixture] = expected_boxes(expected)
        image = images[answer.fixture]
        want = wants[answer.fixture]

        raw: GeometryScore = score_geometry(answer.boxes, want, image,  # type: ignore[arg-type]
                                            valid=answer.valid)
        snapped_boxes = snap_to_ink(image, list(answer.boxes))  # type: ignore[arg-type]
        snapped: GeometryScore = score_geometry(snapped_boxes, want, image,  # type: ignore[arg-type]
                                                valid=answer.valid)

        lines.append(
            f"{answer.run[:33]:34}{answer.fixture[:15]:16}{raw.zones:6d}"
            f"{raw.iou:6.2f}->{snapped.iou:5.2f}"
            f"{raw.covered:8.2f}->{snapped.covered:5.2f}"
            f"{raw.splits:6d}->{snapped.splits:5d}"
            f"{raw.doubles:6d}->{snapped.doubles:5d}"
        )
        if snapped.splits > raw.splits:
            worse_splits.append(answer.run)
        if snapped.zones != raw.zones:
            changed_zones.append(answer.run)
        improved.append(snapped.covered - raw.covered)
        degraded.append(snapped.iou - raw.iou)

    if improved:
        lines += [
            "",
            f"mean change in covered: {statistics.fmean(improved):+.3f}",
            f"mean change in iou:     {statistics.fmean(degraded):+.3f}  "
            f"(secondary — see calibration.txt)",
            f"answers where splits got worse: {len(worse_splits)} of {len(improved)}",
            f"answers where the Zone count changed: {len(changed_zones)}",
        ]
    (out / "rescore.txt").write_text("\n".join(lines) + "\n")
    print()
    print("\n".join(lines[-8:]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="35-snap-offline")
    parser.add_argument("--runs", type=Path, default=REPO / "debug" / "runs")
    parser.add_argument("--fixture", default=None,
                        help="restrict re-scoring to one fixture")
    args = parser.parse_args()

    out = REPO / "debug" / "runs" / args.label
    out.mkdir(parents=True, exist_ok=True)

    calibrate(out)
    answers = recorded_answers(args.runs, args.fixture)
    if answers:
        rescore(out, answers)
    else:
        print(f"no recorded layout answers under {args.runs}", file=sys.stderr)

    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
