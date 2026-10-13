"""Tables stop being skeletons.

Two documents, and between them the whole of what a table can be: one whose
totals row sits inside it, and one with fifteen rows and nothing to reconcile.
This is also where Probes run against extracted data for the first time, and
where the failure contract is exercised on a document that partly worked.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from doc_to_html.engines.ollama import TABLE_PROMPT, OllamaEngine, with_grid
from doc_to_html.ir import BBox, Document, Kind, Row, RowRole, Source, Zone, cell
from doc_to_html.preprocess import (
    MIN_BAND,
    TableGrid,
    caption_band,
    content_ink,
    ink_bands,
    rectify,
    table_grid,
    zone_pixels,
)
from doc_to_html.render import render
from doc_to_html.report import flagged
from doc_to_html.wire import (
    MappingError,
    TableResponse,
    contents_into,
    retrimmed,
    table_repairs,
)

from .documents import SAMPLE_DOCUMENTS
from .replay import (
    break_zone,
    Call,
    ReplayTransport,
    convert_recording,
    recorded_for,
    text,
)

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"
STATISTICS = REPO / "example" / "sample-table.png"


def convert_with(image: Path, replies: list[object]) -> tuple[Document, ReplayTransport]:
    return convert_recording(image, replies)  # type: ignore[arg-type]


def engine_with(*replies: str) -> tuple[OllamaEngine, ReplayTransport]:
    transport = ReplayTransport([text(reply) for reply in replies])
    return OllamaEngine(model="test-model", transport=transport), transport


def table_calls(transport: ReplayTransport) -> list[Call]:
    """The calls that asked for rows, in order."""
    return [call for call in transport.calls if "role" in str(call.schema)
            and "rows" in str(call.schema)]


@pytest.fixture
def invoice() -> tuple[Document, ReplayTransport]:
    return convert_with(INVOICE, recorded_for("invoice_0001"))


@pytest.fixture
def statistics() -> tuple[Document, ReplayTransport]:
    return convert_with(STATISTICS, recorded_for("sample_table_0003"))


class TestARealTable:
    def test_rows_arrive_in_order_with_their_roles(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        document, _ = invoice
        items = document.zones[5]
        assert items.complete
        assert [row.role for row in items.rows] == [
            RowRole.HEADER, RowRole.DATA, RowRole.DATA, RowRole.DATA, RowRole.SUMMARY
        ]
        assert [c.text for c in items.rows[1].cells] == ["Website design", "$300.00"]

    def test_a_totals_row_sits_inside_the_table(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Where a reader expects to find it. A total lifted out into its own
        block would read as a different document."""
        html = render(invoice[0])
        assert "<tfoot>" in html
        assert "Total: $385.00</td>" in html
        assert html.index("<tbody>") < html.index("<tfoot>")

    def test_the_header_row_is_marked_as_one(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Both heading rows are `#eee` in `invoice.html`, so each `thead`
        carries that fill — see `TestAHeaderRowsFillArrivesThroughAConversion`."""
        html = render(invoice[0])
        head = re.escape('<thead style="--shade:rgb(238,238,238)">')
        # A row carries its own line and ground once read — spec 0011, 4c —
        # and its cells the page's gap between rows, 4e.
        cell = r'( style="[^"]*")?'
        assert re.search(rf"{head}<tr[^>]*><th{cell}>Payment Method</th>", html)
        assert re.search(rf'{head}<tr[^>]*><th{cell}>Item</th><th class="num"{cell}>'
                         r"Price</th></tr></thead>", html)

    def test_fifteen_rows_survive(
        self, statistics: tuple[Document, ReplayTransport]
    ) -> None:
        table = statistics[0].zones[1]
        assert len([r for r in table.rows if r.role is RowRole.DATA]) == 15
        assert table.title == "Population and GDP (millions of USD)"

    def test_numeric_columns_are_found_by_content_not_position(
        self, statistics: tuple[Document, ReplayTransport]
    ) -> None:
        """ISO codes and currency names sit to the right of the first column and
        must not be right-aligned for it."""
        html = render(statistics[0])
        cell = r'( style="[^"]*")?'  # the page's gap between rows, spec 0011, 4e
        assert re.search(rf"<td{cell}>USA</td>", html)
        assert re.search(rf'<td class="num"{cell}>331,900,000</td>', html)
        assert re.search(rf"<td{cell}>USD</td>", html)


class TestASparseNumericColumnIsStillNumeric:
    """An empty cell used to vote against its column being numbers.

    `statement_0006`'s "Paid out" holds five amounts in forty rows, so it
    scored 5/40 against a 0.6 threshold and stayed left-aligned beside two
    dense money columns that did not. Counted over the cells that hold
    something it is 5 of 5. See `render._numeric_columns`.
    """

    def a_table(self, column: list[str]) -> Zone:
        return Zone(
            kind=Kind.TABLE,
            rows=[Row(role=RowRole.DATA, cells=[cell("Paid"), cell(value)])
                  for value in column],
        )

    def test_a_sparse_money_column_is_right_aligned(self) -> None:
        from doc_to_html.render import _numeric_columns

        sparse = self.a_table(["", "", "1,180.00", "", "", "", "94.20", ""])

        assert _numeric_columns(sparse) == {1}

    def test_and_it_reaches_the_rendered_cells(self) -> None:
        from doc_to_html.render import _table

        html = _table(self.a_table(["", "3,470.00", "", "1,940.00"]), Document(
            source=Source(path="x.png", sha256="0" * 64, width=9, height=9)))

        assert '<td class="num"></td>' in html
        assert '<td class="num">3,470.00</td>' in html

    def test_a_column_of_words_is_still_not_numeric(self) -> None:
        """The blanks are skipped; the test on what is left is unchanged."""
        from doc_to_html.render import _numeric_columns

        words = self.a_table(["", "Opening balance", "", "Cordell Energy"])

        assert _numeric_columns(words) == set()

    def test_one_value_among_blanks_does_not_decide_a_column(self) -> None:
        """`cv_0013`'s education table: `2015` above three empty cells. One
        cell is a quarter of that column, not a reading of it."""
        from doc_to_html.render import _numeric_columns

        thin = self.a_table(["2015", "", "", ""])

        assert _numeric_columns(thin) == set()

    def test_but_a_single_row_table_still_decides(self) -> None:
        """`invoice_0001`'s payment table has one data row, so its one cell is
        the whole column and nothing was skipped to reach it."""
        from doc_to_html.render import _numeric_columns

        assert _numeric_columns(self.a_table(["1000"])) == {1}

    def test_a_column_that_is_entirely_empty_is_not_numeric(self) -> None:
        """Skipping every cell must leave no vote at all, not a vacuous pass.

        `statement_0006`'s seventh column is empty in all forty data rows, and
        `0 / 0` is the shape that raises or right-aligns nothing depending on
        which way the division falls.
        """
        from doc_to_html.render import _numeric_columns

        assert _numeric_columns(self.a_table(["", "", ""])) == set()


class TestExtractionReadsTheRightPixels:
    def test_a_table_is_read_from_a_crop_and_not_from_the_page(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Each Zone is cropped from the full-resolution rectified image, so a
        table is read at the glyph size it was printed at and not at whatever
        a whole page shrinks to.
        """
        from doc_to_html.preprocess import PAD_X, PAD_Y

        document, transport = invoice
        crop = Image.open(io.BytesIO(table_calls(transport)[1].images[0]))

        # Derived from the box the Conversion actually cropped on, and the pads,
        # rather than written down: a literal here goes stale the moment either
        # pad is retuned, and a stale literal in this assertion reads as a broken
        # crop. The *typed* fixture box will not do — `DTH_SNAP_ZONES` ships on,
        # so the box the Extractor sees has been moved onto its own ink first.
        box = document.zones[5].bbox
        assert box is not None
        wide = min(1.0, box.right + PAD_X) - max(0.0, box.left - PAD_X)
        tall = min(1.0, box.bottom + PAD_Y) - max(0.0, box.top - PAD_Y)

        # A fraction of the page at its own 862 x 563, not of a shrunk copy.
        assert crop.width == pytest.approx(wide * 862, abs=4)
        assert crop.height == pytest.approx(tall * 563, abs=4)

    def test_each_table_gets_its_own_crop(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        crops = [Image.open(io.BytesIO(c.images[0])).size
                 for c in table_calls(invoice[1])]
        assert len(crops) == 2 and crops[0] != crops[1]


class TestProbesRunAgainstExtractedData:
    def test_the_line_items_reconcile_with_the_stated_total(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        document, _ = invoice
        sums = [p for p in document.probes if p.kind == "column-sum"]
        assert [p.ok for p in sums] == [True]
        assert sums[0].stated == "385.00"
        assert sums[0].computed == "385.00"

    def test_a_table_with_nothing_to_reconcile_attracts_no_probe(
        self, statistics: tuple[Document, ReplayTransport]
    ) -> None:
        """No summary row means no column-sum, not a failing column-sum. And two
        numeric columns give the row-product Probe no triple to infer, so
        inventing a relationship would be a false finding on correct data."""
        assert statistics[0].probes == []

    def test_a_passing_probe_produces_no_findings_in_the_render(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        assert "did not reconcile" not in render(invoice[0])


class TestAHeaderRowsFillArrivesThroughAConversion:
    def test_both_invoice_headers_carry_the_sources_grey(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """End to end, because a header row exists only once `_extract` has
        run, and chrome used to be measured before it. `Zone.title_fill`
        shipped, passed offline and never fired for a phase for exactly that
        reason — its stage ran before the pass that sets a Title.

        `invoice.html` fills both heading rows `#eee`."""
        document, _ = invoice

        tables = [z for z in document.zones if z.kind is Kind.TABLE]
        assert [z.header_fill for z in tables] == [(238, 238, 238)] * 2
        assert all(z.header_fill is None
                   for z in document.zones if z.kind is not Kind.TABLE)
        assert render(document).count(
            '<thead style="--shade:rgb(238,238,238)">') == 2


class TestAReceiptThroughAConversion:
    """Spec 0007's queue, Q5: row order and the column sum, where a Conversion
    applies them.

    `receipt_0010`'s own picture, at the box the production layout front draws
    for its table, with the caption, Kind and table answers scripted as the
    model gave them in sweep `Q5-10-reshot-sweep` — the floor's own reading,
    closing on two lines it calls headers.
    """

    ROWS = [
        ("header", ["Till 02 Op. NADIA", "", "29/08/2026"]),
        ("header", ["Order 00418", "", "13:47"]),
        ("data", ["1", "Flat white", "3.40"]),
        ("data", ["", "oat milk", "0.40"]),
        ("data", ["2", "Cortado", "6.20"]),
        ("data", ["1", "Toast, sourdough", "3.10"]),
        ("data", ["", "extra butter", "0.30"]),
        ("data", ["1", "Bacon roll", "5.75"]),
        ("data", ["3", "Shortbread", "4.50"]),
        ("data", ["1", "Elderflower press", "2.80"]),
        ("summary", ["Subtotal", "", "26.45"]),
        ("summary", ["Service 10%", "", "2.65"]),
        ("summary", ["VAT @ 20%", "", "4.85"]),
        ("summary", ["TOTAL", "", "29.10"]),
        ("data", ["Card ***4417", "", "29.10"]),
        ("data", ["Change", "", "0.00"]),
        ("header", ["AID A000000031010", "", ""]),
        ("header", ["Auth 084417", "", "CONTACTLESS"]),
    ]

    def test_the_rows_keep_their_printed_order_and_the_total_reconciles(
            self) -> None:
        from doc_to_html.corpus import SOURCES

        replies = {
            "caption": [text(json.dumps(
                {"first_line": "Till 02 Op. NADIA", "line_is": "caption"}))],
            "classify": [text(json.dumps({"kind": "table", "graphic": ""}))],
            "table": [text(json.dumps({"rows": [
                {"role": role, "cells": cells} for role, cells in self.ROWS]}))],
        }
        zone = Zone(kind=Kind.PROSE, band=0, column=0,
                    bbox=BBox(0.0537, 0.1447, 0.9463, 0.735))
        document, _ = convert_recording(
            REPO / SOURCES["receipt_0010"].png, replies, layout=[zone])

        html = render(document)
        table = html[html.index("<table"):html.index("</table>")]
        printed = ["Till 02 Op. NADIA", "Flat white", "Elderflower press",
                   "Subtotal", "TOTAL", "Card ***4417", "Change",
                   "AID A000000031010", "Auth 084417"]
        assert [table.index(t) for t in printed] == sorted(
            table.index(t) for t in printed)
        assert "<tfoot" not in table

        sums = [p for p in document.probes if p.kind == "column-sum"]
        assert [(p.ok, p.computed) for p in sums] == [(True, "26.45")]


class TestProbesNeverHandOverTheAnswerKey:
    def test_no_expected_value_reaches_a_prompt(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """A failed Probe cannot say which number is wrong, so telling a model
        what would make the arithmetic work makes it bend whichever number it
        can — after which every check passes and the signal is gone. ADR 0004."""
        _, transport = invoice
        for call in transport.calls:
            assert "385" not in call.prompt
        assert any("do not" in call.prompt.lower() for call in table_calls(transport))


class TestTheFailureContractOnAPartlyWorkingDocument:
    def broken_at(self, zone_index: int, payload: str) -> Document:
        replies = break_zone(recorded_for("invoice_0001"), "invoice_0001",
                             zone_index, payload)
        return convert_with(INVOICE, replies)[0]  # type: ignore[arg-type]

    def test_a_clean_run_reports_nothing(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        document, _ = invoice
        assert all(zone.complete for zone in document.zones)
        assert document.failures == []

    def test_zones_that_failed_do_not_cost_the_ones_that_worked(self) -> None:
        """Throwing away two correct tables because a Pairs Zone came back
        unreadable would destroy exactly the evidence the run exists to
        produce."""
        document = self.broken_at(1, '{"pairs": []}')
        assert [z.complete for z in document.zones] == [
            True, False, True, True, True, True
        ]
        assert [f.zone_index for f in document.failures] == [1]
        assert all(f.reason for f in document.failures)

    def test_a_broken_response_leaves_a_skeleton_beside_real_content(self) -> None:
        """Only rectification failing outright, or a layout pass returning no
        Zones, aborts a Conversion. Everything else is reported and the rest of
        the document still renders."""
        document = self.broken_at(5, '{"rows": []}')

        assert document.zones[4].complete
        assert not document.zones[5].complete
        assert [f.zone_index for f in document.failures] == [5]
        assert "no rows" in document.failures[-1].reason

        html = render(document)
        assert 'class="skeleton"' in html
        assert "<table" in html
        assert "could not be read" in flagged(document)


def table_zone(payload: str) -> Zone:
    """Map a raw table payload straight onto a Zone, with no model in the way.

    Returns the Zone rather than a Document: the callers below read `.rows`, and
    a helper that claimed to return a Document made every one of them carry a
    `# type: ignore` for a field the real type has.
    """
    from doc_to_html.ir import Reading

    zone = Zone(kind=Kind.TABLE)
    contents_into(zone, payload, read=lambda t: Reading(engine="test", text=t))
    return zone


class TestMappingATableResponse:
    def test_an_empty_result_is_a_failure_not_an_empty_table(self) -> None:
        """A schema cannot say that a region a model was pointed at has rows in
        it. An empty table rendered as a table looks like a document that had
        one."""
        with pytest.raises(MappingError, match="no rows"):
            table_zone('{"rows": []}')

    def test_a_row_wider_than_the_header_is_kept_whole_and_flagged(self) -> None:
        """It used to raise, and raising cost `statement_0006` 36 read rows.

        Spec 0007 Phase A-1. Dropping the surplus cell would be the one repair
        available here that loses content, so every cell is kept and the row is
        named by `table_repairs` instead.
        """
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["1", "2", "3"]}]}'
        )
        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["a", "b"], ["1", "2"], ["1", "2", "3"],
        ]
        assert any("row 2" in note and "3 cells" in note
                   for note in table_repairs(zone))

    def test_a_summary_row_may_be_narrower_because_totals_rows_merge_cells(
        self,
    ) -> None:
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "data", "cells": ["Design", "300.00"]},'
            ' {"role": "summary", "cells": ["Total: 300.00"]}]}'
        )
        assert [len(r.cells) for r in zone.rows] == [2, 2, 1]

    def test_a_table_with_no_header_row_is_allowed(self) -> None:
        """Plenty of tables have none. There is then nothing to check widths
        against, which is a smaller problem than rejecting the table."""
        zone = table_zone('{"rows": [{"role": "data", "cells": ["a", "b"]}]}')
        assert len(zone.rows) == 1


