"""Spec 0012, G4, the drawing half — boxes and lanes as the page builds them.

Copies in a grid row drawn one height; a card and a filled lane keeping the
inset the page gives their type; a pairs Zone drawn by its printed lines.
"""

from __future__ import annotations

import re

from doc_to_html.ir import (BBox, Block, Document, Flow, Furniture, Kind, Pair,
                            Region, Role, Source, Style, Zone, cell)
from doc_to_html import furnish
from doc_to_html.ir import Look
from doc_to_html.render import (HABIT, PEERS, PLACED_CSS, WRAPS, _aligned, _copies, _edges, _extent,
                                _habit, _heading_size, _indent_in_row, _lanes, _one_grid, _page,
                                _printed_lines, _title_as_label,
                                _title_line, render)


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
        # Spec 0016, step 1: shares of the Zone's width, no `auto` track;
        # `In stock`, flush right, takes its track from halfway across the
        # gap after `each`.
        assert line[0] == ("grid-template-columns:minmax(0,46.52fr) minmax(0,23.99fr) "
                           "minmax(0,29.49fr)")
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


def lines_of(zone: Zone) -> list[tuple[str, list[tuple[str, str]]]]:
    """Each drawn line's tracks, and each span's text and style."""
    html = body_of(render(page([zone])))
    return [(style, re.findall(r'<span[^>]*?(?: style="([^"]*)")?>([^<]*)</span>', spans))
            for style, spans in re.findall(r'<div class="line" style="([^"]*)">(.*?)</div>', html)]


def styled(drawn: list[tuple[str, list[tuple[str, str]]]], text: str) -> str:
    return next(style for _, spans in drawn for style, said in spans if said == text)


class TestStepOneOneColumnGridPerZone:
    """Spec 0016, step 1: a Zone drawn by its printed lines keeps one set
    of column edges across all of them."""

    def test_a_column_keeps_its_left_edge_from_row_to_row(self) -> None:
        """`ticket_0020`'s third column: `BOARDING` / `07:35` and `GROUP` /
        `2` start where the page starts them, not flush right."""
        zone = grid_of_three(at(0.03, 0.65))
        printed = _printed_lines(zone)
        assert printed is not None
        columns = _aligned(printed, 0.01)
        assert {at for _, at in columns.values()} == {0.03, 0.20, 0.38}
        assert not any(right for right, _ in columns.values())
        assert "justify-self:end" not in styled(lines_of(zone), "07:35")

    def test_no_track_is_auto(self) -> None:
        zone = grid_of_three(at(0.03, 0.65))
        tracks = [style for style, _ in lines_of(zone)]
        assert tracks and not any("auto" in style for style in tracks)
        assert all(style.startswith("grid-template-columns:minmax(0,") for style in tracks)

    def test_a_column_whose_right_edges_agree_is_set_flush_right(self) -> None:
        """`SEAT` over `12A` with their right edges agreeing and their left
        edges more than a body glyph apart."""
        zone = pairs((("FLIGHT", at(0.76, 0.30, tall=0.015)),
                      ("NL 0482", at(0.76, 0.34, tall=0.015))),
                     (("SEAT", BBox(0.943, 0.30, 0.974, 0.315)),
                      ("12A", BBox(0.955, 0.34, 0.973, 0.355))),
                     box=BBox(0.74, 0.28, 1.0, 0.4))
        printed = _printed_lines(zone)
        assert printed is not None
        columns = _aligned(printed, 0.01)
        seat = next(id(c) for line in printed for c, _, _ in line if c.text == "SEAT")
        assert columns[seat] == (True, 0.974)
        drawn = lines_of(zone)
        assert "justify-self:end" in styled(drawn, "12A")
        assert "justify-self:end" in styled(drawn, "SEAT")

    def test_flush_right_short_of_the_zones_right_ends_at_its_column(self) -> None:
        """A line set flush right to a column edge left of the Zone's right
        keeps the rest of the line as white space: its one track would
        otherwise take the whole line."""
        zone = pairs((("PASSENGER", BBox(0.76, 0.16, 0.85, 0.175)),
                      ("HALVORSEN / A", BBox(0.76, 0.20, 0.897, 0.215))),
                     (("SEAT", BBox(0.943, 0.30, 0.974, 0.315)),
                      ("12A", BBox(0.955, 0.34, 0.973, 0.355))),
                     (("departure", BBox(0.841, 0.92, 0.894, 0.935)), None),
                     box=BBox(0.74, 0.1, 1.0, 1.0))
        drawn = lines_of(zone)
        (tracks,) = [style for style, spans in drawn if any(t == "departure" for _, t in spans)]
        assert tracks.count("minmax(") == 2

    def test_edges_that_do_not_increase_give_no_grid(self) -> None:
        shown = [BBox(0.1, 0.0, 0.3, 0.1), BBox(0.2, 0.0, 0.4, 0.1)]
        assert _edges(shown, [(False, 0.1), (False, 0.05)], 0.4) is None

    def test_entries_sharing_a_line_do_not_wrap_and_a_lone_one_does(self) -> None:
        assert ".placed .line > span { white-space:nowrap; padding-right:.3em; }" in PLACED_CSS
        assert ".placed .line > span:only-child { white-space:normal; }" in PLACED_CSS
        assert not any("column-gap" in rule for rule in PLACED_CSS)

    def test_an_entry_printed_on_more_than_one_line_wraps(self) -> None:
        """Taller than `WRAPS` of its glyphs (a 10px body on a 1000px page)."""
        tall = 0.01 * WRAPS + 0.005
        zone = pairs((("Gate closes 20 minutes before departure", BBox(0.40, 0.5, 0.6, 0.5 + tall)),
                      None),
                     (("C14", BBox(0.70, 0.5, 0.73, 0.51)), None),
                     box=BBox(0.3, 0.45, 0.8, 0.6))
        drawn = lines_of(zone)
        assert "white-space:normal" in styled(drawn, "Gate closes 20 minutes before departure")
        assert "white-space:normal" not in styled(drawn, "C14")


