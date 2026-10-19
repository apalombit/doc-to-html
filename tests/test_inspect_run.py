"""`tools/inspect_run.py`, the per-page index — spec 0018, 0c.

Its `01_layout_input` was the Source Image, captioned "the page as the layout
pass saw it", and `02_model_boxes` drew boxes taken in the straightened frame
on that picture, so on the ticket they stood on the desk. The layout pass is
given `Rectified.image`; both panels now show it, and the Source Image keeps
a panel of its own.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from PIL import Image

from doc_to_html.preprocess import rectify

REPO = Path(__file__).resolve().parent.parent


def inspect_run() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "inspect_run", REPO / "tools" / "inspect_run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["inspect_run"] = module
    spec.loader.exec_module(module)
    return module


def test_the_layout_panels_show_the_rectified_page(tmp_path: Path) -> None:
    dump = tmp_path / "ticket_0020"
    dump.mkdir()
    (dump / "zones_used.json").write_text(json.dumps([
        {"kind": "prose", "role": "body", "band": 0, "column": 0,
         "left": 0.1, "top": 0.1, "right": 0.5, "bottom": 0.5}]))
    source = REPO / "example" / "ticket.png"
    out = tmp_path / "out"

    assert inspect_run().main([str(dump), "--source", str(source), "--out", str(out)]) == 0

    rectified = rectify(source).image
    straight = (rectified.shape[1], rectified.shape[0])
    assert Image.open(out / "00_source.png").size == Image.open(source).size
    assert Image.open(out / "01_layout_input.png").size == straight
    assert Image.open(out / "02_model_boxes.png").size == straight
    assert straight != Image.open(source).size, "the ticket is warped"
