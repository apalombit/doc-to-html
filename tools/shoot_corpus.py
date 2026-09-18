"""Take the screenshot that makes an HTML file a document of the corpus.

    python tools/shoot_corpus.py                 # anything missing a PNG
    python tools/shoot_corpus.py --list
    python tools/shoot_corpus.py --force cv_0013

**Adding a document to this project is now: write the HTML, run this, done.**
No Python, no transcription, no expected IR. That is what let the corpus leave
five, and it is the whole reason `projection.project()` reads ground truth off
the browser instead of off a file somebody typed.

**It refuses to overwrite a screenshot that already exists.** The five original
documents' PNGs are historical: `example/invoice.png` is the image every run in
this repository was measured against, and `tools/fixture_geometry.py` measured
that `invoice.html` still re-renders to it at 0.74% of pixels differing while
the other four differ by 6.9 to 14.1%. Re-shooting those would silently move the
ground truth under every recorded result. `--force` exists for a document whose
HTML you have just edited, and names it explicitly.

The width per document is a judgement, made once and written down here: it is
the width at which the page reads the way its archetype reads, and it becomes
the matched width every later comparison uses.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html import projection  # noqa: E402
from doc_to_html.corpus import SOURCES  # noqa: E402

WIDTHS: dict[str, int] = {
    "statement_0006": 900,
    "form_0007": 820,
    "newsletter_0008": 960,
    "darkdeck_0009": 1000,
    "receipt_0010": 500,
    "report_0011": 820,
    "menu_0012": 760,
    "cv_0013": 900,
    "nonlatin_0014": 940,
    "catalogue_0015": 900,
}
"""The width each authored document is shot at, and therefore compared at.

`receipt_0010` at 500 is `projection.MIN_WIDTH`, which is the narrowest the
browser will lay out at all; the receipt itself is a 300px slip centred on that
ground. A narrow portrait page is the aspect the corpus had none of, and it is
the one that breaks a renderer whose house column is a fixed 52rem.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", default="",
                        help="comma-separated documents to re-shoot even though "
                             "a PNG exists")
    parser.add_argument("--list", action="store_true",
                        help="say what each document is and whether it is shot")
    args = parser.parse_args(argv)

    if args.list:
        for name, source in SOURCES.items():
            state = "shot" if source.png_path(REPO).is_file() else "MISSING"
            print(f"{name:22s} {state:8s} {source.archetype}")
            print(f"{'':22s} {'':8s} {source.awkward}")
        return 0

    if not projection.available():
        print(f"no headless Chrome at {projection.CHROME}", file=sys.stderr)
        return 1

    forced = {name.strip() for name in args.force.split(",") if name.strip()}
    unknown = forced - set(SOURCES)
    if unknown:
        raise SystemExit(f"unknown document(s): {', '.join(sorted(unknown))}")

    shot = 0
    for name, source in SOURCES.items():
        png = source.png_path(REPO)
        html = source.html_path(REPO)
        if not html.is_file():
            print(f"{name}: no {source.html}", file=sys.stderr)
            continue
        if png.is_file() and name not in forced:
            continue
        width = WIDTHS.get(name)
        if width is None:
            print(f"{name}: no width recorded in WIDTHS, skipping",
                  file=sys.stderr)
            continue
        projection.screenshot(html, png, width=width)
        from PIL import Image

        size = Image.open(png).size
        print(f"{name:22s} {source.png}  {size[0]}x{size[1]}")
        shot += 1

    print(f"\n{shot} screenshot(s) taken", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
