"""The caption pass: the Title is read before the Kind is asked.

Two questions want opposite pixels. The Title needs the caption band in frame,
and the Kind is measurably wrong while it is there — a shaded panel caption
satisfies `CLASSIFY_PROMPT`'s own "top row set apart" test for a table. One call
cannot show both frames, so there are two.

What each half of this file pins:

- the ink measurement, which decides *whether to ask at all*, and whose `None`
  is the only thing standing between an over-split Zone and having its single
  line taken as its own Title and then read again as its content;
- the Orchestrator's two steps, including that the Kind question is handed a
  shorter image than the caption question was.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from doc_to_html.ir import BBox, Document, Kind, Reading, Source, Zone
from doc_to_html.orchestrator import Conversion
from doc_to_html.render import render
from doc_to_html.preprocess import (
    PAD_Y,
    caption_band,
    crop,
    crop_row_as_fraction,
    rectify,
    zone_pixels,
)
from doc_to_html.trace import Disposition, Stage
from doc_to_html.wire import contents_into, prints, table_repairs


def a_reading(content: str) -> Reading:
    """The `Read` a mapper is injected with, so these stay pure. See `wire.Read`."""
    return Reading(engine="test", text=content)

from .replay import (
    ReplayTransport,
    break_zone,
    engines_replaying,
    geometry,
    recorded_for,
    text,
)

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"


def page(rows: list[tuple[int, int]], width: int = 400,
         height: int = 300) -> np.ndarray:
    """A white page with a black bar across each `(top, bottom)` row range."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    for top, bottom in rows:
        image[top:bottom, 20:width - 20] = 0
    return image


class TestTheInkDecidesWhetherToAsk:
    def test_a_crop_with_one_band_has_no_caption(self) -> None:
        """The guard the whole change rests on, and it is structural rather than
        a judgement: one band means nothing is printed below the first line, so
        there is no caption to lift off and no body to leave behind.

        20 of run 69's 36 Zone crops are like this — every one of
        `sample_css_0004`'s and eight of `sample_semantic_0005`'s, which are
        headings standing as Zones of their own.
        """
        assert caption_band(page([(10, 30)])) is None

    def test_an_empty_crop_has_no_caption(self) -> None:
        assert caption_band(page([])) is None

    def test_a_rule_down_the_side_does_not_make_the_region_one_band(self) -> None:
        """`sample_semantic_0005`'s callout and its opening section, as pixels.

        Both carry a 3px `border-left`. Banding projects ink across each row, so
        one column inked top to bottom makes every row inked and the whole crop
        reads as a single unbroken band — which is then refused, and the Zone is
        never asked for a Title it plainly has. Measured on the real crops: 1
        band each with the rule, 3 and 4 without.
        """
        ruled = page([(10, 30), (60, 80)])
        ruled[:, 5:8] = 0

        band = caption_band(ruled)

        assert band is not None
        assert (band.top, band.bottom) == (10, 29)
        assert band.lines == 2

    def test_a_run_that_stops_short_is_ink_and_is_taken_at_face_value(
        self,
    ) -> None:
        """The exception is the strictest one available — inked in *every* row —
        and this is the cost of that, stated rather than hidden.

        A column that stops short of the full height is ink somebody printed: a
        tall glyph, a bullet column, a gridline between two rows of cells. It is
        not removed, so where it happens to bridge two bands the crop still
        reads as one and is still refused. Widening the test to catch this case
        would start deleting real ink, which is the more expensive mistake: the
        cost here is a Title not asked for, and there it is a body silently cut
        off the Kind question.
        """
        bridged = page([(10, 30), (60, 80)])
        bridged[0:200, 5:8] = 0

        assert caption_band(bridged) is None

    def test_a_crop_that_is_solid_ink_is_still_refused(self) -> None:
        """The fallback. Clearing every column would leave nothing to band at
        all, so a genuinely solid crop keeps reporting one band and is refused
        rather than reporting none."""
        solid = np.zeros((300, 400, 3), dtype=np.uint8)

        assert caption_band(solid) is None

    def test_two_bands_are_measured(self) -> None:
        band = caption_band(page([(10, 30), (60, 80), (90, 110)]))

        assert band is not None
        assert (band.top, band.bottom) == (10, 29)
        assert band.gap_below == 31
        assert band.lines == 3

    def test_the_median_gap_skips_the_caption_s_own_gap(self) -> None:
        """`gap_below` is the number under test; the median it is read against
        must not include it, or a well-separated caption would raise the very
        baseline it is being compared to."""
        band = caption_band(page([(10, 20), (80, 90), (100, 110), (120, 130)]))

        assert band is not None
        assert band.gap_below == 61
        assert band.median_gap == 11
        assert band.gap_below > band.median_gap

    def test_a_first_line_over_the_same_columns_is_a_grid_heading(self) -> None:
        """Two cells over two columns of values. This is `invoice_0001`'s Zone 4,
        the crop the model still calls a caption, and the ink says otherwise."""
        image = np.full((300, 400, 3), 255, dtype=np.uint8)
        for top, bottom in [(10, 20), (60, 70), (110, 120)]:
            image[top:bottom, 20:120] = 0        # left column
            image[top:bottom, 260:380] = 0       # right column, a wide gutter off
        band = caption_band(image)

        assert band is not None
        assert (band.head_columns, band.body_columns) == (2, 2)
        assert band.aligns_to_grid

    def test_a_caption_spanning_the_region_does_not_align(self) -> None:
        """`sample_table_0003`: one caption over a six-column table."""
        image = np.full((300, 400, 3), 255, dtype=np.uint8)
        image[10:20, 20:200] = 0                 # the caption, one run of ink
        for top, bottom in [(60, 70), (110, 120)]:
            for left in (20, 120, 220, 320):
                image[top:bottom, left:left + 60] = 0
        band = caption_band(image)

        assert band is not None
        assert band.head_columns == 1
        assert not band.aligns_to_grid

    def test_one_column_either_side_is_not_a_grid(self) -> None:
        """A one-word caption over a stack of single-column lines matches counts
        at 1 == 1, which is why alignment also requires more than one column."""
        band = caption_band(page([(10, 20), (60, 70), (110, 120)]))

        assert band is not None
        assert (band.head_columns, band.body_columns) == (1, 1)
        assert not band.aligns_to_grid

    def test_two_bands_alone_have_no_median_to_compare_against(self) -> None:
        band = caption_band(page([(10, 20), (80, 90)]))

        assert band is not None
        assert band.median_gap is None

    def test_the_cut_lands_in_the_blank_and_not_on_either_line(self) -> None:
        """Clear of this line's descenders, short of the next line's ascenders."""
        band = caption_band(page([(10, 20), (80, 90)]))

        assert band is not None
        assert band.bottom < band.cut_row < 80


