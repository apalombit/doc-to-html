"""The pools and the L3 set — spec 0020, step 6.

Dealt over `corpus/cards.json` as it stands: 200 to a pool, each family
split evenly, the PDF pages a third to a pool, the pilot's 100 in dev,
two pages of every feature in every pool, and an L3 set of 36 panel
pages covering every family and the structural features.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from doc_to_html.factory import cards, pools

REPO = Path(__file__).resolve().parent.parent
TAXONOMY = cards.load_taxonomy(REPO / "corpus" / "taxonomy.json")
SEED = 20261024


@pytest.fixture(scope="module")
def drawn() -> list[cards.Card]:
    return cards.load(REPO / "corpus" / "cards.json")[1]


@pytest.fixture(scope="module")
def dealt(drawn: list[cards.Card]) -> dict[str, str]:
    return pools.deal(TAXONOMY, drawn, SEED)


def test_two_hundred_to_a_pool(dealt: dict[str, str]) -> None:
    assert Counter(dealt.values()) == {"dev": 200, "panel": 200, "vault": 200}


def test_each_family_is_split_evenly(drawn: list[cards.Card], dealt: dict[str, str]) -> None:
    for family in TAXONOMY["families"]:
        counts = Counter(dealt[c.id] for c in drawn if c.family == family)
        assert max(counts.values()) - min(counts.values()) <= 2, family


def test_the_pdf_pages_are_a_third_each(drawn: list[cards.Card],
                                        dealt: dict[str, str]) -> None:
    """Nine to a pool since PDF pages stopped at 27 (Alessandro, 2026-10-27)."""
    pdf = [c for c in drawn if c.origin == "pdf"]
    counts = Counter(dealt[c.id] for c in pdf)
    assert all(abs(n - len(pdf) / 3) < 1 for n in counts.values()), counts


def test_the_pilot_is_in_dev(drawn: list[cards.Card], dealt: dict[str, str]) -> None:
    assert all(dealt[c.id] == "dev" for c in drawn if c.pilot)


def test_every_feature_has_two_pages_in_every_pool(drawn: list[cards.Card],
                                                   dealt: dict[str, str]) -> None:
    assert pools.shortfalls(TAXONOMY, drawn, dealt) == {}


def test_the_deal_is_seeded(drawn: list[cards.Card], dealt: dict[str, str]) -> None:
    assert pools.deal(TAXONOMY, drawn, SEED) == dealt


def test_the_l3_set_covers_families_and_structure(drawn: list[cards.Card],
                                                  dealt: dict[str, str]) -> None:
    chosen = pools.l3_subset(TAXONOMY, drawn, dealt, SEED)
    assert len(chosen) == 36
    picked = [c for c in drawn if c.id in chosen]
    assert all(dealt[c.id] == "panel" for c in picked)
    families = Counter(c.family for c in picked)
    assert all(families[f] >= 4 for f in TAXONOMY["families"]), families
    held = Counter(fid for c in picked for fid in c.all_features())
    for group in pools.L3_GROUPS:
        for fid in TAXONOMY["features"][group]:
            assert held[fid] >= 2, fid
