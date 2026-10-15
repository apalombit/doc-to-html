"""Spec 0012, G4, the drawing half — boxes and lanes as the page builds them.

Copies in a grid row drawn one height; a card and a filled lane keeping the
inset the page gives their type; a pairs Zone drawn by its printed lines.
"""

from __future__ import annotations

import re

from doc_to_html.ir import (BBox, Block, Document, Flow, Furniture, Kind, Pair,
                            Region, Role, Source, Style, Zone, cell)
from doc_to_html.render import _copies, _extent, _lanes, _printed_lines, render


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
        assert [[c.text for c, _, _ in line] for line in printed] == [["£4.20", "each", "In stock"]]

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


def texts(printed: list[list[tuple[object, bool, BBox]]] | None) -> list[list[str]]:
    assert printed is not None
    return [[c.text for c, _, _ in sorted(line, key=lambda e: e[2].left)]  # type: ignore[attr-defined]
            for line in printed]


def at(left: float, top: float, wide: float = 0.04, tall: float = 0.02) -> BBox:
    return BBox(left, top, left + wide, top + tall)


def stub() -> Zone:
    """`ticket_0020`'s stub, its pairs as the model listed them: column by
    column, label over value."""
    return pairs((("FLIGHT", at(0.76, 0.30)), ("NL 0482", at(0.76, 0.34))),
                 (("GATE", at(0.76, 0.42)), ("C14", at(0.76, 0.47))),
                 (("SEAT", at(0.94, 0.30)), ("12A", at(0.94, 0.34))),
                 (("GROUP", at(0.93, 0.42)), ("2", at(0.93, 0.47))),
                 box=BBox(0.74, 0.28, 1.0, 0.5))


def grid_of_three(flight: BBox | None) -> Zone:
    """`ticket_0020`'s passenger grid, three across, label over value, with
    `NL 0482` placed nowhere when `flight` is None."""
    zone = pairs((("FLIGHT", at(0.03, 0.59)), ("NL 0482", flight or at(0.03, 0.65))),
                 (("DATE", at(0.20, 0.59)), ("14 OCT 2026", at(0.20, 0.65, 0.12))),
                 (("BOARDING", at(0.38, 0.59)), ("07:35", at(0.38, 0.65))),
                 box=BBox(0.02, 0.58, 0.45, 0.7))
    if flight is None:
        zone.pairs[0].value.bbox = None
    return zone


class TestStepTwoPairsAsThePagePrintsThem:
    """Spec 0015, step 2."""

    def test_2a_lines_are_formed_by_position_not_the_models_order(self) -> None:
        assert texts(_printed_lines(stub())) == [
            ["FLIGHT", "SEAT"], ["NL 0482", "12A"], ["GATE", "GROUP"], ["C14", "2"]]

    def test_2b_an_unplaced_value_goes_under_its_label_in_a_grid(self) -> None:
        printed = _printed_lines(grid_of_three(None))
        assert texts(printed) == [["FLIGHT", "DATE", "BOARDING"],
                                  ["NL 0482", "14 OCT 2026", "07:35"]]
        assert printed is not None
        [(_, _, box)] = [e for e in printed[1] if e[0].text == "NL 0482"]
        assert box.left == 0.03 and (box.top, box.bottom) == (0.65, 0.67)

    def test_2b_an_implied_box_is_the_renders_and_never_the_irs(self) -> None:
        zone = grid_of_three(None)
        render(page([zone]))
        assert zone.pairs[0].value.bbox is None

    def test_2b_an_unplaced_entry_goes_before_the_next_on_its_line(self) -> None:
        """`catalogue_0015`'s `£9.80`, a label with no value."""
        zone = pairs((("Brass cup handle", at(0.36, 0.25, 0.1)), None),
                     (("£9.80", at(0.36, 0.32)), None),
                     (("each", at(0.49, 0.33, 0.03, 0.008)), None),
                     (("In stock", at(0.60, 0.33, 0.04, 0.008)), None),
                     box=BBox(0.35, 0.24, 0.65, 0.35))
        zone.pairs[1].label.bbox = None
        assert texts(_printed_lines(zone)) == [["Brass cup handle"],
                                               ["£9.80", "each", "In stock"]]

    def test_2b_not_where_its_value_is_on_another_line(self) -> None:
        """The ticket's `DEPARTS`: nothing says whether the page sets it
        over `08:05` or beside it."""
        zone = pairs((("DEPARTS", at(0.55, 0.60)), ("08:05", at(0.55, 0.65))),
                     (("CLASS", at(0.55, 0.75)), ("Economy", at(0.55, 0.80))),
                     box=BBox(0.54, 0.58, 0.7, 0.85))
        zone.pairs[0].label.bbox = None
        assert _printed_lines(zone) is None

    def test_2b_not_where_the_line_has_no_room_before_the_next(self) -> None:
        """`darkdeck_0009`'s `$2.14`, printed over `+9%`, which starts
        where the tile's type starts."""
        zone = pairs((("", at(0.78, 0.15)), ("$2.14", at(0.78, 0.15))),
                     (("+9%", at(0.78, 0.18, 0.02, 0.01)), None),
                     box=BBox(0.77, 0.13, 0.98, 0.2))
        zone.pairs[0].value.bbox = None
        assert _printed_lines(zone) is None

    def test_2c_a_label_with_no_value_and_no_mark_is_drawn_as_a_line(self) -> None:
        zone = pairs((("Name", at(0.13, 0.25)), ("Acme Corporation", at(0.18, 0.25, 0.1))),
                     (("Alpha Bank - M0123", at(0.13, 0.33, 0.15)), None),
                     box=BBox(0.1, 0.24, 0.3, 0.35))
        html = body_of(render(page([zone])))
        assert '<dd class="line">Alpha Bank - M0123</dd>' in html
        assert "dl.pairs dd.line { grid-column:1 / -1; }" in render(page([zone]))
        assert "<dt>Name</dt>" in html

    def test_2c_in_the_lines_drawn_it_is_not_a_label(self) -> None:
        zone = pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35))
        html = body_of(render(page([zone])))
        assert '<span class="label">£4.20</span>' in html
        stock = re.search(r"<span([^>]*)>In stock</span>", html)
        assert stock is not None and "label" not in stock.group(1)

    def test_2d_an_extra_line_is_drawn_among_the_printed_lines(self) -> None:
        """The ticket's `OSLO GARDERMOEN`, under the name, over the grid."""
        zone = grid_of_three(at(0.03, 0.65))
        zone.extra = [Block(kind="paragraph", lines=[cell("OSLO GARDERMOEN",
                                                          bbox=at(0.03, 0.50, 0.16))])]
        printed = _printed_lines(zone)
        assert texts(printed)[0] == ["OSLO GARDERMOEN"]
        html = body_of(render(page([zone])))
        assert html.count("OSLO GARDERMOEN") == 1
        assert html.index("OSLO GARDERMOEN") < html.index("FLIGHT")

    def test_2d_an_extra_line_nothing_placed_is_drawn_after(self) -> None:
        zone = grid_of_three(at(0.03, 0.65))
        zone.extra = [Block(kind="paragraph", lines=[cell("OSL")])]
        html = body_of(render(page([zone])))
        assert html.count(">OSL<") == 1 and html.index("07:35") < html.index(">OSL<")


