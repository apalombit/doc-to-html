"""Deal the pools and the L3 set, and write corpus/manifest.json — spec 0020, step 6.

The 600 cards are dealt by `pools.deal` (seeded by `cards.json`'s seed,
stratified by family, PDF pages apart, the pilot in dev, repaired for
coverage); the 31 known pages of `corpus/known.json` all go to dev. The
L3 set is `pools.l3_subset` over the panel, written to
`corpus/l3-subset.txt`. Each manifest entry names the page's pool, card,
files and their sha256, so a later change to any file shows.

    python tools/corpus_manifest.py            # every card must have a passed page
    python tools/corpus_manifest.py --partial  # deal anyway, for a look (writes nothing)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards, pools  # noqa: E402

CORPUS = REPO / "corpus"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _passed(card_id: str) -> bool:
    record = CORPUS / "checks" / f"{card_id}.json"
    return record.exists() and bool(json.loads(record.read_text(encoding="utf-8"))["passed"])


def entry(card: dict[str, Any], pool: str, files: dict[str, str]) -> dict[str, Any]:
    """One page's manifest entry: its pool, its card and its files with their hashes."""
    return {"pool": pool, **{key: card.get(key) for key in (
        "origin", "family", "kind", "scope", "arrangement", "type", "features", "style",
        "width", "density", "language", "locale", "pilot")},
            "files": files, "sha256": {kind: _sha(REPO / path) for kind, path in files.items()}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--partial", action="store_true",
                        help="deal although pages are missing, print the counts, write nothing")
    args = parser.parse_args()
    taxonomy = cards.load_taxonomy(CORPUS / "taxonomy.json")
    seed, drawn = cards.load(CORPUS / "cards.json")
    known = json.loads((CORPUS / "known.json").read_text(encoding="utf-8"))["cards"]

    missing = [card.id for card in drawn if not _passed(card.id)]
    if missing and not args.partial:
        print(f"{len(missing)} cards have no passed page, e.g. {', '.join(missing[:8])}")
        return 1

    dealt = pools.deal(taxonomy, drawn, seed)
    short = pools.shortfalls(taxonomy, drawn, dealt)
    l3 = pools.l3_subset(taxonomy, drawn, dealt, seed)
    print("pools:", dict(Counter(dealt.values())), "+", len(known), "known pages in dev")
    for pool, counts in sorted(pools.pool_counts(drawn, dealt).items()):
        print(f"  {pool}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"L3: {len(l3)} panel pages; coverage short in pools: {short or 'none'}")
    if args.partial:
        return 0
    if short:
        print("COVERAGE NOT MET in the pools: stop and ask")
        return 1

    manifest: dict[str, Any] = {}
    for card in drawn:
        files = {"html": f"corpus/pages/{card.id}.html", "png": f"corpus/pages/{card.id}.png"}
        if card.origin == "pdf":
            files["pdf"] = f"corpus/pdf/{card.id}.pdf"
        manifest[card.id] = entry(card.to_json(), dealt[card.id], files)
    for page in known:
        manifest[page["id"]] = entry(page, "dev", {"html": page["html"], "png": page["png"]})
    payload = {"about": ("Every corpus page (spec 0020): its pool, its card and its files "
                         "with their sha256. Written by tools/corpus_manifest.py; the vault "
                         "is opened by nobody until a milestone."),
               "seed": seed, "pages": manifest}
    (CORPUS / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (CORPUS / "l3-subset.txt").write_text("".join(f"{i}\n" for i in l3), encoding="utf-8")
    print(f"corpus/manifest.json: {len(manifest)} pages; corpus/l3-subset.txt: {len(l3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
