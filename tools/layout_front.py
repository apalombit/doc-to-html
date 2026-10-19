"""Run every corpus document through a real Conversion with no model at all.

    python tools/layout_front.py <out-dir> [--documents sweep]
    python tools/layout_front.py <out-dir> --jitter    # the jitter check, spec 0019 A0

Every model call is refused. What remains is the production layout front:
rectification, the trained detector, the recovery of unread ink, the snap and
every other model-free stage, under the shipped defaults. Each Zone then fails
to classify and renders as a skeleton, so `<out>/<document>/document.html`
shows exactly the Zones a Conversion would have read, and `trace.json` beside
it records every step that ran. All fifteen take about eleven seconds.

**Built for spec 0007's queue, Q4, and proved before it was used.** Run twice
it comes back byte-identical, and its Zones match `tests/frozen/a3-result/`'s
band, column and bbox on 15 of 15 — so it is the layout path a sweep takes,
not an approximation of it. Q4's gate used the same run with a repo-relative
source path; this writes the absolute one a sweep records, and the two differ
by that string alone. A change that should not move any Zone is measured by
running this before and after and comparing the files; one that should move
Zones is measured by which files differ.

What it cannot see: anything a model answer decides — Kinds, Titles, contents,
and every wire rule downstream of them. `tools/rederive.py` is that loop.

**`--jitter`, the jitter check — spec 0019, A0.** Whether the grouping holds
when the page's own picture changes by what no reader would see. Each page's
`Rectified.image` is perturbed four ways (`PERTURBATIONS`): resampled to 98%
and back, to 102% and back, shifted 1px right and down, and blurred at σ 0.6.
`LayoutEngine.detect_zones` — the forward pass and every rule — runs on each,
and its Zones are counted against the unperturbed page's (`counted`): kept at
IoU 0.5 or more, merged when read inside one larger Zone, split when the
perturbed Zones cover it between them, or lost. It writes
`jitter.md` and `jitter.json` under `<out>`, and run twice it writes the same
bytes. About a minute and a half for all twenty-one.

At `999e254` it reads **635 of 848 kept, 0.749**, 16 of 21 pages regrouping
on at least one perturbation. Spec 0019's §A measured 631 of 848 with a
scratch script whose border and interpolation it did not record; every page
figure §A names is this check's to the Zone — cv 15/31, pricing 4/21 and
1/21 blurred, the ticket 0/5, form 3/8, the timetable 1/3.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.corpus import SOURCES, names  # noqa: E402
from doc_to_html.engines.transport import Response  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.orchestrator import Conversion, EngineSet, default_engines  # noqa: E402
from doc_to_html.preprocess import _cv2, rectify  # noqa: E402
from doc_to_html.render import render  # noqa: E402


class Refused(RuntimeError):
    """What every model call gets. A `RuntimeError`, which is what a Zone that
    fails to classify is recorded under and carried past."""


def refuse(*, model: str, pass_name: str, prompt: str, images: list[bytes],
           schema: dict[str, object], num_ctx: int) -> Response:
    raise Refused(f"no model: {pass_name}")


def resampled(image: np.ndarray, factor: float) -> np.ndarray:
    """The picture taken to `factor` of its size and back, bilinear both ways."""
    cv2 = _cv2()
    height, width = image.shape[:2]
    small = cv2.resize(image, (int(round(width * factor)), int(round(height * factor))),
                       interpolation=cv2.INTER_LINEAR)
    back: np.ndarray = cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)
    return back


def shifted(image: np.ndarray) -> np.ndarray:
    """The picture moved 1px right and down, its first row and column repeated."""
    cv2 = _cv2()
    height, width = image.shape[:2]
    moved: np.ndarray = cv2.warpAffine(image, np.array([[1, 0, 1], [0, 1, 1]], dtype=np.float32),
                                       (width, height), borderMode=cv2.BORDER_REPLICATE)
    return moved


def blurred(image: np.ndarray) -> np.ndarray:
    """The picture softened by a Gaussian of σ 0.6."""
    soft: np.ndarray = _cv2().GaussianBlur(image, (0, 0), 0.6)
    return soft


PERTURBATIONS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "r98": lambda image: resampled(image, 0.98),
    "r102": lambda image: resampled(image, 1.02),
    "shift": shifted,
    "blur": blurred,
}
"""Four changes no reader would see. Softness is what moves the grouping
(spec 0019 §A): resampling and blur move most pages, the 1px shift few."""

KEPT_IOU = 0.5
MERGED = 0.9
"""As `tools/twins.py` counts: a Zone is kept where one perturbed Zone meets
it at IoU 0.5 or more, merged where it lies 0.9 inside a larger one. Split
— spec 0019, A1 — where the perturbed Zones cover 0.9 of it between them,
so its ink is read, in more than one crop."""


def _iou(a: BBox, b: BBox) -> float:
    across = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    down = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    shared = across * down
    union = ((a.right - a.left) * (a.bottom - a.top)
             + (b.right - b.left) * (b.bottom - b.top) - shared)
    return shared / union if union > 0 else 0.0


def _inside(box: BBox, other: BBox) -> float:
    across = max(0.0, min(box.right, other.right) - max(box.left, other.left))
    down = max(0.0, min(box.bottom, other.bottom) - max(box.top, other.top))
    area = (box.right - box.left) * (box.bottom - box.top)
    return across * down / area if area > 0 else 0.0


def _covered(box: BBox, others: list[BBox]) -> float:
    """The share of `box` that `others` cover between them, on a 1000-step grid."""
    steps = 1000
    left, top = int(box.left * steps), int(box.top * steps)
    right, bottom = max(left + 1, int(box.right * steps)), max(top + 1, int(box.bottom * steps))
    grid = np.zeros((bottom - top, right - left), dtype=bool)
    for other in others:
        grid[max(0, int(other.top * steps) - top):max(0, int(other.bottom * steps) - top),
             max(0, int(other.left * steps) - left):max(0, int(other.right * steps) - left)] = True
    return float(grid.mean())


def counted(page: list[BBox], perturbed: list[BBox]) -> dict[str, int]:
    """The page's Zones against the perturbed page's: kept, merged, split, lost."""
    kept = merged = split = 0
    for box in page:
        if any(_iou(box, other) >= KEPT_IOU for other in perturbed):
            kept += 1
        elif any(_inside(box, other) >= MERGED for other in perturbed):
            merged += 1
        elif _covered(box, perturbed) >= MERGED:
            split += 1
    return {"zones": len(page), "kept": kept, "merged": merged, "split": split,
            "lost": len(page) - kept - merged - split}


def jitter(documents: list[str]) -> dict[str, dict[str, dict[str, int]]]:
    """Every page's Zones under each perturbation, counted against its own."""
    engine = default_engines(load()).layout
    report: dict[str, dict[str, dict[str, int]]] = {}
    for name in documents:
        image = rectify(REPO / SOURCES[name].png).image
        boxes = [zone.bbox for zone in engine.detect_zones(image) if zone.bbox is not None]
        report[name] = {
            label: counted(boxes, [zone.bbox for zone in engine.detect_zones(change(image))
                                   if zone.bbox is not None])
            for label, change in PERTURBATIONS.items()
        }
        print(name, " ".join(f"{label}:{row['kept']}/{row['zones']}"
                             for label, row in report[name].items()), flush=True)
    return report


