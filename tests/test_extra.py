"""Spec 0014 — every printed line has a place.

Step 1: a Zone holds the lines its Kind has no place for, `Zone.extra`, and
the render draws them before or after the body. `cells_of` yields them
last, so `locate`, `unclaimed` and `looks` see them as Cells.
"""

from __future__ import annotations

import re

from doc_to_html.ir import (BBox, Block, Document, Kind, Pair, Row, RowRole,
                            Source, Style, Zone, cell)
from doc_to_html.locate import cells_of
from doc_to_html.render import render

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
