"""Spec 0023, arm D2: GLM-OCR's regions mapped into the IR.

Every case is built by hand: no dev page's regions are read here, and no
panel page's ever is."""
from __future__ import annotations

from doc_to_html.adapter import (Region, document_of, groups_of, plain, regions_of,
                                 rows_of)
from doc_to_html.ir import BBox, Kind, Role, RowRole, Source

SOURCE = Source(path="page.png", sha256="0" * 64, width=1000, height=1000)


def region(index: int, label: str, box: tuple[int, int, int, int], content: str = "x") -> dict:
    return {"index": index, "label": label, "bbox_2d": list(box), "content": content}


def regions(*raw: dict) -> list[Region]:
    return regions_of(list(raw))


def box(left: int, top: int, right: int, bottom: int) -> BBox:
    return BBox(left / 1000, top / 1000, right / 1000, bottom / 1000)


class TestPlain:
    def test_inline_maths_is_set_as_printed(self) -> None:
        assert plain("oven to $ 200^{\\circ} \\mathrm{C} $ fan") == "oven to 200°C fan"
        assert plain("matter, $ \\mathrm{C O}_{2} $ , temperature") == "matter, CO₂, temperature"
        assert plain("NDIR CO $_2 $ with") == "NDIR CO₂ with"

    def test_named_marks_are_their_characters(self) -> None:
        assert plain("\\bigcirc A Oxygen \\bigcirc B") == "○ A Oxygen ○ B"
        assert plain("$ \\checkmark $ NDIR") == "✓ NDIR"

    def test_raised_and_lowered_runs(self) -> None:
        assert plain("H<sub>2</sub>O") == "H₂O"
        assert plain("×10^9/L") == "×10⁹/L"
        assert plain("mL/min/1.73m<sup>2</sup>") == "mL/min/1.73m²"

    def test_nothing_read_is_dropped(self) -> None:
        assert plain("<sup>a</sup>") == "^a"
        assert plain("Total: 12.50") == "Total: 12.50"


class TestTables:
    def test_a_span_stands_at_its_first_slot_over_empty_cells(self) -> None:
        rows = rows_of("<table><thead><tr><th>Test</th><th colspan=\"2\">Value</th></tr></thead>"
                       "<tr><td rowspan=\"2\">A</td><td>1</td><td>2</td></tr>"
                       "<tr><td>3</td><td>4</td></tr></table>")
        assert [[c.text for c in r.cells] for r in rows] == [["Test", "Value", ""],
                                                              ["A", "1", "2"], ["", "3", "4"]]
        assert rows[0].role is RowRole.HEADER and rows[1].role is RowRole.DATA
        assert rows[0].cells[1].span == (1, 2) and rows[1].cells[0].span == (2, 1)
        assert rows[1].cells[1].span is None

    def test_a_label_over_its_value_in_one_cell_keeps_its_line(self) -> None:
        (row,) = rows_of("<table><tr><td>PATIENT\nTomasz Wiśniewski</td>"
                         "<td>Net pay<br>£2,998.74</td></tr></table>")
        assert [(c.text, [b.text for b in c.below]) for c in row.cells] == [
            ("PATIENT", ["Tomasz Wiśniewski"]), ("Net pay", ["£2,998.74"])]


