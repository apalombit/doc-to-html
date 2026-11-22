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
import re
import subprocess
import time
from collections import Counter
from dataclasses import replace
from statistics import median
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import checkboxes, furniture, linebreaks, locate, looks, rhythm
from . import style as style_module
from .adapter import FIGURES, document_of, laid_out, line_height, plain, regions_of
from .ir import BBox, Cell, Document, Flow, Kind, Look, Region, RowRole, Zone
from .orchestrator import body_px
from .preprocess import (Rectified, _cv2, caption_band, content_ink, equalise,
                         figure_pixels, ground_is_dark, header_band, resize_long_edge,
                         sha256_of, zone_pixels, TARGET_LONG_EDGE)
from .ir import Source
from .render import SIZE_STEP, render
from .skeleton import Part, skeleton
from .structure import _independent, _marked, _strips, separators, structure
from .style import CONTAINED

REPO = Path(__file__).resolve().parent.parent.parent

MODEL = "glm-ocr:latest"
"""The reader, as Ollama serves it. Its dumps are under `dump/glm-ocr_latest/`."""

CONFIG = REPO / "parser" / "glmocr.yaml"
PARSER_PYTHON = Path.home() / ".venvs" / "glmocr" / "bin" / "python"
"""The parser's own Python: `glmocr[selfhosted]` at `0288f96`, kept out of
this project's environment (spec 0023: it needs PyMuPDF, AGPL-3.0)."""

PARSE = REPO / "tools" / "glmocr_parse.py"
READ = REPO / "tools" / "glmocr_read.py"


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


def parted(region: Region, zones: Sequence[Zone],
           containers: Sequence[BBox] = ()) -> list[Region]:
    """A one-flow region cut into its stretches, each stretch a gutter
    parts into lanes that do not line up drawn as a `columns` region —
    spec 0024, B. `structure` finds lanes at a drawn divider only; the
    detector read a column as one block, the parser reads one block a
    paragraph, so a column of the parser's Zones banded with the tall
    Zone beside it and its second Zone was drawn under it: c0011's
    questions under the travel diary.

    A stretch is a run of Zones down the page, each starting above where
    one before it ends; a gutter is an x none of its Zones reaches
    across; it parts lanes when a Zone on one side stands beside two
    stacked on the other (`structure._independent`), so two rows of
    pairs that line up stay rows. **The split is where the lane's own
    blocks begin**, not the gutter's middle: a lane is drawn from its
    left edge, and invoice_0002's logo, set far right of the title,
    stood at the left of a lane painted with its black. No constant.

    **A Zone inside a drawn container is the container**, as in
    `structure._columns`, and so is one inside a fill or frame the
    page draws (`furniture`): c0112's header is one filled strip, and a
    gutter between its fields parted it into lanes, each painted with
    the strip's padding. c0011's two parts are two frames, and the
    gutter between them stands."""
    if region.flow is not Flow.SINGLE:
        return [region]
    boxes = sorted((zone.bbox for zone in zones
                    if zone.bbox is not None and region.holds(zone.bbox)),
                   key=lambda box: box.top)
    stretches: list[list[BBox]] = []
    for box in boxes:
        if stretches and box.top < max(b.bottom for b in stretches[-1]):
            stretches[-1].append(box)
        else:
            stretches.append([box])
    found: list[Region] = []
    for stretch in stretches:
        splits: list[float] = []
        held = [c for c in containers
                if any(box.overlap_ratio(c) >= CONTAINED for box in stretch)]
        blocks = [box for box in stretch
                  if not any(box.overlap_ratio(c) >= CONTAINED for c in held)] + held
        spans = sorted((box.left, box.right) for box in blocks)
        reach = spans[0][1]
        for left, right in spans[1:]:
            if left > reach:
                x = left
                one = [box for box in stretch if box.right < x]
                other = [box for box in stretch if box.left >= x]
                if _independent(one, other) or _independent(other, one):
                    splits.append(x)
            reach = max(reach, right)
        if splits:
            found.append(Region(top=min(box.top for box in stretch),
                                bottom=max(box.bottom for box in stretch),
                                flow=Flow.COLUMNS, splits=tuple(splits)))
    if not found:
        return [region]
    out: list[Region] = []
    cursor = region.top
    for lanes in found:
        if lanes.top > cursor:
            out.append(Region(top=cursor, bottom=lanes.top))
        out.append(lanes)
        cursor = lanes.bottom
    if cursor < region.bottom:
        out.append(Region(top=cursor, bottom=region.bottom))
    return out


