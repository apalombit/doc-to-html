"""Spec 0014 — every printed line has a place.

Step 1: a Zone holds the lines its Kind has no place for, `Zone.extra`, and
the render draws them before or after the body. `cells_of` yields them
last, so `locate`, `unclaimed` and `looks` see them as Cells.

Step 2: each printed line `locate.unclaimed` flags is read again on its own
crop with the prose prompt — `Conversion._read_unclaimed` — and kept in its
Zone's `extra` unless the Zone already prints it (`locate.holds`).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from doc_to_html.ir import (BBox, Block, Document, Kind, Pair, Reading, Row, RowRole,
                            Source, Style, Unclaimed, Zone, cell)
from doc_to_html.locate import cells_of, holds
from doc_to_html.orchestrator import Conversion, EngineSet
from doc_to_html.preprocess import Rectified
from doc_to_html.render import render
from doc_to_html.trace import Disposition
from doc_to_html.wire import contents_into

IR = re.compile(r'<script type="application/json" id="doc-ir">.*?</script>', re.S)


def page(zones: list[Zone]) -> Document:
    return Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                  rectified_width=1000, rectified_height=1000),
                    style=Style(body_px=10.0), zones=zones, page_px=1000)


def placed(text: str, top: float) -> object:
    return cell(text, bbox=BBox(0.1, top, 0.6, top + 0.012))


def note(text: str, top: float | None) -> Block:
    line = cell(text) if top is None else placed(text, top)
    return Block(kind="paragraph", lines=[line])  # type: ignore[list-item]


def ticks(*extra: Block) -> Zone:
    """`form_0007`'s tick boxes, a pairs Zone, with its note under them."""
    return Zone(kind=Kind.PAIRS, bbox=BBox(0.1, 0.2, 0.9, 0.4), complete=True,
                pairs=[Pair(placed("Standard", 0.22), placed("☐", 0.22)),  # type: ignore[arg-type]
                       Pair(placed("Concession", 0.26), placed("☑", 0.26))],  # type: ignore[arg-type]
                extra=list(extra))


def grid(*extra: Block) -> Zone:
    return Zone(kind=Kind.TABLE, bbox=BBox(0.1, 0.2, 0.9, 0.4), complete=True,
                rows=[Row(cells=[placed("Time", 0.25), placed("Monday", 0.25)],  # type: ignore[list-item]
                          role=RowRole.HEADER),
                      Row(cells=[placed("09:00", 0.29), placed("Mathematics", 0.29)])],  # type: ignore[list-item]
                extra=list(extra))


def drawn(zone: Zone) -> str:
    return IR.sub("", render(page([zone])))


class TestAZoneHoldsTheLinesItsKindHasNoPlaceFor:

    def test_a_note_placed_under_the_pairs_is_drawn_after_them(self) -> None:
        html = drawn(ticks(note("Tick one category.", 0.33)))
        assert html.index("Concession") < html.index("Tick one category.")

    def test_a_line_placed_above_the_first_row_is_drawn_first(self) -> None:
        html = drawn(grid(note("Week A", 0.21)))
        assert html.index("Week A") < html.index("Time")

    def test_a_line_nothing_placed_is_drawn_after(self) -> None:
        html = drawn(grid(note("Mathematics Science English", None)))
        assert html.index("Mathematics</") < html.index("Mathematics Science English")

    def test_it_is_drawn_inside_the_zones_own_container(self) -> None:
        html = drawn(ticks(note("Tick one category.", 0.33)))
        section = re.search(r'<section class="zone[^"]*".*?</section>', html, re.S)
        assert section is not None and "Tick one category." in section.group(0)

    def test_the_body_is_drawn_as_it_was(self) -> None:
        html = drawn(ticks(note("Tick one category.", 0.33)))
        assert re.sub(r"<p[^>]*>Tick one category\.</p>", "", html) == drawn(ticks())