class TestTheTwoCoordinateSystemsAgree:
    def test_a_crop_row_maps_back_onto_the_page(self) -> None:
        """`caption_band` measures in crop rows and the Trace reports in page
        fractions. This pins the one piece of arithmetic that converts between
        them against `crop` itself, so the contact sheet cannot drift into
        drawing a different rectangle from the one the model was shown."""
        image = page([(10, 20)], width=400, height=300)
        box = BBox(left=0.1, top=0.2, right=0.9, bottom=0.8)
        cut = 40

        # Where `crop` starts the Zone's crop, restated from its own arithmetic.
        started = int(max(0.0, box.top - PAD_Y) * 300)
        assert crop(image, box).shape[0] == int(min(1.0, box.bottom + PAD_Y)
                                                * 300) - started

        moved = crop_row_as_fraction(image, box, cut)

        assert int(moved * 300) == started + cut


class TestTheOrchestratorAsksInTheRightOrder:
    def converted(self, *, caption_pass: bool,
                  captions: list[str] | None = None
                  ) -> tuple[Conversion, ReplayTransport]:
        replies = recorded_for("invoice_0001")
        if captions is not None:
            replies["caption"] = [text(answer) for answer in captions]
        transport = ReplayTransport(replies)
        conversion = Conversion(source=INVOICE,
                                engines=engines_replaying(
                                    transport, geometry("invoice_0001")),
                                caption_pass=caption_pass)
        conversion.run()
        return conversion, transport

    def test_switched_off_the_pass_asks_nothing(self) -> None:
        """The escape hatch, which stays reachable now that the pass ships on:
        `DTH_CAPTION_PASS=0` runs one call per Zone, exactly as run 69 did."""
        _, transport = self.converted(caption_pass=False)

        assert [c.pass_name for c in transport.calls].count("caption") == 0

    def test_on_the_shipped_default_it_asks(self) -> None:
        """The mirror, and the reason it is worth a test of its own: for ten runs
        this pass was built, tested and switched off, and every test that
        exercised it named `caption_pass=True` by hand — so nothing would have
        noticed if the default had never taken effect."""
        from doc_to_html.config import DEFAULT_CAPTION_PASS

        assert DEFAULT_CAPTION_PASS is True

        replies = recorded_for("invoice_0001")
        transport = ReplayTransport(replies)
        conversion = Conversion(source=INVOICE,
                                engines=engines_replaying(
                                    transport, geometry("invoice_0001")))
        conversion.run()

        assert [c.pass_name for c in transport.calls].count("caption") > 0

    def test_a_zone_is_asked_before_it_is_classified(self) -> None:
        """Order is the whole design: the Title is read from the whole crop, and
        only then is the Kind asked about what is left."""
        heading = '{"first_line": "Payment Method", "line_is": "caption"}'
        _, transport = self.converted(caption_pass=True, captions=[heading] * 6)

        asked = [c.pass_name for c in transport.calls]
        assert asked[asked.index("caption")] == "caption"
        assert asked[asked.index("caption") + 1] == "classify"

    def test_only_zones_with_something_under_the_first_line_are_asked(
        self,
    ) -> None:
        """`invoice_0001`'s Zone 0 is a wordmark on one line. Asking it for a
        caption would invite it to name its only line as its own Title."""
        heading = '{"first_line": "Payment Method", "line_is": "caption"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[heading] * 6)

        rectified = rectify(INVOICE)
        document = conversion.document
        assert document is not None
        single = [index for index, zone in enumerate(document.zones)
                  if caption_band(zone_pixels(rectified.image, zone)) is None]

        assert single, "the fixture must contain at least one single-band Zone"
        asked = [c.pass_name for c in transport.calls].count("caption")
        assert asked == len(document.zones) - len(single)

    def test_a_skipped_zone_says_so_in_the_trace(self) -> None:
        heading = '{"first_line": "Payment Method", "line_is": "caption"}'
        conversion, _ = self.converted(caption_pass=True, captions=[heading] * 6)

        skipped = [event for event in conversion.trace.in_stage(Stage.CLASSIFY)
                   if event.step == "read_caption"
                   and event.disposition is Disposition.SKIPPED]

        assert skipped
        assert all(event.data["lines"] == 1 for event in skipped)

    def test_a_heading_becomes_the_title_and_is_cut_from_the_kind_question(
        self,
    ) -> None:
        """The two assertions that carry the change: the Title arrives, and the
        Kind question is handed strictly fewer pixels than the caption question
        was — the band whose absence moved 2 of 3 `invoice_0002` panels from
        `table` to the correct `pairs`."""
        heading = '{"first_line": "Payment Method", "line_is": "caption"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[heading] * 6)
        document = conversion.document
        assert document is not None

        assert any(zone.title == "Payment Method" for zone in document.zones)

        captions = [c for c in transport.calls if c.pass_name == "caption"]
        classifies = [c for c in transport.calls if c.pass_name == "classify"]
        shown = Image.open(io.BytesIO(captions[0].images[0]))
        # The classify calls include the Zones no caption was read for, so pair
        # the first caption with the classify that followed it.
        first = transport.calls.index(captions[0])
        after = next(c for c in transport.calls[first:] if c.pass_name == "classify")
        stripped = Image.open(io.BytesIO(after.images[0]))

        assert stripped.height < shown.height
        assert stripped.width == shown.width
        assert len(classifies) == len(document.zones)

    def test_a_first_line_that_is_content_leaves_the_crop_whole(self) -> None:
        """The negative case, and the one `invoice_0001` is the control for: it
        expects no Titles at all, so a Zone told "this line is content" must keep
        both its full crop and an unset Title."""
        content = '{"first_line": "Bill To", "line_is": "content"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[content] * 6)
        document = conversion.document
        assert document is not None

        assert all(zone.title is None for zone in document.zones)

        captions = [c for c in transport.calls if c.pass_name == "caption"]
        first = transport.calls.index(captions[0])
        after = next(c for c in transport.calls[first:] if c.pass_name == "classify")
        assert (Image.open(io.BytesIO(after.images[0])).height
                == Image.open(io.BytesIO(captions[0].images[0])).height)

    def unchanged_crop(self, transport: ReplayTransport) -> None:
        """Assert the Kind question was handed the same pixels the caption was."""
        captions = [c for c in transport.calls if c.pass_name == "caption"]
        first = transport.calls.index(captions[0])
        after = next(c for c in transport.calls[first:]
                     if c.pass_name == "classify")
        assert (Image.open(io.BytesIO(after.images[0])).height
                == Image.open(io.BytesIO(captions[0].images[0])).height)

    def test_a_grid_heading_row_leaves_the_crop_whole(self) -> None:
        """Run 71's actual regression, as a test. `"Item"` and `"Payment Method"`
        are `invoice_0001`'s two table heading rows; the two-value schema had no
        way to say so, called them headings, and cut them off — Zone 4 became one
        data row and classified `pairs`, Zone 5 lost its summary row and the
        385.00 Probe with it. `header` must take no Title and cut nothing."""
        header = '{"first_line": "Item", "line_is": "header"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[header] * 6)
        document = conversion.document
        assert document is not None

        assert all(zone.title is None for zone in document.zones)
        self.unchanged_crop(transport)

    def test_the_ink_refuses_a_caption_on_a_grid_heading_row(self) -> None:
        """`invoice_0001`'s Zone 4 is the case: the model calls "Payment Method"
        a caption in run 72a, and its two cells sit over the two columns of the
        row beneath. The ink refuses, so no Title is taken and nothing is cut —
        which is what keeps the Zone a `table`.

        The veto only ever points one way. It can refuse a caption and never
        assert one, because a refused caption costs a Title and a false one cost
        run 71 a Kind, a summary row and the 385.00 Probe.
        """
        caption = '{"first_line": "Payment Method", "line_is": "caption"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[caption] * 6)
        document = conversion.document
        assert document is not None

        rectified = rectify(INVOICE)
        gridded = [
            index for index, zone in enumerate(document.zones)
            if (band := caption_band(zone_pixels(rectified.image, zone)))
            and band.aligns_to_grid
        ]
        assert gridded, "the fixture must contain at least one grid heading row"
        # What the veto protects: the Kind is asked on the whole crop, so each
        # gridded Zone is still the table its heading row makes it, and the
        # Zone whose heading row *is* the refused line takes no Title.
        assert all(document.zones[index].kind is Kind.TABLE for index in gridded)
        heading_row = [index for index in gridded
                       if prints(document.zones[index], "Payment Method")]
        assert heading_row
        assert all(document.zones[index].title is None for index in heading_row)

        vetoed = [event for event in conversion.trace.in_stage(Stage.CLASSIFY)
                  if event.step == "read_caption" and event.data.get("vetoed")]
        assert [event.zone_index for event in vetoed] == gridded
        for event in vetoed:
            assert event.data["vetoed"] == "Payment Method"
            assert event.data["head_columns"] == event.data["body_columns"]
            assert event.data["cut_row"] == 0

    def test_a_refused_caption_the_reading_drops_becomes_the_title(self) -> None:
        """Spec 0010, step A1. This stub serves `Payment Method` as every
        Zone's caption, so the `Item | Price` table's veto refuses a line its
        reading prints nowhere — the shape of `darkdeck_0009`'s `OPEN RISKS`,
        a caption the veto refused and the list reading then dropped. Once
        extraction is done it is the Title, and the Zone keeps its Kind and
        every row."""
        caption = '{"first_line": "Payment Method", "line_is": "caption"}'
        conversion, _ = self.converted(caption_pass=True, captions=[caption] * 6)
        document = conversion.document
        assert document is not None

        restored = [event for event in conversion.trace.in_stage(Stage.EXTRACT)
                    if event.step == "vetoed_caption"]
        assert restored
        for event in restored:
            assert event.zone_index is not None
            zone = document.zones[event.zone_index]
            assert zone.title == "Payment Method"
            assert zone.kind is Kind.TABLE
            assert zone.rows
            assert not prints(zone, "Payment Method")

    def test_a_caption_naming_nothing_takes_no_title_and_cuts_nothing(
        self,
    ) -> None:
        """`caption` with a blank line. The cut is gated on the Title rather than
        on the verdict, so an unnameable caption cannot cost the Kind question a
        band it could not have named — the two decisions cannot drift apart."""
        blank = '{"first_line": "   ", "line_is": "caption"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[blank] * 6)
        document = conversion.document
        assert document is not None

        assert all(zone.title is None for zone in document.zones)
        self.unchanged_crop(transport)

    def test_a_verdict_outside_the_three_costs_the_title_and_nothing_else(
        self,
    ) -> None:
        """The lenient path for cloud models does not honour `format`, so an
        answer outside the enum is reachable in production."""
        bogus = '{"first_line": "Item", "line_is": "probably"}'
        conversion, transport = self.converted(caption_pass=True,
                                               captions=[bogus] * 6)
        document = conversion.document
        assert document is not None

        assert all(zone.title is None for zone in document.zones)
        assert document.failures == []
        self.unchanged_crop(transport)

        rejected = [event for event in conversion.trace.in_stage(Stage.CLASSIFY)
                    if event.step == "read_caption"
                    and event.disposition is Disposition.REJECTED]
        assert rejected

    def test_a_caption_that_fails_does_not_cost_the_kind(self) -> None:
        """A Title is not worth a skeleton. The Zone keeps its whole crop and
        goes on to be classified, which is what routes it to an Extractor."""
        conversion, transport = self.converted(caption_pass=True,
                                               captions=["not json"] * 6)
        document = conversion.document
        assert document is not None

        assert all(zone.title is None for zone in document.zones)
        assert [zone.kind for zone in document.zones] == [
            Kind.FIGURE, Kind.PAIRS, Kind.PROSE, Kind.PROSE,
            Kind.TABLE, Kind.TABLE,
        ]
        assert document.failures == []

        rejected = [event for event in conversion.trace.in_stage(Stage.CLASSIFY)
                    if event.step == "read_caption"
                    and event.disposition is Disposition.REJECTED]
        assert rejected