def measure(document: Document, rectified: Rectified,
            frames: Sequence[BBox | None] = ()) -> None:
    """Today's measuring passes over the adapter's IR, in a Conversion's
    order, on the flat picture: the furniture, the palette and the ink;
    each Zone's chrome; the type's sizes; the regions and the rules
    between them; where each Cell sits (`locate.locate`, tesseract as a
    locator only, its words never printed), and a reader's line cut where
    the page breaks it (`linebreaks`); which Zone holds each rule;
    how the lines sit; how each entry is printed; each figure's
    pixels; and the tick boxes the reader does not read (`checkboxes`).
    `frames`, for a page laid out from its skeleton, is each Zone's frame
    from its drawn boxes (spec 0025)."""
    plain = rectified.plain if rectified.plain is not None else rectified.image
    document.page_px = rectified.source.width
    document.furniture = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    document.style = style_module.measure(plain, inverted=rectified.inverted, read=rectified.image,
                                          without=furniture.mask(document.furniture, plain.shape))
    boxes = [z.bbox for z in document.zones if z.bbox is not None]
    drawn = style_module.rectangles(plain, ground=document.style.page_bg,
                                    inverted=rectified.inverted)
    containers = (list(drawn) + _strips(_marked(plain, document.style.page_bg,
                                                rectified.inverted), boxes)
                  + [item.bbox for item in document.furniture
                     if item.kind in ("fill", "frame")])
    # A page laid out from its skeleton keeps the stretches it read there
    # (spec 0025, step 3); a page kept flat reads them as before.
    if not document.regions:
        document.regions = [lanes for region in structure(
            plain, boxes, ground=document.style.page_bg, inverted=rectified.inverted,
            furniture=document.furniture)
            for lanes in parted(uncut(region, document.zones), document.zones, containers)]
    own = style_module.boxes_for([z.bbox for z in document.zones], drawn)
    framed = rhythm.frames(document.zones, drawn, document.regions)
    # A page laid out from its skeleton takes each Zone's frame from its
    # drawn boxes (`adapter._Laid.frames`); a box round one Zone is its own.
    for index, box in enumerate(frames):
        if box is not None:
            framed[index] = box
            if sum(1 for other in frames if other == box) == 1:
                own[index] = box
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
    cuts = linebreaks.restore(plain, document)
    furniture.place(document.furniture, document.zones)
    rhythm.read(plain, document)
    looks.read(plain, document, photographed=False, inverted=rectified.inverted)
    table_sizes(document)
    checkboxes.restore(plain, document)
    linebreaks.apart(document, cuts)


PEERS = 3
"""How many measured Cells a table's role, or one column of it, holds for
their median to be the size they are drawn at (`table_sizes`)."""


def table_sizes(document: Document) -> None:
    """One size per role in a table — spec 0025, 3e. A table sets its
    header in one size, its rows in one, its totals in one; a column may
    set its own (a price larger than its item). Each Cell of a role is
    drawn at the median of its column's Cells of that role, where at least
    `PEERS` are measured, else at the median of the role's, where at least
    `PEERS` are; a Cell no group reaches keeps its own.

    A Cell's size is measured on its own line at a glyph of 8 to 11 pixels,
    in whole pixels, so one pixel is 0.09 to 0.12 of the body, and a Cell
    off by three or four is not rare: c0198's backordered row in grey
    italic and its total row at 0.50 among rows at 1.00, its `Ship` header
    at 0.62 among headers at 1.00, c0439's `Hexagon size` at 0.62 in a
    column at 1.00. The page prints every one at the body's size.

    **A row printed larger keeps its size** (spec 0026, part two (b)):
    where two Cells of a row or more measure `SIZE_STEP` or more above
    their group's size, the page set them large — c0177's `Totale` and
    `3.295,22 €` at 1.67 among rows at 1.00 — and each keeps its own; the
    row's other Cells keep their group's (c0177's `PAGAMENTO` note, which
    the parser's table puts in the total's row). One Cell above its peers
    is the measure's: c0112's `Type` header at 1.38, c0489's bold `2,382`
    at 1.22, each printed at its row's size. Below, a whole row is the
    measure's too (c0198's)."""
    for zone in document.zones:
        if zone.kind is not Kind.TABLE:
            continue
        own = {id(cell): cell.look.size for row in zone.rows for cell in row.cells
               if cell.look is not None and cell.look.size is not None}
        for role in RowRole:
            cells = [(column, cell) for row in zone.rows if row.role is role
                     for column, cell in enumerate(row.cells) if cell.text.strip()]

            def measured(group: Sequence[tuple[int, Cell]]) -> float | None:
                sizes = [cell.look.size for _, cell in group
                         if cell.look is not None and cell.look.size is not None]
                return round(float(median(sizes)), 2) if len(sizes) >= PEERS else None

            whole = measured(cells)
            for column in {column for column, _ in cells}:
                group = [(at, cell) for at, cell in cells if at == column]
                size = measured(group)
                size = whole if size is None else size
                if size is None:
                    continue
                for _, cell in group:
                    cell.look = (Look(size=size) if cell.look is None
                                 else replace(cell.look, size=size))
        for row in zone.rows:
            larger = [(cell, look) for cell in row.cells
                      if id(cell) in own and (look := cell.look) is not None
                      and look.size is not None and own[id(cell)] >= look.size + SIZE_STEP]
            if len(larger) >= 2:
                for cell, look in larger:
                    cell.look = replace(look, size=own[id(cell)])


