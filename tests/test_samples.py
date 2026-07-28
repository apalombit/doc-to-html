"""Fixtures 0003-0005 — documents that are not invoices.

Each of these earns its place by covering something the invoice fixtures cannot:
a large table with nothing to reconcile, captioned cards, and an article with a
list, a quotation and a navigation bar.
"""

from __future__ import annotations

import pytest

from doc_to_html import probes
from doc_to_html.ir import Document, Kind, Role, RowRole
from doc_to_html.probes import parse_number
from doc_to_html.render import render

from .fixtures.sample_css_0004 import build as build_css
from .fixtures.sample_semantic_0005 import build as build_semantic
from .fixtures.sample_table_0003 import build as build_table


@pytest.fixture
def table_doc() -> Document:
    return build_table()


@pytest.fixture
def css_doc() -> Document:
    return build_css()


@pytest.fixture
def semantic_doc() -> Document:
    return build_semantic()


class TestLargeTable:
    def test_all_rows_are_captured(self, table_doc: Document) -> None:
        table = table_doc.zones[1]
        assert len([r for r in table.rows if r.role is RowRole.DATA]) == 15
        assert len([r for r in table.rows if r.role is RowRole.HEADER]) == 1

    def test_a_table_with_nothing_to_reconcile_attracts_no_probe(
        self, table_doc: Document
    ) -> None:
        """No summary row means no column-sum, not a failing column-sum."""
        assert probes.run(table_doc) == []

    def test_two_numeric_columns_produce_no_row_product(
        self, table_doc: Document
    ) -> None:
        """Population x GDP = nothing. Inventing a relationship here would be a
        false finding on entirely correct data."""
        assert not [r for r in probes.run(table_doc) if r.kind == "row-product"]

    @pytest.mark.parametrize(
        "text,expected",
        [("331,900,000", "331900000"), ("1,412,000,000", "1412000000"),
         ("19,485,394", "19485394"), ("1,293,490", "1293490")],
    )
    def test_thousands_separators_parse(self, text: str, expected: str) -> None:
        assert str(parse_number(text)) == expected

    def test_alignment_follows_content_not_position(
        self, table_doc: Document
    ) -> None:
        """ISO and Currency are text in columns 1 and 4; they must not be
        right-aligned just because they are not the first column."""
        html = render(table_doc)
        assert "<td>USA</td>" in html
        assert '<td class="num">331,900,000</td>' in html
        assert "<td>USD</td>" in html

    def test_a_table_zone_can_carry_a_title(self, table_doc: Document) -> None:
        html = render(table_doc)
        assert "Population and GDP (millions of USD)</h2>" in html


class TestCards:
    def test_card_headings_are_titles(self, css_doc: Document) -> None:
        html = render(css_doc)
        assert html.count('class="zone-title"') == 2
        assert html.count('class="zone zone-body titled"') == 2

    def test_a_badge_keeps_its_text(self, css_doc: Document) -> None:
        """Unlike a logo's wordmark, a badge carries text a reader reads."""
        html = render(css_doc)
        assert '<div class="mark" data-kind="badge">CSS</div>' in html

    def test_inline_code_survives_escaping(self, css_doc: Document) -> None:
        html = render(css_doc)
        assert "inline &lt;style&gt; blocks" in html
        assert "in the &lt;head&gt; to customize" in html

    def test_decorative_rules_produce_no_zone(self, css_doc: Document) -> None:
        """The rule under the heading is a Separator, not a Graphic."""
        figures = [z for z in css_doc.zones if z.kind is Kind.FIGURE]
        assert [z.graphic_kind for z in figures] == ["badge"]


class TestArticle:
    def test_list_renders_as_a_list(self, semantic_doc: Document) -> None:
        html = render(semantic_doc)
        assert "<li>Search engines understand content hierarchy</li>" in html

    def test_navigation_is_a_list_by_structure(self, semantic_doc: Document) -> None:
        """Structure decides the IR; the header Role decides it renders inline."""
        nav = semantic_doc.zones[1]
        assert nav.kind is Kind.LIST
        assert nav.role is Role.HEADER
        assert len(nav.blocks) == 4

    def test_quotation_and_attribution_are_distinct(
        self, semantic_doc: Document
    ) -> None:
        html = render(semantic_doc)
        assert "<blockquote>HTML provides for a number of elements" in html
        assert '<p class="attribution">— W3C HTML5.2 specification</p>' in html

    def test_the_callout_sits_beside_the_section_it_summarises(
        self, semantic_doc: Document
    ) -> None:
        bands = semantic_doc.bands()
        two_column = [band for band in bands if len(band) == 2]
        assert len(two_column) == 1
        assert [zone.title for zone in two_column[0]] == ["Introduction", "TL;DR"]

    def test_links_render_as_plain_text(self, semantic_doc: Document) -> None:
        """An href is not in the pixels. Recording that text merely *looked*
        like a link would be recording styling."""
        html = render(semantic_doc)
        assert "Jane Author" in html
        assert "editor@example.com" in html
        assert "<a " not in html

    def test_inline_code_in_prose_survives(self, semantic_doc: Document) -> None:
        assert "like &lt;article&gt;, &lt;section&gt;, and &lt;nav&gt;" in render(
            semantic_doc
        )


class TestAllFixturesRoundTrip:
    @pytest.mark.parametrize(
        "builder", [build_table, build_css, build_semantic], ids=["0003", "0004", "0005"]
    )
    def test_json_round_trip(self, builder) -> None:
        document = builder()
        assert Document.from_json(document.to_json()).to_json() == document.to_json()