def jitter_table(report: dict[str, dict[str, dict[str, int]]]) -> str:
    """The check as a table: per page and perturbation `kept/zones +merged
    ÷split -lost`, then the total kept and the pages that regroup."""
    def cell(row: dict[str, int]) -> str:
        return (f"{row['kept']}/{row['zones']}" + (f" +{row['merged']}" if row["merged"] else "")
                + (f" ÷{row['split']}" if row.get("split") else "")
                + (f" -{row['lost']}" if row["lost"] else ""))

    lines = ["| page | " + " | ".join(PERTURBATIONS) + " |",
             "|---|" + "---|" * len(PERTURBATIONS)]
    for name, rows in report.items():
        lines.append(f"| {name} | " + " | ".join(cell(rows[label]) for label in PERTURBATIONS)
                     + " |")
    kept = sum(row["kept"] for rows in report.values() for row in rows.values())
    total = sum(row["zones"] for rows in report.values() for row in rows.values())
    lost = sum(row["lost"] for rows in report.values() for row in rows.values())
    split = sum(row.get("split", 0) for rows in report.values() for row in rows.values())
    moved = sum(1 for rows in report.values()
                if any(row["kept"] < row["zones"] for row in rows.values()))
    share = kept / total if total else 1.0
    lines += ["", f"**Zones kept: {kept} of {total}, {share:.3f}**; split {split}; lost {lost}; "
              f"pages that regroup on at least one perturbation: {moved} of {len(report)}."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--documents", default="all",
                        help="a corpus split, 'all', or a comma-separated list")
    parser.add_argument("--jitter", action="store_true",
                        help="the jitter check: Zones kept under four invisible perturbations")
    args = parser.parse_args(argv)
    if args.jitter:
        report = jitter(list(names(args.documents)))
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "jitter.json").write_text(json.dumps(report, indent=1) + "\n")
        (args.out / "jitter.md").write_text(jitter_table(report))
        print(jitter_table(report).splitlines()[-1])
        return 0

    live = default_engines(load())
    engines = EngineSet(
        layout=live.layout,
        classify=replace(live.classify, transport=refuse),
        extract=replace(live.extract, transport=refuse),
        audit=replace(live.audit, transport=refuse),
    )
    for name in names(args.documents):
        conversion = Conversion(source=REPO / SOURCES[name].png, engines=engines)
        document = conversion.run()
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "document.html").write_text(render(document))
        (out / "trace.json").write_text(conversion.trace.to_json())
        print(f"{name:22} {len(document.zones):3} Zones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
