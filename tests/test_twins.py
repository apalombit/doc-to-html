"""`tools/twins.py`, the photographed twins — spec 0018, B0.

A twin is only worth measuring against if its truth is exact: where the
page's corner pixels land, in the coordinates `warp_to_quad` maps from. These
tests draw twins of a small page with a mark in each corner and find the
marks where the truth says they are, carry a box back through the chain the
check uses, and pin how a Zone of the page as shot is counted.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from doc_to_html.ir import BBox, Document, Kind, Source, Zone
from doc_to_html.preprocess import warp_to_quad

REPO = Path(__file__).resolve().parent.parent


def twins() -> ModuleType:
    spec = importlib.util.spec_from_file_location("twins", REPO / "tools" / "twins.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["twins"] = module
    spec.loader.exec_module(module)
    return module


def page() -> np.ndarray:
    """White paper with a black 6px square in each corner."""
    image = np.full((300, 400, 3), 255, np.uint8)
    for top, left in ((0, 0), (0, 394), (294, 394), (294, 0)):
        image[top:top + 6, left:left + 6] = 0
    return image


@pytest.mark.parametrize("label", ["t0.5", "t1.5", "t3", "shade", "persp"])
def test_each_corner_lands_where_the_truth_says(label: str) -> None:
    module = twins()
    picture, truth = module.draw(page(), module.TWINS[label])
    grey = picture.astype(float).mean(axis=2)
    for x, y in truth:
        near = grey[int(round(y)) - 3:int(round(y)) + 4, int(round(x)) - 3:int(round(x)) + 4]
        assert near.min() < 60, f"no mark at the true corner ({x:.1f}, {y:.1f})"


def test_the_twin_carried_back_through_its_truth_is_the_page() -> None:
    import cv2
    module = twins()
    picture, truth = module.draw(page(), module.TWINS["t1.5"])
    onto = np.linalg.inv(module._homography_of(truth, (400, 300)))
    back = cv2.warpPerspective(picture, onto, (400, 300), flags=cv2.INTER_CUBIC)
    assert np.abs(back.astype(int) - page().astype(int)).mean() < 2.0


def test_warp_to_quad_flattens_the_page_one_pixel_short() -> None:
    """Found by the twins, for C2: the target puts the corner pixels at 0
    and w − 1, with w the distance between their centres, so through its
    true corners a page 400 wide comes back 399 wide."""
    module = twins()
    picture, truth = module.draw(page(), module.TWINS["t1.5"])
    assert warp_to_quad(picture, truth.astype(np.float32)).shape[:2] == (299, 399)


def test_the_desk_is_the_desk_and_the_turn_counter_clockwise() -> None:
    module = twins()
    picture, truth = module.draw(page(), module.TWINS["t3"])
    assert tuple(picture[2, 2][::-1]) == module.DESK
    top_left, top_right = truth[0], truth[1]
    assert top_right[1] < top_left[1], "the right end of the top edge rises"


def test_a_shadow_falls_on_the_desk_and_not_on_the_paper() -> None:
    module = twins()
    plain, truth = module.draw(page(), module.TWINS["t1.5"])
    shaded, _ = module.draw(page(), module.TWINS["shade"])
    below = int(round(truth[2][1])) + 8, int(round(truth[2][0])) - 40
    assert shaded[below].mean() < plain[below].mean() - 5
    middle = tuple(int(v) for v in truth.mean(axis=0)[::-1])
    assert shaded[middle].mean() > module.INK_LEVEL


def test_a_box_is_carried_back_to_the_page_as_shot() -> None:
    """The check's chain: the rectified page, by `rectify`'s geometry, to the
    twin's picture, by its truth to the page as shot."""
    module = twins()
    image = page()
    picture, truth = module.draw(image, module.TWINS["t1.5"])
    size = (image.shape[1], image.shape[0])
    onto = np.linalg.inv(module._homography_of(truth, size))
    width, height = picture.shape[1], picture.shape[0]
    corner = truth[0]
    box = BBox(corner[0] / width, corner[1] / height,
               (corner[0] + 1) / width, (corner[1] + 1) / height)
    document = Document(source=Source(path="p.png", sha256="0", width=width, height=height,
                                      rectified_width=width, rectified_height=height),
                        zones=[Zone(kind=Kind.PROSE, bbox=box)])
    [carried] = module.carried(document, onto, size)
    assert carried.left == pytest.approx(0.0, abs=0.01)
    assert carried.top == pytest.approx(0.0, abs=0.01)


def test_a_zone_read_inside_a_larger_one_is_merged_not_lost() -> None:
    """`pricing_0017`'s feature lines, each a Zone as shot and inside its
    card's one Zone on every twin; `form_0007`'s sections, five Zones as
    shot and one on the twin. Read together is not lost — and the number
    says which it was."""
    module = twins()
    shot = [BBox(0.1, 0.1, 0.4, 0.2), BBox(0.1, 0.3, 0.4, 0.4), BBox(0.6, 0.1, 0.9, 0.2)]
    twin = [BBox(0.1, 0.1, 0.4, 0.2), BBox(0.05, 0.25, 0.45, 0.9)]
    assert module.kept(shot, twin) == "1/3 +1 -1"
    assert module.kept(shot, shot) == "3/3"
