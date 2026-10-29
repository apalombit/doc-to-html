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
from doc_to_html.projection import MIN_WIDTH

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
            if not entry["pages"]:
                continue
            free = [kind for kind, spec in entry["kinds"].items()
                    if "pages" not in spec and not spec.get("recast_only")]
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
        assert {card.family for card in pilot} == {
            family for family, entry in TAXONOMY["families"].items() if entry["pages"]}
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

    def test_a_recast_takes_only_free_cards_and_draws_them_afresh(
            self, drawn: list[cards.Card]) -> None:
        locked = {card.id for card in drawn if card.pilot}
        recast = cards.recast(TAXONOMY, drawn, SEED + 3, locked)
        moved = [(old, new) for old, new in zip(drawn, recast) if old != new]
        plan = TAXONOMY["recasts"]["plan"]
        assert len(moved) == sum(entry["count"] for entry in plan)
        assert not {old.id for old, _ in moved} & locked
        planned = {entry["kind"] for entry in plan if entry.get("kind")}
        for old, new in moved:
            entry = TAXONOMY["families"][old.family]["kinds"][old.kind]
            assert "pages" not in entry and old.kind not in planned, old.id
            assert (new.id, new.language, new.locale) == (old.id, old.language, old.locale)
            assert not cards.problems(TAXONOMY, new), new.id
            if new.kind in ("chart with caption", "book page"):
                assert "fig.chart" in new.features
        made = Counter(new.kind if new.family != "fragments" else "fragments"
                       for _, new in moved)
        for entry in plan:
            assert made[entry.get("kind", entry["family"])] == entry["count"]
        assert cards.recast(TAXONOMY, drawn, SEED + 3, locked) == recast

    def test_a_zoom_deals_the_open_slots_and_makes_parts_of_free_cards(
            self, drawn: list[cards.Card]) -> None:
        locked = {card.id for card in drawn if card.pilot}
        zoomed = cards.zoom(TAXONOMY, drawn, SEED + 4, locked, parts=100)
        assert zoomed == cards.zoom(TAXONOMY, drawn, SEED + 4, locked, parts=100)
        assert not any(card.origin == "pdf" for card in zoomed)
        assert [c.id for c in zoomed] == [c.id for c in drawn]
        for old, new in zip(drawn, zoomed):
            assert not cards.problems(TAXONOMY, new), new.id
            if old.origin == "pdf":
                assert (new.family, new.language) == (old.family, old.language)
            if old.id in locked:
                assert new == old
        parts = [(old, new) for old, new in zip(drawn, zoomed) if new.scope == "part"]
        assert len(parts) == 100
        for old, new in parts:
            assert new.family != "fragments" and (new.family, new.kind) != (None, None)
            assert old.origin == "pdf" or (old.family, old.kind) == (new.family, new.kind)
            assert 500 <= (new.width or 0) <= 800
            assert len(new.features) == TAXONOMY["features_per_card"][0]
        assert cards.Card.from_json(parts[0][1].to_json()) == parts[0][1]
        assert "scope" not in drawn[0].to_json()

    def test_a_part_is_held_to_a_part_s_width(self, drawn: list[cards.Card]) -> None:
        card = next(c for c in drawn if c.kind == "invoice" and c.arrangement == "arr.one_column")
        assert not cards.problems(TAXONOMY, replace(card, scope="part", width=600))
        assert cards.problems(TAXONOMY, replace(card, scope="part", width=900)) == [
            "width 900 outside 500-800"]
        assert cards.problems(TAXONOMY, replace(card, scope="zoom")) == ["scope 'zoom'"]

    def test_the_draw_never_deals_a_recast_kind(self, drawn: list[cards.Card]) -> None:
        recast_only = {kind for fam in TAXONOMY["families"].values()
                       for kind, entry in fam["kinds"].items() if entry.get("recast_only")}
        assert recast_only and not {card.kind for card in drawn} & recast_only
        assert not any(card.family == "fragments" for card in drawn)

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

    def test_no_card_or_kind_is_narrower_than_the_browser_lays_out(self) -> None:
        """Chrome lays out no page under `projection.MIN_WIDTH`, so a narrower
        card can never pass the validator's width check (c0014, 480 px)."""
        _, on_disk = cards.load(REPO / "corpus" / "cards.json")
        assert all((card.width or MIN_WIDTH) >= MIN_WIDTH for card in on_disk)
        for family, entry in TAXONOMY["families"].items():
            for kind in entry["kinds"]:
                assert cards.widths(TAXONOMY, family, kind)[0] >= MIN_WIDTH, kind

    def test_cards_json_is_the_seeded_draw_but_for_the_cards_its_history_names(
            self, drawn: list[cards.Card]) -> None:
        data = json.loads((REPO / "corpus" / "cards.json").read_text(encoding="utf-8"))
        changed = {card_id for entry in data["history"][1:] for card_id in entry["changed"]}
        _, on_disk = cards.load(REPO / "corpus" / "cards.json")
        assert [card for card in on_disk if card.id not in changed] == [
            card for card in drawn if card.id not in changed]
