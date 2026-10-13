"""Print a rendered document's Zones, read back out of its embedded IR.

    python tools/zones.py tests/frozen/s6-result/documents/form_0007.html
    python tools/zones.py debug/runs/<label> --documents form_0007,menu_0012

One line per Zone — index, kind, band and column, box in source pixels,
title, fill, boxed, frame, group and alignment where set — then its rows,
pairs or blocks, one line each. Nearly every question about a page starts
here, so it reads a frozen directory, a run directory or one file alike.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent / "src"))
sys.path.insert(0, str(TOOLS))

from doc_to_html.ir import BBox, Document, Zone  # noqa: E402
from rederive import documents_in  # noqa: E402
from remeasure_style import ir_of  # noqa: E402


def _px(box: BBox | None, document: Document) -> str:
    if box is None:
        return "-"
    width = document.source.rectified_width or document.source.width
    height = document.source.rectified_height or document.source.height
    return (f"({box.left * width:.0f},{box.top * height:.0f})-"
            f"({box.right * width:.0f},{box.bottom * height:.0f})")


def _zone_line(index: int, zone: Zone, document: Document) -> str:
    parts = [f"Z{index:<2} {zone.kind.value:<6} b{zone.band} c{zone.column}",
             _px(zone.bbox, document)]
    if zone.title:
        parts.append(f"title={zone.title!r}")
    for name in ("fill", "title_fill", "header_fill"):
        if getattr(zone, name) is not None:
            parts.append(f"{name}={getattr(zone, name)}")
    if zone.boxed:
        parts.append("boxed")
    for name in ("frame", "group", "align", "title_align", "gap_px"):
        value = getattr(zone, name, None)
        if value is not None:
            parts.append(f"{name}={_px(value, document) if name == 'frame' else value}")
    return "  ".join(parts)


def print_document(name: str, document: Document) -> None:
    print(f"== {name}  {document.source.width}x{document.source.height}"
          f"  regions={[(round(r.top, 3), round(r.bottom, 3), r.flow.value, r.splits) for r in document.regions]}")
    for index, zone in enumerate(document.zones):
        print(_zone_line(index, zone, document))
        for row in zone.rows:
            print(f"      [{row.role.value[0]}] "
                  + " | ".join(cell.text for cell in row.cells))
        for pair in zone.pairs:
            print(f"      {pair.label.text!r}: {pair.value.text!r}")
        for block in zone.blocks:
            text = " / ".join(cell.text for cell in block.lines)
            print(f"      <{block.kind}> {text[:110]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path,
                        help="a rendered document, a frozen directory or a run")
    parser.add_argument("--documents", default="")
    parser.add_argument("--model", default="qwen3-vl:4b")
    args = parser.parse_args()

    wanted = {n.strip() for n in args.documents.split(",") if n.strip()}
    found = ([(args.source.stem, args.source)] if args.source.is_file()
             else documents_in(args.source.resolve(), args.model))
    for name, html in found:
        if wanted and name not in wanted:
            continue
        document = ir_of(html.read_text(encoding="utf-8"))
        if document is not None:
            print_document(name, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
