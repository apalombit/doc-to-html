"""Arm D2: GLM-OCR's whole pipeline reads the page; we measure its looks and draw it.

Spec 0023. One page goes:

    picture -> GLM-OCR (its layout model, then its reader; a subprocess in
               its own venv, `tools/glmocr_parse.py`) -> its regions
            -> `adapter.document_of` -> Zones, Blocks, Cells, Rows
            -> `measure`: today's style record, furniture, chrome, type
               sizes, placement and looks, measured off the picture
            -> `render.render`

**Where the line is** (the spec's table): the parser decides what the page
says and how it is grouped; this measures how it looks and draws it. So
none of today's reading passes runs here (detector, classify, extract,
locate's unclaimed lines, spans, raised, display, drop caps, separators,
the third reading), and neither does `rectify`'s straightening: the parser
reads the picture as it is, and `flat` gives the measuring passes the same
picture, unwarped. Today's pipeline is untouched; nothing here is called by
a Conversion.

The parser's regions are recorded beside each page's render, so the
adapter and the looks are re-run over them with no model (`tools/d2.py`).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import furniture, locate, looks, rhythm
from . import style as style_module
from .adapter import document_of
from .ir import BBox, Document, Flow, Kind, Region, RowRole, Zone
from .orchestrator import body_px
from .preprocess import (Rectified, _cv2, caption_band, equalise, figure_pixels,
                         ground_is_dark, header_band, resize_long_edge, sha256_of,
                         zone_pixels, TARGET_LONG_EDGE)
from .ir import Source
from .render import render
from .structure import separators, structure

REPO = Path(__file__).resolve().parent.parent.parent

MODEL = "glm-ocr:latest"
"""The reader, as Ollama serves it. Its dumps are under `dump/glm-ocr_latest/`."""

CONFIG = REPO / "parser" / "glmocr.yaml"
PARSER_PYTHON = Path(os.environ.get("DTH_PARSER_PYTHON",
                                    Path.home() / ".venvs" / "glmocr" / "bin" / "python"))
"""The parser's own Python: `glmocr[selfhosted]` at `0288f96`, kept out of
this project's environment (spec 0023: it needs PyMuPDF, AGPL-3.0)."""

PARSE = REPO / "tools" / "glmocr_parse.py"


def flat(path: Path) -> Rectified:
    """The picture as the parser reads it, for the measuring passes:
    `preprocess.rectify` without its warp and its deskew, so a box on the
    parser's picture is a box on this one. A dark page is still turned over,
    and the equalised and the plain picture are both kept."""
    cv2 = _cv2()
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    height, width = image.shape[:2]
    inverted = ground_is_dark(image)
    if inverted:
        image = 255 - image
    rectified = resize_long_edge(equalise(image), TARGET_LONG_EDGE)
    plain = resize_long_edge(image, TARGET_LONG_EDGE)
    return Rectified(image=rectified, plain=plain, warped=False, inverted=inverted,
                     source=Source(path=str(path), sha256=sha256_of(path), width=width,
                                   height=height, rectified_width=rectified.shape[1],
                                   rectified_height=rectified.shape[0]))


def containers(rectified: Rectified) -> list[BBox]:
    """Every box the page draws round content: its frames, its solid fills,
    and the rectangles `style.rectangles` finds. A hatched fill is a
    picture's texture, not a container."""
    plain = rectified.plain if rectified.plain is not None else rectified.image
    drawn = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    boxes = [item.bbox for item in drawn
             if item.kind == "frame" or (item.kind == "fill" and item.style != "hatched")]
    measured = style_module.measure(plain, inverted=rectified.inverted, read=rectified.image,
                                    without=furniture.mask(drawn, plain.shape))
    boxes += style_module.rectangles(plain, ground=measured.page_bg, inverted=rectified.inverted)
    return boxes


CUT = 0.02
"""How far past a lane's split a Zone may reach, as a share of the page's
width, before the split is said to cut it."""


def uncut(region: Region, zones: Sequence[Zone]) -> Region:
    """A region of lanes that cuts through one of the parser's blocks is
    drawn as one flow. `structure` reads lanes off the page's gutters, and
    the parser decides what is one block: pricing's three cards, one picture
    region to the parser, were drawn in one lane of the grid their gutters
    made, at a third of their width."""
    if region.flow is Flow.SINGLE or not region.splits:
        return region
    for zone in zones:
        box = zone.bbox
        if box is None or not region.holds(box):
            continue
        if any(box.left + CUT < split < box.right - CUT for split in region.splits):
            return Region(top=region.top, bottom=region.bottom)
    return region


