"""Spec 0012, G3a — what the page draws that is not type, found and drawn.

`furniture.find` on the corpus's own pictures, each claim one the spec makes
of a page; the ink measured over type only; `furnish.anchor` on small
documents, one rule per placement; and what `render` draws from it.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from doc_to_html import furnish, furniture
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import (BBox, Block, Document, Flow, Furniture, Kind, Mark,
                            Pair, Region, Role, Source, Style, Zone, cell)
from doc_to_html.looks import _titles
from doc_to_html.preprocess import rectify
from doc_to_html.render import render
from doc_to_html.style import measure

REPO = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def page(name: str) -> tuple[list[Furniture], int, int]:
    """A corpus page's furniture, and its rectified width and height."""
    rectified = rectify(REPO / SOURCES[name].png)
    plain = rectified.plain if rectified.plain is not None else rectified.image
    found = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    return found, plain.shape[1], plain.shape[0]


def rules(name: str, *, vertical: bool) -> list[Furniture]:
    return [f for f in page(name)[0] if f.kind == "rule" and f.vertical == vertical]


class TestTheFinderOnThePages:
    """Each record the spec names, measured as the page draws it."""

    def test_the_letterhead_rule_is_three_pixels_and_green(self) -> None:
        found, width, _ = page("letter_0016")
        (head,) = [f for f in rules("letter_0016", vertical=False) if f.bbox.top < 0.2]
        assert round(head.thickness * width) == 3
        assert np.abs(np.array(head.color) - (15, 92, 77)).sum() <= 30
        assert head.bbox.right - head.bbox.left >= 0.8

    def test_the_masthead_rule_is_double_and_the_columns_are_ruled(self) -> None:
        assert [f.style for f in rules("newsletter_0008", vertical=False)].count("double") == 1
        down = [f for f in rules("newsletter_0008", vertical=True)
                if f.bbox.bottom - f.bbox.top >= 0.5]
        assert [round((f.bbox.left + f.bbox.right) / 2, 2) for f in down] == [0.33, 0.67]

    def test_the_certificate_frame_is_a_double_frame_round_the_page(self) -> None:
        frames = [f for f in page("certificate_0021")[0] if f.kind == "frame"]
        assert any(f.style == "double" and (f.bbox.right - f.bbox.left)
                   * (f.bbox.bottom - f.bbox.top) >= 0.8 for f in frames)

    def test_pricings_three_cards_are_framed_teams_through_its_ribbon(self) -> None:
        # Spec 0013 step 3b: the `MOST POPULAR` pill is drawn over Team's
        # top edge, in the edge's own blue, cutting it in two.
        frames = sorted((f for f in page("pricing_0017")[0]
                         if f.kind == "frame" and f.bbox.bottom - f.bbox.top > 0.5),
                        key=lambda f: f.bbox.left)
        assert len(frames) == 3
        assert all(abs(f.bbox.left - left) <= 0.005
                   for f, left in zip(frames, (0.044, 0.353, 0.665)))
        team = frames[1]
        assert np.abs(np.array(team.color) - (75, 91, 220)).sum() <= 30
        assert round(team.bbox.top, 2) == 0.26

    def test_the_ticket_stub_is_parted_by_a_dashed_rule(self) -> None:
        (divider,) = rules("ticket_0020", vertical=True)
        assert divider.style == "dashed" and divider.period is not None

    def test_the_pictures_and_the_lunch_row_are_hatched_each_its_way(self) -> None:
        catalogue = [f for f in page("catalogue_0015")[0] if f.style == "hatched"]
        lunch = [f for f in page("timetable_0019")[0] if f.style == "hatched"]
        assert len(catalogue) == 9 and {f.angle for f in catalogue} == {135}
        assert lunch and {f.angle for f in lunch} == {45}

    def test_a_barcode_is_not_a_row_of_rules(self) -> None:
        assert rules("receipt_0010", vertical=True) == []

    def test_the_statement_tiles_each_have_a_side_bar(self) -> None:
        _, width, _ = page("statement_0006")
        bars = [f for f in rules("statement_0006", vertical=True)
                if round(f.thickness * width) == 3]
        assert len(bars) == 4


