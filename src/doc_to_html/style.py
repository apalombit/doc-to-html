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

Here: ground, ink, accent and shade — each a modal colour over a class of
pixel, which is the cheapest honest statement about a page's palette — and per
region, its fill, its Title bar and whether the page draws a box around it.

**A border is found on the page, never grown from a Zone.** `rectangles()`
reads every drawn rectangle off the whole page and `box_around` says which
Zone each one belongs to. The obvious alternative — dilate a Zone's crop until
its rule comes into view — was measured on 2026-09-21 and cannot work: the
Zone's box has been snapped onto its *content* ink, `preprocess.content_ink`
deletes panel borders from that mask by name, and on `sample_css_0004` the
snapped box sits up to 256px inside its card because the text does not reach
the card's right edge. See `rectangles()` for the numbers and the corpus
result.

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

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .ir import BBox, Style
from .preprocess import ImageArray, _cv2, content_ink

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

MARGIN_SHARE = 0.06
"""How much of each edge is sampled to find the page's own ground.

**The ground is what the page is, not what most of it is covered by.**
`sample_css_0004` is white paper carrying two large `#f6f8fa` cards, and the
cards cover more of the image than the margin does, so a mode over the whole
image returns the card colour. That one error then propagates: the render tints
the entire page with it, and the cards become undetectable, because a fill
equal to the ground is not a fill. Measured over a frame instead — the outer
6% of each edge — the answer is the paper, which is what a margin almost always
is.

Six percent rather than more, because a page with a full-bleed header band has
that band at its top edge; the frame spans all four sides so three of them
outvote it.
"""

MIN_INK_CONTRAST = 0.35
"""How far from the ground, toward the opposite extreme, a colour must sit
before it is believed to be the page's type.

A fraction of the available range rather than a fixed distance, so it means the
same thing on a white page and on `darkdeck_0009`'s near-black.

**The case it exists for is `receipt_0010`**, the corpus's only photographed
page. Its paper is not uniformly white, so enough paper texture survives the
ink mask that the modal "ink" comes back `(196,193,187)` — barely a quarter of
the way to black — and the render sets pale grey type on a receipt printed in
black. Refusing to claim a colour is the right answer there: the house ink is a
known-safe default and a measurement this weak is not evidence. Set at 0.35
because the real inks on the corpus sit at 0.54 (`form_0007`) and above, and
the one false reading sits at 0.23.
"""

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