def main_pane() -> list[Zone]:
    """`ticket_0020`'s main pane as the detector cut it at its widest
    gutter: the grid's first three columns and `OSL` in one Zone, `TRD`
    and the `DEPARTS` / `CLASS` column in another, `DEPARTS` and `CLASS`
    placed nowhere."""
    left = pairs((("FLIGHT", at(0.03, 0.59, tall=0.015)), ("NL 0482", at(0.03, 0.65, tall=0.03))),
                 (("DATE", at(0.20, 0.59, tall=0.015)), ("14 OCT 2026", at(0.20, 0.65, 0.12, 0.03))),
                 (("BOARDING", at(0.38, 0.59, 0.07, 0.015)), ("07:35", at(0.38, 0.65, tall=0.03))),
                 (("GATE", at(0.03, 0.74, tall=0.015)), ("C14", at(0.03, 0.79, tall=0.03))),
                 box=BBox(0.03, 0.30, 0.45, 0.84), band=1, title="PASSENGER")
    left.extra = [Block(kind="paragraph", lines=[cell("OSL", bbox=BBox(0.03, 0.40, 0.15, 0.46))])]
    right = pairs((("", at(0.54, 0.50)), ("TRONDHEIM VÆRNES", at(0.54, 0.50, 0.17, 0.03))),
                  (("DEPARTS", at(0.55, 0.59)), ("08:05", at(0.55, 0.65, 0.05, 0.03))),
                  (("CLASS", at(0.55, 0.74)), ("Economy", at(0.55, 0.79, 0.09, 0.03))),
                  box=BBox(0.54, 0.40, 0.71, 0.85), band=1, title="TRD", title_align="right")
    right.pairs[0].label.bbox = None
    right.pairs[1].label.bbox = None
    right.pairs[2].label.bbox = None
    return [left, right]


