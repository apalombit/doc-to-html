"""The twins: each corpus page photographed, beside its truth — spec 0018, B0.

    python tools/twins.py <out>                       # draw every twin and its truth
    python tools/twins.py <out> --check               # measure rectify and the layout front
    python tools/twins.py <out> --check --documents ticket_0020,cv_0013

A twin is a corpus picture — the page as shot — set on a desk the way a phone
photographs it:
- `t0.5`, `t1.5`, `t3`: turned 0.5°, 1.5° and 3° counter-clockwise;
- `shade`: the 1.5° turn under a soft gradient of light, its shadow on the desk;
- `persp`: a mild perspective, the top edge drawn in 3% a side, turned 1°.

The desk is slate, (60, 65, 72), with a `MARGIN` of 50px. **Every twin is drawn
by one homography, with cubic interpolation, so its truth is exact**: where the
page's corner pixels land is that homography applied to them, in the pixel
coordinates `warp_to_quad` maps a quadrilateral from.

`--check` is model-free. For each twin it reports:
- **`rectify` against the truth**: the worst corner's error in pixels; the
  residual tilt, the rotation `cv2.findTransformECC` (`MOTION_EUCLIDEAN`) needs
  to carry the straightened page onto the page as shot; the MAD, their mean
  grey difference once aligned; and the share of the page's ink that falls
  outside the outline. Three ways: through `rectify`'s own outline, and
  through the true one warped linearly, as `warp_to_quad` does, and cubic —
  the bound C1 to C3 work towards.
- **the layout front against the page as shot**: the shot page's Zones a twin
  keeps at IoU 0.5 or more, those it reads inside one larger Zone, the rest;
  and whether the structure regions are the same.
  Every box is carried back into the shot picture's frame first, through
  `rectify`'s own warp and turn and the twin's truth, so a page `rectify`
  leaves on its desk is not counted as lost for its coordinates. And the
  Zones kept once more with the twin straightened through its true corners:
  what is lost there is lost to the resampling, not to the outline.

`ticket_0020` and `receipt_0010` are photographs already, on desks of their
own: their truth is the picture's corners, not the paper's, so `rectify` is
not measured on them; the layout front is.

The pictures go under the `<out>` directory, `debug/twins/` by habit; this tool
and its parameters are what is committed. Run twice, `--check` writes the same
bytes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.corpus import SOURCES, names  # noqa: E402
from doc_to_html.engines.transport import Response  # noqa: E402
from doc_to_html.ir import BBox, Document  # noqa: E402
from doc_to_html.orchestrator import Conversion, EngineSet, default_engines  # noqa: E402
from doc_to_html.preprocess import (INK_LEVEL, _cv2, deskew, ground_is_dark,  # noqa: E402
                                    page_outline, skew_angle)

DESK = (60, 65, 72)
"""The desk's colour, RGB: slate, darker than any corpus paper."""

MARGIN = 50
"""Desk on every side of the turned page, in pixels."""

TWINS: dict[str, dict[str, float]] = {
    "t0.5": {"turn": 0.5},
    "t1.5": {"turn": 1.5},
    "t3": {"turn": 3.0},
    "shade": {"turn": 1.5, "light": 0.12, "shadow": 0.45},
    "persp": {"turn": 1.0, "keystone": 0.03},
}
"""Each twin's parameters. `light` is how far the light falls, as a share,
from the top-left corner to the bottom-right — 0.12 keeps the darkest paper
above `INK_LEVEL`. `shadow` is how much of the desk's light the page's shadow
takes, cast `SHADOW_OFFSET` down and right and blurred by `SHADOW_BLUR`.
`keystone` draws the top corners in by that share of the width a side."""

SHADOW_OFFSET = (10, 12)
SHADOW_BLUR = 8.0

PHOTOGRAPHS = {"ticket_0020", "receipt_0010"}
"""Pages shot as photographs already, whose paper's corners are not known."""

KEPT_IOU = 0.5
MERGED = 0.9


class Refused(RuntimeError):
    """What every model call gets, as in `tools/layout_front.py`."""