def dominant(pixels: Any) -> tuple[int, int, int]:
    """The commonest colour, as the page actually holds it.

    `modal` answers *which bucket* is commonest, which is all a **comparison**
    needs — the scorer buckets both sides and asks whether they agree. Emitting
    CSS is a different question, and bucketing alone gets it visibly wrong:
    `(x // 8) * 8` floors, so a pure white page comes back `#f8f8f8` and every
    render of a white document is laid on a faint grey. It was reported from
    looking at a render beside its source, not from any number.

    So the bucket picks the winner and the winner's own pixels give the colour,
    by median: exact on a flat page (255 stays 255), and robust to the
    antialiasing fringe that shares a bucket with the ground on a real one.
    """
    flat = np.asarray(pixels, dtype=np.int64).reshape(-1, 3)
    if not flat.size:
        return 0, 0, 0
    bucketed = (flat // BUCKET) * BUCKET
    keys = bucketed[:, 0] * 65536 + bucketed[:, 1] * 256 + bucketed[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    winner = values[int(np.argmax(counts))]
    true = np.median(flat[keys == winner], axis=0)
    return int(true[0]), int(true[1]), int(true[2])


def _frame(pixels: Any) -> Any:
    """The outer border of an image, as a flat list of pixels. See `MARGIN_SHARE`."""
    block = np.asarray(pixels)
    height, width = block.shape[:2]
    band = max(1, int(min(height, width) * MARGIN_SHARE))
    if height <= 2 * band or width <= 2 * band:
        return block.reshape(-1, block.shape[-1])
    return np.concatenate([
        block[:band].reshape(-1, block.shape[-1]),
        block[-band:].reshape(-1, block.shape[-1]),
        block[band:-band, :band].reshape(-1, block.shape[-1]),
        block[band:-band, -band:].reshape(-1, block.shape[-1]),
    ])


def _contrast(colour: tuple[int, int, int],
              ground: tuple[int, int, int]) -> float:
    """How far `colour` sits from `ground`, as a share of the room available.

    Per channel, toward whichever extreme is further from the ground — so it
    reads the same on white paper and on a near-black slide. The minimum across
    the three channels, because a colour that separates on one channel only is
    a tint of the page rather than its type.
    """
    room = [max(g, 255 - g) for g in ground]
    return min(abs(c - g) / r if r else 0.0
               for c, g, r in zip(colour, ground, room))


def _ink_mask(read: ImageArray, shape: tuple[int, ...]) -> Any:
    """The project's own ink mask over `read`, or `None` if it does not fit.

    `read` is the equalised image, because deciding *which* pixels are type is
    what equalisation is for. The shape check is what keeps the two arrays
    honest: they are the same geometry by construction, and a mismatch means a
    caller has paired a crop with somebody else's page.
    """
    try:
        mask = np.asarray(content_ink(read)) > 0
    except Exception:  # a caller holding something content_ink cannot read
        return None
    return mask if mask.shape == tuple(shape) else None


def measure(image: ImageArray, *, inverted: bool = False,
            read: ImageArray | None = None) -> Style:
    """The page's palette, from its own pixels.

    `image` is `Rectified.plain` — the page's real colours, as OpenCV holds
    them, BGR. `inverted` is `Rectified.inverted`, and passing it is what keeps
    a dark page dark; see the module docstring.

    `read` is the *equalised* `Rectified.image`, and the split between the two
    is the whole point. **Which pixels are ink is a question for the processed
    image; what colour they are is a question for the plain one.** They came
    apart on the corpus's only photographed page: `receipt_0010`'s paper is not
    uniformly white, so thresholding its plain pixels calls the paper texture
    ink and reports light grey type on a receipt printed in black. Equalisation
    exists to fix exactly that, and destroys colour doing it. So the mask comes
    from one array and the colours from the other, at identical geometry.

    `read=None` falls back to measuring both on `image`, which is right for a
    synthetic page and for any caller holding only one array.
    """
    pixels = np.asarray(image, dtype=np.int64)
    if inverted:
        pixels = 255 - pixels
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        return Style()
    pixels = pixels[:, :, ::-1]  # BGR as OpenCV holds it -> RGB as CSS wants it

    ground = dominant(_frame(pixels))

    from_ground = np.abs(pixels - np.array(ground)).sum(axis=2)

    # `content_ink` is the project's own binarisation — the one `ink_bands`,
    # `table_grid` and the coverage audit all read. Reusing it rather than
    # thresholding here is not only economy: a palette that disagreed with it
    # about which pixels are ink would report a colour for type that no other
    # pass believes is type.
    marked = _ink_mask(read if read is not None else image, pixels.shape[:2])
    if marked is None:
        marked = from_ground > INK_NEAR
    ink = dominant(pixels[marked]) if marked.any() else None
    if ink is None or _contrast(ink, ground) < MIN_INK_CONTRAST:
        # Not "measured as grey" — *not measured*. The default is the house ink,
        # which the renderer would have used anyway, and a Style whose ink was
        # never established should be indistinguishable from one never taken.
        ink = Style().ink

    # Furniture is everything that is neither the page nor its type: shaded
    # caption bars, rules, zebra striping, card fills. It is what a title bar
    # should be filled with, and a page with none of it has no title bars.
    from_ink = np.abs(pixels - np.array(ink)).sum(axis=2)
    furniture = (from_ground > GROUND_NEAR) & (from_ink > INK_NEAR)  # noqa: E501
    shade = dominant(pixels[furniture]) if furniture.mean() > MIN_ACCENT_SHARE else None

    spread = pixels.max(axis=2) - pixels.min(axis=2)
    vivid = spread > SATURATED
    accent = dominant(pixels[vivid]) if vivid.mean() > MIN_ACCENT_SHARE else None

    return Style(page_bg=ground, ink=ink, accent=accent, shade=shade)


SAME_COLOUR = 18
"""Channel-sum distance within which two measured colours are the same colour.

Six levels a channel. Tighter than `GROUND_NEAR`, because that one asks "is
this pixel part of the page" over noisy per-pixel data, while this compares two
values that are already modes over thousands of pixels. Loose enough to absorb
the ringing that makes a flat fill read a level or two apart at its two ends;
tight enough to keep `invoice_0002`'s caption bars distinct from the panel under
them, which is the distinction the whole measurement exists to make.

**Was 24, and that missed real cards by three.** `sample_css_0004` lays
`#f6f8fa` cards on white — 21 apart — and they read as unfilled. Swept over the
corpus on 2026-09-21 at 24 / 18 / 15 / 12 / 9: dropping to 18 gains exactly
`sample_css_0004`'s two cards and `sample_semantic_0005`'s TL;DR aside, all
three of them real fills, and **changes no other document at any value**. The
count is then flat from 18 down to 9, so this sits on a plateau rather than on
an edge — which is the property worth having in a threshold, more than the
particular number.
"""

MIN_FILL_COVERAGE = 0.55
"""How much of a region must be one colour before it counts as filled.

A Zone is mostly ground with type on it, so its modal colour is its fill
whether or not it has one. The share is what separates them: a genuinely
filled card is one flat colour over most of its area, while a region that
merely *contains* a shaded strip is not filled and must not be painted.
"""

BORDER_RUN = 0.80
"""How much of an edge must be inked before that edge counts as drawn."""

BORDER_EDGES = 3
"""How many of a rectangle's four edges must be drawn before it is a border.

Three rather than four. A card whose bottom edge falls outside its detected box
by a pixel is still a card, and requiring all four made `sample_css_0004`'s two
cards read as none. Two would accept an L of rules that nobody drew as a box.
"""

PAGE_SHARE = 0.80
"""A rectangle covering more than this much of the page **is** the page.

Re-measured 2026-09-21, and the guard earns its place on the corpus as it
stands: `invoice_0001`'s only drawn box is `div.invoice-box` at **0.981** of
the page — the frame around the whole invoice. Unguarded, every Zone on that
page sits inside it and every Zone is a card.

The figure was carried in this project's documents for a year as a result to
cite, attached to a finder that **was never in the tree**. It is a re-measured
number now, on this corpus, in this sitting.
"""

MIN_RECT_SHARE = 0.004
"""Smaller than this much of the page is not a panel.

`form_0007` draws 30 full boxes and 16 of them are `span.tick` checkboxes and
single-character entry cells at 0.000-0.001 of the page. They are *drawn* and
they are not containers: reporting them as Zone chrome would card every tick
box on the form. The fourteen `div.box` fields sit at 0.011-0.023, well clear.
"""

CONTAINED = 0.98
"""How much of a Zone must sit inside a rectangle for that rectangle to be its
box.

Not 1.0: a Zone snapped onto its ink can end a pixel outside a rounded corner,
and a Zone must not lose its card to antialiasing.
"""

CLOSE_PX = 3
"""Kernel for closing a rule broken by antialiasing before components are taken.

A 1px `#e1e8ed` border on `#f7f9fb` is not a solid run of identical pixels; it
is a run with gaps where the renderer softened it. Three is enough to bridge
them and too small to weld two adjacent cards into one.
"""


@dataclass
class Chrome:
    """What a page draws *around* a region, as opposed to inside it.

    All three are `None`/`False` for the overwhelmingly common case — a region
    sitting directly on the page with no treatment at all — so a Zone that was
    never measured and a Zone measured as plain render identically. That is
    deliberate: the renderer's fault being fixed here is drawing chrome nobody
    asked for, and an unmeasured default must not reintroduce it.
    """

    fill: tuple[int, int, int] | None = None
    """The region's own background, when it has one the page does not."""

    title_fill: tuple[int, int, int] | None = None
    """The first band's background, when it differs from the region's own.

    **This is the bar, and most cards do not have one.** `render.py` shades
    every Zone Title unconditionally, which on `sample_css_0004` painted a
    full-width blue banner across a card whose heading is simply the card's
    first line, and on `receipt_0010` painted heavy grey bars on a page that
    has no fills anywhere.
    """

    bordered: bool = False
    """Whether a rule is drawn around the region."""


def _flat_share(pixels: Any, colour: tuple[int, int, int]) -> float:
    """What share of `pixels` is `colour`, within `SAME_COLOUR`."""
    flat = np.asarray(pixels, dtype=np.int64).reshape(-1, 3)
    if not flat.size:
        return 0.0
    return float((np.abs(flat - np.array(colour)).sum(axis=1) <= SAME_COLOUR).mean())


def _filled_with(pixels: Any, ground: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """The region's fill, or `None` when it simply sits on the page."""
    flat = np.asarray(pixels, dtype=np.int64).reshape(-1, 3)
    if flat.size < 3:
        return None
    colour = dominant(flat)
    if sum(abs(a - b) for a, b in zip(colour, ground)) <= SAME_COLOUR:
        return None
    return colour if _flat_share(flat, colour) >= MIN_FILL_COVERAGE else None


def _bordered(pixels: Any, fill: tuple[int, int, int]) -> bool:
    """Whether at least `BORDER_EDGES` of the region's four edges are inked.

    Measured against the region's *own* fill rather than the page's ground, so a
    filled card with no rule round it is not called bordered because its fill
    differs from the page.
    """
    block = np.asarray(pixels, dtype=np.int64)
    if block.ndim != 3 or min(block.shape[:2]) < 4:
        return False
    edges = [block[0, :], block[-1, :], block[:, 0], block[:, -1]]
    drawn = sum(
        1 for edge in edges
        if (np.abs(edge - np.array(fill)).sum(axis=1) > SAME_COLOUR).mean() >= BORDER_RUN
    )
    return drawn >= BORDER_EDGES


def rectangles(image: ImageArray, *, ground: tuple[int, int, int],
               inverted: bool = False) -> tuple[BBox, ...]:
    """Every box the page draws, as normalised rectangles.

    **Found on the page, never grown from a Zone.** The obvious first attempt —
    dilate a Zone's crop by a few pixels until its rule comes into view — was
    measured on 2026-09-21 and cannot work. `DTH_SNAP_ZONES` snaps a box onto
    its *content* ink, and `preprocess.content_ink` deletes separators from the
    mask by name ("a horizontal rule, a panel border, a column divider"), so
    the rule is not merely outside the box, it is invisible to the thing that
    placed the box. On `sample_css_0004`'s two cards `_bordered` answers
    **True** on the card's own rectangle and **False** on the snapped box, and
    the inset is L21 T58 R124 B38 and L21 T58 R256 B37 — the text simply does
    not reach the card's right edge. No dilation reaches 256px without
    swallowing the neighbouring column.

    So: threshold everything that is not the page, close the antialiasing gaps
    in a 1px rule, take connected components, and keep a component whose
    bounding box is between `MIN_RECT_SHARE` and `PAGE_SHARE` of the page and
    whose edges pass `_bordered`. Text fails that last test — a paragraph's
    bounding box has ink on a small fraction of each edge — which is what
    separates a card from a block of prose without a second detector.

    Measured over the fifteen documents against the drawn boxes read out of
    each source with `getComputedStyle`: exact on `invoice_0002` (5),
    `sample_css_0004` (2), `darkdeck_0009` (5), `nonlatin_0014` (2) and
    `catalogue_0015` (9); 13 of `form_0007`'s 14 in-range boxes; and **zero on
    all eight documents that draw none**. On the ten documents whose HTML and
    screenshot agree exactly, every match is IoU 0.91 or better.
    """
    cv2 = _cv2()
    pixels = np.asarray(image, dtype=np.int64)
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        return ()
    if inverted:
        pixels = 255 - pixels
    height, width = pixels.shape[:2]
    if height < 4 or width < 4:
        return ()
    rgb = pixels[:, :, ::-1]

    far = np.abs(rgb - np.array(ground)).sum(axis=2) > SAME_COLOUR
    mask = (far.astype(np.uint8)) * 255
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (CLOSE_PX, CLOSE_PX)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    page = float(width * height)
    found: list[BBox] = []
    for index in range(1, count):
        x, y, w, h, _ = stats[index]
        share = (w * h) / page
        if share < MIN_RECT_SHARE or share > PAGE_SHARE:
            continue
        block = rgb[y:y + h, x:x + w]
        if min(block.shape[:2]) < 4:
            continue
        if _bordered(block, _filled_with(block, ground) or ground):
            found.append(BBox(x / width, y / height,
                              (x + w) / width, (y + h) / height))
    return tuple(sorted(found, key=lambda b: (round(b.top, 3), b.left)))


def _area(box: BBox) -> float:
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def box_around(zone: BBox, boxes: tuple[BBox, ...]) -> BBox | None:
    """The smallest drawn rectangle this Zone sits inside, if any.

    Smallest, because a card inside a panel inside a page is three containers
    and only the nearest one is this Zone's own chrome.
    """
    holding = [box for box in boxes
               if zone.overlap_ratio(box) >= CONTAINED and _area(box) > 0]
    return min(holding, key=_area) if holding else None


def boxes_for(zones: Sequence[BBox | None],
              boxes: tuple[BBox, ...]) -> list[BBox | None]:
    """Each Zone's own drawn box — one rectangle, one Zone.

    **A rectangle several Zones sit inside is a container, and no Zone's own
    chrome.** `darkdeck_0009`'s OPEN RISKS panel at (643,302)-(966,610) holds
    six Zones, each covering 3-15% of it; giving the panel to each of them
    draws six boxes where the page draws one, which is the fault this whole
    increment exists to stop making. `ir.Zone` never nests, so the IR has no
    way to say "these six share a box" — and inventing six is worse than
    drawing none.

    A ratio test was measured instead and does not separate the two:
    `sample_css_0004`'s genuine cards sit at 0.26 and 0.34 of their rectangle
    while `darkdeck_0009`'s false ones run 0.03-0.15, and `invoice_0002`'s
    `Services / Products` is a real bordered strip at **0.04**. How many Zones
    claim the rectangle separates them exactly; how much of it they fill does
    not.
    """
    claims = [box_around(zone, boxes) if zone is not None else None
              for zone in zones]
    held = Counter(claim for claim in claims if claim is not None)
    return [claim if claim is not None and held[claim] == 1 else None
            for claim in claims]


def chrome(crop: ImageArray, *, ground: tuple[int, int, int],
           inverted: bool = False, title_rows: int = 0,
           bordered: bool = False) -> Chrome:
    """What the page draws around one region. See `Chrome`.

    `crop` is the region's own pixels as `preprocess.zone_pixels` returns them —
    BGR, already cut from the Rectified Image. Taking the crop rather than a
    `BBox` keeps the normalised-to-pixel conversion in the one place that
    already owns it; a second copy here would be a second chance to disagree
    with the crop the Extractor was actually shown.

    `ground` is the page's own measured colour and `title_rows` how many of the
    region's first rows its Title occupies — zero when it has none, in which
    case no bar is looked for and none can be invented.

    `bordered` is **passed in, not measured here**, and that is the point of
    the border increment. A rule is a property of the page, not of a crop: the
    crop is snapped onto content ink and `content_ink` deletes borders by name,
    so the rule is not in these pixels to find. `rectangles()` reads the page
    once and `box_around` says which Zone each rectangle belongs to. Asking a
    crop directly was also actively wrong rather than merely blind — a crop cut
    tight around a single line of type has ink on all four edges and answers
    **True**.
    """
    pixels = np.asarray(crop, dtype=np.int64)
    if inverted:
        pixels = 255 - pixels
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        return Chrome()
    region = pixels[:, :, ::-1]
    if region.size < 3 or min(region.shape[:2]) < 2:
        return Chrome()

    fill = _filled_with(region, ground)
    title_fill = None
    if title_rows > 0 and region.shape[0] > title_rows + 1:
        band = _filled_with(region[:title_rows], ground)
        body = _filled_with(region[title_rows:], ground)
        # A bar only exists where it differs from what is under it. Equal fills
        # — including both being None — is a heading sitting on its own card,
        # which is what most of the corpus actually has.
        if band is not None and (body is None or
                                 sum(abs(a - b) for a, b in zip(band, body)) > SAME_COLOUR):
            title_fill = band

    return Chrome(fill=fill, title_fill=title_fill, bordered=bordered)
