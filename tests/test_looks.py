"""How each entry is printed, from its own ink — spec 0011, steps 4a and 4b.

A synthetic page: body lines drawn with `cv2.putText`, one twice the size,
one with strokes twice as heavy, one sheared 12 degrees — this OpenCV draws
no italic of its own — one in red, one on a dark chip, one on a band
running the page's width. The corpus check is the sheets.
"""

from __future__ import annotations

import cv2
import numpy as np

from doc_to_html import looks
from doc_to_html.ir import (BBox, Block, Cell, Document, Kind, Look, Reading, Row,
                            RowRole, Run, Source, Stroke, Style, Zone, cell)
from doc_to_html.render import SIZE_STEP, render

WIDTH, HEIGHT = 700, 420
BODY = ("Hello there friend of mine", "Another body line here",
        "Third body line for weight")


class Page:
    def __init__(self) -> None:
        self.image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
        self.cells: list[Cell] = []
        self.y = 30

    def put(self, text: str, scale: float = 0.6, thick: int = 1,
            sheared: bool = False, ink: tuple[int, int, int] = (0, 0, 0),
            ground: tuple[int, int, int] | None = None, across: bool = False) -> Cell:
        """One line at `scale`; `ink` and `ground` are BGR, and a ground is a
        chip 6px round the words or, `across`, a band the page's width."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        (wide, tall), base = cv2.getTextSize(text, font, scale, thick)
        self.y += tall + 2
        y = self.y
        if ground is not None:
            left, right = (0, WIDTH) if across else (14, 26 + wide)
            cv2.rectangle(self.image, (left, y - tall - 6), (right, y + base + 4), ground, -1)
        if sheared:
            patch = np.full((tall + base + 8, wide + 40, 3), 255, np.uint8)
            cv2.putText(patch, text, (4, tall + 4), font, scale, (0, 0, 0), thick,
                        cv2.LINE_AA)
            shear = np.tan(np.radians(12))
            matrix = np.array([[1, -shear, shear * (tall + 4)], [0, 1, 0]], dtype=np.float32)
            leaned = cv2.warpAffine(patch, matrix, (patch.shape[1], patch.shape[0]),
                                    borderValue=(255, 255, 255))
            self.image[y - tall - 4:y + base + 4, 16:16 + patch.shape[1]] = leaned
        else:
            cv2.putText(self.image, text, (20, y), font, scale, ink, thick, cv2.LINE_AA)
        entry = cell(text)
        entry.bbox = BBox(18 / WIDTH, (y - tall - 3) / HEIGHT,
                          (wide + 22) / WIDTH, (y + base + 2) / HEIGHT)
        self.y += base + 14
        self.cells.append(entry)
        return entry

    def document(self) -> Document:
        zone = Zone(kind=Kind.PROSE, bbox=BBox(10 / WIDTH, 10 / HEIGHT,
                                               690 / WIDTH, self.y / HEIGHT),
                    complete=True, blocks=[Block(kind="paragraph", lines=self.cells)])
        return Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                      height=HEIGHT), zones=[zone],
                        style=Style(ink=(0, 0, 0)))


def body_page() -> Page:
    page = Page()
    for text in BODY:
        page.put(text)
    return page


class TestRead:
    def test_a_line_twice_the_body_reads_twice_its_size(self) -> None:
        page = body_page()
        large = page.put("Large Heading", scale=1.2, thick=2)
        looks.read(page.image, page.document())
        assert large.look is not None and large.look.size is not None
        assert 1.8 <= large.look.size <= 2.1
        for body in page.cells[:3]:
            assert body.look is not None and body.look.size is not None
            assert abs(body.look.size - 1.0) < SIZE_STEP

    def test_heavy_strokes_read_bold_and_the_body_regular(self) -> None:
        page = body_page()
        heavy = page.put("Bold body line", thick=2)
        looks.read(page.image, page.document())
        assert heavy.look is not None and heavy.look.bold is True
        assert [c.look.bold for c in page.cells[:3] if c.look] == [False] * 3

    def test_a_sheared_line_reads_italic_and_the_body_upright(self) -> None:
        page = body_page()
        sloped = page.put("Italic body line", sheared=True)
        looks.read(page.image, page.document())
        assert sloped.look is not None and sloped.look.italic is True
        assert [c.look.italic for c in page.cells[:3] if c.look] == [False] * 3

    def test_a_photographed_page_reads_no_weight_and_still_reads_the_rest(self) -> None:
        page = body_page()
        heavy = page.put("Bold body line", thick=2)
        sloped = page.put("Italic body line", sheared=True)
        looks.read(page.image, page.document(), photographed=True)
        assert all(c.look is not None and c.look.bold is None for c in page.cells)
        assert heavy.look is not None and heavy.look.size is not None
        assert sloped.look is not None and sloped.look.italic is True

    def test_a_line_with_no_tall_letter_has_no_size(self) -> None:
        page = body_page()
        low = page.put("a nice ocean swim")
        looks.read(page.image, page.document())
        assert low.look is not None and low.look.size is None

    def test_a_capital_i_stands_as_tall_as_any_capital(self) -> None:
        # A solid 2px stem is a letter, not a bullet: `Invoice` read at its
        # x-height while it was dropped as one.
        page = body_page()
        stem = page.put("Invoice now")
        looks.read(page.image, page.document())
        assert stem.look is not None and stem.look.size is not None
        assert abs(stem.look.size - 1.0) < SIZE_STEP

    def test_a_red_line_reads_red_and_the_body_its_ink(self) -> None:
        page = body_page()
        red = page.put("Paid out 5,772.36", ink=(28, 28, 155))
        looks.read(page.image, page.document())
        assert red.look is not None and red.look.color is not None
        assert sum(abs(a - b) for a, b in zip(red.look.color, (155, 28, 28))) <= 30
        assert all(c.look and c.look.color and sum(c.look.color) <= 30
                   for c in page.cells[:3])
        assert red.look.fill is None

    def test_a_line_on_a_chip_reads_the_chip(self) -> None:
        page = body_page()
        tag = page.put("BR-114", ink=(255, 255, 255), ground=(28, 32, 35))
        looks.read(page.image, page.document())
        assert tag.look is not None and tag.look.fill == (35, 32, 28)
        assert tag.look.color is not None and min(tag.look.color) >= 200
        assert tag.look.chip is not None and tag.bbox is not None
        assert tag.look.chip.left < tag.bbox.left and tag.look.chip.right > tag.bbox.right
        assert tag.look.radius == 0.0

    def test_a_band_across_the_page_is_no_chip_and_its_colour_unread(self) -> None:
        # A shaded row: its ground goes on past the words, and is not the
        # ground the render draws, so neither is taken from it.
        page = body_page()
        row = page.put("Shaded row of the table", ground=(200, 200, 200), across=True)
        looks.read(page.image, page.document())
        assert row.look is not None and row.look.fill is None and row.look.color is None

    def test_a_photographed_page_reads_no_colour(self) -> None:
        page = body_page()
        red = page.put("Paid out 5,772.36", ink=(28, 28, 155))
        tag = page.put("BR-114", ink=(255, 255, 255), ground=(28, 32, 35))
        looks.read(page.image, page.document(), photographed=True)
        assert red.look is not None and red.look.color is None
        assert tag.look is not None and tag.look.fill is None

    def test_a_cell_holding_a_link_reads_no_colour(self) -> None:
        page = body_page()
        line = page.put("Contact: editor@example.com", ink=(238, 0, 0))
        line.readings = [Reading(engine="fixture", text=line.text, runs=[
            Run(text="Contact: "), Run(text="editor@example.com", kind="link")])]
        looks.read(page.image, page.document())
        assert line.look is not None and line.look.color is None

    def test_an_unplaced_cell_has_no_look(self) -> None:
        page = body_page()
        loose = cell("Nowhere on the page")
        page.cells.append(loose)
        looks.read(page.image, page.document())
        assert loose.look is None


def paragraph(*lined: Look | None) -> Document:
    lines = []
    for number, look in enumerate(lined):
        entry = cell(f"Line {number}")
        entry.look = look
        lines.append(entry)
    zone = Zone(kind=Kind.PROSE, complete=True,
                blocks=[Block(kind="paragraph", lines=lines)])
    return Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                  height=HEIGHT), zones=[zone])


class TestDraw:
    def test_a_look_draws_its_size_weight_and_slant(self) -> None:
        html = render(paragraph(Look(size=1.5, bold=True, italic=True)))
        assert ('<p style="font-size:calc(1.50 * var(--body, 1em));'
                'font-weight:700;font-style:italic">') in html

    def test_a_size_near_the_body_is_not_drawn(self) -> None:
        html = render(paragraph(Look(size=1.1, bold=False, italic=False)))
        assert "<p>Line 0</p>" in html

    def test_a_paragraph_takes_the_look_most_of_its_lines_have(self) -> None:
        regular = Look(size=1.0, bold=False, italic=False)
        heavy = Look(size=1.0, bold=True, italic=False)
        assert '<p style="font-weight:700">' in render(paragraph(heavy, heavy, regular))
        assert "<p>" in render(paragraph(heavy, regular, regular))

    def test_a_colour_far_from_the_ink_is_drawn_and_a_near_one_is_not(self) -> None:
        assert "color:rgb(155,28,28)" in render(paragraph(Look(color=(155, 28, 28))))
        near = render(paragraph(Look(color=(40, 40, 40))))
        assert "<p>Line 0</p>" in near

    def test_a_chip_is_a_span_with_the_pages_fill_and_padding(self) -> None:
        entry = cell("BR-114")
        entry.bbox = BBox(43 / WIDTH, 98 / HEIGHT, 79 / WIDTH, 107 / HEIGHT)
        entry.look = Look(color=(255, 255, 255), fill=(35, 32, 28), radius=0.12,
                          chip=BBox(37 / WIDTH, 94 / HEIGHT, 85 / WIDTH, 111 / HEIGHT))
        zone = Zone(kind=Kind.PROSE, complete=True,
                    blocks=[Block(kind="paragraph", lines=[entry])])
        html = render(Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                             height=HEIGHT), zones=[zone]))
        assert ('<span class="chip" style="background:rgb(35,32,28);padding:4px 6px;'
                'border-radius:2px;color:rgb(255,255,255)">BR-114</span>') in html

    def test_looks_survive_the_ir(self) -> None:
        document = paragraph(Look(size=0.8, bold=None, italic=True))
        again = Document.from_json(document.to_json())
        assert again.zones[0].blocks[0].lines[0].look == Look(size=0.8, italic=True)
        chip = Look(color=(255, 255, 255), fill=(35, 32, 28), radius=0.12,
                    chip=BBox(0.1, 0.2, 0.3, 0.4))
        again = Document.from_json(paragraph(chip).to_json())
        assert again.zones[0].blocks[0].lines[0].look == chip


def band(height: int = 14, width: int = 300) -> np.ndarray:
    return np.full((height, width, 3), 255, np.uint8)


class TestLinesBetweenRows:
    """Spec 0011, step 4c: the line in the gap under a row, RGB bands."""

    def test_a_pale_rule_across_the_gap_is_solid(self) -> None:
        gap = band()
        gap[7] = (230, 235, 239)
        line = looks._stroke(gap, 9.0, 1000, coloured=True)
        assert line.kind == "solid" and line.color == (230, 235, 239)
        assert line.width == 0.001

    def test_equal_dashes_are_dashed(self) -> None:
        gap = band()
        for x in range(0, 300, 5):
            gap[7, x:x + 3] = (26, 26, 26)
        assert looks._stroke(gap, 9.0, 1000, coloured=False).kind == "dashed"

    def test_two_rules_with_ground_between_are_double(self) -> None:
        gap = band()
        gap[5] = gap[8] = (0, 0, 0)
        assert looks._stroke(gap, 9.0, 1000, coloured=True).kind == "double"

    def test_two_shades_touching_are_one_line(self) -> None:
        # A photograph's blur splits one rule into two runs of grey.
        gap = band()
        gap[6], gap[7] = (120, 120, 120), (30, 30, 30)
        line = looks._stroke(gap, 9.0, 1000, coloured=True)
        assert line.kind == "solid" and line.color == (30, 30, 30)
        assert line.width == 0.002

    def test_a_fill_reaching_into_the_gap_is_no_line(self) -> None:
        # `statement_0006`'s header bar runs 6px into the gap under it.
        gap = band()
        gap[:6] = (43, 32, 22)
        assert looks._stroke(gap, 9.0, 1000, coloured=True).kind == "none"

    def test_the_edge_of_a_stripe_is_no_line(self) -> None:
        gap = band()
        gap[:7] = (249, 247, 244)
        assert looks._stroke(gap, 9.0, 1000, coloured=True).kind == "none"

    def test_a_row_of_words_is_no_line(self) -> None:
        gap = band()
        cv2.putText(gap, "AID A000000031010", (10, 12), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (0, 0, 0), 1, cv2.LINE_AA)
        assert looks._stroke(gap, 9.0, 1000, coloured=True).kind == "none"


def striped_table() -> tuple[np.ndarray, Document]:
    """Four rows, RGB: a dark header bar, then white, a stripe, white; a pale
    rule under each data row."""
    image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    rows = []
    for number in range(4):
        top = 40 + number * 30
        if number == 0:
            image[top - 6:top + 22] = (22, 32, 43)
        elif number == 2:
            image[top - 6:top + 22] = (244, 247, 249)
        if number:
            image[top + 22] = (230, 235, 239)
        entry = cell(f"Row {number}")
        entry.bbox = BBox(20 / WIDTH, top / HEIGHT, 120 / WIDTH, (top + 14) / HEIGHT)
        rows.append(Row(cells=[entry], role=RowRole.HEADER if number == 0 else RowRole.DATA))
    zone = Zone(kind=Kind.TABLE, bbox=BBox(10 / WIDTH, 30 / HEIGHT, 690 / WIDTH, 160 / HEIGHT),
                complete=True, rows=rows)
    return image, Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                         height=HEIGHT), zones=[zone])


class TestRows:
    def test_each_row_reads_its_line_and_its_ground(self) -> None:
        image, document = striped_table()
        looks._rows(image, document, 9.0, coloured=True)
        rows = document.zones[0].rows
        assert [r.fill for r in rows] == [(22, 32, 43), None, (244, 247, 249), None]
        assert [r.under.kind if r.under else None for r in rows] == [
            "none", "solid", "solid", "solid"]

    def test_a_photograph_reads_the_lines_and_not_their_colours(self) -> None:
        image, document = striped_table()
        looks._rows(image, document, 9.0, coloured=False)
        rows = document.zones[0].rows
        assert [r.fill for r in rows] == [None] * 4
        assert rows[1].under is not None and rows[1].under.kind == "solid"
        assert rows[1].under.color is None

    def test_a_read_table_draws_its_rows_and_drops_the_house_rules(self) -> None:
        under = Stroke(kind="dashed", width=0.002)
        zone = Zone(kind=Kind.TABLE, complete=True, rows=[
            Row(cells=[cell("Till 02")], role=RowRole.HEADER, under=under),
            Row(cells=[cell("Flat white")], under=Stroke(kind="none"), fill=(244, 247, 249)),
            Row(cells=[cell("Auth")], role=RowRole.HEADER)])
        html = render(Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                             height=HEIGHT), zones=[zone]))
        assert '<table class="read">' in html
        assert "table.read th, table.read td { border-bottom:none; }" in html
        assert '<tr style="border-bottom:1px dashed var(--ink)">' in html
        assert '<tr style="background:rgb(244,247,249)">' in html
        # Unread, inside the table: the house rule, and no shade it never had.
        assert '<tr style="border-bottom:1px solid var(--rule)"><th>Auth</th>' in html

    def test_an_unread_table_keeps_the_house_rules(self) -> None:
        zone = Zone(kind=Kind.TABLE, complete=True, rows=[Row(cells=[cell("a")])])
        html = render(Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                             height=HEIGHT), zones=[zone]))
        assert "<table>" in html and "table.read" not in html
