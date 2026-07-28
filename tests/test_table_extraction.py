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

from doc_to_html.ir import Document, Kind, RowRole, Zone
from doc_to_html.orchestrator import convert
from doc_to_html.render import render
from doc_to_html.wire import MappingError, TableResponse, contents_into

from .replay import Call, ReplayTransport, recorded_for, text, wired_zones
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
    def broken_at(self, zone_index: int, payload: str) -> Document:
        replies = recorded_for("invoice_0001")
        replies[wired_zones("invoice_0001").index(zone_index) + 1] = text(payload)
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
        document = self.broken_at(1, '{"pairs": [{"label": "", "value": "x"}]}')
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
        assert "<table>" in html
        assert "could not be read" in html


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

    def test_slices_are_planned_with_an_overlap(self) -> None:
        """The overlap is what makes slicing safe, and doubles as a consistency
        check on the seam. Stitching is not implemented; the plan is."""
        from doc_to_html.extractors import TableExtractor

        plan = TableExtractor.plan_slices(3000)
        assert plan[0][0] == 0 and plan[-1][1] == 3000
        assert plan[1][0] < plan[0][1], "slices must overlap"
