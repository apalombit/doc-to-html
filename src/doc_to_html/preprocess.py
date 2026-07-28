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

from .ir import BBox, Source

ImageArray = NDArray[Any]
"""Pixels as OpenCV hands them over: (H, W, 3), BGR, uint8."""

TARGET_LONG_EDGE = 3508
"""A4 at 300dpi. Crops are taken from this, so it sets the resolution ceiling."""

MODEL_INPUT_LONG_EDGE = 1024
"""Roughly what a vision model sees. Anything denser must be sliced, not shrunk."""


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


def crop(image: ImageArray, bbox: BBox, *, pad: float = 0.01) -> ImageArray:
    """Cut a Zone out of the Rectified Image at full resolution.

    This is what buys back the resolution the layout downscale gave away. A
    little padding is added because a bounding box drawn by a model routinely
    clips a descender or the last character of a line.
    """
    height, width = image.shape[:2]
    left = int(max(0.0, bbox.left - pad) * width)
    right = int(min(1.0, bbox.right + pad) * width)
    top = int(max(0.0, bbox.top - pad) * height)
    bottom = int(min(1.0, bbox.bottom + pad) * height)
    if right - left < 1 or bottom - top < 1:
        raise RectifyError(f"crop for {bbox} is empty at {width}x{height}")
    return np.ascontiguousarray(image[top:bottom, left:right])


def rectify(path: Path) -> Rectified:
    """Detect the page, correct perspective, fix orientation, equalise intensity.

    Steps, in order:
      1. find the page quadrilateral (contour detection on a downscaled copy)
      2. perspective-warp it to a flat rectangle
      3. correct orientation to portrait/landscape as the content implies
      4. equalise intensity (CLAHE) to flatten shadows and uneven lighting
      5. resize so the long edge is at most TARGET_LONG_EDGE

    A page whose quadrilateral cannot be found is used as-is rather than guessed
    at — a bad warp is worse than no warp, because it silently distorts every
    coordinate downstream.

    Steps 1-4 are not yet wired: the image is loaded and resized, and geometry is
    a pass-through. Nobody should read a passing end-to-end test as evidence that
    rectification works.
    """
    if not path.is_file():
        raise RectifyError(f"no such Source Image: {path}")

    cv2 = _cv2()
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RectifyError(f"OpenCV could not decode {path}")

    height, width = image.shape[:2]
    rectified = resize_long_edge(image, TARGET_LONG_EDGE)
    return Rectified(
        image=rectified,
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
