"""Tests for everything downstream of the Engines.

The IR, the Probes and the renderer need no model, so they can be held to real
assertions before a single vision pass exists. Fixture 0001 is the vehicle: if
the back half is right, a correct extraction of example/invoice.png renders
correctly and reconciles arithmetically.
"""

from __future__ import annotations

import json

import pytest

from doc_to_html import probes
from doc_to_html.ir import (
    BBox,
    Caveat,
    CellState,
    Correction,
    Document,
    Kind,
    Reading,
    Row,
    RowRole,
    Zone,
    cell,
)
from doc_to_html.render import render
from doc_to_html.report import flagged
from doc_to_html.probes import parse_number

from .documents.invoice_0001 import build


@pytest.fixture
def invoice() -> Document:
    return build()


class TestNumberParsing:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("$300.00", "300.00"),
            ("Total: $385.00", "385.00"),
            ("1,234.56", "1234.56"),
            ("1.234,56", "1234.56"),
            ("1,50", "1.50"),
            ("1,234", "1234"),
            ("-42", "-42"),
            ("1 284", "1284"),
            ("", None),
            ("Website design", None),
        ],
    )
    def test_parses(self, text: str, expected: str | None) -> None:
        result = parse_number(text)
        assert (str(result) if result is not None else None) == expected


class TestProbes:
    def test_line_items_reconcile_with_the_total(self, invoice: Document) -> None:
        results = probes.run(invoice)
        sums = [r for r in results if r.kind == "column-sum"]
        assert sums, "the item table should attract a column-sum probe"
        assert all(r.ok for r in sums)
        assert any(r.computed == "385.00" for r in sums)

    def test_summary_row_is_excluded_from_the_sum(self, invoice: Document) -> None:
        """The regression Row Roles exist to prevent: 300+75+10+385 = 770."""
        results = probes.run(invoice)
        assert not any(r.computed == "770.00" for r in results)

    def test_a_misread_digit_is_caught(self, invoice: Document) -> None:
        zone = invoice.zones[-1]
        zone.rows[1].cells[1] = cell("$800.00")
        results = probes.run(invoice)
        assert any(not r.ok for r in results)
        assert probes.implicated_zones(results)

    def test_a_total_sums_only_the_rows_above_it(self, invoice: Document) -> None:
        """`receipt_0010` prints `Card` and `Change` after its subtotal.

        Summed with them the prices came to 55.55, which matches nothing, and
        the finding then named a column of quantities summed with the digits
        of the card and authorisation numbers."""
        invoice.zones = [Zone(kind=Kind.TABLE, complete=True, rows=[
            Row(role=RowRole.DATA, cells=[cell("1"), cell("Flat white"), cell("3.40")]),
            Row(role=RowRole.DATA, cells=[cell(""), cell("oat milk"), cell("0.40")]),
            Row(role=RowRole.DATA, cells=[cell("2"), cell("Cortado"), cell("6.20")]),
            Row(role=RowRole.SUMMARY, cells=[cell("Subtotal"), cell(""), cell("10.00")]),
            Row(role=RowRole.DATA, cells=[cell("Card ***4417"), cell(""), cell("10.00")]),
            Row(role=RowRole.DATA, cells=[cell("Change"), cell(""), cell("0.00")]),
            Row(role=RowRole.DATA, cells=[cell("Auth 084417"), cell(""), cell("")]),
        ])]

        sums = [r for r in probes.run(invoice) if r.kind == "column-sum"]

        assert sums and all(r.ok for r in sums)
        assert [r.computed for r in sums] == ["10.00"]

    def test_probe_findings_carry_locations_not_answers(self, invoice: Document) -> None:
        """docs/adr/0004 — a Probe may say where to look, never what to find."""
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        implicated = probes.implicated_zones(probes.run(invoice))
        assert implicated == {5}
        assert all(isinstance(index, int) for index in implicated)