def line_texts(html: str) -> list[list[str]]:
    return [re.findall(r">([^<>]+)</span>", spans)
            for spans in re.findall(r'<div class="line" style="[^"]*">(.*?)</div>', html)]


class TestStepTwoOneGridAcrossSideBySideZones:
    """Spec 0016, step 2."""

    def test_2a_two_pairs_zones_sharing_printed_lines_are_one_grid(self) -> None:
        document = page(main_pane())
        assert _one_grid([[zone] for zone in document.zones], document) == [(0, 1 + 1)]

    def test_2a_they_are_drawn_as_one_unit(self) -> None:
        html = body_of(render(page(main_pane())))
        assert html.count('class="placed"') == 1
        lines = line_texts(html)
        assert ["FLIGHT", "DATE", "BOARDING", "DEPARTS"] in lines
        assert ["NL 0482", "14 OCT 2026", "07:35", "08:05"] in lines
        assert ["GATE", "CLASS"] in lines and ["C14", "Economy"] in lines

    def test_2a_not_where_one_is_framed_or_filled(self) -> None:
        for change in ({"frame": BBox(0.53, 0.39, 0.72, 0.86)}, {"fill": (11, 110, 138)},
                       {"boxed": True}, {"title_fill": (11, 110, 138)}):
            zones = main_pane()
            for name, value in change.items():
                setattr(zones[1], name, value)
            document = page(zones)
            assert _one_grid([[zone] for zone in document.zones], document) == [], change

    def test_2a_not_where_they_share_one_line(self) -> None:
        zones = main_pane()
        zones[1].pairs = zones[1].pairs[:2]
        zones[1].pairs[1].value.bbox = at(0.55, 0.62, 0.05, 0.03)
        document = page(zones)
        assert _one_grid([[zone] for zone in document.zones], document) == []

    def test_2b_a_title_is_a_line_at_its_printed_place(self) -> None:
        zone = main_pane()[1]
        title, label, box = _title_line(zone, 0.50)
        assert title.text == "TRD" and not label
        assert box.left == box.right == 0.71 and box.top == 0.40
        assert abs(box.bottom - (0.40 + 0.85 * 0.10)) < 1e-9
        assert title.look is not None and title.look.bold
        zone.title_align = "centre"
        assert _title_line(zone, 0.50)[2].left == (0.54 + 0.71) / 2
        zone.title_align = None
        assert _title_line(zone, 0.50)[2].left == 0.54

    def test_2b_the_title_is_drawn_on_the_line_it_shares(self) -> None:
        """`TRD` on the line of `OSL`, flush right over `TRONDHEIM VÆRNES`."""
        html = body_of(render(page(main_pane())))
        assert ["OSL", "TRD"] in line_texts(html)
        trd = re.search(r'<span style="([^"]*)">TRD</span>', html)
        assert trd is not None and "justify-self:end" in trd.group(1)

    def test_2c_an_implied_entry_joins_its_roles_line(self) -> None:
        """`CLASS`, set over `Economy` by the page's habit, takes the line
        of `GATE`; the IR keeps no box for it."""
        zones = main_pane()
        render(page(zones))
        assert zones[1].pairs[2].label.bbox is None

    def test_2d_a_label_goes_over_its_value_by_the_pages_habit(self) -> None:
        document = page(main_pane())
        printed = _printed_lines(document.zones[1], document)
        assert texts(printed) == [["TRONDHEIM VÆRNES"], ["DEPARTS"], ["08:05"],
                                  ["CLASS"], ["Economy"]]
        assert _printed_lines(document.zones[1]) is None

    def test_2d_the_habit_is_the_pages_medians(self) -> None:
        document = page(main_pane())
        over = _habit(document, at(0.55, 0.65, 0.05, 0.03), True)
        # Labels 0.015 tall; the median gap to their values 0.045.
        assert over is not None and over.left == over.right == 0.55
        assert abs(over.top - 0.59) < 1e-9 and abs(over.bottom - 0.605) < 1e-9
        under = _habit(document, at(0.55, 0.59, tall=0.015), False)
        assert under is not None and abs(under.top - 0.65) < 1e-9

    def test_2d_no_habit_where_the_page_sets_one_pair_beside(self) -> None:
        zones = main_pane()
        zones[0].pairs[3].value.bbox = at(0.10, 0.74, tall=0.015)
        assert _habit(page(zones), at(0.55, 0.65), True) is None

    def test_2d_no_habit_from_fewer_than_habit_pairs(self) -> None:
        zones = main_pane()
        zones[0].pairs = zones[0].pairs[:HABIT - 1]
        assert _habit(page(zones), at(0.55, 0.65), True) is None