class TestARowWithNoCellsAtAll:
    """A row saying nothing is dropped, and takes nothing with it.

    The width check exists because a row with the *wrong* number of cells hides a
    dropped or invented one, and every value after it lands in the wrong column.
    A row with none has no value to misplace, so it is the one case where
    removing it is safe — and it is the case that cost a document.

    Measured: runs 39 and 45 both converted `invoice_0001` on ink-snapped
    geometry and both returned the whole line-item table plus one empty row after
    `Website design`. The width check rejected it, `rows_from_table` raised, and
    nine correctly read strings, the table and the column-sum Probe were lost to
    an empty skeleton.
    """

    MEASURED = (
        '{"rows": [{"role": "header", "cells": ["Item", ""]},'
        ' {"role": "header", "cells": ["", "Price"]},'
        ' {"role": "data", "cells": ["Website design", "$300.00"]},'
        ' {"role": "data", "cells": []},'
        ' {"role": "data", "cells": ["Hosting (3 months)", "$75.00"]},'
        ' {"role": "data", "cells": ["Domain name (1 year)", "$10.00"]},'
        ' {"role": "summary", "cells": ["", "Total: $385.00"]}]}'
    )
    """Run 45's answer for Zone 5, byte for byte apart from whitespace."""

    def test_the_run_that_lost_the_invoice_table_now_keeps_every_row(self) -> None:
        zone = table_zone(self.MEASURED)

        assert [r.role for r in zone.rows] == [
            RowRole.HEADER, RowRole.DATA, RowRole.DATA, RowRole.DATA,
            RowRole.SUMMARY,
        ]

    def test_no_string_is_lost_or_moved_between_columns(self) -> None:
        zone = table_zone(self.MEASURED)

        assert [[c.readings[0].text for c in r.cells] for r in zone.rows] == [
            ["Item", "Price"],
            ["Website design", "$300.00"],
            ["Hosting (3 months)", "$75.00"],
            ["Domain name (1 year)", "$10.00"],
            ["", "Total: $385.00"],
        ]

    def test_a_row_short_of_the_header_is_padded_and_declared(self) -> None:
        """The dangerous case, and it is now kept rather than thrown away.

        One cell out of two could belong to either column, and that is still
        true — what changed in spec 0007 Phase A-1 is the price of saying so.
        Rejecting the row rejected the Zone, and on `statement_0006` that meant
        discarding 36 transaction rows the model had read correctly to protest
        about one. So the row is padded at the end, the pad carries **no
        Reading** — which is what distinguishes it from a cell read as empty —
        and `table_repairs` says the row is suspect and by how much.
        """
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["1"]}]}'
        )
        assert [len(r.cells) for r in zone.rows] == [2, 2]
        assert [c.text for c in zone.rows[1].cells] == ["1", ""]
        assert zone.rows[1].cells[1].readings == [], "a pad is not a reading"
        assert any("row 1" in note and "short" in note
                   for note in table_repairs(zone))

    def test_a_response_that_is_nothing_but_empty_rows_is_still_a_failure(
        self,
    ) -> None:
        """Dropping them all leaves no table, which is the empty answer the
        layout pass already contradicted — not a table with zero rows."""
        with pytest.raises(MappingError, match="empty rows"):
            table_zone(
                '{"rows": [{"role": "data", "cells": []},'
                ' {"role": "data", "cells": []}]}'
            )

    def test_a_row_of_empty_strings_is_a_row_saying_nothing(self) -> None:
        """The condition was on cell **count** and had to be on cell **content**.

        `if row.cells` is truthy for `['', '', '', '']`: five cells that say
        nothing passed the net that exists to drop them, passed the width check
        on their width, and rendered as a blank line inside the table.
        `report_0011`'s berth table carried one. Spec 0007 Phase A0.
        """
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Berth", "Movements"]},'
            ' {"role": "data", "cells": ["Aggregates", "412"]},'
            ' {"role": "data", "cells": ["", ""]},'
            ' {"role": "data", "cells": ["Timber", "228"]}]}'
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["Berth", "Movements"], ["Aggregates", "412"], ["Timber", "228"],
        ]

    def test_whitespace_is_not_content_either(self) -> None:
        """Or the same row comes back whenever the model pads with a space."""
        zone = table_zone(
            '{"rows": [{"role": "data", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": [" ", "  "]}]}'
        )

        assert len(zone.rows) == 1

    def test_a_row_with_one_value_and_one_blank_is_still_kept(self) -> None:
        """The net stays narrow. A row with *some* content is ambiguous, not
        empty, and dropping it would lose a value the page prints."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["", "1"]}]}'
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["a", "b"], ["", "1"],
        ]

    def test_the_net_still_catches_the_row_that_cost_the_invoice_table(
        self,
    ) -> None:
        """Widening the test must not narrow what it already caught."""
        zone = table_zone(self.MEASURED)

        assert len(zone.rows) == 5


class TestOneRepairIsReportedOnce:
    """Rows repaired the same way are one finding, not one finding per row.

    Measured on `tests/frozen/a3-result/`, 2026-09-26: `statement_0006`'s
    transactions header came back as its six printed headings plus one empty
    cell, so each of its 41 six-cell rows was one short of seven and padded.
    That is one fact about the table, and it was printed as 41 near-identical
    lines at the top of the page — the panel ran longer than the table's first
    screen. No other document of the fifteen has a repair at all.
    """

    STATEMENT_SHAPE = (
        '{"rows": [{"role": "header", "cells": ["Date", "Type", "Paid", ""]},'
        + ",".join(
            f' {{"role": "data", "cells": ["0{day} Aug", "DD", "1.00"]}}'
            for day in range(1, 6)
        )
        + ', {"role": "summary", "cells": ["Totals", "5.00"]}]}'
    )

    def test_rows_short_by_the_same_amount_are_one_note(self) -> None:
        zone = table_zone(self.STATEMENT_SHAPE)

        assert table_repairs(zone) == [
            "rows 1–5 (5 rows) each came back 1 cell(s) short of the header's "
            "4 and were padded rather than discarded — the values they do have "
            "may sit in the wrong columns"
        ]

    def test_a_single_repaired_row_is_reported_exactly_as_before(self) -> None:
        """The wording a one-row repair already had is kept word for word."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["1"]}]}'
        )

        assert table_repairs(zone) == [
            "row 1 came back 1 cell(s) short of the header's 2 and was padded "
            "rather than discarded — the values it does have may sit in the "
            "wrong columns"
        ]

    def test_different_repairs_stay_separate_and_rows_are_named_as_runs(
        self,
    ) -> None:
        """Grouped by what was done, so no note claims a shortfall a row did
        not have; ordered by the first row each names."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b", "c"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["1"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["1", "2", "3", "4"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["1", "2", "3", "4"]}]}'
        )

        notes = table_repairs(zone)

        assert len(notes) == 3
        assert notes[0].startswith("rows 1, 3, 5–6 (4 rows) each came back 1 ")
        assert notes[1].startswith("row 2 came back 2 cell(s) short")
        assert notes[2].startswith("rows 4, 7 (2 rows) each came back with 4 "
                                   "cells against the header's 3 and were kept "
                                   "whole")

    def test_a_conversion_reports_the_repair_once(self) -> None:
        """Through a Conversion, because a note written by `wire.py` reaches
        the report only if the Orchestrator collects it. `invoice_0001`'s line
        items, answered in `statement_0006`'s shape: a header one empty cell
        wider than every row under it."""
        replies = break_zone(
            recorded_for("invoice_0001"), "invoice_0001", 5,
            '{"rows": [{"role": "header", "cells": ["Item", "Price", ""]},'
            ' {"role": "data", "cells": ["Website design", "$300.00"]},'
            ' {"role": "data", "cells": ["Hosting (3 months)", "$75.00"]},'
            ' {"role": "data", "cells": ["Domain name (1 year)", "$10.00"]},'
            ' {"role": "summary", "cells": ["", "Total: $385.00"]}]}',
        )
        document, _ = convert_with(INVOICE, replies)  # type: ignore[arg-type]

        repairs = [c.note for c in document.caveats
                   if c.zone_index == 5 and "padded" in c.note]
        assert repairs == [
            "rows 1–3 (3 rows) each came back 1 cell(s) short of the header's "
            "3 and were padded rather than discarded — the values they do have "
            "may sit in the wrong columns"
        ]
        assert flagged(document).count("padded rather than discarded") == 1


class TestAHeaderRepeatedToPadTheRowCount:
    """The model complies with *how many* and fills the surplus by repeating.

    `table_grid` counts bands of ink and cannot tell a caption from a heading
    row, so a crop whose first line is a caption measures one row more than the
    table has — and `with_grid` states that number. Measured over the corpus,
    exactly two tables padded, and both repeated the header verbatim:
    `darkdeck_0009`'s Service level table and `report_0011`'s berth table.
    """

    MEASURED = (
        '{"rows": [{"role": "header", "cells": ["Berth", "Movements", "Change"]},'
        ' {"role": "data", "cells": ["Aggregates", "412", "+57%"]},'
        ' {"role": "data", "cells": ["Fishing", "1,946", "+1%"]},'
        ' {"role": "header", "cells": ["Berth", "Movements", "Change"]}]}'
    )
    """`report_0011`'s berth table, in the shape run 99 returned it."""

    def test_the_repeat_is_dropped_and_the_first_header_kept(self) -> None:
        zone = table_zone(self.MEASURED)

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["Berth", "Movements", "Change"],
            ["Aggregates", "412", "+57%"],
            ["Fishing", "1,946", "+1%"],
        ]
        assert [r.role for r in zone.rows] == [
            RowRole.HEADER, RowRole.DATA, RowRole.DATA,
        ]

    def test_a_data_row_repeating_another_is_a_real_shape_and_is_kept(
        self,
    ) -> None:
        """Two months with identical figures are two rows, not a pad."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Month", "Total"]},'
            ' {"role": "data", "cells": ["May", "0.00"]},'
            ' {"role": "data", "cells": ["May", "0.00"]}]}'
        )

        assert len(zone.rows) == 3

    def test_a_second_heading_tier_is_not_a_repeat(self) -> None:
        """A header differing by one cell is a different row and stays."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Berth", "Movements"]},'
            ' {"role": "data", "cells": ["Aggregates", "412"]},'
            ' {"role": "header", "cells": ["Berth", "Revenue"]}]}'
        )

        assert len(zone.rows) == 3

    def test_spelling_is_case_and_whitespace_only(self) -> None:
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Berth", "Movements"]},'
            ' {"role": "data", "cells": ["Aggregates", "412"]},'
            ' {"role": "header", "cells": ["  BERTH ", "movements"]}]}'
        )

        assert len(zone.rows) == 2

    def test_a_split_header_is_rejoined_before_it_is_compared(self) -> None:
        """Order matters: `_join_split_header_row` runs first, so a header that
        arrived one cell per row is one row by the time this sees it and cannot
        be mistaken for a repeat of itself."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", ""]},'
            ' {"role": "header", "cells": ["", "Price"]},'
            ' {"role": "data", "cells": ["Website design", "$300.00"]}]}'
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["Item", "Price"], ["Website design", "$300.00"],
        ]

    def test_a_table_with_no_header_at_all_is_untouched(self) -> None:
        zone = table_zone(
            '{"rows": [{"role": "data", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["a", "b"]}]}'
        )

        assert len(zone.rows) == 2


class TestATotalsRowPaddedOnTheLeft:
    """`nonlatin_0014`'s totals came back a cell too wide, and the last twice.

    Spec 0009 step A. The header and every data row are four cells; the third
    summary row arrived as five, its label one column right of `ΦΠΑ 24%`'s,
    and a fourth summary row said only `12.437,82` again, which the page
    prints once (`example/nonlatin.html`). `tests/frozen/s3-result/`'s answer,
    call 20, in the shape it came back.
    """

    MEASURED = (
        '{"rows": [{"role": "header", "cells": '
        '["Περιγραφή", "Ώρες", "Τιμή/ώρα", "Καθαρή αξία"]},'
        ' {"role": "data", "cells": ["Στατική μελέτη προβλήτας", "84", "65,00", "5.460,00"]},'
        ' {"role": "data", "cells": ["Μετακινήσεις και διαμονή", "", "", "438,50"]},'
        ' {"role": "summary", "cells": ["", "", "Καθαρή αξία", "10.030,50"]},'
        ' {"role": "summary", "cells": ["", "", "ΦΠΑ 24%", "2.407,32"]},'
        ' {"role": "summary", "cells": ["", "", "", "Συνολικό πληρωτέο", "12.437,82"]},'
        ' {"role": "summary", "cells": ["", "", "", "", "12.437,82"]}]}'
    )

    def test_the_total_lines_up_and_prints_once(self) -> None:
        zone = table_zone(self.MEASURED)

        assert [[c.text for c in r.cells] for r in zone.rows][3:] == [
            ["", "", "Καθαρή αξία", "10.030,50"],
            ["", "", "ΦΠΑ 24%", "2.407,32"],
            ["", "", "Συνολικό πληρωτέο", "12.437,82"],
        ]
        assert all(len(r.cells) == 4 for r in zone.rows)
        assert table_repairs(zone) == []

    def test_a_non_empty_cell_is_never_trimmed(self) -> None:
        """Only leading *empty* cells go: a wide row whose first cell says
        something is kept whole, and flagged as before."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["a", "b"]},'
            ' {"role": "data", "cells": ["1", "2"]},'
            ' {"role": "data", "cells": ["3", "", "4"]},'
            ' {"role": "data", "cells": ["", "x", "y", "z"]}]}'
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["a", "b"], ["1", "2"], ["3", "", "4"], ["x", "y", "z"],
        ]
        assert ["rows 2–3" in note and "3 cells" in note
                for note in table_repairs(zone)] == [True]

    def test_a_header_narrower_than_its_table_trims_nothing(self) -> None:
        """`menu_0012` and `cv_0013` both read a one-cell header over wider
        rows. There the header's width is not the table's, and trimming to it
        would move values into columns they were not read in."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["To begin"]},'
            ' {"role": "data", "cells": ["Soup", "6.50"]},'
            ' {"role": "data", "cells": ["", "8.00"]}]}'
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["To begin"], ["Soup", "6.50"], ["", "8.00"],
        ]

    def test_a_summary_row_that_adds_any_new_cell_is_kept(self) -> None:
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "summary", "cells": ["Subtotal", "300.00"]},'
            ' {"role": "summary", "cells": ["Total", "300.00"]},'
            ' {"role": "summary", "cells": ["", "300.00", "x"]}]}'
        )

        assert len(zone.rows) == 4

    def test_a_total_repeating_a_data_row_is_kept(self) -> None:
        """Only a summary under a summary: a total equal to the one line above
        it is a real shape, and dropping it would lose a printed number."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "data", "cells": ["Design", "300.00"]},'
            ' {"role": "summary", "cells": ["", "300.00"]}]}'
        )

        assert len(zone.rows) == 3

    def test_the_ir_level_repair_matches_the_wire_level_one(self) -> None:
        """`tools/rederive.py` applies `retrimmed` to IRs made before the two
        nets existed, and must reach the rows a Conversion now makes."""
        raw = TableResponse.model_validate_json(self.MEASURED)
        rows = [Row(role=RowRole(r.role), cells=[cell(t) for t in r.cells])
                for r in raw.rows]

        assert ([[c.text for c in r.cells] for r in retrimmed(rows)]
                == [[c.text for c in r.cells] for r in table_zone(self.MEASURED).rows])


