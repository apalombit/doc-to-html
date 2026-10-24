"""The corpus's font allow-list — spec 0020, step 0.

A page names only faces on the list, so the face its HTML declares is the
face its picture shows. These pin that the list on disk is the one the code
measures, and that it still holds on this machine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_to_html import projection
from doc_to_html.factory import fonts

REPO = Path(__file__).resolve().parent.parent
LISTED = REPO / "corpus" / "fonts.json"

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)


class TestTheListOnDisk:
    def test_every_listed_face_is_a_candidate_of_the_same_class(self) -> None:
        listed = fonts.load(LISTED)
        assert listed
        for family, face in listed.items():
            assert family in fonts.CANDIDATES
            assert (face.cls, face.origin) == fonts.CANDIDATES[family]

    def test_each_class_a_page_can_draw_has_several_faces(self) -> None:
        """A style family picks a face per class; one face per class would
        make every serif page the same page."""
        listed = fonts.load(LISTED)
        for cls in fonts.CLASSES:
            assert sum(face.cls == cls for face in listed.values()) >= 5, cls

    def test_every_candidate_left_out_says_why(self) -> None:
        data = json.loads(LISTED.read_text(encoding="utf-8"))
        assert set(data["faces"]) | set(data["left_out"]) == set(fonts.CANDIDATES)


class TestTheSelection:
    def test_a_face_that_lacks_a_glyph_or_does_not_resolve_is_left_out(self) -> None:
        measured = {
            "Georgia": {"resolves": True, "missing": "", "weights": 2},
            "Futura": {"resolves": True, "missing": "€", "weights": 3},
            "Party LET": {"resolves": False, "missing": "", "weights": 1},
        }
        kept = [face.family for face in fonts.allow_list(measured)]
        assert kept == ["Georgia"]

    def test_a_mono_class_must_be_monospaced(self) -> None:
        measured = {
            "Menlo": {"resolves": True, "monospaced": True},
            "Courier": {"resolves": True, "monospaced": False},
            "Georgia": {"resolves": True, "monospaced": True},
        }
        wrong = fonts.check_classes(measured)
        assert len(wrong) == 2
        assert any(line.startswith("Courier") for line in wrong)
        assert any(line.startswith("Georgia") for line in wrong)


class TestItHoldsOnThisMachine:
    @needs_chrome
    def test_every_listed_face_still_resolves_and_covers_the_glyphs(self) -> None:
        listed = fonts.load(LISTED)
        measured = fonts.measure(list(listed))
        broken = {family: found for family, found in measured.items()
                  if not found["resolves"] or found["missing"]}
        assert not broken, (
            f"faces on the list no longer draw as listed: {broken}. "
            "Run tools/corpus_fonts.py --check before shooting any page."
        )
        assert not fonts.check_classes(measured)
