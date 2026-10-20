"""A pair's separator, as printed — spec 0019, B4.

On the invoices' own pictures, at the boxes `locate` gives their pairs:
`invoice_0001`'s `Created:` and `Due:`, `invoice_0002`'s
`NO: 554775/R1 | Date: 01/01/2015`, and its `Company Details`, which print
no colon.
"""

from __future__ import annotations

import cv2
import pytest

from doc_to_html import locate, separator
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import BBox, Cell, Document, Kind, Pair, Reading, Source, Zone
from doc_to_html.render import render

pytestmark = pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")


def cell(text: str, box: tuple[float, float, float, float]) -> Cell:
    return Cell(bbox=BBox(*box), readings=[Reading(engine="model", text=text)])


def pairs(name: str, box: tuple[float, float, float, float],
          *entries: tuple[str, tuple[float, float, float, float], str,
                          tuple[float, float, float, float]]) -> tuple[Document, object]:
    zone = Zone(kind=Kind.PAIRS, bbox=BBox(*box), complete=True,
                pairs=[Pair(label=cell(label, at), value=cell(value, where))
                       for label, at, value, where in entries])
    image = cv2.imread(str(SOURCES[name].png_path()))
    height, width = image.shape[:2]
    return Document(source=Source(path=f"{name}.png", sha256="", width=width,
                                  height=height), zones=[zone]), image


def dates(created: str = "Created") -> tuple[Document, object]:
    return pairs("invoice_0001", (0.741, 0.087, 0.949, 0.199),
                 ("Invoice", (0.835, 0.087, 0.894, 0.109), "#: 123", (0.920, 0.087, 0.949, 0.109)),
                 (created, (0.741, 0.129, 0.811, 0.152), "January 1, 2023",
                  (0.817, 0.130, 0.949, 0.157)),
                 ("Due", (0.767, 0.172, 0.803, 0.194), "February 1, 2023",
                  (0.810, 0.172, 0.949, 0.199)))


def number_and_date() -> tuple[Document, object]:
    return pairs("invoice_0002", (0.015, 0.063, 0.256, 0.150),
                 ("NO", (0.015, 0.126, 0.040, 0.145), "554775/R1", (0.046, 0.126, 0.119, 0.145)),
                 ("Date", (0.135, 0.127, 0.171, 0.145), "01/01/2015",
                  (0.177, 0.126, 0.255, 0.145)))


def test_a_colon_the_page_prints_after_a_label_is_kept() -> None:
    document, image = dates()
    separator.read(image, document)
    assert [pair.separator for pair in document.zones[0].pairs] == [None, ":", ":"]


def test_a_bar_between_two_pairs_is_kept() -> None:
    document, image = number_and_date()
    assert separator.read(image, document) == (2, 1)
    found = document.zones[0].pairs
    assert [pair.separator for pair in found] == [":", ":"]
    assert [pair.divider for pair in found] == ["|", None]


def test_labels_printed_bare_stay_bare() -> None:
    document, image = pairs(
        "invoice_0002", (0.028, 0.181, 0.305, 0.428),
        ("Name", (0.132, 0.246, 0.165, 0.261), "Acme Corporation", (0.182, 0.246, 0.287, 0.264)),
        ("Industry", (0.119, 0.274, 0.166, 0.292), "Software Development",
         (0.183, 0.274, 0.305, 0.292)),
        ("Phone", (0.129, 0.330, 0.165, 0.344), "123.4456.4567", (0.184, 0.330, 0.262, 0.344)))
    assert separator.read(image, document) == (0, 0)


def test_a_label_read_with_its_colon_is_not_given_a_second() -> None:
    document, image = dates(created="Created:")
    separator.read(image, document)
    assert document.zones[0].pairs[1].separator is None


def test_reading_twice_reads_the_same() -> None:
    document, image = number_and_date()
    separator.read(image, document)
    once = document.to_json()
    separator.read(image, document)
    assert document.to_json() == once


def test_the_ir_keeps_them_and_omits_them_unset() -> None:
    document, image = number_and_date()
    separator.read(image, document)
    back = Document.from_json(document.to_json())
    assert [(p.separator, p.divider) for p in back.zones[0].pairs] == [(":", "|"), (":", None)]
    plain, _ = number_and_date()
    assert '"separator"' not in plain.to_json() and '"divider"' not in plain.to_json()


def test_drawn_as_printed() -> None:
    document, image = dates()
    separator.read(image, document)
    out = render(document)
    assert "Created:<" in out and "Due:<" in out and "Invoice:" not in out
    document, image = number_and_date()
    separator.read(image, document)
    out = render(document)
    assert "NO:<" in out and "554775/R1 |<" in out and "Date:<" in out
