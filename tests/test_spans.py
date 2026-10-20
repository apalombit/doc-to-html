"""Cells that span — spec 0019, B1.

A small ruled grid shaped like `timetable_0019`'s: a time column and three
days, a lesson two slots long, a lesson's room printed under it and given by
the model as a row of its own, a line across the days, and a line read on its
own that the page prints in an empty drawn cell.
"""

from __future__ import annotations

from doc_to_html import spans
from doc_to_html.ir import (BBox, Cell, Document, Furniture, Kind, Look, Reading, Row,
                            RowRole, Source, Zone, Block)
from doc_to_html.render import render

EDGES = (0.10, 0.20, 0.40, 0.60, 0.80)
"""The grid's vertical edges: time, Monday, Tuesday, Wednesday."""

LINES = (0.30, 0.40, 0.50, 0.60, 0.70)
"""Its horizontal rules: under the header bar, and under each slot."""


def cell(text: str, box: tuple[float, float, float, float] | None = None,
         look: Look | None = None) -> Cell:
    return Cell(bbox=None if box is None else BBox(*box),
                readings=[Reading(engine="model", text=text)] if text else [], look=look)


def rule(left: float, top: float, right: float, bottom: float) -> Furniture:
    return Furniture(kind="rule", bbox=BBox(left, top, right, bottom), zone=0)


def grid_rules(skip_down: set[tuple[int, int]] = frozenset(),
               skip_across: set[tuple[int, int]] = frozenset()) -> list[Furniture]:
    """Every edge and every slot rule, less the pieces the page leaves out:
    `skip_down` (edge, slot) and `skip_across` (rule, lane)."""
    rules = []
    for edge, x in enumerate(EDGES):
        for slot in range(len(LINES) - 1):
            if (edge, slot) not in skip_down:
                rules.append(rule(x, LINES[slot], x + 0.002, LINES[slot + 1]))
    for line, y in enumerate(LINES[1:-1], start=1):
        for lane in range(len(EDGES) - 1):
            if (line, lane) not in skip_across:
                rules.append(rule(EDGES[lane], y, EDGES[lane + 1], y + 0.002))
    rules.append(rule(EDGES[0], LINES[-1], EDGES[-1], LINES[-1] + 0.002))
    return rules


def timetable() -> Document:
    """09:00 Monday Maths over two slots; Tuesday English with its room as a
    row of its own, given under Monday; 11:00 Registration across the days
    (no edge between them in that slot); 12:00 empty, `Lunch` read apart."""
    header = Row(role=RowRole.HEADER, cells=[
        cell("Time"), cell("Mon"), cell("Tue"), cell("Wed")])
    rows = [
        header,
        Row(cells=[cell("09:00", (0.11, 0.32, 0.15, 0.36)),
                   cell("Maths", (0.21, 0.32, 0.30, 0.36)),
                   cell("English", (0.41, 0.32, 0.50, 0.36)),
                   cell("Art", (0.61, 0.32, 0.70, 0.36))]),
        Row(cells=[cell(""), cell("A11 · Doran", (0.41, 0.36, 0.52, 0.38),
                                  Look(size=1.0, bold=False)),
                   cell(""), cell("")]),
        Row(cells=[cell("10:00", (0.11, 0.42, 0.15, 0.46)), cell(""),
                   cell("PE", (0.41, 0.42, 0.45, 0.46)),
                   cell("Art", (0.61, 0.42, 0.70, 0.46))]),
        Row(cells=[cell("11:00", (0.11, 0.52, 0.15, 0.56)), cell(""),
                   cell("Registration", (0.42, 0.52, 0.58, 0.56)), cell("")]),
        Row(cells=[cell("12:00", (0.11, 0.62, 0.15, 0.66)), cell(""), cell(""), cell("")]),
    ]
    zone = Zone(kind=Kind.TABLE, bbox=BBox(0.10, 0.20, 0.80, 0.70), rows=rows, complete=True,
                extra=[Block(kind="paragraph", lines=[cell("Lunch", (0.46, 0.62, 0.54, 0.66))])])
    furniture = grid_rules(
        skip_down={(2, 2), (3, 2), (2, 3), (3, 3)},   # no edges across 11:00 and 12:00
        skip_across={(1, 0 + 1)})                     # none under Monday's 09:00
    return Document(source=Source(path="t.png", sha256="", width=1000, height=1000),
                    zones=[zone], furniture=furniture)


def read() -> Document:
    document = timetable()
    spans.read(document)
    return document


def test_a_second_line_joins_the_cell_its_box_stands_in() -> None:
    rows = read().zones[0].rows
    assert [row.cells[0].text for row in rows] == ["Time", "09:00", "10:00", "11:00", "12:00"]
    english = rows[1].cells[2]
    assert [line.text for line in english.below] == ["A11 · Doran"]
    assert not rows[1].cells[1].below


def test_an_entry_spans_the_empty_slot_its_drawn_cell_covers() -> None:
    rows = read().zones[0].rows
    assert rows[1].cells[1].span == (2, 1)
    assert rows[1].cells[2].span is None, "a rule stands under Tuesday's 09:00"


def test_an_entry_across_undrawn_edges_spans_them_from_the_first() -> None:
    rows = read().zones[0].rows
    assert rows[3].cells[1].text == "Registration"
    assert rows[3].cells[1].span == (1, 3)


def test_a_line_read_apart_inside_an_empty_drawn_cell_is_its_text() -> None:
    document = read()
    zone = document.zones[0]
    assert zone.extra == []
    assert zone.rows[4].cells[1].text == "Lunch"
    assert zone.rows[4].cells[1].span == (1, 3)


def test_a_table_drawn_without_its_grid_is_left_alone() -> None:
    document = timetable()
    document.furniture = [item for item in document.furniture if not item.vertical]
    before = document.to_json()
    spans.read(document)
    assert document.to_json() == before


def test_reading_twice_reads_the_same() -> None:
    document = read()
    once = document.to_json()
    spans.read(document)
    assert document.to_json() == once


def test_the_ir_keeps_spans_and_lines_and_omits_them_unset() -> None:
    document = read()
    back = Document.from_json(document.to_json())
    rows = back.zones[0].rows
    assert rows[1].cells[1].span == (2, 1)
    assert [line.text for line in rows[1].cells[2].below] == ["A11 · Doran"]
    plain = Document(source=Source(path="p.png", sha256="", width=10, height=10),
                     zones=[Zone(kind=Kind.TABLE, rows=[Row(cells=[cell("a")])])])
    assert '"span"' not in plain.to_json() and '"below"' not in plain.to_json()


def test_the_render_draws_the_grid_as_the_page_does() -> None:
    page = render(read())
    assert 'rowspan="2"' in page and 'colspan="3"' in page
    assert ">English<div" in page and "A11 · Doran</div>" in page
    assert ">Lunch<" in page
    # The 10:00 Monday slot is under Maths: three cells in that row, not four.
    row = page.split(">10:00<")[1].split("</tr>")[0]
    assert row.count("<td") == 2