def refuse(*, model: str, pass_name: str, prompt: str, images: list[bytes],
           schema: dict[str, object], num_ctx: int) -> Response:
    raise Refused(f"no model: {pass_name}")


# -- drawing -------------------------------------------------------------------

def corners(width: int, height: int) -> np.ndarray:
    """The page's corner pixels, top-left first, clockwise."""
    return np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
                    dtype=np.float64)


def homography(width: int, height: int, twin: dict[str, float]
               ) -> tuple[np.ndarray, tuple[int, int]]:
    """The map from the page as shot onto the twin's picture, and its size."""
    cv2 = _cv2()
    source = corners(width, height)
    target = source.copy()
    inset = twin.get("keystone", 0.0) * (width - 1)
    target[0, 0] += inset
    target[1, 0] -= inset
    middle = source.mean(axis=0)
    turn = math.radians(twin["turn"])
    # Counter-clockwise on the picture, whose y runs down.
    rotation = np.array([[math.cos(turn), math.sin(turn)],
                         [-math.sin(turn), math.cos(turn)]])
    target = (target - middle) @ rotation.T + middle
    target += MARGIN - target.min(axis=0)
    size = (int(math.ceil(target[:, 0].max())) + MARGIN + 1,
            int(math.ceil(target[:, 1].max())) + MARGIN + 1)
    matrix = cv2.getPerspectiveTransform(source.astype(np.float32), target.astype(np.float32))
    return matrix.astype(np.float64), size


def draw(page: np.ndarray, twin: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """The twin's picture, BGR, and its truth: where the page's corners land."""
    cv2 = _cv2()
    height, width = page.shape[:2]
    matrix, size = homography(width, height, twin)
    desk = tuple(float(v) for v in DESK[::-1])
    picture = cv2.warpPerspective(page, matrix, size, flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=desk)
    if "shadow" in twin:
        held = cv2.warpPerspective(np.ones((height, width), np.float32), matrix, size,
                                   flags=cv2.INTER_LINEAR)
        shift = np.array([[1, 0, SHADOW_OFFSET[0]], [0, 1, SHADOW_OFFSET[1]]], np.float32)
        cast = cv2.GaussianBlur(cv2.warpAffine(held, shift, size), (0, 0), SHADOW_BLUR)
        dimmed = 1.0 - twin["shadow"] * cast * (1.0 - held)
        picture = picture.astype(np.float64) * dimmed[:, :, None]
    if "light" in twin:
        rows, columns = np.mgrid[0:size[1], 0:size[0]]
        fall = (columns / max(size[0] - 1, 1) + rows / max(size[1] - 1, 1)) / 2
        picture = picture.astype(np.float64) * (1.0 - twin["light"] * fall)[:, :, None]
    picture = np.clip(np.round(picture), 0, 255).astype(np.uint8)
    truth = cv2.perspectiveTransform(corners(width, height)[None], matrix)[0]
    return picture, truth


def build(out: Path, documents: list[str]) -> None:
    cv2 = _cv2()
    for name in documents:
        page = cv2.imread(str(REPO / SOURCES[name].png), cv2.IMREAD_COLOR)
        folder = out / name
        folder.mkdir(parents=True, exist_ok=True)
        truth: dict[str, Any] = {}
        for label, twin in TWINS.items():
            picture, found = draw(page, twin)
            cv2.imwrite(str(folder / f"{label}.png"), picture)
            truth[label] = {"corners": [[round(float(v), 3) for v in point] for point in found],
                            **twin}
        (folder / "truth.json").write_text(json.dumps(truth, indent=1) + "\n")
        print(f"{name:22} {len(TWINS)} twins")


# -- measuring -----------------------------------------------------------------

def straightened(picture: np.ndarray, quad: np.ndarray | None, *,
                 cubic: bool = False) -> np.ndarray:
    """The page as `rectify` straightens it, without equalising: warp to the
    quadrilateral, deskew — on the page turned over where it is printed light
    on dark — and back to the page's own polarity, so it can be laid on the
    page as shot."""
    cv2 = _cv2()
    flat = picture
    if quad is not None:
        top_left, top_right, bottom_right, bottom_left = quad
        width = int(round(max(np.linalg.norm(top_right - top_left),
                              np.linalg.norm(bottom_right - bottom_left))))
        height = int(round(max(np.linalg.norm(bottom_left - top_left),
                               np.linalg.norm(bottom_right - top_right))))
        target = corners(width, height).astype(np.float32)
        matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
        flat = cv2.warpPerspective(picture, matrix, (width, height),
                                   flags=cv2.INTER_CUBIC if cubic else cv2.INTER_LINEAR)
    dark = ground_is_dark(flat)
    level = deskew(255 - flat if dark else flat)
    return 255 - level if dark else level


def against(shot: np.ndarray, straight: np.ndarray) -> tuple[float | None, float | None]:
    """The residual tilt, in degrees, and the MAD once aligned — or None
    where ECC does not converge."""
    cv2 = _cv2()
    height, width = shot.shape[:2]
    if straight.shape[:2] != (height, width):
        straight = cv2.resize(straight, (width, height), interpolation=cv2.INTER_LINEAR)
    one = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY).astype(np.float32)
    other = cv2.cvtColor(straight, cv2.COLOR_BGR2GRAY).astype(np.float32)
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
    try:
        _, warp = cv2.findTransformECC(one, other, warp, cv2.MOTION_EUCLIDEAN, criteria, None, 5)
    except cv2.error:
        return None, None
    aligned = cv2.warpAffine(other, warp, (width, height),
                             flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                             borderMode=cv2.BORDER_REPLICATE)
    tilt = math.degrees(math.atan2(float(warp[1, 0]), float(warp[0, 0])))
    return tilt, float(np.abs(aligned - one).mean())


