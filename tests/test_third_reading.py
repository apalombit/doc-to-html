"""The third reading, where the two are near — spec 0019, D2."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from doc_to_html import ladder
from doc_to_html.ir import BBox, Block, Cell, CellState, Document, Kind, Reading, Source, Zone
from doc_to_html.orchestrator import Conversion, EngineSet
from doc_to_html.preprocess import Rectified
from doc_to_html.trace import Disposition
from doc_to_html.wire import contents_into


def cell(model: str, tesseract: str | None, *, placed: bool = True) -> Cell:
    readings = [Reading(engine="ollama", text=model, model="qwen3-vl:4b")]
    if tesseract is not None:
        readings.append(Reading(engine="tesseract", text=tesseract))
    return Cell(bbox=BBox(0.1, 0.1, 0.3, 0.12) if placed else None, readings=readings)


def third(text: str) -> Reading:
    return Reading(engine="ollama", text=text, model="qwen3-vl:4b")


def test_distance() -> None:
    assert ladder.distance("lindwardpharmacy", "lindowpharmacy") == 4
    assert ladder.distance("21008", "21608") == 1
    assert ladder.distance("", "abc") == 3


class TestDue:
    def test_near_readings_are_read_again(self) -> None:
        assert ladder.due(cell("Lindward Pharmacy", "Lindow Pharmacy"))
        assert ladder.due(cell("210.08", "216.08"))

    def test_alike_far_or_lone_readings_are_not(self) -> None:
        assert not ladder.due(cell("1,940.00", "1,940.00"))
        assert not ladder.due(cell("Αγγελίδης Μπραγκαντής Α.Ε.", "Αιγαίο Μηχανική Α.Ε."))
        assert not ladder.due(cell("210.08", None))
        assert not ladder.due(cell("210.08", "216.08", placed=False))

    def test_a_settled_cell_is_not(self) -> None:
        settled = cell("210.08", "216.08")
        settled.state = CellState.RESOLVED
        assert not ladder.due(settled)


class TestSettle:
    def test_siding_with_tesseract_carries_its_text(self) -> None:
        line = cell("210.08", "216.08")
        assert ladder.settle(line, third("216.08"))
        assert line.state is CellState.RESOLVED and line.text == "216.08"
        assert [r.text for r in line.readings] == ["216.08", "210.08", "216.08"]

    def test_siding_with_the_model_keeps_its_text(self) -> None:
        line = cell("quince paste, oat biscuits", "quince paste, oat bisewits")
        assert not ladder.settle(line, third("quince paste, oat biscuits"))
        assert line.state is CellState.RESOLVED and line.text == "quince paste, oat biscuits"

    def test_three_ways_apart_is_disputed_and_the_model_drawn(self) -> None:
        line = cell("m.whitlock@fempost.example", "m.whitlock@fernpost.example")
        assert not ladder.settle(line, third("m.whitlock@tempost.example"))
        assert line.state is CellState.DISPUTED and line.text == "m.whitlock@fempost.example"
        assert len(line.readings) == 3

    def test_siding_with_the_models_words_leaves_its_raised_mark(self) -> None:
        line = cell("²Delta Structural Monitoring BV, Delft",
                    "?Delta Structural Monitoring BV, Delfi")
        assert ladder.due(line)
        assert not ladder.settle(line, third("Delta Structural Monitoring BV, Delft"))
        assert line.state is CellState.RESOLVED
        assert line.text == "²Delta Structural Monitoring BV, Delft"

    def test_agreement_is_folded(self) -> None:
        line = cell("Councilor Ruth", "Councillor Ruth")
        assert ladder.settle(line, third("COUNCILLOR RUTH"))
        assert line.text == "COUNCILLOR RUTH"


# The pass, through a Conversion: one prose question per near Cell, on its
# own box, through the real mapping.

class CellReader:
    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.asked: list[tuple[Kind, BBox | None]] = []

    def extract_zone(self, image: object, zone: Zone,
                     hint: str | None = None, grid: object = None) -> Zone:
        self.asked.append((zone.kind, zone.bbox))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return contents_into(zone, reply, read=lambda t: Reading(engine="ollama", text=t))


def line_of(text: str) -> str:
    return '{"blocks": [{"kind": "paragraph", "lines": ["' + text + '"]}]}'


def climb(*cells: Cell, replies: tuple[str | Exception, ...]
          ) -> tuple[bool, CellReader, Conversion]:
    engine = CellReader(*replies)
    document = Document(source=Source(path="p.png", sha256="", width=400, height=400),
                        zones=[Zone(kind=Kind.PROSE, bbox=BBox(0.05, 0.05, 0.95, 0.5),
                                    complete=True,
                                    blocks=[Block(kind="paragraph", lines=list(cells))])])
    conversion = Conversion(
        source=Path("unused.png"),
        engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                          extract=engine, audit=engine))
    image = np.full((400, 400, 3), 255, dtype=np.uint8)
    moved = conversion._climb_ladders(Rectified(image=image, source=document.source), document)
    return moved, engine, conversion


class TestThePass:
    def test_only_near_cells_are_asked_each_on_its_own_box(self) -> None:
        near, alike = cell("210.08", "216.08"), cell("1,940.00", "1,940.00")
        moved, engine, _ = climb(near, alike, replies=(line_of("216.08"),))
        assert engine.asked == [(Kind.PROSE, near.bbox)]
        assert moved and near.text == "216.08" and near.state is CellState.RESOLVED
        assert alike.state is CellState.AGREED

    def test_a_call_that_raises_costs_that_cell_alone(self) -> None:
        one, other = cell("210.08", "216.08"), cell("Quillton Books", "Quillon Books")
        moved, _, conversion = climb(one, other,
                                     replies=(RuntimeError("timeout"), line_of("Quillon Books")))
        assert one.state is CellState.AGREED and one.text == "210.08"
        assert moved and other.text == "Quillon Books"
        dispositions = [e.disposition for e in conversion.trace.events
                        if e.step == "third reading"]
        assert dispositions == [Disposition.REJECTED, Disposition.ACCEPTED]

    def test_no_near_cell_asks_nothing(self) -> None:
        moved, engine, _ = climb(cell("Total", "Total"), replies=())
        assert not moved and engine.asked == []


def test_the_line_a_drop_cap_is_set_into_is_not_read_again() -> None:
    cap = Cell(readings=[Reading(engine="ollama", text="T")], display="cap",
               bbox=BBox(0.02, 0.1, 0.06, 0.2))
    line = cell("he stretch of towpath", "whe stretch of towpath")
    later = cell("Councilor Ruth", "Councillor Ruth")
    moved, engine, _ = climb(cap, line, later, replies=(line_of("Councillor Ruth"),))
    assert engine.asked == [(Kind.PROSE, later.bbox)]
    assert line.state is CellState.AGREED and moved