TEAL = (11, 110, 138)
STRIP = Furniture(kind="fill", bbox=BBox(0.0, 0.0, 1.0, 0.15), color=TEAL)
"""`ticket_0020`'s teal strip: one solid fill across both panes, no Zone's."""


def on_strip(text: str, box: BBox, band: int = 0, **fields: object) -> Zone:
    return Zone(kind=Kind.PROSE, role=Role.HEADER, bbox=box, band=band, complete=True,
                fill=TEAL, blocks=[Block(kind="heading" if "PASS" in text else "paragraph",
                                         lines=[cell(text, bbox=box)])],
                **fields)  # type: ignore[arg-type]


def stub_under_strip() -> Zone:
    return pairs((("FLIGHT", at(0.76, 0.30, tall=0.015)), ("NL 0482", at(0.76, 0.34, tall=0.015))),
                 (("SEAT", at(0.94, 0.30, tall=0.015)), ("12A", at(0.94, 0.34, tall=0.015))),
                 box=BBox(0.74, 0.0, 1.0, 1.0))


class TestStepThreeADrawnStripIsOneContainer:
    """Spec 0016, step 3."""

    def test_3a_rows_on_one_plain_fill_are_drawn_once_on_it(self) -> None:
        zones = [on_strip("NORDLYS AIR", BBox(0.02, 0.03, 0.2, 0.12), band=0),
                 on_strip("BOARDING PASS", BBox(0.56, 0.03, 0.71, 0.10), band=0),
                 on_strip("The", BBox(0.21, 0.11, 0.73, 0.14), band=1),
                 pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35), band=2)]
        html = body_of(render(page(zones, furniture=[STRIP])))
        filled = re.findall(r'<div class="filled" style="([^"]*)">', html)
        assert len(filled) == 1 and filled[0].startswith("background:rgb(11,110,138)")
        inside = html[html.index('<div class="filled"'):html.index("£4.20")]
        assert "NORDLYS AIR" in inside and "BOARDING PASS" in inside and ">The<" in inside

    def test_3a_its_last_row_keeps_no_margin_of_its_own(self) -> None:
        zones = [on_strip("NORDLYS AIR", BBox(0.02, 0.03, 0.2, 0.12)),
                 pairs(CARD, STOCK, box=BBox(0.03, 0.3, 0.33, 0.35), band=1)]
        html = body_of(render(page(zones, furniture=[STRIP])))
        start = html.index('<div class="filled"')
        assert re.search(r'<div class="band" style="[^"]*margin-bottom:0"', html[start:])

    def test_3a_not_a_fill_a_zone_holds_or_one_of_another_colour(self) -> None:
        zones = [on_strip("NORDLYS AIR", BBox(0.02, 0.03, 0.2, 0.12))]
        owned = Furniture(kind="fill", bbox=STRIP.bbox, color=TEAL, zone=0)
        assert 'class="filled"' not in body_of(render(page(zones, furniture=[owned])))
        zones[0].fill = (250, 250, 250)
        assert 'class="filled"' not in body_of(render(page(zones, furniture=[STRIP])))

    def test_3b_a_fill_across_a_zones_top_is_its_band(self) -> None:
        document = page([stub_under_strip()], furniture=[STRIP])
        band = furnish.anchor(document).bands[0]
        assert band.bbox == BBox(0.74, 0.0, 1.0, 0.15) and band.color == TEAL
        assert not furnish.anchor(document).hatches

    def test_3b_it_is_drawn_across_the_zones_top_and_its_lines_start_under_it(self) -> None:
        html = body_of(render(page([stub_under_strip()], furniture=[STRIP])))
        assert ("background-image:linear-gradient(rgb(11,110,138),rgb(11,110,138));"
                "background-size:100% 150px;background-repeat:no-repeat") in html
        first = re.findall(r'<div class="line" style="([^"]*)">', html)[0]
        assert "margin-top:" in first

    def test_3b_not_for_a_zone_with_its_own_fill_or_bar(self) -> None:
        for change in ({"fill": TEAL}, {"title_fill": TEAL}, {"header_fill": TEAL}):
            zone = stub_under_strip()
            for name, value in change.items():
                setattr(zone, name, value)
            assert not furnish.anchor(page([zone], furniture=[STRIP])).bands, change

    def test_3b_not_where_the_fill_does_not_open_the_zone(self) -> None:
        zone = stub_under_strip()
        zone.bbox = BBox(0.74, 0.05, 1.0, 1.0)
        assert not furnish.anchor(page([zone], furniture=[STRIP])).bands

    def test_3c_a_heading_with_no_measured_size_takes_its_lines(self) -> None:
        """`BOARDING PASS`, white on teal, which `style.heading_sizes` does
        not measure."""
        heading = Block(kind="heading", lines=[cell("BOARDING PASS")])
        assert _heading_size(heading) is None
        heading.lines[0].look = Look(size=1.06)
        assert _heading_size(heading) == 1.06
        heading.size = 1.4
        assert _heading_size(heading) == 1.4

    def test_3c_not_where_a_line_is_unmeasured(self) -> None:
        heading = Block(kind="heading", lines=[cell("BOARDING"), cell("PASS")])
        heading.lines[0].look = Look(size=1.06)
        assert _heading_size(heading) is None

    def test_3c_it_is_drawn_at_that_size(self) -> None:
        zone = on_strip("BOARDING PASS", BBox(0.56, 0.03, 0.71, 0.10))
        zone.fill = None
        zone.blocks[0].lines[0].look = Look(size=1.06)
        assert '<h1 style="font-size:1.06em">BOARDING PASS</h1>' in body_of(render(page([zone])))


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
        # 0.045 to 0.318 of a 1000px page; the box starts 15px short of
        # its type, an inset kept since spec 0017, 1b.
        assert '<div class="placed" style="max-width:273px;margin-left:15px">' in html


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


