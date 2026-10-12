"""Draw every located Cell on its page — spec 0011, step 2's check.

    python tools/locate_overlay.py debug/runs/<label>
    python tools/locate_overlay.py tests/frozen/s5-result --out /tmp/overlays \\
        --documents form_0007,menu_0012

For each document: the Rectified Image — the frame `Cell.bbox` is in — with
every placed Cell's box drawn and labelled with its first word; and every
unplaced Cell listed under the picture. **The check is the picture**: every box should
sit on its own words.

It also prints, per document, how many Cells were placed, and how many of
those whose text is one text node of the source HTML land on that node, read
off `projection.project` — a diagnostic, not a gate. It is only meaningful
where the screenshot is its own HTML: the ten authored documents and
`invoice_0001`; `CLAUDE.md` says why the other four differ.

A run directory's IRs already carry the boxes. A frozen directory's predate
step 2, so it is located here first, with today's `locate.locate`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent / "src"))
sys.path.insert(0, str(TOOLS))

from doc_to_html import locate as locate_module  # noqa: E402
from doc_to_html.corpus import SOURCES  # noqa: E402
from doc_to_html.ir import BBox, Document  # noqa: E402
from doc_to_html.preprocess import _cv2, rectify  # noqa: E402
from doc_to_html.projection import project  # noqa: E402
from rederive import documents_in  # noqa: E402
from remeasure_style import ir_of  # noqa: E402

REPO = TOOLS.parent


def _overlap(box: BBox, rect: BBox) -> float:
    return box.overlap_ratio(rect)


def landed(name: str, document: Document) -> tuple[int, int]:
    """How many placed Cells matching one source text node land on it."""
    source = SOURCES[name]
    width, height = document.source.width, document.source.height
    shown = project(source.html_path(REPO).read_text(encoding="utf-8"),
                    width=width)
    runs: dict[str, list[BBox]] = {}
    for run in shown.runs:
        left, top, right, bottom = run.rect
        runs.setdefault(locate_module.fold(run.text), []).append(
            BBox(left / width, top / height, right / width, bottom / height))
    checkable = hit = 0
    for zone in document.zones:
        for cell, _ in locate_module.cells_of(zone):
            key = locate_module.fold(cell.text)
            if cell.bbox is None or not key or key not in runs:
                continue
            checkable += 1
            hit += any(_overlap(cell.bbox, rect) >= 0.5 for rect in runs[key])
    return hit, checkable


def draw(name: str, document: Document, out: Path) -> None:
    cv2 = _cv2()
    rectified = rectify(REPO / SOURCES[name].png)
    page = (rectified.plain if rectified.plain is not None
            else rectified.image).copy()
    height, width = page.shape[:2]
    scale = max(1, int(round(1400 / width)))
    page = cv2.resize(page, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_NEAREST)
    missing = []
    for zone in document.zones:
        for cell, _ in locate_module.cells_of(zone):
            if cell.bbox is None:
                if cell.text.strip():
                    missing.append(cell.text.strip())
                continue
            b = cell.bbox
            colour = (0, 0, 220)
            p1 = (int(b.left * width * scale), int(b.top * height * scale))
            p2 = (int(b.right * width * scale), int(b.bottom * height * scale))
            cv2.rectangle(page, p1, p2, colour, 1)
            label = cell.text.split()[0] if cell.text.split() else ""
            cv2.putText(page, label[:14], (p1[0], max(9, p1[1] - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, colour, 1, cv2.LINE_AA)
    if missing:
        band = np.full((16 * (len(missing) + 1), page.shape[1], 3), 255, np.uint8)
        cv2.putText(band, f"unplaced ({len(missing)}):", (6, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        for index, text in enumerate(missing):
            cv2.putText(band, text[:120], (6, 12 + 16 * (index + 1)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 180), 1, cv2.LINE_AA)
        page = np.vstack([page, band])
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / f"{name}.png"), page)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="a run or a frozen directory")
    parser.add_argument("--out", type=Path, default=None,
                        help="default: <source>/_locate")
    parser.add_argument("--documents", default="")
    parser.add_argument("--model", default="qwen3-vl:4b")
    args = parser.parse_args()

    root = args.source.resolve()
    out = (args.out or root / "_locate").resolve()
    wanted = {n.strip() for n in args.documents.split(",") if n.strip()}
    frozen = (root / "documents").is_dir()
    print(f"{'document':<22}{'placed':>12}{'on its node':>14}")
    for name, html in documents_in(root, args.model):
        if (wanted and name not in wanted) or name not in SOURCES:
            continue
        document = ir_of(html.read_text(encoding="utf-8"))
        if document is None:
            continue
        if frozen:
            rectified = rectify(REPO / SOURCES[name].png)
            locate_module.locate(rectified.plain if rectified.plain is not None
                                 else rectified.image, document)
        cells = [cell for zone in document.zones
                 for cell, _ in locate_module.cells_of(zone)
                 if cell.text.strip()]
        placed = sum(1 for cell in cells if cell.bbox is not None)
        hit, checkable = landed(name, document)
        draw(name, document, out)
        print(f"{name:<22}{placed:>6} of {len(cells):<4}{hit:>7} of {checkable:<4}")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
