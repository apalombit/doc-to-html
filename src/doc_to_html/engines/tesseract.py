"""Tesseract, as a source of word boxes.

Its place in the system is undecided on purpose. The argument for it is that it
does not *invent* plausible digits the way a small vision model can — it produces
obvious garbage instead, which is the safer failure. The argument against is that
on a skewed or shadowed photograph its layout analysis degrades badly, and it
degrades by finding *less*, which is a silent failure.

The first end-to-end slice runs vision-only and so measures what tesseract would
have to beat.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir import BBox


@dataclass
class TesseractEngine:
    name: str = "tesseract"

    def word_boxes(self, image: object) -> list[tuple[BBox, str]]:
        raise NotImplementedError("tesseract not yet wired")