def strip_and_grid(left: float, **fields: object) -> list[Zone]:
    """A strip whose type runs to the paper's edge, and under it a Zone
    set `left` in — `ticket_0020`'s main pane, the strip's wordmark at the
    edge and the field grid 22px in."""
    strip = Zone(kind=Kind.PROSE, role=Role.HEADER, bbox=BBox(0.0, 0.0, 0.2, 0.1), band=0,
                 complete=True, blocks=[Block(kind="paragraph",
                                              lines=[cell("NORDLYS AIR", bbox=BBox(0.0, 0.0, 0.2, 0.1))])])
    grid = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=BBox(left, 0.2, 0.6, 0.3), band=1,
                complete=True, blocks=[Block(kind="paragraph",
                                             lines=[cell("HALVORSEN", bbox=BBox(left, 0.2, 0.6, 0.3))])],
                **fields)  # type: ignore[arg-type]
    return [strip, grid]


def section_style(html: str, text: str) -> str:
    """The style of the section that holds `text`."""
    head = html[:html.index(text)]
    found = re.findall(r'<section class="zone[^"]*"(?: style="([^"]*)")?>', head)
    return found[-1] if found else ""


class TestSpec0017StepOneTheTypeKeepsItsInset:
    """Spec 0017, step 1: margins from the type."""

    def test_1a_a_row_set_in_from_the_rows_edge_keeps_it(self) -> None:
        html = body_of(render(page(strip_and_grid(0.05))))
        assert "margin-left:50px" in section_style(html, "HALVORSEN")

    def test_1a_not_within_a_body_glyph(self) -> None:
        html = body_of(render(page(strip_and_grid(0.008))))
        assert "margin-left" not in section_style(html, "HALVORSEN")

    def test_1a_not_for_a_zone_set_centred_or_flush_right(self) -> None:
        for align in ("centre", "right"):
            html = body_of(render(page(strip_and_grid(0.05, align=align))))
            assert "margin-left" not in section_style(html, "HALVORSEN"), align

    def test_1a_not_for_a_list_whose_box_may_start_at_its_text(self) -> None:
        zones = strip_and_grid(0.05)
        zones[1].kind = Kind.LIST
        zones[1].blocks[0].kind = "item"
        document = page(zones)
        assert _indent_in_row([zones[1]], document, _page(document), (0.0, 0.6)) == 0.0

    def test_1a_not_inside_a_frame_other_zones_share(self) -> None:
        zones = strip_and_grid(0.05)
        card = BBox(0.0, 0.15, 0.7, 0.4)
        third = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=BBox(0.05, 0.32, 0.6, 0.38), band=2,
                     complete=True, frame=card,
                     blocks=[Block(kind="paragraph", lines=[cell("more")])])
        zones[1].frame = card
        document = page(zones + [third])
        assert _indent_in_row([zones[1]], document, _page(document), (0.0, 0.6)) == 0.0

    def test_1b_a_box_short_of_its_type_keeps_the_inset(self) -> None:
        """The stub, whose box starts at the perforation."""
        html = body_of(render(page([stub_under_strip()])))
        placed = re.search(r'<div class="placed" style="([^"]*)">', html)
        assert placed is not None and "margin-left:20px" in placed.group(1)

    def test_1b_not_on_a_fill_whose_lane_pads_to_the_type(self) -> None:
        zone = stub_under_strip()
        zone.fill = (38, 51, 63)
        html = body_of(render(page([zone])))
        placed = re.search(r'<div class="placed" style="([^"]*)">', html)
        assert placed is not None and "margin-left" not in placed.group(1)


