"""Bake off two trained layout detectors, and draw what each of them did.

    python tools/detector_probe.py --label 58-detector-bakeoff
    python tools/detector_probe.py --fixtures invoice_0001,invoice_0002
    python tools/detector_probe.py --vlm-from debug/runs/50-pairs-orientation

The VLM layout pass is the least stable step in the pipeline, and every
measurement says the instability is structural. Three prompt instructions have
been measured ignored. Resolution does nothing — runs 26-28 returned
byte-identical geometry at 384, 512 and 862. Model swaps changed the failure
rather than removing it. A measured region ceiling worked as a lever and was
read as a target, costing `invoice_0001` its zero-mismatch Conversion twice.

The mechanism is not mysterious. At `DTH_LAYOUT_LONG_EDGE=384`, Qwen3-VL's
patch-16 encoder with a 2x2 spatial merge resolves the whole of `invoice_0001`
into roughly **12x8 visual tokens**, so a 3px panel border is a tenth of one
token, and the boxes are decoded as text with no localization objective anywhere
in the loop. A trained detector has neither problem: it sees the full-resolution
page and it was trained against IoU.

This decides nothing about the pipeline. It answers *which detector, if either*,
and it is deliberately confined to `tools/` for that reason.

**Raw detections only — no nesting policy, no class filtering.** Both models emit
nested boxes, and how to resolve that is the first real design decision a
detector forces. Making it here, before looking, would be guessing; the pictures
below are what it should be made from.

## Two corrections to what the shared ruler measures

Both matter for reading the table, and one of them contradicts what this probe
was planned against.

**`covered` is "exactly one box", not "at least one".** `_covered_share` counts
ink claimed by precisely one rectangle, so it falls for two different reasons —
ink nobody claimed, and ink two boxes both claimed. A single number cannot say
which, so this probe reports `crowded` beside it: the share of ink under two or
more boxes. `covered + crowded` near 1.0 means the page is fully described and
the problem is nesting; a low `covered` with `crowded` near 0 means the detector
missed content. `ink.png` is the same decomposition as a picture.

**`doubles` does not measure overlap.** It counts boxes whose contents are parted
by far more whitespace than their own leading — a box that *swallowed* two
regions, not two boxes on one region. It is a merge detector. Nesting is what
`crowded` is for.

## What lands in the run directory

Everything, per (detector, fixture, threshold) cell:

    <fixture>/<detector>/t<threshold>/boxes.png   detections against reference
    <fixture>/<detector>/t<threshold>/ink.png     the coverage numbers, drawn
    index.html                                    all of it on one page
    summary.txt                                   the table, for grepping

**Read `index.html` before believing the table.** Morphology reached IoU 0.475 on
this fixture while describing a different page; a mean IoU cannot tell you
whether a detector's idea of a region matches a reader's, and the pictures can.

**The reference rectangles are only read off the browser for `invoice_0001`**,
by `tools/fixture_geometry.py`. The other four cannot be re-rendered, so that
tool snaps their rectangles onto their own ink instead — the same convention,
a weaker derivation, scoring 0.916 against the browser truth where both exist.
Their `boxes.png` says so on the image itself and their `iou` column is
parenthesised. `covered`, `crowded`, `splits` and `zones` are computed from the
ink and are trustworthy on all five.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from doc_to_html.geometry_score import ExpectedZone, score_geometry  # noqa: E402


def _reference_zones(fixture: str) -> list[ExpectedZone]:
    """Reference rectangles, off the sample document rather than off a file.

    They used to be read from `tests/fixtures/<name>.expected.json`, which was
    the serialised acceptance set and spec 0007 Thread 0 deleted. The numbers
    are the same; what is gone is the harness that scored against them. Here
    they are *rectangles to compare a detector's guesses with*, which is the
    job this probe has always had.
    """
    from tests.documents import SAMPLE_DOCUMENTS

    return [
        ExpectedZone(index=index, box=zone.bbox, kind=zone.kind.value,
                     role=zone.role.value, band=zone.band, column=zone.column)
        for index, zone in enumerate(SAMPLE_DOCUMENTS[fixture]().zones)
    ]
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import content_ink, rectify, snap_to_ink  # noqa: E402
from doc_to_html.wire import bands_from_boxes  # noqa: E402
from doc_to_html.engines.detector import (  # noqa: E402
    DETECTORS,
    Detection,
    outermost,
)
from doc_to_html.corpus import SOURCES  # noqa: E402
from tests.documents import SAMPLE_DOCUMENTS  # noqa: E402

IMAGES = {name: SOURCES[name].png for name in SAMPLE_DOCUMENTS}
"""The five documents this probe was tuned against, as name -> Source Image.

