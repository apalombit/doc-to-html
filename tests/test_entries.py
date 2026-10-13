"""Spec 0012, G6 — every entry placed by its own box.

A Block centred or set flush right in its lane is drawn so; a line the page
breaks stays broken, and an equation's number stays flush right; a table's
column is set the way its entries are, and an entry the page prints across
an empty neighbour spans it; a pairs list's labels are set flush right where
the page sets them so; a paragraph keeps its first-line indent; and a prose
Zone whose lines are justified is drawn justified.
"""

from __future__ import annotations

import re

from doc_to_html.ir import (BBox, Block, Document, Kind, Pair, Role, Row, RowRole,
                            Source, Style, Zone, cell)
from doc_to_html.render import (_Lane, _block_aligns, _broken, _column_aligns,
                                _indent, _labels_flush, _numeric_columns, _page,
                                _spans, render)
from doc_to_html.rhythm import _justified, _Line


def page(zones: list[Zone]) -> Document:
    return Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                  rectified_width=1000, rectified_height=1000),
                    style=Style(body_px=10.0), zones=zones, page_px=1000)


def prose(*blocks: Block, box: BBox, **fields: object) -> Zone:
    return Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, blocks=list(blocks),
                complete=True, **fields)  # type: ignore[arg-type]


def line(text: str, left: float, top: float, right: float) -> object:
    return cell(text, bbox=BBox(left, top, right, top + 0.012))


def paragraph(*lines: object, kind: str = "paragraph") -> Block:
    return Block(kind=kind, lines=list(lines))  # type: ignore[arg-type]


LANE = _Lane(low=0.05, high=0.95, alone=True)
PAGE = _page(page([]))


class TestABlockSetInItsLane:

    def test_a_centred_footer_under_a_footnote_is_centred(self) -> None:
        notes = prose(paragraph(line("3. Deferral was agreed at the Board meeting", 0.05, 0.90, 0.48)),
                      paragraph(line("Harbour Trust · Page 1 of 1", 0.37, 0.95, 0.63)),
                      box=BBox(0.05, 0.90, 0.63, 0.962))
        document = page([prose(paragraph(line("Body", 0.05, 0.1, 0.95)),
                               box=BBox(0.05, 0.1, 0.95, 0.112)), notes])
        aligns = _block_aligns(notes, document)
        assert aligns == {id(notes.blocks[1]): "center"}

    def test_a_zone_of_centred_blocks_is_centred_whole(self) -> None:
        title = prose(paragraph(line("CERTIFICATE OF COMPLETION", 0.30, 0.1, 0.70), kind="heading"),
                      Block(kind="mark", lines=[cell("✦")]),
                      box=BBox(0.30, 0.1, 0.70, 0.15))
        document = page([title, prose(paragraph(line("Body", 0.05, 0.3, 0.95)),
                                      box=BBox(0.05, 0.3, 0.95, 0.312))])
        assert set(_block_aligns(title, document).values()) == {"center"}
        assert len(_block_aligns(title, document)) == 2


class TestALineThePageBreaks:

    def test_a_line_ending_far_short_is_broken(self) -> None:
        block = paragraph(line("Enc. Condition survey report, cost schedule", 0.05, 0.1, 0.35),
                          line("cc: Ruth Okafor, Brightwater Housing Trust", 0.05, 0.12, 0.34))
        assert _broken(block, LANE, PAGE) == ({1}, set())

    def test_a_line_wrapped_at_the_edge_is_joined(self) -> None:
        block = paragraph(line("Thank you for instructing us to carry out the survey of", 0.05, 0.1, 0.94),
                          line("Wharfside Court.", 0.05, 0.12, 0.2))
        assert _broken(block, LANE, PAGE) == (set(), set())

    def test_an_equation_number_is_set_flush_right(self) -> None:
        block = paragraph(line("sum of daily mean temperatures. We fitted the relation", 0.05, 0.1, 0.80),
                          cell("Δh = α √F"),
                          line("(1)", 0.92, 0.14, 0.95),
                          line("where Δh is the heave in millimetres.", 0.07, 0.16, 0.6))
        breaks, right = _broken(block, LANE, PAGE)
        assert breaks == {1} and right == {2}

    def test_a_centred_pair_of_lines_is_measured_by_width(self) -> None:
        lane = _Lane(low=0.55, high=0.83, alone=False)
        block = paragraph(line("Helena Brandt", 0.721, 0.80, 0.809),
                          line("COURSE LEADER", 0.712, 0.83, 0.817))
        assert _broken(block, lane, PAGE) == ({1}, set())

    def test_a_block_out_of_its_lane_is_not_judged(self) -> None:
        lane = _Lane(low=0.3, high=0.5, alone=False)
        block = paragraph(line("For small teams that plan", 0.38, 0.1, 0.53),
                          line("together.", 0.47, 0.12, 0.526))
        assert _broken(block, lane, PAGE) == (set(), set())


