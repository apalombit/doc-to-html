"""The two documents that are not invoices: a card layout and an article.

Between them they cover every Kind the invoices do not — a real bulleted list, a
navigation row that is a list by structure and a row by appearance, a quotation
with its attribution, a badge whose text is content and a logo whose wordmark is
not, and decoration that must produce nothing at all.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from doc_to_html.ir import BBox, Document, Kind, Reading, Role, Zone
from doc_to_html.preprocess import Rectified, figure_pixels
from doc_to_html.render import render
from doc_to_html.wire import FigureResponse, contents_into, schema_of

from .replay import convert_replaying, recorded_for

REPO = Path(__file__).resolve().parent.parent
CARDS = REPO / "example" / "sample-css.png"
ARTICLE = REPO / "example" / "sample-semantic.png"
INVOICE2 = REPO / "example" / "invoice2.png"


def converted(image: Path, fixture: str) -> Document:
    return convert_replaying(image, recorded_for(fixture))


def zones_of(html: str) -> str:
    """The rendered Zones, with the findings blocks cut out."""
    return re.sub(r'<div class="findings.*?</div>', "", html, flags=re.S)


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
        # Counted inside the Zones only. The findings block renders a `<ul>` of
        # its own, so a page-wide count measures the audit as well as the lists.
        assert zones_of(html).count("<ul>") == 2

    def test_a_navigation_row_is_a_list_by_structure(self, article: Document) -> None:
        """Structure decides the IR; the header Role is what makes it render as a
        row. Modelling it as prose would lose that it is a set of peers.

        It shares a Zone with the masthead `<h1>` that names it, which is the
        `<header>` read the way a card and a panel are read — so the heading is
        this Zone's Title and the four links are its whole content."""
        nav = article.zones[0]
        assert nav.kind is Kind.LIST
        assert nav.role is Role.HEADER
        assert nav.title == "The Weekly Digest"
        assert len(nav.blocks) == 4
        assert all(block.kind == "item" for block in nav.blocks)

    def test_a_list_zone_keeps_its_title(self, article: Document) -> None:
        assert re.search(r'<h2 class="zone-title"[^>]*>Benefits</h2>',
                         render(article))

    def test_a_list_that_comes_back_as_paragraphs_renders_nothing(self) -> None:
        """The renderer only lists `item` blocks, so this is worth knowing: a
        LIST Zone whose blocks are paragraphs is a mis-read, not a styling
        problem."""
        zone = fill(Kind.LIST, '{"blocks": [{"kind": "paragraph", "lines": ["a"]}]}')
        assert zone.complete
        assert "<ul></ul>" in render(Document(source=_source(), zones=[zone]))

    def test_a_list_classified_as_prose_still_renders_as_a_list(self) -> None:
        """`prose` and `list` are not disjoint — `PROSE_PROMPT` offers `item` as
        a block kind — so the Kind must not be what decides the reader gets a
        list. Before this, the same blocks rendered as paragraphs under one Kind
        and list items under the other, with nothing recorded to say so."""
        zone = fill(
            Kind.PROSE,
            '{"blocks": [{"kind": "item", "lines": ["one"]},'
            ' {"kind": "item", "lines": ["two"]}]}',
        )
        html = render(Document(source=_source(), zones=[zone]))
        assert "<ul><li>one</li><li>two</li></ul>" in html
        assert "<p>one</p>" not in html

    def test_prose_around_a_list_keeps_its_paragraphs(self) -> None:
        """Only consecutive items group. A paragraph between two bullets ends
        the list on the page, and closing the `<ul>` is what says so."""
        zone = fill(
            Kind.PROSE,
            '{"blocks": [{"kind": "heading", "lines": ["Title"]},'
            ' {"kind": "item", "lines": ["one"]},'
            ' {"kind": "paragraph", "lines": ["aside"]},'
            ' {"kind": "item", "lines": ["two"]}]}',
        )
        html = render(Document(source=_source(), zones=[zone]))
        assert "<h1>Title</h1><ul><li>one</li></ul>" in html
        assert "<p>aside</p><ul><li>two</li></ul>" in html


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

    def test_a_logo_is_drawn_from_its_own_pixels(self) -> None:
        """End to end through a Conversion, which is the only test that proves
        the step is armed: `Zone.title_fill` shipped, passed offline, and was
        never once set in a conversion because of where its stage sat.

        The ACME logo's lettering is drawn as part of the artwork. Capturing it
        would be reconstructing a picture as text; drawing it is the picture."""
        invoice2 = converted(INVOICE2, "invoice_0002")
        logo = invoice2.zones[1]
        assert logo.graphic_kind == "logo"
        assert logo.blocks == []
        assert base64.b64decode(logo.pixels or "")[:8] == b"\x89PNG\r\n\x1a\n"
        assert [z.pixels for z in invoice2.zones if z is not logo] == (
            [None] * (len(invoice2.zones) - 1))

        html = render(invoice2)
        assert f'<img src="data:image/png;base64,{logo.pixels}" alt="logo"' in html
        assert 'class="omitted"' not in zones_of(html)
        assert "data-bbox=" in html

    def test_what_was_read_off_a_graphic_is_alt_text_and_not_printed(
            self) -> None:
        """`sparksuite` was `invoice_0001`'s only invented word: the page shows
        its wordmark as pixels, so printing the reading of it put a word on the
        page that the page does not have as text."""
        zone = fill(Kind.FIGURE, '{"graphic": "logo", "text": ["SPARKSUITE"]}')
        zone.pixels = _PNG
        html = zones_of(render(Document(source=_source(), zones=[zone])))

        assert 'alt="SPARKSUITE"' in html
        assert ">SPARKSUITE<" not in html
        assert "<figcaption>" not in html

    def test_a_drawn_figure_changes_nothing_outside_itself(self) -> None:
        """The figure's styling sits on its own elements. Put in `STYLESHEET` it
        changed the bytes of all fifteen corpus renders to draw two of them."""
        zone = fill(Kind.FIGURE, '{"graphic": "logo", "text": []}')
        without = render(Document(source=_source(), zones=[zone]))
        zone.pixels = _PNG
        drawn = render(Document(source=_source(), zones=[zone]))

        def style(page: str) -> str:
            return re.search(r"<style>.*?</style>", page, re.S).group(0)  # type: ignore[union-attr]

        assert style(drawn) == style(without)

    def test_a_mark_with_pixels_still_prints_its_text(self) -> None:
        """A badge's text is content, so it is printed whatever else the Zone
        carries."""
        zone = fill(Kind.FIGURE, '{"graphic": "badge", "text": ["CSS"]}')
        zone.pixels = _PNG
        html = render(Document(source=_source(), zones=[zone]))
        assert '<div class="mark" data-kind="badge">CSS</div>' in html
        assert "<img" not in html

    def test_the_pixels_survive_the_round_trip_through_json(self) -> None:
        """Every offline loop reads the IR back out of a rendered file, so a
        field the decoder forgets is a figure the next re-render loses."""
        zone = fill(Kind.FIGURE, '{"graphic": "logo", "text": []}')
        zone.pixels = _PNG
        document = Document(source=_source(), zones=[zone])  # type: ignore[arg-type]
        assert Document.from_json(document.to_json()).zones[0].pixels == _PNG

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