def sized(text: str, box: BBox, size: float | None) -> object:
    made = cell(text, bbox=box)
    made.look = None if size is None else Look(size=size)
    return made


def fields_grid(nl: float | None = None, two: float = 1.38) -> Zone:
    """`ticket_0020`'s main grid, two rows of three, label over value:
    `NL 0482` placed nowhere and unmeasured unless `nl` is given, and
    `2` measured `two` among values of 1.50."""
    rows = [("FLIGHT", 0.03, 0.59, "NL 0482", nl), ("DATE", 0.20, 0.59, "14 OCT 2026", 1.5),
            ("BOARDING", 0.38, 0.59, "07:35", 1.5), ("GATE", 0.03, 0.74, "C14", 1.5),
            ("SEAT", 0.20, 0.74, "12A", 1.5), ("GROUP", 0.38, 0.74, "2", two)]
    made = []
    for label, left, top, value, size in rows:
        made.append(Pair(label=sized(label, at(left, top, tall=0.015), 1.0),  # type: ignore[arg-type]
                         value=sized(value, at(left, top + 0.05, tall=0.03), size)))  # type: ignore[arg-type]
    zone = Zone(kind=Kind.PAIRS, role=Role.BODY, bbox=BBox(0.03, 0.59, 0.45, 0.8), pairs=made,
                complete=True)
    if nl is None:
        zone.pairs[0].value.bbox = None
    return zone