The corpus is fifteen now; this probe's recorded numbers are all against these
five, so it keeps naming them rather than silently changing what it measures.
"""

FIXTURES = REPO / "tests" / "fixtures"

EXACT_REFERENCE = "invoice_0001"
"""The one fixture whose reference rectangles were read off the browser.

`tools/fixture_geometry.py` re-renders `example/invoice.html` and takes the
client rects, checking the render still matches the screenshot pixel for pixel.
Nothing like that exists for the other four (#19), so their `iou` is scored
against boxes snapped onto their own ink and is reported as such rather than
dropped — a missing column reads as "not measured", and this is "measured
against a derived ruler", which is a different thing.
"""

THRESHOLDS = (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
"""Swept low as well as high, because one confidence is not one behaviour.

`doclayout_yolo` reports `invoice_0001`'s line-item table — both tables as one
correct region — at **0.189**, below every threshold a sane default would pick,
while calling the four header blocks 0.88-0.96. So a sweep starting at 0.2 would
have recorded that model as blind to tables when it is only unsure about them,
which is a different finding with a different fix.
"""

# BGR, because that is what the Rectified Image is and what cv2 draws in.
GREEN = (60, 160, 60)     # reference rectangles
RED = (40, 40, 220)       # detections, and unclaimed ink
GREY = (150, 150, 150)    # ink exactly one box claims
AMBER = (0, 170, 255)     # ink two or more boxes claim
BLUE = (200, 90, 0)       # detection outlines on the ink view
MAGENTA = (200, 0, 200)   # a mass of ink some box cuts through
INK_WHITE = (252, 252, 252)


@dataclass(frozen=True)
class Cell:
    """One (detector, fixture, threshold) result, scored and drawn."""

    fixture: str
    detector: str
    threshold: float
    boxes: list[BBox]
    labels: list[str]
    zones: int
    iou: float
    covered: float
    crowded: float
    splits: int
    doubles: int
    bands_match: bool
    seconds: float
    folder: Path

    @property
    def exact(self) -> bool:
        return self.fixture == EXACT_REFERENCE


def reference(fixture: str) -> tuple[list[BBox], list[tuple[int, int]]]:
    """The expected IR's rectangles and its own Band/column numbering.

    Zones without a rectangle are dropped from both lists together, so the two
    stay index-aligned. `expected_boxes` refuses this case outright, which is
    right for a caller scoring a mean it will quote; here a fixture that omits
    one rectangle should still contribute its other four rather than take the
    whole run down.
    """
    zones = [zone for zone in _reference_zones(fixture)
             if zone.box is not None]
    return (
        [zone.box for zone in zones if zone.box is not None],
        [(zone.band if zone.band is not None else -1,
          zone.column if zone.column is not None else -1) for zone in zones],
    )


def pixel_rect(box: BBox, width: int, height: int) -> tuple[int, int, int, int]:
    """A normalised box as pixel bounds, clamped and never empty."""
    left = max(0, min(width - 1, int(round(box.left * width))))
    top = max(0, min(height - 1, int(round(box.top * height))))
    right = max(left + 1, min(width, int(round(box.right * width))))
    bottom = max(top + 1, min(height, int(round(box.bottom * height))))
    return left, top, right, bottom


def claim_map(mask: np.ndarray, boxes: list[BBox]) -> np.ndarray:
    """How many boxes cover each pixel. The basis of `covered` and `crowded`."""
    height, width = mask.shape[:2]
    claims = np.zeros((height, width), dtype=np.int32)
    for box in boxes:
        left, top, right, bottom = pixel_rect(box, width, height)
        claims[top:bottom, left:right] += 1
    return claims


def crowded_share(mask: np.ndarray, boxes: list[BBox]) -> float:
    """Share of the ink that two or more boxes claim — nesting, as a number.

    The missing half of `covered`. `score_geometry` reports the ink exactly one
    box claims, which drops both when a detector misses content and when it
    stacks boxes on it; those want opposite fixes, so they are worth telling
    apart before choosing a nesting policy.
    """
    ink = mask > 0
    total = int(ink.sum())
    if total == 0:
        return 0.0
    return float(np.logical_and(ink, claim_map(mask, boxes) >= 2).sum()) / total


def cut_masses(mask: np.ndarray, boxes: list[BBox]) -> list[tuple[int, int, int, int]]:
    """Bounds of every connected mass of ink that some box crosses.

    The same test `_split_count` counts, kept as rectangles so `ink.png` can point
    at the mass rather than only report how many there were.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return []

    height, width = mask.shape[:2]
    areas = stats[:, cv2.CC_STAT_AREA]
    cut: set[int] = set()
    for box in boxes:
        left, top, right, bottom = pixel_rect(box, width, height)
        inside = np.bincount(labels[top:bottom, left:right].ravel(), minlength=count)
        partial = np.nonzero((inside > 0) & (inside < areas))[0]
        cut.update(int(label) for label in partial if label != 0)

    return [
        (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
         stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH],
         stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])
        for i in sorted(cut)
    ]