class TestTheInkIsTheTypes:
    """`style.measure(without=...)`: decoration outweighed the type on two
    pages, and every line was drawn in its colour."""

    @pytest.mark.parametrize("name", ["certificate_0021", "ticket_0020"])
    def test_masked_the_ink_is_dark(self, name: str) -> None:
        rectified = rectify(REPO / SOURCES[name].png)
        plain = rectified.plain if rectified.plain is not None else rectified.image
        found = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
        before = measure(plain, inverted=rectified.inverted, read=rectified.image)
        after = measure(plain, inverted=rectified.inverted, read=rectified.image,
                        without=furniture.mask(found, plain.shape))
        assert max(before.ink) - min(before.ink) >= 80  # gold, teal
        assert sum(after.ink) <= 150


def zone(text: str, box: BBox, *, title: str | None = None, band: int = 0,
         column: int = 0, kind: Kind = Kind.PROSE) -> Zone:
    placed = cell(text, bbox=BBox(box.left, box.bottom - 0.02, box.right - 0.1, box.bottom))
    return Zone(kind=kind, role=Role.BODY, band=band, column=column, bbox=box,
                title=title, blocks=[Block(kind="paragraph", lines=[placed])],
                complete=True)


def rule(left: float, top: float, right: float, bottom: float, **fields: object) -> Furniture:
    return Furniture(kind="rule", bbox=BBox(left, top, right, bottom),
                     thickness=fields.pop("thickness", 0.002),  # type: ignore[arg-type]
                     color=(20, 40, 60), **fields)  # type: ignore[arg-type]


def document(zones: list[Zone], items: list[Furniture], **fields: object) -> Document:
    doc = Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                 rectified_width=1000, rectified_height=1000),
                   style=Style(body_px=10.0), zones=zones, furniture=items,
                   **fields)  # type: ignore[arg-type]
    furniture.place(doc.furniture, doc.zones)
    return doc


class TestWhatDrawsEachRecord:
    """`furnish.anchor` — each record to the element whose border it is."""

    def test_a_rule_under_a_title_and_over_the_entries_is_the_titles(self) -> None:
        heading = zone("Senior engineer", BBox(0.1, 0.1, 0.5, 0.3), title="EXPERIENCE")
        under = rule(0.1, 0.15, 0.9, 0.152)  # runs on past the Zone, as cv_0013's
        assert furnish.anchor(document([heading], [under])).under_title == {0: under}

    def test_a_link_underline_inside_a_zone_is_not_drawn(self) -> None:
        text = zone("by Jane Author", BBox(0.1, 0.1, 0.5, 0.3))
        underline = rule(0.3, 0.29, 0.4, 0.291)
        anchors = furnish.anchor(document([text], [underline]))
        assert anchors.between == [] and anchors.bottoms == {} and anchors.blocks == {}

    def test_a_rule_between_two_zones_is_drawn_between_them(self) -> None:
        zones = [zone("one", BBox(0.1, 0.1, 0.9, 0.2)),
                 zone("two", BBox(0.1, 0.3, 0.9, 0.4), band=1)]
        between = rule(0.1, 0.25, 0.9, 0.252)
        assert furnish.anchor(document(zones, [between])).between == [between]

    def test_a_bar_beside_a_zone_is_its_side_and_beside_its_title_the_titles(self) -> None:
        tile = zone("2,418.50", BBox(0.12, 0.1, 0.3, 0.2))
        head = zone("Whitlock", BBox(0.12, 0.4, 0.9, 0.6), title="1. APPLICANT DETAILS",
                    band=1)
        whole = rule(0.1, 0.09, 0.103, 0.21)
        title = rule(0.12, 0.4, 0.124, 0.43)  # on the Zone's own left edge
        anchors = furnish.anchor(document([tile, head], [whole, title]))
        assert anchors.sides == {0: whole} and anchors.title_sides == {1: title}

    def test_a_rule_down_a_split_is_the_lanes(self) -> None:
        zones = [zone("left", BBox(0.05, 0.1, 0.45, 0.9)),
                 zone("right", BBox(0.55, 0.1, 0.95, 0.9), column=1)]
        down = rule(0.499, 0.1, 0.5, 0.9)
        region = Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.5,))
        anchors = furnish.anchor(document(zones, [down], regions=[region]))
        assert [(lane, item) for _, lane, item in anchors.lanes] == [(1, down)]

    def test_nothing_inside_a_figure_and_no_field_line_is_drawn(self) -> None:
        figure = Zone(kind=Kind.FIGURE, bbox=BBox(0.5, 0.5, 0.9, 0.9))
        axis = rule(0.5, 0.88, 0.9, 0.881)
        form = Zone(kind=Kind.PAIRS, bbox=BBox(0.1, 0.1, 0.45, 0.3), complete=True,
                    pairs=[Pair(label=cell("Name", bbox=BBox(0.1, 0.1, 0.2, 0.12)),
                                value=cell("Peter", bbox=BBox(0.1, 0.14, 0.3, 0.16)),
                                marks=[Mark(kind="line", bbox=BBox(0.1, 0.17, 0.45, 0.171))])])
        line = rule(0.1, 0.17, 0.45, 0.171)
        anchors = furnish.anchor(document([form, figure], [axis, line]))
        assert anchors == furnish.Anchors()

    def test_a_frame_round_the_zones_sharing_a_box_is_its_border(self) -> None:
        # Spec 0013 step 3b, `pricing_0017`'s Team card: the box its Zones
        # share takes in the ribbon over its top edge and its shadow, so it
        # is not the frame's box; the frame holds exactly those Zones.
        card = BBox(0.350, 0.249, 0.650, 0.899)
        zones = [zone("MOST POPULAR", BBox(0.45, 0.249, 0.55, 0.318)),
                 zone("£12", BBox(0.38, 0.34, 0.62, 0.50), band=1),
                 zone("Unlimited", BBox(0.38, 0.55, 0.60, 0.76), band=2)]
        for each in zones:
            each.frame = card
        frame = Furniture(kind="frame", bbox=BBox(0.353, 0.262, 0.647, 0.889),
                          thickness=0.002, color=(75, 91, 220))
        assert furnish.anchor(document(zones, [frame])).frames == {card: frame}

    def test_a_frame_round_the_page_is_the_pages(self) -> None:
        frame = Furniture(kind="frame", bbox=BBox(0.01, 0.01, 0.99, 0.99),
                          thickness=0.006, style="double", color=(138, 109, 47))
        anchors = furnish.anchor(document([zone("x", BBox(0.2, 0.2, 0.8, 0.8))], [frame]))
        assert anchors.page is frame


