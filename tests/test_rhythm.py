"""The page's rhythm — spec 0011, step 1: its gaps, its runs, its alignment.

Synthetic pages throughout: a printed line is a row of glyph-sized blocks,
which `style.type_lines` reads as a line and `content_ink` keeps, where one
long bar would be deleted as a rule. The corpus measurements every threshold
sits on are in `rhythm`'s constants.
"""

from __future__ import annotations

import json
import re

import numpy as np

from doc_to_html.ir import (BBox, Block, Document, Flow, Furniture, Kind, Pair, Region,
                            Source, Style, Zone, cell)
from doc_to_html.render import ABOVE_INK, BELOW_INK, render
from doc_to_html.rhythm import (CENTRE, LEFT, RIGHT, _by_lines, _Line,
                                alignment, frames, groups, title_alignment)

SIDE = 400
BODY = 8.0


def page() -> np.ndarray:
    return np.full((SIDE, SIDE, 3), 255, dtype=np.uint8)


def printed(image: np.ndarray, left: int, right: int, top: int,
            height: int = 8) -> None:
    """One printed line: glyph-sized blocks from `left` to `right`."""
    for x in range(left, right - 4, 8):
        image[top:top + height, x:x + 5] = 0


def box(left: int, top: int, right: int, bottom: int) -> BBox:
    return BBox(left / SIDE, top / SIDE, right / SIDE, bottom / SIDE)


def prose(text: str, bbox: BBox, **fields: object) -> Zone:
    return Zone(kind=Kind.PROSE, bbox=bbox, complete=True,
                blocks=[Block(kind="paragraph", lines=[cell(text)])],
                **fields)  # type: ignore[arg-type]


ONE = [Region(top=0.0, bottom=1.0)]


class TestFrames:
    """`rhythm.frames` — a rectangle a run of one lane shares is that run's."""

    LANES = [Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.5,))]
    PANEL = BBox(0.55, 0.10, 0.95, 0.60)

    def test_a_run_of_one_lane_shares_the_box_it_sits_in(self) -> None:
        zones = [prose("main", BBox(0.05, 0.10, 0.45, 0.90)),
                 prose("a", BBox(0.60, 0.15, 0.90, 0.25)),
                 prose("b", BBox(0.60, 0.30, 0.90, 0.40)),
                 prose("c", BBox(0.60, 0.45, 0.90, 0.55))]
        assert frames(zones, (self.PANEL,), self.LANES) == [
            None, self.PANEL, self.PANEL, self.PANEL]

    def test_a_box_one_zone_sits_in_is_its_own(self) -> None:
        zones = [prose("a", BBox(0.60, 0.15, 0.90, 0.25))]
        assert frames(zones, (self.PANEL,), self.LANES) == [self.PANEL]

    def test_a_box_held_across_two_lanes_is_nobodys(self) -> None:
        wide = BBox(0.02, 0.10, 0.98, 0.60)
        zones = [prose("a", BBox(0.05, 0.15, 0.45, 0.25)),
                 prose("b", BBox(0.60, 0.15, 0.90, 0.25))]
        assert frames(zones, (wide,), self.LANES) == [None, None]

    def test_a_run_broken_by_a_zone_outside_the_box_is_nobodys(self) -> None:
        zones = [prose("a", BBox(0.60, 0.15, 0.90, 0.25)),
                 prose("wider", BBox(0.52, 0.28, 0.99, 0.32)),
                 prose("c", BBox(0.60, 0.45, 0.90, 0.55))]
        assert frames(zones, (self.PANEL,), self.LANES) == [None, None, None]

    CARDS = (BBox(0.04, 0.26, 0.33, 0.89), BBox(0.35, 0.25, 0.65, 0.90),
             BBox(0.67, 0.26, 0.96, 0.89))

    def cards(self) -> list[Zone]:
        """`pricing_0017`: three cards, each read as several Zones."""
        return [prose(f"{name}{part}", BBox(left + 0.02, top, left + 0.25, top + 0.05))
                for name, left in (("starter", 0.04), ("team", 0.35), ("business", 0.67))
                for part, top in enumerate((0.30, 0.55, 0.80))]

    def test_a_lane_of_a_one_row_grid_is_a_run(self) -> None:
        # Spec 0013 step 3a: a one-row grid is a row of cards, each lane one.
        grid = [Region(top=0.2, bottom=0.95, flow=Flow.GRID, splits=(0.345, 0.655))]
        assert frames(self.cards(), self.CARDS, grid) == [
            card for card in self.CARDS for _ in range(3)]

    def test_a_grid_of_several_rows_places_its_cells_by_the_grid(self) -> None:
        grid = [Region(top=0.2, bottom=0.95, flow=Flow.GRID, splits=(0.345, 0.655),
                       rows=3)]
        assert frames(self.cards(), self.CARDS, grid) == [None] * 9


