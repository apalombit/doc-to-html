"""One grouping however the page is pictured — spec 0019, A1.

Softness — resampling, a blur — moves the detector's scores: a container
rises across the 0.40 threshold, its parts fall. `outermost` decided the
grouping on which side of 0.40 a container fell, so the same page grouped
two ways (`tools/layout_front.py --jitter`). These pin the four decisions
taken on what the page shows instead, each on the shape of the page that
made it: cv's sidebar, the ticket's sheet, the timetable's grid, the form's
heading bars.
"""

from __future__ import annotations

import numpy as np

from doc_to_html.engines.detector import (
    CONTAINER_HEIGHT,
    SHEET,
    TRIM,
    Detection,
    LayoutEngine,
    trimmed_to_drawn,
    without_unsure_tall_containers,
)
from doc_to_html.ir import BBox
from doc_to_html.style import outlined


def box(left: float, top: float, right: float, bottom: float,
        label: str = "text", score: float = 0.9) -> Detection:
    return Detection(left=left, top=top, right=right, bottom=bottom,
                     label=label, score=score)


class TestATallContainerLessSureThanItsParts:
    """`cv_0013`'s sidebar, blurred: a `picture` at 0.43 down the whole page
    over sections at 0.85, which `outermost` kept and the sections went."""

    def sidebar(self, score: float, *parts: Detection) -> list[Detection]:
        return [box(0.01, 0.0, 0.34, 1.0, "picture", score), *parts]

    SECTIONS = (box(0.02, 0.05, 0.30, 0.10, "section_header", 0.79),
                box(0.02, 0.12, 0.30, 0.30, "text", 0.85),
                box(0.02, 0.40, 0.30, 0.60, "text", 0.81))

    def test_it_goes_and_its_parts_stand(self) -> None:
        kept = without_unsure_tall_containers(self.sidebar(0.43, *self.SECTIONS))
        assert [d.label for d in kept] == ["section_header", "text", "text"]

    def test_a_container_surer_than_every_part_stays(self) -> None:
        found = self.sidebar(0.90, *self.SECTIONS)
        assert without_unsure_tall_containers(found) == found

    def test_a_short_one_is_a_paragraph_over_its_lines_and_stays(self) -> None:
        """`pricing_0017`'s `text` at 0.53 over its two lines at 0.66 and 0.57."""
        paragraph = box(0.42, 0.34, 0.59, 0.34 + CONTAINER_HEIGHT * 0.4, "text", 0.53)
        found = [paragraph, box(0.42, 0.34, 0.59, 0.37, "text", 0.66),
                 box(0.42, 0.38, 0.59, 0.43, "text", 0.57)]
        assert without_unsure_tall_containers(found) == found

    def test_one_holding_a_graphic_stays(self) -> None:
        """`ticket_0020`'s stub: 0.55 over its heading at 0.57 and its barcode."""
        found = [box(0.74, 0.01, 1.0, 0.99, "picture", 0.55),
                 box(0.81, 0.04, 0.93, 0.08, "section_header", 0.57),
                 box(0.78, 0.87, 0.95, 0.96, "text", 0.48),
                 box(0.81, 0.54, 0.93, 0.85, "picture", 0.46)]
        assert without_unsure_tall_containers(found) == found

    def test_a_picture_with_parts_of_its_own_is_not_a_graphic(self) -> None:
        """`pricing_0017`'s row of cards: each card a picture less sure than
        its list, so the row goes and so does each card."""
        card = box(0.04, 0.26, 0.33, 0.89, "picture", 0.60)
        found = [box(0.03, 0.24, 0.96, 0.89, "picture", 0.52), card,
                 box(0.66, 0.26, 0.96, 0.89, "picture", 0.57),
                 box(0.07, 0.45, 0.31, 0.50, "text", 0.63),
                 box(0.07, 0.55, 0.30, 0.73, "list_item", 0.65),
                 box(0.69, 0.45, 0.91, 0.50, "text", 0.65),
                 box(0.69, 0.55, 0.93, 0.73, "list_item", 0.66)]
        kept = without_unsure_tall_containers(found)
        assert all(d.label != "picture" for d in kept)
        assert len(kept) == 4

    def test_one_part_is_not_a_container_over_parts(self) -> None:
        found = self.sidebar(0.43, self.SECTIONS[1])
        assert without_unsure_tall_containers(found) == found


