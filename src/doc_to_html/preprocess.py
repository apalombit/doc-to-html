"""Source Image -> Rectified Image.

Everything downstream reads the rectified image and never the raw photograph.
This is not a convenience: Bands are horizontal stripes, so they only mean
anything on an axis-aligned page, and an Escalation crop taken from a skewed
photo is just a bigger skewed crop.

Rectification must stay deterministic. Corrections are anchored to coordinates
in this space, so any change to the geometry here needs RECTIFIER_VERSION bumped
in ir.py — otherwise stored Corrections silently point at the wrong pixels.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .ir import BBox, Source, Zone

log = logging.getLogger(__name__)

ImageArray = NDArray[Any]
"""Pixels as OpenCV hands them over: (H, W, 3), BGR, uint8."""

TARGET_LONG_EDGE = 3508
"""A4 at 300dpi. Crops are taken from this, so it sets the resolution ceiling."""

MODEL_INPUT_LONG_EDGE = 1024
"""Roughly what a vision model sees. Anything denser must be sliced, not shrunk.

This is the budget for *extraction*, which has to read glyphs.
"""

LAYOUT_LONG_EDGE = 512
"""What the layout pass sees, and deliberately less.

Finding regions is coarse work: the layout prompt says not to read the text at
all, so it needs positions rather than glyphs. A vision model's token count scales
with pixels, so halving each dimension is roughly a quarter of the image tokens —
which is context a small model was otherwise spending before it reached an answer.

Note this had never actually been exercised: every fixture is under 1024px, so the
"layout runs on a downscaled page" design was a no-op until this existed.
"""


class RectifyError(RuntimeError):
    """The pixels could not be read at all.

    One of only two things that abort a Conversion: with no Rectified Image there
    is nothing to lay out, so there is nothing to show.
    """


@dataclass
class Rectified:
    """The normalised image and its provenance."""

    image: ImageArray
    """A numpy array (H, W, 3). Warped, turned over, deskewed, **equalised**
    and resized — what every reading pass and the model itself are shown."""

    source: Source

    plain: ImageArray | None = None
    """The same pixels in the same geometry, without `equalise`.

    **Colour must be measured here and nowhere else.** `equalise` is CLAHE: it
    divides lightness by an estimate of the illumination, which is exactly right
    for making faint type legible and exactly wrong for reading what colour
    something was. Measured on `darkdeck_0009`'s first KPI card on 2026-09-21:
    the card stands **31** channel-sum away from its page in the source and
    **5** after equalisation — under `style.SAME_COLOUR`, so every card on that
    page read as unfilled. The palette suffers the same way more quietly, the
    page's true near-black `(18,22,28)` reading as `(0,0,6)`.

    Identical geometry is the point: a Zone's `BBox` indexes either array, so
    `zone_pixels` can crop one and `style.chrome` measure the other without a
    second coordinate space to keep in step.

    Optional so a `Rectified` built by hand in a test is still valid; callers
    fall back to `image`, which is wrong about colour but never absent.
    """

    warped: bool = False
    """Whether a page quadrilateral was found and the page flattened to it.

    False means the image was used as-is, which is the normal answer for a scan or
    a screenshot. Worth knowing when a render comes out badly: an unwarped
    photograph of a page shot at an angle explains a great deal.
    """

    inverted: bool = False
    """Whether the page was printed light on dark and has been turned over.

    Recorded rather than left implicit, because it changes the pixels every later
    pass reads *and* the pixels the model is shown. A render that comes back in
    the wrong polarity, or a palette that reads as paper-white on a page that is
    not, starts here. See `ground_is_dark`.
    """


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cv2() -> Any:
    """OpenCV, imported on use.

    Keeping it out of module scope means the IR, the Probes and the renderer can
    be imported — and the fixtures exercised — without it.
    """
    import cv2

    return cv2


def resize_long_edge(image: ImageArray, long_edge: int) -> ImageArray:
    """Scale so the longer side is at most `long_edge`. Never enlarges.

    `long_edge` is a ceiling rather than a target. Enlarging a small source adds
    no detail while multiplying the cost of every crop taken from it, and a
    screenshot 862px wide is not improved by being told it is A4.
    """
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= long_edge:
        return image
    scale = long_edge / longest
    resized: ImageArray = _cv2().resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=_cv2().INTER_AREA,
    )
    return resized


def to_png(image: ImageArray) -> bytes:
    """Encode for transport to an Engine. PNG because reading text off a
    re-compressed JPEG is a self-inflicted wound."""
    ok, buffer = _cv2().imencode(".png", image)
    if not ok:
        raise RectifyError("could not encode image as PNG")
    return bytes(buffer.tobytes())


PAD_X = 0.03
"""Horizontal padding on a Zone crop.

Wider than the vertical pad, and measured rather than chosen. On
`example/invoice.png` a real `qwen3-vl:4b` returns boxes ending at `right=0.94`
while the right-aligned prices run to about 0.97. The old symmetric 0.01 was
8.6px on an 862px page — narrower than the character it was meant to rescue — so
every crop clipped the last glyph and the model dutifully read `$300.00` as
`$300.0` and `Price` as `Pric`. Three model families reproduced it exactly,
because they were all reading the same short image.
"""

PAD_Y = 0.01
"""Vertical padding on a Zone crop, deliberately left small.

Padding is not free: it pulls a neighbour's content into the crop. On this page
the two are not symmetric risks. Side-by-side Zones sit far apart — 0.38 and
0.75 in the same Band, a gap of 0.37 — while stacked Zones nearly touch, 0.63
and 0.64 between the two tables. A 0.03 vertical pad would make those two
overlap and re-create the split-table failure that took five runs to remove.
"""


def crop(image: ImageArray, bbox: BBox, *,
         pad_x: float = PAD_X, pad_y: float = PAD_Y) -> ImageArray:
    """Cut a Zone out of the Rectified Image at full resolution.

    This is what buys back the resolution the layout downscale gave away. Padding
    is added because a bounding box drawn by a model routinely clips a descender
    or the last character of a line — and on measured evidence it does that far
    more readily on the right edge than the bottom, so the two axes are padded
    differently. See `PAD_X` and `PAD_Y`.
    """
    height, width = image.shape[:2]
    left = int(max(0.0, bbox.left - pad_x) * width)
    right = int(min(1.0, bbox.right + pad_x) * width)
    top = int(max(0.0, bbox.top - pad_y) * height)
    bottom = int(min(1.0, bbox.bottom + pad_y) * height)
    if right - left < 1 or bottom - top < 1:
        raise RectifyError(f"crop for {bbox} is empty at {width}x{height}")
    return np.ascontiguousarray(image[top:bottom, left:right])


class NoGeometry(ValueError):
    """A Zone with no bounding box cannot be cropped, so it cannot be read."""


class EmptyZone(ValueError):
    """A Zone whose crop carries no ink, so there is nothing in it to read."""


MIN_ZONE_INK = 0.001
"""How much of a Zone's crop must be ink before the Zone is believed.

Measured, not chosen. On `example/invoice.png` the six Zones `qwen3-vl:4b`
returns carry between 1.5% and 18.7% ink (`debug/runs/23-fresh-invoice-e2e/`).
The two Zones that made `qwen3.5:4b` fabricate content carry **0.0%**
(`debug/runs/25-invoice-qwen35-longedge768/`, `zone_00` and `zone_01`, 164 and
170 byte PNGs). The gap between those populations is three orders of magnitude,
so the threshold sits fifteen times below the sparsest real Zone rather than
splitting a difference.

Low on purpose. This exists to reject *blank* crops, not thin ones: a signature
or a one-line note is a real Zone with little ink, and a threshold tuned to catch
those would start deleting content. On an 819x135 crop 0.1% is about 110 pixels —
a few glyphs, and less than one character of a heading.

