"""The cards every corpus page is written from — spec 0020, step 1.

**A card** names what one page must be: its family and kind, one
arrangement, one main type class, three to six other features, a style
family, a width, a density, a language and a locale. A writer turns it
into a page (`corpus/brief.md`); the validator confirms the features it
can (`check`); the contact sheets show the rest.

**Drawn at random inside agreed bounds** (`level-up.md` §4.7). Every
quota is met exactly, by construction:

- *families*: `taxonomy.json`'s pages, less each family's PDF slots;
- *kinds*: a kind with its own `pages` (receipts 40, the three clinical
  kinds 40 together) gets exactly that many, and the rest of the family
  is dealt round the other kinds, so no kind leads another by more than
  one card;
- *languages*: the shares are dealt over all 600 slots, PDF slots
  included. A PDF slot's language is the language wanted; step 4 chooses
  its page.

Then, per card and in this order: a style family by the kind's (or the
family's) weights; a main type class by the style's; an arrangement by the
kind's weights, among those that fit its widths; a width, in 20px steps,
at least the arrangement's minimum; a density; a locale. Last, 3–6 other
features by the family's priors, plus the kind's boosts and less its
exclusions, never two that `taxonomy.json`'s exclusions pair.

**The coverage top-up.** Every feature id must appear on at least 9 pages
in at least 3 kinds (`coverage`). While one misses, it is put on a card
of a kind that lacks it — added if the card has fewer than six features,
otherwise in place of the card's most plentiful feature, but only when
that feature stays above its own minimum. An arrangement or a main type
replaces the card's own. A card whose page is written is **locked** and
never changes. If no card can take a missing feature, `top_up` returns it
and the caller stops — spec 0020's "stop and ask".

**Seeded.** `draw(taxonomy, seed)` is a pure function of its inputs, and
`cards.json` records the seed.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

Taxonomy = dict[str, Any]

LOCALES: dict[str, dict[str, int]] = {
    "en": {"en-GB": 1, "en-US": 1},
    "it": {"it-IT": 1},
    "fr": {"fr-FR": 1},
    "es": {"es-ES": 1},
    "pt": {"pt-PT": 1, "pt-BR": 1},
}
"""The locale a language's page is written in. English is British or
American, Portuguese European or Brazilian, so dates and spellings vary
inside one language; each keeps the number format the spec asks for
(`1.234,56` in all four of the others; French `1 234,56`)."""


@dataclass(frozen=True)
class Card:
    """One page to be written. A PDF slot carries only its family and the
    language wanted until step 4 fills it from the page chosen."""

    id: str
    origin: str
    family: str
    language: str
    kind: str | None = None
    arrangement: str | None = None
    type: str | None = None
    features: tuple[str, ...] = ()
    style: str | None = None
    width: int | None = None
    density: str | None = None
    locale: str | None = None
    pilot: bool = False

    def tokens(self) -> set[str]:
        """Everything an exclusion pair can name about this card."""
        found = set(self.features)
        for value in (self.arrangement, self.type):
            if value:
                found.add(value)
        if self.density:
            found.add(f"density:{self.density}")
        if self.style:
            found.add(f"style:{self.style}")
        found.add(f"language:{self.language}")
        return found

    def all_features(self) -> tuple[str, ...]:
        """The arrangement, the main type and the others, as one list."""
        head = tuple(value for value in (self.arrangement, self.type) if value)
        return head + self.features

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["features"] = list(self.features)
        return data

    @staticmethod
    def from_json(data: dict[str, Any]) -> Card:
        return Card(**{**data, "features": tuple(data.get("features", ()))})


def load_taxonomy(path: Path) -> Taxonomy:
    taxonomy: Taxonomy = json.loads(path.read_text(encoding="utf-8"))
    return taxonomy


def feature_ids(taxonomy: Taxonomy) -> list[str]:
    """Every feature id, in the spec's order."""
    return [fid for group in taxonomy["features"].values() for fid in group]


def other_feature_ids(taxonomy: Taxonomy) -> list[str]:
    """The ids drawn as a card's 3–6 others: all but arrangement and type."""
    return [fid for name, group in taxonomy["features"].items()
            if name not in ("arrangement", "type_main") for fid in group]


