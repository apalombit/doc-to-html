"""Raised marks — spec 0019, B2.

(i) on Cells as the model reads `paper_0018`'s authors; (ii) on
`report_0011`'s own picture, at the boxes `locate` gives its lines: the
model dropped `side by side.¹` and set `2027.³` apart as a line `3`.
"""

from __future__ import annotations

import cv2
import pytest

from doc_to_html import locate, raised
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import BBox, Block, Cell, Document, Kind, Reading, Run, Source, Zone
from doc_to_html.render import SUP, render


def line(text: str, box: BBox | None = None) -> Cell:
    return Cell(bbox=box, readings=[Reading(engine="model", text=text)])


def page(*lines: Cell) -> Document:
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.05, 0.1, 0.95, 0.9), complete=True,
                blocks=[Block(kind="paragraph", lines=list(lines))])
    return Document(source=Source(path="p.png", sha256="", width=820, height=1195),
                    zones=[zone])


class TestASuperscriptIsItsOwnRun:
    def test_digits_and_signs_are_marks_and_letters_are_not(self) -> None:
        assert all(raised.superscript(c) for c in "¹²³⁰⁹⁺⁻")
        assert not any(raised.superscript(c) for c in "1a™ªⁿ")

    def test_the_characters_are_kept_and_set_apart(self) -> None:
        document = page(line("Maren Solberg¹, Pieter Achterberg² and Lucia Ferrante¹"))
        raised.read(None, document)
        cell = document.zones[0].blocks[0].lines[0]
        assert cell.text == "Maren Solberg¹, Pieter Achterberg² and Lucia Ferrante¹"
        assert [(r.kind, r.text) for r in cell.runs] == [
            ("text", "Maren Solberg"), ("sup", "¹"), ("text", ", Pieter Achterberg"),
            ("sup", "²"), ("text", " and Lucia Ferrante"), ("sup", "¹")]

    def test_a_marked_run_keeps_its_kind(self) -> None:
        assert raised.split([Run("x²", "code"), Run("a³b")]) == [
            Run("x²", "code"), Run("a"), Run("³", "sup"), Run("b")]

    def test_drawn_raised_once_in_its_plain_form(self) -> None:
        document = page(line("common.¹ The resulting"))
        raised.read(None, document)
        out = render(document)
        assert f'common.<sup style="{SUP}">1</sup> The' in out

    def test_a_cell_without_one_is_untouched(self) -> None:
        document = page(line("No mark here"))
        before = document.to_json()
        raised.read(None, document)
        assert document.to_json() == before


@pytest.fixture(scope="module")
def image():
    return cv2.imread(str(SOURCES["report_0011"].png_path()))


@pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")
class TestAMarkTheReadingLost:
    SIDE = BBox(0.0539, 0.1531, 0.9371, 0.1664)
    CAPITAL = BBox(0.0535, 0.6266, 0.9459, 0.6577)
    PLAIN = BBox(0.0633, 0.9364, 0.4833, 0.9457)

    def test_a_dropped_mark_is_read_off_its_glyph(self, image) -> None:
        document = page(line("so that the two may be read side by side.", self.SIDE))
        assert raised.read(image, document) == 1
        cell = document.zones[0].blocks[0].lines[0]
        assert cell.text == "so that the two may be read side by side.1"
        assert cell.runs[-1] == Run("1", "sup")

    def test_a_mark_set_apart_folds_into_the_line_before(self, image) -> None:
        document = page(line("The lock gate refurbishment has been deferred to 2027.", self.CAPITAL),
                        line("3", BBox(0.0539, 0.6028, 0.0667, 0.6110)))
        assert raised.read(image, document) == 1
        lines = document.zones[0].blocks[0].lines
        assert [cell.text for cell in lines] == [
            "The lock gate refurbishment has been deferred to 2027.3"]
        assert lines[0].runs[-1] == Run("3", "sup")

    def test_a_line_the_page_prints_no_mark_on_is_untouched(self, image) -> None:
        document = page(line("Deferral was agreed at the Board meeting, minute 26/11.", self.PLAIN))
        before = document.to_json()
        assert raised.read(image, document) == 0
        assert document.to_json() == before

    def test_reading_twice_adds_nothing(self, image) -> None:
        document = page(line("so that the two may be read side by side.", self.SIDE))
        raised.read(image, document)
        once = document.to_json()
        assert raised.read(image, document) == 0
        assert document.to_json() == once
