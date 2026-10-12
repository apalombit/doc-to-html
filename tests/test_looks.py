"""How each entry is printed, from its own ink — spec 0011, step 4a.

A synthetic page: body lines drawn with `cv2.putText`, one twice the size,
one with strokes twice as heavy, one sheared 12 degrees — this OpenCV draws
no italic of its own. The corpus check is the sheets.
"""

from __future__ import annotations

import cv2
import numpy as np

from doc_to_html import looks
from doc_to_html.ir import BBox, Block, Cell, Document, Kind, Look, Source, Zone, cell
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
            sheared: bool = False) -> Cell:
        font = cv2.FONT_HERSHEY_SIMPLEX
        (wide, tall), base = cv2.getTextSize(text, font, scale, thick)
        self.y += tall + 2
        y = self.y
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
            cv2.putText(self.image, text, (20, y), font, scale, (0, 0, 0), thick,
                        cv2.LINE_AA)
        entry = cell(text)
        entry.bbox = BBox(18 / WIDTH, (y - tall - 3) / HEIGHT,
                          (wide + 30) / WIDTH, (y + base + 2) / HEIGHT)
        self.y += base + 14
        self.cells.append(entry)
        return entry

    def document(self) -> Document:
        zone = Zone(kind=Kind.PROSE, bbox=BBox(10 / WIDTH, 10 / HEIGHT,
                                               690 / WIDTH, self.y / HEIGHT),
                    complete=True, blocks=[Block(kind="paragraph", lines=self.cells)])
        return Document(source=Source(path="x.png", sha256="0", width=WIDTH,
                                      height=HEIGHT), zones=[zone])


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

    def test_looks_survive_the_ir(self) -> None:
        document = paragraph(Look(size=0.8, bold=None, italic=True))
        again = Document.from_json(document.to_json())
        assert again.zones[0].blocks[0].lines[0].look == Look(size=0.8, italic=True)