def outside(shot: np.ndarray, truth: np.ndarray, quad: np.ndarray | None,
            size: tuple[int, int]) -> float:
    """The share of the page's ink — dark on the page as shot, under
    `INK_LEVEL` — that the outline leaves outside it, in the twin's picture
    of `size`."""
    cv2 = _cv2()
    grey = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY)
    if ground_is_dark(shot):
        grey = 255 - grey
    rows, columns = np.nonzero(grey < INK_LEVEL)
    if not len(rows) or quad is None:
        return 0.0
    height, width = shot.shape[:2]
    matrix = cv2.getPerspectiveTransform(corners(width, height).astype(np.float32),
                                         truth.astype(np.float32))
    points = np.stack([columns, rows], axis=1).astype(np.float64)[None]
    placed = np.round(cv2.perspectiveTransform(points, matrix)[0]).astype(int)
    held = np.zeros((size[1], size[0]), np.uint8)
    cv2.fillPoly(held, [np.round(quad).astype(np.int32)], 1)
    x, y = placed[:, 0], placed[:, 1]
    inside = (x >= 0) & (x < size[0]) & (y >= 0) & (y < size[1])
    within = np.zeros(len(placed), bool)
    within[inside] = held[y[inside], x[inside]] > 0
    return float((~within).mean())


def engines() -> EngineSet:
    live = default_engines(load())
    return EngineSet(layout=live.layout,
                     classify=replace(live.classify, transport=refuse),  # type: ignore[type-var]
                     extract=replace(live.extract, transport=refuse),  # type: ignore[type-var]
                     audit=replace(live.audit, transport=refuse))  # type: ignore[type-var]


def layout(path: Path, engine_set: EngineSet) -> Document:
    return Conversion(source=path, engines=engine_set).run()


def frame(picture: np.ndarray) -> np.ndarray:
    """The map from a picture onto the page `rectify` makes of it: the
    outline's warp, then deskew's turn — `rectify`'s own geometry, step by
    step, so a box on the rectified page can be carried back."""
    cv2 = _cv2()
    outline = page_outline(picture)
    matrix = np.eye(3)
    flat = picture
    if outline is not None:
        quad = np.asarray(outline.quad, dtype=np.float64)
        top_left, top_right, bottom_right, bottom_left = quad
        width = int(round(max(np.linalg.norm(top_right - top_left),
                              np.linalg.norm(bottom_right - bottom_left))))
        height = int(round(max(np.linalg.norm(bottom_left - top_left),
                               np.linalg.norm(bottom_right - top_right))))
        matrix = cv2.getPerspectiveTransform(
            quad.astype(np.float32), corners(width, height).astype(np.float32)).astype(np.float64)
        flat = cv2.warpPerspective(picture, matrix, (width, height))
    angle = skew_angle(255 - flat if ground_is_dark(flat) else flat)
    if abs(angle) >= 0.25:
        height, width = flat.shape[:2]
        turn = np.vstack([cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0),
                          [0.0, 0.0, 1.0]])
        matrix = turn @ matrix
    return matrix


