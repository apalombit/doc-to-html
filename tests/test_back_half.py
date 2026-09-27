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

    def test_unresolved_findings_are_surfaced_to_the_reader(self, invoice: Document) -> None:
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        invoice.probes = probes.run(invoice)
        html = render(invoice)
        assert "Unresolved" in html

    def test_a_caveat_is_not_filed_as_unresolved(self, invoice: Document) -> None:
        """A Caveat says the Zone converted with a qualifier on how. Under an
        "Unresolved" heading it tells a reader the document failed while showing
        them a complete document — which is what run 46 looked like, with one
        re-read Zone, no Failures and every string on the page rendered."""
        invoice.caveats = [
            Caveat(zone_index=3, kind="prose",
                   note="classified pairs, re-read as prose")
        ]
        html = render(invoice)

        assert "Read with a caveat" in html
        assert "Unresolved" not in html

    def test_both_blocks_appear_when_both_apply(self, invoice: Document) -> None:
        invoice.zones[-1].rows[1].cells[1] = cell("$800.00")
        invoice.probes = probes.run(invoice)
        invoice.caveats = [Caveat(zone_index=3, kind="prose", note="re-read")]
        html = render(invoice)

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
