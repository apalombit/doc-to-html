"""Spec 0012, step U — what the page draws, taken into the counts and the lanes.

A table's grid is counted with the page's rules cleared, a dark fill across
it left out of its columns, and its rows and columns as the page rules them;
a box drawn larger than its row's copies is one of them, and a grid's split
never crosses a drawn box; a dashed vertical rule divides lanes.
"""

from __future__ import annotations

import numpy as np

from doc_to_html.furniture import drawn
from doc_to_html.ir import BBox, Furniture
from doc_to_html.preprocess import Drawn, crop, table_grid
from doc_to_html.structure import _broken, _grids


def timetable() -> tuple[np.ndarray, list[Furniture]]:
    """A 200x400 page: a dark header across, then three ruled rows of two
    lines each (a subject and its room), two columns divided by a rule, a
    4px colour bar down the first column's first two rows, and a legend
    line under the last rule."""
    page = np.full((200, 400, 3), 255, np.uint8)
    page[10:30, 10:390] = 40                       # the dark header
    page[14:22, 30:80] = page[14:22, 230:280] = 250  # its white labels
    furniture = [Furniture(kind="fill", bbox=BBox(10 / 400, 10 / 200, 390 / 400, 30 / 200),
                           color=(40, 40, 40))]
    for top in (40, 90, 140):
        for left in (20, 220):
            page[top:top + 10, left:left + 90] = 0        # the subject
            page[top + 14:top + 21, left:left + 60] = 0   # its room
        furniture.append(Furniture(kind="rule", bbox=BBox(10 / 400, (top + 35) / 200,
                                                          390 / 400, (top + 36) / 200),
                                   color=(200, 200, 200), thickness=1 / 400))
    page[180:187, 20:200] = 0                     # the legend
    page[40:125, 12:16] = 30                      # a colour bar down two rows
    furniture.append(Furniture(kind="rule", bbox=BBox(12 / 400, 40 / 200, 16 / 400, 125 / 200),
                               color=(30, 30, 30), thickness=4 / 400))
    furniture.append(Furniture(kind="rule", bbox=BBox(200 / 400, 30 / 200, 201 / 400, 175 / 200),
                               color=(200, 200, 200), thickness=1 / 400))
    furniture.append(Furniture(kind="rule", bbox=BBox(10 / 400, 30 / 200, 11 / 400, 175 / 200),
                               color=(200, 200, 200), thickness=1 / 400))
    return page, furniture


class TestTheGridAsThePageDrawsIt:

    def test_a_ruled_table_counts_its_rows_and_columns(self) -> None:
        page, furniture = timetable()
        box = BBox(10 / 400, 10 / 200, 390 / 400, 190 / 200)
        grid = table_grid(crop(page, box), drawn(furniture, page, box))
        assert (grid.rows, grid.columns) == (5, 2), "header, three rows, legend"

    def test_without_the_drawing_the_bar_and_the_header_decide(self) -> None:
        page, _ = timetable()
        box = BBox(10 / 400, 10 / 200, 390 / 400, 190 / 200)
        grid = table_grid(crop(page, box))
        assert grid.columns == 1, "the dark header is one band across"

    def test_columns_the_page_does_not_rule_are_counted_as_without_it(self) -> None:
        # Spec 0013 step 1: `receipt_0010`, `statement_0006` and `cv_0013`
        # draw no vertical rule, and step U's cleared projection undercounted
        # each by one — a near count, which the model obeyed by dropping a
        # column. With fewer than two rule places the columns are the
        # projection's with nothing cleared; the rows stay as ruled.
        page, furniture = timetable()
        unruled = [f for f in furniture
                   if not (f.kind == "rule" and f.bbox.bottom - f.bbox.top > 0.5)]
        box = BBox(10 / 400, 10 / 200, 390 / 400, 190 / 200)
        grid = table_grid(crop(page, box), drawn(unruled, page, box))
        assert grid.columns == table_grid(crop(page, box)).columns
        assert grid.rows == 5, "header, three rows, legend"

    def test_lines_as_far_apart_as_ruled_rows_stay_rows(self) -> None:
        # `nonlatin_0014`'s totals: ruled items, unruled totals 16px apart.
        ink = np.zeros((120, 100), np.uint8)
        for top in (0, 28, 56, 84, 106):
            ink[top:top + 10, 10:60] = 255
        nothing = np.zeros_like(ink, dtype=bool)
        rows = table_grid(np.dstack([255 - ink] * 3),
                          Drawn(rules=nothing, across=nothing,
                                edges=(19.0, 47.0, 75.0), downs=())).rows
        assert rows == 5


class TestCopiesAndSplits:

    CARD = (0.291, 0.627)

    def card(self, left: float, top: float = 0.262) -> BBox:
        return BBox(left, top, left + self.CARD[0], top + self.CARD[1])

    def test_an_emphasised_middle_card_is_a_copy(self) -> None:
        middle = BBox(0.35, 0.249, 0.65, 0.899)   # 3% larger, centred on the row
        regions = _grids([middle, self.card(0.044), self.card(0.665)])
        assert len(regions) == 1
        assert [round(x, 3) for x in regions[0].splits] == [0.345, 0.655]
        assert regions[0].top == 0.249

    def test_a_split_through_a_drawn_box_is_no_grid(self) -> None:
        middle = BBox(0.30, 0.2, 0.70, 0.95)      # far larger: not a copy
        assert _grids([middle, self.card(0.044), self.card(0.665)]) == []

    def test_a_box_round_the_whole_grid_does_not_stop_it(self) -> None:
        panel = BBox(0.02, 0.2, 0.98, 0.95)
        regions = _grids([panel, self.card(0.044), self.card(0.665)])
        assert len(regions) == 1


class TestADashedRuleDividesLanes:

    def test_only_broken_vertical_rules_are_taken(self) -> None:
        dashed = Furniture(kind="rule", bbox=BBox(0.715, 0.09, 0.718, 0.99),
                           color=(193, 201, 210), style="dashed")
        solid = Furniture(kind="rule", bbox=BBox(0.5, 0.1, 0.501, 0.9),
                          color=(0, 0, 0))
        across = Furniture(kind="rule", bbox=BBox(0.1, 0.5, 0.9, 0.502),
                           color=(0, 0, 0), style="dashed")
        rules = _broken([dashed, solid, across])
        assert [round(rule.x, 4) for rule in rules] == [0.7165]