def caption(canvas: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]]) -> np.ndarray:
    """A band above the image carrying the legend, and any warning about it.

    Above rather than on top of the page, because a legend drawn over the
    document hides the thing the legend is about — and on these fixtures the top
    of the page is where the header Zone lives.
    """
    line_height = 22
    band = np.full((line_height * len(lines) + 10, canvas.shape[1], 3), 255,
                   dtype=np.uint8)
    for index, (text, colour) in enumerate(lines):
        cv2.putText(band, text, (10, 20 + index * line_height),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, colour, 1, cv2.LINE_AA)
    return np.vstack([band, canvas])


def label_box(canvas: np.ndarray, left: int, top: int, text: str,
              colour: tuple[int, int, int]) -> None:
    """A box's name, on an opaque plate so it stays readable over ink."""
    (width, height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    y = top if top - height - 6 >= 0 else top + height + 8
    cv2.rectangle(canvas, (left, y - height - 5), (left + width + 6, y + 3),
                  colour, -1)
    cv2.putText(canvas, text, (left + 3, y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (255, 255, 255), 1, cv2.LINE_AA)


def draw_boxes(image: np.ndarray, cell: Cell, want: list[BBox]) -> np.ndarray:
    """Detections against the reference, each box named and scored.

    Reference in green, detections in red. On the four fixtures whose reference
    is snapped rather than read off the browser, the warning is drawn **into the
    image**, not just written in a report next to it: these files get opened on
    their own, and a reader who reads green as truth will blame the detector for
    the derivation's slop.
    """
    canvas = image.copy()
    height, width = canvas.shape[:2]

    for box in want:
        left, top, right, bottom = pixel_rect(box, width, height)
        cv2.rectangle(canvas, (left, top), (right, bottom), GREEN, 2)

    for index, (box, name) in enumerate(zip(cell.boxes, cell.labels)):
        left, top, right, bottom = pixel_rect(box, width, height)
        cv2.rectangle(canvas, (left, top), (right, bottom), RED, 2)
        label_box(canvas, left, top, f"{index} {name}", RED)

    lines = [
        (f"{cell.detector}  {cell.fixture}  conf >= {cell.threshold:.2f}  "
         f"-  {cell.zones} boxes found, {len(want)} expected", (30, 30, 30)),
        ("red = detected", RED),
    ]
    lines.append(
        ("green = reference, read off the browser that rendered the page", GREEN)
        if cell.exact else
        ("green = reference, SNAPPED TO ITS OWN INK (0.916 vs browser truth "
         "where known) - derived, do not read as exact", GREEN)
    )
    return caption(canvas, lines)


def draw_ink(image: np.ndarray, cell: Cell) -> np.ndarray:
    """The coverage numbers as a picture, needing no reference at all.

    Every colour is one term of the table: red is the ink no box claimed, amber
    is the ink two or more claimed, magenta rings a mass some box cut through.
    Grey is the ink exactly one box claims, which is the whole of what a correct
    answer looks like here.

    This view is equally trustworthy on all five fixtures, because `content_ink`
    is the page rather than somebody's reading of it.
    """
    mask = content_ink(image)
    height, width = mask.shape[:2]
    claims = claim_map(mask, cell.boxes)
    ink = mask > 0

    canvas = np.full((height, width, 3), INK_WHITE, dtype=np.uint8)
    canvas[np.logical_and(ink, claims == 0)] = RED
    canvas[np.logical_and(ink, claims == 1)] = GREY
    canvas[np.logical_and(ink, claims >= 2)] = AMBER

    for box in cell.boxes:
        left, top, right, bottom = pixel_rect(box, width, height)
        cv2.rectangle(canvas, (left, top), (right, bottom), BLUE, 1)
    for left, top, right, bottom in cut_masses(mask, cell.boxes):
        cv2.rectangle(canvas, (left - 2, top - 2), (right + 2, bottom + 2),
                      MAGENTA, 3)

    return caption(canvas, [
        (f"{cell.detector}  {cell.fixture}  conf >= {cell.threshold:.2f}  -  "
         f"covered {cell.covered:.2f}   crowded {cell.crowded:.2f}   "
         f"splits {cell.splits}", (30, 30, 30)),
        ("red = ink no box claimed        amber = ink 2+ boxes claimed", RED),
        ("grey = ink exactly one box claimed (correct)   "
         "magenta = a mass a box cuts through", (110, 110, 110)),
    ])


def vlm_boxes(run: Path, fixture: str) -> tuple[list[BBox], list[str]] | None:
    """The boxes a previous run's VLM layout pass returned, out of its Trace.

    The control column. Reading a recorded run costs nothing, where re-asking the
    model costs the 187s `invoice_0001` took in run 50 and the 2498s
    `invoice_0002` took on its retry — and the recorded answer is the one the
    comparison is actually about.

    **The snapped boxes, where the run snapped.** `_layout` records the model's
    raw answer under `layout/detect_zones` and the moved boxes under
    `snap/snap_to_ink`, and `DTH_SNAP_ZONES` has been on since run 49 — so the
    raw answer is not what any recent Conversion used. It is also a very
    different page: on `invoice_0001` the raw boxes score IoU 0.56 / covered 0.82
    / 46 splits and the snapped ones 0.91 / 0.99 / 0. Comparing a detector
    against the raw answer would be scoring it against a baseline the project
    stopped shipping.
    """
    # Searched rather than constructed: a run directory nests its Traces under
    # `dump/<model>/<fixture>/`, and hardcoding that shape means this quietly
    # reports "no recorded boxes" the first time the dump layout moves.
    #
    # **Matched on the fixture name, with no fallback.** An earlier version fell
    # back to whatever single Trace the run held, and run 50 holds only
    # `invoice_0001` — so the control column drew `invoice_0001`'s six boxes onto
    # the other four pages and reported "6, 6, 6, 6, 6 zones", which reads as a
    # finding about the model and is an artefact of the fallback. A missing arm
    # is a gap a reader can see; a wrong arm is one they cannot.
    traces = sorted(p for p in run.rglob("trace.json") if p.parent.name == fixture)
    if not traces:
        return None

    events = json.loads(traces[0].read_text()).get("events", [])
    snapped = [e for e in events
               if e.get("stage") == "snap" and e.get("data", {}).get("after")]
    raw = [e for e in events
           if e.get("stage") == "layout" and e.get("data", {}).get("boxes")]

    if snapped:
        boxes, source = snapped[-1]["data"]["after"], "vlm+snap"
    elif raw:
        boxes, source = raw[-1]["data"]["boxes"], "vlm"
    else:
        return None

    kept = [box for box in boxes if box]
    return (
        [BBox(b["left"], b["top"], b["right"], b["bottom"]) for b in kept],
        [source] * len(kept),
    )


def measure(fixture: str, detector: str, threshold: float,
            found: list[Detection], image: np.ndarray, want: list[BBox],
            want_bands: list[tuple[int, int]], seconds: float,
            out: Path, *, snap: bool = False, outer: bool = False) -> Cell:
    """Score one cell and write its two pictures.

    `snap` moves each box onto its own ink with the pipeline's own
    `snap_to_ink`, which is the only fair way to compare against the VLM arm:
    `DTH_SNAP_ZONES` has been on since run 49, and on `invoice_0001` snapping
    took the model's raw answer from 46 splits to 0. Scoring a detector's raw
    edges against the VLM's snapped ones would credit snapping to the model.
    """
    kept = [d for d in found if d.score >= threshold]
    if outer:
        kept = outermost(kept)
    kept = sorted(kept, key=lambda d: (round(d.top, 3), d.left))
    boxes = [BBox(d.left, d.top, d.right, d.bottom) for d in kept]
    labels = [f"{d.label} {d.score:.2f}" for d in kept]
    if snap and boxes:
        boxes = snap_to_ink(image, boxes)

    score = score_geometry(boxes, want, image)
    folder = out / fixture / detector / f"t{threshold:.2f}"
    folder.mkdir(parents=True, exist_ok=True)

    cell = Cell(
        fixture=fixture, detector=detector, threshold=threshold,
        boxes=boxes, labels=labels, zones=score.zones, iou=score.iou,
        covered=score.covered, crowded=crowded_share(content_ink(image), boxes),
        splits=score.splits, doubles=score.doubles,
        bands_match=bands_from_boxes(boxes) == want_bands,
        seconds=seconds, folder=folder,
    )
    cv2.imwrite(str(folder / "boxes.png"), draw_boxes(image, cell, want))
    cv2.imwrite(str(folder / "ink.png"), draw_ink(image, cell))
    return cell


def arm_order(names: set[str]) -> list[str]:
    """Control first, then each detector raw, snapped, merged.

    Alphabetical would interleave `doclayout_yolo+outer` between the raw arm and
    `+snap`, which puts the two arms a reader most wants side by side three
    columns apart.
    """
    rank = {"": 0, "+snap": 1, "+outer": 2}
    return sorted(names, key=lambda name: (
        name != "vlm" and not name.startswith("vlm"),
        name.split("+")[0],
        rank.get("+" + name.split("+")[1] if "+" in name else "", 0),
    ))


def verdict(cells: list[Cell], fixtures: list[str]) -> list[str]:
    """Each arm at the single threshold that serves every fixture best.

    **One threshold across the corpus, not the best per page.** A detector tuned
    per fixture is a detector with a hand-fitted constant, which is the failure
    `REGION_GAP` already records — 0.04 overcounts both invoices and 0.08 welds
    `invoice_0002` into one region. What has to be true of a shipped default is
    that one number works everywhere, so that is what is reported.

    Ranked by the **worst** `covered` any fixture gets, because a layout pass is
    only as good as the page it does worst on — then by splits, then by how far
    the zone counts sit from the truth.

    **That last term is not a tiebreak, it is what stops the first two being
    gamed.** One box over the whole page scores `covered` 1.00 and `splits` 0
    and describes nothing: `heron+outer` at 0.15 reaches a perfect worst-covered
    with 3 boxes on `invoice_0001`'s 6 regions and 6 on `invoice_0002`'s 10.
    Ranking on coverage alone would have called that the winner.
    """
    lines = [
        "",
        "best single threshold per arm, ranked by the worst fixture it leaves",
        "",
        f"{'arm':<24}{'conf':>6}{'worst covered':>15}{'splits':>8}{'count err':>11}"
        f"   zones found vs expected",
    ]
    truth = [len(reference(fixture)[0]) for fixture in fixtures]

    rows = []
    for arm in {cell.detector for cell in cells}:
        best: tuple[float, float, int, int, str] | None = None
        for threshold in sorted({c.threshold for c in cells if c.detector == arm}):
            at = sorted([c for c in cells
                         if c.detector == arm and c.threshold == threshold],
                        key=lambda c: fixtures.index(c.fixture))
            if len(at) != len(fixtures):
                continue
            worst = min(c.covered for c in at)
            splits = sum(c.splits for c in at)
            error = sum(abs(c.zones - want) for c, want in zip(at, truth))
            counts = ", ".join(str(c.zones) for c in at)
            # Rounded to what the row prints. Unrounded, a 0.9997 loses to a
            # 1.0000 that both display as 1.00, and the table then recommends a
            # threshold whose advantage a reader cannot see in it.
            rank = (round(worst, 2), -splits, -error)
            if best is None or rank > (round(best[1], 2), -best[2], -best[3]):
                best = (threshold, worst, splits, error, counts)
        if best is not None:
            rows.append(((round(best[1], 2), -best[2], -best[3]), arm, best))

    for _, arm, (threshold, worst, splits, error, counts) in sorted(
            rows, key=lambda row: row[0], reverse=True):
        lines.append(f"{arm:<24}{threshold:>6.2f}{worst:>15.2f}{splits:>8}"
                     f"{error:>11}   {counts}")
    lines.append("")
    lines.append(f"{'expected':<24}{'':>6}{'':>15}{'':>8}{'':>11}   "
                 + ", ".join(str(want) for want in truth))
    return lines


def table(cells: list[Cell]) -> list[str]:
    """The sweep as text. `iou` is parenthesised where the reference is soft."""
    lines = [
        f"{'fixture':<22}{'detector':<16}{'conf':>6}{'zones':>7}{'iou':>10}"
        f"{'covered':>9}{'crowded':>9}{'splits':>8}{'doubles':>9}{'bands':>7}",
    ]
    for cell in cells:
        shown = f"{cell.iou:.3f}" if cell.exact else f"({cell.iou:.3f})"
        lines.append(
            f"{cell.fixture:<22}{cell.detector:<16}{cell.threshold:>6.2f}"
            f"{cell.zones:>7}{shown:>10}{cell.covered:>9.2f}{cell.crowded:>9.2f}"
            f"{cell.splits:>8}{cell.doubles:>9}"
            f"{'yes' if cell.bands_match else 'no':>7}"
        )
    return lines


def contact_sheet(cells: list[Cell], out: Path, expected: dict[str, int]) -> None:
    """One page holding every picture, grouped so the arms line up.

    Fixtures down the page, thresholds down each fixture's table, detectors
    across it — so the two candidates are compared at the same page, the same
    threshold and the same scale, side by side, rather than by opening files in
    turn and remembering the last one.
    """
    detectors = arm_order({cell.detector for cell in cells})
    parts = [
        "<title>Layout detector bakeoff</title>",
        "<style>",
        "body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;"
        "padding:24px;background:#fbfbfa;color:#1a1a19}",
        "h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 4px;"
        "border-top:1px solid #ddd;padding-top:20px}",
        "p.note{color:#57534e;max-width:76ch;margin:4px 0}",
        "table{border-collapse:collapse;width:100%;margin-top:12px}",
        "td,th{vertical-align:top;padding:8px;border-bottom:1px solid #e7e5e4;"
        "text-align:left}",
        "th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;"
        "color:#57534e}",
        "img{width:100%;max-width:560px;display:block;border:1px solid #d6d3d1;"
        "border-radius:4px;margin-bottom:8px}",
        "code{background:#f0efed;padding:1px 5px;border-radius:3px;"
        "font-size:12px}",
        ".m{font-size:12px;color:#44403c;margin:0 0 8px}",
        ".bad{color:#b91c1c;font-weight:600}",
        "</style>",
        "<h1>Layout detector bakeoff</h1>",
        "<p class=note><b>Read the pictures before the numbers.</b> Morphology "
        "scored IoU 0.475 on <code>invoice_0001</code> while describing a "
        "different page. A mean IoU cannot say whether a detector's idea of a "
        "region matches a reader's; these can.</p>",
        "<p class=note><b>boxes.png</b> — red is what the detector found, green "
        "is the reference. <b>ink.png</b> — red is ink no box claimed, amber is "
        "ink two or more boxes claimed, grey is ink exactly one box claimed "
        "(correct), magenta rings a mass of ink some box cuts through.</p>",
        "<p class=note>Only <code>invoice_0001</code> has an exact reference, "
        "read off the browser that rendered it. The other four cannot be "
        "re-rendered, so their rectangles are snapped onto their own ink "
        "instead \u2014 same convention, weaker derivation \u2014 and their "
        "<code>iou</code> is parenthesised with the warning drawn on the image. "
        "Everything derived from the ink is trustworthy on all five.</p>",
    ]

    for fixture in sorted({cell.fixture for cell in cells}):
        parts.append(f"<h2>{html.escape(fixture)} "
                     f"<span class=m>{expected[fixture]} regions expected</span></h2>")
        parts.append("<table><tr><th style='width:70px'>conf</th>"
                     + "".join(f"<th>{html.escape(d)}</th>" for d in detectors)
                     + "</tr>")
        rows = sorted({cell.threshold for cell in cells if cell.fixture == fixture})
        for threshold in rows:
            parts.append(f"<tr><td><b>{threshold:.2f}</b></td>")
            for detector in detectors:
                match = [c for c in cells if c.fixture == fixture
                         and c.detector == detector and c.threshold == threshold]
                if not match:
                    parts.append("<td>—</td>")
                    continue
                cell = match[0]
                miss = "" if cell.covered >= 0.95 else " class=bad"
                where = cell.folder.relative_to(out).as_posix()
                parts.append(
                    f"<td><p class=m><b>{cell.zones}</b> boxes &nbsp; "
                    f"<span{miss}>covered {cell.covered:.2f}</span> &nbsp; "
                    f"crowded {cell.crowded:.2f} &nbsp; splits {cell.splits} "
                    f"&nbsp; iou {cell.iou:.3f}"
                    f"{'' if cell.exact else ' (soft)'}</p>"
                    f"<img src='{where}/boxes.png' loading=lazy>"
                    f"<img src='{where}/ink.png' loading=lazy></td>"
                )
            parts.append("</tr>")
        parts.append("</table>")

    (out / "index.html").write_text("\n".join(parts) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="58-detector-bakeoff")
    parser.add_argument("--fixtures", default=",".join(IMAGES),
                        help="comma-separated fixture names")
    parser.add_argument("--detectors", default=",".join(DETECTORS))
    parser.add_argument("--thresholds", default=",".join(str(t) for t in THRESHOLDS))
    parser.add_argument("--vlm-from", type=Path, default=None,
                        help="a debug/runs/<label> directory, to draw its "
                             "recorded VLM boxes as a third arm")
    parser.add_argument("--no-snap", dest="snap", action="store_false",
                        help="score raw detector edges only. On by default, "
                             "because the VLM arm is snapped and the pipeline "
                             "has snapped since run 49")
    parser.add_argument("--no-outer", dest="outer", action="store_false",
                        help="drop the +outer arm, which keeps only boxes no "
                             "larger box contains, then snaps")
    args = parser.parse_args()

    out = REPO / "debug" / "runs" / args.label
    if out.exists():
        print(f"refusing to overwrite {out} — pick a new label", file=sys.stderr)
        return 1
    out.mkdir(parents=True)

    fixtures = [f.strip() for f in args.fixtures.split(",") if f.strip()]
    wanted = [d.strip() for d in args.detectors.split(",") if d.strip()]
    thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]

    cells: list[Cell] = []
    expected: dict[str, int] = {}
    timings: list[str] = []

    for fixture in fixtures:
        image = rectify(REPO / IMAGES[fixture]).image
        want, want_bands = reference(fixture)
        expected[fixture] = len(want)
        height, width = image.shape[:2]
        print(f"{fixture}  {width}x{height}  {len(want)} regions expected")

        for name in wanted:
            started = time.perf_counter()
            found = DETECTORS[name].detect(image)
            seconds = time.perf_counter() - started
            timings.append(f"  {name:<16}{fixture:<22}{seconds:6.2f}s  "
                           f"{len(found)} raw detections")
            print(f"  {name:<16}{seconds:6.2f}s  {len(found)} raw")
            for threshold in thresholds:
                cells.append(measure(fixture, name, threshold, found, image,
                                     want, want_bands, seconds, out))
                if args.snap:
                    cells.append(measure(fixture, f"{name}+snap", threshold,
                                         found, image, want, want_bands,
                                         seconds, out, snap=True))
                if args.outer:
                    cells.append(measure(fixture, f"{name}+outer", threshold,
                                         found, image, want, want_bands,
                                         seconds, out, snap=True, outer=True))

        if args.vlm_from is not None:
            recorded = vlm_boxes(args.vlm_from, fixture)
            if recorded is None:
                print(f"  vlm             no recorded boxes in {args.vlm_from}")
            else:
                boxes, labels = recorded
                as_detections = [
                    Detection(b.left, b.top, b.right, b.bottom, label, 1.0)
                    for b, label in zip(boxes, labels)
                ]
                cells.append(measure(fixture, "vlm", min(thresholds),
                                     as_detections, image, want, want_bands,
                                     0.0, out))
                print(f"  vlm             {len(boxes)} boxes from "
                      f"{args.vlm_from.name}")

    report = "\n".join([
        f"detector bakeoff — {args.label}",
        "",
        "iou in parentheses is scored against reference rectangles snapped onto",
        "their own ink, not read off a browser. covered/crowded/splits come from",
        "the ink and are trustworthy everywhere. covered counts ink exactly one",
        "box claims; crowded counts ink two or more claim.",
        "",
        *verdict(cells, fixtures),
        "",
        *table(cells),
        "",
        "inference, once per page — the sweep is a filter over one forward pass",
        *timings,
    ])
    (out / "summary.txt").write_text(report + "\n")
    contact_sheet(cells, out, expected)

    print()
    print(report)
    print(f"\nwritten to {out}\nopen {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
