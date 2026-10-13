"""Spec 0012, G7 — the type's own features.

A head in small capitals is drawn in small capitals at its capitals' size; a
large italic entry whose letters join is drawn in a script hand; a Zone set
in another face than its page's is drawn in it.
"""

from __future__ import annotations

import re

import numpy as np

from doc_to_html.ir import (BBox, Block, Document, Kind, Look, Role, Source, Style,
                            Zone, cell)
from doc_to_html.looks import _joined, _small_caps
from doc_to_html.render import render


def line(*letters: tuple[int, int, int]) -> np.ndarray:
    """A printed line of letters, each (left, top, bottom) of a 6px-wide
    block, on a 40px band."""
    ink = np.zeros((40, 10 * len(letters) + 10), dtype=bool)
    for left, top, bottom in letters:
        ink[top:bottom, left:left + 6] = True
    return ink


BASE = 30


def word(heights: list[tuple[int, int]]) -> np.ndarray:
    return line(*[(5 + 10 * at, BASE - up, BASE + down) for at, (up, down) in enumerate(heights)])


class TestSmallCapitals:

    def test_a_head_with_no_riser_and_no_hanger_is_in_small_capitals(self) -> None:
        # `To begin`: the T at its capital's height, every other letter at one
        # smaller height — the b does not rise, the g does not hang.
        ink = word([(20, 0), (14, 0), (14, 0), (14, 0), (14, 0), (14, 0), (14, 0)])
        verdict = _small_caps(ink, "To begin")
        assert verdict is not None and verdict[0] and verdict[1] == 20

    def test_a_head_whose_letters_rise_and_hang_is_not(self) -> None:
        ink = word([(20, 0), (10, 0), (20, 0), (10, 0), (10, 5), (10, 0), (10, 0)])
        verdict = _small_caps(ink, "To begin")
        assert verdict is not None and not verdict[0]

    def test_letters_that_cannot_rise_or_hang_say_nothing(self) -> None:
        ink = word([(20, 0)] + [(14, 0)] * 10)
        assert _small_caps(ink, "Main courses") is None


class TestJoinedLetters:

    def test_one_stroke_for_a_word_is_joined(self) -> None:
        ink = np.zeros((30, 80), dtype=bool)
        ink[10:25, 5:70] = True
        assert _joined(ink, "Tomas")

    def test_a_piece_a_letter_is_not(self) -> None:
        assert not _joined(word([(20, 0)] * 5), "Tomas")

    def test_digits_and_slashes_are_not_handwriting(self) -> None:
        ink = np.zeros((30, 80), dtype=bool)
        ink[10:25, 5:70] = True
        assert not _joined(ink, "2 / user / month")


def page(zones: list[Zone]) -> Document:
    return Document(source=Source(path="page.png", sha256="0", width=1000, height=1000,
                                  rectified_width=1000, rectified_height=1000),
                    style=Style(body_px=10.0, face="serif"), zones=zones, page_px=1000)


def styles(html: str) -> list[str]:
    body = html[html.index('<div class="doc"'):html.index('id="doc-ir"')]
    return re.findall(r'style="([^"]*)"', body)


class TestDrawn:

    def test_small_capitals_and_a_script_hand(self) -> None:
        head = cell("From the grill", bbox=BBox(0.1, 0.1, 0.3, 0.12))
        head.look = Look(size=1.1, caps=True)
        name = cell("Tomas Halden", bbox=BBox(0.1, 0.2, 0.3, 0.24))
        name.look = Look(size=2.1, italic=True, face="script")
        zone = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=BBox(0.1, 0.1, 0.3, 0.24),
                    complete=True, blocks=[Block(kind="heading", lines=[head]),
                                           Block(kind="paragraph", lines=[name])])
        drawn = styles(render(page([zone])))
        assert any("font-variant:small-caps" in style for style in drawn)
        assert any("font-family:'Snell Roundhand'" in style for style in drawn)

    def test_a_title_in_small_capitals_and_a_zone_in_its_own_face(self) -> None:
        zone = Zone(kind=Kind.PROSE, role=Role.BODY, bbox=BBox(0.1, 0.1, 0.9, 0.3),
                    complete=True, title="To begin", title_caps=True, face="sans",
                    blocks=[Block(kind="paragraph", lines=[cell("Potted brown shrimp")])])
        html = render(page([zone]))
        assert re.search(r'<h2 class="zone-title" style="[^"]*font-variant:small-caps', html)
        assert re.search(r"<section[^>]*font-family:-apple-system", html)

    def test_the_fields_survive_the_json(self) -> None:
        line_ = cell("S. Okonkwo")
        line_.look = Look(caps=True, face="script")
        zone = Zone(kind=Kind.PROSE, role=Role.BODY, title="To begin", title_caps=True,
                    face="sans", blocks=[Block(kind="heading", lines=[line_])])
        back = Document.from_json(page([zone]).to_json()).zones[0]
        assert back.title_caps and back.face == "sans"
        look = back.blocks[0].lines[0].look
        assert look is not None and look.caps and look.face == "script"