def kind_entry(taxonomy: Taxonomy, family: str, kind: str) -> dict[str, Any]:
    entry: dict[str, Any] = taxonomy["families"][family]["kinds"][kind]
    return entry


def priors(taxonomy: Taxonomy, family: str, kind: str) -> dict[str, float]:
    """The weights a kind's other features are drawn by."""
    fam = taxonomy["families"][family]
    entry = kind_entry(taxonomy, family, kind)
    weights = {fid: float(fam["priors"].get(fid, 0)) for fid in other_feature_ids(taxonomy)}
    for fid, extra in entry.get("boost", {}).items():
        weights[fid] = weights.get(fid, 0.0) + float(extra)
    for fid in entry.get("exclude", ()):
        weights[fid] = 0.0
    return {fid: weight for fid, weight in weights.items() if weight > 0}


def widths(taxonomy: Taxonomy, family: str, kind: str) -> tuple[int, int]:
    entry = kind_entry(taxonomy, family, kind)
    low, high = entry.get("widths", taxonomy["families"][family]["widths"])
    return int(low), int(high)


def arrangements(taxonomy: Taxonomy, family: str, kind: str) -> dict[str, float]:
    """A kind's arrangements, only those whose minimum width fits it."""
    entry = kind_entry(taxonomy, family, kind)
    weights = entry.get("arrangements", taxonomy["families"][family]["arrangements"])
    _, high = widths(taxonomy, family, kind)
    least = taxonomy["min_width"]
    return {arr: float(weight) for arr, weight in weights.items()
            if weight > 0 and least.get(arr, 0) <= high}


def styles(taxonomy: Taxonomy, family: str, kind: str) -> dict[str, float]:
    entry = kind_entry(taxonomy, family, kind)
    weights = entry.get("styles", taxonomy["families"][family]["styles"])
    return {style: float(weight) for style, weight in weights.items() if weight > 0}


def densities(taxonomy: Taxonomy, family: str, kind: str) -> dict[str, float]:
    entry = kind_entry(taxonomy, family, kind)
    weights = entry.get("density", taxonomy["families"][family]["density"])
    return {name: float(weight) for name, weight in weights.items() if weight > 0}


def _pick(rng: random.Random, weights: dict[str, float]) -> str:
    names = sorted(weights)
    return rng.choices(names, weights=[weights[name] for name in names])[0]


def _exclusion_pairs(taxonomy: Taxonomy) -> list[tuple[str, str]]:
    return [(a, b) for a, b in taxonomy["exclusions"]["features"]]


def clashes(taxonomy: Taxonomy, tokens: set[str]) -> list[tuple[str, str]]:
    """The exclusion pairs a card's tokens hold both halves of."""
    return [(a, b) for a, b in _exclusion_pairs(taxonomy) if a in tokens and b in tokens]


def _width_for(rng: random.Random, taxonomy: Taxonomy, family: str, kind: str,
               arrangement: str) -> int:
    low, high = widths(taxonomy, family, kind)
    low = max(low, int(taxonomy["min_width"].get(arrangement, 0)))
    steps = (high - low) // 20
    return low + 20 * rng.randint(0, steps)


def _kinds_for(rng: random.Random, taxonomy: Taxonomy, family: str, count: int
               ) -> list[str]:
    """`count` kinds for a family's generated cards, shares exact."""
    kinds = {kind: entry for kind, entry in taxonomy["families"][family]["kinds"].items()
             if not entry.get("recast_only")}
    fixed = {kind: int(entry["pages"]) for kind, entry in kinds.items() if "pages" in entry}
    rest = [kind for kind in kinds if kind not in fixed]
    dealt = [kind for kind, pages in fixed.items() for _ in range(pages)]
    remaining = count - len(dealt)
    if remaining < 0:
        raise ValueError(f"{family}: fixed kind shares exceed {count} generated pages")
    order = list(rest)
    rng.shuffle(order)
    dealt += [order[index % len(order)] for index in range(remaining)]
    rng.shuffle(dealt)
    return dealt


def _languages(rng: random.Random, taxonomy: Taxonomy) -> list[str]:
    dealt = [lang for lang, pages in taxonomy["languages"].items() for _ in range(pages)]
    if len(dealt) != taxonomy["total"]:
        raise ValueError("language shares do not add up to the total")
    rng.shuffle(dealt)
    return dealt