class TestGroups:
    """`rhythm.groups` — Zones that continue one another down a lane."""

    def column(self, lower_top: int = 90) -> tuple[np.ndarray, list[Zone]]:
        """Three lines 14px apart, then two more starting at `lower_top`."""
        image = page()
        for top in (40, 54, 68):
            printed(image, 20, 200, top)
        for top in (lower_top, lower_top + 14):
            printed(image, 20, 200, top)
        return image, [prose("upper", box(20, 40, 200, 76)),
                       prose("lower", box(20, lower_top, 200, lower_top + 22))]

    def test_a_paragraph_set_a_line_below_continues_the_one_above(self) -> None:
        image, zones = self.column()
        assert groups(image, zones, ONE, [], body=BODY) == [0, 0]

    def test_a_paragraph_set_further_off_does_not(self) -> None:
        image, zones = self.column(lower_top=130)
        assert groups(image, zones, ONE, [], body=BODY) == [None, None]

    def test_a_title_starts_a_run(self) -> None:
        image, zones = self.column()
        zones[1].title = "DECISIONS WANTED"
        assert groups(image, zones, ONE, [], body=BODY) == [None, None]

    def test_a_rule_between_them_parts_them(self) -> None:
        image, zones = self.column()
        assert groups(image, zones, ONE, [83 / SIDE], body=BODY) == [None, None]

    def test_a_zone_sharing_its_row_continues_nothing(self) -> None:
        """`VOL. CLII` sits in the dateline beside the date."""
        image, zones = self.column()
        printed(image, 250, 380, 40)
        zones.append(prose("beside", box(250, 40, 380, 76)))
        assert groups(image, zones, ONE, [], body=BODY) == [None, None, None]

    def test_a_table_continues_nothing(self) -> None:
        image, zones = self.column()
        zones[1].kind = Kind.TABLE
        assert groups(image, zones, ONE, [], body=BODY) == [None, None]


class TestAlignment:
    """`rhythm.alignment` and `title_alignment` — left, centre or right."""

    def test_lines_decide_when_they_agree(self) -> None:
        def lines(*spans: tuple[int, int]) -> list[_Line]:
            return [_Line(i * 14, i * 14 + 8, left, right)
                    for i, (left, right) in enumerate(spans)]

        assert _by_lines(lines((10, 300), (10, 180)), BODY) == LEFT
        assert _by_lines(lines((100, 300), (180, 300)), BODY) == RIGHT
        assert _by_lines(lines((100, 300), (150, 250)), BODY) == CENTRE
        assert _by_lines(lines((10, 300), (26, 200)), BODY) is None
        assert _by_lines(lines((10, 300)), BODY) is None

    def test_a_line_flush_right_in_its_row_is_right(self) -> None:
        """`Q3 2026 · INTERNAL` beside `Platform review`."""
        image = page()
        printed(image, 20, 200, 40)
        printed(image, 300, 380, 40)
        zones = [prose("Platform review", box(20, 40, 200, 48)),
                 prose("Q3 2026", box(300, 40, 380, 48))]
        assert alignment(image, zones, ONE, body=BODY) == [LEFT, RIGHT]

    def test_a_line_centred_on_its_row_is_centred(self) -> None:
        image = page()
        printed(image, 20, 380, 40)
        printed(image, 150, 250, 80)
        zones = [prose("wide", box(20, 40, 380, 48)),
                 prose("THANK YOU", box(150, 80, 250, 88))]
        assert alignment(image, zones, ONE, body=BODY) == [LEFT, CENTRE]

    def test_right_set_lines_flush_right_are_right(self) -> None:
        image = page()
        printed(image, 20, 380, 20)
        printed(image, 260, 380, 60)
        printed(image, 300, 380, 74)
        zones = [prose("wide", box(20, 20, 380, 28)),
                 Zone(kind=Kind.PAIRS, bbox=box(260, 60, 380, 82),
                      complete=True)]
        assert alignment(image, zones, ONE, body=BODY)[1] == RIGHT

    def test_where_a_card_stands_says_nothing_of_its_text(self) -> None:
        image = page()
        printed(image, 20, 200, 40)
        printed(image, 300, 380, 40)
        zones = [prose("left", box(20, 40, 200, 48)),
                 prose("card", box(300, 40, 380, 48), boxed=True)]
        assert alignment(image, zones, ONE, body=BODY)[1] == LEFT

    def test_lines_that_do_not_agree_are_left_wherever_they_sit(self) -> None:
        """A list flush right: its wrapped line is indented past its bullet."""
        image = page()
        printed(image, 20, 200, 40)
        printed(image, 250, 380, 40)
        printed(image, 266, 340, 54)
        zones = [prose("left", box(20, 40, 200, 48)),
                 Zone(kind=Kind.LIST, bbox=box(250, 40, 380, 62), complete=True)]
        assert alignment(image, zones, ONE, body=BODY)[1] == LEFT

    def test_a_title_centred_over_its_column(self) -> None:
        """The menu's `To begin`."""
        image = page()
        printed(image, 150, 250, 40)
        printed(image, 20, 380, 60)
        printed(image, 20, 380, 74)
        zone = prose("dishes", box(20, 40, 380, 82), title="To begin")
        assert title_alignment(image, [zone], body=BODY) == [CENTRE]
        flush = page()
        printed(flush, 20, 120, 40)
        printed(flush, 20, 380, 60)
        zone.bbox = box(20, 40, 380, 68)
        assert title_alignment(flush, [zone], body=BODY) == [LEFT]


