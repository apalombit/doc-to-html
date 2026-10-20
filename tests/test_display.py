"""Display lines — spec 0019, B3.

On `paper_0018`'s own picture, at the boxes `locate` gives its Method
paragraph: the equation `Δh = α √F`, which tesseract cannot place, and its
number `(1)` flush right on its line.
"""

from __future__ import annotations

import cv2
import pytest

from doc_to_html import display
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import BBox, Block, Cell, Document, Kind, Reading, Source, Zone
from doc_to_html.render import render

COLUMN = BBox(0.060, 0.662, 0.477, 0.839)


def line(text: str, box: tuple[float, float, float, float] | None) -> Cell:
    return Cell(bbox=None if box is None else BBox(*box),
                readings=[Reading(engine="model", text=text)])


def method(*, number: bool = True, after: bool = True) -> Document:
    lines = [
        line("Each abutment carried two survey targets read weekly with a total station.",
             (0.077, 0.694, 0.477, 0.715)),
        line("Air temperature was logged hourly, and the frost index F was taken as the",
             (0.060, 0.722, 0.477, 0.739)),
        line("sum of daily mean temperatures below zero. We fitted the relation",
             (0.060, 0.747, 0.412, 0.765)),
        line("Δh = α √F", None),
    ]
    if number:
        lines.append(line("(1)", (0.462, 0.787, 0.477, 0.803)))
    if after:
        lines.append(line("where Δh is the heave in millimetres and α a site coefficient.",
                          (0.076, 0.824, 0.397, 0.846)))
    zone = Zone(kind=Kind.PROSE, bbox=COLUMN, complete=True,
                blocks=[Block(kind="paragraph", lines=lines)])
    return Document(source=Source(path="paper.png", sha256="", width=900, height=659),
                    zones=[zone])


@pytest.fixture(scope="module")
def image():
    return cv2.imread(str(SOURCES["paper_0018"].png_path()))


def test_the_equation_and_its_number_are_found(image) -> None:
    document = method()
    assert display.read(image, document) == 1
    lines = document.zones[0].blocks[0].lines
    assert [cell.display for cell in lines] == [None, None, None, "line", "number", None]


def test_the_last_line_of_a_paragraph_is_never_one(image) -> None:
    document = method(after=False)
    assert display.read(image, document) == 0


def test_reading_twice_reads_the_same(image) -> None:
    document = method()
    display.read(image, document)
    once = document.to_json()
    assert display.read(image, document) == 0
    assert document.to_json() == once


def test_the_ir_keeps_the_flag_and_omits_it_unset(image) -> None:
    document = method()
    display.read(image, document)
    back = Document.from_json(document.to_json())
    assert [cell.display for cell in back.zones[0].blocks[0].lines][3:5] == ["line", "number"]
    assert '"display"' not in method().to_json()


def test_drawn_centred_on_its_own_line_its_number_flush_right(image) -> None:
    document = method()
    display.read(image, document)
    out = render(document)
    assert "relation Δh" not in out and "√F (1)" not in out
    shown = out.split("We fitted the relation")[1].split("where Δh")[0]
    assert "display:flex" in shown and "text-align:center" in shown
    assert shown.index("Δh = α √F") < shown.index("(1)")