def _features_for(rng: random.Random, taxonomy: Taxonomy, card: Card) -> tuple[str, ...]:
    assert card.kind
    weights = priors(taxonomy, card.family, card.kind)
    low, high = taxonomy["features_per_card"]
    wanted = rng.randint(low, high)
    chosen: list[str] = list(kind_entry(taxonomy, card.family, card.kind).get("always", ()))
    while len(chosen) < wanted:
        tokens = card.tokens() | set(chosen)
        open_ = {fid: weight for fid, weight in weights.items()
                 if fid not in tokens and not clashes(taxonomy, tokens | {fid})}
        if not open_:
            break
        chosen.append(_pick(rng, open_))
    return tuple(sorted(chosen))


def _drawn_as(rng: random.Random, taxonomy: Taxonomy, card: Card, with_locale: bool
              ) -> Card:
    """`card` drawn as its family and kind: style, main type, arrangement,
    width, density, the locale if asked, and its other features."""
    assert card.kind
    family, kind = card.family, card.kind
    style = _pick(rng, styles(taxonomy, family, kind))
    main = _pick(rng, {cls: float(w) for cls, w in taxonomy["styles"][style]["type"].items()})
    arrangement = _pick(rng, arrangements(taxonomy, family, kind))
    card = replace(
        card, style=style, type=main, arrangement=arrangement,
        width=_width_for(rng, taxonomy, family, kind, arrangement),
        density=_pick(rng, densities(taxonomy, family, kind)),
        locale=(_pick(rng, {k: float(v) for k, v in LOCALES[card.language].items()})
                if with_locale else card.locale),
        features=(),
    )
    return replace(card, features=_features_for(rng, taxonomy, card))


def draw(taxonomy: Taxonomy, seed: int) -> list[Card]:
    """Every card, PDF slots included, before the coverage top-up."""
    rng = random.Random(seed)
    languages = _languages(rng, taxonomy)
    cards: list[Card] = []
    for family, fam in taxonomy["families"].items():
        if not fam["pages"]:
            continue
        generated = int(fam["pages"]) - int(fam["pdf"])
        for kind in _kinds_for(rng, taxonomy, family, generated):
            card = Card(id="", origin="generated", family=family,
                        language=languages[len(cards)], kind=kind)
            cards.append(_drawn_as(rng, taxonomy, card, with_locale=True))
        for _ in range(int(fam["pdf"])):
            cards.append(Card(id="", origin="pdf", family=family,
                              language=languages[len(cards)]))
    return [replace(card, id=f"c{index + 1:04d}") for index, card in enumerate(cards)]


@dataclass
class Coverage:
    """Pages and kinds per feature id, and per pool once pools are dealt."""

    pages: Counter[str] = field(default_factory=Counter)
    kinds: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    pools: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))


def coverage(cards: Iterable[Card], pools: dict[str, str] | None = None) -> Coverage:
    """How often each feature id is on a card, in how many kinds, and per
    pool when `pools` maps card id to pool. PDF slots not yet filled count
    for nothing."""
    found = Coverage()
    for card in cards:
        for fid in card.all_features():
            found.pages[fid] += 1
            if card.kind:
                found.kinds[fid].add(card.kind)
            if pools and card.id in pools:
                found.pools[fid][pools[card.id]] += 1
    return found


def shortfalls(taxonomy: Taxonomy, cards: Sequence[Card]) -> dict[str, str]:
    """Each feature id below the coverage rule, with what it lacks."""
    rule = taxonomy["coverage"]
    found = coverage(cards)
    short = {}
    for fid in feature_ids(taxonomy):
        pages, kinds = found.pages[fid], len(found.kinds[fid])
        if pages < rule["pages"] or kinds < rule["kinds"]:
            short[fid] = f"{pages} pages in {kinds} kinds"
    return short


def _allowed(taxonomy: Taxonomy, card: Card, fid: str) -> bool:
    """Whether `fid` may stand on `card` at all, ignoring how many it holds."""
    assert card.kind and card.style
    groups = taxonomy["features"]
    if fid in groups["arrangement"]:
        return fid in arrangements(taxonomy, card.family, card.kind)
    if fid in groups["type_main"]:
        return bool(taxonomy["styles"][card.style]["type"].get(fid, 0) > 0)
    return fid in priors(taxonomy, card.family, card.kind)


