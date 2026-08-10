"""Find Zones with morphology instead of a model, and score it the same way.

    python tools/cv_layout_probe.py [--label 30-cv-layout]

Runs 26-28 closed the two cheap routes to a better geometry pass. Prompt framing
makes both models worse (two arms, two models, eight cells, all monotonic). And
resolution does nothing: `qwen3-vl:4b` returned byte-identical geometry at 384,
512 and 862 — five calls spanning 2.25x the linear pixels, one answer, IoU 0.529.

That ceiling belongs to the model, so the remaining ways past it are a different
model or no model. This is no model.

**What it does.** Threshold the Rectified Image to an ink mask, dilate so that
neighbouring ink merges, take connected components as candidate Zones. A wide
kernel welds words into lines; a tall one welds lines into blocks. The whole
question is whether any kernel lands on *Zone* granularity — "the address block",
"the line-item table" — rather than on words or on the whole page.

**Why it is worth knowing even if it loses.** Zone counts are the tell in every
failure this project has measured: `qwen3-vl:4b` goes to 44 Zones under a frame
instruction and to 28 at long edge 768, and `qwen3.5:4b` produced slivers holding
0.0% ink. A deterministic segmenter that gets granularity roughly right is a
bound on those answers even when it is worse than the model on IoU — it can say
"this box splits a connected mass of ink" without being able to say what the mass
is. That use survives losing the head-to-head, so both numbers are reported: IoU
against the expected IR, and Zone count.

Scored with the shared ruler in `doc_to_html.geometry_score`, against the same
fixture, so a row here, a row in the layout probe and a line in a run's contact
sheet are directly comparable.

Deliberately not wired into the pipeline. This asks whether the approach is worth
building, and nothing here decides that it is.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from doc_to_html.geometry_score import (  # noqa: E402
    expected_boxes,
    expected_zones,
    mean_best_iou,
    score_geometry,
)
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import content_ink, rectify  # noqa: E402
from layout_probe import FIXTURE, SOURCE  # noqa: E402


def ink_mask(image: np.ndarray) -> np.ndarray:
    """Ink as white on black, from the Rectified Image.

    Otsu rather than a fixed threshold because the Rectified Image has already
    been intensity-equalised, so its histogram is bimodal and Otsu's assumption
    holds. A fixed cut would re-introduce the lighting sensitivity that
    rectification exists to remove.
    """
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def zones_from_morphology(image: np.ndarray, kx: float, ky: float,
                          min_area: float) -> list[BBox]:
    """Connected components of dilated ink, as normalised boxes.

    `kx` and `ky` are fractions of the page width and height, so a kernel means
    the same thing on a 862px scan and a 2000px photograph. Choosing them in
    pixels is what makes this kind of segmenter fixture-specific.
    """
    height, width = image.shape[:2]
    mask = ink_mask(image)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(1, int(width * kx)), max(1, int(height * ky))),
    )
    merged = cv2.dilate(mask, kernel, iterations=1)
    count, _, stats, _ = cv2.connectedComponentsWithStats(merged, connectivity=8)

    boxes = []
    page = width * height
    for i in range(1, count):
        x, y, w, h, _ = stats[i]
        if (w * h) / page < min_area:
            continue
        boxes.append(BBox(x / width, y / height, (x + w) / width, (y + h) / height))
    return sorted(boxes, key=lambda b: (round(b.top, 2), b.left))


def _runs_of_blank(profile: np.ndarray, least: int) -> list[tuple[int, int]]:
    """Stretches of `least` or more empty lines, as half-open (start, end)."""
    empty = np.flatnonzero(profile == 0)
    if empty.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(empty) > 1)
    starts = np.concatenate(([empty[0]], empty[breaks + 1]))
    ends = np.concatenate((empty[breaks], [empty[-1]]))
    return [(int(a), int(b) + 1) for a, b in zip(starts, ends)
            if b + 1 - a >= least]


def _slices_between(gaps: list[tuple[int, int]], span: int) -> list[tuple[int, int]]:
    """What is left once the gaps are removed."""
    pieces, cursor = [], 0
    for start, end in gaps:
        if start > cursor:
            pieces.append((cursor, start))
        cursor = end
    if cursor < span:
        pieces.append((cursor, span))
    return pieces


def zones_from_xy_cut(mask: np.ndarray, gap: float) -> list[tuple[BBox, int, int]]:
    """Recursive projection cutting, emitting Bands and columns natively.

    Blind dilation cannot group, because it has no notion of axis alternation: a
    kernel wide enough to weld a line together is wide enough to weld two columns
    together, and its best six-region answer welded the whole page into two
    full-height strips. Cutting alternates axes by construction —

        ink profile down the page -> widest full-width blank bands -> Bands
          within each Band: profile across -> gutters -> columns

    — which is the IR's own vocabulary rather than a bag of boxes, so its output
    can be compared with an expected IR on Band and column as well as on
    position.

    Two levels deep and no further. Cutting naturally produces a split *tree*,
    and Zones are a flat list by definition; going deeper would need a flattening
    rule, which is a design decision this probe exists to inform rather than to
    take. `gap` is a fraction of the page's short edge, applied to both axes so
    one number sweeps the whole method.
    """
    height, width = mask.shape[:2]
    short_edge = min(width, height)
    least = max(1, int(gap * short_edge))

    rows = (mask > 0).sum(axis=1)
    bands = _slices_between(_runs_of_blank(rows, least), height)

    found = []
    for band_index, (top, bottom) in enumerate(bands):
        strip = mask[top:bottom]
        if not strip.any():
            continue
        columns = _slices_between(
            _runs_of_blank((strip > 0).sum(axis=0), least), width)
        placed = 0
        for left, right in columns:
            cell = strip[:, left:right]
            if not cell.any():
                continue
            # Tighten to the cell's own ink: the cut lands in the middle of a
            # gutter, and a box that keeps half the gutter is not the Zone.
            ys = np.flatnonzero(cell.any(axis=1))
            xs = np.flatnonzero(cell.any(axis=0))
            found.append((
                BBox((left + int(xs[0])) / width, (top + int(ys[0])) / height,
                     (left + int(xs[-1]) + 1) / width,
                     (top + int(ys[-1]) + 1) / height),
                band_index, placed,
            ))
            placed += 1
    return found


def expected_bands(path: Path) -> list[tuple[int, int]]:
    """The reference IR's own Band and column numbering, in Zone order."""
    return [
        (zone.band if zone.band is not None else -1,
         zone.column if zone.column is not None else -1)
        for zone in expected_zones(path)
    ]