def body_of(html: str) -> str:
    return html[html.index('<div class="doc"'):html.index('id="doc-ir"')]


class TestTheRenderDrawsThem:
    """Each as the page draws it: width, style, colour, and where."""

    def test_the_page_frame_is_the_docs_border(self) -> None:
        frame = Furniture(kind="frame", bbox=BBox(0.01, 0.01, 0.99, 0.99),
                          thickness=0.006, style="double", color=(138, 109, 47))
        html = render(document([zone("x", BBox(0.2, 0.2, 0.8, 0.8))], [frame]))
        assert re.search(r'<div class="doc" style="border:6px double rgb\(138,109,47\);'
                         r'padding:\d+px', html)

    def test_a_frame_inside_the_page_frame_is_padded_to_once(self) -> None:
        # Spec 0013 step 2, `certificate_0021`: `.doc` padded from the page
        # frame to the Zones, and the inner frame padded from itself to them
        # again, left a third of the page for the text — drawn portrait.
        outer = Furniture(kind="frame", bbox=BBox(0.01, 0.01, 0.99, 0.99),
                          thickness=0.006, style="double", color=(138, 109, 47))
        inner = Furniture(kind="frame", bbox=BBox(0.03, 0.03, 0.97, 0.97),
                          thickness=0.001, color=(199, 173, 106))
        zones = [zone("Guild", BBox(0.2, 0.2, 0.8, 0.3)),
                 zone("Awarded", BBox(0.2, 0.6, 0.8, 0.8), band=1)]
        for each in zones:
            each.frame = inner.bbox   # as `rhythm.frames` gives it
        html = render(document(zones, [outer, inner], page_px=1000))
        assert '<div class="doc" style="border:6px double rgb(138,109,47);' \
               'padding:14px 14px 14px 14px"' in html
        assert ".doc { max-width:940px; }" in html
        assert re.search(r'class="frame" style="padding:\d+px 170px', html)

    def test_the_title_rule_is_its_border(self) -> None:
        heading = zone("Senior engineer", BBox(0.1, 0.1, 0.5, 0.3), title="EXPERIENCE")
        html = render(document([heading], [rule(0.1, 0.15, 0.9, 0.152)]))
        assert re.search(r'<h2 class="zone-title" style="border-bottom:2px solid '
                         r'rgb\(20,40,60\)[^"]*">EXPERIENCE', html)

    def test_the_column_rule_is_the_lanes_left_border(self) -> None:
        zones = [zone("left", BBox(0.05, 0.1, 0.45, 0.9)),
                 zone("right", BBox(0.55, 0.1, 0.95, 0.9), column=1)]
        region = Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.5,))
        html = render(document(zones, [rule(0.499, 0.1, 0.5, 0.9, thickness=0.001)],
                               regions=[region]))
        lanes = re.findall(r'class="lane" style="([^"]*)"', html)
        assert "border-left" not in lanes[0]
        assert "border-left:1px solid rgb(20,40,60);padding-left:50px" in lanes[1]

    def test_a_dashed_rule_keeps_its_period(self) -> None:
        zones = [zone("one", BBox(0.1, 0.1, 0.9, 0.2)),
                 zone("two", BBox(0.1, 0.3, 0.9, 0.4), band=1)]
        dashed = rule(0.1, 0.25, 0.9, 0.251, thickness=0.001, style="dashed",
                      period=0.005)
        html = body_of(render(document(zones, [dashed])))
        assert ("height:1px;background:repeating-linear-gradient(90deg,"
                "rgb(20,40,60) 0 2.5px,transparent 2.5px 5.0px)") in html

    def test_two_rules_on_one_line_are_drawn_side_by_side(self) -> None:
        zones = [zone("Awarded", BBox(0.1, 0.1, 0.9, 0.2)),
                 zone("Okonkwo", BBox(0.1, 0.3, 0.4, 0.4), band=1),
                 zone("Brandt", BBox(0.6, 0.3, 0.9, 0.4), band=1, column=1)]
        lines = [rule(0.1, 0.25, 0.4, 0.251), rule(0.6, 0.25, 0.9, 0.251)]
        html = body_of(render(document(zones, lines)))
        (row,) = re.findall(r'<div class="separator rules"[^>]*>(.*?)</div></div>', html)
        assert re.findall(r"width:([\d.]+)%", row) == ["37.50", "37.50"]
        assert re.findall(r"margin-left:([\d.]+)%", row) == ["0.00", "25.00"]

    def test_a_page_with_no_furniture_draws_no_rule(self) -> None:
        html = render(document([zone("x", BBox(0.2, 0.2, 0.8, 0.8))], []))
        assert "separator" not in html[:html.index('id="doc-ir"')]


