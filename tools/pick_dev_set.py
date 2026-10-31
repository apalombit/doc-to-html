"""Pick the dev pages L2 converts after its first twenty — spec 0021, decision 12.

Dev's 200 would take about 33 hours. This picks the `size` pages that show
the checks the most of the corpus's variety, and writes them in the order
to convert them:

- **no PDF**, Alessandro's call;
- **c0008 and c0493 first**: the two first-stretch pages lost to a runaway
  call, now the test of the 3-minute call limit;
- **stratified by density** in dev's own proportions (without PDFs: 76
  medium, 64 dense, 51 sparse), the stratum furthest behind its share
  next, so a run stopped early leaves a balanced set;
- within a stratum, **the page that adds the most sightings** of the
  corpus's variability values — family × density, kind (page or part),
  arrangement, language, style, type, width in three bins, each feature —
  counting a value up to five times. A dense page counts as 3/7 of a
  sighting, the share of dense pages the first stretch converted inside
  20 minutes; ties go to the mixed order.

The first stretch's converted pages count as already seen, and none of its
pages is picked again but those two: the others timed out on their size,
and would again.

    python tools/pick_dev_set.py corpus/l2-dev-mixed.txt --size 90 \
        --tried <the first stretch> --converted <those it converted> \
        > corpus/l2-dev-90.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
FIRST = ("c0008", "c0493")
SIGHTINGS = 5
CONVERTS = {"sparse": 1.0, "medium": 1.0, "dense": 3 / 7}


def kind(card: dict[str, Any]) -> str:
    if card["origin"] == "pdf":
        return "pdf"
    return "part" if card.get("scope") == "part" else "page"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("order", type=Path, help="dev's 200 in the mixed order")
    parser.add_argument("--size", type=int, default=90)
    parser.add_argument("--tried", default="", help="pages already tried, comma-separated")
    parser.add_argument("--converted", default="", help="those of them converted, comma-separated")
    args = parser.parse_args()

    cards = json.loads((REPO / "corpus" / "manifest.json").read_text())["pages"]
    order = [name for name in args.order.read_text().split() if kind(cards[name]) != "pdf"]
    tried = [name for name in args.tried.split(",") if name]
    converted = [name for name in args.converted.split(",") if name]
    widths = sorted(int(cards[name]["width"]) for name in order)
    third, two_thirds = widths[len(widths) // 3], widths[2 * len(widths) // 3]

    def values(name: str) -> set[tuple[str, ...]]:
        card = cards[name]
        out = {("cell", card["family"], card["density"]), ("kind", kind(card))}
        for axis in ("arrangement", "language", "style", "type"):
            value = card.get(axis)
            if isinstance(value, list):
                out |= {(axis, str(item)) for item in value}
            elif value is not None:
                out.add((axis, str(value)))
        width = int(card["width"])
        out.add(("width", "narrow" if width < third else "mid" if width < two_thirds else "wide"))
        out |= {("feature", str(feature)) for feature in card.get("features") or []}
        return out

    available = Counter(value for name in order for value in values(name))
    seen: defaultdict[tuple[str, ...], float] = defaultdict(float)
    for name in converted:
        for value in values(name):
            seen[value] += 1

    def gain(name: str) -> float:
        weight = CONVERTS[cards[name]["density"]]
        return sum(min(seen[v] + weight, min(SIGHTINGS, available[v]))
                   - min(seen[v], min(SIGHTINGS, available[v])) for v in values(name))

    shares = Counter(cards[name]["density"] for name in order)
    quota = {density: round(args.size * count / len(order)) for density, count in shares.items()}
    candidates = [name for name in order if name not in tried]
    picked = list(FIRST)
    for name in picked:
        for value in values(name):
            seen[value] += CONVERTS[cards[name]["density"]]
    while len(picked) < args.size:
        have = Counter(cards[name]["density"] for name in picked)
        density = min((d for d in quota if have[d] < quota[d]), key=lambda d: have[d] / quota[d])
        best = max((name for name in candidates
                    if name not in picked and cards[name]["density"] == density),
                   key=lambda name: (gain(name), -candidates.index(name)))
        picked.append(best)
        for value in values(best):
            seen[value] += CONVERTS[cards[best]["density"]]
    print("\n".join(picked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
