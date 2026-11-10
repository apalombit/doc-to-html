"""Spec 0023, arm D2: GLM-OCR's regions mapped into the IR.

Every case is built by hand: no dev page's regions are read here, and no
panel page's ever is."""
from __future__ import annotations

from doc_to_html.adapter import (Region, document_of, formula, groups_of, plain, regions_of,
                                 rows_of, runs_of)
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
        assert plain("<sup>a</sup>") == "a"
        assert plain("Total: 12.50") == "Total: 12.50"


class TestRuns:
    """Spec 0024, group A: a raised or bold run the reader writes is a Run
    of its Cell, never a mark drawn as text (`3^rd`, `**year**`) or a
    character set against its neighbour as one word."""

    def runs(self, text: str) -> list[tuple[str, str]]:
        (cell,) = document_of([region(0, "text", (0, 0, 500, 30), text)], SOURCE).zones[0] \
            .blocks[0].lines
        return [(run.text, run.kind) for run in cell.runs]

    def test_a_raised_run_is_a_sup_run(self) -> None:
        assert self.runs("the 3<sup>rd</sup> floor") == [("the 3", "text"), ("rd", "sup"),
                                                         (" floor", "text")]
        assert self.runs("handed over $ ^{2} $") == [("handed over", "text"), ("²", "sup")]

    def test_bold_is_a_strong_run(self) -> None:
        assert self.runs("true only when **year** is a leap year") == [
            ("true only when ", "text"), ("year", "strong"), (" is a leap year", "text")]
        assert self.runs("<strong>A. Monitoring at home</strong>") == [
            ("A. Monitoring at home", "strong")]

    def test_a_printed_double_star_stays(self) -> None:
        assert self.runs("(c) 2 ** 3 ** 2") == [("(c) 2 ** 3 ** 2", "text")]
        assert self.runs("Card:***********4419") == [("Card:***********4419", "text")]

    def test_a_circled_number(self) -> None:
        assert plain("$ \\textcircled{2} $ Tenancy agreement") == "② Tenancy agreement"

    def test_a_table_cell_keeps_its_bold(self) -> None:
        (row,) = rows_of("<table><tr><td colspan=\"5\"><strong>A. Monitoring at home</strong>"
                         "</td></tr></table>")
        assert [(r.text, r.kind) for r in row.cells[0].runs] == [
            ("A. Monitoring at home", "strong")]


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

    def test_an_indented_line_continues_its_stack(self) -> None:
        # c0573's sub-items, which the parser cuts from their items.
        found = groups_of(regions(
            region(0, "text", (100, 100, 450, 125)), region(1, "text", (130, 130, 450, 155)),
            region(2, "text", (100, 160, 450, 185))), [])
        assert [[r.index for r in g] for g in found] == [[0, 1, 2]]

    def test_a_line_set_further_in_than_an_indent_does_not(self) -> None:
        found = groups_of(regions(region(0, "text", (100, 100, 450, 125)),
                                  region(1, "text", (200, 130, 450, 155))), [])
        assert len(found) == 2

    def test_an_indented_chip_in_a_row_of_chips_does_not_join(self) -> None:
        # c0257's `9 URGENT` beside `27 ROUTINE`, under the headline.
        found = groups_of(regions(
            region(0, "text", (40, 70, 700, 120)), region(1, "text", (40, 130, 800, 155)),
            region(2, "text", (65, 175, 180, 197)), region(3, "text", (220, 175, 360, 197))), [])
        assert sorted([r.index for r in g] for g in found) == [[0, 1], [2], [3]]

    def test_a_join_that_would_reach_over_the_next_column_is_refused(self) -> None:
        # c0402's table caption, wider than its column, under column 1.
        found = groups_of(regions(
            region(0, "text", (100, 100, 450, 125)), region(1, "text", (100, 130, 450, 155)),
            region(2, "text", (100, 160, 450, 185)), region(3, "text", (520, 100, 900, 180)),
            region(4, "text", (100, 190, 700, 215))), [])
        assert sorted([r.index for r in g] for g in found) == [[0, 1, 2], [3], [4]]

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