def signature(name: str, left: float, rule: tuple[float, float]) -> Zone:
    """One of `certificate_0021`'s signatures: a name centred over a rule
    a quarter of the page wide, which `furnish.anchor` draws under it."""
    return Zone(kind=Kind.PROSE, role=Role.BODY, complete=True, band=4,
                bbox=BBox(left, 0.72, left + 0.11, 0.85),
                blocks=[Block(kind="paragraph", lines=[
                            cell(name, bbox=BBox(left + 0.01, 0.72, left + 0.10, 0.755))]),
                        Block(kind="paragraph", lines=[
                            cell("Course leader", bbox=BBox(left, 0.775, left + 0.11, 0.79))])])


def certificate() -> Document:
    zones = [signature("S. Okonkwo", 0.18, (0.122, 0.372)),
             Zone(kind=Kind.PROSE, role=Role.BODY, complete=True, band=4,
                  bbox=BBox(0.444, 0.67, 0.556, 0.83),
                  blocks=[Block(kind="paragraph", lines=[cell("GUILD GTE 2026")])]),
             signature("H. Brandt", 0.70, (0.628, 0.878))]
    rules = [Furniture(kind="rule", bbox=BBox(0.122, 0.765, 0.372, 0.766), zone=0),
             Furniture(kind="rule", bbox=BBox(0.628, 0.765, 0.878, 0.766), zone=2)]
    return page(zones, furniture=rules)


class TestStepThreeUnitsInThePagesLanes:
    """Spec 0015, 3a."""

    def test_each_unit_takes_the_lane_the_page_gives_it(self) -> None:
        document = certificate()
        units = [[zone] for zone in document.zones]
        lanes = _lanes(units, document, (0.122, 0.878))
        assert [round(lane or 0, 3) for lane in lanes] == [0.426, 0.243, 0.331]

    def test_a_unit_starts_where_its_rule_starts_not_its_type(self) -> None:
        document = certificate()
        extent = _extent([document.zones[2]], document)
        assert extent is not None and extent.left == 0.628 and extent.right == 0.878

    def test_the_lane_is_drawn_as_the_units_flex(self) -> None:
        html = body_of(render(certificate()))
        assert html.count("flex:") >= 3 and "flex:42.6 1 0" in html

    def test_a_row_of_one_asks_nothing(self) -> None:
        document = certificate()
        assert _lanes([[document.zones[0]]], document, (0.1, 0.9)) == [None]


class TestAPairsZoneIsNoWiderThanItsType:
    """Spec 0015, step 3: `invoice_0002`'s `NO … Date …` line, given the
    page's lane, spread across it."""

    def test_the_lines_are_capped_at_the_types_width(self) -> None:
        zone = pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35))
        html = body_of(render(page([zone])))
        # 0.045 to 0.318 of a 1000px page.
        assert '<div class="placed" style="max-width:273px">' in html


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
