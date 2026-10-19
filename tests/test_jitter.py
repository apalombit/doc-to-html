"""`tools/layout_front.py --jitter`, the jitter check — spec 0019, A0.

The check perturbs a page's picture four ways no reader would see and counts
the page's Zones against the perturbed page's. These tests pin the four
perturbations — same size, deterministic, invisible — and how a Zone is
counted kept, merged or lost.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

from doc_to_html.ir import BBox

REPO = Path(__file__).resolve().parent.parent


def front() -> ModuleType:
    spec = importlib.util.spec_from_file_location("layout_front",
                                                  REPO / "tools" / "layout_front.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["layout_front"] = module
    spec.loader.exec_module(module)
    return module


def page() -> np.ndarray:
    """White paper with two lines of black type-like bars."""
    image = np.full((200, 300, 3), 255, np.uint8)
    image[40:52, 30:270] = 0
    image[120:132, 30:200] = 0
    return image


def test_the_four_perturbations_keep_the_picture_and_its_size() -> None:
    module = front()
    assert list(module.PERTURBATIONS) == ["r98", "r102", "shift", "blur"]
    for label, change in module.PERTURBATIONS.items():
        changed = change(page())
        assert changed.shape == page().shape, label
        assert changed.dtype == np.uint8, label
        # Invisible: the mean grey moves by under a level.
        assert abs(changed.astype(float).mean() - page().astype(float).mean()) < 1.0, label
        assert np.array_equal(changed, change(page())), f"{label} is not deterministic"


def test_the_shift_moves_one_pixel_right_and_down() -> None:
    moved = front().shifted(page())[..., 0]
    assert moved[41, 31:271].max() == 0 and moved[40, 100] == 255 and moved[41, 30] == 255
    assert moved[52, 100] == 0 and moved[53, 100] == 255


def test_a_zone_is_kept_merged_or_lost() -> None:
    module = front()
    zones = [BBox(0.1, 0.1, 0.5, 0.2), BBox(0.1, 0.3, 0.5, 0.4), BBox(0.6, 0.6, 0.9, 0.9)]
    perturbed = [BBox(0.1, 0.1, 0.5, 0.21),          # the first, kept
                 BBox(0.05, 0.25, 0.55, 0.55)]       # a larger one round the second
    assert module.counted(zones, perturbed) == {"zones": 3, "kept": 1, "merged": 1, "lost": 1}


def test_the_table_totals_the_kept_and_names_the_pages_that_regroup() -> None:
    module = front()
    steady = {label: {"zones": 4, "kept": 4, "merged": 0, "lost": 0}
              for label in module.PERTURBATIONS}
    moved = dict(steady, blur={"zones": 4, "kept": 1, "merged": 2, "lost": 1})
    table = module.jitter_table({"a": steady, "b": moved})
    assert "| b | 4/4 | 4/4 | 4/4 | 1/4 +2 -1 |" in table
    assert "**Zones kept: 29 of 32, 0.906**; lost 1" in table
    assert "regroup on at least one perturbation: 1 of 2" in table