def _with(taxonomy: Taxonomy, card: Card, fid: str, drop: str | None,
          rng: random.Random) -> Card:
    groups = taxonomy["features"]
    if fid in groups["arrangement"]:
        assert card.kind
        least = int(taxonomy["min_width"].get(fid, 0))
        width = card.width or 0
        if width < least:
            width = _width_for(rng, taxonomy, card.family, card.kind, fid)
        return replace(card, arrangement=fid, width=width)
    if fid in groups["type_main"]:
        return replace(card, type=fid)
    kept = [f for f in card.features if f != drop]
    return replace(card, features=tuple(sorted(kept + [fid])))


SLACK = 3
"""How far above its minimum a feature must stand before the top-up takes
one away to make room for another. The pools are dealt after the top-up,
and a feature sitting exactly at 9 pages has no room to put 2 in each."""


def top_up(taxonomy: Taxonomy, cards: list[Card], seed: int,
           locked: Iterable[str] = ()) -> tuple[list[Card], dict[str, str]]:
    """Cards with every feature at its minimum where that can be done, and
    what could not be met. `locked` names cards that must not change."""
    rng = random.Random(seed)
    rule = taxonomy["coverage"]
    groups = taxonomy["features"]
    fixed = set(locked)
    cards = list(cards)
    for _ in range(5000):
        short = shortfalls(taxonomy, cards)
        if not short:
            return cards, {}
        fid = sorted(short)[0]
        found = coverage(cards)
        per_kind: Counter[tuple[str, str]] = Counter(
            (other, card.kind) for card in cards if card.kind
            for other in card.all_features())
        need_kinds = len(found.kinds[fid]) < rule["kinds"]

        def spare(other: str, kind: str) -> bool:
            """Whether one `other` can leave a card of `kind` and the rule
            still hold for it, with `SLACK` pages to spare."""
            return (found.pages[other] >= rule["pages"] + SLACK
                    and (len(found.kinds[other]) > rule["kinds"]
                         or per_kind[(other, kind)] > 1))

        candidates: list[tuple[Card, str | None]] = []
        for card in cards:
            if (card.id in fixed or card.origin != "generated" or not card.kind
                    or fid in card.all_features() or not _allowed(taxonomy, card, fid)):
                continue
            if need_kinds and card.kind in found.kinds[fid]:
                continue
            drop: str | None
            if fid in groups["arrangement"]:
                drop = card.arrangement
            elif fid in groups["type_main"]:
                drop = card.type
            elif len(card.features) < taxonomy["features_per_card"][1]:
                drop = None
            else:
                kind = card.kind
                plenty = [f for f in card.features if spare(f, kind)]
                if not plenty:
                    continue
                drop = max(plenty, key=lambda f: (found.pages[f], f))
            if drop is not None and not spare(drop, card.kind):
                continue
            changed = _with(taxonomy, card, fid, drop, rng)
            if clashes(taxonomy, changed.tokens()):
                continue
            candidates.append((card, drop))
        if not candidates:
            return cards, short
        card, drop = rng.choice(candidates)
        cards[cards.index(card)] = _with(taxonomy, card, fid, drop, rng)
    return cards, shortfalls(taxonomy, cards)


def choose_pilot(taxonomy: Taxonomy, cards: list[Card], seed: int, count: int = 50
                 ) -> list[Card]:
    """`count` generated cards marked as the pilot: every family in
    proportion, at least eight style families, every language.

    Drawn again with the next seed until the spread holds, so the result
    is still a pure function of `seed`."""
    generated = [card for card in cards if card.origin == "generated"]
    by_family: dict[str, list[Card]] = defaultdict(list)
    for card in generated:
        by_family[card.family].append(card)
    share = {family: count * len(members) / len(generated)
             for family, members in by_family.items()}
    quota = {family: int(value) for family, value in share.items()}
    for family in sorted(share, key=lambda f: share[f] - quota[f], reverse=True):
        if sum(quota.values()) >= count:
            break
        quota[family] += 1
    for attempt in range(1000):
        rng = random.Random(seed + attempt)
        chosen = [card for family in sorted(by_family)
                  for card in rng.sample(by_family[family], quota[family])]
        if (len({card.style for card in chosen}) >= 8
                and {card.language for card in chosen} == set(taxonomy["languages"])):
            ids = {card.id for card in chosen}
            return [replace(card, pilot=card.id in ids) for card in cards]
    raise ValueError("no pilot spans eight style families and every language")