def receipt() -> Zone:
    rows = [Row(role=RowRole.DATA, cells=[line("1", 0.056, 0.2, 0.070),
                                          line("Flat white", 0.12, 0.2, 0.31),
                                          line("3.40", 0.87, 0.2, 0.944)]),
            Row(role=RowRole.DATA, cells=[line("2", 0.056, 0.23, 0.070),
                                          line("Cortado", 0.12, 0.23, 0.25),
                                          line("6.20", 0.87, 0.23, 0.944)]),
            Row(role=RowRole.SUMMARY, cells=[line("Subtotal", 0.056, 0.3, 0.208), cell(""),
                                             line("26.45", 0.85, 0.3, 0.944)]),
            Row(role=RowRole.HEADER, cells=[cell("AID A000000031010"), cell(""), cell("")])]
    return Zone(kind=Kind.TABLE, role=Role.BODY, bbox=BBox(0.05, 0.2, 0.95, 0.4),
                rows=rows, complete=True)


class TestATablesEntriesByTheirBoxes:

    def test_an_entry_across_an_empty_neighbour_spans_it(self) -> None:
        assert _spans(receipt(), PAGE, set()) == {(2, 0): 2, (3, 0): 3}

    def test_the_spans_are_drawn(self) -> None:
        html = render(page([receipt()]))
        assert re.search(r'<td colspan="2"[^>]*>Subtotal</td>', html)
        assert re.search(r'<th colspan="3"[^>]*>AID A000000031010</th>', html)

    def test_tiles_set_left_over_their_numbers(self) -> None:
        tiles = Zone(kind=Kind.TABLE, role=Role.BODY, bbox=BBox(0.05, 0.08, 0.6, 0.11),
                     complete=True, rows=[
                         Row(role=RowRole.HEADER, cells=[line("OPENING BALANCE", 0.048, 0.082, 0.170),
                                                         line("PAID IN", 0.224, 0.082, 0.270)]),
                         Row(role=RowRole.DATA, cells=[line("2,418.50", 0.048, 0.094, 0.117),
                                                       line("6,940.00", 0.224, 0.094, 0.293)])])
        assert _column_aligns(tiles, PAGE, {}, _numeric_columns(tiles)) == {0: "left", 1: "left"}

    def test_entries_of_one_width_say_nothing(self) -> None:
        assert _column_aligns(receipt(), PAGE, {}, _numeric_columns(receipt())) == {}


class TestLabelsFlushRight:

    def test_labels_ending_together_are_flush(self) -> None:
        zone = Zone(kind=Kind.PAIRS, role=Role.BODY, bbox=BBox(0.1, 0.2, 0.4, 0.3), complete=True,
                    pairs=[Pair(label=line("Name", 0.15, 0.2, 0.18), value=line("Acme", 0.19, 0.2, 0.3)),
                           Pair(label=line("Tax Office", 0.12, 0.22, 0.18),  # type: ignore[arg-type]
                                value=line("A' Moon", 0.19, 0.22, 0.25))])  # type: ignore[arg-type]
        assert _labels_flush(zone, PAGE)
        html = render(page([zone]))
        assert html.count('text-align:right">') >= 2


class TestFirstLineIndentAndJustification:

    def test_a_first_line_set_in_is_an_indent(self) -> None:
        block = paragraph(line("Most footbridges built by small", 0.066, 0.1, 0.48),
                          line("with a single span of 15 to 35 m.", 0.05, 0.12, 0.48),
                          line("where the ground freezes, pad", 0.05, 0.14, 0.48))
        assert _indent(block, PAGE) == "text-indent:16px"

    def test_two_lines_say_nothing(self) -> None:
        block = paragraph(line("Helena Brandt", 0.721, 0.80, 0.809),
                          line("COURSE LEADER", 0.712, 0.83, 0.817))
        assert _indent(block, PAGE) == ""

    def test_lines_ending_together_are_justified(self) -> None:
        body = 10.0
        lines = [_Line(0, 10, 100, 900), _Line(20, 30, 100, 901), _Line(40, 50, 100, 899),
                 _Line(60, 70, 100, 400)]
        assert _justified(lines, body)

    def test_ragged_lines_are_not(self) -> None:
        body = 10.0
        lines = [_Line(0, 10, 100, 900), _Line(20, 30, 100, 870), _Line(40, 50, 100, 885),
                 _Line(60, 70, 100, 400)]
        assert not _justified(lines, body)

    def test_right_set_lines_are_not(self) -> None:
        body = 10.0
        lines = [_Line(0, 10, 500, 900), _Line(20, 30, 450, 900), _Line(40, 50, 600, 900)]
        assert not _justified(lines, body)