class TestRender:
    def test_structure_survives(self, invoice: Document) -> None:
        html = render(invoice)
        assert "<thead>" in html and "<tbody>" in html and "<tfoot>" in html
        assert "Website design" in html
        assert "Total: $385.00" in html

    def test_bands_render_side_by_side(self, invoice: Document) -> None:
        html = render(invoice)
        assert html.count('class="band"') == 4

    def test_graphic_is_placeholdered_not_reconstructed(self, invoice: Document) -> None:
        html = render(invoice)
        assert 'class="omitted" data-kind="logo"' in html
        assert "<img" not in html

    def test_ir_is_embedded_and_parseable(self, invoice: Document) -> None:
        html = render(invoice)
        raw = html.split('id="doc-ir">')[1].split("</script>")[0]
        data = json.loads(raw.replace("<\\/", "</"))
        assert data["ir_version"] == 1
        assert len(data["zones"]) == 6

    def test_script_tags_in_content_cannot_break_the_page(self) -> None:
        document = build()
        document.zones[2].blocks[0].lines[0] = cell("</script><b>oops")
        html = render(document)
        assert html.count("</script>") == 1

    def test_partial_ir_renders_as_a_skeleton(self, invoice: Document) -> None:
        """Drafts render mid-Conversion, so nothing may assume completeness."""
        invoice.zones[-1].complete = False
        html = render(invoice)
        assert 'class="skeleton"' in html

    def test_disputed_cells_keep_the_rival_reading(self, invoice: Document) -> None:
        target = invoice.zones[-1].rows[1].cells[1]
        target.readings = [
            Reading(engine="tesseract", text="$300.00"),
            Reading(engine="qwen3-vl:4b", text="$800.00"),
        ]
        target.state = CellState.DISPUTED
        html = render(invoice)
        assert 'class="disputed"' in html
        assert 'data-alt="$800.00"' in html

    def test_a_disputed_cell_is_drawn_as_the_page_prints_it(self, invoice: Document) -> None:
        """No ground and no underline the page does not print — spec 0019,
        D2: on a dark ground the flag's tint made the line unreadable."""
        html = render(invoice)
        rule = next(line for line in html.splitlines() if line.startswith(".disputed"))
        assert "background" not in rule and "border" not in rule

    def test_unresolved_findings_are_surfaced_to_the_reader(self, invoice: Document) -> None:
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        invoice.probes = probes.run(invoice)
        html = flagged(invoice)
        assert "Unresolved" in html

    def test_and_in_the_report_not_on_the_page(self, invoice: Document) -> None:
        """Spec 0012, G1: a reader of the page took the card for the page's
        own. The IR keeps every finding; `report.html` shows them."""
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        invoice.probes = probes.run(invoice)
        invoice.caveats = [Caveat(zone_index=3, kind="prose", note="re-read")]
        page = render(invoice)
        assert "Unresolved" not in page and "Read with a caveat" not in page
        assert 'class="findings' not in page
        assert any(not p.ok for p in Document.from_json(invoice.to_json()).probes)

    def test_a_caveat_is_not_filed_as_unresolved(self, invoice: Document) -> None:
        """A Caveat says the Zone converted with a qualifier on how. Under an
        "Unresolved" heading it tells a reader the document failed while showing
        them a complete document — which is what run 46 looked like, with one
        re-read Zone, no Failures and every string on the page rendered."""
        invoice.caveats = [
            Caveat(zone_index=3, kind="prose",
                   note="classified pairs, re-read as prose")
        ]
        html = flagged(invoice)

        assert "Read with a caveat" in html
        assert "Unresolved" not in html

    def test_both_blocks_appear_when_both_apply(self, invoice: Document) -> None:
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        invoice.probes = probes.run(invoice)
        invoice.caveats = [Caveat(zone_index=3, kind="prose", note="re-read")]
        html = flagged(invoice)

        assert html.index("Unresolved") < html.index("Read with a caveat"), (
            "what is missing comes before what is merely qualified"
        )