def widen_pilot(taxonomy: Taxonomy, cards: list[Card], seed: int, count: int
                ) -> list[Card]:
    """The pilot widened to `count` cards, the cards already in it kept.

    Each family takes its share of `count`, as in `choose_pilot`, less the
    pilot cards it already has; those are drawn from its other generated
    cards with `seed`. The widened pilot goes to dev, like the first."""
    generated = [card for card in cards if card.origin == "generated"]
    by_family: dict[str, list[Card]] = defaultdict(list)
    for card in generated:
        by_family[card.family].append(card)
    share = {family: count * len(members) / len(generated)
             for family, members in by_family.items()}
    quota = {family: int(value) for family, value in share.items()}
    for family in sorted(share, key=lambda f: share[f] - quota[f], reverse=True):
        if sum(quota.values()) >= count:
            break
        quota[family] += 1
    rng = random.Random(seed)
    ids = {card.id for card in cards if card.pilot}
    for family in sorted(by_family):
        rest = [card for card in by_family[family] if not card.pilot]
        held = len(by_family[family]) - len(rest)
        ids.update(card.id for card in rng.sample(rest, max(0, quota[family] - held)))
    return [replace(card, pilot=card.id in ids) for card in cards]


def recast(taxonomy: Taxonomy, cards: list[Card], seed: int, locked: Iterable[str] = ()
           ) -> list[Card]:
    """Unwritten generated cards recast as the kinds `taxonomy["recasts"]`
    plans, which the draw does not deal.

    Each entry of the plan takes `count` cards from the families it names
    (`"all"` for every family), in proportion to the cards each has left.
    It never takes a locked card, a card already recast, one of a kind
    with fixed pages, or one of a kind the plan adds to. Within a family the kind with the most cards left
    gives first, so no kind is emptied. A recast card keeps its id,
    language and locale. It is drawn afresh as its new family and kind, as
    `draw` would draw it, the features its kind lists as `always` first.
    The kinds of an entry naming none are dealt as `draw` deals a
    family's."""
    rng = random.Random(seed)
    fixed = set(locked)
    cards = list(cards)
    taken: set[str] = set()
    planned = {entry["kind"] for entry in taxonomy["recasts"]["plan"] if entry.get("kind")}
    for entry in taxonomy["recasts"]["plan"]:
        family, count = entry["family"], int(entry["count"])
        sources = (list(taxonomy["families"]) if entry["from"] == "all" else [entry["from"]])
        free: dict[str, list[Card]] = {}
        for source in sources:
            kinds = taxonomy["families"][source]["kinds"]
            free[source] = [
                card for card in cards
                if card.family == source and card.origin == "generated"
                and card.id not in fixed and card.id not in taken and card.kind in kinds
                and "pages" not in kinds[card.kind] and not kinds[card.kind].get("recast_only")
                and card.kind not in planned]
        total = sum(len(members) for members in free.values())
        if total < count:
            raise ValueError(f"{family}: {count} to recast, {total} cards free")
        share = {source: count * len(members) / total for source, members in free.items()}
        quota = {source: int(value) for source, value in share.items()}
        for source in sorted(share, key=lambda f: share[f] - quota[f], reverse=True):
            if sum(quota.values()) >= count:
                break
            quota[source] += 1
        chosen: list[Card] = []
        for source in sorted(quota):
            members = free[source]
            rng.shuffle(members)
            for _ in range(quota[source]):
                left = Counter(card.kind for card in members if card.id not in taken)
                most = max(left.values())
                kind = next(k for k in sorted(left, key=str) if left[k] == most)
                card = next(c for c in members if c.kind == kind and c.id not in taken)
                taken.add(card.id)
                chosen.append(card)
        targets = ([entry["kind"]] * count if entry.get("kind")
                   else _kinds_for(rng, taxonomy, family, count))
        index = {card.id: position for position, card in enumerate(cards)}
        for card, kind in zip(sorted(chosen, key=lambda c: c.id), targets):
            fresh = replace(card, family=family, kind=kind)
            cards[index[card.id]] = _drawn_as(rng, taxonomy, fresh, with_locale=False)
    return cards


