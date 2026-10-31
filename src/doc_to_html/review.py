"""Look at what this project produced, beside what it was given.

**Why this exists.** The project's most expensive lesson is that a measure can
saturate and then invert while every number improves — `sample_table_0003`
scored a full match having deleted every column header of its only table, and
nobody had opened a render beside its source in eighty runs. `report.html`
answers *what do the numbers say*; this answers *what does it look like*, and
the two catch different things. `docs/agents/visual-review.md` carries the
evidence and the rationale; this module is the instrument.

**What it builds**, under `<run>/_review/`:

    00-invoice_0001.png       source | (previous render) | render, matched width
    00-invoice_0001-p2.png    ...part 2 of a tall document
    00-invoice_0001-tile1.png a dense page's strip of the source over the
                              same strip of the render, at full scale
    00-invoice_0001-diff.png  with a previous run: where the two renders differ

On a photographed page — one whose picture `rectify` warps — the sheet has a
second row: each render re-photographed into the picture's frame, and its
overlay on the source (spec 0018, 0a; `rephotograph`).
    findings.json             the machine-readable form, filled in by looking
    review.md                 the same form for a person; regenerated on --check
    numbers.md                the scored axes, to quote in a note

Each fault the checks found (`checks.py`, spec 0021) is drawn on the sheet
as a numbered box, keyed to the form; `measure.py` passes them in.

**Three rules are built in and all three are load-bearing.**

*The reference is the PNG, never the re-rendered source HTML.* The screenshot
is what the model was shown and what a person compares against. Four of the
five original documents re-render 6.9-14.1% different from their own
screenshots on this machine and `invoice2.html` additionally wants a CDN, so
comparing against the HTML would show differences nobody introduced.

*Every panel is laid out at the source's width.* A page compared against itself
at two widths is two different pages. `projection.project()` already takes this
position for scoring; the review takes the same one so the two never disagree.

*Judgements are pairwise and in-session only.* CLAUDE.md is explicit that a
rubric reading from one session and one from another are not comparable, and
that this binds a model's visual judgements at least as strongly as numbers. So
every sheet and every form is stamped with its run label and date, the rubric
asks for *differences*, which are observations, rather than a score out of ten,
which is not — and `summarise()` refuses to merge findings from two stamps.

**Rubric 2: faults, not axes** (spec 0021, from the criteria agreed
2026-10-24). Rubric 1 asked seven axes a verdict each. The checks now find
what the source HTML settles, and the form arrives with their faults filled
in, numbered as on the sheet; Claude calls each by looking, names its stage,
and adds what the HTML cannot settle under one of `AREAS`. `summarise`
ranks the classes and names the pages where the review overturns a check.
A class the checks do not know is accepted under its area, never bent into
one that does not fit.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent.parent

GUTTER = 24
"""Pixels between two pages, and the frame around the sheet.

Wide enough that a page's own right-hand edge is never mistaken for the seam,
which matters most on the documents that draw a border round the whole page.
"""

LABEL_BAR = 30
"""Height of the strip naming which panel is which.

It is **drawn**, not merely reserved. It used to be reserved and left blank,
which bought the sheet thirty pixels of grey and none of the protection its
docstring claimed: the one thing worse than no comparison is a confident
backwards one.
"""

SHEET_GROUND = (128, 128, 128)
"""Mid grey. Neither a light page nor a dark one can blend into it, and the
corpus holds both — `darkdeck_0009` and `cv_0013` are dark-grounded."""

LABEL_INK = (255, 255, 255)

MAX_SHEET_PX = 1600
"""Tallest a single sheet may be before it is cut into parts.

**Sized against the reader, not against taste.** An image arrives at the
reviewer downsampled to roughly 1568px on its long edge, so `statement_0006`'s
5166px sheet reached the one step of this workflow that finds anything at 30%
scale, with 10px type rendered at 3px. Cut into four parts it arrives at ~90%.

Only the height is cut. The width is set by how many panels are being compared
and no cutting helps it — comparing three renders instead of two is a
deliberate trade of scale for history.
"""

INK_DELTA = 40
"""How far a pixel must sit from the page's median grey to count as ink.

An absolute difference, so it reads light-on-dark pages as readily as
dark-on-light. It is a cutting aid, not a measurement: nothing scored depends
on it, and `style._ink_mask` remains the pipeline's own answer to this question.
"""

GUTTER_SEARCH = 0.10
"""How far from an ideal cut, as a share of page height, to hunt for a blank row.

A cut through the middle of a line of type is unreadable on both sheets it
lands on. Beyond this distance the ideal cut is better than a gutter, because a
cut that has wandered a tenth of the page no longer pairs with the other panel.
"""

BLEND = 0.5
"""How much of a cut's position comes from ink mass, the rest from height.

**Both pure measures were tried on `statement_0006` and both failed.** Cutting
by height pairs part 2 of the source with part 2 of nothing in particular,
because that document's render runs 5124px against a 1401px page. Cutting by
ink pairs the content and then produces a part **3316px tall**: 84% of that
render's ink is in its first 1900 rows — a dense table — and the remaining
3200 rows are the forty-one near-identical caveat lines, which are sparse. All
three cuts landed in the table and the tail arrived as one unreadable sheet.

Half and half keeps the pairing roughly honest and bounds the overrun, and
`_plan` then adds parts until the cap is actually met. Where the pairing slips
the reviewer sees the slip, because both panels stay whole, full width, and
labelled with the part they are.
"""

OVERRUN = 1.05
"""How far past the cap a part may run before another sheet is worth cutting.

A cut moved into a gutter lands a few rows from where it was asked to, and
spending a whole extra sheet on a five-row overshoot is worse than the
overshoot.
"""

MAX_PARTS = 12
"""Sheets one document may be cut into before the cap is abandoned.