It also clears the noise floor. A photographed blank still measures 0.00% at
`INK_LEVEL` up to sigma 20 and 0.06% at sigma 20 itself, so the threshold sits
above what noise alone produces and fifteen times below the sparsest real Zone.
"""


def zone_pixels(image: ImageArray, zone: Zone) -> ImageArray:
    """This Zone's own pixels, at the resolution the Rectified Image has them.

    Every reader of a single Zone starts here — the Extractors, and the
    classification pass that decides the Zone's Kind before them. It lives beside
    `crop` rather than with the Extractors because two callers cutting a Zone out
    with different padding would be judging different pixels: the classifier
    would name a Kind for one image and the Extractor would read another, and
    the two could disagree about what the block is with nothing in the IR to say
    why.

    The layout pass looked at a downscaled page because finding regions is coarse
    work. Reading one is not, and this is where the resolution that bought is
    spent.
    """
    if zone.bbox is None:
        raise NoGeometry(
            f"{zone.kind.value} Zone in band {zone.band} has no bounding box"
        )
    return crop(image, zone.bbox)


def figure_pixels(rectified: Rectified, zone: Zone) -> str | None:
    """A FIGURE Zone's pixels as the page printed them, for the render to draw.

    **Not `zone_pixels`, on three counts, each measured on 2026-09-26:**

    - **No padding.** `zone_pixels` pads a crop so a model can read the last
      glyph, and a pad pulls in the neighbour: `invoice_0002`'s padded ACME
      tile carries the first letters of the address beside it — `Acm`,
      `Soft`, `Field`, `info`. The box is snapped onto its ink, and on all
      three corpus figures a 3px ring outside it holds no ink at all.
    - **`plain`, not `image`.** Equalisation is for reading; a picture is
      drawn in the colours it has. See `Rectified.plain`.
    - **Turned back over** on a light-on-dark page, which `rectify` inverted
      for the readers and which the reader of the render never saw inverted.

    Compressed at PNG level 9 rather than OpenCV's default: the barcode is
    13.5 KB of base64 at the default and 0.7 KB at 9, pixel for pixel the same.

    None when the Zone has no box, so the render keeps its placeholder.
    """
    if zone.bbox is None:
        return None
    plain = rectified.plain if rectified.plain is not None else rectified.image
    if rectified.inverted:
        plain = 255 - plain
    pixels = crop(plain, zone.bbox, pad_x=0.0, pad_y=0.0)
    ok, buffer = _cv2().imencode(".png", pixels,
                                 [_cv2().IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise RectifyError("could not encode a figure as PNG")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def height_over_input_budget(image: ImageArray, zone: Zone) -> int | None:
    """This Zone's crop height, when it is taller than a model can be shown.

    What *extraction* loses to the budget, and the axis is the point. Height,
    because height is what slicing would address if it were built: slices are
    horizontal bands. A Zone merely wider than the budget loses a few percent of
    scale and no rows, and flagging that would bury a real finding in noise.

    Deliberately not the test classification uses — see
    `long_edge_over_input_budget`, which asks a different question about the same
    crop because the two passes lose different things to the same shrink.
    """
    if zone.bbox is None:
        return None
    height = int(zone_pixels(image, zone).shape[0])
    return height if height > MODEL_INPUT_LONG_EDGE else None


def long_edge_over_input_budget(image: ImageArray, zone: Zone) -> int | None:
    """This Zone's crop's longer side, when the crop will be shrunk to fit.

    What *classification* loses to the budget. `resize_long_edge` scales on
    `max(height, width)`, so this is the exact condition under which the model is
    shown fewer pixels than the crop has — on either axis.

    Wider-and-not-taller matters here where it does not for extraction, and that
    asymmetry is the whole reason this is a second function rather than a second
    caller of the first. Extraction loses rows, which only a vertical shrink
    takes. Classification loses the shading under a heading row and the colons
    after a label — evidence a *horizontal* shrink destroys just as thoroughly,
    and evidence that is the entire basis on which this pass tells `table` from
    `pairs` from `prose`. A full-width Zone of a 3508px page is 2-3x over this
    budget while being nowhere near over the height one.
    """
    if zone.bbox is None:
        return None
    height, width = zone_pixels(image, zone).shape[:2]
    longest = int(max(height, width))
    return longest if longest > MODEL_INPUT_LONG_EDGE else None


DETECT_LONG_EDGE = 800
"""Page edges are a coarse feature. Finding them on a small copy is faster and
less distracted by the texture of the paper."""

MIN_PAGE_AREA = 0.25
"""A quadrilateral covering less than this much of the frame is not the page.

Photographs of documents are framed on the document. A small quadrilateral is a
panel, a photograph within the page, or a shadow — warping to it would crop the
document to one of its own parts.
"""

MAX_PAGE_AREA = 0.97
"""A quadrilateral covering more than this much of the frame is the frame.

This is what sends a clean screenshot down the fallback path: a white document
filling a white image has no page edge to find, and the largest contour is the
image border. Warping to the border is a no-op with rounding error attached.
"""

MAX_DESKEW_DEGREES = 15.0
"""Beyond this, the estimate is not skew.

A page photographed sideways is a rotation of about 90 degrees, and correcting it
means knowing which way up the text runs — which means reading the text. That is
an Engine's job, not the rectifier's, and guessing between 90 and 270 degrees
would be a coin flip that destroys every coordinate downstream.
"""


GROUND_BUCKET = 8
"""How coarsely grey is rounded before the page's own level is counted.

An antialiased page holds thousands of near-identical shades and the true mode
of the raw levels is a coin toss between them. Eight levels, matching
`style.BUCKET`, because these are the same measurement taken for two purposes
and two different roundings would eventually disagree about one page.
"""

GROUND_DARK = 128
"""Below this level, the page's own ground is dark and the ink on it is light."""

GROUND_MAJORITY = 0.25
"""How much of the image the modal level must hold before it is read as ground.

**What this guard does and does not do.** It refuses to call a page dark when no
level dominates it — a photograph with a shadow gradient, a scan of a heavily
illustrated page — because there the mode is close to a coin toss between
neighbouring buckets and acting on it would invert an image on the strength of
noise. It does **not** distinguish a page that is dark from a crop that is
mostly mark: a tile 80% covered in ink has a dominant dark level and is
indistinguishable from a dark page by histogram alone. That is why polarity is
decided once, on the whole page, in `rectify` — where "mostly dark" really does
mean a dark page — and never per crop.

Measured on the corpus: `darkdeck_0009`'s raw page holds its modal level over
0.745 of the frame and every light page over 0.84, so no document in the corpus
is anywhere near this bound.
"""