def document(zones: list[Zone], **fields: object) -> Document:
    fields.setdefault("regions", [Region(top=0.0, bottom=1.0)])
    return Document(
        source=Source(path="page.png", sha256="0", width=1000, height=1000,
                      rectified_width=1000, rectified_height=1000),
        style=Style(body_px=10.0), zones=zones,
        **fields)  # type: ignore[arg-type]


def body_of(html: str) -> str:
    return html[html.index('<div class="doc">'):html.index('id="doc-ir"')]


def margins(html: str) -> list[int]:
    return [int(m) for m in re.findall(r"margin-bottom:(\d+)px", body_of(html))]


class TestTheGapsAreThePages:
    """`render._stack` — each row followed by the page's own gap."""

    def two(self) -> list[Zone]:
        return [prose("one", BBox(0.1, 0.10, 0.9, 0.20), band=0),
                prose("two", BBox(0.1, 0.25, 0.9, 0.35), band=1)]

    def test_the_ink_gap_less_what_the_stylesheet_draws_round_the_ink(self) -> None:
        expected = 50 - (BELOW_INK["p"] + ABOVE_INK["p"]) * 10
        assert margins(render(document(self.two()))) == [round(expected)]

    def test_a_rule_splits_the_gap_where_it_lies(self) -> None:
        """Since spec 0012, G3a, the rule is one the page draws: its own
        width and colour, at its own height — 219.5 to 220.5 of 1000."""
        rule = Furniture(kind="rule", bbox=BBox(0.1, 0.2195, 0.9, 0.2205),
                         thickness=0.001, color=(10, 20, 30))
        html = body_of(render(document(self.two(), furniture=[rule])))
        assert re.search(r'class="band" style="margin-bottom:13px".*?'
                         r'class="separator" style="border-top:1px solid '
                         r'rgb\(10,20,30\);margin:0 0 26px"', html)

    def test_a_zone_with_no_box_keeps_the_house_gap(self) -> None:
        zones = self.two()
        zones[0].bbox = None
        assert margins(render(document(zones))) == []