A document needing more than this is telling you something — a render an order
of magnitude taller than its page — and twelve sheets is already past the point
where a reviewer reads them all.
"""

AREAS: tuple[tuple[str, str], ...] = (
    ("words", "a word or number lost, invented, changed or merged"),
    ("structure", "cells in their row and column, numbered steps as numbers, "
                  "content under its own heading, groups not interleaved; the "
                  "right look from the wrong HTML is a minor"),
    ("layout", "every line breaking where the page breaks it, the page's "
               "height, alignment, what sits beside what"),
    ("type", "the face class, sizes in proportion, bold as printed; italics, "
             "letterspacing and small caps are minors"),
    ("looks", "the ground, a colour that carries meaning, fills, bands, frames "
              "and rules"),
    ("figures", "logos, barcodes, icons, signatures, photos: a minor, for now"),
)
"""The criteria's six rows (`docs/agents/review-criteria.md`), each with what
it asks. **Rubric 2 reports faults, not axes**: the seven axes of rubric 1
asked for a verdict on each of a page's aspects, and the criteria ask for
each fault, its class and its severity. A fault the checks cannot find is
added under the area it belongs to."""

AREA_OF_CHECK: dict[str, str] = {
    "words": "words", "cells": "structure", "structure": "structure",
    "order": "structure", "rules": "looks", "lines": "layout",
    "height": "layout", "alignment": "layout", "type": "type",
}
"""Which area each of `checks`'s checks reports under: a rule missing is a
look ("a frame or rule missing"), a cell out of place is structure."""

SEVERITIES = ("major", "minor")
"""The criteria's two. Every class a check reports has one, decided."""

CALLS = ("confirmed", "rejected")
"""Claude's call on a fault a check found, made by looking: markup can still
fool a check. A fault Claude adds is a call in itself."""

STAGES = ("rectify", "layout", "caption", "classify", "extract", "inline runs",
          "re-read", "third reading", "wire", "locate", "render")
"""Where a fault was made, `level-up.md` §1.2. A CV pass is named as
`cv:<pass>` (`cv:furniture`, `cv:rhythm`). Named by reading the page's IR and
trace, never guessed from the picture."""

CHANGED_VERDICTS = ("better", "same", "worse")
"""A page against the previous run's render, when one is on the sheet."""

RUBRIC_VERSION = 2
"""Bumped whenever the form changes, so a findings file says which form it
was answered on. Version 1 was seven axes and a verdict each; version 2 is
faults. Two files at different versions are not one table, and `summarise`
refuses a file of another version."""


# --- cutting a tall page into readable parts -------------------------------


def ink_profile(image: Image.Image) -> npt.NDArray[np.int64]:
    """Ink pixels per row, read against the page's own median grey.

    The median is the page and the difference is the type, which reads a
    dark-grounded page — `darkdeck_0009`, `cv_0013` — exactly as readily as a
    light one. It assumes ink is a minority of the pixels, which every page in
    the corpus satisfies by a wide margin; a page that is more than half ink
    would be read inside out, and that page is not a document.
    """
    grey = np.asarray(image.convert("L"), dtype=np.int16)
    ground = int(np.median(grey))
    counted = np.count_nonzero(np.abs(grey - ground) >= INK_DELTA, axis=1)
    return np.asarray(counted, dtype=np.int64)


def parts_for(height: int, cap: int = MAX_SHEET_PX) -> int:
    """How many parts a page of this height must be cut into to stay readable."""
    return max(1, math.ceil(height / cap)) if height > 0 else 1


def _nearest_gutter(profile: npt.NDArray[np.int64], row: int, reach: int) -> int:
    """The blank row closest to `row`, or `row` itself if none is within reach."""
    blank = profile == 0
    for offset in range(reach + 1):
        for candidate in (row - offset, row + offset):
            if 0 < candidate < len(profile) and blank[candidate]:
                return candidate
    return row


def cut_rows(profile: npt.NDArray[np.int64], parts: int) -> tuple[int, ...]:
    """Rows at which to cut a page into `parts`, by `BLEND` of ink and height.

    The two panels of a sheet hold the same content at different heights — our
    renders run to 3.7x the source — so a cut has two jobs that pull apart:
    part k of each panel should hold the same *content*, and no part should be
    too tall to read. `BLEND` carries the measurement that set the trade.

    Each cut is then moved to the nearest blank row within `GUTTER_SEARCH`,
    because a cut through the middle of a line of type is unreadable on both
    sheets it lands on.
    """
    if parts <= 1 or len(profile) == 0:
        return ()
    rows = len(profile)
    total = int(profile.sum())
    reach = max(1, int(rows * GUTTER_SEARCH))
    position = np.arange(rows, dtype=np.float64) / rows
    if total == 0:
        measure = position
    else:
        above = np.concatenate(([0.0], np.cumsum(profile, dtype=np.float64)[:-1]))
        measure = BLEND * (above / total) + (1 - BLEND) * position
    cuts: list[int] = []
    for k in range(1, parts):
        row = int(np.searchsorted(measure, k / parts))
        cut = _nearest_gutter(profile, row, reach)
        cut = min(max(cut, len(cuts) + 1), rows - (parts - len(cuts) - 1))
        if cuts and cut <= cuts[-1]:
            cut = cuts[-1] + 1
        cuts.append(cut)
    return tuple(cuts)


def _slices(profile: npt.NDArray[np.int64], height: int,
            parts: int) -> list[tuple[int, int]]:
    edges = (0, *cut_rows(profile, parts), height)
    return [(edges[k], edges[k + 1]) for k in range(len(edges) - 1)]


def plan(images: Sequence[Image.Image], cap: int = MAX_SHEET_PX
         ) -> list[list[tuple[int, int]]]:
    """Slice every panel into the same number of parts, none taller than `cap`.

    The part count starts from the tallest panel and rises until the cap is
    actually met, because a blended cut only bounds the overrun — it does not
    remove it. `MAX_PARTS` stops the rise.
    """
    profiles = [ink_profile(image) for image in images]
    heights = [image.height for image in images]
    start = parts_for(max(heights), cap)
    cut: list[list[tuple[int, int]]] = []
    for parts in range(start, MAX_PARTS + 1):
        cut = [_slices(profile, height, parts)
               for profile, height in zip(profiles, heights)]
        tallest = max(bottom - top for slices in cut for top, bottom in slices)
        if tallest <= cap * OVERRUN:
            break
    return cut