class TestItemsTheZoneHasNoPlaceFor:

    def items(self, *lefts: float) -> list[Block]:
        return [Block(kind="item", lines=[cell(word, bbox=BBox(left, 0.35, left + 0.08, 0.362))])
                for word, left in zip(("Mathematics", "Science", "English"), lefts)]

    def test_items_printed_on_one_line_are_drawn_on_one_line(self) -> None:
        html = drawn(grid(*self.items(0.1, 0.25, 0.4)))
        assert re.search(r'<ul style="display:flex[^"]*"><li>Mathematics</li>'
                         r'<li>Science</li><li>English</li></ul>', html)

    def test_items_printed_down_the_page_are_a_list(self) -> None:
        listed = self.items(0.1, 0.1, 0.1)
        for index, block in enumerate(listed):
            box = block.lines[0].bbox
            assert box is not None
            block.lines[0].bbox = BBox(box.left, 0.35 + 0.02 * index,
                                       box.right, 0.362 + 0.02 * index)
        html = drawn(grid(*listed))
        assert "<ul><li>Mathematics</li><li>Science</li><li>English</li></ul>" in html


class TestTheCellsOfAZone:

    def test_the_extra_lines_come_last_with_no_row(self) -> None:
        zone = grid(note("Legend", 0.35))
        cells = cells_of(zone)
        assert [c.text for c, _ in cells][-1] == "Legend"
        assert cells[-1][1] is None
        assert [row for _, row in cells[:-1]] == [0, 0, 1, 1]


class TestTheJson:

    def test_extra_survives_the_round_trip(self) -> None:
        document = page([ticks(note("Tick one category.", 0.33))])
        back = Document.from_json(document.to_json())
        assert back.zones[0].extra == document.zones[0].extra
        assert back.to_json() == document.to_json()

    def test_an_ir_written_before_it_reads_back_empty(self) -> None:
        raw = page([ticks()]).to_json().replace('"extra": [],', "")
        assert '"extra"' not in raw
        assert Document.from_json(raw).zones[0].extra == []


# Step 2: each line `locate.unclaimed` flags is read on its own crop, with the
# prose prompt, and kept in its Zone's `extra` unless the Zone prints it.

