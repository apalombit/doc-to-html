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

from .ir import Source

TARGET_LONG_EDGE = 3508
"""A4 at 300dpi. Crops are taken from this, so it sets the resolution ceiling."""

MODEL_INPUT_LONG_EDGE = 1024
"""Roughly what a vision model sees. Anything denser must be sliced, not shrunk."""


@dataclass
class Rectified:
    """The normalised image and its provenance."""

    image: object
    """A numpy array (H, W, 3). Typed loosely so importing this module does not
    require OpenCV to be installed."""

    source: Source


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rectify(path: Path) -> Rectified:
    """Detect the page, correct perspective, fix orientation, equalise intensity.

    Steps, in order:
      1. find the page quadrilateral (contour detection on a downscaled copy)
      2. perspective-warp it to a flat rectangle
      3. correct orientation to portrait/landscape as the content implies
      4. equalise intensity (CLAHE) to flatten shadows and uneven lighting
      5. resize so the long edge is TARGET_LONG_EDGE

    A page whose quadrilateral cannot be found is used as-is rather than guessed
    at — a bad warp is worse than no warp, because it silently distorts every
    coordinate downstream.
    """
    raise NotImplementedError("rectification not yet wired")


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