class TestRunsAndFrames:
    """`render._unit` and `render._framed`."""

    LANES = [Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.5,))]
    PANEL = BBox(0.55, 0.08, 0.95, 0.50)

    def items(self, text: str, bbox: BBox, **fields: object) -> Zone:
        return Zone(kind=Kind.LIST, bbox=bbox, complete=True,
                    blocks=[Block(kind="item", lines=[cell(text)])],
                    **fields)  # type: ignore[arg-type]

    def risks(self) -> Document:
        fill = (26, 32, 41)
        zones = [prose("main", BBox(0.05, 0.10, 0.45, 0.90)),
                 self.items("one", BBox(0.60, 0.10, 0.90, 0.15),
                            title="OPEN RISKS", fill=fill, frame=self.PANEL,
                            group=1),
                 self.items("two", BBox(0.60, 0.17, 0.90, 0.20), fill=fill,
                            frame=self.PANEL, group=1),
                 self.items("three", BBox(0.60, 0.30, 0.90, 0.35),
                            title="DECISIONS WANTED", fill=fill,
                            frame=self.PANEL)]
        return document(zones, regions=self.LANES)

    def test_a_shared_frame_is_drawn_once_round_its_run(self) -> None:
        html = body_of(render(self.risks()))
        assert html.count('class="frame"') == 1
        frame = html[html.index('class="frame"'):]
        assert frame.index("OPEN RISKS") < frame.index("DECISIONS WANTED")
        assert "filled" not in html and "background:rgb(26,32,41)" in frame

    def test_a_list_run_is_one_list_at_the_pages_spacing(self) -> None:
        html = body_of(render(self.risks()))
        run = html[html.index("OPEN RISKS"):html.index("DECISIONS WANTED")]
        assert run.count("<ul>") == 1
        expected = 20 - (BELOW_INK["li"] + ABOVE_INK["li"]) * 10
        assert f'<li style="margin-top:{round(expected)}px">two</li>' in run

    def test_a_card_in_a_one_row_grid_is_one_framed_stack(self) -> None:
        # Spec 0013 step 3a, `pricing_0017`: drawn band by band, each card's
        # parts sat in rows running across the three, Team's price far
        # below its name. Each lane is one stack, inside its card.
        zones = TestFrames().cards()
        cards = TestFrames.CARDS
        for index, zone in enumerate(zones):
            zone.band, zone.column = [0, 1, 2][index % 3], index // 3
            zone.frame = cards[index // 3]
            zone.fill = (255, 255, 255)
        grid = Region(top=0.2, bottom=0.95, flow=Flow.GRID, splits=(0.345, 0.655))
        html = body_of(render(document(zones, regions=[grid])))
        frames = html.split('class="frame"')[1:]
        assert len(frames) == 3
        for frame, name in zip(frames, ("starter", "team", "business")):
            assert [frame.index(f"{name}{part}") for part in range(3)] == sorted(
                frame.index(f"{name}{part}") for part in range(3))
            assert "background:rgb(255,255,255)" in frame[:frame.index(">")]

    def test_a_button_in_a_card_keeps_its_own_fill(self) -> None:
        # `pricing_0017`'s Team card: white, and its `Start a 14-day trial`
        # button blue. The card is painted white, the button blue.
        zones = TestFrames().cards()
        for index, zone in enumerate(zones):
            zone.band, zone.column = [0, 1, 2][index % 3], index // 3
            zone.frame = TestFrames.CARDS[index // 3]
            zone.fill = (255, 255, 255)
        zones[5].fill = (75, 91, 220)
        grid = Region(top=0.2, bottom=0.95, flow=Flow.GRID, splits=(0.345, 0.655))
        team = body_of(render(document(zones, regions=[grid]))).split('class="frame"')[2]
        assert "background:rgb(255,255,255)" in team[:team.index(">")]
        assert "background:rgb(75,91,220)" in team

    def test_a_frame_paints_the_lane_not_the_lane_itself(self) -> None:
        lane = body_of(render(self.risks())).split('class="lane"')[2]
        assert "background" not in lane[:lane.index(">")]


class TestWhereLinesSit:
    """`Zone.align` and `Zone.title_align`, drawn."""

    def test_right_set_pairs_are_drawn_as_lines(self) -> None:
        zone = Zone(kind=Kind.PAIRS, bbox=BBox(0.6, 0.1, 0.9, 0.2),
                    complete=True, align="right",
                    pairs=[Pair(label=cell("Account"), value=cell("40-21-88"))])
        html = body_of(render(document([zone])))
        assert ('<dl class="pairs lines"><div><dt>Account</dt> '
                '<dd>40-21-88</dd></div></dl>') in html
        assert "text-align:right" in html

    def test_a_flush_right_zone_is_pushed_to_its_rows_end(self) -> None:
        zones = [prose("Platform review", BBox(0.05, 0.04, 0.70, 0.15)),
                 prose("Q3", BBox(0.80, 0.05, 0.96, 0.06), column=1,
                       align="right")]
        html = body_of(render(document(zones)))
        assert "flex:0 1 auto;margin-left:auto" in html
        assert re.search(r"margin-top:10px;flex:0 1 auto", html)

    def test_a_centred_title(self) -> None:
        zone = prose("dishes", BBox(0.1, 0.1, 0.9, 0.3), title="To begin",
                     title_align="centre")
        assert 'text-align:center">To begin</h2>' in render(document([zone]))


def test_the_new_fields_survive_the_round_trip() -> None:
    zone = prose("x", BBox(0.1, 0.1, 0.5, 0.2), frame=BBox(0.0, 0.0, 0.6, 0.3),
                 group=3, align="centre", title_align="right")
    back = Document.from_json(document([zone]).to_json()).zones[0]
    assert (back.frame, back.group, back.align, back.title_align) == (
        BBox(0.0, 0.0, 0.6, 0.3), 3, "centre", "right")
    raw = json.loads(document([prose("x", None)]).to_json())  # type: ignore[arg-type]
    for name in ("frame", "group", "align", "title_align"):
        del raw["zones"][0][name]
    old = Document.from_json(json.dumps(raw)).zones[0]
    assert (old.frame, old.group, old.align, old.title_align) == (None,) * 4
