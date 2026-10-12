"""The marks a page draws for its entries — spec 0011, step 3.

Synthetic pages: a field's box, comb, tick box and rule are drawn 1px wide
with OpenCV, and a printed line is a row of glyph-sized blocks, which
`style.body_glyph` reads as type. The corpus check is `form_0007`'s sheet.
"""

from __future__ import annotations

import re

import cv2
import numpy as np

from doc_to_html.fields import BOX, COMB, LINE, TICK, find, read
from doc_to_html.ir import (BBox, Block, Cell, Document, Kind, Mark, Pair, Row,
                            Source, Zone, cell)
from doc_to_html.render import render

SIDE = 400
GLYPH = 10.0


def page() -> np.ndarray:
    return np.full((SIDE, SIDE, 3), 255, np.uint8)


def at(left: int, top: int, right: int, bottom: int) -> BBox:
    return BBox(left / SIDE, top / SIDE, right / SIDE, bottom / SIDE)


def outline(image: np.ndarray, left: int, top: int, right: int, bottom: int) -> None:
    cv2.rectangle(image, (left, top), (right - 1, bottom - 1), (0, 0, 0), 1)


def rule(image: np.ndarray, left: int, right: int, y: int) -> None:
    image[y:y + 1, left:right] = 0


def printed(image: np.ndarray, left: int, right: int, top: int) -> None:
    """A printed line: L-shaped glyphs 10px tall — a solid block is a tile's
    edge to `style.glyph_height`, not type."""
    for x in range(left, right - 4, 8):
        image[top:top + 10, x:x + 2] = 0
        image[top + 8:top + 10, x:x + 5] = 0


def placed(text: str, box: BBox) -> Cell:
    entry = cell(text)
    entry.bbox = box
    return entry


def document(*zones: Zone) -> Document:
    return Document(source=Source(path="x.png", sha256="0", width=SIDE,
                                  height=SIDE), zones=list(zones))


class TestFind:
    def test_a_value_box_a_comb_a_tick_box_and_a_rule(self) -> None:
        image = page()
        outline(image, 20, 20, 200, 47)          # a value box, 2.7 glyphs tall
        for x in range(20, 116, 24):              # four boxes, 3px apart
            outline(image, x, 80, x + 21, 103)
        outline(image, 20, 140, 34, 154)          # a tick box, ticked
        cv2.line(image, (23, 143), (30, 150), (0, 0, 0), 2)
        cv2.line(image, (30, 143), (23, 150), (0, 0, 0), 2)
        outline(image, 60, 140, 74, 154)          # a tick box, empty
        rule(image, 20, 300, 200)
        marks = find(image, GLYPH)
        assert [m.kind for m in marks] == [BOX, COMB, TICK, TICK, LINE]
        box, comb, ticked, empty, line = marks
        assert box.bbox == at(20, 20, 200, 47)
        assert comb.count == 4
        assert (ticked.ticked, empty.ticked) == (True, False)
        assert line.bbox.right == 300 / SIDE

    def test_letters_and_panels_are_not_marks(self) -> None:
        image = page()
        outline(image, 20, 20, 29, 29)            # letter-sized: 0.9 glyph
        outline(image, 20, 60, 380, 300)          # a panel: 24 glyphs tall
        printed(image, 40, 200, 100)
        image[350:351, 20:50] = 0                 # a rule 3 glyphs long
        assert find(image, GLYPH) == []


def form_page() -> tuple[np.ndarray, Zone]:
    """Two fields: a label over a boxed value, and a label over an empty box."""
    image = page()
    printed(image, 20, 100, 20)
    outline(image, 20, 34, 180, 61)
    printed(image, 25, 120, 42)
    printed(image, 210, 300, 20)
    outline(image, 210, 34, 380, 61)
    zone = Zone(kind=Kind.PAIRS, bbox=at(20, 20, 380, 61), complete=True, pairs=[
        Pair(placed("Family name", at(20, 20, 98, 30)),
             placed("Whitlock", at(25, 42, 118, 52))),
        Pair(placed("Telephone", at(210, 20, 298, 30)), cell(""))])
    return image, zone