def skeleton_of(raw: Sequence[dict[str, Any]], rectified: Rectified,
                drawn: Sequence[BBox]) -> Part:
    """The page's skeleton (spec 0025): the parser's regions cut top-down,
    on the page's content ink, rules removed and fills read against their
    own ground."""
    plain = rectified.plain if rectified.plain is not None else rectified.image
    found = furniture.find(plain, inverted=rectified.inverted, read=rectified.image)
    ink = content_ink(furniture.grounded(rectified.image, plain, found,
                                         inverted=rectified.inverted))
    height, width = ink.shape[:2]
    return skeleton(regions_of(raw), drawn, ink, (width, height))


MARK = 2.0
"""The largest picture, in lines either way, a grid may hold and be read as
a table: a tick box (c0008's, a line square) is a mark the reader's table
mode drops and `checkboxes` puts back from the pixels; a signature
(c0012's, nine lines wide) or a barcode (c0024's) is content it drops."""


def readable(blocks: Sequence[int], regions: dict[int, Any], size: tuple[int, int]) -> bool:
    """Whether a grid may be read as a table: it holds no picture larger
    than a mark (`MARK` lines either way, a line the page's own)."""
    width, height = size
    line = line_height(list(regions.values())) * height
    return not any(regions[i].label in FIGURES
                   and max((regions[i].box.right - regions[i].box.left) * width,
                           (regions[i].box.bottom - regions[i].box.top) * height) > MARK * line
                   for i in blocks)


def grids_of(raw: Sequence[dict[str, Any]], rectified: Rectified,
             drawn: Sequence[BBox]) -> list[dict[str, Any]]:
    """The page's grids (spec 0025, 3c): each grid part of its skeleton,
    the parser's indices it holds and the box it is read in, on 0-1000 as
    the parser's own boxes are: its blocks' boxes and the boxes drawn
    round its cells. A grid holding a picture larger than a mark (`MARK`)
    is not read: its fragments stay."""
    regions = {r.index: r for r in regions_of(raw)}
    size = (rectified.source.width, rectified.source.height)
    out = []
    for part in skeleton_of(raw, rectified, drawn).walk():
        if part.kind != "grid" or not readable(part.blocks, regions, size):
            continue
        boxes = [part.box] + [regions[i].box for i in part.blocks]
        box = [min(b.left for b in boxes), min(b.top for b in boxes),
               max(b.right for b in boxes), max(b.bottom for b in boxes)]
        out.append({"blocks": list(part.blocks),
                    "bbox_2d": [max(0, min(1000, round(v * 1000))) for v in box]})
    return out


def read_grids(png: Path, grids: Sequence[dict[str, Any]], *,
               timeout: float | None = None) -> list[dict[str, Any]]:
    """Each grid read once by the reader in its own table mode, its whole
    crop (`tools/glmocr_read.py`, in the parser's own Python): its content
    and seconds added. Its prompt and settings are the parser's own."""
    import tempfile

    if not grids:
        return []
    with tempfile.TemporaryDirectory(prefix="d2-grids-") as scratch:
        asked = Path(scratch) / "requests.json"
        asked.write_text(json.dumps([{"picture": str(png), "bbox_2d": g["bbox_2d"],
                                      "task": "table"} for g in grids]), encoding="utf-8")
        done = subprocess.run([str(PARSER_PYTHON), str(READ), str(CONFIG), str(asked)],
                              capture_output=True, text=True, timeout=timeout, cwd=REPO)
    if done.returncode != 0:
        raise RuntimeError(f"the reader failed (exit {done.returncode}): "
                           f"{done.stderr.strip().splitlines()[-1:] or ''}")
    answers = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    return [dict(grid, content=answer["content"], seconds=answer["seconds"])
            for grid, answer in zip(grids, answers)]