class TestAHeaderRowSplitOneCellPerRow:
    """A header row whose cells sit at opposite edges comes back as two rows.

    Measured on `example/invoice.png` against a real `qwen3-vl:4b` in runs 01,
    05, 10 and 13 — the last of those with a prompt telling it in as many words
    not to. The rows below bind correctly; it is specifically the shaded header
    row, whose two cells are separated by most of the page width.

    The model's *width* is already right — it returns `["Item", ""]`, two cells,
    so it has counted the columns correctly. What it gets wrong is which line
    each cell belongs to. That rules out the remedy 0002 proposed for this (a
    pass asking how many columns the table has): the count was never the thing
    in doubt.

    So the repair is here, and it is exact rather than a guess: two adjacent
    header rows of the same width that are never both filled at the same
    position hold, between them, one row's cells. Merging them invents nothing
    and discards nothing. Anything less tidy is left alone and still fails
    loudly.
    """

    def test_the_split_header_measured_on_the_invoice_becomes_one_row(self) -> None:
        """Verbatim from debug/runs/13-header-row-only, zone 5."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", ""]},'
            ' {"role": "header", "cells": ["", "Price"]},'
            ' {"role": "data", "cells": ["Website design", "$300.00"]}]}'
        )
        assert [r.role for r in zone.rows] == [
            RowRole.HEADER,
            RowRole.DATA,
        ]
        header = zone.rows[0]
        assert [c.readings[0].text for c in header.cells] == ["Item", "Price"]

    def test_two_headers_that_disagree_are_not_merged(self) -> None:
        """Both filled at position 0 is not one row split in two, and guessing
        which to keep would silently drop a heading.

        The join still refuses, which is what this pins. What follows the
        refusal changed in Phase A-1: the second header row is padded and
        declared rather than taking the whole Zone down with it, so `Price`
        survives as its own row instead of being lost along with `Item` and
        `Design`.
        """
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", ""]},'
            ' {"role": "header", "cells": ["Price"]},'
            ' {"role": "data", "cells": ["Design", "$300.00"]}]}'
        )
        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["Item", ""], ["Price", ""], ["Design", "$300.00"],
        ]
        assert any("row 1" in note for note in table_repairs(zone))

    def test_a_single_header_row_is_left_alone(self) -> None:
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "data", "cells": ["Design", "$300.00"]}]}'
        )
        assert len(zone.rows) == 2
        assert [c.readings[0].text for c in zone.rows[0].cells] == ["Item", "Price"]

    def test_data_rows_are_never_merged(self) -> None:
        """Two sparse data rows are a real shape — a table with gaps in it — and
        the evidence says the model reads data rows correctly, so there is
        nothing here to repair and everything to lose."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "data", "cells": ["Design", ""]},'
            ' {"role": "data", "cells": ["", "$300.00"]}]}'
        )
        assert len(zone.rows) == 3

    def test_three_way_splits_merge_into_one(self) -> None:
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["A", "", ""]},'
            ' {"role": "header", "cells": ["", "B", ""]},'
            ' {"role": "header", "cells": ["", "", "C"]},'
            ' {"role": "data", "cells": ["1", "2", "3"]}]}'
        )
        assert len(zone.rows) == 2
        assert [c.readings[0].text for c in zone.rows[0].cells] == ["A", "B", "C"]

    def test_a_wholly_blank_header_row_does_not_survive_the_merge(self) -> None:
        """Run 13 also produced a row with no cells at all. Merging the blank
        away is right; leaving it to fail the width check is not, because the
        message then blames a dropped cell for a row that never held one."""
        zone = table_zone(
            '{"rows": [{"role": "header", "cells": ["Item", ""]},'
            ' {"role": "header", "cells": ["", "Price"]},'
            ' {"role": "header", "cells": ["", ""]},'
            ' {"role": "data", "cells": ["Design", "$300.00"]}]}'
        )
        assert len(zone.rows) == 2
        assert [c.readings[0].text for c in zone.rows[0].cells] == ["Item", "Price"]

    def test_every_cell_records_what_read_it(self) -> None:
        document, _ = convert_with(INVOICE, recorded_for("invoice_0001"))
        reading = document.zones[5].rows[1].cells[0].readings[0]
        assert reading.engine == "ollama"
        assert reading.model and reading.prompt_version


