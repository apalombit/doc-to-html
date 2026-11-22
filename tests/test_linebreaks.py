"""A reader's line over two printed lines, cut where the page breaks it —
spec 0024, part two, direction 3 (`linebreaks`).

A synthetic page drawn with `cv2.putText`, read by tesseract: each test
places one reader's line on a box and asks whether it is cut, and where.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from doc_to_html import linebreaks, locate
from doc_to_html.ir import (BBox, Block, Cell, Document, Kind, Look, Reading, Run, Source, Zone,
                            cell)

WIDTH, HEIGHT = 640, 200

pytestmark = pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")


def page(*printed: tuple[str, int, int]) -> np.ndarray:
    """A white page with each (text, x, baseline) drawn on it."""
    image = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    for text, x, y in printed:
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2,
                    cv2.LINE_AA)
    return image


def placed(text: str, box: tuple[int, int, int, int], *, runs: list[Run] | None = None
           ) -> tuple[Document, Block]:
    """One reader's line, placed on `box` (pixels), alone in a prose Zone."""
    entry = cell(text)
    if runs is not None:
        entry.readings = [Reading(engine="glm-ocr", text=text, runs=runs)]
    left, top, right, bottom = box
    entry.bbox = BBox(left / WIDTH, top / HEIGHT, right / WIDTH, bottom / HEIGHT)
    block = Block(kind="paragraph", lines=[entry])
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True, blocks=[block])
    return Document(source=Source(path="x.png", sha256="0", width=WIDTH, height=HEIGHT),
                    zones=[zone]), block


def texts(block: Block) -> list[str]:
    return [line.text for line in block.lines]


class TestCutWhereThePageBreaks:
    def test_a_label_over_its_value(self) -> None:
        """c0055's `FULL NAME` over `Priya Raghunathan`, read as one line."""
        image = page(("FULL NAME", 20, 60), ("Priya Raghunathan", 20, 120))
        document, block = placed("FULL NAME Priya Raghunathan", (16, 36, 330, 130))
        assert len(linebreaks.restore(image, document)) == 1
        assert texts(block) == ["FULL NAME", "Priya Raghunathan"]
        first, second = (line.bbox for line in block.lines)
        assert first is not None and second is not None and first.bottom <= second.top

    def test_the_parts_keep_their_marking(self) -> None:
        image = page(("FULL NAME", 20, 60), ("Priya Raghunathan", 20, 120))
        document, block = placed("FULL NAME Priya Raghunathan", (16, 36, 330, 130),
                                 runs=[Run(text="FULL NAME", kind="strong"),
                                       Run(text=" Priya Raghunathan")])
        linebreaks.restore(image, document)
        assert [[(run.text, run.kind) for run in line.runs] for line in block.lines] == [
            [("FULL NAME", "strong")], [("Priya Raghunathan", "text")]]


class TestLeftAsRead:
    def test_one_printed_line_with_its_value_far_along_it(self) -> None:
        """A label and its value on one baseline: tesseract may number them
        as two lines; they stand on one."""
        image = page(("Pay date", 20, 100), ("08/19/2024", 420, 100))
        document, block = placed("Pay date 08/19/2024", (16, 40, 600, 140))
        linebreaks.restore(image, document)
        assert texts(block) == ["Pay date 08/19/2024"]

    def test_words_that_do_not_run_down_the_lines(self) -> None:
        """The reader's order against the page's: the words it matches in
        order stand on one printed line."""
        image = page(("FULL NAME", 20, 60), ("Priya Raghunathan", 20, 120))
        document, block = placed("Priya Raghunathan FULL NAME", (16, 36, 330, 130))
        linebreaks.restore(image, document)
        assert texts(block) == ["Priya Raghunathan FULL NAME"]

    def test_a_line_placed_one_line_tall(self) -> None:
        image = page(("FULL NAME", 20, 60), ("Priya Raghunathan", 20, 120))
        document, block = placed("FULL NAME", (16, 36, 190, 66))
        assert linebreaks.restore(image, document) == []
        assert texts(block) == ["FULL NAME"]


