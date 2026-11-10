"""Spec 0024, B: arm D2's lanes from the parser's own Zones.

Every case is built by hand: no dev page's regions are read here, and no
panel page's ever is."""
from __future__ import annotations

from doc_to_html.ir import BBox, Flow, Kind, Region, Zone
from doc_to_html.parser_first import parted

PAGE = Region(top=0.0, bottom=1.0)


def zone(left: int, top: int, right: int, bottom: int) -> Zone:
    return Zone(kind=Kind.PROSE, bbox=BBox(left / 1000, top / 1000, right / 1000, bottom / 1000))


class TestParted:
    def test_a_column_beside_a_tall_block_is_a_lane(self) -> None:
        # c0011's questions, one Zone each, beside the travel diary.
        zones = [zone(20, 200, 470, 260), zone(20, 270, 470, 330), zone(20, 340, 470, 400),
                 zone(500, 200, 970, 860)]
        found = parted(PAGE, zones)
        assert [(r.top, r.bottom, r.flow) for r in found] == [
            (0.0, 0.2, Flow.SINGLE), (0.2, 0.86, Flow.COLUMNS), (0.86, 1.0, Flow.SINGLE)]
        assert found[1].splits == (0.5,)

    def test_the_split_is_where_the_lane_begins(self) -> None:
        # invoice_0002's logo, far right of the title it stands beside.
        found = parted(PAGE, [zone(10, 50, 230, 100), zone(10, 110, 260, 150),
                              zone(680, 20, 740, 130)])
        assert found[1].splits == (0.68,)

    def test_rows_of_pairs_that_line_up_stay_rows(self) -> None:
        zones = [zone(50, 100, 200, 120), zone(300, 100, 600, 120),
                 zone(50, 130, 200, 150), zone(300, 130, 600, 150)]
        assert parted(PAGE, zones) == [PAGE]

    def test_a_block_across_the_gutter_parts_nothing(self) -> None:
        zones = [zone(20, 200, 470, 260), zone(20, 270, 470, 330),
                 zone(500, 200, 970, 330), zone(20, 300, 970, 320)]
        assert parted(PAGE, zones) == [PAGE]

    def test_a_drawn_strip_round_both_sides_is_one_block(self) -> None:
        # c0112's header: its fields, a gutter apart, on one filled strip.
        zones = [zone(30, 30, 390, 150), zone(500, 40, 640, 60), zone(500, 90, 640, 150)]
        strip = BBox(0.02, 0.02, 0.98, 0.16)
        assert parted(PAGE, zones, [strip]) == [PAGE]
        assert parted(PAGE, zones)[1].flow is Flow.COLUMNS

    def test_two_frames_side_by_side_keep_their_gutter(self) -> None:
        zones = [zone(30, 200, 470, 260), zone(30, 270, 470, 330), zone(510, 200, 970, 860)]
        frames = [BBox(0.02, 0.19, 0.48, 0.92), BBox(0.495, 0.19, 0.98, 0.92)]
        assert parted(PAGE, zones, frames)[1].splits == (0.495,)

    def test_a_region_of_lanes_is_left_as_it_is(self) -> None:
        lanes = Region(top=0.0, bottom=1.0, flow=Flow.COLUMNS, splits=(0.3,))
        assert parted(lanes, [zone(20, 200, 470, 260)]) == [lanes]