# --- the sheet --------------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    """One page on a sheet: what to call it, and where its PNG is."""

    label: str
    image: Path


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=18)
    except TypeError:  # Pillow older than 10.1
        return ImageFont.load_default()


def _plan_rows(rows: Sequence[Sequence[Image.Image]], cap: int
               ) -> list[list[list[tuple[int, int]]]]:
    """`plan` over a sheet of one row or more: every panel of every row cut
    into the same number of parts, the rows of a part together no taller
    than `cap`. One row is `plan` exactly."""
    if len(rows) == 1:
        return [plan(rows[0], cap)]
    profiles = [[ink_profile(image) for image in row] for row in rows]
    heights = [[image.height for image in row] for row in rows]
    start = parts_for(sum(max(row) for row in heights), cap)
    cut: list[list[list[tuple[int, int]]]] = []
    for parts in range(start, MAX_PARTS + 1):
        cut = [[_slices(profile, height, parts)
                for profile, height in zip(row_profiles, row_heights)]
               for row_profiles, row_heights in zip(profiles, heights)]
        tallest = max(sum(max(slices[part][1] - slices[part][0] for slices in row)
                          for row in cut)
                      for part in range(parts))
        if tallest <= cap * OVERRUN:
            break
    return cut


def contact_sheet(panels: Sequence[Panel], stem: Path, *,
                  stamp: str, cap: int = MAX_SHEET_PX,
                  below: Sequence[Panel] = ()) -> list[Path]:
    """Write one sheet per part, panels side by side, each labelled.

    Returns the files written, in reading order. A short document is one file
    at `stem.png`; a tall one is `stem-p1.png`, `stem-p2.png`, ...

    `below` is a second row under the first — spec 0018, 0a: on a
    photographed page, each render re-photographed and its overlay. Every
    panel of both rows is cut into the same parts, and only the first row's
    labels carry the stamp, which the second's would run into on a narrow
    page.
    """
    if not panels:
        raise ValueError("a sheet needs at least one panel")
    panels_row = list(panels)
    rows = [panels_row, *([list(below)] if below else [])]
    images = [[Image.open(panel.image).convert("RGB") for panel in row] for row in rows]
    cut = _plan_rows(images, cap)
    parts = len(cut[0][0])

    width = max(sum(image.width for image in row) + GUTTER * (len(row) + 1)
                for row in images)
    font = _font()
    written: list[Path] = []
    for part in range(parts):
        talls = [max(slices[part][1] - slices[part][0] for slices in row) for row in cut]
        height = sum(talls) + (LABEL_BAR + GUTTER) * len(rows)
        sheet = Image.new("RGB", (width, height), SHEET_GROUND)
        draw = ImageDraw.Draw(sheet)
        y = 0
        for row_images, row_cut, row_panels, tall in zip(images, cut, rows, talls):
            x = GUTTER
            for image, slices, panel in zip(row_images, row_cut, row_panels):
                top, bottom = slices[part]
                name = panel.label
                if parts > 1:
                    name = f"{name} · part {part + 1} of {parts}"
                if row_panels is panels_row:
                    name = f"{name}   ·   {stamp}"
                draw.text((x, y + 6), name, fill=LABEL_INK, font=font)
                sheet.paste(image.crop((0, top, image.width, bottom)), (x, y + LABEL_BAR))
                x += image.width + GUTTER
            y += tall + LABEL_BAR + GUTTER
        target = stem.with_name(f"{stem.name}-p{part + 1}.png") if parts > 1 \
            else stem.with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(target)
        written.append(target)
    return written


# --- the render re-photographed, spec 0018, 0a -----------------------------