def carried(document: Document, onto: np.ndarray, size: tuple[int, int]) -> list[BBox]:
    """Each Zone's box carried from the rectified page by `onto`, a map from
    it to the picture of the page as shot, normalised to that picture's
    `size` — the frame every twin is compared in."""
    cv2 = _cv2()
    width, height = document.source.rectified_width, document.source.rectified_height
    boxes = []
    for zone in document.zones:
        if zone.bbox is None or not width or not height:
            continue
        b = zone.bbox
        points = np.array([[[b.left * width, b.top * height], [b.right * width, b.top * height],
                            [b.right * width, b.bottom * height],
                            [b.left * width, b.bottom * height]]])
        x, y = cv2.perspectiveTransform(points, onto)[0].T
        boxes.append(BBox(float(x.min()) / size[0], float(y.min()) / size[1],
                          float(x.max()) / size[0], float(y.max()) / size[1]))
    return boxes


def _iou(a: BBox, b: BBox) -> float:
    across = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    down = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    shared = across * down
    union = ((a.right - a.left) * (a.bottom - a.top)
             + (b.right - b.left) * (b.bottom - b.top) - shared)
    return shared / union if union > 0 else 0.0


def kept(shot: list[BBox], twin: list[BBox]) -> str:
    """How the shot page's Zones fare on the twin: `kept/total`, and after
    a `+` how many more lie inside one larger Zone of the twin (`MERGED`) —
    read together, not lost — and after a `-` how many neither."""
    held = merged = 0
    for box in shot:
        if any(_iou(box, other) >= KEPT_IOU for other in twin):
            held += 1
        elif any(_inside(box, other) >= MERGED for other in twin):
            merged += 1
    rest = len(shot) - held - merged
    return f"{held}/{len(shot)}" + (f" +{merged}" if merged else "") + (f" -{rest}" if rest else "")


def _inside(box: BBox, other: BBox) -> float:
    """The share of `box` that lies inside `other`."""
    across = max(0.0, min(box.right, other.right) - max(box.left, other.left))
    down = max(0.0, min(box.bottom, other.bottom) - max(box.top, other.top))
    area = (box.right - box.left) * (box.bottom - box.top)
    return across * down / area if area > 0 else 0.0


def regions(document: Document) -> list[str]:
    return [f"{r.flow.value}{len(r.splits) + 1 if r.splits else ''}"
            + (f"x{r.rows}" if r.rows > 1 else "") for r in document.regions]


def same_structure(shot: Document, twin: Document) -> bool:
    """The same flows in the same order, each with as many lanes and rows.
    The splits' places are not compared: they are taken in each page's own
    frame, and the Zones kept already say where things went."""
    if len(shot.regions) != len(twin.regions):
        return False
    return all(a.flow is b.flow and a.rows == b.rows and len(a.splits) == len(b.splits)
               for a, b in zip(shot.regions, twin.regions))


def _r(value: float | None, places: int) -> float | None:
    return None if value is None else round(value, places)


