"""The second invoice: dense Pairs, captioned panels, prose, and no arithmetic.

Everything the first invoice exercises, this document deliberately does not. What
it covers instead is Titles bound to the block they caption, two panels of
label/value lines, a section that is legitimately empty, and a document that must
attract no Probe at all.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

import numpy as np

from doc_to_html.ir import BBox, Document, Kind, Reading, Role, Source, Zone
from doc_to_html.orchestrator import Conversion, EngineSet
from doc_to_html.preprocess import Rectified
from doc_to_html.render import render
from doc_to_html.wire import MappingError, contents_into

from .replay import break_zone, convert_replaying, recorded_for, text

REPO = Path(__file__).resolve().parent.parent
INVOICE2 = REPO / "example" / "invoice2.png"

PAGE_HEIGHT, PAGE_WIDTH = 600, 800


def source() -> Source:
    return Source(path="unused.png", sha256="0" * 64,
                  width=PAGE_WIDTH, height=PAGE_HEIGHT)


def rectified_page() -> Rectified:
    page = np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), 245, dtype=np.uint8)
    return Rectified(image=page, source=source())

@pytest.fixture
def invoice2() -> Document:
    return convert_replaying(INVOICE2, recorded_for("invoice_0002"))


def fill(kind: Kind, payload: str, *, title: str | None = None) -> Zone:
    zone = Zone(kind=kind, title=title)
    return contents_into(zone, payload, read=lambda t: Reading(engine="test", text=t))


class TestTitledPanels:
    def test_both_panels_come_back_populated(self, invoice2: Document) -> None:
        panels = [z for z in invoice2.zones
                  if z.kind is Kind.PAIRS and z.title and z.role is Role.BODY]
        assert [z.title for z in panels] == ["Company Details", "Customer Details"]
        assert [len(z.pairs) for z in panels] == [7, 6]
        assert sum(len(z.pairs) for z in panels) == 13

    def test_a_title_stays_bound_to_the_block_it_captions(
        self, invoice2: Document
    ) -> None:
        """The two panels sit in one Band at different heights. A caption modelled
        as its own Zone renders correctly only while neighbours are the same
        height; binding it to the block holds regardless."""
        html = render(invoice2)
        for title in ("Company Details", "Customer Details"):
            # Matched loosely on purpose. The Title's own tag now carries
            # whatever chrome was *measured* for that Zone — this page really
            # does draw grey caption bars, and the detector finds them — so an
            # exact-string split would be asserting the colour rather than the
            # binding, which is what this test is about.
            panel = re.split(rf"<h2[^>]*>{re.escape(title)}</h2>", html)[1]
            assert panel.startswith('<div class="zone-body"><dl class="pairs">')

        band = [z for z in invoice2.zones if z.band == 1]
        assert [z.column for z in band] == [0, 1]

    def test_pairs_render_as_a_description_list(self, invoice2: Document) -> None:
        html = render(invoice2)
        assert "<dt>Industry</dt>" in html
        assert "<dd>Software Development</dd>" in html
        assert "<dd>One Microsoft Way Redmond, WA 98052-7329, USA</dd>" in html

    def test_the_trap_bank_account_survives_unchanged(
        self, invoice2: Document
    ) -> None:
        """MO123456789456123 begins with a letter O, not a zero, and there is no
        arithmetic anywhere to catch a misreading. Nothing in the pipeline may
        normalise it."""
        assert "MO123456789456123" in render(invoice2)


class TestASectionThatIsLegitimatelyEmpty:
    def test_an_empty_titled_section_is_a_success(self, invoice2: Document) -> None:
        """"Services / Products" has a heading and nothing under it. That is what
        the page says, and reporting it as a failed extraction would put a finding
        in front of an operator with nothing to fix."""
        empty = invoice2.zones[5]
        assert empty.title == "Services / Products"
        assert empty.complete and not empty.blocks
        assert 5 not in [f.zone_index for f in invoice2.failures]

    def test_it_renders_as_a_titled_zone_with_nothing_in_it(
        self, invoice2: Document
    ) -> None:
        html = render(invoice2)
        assert '<h2 class="zone-title">Services / Products</h2>' in html
        assert 'class="skeleton"' not in html

    def test_an_untitled_zone_that_comes_back_empty_is_a_failure(self) -> None:
        """Without a Title there is nothing on the page to explain the emptiness,
        so the layout pass and the extraction pass disagree — and a silently
        empty Zone looks exactly like a region that held nothing."""
        with pytest.raises(MappingError, match="no text"):
            fill(Kind.PROSE, '{"blocks": []}')
        assert fill(Kind.PROSE, '{"blocks": []}', title="Notes").complete


class TestProseKeepsItsShape:
    def test_a_multi_line_address_stays_multi_line(self, invoice2: Document) -> None:
        address = invoice2.zones[2]
        assert [line.text for line in address.blocks[0].lines] == [
            "Acme Corporation", "Software Development", "Field 3, Moon",
            "info@acme.com",
        ]
        assert "Acme Corporation<br>Software Development" in render(invoice2)

    def test_a_long_paragraph_survives_intact(self, invoice2: Document) -> None:
        """Truncation and summarisation are the two ways a reader silently loses
        text, and neither leaves a trace in the output."""
        comments = invoice2.zones[6]
        text_out = comments.blocks[0].lines[0].text
        assert len(text_out) > 70
        assert text_out in render(invoice2)

    def test_the_document_title_renders_bound_to_its_own_numbers(
        self, invoice2: Document
    ) -> None:
        """`Invoice With Credit` used to be a `heading` Block in a Zone of its
        own, rendering `<h1>` a Band above the NO/Date line it names. It is that
        Zone's Title now, so it renders at the level a Title renders at and the
        numbers sit under it — which is what the page shows."""
        html = render(invoice2)
        assert '<h2 class="zone-title">Invoice With Credit</h2>' in html
        assert "<h1>" not in html

    def test_the_footer_role_is_preserved(self, invoice2: Document) -> None:
        html = render(invoice2)
        assert 'class="zone zone-footer"' in html


class TestNoArithmeticMeansNoProbe:
    def test_the_document_attracts_no_probe_results(
        self, invoice2: Document
    ) -> None:
        """Zero Probe coverage is a valid outcome, not a failure to report."""
        assert invoice2.probes == []

    def test_and_therefore_no_findings(self, invoice2: Document) -> None:
        assert "did not reconcile" not in render(invoice2)


class TestMappingPairs:
    def test_two_pairs_on_one_line_stay_two_pairs(self) -> None:
        """A line reading "Invoice No: 12    Date: 1 Jan" is two bindings. Merged
        into one, the second label becomes part of the first value."""
        zone = fill(
            Kind.PAIRS,
            '{"pairs": [{"label": "Invoice No", "value": "12"},'
            ' {"label": "Date", "value": "1 Jan"}]}',
        )
        assert [(p.label.text, p.value.text) for p in zone.pairs] == [
            ("Invoice No", "12"), ("Date", "1 Jan")
        ]

    def test_a_label_with_no_value_is_kept(self) -> None:
        """A printed label with nothing against it is what the page says."""
        zone = fill(Kind.PAIRS, '{"pairs": [{"label": "Notes", "value": ""}]}')
        assert (zone.pairs[0].label.text, zone.pairs[0].value.text) == ("Notes", "")

    def test_a_value_with_no_label_is_not_a_pair(self) -> None:
        """A Pair is a label bound to a value. An unlabelled value means the
        region was not Pairs, which is a finding rather than something to coerce."""
        with pytest.raises(MappingError, match="no label"):
            fill(Kind.PAIRS, '{"pairs": [{"label": "", "value": "12"}]}')

    def test_an_entirely_blank_pair_is_dropped(self) -> None:
        zone = fill(
            Kind.PAIRS,
            '{"pairs": [{"label": "A", "value": "1"}, {"label": " ", "value": ""}]}',
        )
        assert len(zone.pairs) == 1


class TestMappingProse:
    def test_blank_lines_are_dropped_but_a_block_of_them_is_a_failure(self) -> None:
        zone = fill(
            Kind.PROSE,
            '{"blocks": [{"kind": "paragraph", "lines": ["real", "", "  "]}]}',
        )
        assert [line.text for line in zone.blocks[0].lines] == ["real"]

        with pytest.raises(MappingError, match="no text"):
            fill(Kind.PROSE, '{"blocks": [{"kind": "paragraph", "lines": ["", " "]}]}')

    def test_every_line_records_what_read_it(self, invoice2: Document) -> None:
        reading = invoice2.zones[2].blocks[0].lines[0].readings[0]
        assert reading.engine == "ollama"
        assert reading.model and reading.prompt_version


class TestThePromptSaysWhatTheMappingCannotEnforce:
    def test_pairs_are_told_not_to_merge_a_shared_line(self) -> None:
        from doc_to_html.engines.ollama import PAIRS_PROMPT

        assert "side by side" in PAIRS_PROMPT
        assert "two pairs and not one" in PAIRS_PROMPT

    def test_prose_is_told_not_to_summarise(self) -> None:
        from doc_to_html.engines.ollama import PROSE_PROMPT

        assert "summarise" in PROSE_PROMPT
        assert "empty list" in PROSE_PROMPT

    def test_the_kind_definitions_are_frozen_pending_a_split_of_the_pass(
        self,
    ) -> None:
        """Editing this block breaks Band numbering, measured three times.

        Three attempts, each aimed only at which Kind a Zone gets, each of which
        left the layout unmappable for a reason in a different part of the
        answer:

        - run 11 added "the heading row names the columns" — the Kind was fixed,
          Zone 4 came back `table`, and the model returned each table once per
          column at byte-identical boxes.
        - run 12 said the same thing without the word "columns" — all seven
          Zones landed in band 0 and both tables merged into one box.
        - run 16 added five words to `prose` alone, one line, no growth — four
          Zones in band 0, column order [0, 1, 2, 3] against lefts 0.05, 0.75,
          0.05, 0.75. **Run 17 repeated it verbatim and reproduced the failure
          exactly**, at 475.3s against 220.0s, which also rules out the
          CPU-offload confound: offload costs latency, not correctness.

        Seven runs separate cleanly: 11, 12, 16 and 17 touched this block and
        all four were rejected; 13, 14 and 15 did not and all three mapped. The
        variable is not how *long* these definitions are — run 16 grew nothing.

        Be exact about what that supports. Run 16's wording is repeated, so
        "this edit breaks Band numbering" is established. "*Any* edit does" is a
        generalisation from three wordings, and 0001 already withdrew a claim of
        that class. It is the working hypothesis, not a finding.

        So this is a tripwire, not a style rule: it exists to make the next edit
        here a deliberate act that reads this docstring first. Deleting it as
        part of separating classification from geometry is the expected way for
        it to go. See docs/specs/0002-structure-not-geometry.md.
        """
        from doc_to_html.engines.ollama import LAYOUT_PROMPT

        block = LAYOUT_PROMPT.split("kind — one of:")[1].split("role — one of:")[0]
        assert " ".join(block.split()) == (
            "table a grid of rows and columns under a heading row. Two grids "
            "stacked one above the other are two regions, not one, whenever "
            "each has its own heading row — even if their columns line up and "
            "only a small gap separates them. A grid with a heading row is a "
            "table even if only one row of values follows it "
            "pairs label and value lines with no heading row, such as "
            '"Invoice No: 12" '
            "prose headings, paragraphs, addresses, free text "
            "list bulleted or numbered items, or a row of navigation links "
            "figure a logo, chart, stamp, signature or badge"
        )


class TestAFailureStillDoesNotSpread:
    def test_one_bad_panel_does_not_cost_the_other(self) -> None:
        """An empty answer rather than an unlabelled value, on purpose.

        An unlabelled value is no longer a plain Failure — it is the Pairs
        Extractor diagnosing the Kind, and the Orchestrator re-reads the Zone as
        prose on the strength of it (`TestAnUnlabelledValueIsADiagnosis`). What
        this test is for is the other contract, that a Zone which genuinely
        cannot be read does not cost its neighbours, so it needs a failure with
        no diagnosis attached. An empty answer for an untitled Zone is one.
        """
        replies = break_zone(recorded_for("invoice_0002"), "invoice_0002",
                             2, '{"blocks": []}')
        document = convert_replaying(INVOICE2, replies)

        assert not document.zones[2].complete
        assert [len(document.zones[i].pairs) for i in (3, 4)] == [7, 6]
        assert [f.zone_index for f in document.failures] == [2]


class TestAnUnlabelledValueIsADiagnosis:
    """The Pairs Extractor says the region is not Pairs, and is believed.

    `invoice_0001`'s Zone 3 is `Acme Corp.` / `John Doe` / `john@example.com` —
    prose, classified `pairs` in every run ever taken. Asked for Pairs, the model
    binds the first two and returns the email with a blank label, which is a fact
    about the page rather than a bad read: nothing is printed to the left of it.

    Before this, `pairs_from_response` raised and the raise happened before any
    Pair reached the Zone, so all three lines were discarded — including the two
    that had bound correctly — and the Zone rendered as an empty skeleton. The
    payload below is run 45's answer for that Zone verbatim.
    """

    ZONE_3 = (
        '{"pairs": [{"label": "Acme Corp.", "value": "John Doe"},'
        ' {"label": "", "value": "john@example.com"}]}'
    )
    AS_PROSE = (
        '{"blocks": [{"kind": "address", "lines":'
        ' ["Acme Corp.", "John Doe", "john@example.com"]}]}'
    )

    class TwoAnswers:
        """An Engine that answers Pairs once and prose once, through real mapping.

        Goes through `contents_into` rather than returning a filled Zone, so the
        `NotPairs` this turns on is raised by the code that ships rather than by
        the test.
        """

        def __init__(self, pairs: str, prose: str) -> None:
            self.replies = {Kind.PAIRS: pairs, Kind.PROSE: prose}
            self.asked: list[Kind] = []

        def extract_zone(self, image: object, zone: Zone,
                         hint: str | None = None) -> Zone:
            self.asked.append(zone.kind)
            return contents_into(
                zone, self.replies[zone.kind],
                read=lambda t: Reading(engine="test", text=t),
            )

    def converted(self, pairs: str | None = None) -> tuple[Document, TwoAnswers]:
        engine = self.TwoAnswers(pairs or self.ZONE_3, self.AS_PROSE)
        document = Document(source=source())
        document.zones = [Zone(kind=Kind.PAIRS, role=Role.BODY, band=0, column=0,
                               bbox=BBox(0.1, 0.1, 0.9, 0.4))]
        conversion = Conversion(
            source=Path("unused.png"),
            engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                              extract=engine, audit=engine),
        )
        conversion.classification_ran = True
        conversion._extract(rectified_page(), document)
        return document, engine

    def test_the_zone_is_asked_again_as_prose(self) -> None:
        _, engine = self.converted()
        assert engine.asked == [Kind.PAIRS, Kind.PROSE]

    def test_every_line_reaches_the_document(self) -> None:
        """Including the two the Pairs answer had already bound correctly, which
        is what the raise used to throw away."""
        document, _ = self.converted()
        lines = [
            line.text for block in document.zones[0].blocks for line in block.lines
        ]
        assert lines == ["Acme Corp.", "John Doe", "john@example.com"]

    def test_the_kind_is_corrected_on_the_zone(self) -> None:
        """So the Document records what it converted, not what was guessed."""
        document, _ = self.converted()
        assert document.zones[0].kind is Kind.PROSE
        assert document.zones[0].complete

    def test_it_is_a_caveat_and_not_a_failure(self) -> None:
        """The Zone has its content. A Failure would put "could not be read"
        above the text that was read."""
        document, _ = self.converted()
        assert document.failures == []
        assert [c.zone_index for c in document.caveats] == [0]
        assert "re-read as prose" in document.caveats[0].note

    def test_a_prose_reread_that_also_fails_is_reported_once(self) -> None:
        """The re-read is one extra attempt, not an unbounded search."""
        engine = self.TwoAnswers(self.ZONE_3, '{"blocks": []}')
        document = Document(source=source())
        document.zones = [Zone(kind=Kind.PAIRS, role=Role.BODY, band=0, column=0,
                               bbox=BBox(0.1, 0.1, 0.9, 0.4))]
        conversion = Conversion(
            source=Path("unused.png"),
            engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                              extract=engine, audit=engine),
        )
        conversion.classification_ran = True
        conversion._extract(rectified_page(), document)

        assert [f.zone_index for f in document.failures] == [0]
        assert not document.zones[0].complete