class LineReader:
    """An Engine that answers each prose question with the next reply, through
    the real mapping, and records the box it was asked about."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.asked: list[tuple[Kind, BBox | None]] = []

    def extract_zone(self, image: object, zone: Zone,
                     hint: str | None = None, grid: object = None) -> Zone:
        self.asked.append((zone.kind, zone.bbox))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return contents_into(zone, reply, read=lambda t: Reading(engine="test", text=t))


LINE = BBox(0.03, 0.44, 0.36, 0.45)
NOTE = '{"blocks": [{"kind": "paragraph", "lines": ["Tick one category."]}]}'


def read_again(zone: Zone, *replies: str | Exception,
               lines: list[BBox] | None = None) -> tuple[Document, LineReader, Conversion]:
    engine = LineReader(*replies)
    document = page([zone])
    document.unclaimed = [Unclaimed(zone_index=0, bbox=box, words=3)
                          for box in (lines or [LINE])]
    conversion = Conversion(
        source=Path("unused.png"),
        engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                          extract=engine, audit=engine))
    image = np.full((400, 400, 3), 255, dtype=np.uint8)
    conversion._read_unclaimed(Rectified(image=image, source=document.source), document)
    return document, engine, conversion


def unclaimed_events(conversion: Conversion) -> list[object]:
    return [e for e in conversion.trace.events if e.step == "unclaimed"]


class TestReadWhatNobodyRead:

    def test_the_line_is_read_once_as_prose_on_its_own_box(self) -> None:
        _, engine, _ = read_again(ticks(), NOTE)
        assert engine.asked == [(Kind.PROSE, LINE)]

    def test_a_line_the_zone_does_not_print_is_kept_in_its_extra(self) -> None:
        document, _, conversion = read_again(ticks(), NOTE)
        zone = document.zones[0]
        assert [[c.text for c in b.lines] for b in zone.extra] == [["Tick one category."]]
        assert [p.label.text for p in zone.pairs] == ["Standard", "Concession"]
        event = unclaimed_events(conversion)[0]
        assert event.disposition is Disposition.ACCEPTED  # type: ignore[attr-defined]
        assert event.data["kept"] == ["Tick one category."]  # type: ignore[attr-defined]

    def test_a_line_the_zone_already_prints_is_refused(self) -> None:
        printed = '{"blocks": [{"kind": "paragraph", "lines": ["CONCESSION"]}]}'
        document, _, conversion = read_again(ticks(), printed)
        assert document.zones[0].extra == []
        event = unclaimed_events(conversion)[0]
        assert event.disposition is Disposition.REJECTED  # type: ignore[attr-defined]
        assert event.data["reason"] == "the Zone already prints what was read"  # type: ignore[attr-defined]

    def test_a_line_read_as_words_its_zone_prints_one_by_one_is_kept_whole(self) -> None:
        """`timetable_0019`'s legend comes back five items, each a word its
        grid prints too; the page prints them again, as a line."""
        legend = ('{"blocks": [' + ", ".join(
            f'{{"kind": "item", "lines": ["{word}"]}}'
            for word in ("Monday", "Mathematics")) + "]}")
        document, _, _ = read_again(grid(), legend)
        assert [[c.text for c in b.lines] for b in document.zones[0].extra] == [
            ["Monday"], ["Mathematics"]]

    def test_a_line_read_twice_is_kept_once(self) -> None:
        document, _, _ = read_again(ticks(), NOTE, NOTE, lines=[LINE, LINE])
        assert len(document.zones[0].extra) == 1

    def test_a_call_that_raises_costs_that_line_alone(self) -> None:
        document, _, conversion = read_again(
            ticks(), RuntimeError("no answer"), NOTE, lines=[LINE, LINE])
        assert len(document.zones[0].extra) == 1
        assert document.failures == []
        first, second = unclaimed_events(conversion)
        assert first.disposition is Disposition.REJECTED  # type: ignore[attr-defined]
        assert second.disposition is Disposition.ACCEPTED  # type: ignore[attr-defined]

    def test_nothing_unclaimed_asks_nothing(self) -> None:
        engine = LineReader()
        document = page([ticks()])
        conversion = Conversion(
            source=Path("unused.png"),
            engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                              extract=engine, audit=engine))
        image = np.full((400, 400, 3), 255, dtype=np.uint8)
        conversion._read_unclaimed(Rectified(image=image, source=document.source), document)
        assert engine.asked == [] and unclaimed_events(conversion) == []

    def test_extracting_the_zone_again_clears_its_extra(self) -> None:
        zone = ticks(note("Tick one category.", 0.33))
        zone.complete = False
        engine = LineReader('{"pairs": [{"label": "Standard", "value": "☐"}]}')
        document = page([zone])
        conversion = Conversion(
            source=Path("unused.png"),
            engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                              extract=engine, audit=engine))
        conversion.classification_ran = True
        image = np.full((400, 400, 3), 255, dtype=np.uint8)
        conversion._extract(Rectified(image=image, source=document.source), document)
        assert document.zones[0].extra == []


class TestTheZoneAlreadyPrintsIt:

    def test_folded_inside_one_cell(self) -> None:
        assert holds(ticks(), "concession")

    def test_inside_a_row_read_together(self) -> None:
        assert holds(grid(), "09:00 Mathematics")

    def test_inside_its_title(self) -> None:
        zone = ticks()
        zone.title = "2. Membership category"
        assert holds(zone, "MEMBERSHIP CATEGORY")

    def test_a_line_spread_over_cells_of_other_rows_is_not(self) -> None:
        assert not holds(grid(), "Mathematics Science English")

    def test_an_empty_text_is_held(self) -> None:
        assert holds(ticks(), " · ")