def _homography_of(truth: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """The map from the page as shot, of `size`, onto its twin: the one
    that carries the page's corners to `truth`."""
    cv2 = _cv2()
    matrix: np.ndarray = cv2.getPerspectiveTransform(corners(*size).astype(np.float32),
                                                     truth.astype(np.float32))
    return matrix.astype(np.float64)


def check(out: Path, documents: list[str]) -> dict[str, Any]:
    cv2 = _cv2()
    engine_set = engines()
    report: dict[str, Any] = {}
    for name in documents:
        shot_path = REPO / SOURCES[name].png
        shot = cv2.imread(str(shot_path), cv2.IMREAD_COLOR)
        size = (shot.shape[1], shot.shape[0])
        as_shot = layout(shot_path, engine_set)
        shot_boxes = carried(as_shot, np.linalg.inv(frame(shot)), size)
        truth = json.loads((out / name / "truth.json").read_text())
        rows: dict[str, Any] = {}
        for label in TWINS:
            path = out / name / f"{label}.png"
            picture = cv2.imread(str(path), cv2.IMREAD_COLOR)
            true = np.array(truth[label]["corners"], dtype=np.float64)
            row: dict[str, Any] = {}
            if name not in PHOTOGRAPHS:
                outline = page_outline(picture)
                quad = None if outline is None else np.asarray(outline.quad, dtype=np.float64)
                row["corner_px"] = (None if quad is None else
                                    round(float(np.linalg.norm(quad - true, axis=1).max()), 2))
                row["outside"] = round(outside(shot, true, quad, picture.shape[1::-1]), 4)
                for key, which, cubic in (("found", quad, False), ("true", true, False),
                                          ("true_cubic", true, True)):
                    tilt, mad = against(shot, straightened(picture, which, cubic=cubic))
                    row[key] = {"tilt": _r(tilt, 3), "mad": _r(mad, 2)}
            twin = layout(path, engine_set)
            back = np.linalg.inv(_homography_of(true, size)) @ np.linalg.inv(frame(picture))
            row["zones_kept"] = kept(shot_boxes, carried(twin, back, size))
            # The same twin straightened through its true corners: what is
            # still lost there is lost to the resampling, not to the outline.
            back_to_shot = cv2.warpPerspective(picture, np.linalg.inv(_homography_of(true, size)),
                                               size, flags=cv2.INTER_CUBIC)
            straight_path = out / name / f"_true_{label}.png"
            cv2.imwrite(str(straight_path), back_to_shot)
            through_true = layout(straight_path, engine_set)
            row["zones_kept_true"] = kept(
                shot_boxes, carried(through_true, np.linalg.inv(frame(back_to_shot)), size))
            straight_path.unlink()
            row["structure"] = "same" if same_structure(as_shot, twin) else \
                f"{'+'.join(regions(as_shot)) or '-'} -> {'+'.join(regions(twin)) or '-'}"
            rows[label] = row
        report[name] = rows
        print(name, " ".join(f"{label}:{row['zones_kept']}|{row['zones_kept_true']}"
                             for label, row in rows.items()),
              flush=True)
    return report


def table(report: dict[str, Any]) -> str:
    lines = ["| page | twin | corner px | outside | found tilt / MAD | true tilt / MAD "
             "| true cubic | Zones kept | through true corners | structure |",
             "|---|---|---|---|---|---|---|---|---|---|"]

    def pair(cell: dict[str, Any] | None) -> str:
        if not cell:
            return "—"
        tilt = "—" if cell["tilt"] is None else f"{cell['tilt']:+.3f}°"
        mad = "—" if cell["mad"] is None else f"{cell['mad']:.2f}"
        return f"{tilt} / {mad}"

    for name, rows in report.items():
        for label, row in rows.items():
            corner = row.get("corner_px")
            lines.append(
                f"| {name} | {label} | {'—' if corner is None else corner} "
                f"| {row.get('outside', '—')} | {pair(row.get('found'))} "
                f"| {pair(row.get('true'))} | {pair(row.get('true_cubic'))} "
                f"| {row['zones_kept']} | {row['zones_kept_true']} | {row['structure']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--check", action="store_true",
                        help="measure rectify and the layout front on twins already drawn")
    parser.add_argument("--documents", default="all",
                        help="a corpus split, 'all', or a comma-separated list")
    args = parser.parse_args(argv)
    documents = list(names(args.documents))
    if not args.check:
        build(args.out, documents)
        return 0
    report = check(args.out, documents)
    (args.out / "check.json").write_text(json.dumps(report, indent=1) + "\n")
    (args.out / "check.md").write_text(table(report))
    print(f"-> {args.out / 'check.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