def _table_of(invoice: Document, rows: list[tuple[RowRole, str]]) -> str:
    """One two-column table on the page, rendered, and nothing else."""
    invoice.zones = [Zone(kind=Kind.TABLE, complete=True, rows=[
        Row(role=role, cells=[cell(text), cell("")]) for role, text in rows
    ])]
    html = render(invoice)
    return html[html.index("<table>"):html.index("</table>")]


class TestHeaderRowPlacement:
    """A header row between data rows is a section heading, and stays put.

    `menu_0012` prints `From the grill`, `Main courses` and `Puddings` above
    their dishes; the model returned them as header rows 7, 12 and 19, in the
    right places, and gathering every header into one `<thead>` stacked all
    three above the first dish. A header with nothing after it is not a section
    heading: `sample_table_0003`'s only header came back as its last row, and
    `<thead>` is what puts it back on top.
    """

    def test_a_header_between_data_rows_stays_where_it_is(
            self, invoice: Document) -> None:
        table = _table_of(invoice, [
            (RowRole.DATA, "Potted brown shrimp"),
            (RowRole.HEADER, "From the grill"),
            (RowRole.DATA, "Rib of beef, for two"),
        ])

        assert "<thead" not in table
        assert (table.index("Potted brown shrimp")
                < table.index("<th>From the grill</th>")
                < table.index("Rib of beef, for two"))
        assert table.count("<tbody>") == 1

    def test_a_header_with_nothing_after_it_goes_on_top(
            self, invoice: Document) -> None:
        table = _table_of(invoice, [
            (RowRole.DATA, "United States"),
            (RowRole.DATA, "China"),
            (RowRole.HEADER, "Country"),
        ])

        assert table.index("<thead><tr><th>Country</th>") < table.index(
            "United States")

    def test_a_leading_header_goes_on_top_beside_a_section_heading(
            self, invoice: Document) -> None:
        table = _table_of(invoice, [
            (RowRole.HEADER, "Dish"),
            (RowRole.DATA, "Potted brown shrimp"),
            (RowRole.HEADER, "From the grill"),
            (RowRole.DATA, "Rib of beef, for two"),
        ])

        assert table.index("<thead><tr><th>Dish</th>") < table.index(
            "Potted brown shrimp") < table.index("<th>From the grill</th>")
        assert table.count("<thead") == 1

    def test_once_the_table_opens_with_a_header_a_last_one_stays_last(
            self, invoice: Document) -> None:
        """`receipt_0010`, read whole in Q5: it opens with its order lines and
        closes with a farewell the model also calls a header. Lifting that to
        the top put `THANK YOU` above the order."""
        table = _table_of(invoice, [
            (RowRole.HEADER, "Till 02 Op. NADIA"),
            (RowRole.DATA, "Flat white"),
            (RowRole.HEADER, "AID A0000000031010"),
            (RowRole.DATA, "Auth 084417"),
            (RowRole.HEADER, "THANK YOU — PLEASE CALL AGAIN"),
        ])

        assert table.count("<thead") == 1
        assert "THANK YOU" not in table[:table.index("</thead>")]
        assert (table.index("Flat white") < table.index("AID A0000000031010")
                < table.index("Auth 084417") < table.index("THANK YOU"))


class TestSummaryRowPlacement:
    """Summaries go to the foot only when nothing follows them."""

    def test_closing_summaries_go_to_the_foot(self, invoice: Document) -> None:
        table = _table_of(invoice, [
            (RowRole.DATA, "Website design"),
            (RowRole.SUMMARY, "Total"),
        ])

        assert "<tfoot><tr><td>Total</td>" in table

    def test_a_summary_with_rows_after_it_stays_where_it_is(
            self, invoice: Document) -> None:
        """`receipt_0010` prints its payment lines after its total. At the
        foot, the total was drawn below `Change`."""
        table = _table_of(invoice, [
            (RowRole.DATA, "Elderflower press"),
            (RowRole.SUMMARY, "Subtotal"),
            (RowRole.SUMMARY, "TOTAL"),
            (RowRole.DATA, "Card ****4417"),
            (RowRole.DATA, "Change"),
        ])

        assert "<tfoot" not in table
        assert (table.index("Elderflower press") < table.index("Subtotal")
                < table.index("TOTAL") < table.index("Card ****4417")
                < table.index("Change"))