class TestATitlesOwnColour:
    """`looks._titles`: `nonlatin_0014`'s Titles are blue over black type,
    and were drawn blue only while the page's ink was measured blue."""

    def test_the_first_line_over_the_entries_is_measured(self) -> None:
        rgb = np.full((200, 200, 3), 255, dtype=np.uint8)
        rgb[20:30, 20:120] = (28, 79, 124)    # the Title's line
        rgb[60:70, 20:150] = (28, 28, 28)     # the first entry
        titled = zone("entry", BBox(0.1, 0.1, 0.8, 0.35), title="ΟΡΟΙ")
        titled.blocks[0].lines[0].bbox = BBox(0.1, 0.3, 0.75, 0.35)
        doc = document([titled], [])
        _titles(rgb, doc, doc.style or Style())
        assert titled.title_color == (28, 79, 124)

    def test_it_is_drawn_where_it_differs_from_the_ink(self) -> None:
        titled = zone("entry", BBox(0.1, 0.1, 0.8, 0.35), title="ΟΡΟΙ")
        titled.title_color = (28, 79, 124)
        html = render(document([titled], []))
        assert re.search(r'<h2 class="zone-title" style="color:rgb\(28,79,124\)', html)


class TestTheConversionPlacesThemOnTheFinalZones:
    """`Conversion._place_furniture` runs after `_read_fields`, the last
    step that moves a Zone's box."""

    def test_every_rule_is_placed_against_the_zones_as_they_end(self) -> None:
        from .replay import convert_recording, recorded_for

        document_, _ = convert_recording(REPO / SOURCES["invoice_0001"].png,
                                         recorded_for("invoice_0001"))
        assert document_.furniture
        placed = [item.zone for item in document_.furniture]
        furniture.place(document_.furniture, document_.zones)
        assert placed == [item.zone for item in document_.furniture]
        assert any(zone is not None for zone in placed)