class TestTheSheet:
    """`ticket_0020`: a `picture` over the whole page, kept or dropped on a
    score difference of a hundredth."""

    def test_a_box_over_the_whole_page_is_never_a_region(self) -> None:
        image = np.full((200, 300, 3), 250, np.uint8)
        image[20:40, 20:120] = 20
        image[120:140, 160:280] = 20
        found = [box(0.0, 0.0, 1.0, 1.0, "picture", 0.95),
                 box(0.06, 0.1, 0.4, 0.2), box(0.53, 0.6, 0.94, 0.7)]

        class Fixed:
            name, license, confidence = "fixed", "n/a", 0.4

            def detect(self, image: np.ndarray) -> list[Detection]:
                return found

        zones = LayoutEngine(Fixed()).detect_zones(image)
        assert len(zones) == 2

    def test_the_bound_sits_between_the_page_and_the_widest_region(self) -> None:
        """Every whole-page box spans 0.99; `form_0007`'s form 0.94 by 0.87."""
        assert 0.87 < SHEET < 0.99


class TestADrawnContainerIsAsLargeAsThePageDrawsIt:
    """`timetable_0019`'s grid, blurred: the detector's box climbs over the
    line printed above the drawn grid and swallows it."""

    GRID = BBox(0.03, 0.20, 0.97, 0.94)

    def test_it_is_cut_back_to_the_outline_and_the_line_above_stands(self) -> None:
        grid = box(0.03, 0.13, 0.97, 0.94, "picture", 0.94)
        line = box(0.03, 0.14, 0.19, 0.16, "text", 0.46)
        out = trimmed_to_drawn([grid], [grid, line], [self.GRID])
        assert out[0].top == self.GRID.top and out[0].label == "picture"
        assert out[1] == line

    def test_a_box_holding_nothing_outside_its_outline_is_left_alone(self) -> None:
        grid = box(0.03, 0.19, 0.97, 0.94, "picture", 0.98)
        cell = box(0.10, 0.30, 0.20, 0.35, "text", 0.5)
        assert trimmed_to_drawn([grid], [grid, cell], [self.GRID]) == [grid]

    def test_a_drawn_box_much_smaller_than_the_container_is_not_its_outline(self) -> None:
        panel = box(0.03, 0.13, 0.97, 0.94, "picture", 0.94)
        small = BBox(0.03, 0.60, 0.97, 0.60 + 0.81 * (TRIM - 0.1))
        line = box(0.03, 0.14, 0.19, 0.16, "text", 0.46)
        assert trimmed_to_drawn([panel], [panel, line], [small]) == [panel]


class TestOutlined:
    """`form_0007`: a field drawn as a grey box with a rule round it, and a
    section heading on a grey bar. Softened, `_bordered` takes both for
    boxes; only one has a line round it."""

    GROUND = (255, 255, 255)

    def picture(self, *, rule: bool, blur: bool) -> tuple[np.ndarray, BBox]:
        import cv2
        image = np.full((120, 400, 3), 255, np.uint8)
        image[40:70, 20:380] = 236
        if rule:
            image[40, 20:380] = image[69, 20:380] = 120
            image[40:70, 20] = image[40:70, 379] = 120
        if blur:
            image = cv2.GaussianBlur(image, (0, 0), 0.6)
        return image, BBox(19 / 400, 39 / 120, 381 / 400, 71 / 120)

    def test_a_field_with_a_rule_round_it_is_outlined(self) -> None:
        for blur in (False, True):
            image, rect = self.picture(rule=True, blur=blur)
            assert outlined(image, rect, ground=self.GROUND)

    def test_a_bar_is_not_however_soft_its_edge(self) -> None:
        for blur in (False, True):
            image, rect = self.picture(rule=False, blur=blur)
            assert not outlined(image, rect, ground=self.GROUND)