def _words(content: str) -> Counter[str]:
    return Counter(re.findall(r"\w+", plain(re.sub(r"<[^>]+>", " ", content)).lower()))


def with_grids(raw: Sequence[dict[str, Any]], grids: Sequence[dict[str, Any]]
               ) -> list[dict[str, Any]]:
    """The parser's regions with each grid read as a table in their place:
    one `table` region at the first of the grid's places in the reading
    order. A grid the reader did not read as a table, or whose table drops
    a word its text fragments hold, keeps its regions: never a word lost to
    a second reading. A picture's content is not a printed word (c0024's
    barcode reads as an empty code fence)."""
    out = list(raw)
    for grid in grids:
        content = str(grid.get("content", ""))
        if "<table" not in content:
            continue
        taken = set(grid["blocks"])
        held = sum((_words(str(r.get("content") or "")) for r in raw
                    if int(r.get("index", 0)) in taken and r.get("label") not in FIGURES),
                   Counter())
        if held - _words(content):
            continue
        out = [r for r in out if int(r.get("index", 0)) not in taken]
        out.append({"index": min(taken), "label": "table", "content": grid["content"],
                    "bbox_2d": grid["bbox_2d"], "polygon": []})
    return out


def from_regions(raw: Sequence[dict[str, Any]], png: Path,
                 grids: Sequence[dict[str, Any]] = ()) -> Document:
    """The parser's regions for one picture, as a measured IR: grouped and
    placed inside the page's skeleton (spec 0025), or as before where the
    whole page was kept flat. `grids` are its grids as the reader read
    them (`read_grids`), each in its fragments' place."""
    raw = with_grids(raw, grids)
    rectified = flat(png)
    drawn = containers(rectified)
    parts = skeleton_of(raw, rectified, drawn)
    frames: list[BBox | None] = []
    if parts.kind == "flat":
        document = document_of(raw, rectified.source, drawn)
    else:
        document, frames = laid_out(raw, parts, rectified.source, drawn)
    measure(document, rectified, frames)
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
    """One page through the whole arm: the parser, its grids read as tables
    (spec 0025, 3c), the adapter, the measuring passes and the renderer.
    Returns the IR, the HTML, and the parser's entry (its regions, grids
    and seconds)."""
    started = time.perf_counter()
    entry = parse([png], scratch)[png.stem]
    rectified = flat(png)
    entry["grids"] = read_grids(png, grids_of(entry["regions"], rectified,
                                              containers(rectified)))
    parsed = time.perf_counter()
    document = from_regions(entry["regions"], png, entry["grids"])
    html = render(document)
    entry["seconds_after"] = round(time.perf_counter() - parsed, 2)
    entry["seconds_total"] = round(time.perf_counter() - started, 2)
    return document, html, entry


def attempt(name: str, png: Path) -> Any:
    """One page as the batch runner records it (`bakeoff.Attempt`): the
    parser's regions and its grids as read as tables (`00_regions.json`,
    `01_grids.json`), their seconds as the model's, the render. A temporary
    folder holds the parser's output."""
    import tempfile

    from .bakeoff import Attempt, PassTiming

    with tempfile.TemporaryDirectory(prefix="d2-") as scratch:
        try:
            _, html, entry = convert(name, png, Path(scratch))
        except Exception as error:  # noqa: BLE001 — recorded, as a Conversion's is
            return Attempt(fixture=name, model=MODEL, error=f"{type(error).__name__}: {error}")
    regions = json.dumps(entry["regions"], ensure_ascii=False, indent=1)
    grids = json.dumps(entry["grids"], ensure_ascii=False, indent=1)
    return Attempt(fixture=name, model=MODEL,
                   timings=[PassTiming("parse", float(entry["seconds"])),
                            PassTiming("grids", sum(float(g["seconds"])
                                                    for g in entry["grids"]))],
                   answers=[("regions", regions, CONFIG.read_text(encoding="utf-8")),
                            ("grids", grids, "Table Recognition: (spec 0025, 3c)")],
                   html=html)