class TestMaths:
    """Spec 0024, group A: what the reader writes as LaTeX set as the page
    prints it; a `$` that opens no maths is printed."""

    def test_dollar_amounts_are_not_maths(self) -> None:
        assert plain("deemed income of $250 or $500 a month") == \
            "deemed income of $250 or $500 a month"
        assert plain("read $450, not $540.") == "read $450, not $540."
        assert plain("$0-15,000.35 $25,000-27,000.29") == "$0-15,000.35 $25,000-27,000.29"

    def test_a_variable_is_maths(self) -> None:
        assert plain("the index $F$ was") == "the index F was"

    def test_words_in_maths_keep_their_spaces(self) -> None:
        assert plain("$ \\mathbf{Star point chart : cycle racks} $") == \
            "Star point chart: cycle racks"
        assert plain("area is $ 54 \\mathrm{~m}^{2} $ , giving") == "area is 54 m², giving"
        assert plain("Output $I = 20\\text{ A}$") == "Output I = 20 A"

    def test_a_display_formula_is_set_as_printed(self) -> None:
        def formula_text(content: str) -> str:
            return "".join(run.text for run in runs_of(formula(content)))

        assert formula_text("$$\nB M I = \\text {w e i g h t} (\\mathrm {k g}) / \\text {h e i g h t} "
                       "^ {2} \\left(\\mathrm {m} ^ {2}\\right) = 9 2. 4 / 3. 1 7 = 2 9. 2 "
                       "\\mathrm {k g} / \\mathrm {m} ^ {2}\n$$") == \
            "BMI = weight (kg) / height² (m²) = 92.4 / 3.17 = 29.2 kg/m²"
        assert formula_text("$$\nC = (M + S) \\div N\n$$") == "C = (M + S) ÷ N"
        assert formula_text("$$\nn _ {1} \\sin \\theta_ {1} = n _ {2} \\sin \\theta_ {2}\n$$") == \
            "n₁ sin θ₁ = n₂ sin θ₂"
        assert formula_text("$$\n\\Delta h = \\alpha \\sqrt {F}\n$$") == "Δh = α √F"

    def test_a_maths_span_split_at_a_cell_edge_is_put_back(self) -> None:
        rows = rows_of("<table><tr><td>Lampe L<sub>1}$</td><td>$1,5</td></tr>"
                       "<tr><td>Lampe L_{2}$</td><td>$1,5</td></tr>"
                       "<tr><td>$0.00</td><td>$\\times$</td><td>$410.00</td></tr></table>")
        assert [[c.text for c in r.cells] for r in rows] == [
            ["Lampe L₁", "1,5", ""], ["Lampe L₂", "1,5", ""], ["$0.00", "×", "$410.00"]]

    def test_a_circled_letter(self) -> None:
        assert plain("$ \\textcircled{f} $") == "ⓕ"

    def test_an_underline_is_not_drawn(self) -> None:
        assert plain("Tags: <u>html</u>, <u>web</u>") == "Tags: html, web"

    def test_groups_nest_and_end_a_command(self) -> None:
        assert plain("on air $ \\mathrm{SpO_{2}} $ 90%") == "on air SpO₂ 90%"
        assert plain("82 $ \\mu\\mathrm{mol} $/L") == "82 µmol/L"

    def test_a_raised_run_joins_what_it_marks(self) -> None:
        assert plain("concern $^{1}$: recurring") == "concern¹: recurring"
        assert plain("ligação e controlo. $ ^{1} $") == "ligação e controlo.¹"
        assert plain("(monthly, before tax) $ ^{1} $") == "(monthly, before tax)¹"
        assert plain("encomenda n. $ ^{o} $ 2103-118") == "encomenda n.o 2103-118"

    def test_a_raised_run_opening_a_note_or_after_a_sign_stands_apart(self) -> None:
        assert plain("taken that month. $ ^{1} $ Provisional") == "taken that month. ¹ Provisional"
        assert plain("the original. $ ^{2} $Required") == "the original. ²Required"
        assert plain("600 € $ ^{\\mathrm{HT}} $") == "600 € HT"

    def test_an_unclosed_tag_keeps_its_words(self) -> None:
        rows = rows_of("<table><tr><td colspan=\"2\"><strong B. Clinic visits</strong></td></tr>"
                       "</table>")
        assert [(r.text, r.kind) for r in rows[0].cells[0].runs] == [("B. Clinic visits", "strong")]

    def test_spaces_in_a_group_are_real_only_between_words(self) -> None:
        assert plain("breathlessness; $ \\mathrm{S p O_{2}} $ 90%") == "breathlessness; SpO₂ 90%"
        assert plain("density 2,395 $ \\mathrm{kg / m^{3}} $ , within") == "density 2,395 kg/m³, within"
