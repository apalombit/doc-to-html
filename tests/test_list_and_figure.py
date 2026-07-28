"""The two documents that are not invoices: a card layout and an article.

Between them they cover every Kind the invoices do not — a real bulleted list, a
navigation row that is a list by structure and a row by appearance, a quotation
with its attribution, a badge whose text is content and a logo whose wordmark is
not, and decoration that must produce nothing at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_to_html.ir import Document, Kind, Reading, Role, Zone
from doc_to_html.render import render
from doc_to_html.wire import FigureResponse, contents_into, schema_of

from .replay import convert_replaying, recorded_for

REPO = Path(__file__).resolve().parent.parent
CARDS = REPO / "example" / "sample-css.png"
ARTICLE = REPO / "example" / "sample-semantic.png"
INVOICE2 = REPO / "example" / "invoice2.png"


def converted(image: Path, fixture: str) -> Document:
    return convert_replaying(image, recorded_for(fixture))


def fill(kind: Kind, payload: str, **zone_args: object) -> Zone:
    zone = Zone(kind=kind, **zone_args)  # type: ignore[arg-type]
    return contents_into(zone, payload, read=lambda t: Reading(engine="test", text=t))


@pytest.fixture
def cards() -> Document:
    return converted(CARDS, "sample_css_0004")


@pytest.fixture
def article() -> Document:
    return converted(ARTICLE, "sample_semantic_0005")


class TestEverythingExtracts:
    def test_the_card_document_comes_back_whole(self, cards: Document) -> None:
        assert all(zone.complete for zone in cards.zones)
        assert cards.failures == []

    def test_the_article_comes_back_whole(self, article: Document) -> None:
        assert all(zone.complete for zone in article.zones)
        assert article.failures == []


class TestLists:
    def test_a_bulleted_list_becomes_a_real_list(self, article: Document) -> None:
        html = render(article)
        assert "<li>Search engines understand content hierarchy</li>" in html
        assert html.count("<ul>") == 2

    def test_a_navigation_row_is_a_list_by_structure(self, article: Document) -> None:
        """Structure decides the IR; the header Role is what makes it render as a
        row. Modelling it as prose would lose that it is a set of peers."""
        nav = article.zones[1]
        assert nav.kind is Kind.LIST
        assert nav.role is Role.HEADER
        assert len(nav.blocks) == 4
        assert all(block.kind == "item" for block in nav.blocks)

    def test_a_list_zone_keeps_its_title(self, article: Document) -> None:
        assert '<h2 class="zone-title">Benefits</h2>' in render(article)

    def test_a_list_that_comes_back_as_paragraphs_renders_nothing(self) -> None:
        """The renderer only lists `item` blocks, so this is worth knowing: a
        LIST Zone whose blocks are paragraphs is a mis-read, not a styling
        problem."""
        zone = fill(Kind.LIST, '{"blocks": [{"kind": "paragraph", "lines": ["a"]}]}')
        assert zone.complete
        assert "<ul></ul>" in render(Document(source=_source(), zones=[zone]))


class TestQuotations:
    def test_a_quotation_and_its_attribution_stay_distinct(
        self, article: Document
    ) -> None:
        html = render(article)
        assert "<blockquote>HTML provides for a number of elements" in html
        assert '<p class="attribution">— W3C HTML5.2 specification</p>' in html

    def test_the_callout_sits_beside_the_section_it_summarises(
        self, article: Document
    ) -> None:
        two_column = [band for band in article.bands() if len(band) == 2]
        assert len(two_column) == 1
        assert [zone.title for zone in two_column[0]] == ["Introduction", "TL;DR"]


class TestGraphicsAndMarks:
    def test_a_badge_keeps_its_text(self, cards: Document) -> None:
        """Unlike a logo's wordmark, a badge carries text a reader reads."""
        assert '<div class="mark" data-kind="badge">CSS</div>' in render(cards)

    def test_a_logo_holds_its_position_without_its_wordmark(self) -> None:
        """The ACME logo's lettering is drawn as part of the artwork. Capturing it
        would be reconstructing a picture as text."""
        invoice2 = converted(INVOICE2, "invoice_0002")
        logo = invoice2.zones[1]
        assert logo.graphic_kind == "logo"
        assert logo.blocks == []

        html = render(invoice2)
        assert '<figure class="omitted" data-kind="logo"' in html
        assert "data-bbox=" in html

    def test_a_mark_with_no_text_still_records_its_presence(self) -> None:
        """A signature is often illegible. That it is there is the finding."""
        zone = fill(Kind.FIGURE, '{"graphic": "signature", "text": []}')
        assert zone.graphic_kind == "signature"
        html = render(Document(source=_source(), zones=[zone]))
        assert 'data-kind="signature"' in html
        assert "signature</div>" in html

    def test_a_chart_keeps_its_words_and_none_of_its_data(self) -> None:
        zone = fill(
            Kind.FIGURE,
            '{"graphic": "chart", "text": ["Revenue by quarter", "Q1", "Q2"]}',
        )
        html = render(Document(source=_source(), zones=[zone]))
        assert "Revenue by quarter" in html
        assert '<figure class="omitted" data-kind="chart"' in html

    def test_no_schema_field_could_carry_a_chart_s_data(self) -> None:
        """The guarantee is structural rather than a prompt instruction: there is
        nowhere for a series of values to go, so nothing can put a guess in the
        output presented as a reading."""
        fields = set(schema_of(FigureResponse)["properties"])
        assert fields == {"graphic", "text"}


class TestDecorationProducesNothing:
    def test_the_rule_under_the_heading_is_not_a_zone(self, cards: Document) -> None:
        """A placeholder for a horizontal rule would add a box to the render
        carrying no information."""
        figures = [z for z in cards.zones if z.kind is Kind.FIGURE]
        assert [z.graphic_kind for z in figures] == ["badge"]

    def test_the_layout_pass_is_told_to_ignore_decoration(self) -> None:
        from doc_to_html.engines.ollama import LAYOUT_PROMPT

        flat = " ".join(LAYOUT_PROMPT.split())
        assert (
            "A horizontal rule, a panel border or a column divider is not a "
            "region and must not appear in the list."
        ) in flat


class TestTextThatCouldBreakThePage:
    def test_inline_code_in_angle_brackets_survives(self, cards: Document) -> None:
        html = render(cards)
        assert "inline &lt;style&gt; blocks" in html
        assert "in the &lt;head&gt; to customize" in html
        assert "<style>" in html  # the stylesheet's own tag, and only that

    def test_inline_code_in_the_article_survives(self, article: Document) -> None:
        assert "like &lt;article&gt;, &lt;section&gt;, and &lt;nav&gt;" in render(
            article
        )

    def test_link_text_renders_as_plain_text(self, article: Document) -> None:
        """An href is not in the pixels — a photograph contains blue underlined
        text and nothing more. Recording that something looked like a link would
        be recording styling."""
        html = render(article)
        assert "Jane Author" in html and "editor@example.com" in html
        assert "<a " not in html


class TestCards:
    def test_both_cards_are_captioned_panels(self, cards: Document) -> None:
        html = render(cards)
        assert html.count('class="zone-title"') == 2
        assert html.count('class="zone zone-body titled"') == 2
        for title in ("Card heading", "Another card"):
            assert f'<h2 class="zone-title">{title}</h2>' in html


def _source() -> object:
    from doc_to_html.ir import Source

    return Source(path="synthetic", sha256="0" * 64, width=100, height=100)
