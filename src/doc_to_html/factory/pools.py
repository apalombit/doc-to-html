"""The pools and the L3 set — spec 0020, step 6.

**Three pools of 200** (`level-up.md` §4.3): **dev**, looked at page by
page; **panel**, fixed, what a change is decided on; **vault**, opened by
nobody until a milestone. A page looked at closely is a practice page, so
the pilot's 50 go to dev.

**The deal**, seeded:
- *stratified by family*: each family's pages split as evenly over the
  three pools as its count allows, so dev, panel and vault share one mix;
- *PDF pages dealt separately*, the same way, a third to a pool (nine
  since they stopped at 27, Alessandro 2026-10-27);
- *the pilot fixed in dev*;
- *then repaired for coverage*: while a feature has fewer than
  `per_pool` pages in a pool, two pages of the same family and origin
  are swapped between pools when that lowers the pages lacking over
  every feature and pool, so no other count falls below its minimum.
  Pilot pages never move.

**The L3 set**: 36 panel pages chosen by greedy cover, so that each
family is there at least 4 times and each table, key–value, list and
arrangement feature at least twice. While anything is uncovered, the page
covering the most of what is missing is taken. After that, the page
adding the most features not yet held twice is taken. Ties go to the
seeded order.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Sequence

from doc_to_html.factory.cards import Card, Taxonomy, coverage, feature_ids

POOLS = ("dev", "panel", "vault")


def _split(count: int, offset: int) -> list[int]:
    """`count` items over three pools, as even as possible; the remainder
    goes to the pools from `offset` on, so families take turns."""
    base, extra = divmod(count, 3)
    sizes = [base] * 3
    for step in range(extra):
        sizes[(offset + step) % 3] += 1
    return sizes


def deal(taxonomy: Taxonomy, cards: Sequence[Card], seed: int) -> dict[str, str]:
    """Card id to pool, every card dealt."""
    rng = random.Random(seed)
    pools: dict[str, str] = {}
    turn = 0
    for origin in ("generated", "pdf"):
        for family in taxonomy["families"]:
            members = [c for c in cards if c.family == family and c.origin == origin]
            if not members:
                continue
            sizes = _split(len(members), turn)
            turn += len(members) % 3
            pilot = [c for c in members if c.pilot]
            rest = [c for c in members if not c.pilot]
            rng.shuffle(rest)
            for card in pilot:
                pools[card.id] = "dev"
            want = {"dev": sizes[0] - len(pilot), "panel": sizes[1], "vault": sizes[2]}
            if want["dev"] < 0:
                raise ValueError(f"{family}: more pilot pages than dev's share")
            cursor = 0
            for pool in POOLS:
                for card in rest[cursor:cursor + want[pool]]:
                    pools[card.id] = pool
                cursor += want[pool]
    return _repair(taxonomy, cards, pools, rng)


def shortfalls(taxonomy: Taxonomy, cards: Sequence[Card], pools: dict[str, str]
               ) -> dict[tuple[str, str], int]:
    """(feature, pool) to how many pages that pool lacks of the minimum."""
    least = taxonomy["coverage"]["per_pool"]
    found = coverage(cards, pools)
    return {(fid, pool): least - found.pools[fid][pool]
            for fid in feature_ids(taxonomy) for pool in POOLS
            if found.pools[fid][pool] < least}


def _repair(taxonomy: Taxonomy, cards: Sequence[Card], pools: dict[str, str],
            rng: random.Random) -> dict[str, str]:
    least = taxonomy["coverage"]["per_pool"]
    pools = dict(pools)
    for _ in range(2000):
        short = shortfalls(taxonomy, cards, pools)
        if not short:
            return pools
        (fid, pool) = sorted(short)[0]
        found = coverage(cards, pools)
        carriers = [c for c in cards if fid in c.all_features() and pools[c.id] != pool
                    and not c.pilot and found.pools[fid][pools[c.id]] > least]
        rng.shuffle(carriers)
        done = False
        for giver in carriers:
            takers = [c for c in cards if pools[c.id] == pool and not c.pilot
                      and c.family == giver.family and c.origin == giver.origin
                      and fid not in c.all_features()]
            rng.shuffle(takers)
            for taker in takers:
                trial = dict(pools)
                trial[giver.id], trial[taker.id] = pool, pools[giver.id]
                if sum(shortfalls(taxonomy, cards, trial).values()) < sum(short.values()):
                    pools = trial
                    done = True
                    break
            if done:
                break
        if not done:
            return pools
    return pools


L3_GROUPS = ("tables", "key_value", "lists", "arrangement")


def l3_subset(taxonomy: Taxonomy, cards: Sequence[Card], pools: dict[str, str],
              seed: int, size: int = 36, per_family: int = 4, per_feature: int = 2
              ) -> list[str]:
    """`size` panel pages covering every family and the structural features."""
    rng = random.Random(seed)
    panel = [c for c in cards if pools.get(c.id) == "panel" and c.kind]
    rng.shuffle(panel)
    wanted = [fid for group in L3_GROUPS for fid in taxonomy["features"][group]]
    chosen: list[Card] = []

    def missing() -> Counter[str]:
        need: Counter[str] = Counter()
        families = Counter(c.family for c in chosen)
        for family in taxonomy["families"]:
            if families[family] < per_family:
                need[f"family:{family}"] = per_family - families[family]
        held = Counter(fid for c in chosen for fid in c.all_features())
        for fid in wanted:
            if held[fid] < per_feature:
                need[fid] = per_feature - held[fid]
        return need

    def gain(card: Card, need: Counter[str]) -> int:
        tokens = {f"family:{card.family}", *card.all_features()}
        return sum(1 for token in tokens if need[token] > 0)

    while len(chosen) < size:
        need = missing()
        if not need:
            held = Counter(fid for c in chosen for fid in c.all_features())
            need = Counter({fid: 1 for fid in feature_ids(taxonomy) if held[fid] < 2})
        pool = [c for c in panel if c not in chosen]
        if not pool:
            break
        best = max(pool, key=lambda c: gain(c, need))
        chosen.append(best)
    return sorted(c.id for c in chosen)


def pool_counts(cards: Sequence[Card], pools: dict[str, str]) -> dict[str, Counter[str]]:
    """Per pool: pages by family and by origin, for the outcome's tables."""
    found: dict[str, Counter[str]] = defaultdict(Counter)
    for card in cards:
        pool = pools[card.id]
        found[pool][card.family] += 1
        found[pool][f"origin:{card.origin}"] += 1
    return found
