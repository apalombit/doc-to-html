"""Arm D2's offline loop: the parser's recorded regions -> adapter -> looks -> render.

Spec 0023, step 2; spec 0024, step 1. The parser reads each page once
(`--parse`, or a batch run); every change to the adapter or the looks is
drawn again from its regions with no model, in seconds a page.

    python tools/d2.py <label> --pages probe_payslip,c0197 [--parse] [--sheets]
    python tools/d2.py <label> --pages dev --regions L5-D2-dev --jobs 6 \
        [--previous <older label>] [--sheets]

writes `debug/runs/<label>/dump/glm-ocr_latest/<page>/document.html` (the
layout `tools/measure_run.py` reads) with the regions beside it.

- `--regions <run>` takes each page's regions from that run's dump
  (`00_regions.json`, as `tools/batch.py --arm d2` records them) instead
  of `debug/parsed/`.
- `--previous <label>` names every page whose HTML differs from that
  label's: the pages a change moved, each to be opened.
- `--grids` reads each page's grids with the reader in its table mode
  (spec 0025, 3c; one reader call per grid, no layout model) and records
  them as `01_grids.json` beside its render, as a batch run does; a page
  that has them in this label is not read again. A page drawn with
  recorded grids (this label's, or its regions' run's) is drawn with them.
- `--sheets` shoots each render at the source's width and writes
  `sheet.png`: the source beside the render, or, with `--previous`, the
  source, the previous render and this one, for the moved pages only.

Dev pages only: a panel page is refused (spec 0023's and 0024's rules).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.corpus import manifest, names, page  # noqa: E402
from doc_to_html.parser_first import (MODEL, containers, flat, from_regions,  # noqa: E402
                                      grids_of, parse, read_grids)
from doc_to_html.render import render  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "debug" / "parsed"
ARM = MODEL.replace(":", "_")


def sheet(pictures: list[Path], out: Path) -> float:
    """The pictures side by side, the source first; the last one's height
    against the source's."""
    from PIL import Image
    tiles = [Image.open(p).convert("RGB") for p in pictures]
    both = Image.new("RGB", (sum(t.width for t in tiles) + 20 * (len(tiles) - 1),
                             max(t.height for t in tiles)), (136, 136, 136))
    x = 0
    for tile in tiles:
        both.paste(tile, (x, 0))
        x += tile.width + 20
    both.save(out)
    return tiles[-1].height / tiles[0].height


def regions_path(name: str, run: str | None) -> Path:
    if run is None:
        return CACHE / f"{name}.regions.json"
    return REPO / "debug" / "runs" / run / "dump" / ARM / name / "00_regions.json"


