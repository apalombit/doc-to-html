"""The second reading, kept — spec 0019, D1.

`locate` reads every Zone with tesseract to place its Cells; the words
that placed a Cell are a second reading of it, kept as a `Reading` of
engine `tesseract`. No text changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from doc_to_html import locate
from doc_to_html.corpus import REPO, SOURCES
from doc_to_html.ir import BBox, Cell, CellState, Document, Reading
from doc_to_html.render import _cell

sys.path.insert(0, str(REPO / "tools"))
import rederive  # noqa: E402


def word(text: str, left: float, confidence: float = 95.0) -> locate.Word:
    return locate.Word(locate.fold(text), BBox(left, 0.10, left + 0.05, 0.12), (0, 1, 1),
                       confidence, text)


def cell(text: str, state: CellState = CellState.AGREED) -> Cell:
    return Cell(readings=[Reading(engine="ollama", text=text)], state=state)


class TestKept:
    def test_the_run_that_placed_a_cell_is_its_second_reading(self) -> None:
        line = cell("Lindward Pharmacy")
        locate._second(line, [word("Lindow", 0.1), word("Pharmacy", 0.2)])
        assert [(r.engine, r.text) for r in line.readings] == [
            ("ollama", "Lindward Pharmacy"), ("tesseract", "Lindow Pharmacy")]
        assert line.text == "Lindward Pharmacy"

    def test_nothing_is_kept_where_nothing_was_read(self) -> None:
        line = cell("210.08")
        locate._second(line, [])
        assert len(line.readings) == 1

    def test_a_settled_cell_keeps_its_readings(self) -> None:
        for state in (CellState.RESOLVED, CellState.DISPUTED, CellState.CORRECTED):
            line = cell("216.08", state)
            locate._second(line, [word("216.08", 0.1)])
            locate._without_second(line)
            assert len(line.readings) == 1

    def test_placed_again_it_keeps_one(self) -> None:
        line = cell("Quillton Books")
        locate._second(line, [word("Quillon", 0.1), word("Books", 0.2)])
        locate._without_second(line)
        locate._second(line, [word("Quillon", 0.1), word("Books", 0.2)])
        assert [r.engine for r in line.readings] == ["ollama", "tesseract"]

    def test_inside_a_box_no_run_placed_only_sure_words_count(self) -> None:
        box = BBox(0.0, 0.0, 0.5, 0.5)
        found = [word("&ta", 0.2, confidence=31.0), word("216.08", 0.1),
                 word("outside", 0.8)]
        assert [w.raw for w in locate._inside(box, found)] == ["216.08"]


def test_a_cell_draws_its_first_reading() -> None:
    line = cell("210.08")
    line.readings.append(Reading(engine="tesseract", text="216.08"))
    document = Document.from_json('{"source": {"path": "p.png", "sha256": "", '
                                  '"width": 10, "height": 10}, "zones": []}')
    assert _cell(line, document) == "210.08"


@pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")
def test_the_statements_misreads_carry_tesseracts_reading() -> None:
    frozen = REPO / "tests" / "frozen" / "s13-result" / "documents" / "statement_0006.html"
    document = rederive.ir_of(Path(frozen).read_text())
    rederive.rederive(document, SOURCES["statement_0006"].png_path())
    rederive.rederive(document, SOURCES["statement_0006"].png_path())
    seconds = {c.text: [r.text for r in c.readings[1:]] for zone in document.zones
               for c, _ in locate.cells_of(zone)}
    assert seconds["210.08"] == ["216.08"]
    assert seconds["Lindward Pharmacy"] == ["Lindow Pharmacy"]
    assert seconds["Quillton Books"] == ["Quillon Books"]
