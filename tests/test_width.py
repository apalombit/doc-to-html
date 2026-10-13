"""Spec 0012, G5 — the page's own width, and a photographed page at its
paper's share of the picture.

The margins and the content width come from what the page draws; a sheet in
a picture is recorded with what lies round it, and a frame the page draws is
not a sheet; a cell the page prints under the one before it is drawn under
it, so the page's width does not wrap the line above.
"""

from __future__ import annotations

import re

import numpy as np

from doc_to_html.ir import (BBox, Document, Furniture, Kind, Role, Row, RowRole,
                            Source, Style, Zone, cell)
from doc_to_html.preprocess import paper_box, surround_of
from doc_to_html.render import _measure, _under, render


def page(zones: list[Zone], *, paper: BBox | None = None,
         surround: tuple[int, int, int] | None = None, **fields: object) -> Document:
    return Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                  rectified_width=1000, rectified_height=1000,
                                  paper=paper, surround=surround),
                    style=Style(body_px=10.0), zones=zones, page_px=1000,
                    **fields)  # type: ignore[arg-type]


def prose(box: BBox) -> Zone:
    from doc_to_html.ir import Block
    return Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box, complete=True,
                blocks=[Block(kind="paragraph", lines=[cell("Words", bbox=box)])])


class TestThePaperIsRecorded:

    def test_it_survives_the_json(self) -> None:
        document = page([prose(BBox(0.1, 0.1, 0.9, 0.2))],
                        paper=BBox(0.2, 0.1, 0.8, 0.9), surround=(207, 204, 198))
        back = Document.from_json(document.to_json())
        assert back.source.paper == BBox(0.2, 0.1, 0.8, 0.9)
        assert back.source.surround == (207, 204, 198)

    def test_a_square_quad_is_its_own_box(self) -> None:
        quad = np.array([[100, 50], [300, 50], [300, 250], [100, 250]], dtype=float)
        assert paper_box(quad, 400, 300) == BBox(0.25, round(50 / 300, 5), 0.75,
                                                 round(250 / 300, 5))

    def test_a_sheet_on_grey_has_a_surround(self) -> None:
        image = np.full((100, 100, 3), (198, 204, 207), np.uint8)  # BGR grey
        image[20:80, 30:70] = 255
        quad = np.array([[30, 20], [69, 20], [69, 79], [30, 79]])
        assert surround_of(image, quad) == (207, 204, 198)

    def test_a_frame_drawn_on_the_page_is_not_a_sheet(self) -> None:
        image = np.full((100, 100, 3), (241, 248, 251), np.uint8)
        image[10, 10:90] = image[89, 10:90] = image[10:90, 10] = image[10:90, 89] = 90
        quad = np.array([[10, 10], [89, 10], [89, 89], [10, 89]])
        assert surround_of(image, quad) is None


class TestTheWidthIsThePages:

    def test_the_margins_are_the_pages(self) -> None:
        rules = _measure(page([prose(BBox(0.1, 0.05, 0.85, 0.2))]))
        # Above and below, the page's gap less what CSS draws round the ink.
        assert re.fullmatch(r"body \{ padding:\d+px 150px \d+px 100px; \}", rules[0])
        assert rules[1] == ".doc { max-width:750px; }"

    def test_a_rule_past_the_type_sets_the_width(self) -> None:
        rule = Furniture(kind="rule", bbox=BBox(0.05, 0.3, 0.95, 0.301), thickness=0.001)
        rules = _measure(page([prose(BBox(0.1, 0.05, 0.85, 0.2))], furniture=[rule]))
        assert rules[1] == ".doc { max-width:900px; }"

    def test_a_photographed_page_is_drawn_on_its_surround(self) -> None:
        document = page([prose(BBox(0.1, 0.05, 0.9, 0.2))],
                        paper=BBox(0.2, 0.1, 0.8, 0.9), surround=(59, 65, 72))
        rules = _measure(document)
        assert rules[0] == "body { padding:100px 200px 100px 200px; }"
        assert "background:var(--page-bg)" in rules[1]
        assert rules[2] == "html, body { background:rgb(59,65,72); }"


DISH = BBox(0.526, 0.286, 0.709, 0.307)
"""`menu_0012`'s `Main courses`, as the IR holds it: a description in a
second cell, printed under the dish."""


def dishes() -> Zone:
    rows = [Row(role=RowRole.DATA, cells=[
                cell("Braised shin, bone marrow", bbox=DISH),
                cell("mashed potato, red wine", bbox=BBox(0.525, 0.321, 0.637, 0.339)),
                cell("23.00", bbox=BBox(0.917, 0.286, 0.955, 0.303))]),
            Row(role=RowRole.DATA, cells=[
                cell("Guinea fowl, autumn roots", bbox=BBox(0.526, 0.367, 0.709, 0.388)),
                cell(""), cell("21.50", bbox=BBox(0.917, 0.367, 0.955, 0.385))])]
    return Zone(kind=Kind.TABLE, role=Role.BODY, bbox=BBox(0.525, 0.28, 0.955, 0.39),
                rows=rows, complete=True)


class TestACellPrintedUnderTheOneBefore:

    def test_its_column_is_under(self) -> None:
        assert _under(dishes()) == {1}

    def test_a_cell_beside_is_a_column(self) -> None:
        zone = dishes()
        zone.rows[0].cells[1] = cell("mashed potato", bbox=BBox(0.72, 0.286, 0.8, 0.307))
        assert _under(zone) == set()

    def test_it_is_drawn_in_the_cell_above_on_the_first_lines_baseline(self) -> None:
        html = render(page([dishes()]))
        row = re.search(r'<tr style="vertical-align:baseline"><td[^>]*>(.*?)</td>', html)
        assert row is not None
        assert row.group(1).startswith("Braised shin, bone marrow<div")
        assert "mashed potato, red wine</div>" in row.group(1)
        assert html.count("<td") == 4
