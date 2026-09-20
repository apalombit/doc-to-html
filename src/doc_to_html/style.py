"""What a page looks like, measured from its own pixels — the Style Record.

**All CV, zero model calls.** That is ADR 0005's decision and not a starting
position: colour is perception, the pixels are already in hand, and this project
has written down that a model complies with an instruction to *decide*
differently and ignores one to *perceive* differently. Sampling a pixel is
exact, free, deterministic and cannot hallucinate; asking a 4B model what colour
a band was is worse on all four counts.

**Measured on the page's own polarity, not on the Rectified Image's.**
`preprocess.rectify` turns a light-on-dark page over before equalising, so by
the time anything downstream sees `darkdeck_0009` it is a light page — and a
style record read off that would report white paper for a document printed on
near-black. `Rectified.inverted` says it happened and `measure()` undoes it for
the purpose of reading colour. This is the one place in the pipeline that wants
the original polarity back.

## What is here, and what is deliberately not

Here: ground, ink, accent and shade. Each is a modal colour over a class of
pixel, which is the cheapest honest statement about a page's palette.

**Not here yet: the type scale.** It was measured across the corpus on
2026-09-20 and it is not safe to ship. Ink-band height tracks the true CSS font
size closely — the per-Zone pooled mode lands at a median of **0.93** of it,
inside 0.75-1.13 on thirteen of fifteen documents — but `catalogue_0015` reads
**2.40x** because its dense cards merge a title, a price and a description into
one band, and `form_0007` and `menu_0012` sit at 0.75 and 0.69. No confidence
signal tried separated the bad estimate from the good ones: agreement within
+-25% of the mode reads 0.50 on `catalogue_0015` and 0.40 on `form_0007`, whose
estimate is *fine*. Shipping the estimate anyway would set 24px type on a
document whose real body is 10px, and `catalogue_0015` currently has the best
`height_ratio` in the corpus at 1.03. **Making the corpus's best document worse
to improve the others is not a trade worth making blind**, so the type scale
gets its own increment, measured against `height_ratio` directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .ir import Style
from .preprocess import ImageArray

BUCKET = 8
"""How coarsely a colour is rounded before the modal one is counted.

Eight levels per channel, not more. An antialiased page holds thousands of
near-identical shades and the true mode of the raw pixels is a coin toss
between them; bucketing collapses those into one. Coarser than this and a light
shaded band merges with the page it sits on, which is the distinction
`invoice_0002`'s caption bars exist to make.
"""

GROUND_NEAR = 60
"""Channel-sum distance within which a pixel is still the page, not a mark."""

INK_NEAR = 120
"""Channel-sum distance within which a mark is body ink rather than furniture."""

SATURATED = 60
"""Channel spread above which a pixel carries a hue rather than a grey level."""

MIN_ACCENT_SHARE = 0.002
"""How much of the page must carry a hue before an accent is claimed.

Below this the "accent" is antialiasing fringes and JPEG ringing around black
text, which every page has and no page means. Two thousandths is what
`scoring._sample` already uses for the same judgement on the same images, and
the two must agree: this decides whether the render *has* an accent and that
decides whether the scorer can *find* one.
"""


def modal(pixels: Any) -> tuple[int, int, int]:
    """The commonest colour, bucketed. int64 throughout, and that matters.

    The obvious packing — `r * 65536 + g * 256 + b` — overflows an int16 array
    at `g * 256` and comes back as a colour the image does not contain. It is
    silent, it is plausible, and it reported every page in the corpus as having
    the same background.

    Lives here rather than in `scoring` because both need it and two copies of
    a rounding rule is how the binarisation and the palette end up disagreeing
    about what colour a page is. `scoring` imports it.
    """
    flat = ((np.asarray(pixels, dtype=np.int64) // BUCKET) * BUCKET).reshape(-1, 3)
    if not flat.size:
        return 0, 0, 0
    keys = flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    key = int(values[int(np.argmax(counts))])
    return (key >> 16) & 0xFF, (key >> 8) & 0xFF, key & 0xFF


def measure(image: ImageArray, *, inverted: bool = False) -> Style:
    """The page's palette, from its own pixels.

    `image` is the Rectified Image as OpenCV holds it — BGR. `inverted` is
    `Rectified.inverted`, and passing it is what keeps a dark page dark; see the
    module docstring for why that is not optional.
    """
    pixels = np.asarray(image, dtype=np.int64)
    if inverted:
        pixels = 255 - pixels
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        return Style()
    pixels = pixels[:, :, ::-1]  # BGR as OpenCV holds it -> RGB as CSS wants it

    ground = modal(pixels)
    from_ground = np.abs(pixels - np.array(ground)).sum(axis=2)

    marked = from_ground > INK_NEAR
    ink = modal(pixels[marked]) if marked.any() else (26, 26, 26)

    # Furniture is everything that is neither the page nor its type: shaded
    # caption bars, rules, zebra striping, card fills. It is what a title bar
    # should be filled with, and a page with none of it has no title bars.
    from_ink = np.abs(pixels - np.array(ink)).sum(axis=2)
    furniture = (from_ground > GROUND_NEAR) & (from_ink > INK_NEAR)
    shade = modal(pixels[furniture]) if furniture.mean() > MIN_ACCENT_SHARE else None

    spread = pixels.max(axis=2) - pixels.min(axis=2)
    vivid = spread > SATURATED
    accent = modal(pixels[vivid]) if vivid.mean() > MIN_ACCENT_SHARE else None

    return Style(page_bg=ground, ink=ink, accent=accent, shade=shade)