class TestInkAgainstItsLocalGround:
    """Spec 0018, A1 — `grounded`: a fill the page draws is ground, its type
    ink by its contrast with the fill, its blended edge not ink. `equalise`
    lifts a fill wider than its kernel and leaves a dark fringe round its
    letters and along its foot; on `ticket_0020` that fringe was recovered
    as a Zone and read `The`, twice."""

    TEAL = (11, 110, 138)

    def strip(self) -> tuple[np.ndarray, np.ndarray, list[Furniture]]:
        """A teal strip with a white letter on it, over white paper, a
        blended row at its foot; and an equalised copy with a dark fringe."""
        plain = np.full((120, 200, 3), 255, np.uint8)
        plain[:40, :] = self.TEAL[::-1]
        plain[40, :] = (180, 165, 100)  # a blend of teal and white, BGR
        plain[12:28, 30:38] = 255  # a white letter's stem
        read = np.full_like(plain, 255)
        read[34:41, :] = 120  # the fringe along its foot
        read[10:30, 28:40] = 150  # a halo round the letter
        read[12:28, 30:38] = 255
        plain[70:80, 30:120] = 0  # a line of type on the paper
        read[70:80, 30:120] = 0
        fill = Furniture(kind="fill", bbox=BBox(0.0, 0.0, 1.0, 40 / 120), color=self.TEAL)
        return plain, read, [fill]

    def test_the_fringe_is_not_ink_and_the_letter_is(self) -> None:
        plain, read, found = self.strip()
        out = furniture.grounded(read, plain, found)
        assert (out[34:42, :] == 255).all(), "the fringe and the blended foot"
        assert (out[12:28, 30:38] == 0).all(), "the white letter, by its contrast"
        assert (out[10:12, 28:40] == 255).all(), "the halo round it"
        assert (out[70:80, 30:120] == 0).all(), "type on the paper is untouched"

    def test_a_fill_a_zone_holds_whole_is_left_alone(self) -> None:
        """A logo's square, a table's header bar: the Zone's extent."""
        plain, read, found = self.strip()
        out = furniture.grounded(read, plain, found, held=[BBox(0.0, 0.0, 1.0, 0.5)])
        assert (out == read).all()

    def test_a_fill_with_no_type_is_a_mark(self) -> None:
        """`paper_0018`'s chart bars are content, not ground."""
        plain, read, found = self.strip()
        plain[12:28, 30:38] = self.TEAL[::-1]
        assert (furniture.grounded(read, plain, found) == read).all()

    def test_the_tickets_halo_is_no_longer_uncovered_ink(self) -> None:
        """With the baseline's five other Zones, the halo under the strip is
        the one patch of ink no box covers — until it is read against the
        strip."""
        from doc_to_html.orchestrator import recovered_zones
        result = rectify(REPO / "example" / "ticket.png")
        found = furniture.find(result.plain, inverted=result.inverted, read=result.image)
        boxes = [BBox(0.736, 0.0, 1.0, 1.0), BBox(0.0, 0.0, 0.18, 0.131),
                 BBox(0.561, 0.03, 0.711, 0.102), BBox(0.03, 0.151, 0.47, 0.937),
                 BBox(0.53, 0.32, 0.71, 0.937)]
        zones = [Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, band=0, column=i)
                 for i, box in enumerate(boxes)]
        assert len(recovered_zones(result.image, zones)) > len(zones)
        ink = furniture.grounded(result.image, result.plain, found,
                                 inverted=result.inverted, held=boxes)
        assert len(recovered_zones(ink, zones)) == len(zones)

    def sidebar(self, box: BBox) -> Document:
        """`cv_0013`'s sidebar: one drawn fill, a titled Zone standing on it."""
        zone = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, band=0, column=0,
                    title="CONTACT", fill=(40, 52, 70),
                    blocks=[Block(kind="paragraph", lines=[cell("ada@example.com")])])
        return Document(source=Source(path="p.png", sha256="0", width=800, height=1000),
                        zones=[zone],
                        furniture=[Furniture(kind="fill", bbox=BBox(0.0, 0.0, 0.3, 1.0),
                                             color=(41, 53, 70))])

    def test_a_zone_on_its_ground_takes_no_card_padding(self) -> None:
        """With its type read as type, the sidebar's `CONTACT` became its
        Zone's Title, and the Zone was padded in from the lane as a card."""
        html = render(self.sidebar(BBox(0.03, 0.05, 0.27, 0.2)))
        assert re.search(r'<section class="[^"]*\bfilled grounded\b', html)

    def test_a_card_is_still_a_card(self) -> None:
        """A Zone that holds the whole fill is the fill's own: a card."""
        html = render(self.sidebar(BBox(0.0, 0.0, 0.3, 1.0)))
        assert re.search(r'<section class="[^"]*\bfilled\b', html)
        assert "grounded" not in html[:html.index('id="doc-ir"')].split("<body")[1]
