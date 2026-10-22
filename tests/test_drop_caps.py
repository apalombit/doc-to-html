"""Drop caps — spec 0019, C4.

`newsletter_0008` floats a `T` four lines deep at its first story's top
left. The model read `T` as a line of its own, never placed, and the
first line as a heading; the render drew a body-size `The` in an `h1`.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from doc_to_html import dropcap, locate
from doc_to_html.ir import BBox, Block, Cell, Document, Kind, Look, Reading, Source, Style, Zone
from doc_to_html.render import render

WIDTH, HEIGHT = 400, 200


def line(text: str, box: tuple[float, float, float, float] | None,
         look: Look | None = None) -> Cell:
    return Cell(bbox=None if box is None else BBox(*box),
                readings=[Reading(engine="model", text=text)], look=look)


def paragraph() -> Zone:
    """A `T` three lines deep at the top left, three lines beside it and
    one under it, as the model returns them: the cap and the first line a
    heading, the rest a paragraph."""
    return Zone(kind=Kind.PROSE, bbox=BBox(0.05, 0.10, 0.95, 0.80), complete=True, blocks=[
        Block(kind="heading", lines=[line("T", None),
                                     line("he stretch of towpath", (0.20, 0.10, 0.90, 0.20))]),
        Block(kind="paragraph", lines=[
            line("and the old lock will", (0.20, 0.25, 0.90, 0.35)),
            line("reopen to the public on", (0.20, 0.40, 0.90, 0.50)),
            line("the first of October.", (0.05, 0.60, 0.80, 0.70))])])


def picture() -> np.ndarray:
    """The page `paragraph` reads: a heavy `T` 0.05–0.17 across, 0.10–0.48
    down, and grey bars where the lines are."""
    image = np.full((HEIGHT, WIDTH, 3), 250, np.uint8)
    cv2.rectangle(image, (20, 20), (68, 30), (20, 20, 20), -1)           # the bar
    cv2.rectangle(image, (38, 20), (50, 96), (20, 20, 20), -1)           # the stem
    for left, top in ((80, 20), (80, 50), (80, 80), (20, 120)):
        for x in range(left, left + 260, 14):
            cv2.rectangle(image, (x, top + 3), (x + 9, top + 17), (40, 40, 40), -1)
    return image


def test_a_letter_lines_deep_at_the_top_left_is_found() -> None:
    zone = paragraph()
    grey = cv2.cvtColor(picture(), cv2.COLOR_BGR2GRAY)
    box = dropcap.glyph(grey, zone, 0)
    assert box is not None
    assert (round(box.left * WIDTH), round(box.top * HEIGHT)) == (20, 20)
    assert round(box.bottom * HEIGHT) == 97


def test_a_tall_mark_with_nothing_set_beside_it_is_not() -> None:
    zone = paragraph()
    zone.blocks = [Block(kind="paragraph", lines=[line("he stretch", (0.20, 0.10, 0.90, 0.20))])]
    grey = cv2.cvtColor(picture(), cv2.COLOR_BGR2GRAY)
    assert dropcap.glyph(grey, zone, 0) is None


def test_a_rule_at_the_left_is_not_a_letter() -> None:
    image = np.full((HEIGHT, WIDTH, 3), 250, np.uint8)
    cv2.rectangle(image, (20, 20), (22, 120), (20, 20, 20), -1)
    zone = paragraph()
    assert dropcap.glyph(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), zone, 0) is None


def test_the_models_letter_is_placed_and_its_paragraph_made_whole() -> None:
    zone = paragraph()
    document = Document(source=Source(path="p.png", sha256="", width=WIDTH, height=HEIGHT),
                        zones=[zone])
    assert dropcap.read(picture(), document) == 1
    assert [block.kind for block in zone.blocks] == ["paragraph"]
    cap = zone.blocks[0].lines[0]
    assert cap.text == "T" and cap.display == "cap" and cap.bbox is not None
    assert len(zone.blocks[0].lines) == 5
    assert dropcap.read(picture(), document) == 0


def test_a_paragraph_opening_lowercase_has_its_letter_read() -> None:
    if not locate.available():
        pytest.skip("no tesseract on PATH")
    zone = paragraph()
    zone.blocks[0].lines.pop(0)
    document = Document(source=Source(path="p.png", sha256="", width=WIDTH, height=HEIGHT),
                        zones=[zone])
    assert dropcap.read(picture(), document) == 1
    cap = zone.blocks[0].lines[0]
    assert cap.display == "cap" and cap.readings[0].engine == "tesseract"
    assert cap.text == "T"


def test_a_cap_is_drawn_as_the_paragraphs_first_letter() -> None:
    zone = paragraph()
    document = Document(source=Source(path="p.png", sha256="", width=WIDTH, height=HEIGHT),
                        page_px=WIDTH, style=Style(body_px=13.0), zones=[zone])
    dropcap.read(picture(), document)
    cap = zone.blocks[0].lines[0]
    cap.look = Look(size=3.44, bold=True)
    out = render(document)
    assert "p.cap::first-letter" in out
    body = out.split("<body>", 1)[1]
    assert '<p class="cap" style="--cap:calc(3.44 * var(--body, 1em));--cap-weight:700' in body
    # One word in the text, as the page prints it: a float would be a block.
    assert ">The stretch of towpath and the old lock" in body
    assert "<h1" not in body


def test_a_page_with_no_cap_draws_no_rule() -> None:
    zone = paragraph()
    document = Document(source=Source(path="p.png", sha256="", width=WIDTH, height=HEIGHT),
                        page_px=WIDTH, style=Style(body_px=13.0), zones=[zone])
    assert "::first-letter" not in render(document)