def rephotograph(render: Image.Image, outline: Any, size: tuple[int, int]
                 ) -> tuple[Image.Image, tuple[int, int]]:
    """The render as the photograph would hold it, and where the picture
    sits on the result.

    **Rotate the render, not the original** — Alessandro, 2026-10-19. The
    render draws the paper at `Source.paper` × the picture's size (spec
    0012, G5), so that rectangle is mapped onto the outline `rectify`
    warped by (`preprocess.page_outline`), by the homography of their four
    corners, cubic, onto the surround. A wrong outline then shows as
    misregistration instead of being hidden by straightening both sides
    alike. A render taller than its paper overhangs the picture, and the
    result grows to hold it: that overhang is information.
    """
    import cv2

    from doc_to_html.preprocess import paper_box

    across, down = size
    paper = paper_box(outline.quad, across, down)
    rectangle = np.array([[paper.left * across, paper.top * down],
                          [paper.right * across, paper.top * down],
                          [paper.right * across, paper.bottom * down],
                          [paper.left * across, paper.bottom * down]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(rectangle, np.asarray(outline.quad, dtype=np.float32))
    corners = np.array([[[0, 0], [render.width, 0], [render.width, render.height],
                         [0, render.height]]], dtype=np.float32)
    landed = np.round(cv2.perspectiveTransform(corners, matrix)[0], 3)
    left = int(math.floor(min(0.0, float(landed[:, 0].min()))))
    top = int(math.floor(min(0.0, float(landed[:, 1].min()))))
    right = int(math.ceil(max(float(across), float(landed[:, 0].max()))))
    bottom = int(math.ceil(max(float(down), float(landed[:, 1].max()))))
    shift = np.array([[1, 0, -left], [0, 1, -top], [0, 0, 1]], dtype=np.float64)
    pixels = cv2.warpPerspective(np.asarray(render.convert("RGB")), shift @ matrix,
                                 (right - left, bottom - top), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=tuple(int(v) for v in outline.surround))
    return Image.fromarray(pixels), (-left, -top)


def overlay(source: Image.Image, photographed: Image.Image,
            offset: tuple[int, int], surround: tuple[int, int, int]) -> Image.Image:
    """The source's grey in the red channel, the re-photographed render's in
    green and blue: **cyan is the source's alone, red the render's alone,
    dark both.** The source stands on the surround where the render
    overhangs it."""
    ground = Image.new("RGB", photographed.size, tuple(surround))
    ground.paste(source.convert("RGB"), offset)
    red = np.asarray(ground.convert("L"))
    cyan = np.asarray(photographed.convert("L"))
    return Image.fromarray(np.dstack([red, cyan, cyan]))


def photographed_panels(source: Path, render: Path, label: str, scratch: Path
                        ) -> list[Panel]:
    """The second row's pair for one render on a photographed page: the
    render re-photographed, and the overlay. Empty for a picture that is
    the paper, whose sheet stays as it was."""
    import cv2

    from doc_to_html.preprocess import page_outline

    pixels = cv2.imread(str(source), cv2.IMREAD_COLOR)
    outline = None if pixels is None else page_outline(pixels)
    if outline is None:
        return []
    picture = Image.open(source).convert("RGB")
    photo, offset = rephotograph(Image.open(render), outline, picture.size)
    shot = scratch.with_name(f"{scratch.name}-photographed.png")
    laid = scratch.with_name(f"{scratch.name}-overlay.png")
    photo.save(shot)
    overlay(picture, photo, offset, outline.surround).save(laid)
    return [Panel(f"{label} re-photographed", shot),
            Panel(f"OVERLAY {label.removeprefix('RENDER ')} · cyan source, red render",
                  laid)]


# --- marks, the renders' difference, zoomed tiles (spec 0021, step 5) -----


Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Mark:
    """One fault drawn on a sheet: its number in the form, and its boxes on
    the source and on the render, in CSS pixels at the source's width, which
    are the screenshots' pixels."""

    n: int
    source: tuple[Box, ...] = ()
    output: tuple[Box, ...] = ()


MARK_INK = (225, 0, 125)
"""Magenta: no corpus page's palette, and it reads on light and dark alike."""


def marked(image: Path, boxes: Sequence[tuple[int, Box]], target: Path) -> Path:
    """`image` with each box drawn and numbered, saved to `target`. A box is
    padded by two pixels so the outline never sits on the ink it names, and
    its number stands to its left, in the margin or the gutter before it,
    where it covers no line above (to its right where the page's edge is)."""
    picture = Image.open(image).convert("RGBA")
    layer = Image.new("RGBA", picture.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _tag_font()
    for n, (left, top, right, bottom) in boxes:
        frame = (left - 2, top - 2, right + 2, bottom + 2)
        draw.rectangle(frame, outline=(*MARK_INK, 255), width=2)
        label = str(n)
        width = draw.textlength(label, font=font) + 4
        tag_left = frame[0] - width if frame[0] - width >= 0 else frame[2]
        draw.rectangle((tag_left, frame[1], tag_left + width, frame[1] + 15),
                       fill=(*MARK_INK, TAG_ALPHA))
        draw.text((tag_left + 2, frame[1]), label, fill=(*LABEL_INK, 255), font=font)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(picture, layer).convert("RGB").save(target)
    return target


TAG_ALPHA = 150
"""A number's tag is see-through, so a glyph it stands on — an answer's
circle, a list's marker, which are often the fault — still shows."""


def _tag_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=13)
    except TypeError:  # Pillow older than 10.1
        return ImageFont.load_default()


DIFF_DELTA = 30
"""Summed channel difference past which two renders' pixels differ: the
level the re-render measurements in spec 0021 used. Anti-aliasing on one
machine, one Chrome, moves no pixel at all, so any real change clears it."""


def difference(before: Image.Image, after: Image.Image) -> tuple[Image.Image, float]:
    """Where two renders at one width differ, pixel for pixel: `after`
    faded, and every differing pixel red. Returns it and the share of pixels
    that differ, 0.0 for a render that did not move. The shorter is padded
    with white, so a render that grew shows its new rows as changed."""
    width = max(before.width, after.width)
    height = max(before.height, after.height)
    pads = []
    for image in (before, after):
        ground = Image.new("RGB", (width, height), (255, 255, 255))
        ground.paste(image.convert("RGB"), (0, 0))
        pads.append(np.asarray(ground, dtype=np.int16))
    changed = np.abs(pads[0] - pads[1]).sum(axis=2) > DIFF_DELTA
    faded = (255 - (255 - pads[1].mean(axis=2)) * 0.3).astype(np.uint8)
    picture = np.dstack([faded, faded, faded])
    picture[changed] = (220, 0, 0)
    return Image.fromarray(picture), float(changed.mean())


READER_EDGE = 1568
"""The long edge an image reaches the reviewer at, in pixels: anything
larger is scaled down to it (`MAX_SHEET_PX`'s docstring)."""

LEGIBLE_PX = 8.0
"""The smallest body type, in pixels as it reaches the reviewer, that is read
rather than guessed at. Below it a sheet gains zoomed tiles (`dense`).
Set on the 31 known pages' sheets, spec 0021 step 7, by opening them: the
value and the pages either side of it are recorded there."""

TILE_STRIP = 700
"""A tile's source strip, in pixels. A tile holds the strip over the same
strip of the render, so two strips and their bars stay inside
`READER_EDGE` on a page up to that wide."""


def reader_scale(size: tuple[int, int]) -> float:
    """How much a sheet of this size is shrunk on its way to the reviewer."""
    return min(1.0, READER_EDGE / max(size)) if max(size) > 0 else 1.0


def dense(body_px: float, sheet_size: tuple[int, int]) -> bool:
    """A sheet whose body type reaches the reviewer below `LEGIBLE_PX`."""
    return body_px > 0 and body_px * reader_scale(sheet_size) < LEGIBLE_PX


def _monotone(anchors: Sequence[tuple[float, float]], source_height: int,
              output_height: int) -> tuple[list[float], list[float]]:
    """The anchors as a map that only goes down the page: a block the render
    moved up does not pull a strip back over what it already showed."""
    points = sorted([(0.0, 0.0), *anchors, (float(source_height), float(output_height))])
    xs: list[float] = []
    ys: list[float] = []
    for x, y in points:
        y = max(y, ys[-1]) if ys else y
        if xs and x == xs[-1]:
            ys[-1] = max(ys[-1], y)
            continue
        xs.append(x)
        ys.append(y)
    return xs, ys


def tile_rows(source_height: int, output_height: int,
              anchors: Sequence[tuple[float, float]], strip: int = TILE_STRIP
              ) -> list[tuple[int, int, int, int]]:
    """Each tile's (source top, bottom, render top, bottom): the source cut
    into strips, each matched to where its words landed in the render, through
    the checks' anchors (`checks.PageCheck.anchors`)."""
    xs, ys = _monotone(anchors, source_height, output_height)
    rows = []
    for top in range(0, max(source_height, 1), strip):
        bottom = min(top + strip, source_height)
        out_top = int(max(0.0, float(np.interp(top, xs, ys)) - 12))
        out_bottom = int(min(float(output_height), float(np.interp(bottom, xs, ys)) + 12))
        rows.append((top, bottom, out_top, max(out_bottom, out_top + 1)))
    return rows


def tiles(source: Path, render: Path, stem: Path, *, stamp: str,
          anchors: Sequence[tuple[float, float]], strip: int = TILE_STRIP) -> list[Path]:
    """Zoomed tiles for a dense page: one file per strip, the source's strip
    over the render's, both at full scale."""
    mine = Image.open(source).convert("RGB")
    theirs = Image.open(render).convert("RGB")
    rows = tile_rows(mine.height, theirs.height, anchors, strip)
    font = _font()
    written = []
    for k, (top, bottom, out_top, out_bottom) in enumerate(rows, start=1):
        width = max(mine.width, theirs.width) + 2 * GUTTER
        height = (bottom - top) + (out_bottom - out_top) + 2 * LABEL_BAR + 3 * GUTTER
        sheet = Image.new("RGB", (width, height), SHEET_GROUND)
        draw = ImageDraw.Draw(sheet)
        draw.text((GUTTER, GUTTER // 2 + 4),
                  f"SOURCE · tile {k} of {len(rows)} · rows {top}-{bottom}   ·   {stamp}",
                  fill=LABEL_INK, font=font)
        sheet.paste(mine.crop((0, top, mine.width, bottom)), (GUTTER, GUTTER // 2 + LABEL_BAR))
        y = GUTTER // 2 + LABEL_BAR + (bottom - top) + GUTTER
        draw.text((GUTTER, y + 4), f"RENDER · rows {out_top}-{out_bottom}",
                  fill=LABEL_INK, font=font)
        sheet.paste(theirs.crop((0, out_top, theirs.width, out_bottom)), (GUTTER, y + LABEL_BAR))
        target = stem.with_name(f"{stem.name}-tile{k}.png")
        sheet.save(target)
        written.append(target)
    return written


# --- findings ---------------------------------------------------------------


FAULT_FIELDS = ("check", "fault", "severity", "element", "note", "features")
"""What a check's fault brings into the form. Its boxes stay in
`<run>/checks/<page>.json` and reach the sheet as numbered marks."""


def page_entry(name: str, *, family: str = "", kind: str = "", opened: bool = True,
               why: Sequence[str] = (), faults: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    """One page of the form: the checks' faults, numbered as on the sheet,
    each waiting for Claude's call and its stage."""
    return {
        "name": name, "family": family, "kind": kind, "opened": opened,
        "why": list(why),
        "faults": [{"n": n, "from": "check",
                    **{key: fault.get(key) for key in FAULT_FIELDS},
                    "stage": None, "call": None, "why": ""}
                   for n, fault in enumerate(faults, start=1)],
        "changed": None, "changed_note": "", "worst": None,
    }


def blank_findings(pages: Sequence[dict[str, Any]], *, stamp: str, run: str,
                   previous: str | None, model: str) -> dict[str, Any]:
    """The form, unanswered: every page checked, the opened ones to review.

    Claude, on each opened page: a **call** on each check's fault
    (`CALLS`) and its **stage**; every fault the checks cannot see added
    with `"from": "review"`, an area for its `check`, a class, a severity,
    the element and a note; with a previous run, `changed`. Across the run:
    `ranked`, the fault classes in the order to fix them, each with why.
    """
    return {
        "run": run, "previous": previous, "model": model, "stamp": stamp,
        "taken": date.today().isoformat(), "rubric_version": RUBRIC_VERSION,
        "areas": [area for area, _ in AREAS], "stages": list(STAGES),
        "pages": list(pages), "ranked": [],
    }


@dataclass(frozen=True)
class Finding:
    """One fault on one page, as the form holds it."""

    page: str
    n: int
    origin: str
    check: str
    fault: str
    severity: str
    call: str | None
    stage: str | None
    features: tuple[str, ...]
    element: str
    note: str
    opened: bool

    @property
    def standing(self) -> bool:
        """A fault the review keeps: added by Claude, or a check's not rejected."""
        return self.origin == "review" or self.call != "rejected"

    @property
    def key(self) -> tuple[str, str]:
        return (self.check, self.fault)


def findings_of(record: dict[str, Any]) -> tuple[Finding, ...]:
    """Every fault in a findings file, as flat records."""
    out = []
    for page in record.get("pages", ()):
        for fault in page.get("faults", ()):
            out.append(Finding(
                page=str(page.get("name", "")), n=int(fault.get("n", 0)),
                origin=str(fault.get("from", "check")), check=str(fault.get("check", "")),
                fault=str(fault.get("fault", "")), severity=str(fault.get("severity", "")),
                call=fault.get("call"), stage=fault.get("stage"),
                features=tuple(fault.get("features") or ()),
                element=str(fault.get("element", "")), note=str(fault.get("note", "")),
                opened=bool(page.get("opened"))))
    return tuple(out)


@dataclass(frozen=True)
class FaultClass:
    """One class of fault across a run: what the ranked roll-up ranks."""

    check: str
    fault: str
    severity: str
    pages: tuple[str, ...]
    occurrences: int
    features: Counter[str]
    stages: Counter[str]
    confirmed: int
    rejected: int
    added: int
    why: str = ""

    @property
    def name(self) -> str:
        return f"{self.check}: {self.fault}"


@dataclass(frozen=True)
class Summary:
    """What a filled findings file adds up to.

    `overturned` is decision 2 of spec 0021: the pages where Claude's call
    overturns a check, a check's fault rejected or a major added, which
    Alessandro spot-checks. `unreported` keeps rubric 1's catch: a major
    standing beside scored ratios all at 1.000, computed without a chosen
    threshold, since one is the ceiling.
    """

    stamp: str
    pages: int
    opened: int
    classes: tuple[FaultClass, ...]
    ranked_by: str
    overturned: tuple[str, ...]
    unanswered: tuple[tuple[str, int], ...]
    unstaged: tuple[tuple[str, int], ...]
    changed: Counter[str]
    worse: tuple[tuple[str, str], ...]
    unreported: tuple[Finding, ...]
    cross_checked: tuple[str, ...]


PERFECT = ("recall", "precision", "join_recall", "tau")
"""The scored ratios whose ceiling is exactly 1.000, so "did not notice" can be
stated as a fact rather than as a threshold somebody picked."""

SEVERITY_RANK = {"major": 0, "minor": 1}
"""Majors first: the order every roll-up sorts by."""


def _scored(scores: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    if not scores:
        return {}
    flat: dict[str, dict[str, float]] = {}
    for document in scores.get("documents", ()):
        flat[str(document["name"])] = {
            "recall": float(document["completeness"]["recall"]),
            "precision": float(document["completeness"]["precision"]),
            "join_recall": float(document["completeness"]["join_recall"]),
            "tau": float(document["order"]["tau"]),
            "beside": float(document["layout"]["beside_agreement"]),
            "height_ratio": float(document["layout"]["height_ratio"]),
            "ink_delta": float(document["palette"]["ink_delta"]),
        }
    return flat


def summarise(record: dict[str, Any], *, scores: dict[str, Any] | None = None) -> Summary:
    """Count a filled findings file: the classes ranked, the pages to
    spot-check, and what is still unanswered. Refuses another rubric."""
    version = record.get("rubric_version")
    if version != RUBRIC_VERSION:
        raise ValueError(f"a findings file of rubric {version}, not {RUBRIC_VERSION}: "
                         "two rubrics are not one table")
    findings = findings_of(record)
    standing = [finding for finding in findings if finding.standing]

    grouped: dict[tuple[str, str], list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.key, []).append(finding)
    whys = {(str(entry.get("check")), str(entry.get("fault"))): str(entry.get("why", ""))
            for entry in record.get("ranked") or ()}
    classes = []
    for key, members in grouped.items():
        kept = [finding for finding in members if finding.standing]
        if not kept and not any(finding.call == "rejected" for finding in members):
            continue
        severity = min((finding.severity for finding in kept or members),
                       key=lambda value: SEVERITY_RANK.get(value, 2))
        classes.append(FaultClass(
            check=key[0], fault=key[1], severity=severity,
            pages=tuple(sorted({finding.page for finding in kept})),
            occurrences=len(kept),
            features=Counter(feature for finding in kept for feature in finding.features),
            stages=Counter(finding.stage for finding in kept if finding.stage),
            confirmed=sum(1 for finding in members if finding.call == "confirmed"),
            rejected=sum(1 for finding in members if finding.call == "rejected"),
            added=sum(1 for finding in members if finding.origin == "review"),
            why=whys.get(key, "")))
    order = {key: index for index, key in enumerate(whys)}
    classes.sort(key=lambda c: (order.get((c.check, c.fault), len(order)),
                                SEVERITY_RANK.get(c.severity, 2), -len(c.pages), -c.occurrences,
                                c.name))

    overturned = sorted({finding.page for finding in findings
                         if (finding.origin == "check" and finding.call == "rejected")
                         or (finding.origin == "review" and finding.severity == "major")})
    unanswered = tuple((f.page, f.n) for f in findings
                       if f.opened and f.origin == "check" and f.call not in CALLS)
    unstaged = tuple((f.page, f.n) for f in standing
                     if f.opened and f.severity == "major" and not f.stage)

    pages = list(record.get("pages", ()))
    changed: Counter[str] = Counter(str(page["changed"]) for page in pages if page.get("changed"))
    worse = tuple((str(page["name"]), str(page.get("changed_note", "")))
                  for page in pages if page.get("changed") == "worse")

    now = _scored(scores)
    unreported = tuple(
        finding for finding in standing
        if finding.severity == "major" and finding.page in now
        and all(now[finding.page][key] == 1.0 for key in PERFECT))
    return Summary(
        stamp=str(record.get("stamp", "")), pages=len(pages),
        opened=sum(1 for page in pages if page.get("opened")),
        classes=tuple(classes), ranked_by="review" if whys else "count",
        overturned=tuple(overturned), unanswered=unanswered, unstaged=unstaged,
        changed=changed, worse=worse, unreported=unreported,
        cross_checked=tuple(str(page.get("name")) for page in pages
                            if str(page.get("name")) in now))


# --- building a review off a run -------------------------------------------


@dataclass(frozen=True)
class Sheet:
    """One page's comparison: the files that came out, the width they were
    all laid out at, and what was added for a dense or a moved page."""

    document: str
    width: int
    parts: tuple[Path, ...]
    tiles: tuple[Path, ...] = ()
    diff: Path | None = None
    moved: float | None = None
    """The share of pixels that differ from the previous run's render."""


def _dump(run: Path, model: str) -> Path:
    return run / "dump" / model.replace(":", "_")


def documents_in(run: Path, model: str) -> list[str]:
    """Every document the run converted, in name order."""
    dump = _dump(run, model)
    if not dump.is_dir():
        return []
    return sorted(d.name for d in dump.iterdir() if d.is_dir())


def _scores_file(run: Path) -> dict[str, Any] | None:
    path = run / "scores.json"
    if not path.exists():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


def build(run: Path, *, model: str = "qwen3-vl:4b",
          documents: Sequence[str] | None = None,
          previous: Path | None = None,
          out: Path | None = None,
          cap: int = MAX_SHEET_PX,
          render: Any = None,
          marks: dict[str, Sequence[Mark]] | None = None,
          body_px: dict[str, float] | None = None,
          anchors: dict[str, Sequence[tuple[float, float]]] | None = None,
          pages: Sequence[dict[str, Any]] | None = None) -> tuple[list[Sheet], Path]:
    """Build every sheet and the two forms for one run.

    `previous` is another run directory; when given, each sheet carries three
    panels — source, that run's render, this run's render — beside a file
    showing where the two renders differ, and the form asks `changed`.

    `marks` draws each page's faults, numbered as in the form, on the source
    and on this run's render. A page whose body type would reach the reviewer
    below `LEGIBLE_PX` (`body_px`) gains zoomed tiles, cut along `anchors`.
    `pages` is the form's entries (`page_entry`), every page checked, the
    opened ones among them; without it, each sheet gets an empty entry.

    `render` is the screenshot function, injected so the sheet builder can be
    tested without a browser; it defaults to `projection.screenshot`.
    """
    from doc_to_html.corpus import page

    if render is None:
        from doc_to_html.projection import screenshot as render
    out = out or (run / "_review")
    out.mkdir(parents=True, exist_ok=True)
    stamp = f"{run.name} · {date.today().isoformat()}"
    if previous:
        stamp = f"{run.name} vs {previous.name} · {date.today().isoformat()}"

    names = [name for name in documents_in(run, model)
             if documents is None or name in documents]
    sheets: list[Sheet] = []
    skipped: list[str] = []
    for index, name in enumerate(names):
        source = page(name).png_path(REPO)
        width = Image.open(source).width
        html = _dump(run, model) / name / "document.html"
        if not html.exists():
            skipped.append(f"{name}: no document.html in {run.name}")
            continue
        stem = out / f"{index:02d}-{name}"
        mine = (marks or {}).get(name, ())

        shown_source = source
        scratch: list[Path] = []
        if mine:
            shown_source = marked(source, [(m.n, box) for m in mine for box in m.source],
                                  stem.with_name(f"{stem.name}-source.png"))
            scratch.append(shown_source)
        panels = [Panel("SOURCE (the page)", shown_source)]
        below: list[Panel] = []
        older_shot: Path | None = None
        if previous:
            older = _dump(previous, model) / name / "document.html"
            if older.exists():
                older_shot = out / f"{index:02d}-{name}-previous.png"
                render(older, older_shot, width=width)
                scratch.append(older_shot)
                panels.append(Panel(f"RENDER {previous.name}", older_shot))
                below += photographed_panels(source, older_shot, f"RENDER {previous.name}",
                                             older_shot.with_suffix(""))
            else:
                skipped.append(f"{name}: no document.html in {previous.name}, "
                               "compared against the source only")
        shot = out / f"{index:02d}-{name}-render.png"
        render(html, shot, width=width)
        scratch.append(shot)
        diff: Path | None = None
        moved: float | None = None
        if older_shot is not None:
            picture, moved = difference(Image.open(older_shot), Image.open(shot))
            diff = stem.with_name(f"{stem.name}-diff.png")
            picture.save(diff)
        shown_render = shot
        if mine:
            shown_render = marked(shot, [(m.n, box) for m in mine for box in m.output],
                                  stem.with_name(f"{stem.name}-render-marked.png"))
            scratch.append(shown_render)
        panels.append(Panel(f"RENDER {run.name}", shown_render))
        below += photographed_panels(source, shot, f"RENDER {run.name}",
                                     shot.with_suffix(""))
        scratch += [panel.image for panel in below]

        parts = contact_sheet(panels, stem, stamp=stamp, cap=cap, below=below)
        zoomed: list[Path] = []
        size = Image.open(parts[0]).size
        if dense((body_px or {}).get(name, 0.0), size):
            zoomed = tiles(shown_source, shown_render, stem, stamp=stamp,
                           anchors=(anchors or {}).get(name, ()))
        for path in scratch:
            path.unlink(missing_ok=True)
        sheets.append(Sheet(name, width, tuple(parts), tuple(zoomed), diff, moved))

    built = {sheet.document for sheet in sheets}
    entries = list(pages) if pages is not None else [page_entry(sheet.document)
                                                     for sheet in sheets]
    for entry in entries:
        if entry.get("opened") and entry["name"] not in built:
            entry["opened"] = False
            entry["why"] = [*entry.get("why", ()), "no sheet: no document.html"]
    record = blank_findings(entries, stamp=stamp, run=run.name,
                            previous=previous.name if previous else None, model=model)
    findings = out / "findings.json"
    if findings.exists():
        record["note"] = (f"{findings.name} already existed and was left alone; "
                          "the blank form is at findings.blank.json")
        (out / "findings.blank.json").write_text(json.dumps(record, indent=2) + "\n")
    else:
        findings.write_text(json.dumps(record, indent=2) + "\n")

    (out / "numbers.md").write_text(_numbers_md(stamp, sheets, _scores_file(run)))
    (out / "review.md").write_text(_form_md(stamp, sheets, record, skipped))
    return sheets, out


def _numbers_md(stamp: str, sheets: Sequence[Sheet],
                scores: dict[str, Any] | None) -> str:
    flat = _scored(scores)
    keys = ("recall", "precision", "join_recall", "tau", "beside",
            "height_ratio", "ink_delta")
    rows = []
    for sheet in sheets:
        values = flat.get(sheet.document, {})
        rows.append(f"| `{sheet.document}` | {sheet.width}px | " + " | ".join(
            f"{values[key]:.3f}" if key in values else "—" for key in keys) + " |")
    return (f"# Scored axes — {stamp}\n\n"
            "Here to be quoted in a note, not to be reviewed. The images are "
            "the review, and a finding that could have been written from this "
            "table has not done the job.\n\n"
            "| document | width | " + " | ".join(keys) + " |\n"
            + "|---" * (len(keys) + 2) + "|\n" + "\n".join(rows) + "\n")


def _fault_line(fault: dict[str, Any]) -> str:
    call = fault.get("call") or ("added" if fault.get("from") == "review" else "—")
    stage = fault.get("stage") or "—"
    return (f"- **{fault.get('n')}** `{fault.get('check')}: {fault.get('fault')}` "
            f"· {fault.get('severity')} · call {call} · stage {stage} — "
            f"{fault.get('element')}" + (f" ({fault['note']})" if fault.get("note") else "")
            + (f" — {fault['why']}" if fault.get("why") else ""))


def _form_md(stamp: str, sheets: Sequence[Sheet], record: dict[str, Any],
             skipped: Sequence[str]) -> str:
    lines = [
        f"# Visual review — {stamp}",
        "",
        "**Filled in by opening each PNG**, one at a time. Rubric "
        f"{RUBRIC_VERSION}: faults, not axes. Answers go in `findings.json`; "
        "`--check` rewrites this file from it.",
        "",
        "**Each fault a check found is numbered on the sheet.** Call it "
        f"`{' / '.join(CALLS)}` by looking, and name its stage "
        f"({', '.join(STAGES)}, or `cv:<pass>`) from the page's IR and trace. "
        "Add every fault the checks cannot see, under its area: "
        + "; ".join(f"**{area}** — {text}" for area, text in AREAS) + ".",
        "",
        "**Pairwise and in-session only.** These readings are not comparable "
        "with a review from another session.",
        "",
    ]
    if skipped:
        lines += ["**Skipped:**", *(f"- {line}" for line in skipped), ""]
    entries = {entry["name"]: entry for entry in record.get("pages", ())}
    for sheet in sheets:
        entry = entries.get(sheet.document, {})
        lines += [f"## {sheet.document}  ({sheet.width}px)", ""]
        if entry.get("why"):
            lines += [f"_Opened: {'; '.join(entry['why'])}._", ""]
        lines += [f"![{sheet.document}]({part.name})" for part in sheet.parts]
        lines += [f"![{sheet.document} tile]({tile.name})" for tile in sheet.tiles]
        if sheet.diff is not None:
            lines += [f"![where the renders differ]({sheet.diff.name}) "
                      f"— {100 * (sheet.moved or 0):.2f}% of pixels"]
        lines += [""]
        lines += [_fault_line(fault) for fault in entry.get("faults", ())] or [
            "- no fault found by a check"]
        if record.get("previous"):
            lines.append(f"- **changed** — _{' / '.join(CHANGED_VERDICTS)}, and what moved_")
        lines += [""]
    return "\n".join(lines) + "\n"


def report_md(record: dict[str, Any], summary: Summary) -> str:
    """The filled form, rendered back out with the roll-up. Written by `--check`."""
    lines = [
        f"# Visual review — {summary.stamp}",
        "",
        f"{summary.opened} of {summary.pages} page(s) opened, rubric "
        f"{record.get('rubric_version')}. **Pairwise and in-session only.**",
        "",
        "## The fault classes, ranked",
        "",
        ("In Claude's order, each with why: majors first, then the biggest "
         "visible gain for the effort." if summary.ranked_by == "review" else
         "**Not yet ranked by the review**: counted order, majors first, then "
         "pages touched."),
        "",
        "| # | class | severity | pages | times | features | stages | confirmed / rejected / added | why |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rank, item in enumerate(summary.classes, start=1):
        features = ", ".join(f"{name} {count}" for name, count in item.features.most_common(3))
        stages = ", ".join(f"{name} {count}" for name, count in item.stages.most_common(3))
        lines.append(f"| {rank} | {item.name} | {item.severity} | {len(item.pages)} | "
                     f"{item.occurrences} | {features or '—'} | {stages or '—'} | "
                     f"{item.confirmed} / {item.rejected} / {item.added} | {item.why or '—'} |")
    lines += ["", "## Where the review overturns a check", "",
              "A check's fault rejected, or a major added: each is a page "
              "Alessandro checks (spec 0021, decision 2).", ""]
    lines += [f"- {name}" for name in summary.overturned] or ["None."]
    if summary.changed or record.get("previous"):
        lines += ["", "## Against the previous run", "",
                  ", ".join(f"{verdict} {summary.changed.get(verdict, 0)}"
                            for verdict in CHANGED_VERDICTS), ""]
        lines += [f"- **worse: {name}** — {note}" for name, note in summary.worse]
    lines += ["", "## Majors beside scores all at 1.000", ""]
    if not summary.cross_checked:
        lines += ["**Not checked.** No `scores.json` was found for these pages, "
                  "so nothing could be cross-checked — which is not the same as "
                  "nothing being found."]
    else:
        lines += [f"- **{f.page}** {f.n} `{f.check}: {f.fault}` — {f.element}"
                  for f in summary.unreported] or ["None."]
    if summary.unanswered or summary.unstaged:
        lines += ["", "## Still to answer", ""]
        lines += [f"- {name} {n}: no call" for name, n in summary.unanswered]
        lines += [f"- {name} {n}: a major with no stage" for name, n in summary.unstaged]
    lines += ["", "## Every opened page", ""]
    for entry in record.get("pages", ()):
        if not entry.get("opened"):
            continue
        lines += [f"### {entry.get('name')}", ""]
        if entry.get("why"):
            lines += [f"_Opened: {'; '.join(entry['why'])}._", ""]
        lines += [_fault_line(fault) for fault in entry.get("faults", ())] or ["- no fault"]
        if entry.get("changed"):
            lines.append(f"- **changed** · {entry['changed']} — {entry.get('changed_note', '')}")
        if entry.get("worst"):
            lines.append(f"- **worst** — {entry['worst']}")
        lines += [""]
    return "\n".join(lines) + "\n"


def pair(source: Path, render_html: Path, out: Path, *, label: str = "pair",
         render: Any = None, cap: int = MAX_SHEET_PX) -> list[Path]:
    """Compare one arbitrary PNG against one arbitrary page, outside any run.

    The general case the run-shaped entry point could not reach: a hand-written
    HTML file against a photograph, a render saved from anywhere against the
    page it claims to be.
    """
    if render is None:
        from doc_to_html.projection import screenshot as render
    out.mkdir(parents=True, exist_ok=True)
    width = Image.open(source).width
    shot = out / f"{label}-render.png"
    if render_html.suffix.lower() == ".png":
        shot = render_html
    else:
        render(render_html, shot, width=width)
    parts = contact_sheet(
        [Panel(f"SOURCE {source.name}", source),
         Panel(f"RENDER {render_html.name}", shot)],
        out / label, stamp=f"{label} · {date.today().isoformat()}", cap=cap)
    if shot != render_html and shot.exists():
        shot.unlink()
    return parts
