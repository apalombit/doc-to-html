"""Faces and colours, once placed — spec 0019, C5.

C1 placed the certificate's stars and its signature `S. Okonkwo`. The
stars' gold was measured as it stood; the signature's script was missed —
its `O`, `k` and both `o`s stand clear of their neighbours, 0.75 pieces a
letter against `SCRIPT_JOINED`'s 0.6 — and its `S.`'s loose tail read as
a small first part, so it drew as a tiny `s.` before a bold serif name.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from doc_to_html import locate
from doc_to_html.corpus import REPO, SOURCES
from doc_to_html.ir import Cell, Document

sys.path.insert(0, str(REPO / "tools"))
import rederive  # noqa: E402


def derived(name: str) -> Document:
    frozen = REPO / "tests" / "frozen" / "s13-result" / "documents" / f"{name}.html"
    document = rederive.ir_of(Path(frozen).read_text())
    rederive.rederive(document, SOURCES[name].png_path())
    return document


def cells(document: Document) -> dict[str, Cell]:
    return {cell.text: cell for zone in document.zones
            for cell, _ in locate.cells_of(zone)}


@pytest.fixture(scope="module")
def certificate() -> dict[str, Cell]:
    return cells(derived("certificate_0021"))


def test_every_signature_is_script_and_one_size(certificate: dict[str, Cell]) -> None:
    for name in ("S. Okonkwo", "H. Brandt", "Eleanor Ashworth-Reyes"):
        look = certificate[name].look
        assert look is not None and look.face == "script" and look.sizes is None, name


def test_the_stars_are_their_gold(certificate: dict[str, Cell]) -> None:
    stars = [cell for text, cell in certificate.items() if text == "★"]
    assert stars and all(cell.look is not None and cell.look.color == (179, 149, 82)
                         for cell in stars)


def test_italic_type_stays_type() -> None:
    """The newsletter's pull quote, 0.90-1.03 pieces a letter."""
    quote = [cell for text, cell in cells(derived("newsletter_0008")).items()
             if text.startswith(("We found three", "could not have seen"))]
    assert len(quote) == 2
    assert all(cell.look is not None and cell.look.italic and cell.look.face is None
               for cell in quote)
