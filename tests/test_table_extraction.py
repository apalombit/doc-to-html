"""Tables stop being skeletons.

Two documents, and between them the whole of what a table can be: one whose
totals row sits inside it, and one with fifteen rows and nothing to reconcile.
This is also where Probes run against extracted data for the first time, and
where the failure contract is exercised on a document that partly worked.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from doc_to_html.ir import Document, Kind, RowRole
from doc_to_html.orchestrator import convert
from doc_to_html.render import render
from doc_to_html.wire import MappingError, TableResponse, contents_into

from .replay import Call, ReplayTransport, recorded, text
from .test_tracer_bullet import engines_replaying

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"
STATISTICS = REPO / "example" / "sample-table.png"


def convert_with(image: Path, replies: list[object]) -> tuple[Document, ReplayTransport]:
    transport = ReplayTransport(replies)  # type: ignore[arg-type]
    return convert(image, engines=engines_replaying(transport)), transport


def table_calls(transport: ReplayTransport) -> list[Call]:
    """The calls that asked for rows, in order."""
    return [call for call in transport.calls if "role" in str(call.schema)
            and "rows" in str(call.schema)]


@pytest.fixture
def invoice() -> tuple[Document, ReplayTransport]:
    return convert_with(INVOICE, recorded("invoice_0001", zones=[4, 5]))


@pytest.fixture
def statistics() -> tuple[Document, ReplayTransport]:
    return convert_with(STATISTICS, recorded("sample_table_0003", zones=[1]))


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
        html = render(invoice[0])
        assert "<thead><tr><th>Payment Method</th>" in html
        assert '<thead><tr><th>Item</th><th class="num">Price</th></tr></thead>' in html

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
        assert "<td>USA</td>" in html
        assert '<td class="num">331,900,000</td>' in html
        assert "<td>USD</td>" in html


class TestExtractionReadsTheRightPixels:
    def test_a_table_is_read_from_a_crop_and_not_from_the_page(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """The layout pass gives resolution away by looking at the whole page.
        Cropping each Zone from the rectified image is what buys it back."""
        _, transport = invoice
        page = Image.open(io.BytesIO(transport.calls[0].images[0]))
        crop = Image.open(io.BytesIO(table_calls(transport)[1].images[0]))
        assert page.size == (862, 563)
        assert crop.width == pytest.approx(0.96 * 862, abs=4)
        assert crop.height == pytest.approx(0.34 * 563, abs=4)

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
    def test_zones_that_failed_do_not_cost_the_ones_that_worked(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Throwing away two correct tables because a Pairs Zone had no
        Extractor would destroy exactly the evidence the run exists to produce."""
        document, _ = invoice
        assert [z.complete for z in document.zones] == [
            False, False, False, False, True, True
        ]
        assert [f.zone_index for f in document.failures] == [0, 1, 2, 3]
        assert all(f.reason for f in document.failures)

    def test_a_failed_zone_renders_as_a_skeleton_beside_real_content(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        html = render(invoice[0])
        assert 'class="skeleton"' in html
        assert "<table>" in html
        assert "could not be read" in html

    def test_a_broken_table_response_does_not_abort_the_run(self) -> None:
        """Only rectification failing outright, or a layout pass returning no
        Zones, aborts a Conversion. Everything else is reported."""
        replies = recorded("invoice_0001", zones=[4])
        replies.append(text('{"rows": []}'))
        document, _ = convert_with(INVOICE, replies)  # type: ignore[arg-type]
        assert document.zones[4].complete
        assert not document.zones[5].complete
        assert [f.zone_index for f in document.failures] == [0, 1, 2, 3, 5]
        assert "no rows" in document.failures[-1].reason


class TestMappingATableResponse:
    def rows(self, payload: str) -> Document:
        from doc_to_html.ir import Reading, Zone

        zone = Zone(kind=Kind.TABLE)
        contents_into(zone, payload, read=lambda t: Reading(engine="test", text=t))
        return zone  # type: ignore[return-value]

    def test_an_empty_result_is_a_failure_not_an_empty_table(self) -> None:
        """A schema cannot say that a region a model was pointed at has rows in
        it. An empty table rendered as a table looks like a document that had
        one."""
        with pytest.raises(MappingError, match="no rows"):
            self.rows('{"rows": []}')

    def test_a_data_row_must_match_the_header_width(self) -> None:
        with pytest.raises(MappingError, match="row 2 has 3 cells.*header has 2"):
            self.rows(
                '{"rows": [{"role": "header", "cells": ["a", "b"]},'
                ' {"role": "data", "cells": ["1", "2"]},'
                ' {"role": "data", "cells": ["1", "2", "3"]}]}'
            )

    def test_a_summary_row_may_be_narrower_because_totals_rows_merge_cells(
        self,
    ) -> None:
        zone = self.rows(
            '{"rows": [{"role": "header", "cells": ["Item", "Price"]},'
            ' {"role": "data", "cells": ["Design", "300.00"]},'
            ' {"role": "summary", "cells": ["Total: 300.00"]}]}'
        )
        assert [len(r.cells) for r in zone.rows] == [2, 2, 1]  # type: ignore[attr-defined]

    def test_a_table_with_no_header_row_is_allowed(self) -> None:
        """Plenty of tables have none. There is then nothing to check widths
        against, which is a smaller problem than rejecting the table."""
        zone = self.rows('{"rows": [{"role": "data", "cells": ["a", "b"]}]}')
        assert len(zone.rows) == 1  # type: ignore[attr-defined]

    def test_every_cell_records_what_read_it(self) -> None:
        document, _ = convert_with(INVOICE, recorded("invoice_0001", zones=[4, 5]))
        reading = document.zones[5].rows[1].cells[0].readings[0]
        assert reading.engine == "ollama"
        assert reading.model and reading.prompt_version


class TestAZoneTooDenseToReadWhole:
    def test_a_zone_over_the_input_budget_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Slice stitching is not built, so an over-tall Zone is read at reduced
        resolution. Silently returning a degraded reading as if it were a normal
        one is the failure mode worth preventing here."""
        from doc_to_html import extractors

        monkeypatch.setattr(extractors, "MODEL_INPUT_LONG_EDGE", 64)
        document, _ = convert_with(INVOICE, recorded("invoice_0001", zones=[4, 5]))
        assert document.zones[5].complete
        reduced = [f for f in document.failures if "reduced resolution" in f.reason]
        assert [f.zone_index for f in reduced] == [4, 5]

    def test_slices_are_planned_with_an_overlap(self) -> None:
        """The overlap is what makes slicing safe, and doubles as a consistency
        check on the seam. Stitching is not implemented; the plan is."""
        from doc_to_html.extractors import TableExtractor

        plan = TableExtractor.plan_slices(3000)
        assert plan[0][0] == 0 and plan[-1][1] == 3000
        assert plan[1][0] < plan[0][1], "slices must overlap"
