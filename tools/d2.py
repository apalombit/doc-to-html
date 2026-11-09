"""Arm D2's offline loop: the parser's recorded regions -> adapter -> looks -> render.

Spec 0023, step 2. The parser reads each page once (`--parse`); its regions
are kept in `debug/parsed/<page>.regions.json`, and every change to the
adapter or the looks is drawn again from them with no model, in seconds.

    python tools/d2.py <label> --pages probe_payslip,c0197 [--parse] [--sheets]

writes `debug/runs/<label>/dump/glm-ocr_latest/<page>/document.html` (the
layout `tools/measure_run.py` reads) with the regions beside it, and with
`--sheets` each page's render shot at the source's width and a sheet of
the source beside it, `sheet.png`. Dev pages only: a panel page is
refused unless it is in the L3 run's own dump (spec 0023's rules).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.corpus import manifest, page  # noqa: E402
from doc_to_html.parser_first import MODEL, from_regions, parse  # noqa: E402
from doc_to_html.render import render  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "debug" / "parsed"


def sheet(source: Path, render_png: Path, out: Path) -> float:
    """The source beside the render, at one width; the height ratio."""
    from PIL import Image
    left, right = Image.open(source).convert("RGB"), Image.open(render_png).convert("RGB")
    both = Image.new("RGB", (left.width + right.width + 20, max(left.height, right.height)),
                     (136, 136, 136))
    both.paste(left, (0, 0))
    both.paste(right, (left.width + 20, 0))
    both.save(out)
    return right.height / left.height


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--pages", required=True, help="a comma list of dev page ids")
    parser.add_argument("--parse", action="store_true",
                        help="read the pages with the parser first, even if recorded")
    parser.add_argument("--sheets", action="store_true", help="shoot each render, with a sheet")
    args = parser.parse_args()

    names = [n for n in args.pages.split(",") if n]
    entries = manifest()
    refused = [n for n in names if entries[n]["pool"] != "dev"]
    if refused:
        print(f"refused: not dev pages: {', '.join(refused)}", file=sys.stderr)
        return 2
    CACHE.mkdir(parents=True, exist_ok=True)
    wanted = [n for n in names if args.parse or not (CACHE / f"{n}.regions.json").exists()]
    if wanted:
        pictures = {page(n).png_path(REPO): n for n in wanted}
        scratch = CACHE / ".scratch"
        for stem, entry in parse(list(pictures), scratch).items():
            name = next(n for p, n in pictures.items() if p.stem == stem)
            shutil.copy(scratch / f"{stem}.regions.json", CACHE / f"{name}.regions.json")
            print(f"{name}: parsed, {entry['seconds']} s, {len(entry['regions'])} regions")

    dump = REPO / "debug" / "runs" / args.label / "dump" / MODEL.replace(":", "_")
    for name in names:
        png = page(name).png_path(REPO)
        raw = json.loads((CACHE / f"{name}.regions.json").read_text(encoding="utf-8"))
        started = time.perf_counter()
        document = from_regions(raw, png)
        html = render(document)
        seconds = time.perf_counter() - started
        out = dump / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "document.html").write_text(html, encoding="utf-8")
        (out / "regions.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
        line = f"{name}: {len(document.zones)} zones, {seconds:.1f} s"
        if args.sheets:
            from PIL import Image

            from doc_to_html.projection import screenshot
            screenshot(out / "document.html", out / "render.png", width=Image.open(png).width)
            line += f", height {sheet(png, out / 'render.png', out / 'sheet.png'):.2f}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
