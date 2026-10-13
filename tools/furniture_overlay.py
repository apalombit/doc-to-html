"""Draw every furniture record on its page — spec 0012, G3, §4b item 3.

    python tools/furniture_overlay.py <out dir> [--documents a,b]

One PNG per document: the rectified page, each record drawn over it in a
colour by kind — **rules red, dashed and dotted rules orange, double rules
magenta, frames blue, fills green, hatched fills cyan** — and a line per
record in `records.txt`. It reads the pages only, with no model and no run,
so the finder is judged by eye before anything is drawn from it, as
`tools/locate_overlay.py` does for `locate`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html import furniture  # noqa: E402
from doc_to_html.corpus import SOURCES, SWEEP  # noqa: E402
from doc_to_html.preprocess import _cv2, rectify  # noqa: E402

COLOURS = {"rule": (0, 0, 230), "dashed": (0, 140, 255), "dotted": (0, 140, 255),
           "double": (200, 0, 200), "frame": (230, 90, 0), "fill": (0, 170, 0),
           "hatched": (200, 200, 0)}
"""BGR, by the record's style where that is telling, else by its kind."""


def overlay(name: str, out: Path) -> list[str]:
    cv2 = _cv2()
    rectified = rectify(REPO / SOURCES[name].png)
    plain = rectified.plain if rectified.plain is not None else rectified.image
    found = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    picture = np.asarray(plain).copy()
    if rectified.inverted:
        picture = 255 - picture
    faded = (picture.astype(np.int32) * 2 + 255) // 3
    canvas = faded.astype(np.uint8)
    height, width = canvas.shape[:2]
    lines = []
    for index, item in enumerate(found):
        box = item.bbox
        x0, y0 = int(box.left * width), int(box.top * height)
        x1, y1 = int(np.ceil(box.right * width)), int(np.ceil(box.bottom * height))
        colour = COLOURS.get(item.style if item.style != "solid" else item.kind,
                             COLOURS["rule"])
        if item.kind == "rule":
            cv2.rectangle(canvas, (x0 - 1, y0 - 1), (x1, y1), colour, -1)
        else:
            cv2.rectangle(canvas, (x0, y0), (x1 - 1, y1 - 1), colour, 2)
        cv2.putText(canvas, str(index), (x0 + 2, max(10, y0 - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, colour, 1, cv2.LINE_AA)
        lines.append(
            f"{index:3} {item.kind:5} {item.style:7} "
            f"x {x0}-{x1} y {y0}-{y1} "
            f"{item.thickness * width:.1f}px rgb{item.color}"
            + (f" / rgb{item.second}" if item.second else "")
            + (f" period {item.period * width:.1f}px" if item.period else ""))
    cv2.imwrite(str(out / f"{name}.png"), canvas)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--documents", default="")
    args = parser.parse_args()
    names = [n.strip() for n in args.documents.split(",") if n.strip()] or list(SWEEP)
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    for name in names:
        lines = overlay(name, args.out)
        report.append(f"== {name}: {len(lines)} records")
        report += [f"   {line}" for line in lines]
        print(f"{name:<22} {len(lines)} records")
    (args.out / "records.txt").write_text("\n".join(report) + "\n")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