def draw(name: str, source: Path, out: Path) -> tuple[str, int, float]:
    """One page drawn from its regions into `out`; its zones and seconds."""
    png = page(name).png_path(REPO)
    raw = json.loads(source.read_text(encoding="utf-8"))
    read = next((f for f in (out / "01_grids.json", source.parent / "01_grids.json")
                 if f.exists()), None)
    grids = json.loads(read.read_text(encoding="utf-8")) if read is not None else []
    started = time.perf_counter()
    document = from_regions(raw, png, grids)
    html = render(document)
    seconds = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    (out / "document.html").write_text(html, encoding="utf-8")
    (out / "regions.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    return name, len(document.zones), seconds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--pages", required=True, help="dev, or a comma list of dev page ids")
    parser.add_argument("--regions", metavar="RUN",
                        help="take each page's regions from this run's dump")
    parser.add_argument("--parse", action="store_true",
                        help="read the pages with the parser first, even if recorded")
    parser.add_argument("--previous", metavar="LABEL",
                        help="name the pages whose HTML differs from this label's")
    parser.add_argument("--grids", action="store_true",
                        help="read each page's grids as tables with the reader first")
    parser.add_argument("--sheets", action="store_true", help="shoot each render, with a sheet")
    parser.add_argument("--jobs", type=int, default=1, help="pages drawn at once")
    args = parser.parse_args()

    wanted = names("dev") if args.pages == "dev" else [n for n in args.pages.split(",") if n]
    entries = manifest()
    refused = [n for n in wanted if entries[n]["pool"] != "dev"]
    if refused:
        print(f"refused: not dev pages: {', '.join(refused)}", file=sys.stderr)
        return 2
    if args.regions and args.parse:
        print("refused: --regions takes a run's recorded regions; --parse reads anew",
              file=sys.stderr)
        return 2
    if not args.regions:
        CACHE.mkdir(parents=True, exist_ok=True)
        unread = [n for n in wanted if args.parse or not regions_path(n, None).exists()]
        if unread:
            pictures = {page(n).png_path(REPO): n for n in unread}
            scratch = CACHE / ".scratch"
            for stem, entry in parse(list(pictures), scratch).items():
                name = next(n for p, n in pictures.items() if p.stem == stem)
                shutil.copy(scratch / f"{stem}.regions.json", regions_path(name, None))
                print(f"{name}: parsed, {entry['seconds']} s, {len(entry['regions'])} regions")
    missing = [n for n in wanted if not regions_path(n, args.regions).exists()]
    if missing:
        print(f"no regions recorded for {len(missing)} pages: {', '.join(missing[:8])}"
              f"{' …' if len(missing) > 8 else ''}", file=sys.stderr)
        wanted = [n for n in wanted if n not in missing]

    dump = REPO / "debug" / "runs" / args.label / "dump" / ARM
    if args.grids:
        # One page at a time, before any drawing: the reader is the model.
        for name in wanted:
            target = dump / name / "01_grids.json"
            if target.exists():
                continue
            png = page(name).png_path(REPO)
            raw = json.loads(regions_path(name, args.regions).read_text(encoding="utf-8"))
            rectified = flat(png)
            grids = read_grids(png, grids_of(raw, rectified, containers(rectified)))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(grids, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
            print(f"{name}: {len(grids)} grids read, "
                  f"{sum(g['seconds'] for g in grids):.1f} s, "
                  f"{sum('<table' in g['content'] for g in grids)} as tables")
    jobs = [(n, regions_path(n, args.regions), dump / n) for n in wanted]
    if args.jobs > 1:
        with ProcessPoolExecutor(args.jobs) as pool:
            drawn = list(pool.map(draw, *zip(*jobs)))
    else:
        drawn = [draw(*job) for job in jobs]

    moved = list(wanted)
    if args.previous:
        before = REPO / "debug" / "runs" / args.previous / "dump" / ARM
        moved = [n for n in wanted if not (before / n / "document.html").exists()
                 or (before / n / "document.html").read_bytes()
                 != (dump / n / "document.html").read_bytes()]
    for name, zones, seconds in drawn:
        line = f"{name}: {zones} zones, {seconds:.1f} s"
        if args.previous:
            line += ", moved" if name in moved else ", same"
        if args.sheets and name in moved:
            from PIL import Image

            from doc_to_html.projection import screenshot
            png = page(name).png_path(REPO)
            out = dump / name
            screenshot(out / "document.html", out / "render.png", width=Image.open(png).width)
            pictures = [png, out / "render.png"]
            if args.previous:
                old = REPO / "debug" / "runs" / args.previous / "dump" / ARM / name
                if not (old / "render.png").exists() and (old / "document.html").exists():
                    screenshot(old / "document.html", old / "render.png",
                               width=Image.open(png).width)
                if (old / "render.png").exists():
                    pictures.insert(1, old / "render.png")
            line += f", height {sheet(pictures, out / 'sheet.png'):.2f}"
        print(line)
    if args.previous:
        print(f"{len(moved)} of {len(wanted)} pages moved against {args.previous}"
              + (f": {', '.join(moved)}" if moved else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
