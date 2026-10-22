"""Shapes the page draws round type — spec 0019, C3.

A chip printed at the end of a line is drawn on that line
(`sample_css_0004`'s badge after its heading), and a Mark printed on a disc
is drawn as the disc, in its fill, its ink and the ring round it
(`certificate_0021`'s seal).
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from doc_to_html import furniture
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import (BBox, Block, Cell, Document, Furniture, Kind, Look, Reading, Source,
                            Style, Zone)
from doc_to_html.preprocess import rectify
from doc_to_html.render import _on_its_line, render


def line(text: str, box: BBox, look: Look | None = None) -> Cell:
    return Cell(bbox=box, readings=[Reading(engine="model", text=text)], look=look)


def page(*zones: Zone, found: list[Furniture] | None = None) -> Document:
    return Document(source=Source(path="p.png", sha256="", width=1000, height=600),
                    page_px=1000, style=Style(page_bg=(251, 248, 241)),
                    zones=list(zones), furniture=found or [])


def body(document: Document) -> str:
    return render(document).split("<body>", 1)[1]


BADGE = Look(color=(255, 255, 255), fill=(72, 139, 210), chip=BBox(0.322, 0.086, 0.378, 0.135),
             radius=0.1)


class TestAChipOnItsLine:
    def heading(self) -> Block:
        return Block(kind="heading", lines=[line("Sample HTML", BBox(0.046, 0.073, 0.311, 0.119))])

    def test_a_chip_after_a_heading_is_carried_onto_it(self) -> None:
        heading = self.heading()
        badge = Block(kind="item", lines=[line("css", BBox(0.333, 0.099, 0.368, 0.119), BADGE)])
        assert _on_its_line([heading, badge]) == {id(heading): [badge]}

    def test_and_drawn_inside_it_at_the_body_size(self) -> None:
        zone = Zone(kind=Kind.PROSE, bbox=BBox(0.046, 0.073, 0.378, 0.135), complete=True,
                    blocks=[self.heading(), Block(kind="item", lines=[
                        line("css", BBox(0.333, 0.099, 0.368, 0.119), BADGE)])])
        out = body(page(zone))
        heading = out.split("<h1", 1)[1].split("</h1>", 1)[0]
        assert 'class="chip"' in heading and "font-size:var(--body, 1em)" in heading
        assert "<ul>" not in out

    def test_a_chip_on_a_line_below_stays_there(self) -> None:
        heading = self.heading()
        below = Block(kind="item", lines=[line("css", BBox(0.050, 0.150, 0.090, 0.170),
                                               Look(fill=(72, 139, 210),
                                                    chip=BBox(0.040, 0.140, 0.100, 0.180)))])
        assert _on_its_line([heading, below]) == {}

    def test_a_line_on_no_chip_is_not_carried(self) -> None:
        heading = self.heading()
        plain = Block(kind="paragraph", lines=[line("css", BBox(0.333, 0.099, 0.368, 0.119))])
        assert _on_its_line([heading, plain]) == {}

    def test_items_are_left_to_the_list(self) -> None:
        monthly = Block(kind="item", lines=[line("Monthly", BBox(0.40, 0.10, 0.48, 0.12))])
        annual = Block(kind="item", lines=[line("Annual", BBox(0.52, 0.10, 0.58, 0.12), Look(
            fill=(75, 91, 220), chip=BBox(0.50, 0.09, 0.60, 0.13)))])
        assert _on_its_line([monthly, annual]) == {}


class TestADisc:
    def picture(self, *, round_: bool) -> np.ndarray:
        """A 100px disc, a 2px ring 4px clear of it, as Chrome draws the
        seal's CSS: drawn eight times over and shrunk, so its edges blend."""
        scale = 8
        image = np.full((300 * scale, 300 * scale, 3), (241, 248, 251), np.uint8)
        gold = (47, 109, 138)
        if round_:
            middle = 150 * scale
            cv2.circle(image, (middle, middle), 56 * scale, gold, -1)
            cv2.circle(image, (middle, middle), 54 * scale, (241, 248, 251), -1)
            cv2.circle(image, (middle, middle), 50 * scale, gold, -1)
        else:
            image[100 * scale:200 * scale, 100 * scale:200 * scale] = gold
        return cv2.resize(image, (300, 300), interpolation=cv2.INTER_AREA)

    def fill_of(self, image: np.ndarray) -> furniture._Fill:
        rgb = image[:, :, ::-1].astype(np.int64)
        found = furniture._fills(rgb, (251, 248, 241), np.zeros(image.shape[:2], bool), 12.0, [])
        assert len(found) == 1
        return found[0]

    def test_a_round_fill_covers_pi_over_four_and_is_a_disc(self) -> None:
        image = self.picture(round_=True)
        fill = self.fill_of(image)
        record = furniture._fill_record(fill, 300, 300, image[:, :, ::-1].astype(np.int64),
                                        (251, 248, 241), 12.0)
        assert record.disc and record.second == (138, 109, 47)
        assert record.ring is not None
        assert [round(share * 300) for share in record.ring] == [4, 2]

    def test_a_square_fill_is_not(self) -> None:
        image = self.picture(round_=False)
        record = furniture._fill_record(self.fill_of(image), 300, 300,
                                        image[:, :, ::-1].astype(np.int64), (251, 248, 241), 12.0)
        assert not record.disc and record.ring is None


