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
from doc_to_html.render import render
from doc_to_html.wire import MappingError, TableResponse, contents_into

from .fixtures import BUILDERS
from .replay import (
    Call,
    ReplayTransport,
    convert_recording,
    recorded_for,
    text,
    wired_zones,
)

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"
STATISTICS = REPO / "example" / "sample-table.png"


def convert_with(image: Path, replies: list[object]) -> tuple[Document, ReplayTransport]:
    return convert_recording(image, replies)  # type: ignore[arg-type]


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
        Cropping each Zone from the rectified image is what buys it back.

        The two budgets are what makes this real: layout sees the page at
        `LAYOUT_LONG_EDGE`, extraction crops from the full-resolution rectified
        image. Both were 1024 once, which on an 862px fixture meant neither
        happened and the test below would have passed on a no-op.
        """
        from doc_to_html.preprocess import LAYOUT_LONG_EDGE, PAD_X, PAD_Y

        _, transport = invoice
        page = Image.open(io.BytesIO(transport.calls[0].images[0]))
        crop = Image.open(io.BytesIO(table_calls(transport)[1].images[0]))

        assert max(page.size) == LAYOUT_LONG_EDGE < 862

        # Derived from the fixture's own box and the pads rather than written
        # down: a literal here goes stale the moment either pad is retuned, and
        # a stale literal in this assertion reads as a broken crop.
        box = BUILDERS["invoice_0001"]().zones[5].bbox
        assert box is not None
        wide = min(1.0, box.right + PAD_X) - max(0.0, box.left - PAD_X)
        tall = min(1.0, box.bottom + PAD_Y) - max(0.0, box.top - PAD_Y)

        # The crop is a fraction of a *bigger* page than layout ever saw.
        assert crop.width == pytest.approx(wide * 862, abs=4)
        assert crop.height == pytest.approx(tall * 563, abs=4)
        assert crop.width > page.width

    def test_layout_and_extraction_have_separate_budgets(
        self, invoice: tuple[Document, ReplayTransport]
    ) -> None:
        """Finding regions needs positions; reading a table needs glyphs. One
        budget for both means either layout wastes tokens or extraction cannot
        read."""
        from doc_to_html.preprocess import LAYOUT_LONG_EDGE, MODEL_INPUT_LONG_EDGE

        assert LAYOUT_LONG_EDGE < MODEL_INPUT_LONG_EDGE
        _, transport = invoice
        layout_px = max(Image.open(io.BytesIO(transport.calls[0].images[0])).size)
        assert layout_px <= LAYOUT_LONG_EDGE

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

    def test_a_data_row_must_match_the_header_width(self) -> None:
        with pytest.raises(MappingError, match="row 2 has 3 cells.*header has 2"):
            table_zone(
                '{"rows": [{"role": "header", "cells": ["a", "b"]},'
                ' {"role": "data", "cells": ["1", "2"]},'
                ' {"role": "data", "cells": ["1", "2", "3"]}]}'
            )

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
        which to keep would silently drop a heading."""
        with pytest.raises(MappingError, match="row 1 has 1 cells"):
            table_zone(
                '{"rows": [{"role": "header", "cells": ["Item", ""]},'
                ' {"role": "header", "cells": ["Price"]},'
                ' {"role": "data", "cells": ["Design", "$300.00"]}]}'
            )

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

        document = BUILDERS["invoice_0001"]()
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
