"""Fixture 0002 — a document with no table and no arithmetic.

Everything fixture 0001 exercises, this one deliberately does not: no table, no
numbers, nothing for a Probe to check. What it covers instead is Titles, dense
Pairs, prose, an empty section, and a Graphic with no caption. The two fixtures
together are the acceptance set.
"""

from __future__ import annotations

import pytest

from doc_to_html import probes
from doc_to_html.ir import Document, Kind, Role
from doc_to_html.render import render

from .fixtures.invoice_0002 import build


@pytest.fixture
def invoice2() -> Document:
    return build()


class TestStructure:
    def test_band_layout(self, invoice2: Document) -> None:
        """Five Bands, not six. The `<h1>` and the NO/Date line beneath it are
        one Zone in Band 0 — the same reading every other titled region in this
        corpus gets — so the Band that held the numbers alone is gone."""
        bands = invoice2.bands()
        assert [len(band) for band in bands] == [3, 2, 1, 2, 1]

    def test_kinds_present(self, invoice2: Document) -> None:
        kinds = {zone.kind for zone in invoice2.zones}
        assert kinds == {Kind.PROSE, Kind.PAIRS, Kind.FIGURE}
        assert Kind.TABLE not in kinds

    def test_dense_pairs_are_captured(self, invoice2: Document) -> None:
        """The two boxed panels, which is what "dense" means here. Selected by
        Role as well as Kind, because the document title is now a titled Pairs
        Zone too — two Pairs on one line, in the header, which is a different
        thing from a seven-row panel."""
        panels = [z for z in invoice2.zones
                  if z.kind is Kind.PAIRS and z.title and z.role is Role.BODY]
        assert [len(z.pairs) for z in panels] == [7, 6]

    def test_footer_role_is_assigned(self, invoice2: Document) -> None:
        footers = [z for z in invoice2.zones if z.role is Role.FOOTER]
        assert len(footers) == 1


class TestProbes:
    def test_a_document_without_arithmetic_attracts_no_probes(
        self, invoice2: Document
    ) -> None:
        """Zero Probe coverage is a valid outcome, not a failure to report."""
        assert probes.run(invoice2) == []

    def test_no_findings_are_surfaced(self, invoice2: Document) -> None:
        invoice2.probes = probes.run(invoice2)
        assert "Unresolved" not in render(invoice2)


class TestTitles:
    def test_titles_render_bound_to_their_block(self, invoice2: Document) -> None:
        html = render(invoice2)
        for panel in ("Company Details", "Customer Details"):
            assert (
                f'<h2 class="zone-title">{panel}</h2>'
                '<div class="zone-body"><dl class="pairs">'
            ) in html

    def test_an_empty_section_keeps_its_title(self, invoice2: Document) -> None:
        """A heading with nothing under it is empty, not failed."""
        html = render(invoice2)
        assert '<h2 class="zone-title">Services / Products</h2>' in html

    def test_a_titled_zone_pending_extraction_keeps_its_title(
        self, invoice2: Document
    ) -> None:
        """A Draft should show what is being worked on, not an unlabelled box."""
        panel = next(z for z in invoice2.zones if z.title == "Company Details")
        panel.complete = False
        html = render(invoice2)
        assert (
            '<h2 class="zone-title">Company Details</h2>'
            '<div class="zone-body"><div class="skeleton">'
        ) in html


class TestContent:
    def test_the_ambiguous_account_number_is_letter_o(self, invoice2: Document) -> None:
        """MO not M0 — the glyphs are near-identical in the render.

        No Probe can catch a model reading this wrong, because there is no
        arithmetic to check it against. It is the case Escalation exists for.
        """
        html = render(invoice2)
        assert "MO123456789456123" in html
        assert "M0123456789456123" not in html

    def test_the_logo_is_placeholdered_without_transcribing_its_wordmark(
        self, invoice2: Document
    ) -> None:
        """A logo's wordmark is part of the Graphic, unlike a stamp's text."""
        logo = next(z for z in invoice2.zones if z.kind is Kind.FIGURE)
        assert logo.blocks == []
        assert 'data-kind="logo"' in render(invoice2)

    def test_long_prose_survives_intact(self, invoice2: Document) -> None:
        html = render(invoice2)
        assert "Lorem ipsum dolor sit amet" in html
        assert "nobis iure amet vero." in html


class TestRoundTrip:
    def test_title_survives_json(self, invoice2: Document) -> None:
        restored = Document.from_json(invoice2.to_json())
        assert restored.to_json() == invoice2.to_json()
        assert any(z.title == "Payment Method" for z in restored.zones)
