"""Spec 0012, G4, the drawing half — boxes and lanes as the page builds them.

Copies in a grid row drawn one height; a card and a filled lane keeping the
inset the page gives their type; a pairs Zone drawn by its printed lines.
"""

from __future__ import annotations

import re

from doc_to_html.ir import (BBox, Block, Document, Flow, Furniture, Kind, Pair,
                            Region, Role, Source, Style, Zone, cell)
from doc_to_html.render import _copies, _printed_lines, render


def pairs(*rows: tuple[tuple[str, BBox], tuple[str, BBox] | None], box: BBox,
          **fields: object) -> Zone:
    made = [Pair(label=cell(label, bbox=lbox),
                 value=cell(value[0], bbox=value[1]) if value else cell(""))
            for (label, lbox), value in rows]
    return Zone(kind=Kind.PAIRS, role=Role.BODY, bbox=box, pairs=made,
                complete=True, **fields)  # type: ignore[arg-type]


def page(zones: list[Zone], **fields: object) -> Document:
    return Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                  rectified_width=1000, rectified_height=1000),
                    style=Style(body_px=10.0), zones=zones,
                    **fields)  # type: ignore[arg-type]


def body_of(html: str) -> str:
    return html[html.index('<div class="doc"'):html.index('id="doc-ir"')]


CARD = (("£4.20", BBox(0.045, 0.323, 0.089, 0.339)), ("each", BBox(0.172, 0.33, 0.195, 0.338)))
STOCK = (("In stock", BBox(0.28, 0.33, 0.318, 0.338)), None)
"""`catalogue_0015`'s first card's foot, as the IR holds it: two pairs on
one printed line."""


class TestAPairsZoneByItsPrintedLines:

    def test_two_pairs_on_one_line_are_one_line(self) -> None:
        zone = pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35))
        printed = _printed_lines(zone)
        assert printed is not None
        assert [[c.text for c, _ in line] for line in printed] == [["£4.20", "each", "In stock"]]

    def test_a_value_under_its_label_is_its_own_line(self) -> None:
        zone = pairs((("Chartered Engineer", BBox(0.02, 0.30, 0.29, 0.32)),
                      ("Reg. no. 11408", BBox(0.02, 0.34, 0.11, 0.36))),
                     box=BBox(0.0, 0.3, 0.3, 0.36))
        printed = _printed_lines(zone)
        assert printed is not None and len(printed) == 2

    def test_a_label_beside_its_value_keeps_the_list(self) -> None:
        zone = pairs((("Name", BBox(0.13, 0.25, 0.16, 0.26)),
                      ("Acme Corporation", BBox(0.18, 0.25, 0.29, 0.26))),
                     (("Phone", BBox(0.13, 0.33, 0.16, 0.34)),
                      ("123.4456.4567", BBox(0.18, 0.33, 0.26, 0.34))),
                     box=BBox(0.1, 0.24, 0.3, 0.35))
        assert _printed_lines(zone) is None

    def test_the_line_is_drawn_by_where_each_entry_starts(self) -> None:
        zone = pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35))
        html = body_of(render(page([zone])))
        (line,) = re.findall(r'<div class="line" style="([^"]*)">(.*?)</div>', html)
        assert line[0].startswith("grid-template-columns:46.52fr 39.56fr auto")
        assert 'justify-self:end">In stock' in line[1]
        assert '<span class="label">£4.20</span>' in line[1]


def tile(left: float, height: float) -> Zone:
    zone = pairs((("184", BBox(left + 0.02, 0.2, left + 0.06, 0.22)),
                  ("ms", BBox(left + 0.065, 0.2, left + 0.09, 0.22))),
                 box=BBox(left + 0.015, 0.2, left + 0.1, 0.27))
    zone.boxed, zone.frame = True, BBox(left, 0.18, left + 0.2, 0.18 + height)
    return zone


class TestCopiesInARowAreOneHeight:

    def test_cards_of_one_height_are_copies(self) -> None:
        assert _copies([tile(0.0, 0.11), tile(0.25, 0.11)])
        assert not _copies([tile(0.0, 0.11), tile(0.25, 0.2)])

    def test_a_grid_row_of_copies_stretches_each_card(self) -> None:
        zones = [tile(0.0, 0.11), tile(0.25, 0.11)]
        for column, zone in enumerate(zones):
            zone.column = column
        grid = Region(top=0.1, bottom=0.4, flow=Flow.GRID, splits=(0.24,))
        html = body_of(render(page(zones, regions=[grid])))
        assert html.count("align-self:stretch;display:grid") == 2


class TestTheInsetIsThePages:

    def test_a_card_keeps_its_type_off_its_frame(self) -> None:
        card = tile(0.0, 0.11)
        html = body_of(render(page([card])))
        # 20px from the frame's left to the type, less its 1px border.
        assert re.search(r'<section class="zone zone-body boxed" style="padding:\d+px 19px \d+px 19px',
                         html)

    def test_a_filled_lane_starts_at_its_fill_and_insets_its_type(self) -> None:
        side = Zone(kind=Kind.PROSE, role=Role.BODY, column=0, complete=True,
                    bbox=BBox(0.02, 0.05, 0.3, 0.1), fill=(38, 51, 63),
                    blocks=[Block(kind="paragraph", lines=[
                        cell("Ines Halloran", bbox=BBox(0.03, 0.05, 0.2, 0.07))])])
        main = Zone(kind=Kind.PROSE, role=Role.BODY, column=1, complete=True,
                    bbox=BBox(0.4, 0.05, 0.9, 0.1),
                    blocks=[Block(kind="paragraph", lines=[cell("EXPERIENCE")])])
        fill = Furniture(kind="fill", bbox=BBox(0.0, 0.0, 0.34, 1.0), color=(38, 51, 63))
        lanes = Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.34,))
        html = body_of(render(page([side, main], regions=[lanes], furniture=[fill])))
        first = re.findall(r'class="lane" style="([^"]*)"', html)[0]
        assert "background:rgb(38,51,63)" in first
        assert re.search(r"padding:\d+px 30px \d+px 30px", first)