def problems(taxonomy: Taxonomy, card: Card) -> list[str]:
    """Everything wrong with one card; empty for a sound one. A PDF slot
    not yet filled is sound with no fields."""
    found: list[str] = []
    if card.origin == "pdf" and card.kind is None:
        return found
    groups = taxonomy["features"]
    if card.arrangement not in groups["arrangement"]:
        found.append(f"arrangement {card.arrangement!r}")
    if card.type not in groups["type_main"]:
        found.append(f"main type {card.type!r}")
    low, high = taxonomy["features_per_card"]
    if card.origin == "generated" and not low <= len(card.features) <= high:
        found.append(f"{len(card.features)} other features")
    others = set(other_feature_ids(taxonomy))
    for fid in card.features:
        if fid not in others:
            found.append(f"{fid} is not an other feature")
    if len(set(card.features)) != len(card.features):
        found.append("a feature twice")
    for a, b in clashes(taxonomy, card.tokens()):
        found.append(f"{a} with {b}")
    if card.origin == "pdf":
        # A real page is what it is: its width and features are not drawn,
        # but its kind and locale are the taxonomy's like any card's.
        if card.kind not in taxonomy["families"][card.family]["kinds"]:
            found.append(f"kind {card.kind!r} not in {card.family}")
        if card.locale not in LOCALES[card.language]:
            found.append(f"locale {card.locale} for {card.language}")
    if card.origin == "generated":
        assert card.kind
        if card.kind not in taxonomy["families"][card.family]["kinds"]:
            found.append(f"kind {card.kind!r} not in {card.family}")
            return found
        for fid in card.all_features():
            if not _allowed(taxonomy, card, fid):
                found.append(f"{fid} not allowed on a {card.kind}")
        lo, hi = widths(taxonomy, card.family, card.kind)
        least = int(taxonomy["min_width"].get(card.arrangement or "", 0))
        if card.width is None or not max(lo, least) <= card.width <= hi:
            found.append(f"width {card.width} outside {max(lo, least)}-{hi}")
        if card.locale not in LOCALES[card.language]:
            found.append(f"locale {card.locale} for {card.language}")
    return found


def write(path: Path, cards: Sequence[Card], seed: int, note: str = "") -> None:
    payload = {
        "about": ("Every card of the corpus (spec 0020, step 1), drawn by "
                  "tools/corpus_cards.py from corpus/taxonomy.json."),
        "seed": seed,
        "note": note,
        "cards": [card.to_json() for card in cards],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")


def load(path: Path) -> tuple[int, list[Card]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return int(data["seed"]), [Card.from_json(item) for item in data["cards"]]


def coverage_table(taxonomy: Taxonomy, cards: Sequence[Card],
                   pools: dict[str, str] | None = None) -> str:
    """The printed table: feature × pages, kinds, families, and pools."""
    found = coverage(cards, pools)
    families: dict[str, Counter[str]] = defaultdict(Counter)
    for card in cards:
        for fid in card.all_features():
            families[fid][card.family] += 1
    names = list(taxonomy["families"])
    short = {name: taxonomy["families"][name].get("short", name[:3]) for name in names}
    pool_names = list(taxonomy["pools"]) if pools else []
    head = (f"{'feature':22} {'pages':>5} {'kinds':>5}  "
            + " ".join(f"{short[name]:>3}" for name in names)
            + ("  " + " ".join(f"{p:>5}" for p in pool_names) if pool_names else ""))
    lines = [head, "-" * len(head)]
    rule = taxonomy["coverage"]
    for fid in feature_ids(taxonomy):
        pages, kinds = found.pages[fid], len(found.kinds[fid])
        flag = "" if pages >= rule["pages"] and kinds >= rule["kinds"] else "  SHORT"
        if pools:
            if any(found.pools[fid][p] < rule["per_pool"] for p in pool_names):
                flag += "  POOL"
        lines.append(
            f"{fid:22} {pages:5} {kinds:5}  "
            + " ".join(f"{families[fid][name]:3}" for name in names)
            + ("  " + " ".join(f"{found.pools[fid][p]:5}" for p in pool_names)
               if pool_names else "")
            + flag)
    lines.append("families: " + ", ".join(f"{short[n]} = {n}" for n in names))
    return "\n".join(lines)
