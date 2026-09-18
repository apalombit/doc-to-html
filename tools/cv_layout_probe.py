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
sys.path.insert(0, str(REPO))

from doc_to_html.geometry_score import (  # noqa: E402

    mean_best_iou,
    score_geometry,
)
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import (  # noqa: E402
    content_ink,
    rectify,
    regions_from_xy_cut,
)
from doc_to_html.corpus import SOURCES  # noqa: E402

FIXTURE = "invoice_0001"
"""The document this probe's recorded numbers are all against.

It used to import a path to `tests/fixtures/invoice_0001.expected.json` from
`tools/layout_probe.py`. Both are gone — that file was the serialised
acceptance set and that probe measured the vision layout pass, and spec 0007
Thread 0 retired the reference and the pass. The rectangles now come off the
sample `Document`, which is where the same numbers live.
"""

SOURCE = SOURCES[FIXTURE].png_path(REPO)


def reference_boxes(fixture: str) -> list["BBox"]:
    """The document's own Zone rectangles, as something to compare against.

    Not a score. **The rectangle finder below is the reason this file is
    kept**: spec 0006 Change 3 built it, measured it, and did not ship it
    because Change 2 had already spent its value on grouping — it locates
    exactly `invoice_0002`'s four panels and `sample_css_0004`'s two cards and
    nothing on the other three pages. Spec 0007 Thread 2/B reuses it to measure
    borders, rules and card treatment for the style record, which is a use its
    value has not been spent on. Keep its guard: a rectangle covering more than
    0.80 of the page is the page, and unguarded it took `invoice_0001` from six
    Zones to one.
    """
    from tests.documents import SAMPLE_DOCUMENTS

    return [zone.bbox for zone in SAMPLE_DOCUMENTS[fixture]().zones
            if zone.bbox is not None]


def expected_bands(fixture: str) -> list[tuple[int, int]]:
    """The sample document's own Band and column numbering, in Zone order."""
    from tests.documents import SAMPLE_DOCUMENTS

    return [
        (zone.band if zone.band is not None else -1,
         zone.column if zone.column is not None else -1)
        for zone in SAMPLE_DOCUMENTS[fixture]().zones
    ]


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
        found = regions_from_xy_cut(mask, gap)
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
    want = reference_boxes(FIXTURE)
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