class TestRead:
    def test_a_value_in_a_box_and_an_empty_box_under_its_label(self) -> None:
        image, zone = form_page()
        read(image, document(zone))
        assert [[m.kind for m in p.marks] for p in zone.pairs] == [[BOX], [BOX]]
        assert zone.pairs[1].marks[0].bbox.left == 210 / SIDE

    def test_a_list_of_options_beside_tick_boxes_becomes_fields(self) -> None:
        image, form = form_page()
        outline(image, 20, 100, 34, 114)
        cv2.line(image, (23, 103), (30, 110), (0, 0, 0), 2)
        printed(image, 40, 100, 102)
        outline(image, 120, 100, 134, 114)
        printed(image, 140, 200, 102)
        options = Zone(kind=Kind.LIST, bbox=at(20, 100, 200, 114), complete=True,
                       blocks=[Block(kind="item", lines=[
                           placed("Full rowing", at(40, 102, 98, 112)),
                           placed("Social", at(140, 102, 198, 112))])])
        read(image, document(form, options))
        assert options.kind is Kind.PAIRS and not options.blocks
        assert [(p.label.text, p.marks[0].ticked) for p in options.pairs] == [
            ("Full rowing", True), ("Social", False)]

    def test_label_rows_over_boxed_value_rows_become_fields(self) -> None:
        image = page()
        printed(image, 20, 60, 20)
        printed(image, 210, 290, 20)
        outline(image, 20, 34, 180, 61)
        printed(image, 25, 120, 42)
        outline(image, 210, 34, 380, 61)
        zone = Zone(kind=Kind.TABLE, bbox=at(20, 20, 380, 61), complete=True, rows=[
            Row(cells=[placed("Name", at(20, 20, 58, 30)),
                       placed("Relationship", at(210, 20, 288, 30))]),
            Row(cells=[placed("Peter Whitlock", at(25, 42, 118, 52)), cell("")])])
        read(image, document(zone))
        assert zone.kind is Kind.PAIRS and not zone.rows
        assert [(p.label.text, p.value.text) for p in zone.pairs] == [
            ("Name", "Peter Whitlock"), ("Relationship", "")]

    def test_rules_under_a_blank_label_are_its_lines_and_leave_the_separators(self) -> None:
        image, form = form_page()
        printed(image, 20, 200, 100)
        rule(image, 20, 380, 125)
        rule(image, 20, 380, 160)
        medical = Zone(kind=Kind.PAIRS, bbox=at(20, 100, 200, 110), complete=True,
                       pairs=[Pair(placed("Any medical condition", at(20, 100, 198, 110)),
                                   cell(""))])
        doc = document(form, medical)
        doc.separators = [125.5 / SIDE, 160.5 / SIDE, 390 / SIDE]
        read(image, doc)
        assert [m.kind for m in medical.pairs[0].marks] == [LINE, LINE]
        assert doc.separators == [390 / SIDE]
        assert medical.bbox is not None and medical.bbox.bottom == 161 / SIDE

    def test_a_signature_line_sits_over_its_caption(self) -> None:
        image, form = form_page()
        rule(image, 20, 180, 120)
        printed(image, 20, 120, 126)
        sign = Zone(kind=Kind.PAIRS, bbox=at(20, 120, 180, 136), complete=True,
                    pairs=[Pair(placed("Signature", at(20, 126, 118, 136)), cell(""))])
        read(image, document(form, sign))
        assert [m.kind for m in sign.pairs[0].marks] == [LINE]

    def test_a_rule_the_model_read_as_the_value_is_no_signature_line(self) -> None:
        # `form_0007`'s `Ref. ____`, and `Date stamp` centred under it.
        image, form = form_page()
        printed(image, 100, 130, 100)
        rule(image, 140, 200, 109)
        printed(image, 140, 200, 114)
        office = Zone(kind=Kind.PAIRS, bbox=at(100, 100, 200, 124), complete=True, pairs=[
            Pair(placed("Ref.", at(100, 100, 128, 110)), cell("__________")),
            Pair(placed("Date stamp", at(140, 114, 198, 124)), cell(""))])
        read(image, document(form, office))
        assert [p.marks for p in office.pairs] == [[], []]

    def test_a_page_without_marks_keeps_every_pair_bare(self) -> None:
        image = page()
        printed(image, 20, 100, 20)
        printed(image, 150, 250, 20)
        zone = Zone(kind=Kind.PAIRS, bbox=at(20, 20, 250, 30), complete=True, pairs=[
            Pair(placed("Invoice", at(20, 20, 98, 30)), placed("123", at(150, 20, 248, 30)))])
        read(image, document(zone))
        assert zone.pairs[0].marks == [] and zone.bbox == at(20, 20, 250, 30)


class TestDraw:
    def test_fields_are_a_grid_with_their_boxes(self) -> None:
        image, zone = form_page()
        doc = document(zone)
        read(image, doc)
        html = render(doc)
        assert 'class="fields"' in html and 'class="box"' in html
        assert ".fields { display:grid" in html
        assert "Whitlock" in html and "Family name" in html

    def test_a_page_with_no_field_draws_and_styles_none(self) -> None:
        zone = Zone(kind=Kind.PAIRS, bbox=at(20, 20, 250, 30), complete=True,
                    pairs=[Pair(cell("Invoice"), cell("123"))])
        html = render(document(zone))
        assert "fields" not in re.sub(r'<script type="application/json".*?</script>',
                                      "", html, flags=re.S)

    def test_a_ticked_option_is_crossed_and_keeps_the_value_read(self) -> None:
        tick = Mark(kind=TICK, bbox=at(20, 100, 34, 114), ticked=True)
        zone = Zone(kind=Kind.PAIRS, bbox=at(20, 100, 200, 114), complete=True, pairs=[
            Pair(placed("I accept", at(40, 102, 98, 112)), cell("X"), marks=[tick]),
            Pair(placed("Social", at(140, 102, 198, 112)), cell(""),
                 marks=[Mark(kind=TICK, bbox=at(120, 100, 134, 114), ticked=False)])])
        html = render(document(zone))
        assert '<span class="tick on" style="width:14px;height:14px">X</span>' in html
        assert '<span class="tick" style="width:14px;height:14px"></span>' in html

    def test_marks_survive_the_ir(self) -> None:
        image, zone = form_page()
        doc = document(zone)
        read(image, doc)
        again = Document.from_json(doc.to_json())
        assert again.zones[0].pairs[0].marks == zone.pairs[0].marks
