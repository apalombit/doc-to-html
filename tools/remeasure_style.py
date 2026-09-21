"""Re-measure a run's pixel-derived style and re-render it, with no model.

**The loop that makes the Style Record cheap to iterate on.** Everything in
Thread 2/B — the palette, per-Zone fills and title bars, and now the drawn
boxes — is read off the source pixels by OpenCV. None of it asks the model
anything. So a change to any of it does not need another ninety-minute sweep:
take a sweep that exists, keep every answer the model gave, re-measure the
pixels, and re-render.

What is reused and what is recomputed:

    reused       Zones, their boxes, their text, their Kinds — everything the
                 model decided. Read back out of the run's own `document.html`,
                 which embeds the IR.
    recomputed   Document.style, and each Zone's fill, title_fill and boxed.
                 Measured from `example/<doc>.png` through the same `rectify`
                 the Conversion used.

The output is a run-shaped directory, so `doc_to_html.report` and
`tools/visual_review.py` both read it without knowing the difference.

    python tools/remeasure_style.py debug/runs/94-baseline --label 95-borders
    python -m doc_to_html.report debug/runs/95-borders --model qwen3-vl:4b \
        --previous tests/frozen/a1-checkpoint/scores.json
    python tools/visual_review.py debug/runs/95-borders \
        --previous debug/runs/94-baseline

**This is not a substitute for a run.** It cannot move anything the model
decided, so a prompt or extraction change still costs a sweep. Say which of
the two produced any number you report.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html import style as style_module  # noqa: E402
from doc_to_html.corpus import SOURCES  # noqa: E402
from doc_to_html.ir import Document  # noqa: E402
from doc_to_html.preprocess import caption_band, rectify, zone_pixels  # noqa: E402
from doc_to_html.render import render  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
_IR = re.compile(r'<script type="application/json" id="doc-ir">(.*?)</script>', re.S)


def ir_of(html: str) -> Document | None:
    """The IR a render embedded in itself, or None if it carries none."""
    found = _IR.search(html)
    if not found:
        return None
    return Document.from_json(found.group(1).replace("<\\/", "</"))


def remeasure(document: Document, png: Path) -> tuple[int, int]:
    """Recompute every pixel-derived field in place. Returns (rects, boxed)."""
    rectified = rectify(png)
    plain = rectified.plain if rectified.plain is not None else rectified.image
    document.style = style_module.measure(plain, inverted=rectified.inverted)
    drawn = style_module.rectangles(
        plain, ground=document.style.page_bg, inverted=rectified.inverted)
    own = style_module.boxes_for([z.bbox for z in document.zones], drawn)
    boxed = 0
    for index, zone in enumerate(document.zones):
        if zone.bbox is None:
            continue
        band = caption_band(zone_pixels(rectified.image, zone))
        found = style_module.chrome(
            zone_pixels(plain, zone),
            ground=document.style.page_bg,
            inverted=rectified.inverted,
            title_rows=band.bottom if band is not None and zone.title else 0,
            bordered=own[index] is not None,
        )
        zone.fill, zone.title_fill, zone.boxed = (
            found.fill, found.title_fill, found.bordered)
        boxed += int(found.bordered)
    return len(drawn), boxed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="the sweep to re-measure")
    parser.add_argument("--label", required=True, help="the new run's label")
    parser.add_argument("--model", default="qwen3-vl:4b")
    args = parser.parse_args()

    source_run: Path = args.run.resolve()
    target = REPO / "debug" / "runs" / args.label
    slug = args.model.replace(":", "_")
    dump = source_run / "dump" / slug
    if not dump.is_dir():
        print(f"no dump at {dump}")
        return 1
    if target.exists():
        print(f"{target} already exists — pick another label")
        return 1

    target.mkdir(parents=True)
    for name in ("commit.txt", "host.txt", "fixtures.txt", "dth_env.txt"):
        if (source_run / name).exists():
            shutil.copy2(source_run / name, target / name)
    (target / "remeasured_from.txt").write_text(
        f"{source_run.name}\nmodel answers reused; pixel-derived style "
        f"recomputed by tools/remeasure_style.py\n")

    print(f"{'document':<22}{'rects':>7}{'boxed':>7}{'fills':>7}")
    done = 0
    for folder in sorted(d for d in dump.iterdir() if d.is_dir()):
        html = folder / "document.html"
        if not html.exists() or folder.name not in SOURCES:
            print(f"{folder.name:<22}  skipped (no document.html)")
            continue
        document = ir_of(html.read_text(encoding="utf-8"))
        if document is None:
            print(f"{folder.name:<22}  skipped (no embedded IR)")
            continue
        rects, boxed = remeasure(document, REPO / SOURCES[folder.name].png)
        out = target / "dump" / slug / folder.name
        out.mkdir(parents=True, exist_ok=True)
        (out / "document.html").write_text(render(document), encoding="utf-8")
        fills = sum(1 for z in document.zones if z.fill)
        print(f"{folder.name:<22}{rects:>7}{boxed:>7}{fills:>7}")
        done += 1

    print(f"\n{done} document(s) -> {target.relative_to(REPO)}")
    print("Next: python -m doc_to_html.report "
          f"{target.relative_to(REPO)} --model {args.model} "
          "--previous tests/frozen/a1-checkpoint/scores.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