def measure(document: Document, rectified: Rectified) -> None:
    """Today's measuring passes over the adapter's IR, in a Conversion's
    order, on the flat picture: the furniture, the palette and the ink;
    each Zone's chrome; the type's sizes; the regions and the rules
    between them; where each Cell sits (`locate.locate`, tesseract as a
    locator only, its words never printed); which Zone holds each rule;
    how the lines sit; how each entry is printed; and each figure's
    pixels."""
    plain = rectified.plain if rectified.plain is not None else rectified.image
    document.page_px = rectified.source.width
    document.furniture = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    document.style = style_module.measure(plain, inverted=rectified.inverted, read=rectified.image,
                                          without=furniture.mask(document.furniture, plain.shape))
    document.regions = [uncut(region, document.zones) for region in structure(
        plain, [z.bbox for z in document.zones if z.bbox is not None],
        ground=document.style.page_bg, inverted=rectified.inverted,
        furniture=document.furniture)]
    drawn = style_module.rectangles(plain, ground=document.style.page_bg,
                                    inverted=rectified.inverted)
    own = style_module.boxes_for([z.bbox for z in document.zones], drawn)
    framed = rhythm.frames(document.zones, drawn, document.regions)
    ink = furniture.grounded(rectified.image, plain, document.furniture,
                             inverted=rectified.inverted,
                             held=[z.bbox for z in document.zones if z.bbox is not None])
    for index, zone in enumerate(document.zones):
        zone.frame = framed[index]
        if zone.bbox is None:
            continue
        read = zone_pixels(ink, zone)
        band = caption_band(read)
        names_a_header = (zone.kind is Kind.TABLE and bool(zone.rows)
                          and zone.rows[0].role is RowRole.HEADER)
        found = style_module.chrome(
            zone_pixels(plain, zone), ground=document.style.page_bg,
            inverted=rectified.inverted,
            title_rows=band.bottom if band is not None and zone.title else 0,
            header_rows=(header_band(read, titled=bool(zone.title))
                         if names_a_header else None),
            bordered=own[index] is not None)
        zone.fill, zone.title_fill, zone.header_fill, zone.boxed = (
            found.fill, found.title_fill, found.header_fill, found.bordered)
        zone.pixels = figure_pixels(rectified, zone) if zone.kind is Kind.FIGURE else None
    sizes = style_module.heading_sizes(plain, document.zones)
    for zone, size in zip(document.zones, sizes):
        for position, block in enumerate(zone.blocks):
            block.size = size if position == 0 else None
    document.style.body_px = body_px(plain, document.zones, rectified.source.width)
    for zone, title in zip(document.zones, style_module.title_sizes(plain, document.zones)):
        zone.title_size = title
    document.separators = separators(plain, document.zones, ground=document.style.page_bg,
                                     inverted=rectified.inverted)
    locate.locate(plain, document)
    furniture.place(document.furniture, document.zones)
    rhythm.read(plain, document)
    looks.read(plain, document, photographed=False, inverted=rectified.inverted)


def from_regions(raw: Sequence[dict[str, Any]], png: Path) -> Document:
    """The parser's regions for one picture, as a measured IR."""
    rectified = flat(png)
    document = document_of(raw, rectified.source, containers(rectified))
    measure(document, rectified)
    return document


def parse(pictures: Sequence[Path], out: Path, *, timeout: float | None = None
          ) -> dict[str, dict[str, Any]]:
    """GLM-OCR over pictures, in one subprocess of the parser's own Python.
    Writes `<out>/<stem>.regions.json` per picture and returns, by stem, the
    regions and the seconds it read the page in."""
    out.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(PARSER_PYTHON), str(PARSE), str(CONFIG), str(out), *map(str, pictures)],
        capture_output=True, text=True, timeout=timeout, cwd=REPO)
    if done.returncode != 0:
        raise RuntimeError(f"the parser failed (exit {done.returncode}): "
                           f"{done.stderr.strip().splitlines()[-1:] or ''}")
    found: dict[str, dict[str, Any]] = {}
    for line in done.stdout.splitlines():
        if not line.startswith("{"):
            continue
        entry = json.loads(line)
        stem = Path(entry["picture"]).stem
        entry["regions"] = json.loads((out / f"{stem}.regions.json").read_text(encoding="utf-8"))
        found[stem] = entry
    return found


def convert(name: str, png: Path, scratch: Path) -> tuple[Document, str, dict[str, Any]]:
    """One page through the whole arm: the parser, the adapter, the
    measuring passes and the renderer. Returns the IR, the HTML, and the
    parser's entry (its regions and seconds)."""
    started = time.perf_counter()
    entry = parse([png], scratch)[png.stem]
    parsed = time.perf_counter()
    document = from_regions(entry["regions"], png)
    html = render(document)
    entry["seconds_after"] = round(time.perf_counter() - parsed, 2)
    entry["seconds_total"] = round(time.perf_counter() - started, 2)
    return document, html, entry


def attempt(name: str, png: Path) -> Any:
    """One page as the batch runner records it (`bakeoff.Attempt`): the
    parser's regions as its one answer, its seconds as the model's, the
    render. A temporary folder holds the parser's output."""
    import tempfile

    from .bakeoff import Attempt, PassTiming

    with tempfile.TemporaryDirectory(prefix="d2-") as scratch:
        try:
            _, html, entry = convert(name, png, Path(scratch))
        except Exception as error:  # noqa: BLE001 — recorded, as a Conversion's is
            return Attempt(fixture=name, model=MODEL, error=f"{type(error).__name__}: {error}")
    regions = json.dumps(entry["regions"], ensure_ascii=False, indent=1)
    return Attempt(fixture=name, model=MODEL,
                   timings=[PassTiming("parse", float(entry["seconds"]))],
                   answers=[("regions", regions, CONFIG.read_text(encoding="utf-8"))],
                   html=html)
