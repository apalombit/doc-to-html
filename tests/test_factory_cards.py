"""The cards the corpus is written from — spec 0020, step 1.

Quotas met exactly, the same seed giving the same cards, the coverage rule
met, and no card holding features that cannot stand together. The last
class tests plants each kind of fault on a sound card and asks
`problems` to name it.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from doc_to_html.factory import cards

REPO = Path(__file__).resolve().parent.parent
TAXONOMY = cards.load_taxonomy(REPO / "corpus" / "taxonomy.json")
SEED = 20261024


@pytest.fixture(scope="module")
def drawn() -> list[cards.Card]:
    topped, short = cards.top_up(TAXONOMY, cards.draw(TAXONOMY, SEED), SEED)
    assert not short
    return cards.choose_pilot(TAXONOMY, topped, SEED)


class TestQuotas:
    def test_every_family_has_its_pages_and_its_pdf_slots(self, drawn: list[cards.Card]) -> None:
        assert len(drawn) == TAXONOMY["total"] == 600
        for family, entry in TAXONOMY["families"].items():
            members = [card for card in drawn if card.family == family]
            assert len(members) == entry["pages"], family
            assert sum(card.origin == "pdf" for card in members) == entry["pdf"], family
        assert sum(card.origin == "pdf" for card in drawn) == 100

    def test_receipts_and_clinical_notes_have_their_shares(self, drawn: list[cards.Card]) -> None:
        kinds = Counter(card.kind for card in drawn)
        assert kinds["receipt"] == 40
        clinical = [kind for kind, entry in TAXONOMY["families"]["reports"]["kinds"].items()
                    if entry.get("clinical")]
        assert sum(kinds[kind] for kind in clinical) == 40

    def test_the_other_kinds_of_a_family_differ_by_at_most_one(
            self, drawn: list[cards.Card]) -> None:
        for family, entry in TAXONOMY["families"].items():
            free = [kind for kind, spec in entry["kinds"].items() if "pages" not in spec]
            counts = Counter(card.kind for card in drawn
                             if card.family == family and card.kind in free)
            assert max(counts.values()) - min(counts.values()) <= 1, family
            assert set(counts) == set(free), family

    def test_the_languages_are_dealt_exactly(self, drawn: list[cards.Card]) -> None:
        assert Counter(card.language for card in drawn) == Counter(TAXONOMY["languages"])


class TestTheDrawIsSeeded:
    def test_the_same_seed_gives_the_same_cards(self) -> None:
        assert cards.draw(TAXONOMY, SEED) == cards.draw(TAXONOMY, SEED)

    def test_another_seed_gives_other_cards(self) -> None:
        assert cards.draw(TAXONOMY, SEED) != cards.draw(TAXONOMY, SEED + 1)

    def test_the_top_up_and_the_pilot_are_seeded_too(self, drawn: list[cards.Card]) -> None:
        again, _ = cards.top_up(TAXONOMY, cards.draw(TAXONOMY, SEED), SEED)
        assert cards.choose_pilot(TAXONOMY, again, SEED) == drawn


class TestCoverage:
    def test_every_feature_is_on_nine_pages_in_three_kinds(self, drawn: list[cards.Card]) -> None:
        assert cards.shortfalls(TAXONOMY, drawn) == {}

    def test_the_top_up_never_touches_a_locked_card(self) -> None:
        first = cards.draw(TAXONOMY, SEED)
        topped, _ = cards.top_up(TAXONOMY, first, SEED)
        moved = {new.id for old, new in zip(first, topped) if old != new}
        assert moved
        relocked, _ = cards.top_up(TAXONOMY, first, SEED, locked=moved)
        assert all(old == new for old, new in zip(first, relocked) if old.id in moved)

    def test_a_feature_no_card_may_carry_is_reported_not_forced(self) -> None:
        taxonomy = json.loads(json.dumps(TAXONOMY))
        for family in taxonomy["families"].values():
            family["priors"].pop("text.drop_cap", None)
            for kind in family["kinds"].values():
                kind.get("boost", {}).pop("text.drop_cap", None)
        drawn = cards.draw(taxonomy, SEED)
        _, short = cards.top_up(taxonomy, drawn, SEED)
        assert "text.drop_cap" in short


class TestEveryCardIsSound:
    def test_no_drawn_card_has_a_problem(self, drawn: list[cards.Card]) -> None:
        assert {card.id: cards.problems(TAXONOMY, card) for card in drawn
                if cards.problems(TAXONOMY, card)} == {}

    def test_the_pilot_spans_families_styles_and_languages(self, drawn: list[cards.Card]) -> None:
        pilot = [card for card in drawn if card.pilot]
        assert len(pilot) == 50
        assert all(card.origin == "generated" for card in pilot)
        assert {card.family for card in pilot} == set(TAXONOMY["families"])
        assert len({card.style for card in pilot}) >= 8
        assert {card.language for card in pilot} == set(TAXONOMY["languages"])

    def test_the_pilot_widens_keeping_its_cards(self, drawn: list[cards.Card]) -> None:
        widened = cards.widen_pilot(TAXONOMY, drawn, SEED + 1, 100)
        first = {card.id for card in drawn if card.pilot}
        pilot = [card for card in widened if card.pilot]
        assert len(pilot) == 100 and first < {card.id for card in pilot}
        assert all(card.origin == "generated" for card in pilot)
        generated = Counter(card.family for card in drawn if card.origin == "generated")
        for family, count in Counter(card.family for card in pilot).items():
            assert abs(count - 100 * generated[family] / 500) < 1, family
        assert [replace(card, pilot=False) for card in widened] == [
            replace(card, pilot=False) for card in drawn]

    @pytest.fixture
    def sound(self, drawn: list[cards.Card]) -> cards.Card:
        return next(card for card in drawn if card.kind == "invoice"
                    and card.arrangement == "arr.one_column" and len(card.features) < 6)

    def test_seven_features_are_too_many(self, sound: cards.Card) -> None:
        extra = [fid for fid in cards.other_feature_ids(TAXONOMY) if fid not in sound.features]
        crowded = replace(sound, features=tuple(sound.features) + tuple(extra[:7]))
        assert any("other features" in p for p in cards.problems(TAXONOMY, crowded))

    def test_a_long_table_on_a_sparse_page(self, sound: cards.Card) -> None:
        planted = replace(sound, density="sparse", features=("table.long", "kv.inline", "fig.logo"))
        assert "table.long with density:sparse" in cards.problems(TAXONOMY, planted)

    def test_a_receipt_in_three_columns(self, drawn: list[cards.Card]) -> None:
        receipt = next(card for card in drawn if card.kind == "receipt")
        planted = replace(receipt, arrangement="arr.three_columns")
        assert any("arr.three_columns not allowed" in p for p in cards.problems(TAXONOMY, planted))

    def test_european_numbers_on_an_english_page(self, sound: cards.Card) -> None:
        planted = replace(sound, language="en", locale="en-GB",
                          features=("fmt.eu_numbers", "kv.inline", "fig.logo"))
        assert "fmt.eu_numbers with language:en" in cards.problems(TAXONOMY, planted)

    def test_two_columns_narrower_than_they_fit(self, sound: cards.Card) -> None:
        planted = replace(sound, arrangement="arr.two_columns", width=600)
        assert any(p.startswith("width 600") for p in cards.problems(TAXONOMY, planted))

    def test_a_feature_the_kind_excludes(self, drawn: list[cards.Card]) -> None:
        receipt = next(card for card in drawn if card.kind == "receipt")
        planted = replace(receipt, features=("kv.over", "look.rules", "fig.logo"))
        assert any("kv.over not allowed" in p for p in cards.problems(TAXONOMY, planted))


class TestTheFileOnDisk:
    def test_cards_json_holds_sound_cards_with_coverage_met(self) -> None:
        seed, on_disk = cards.load(REPO / "corpus" / "cards.json")
        assert seed == SEED
        assert len(on_disk) == 600
        assert all(not cards.problems(TAXONOMY, card) for card in on_disk)
        assert cards.shortfalls(TAXONOMY, on_disk) == {}
        assert sum(card.pilot for card in on_disk) == 100

    def test_cards_json_is_the_seeded_draw_but_for_the_cards_its_history_names(
            self, drawn: list[cards.Card]) -> None:
        data = json.loads((REPO / "corpus" / "cards.json").read_text(encoding="utf-8"))
        changed = {card_id for entry in data["history"][1:] for card_id in entry["changed"]}
        _, on_disk = cards.load(REPO / "corpus" / "cards.json")
        assert [card for card in on_disk if card.id not in changed] == [
            card for card in drawn if card.id not in changed]
