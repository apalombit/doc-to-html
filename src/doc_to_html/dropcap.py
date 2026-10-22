"""Drop caps — spec 0019, C4.

`newsletter_0008` opens its first story with a `T` set four lines deep and
floated, the paragraph's lines running round it. The model reads the first
line as `he stretch of towpath between Bridge Street`, a heading, with the
`T` a line of its own it never places; the render drew a body-size `The`
at the head of an `h1` and the paragraph after it indented.

**The rule.** A glyph two or more of the paragraph's lines tall, at its
top left, with the paragraph's lines set beside it, is the paragraph's
first letter:

- it is read on its own, by tesseract on the glyph's crop, where the
  model left it out — kept as the model read it where it did;
- it is put back before the paragraph's first word, and that first line
  rejoins its paragraph: every Block whose first line is set beside it is
  one paragraph;
- it is drawn floated, as tall as the page draws it (`Cell.display`
  `cap`, its size measured by `looks`).

Model-free and offline; `tools/rederive.py` runs it after `raised`.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .ir import BBox, Block, Cell, Document, Kind, Reading, Zone
from .locate import CONFIDENT, TESSERACT, available
from .preprocess import _cv2

ImageArray = np.ndarray

TALL = 2.0
"""How many of the paragraph's lines tall a first letter stands, at least,
to be a drop cap: `newsletter_0008`'s `T` stands 3.3."""

REACH = 4
"""How many lines down from the first line a drop cap is looked for."""

SCALE = 3
"""How many times the glyph's crop is enlarged for tesseract: a 41px
capital reads as one letter at three times its size."""


def _ink(grey: ImageArray) -> ImageArray:
    """Dark type on a light ground, by Otsu over the crop."""
    cv2 = _cv2()
    _, ink = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return ink > 0


NARROW = 0.25
"""How narrow a letter stands against its height, at most: a serif `I`
stands about a third as wide as tall, a rule or a fill's edge a tenth."""

SOLID = 0.85
"""How much of its box a letter's ink covers, at most: a block of colour
covers all of it."""


def glyph(grey: ImageArray, zone: Zone, index: int) -> BBox | None:
    """The drop cap at the top left of `zone.blocks[index]`, where the page
    sets one: an ink component standing from within half a line of the
    first placed line's top, at the Zone's left edge and starting left of
    that line, `TALL` lines tall or more, shaped as a letter, with another
    line of the paragraph — in this Block or the ones after it — set
    beside it. None where there is none."""
    cv2 = _cv2()
    placed = [cell.bbox for block in zone.blocks[index:] for cell in block.lines
              if cell.bbox is not None]
    if zone.bbox is None or not any(cell.bbox for cell in zone.blocks[index].lines):
        return None
    first = placed[0]
    height, width = grey.shape[:2]
    line = (first.bottom - first.top) * height
    if line <= 0:
        return None
    # A line past the first line's left: a `T`'s arm reaches over the `he`
    # tucked under it.
    left = max(0, int(zone.bbox.left * width - line))
    right = min(width, int(first.left * width + line))
    top = max(0, int(first.top * height - line / 2))
    bottom = min(height, int(np.ceil(first.top * height + REACH * line * 1.6)))
    if right - left < 2 or bottom - top < 2:
        return None
    ink = _ink(grey[top:bottom, left:right]).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    best = None
    for component in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[component])
        if (h < TALL * line or y > line or w > 2 * h or w < NARROW * h
                or area > SOLID * w * h or left + x >= first.left * width
                or abs(left + x - zone.bbox.left * width) > line):
            continue
        if best is None or h > best[3]:
            best = (x, y, w, h)
    if best is None:
        return None
    x, y, w, h = best
    box = BBox((left + x) / width, (top + y) / height,
               (left + x + w) / width, (top + y + h) / height)
    beside = [b for b in placed[1:]
              if box.top <= b.top <= box.bottom and b.left >= box.right - 0.5 * line / width]
    return box if beside else None


def _letter(grey: ImageArray, box: BBox) -> str:
    """The one letter tesseract reads off the glyph's crop, or ''."""
    cv2 = _cv2()
    height, width = grey.shape[:2]
    crop = grey[int(box.top * height):int(np.ceil(box.bottom * height)),
                int(box.left * width):int(np.ceil(box.right * width))]
    big = cv2.resize(crop, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "cap.png"
        cv2.imwrite(str(path), big)
        out = subprocess.run(
            ["env", "OMP_THREAD_LIMIT=1", TESSERACT, str(path), "stdout", "--psm", "10",
             "tsv"], capture_output=True, text=True, check=False).stdout
    for row in out.splitlines()[1:]:
        cols = row.split("\t")
        if (len(cols) >= 12 and len(cols[11].strip()) == 1 and cols[11].strip().isalpha()
                and float(cols[10]) >= CONFIDENT):
            return cols[11].strip()
    return ""


def read(image: ImageArray | None, document: Document) -> int:
    """Each drop cap placed and put back before its paragraph's first word,
    and the Blocks set beside it made one paragraph, in place. Returns how
    many were found."""
    if image is None:
        return 0
    cv2 = _cv2()
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    found = 0
    for zone in document.zones:
        if zone.kind is not Kind.PROSE:
            continue
        index = 0
        while index < len(zone.blocks):
            block = zone.blocks[index]
            if any(cell.display == "cap" for cell in block.lines):
                index += 1
                continue
            box = glyph(grey, zone, index)
            cap = _cap(grey, block, box) if box is not None else None
            if box is None or cap is None:
                index += 1
                continue
            cap.bbox, cap.display = box, "cap"
            found += 1
            # The Blocks whose first line is set beside the cap are its
            # paragraph's.
            joined = [block]
            for after in zone.blocks[index + 1:]:
                top = next((cell.bbox for cell in after.lines if cell.bbox is not None), None)
                if top is None or not (box.top <= top.top <= box.bottom):
                    break
                joined.append(after)
            if len(joined) > 1 or block.kind != "paragraph":
                zone.blocks[index:index + len(joined)] = [Block(
                    kind="paragraph", lines=[line for part in joined for line in part.lines],
                    gap=block.gap)]
            index += 1
    return found


def _cap(grey: ImageArray, block: Block, box: BBox) -> Cell | None:
    """The Cell the cap is: the model's own, a lone letter left unplaced
    before the first placed line; or one tesseract reads, put first, where
    the first line opens on a lowercase letter. None where neither."""
    first = next(index for index, cell in enumerate(block.lines) if cell.bbox is not None)
    for cell in block.lines[:first]:
        text = cell.text.strip()
        if len(text) == 1 and text.isalpha():
            return cell
    opening = block.lines[first].text.lstrip()
    if not opening[:1].islower() or not available():
        return None
    letter = _letter(grey, box)
    if not letter:
        return None
    cell = Cell(readings=[Reading(engine="tesseract", text=letter)])
    block.lines.insert(first, cell)
    return cell