def _boxed_sections(html: str) -> list[str]:
    """The `<section>` tags carrying the boxed class, and nothing else.

    Three other things in a render contain the word: the stylesheet's
    `section.boxed` rule, the embedded IR's `"boxed"` key, and any Zone Role
    that happens to share a substring. Matching the tag is the only test that
    means what it says.
    """
    return re.findall(r'<section class="[^"]*\bboxed\b[^"]*"', html)


class TestCards:
    def test_both_cards_keep_their_captions(self, cards: Document) -> None:
        """The caption binding is the thing under test, not the panel.

        This used to also assert the `titled` class that made every captioned
        Zone a bordered panel; chrome is now measured per Zone rather than
        implied by having a Title. See `render._zone`.
        """
        html = render(cards)
        assert html.count('class="zone-title"') == 2
        for title in ("Card heading", "Another card"):
            assert re.search(f'<h2 class="zone-title"[^>]*>{re.escape(title)}</h2>',
                             html)

    def test_only_the_zones_the_page_cards_come_back_boxed(
            self, cards: Document) -> None:
        """End to end through a real Conversion, and the border finder's only
        test that runs one.

        `sample_css_0004` draws exactly two `.card` rectangles. The heading,
        the badge figure and the intro prose sit on bare paper. Before the
        finder this was 0 of 5, because the box each Zone is measured in has
        been snapped onto its content ink and `preprocess.content_ink` deletes
        panel borders from that mask by name.
        """
        boxed = [zone for zone in cards.zones if zone.boxed]

        assert [zone.title for zone in boxed] == ["Card heading", "Another card"]
        assert all(zone.fill == (246, 248, 250) for zone in boxed)
        assert len(_boxed_sections(render(cards))) == 2

    def test_a_page_that_draws_no_card_gets_none(self, article: Document) -> None:
        """The fault this replaces went the other way: `section.titled` drew a
        bordered panel round every captioned Zone, on roughly ten of fifteen
        documents whose sources draw nothing of the kind."""
        assert not any(zone.boxed for zone in article.zones)
        assert not _boxed_sections(render(article))

    def test_an_unmeasured_zone_is_never_drawn_as_a_card(
            self, cards: Document) -> None:
        """A Zone nothing measured and a Zone measured as plain must render
        identically — an unmeasured default is how chrome nobody asked for
        gets reintroduced."""
        for zone in cards.zones:
            zone.boxed, zone.fill, zone.title_fill = False, None, None

        assert not _boxed_sections(render(cards))


_PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"a stand-in; nothing here decodes it").decode("ascii")


def _source() -> object:
    from doc_to_html.ir import Source

    return Source(path="synthetic", sha256="0" * 64, width=100, height=100)


class TestAFiguresPixels:
    """What `preprocess.figure_pixels` cuts, and from which of the two arrays.

    A 100x100 page with a 20x20 block at (40, 40) and a neighbour's ink one
    pixel to its right, which is where `invoice_0002`'s address sits beside
    the ACME tile.
    """

    BOX = BBox(0.40, 0.40, 0.60, 0.60)

    def rectified(self, *, inverted: bool = False) -> Rectified:
        plain = np.full((100, 100, 3), 255, dtype=np.uint8)
        plain[40:60, 40:60] = (200, 30, 30)
        plain[40:60, 61:70] = 0
        image = np.full_like(plain, 128)  # what the readers see; never drawn
        return Rectified(image=image, plain=plain, inverted=inverted,
                         source=_source())  # type: ignore[arg-type]

    def decoded(self, pixels: str | None) -> np.ndarray:
        assert pixels is not None
        return cv2.imdecode(np.frombuffer(base64.b64decode(pixels), np.uint8),
                            cv2.IMREAD_COLOR)

    def test_it_is_the_box_with_no_padding(self) -> None:
        """`zone_pixels` pads for the reader's sake, and the pad is where the
        neighbour is: padded, the ACME tile carried `Acm`, `Soft`, `Field`."""
        drawn = self.decoded(figure_pixels(self.rectified(),
                                           Zone(kind=Kind.FIGURE, bbox=self.BOX)))
        assert drawn.shape == (20, 20, 3)
        assert (drawn == (200, 30, 30)).all()

    def test_it_is_cut_from_the_plain_image(self) -> None:
        """Equalised pixels are for reading; drawn, they would be the wrong
        colour."""
        drawn = self.decoded(figure_pixels(self.rectified(),
                                           Zone(kind=Kind.FIGURE, bbox=self.BOX)))
        assert not (drawn == 128).all()

    def test_a_page_turned_over_for_reading_is_turned_back(self) -> None:
        rectified = self.rectified(inverted=True)
        assert rectified.plain is not None
        drawn = self.decoded(figure_pixels(rectified,
                                           Zone(kind=Kind.FIGURE, bbox=self.BOX)))
        assert (drawn == (55, 225, 225)).all()

    def test_a_zone_with_no_box_has_no_pixels(self) -> None:
        assert figure_pixels(self.rectified(), Zone(kind=Kind.FIGURE)) is None
