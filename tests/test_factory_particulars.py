"""Each card's particulars — spec 0020, after the pilot.

The same card always gets the same particulars; they come from its own
locale's lists; the dates spread over the whole range; and the names the
pilot overused are on no list.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from doc_to_html.factory import cards, particulars

REPO = Path(__file__).resolve().parent.parent
_, CARDS = cards.load(REPO / "corpus" / "cards.json")
GENERATED = [card for card in CARDS if card.origin == "generated"]


def test_a_card_always_gets_the_same_particulars() -> None:
    assert [particulars.particulars(c) for c in GENERATED[:20]] == [
        particulars.particulars(c) for c in GENERATED[:20]]


def test_they_come_from_the_cards_own_locale() -> None:
    for card in GENERATED:
        given = particulars.particulars(card)
        locale = card.locale or "en-GB"
        assert all(place in particulars.PLACES[locale] for place in given["places"])
        for person in given["people"]:
            assert any(person.startswith(first + " ") for first in particulars.GIVEN[locale])
            assert any(person.endswith(" " + last) for last in particulars.SURNAMES[locale])
        assert len(set(given["people"])) == 3 and len(set(given["places"])) == 2


def test_the_dates_spread_over_the_range() -> None:
    dates = [date.fromisoformat(particulars.particulars(c)["date"]) for c in GENERATED]
    assert min(dates) >= particulars.FIRST and max(dates) <= particulars.LAST
    years = Counter(d.year for d in dates)
    assert set(years) == set(range(2019, 2028))
    assert max(Counter((d.year, d.month) for d in dates).values()) < 20


def test_no_list_holds_an_overused_name() -> None:
    lists = [particulars.NAME_WORDS, *particulars.GIVEN.values(),
             *particulars.SURNAMES.values(), *particulars.PLACES.values()]
    words = {word for names in lists for name in names for word in name.split()}
    assert not words & set(particulars.OVERUSED)


def test_every_locale_a_card_can_have_has_its_lists() -> None:
    for locale in {card.locale for card in GENERATED}:
        assert locale in particulars.GIVEN and locale in particulars.SURNAMES
        assert locale in particulars.PLACES