def size_of(html: str, text: str) -> str | None:
    found = re.search(r'<span(?: class="label")?(?: style="([^"]*)")?>' + re.escape(text)
                      + "</span>", html)
    assert found is not None, text
    size = re.search(r"font-size:calc\(([\d.]+) ", found.group(1) or "")
    return size.group(1) if size else None


class TestSpec0017StepTwoOneSizePerRole:
    """Spec 0017, step 2: one style per role in a grid."""

    def test_2a_an_entry_with_no_size_takes_its_groups(self) -> None:
        html = body_of(render(page([fields_grid()])))
        assert size_of(html, "NL 0482") == "1.50"

    def test_2a_a_size_within_the_noise_takes_the_groups(self) -> None:
        html = body_of(render(page([fields_grid(nl=1.5, two=1.38)])))
        assert size_of(html, "2") == "1.50"

    def test_2a_a_size_beyond_the_noise_is_the_pages_own(self) -> None:
        html = body_of(render(page([fields_grid(nl=1.5, two=2.0)])))
        assert size_of(html, "2") == "2.00"

    def test_2a_labels_are_a_group_of_their_own(self) -> None:
        html = body_of(render(page([fields_grid()])))
        assert size_of(html, "FLIGHT") is None

    def test_2a_not_from_fewer_than_peers_measured(self) -> None:
        zone = fields_grid()
        for pair in zone.pairs[1:]:
            pair.value.look = None
        zone.pairs[1].value.look = Look(size=1.5)
        zone.pairs[2].value.look = Look(size=1.5)
        assert PEERS == 3
        html = body_of(render(page([zone])))
        assert size_of(html, "NL 0482") is None

    def test_2a_the_ir_keeps_what_was_measured(self) -> None:
        zone = fields_grid()
        render(page([zone]))
        two = zone.pairs[5].value.look
        assert zone.pairs[0].value.look is None and two is not None and two.size == 1.38

    def test_2b_a_title_set_as_the_labels_are_is_the_first_values_label(self) -> None:
        zone = fields_grid(nl=1.5)
        zone.pairs.insert(0, Pair(label=cell(""), value=sized(  # type: ignore[arg-type]
            "HALVORSEN / ASTRID MS", at(0.03, 0.50, 0.25, 0.03), 1.5)))
        zone.bbox = BBox(0.03, 0.45, 0.45, 0.8)
        zone.title, zone.title_size = "PASSENGER", 0.88
        assert _title_as_label(zone)
        html = body_of(render(page([zone])))
        assert "<h2" not in html
        assert re.search(r'<span class="label"(?: style="[^"]*")?>PASSENGER</span>', html)
        assert "font-weight:700" not in html[:html.index("PASSENGER")]
        assert html.index("PASSENGER") < html.index("HALVORSEN")

    def test_2b_not_a_heading_set_apart_from_the_labels(self) -> None:
        zone = fields_grid(nl=1.5)
        zone.pairs.insert(0, Pair(label=cell(""), value=cell("$0.42")))
        zone.title = "COST PER MILLION"
        for change in ({"title_size": 0.7}, {"title_size": None},
                       {"title_size": 0.95, "title_align": "right"},
                       {"title_size": 0.95, "title_color": (255, 122, 122)}):
            zone.title_size, zone.title_align, zone.title_color = None, None, None
            for pair in zone.pairs[1:]:
                pair.label.look = Look(size=1.0, color=(90, 102, 118))
            for name, value in change.items():
                setattr(zone, name, value)
            assert not _title_as_label(zone), change

    def test_2b_not_where_the_first_pair_has_its_label(self) -> None:
        zone = fields_grid(nl=1.5)
        zone.title, zone.title_size = "FIELDS", 1.0
        assert not _title_as_label(zone)
