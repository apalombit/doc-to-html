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