class TestAZoneTooDenseToReadWhole:
    def zone_over(self, height: int, width: int) -> str | None:
        import numpy as np

        from doc_to_html.extractors import resolution_caveat
        from doc_to_html.ir import BBox

        page = np.zeros((height, width, 3), dtype=np.uint8)
        return resolution_caveat(page, Zone(kind=Kind.TABLE,
                                            bbox=BBox(0.0, 0.0, 1.0, 1.0)))

    def test_an_over_tall_zone_is_flagged_as_read_at_reduced_resolution(self) -> None:
        """Slice stitching is not built, so an over-tall Zone is read whole at
        reduced resolution, which can drop rows. Returning a degraded reading as
        if it were an ordinary one is the failure mode worth preventing here."""
        caveat = self.zone_over(4000, 800) or ""
        assert "reduced resolution" in caveat
        assert "overlapping slices" in caveat

    def test_a_zone_merely_wider_than_the_budget_is_not_flagged(self) -> None:
        """Slices are horizontal bands, so width is not what slicing addresses.
        Flagging every full-width Zone of a 1200px page would bury a real finding
        in noise."""
        assert self.zone_over(200, 4000) is None

    def test_a_flagged_zone_keeps_its_content(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Degraded content beats none, so a flagged Zone stays complete and the
        caveat rides alongside it rather than replacing it."""
        assert invoice[0].zones[5].complete

    def test_a_caveat_is_not_a_failure(self) -> None:
        """They were one type once, and the render said so out loud: "Zone 5
        (table) could not be read: read at reduced resolution" — directly above
        the table it had read. A Failure has no content and a skeleton; a Caveat
        has content and a note."""
        from doc_to_html.ir import Caveat

        document = SAMPLE_DOCUMENTS["invoice_0001"]()
        document.caveats = [
            Caveat(zone_index=5, kind="table",
                   note="read at reduced resolution: 4000px tall")
        ]
        html = render(document)

        assert "could not be read" not in html
        assert "read at reduced resolution" in html
        assert 'class="skeleton"' not in html
        assert "Total: $385.00" in html

    def test_slices_are_planned_with_an_overlap(self) -> None:
        """The overlap is what makes slicing safe, and doubles as a consistency
        check on the seam. Stitching is not implemented; the plan is."""
        from doc_to_html.extractors import TableExtractor

        plan = TableExtractor.plan_slices(3000)
        assert plan[0][0] == 0 and plan[-1][1] == 3000
        assert plan[1][0] < plan[0][1], "slices must overlap"


class TestMeasuringTheGridFromThePixels:
    """`table_grid`, and the three real tables it has to be right about.

    Two prompt attempts have failed to stop this model cutting a wide row in half
    — run 13 on the header, run 48 on the general case, the latter returning
    output byte-identical to the run before it. So the remedy has to come from
    something a prompt cannot consult, and this is it: project the crop's ink down
    for rows and across for columns, and count the bands. It reads nothing and
    understands nothing, which is exactly why it can be trusted.

    These are the fixtures' own pixels rather than a synthetic grid, because the
    parameter that matters is the one a drawn test would never exercise — see
    `test_the_gutter_threshold_is_absolute_and_not_a_fraction`.
    """

    def crop_of(self, fixture: str, index: int) -> object:
        """One Zone's pixels, from the sample document's own rectangle.

        Read off the sample `Document` rather than off a committed
        `*.expected.json`: those files were the serialised acceptance set and
        Thread 0 deleted them. The rectangles are the same ones, and they are
        used here as *realistic geometry to crop with*, never as an answer to
        score against.
        """
        from doc_to_html.corpus import SOURCES

        from .documents import SAMPLE_DOCUMENTS

        zone = SAMPLE_DOCUMENTS[fixture]().zones[index]
        assert zone.bbox is not None
        image = rectify(REPO / SOURCES[fixture].png).image
        return zone_pixels(image, Zone(kind=Kind.TABLE, bbox=zone.bbox))

    def test_a_two_row_table_measures_two_rows(self) -> None:
        """`invoice_0001`'s Zone 4 — the Zone the model returns as four rows."""
        grid = table_grid(self.crop_of("invoice_0001", 4))
        assert (grid.rows, grid.columns) == (2, 2)

    def test_the_line_item_table_measures_its_five_rows(self) -> None:
        """Five rows, not six: `content_ink` has already dropped the rule above
        the total, so the ruling does not become a row."""
        grid = table_grid(self.crop_of("invoice_0001", 5))
        assert (grid.rows, grid.columns) == (5, 2)

    def test_the_gutter_threshold_is_absolute_and_not_a_fraction(self) -> None:
        """The parameter that decides whether this generalises at all.

        `invoice_0001`'s table has one 530px gutter, so any threshold works on it.
        `sample_table_0003` has five columns with narrow gutters: at 4% of a 960px
        crop the threshold is 38px, wider than any of them, and all five collapse
        into two bands. Measured, and the reason `MIN_COLUMN_GAP` is a pixel count.
        """
        crop = self.crop_of("sample_table_0003", 1)
        assert table_grid(crop).columns == 5

        mask = content_ink(crop)
        as_a_fraction = len(ink_bands(mask.sum(axis=0),
                                      int(mask.shape[1] * 0.04), MIN_BAND))
        assert as_a_fraction == 2, "the fraction is what this test exists to reject"

    def test_a_title_is_a_printed_line_and_the_prompt_no_longer_hides_it(
        self,
    ) -> None:
        """The ruler and the picture must measure the same pixels.

        `sample_table_0003` prints "Population and GDP (millions of USD)" above
        its grid. That is the Zone's Title in the IR — not a row — but it is a
        band of ink like any other, so the crop counts 17 where the table has
        16. Both numbers are right; they count different things.

        **The old correction was `with_grid(titled=True)` taking one off the
        stated count while the caption stayed in the Extractor's picture, and it
        shipped a deletion** — spec 0007 Phase A0. The crop showed 17 lines, the
        prompt said "return exactly 16", and the model resolved the
        disagreement by dropping the real header row and keeping the caption.
        All five of this table's column headers went that way and the harness
        scored it a full match.

        So the prompt now states what the crop holds, and the caption comes back
        as a row that `wire._without_title_echo` drops after it has been read.
        """
        crop = self.crop_of("sample_table_0003", 1)
        assert table_grid(crop).rows == 17, "the crop really does hold 17 lines"

        asked = with_grid(TABLE_PROMPT, table_grid(crop))
        assert "it holds 17 rows and 5 columns" in asked, (
            "the count describes the picture that is sent, caption included"
        )

    def test_the_prompt_quotes_the_pixels_the_model_is_sent(self) -> None:
        """The property the subtraction could not have, pinned end to end.

        On `with_grid` alone it would not have caught the fault: the count was
        corrected in one place and the crop left alone in another, and nothing
        checked that the two described one page.
        """
        from doc_to_html.corpus import SOURCES

        from .documents import SAMPLE_DOCUMENTS

        zone = SAMPLE_DOCUMENTS["sample_table_0003"]().zones[1]
        assert zone.bbox is not None
        zone.title = "Population and GDP (millions of USD)"
        crop = zone_pixels(rectify(REPO / SOURCES["sample_table_0003"].png).image,
                           zone)

        engine, transport = engine_with(
            '{"rows": [{"role": "header", "cells": ["Country", "ISO",'
            ' "Population", "GDP (USD M)", "Currency"]}]}'
        )
        engine.table_grid_hint = True
        engine.extract_zone(crop, zone)

        assert transport.last is not None
        sent = np.asarray(Image.open(io.BytesIO(transport.last.images[0])))
        grid = table_grid(sent)
        assert f"it holds {grid.rows} rows and {grid.columns} columns" \
            in transport.last.prompt

    def test_a_titled_table_is_no_longer_asked_for_one_row_fewer(self) -> None:
        """The regression test for the deletion itself.

        A Title on the Zone must change nothing about the count, because the
        Title is still in the picture. Both of `invoice_0001`'s tables lack one,
        which is why the count was exact there and this never surfaced until a
        titled table was measured.
        """
        grid = TableGrid(rows=17, columns=5, row_bands=[], column_bands=[])

        assert "it holds 17 rows" in with_grid(TABLE_PROMPT, grid)


class TestStatingTheGridInThePrompt:
    def test_the_counts_reach_the_prompt(self) -> None:
        grid = TableGrid(rows=2, columns=2, row_bands=[], column_bands=[])
        asked = with_grid(TABLE_PROMPT, grid)

        assert "it holds 2 rows and 2 columns" in asked
        assert asked.startswith(TABLE_PROMPT), "stated after, never instead of"

    def test_a_one_column_count_is_still_stated(self) -> None:
        """Measured and kept — spec 0007's queue, Q5, 2026-09-29.

        One column is a wrong count on five of the fifteen tables of the
        re-shot corpus: rules and centred lines bridge the gutters. Withholding
        it was built and measured on all five, by replaying the floor with each
        table asked again without it, and it crossed the ratchet: `menu_0012`
        stopped printing 30 words — told 16 rows it returns the whole menu,
        told nothing it pairs the two columns into 16 rows and drops the rest
        — and `statement_0006` lost `Castleton`. A wrong count of columns still
        carries a count of rows, and that is the part this model obeys.

        On the truncated picture it was measured against first, `receipt_0010`
        collapsed under "19 rows and 1 columns"; on the whole picture its crop
        no longer holds the centred line and it reads every row with the count.
        """
        engine, transport = engine_with('{"rows": [{"role": "data",'
                                        ' "cells": ["a", "b"]}]}')
        engine.table_grid_hint = True
        page = np.full((120, 400, 3), 245, dtype=np.uint8)
        page[20:40, 10:390] = 20
        page[60:80, 10:390] = 20
        assert table_grid(page).columns == 1, "the page must measure one column"

        engine.extract_zone(page, Zone(kind=Kind.TABLE, bbox=BBox(0, 0, 1, 1)))

        assert transport.last is not None
        assert "it holds 2 rows and 1 columns" in transport.last.prompt

    def test_the_flag_off_leaves_the_prompt_exactly_as_it_ships(self) -> None:
        """Off has to mean untouched, or the default is not the measured one."""
        engine, transport = engine_with('{"rows": [{"role": "data",'
                                        ' "cells": ["a", "b"]}]}')
        engine.table_grid_hint = False
        page = np.full((120, 400, 3), 245, dtype=np.uint8)
        page[20:40, 10:100] = 20

        engine.extract_zone(page, Zone(kind=Kind.TABLE, bbox=BBox(0, 0, 1, 1)))

        assert transport.last is not None
        assert transport.last.prompt == TABLE_PROMPT