def xy_cut_report(image: np.ndarray, want: list[BBox],
                  want_bands: list[tuple[int, int]]) -> list[str]:
    """Sweep the gap threshold, scored on the same ruler as everything else.

    **Gate 3, from spec 0004.** This earns a follow-up spec only if it produces
    six Zones on `invoice_0001` *with Bands and columns matching the expected IR*
    and beats the model's snapped score on `covered` and `splits`. Beating IoU
    alone is explicitly not enough — morphology's 0.475 is the standing example
    of a high IoU describing a different page. And `iou` is a secondary field
    anyway since the calibration in #23 measured the reference at 0.70 against
    its own ink.
    """
    mask = content_ink(image)
    lines = [
        "",
        "xy-cut arm — recursive projection cutting, Bands and columns native",
        "",
        "the model's snapped geometry is the bar: 6 Zones, covered 0.99, splits 0",
        "",
        f"{'gap':>7}{'zones':>7}{'iou':>8}{'covered':>10}{'splits':>8}"
        f"{'doubles':>9}   bands match?",
    ]
    for gap in (0.008, 0.012, 0.016, 0.02, 0.03, 0.04, 0.06, 0.08):
        found = zones_from_xy_cut(mask, gap)
        boxes = [box for box, _, _ in found]
        got_bands = [(band, column) for _, band, column in found]
        score = score_geometry(boxes, want, image)
        matches = (
            "yes" if got_bands == want_bands
            else f"no ({len(got_bands)} vs {len(want_bands)})"
        )
        lines.append(
            f"{gap:7.3f}{score.zones:7d}{score.iou:8.3f}{score.covered:10.2f}"
            f"{score.splits:8d}{score.doubles:9d}   {matches}"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="30-cv-layout")
    parser.add_argument("--min-area", type=float, default=0.0015,
                        help="drop components smaller than this fraction of the "
                             "page — specks, rule fragments, stray marks")
    parser.add_argument("--arm", default="both",
                        choices=("morphology", "xy-cut", "both"))
    args = parser.parse_args()

    out = REPO / "debug" / "runs" / args.label
    if out.exists():
        print(f"refusing to overwrite {out} — pick a new label", file=sys.stderr)
        return 1
    out.mkdir(parents=True)

    rectified = rectify(SOURCE)
    image = rectified.image
    want = expected_boxes(FIXTURE)
    height, width = image.shape[:2]

    # Swept rather than tuned. A single hand-picked kernel that scored well would
    # be a number fitted to one fixture; the shape of the sweep says whether any
    # kernel finds Zone granularity at all, which is the actual question.
    kernels = [
        (kx, ky)
        for kx in (0.01, 0.02, 0.04, 0.08, 0.12, 0.18, 0.25, 0.35)
        for ky in (0.004, 0.01, 0.02, 0.03, 0.05, 0.08)
    ]

    lines = [
        f"cv layout probe — {width}x{height}, min area {args.min_area}",
        f"expected {len(want)} Zones; qwen3-vl:4b scores 0.529 with 6",
        "",
        f"{'kx':>7s}{'ky':>7s}{'zones':>7s}{'mean IoU':>10s}",
    ]
    best: tuple[float, tuple[float, float, list[BBox]] | None] = (0.0, None)
    if args.arm in ("morphology", "both"):
        for kx, ky in kernels:
            got = zones_from_morphology(image, kx, ky, args.min_area)
            value = mean_best_iou(got, want)
            lines.append(f"{kx:7.3f}{ky:7.3f}{len(got):7d}{value:10.3f}")
            if value > best[0]:
                best = (value, (kx, ky, got))

    if args.arm in ("xy-cut", "both"):
        lines += xy_cut_report(image, want, expected_bands(FIXTURE))

    if best[1]:
        kx, ky, got = best[1]
        lines += ["", f"best kernel {kx}x{ky} — {len(got)} Zones, IoU {best[0]:.3f}"]
        for i, b in enumerate(got):
            lines.append(
                f"  {i}  ({b.left:.3f},{b.top:.3f},{b.right:.3f},{b.bottom:.3f})"
            )
        drawn = image.copy()
        for b in got:
            cv2.rectangle(
                drawn,
                (int(b.left * width), int(b.top * height)),
                (int(b.right * width), int(b.bottom * height)),
                (0, 0, 255), 2,
            )
        for w in want:
            cv2.rectangle(
                drawn,
                (int(w.left * width), int(w.top * height)),
                (int(w.right * width), int(w.bottom * height)),
                (0, 160, 0), 2,
            )
        cv2.imwrite(str(out / "best_vs_expected.png"), drawn)

    report = "\n".join(lines)
    (out / "summary.txt").write_text(report + "\n")
    print(report)
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