def ground_level(image: ImageArray) -> int:
    """The grey level this image's own ground sits at, bucketed.

    **One measurement, two callers.** `ground_is_dark` below uses it to decide
    polarity; Thread 2/B needs the same modal background for the style record.
    Building a second one is how the binarisation and the palette end up
    disagreeing about what colour a page is.
    """
    cv2 = _cv2()
    if image.size == 0:
        return 255
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    counts = np.bincount((grey // GROUND_BUCKET).ravel(),
                         minlength=256 // GROUND_BUCKET)
    return int(np.argmax(counts)) * GROUND_BUCKET


def ground_is_dark(image: ImageArray) -> bool:
    """Whether this page is printed light on dark.

    **The fault this exists for, measured.** Every binarisation in this file
    treats dark pixels as ink, which is a claim about the page and not about
    printing. `darkdeck_0009` is 96.2% below mid-grey, so read that way nearly
    the whole page is one mass of ink: `count_regions` returns **1** for a page
    with ten regions, the detector's grouping has nothing to work with, and the
    document converted as a single Zone with no finding of any kind against it.

    **Why polarity is tested before `equalise` and not after.** Equalisation
    divides lightness by a closed estimate of the illumination, which on a dark
    page divides dark by dark and blows the result out. Measured on
    `darkdeck.png` in one sitting on 2026-09-19: raw modal level **16** over
    0.745 of the frame, and after equalisation modal **248** with 55% of the
    page reading as ink and one region found. Inverting first and then
    equalising gives modal 248 over 0.89 of the page, 5.0% ink, and **10**
    regions. The same test on `invoice_0001` reads modal 248 and does not fire.

    **Ask it about a page, not about a crop.** A tile mostly covered in ink has
    a dominant dark level too, and nothing in a histogram separates the two —
    which is why `rectify` settles polarity once for the whole page and no crop
    is ever asked again. See `GROUND_MAJORITY` for what the majority guard does
    instead, which is to decline when no level dominates at all.
    """
    cv2 = _cv2()
    if image.size == 0:
        return False
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    counts = np.bincount((grey // GROUND_BUCKET).ravel(),
                         minlength=256 // GROUND_BUCKET)
    level = int(np.argmax(counts)) * GROUND_BUCKET
    share = float(counts.max()) / grey.size
    return level < GROUND_DARK and share >= GROUND_MAJORITY


def with_dark_ink(image: ImageArray) -> ImageArray:
    """The same page with its ink dark, turned over if it was not.

    Every threshold downstream of this reads dark as ink. Normalising polarity
    once, here, is what lets all of them keep saying so.
    """
    inverted: ImageArray = 255 - image
    return inverted if ground_is_dark(image) else image


def _ink(gray: ImageArray) -> ImageArray:
    """Dark pixels, as a binary mask. Deterministic: Otsu, no sampling."""
    cv2 = _cv2()
    _, mask = cv2.threshold(with_dark_ink(gray), 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary: ImageArray = mask
    return binary


INK_LEVEL = 200
"""How dark a pixel must be to count as ink, on the equalised grey.

An absolute cut, and **deliberately not Otsu** — which is what `_ink` uses
everywhere else in this file. The difference is whether the input is guaranteed
to contain ink. `skew_angle` gets a whole page and Otsu's bimodal assumption
holds. This gets one Zone's crop, and the entire question is whether that crop
contains anything at all.

Otsu always splits a histogram into two classes, so on a blank crop it splits
paper noise and calls half of it ink. Measured on synthetic blanks: 0.0% at
uniform white, but **30.2% at sigma 2, 47.0% at sigma 8** — sensor noise on a
photograph of blank paper. A guard built on Otsu would rate an empty crop as the
densest Zone on the page and pass exactly the case it exists to catch.

An absolute cut is available here only because the Rectified Image has already
been intensity-equalised — flattening the illumination so a fixed level means
the same thing across the page is what `equalise` is for. Measured at this
level: blank crops stay at 0.00% through sigma 20 (0.06%), while the sparsest
real Zone on `invoice.png` is 1.53%.
"""


def ink_fraction(image: ImageArray) -> float:
    """How much of this image is ink, between 0 and 1.

    The one measurement in the system that reads the pixels back. Everything else
    checks the model's answer against another part of the model's answer — Bands
    against each other, Probe sums against a stated total, extracted content
    against its Zone's Kind — so a region the model located where nothing is
    printed passes every existing check and reaches an Extractor, which is asked
    what a blank image says and answers.
    """
    cv2 = _cv2()
    if image.size == 0:
        return 0.0
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float((grey < INK_LEVEL).mean())


GAP_MERGE_X = 0.02
GAP_MERGE_Y = 0.04
"""How far uncovered ink is spread before it is grouped, as fractions of the page.

Without this the check finds nothing useful: connected components of raw ink are
*words*, and every word is far below `MIN_GAP_AREA`. On the line-item table
`qwen3.5:4b` missed entirely, undilated components reported **zero** Gaps for a
block covering 28% of the page. Spreading first is what turns words into the
mass a human would call "a table nobody read".

Taller than it is wide, because that is the shape of the merge wanted: lines
should join into a block, while two columns side by side should stay apart. The
asymmetry is also where the safety margin is. Measured against `invoice.png`,
geometry that is *correct* (`debug/runs/23-fresh-invoice-e2e/`) yields no Gaps at
0.02 x 0.04 and none at 0.02 x 0.06, but **one** at 0.03 x 0.06 and two at
0.03 x 0.08 — the horizontal term is what starts welding real Zones to their
neighbours and inventing findings. So the vertical term carries the merging and
the horizontal one stays well below where false Gaps begin.
"""

MIN_GAP_AREA = 0.004
"""How much of the page a patch of uncovered ink must cover to be a Gap.

Sized against what the check exists to catch and what it must ignore. The
line-item table `qwen3.5:4b` missed entirely in
`debug/runs/25-invoice-qwen35-longedge768/` spans about 28% of the page — three
orders of magnitude clear of this. What sits just underneath is padding
overspill and antialiasing along a Zone edge, which is a few hundred pixels.

Not tuned finer, because a Gap is a *finding* rather than a fact: it enters the
Ladder and gets looked at again. A threshold precise enough to catch a stray
word would report one on every document and make the finding worthless.
"""

MIN_GAP_THICKNESS = 0.01
"""How thick, as a fraction of the page's short edge, a mark must be to be content.

A **Separator** is ink and is explicitly not a Zone: a horizontal rule, a panel
border, a column divider. Every one of them is a few pixels thick, so thickness
is part of telling a rule from a paragraph without knowing what either says.

On `invoice.png` this is about 5.6px against a text line of roughly 15px.

Applied to *raw* ink, before `GAP_MERGE_X`/`GAP_MERGE_Y` spread it. After
dilation everything is thick — a 3px rule on a 600px page comes out 27px — so a
thickness test on grouped ink cannot see a Separator at all.
"""

SEPARATOR_ASPECT = 10.0
"""How much longer than it is thick a mark must be before it is a Separator.

Thickness alone is not enough, and using it alone deletes content: the stem of a
letter is as thin as a rule. What distinguishes them is that a rule is also
*long* — it runs the width of a panel — while a glyph is thin and short.

Requiring both is what lets the check drop a table's ruling without dropping the
narrow characters in the row above it.
"""


def content_ink(image: ImageArray) -> ImageArray:
    """Ink a reader would call content, as a binary mask.

    Dark pixels at `INK_LEVEL`, with **Separators removed** — a horizontal rule,
    a panel border, a column divider. They are ink and are explicitly not
    content, so anything reasoning about where the content on a page is has to
    drop them first or it reasons about the ruling too.

    Separators go from the mask rather than from the findings, because grouping
    welds a rule to whatever sits near it: once a panel border has merged with
    the paragraph beside it there is no component left that is recognisably a
    rule.
    """
    cv2 = _cv2()
    height, width = image.shape[:2]
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask: ImageArray = (grey < INK_LEVEL).astype(np.uint8) * 255

    short_edge = min(width, height)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    for i in range(1, count):
        _, _, w, h, _ = stats[i]
        thin = min(w, h) < MIN_GAP_THICKNESS * short_edge
        long_for_its_thickness = max(w, h) >= SEPARATOR_ASPECT * max(1, min(w, h))
        if thin and long_for_its_thickness:
            mask[labels == i] = 0
    return mask


REGION_GAP = 0.04
"""How wide a blank run must be, as a fraction of the page's short edge, to end
one region and begin the next. Used by `count_regions`.

**Calibrated on two fixtures, and it overcounts on both** — which is the whole
reason `count_regions` is only ever stated as a ceiling:

| fixture | regions on the page | `count_regions` at 0.04 |
|---|---|---|
| `invoice_0001` | 6 | 8 |
| `invoice_0002` | 10 | 11 |

0.04 is the best *joint* value rather than the best for either. No single gap
gets both right: at 0.08 `invoice_0001` measures a correct 6 and `invoice_0002`
collapses to **1**, the whole page welded into one region. Do not chase one
number that serves both — the sweep in `tools/cv_layout_probe.py` is where this
gets re-calibrated, and it prints the whole curve for exactly that reason."""

MIN_ROW_GAP = 4
"""Blank rows that separate one printed line from the next, in pixels.

Line spacing on `invoice.png` is roughly 20px between 15px lines, so this has a
lot of room. It is a floor against antialiasing joining two lines, not a tuned
value."""

MIN_COLUMN_GAP = 6
"""Blank columns that separate one column of a table from the next, in pixels.

**An absolute count, deliberately not a fraction of the crop's width.** A
fraction works on `invoice_0001`, whose two-column table has a 530px gutter, and
destroys `sample_table_0003`: at 4% of a 960px crop the threshold is 38px, wider
than any gutter in a five-column table, so all five collapse into one band and
the measurement reports two columns where there are five. At 6px the same three
tables measure 2, 2 and 5 columns — all correct."""

MIN_BAND = 4
"""How much ink, along the axis being projected, counts as a band rather than a
mark.

`content_ink` already drops separators, so this is not what excludes a table's
ruling. It excludes what survives that: a stray descender, an antialiased edge, a
dot."""


def ink_bands(profile: ImageArray, min_gap: int, min_size: int) -> list[tuple[int, int]]:
    """Runs of ink in a projection, split where the blank is wide enough.

    One helper for both axes, because a row of a table and a column of one are
    the same question asked ninety degrees apart: project the ink onto an axis,
    and the stretches that survive are the structure.

    `tools/cv_layout_probe.py` has `_runs_of_blank` and `_slices_between` doing
    this for the XY-cut arm. That duplication is known and is not resolved here —
    unifying a probe with shipping code is its own change, and commit 080f7aa,
    which collapsed three copies of the geometry ruler into one, is the record of
    how that should be done when it is done.
    """
    bands: list[tuple[int, int]] = []
    start: int | None = None
    gap = 0
    for index, value in enumerate(profile):
        if value > 0:
            if start is None:
                start = index
            gap = 0
            continue
        if start is None:
            continue
        gap += 1
        if gap >= min_gap:
            end = index - gap
            if end - start + 1 >= min_size:
                bands.append((start, end))
            start = None
    if start is not None and len(profile) - start >= min_size:
        bands.append((start, len(profile) - 1))
    return bands


@dataclass(frozen=True)
class TableGrid:
    """How many rows and columns a table crop actually has, read off the pixels.

    **The point of this is that it is not the model's opinion.** The extraction
    pass returns rows and cells, and on a wide, short table it returns them
    wrongly: `invoice_0001`'s Zone 4 is two printed lines and comes back as four
    rows, each cut in half, because its two columns sit ~800px apart with nothing
    between them. Two prompt attempts failed to move that — run 13 and run 48,
    the latter returning output byte-identical to the run before it — so the
    remedy has to come from something the prompt cannot consult.

    This reads nothing and understands nothing. It counts bands of ink down the
    crop and across it, which is why it is trustworthy: there is no judgement in
    it to get wrong.

    Measured against three real tables: `invoice_0001` Zone 4 gives 2x2 and Zone 5
    gives 5x2, both correct. `sample_table_0003` gives 17x5 where the truth is
    16x5 — the columns right, the rows one over, against a hand-typed Zone box
    that CLAUDE.md already flags as 0.605-0.854 IoU against its own ink. So the
    row count is **not yet proven** on a crop this tool did not choose, and that
    is why a caller should state this to a model rather than enforce it on one.
    """

    rows: int
    columns: int
    row_bands: list[tuple[int, int]]
    column_bands: list[tuple[int, int]]


def table_grid(crop: ImageArray) -> TableGrid:
    """Count a table crop's rows and columns by projecting its ink.

    Down the crop for rows, across it for columns. Separators are already gone —
    `content_ink` removes them — so the horizontal rule above a totals row does
    not become a sixth row, and a column divider does not become a column.
    """
    mask = content_ink(crop)
    rows = ink_bands(mask.sum(axis=1), MIN_ROW_GAP, MIN_BAND)
    columns = ink_bands(mask.sum(axis=0), MIN_COLUMN_GAP, MIN_BAND)
    return TableGrid(rows=len(rows), columns=len(columns),
                     row_bands=rows, column_bands=columns)


def printed_lines(crop: ImageArray) -> int:
    """How many lines of type are printed in this crop. No model, no reading.

    The measurement behind spec 0007 Phase A-1's honesty rule. A Zone that was
    read *at all* satisfies every other check in the system — it has content, it
    is `complete`, no Failure names it — and a reading that came back with two
    of its thirty-six rows looks exactly like a reading of a two-row region.
    Counting bands of ink is the one cheap thing that can disagree with the
    answer, because it is not the answer: it is the same projection `table_grid`
    does, over the same mask, with the vertical rules taken out first for the
    reason `_without_vertical_rules` gives.

    It counts *printed lines*, which is not the same as rows, blocks or pairs —
    a wrapped table cell is two printed lines in one row, and a caption is a
    line that is not a row at all. So it is only ever safe as a floor under a
    gross shortfall, never as an expected count. `orchestrator.shortfall` is
    where that judgement lives, and it is deliberately coarse.
    """
    mask = _without_vertical_rules(content_ink(crop))
    return len(ink_bands(mask.sum(axis=1), MIN_ROW_GAP, MIN_BAND))


def ink_share(image: ImageArray, box: BBox) -> float:
    """How much of the page's content ink lies inside this box.

    A share of the *ink*, not of the area, because that is the quantity a
    finding needs to be honest about: "a region covering 6% of the page" says
    nothing a reader can act on when the page is mostly margin, while "12% of
    what is printed on this page" is the sentence that would have stopped
    `receipt_0010`'s 77 lost tokens being filed as a possible mark.
    """
    mask = content_ink(image)
    total = float((mask > 0).sum())
    if total <= 0:
        return 0.0
    height, width = mask.shape[:2]
    left, right = int(box.left * width), int(box.right * width)
    top, bottom = int(box.top * height), int(box.bottom * height)
    inside = mask[max(0, top):max(0, bottom), max(0, left):max(0, right)]
    return float((inside > 0).sum()) / total


@dataclass(frozen=True)
class CaptionBand:
    """A crop's first line of ink, and how far it stands apart from the rest.

    Measurement only. Nothing here decides whether the line *is* a caption — that
    is asked of a model, for a reason the numbers below make plain.
    """

    top: int
    bottom: int
    """The first band's edges, in crop rows."""

    gap_below: int
    """Blank rows between this band and the next."""

    median_gap: int | None
    """The typical blank between the bands that follow, or `None` when there are
    fewer than three bands in all and there is nothing to compare against."""

    lines: int
    """How many bands the crop holds altogether. Always 2 or more."""

    head_columns: int
    body_columns: int
    """Columns of ink in the first band, and in everything below the cut.

    The two numbers `aligns_to_grid` compares. Kept as fields rather than
    recomputed, so the contact sheet reports the same pair the decision used.
    """

    @property
    def cut_row(self) -> int:
        """The crop row a caption-less body starts at — the middle of the blank.

        The middle rather than the band's own edge, so the cut clears this line's
        descenders without reaching the next line's ascenders.
        """
        return self.bottom + max(1, self.gap_below // 2)

    @property
    def aligns_to_grid(self) -> bool:
        """Whether the first line is a grid's heading row rather than a caption.

        **The measurable half of a distinction the model gets wrong in one
        direction only.** A heading row has one cell per column of the values
        under it and its words sit over the columns they name; a caption spans
        the region and ignores that grid. Counting columns either side of the cut
        separates the two without reading a word.

        An equality of counts, not a threshold — the same shape as `table_grid`,
        and calibrated on nothing. Measured over the 16 Zone crops in runs 71 and
        72a that have a band to test:

        - **2 true positives**: `invoice_0001`'s two tables, 2 columns against 2.
        - **0 false positives**: every real caption differs — `sample_table_0003`
          gives 1 against 6, `invoice_0002`'s panels 1 against 2.

        `head_columns > 1` is required so a single-column list of lines under a
        one-word caption cannot read as a grid.
        """
        return self.head_columns > 1 and self.head_columns == self.body_columns


def _without_vertical_rules(mask: ImageArray) -> ImageArray:
    """The same ink with any rule drawn down the side of the region removed.

    **A rule is not a printed line, and leaving it in costs the whole region.**
    Banding projects ink across each row, so a single column inked from top to
    bottom makes *every* row inked and the crop reads as one unbroken band —
    which `caption_band` then refuses, because one band means nothing sits under
    the first line. Two of `sample_semantic_0005`'s Zones were never asked for a
    Title for exactly this reason: a 3px `border-left` at columns 10-12 of one
    crop and 487-489 of the other. Removed, they read as 3 and 4 bands with the
    heading first, which is what they look like. Measured live, run 84 against
    83: those two Zones gained their Titles and **nothing else on the corpus
    moved**, 12 findings to 10. Which Zones it would reach was derived before the
    run — `caption_band` is arithmetic — and came back exact.

    The test is deliberately the strictest one available — inked in *every* row,
    so only a run spanning the full height qualifies. A rule beside a paragraph
    is that; a tall glyph, a bullet column and a table's vertical gridline
    between two rows of cells are not, because text leaves gaps between lines.

    Falls back to the original when clearing would leave nothing, so a crop that
    is genuinely solid still reports one band and is refused, rather than
    reporting none and dividing by zero further down.
    """
    inked = mask > 0
    if inked.size == 0:
        return mask
    rules = inked.all(axis=0)
    if not rules.any() or rules.all():
        return mask

    without = mask.copy()
    without[:, rules] = 0
    return without


def caption_band(crop: ImageArray) -> CaptionBand | None:
    """The crop's first printed line, when there is anything printed below it.

    `None` when the crop holds fewer than two bands, and **that is the whole
    safety property for a Zone whose box is a fragment**. One band means there is
    nothing under the first line, so there is no caption to lift off and no body
    to leave behind. Structural rather than a judgement: it asks whether a second
    line exists, not whether the first one looks like a heading.

    It matters because over-splitting is real and common. Over run 69's 36 Zone
    crops, 20 hold a single band — all six of `sample_css_0004`'s and eight of
    `sample_semantic_0005`'s, which are headings standing as Zones of their own.
    Without this guard `sample_css_0004`'s "Card heading" would have its only
    line taken as its own Title and then read again as its content.

    **The gap it measures is reported, never thresholded.** A caption is
    sometimes set far apart — `invoice_0002`'s three panels give 30, 33 and 29
    rows against median line gaps of 10, 7 and 10 — and sometimes not at all:
    `sample_table_0003`'s caption gives **19 against a median of 20**. A rule
    keyed on that ratio would miss the one case the whole change is gated on,
    which is why the numbers stay out of `CAPTION_PROMPT` and reach only the
    contact sheet. See `engines.ollama.CAPTION_PROMPT`.

    **The column counts are a different matter and do decide something.** See
    `CaptionBand.aligns_to_grid`: they are compared for equality rather than
    against a threshold, and they separate a heading row from a caption cleanly
    where the gap does not.
    """
    mask = _without_vertical_rules(content_ink(crop))
    bands = ink_bands(mask.sum(axis=1), MIN_ROW_GAP, MIN_BAND)
    if len(bands) < 2:
        return None

    gaps = [bands[index + 1][0] - bands[index][1]
            for index in range(1, len(bands) - 1)]
    top, bottom = bands[0]
    cut = bottom + max(1, (bands[1][0] - bottom) // 2)
    head = ink_bands(mask[top:bottom + 1].sum(axis=0), MIN_COLUMN_GAP, MIN_BAND)
    body = ink_bands(mask[cut:].sum(axis=0), MIN_COLUMN_GAP, MIN_BAND)
    return CaptionBand(
        top=top, bottom=bottom,
        gap_below=bands[1][0] - bottom,
        median_gap=sorted(gaps)[len(gaps) // 2] if gaps else None,
        lines=len(bands),
        head_columns=len(head), body_columns=len(body),
    )


def crop_row_as_fraction(image: ImageArray, bbox: BBox, row: int) -> float:
    """Where one row of a Zone's crop falls on the page, as a fraction of height.

    The inverse of `crop`'s vertical arithmetic, and it exists so a cut measured
    in crop rows can be *described* in page coordinates for the contact sheet
    without a second, drifting copy of that arithmetic. `tests/test_caption.py`
    pins the two together.
    """
    height = image.shape[0]
    top = int(max(0.0, bbox.top - PAD_Y) * height)
    # The row's centre, not its top edge. `x / height * height` lands a hair
    # under `x` in binary, so naming the edge makes `int()` round-trip to the row
    # above roughly half the time and the drawn box slips by a pixel.
    return float(min(1.0, (top + row + 0.5) / height))


MAX_SNAP_GROWTH = 0.05
"""How far an edge may travel outward looking for the rest of its ink, as a
fraction of the page.

A backstop, not a working limit. Growth already stops the moment the boundary row
or column is blank, so on any real page it ends after a few pixels of a clipped
descender. This exists for the pathological answer — run 25's slivers, where a
box holding 0.0% ink sits inside a dense region and every row it meets is inked.
Without a cap such a box would grow until it hit its neighbours' midpoints and
turn a visible failure into a plausible-looking one.

Five percent of the page is about 28px on `invoice.png`, against a text line of
roughly 15px: enough to recover a clipped line, not enough to acquire another.
"""


def _grow_edge(has_ink: Callable[[int], bool], start: int, step: int,
               limit: int) -> int:
    """Walk an edge outward while the line it lands on still carries ink.

    Stops on the first blank line, so an edge can never come to rest part-way
    through a line of text or a logo — which is the whole point of growing rather
    than only trimming.

    Bounded by comparison rather than by equality: a cap can legitimately land on
    the far side of the edge when two boxes already overlap, and `edge != limit`
    would then walk away from the limit for ever and index the mask from the
    wrong end.
    """
    edge = start
    if step < 0:
        while edge > limit and has_ink(edge - 1):
            edge -= 1
    else:
        while edge < limit and has_ink(edge):
            edge += 1
    return edge


def snap_to_ink(image: ImageArray, boxes: list[BBox]) -> list[BBox]:
    """Move each box's edges onto the ink it was drawn around.

    The layout pass asks a model for metric coordinates on a 384x251 thumbnail,
    and runs 26-28 measured that it cannot produce them: every coordinate lands
    on a coarse mental grid, 2.25x the linear pixels changes nothing, and stating
    the image's exact dimensions makes it monotonically worse. This stops asking.
    The model says *which* regions exist and in what order; the page says where
    their edges are.

    Per edge: trim inward past blank lines to the ink, then grow outward while
    the boundary line still carries ink, capped at the midpoint to the nearest
    box that could be grown into and at `MAX_SNAP_GROWTH`.

    Four properties, each of them a test:

    - **Idempotent.** The trim/grow pair is iterated to a fixed point here, so
      snapping a snapped layout returns it unchanged. Without the loop a
      cap-limited edge could move again on a second call, because the cap is
      computed from where the boxes currently are.
    - **Cannot create an overlap.** Two boxes growing towards each other stop at
      their shared midpoint, so a layout that satisfied `validate_bands` before
      still does.
    - **Invisible on good geometry.** A box already tight against its ink comes
      back unchanged.
    - **Silent on a blank Zone.** A box with no ink in it is returned untouched
      and left to the empty-crop guard. Two mechanisms claiming one failure is
      how a Finding ends up reported twice and fixed neither time.

    Separators are not ink here, because `content_ink` has already removed them:
    a box must not stretch to reach a horizontal rule that is explicitly not
    content.
    """
    if not boxes:
        return []

    height, width = image.shape[:2]
    mask = content_ink(image)

    snapped = list(boxes)
    for _ in range(4):
        moved = [_snap_one(mask, box, snapped, width, height) for box in snapped]
        if moved == snapped:
            break
        snapped = moved
    return snapped


def _snap_one(mask: ImageArray, box: BBox, others: list[BBox],
              width: int, height: int) -> BBox:
    """One box, trimmed and grown against the ink, capped by its neighbours."""
    left = min(max(round(box.left * width), 0), width)
    right = min(max(round(box.right * width), 0), width)
    top = min(max(round(box.top * height), 0), height)
    bottom = min(max(round(box.bottom * height), 0), height)
    if right - left < 1 or bottom - top < 1:
        return box

    inside = mask[top:bottom, left:right]
    if not inside.any():
        return box  # a blank Zone is the empty-crop guard's finding, not ours

    rows = np.flatnonzero(inside.any(axis=1))
    columns = np.flatnonzero(inside.any(axis=0))
    trimmed_top, trimmed_bottom = top + int(rows[0]), top + int(rows[-1]) + 1
    trimmed_left, trimmed_right = left + int(columns[0]), left + int(columns[-1]) + 1

    reach_y = int(MAX_SNAP_GROWTH * height)
    reach_x = int(MAX_SNAP_GROWTH * width)
    row_ink = lambda row: bool(mask[row, trimmed_left:trimmed_right].any())  # noqa: E731

    new_top = _reached(
        _grow_edge(row_ink, trimmed_top, -1, 0),
        trimmed_top, reach_y, _cap(box, others, "up", height), low=True)
    new_bottom = _reached(
        _grow_edge(row_ink, trimmed_bottom, 1, height),
        trimmed_bottom, reach_y, _cap(box, others, "down", height), low=False)

    column_ink = lambda col: bool(mask[new_top:new_bottom, col].any())  # noqa: E731
    new_left = _reached(
        _grow_edge(column_ink, trimmed_left, -1, 0),
        trimmed_left, reach_x, _cap(box, others, "left", width), low=True)
    new_right = _reached(
        _grow_edge(column_ink, trimmed_right, 1, width),
        trimmed_right, reach_x, _cap(box, others, "right", width), low=False)

    return BBox(new_left / width, new_top / height,
                new_right / width, new_bottom / height)


def _reached(target: int, trimmed: int, reach: int, cap: int | None, *,
             low: bool) -> int:
    """Where the edge actually lands, once the two limits have had their say.

    The reach is **all or nothing**, not a partial move. An edge that would have
    to travel further than `MAX_SNAP_GROWTH` is looking at ink that runs on and
    on — run 25's sliver inside a dense block — and following it part of the way
    would leave the edge in the middle of that ink, which is the one place the
    grow step exists to avoid. Refusing to move at all leaves the box visibly
    wrong, which is the honest outcome.

    Refusing rather than truncating also keeps the whole snap idempotent: a
    partial move measured from wherever the edge currently sits would advance
    again on every call.
    """
    if abs(target - trimmed) > reach:
        target = trimmed
    if cap is None:
        return target
    return max(target, cap) if low else min(target, cap)


def _cap(box: BBox, others: list[BBox], direction: str,
         span: int) -> int | None:
    """How far this edge may travel before it would meet a neighbour.

    The midpoint of the gap, so two boxes growing towards each other meet and
    stop rather than overlap. Only boxes that overlap on the *other* axis count:
    a Zone in the next column cannot be grown into by moving downward, and
    letting it cap the growth would pin every box in a two-column Band to its
    neighbour's height.
    """
    if direction in ("up", "down"):
        near = [
            other for other in others
            if other is not box
            and other.right > box.left and other.left < box.right
        ]
        edges = (
            [other.bottom for other in near if other.bottom <= box.top]
            if direction == "up" else
            [other.top for other in near if other.top >= box.bottom]
        )
        here = box.top if direction == "up" else box.bottom
    else:
        near = [
            other for other in others
            if other is not box
            and other.bottom > box.top and other.top < box.bottom
        ]
        edges = (
            [other.right for other in near if other.right <= box.left]
            if direction == "left" else
            [other.left for other in near if other.left >= box.right]
        )
        here = box.left if direction == "left" else box.right

    if not edges:
        return None
    neighbour = max(edges) if direction in ("up", "left") else min(edges)
    return round((neighbour + here) / 2 * span)


def uncovered_regions(image: ImageArray, boxes: list[BBox]
                      ) -> list[tuple[BBox, float]]:
    """Patches of uncovered ink, each bounded to its own ink and measured.

    The same search `uncovered_ink` has always done, reporting two things it
    could not: a box drawn round the **ink** rather than round the dilation that
    grouped it, and how much of the page's ink is actually in there.

    **Both matter, and both were found by looking at three documents.** The
    grouping kernel spreads ink by 2% of the page across and 4% down before
    components are taken — without that, components are *words* — so the
    component's own box overlaps whatever sits within that margin. On
    `form_0007` and `nonlatin_0014` the missing title's box bled into the Zones
    above and below it, and a box that overlaps its neighbours cannot be placed
    in a valid Band, so the one region worth recovering on each page was the one
    region refused. Re-bounding to the ink inside the component removes the
    bleed without touching the grouping that found it.

    The share is measured the same way, over the pixels rather than the
    rectangle, and that is what stops a finding lying. On `receipt_0010` the
    dilation welds the page's leftover edges into a single component whose box
    is the whole page; asked about the rectangle, it holds 100% of the page's
    ink, and a finding saying so would be false in the direction this phase
    exists to prevent. Asked about the uncovered pixels, it holds 1.5%.
    """
    cv2 = _cv2()
    height, width = image.shape[:2]
    mask = _uncovered_mask(image, boxes)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(1, int(width * GAP_MERGE_X)), max(1, int(height * GAP_MERGE_Y))),
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        cv2.dilate(mask, kernel), connectivity=8
    )
    # Of the *page's* ink, not of the uncovered ink. Dividing by the uncovered
    # total would make every region a large share of a small thing — a 2px
    # sliver on `form_0007` reported 100%, which as a finding is a lie in the
    # direction this phase exists to prevent.
    total = float((content_ink(image) > 0).sum())
    found: list[tuple[BBox, float]] = []
    for i in range(1, count):
        x, y, w, h, _ = stats[i]
        if (w * h) / (width * height) < MIN_GAP_AREA:
            continue
        # The ink this component grouped, as opposed to the area it spread over.
        inside = np.argwhere((labels == i) & (mask > 0))
        if not inside.size:
            continue
        top, left = inside.min(axis=0)
        bottom, right = inside.max(axis=0)
        found.append((
            BBox(float(left) / width, float(top) / height,
                 float(right + 1) / width, float(bottom + 1) / height),
            float(inside.shape[0]) / total if total else 0.0,
        ))
    return found


def _uncovered_mask(image: ImageArray, boxes: list[BBox]) -> ImageArray:
    """Content ink with every box's padded footprint removed.

    Boxes are subtracted with the same padding `crop` adds, so ink the Extractor
    was actually shown is not then reported as ink nobody covered.

    Separators come off the whole page, before any box is subtracted. Doing it
    the other way round leaves a rule that a box happens to overlap broken into
    stubs too short for the aspect test to recognise, so the half of a rule
    nobody covered would be reported as content nobody covered.
    """
    height, width = image.shape[:2]
    mask = content_ink(image)
    for box in boxes:
        left = int(max(0.0, box.left - PAD_X) * width)
        right = int(min(1.0, box.right + PAD_X) * width)
        top = int(max(0.0, box.top - PAD_Y) * height)
        bottom = int(min(1.0, box.bottom + PAD_Y) * height)
        mask[top:bottom, left:right] = 0
    return mask


def uncovered_ink(image: ImageArray, boxes: list[BBox]) -> list[BBox]:
    """Patches of ink that no box contains — candidate Gaps.

    The only check in the system that can see content the layout pass never
    detected. Everything else reasons from the Zones outward, so a block nobody
    put a Zone on leaves the IR self-consistent and every Probe passing, and the
    document is simply missing a table.

    Deliberately weaker than the Coverage Audit `orchestrator._audit` describes,
    and not a substitute for it. This finds *ink*, not content: it cannot tell a
    decorative mark from a lost paragraph, and it is blind to the other half of
    the problem — a Zone that covers its content and reads it wrongly. What it
    has instead is independence. It is not a model, so unlike an auditor sharing
    the layout model's weights it cannot share the blind spot that caused the
    miss.

    Boxes are subtracted with the same padding `crop` adds, so ink the Extractor
    was actually shown is not then reported as ink nobody covered.

    The rectangles come back bounded to their own ink rather than to the
    dilation that grouped it, and `uncovered_regions` — which this is now a thin
    reading of — says why that matters and reports the share alongside.
    """
    return [box for box, _ in uncovered_regions(image, boxes)]


def _runs_of_blank(profile: ImageArray, least: int) -> list[tuple[int, int]]:
    """Stretches of `least` or more empty lines, as half-open (start, end)."""
    empty = np.flatnonzero(profile == 0)
    if empty.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(empty) > 1)
    starts = np.concatenate(([empty[0]], empty[breaks + 1]))
    ends = np.concatenate((empty[breaks], [empty[-1]]))
    return [(int(a), int(b) + 1) for a, b in zip(starts, ends)
            if b + 1 - a >= least]


def _slices_between(gaps: list[tuple[int, int]], span: int) -> list[tuple[int, int]]:
    """What is left once the gaps are removed."""
    pieces, cursor = [], 0
    for start, end in gaps:
        if start > cursor:
            pieces.append((cursor, start))
        cursor = end
    if cursor < span:
        pieces.append((cursor, span))
    return pieces


def regions_from_xy_cut(mask: ImageArray, gap: float) -> list[tuple[BBox, int, int]]:
    """Recursive projection cutting, emitting Bands and columns natively.

    Blind dilation cannot group, because it has no notion of axis alternation: a
    kernel wide enough to weld a line together is wide enough to weld two columns
    together, and its best six-region answer welded the whole page into two
    full-height strips. Cutting alternates axes by construction —

        ink profile down the page -> widest full-width blank bands -> Bands
          within each Band: profile across -> gutters -> columns

    — which is the IR's own vocabulary rather than a bag of boxes, so its output
    can be compared with an expected IR on Band and column as well as on
    position.

    Two levels deep and no further. Cutting naturally produces a split *tree*,
    and Zones are a flat list by definition; going deeper would need a flattening
    rule, which is a design decision this probe exists to inform rather than to
    take. `gap` is a fraction of the page's short edge, applied to both axes so
    one number sweeps the whole method.

    **Moved here verbatim from `tools/cv_layout_probe.py`**, where it was the
    XY-cut arm, so that `count_regions` and the probe measure with one
    implementation rather than two that can drift. `ink_bands` above answers a
    similar question and is deliberately *not* reused: its edge handling differs,
    and rebuilding this on it would move the counts that `REGION_GAP` is
    calibrated against. Unifying the two is its own change — see `ink_bands`.
    """
    height, width = mask.shape[:2]
    short_edge = min(width, height)
    least = max(1, int(gap * short_edge))

    rows = (mask > 0).sum(axis=1)
    bands = _slices_between(_runs_of_blank(rows, least), height)

    found = []
    for band_index, (top, bottom) in enumerate(bands):
        strip = mask[top:bottom]
        if not strip.any():
            continue
        columns = _slices_between(
            _runs_of_blank((strip > 0).sum(axis=0), least), width)
        placed = 0
        for left, right in columns:
            cell = strip[:, left:right]
            if not cell.any():
                continue
            # Tighten to the cell's own ink: the cut lands in the middle of a
            # gutter, and a box that keeps half the gutter is not the Zone.
            ys = np.flatnonzero(cell.any(axis=1))
            xs = np.flatnonzero(cell.any(axis=0))
            found.append((
                BBox((left + int(xs[0])) / width, (top + int(ys[0])) / height,
                     (left + int(xs[-1]) + 1) / width,
                     (top + int(ys[-1]) + 1) / height),
                band_index, placed,
            ))
            placed += 1
    return found


def count_regions(image: ImageArray, gap: float = REGION_GAP) -> int:
    """How many regions the ink on this page falls into. No model.

    A measurement, not an opinion, and that is the point: two attempts to talk
    `qwen3-vl:4b` out of over-segmenting a nested page were behavioural
    instructions and both were ignored — `LAYOUT_PROMPT` already says a panel's
    inner rows "are not regions themselves" and the model returned 72 regions for
    a 10-region page anyway. The same asymmetry `DTH_TABLE_GRID_HINT` exploits
    applies here: this model complies with *how many* and ignores *which*.

    **Read the answer as an upper bound.** It overcounts on both fixtures it is
    calibrated against (8 for a true 6, 11 for a true 10), which is why
    `engines.ollama.with_regions` states it as a ceiling. A ceiling is safe in a
    way an exact count is not: a page whose regions the model already gets right
    sits under the bound and feels no pressure to split, while a runaway is
    still capped.

    Boxes are discarded here deliberately. Using them as geometry is a separate
    and much larger change — their Bands do not match the expected IR on either
    fixture, and their IoU is well below what the layout pass already achieves on
    `invoice_0001`.
    """
    return len(regions_from_xy_cut(content_ink(image), gap))


def _order_corners(quad: ImageArray) -> ImageArray:
    """Corners as top-left, top-right, bottom-right, bottom-left.

    By sum and difference of coordinates rather than by angle, which keeps the
    ordering stable for the near-rectangles this is used on.
    """
    points = quad.reshape(4, 2).astype(np.float32)
    by_sum = points.sum(axis=1)
    by_diff = (points[:, 0] - points[:, 1])
    return np.array(
        [
            points[np.argmin(by_sum)],
            points[np.argmax(by_diff)],
            points[np.argmax(by_sum)],
            points[np.argmin(by_diff)],
        ],
        dtype=np.float32,
    )


def find_page_quad(image: ImageArray) -> ImageArray | None:
    """The page's four corners in full-resolution coordinates, or None.

    None is a legitimate and common answer — a scan or a screenshot has no page
    edge in it — and it is the answer that matters most, because the alternative
    to admitting it is a confident warp to something that is not the page.
    """
    cv2 = _cv2()
    small = resize_long_edge(image, DETECT_LONG_EDGE)
    scale = max(image.shape[:2]) / max(small.shape[:2])

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(small.shape[0] * small.shape[1])

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        share = cv2.contourArea(approx) / frame_area
        if not MIN_PAGE_AREA <= share <= MAX_PAGE_AREA:
            continue
        found: ImageArray = _order_corners(approx) * scale
        return found
    return None


def warp_to_quad(image: ImageArray, quad: ImageArray) -> ImageArray:
    """Flatten the page, sizing the output from the quadrilateral's own edges."""
    cv2 = _cv2()
    top_left, top_right, bottom_right, bottom_left = quad
    width = int(round(max(
        float(np.linalg.norm(top_right - top_left)),
        float(np.linalg.norm(bottom_right - bottom_left)),
    )))
    height = int(round(max(
        float(np.linalg.norm(bottom_left - top_left)),
        float(np.linalg.norm(bottom_right - top_right)),
    )))
    if width < 2 or height < 2:
        raise RectifyError(f"page quadrilateral is degenerate: {quad.tolist()}")

    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(quad, target)
    warped: ImageArray = cv2.warpPerspective(image, matrix, (width, height))
    return warped


DESKEW_STEP_DEGREES = 0.5
"""How finely candidate angles are tried. Half a degree over a 3000px page moves
its far edge by 25px, which is finer than any Zone boundary the layout pass
draws."""

DESKEW_MARGIN = 1.05
"""How much better than level a candidate must score to be worth rotating to.

A page of text has a decisive best angle. Without a margin, image noise picks a
fractional angle on a perfectly straight page, and rotating costs a resampling
blur while moving every coordinate.
"""


def _line_sharpness(mask: ImageArray, angle: float) -> float:
    """How crisply the ink stacks into horizontal lines at this angle.

    Rows of text produce a row-sum profile of tall peaks and empty troughs, so its
    variance peaks when the lines are level. This is the classic projection-profile
    estimate, used in preference to the minimum-area rectangle around the ink:
    that rectangle is dominated by the overall shape of the page's margins, and it
    reports a two-degree tilt on documents that are perfectly straight.
    """
    cv2 = _cv2()
    if angle:
        height, width = mask.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        mask = cv2.warpAffine(mask, matrix, (width, height), flags=cv2.INTER_NEAREST)
    profile = mask.sum(axis=1, dtype=np.float64)
    return float(profile.var())


def skew_angle(image: ImageArray) -> float:
    """The angle the text sits at, in degrees, or 0.0 when it cannot be told.

    Bounded to small angles by MAX_DESKEW_DEGREES: this corrects a tilt, never an
    orientation.
    """
    cv2 = _cv2()
    small = resize_long_edge(image, DETECT_LONG_EDGE)
    mask = _ink(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    if cv2.countNonZero(mask) < 50:
        return 0.0

    level = _line_sharpness(mask, 0.0)
    if level <= 0:
        return 0.0

    steps = int(MAX_DESKEW_DEGREES / DESKEW_STEP_DEGREES)
    candidates = [step * DESKEW_STEP_DEGREES for step in range(-steps, steps + 1)]
    best = max(candidates, key=lambda angle: _line_sharpness(mask, angle))
    if best == 0.0 or _line_sharpness(mask, best) < level * DESKEW_MARGIN:
        return 0.0
    return best


def deskew(image: ImageArray) -> ImageArray:
    """Rotate a small tilt out of the page, about its centre."""
    cv2 = _cv2()
    angle = skew_angle(image)
    if abs(angle) < 0.25:
        # Below this, rotating costs a resampling blur and buys nothing.
        return image

    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated: ImageArray = cv2.warpAffine(
        image, matrix, (width, height),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def equalise(image: ImageArray) -> ImageArray:
    """Flatten shadows and uneven lighting, leaving colour alone.

    Two steps, and the order matters. First the illumination field is estimated by
    closing the lightness channel with a kernel larger than any glyph — that
    removes the text and leaves the paper — and the lightness is divided by it.
    That is what actually flattens a shadow: CLAHE alone is a local contrast
    stretch and leaves a gradient across the page almost untouched, which is worth
    knowing because it is the obvious thing to reach for. CLAHE then follows, to
    recover contrast in whatever the division left flat but faint.

    Lightness only. Equalising the colour channels would shift the hues a Mark is
    recognised by, and nothing downstream is allowed to read colour anyway — see
    docs/adr/0002.
    """
    cv2 = _cv2()
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)

    span = max(15, min(lightness.shape[:2]) // 20 | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (span, span))
    illumination = cv2.GaussianBlur(
        cv2.morphologyEx(lightness, cv2.MORPH_CLOSE, kernel), (0, 0), span / 3
    )
    flattened = cv2.divide(lightness, illumination, scale=255)
    flattened = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(flattened)

    merged: ImageArray = cv2.cvtColor(
        cv2.merge((flattened, a_channel, b_channel)), cv2.COLOR_LAB2BGR
    )
    return merged


def rectify(path: Path) -> Rectified:
    """Detect the page, flatten it, straighten it, even out the light.

    Steps, in order:
      1. find the page quadrilateral (contour detection on a downscaled copy)
      2. perspective-warp it to a flat rectangle
      3. turn the page over if it is printed light on dark
      4. rotate a residual tilt out of the text
      5. equalise intensity (CLAHE) to flatten shadows and uneven lighting
      6. resize so the long edge is at most TARGET_LONG_EDGE

    Step 5 is also kept *undone*, in `Rectified.plain`: equalisation is what
    makes faint type readable and what makes colour unreadable, so the passes
    that read and the passes that measure colour are given different arrays of
    the same pixels. See `Rectified.plain` for the measurement.

    Step 3 is before both of the steps that follow it, and that order is the
    whole of it: `equalise` divides lightness by an estimate of the illumination
    and blows out a dark page, and every threshold after it reads dark as ink.
    See `ground_is_dark` for what that cost `darkdeck_0009` and for the
    measurement. It changes the pixels the model is shown as well as the pixels
    the CV reads, which is why `Rectified.inverted` records that it happened.

    A page whose quadrilateral cannot be found is used as-is rather than guessed
    at — a bad warp is worse than no warp, because it silently distorts every
    coordinate downstream. All five of the project's fixtures take that path: a
    white document filling a white frame has no page edge in it, so nobody should
    read a passing end-to-end test as evidence that the geometry here works.

    Step 3 corrects a tilt and not an orientation. A page photographed sideways or
    upside down stays that way, because telling 90 degrees from 270 means reading
    the text, and a rectifier that guesses wrong ruins every coordinate in the IR.

    Every step is deterministic. Corrections are anchored in this coordinate
    space, so the same Source Image must always produce the same pixels — which is
    also why changing anything here means bumping RECTIFIER_VERSION in ir.py.
    """
    if not path.is_file():
        raise RectifyError(f"no such Source Image: {path}")

    cv2 = _cv2()
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RectifyError(f"OpenCV could not decode {path}")

    height, width = image.shape[:2]

    quad = find_page_quad(image)
    flattened = image if quad is None else warp_to_quad(image, quad)
    inverted = ground_is_dark(flattened)
    if inverted:
        log.info("the page is printed light on dark, so it is turned over "
                 "before equalisation")
        flattened = 255 - flattened
    straight = deskew(flattened)
    rectified = resize_long_edge(equalise(straight), TARGET_LONG_EDGE)
    # Same geometry, none of the photometry. See `Rectified.plain`.
    plain = resize_long_edge(straight, TARGET_LONG_EDGE)

    return Rectified(
        image=rectified,
        plain=plain,
        warped=quad is not None,
        inverted=inverted,
        source=Source(
            path=str(path),
            sha256=sha256_of(path),
            width=width,
            height=height,
            rectified_width=rectified.shape[1],
            rectified_height=rectified.shape[0],
        ),
    )


def slice_points(height: int, budget: int = MODEL_INPUT_LONG_EDGE,
                 overlap: float = 0.12) -> list[tuple[int, int]]:
    """Split a too-tall region into overlapping (top, bottom) slices.

    The overlap is what makes slicing safe: without it a row straddling a cut is
    seen as two half-rows by two passes, and neither reports a problem. With it,
    the repeated rows are matched during stitching and double as a consistency
    check on the seam.
    """
    if height <= budget:
        return [(0, height)]

    step = max(1, int(budget * (1 - overlap)))
    points = []
    top = 0
    while top < height:
        bottom = min(top + budget, height)
        points.append((top, bottom))
        if bottom >= height:
            break
        top += step
    return points
