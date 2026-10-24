"""Run the validator (spec 0020 §V) on corpus pages, and keep the ones that pass.

    python tools/corpus_check.py c0008 c0012     # check; keep each page that passes
    python tools/corpus_check.py --all           # every page in corpus/pages/
    python tools/corpus_check.py --dry c0008     # check; keep nothing

A page that passes gets its picture, `corpus/pages/<id>.png`, and its
record, `corpus/checks/<id>.json`. A page that fails keeps nothing, and its
screenshot is left at `debug/corpus-check/<id>.png` to look at. The exit
status is non-zero when any page fails, and each failed check is named.
Every decision is in `doc_to_html.factory.check`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards, check, fonts  # noqa: E402

CORPUS = REPO / "corpus"
DEBUG = REPO / "debug" / "corpus-check"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="card ids, e.g. c0008")
    parser.add_argument("--all", action="store_true", help="every page in corpus/pages/")
    parser.add_argument("--dry", action="store_true", help="keep nothing")
    args = parser.parse_args()

    _, drawn = cards.load(CORPUS / "cards.json")
    by_id = {card.id: card for card in drawn}
    ids = sorted(p.stem for p in (CORPUS / "pages").glob("*.html")) if args.all else args.ids
    unknown = [page_id for page_id in ids if page_id not in by_id]
    if unknown or not ids:
        print(f"no such card: {', '.join(unknown)}" if unknown else "name a page, or --all")
        return 2
    allowed = fonts.load(CORPUS / "fonts.json")
    known = check.known_in(REPO)
    failed = 0
    for page_id in ids:
        card = by_id[page_id]
        html_path = CORPUS / "pages" / f"{page_id}.html"
        if not html_path.exists():
            print(f"FAIL {page_id}: no {html_path.relative_to(REPO)}")
            failed += 1
            continue
        result = check.check(card, html_path, allowed, known)
        shape = f"{card.width}x{result.height}, {result.words} words"
        if result.passed:
            if not args.dry:
                check.keep(result, card, html_path, CORPUS / "pages" / f"{page_id}.png",
                           CORPUS / "checks" / f"{page_id}.json")
                known = [k for k in known if k.id != page_id] + [
                    check.Known(page_id, frozenset(check.shingles(check.html_text(
                        html_path.read_text(encoding="utf-8")))), result.dhash)]
            print(f"PASS {page_id} ({result.seconds} s, {shape}; detected: "
                  f"{', '.join(result.detected) or '-'})")
        else:
            failed += 1
            print(f"FAIL {page_id} ({result.seconds} s, {shape})")
            for name, messages in result.failures.items():
                for message in messages[:8]:
                    print(f"  {name}: {message}")
                if len(messages) > 8:
                    print(f"  {name}: ... and {len(messages) - 8} more")
            if result.picture and result.picture.exists():
                DEBUG.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(result.picture, DEBUG / f"{page_id}.png")
                print(f"  its screenshot: {(DEBUG / f'{page_id}.png').relative_to(REPO)}")
        if result.picture:
            shutil.rmtree(result.picture.parent, ignore_errors=True)
    print(f"{len(ids) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
