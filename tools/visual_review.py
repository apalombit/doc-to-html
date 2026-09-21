"""Set up, or check, a visual review: source beside render, and what changed.

The workflow this belongs to is a skill — `.claude/skills/visual-review/` —
and its rationale and gap list live in `docs/agents/visual-review.md`. Every
decision the tool encodes is in `doc_to_html.review`'s module docstring; this
file is the command line and nothing else.

    # build the sheets and the blank form
    python tools/visual_review.py debug/runs/<label>

    # ...with the previous run's render as a third panel
    python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>

    # ...a few documents only
    python tools/visual_review.py debug/runs/<label> --documents cv_0013,menu_0012

    # tally a filled findings.json and name what no scored axis caught
    python tools/visual_review.py debug/runs/<label> --check

    # one arbitrary page against one arbitrary picture
    python tools/visual_review.py --pair example/invoice.png /tmp/mine.html \
        --out /tmp/review
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html import review  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def _short(path: Path) -> str:
    """Repository-relative where that is shorter, absolute where --out points
    somewhere else entirely."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _check(run: Path, out: Path, previous: Path | None) -> int:
    findings = out / "findings.json"
    if not findings.exists():
        print(f"no {_short(findings)} — build the review first")
        return 1
    record = json.loads(findings.read_text())
    scores = review._scores_file(run)
    older = review._scores_file(previous) if previous else None
    summary = review.summarise(record, scores=scores, previous_scores=older)
    (out / "review.md").write_text(review.report_md(record, summary))
    print(f"{summary.answered} axes answered across {summary.documents} "
          f"document(s) — {_short(out / 'review.md')}")
    if not summary.cross_checked:
        print("no scores.json for these documents — nothing was cross-checked")
    elif summary.unreported:
        print("\nFaults no scored axis reported (every ratio at 1.000):")
        for finding in summary.unreported:
            print(f"  {finding.document}  {finding.axis}: {finding.note}")
    if summary.missing_axes:
        print(f"\nAxes that never fired: {', '.join(summary.missing_axes)}")
    if summary.unknown_axes:
        print(f"Trial axes kept: {', '.join(summary.unknown_axes)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, nargs="?", help="debug/runs/<label>")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--documents", default=None,
                        help="comma-separated names; default is every document "
                             "the run converted")
    parser.add_argument("--previous", type=Path, default=None,
                        help="another run directory, rendered as a third panel")
    parser.add_argument("--check", action="store_true",
                        help="tally a filled findings.json instead of building")
    parser.add_argument("--pair", nargs=2, metavar=("SOURCE_PNG", "RENDER"),
                        default=None,
                        help="compare two files outside any run")
    parser.add_argument("--out", type=Path, default=None,
                        help="where to write; default is <run>/_review")
    args = parser.parse_args()

    if args.pair:
        out = args.out or Path.cwd() / "_review"
        for part in review.pair(Path(args.pair[0]), Path(args.pair[1]), out):
            print(f"  {part}")
        return 0

    if args.run is None:
        parser.error("a run directory, or --pair")
    run = args.run.resolve()
    out = (args.out or run / "_review").resolve()

    if args.check:
        return _check(run, out, args.previous.resolve() if args.previous else None)

    sheets, out = review.build(
        run, model=args.model,
        documents=args.documents.split(",") if args.documents else None,
        previous=args.previous.resolve() if args.previous else None,
        out=args.out)
    for sheet in sheets:
        for part in sheet.parts:
            print(f"  {_short(part)}")
    print(f"\n{len(sheets)} document(s). Answer {_short(out / 'findings.json')} "
          f"by opening each PNG, then re-run with --check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