@pytest.mark.parametrize("name, discs", [("certificate_0021", 1), ("invoice_0002", 0)])
def test_the_corpus_discs(name: str, discs: int) -> None:
    """The seal, ringed 4px clear and 2px wide in its own gold, as its CSS
    draws it; `invoice_0002`'s rounded logo, at 0.871 of its box, no disc."""
    rectified = rectify(SOURCES[name].png_path())
    plain = rectified.plain if rectified.plain is not None else rectified.image
    found = [item for item in furniture.find(plain, inverted=rectified.inverted,
                                             read=rectified.image) if item.disc]
    assert len(found) == discs
    if discs:
        width = plain.shape[1]
        assert found[0].ring is not None and found[0].second == found[0].color
        assert [round(share * width) for share in found[0].ring] == [4, 2]


def seal(ringed: bool) -> Document:
    zone = Zone(kind=Kind.FIGURE, graphic_kind="badge", bbox=BBox(0.444, 0.658, 0.556, 0.842),
                complete=True, boxed=True, frame=BBox(0.444, 0.658, 0.556, 0.842),
                blocks=[Block(kind="caption", lines=[
                    line(text, BBox(0.48, top, 0.52, top + 0.02),
                         Look(size=size, color=(251, 248, 241)))
                    for text, top, size in (("GUILD", 0.71, 0.58), ("GTE", 0.74, 1.0),
                                            ("2026", 0.78, 0.58))])])
    disc = Furniture(kind="fill", bbox=BBox(0.451, 0.670, 0.551, 0.833), color=(138, 109, 47),
                     disc=True, second=(138, 109, 47) if ringed else None,
                     ring=(0.004, 0.002) if ringed else None)
    return page(zone, found=[disc])


def test_a_mark_on_a_disc_is_drawn_as_the_disc() -> None:
    out = body(seal(ringed=True))
    mark = out.split('class="mark"', 1)[1].split("</div>", 1)[0]
    assert "border-radius:50%" in mark and "background:rgb(138,109,47)" in mark
    assert "color:rgb(251,248,241)" in mark
    assert "box-shadow:0 0 0 4px rgb(251,248,241),0 0 0 6px rgb(138,109,47)" in mark
    assert [text in mark for text in ("GUILD", "GTE", "2026")] == [True] * 3
    assert "boxed" not in out.split('class="mark"', 1)[0].rsplit("<section", 1)[1]


def test_a_disc_with_no_ring_keeps_the_frame_round_its_zone() -> None:
    out = body(seal(ringed=False))
    assert "box-shadow" not in out
    assert "boxed" in out.split('class="mark"', 1)[0].rsplit("<section", 1)[1]


def test_disc_and_ring_are_written_only_where_set() -> None:
    plain = Furniture(kind="fill", bbox=BBox(0.1, 0.1, 0.2, 0.2))
    assert '"disc"' not in page(found=[plain]).to_json()
    document = seal(ringed=True)
    again = Document.from_json(document.to_json()).furniture[0]
    assert again.disc and again.ring == (0.004, 0.002) and again.second == (138, 109, 47)
