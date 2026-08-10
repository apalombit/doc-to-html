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

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .ir import BBox, Source, Zone

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
    """A numpy array (H, W, 3)."""

    source: Source

    warped: bool = False
    """Whether a page quadrilateral was found and the page flattened to it.

    False means the image was used as-is, which is the normal answer for a scan or
    a screenshot. Worth knowing when a render comes out badly: an unwarped
    photograph of a page shot at an angle explains a great deal.
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


def _ink(gray: ImageArray) -> ImageArray:
    """Dark pixels, as a binary mask. Deterministic: Otsu, no sampling."""
    cv2 = _cv2()
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
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
      their shared midpoint, so a layout that satisfied `_validate_bands` before
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
    """
    cv2 = _cv2()
    height, width = image.shape[:2]

    # Separators come off the whole page, before any box is subtracted. Doing it
    # the other way round leaves a rule that a box happens to overlap broken into
    # stubs too short for the aspect test to recognise, so the half of a rule
    # nobody covered would be reported as content nobody covered.
    mask = content_ink(image)

    for box in boxes:
        left = int(max(0.0, box.left - PAD_X) * width)
        right = int(min(1.0, box.right + PAD_X) * width)
        top = int(max(0.0, box.top - PAD_Y) * height)
        bottom = int(min(1.0, box.bottom + PAD_Y) * height)
        mask[top:bottom, left:right] = 0

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(1, int(width * GAP_MERGE_X)), max(1, int(height * GAP_MERGE_Y))),
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        cv2.dilate(mask, kernel), connectivity=8
    )
    found = []
    for i in range(1, count):
        x, y, w, h, _ = stats[i]
        if (w * h) / (width * height) < MIN_GAP_AREA:
            continue
        found.append(
            BBox(x / width, y / height, (x + w) / width, (y + h) / height)
        )
    return found


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
      3. rotate a residual tilt out of the text
      4. equalise intensity (CLAHE) to flatten shadows and uneven lighting
      5. resize so the long edge is at most TARGET_LONG_EDGE

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
    rectified = resize_long_edge(equalise(deskew(flattened)), TARGET_LONG_EDGE)

    return Rectified(
        image=rectified,
        warped=quad is not None,
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
