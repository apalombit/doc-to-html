"""Weight as measured, never by element — spec 0019, C2.

A heading, a header cell, a total and a Zone's Title are drawn bold by the
stylesheet; each is drawn regular where its entry measured regular, and
keeps the house weight where nothing was measured.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from doc_to_html import locate
from doc_to_html.corpus import REPO, SOURCES
from doc_to_html.ir import (BBox, Block, Cell, Document, Kind, Look, Reading, Row, RowRole,
                            Source, Zone)
from doc_to_html.render import _look, render


def cell(text: str, bold: bool | None) -> Cell:
    return Cell(bbox=BBox(0.1, 0.1, 0.5, 0.15), readings=[Reading(engine="model", text=text)],
                look=Look(size=1.0, bold=bold))


def page(*zones: Zone) -> Document:
    return Document(source=Source(path="p.png", sha256="", width=800, height=1000),
                    zones=list(zones))


def body(document: Document) -> str:
    return render(document).split("<body>", 1)[1]


class TestTheLook:
    def test_regular_on_a_bold_element_is_drawn_regular(self) -> None:
        assert "font-weight:400" in _look(cell("Annual review", False), bold=True)

    def test_unmeasured_keeps_the_house_weight(self) -> None:
        assert "font-weight" not in _look(cell("Annual review", None), bold=True)

    def test_bold_on_a_bold_element_adds_nothing(self) -> None:
        assert "font-weight" not in _look(cell("Annual review", True), bold=True)

    def test_bold_on_a_regular_element_is_drawn_bold(self) -> None:
        assert "font-weight:700" in _look(cell("Design", True))


def test_a_heading_measured_regular_is_drawn_regular() -> None:
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.1, 0.1, 0.9, 0.2), complete=True,
                blocks=[Block(kind="heading", lines=[cell("Annual review", False)])])
    assert 'font-weight:400' in body(page(zone)).split("Annual review")[0].rsplit("<h1", 1)[1]


def test_a_header_cell_measured_regular_is_drawn_regular() -> None:
    zone = Zone(kind=Kind.TABLE, bbox=BBox(0.1, 0.1, 0.9, 0.5), complete=True,
                rows=[Row(role=RowRole.HEADER, cells=[cell("Time", False), cell("Monday", True)]),
                      Row(cells=[cell("08:40", False), cell("Maths", False)])])
    out = body(page(zone))
    assert "font-weight:400" in out.split(">Time<")[0].rsplit("<th", 1)[1]
    assert "font-weight" not in out.split(">Monday<")[0].rsplit("<th", 1)[1]


def test_a_title_measured_regular_is_drawn_regular_and_kept_in_the_ir() -> None:
    zone = Zone(kind=Kind.PROSE, bbox=BBox(0.1, 0.1, 0.9, 0.3), complete=True,
                title="NORTHGATE MUTUAL", title_bold=False,
                blocks=[Block(kind="paragraph", lines=[cell("Current account", None)])])
    out = body(page(zone))
    assert "font-weight:400" in out.split("NORTHGATE MUTUAL</h2>")[0].rsplit("<h2", 1)[1]
    assert Document.from_json(page(zone).to_json()).zones[0].title_bold is False
    zone.title_bold = None
    assert '"title_bold"' not in page(zone).to_json()


@pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")
def test_a_mark_set_apart_is_folded_before_the_page_is_measured() -> None:
    """`report_0011`'s set-apart `3` was placed on the bold heading `3.`
    and, measured, raised the page's regular weight: its bold table header
    measured regular. Folded first, the header is bold and the title, which
    the page prints regular, is regular."""
    sys.path.insert(0, str(REPO / "tools"))
    import rederive

    frozen = REPO / "tests" / "frozen" / "s13-result" / "documents" / "report_0011.html"
    document = rederive.ir_of(Path(frozen).read_text())
    rederive.rederive(document, SOURCES["report_0011"].png_path())
    table = next(zone for zone in document.zones if zone.kind is Kind.TABLE)
    assert [c.look.bold for c in table.rows[0].cells if c.look] == [True] * 4
    title = document.zones[0].blocks[0].lines[0]
    assert title.text.startswith("Annual review") and title.look.bold is False