class TestGroups:
    def test_a_column_stack_is_one_group_and_a_far_line_is_not(self) -> None:
        found = groups_of(regions(
            region(0, "text", (100, 100, 400, 125)),
            region(1, "text", (100, 130, 380, 155)),
            region(2, "text", (100, 300, 380, 325))), [])
        assert [[r.index for r in g] for g in found] == [[0, 1], [2]]

    def test_lines_side_by_side_are_two_stacks(self) -> None:
        found = groups_of(regions(
            region(0, "text", (100, 100, 300, 125)), region(1, "text", (500, 100, 800, 125)),
            region(2, "text", (100, 130, 300, 155)), region(3, "text", (500, 130, 800, 155))), [])
        assert sorted([r.index for r in g] for g in found) == [[0, 2], [1, 3]]

    def test_overlap_without_a_shared_edge_does_not_stack(self) -> None:
        # The recipe's VEGETARIAN chip over its METHOD heading.
        found = groups_of(regions(region(0, "text", (404, 166, 498, 193)),
                                  region(1, "text", (386, 205, 470, 230))), [])
        assert len(found) == 2

    def test_a_heading_opens_a_stack_two_lines_above_it_and_joins_none(self) -> None:
        found = groups_of(regions(
            region(0, "text", (30, 171, 955, 232)),
            region(1, "paragraph_title", (31, 256, 148, 281)),
            region(2, "text", (31, 312, 295, 339)),
            region(3, "text", (31, 352, 327, 379))), [])
        assert [[r.index for r in g] for g in found] == [[0], [1, 2, 3]]

    def test_a_card_is_one_group_and_a_wide_panel_only_bounds_stacks(self) -> None:
        card = box(20, 60, 330, 300)
        panel = box(400, 60, 990, 600)
        found = groups_of(regions(
            region(0, "text", (40, 80, 120, 100)), region(1, "text", (40, 220, 250, 245)),
            region(2, "text", (40, 270, 90, 290)), region(3, "text", (200, 272, 240, 288)),
            region(4, "text", (420, 80, 600, 105)), region(5, "text", (700, 80, 900, 105)),
            region(6, "text", (420, 110, 600, 135))), [card, panel])
        assert sorted([r.index for r in g] for g in found) == [[0, 1, 2, 3], [4, 6], [5]]

    def test_a_region_alone_in_a_box_joins_no_stack(self) -> None:
        chip = box(95, 155, 310, 200)
        found = groups_of(regions(region(0, "text", (100, 100, 300, 140)),
                                  region(1, "text", (100, 160, 300, 195))), [chip])
        assert len(found) == 2


class TestDocument:
    def test_a_heading_over_its_table_is_its_title_whatever_comes_between(self) -> None:
        document = document_of([
            region(0, "paragraph_title", (40, 330, 140, 358), "EARNINGS"),
            region(1, "text", (600, 175, 960, 290), "Tax code 1257L\nNI number QQ"),
            region(2, "table", (36, 371, 577, 641),
                   "<table><tr><th>Description</th></tr><tr><td>Basic</td></tr></table>")],
            SOURCE)
        tables = [z for z in document.zones if z.kind is Kind.TABLE]
        assert len(tables) == 1 and tables[0].title == "EARNINGS"
        assert tables[0].bbox is not None and abs(tables[0].bbox.top - 0.330) < 1e-9
        assert not any(z.blocks and z.blocks[0].kind == "heading" for z in document.zones)

    def test_a_sliver_of_overlap_does_not_share_a_band(self) -> None:
        document = document_of([
            region(0, "header", (32, 41, 289, 99), "Northfield Pathology"),
            region(1, "table", (34, 90, 965, 804), "<table><tr><td>a</td></tr></table>")],
            SOURCE)
        header, table = document.zones
        assert header.role is Role.HEADER and header.band < table.band

    def test_a_line_end_the_reader_writes_is_kept(self) -> None:
        document = document_of([region(0, "text", (100, 100, 400, 180), "Tax code\nNI number")],
                               SOURCE)
        (zone,) = document.zones
        assert zone.blocks[0].kind == "address"
        assert [c.text for c in zone.blocks[0].lines] == ["Tax code", "NI number"]

    def test_bullets_are_items_and_a_picture_is_kept_with_no_text(self) -> None:
        document = document_of([
            region(0, "text", (100, 100, 400, 180), "- one\n- two"),
            region(1, "image", (500, 100, 900, 400), "")], SOURCE)
        listed, picture = document.zones
        assert listed.kind is Kind.LIST and [b.lines[0].text for b in listed.blocks] == ["one", "two"]
        assert picture.kind is Kind.FIGURE

    def test_an_empty_region_is_dropped(self) -> None:
        assert regions_of([region(0, "text", (1, 1, 2, 2), "  ")]) == []