class TestCorrections:
    def test_a_correction_wins_and_the_reading_survives(self, invoice: Document) -> None:
        box = invoice.zones[-1].rows[1].cells[1].bbox
        assert box is not None
        invoice.corrections.append(
            Correction(bbox=box, text="$310.00", replaced="$300.00")
        )
        html = render(invoice)
        assert "$310.00" in html
        assert 'title="read as: $300.00"' in html

    def test_anchoring_survives_a_shifted_layout(self, invoice: Document) -> None:
        """The point of geometric anchoring: prompts change, pixels do not."""
        box = invoice.zones[-1].rows[1].cells[1].bbox
        assert box is not None
        invoice.corrections.append(Correction(bbox=box, text="$310.00"))

        nudged = BBox(box.left + 0.004, box.top + 0.002,
                      box.right + 0.004, box.bottom + 0.002)
        assert invoice.correction_for(nudged) is not None

    def test_an_unrelated_cell_does_not_pick_up_the_correction(
        self, invoice: Document
    ) -> None:
        box = invoice.zones[-1].rows[1].cells[1].bbox
        assert box is not None
        invoice.corrections.append(Correction(bbox=box, text="$310.00"))

        elsewhere = BBox(0.10, 0.30, 0.20, 0.32)
        assert invoice.correction_for(elsewhere) is None


class TestIRRoundTrip:
    def test_json_round_trip_preserves_the_document(self, invoice: Document) -> None:
        restored = Document.from_json(invoice.to_json())
        assert restored.to_json() == invoice.to_json()
        assert len(restored.zones) == len(invoice.zones)
        assert restored.zones[5].rows[4].role == invoice.zones[5].rows[4].role


class TestTheStatementsArithmeticReachesThePage:
    """Spec 0010, step B2. The floor's `statement_0006` was read at reduced
    resolution, and two of its amounts are wrong: Cordell Energy's balance
    1,144.30 read 1,141.30, and Wexford Insurance's 216.08 read 210.08."""

    @staticmethod
    def floor(name: str, frozen: str = "s3-result") -> Document:
        import re
        from pathlib import Path
        html = (Path(__file__).resolve().parent / "frozen" / frozen
                / "documents" / f"{name}.html").read_text(encoding="utf-8")
        found = re.search(r'id="doc-ir">(.*?)</script>', html, re.S)
        assert found
        return Document.from_json(found.group(1).replace("<\\/", "</"))

    def test_the_running_balance_names_both_rows(self) -> None:
        failed = [r for r in probes.run(self.floor("statement_0006"))
                  if r.kind == "running-balance" and not r.ok]
        assert len(failed) == 1
        assert failed[0].detail is not None
        assert "the balance of Cordell Energy" in failed[0].detail
        assert "(1,141.30)" in failed[0].detail
        assert "Wexford Insurance" in failed[0].detail
        assert "Hale" not in failed[0].detail

    def test_the_paid_out_column_is_reported_six_short(self) -> None:
        near = [r for r in probes.run(self.floor("statement_0006"))
                if r.kind == "column-sum" and not r.ok]
        assert [(r.computed, r.stated) for r in near] == [("5766.36", "5772.36")]

    def test_no_other_document_on_the_floor_fails_a_probe(self) -> None:
        from doc_to_html.corpus import NEW, SWEEP
        # The six added 2026-10-13 are first held in `s7-result/`. None
        # prints a sum, a balance or a line total to check: pricing's
        # "£144 per user" is twelve months of £12 in a sentence, not a
        # table. Spec 0012 step 0.
        for name in SWEEP:
            if name == "statement_0006":
                continue
            floor = self.floor(name, "s7-result" if name in NEW else "s3-result")
            assert all(r.ok for r in probes.run(floor)), name
