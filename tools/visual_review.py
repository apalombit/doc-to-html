"""Set up a visual review: one image per document, source beside render.

**Why this exists.** This project's most expensive lesson is that a measure can
saturate and then invert while every number improves — `sample_table_0003`
scored a full match having deleted every column header of its only table, and
nobody had opened a render beside its source in eighty runs. `report.html`
answers "what do the numbers say"; this answers "what does it look like", and
the two catch different things. On 2026-09-20 a review of five documents found
four faults no axis had reported, including every white page being rendered on
`#f8f8f8`.

**What it produces**, under `<run>/_review/`:

    00-invoice_0001.png     source left, render right, matched width
    ...
    review.md               one rubric block per document, to fill in by looking
    numbers.md              the scored axes per document, to cite in the notes

The images are the point. `review.md` is a form, not a result — it is filled in
by **opening each PNG**, not by reading `numbers.md`.

**Scores here are pairwise and in-session only.** CLAUDE.md is explicit that a
rubric judgement from one session and one from another are not comparable and
must never be tabulated together, and that applies to a model's visual
judgements at least as strongly as to numbers. So every sheet is stamped with
its run label and the date, and the rubric asks for *differences from the
source*, which are observations, rather than a score out of ten, which is not.

**The reference is the PNG, not the re-rendered HTML.** The screenshot is what
the model was shown and what a person compares against. Four of the five
original documents re-render 6.9-14.1% different from their own screenshots on
this machine, so using the HTML would show differences nobody introduced.

Usage:

    python tools/visual_review.py debug/runs/<label>
    python tools/visual_review.py debug/runs/<label> --documents cv_0013,menu_0012
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from PIL import Image

from doc_to_html.corpus import SOURCES
from doc_to_html.projection import project, screenshot

REPO = Path(__file__).resolve().parent.parent

GUTTER = 24
"""Pixels between the two pages, in the page's own ground colour where possible.

Wide enough that a page's own right-hand edge is never mistaken for the seam,
which matters most on the documents that have a border round the whole page.
"""

LABEL_BAR = 28
"""Height of the strip naming which side is which. Without it a reviewer has to
remember the convention, and the one thing worse than no comparison is a
confident backwards one."""

RUBRIC = [
    ("content", "Anything in the source missing from the render, or anything in "
                "the render that is not in the source"),
    ("order", "Reading order and grouping — same things, in the same sequence, "
              "bound to the same headings"),
    ("columns", "What sits beside what. A source column rendered as a stack is a "
                "major, not a minor"),
    ("chrome", "Borders, cards, rules, fills — drawn where the source draws them "
               "and nowhere else"),
    ("type", "Relative size and weight. Is the hierarchy the same shape, even if "
             "the absolute sizes differ"),
    ("colour", "Ground, ink, accent, shaded bands"),
    ("rhythm", "Spacing and density — how much taller or tighter the render is "
               "than the page"),
]


def _stack(source: Path, render: Path, destination: Path, width: int) -> None:
    """One image, source left and render right, both at the source's width."""
    left, right = Image.open(source).convert("RGB"), Image.open(render).convert("RGB")
    height = max(left.height, right.height) + LABEL_BAR
    sheet = Image.new("RGB", (left.width + GUTTER + right.width, height), (128, 128, 128))
    sheet.paste(left, (0, LABEL_BAR))
    sheet.paste(right, (left.width + GUTTER, LABEL_BAR))
    sheet.save(destination)


def _numbers(run: Path) -> dict[str, dict[str, float]]:
    """The run's own scores, if it has any. Absent is fine — the images are the
    review and the numbers are only there so a note can quote one."""
    scores = run / "scores.json"
    if not scores.exists():
        return {}
    import json

    return {
        d["name"]: {
            "recall": d["completeness"]["recall"],
            "precision": d["completeness"]["precision"],
            "tau": d["order"]["tau"],
            "beside": d["layout"]["beside_agreement"],
            "height_ratio": d["layout"]["height_ratio"],
            "ink_delta": d["palette"]["ink_delta"],
        }
        for d in json.load(scores.open())["documents"]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="debug/runs/<label>")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--documents", default=None,
                        help="comma-separated names; default is every document "
                             "the run converted")
    args = parser.parse_args()

    run: Path = args.run.resolve()
    dump = run / "dump" / args.model.replace(":", "_")
    out = run / "_review"
    out.mkdir(parents=True, exist_ok=True)

    wanted = args.documents.split(",") if args.documents else None
    names = [d.name for d in sorted(dump.iterdir()) if d.is_dir()
             and (wanted is None or d.name in wanted)]

    numbers = _numbers(run)
    sheets, rows = [], []
    for index, name in enumerate(names):
        source = REPO / SOURCES[name].png
        width = Image.open(source).width
        html = dump / name / "document.html"
        if not html.exists():
            print(f"  {name}: no document.html in the dump, skipped")
            continue

        render_png = out / f"{index:02d}-{name}-render.png"
        screenshot(html, render_png, width=width)
        sheet = out / f"{index:02d}-{name}.png"
        _stack(source, render_png, sheet, width)
        render_png.unlink()
        sheets.append((name, sheet))

        n = numbers.get(name, {})
        rows.append(f"| `{name}` | {width}px | "
                    + " | ".join(f"{n[k]:.3f}" if k in n else "—"
                                 for k in ("recall", "precision", "tau", "beside",
                                           "height_ratio", "ink_delta"))
                    + " |")
        print(f"  {sheet.relative_to(REPO)}")

    stamp = f"{run.name} · {date.today().isoformat()}"
    (out / "numbers.md").write_text(
        f"# Scored axes — {stamp}\n\n"
        "Here to be quoted in a note, not to be reviewed. The images are the "
        "review.\n\n"
        "| document | width | recall | precision | tau | beside | height_ratio | ink_delta |\n"
        "|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    )

    form = [
        f"# Visual review — {stamp}",
        "",
        "**Source left, render right, matched width.** Filled in by opening each",
        "PNG in this directory, one at a time. A note that could have been written",
        "from `numbers.md` alone has not done the job this file exists for.",
        "",
        "**Pairwise and in-session only.** These readings are not comparable with",
        "a review from another session — see CLAUDE.md, *How runs are used here*.",
        "",
        "Each axis: `match` / `minor` / `major`, and one concrete sentence. Name",
        "the element, not the impression.",
        "",
    ]
    for name, sheet in sheets:
        form += [f"## {name}", "", f"![{name}]({sheet.name})", ""]
        form += [f"- **{axis}** — _{prompt}_" for axis, prompt in RUBRIC]
        form += ["- **worst fault** —", "- **owner** — (which thread or phase "
                 "this belongs to, or `new`)", ""]
    (out / "review.md").write_text("\n".join(form) + "\n")

    print(f"\n{len(sheets)} sheet(s), the form at {(out / 'review.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
