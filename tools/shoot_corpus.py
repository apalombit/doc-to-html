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
    "letter_0016": 820,
    "pricing_0017": 1000,
    "paper_0018": 900,
    "timetable_0019": 960,
    "ticket_0020": 900,
    "certificate_0021": 1000,
}
"""The width each authored document is shot at, and therefore compared at.

`receipt_0010` at 500 is `projection.MIN_WIDTH`, which is the narrowest the
browser will lay out at all; the receipt itself is a 300px slip centred on that
ground. A narrow portrait page is the aspect the corpus had none of, and it is
the one that breaks a renderer whose house column is a fixed 52rem.
"""


def check() -> int:
    """Score each document against its own HTML. It must come out perfect.

    **The strongest single check on the whole measure**, and it costs one
    command. `project(source)` and `project(output)` are the same function over
    the same bytes, so every axis has a known answer: recall, precision, joins,
    tau and side-by-side agreement are exactly 1.00, column error exactly 0.00,
    and nothing is lost on T6. Anything else is a bug in the scorer or a
    document that cannot be scored — and it finds both without a model, a run
    or a judgement.

    `height_ratio` is the one axis that is *not* exactly 1.00, and the reason is
    the corpus rather than the scorer: it divides by the **PNG's** height, which
    is what the model was shown, and only `invoice.html` still re-renders to its
    screenshot. The other four originals differ by 6.9-14.1% in content height —
    fonts on this machine, and `invoice2.html` additionally wants a CDN. The ten
    authored documents were screenshotted by this tool on this machine, so they
    come out at 1.00 and are held to it.
    """
    from doc_to_html.corpus import ITERATE, SWEEP
    from doc_to_html.scoring import score_document

    work = REPO / "debug" / "selfcheck"
    print(f"{'document':22s} {'recall':>7s} {'prec':>6s} {'joins':>6s} {'tau':>6s}"
          f" {'beside':>7s} {'colerr':>7s} {'h_ratio':>8s}")
    failed = []
    for name in SWEEP:
        source = SOURCES[name]
        if not source.png_path(REPO).is_file():
            print(f"{name:22s} not shot")
            failed.append(name)
            continue
        score = score_document(source, source.html_path(REPO), work=work,
                               root=REPO)
        done, layout = score.completeness, score.layout
        # The originals are allowed their measured drift; anything authored
        # here was shot from the same file on the same machine and is not.
        slack = 0.15 if name in ITERATE else 0.01
        wrong = (
            done.recall < 1.0 or done.precision < 1.0 or done.join_recall < 1.0
            or score.order.tau < 0.999 or layout.beside_agreement < 0.999
            or layout.column_error > 0.001
            or abs(layout.height_ratio - 1.0) > slack
        )
        if wrong:
            failed.append(name)
        print(f"{name:22s} {done.recall:7.3f} {done.precision:6.3f} "
              f"{done.join_recall:6.3f} {score.order.tau:6.3f} "
              f"{layout.beside_agreement:7.2f} {layout.column_error:7.2f} "
              f"{layout.height_ratio:8.2f}" + ("   <-- WRONG" if wrong else ""))

    if failed:
        print(f"\n{len(failed)} document(s) do not score perfectly against "
              f"themselves: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("\nevery document scores perfectly against itself", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", default="",
                        help="comma-separated documents to re-shoot even though "
                             "a PNG exists")
    parser.add_argument("--list", action="store_true",
                        help="say what each document is and whether it is shot")
    parser.add_argument("--check", action="store_true",
                        help="score every document against ITSELF, which must "
                             "come out perfect; anything less is a broken "
                             "document or a broken scorer")
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

    if args.check:
        return check()

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
