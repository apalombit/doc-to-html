"""Build contact sheets of corpus pages, twelve to an image.

    python tools/corpus_sheet.py --pilot                 # the pilot's pages
    python tools/corpus_sheet.py --ids c0008,c0012
    python tools/corpus_sheet.py --random 24 --seed 7    # drawn from the pages written
    python tools/corpus_sheet.py --since c0300           # pages written after c0300
    python tools/corpus_sheet.py --pilot --gallery       # and one page at full size

Sheets go to `debug/corpus-sheets/`. Every decision is in
`doc_to_html.factory.sheets`.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards, sheets  # noqa: E402

CORPUS = REPO / "corpus"
OUT = REPO / "debug" / "corpus-sheets"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", help="comma-separated card ids")
    parser.add_argument("--pilot", action="store_true", help="the pilot's pages")
    parser.add_argument("--random", type=int, help="this many pages drawn at random")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--since", help="pages whose id comes after this one")
    parser.add_argument("--name", help="the sheets' file name, default from the selection")
    parser.add_argument("--gallery", action="store_true",
                        help="also write one HTML page with every picture at full size")
    args = parser.parse_args()

    _, drawn = cards.load(CORPUS / "cards.json")
    written = [card for card in drawn if (CORPUS / "pages" / f"{card.id}.png").exists()]
    if args.ids:
        wanted = args.ids.split(",")
        chosen = [card for card in drawn if card.id in wanted]
        name = args.name or "ids"
    elif args.pilot:
        chosen = [card for card in drawn if card.pilot]
        name = args.name or "pilot"
    elif args.since:
        chosen = [card for card in written if card.id > args.since]
        name = args.name or f"since-{args.since}"
    elif args.random:
        chosen = random.Random(args.seed).sample(written, min(args.random, len(written)))
        name = args.name or f"random-{args.seed}"
    else:
        parser.error("say which pages: --ids, --pilot, --random or --since")
    ledger_path = CORPUS / "written.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    notes = [ledger.get(card.id, {}).get("writer", "") for card in chosen]
    pictures = [CORPUS / "pages" / f"{card.id}.png" for card in chosen]
    for path in sheets.sheets(chosen, pictures, OUT, name, notes):
        print(path.relative_to(REPO))
    if args.gallery:
        page = sheets.gallery(chosen, pictures, OUT / f"{name}.html",
                              f"Corpus pages — {name}", notes)
        print(page.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
