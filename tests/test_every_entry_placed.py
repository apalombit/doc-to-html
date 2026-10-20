"""Every printed entry placed, and every placed entry measured — spec 0019, C1.

Type knocked out of a fill, read on the fill's own crop (`sample_css_0004`'s
badge, `certificate_0021`'s seal); marks placed by their glyphs (the
certificate's stars); heavy display type measured, not taken for a chip
(`ticket_0020`'s `OSL`); and a knocked-out chip's letters measured turned
over.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from doc_to_html import locate, looks
from doc_to_html.corpus import SOURCES
from doc_to_html.ir import BBox, Block, Cell, Kind, Reading, Zone
from doc_to_html.render import _beside

tesseract = pytest.mark.skipif(not locate.available(), reason="no tesseract on PATH")


def picture(name: str) -> np.ndarray:
    return cv2.imread(str(SOURCES[name].png_path()))


def zone(box: tuple[float, float, float, float], *texts: str,
         kind: Kind = Kind.PROSE, graphic: str | None = None) -> Zone:
    return Zone(kind=kind, bbox=BBox(*box), complete=True, graphic_kind=graphic,
                blocks=[Block(kind="paragraph", lines=[
                    Cell(readings=[Reading(engine="model", text=text)]) for text in texts])])


@tesseract
def test_a_badge_beside_a_heading_is_read_off_its_own_fill() -> None:
    image = picture("sample_css_0004")
    header = zone((0.046, 0.073, 0.378, 0.135), "Sample HTML", "css")
    found = locate.fills(image, header, 12.0)
    assert len(found) == 1
    assert [word.text for word in locate.fill_words(image, found[0], glyph=12.0)] == ["css"]


@tesseract
def test_a_seal_is_read_off_its_disc() -> None:
    image = picture("certificate_0021")
    seal = zone((0.444, 0.658, 0.556, 0.842), "GUILD", "GTE", "2026",
                kind=Kind.FIGURE, graphic="badge")
    found = locate.fills(image, seal, 12.0)
    assert len(found) == 1
    words = locate.fill_words(image, found[0], glyph=12.0)
    assert [word.text for word in words] == ["guild", "gte", "2026"]


def test_a_zone_with_no_fill_has_none() -> None:
    image = np.full((200, 400, 3), 250, np.uint8)
    cv2.putText(image, "Plain words", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)
    assert locate.fills(image, zone((0.0, 0.0, 1.0, 1.0), "Plain words"), 12.0) == []


def test_marks_are_placed_on_their_glyphs_in_reading_order() -> None:
    image = np.full((200, 400, 3), 250, np.uint8)
    for x in (150, 200, 250):
        cv2.circle(image, (x, 100), 6, (40, 110, 160), -1)
    stars = zone((0.1, 0.1, 0.9, 0.9), "★", "★", "★")
    placed = locate._from_marks(image, stars, [None, None, None])
    assert all(box is not None for box in placed)
    assert [round((box.left + box.right) / 2 * 400) for box in placed] == [150, 200, 250]


def test_marks_that_do_not_count_alike_stay_unplaced() -> None:
    image = np.full((200, 400, 3), 250, np.uint8)
    for x in (150, 200):
        cv2.circle(image, (x, 100), 6, (40, 110, 160), -1)
    stars = zone((0.1, 0.1, 0.9, 0.9), "★", "★", "★")
    assert locate._from_marks(image, stars, [None, None, None]) == [None, None, None]


class TestAChipIsFramed:
    def test_a_chip_runs_to_its_crops_edge(self) -> None:
        chip = np.ones((20, 60), bool)
        chip[6:14, 10:50] = False            # the knocked-out letters
        assert looks._framed(chip)

    def test_heavy_type_stops_short_of_it(self) -> None:
        heavy = np.zeros((30, 60), bool)
        heavy[2:28, 2:58] = True
        heavy[10:20, 15:25] = heavy[10:20, 35:45] = False
        assert heavy.mean() > looks.CHIP and not looks._framed(heavy)


def test_a_line_whose_hanging_letters_carry_its_baseline_says_nothing() -> None:
    """`Type`: its `T` and `y` touching, three pieces, two hanging."""
    ink = np.zeros((16, 40), bool)
    ink[2:14, 2:14] = True                   # `Ty`, cap top to descender
    ink[5:14, 16:24] = True                  # `p`, x-height to descender
    ink[5:11, 26:34] = True                  # `e`, on the baseline
    assert looks._small_caps(ink, "Type") is None


def test_cells_side_by_side_on_a_line_are_one_printed_line() -> None:
    assert _beside(BBox(0.45, 0.26, 0.46, 0.28), BBox(0.49, 0.26, 0.50, 0.28))
    assert not _beside(BBox(0.45, 0.26, 0.46, 0.28), BBox(0.45, 0.30, 0.46, 0.32))