class TestTheTraceExplainsTheStep:
    def test_the_caption_step_records_the_band_it_measured(self) -> None:
        """`trace.py`'s standard: could someone troubleshoot this step from the
        trace alone? That means the numbers the guard was applied to, not just
        its verdict."""
        replies = recorded_for("invoice_0001")
        replies["caption"] = [
            text('{"first_line": "Payment Method", "line_is": "caption"}')
        ] * 6
        conversion = Conversion(
            source=INVOICE,
            engines=engines_replaying(ReplayTransport(replies),
                                      geometry("invoice_0001")),
            caption_pass=True,
        )
        conversion.run()

        taken = [event for event in conversion.trace.in_stage(Stage.CLASSIFY)
                 if event.step == "read_caption"
                 and event.disposition is Disposition.ACCEPTED]

        assert taken
        for event in taken:
            assert event.data["title"] == "Payment Method"
            assert event.data["lines"] >= 2
            assert event.data["cut_row"] > event.data["band_bottom"]
            assert event.data["crop"]["box"] is not None
            assert event.changed[0].path.endswith(".title")

    def test_the_kind_step_reports_the_crop_it_was_actually_shown(self) -> None:
        """The contact sheet draws `crop.box`, so a Zone whose caption was cut
        must report the cut box — otherwise the sheet shows the reader a band
        the model never saw, which is the one thing this diagnostic exists to
        settle."""
        replies = recorded_for("invoice_0001")
        replies["caption"] = [
            text('{"first_line": "Payment Method", "line_is": "caption"}')
        ] * 6
        conversion = Conversion(
            source=INVOICE,
            engines=engines_replaying(ReplayTransport(replies),
                                      geometry("invoice_0001")),
            caption_pass=True,
        )
        conversion.run()
        document = conversion.document
        assert document is not None

        for event in conversion.trace.in_stage(Stage.CLASSIFY):
            if event.step != "classify_zone" or not event.data.get("skip_rows"):
                continue
            assert event.zone_index is not None
            zone = document.zones[event.zone_index]
            assert zone.bbox is not None
            assert event.data["crop"]["box"]["top"] > zone.bbox.top


