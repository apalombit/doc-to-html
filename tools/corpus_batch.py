"""Hand out the next unwritten cards to writers, in batches, with their particulars.

    python tools/corpus_batch.py --next 50 --batches 5 --out <dir>

Takes the next `--next` generated cards with no passing page (no record in
`corpus/checks/`; a draft without one is handed out again), families taken in
turn so every batch mixes them, and writes `<dir>/batch-<n>.jsonl`: one
card a line, as the brief shows it, with the card's particulars
(`doc_to_html.factory.particulars`). Nothing in `corpus/` is changed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards, particulars  # noqa: E402

CORPUS = REPO / "corpus"
FIELDS = ("id", "family", "kind", "arrangement", "type", "features", "style",
          "language", "locale", "width", "density", "scope")


def _passed(card_id: str) -> bool:
    """A card is written once its page has passed: a draft's failed record
    leaves it open."""
    record = CORPUS / "checks" / f"{card_id}.json"
    return record.exists() and bool(json.loads(record.read_text(encoding="utf-8"))["passed"])


def line(card: cards.Card) -> str:
    data = {name: getattr(card, name) for name in FIELDS}
    data["features"] = list(card.features)
    data["particulars"] = particulars.particulars(card)
    return json.dumps(data, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--next", type=int, required=True, help="how many cards")
    parser.add_argument("--batches", type=int, default=5)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    _, drawn = cards.load(CORPUS / "cards.json")
    open_: dict[str, list[cards.Card]] = defaultdict(list)
    for card in drawn:
        if card.origin == "generated" and not _passed(card.id):
            open_[card.family].append(card)
    order: list[cards.Card] = []
    while any(open_.values()):
        for family in sorted(open_, key=lambda f: -len(open_[f])):
            if open_[family]:
                order.append(open_[family].pop(0))
    chosen = order[:args.next]
    args.out.mkdir(parents=True, exist_ok=True)
    for number in range(args.batches):
        batch = chosen[number::args.batches]
        if not batch:
            continue
        target = args.out / f"batch-{number + 1}.jsonl"
        target.write_text("".join(line(card) + "\n" for card in batch), encoding="utf-8")
        print(f"{target}: " + ", ".join(f"{c.id} {c.kind}" for c in batch))
    print(f"{len(chosen)} of {len(order)} unwritten cards handed out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
