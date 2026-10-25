"""Draw the corpus's cards, top up coverage, and print the coverage table.

    python tools/corpus_cards.py                  # draw corpus/cards.json (refuses to overwrite)
    python tools/corpus_cards.py --table          # the coverage table of cards.json
    python tools/corpus_cards.py --top-up         # top up again; written pages stay locked
    python tools/corpus_cards.py --widen-pilot 100  # more pilot cards, the first kept

Every decision is in `doc_to_html.factory.cards`; this is the command line.
`cards.json` records the seed it was drawn with and every later top-up,
with the cards each one changed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards  # noqa: E402

CORPUS = REPO / "corpus"
TAXONOMY = CORPUS / "taxonomy.json"
CARDS = CORPUS / "cards.json"
SEED = 20261024


def _history(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    history: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8")).get(
        "history", [])
    return history


def _write(drawn: list[cards.Card], seed: int, history: list[dict[str, object]]) -> None:
    cards.write(CARDS, drawn, seed)
    data = json.loads(CARDS.read_text(encoding="utf-8"))
    data["history"] = history
    CARDS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--table", action="store_true", help="print the table of cards.json")
    parser.add_argument("--top-up", action="store_true",
                        help="top up cards.json again, cards with a page locked")
    parser.add_argument("--widen-pilot", type=int, metavar="N",
                        help="widen the pilot to N cards, its cards kept")
    parser.add_argument("--force", action="store_true", help="overwrite cards.json")
    args = parser.parse_args()
    taxonomy = cards.load_taxonomy(TAXONOMY)

    if args.table:
        _, drawn = cards.load(CARDS)
        print(cards.coverage_table(taxonomy, drawn))
        return 0

    if args.top_up:
        seed, drawn = cards.load(CARDS)
        history = _history(CARDS)
        locked = {card.id for card in drawn
                  if (CORPUS / "pages" / f"{card.id}.html").exists()}
        step_seed = seed + len(history)
        topped, short = cards.top_up(taxonomy, drawn, step_seed, locked)
        changed = [new.id for old, new in zip(drawn, topped) if old != new]
        history.append({"step": "top-up", "seed": step_seed,
                        "locked": len(locked), "changed": changed})
        _write(topped, seed, history)
        print(cards.coverage_table(taxonomy, topped))
        print(f"top-up changed {len(changed)} cards: {', '.join(changed) or '-'}")
        if short:
            print(f"COVERAGE NOT MET: {short}")
            return 1
        return 0

    if args.widen_pilot:
        seed, drawn = cards.load(CARDS)
        history = _history(CARDS)
        step_seed = seed + len(history)
        widened = cards.widen_pilot(taxonomy, drawn, step_seed, args.widen_pilot)
        changed = [new.id for old, new in zip(drawn, widened) if old != new]
        history.append({"step": "widen pilot", "seed": step_seed,
                        "count": args.widen_pilot, "changed": changed})
        _write(widened, seed, history)
        print(f"the pilot widened by {len(changed)} cards: {', '.join(changed)}")
        return 0

    if CARDS.exists() and not args.force:
        print(f"{CARDS.relative_to(REPO)} exists; its cards may have pages. "
              "Use --top-up, or --force to draw afresh.")
        return 1
    drawn = cards.draw(taxonomy, SEED)
    topped, short = cards.top_up(taxonomy, drawn, SEED)
    changed = [new.id for old, new in zip(drawn, topped) if old != new]
    piloted = cards.choose_pilot(taxonomy, topped, SEED)
    _write(piloted, SEED, [{"step": "draw", "seed": SEED, "top-up changed": changed,
                            "pilot": [c.id for c in piloted if c.pilot]}])
    print(cards.coverage_table(taxonomy, piloted))
    print(f"drew {len(piloted)} cards with seed {SEED}; the top-up changed "
          f"{len(changed)}: {', '.join(changed) or '-'}")
    for problem in [(c.id, p) for c in piloted for p in cards.problems(taxonomy, c)]:
        print(f"PROBLEM {problem}")
    if short:
        print(f"COVERAGE NOT MET: {short}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