class TestATitleIsNeverPrintedTwice:
    """A Zone carrying a Title must not also carry an entry repeating it.

    **The corpus's most pervasive visual fault, and spec 0007 Phase A0's first.**
    Over Phase A0's checkpoint, 34 Zones of 45 titled ones carried an echo across
    12 of the 15 documents, and `report_0011` printed all eight of its numbered
    headings twice — the duplicate rendered *larger* than the Title level, so the
    hierarchy inverted.

    The cause is that the caption pass lifts the first printed line into
    `Zone.title` and then leaves it in the Extractor's crop, so the model is
    shown it twice and answers honestly both times. The remedy is here, in
    `wire.py`, rather than as a filter in `render.py`, because anything reading
    the IR rather than the page would otherwise see the heading twice as well.

    **`Completeness.duplicated` is not what this is measured against** and was
    rejected as A0's gate: it reports only strings the *source projection* also
    carries, and `report_0011`'s section numbers are CSS `::before` counters that
    the projection cannot see, so it came back empty for the worst document in
    the corpus. This is counted in the IR instead, where nothing can be blind.
    """

    def zone(self, **fields: object) -> Zone:
        return Zone(kind=Kind.PROSE, title="Deferred works", **fields)  # type: ignore[arg-type]

    def test_a_block_repeating_the_title_is_dropped(self) -> None:
        zone = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "heading", "lines": ["Deferred works"]},'
            ' {"kind": "paragraph", "lines": ["The gates were last surveyed."]}]}',
            read=a_reading,
        )

        assert [line.text for block in zone.blocks for line in block.lines] == [
            "The gates were last surveyed."
        ]
        assert zone.title == "Deferred works", "the Title is what survives"

    def test_the_spelling_rule_is_case_and_whitespace_only(self) -> None:
        """Punctuation is deliberately kept. A Title and a Block differing by a
        colon are two different printed lines, and the echo is a verbatim
        repeat."""
        kept = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "heading", "lines": ["Deferred works:"]}]}',
            read=a_reading,
        )
        assert len(kept.blocks) == 1, "a colon makes it a different line"

        dropped = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "heading", "lines": ["  DEFERRED   WORKS "]},'
            ' {"kind": "paragraph", "lines": ["body"]}]}',
            read=a_reading,
        )
        assert [line.text for b in dropped.blocks for line in b.lines] == ["body"]

    def test_a_title_that_starts_its_heading_goes_and_the_heading_stays(self) -> None:
        """Spec 0012, G8 — `paper_0018`'s title, set on two lines: the caption
        pass read the first, the heading Block holds both, and the page drew
        the first line twice."""
        zone = contents_into(
            Zone(kind=Kind.PROSE, title="Frost Heave Under Lightweight Footbridges:"),
            '{"blocks": [{"kind": "heading", "lines": ["Frost Heave Under Lightweight'
            ' Footbridges: A Field Study of Three Timber Crossings"]},'
            ' {"kind": "paragraph", "lines": ["M. Lindqvist"]}]}',
            read=a_reading,
        )

        assert zone.title is None
        assert [b.lines[0].text for b in zone.blocks] == [
            "Frost Heave Under Lightweight Footbridges: A Field Study of Three"
            " Timber Crossings", "M. Lindqvist"]

    def test_a_paragraph_opening_with_the_titles_words_keeps_it(self) -> None:
        zone = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "paragraph", "lines": ["Deferred works were'
            ' agreed at the Board."]}]}',
            read=a_reading,
        )
        assert zone.title == "Deferred works" and len(zone.blocks) == 1

    def test_only_the_first_block_is_ever_looked_at(self) -> None:
        """Measured rather than chosen: every one of the checkpoint's 27 Block
        echoes was `blocks[0]`, with nothing between 0.80 similarity and an
        exact match. A rule that scanned the body would catch none of them that
        this does not, and would be free to delete a legitimate repetition."""
        zone = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "paragraph", "lines": ["Three schemes ran."]},'
            ' {"kind": "paragraph", "lines": ["Deferred works"]}]}',
            read=a_reading,
        )

        assert len(zone.blocks) == 2, "a repeat further down is content"

    def test_a_table_caption_returned_as_its_first_row_is_dropped(self) -> None:
        zone = contents_into(
            Zone(kind=Kind.TABLE, title="Population and GDP (millions of USD)"),
            '{"rows": [{"role": "header",'
            ' "cells": ["Population and GDP (millions of USD)", "", ""]},'
            ' {"role": "header", "cells": ["Country", "ISO", "Population"]},'
            ' {"role": "data", "cells": ["United States", "USA", "331,900,000"]}]}',
            read=a_reading,
        )

        assert [[c.text for c in r.cells] for r in zone.rows] == [
            ["Country", "ISO", "Population"],
            ["United States", "USA", "331,900,000"],
        ]

    def test_a_dropped_caption_row_leaves_no_padding_behind(self) -> None:
        """The caption row is one cell wider than the table, and it goes.

        `statement_0006`'s header and all forty of its rows were read six
        cells wide, and its caption came back as a first header row of seven.
        The table's width is taken from the first header, so every other row
        was padded to seven before the caption was dropped as an echo — and
        the padding outlived the row that caused it: an empty seventh column,
        and a Caveat saying 41 rows came back a cell short when none had.
        """
        zone = contents_into(
            Zone(kind=Kind.TABLE, title="Transactions in date order"),
            '{"rows": [{"role": "header",'
            ' "cells": ["Transactions in date order", "", "", ""]},'
            ' {"role": "header", "cells": ["Date", "Description", "Balance"]},'
            ' {"role": "data", "cells": ["01 Aug", "Opening balance", "2,418.50"]},'
            ' {"role": "data", "cells": ["02 Aug", "Cordell Energy"]},'
            ' {"role": "summary", "cells": ["Totals", "3,586.14"]}]}',
            read=a_reading,
        )

        assert [len(r.cells) for r in zone.rows] == [3, 3, 3, 2]
        assert [[c.text for c in r.cells] for r in zone.rows][:2] == [
            ["Date", "Description", "Balance"],
            ["01 Aug", "Opening balance", "2,418.50"],
        ]
        # A row genuinely short of the header that is left is still padded,
        # and still carries no Reading where it was padded.
        assert [bool(c.readings) for c in zone.rows[2].cells] == [
            True, True, False]
        assert table_repairs(zone) == [
            "row 2 came back 1 cell(s) short of the header's 3 and was padded "
            "rather than discarded — the values it does have may sit in the "
            "wrong columns"
        ]

    def test_through_a_conversion_a_wide_caption_row_pads_nothing(self) -> None:
        """The rule runs where the pipeline binds contents to a titled Zone.

        `sample_table_0003` replayed, with its table answer given a caption row
        one cell wider than its five columns — `statement_0006`'s shape.
        """
        recorded = json.loads(
            (REPO / "tests/responses/sample_table_0003/zone_01.json").read_text())
        caption = {"role": "header", "cells": [
            "Population and GDP (millions of USD)", "", "", "", "", ""]}
        replies = break_zone(recorded_for("sample_table_0003"),
                             "sample_table_0003", 1,
                             json.dumps({"rows": [caption, *recorded["rows"]]}))
        conversion = Conversion(source=REPO / "example" / "sample-table.png",
                                engines=engines_replaying(ReplayTransport(replies),
                                                          geometry("sample_table_0003")))
        document = conversion.run()

        table = next(z for z in document.zones if z.kind is Kind.TABLE)
        assert len(table.rows) == 16
        assert all(len(r.cells) == 5 for r in table.rows)
        assert all(c.readings for r in table.rows for c in r.cells)
        assert not any("short of the header" in c.note
                       for c in document.caveats)

    def test_a_real_heading_row_that_starts_with_the_title_keeps_the_label(
            self) -> None:
        """The bound that makes the row rule safe, and it is a live case.

        `darkdeck_0009`'s Zone 2 is four metric cards whose labels read
        `AVAILABILITY / P95 LATENCY / INGEST VOLUME / COST PER MILLION`, and the
        caption pass takes the first of them as the Zone's Title. The row is not
        an echo of that Title — it is the Title plus three more labels — so the
        test is on the row's *whole* text and the row stays. Dropping it would
        delete three labels the page prints.

        **The Title is the copy, and it goes** — 2026-09-26. The page prints
        `AVAILABILITY` once, as the first card's label; ours printed it as a
        caption and again as the heading row's first cell. The row is the
        reading that keeps its place in a grid of four, so the lifted copy is
        the one dropped. Measured on `tests/frozen/a3-result/`: this is the
        only one of 47 titled Zones the rule touches.
        """
        zone = contents_into(
            Zone(kind=Kind.TABLE, title="AVAILABILITY"),
            '{"rows": [{"role": "header", "cells": ["AVAILABILITY",'
            ' "P95 LATENCY", "INGEST VOLUME", "COST PER MILLION"]},'
            ' {"role": "data", "cells": ["99.97%", "184 ms", "4.8 bn", "$2.14"]}]}',
            read=a_reading,
        )

        assert len(zone.rows) == 2
        assert [c.text for c in zone.rows[0].cells] == [
            "AVAILABILITY", "P95 LATENCY", "INGEST VOLUME", "COST PER MILLION"]
        assert zone.title is None

    def test_a_data_row_starting_with_the_title_keeps_both(self) -> None:
        """Only a *header* row's first cell is the Title's lifted copy. A data
        row may name its own section — `menu_0012`'s section headings are rows
        — and a caption over it is a separate printed line."""
        zone = contents_into(
            Zone(kind=Kind.TABLE, title="Mains"),
            '{"rows": [{"role": "data", "cells": ["Mains", "12.00"]},'
            ' {"role": "data", "cells": ["Pie", "9.00"]}]}',
            read=a_reading,
        )

        assert zone.title == "Mains"
        assert len(zone.rows) == 2

    def test_through_a_conversion_the_lifted_copy_goes(self) -> None:
        """The rule runs where the pipeline binds contents to a titled Zone,
        which a rule measured on IRs offline does not prove.

        `sample_table_0003` replayed, with the caption pass answering the
        table's first heading, `Country`, instead of its caption — which is
        `darkdeck_0009`'s shape. The grid veto does not fire here (one column
        of ink in the first line against five below), so the Title reaches
        extraction, exactly as `AVAILABILITY` did."""
        replies = recorded_for("sample_table_0003")
        replies["caption"] = [text('{"first_line": "Country",'
                                   ' "line_is": "caption"}')]
        conversion = Conversion(source=REPO / "example" / "sample-table.png",
                                engines=engines_replaying(ReplayTransport(replies),
                                                          geometry("sample_table_0003")))
        document = conversion.run()

        table = next(z for z in document.zones if z.kind is Kind.TABLE)
        assert table.title is None
        assert table.rows[0].cells[0].text == "Country"

    def test_a_pair_repeating_the_title_is_dropped(self) -> None:
        zone = contents_into(
            Zone(kind=Kind.PAIRS, title="Comments / Notes"),
            '{"pairs": [{"label": "Comments / Notes", "value": ""},'
            ' {"label": "Terms", "value": "30 days"}]}',
            read=a_reading,
        )

        assert [(p.label.text, p.value.text) for p in zone.pairs] == [
            ("Terms", "30 days")
        ]

    def test_a_pair_whose_label_repeats_the_title_keeps_its_value(self) -> None:
        """Spec 0010, step A2 — `darkdeck_0009`'s cost tile. The caption pass
        took `COST PER MILLION` for the Title and the pairs reading bound it to
        `$2.14`; dropping the pair took the only print of `$2.14` with it."""
        zone = contents_into(
            Zone(kind=Kind.PAIRS, title="COST PER MILLION"),
            '{"pairs": [{"label": "COST PER MILLION", "value": "$2.14"},'
            ' {"label": "+9%", "value": ""}]}',
            read=a_reading,
        )

        assert [(p.label.text, p.value.text) for p in zone.pairs] == [
            ("", "$2.14"), ("+9%", "")
        ]
        html = render(Document(source=Source(path="x", sha256="0" * 64,
                                             width=100, height=100),
                               zones=[zone]))
        assert '<dt class="alone">$2.14</dt>' in html
        assert html.count("COST PER MILLION") == 2  # the h2, and the embedded IR

    def test_a_pair_that_is_the_title_split_in_two_is_dropped(self) -> None:
        zone = contents_into(
            Zone(kind=Kind.PAIRS, title="Payment Method"),
            '{"pairs": [{"label": "Payment", "value": "Method"},'
            ' {"label": "Check #", "value": "1000"}]}',
            read=a_reading,
        )

        assert [(p.label.text, p.value.text) for p in zone.pairs] == [
            ("Check #", "1000")
        ]

    def test_an_untitled_zone_is_untouched(self) -> None:
        zone = contents_into(
            Zone(kind=Kind.PROSE),
            '{"blocks": [{"kind": "heading", "lines": ["Deferred works"]},'
            ' {"kind": "paragraph", "lines": ["body"]}]}',
            read=a_reading,
        )

        assert len(zone.blocks) == 2

    def test_a_zone_whose_only_block_was_the_echo_keeps_its_title(self) -> None:
        """A titled section with nothing under it is a real thing on a page, and
        `contents_into` already allows it. Emptying the body here must not turn
        that into a failure after the fact."""
        zone = contents_into(
            self.zone(),
            '{"blocks": [{"kind": "heading", "lines": ["Deferred works"]}]}',
            read=a_reading,
        )

        assert zone.blocks == []
        assert zone.title == "Deferred works"
        assert zone.complete