class TestOnePrintedLine:
    def test_words_tesseract_numbers_apart_stand_on_one_line(self) -> None:
        """c0355's `Inês Marques Feixeira`: one printed line, two of
        tesseract's line numbers."""
        words = [locate.Word(text="ines", box=BBox(0.10, 0.40, 0.18, 0.46), line=(1, 1, 1)),
                 locate.Word(text="marques", box=BBox(0.20, 0.40, 0.34, 0.47), line=(1, 1, 2)),
                 locate.Word(text="feixeira", box=BBox(0.36, 0.41, 0.50, 0.46), line=(1, 1, 2))]
        assert [[w.text for w in row] for row in linebreaks._printed_lines(words)] == [
            ["ines", "marques", "feixeira"]]


def cut_block(*looks: Look, kind: str = "paragraph") -> tuple[Document, list[Cell]]:
    """One Block of the parts of one cut line, each measured as `looks`."""
    parts = []
    for number, look in enumerate(looks):
        part = cell(f"Part {number}")
        part.bbox = BBox(0.1, 0.1 + 0.1 * number, 0.6, 0.15 + 0.1 * number)
        part.look = look
        parts.append(part)
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.0, 0.0, 1.0, 1.0), complete=True,
                blocks=[Block(kind=kind, lines=parts)])
    return Document(source=Source(path="x.png", sha256="0", width=WIDTH, height=HEIGHT),
                    zones=[zone]), parts


class TestPartsInAnotherLook:
    def test_a_bold_part_over_a_regular_one_is_a_block_of_its_own(self) -> None:
        """c0444's `Rump of Dorset lamb £24.50`, bold, over its regular
        description: one Block draws them in one look."""
        document, parts = cut_block(Look(bold=True, size=1.0), Look(bold=False, size=1.0))
        assert linebreaks.apart(document, [parts]) == 1
        blocks = document.zones[0].blocks
        assert [[line.text for line in block.lines] for block in blocks] == [["Part 0"], ["Part 1"]]
        assert blocks[1].gap is not None

    def test_a_part_in_another_size_is_a_block_of_its_own(self) -> None:
        """c0148's `INVOICE`, 1.5, over `No. 2026-0418`, 0.9."""
        document, parts = cut_block(Look(bold=False, size=1.5), Look(bold=False, size=0.9))
        assert linebreaks.apart(document, [parts]) == 1

    def test_parts_in_one_look_stay_one_paragraph(self) -> None:
        document, parts = cut_block(Look(bold=False, size=1.0), Look(bold=False, size=1.05))
        assert linebreaks.apart(document, [parts]) == 0
        assert len(document.zones[0].blocks) == 1

    def test_lines_the_reader_gave_apart_are_left(self) -> None:
        """Only the parts of a line `restore` cut: a paragraph's own lines
        in two looks are `render._common_look`'s to judge."""
        document, parts = cut_block(Look(bold=True, size=1.0), Look(bold=False, size=1.0))
        assert linebreaks.apart(document, []) == 0

    def test_a_sentence_going_on_keeps_its_size(self) -> None:
        """c0434's footnote over its last word, `quarter.`, measured 0.75 on
        its `t` alone: the page wrapped the sentence, set in one size."""
        document, parts = cut_block(Look(bold=False, size=1.0), Look(bold=False, size=0.75))
        parts[0].readings = [Reading(engine="glm-ocr", text="the move in wheat from the previous")]
        parts[1].readings = [Reading(engine="glm-ocr", text="quarter.")]
        assert linebreaks.apart(document, [parts]) == 0

    def test_a_label_over_a_value_in_lower_case_is_set_apart(self) -> None:
        """c0504's `E-MAIL`, 0.70, over `d.lockhart@example.com`, 1.00."""
        document, parts = cut_block(Look(bold=False, size=0.7), Look(bold=False, size=1.0))
        parts[0].readings = [Reading(engine="glm-ocr", text="E-MAIL")]
        parts[1].readings = [Reading(engine="glm-ocr", text="d.lockhart@example.com")]
        assert linebreaks.apart(document, [parts]) == 1
