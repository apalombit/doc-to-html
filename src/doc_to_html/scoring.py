"""Six axes, source against render — the measure spec 0007 replaced the old one with.

The harness this supersedes compared the IR against a hand-typed reference IR.
It scored `sample_table_0003` a **full match** while that document had lost every
column header of its only table, because it compared `RowRole` sequences and
never compared cell content. That is the shape of failure everything here is
arranged against: a measure that cannot see a class of fault is unconstrained in
that direction, and improving it will eventually start making the artefact worse.

| axis | asks | how |
|---|---|---|
| T1 completeness | every string present, exactly once, nothing invented | token recall and precision, plus the joins between adjacent words |
| T2 order | right reading order | Kendall tau over matched runs |
| T3 layout | what sits beside what, in what proportion, how tall | pairwise side-by-side relations, column shares, height ratio |
| T4 weight | heading hierarchy, emphasis, alignment | type scale and ink centroid |
| T5 palette | ground, ink, accent, texture | sampled pixels |
| T6 inline | links, code spans, badges | runs by inline kind |

**T1, T2 and T3 are a hard tier.** A regression on any of them fails a phase
whatever improved elsewhere. **T1 is a ratchet**: completeness may never decrease
between phases, for any reason. It is not a target to optimise, it is a floor
never to cross, and it is the rule that would have caught all three of the faults
that shipped as improvements in runs 81 to 84.

## Three things here are deliberate and look like gaps

**Tokens, not strings, for recall and precision.** A reader who finds every word
of the source in the output, once each, has lost nothing — even if our line
breaks fall elsewhere. Scoring whole strings would report every reflow as content
loss and make the measure unusable during Phase A0, which is about to change
where lines break on purpose.

**Joins, because tokens alone cannot see a mis-split.** `Invoice #: 123` read as
label `Invoice` and value `#: 123` has exactly the tokens the source has, in
order, so recall, precision and tau are all perfect and the fault is invisible.
The adjacent-word pairs are not: the source has `invoice -> #` and the output does
not. This is the one measure here that is about text *continuity* rather than
text presence, and it is why `join_recall` is reported beside the other two.

**Relations, not IoU, for layout.** A box twenty pixels off is not a finding.
Chasing IoU against a reference rectangle is precisely the overfit spec 0007
exists to escape, so T3 asks whether the same things sit beside each other, in
roughly the same proportion, at roughly the same total height.
`geometry_score.align()` is reused for the region correspondence underneath it,
because splitting and merging regions is still worth naming.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from . import geometry_score
from .corpus import ITERATE, Source
from .ir import BBox
from .projection import Block, Projection, project, screenshot
from .style import modal

NARROW = 0.62
"""How far the page is squeezed when asking whether its text reflows.

Any factor well inside the range where a paragraph rewraps and outside the noise
of a single trailing word would do; this one is far enough that every multi-line
paragraph in the corpus changes its line count, and not so far that a table cell
starts wrapping words it would never wrap.
"""

ALIGN_SLACK = 0.12
"""Share of a block's own width that its ink may sit off-centre before it counts
as aligned to one side. Below it the block reads as filling its container, which
is neither left- nor right-aligned in any way a reader would name."""

COLUMN_TOLERANCE = 0.15
"""How far a column's share of its row may drift before T3 calls it wrong.

Spec 0007's figure. `sample_semantic_0005`'s TL;DR aside is 35% of the width in
the source and 50% in the output — a 0.43 relative error — so the threshold is
not what decides that case, and it is loose enough that a one-word difference in
a heading cannot manufacture a finding.
"""

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def normalise(text: str) -> str:
    """One spelling of a string, so two renderings of it compare equal.

    Unicode-normalised, whitespace collapsed, case folded. Nothing else: a
    scorer that also stripped punctuation would stop being able to see
    `Invoice #: 123` split at the wrong point, and stripping accents would make
    `nonlatin_0014` unscoreable in the way it exists to be scored.
    """
    folded = unicodedata.normalize("NFKC", text)
    return " ".join(folded.split()).casefold()


def tokens(text: str) -> list[str]:
    """The words of a string, in order, punctuation dropped between them.

    Punctuation is dropped from the *token stream* although `normalise` keeps
    it, because a comma read as a full stop is an OCR slip and not a content
    loss, and T1 is the axis that must mean "content". Where the punctuation
    itself matters — a currency symbol, a decimal point — it is inside a word
    here rather than between two, so it survives.
    """
    return _WORD.findall(normalise(text))


def _bigrams(words: Sequence[str]) -> list[tuple[str, str]]:
    return list(zip(words, words[1:]))


# --------------------------------------------------------------------------
# T1 completeness
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Completeness:
    """Is every printed string present, exactly once, and nothing invented.

    The top of the rubric and the axis under the ratchet. `recall` below 1.00
    means content was lost; `precision` below 1.00 means content was duplicated
    or invented; `join_recall` below 1.00 means content is all present but was
    cut somewhere the source did not cut it.

    **`recall` is a multiset and `vocabulary_recall` is a set, and the ratchet
    is on the second — spec 0007 Phase A0, 2026-09-22.** Read the two together:
    the multiset says how many times a word came back and the set says whether
    it came back at all, and they answer different questions about a page. See
    `vocabulary_recall` for the measurement that forced the distinction.
    """

    recall: float
    precision: float
    join_recall: float

    vocabulary_recall: float
    """The share of *distinct* source words the output still prints somewhere.

    **The ratchet's floor, and the multiset `recall` above is not.** The change
    was forced by a measurement rather than argued: removing a doubled Zone
    Title *lowers* multiset recall on six of the fifteen documents, because the
    echo had been numerically standing in for a genuine occurrence elsewhere on
    the page that the output never read. `newsletter_0008` prints "Castleton
    Chronicle" twice — masthead and footer — and the output printed it twice in
    the masthead Zone; the multiset was satisfied and the footer copy was always
    missing. Remove the echo and the count finally reports that.

    So the multiset can fall while nothing leaves the page, and the ratchet's
    stated intent is *no content that previously converted stops converting* —
    a statement about what is printed, not about how many times. Measured over
    all fifteen documents, that fix moves this number on **none** of them.

    Both are reported. A multiset fall is worth reading; it is not a floor."""

    vanished: tuple[str, ...]
    """Distinct source words the output does not print at all.

    What `vocabulary_recall` is short by, named. The ratchet's failure message
    is built from this, so a clause that fails says which words it caught rather
    than only that a ratio moved."""
    source_tokens: int
    output_tokens: int
    lost: tuple[tuple[str, int], ...]
    """Words the output does not have enough of, and how many are short."""

    duplicated: tuple[tuple[str, int, int], ...]
    """Whole source strings the output repeats: the text, source count, output
    count. Reported as strings rather than as words because eight duplicated
    Titles is one sentence and forty-one surplus words is not."""

    invented: tuple[tuple[str, int], ...]
    """Words the output has that the source does not, and how many spare."""

    broken_joins: tuple[tuple[str, str], ...]
    """Adjacent word pairs the source prints together and the output does not."""

    figures_lost: int
    """Images the source draws that the output does not — a logo gone, or a
    dashed placeholder standing in for one."""

    hard_breaks: int
    """Line breaks the output draws that no column edge caused — the source
    image's own wrapping, carried into the render because `Block.lines` is a
    list of lines joined by `<br>` and a paragraph in this IR cannot reflow."""

    source_hard_breaks: int
    """The same count on the source side, which is the control. Several of
    these documents break lines on purpose — `invoice.html`'s address blocks
    are `<br>`-separated — so the number that means anything is the excess."""

    short_lines: int
    """The geometric signal beside the exact one. See `scoring.short_lines`."""

    source_short_lines: int

    @property
    def surplus_breaks(self) -> int:
        """Hard breaks the output has and the source does not."""
        return max(0, self.hard_breaks - self.source_hard_breaks)

    @property
    def ok(self) -> bool:
        return self.recall >= 1.0 and self.precision >= 1.0


def _duplicated_strings(source: Projection, output: Projection
                        ) -> tuple[tuple[str, int, int], ...]:
    """Strings the output prints more often than the source does.

    Counted over *blocks* rather than runs, so a Zone Title repeated as the
    first Block of its own body is one finding rather than one per word. Only
    strings the source actually has are reported: something the output prints
    twice and the source never prints at all is invention, which `invented`
    already names.
    """
    have = Counter(normalise(block.text) for block in source.blocks if block.text)
    got = Counter(normalise(block.text) for block in output.blocks if block.text)
    found = [
        (text, have[text], got[text])
        for text, count in got.items()
        if text and have.get(text, 0) and count > have[text]
    ]
    return tuple(sorted(found, key=lambda item: (-item[2], item[0])))


def short_lines(page: Projection) -> int:
    """Lines that stop well short of their column with more text beneath them.

    The geometric half of the hard-break question, and on its own it is not
    enough — a paragraph running beside a floated aside has short lines and no
    hard breaks at all, which is `sample_semantic_0005` exactly. Kept because
    it is the half that would still fire if a future renderer stopped using
    `br` and started emitting one element per line.

    Code blocks are exempt. A `pre` is *supposed* to keep its line breaks, and
    counting it would make `receipt_0010` and `report_0011` report a fault for
    being typeset correctly.
    """
    return sum(
        block.forced_breaks for block in page.blocks
        if not block.mono and block.role != "code-block"
    )


def completeness(source: Projection, output: Projection) -> Completeness:
    want = Counter(token for run in source.runs for token in tokens(run.text))
    got = Counter(token for run in output.runs for token in tokens(run.text))
    kept = want & got
    total_want = sum(want.values())
    total_got = sum(got.values())

    want_joins = Counter(
        pair for run in source.runs for pair in _bigrams(tokens(run.text))
    )
    got_joins = Counter(
        pair for run in output.runs for pair in _bigrams(tokens(run.text))
    )
    joins_kept = sum((want_joins & got_joins).values())
    joins_total = sum(want_joins.values())

    lost = want - got
    extra = got - want
    vanished = tuple(sorted(set(want) - set(got)))
    return Completeness(
        recall=sum(kept.values()) / total_want if total_want else 1.0,
        precision=sum(kept.values()) / total_got if total_got else 1.0,
        join_recall=joins_kept / joins_total if joins_total else 1.0,
        vocabulary_recall=(
            (len(want) - len(vanished)) / len(want) if want else 1.0
        ),
        vanished=vanished,
        source_tokens=total_want,
        output_tokens=total_got,
        lost=tuple(sorted(lost.items(), key=lambda item: (-item[1], item[0]))[:40]),
        duplicated=_duplicated_strings(source, output),
        invented=tuple(
            sorted(extra.items(), key=lambda item: (-item[1], item[0]))[:40]
        ),
        broken_joins=tuple(
            pair for pair in (want_joins - got_joins) if pair
        )[:40],
        figures_lost=max(
            0,
            sum(1 for figure in source.figures if figure.drawn)
            - sum(1 for figure in output.figures if figure.drawn),
        ),
        hard_breaks=output.break_elements,
        source_hard_breaks=source.break_elements,
        short_lines=short_lines(output),
        source_short_lines=short_lines(source),
    )


# --------------------------------------------------------------------------
# T2 order
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Order:
    """Does the output read in the same sequence as the source.

    Kendall tau over the **blocks** the two pages have in common, not over
    their text nodes. The source splits a sentence at every link and code span
    while the output prints it flat, so a run-level match pairs four of
    `sample_css_0004`'s thirteen runs and reports a tau about a third of the
    page. A block is the unit whose order a reader would actually name.

    `matched` is reported beside tau because tau over three blocks is not a
    statement about a page: a document that lost most of its content can still
    order what survived perfectly, and T1 is the axis that is meant to notice.
    """

    tau: float
    matched: int
    of: int


def kendall_tau(pairs: Sequence[tuple[int, int]]) -> float:
    """Tau-b over the paired orders. 1.0 is the same sequence, -1.0 reversed."""
    size = len(pairs)
    if size < 2:
        return 1.0
    concordant = discordant = tied_first = tied_second = 0
    for i in range(size):
        for j in range(i + 1, size):
            first = pairs[i][0] - pairs[j][0]
            second = pairs[i][1] - pairs[j][1]
            product = first * second
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            else:
                tied_first += first == 0
                tied_second += second == 0
    denominator = math.sqrt(
        (concordant + discordant + tied_first)
        * (concordant + discordant + tied_second)
    )
    return (concordant - discordant) / denominator if denominator else 1.0


def order(source: Projection, output: Projection) -> Order:
    matched = _pair_blocks(source, output)
    pairs = [(mine.index, theirs.index) for mine, theirs in matched]
    return Order(tau=kendall_tau(pairs), matched=len(pairs),
                 of=len(source.blocks))


# --------------------------------------------------------------------------
# T3 layout skeleton
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Layout:
    """What sits beside what, in what proportion, and how tall it all comes out.

    Relational on purpose. `beside_agreement` asks only whether two things that
    share a row in the source share a row in the output, which survives every
    box being twenty pixels off and does not survive a two-column band being
    rendered as two stacked rows.
    """

    beside_agreement: float
    beside_pairs: int
    column_error: float
    """Mean relative error of column shares within the rows both pages agree
    are rows. 0.0 is exact; `sample_semantic_0005`'s 35%-against-50% aside is
    0.43."""

    columns_within_tolerance: float
    height_ratio: float
    """Output height divided by the Source Image's height, at matched width.
    1.0 is the same page; 1.54 says the vertical rhythm is wrong."""

    matched_blocks: int
    of_blocks: int
    split_regions: int
    """Source regions the output cut into pieces, from `geometry_score.align`."""

    merged_regions: int
    """Source regions the output welded together. The same fault, inverted."""

    clipped: int
    """Elements in the output whose content is wider than the box holding it.

    **Reported, not gated** — one run is not enough evidence to ratchet on. It
    is here because `project()` has always measured it and nothing has ever
    read it, and on 2026-09-22 it fired on exactly the three renders whose
    tables and pairs lists were cut off at the right edge, and on none of the
    fifteen sources. That is the two-tiers-disagreeing failure spec 0007 warns
    about — recall says the text is present and the picture does not contain
    it — and it was sitting in the projection the whole time.
    """

    source_clipped: int
    """The same count for the source page, so a document that clips its own
    content is not reported as our fault."""


def _pair_blocks(source: Projection, output: Projection
                 ) -> list[tuple[Block, Block]]:
    """Which output block stands for which source block, by what it says.

    Exact text first, then by shared words, so a block the extractor split or
    joined still pairs with the source region it came from and T3 can say
    something about where it landed.
    """
    remaining = list(output.blocks)
    by_text: dict[str, list[Block]] = {}
    for block in remaining:
        by_text.setdefault(normalise(block.text), []).append(block)

    pairs: list[tuple[Block, Block]] = []
    taken: set[int] = set()
    for block in source.blocks:
        queue = by_text.get(normalise(block.text))
        while queue:
            candidate = queue.pop(0)
            if candidate.index not in taken:
                taken.add(candidate.index)
                pairs.append((block, candidate))
                break

    paired = {source_block.index for source_block, _ in pairs}
    free = [block for block in remaining if block.index not in taken]
    for block in source.blocks:
        if block.index in paired or not block.text:
            continue
        want = set(tokens(block.text))
        if not want:
            continue
        best, score = None, 0.0
        for candidate in free:
            got = set(tokens(candidate.text))
            if not got:
                continue
            overlap = len(want & got) / len(want | got)
            if overlap > score:
                best, score = candidate, overlap
        if best is not None and score >= 0.5:
            free.remove(best)
            pairs.append((block, best))
    return pairs


def _beside(blocks: Sequence[Block]) -> set[tuple[int, int]]:
    """Unordered pairs of blocks that share a row.

    Sharing a row is vertical overlap over half the shorter block, *and*
    horizontal disjointness. Both halves are needed: without the second, a
    heading and the paragraph indented under it read as a two-column band.
    """
    found = set()
    for first in range(len(blocks)):
        for second in range(first + 1, len(blocks)):
            a, b = blocks[first], blocks[second]
            top, bottom = max(a.ink[1], b.ink[1]), min(a.ink[3], b.ink[3])
            overlap = bottom - top
            shorter = min(a.ink[3] - a.ink[1], b.ink[3] - b.ink[1])
            if shorter <= 0 or overlap < 0.5 * shorter:
                continue
            if a.ink[2] <= b.ink[0] + 1 or b.ink[2] <= a.ink[0] + 1:
                found.add((first, second))
    return found


def _column_error(source: Projection, output: Projection,
                  pairs: Sequence[tuple[Block, Block]]) -> tuple[float, float]:
    """How far each shared row's column shares drift, as a mean and a pass rate.

    Measured as each block's width over the row's total inked width, so it is a
    proportion rather than a pixel count and does not need the two pages to be
    the same size.
    """
    lookup = {source_block.index: output_block for source_block, output_block in pairs}
    blocks = [block for block, _ in pairs]

    # A row is a connected component of the beside relation, so three panels in
    # one band are one row of three rather than three overlapping pairs — which
    # is what decides whether a share is out of two or out of three.
    groups: list[set[int]] = []
    for first, second in sorted(_beside(blocks)):
        joined = [group for group in groups if first in group or second in group]
        merged = {first, second}
        for group in joined:
            merged |= group
            groups.remove(group)
        groups.append(merged)

    errors: list[float] = []
    for group in groups:
        members = sorted((blocks[index] for index in group),
                         key=lambda block: block.ink[0])
        if len(members) < 2:
            continue
        theirs = [lookup.get(block.index) for block in members]
        if any(block is None for block in theirs):
            continue
        want = [block.ink[2] - block.ink[0] for block in members]
        got = [block.ink[2] - block.ink[0] for block in theirs]  # type: ignore[union-attr]
        if sum(want) <= 0 or sum(got) <= 0:
            continue
        for mine, other in zip(want, got):
            share, theirs_share = mine / sum(want), other / sum(got)
            errors.append(abs(share - theirs_share) / share if share else 0.0)
    if not errors:
        return 0.0, 1.0
    within = sum(1 for error in errors if error <= COLUMN_TOLERANCE) / len(errors)
    return sum(errors) / len(errors), within


def _normalised(blocks: Sequence[Block], page: Projection) -> list[BBox]:
    width = max(1, page.width)
    height = max(1, page.height)
    return [
        BBox(block.ink[0] / width, block.ink[1] / height,
             block.ink[2] / width, block.ink[3] / height)
        for block in blocks
    ]


def layout(source: Projection, output: Projection, *,
           source_height: int) -> Layout:
    pairs = _pair_blocks(source, output)
    mine = [block for block, _ in pairs]
    theirs = [block for _, block in pairs]

    want, got = _beside(mine), _beside(theirs)
    union = want | got
    agreement = len(want & got) / len(union) if union else 1.0
    error, within = _column_error(source, output, pairs)

    # `geometry_score.align()` survives the old harness for exactly this: it is
    # the one place a split or a merge gets named rather than showing up as a
    # slightly worse number somewhere else.
    correspondence = geometry_score.align(
        _normalised(theirs, output), _normalised(mine, source)
    )
    return Layout(
        beside_agreement=agreement,
        beside_pairs=len(union),
        column_error=error,
        columns_within_tolerance=within,
        height_ratio=output.height / source_height if source_height else 0.0,
        matched_blocks=len(pairs),
        of_blocks=len(source.blocks),
        split_regions=len(correspondence.split()),
        merged_regions=len(correspondence.merged),
        clipped=output.clipped,
        source_clipped=source.clipped,
    )


# --------------------------------------------------------------------------
# T4 typographic weight
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Typography:
    """Heading hierarchy, emphasis, and which edge the ink sits against."""

    source_scale: float
    output_scale: float
    scale_error: float
    heading_levels_source: int
    heading_levels_output: int
    alignment_agreement: float
    aligned_blocks: int


def _scale(page: Projection) -> tuple[float, int]:
    """The page's heading-to-body type ratio, and how many sizes it uses.

    Medians rather than extremes, so one oversized pull quote does not decide
    the scale of a whole page.
    """
    headings = sorted(
        block.font_px for block in page.blocks if block.role == "heading"
    )
    body = sorted(
        block.font_px for block in page.blocks
        if block.role in {"paragraph", "cell", "item"}
    )
    if not headings or not body:
        return 1.0, len({round(value, 1) for value in headings})
    middle = headings[len(headings) // 2] / body[len(body) // 2]
    return middle, len({round(value, 1) for value in headings})


def _alignment(block: Block) -> str:
    """Which edge of its own container a block's ink sits against.

    From the ink, not from `text-align`: a declared alignment that a wrapper
    overrides is a claim about the stylesheet, and this axis is about the page.
    """
    left = block.ink[0] - block.box[0]
    right = block.box[2] - block.ink[2]
    width = max(1.0, block.box[2] - block.box[0])
    if abs(left - right) <= ALIGN_SLACK * width:
        return "centre" if min(left, right) > ALIGN_SLACK * width else "fill"
    return "left" if left < right else "right"


def typography(source: Projection, output: Projection) -> Typography:
    source_scale, source_levels = _scale(source)
    output_scale, output_levels = _scale(output)
    pairs = _pair_blocks(source, output)
    agree = sum(
        1 for mine, other in pairs if _alignment(mine) == _alignment(other)
    )
    return Typography(
        source_scale=source_scale,
        output_scale=output_scale,
        scale_error=(
            abs(output_scale - source_scale) / source_scale if source_scale else 0.0
        ),
        heading_levels_source=source_levels,
        heading_levels_output=output_levels,
        alignment_agreement=agree / len(pairs) if pairs else 1.0,
        aligned_blocks=len(pairs),
    )


# --------------------------------------------------------------------------
# T5 palette and texture
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """Ground, ink, accent and how much of the page is neither of the first two.

    Sampled from pixels on both sides rather than asked of a model. Colour is
    perception and the pixels are already in hand, and this project has written
    down what asking a 4B model to perceive rather than decide is worth.
    """

    source_background: tuple[int, int, int]
    output_background: tuple[int, int, int]
    source_ink: tuple[int, int, int]
    output_ink: tuple[int, int, int]
    source_accent: tuple[int, int, int] | None
    output_accent: tuple[int, int, int] | None
    background_delta: float
    ink_delta: float
    accent_delta: float
    source_texture: float
    """Share of the page that is neither ground nor ink — shaded bands, rules,
    card fills. The single number that says whether the page has any furniture."""

    output_texture: float


GROUND_NEAR = 60
"""Channel-sum distance within which a pixel is still the page, not a mark."""

INK_NEAR = 120
"""Channel-sum distance within which a mark is the body ink rather than furniture."""


def _sample(path: Path) -> tuple[tuple[int, int, int], tuple[int, int, int],
                                 tuple[int, int, int] | None, float]:
    import numpy as np
    from PIL import Image

    image = Image.open(path).convert("RGB")
    image.thumbnail((600, 6000))
    pixels = np.asarray(image, dtype=np.int64)
    ground = modal(pixels)

    from_ground = np.abs(pixels - np.array(ground)).sum(axis=2)
    marked = from_ground > INK_NEAR
    ink = modal(pixels[marked]) if marked.any() else ground

    # Texture is everything that is neither the page nor its type: shaded
    # caption bars, rules, zebra striping, card fills. A page with none of it
    # is a page the current renderer can already reach, so this is the single
    # number that says whether Thread B has anything to do here.
    from_ink = np.abs(pixels - np.array(ink)).sum(axis=2)
    furniture = (from_ground > GROUND_NEAR) & (from_ink > INK_NEAR)
    texture = float(furniture.mean())

    saturation = pixels.max(axis=2) - pixels.min(axis=2)
    vivid = saturation > 60
    accent = modal(pixels[vivid]) if vivid.mean() > 0.002 else None
    return ground, ink, accent, texture


def _delta(first: tuple[int, int, int] | None,
           second: tuple[int, int, int] | None) -> float:
    """Distance between two colours as a share of the diagonal of RGB space."""
    if first is None or second is None:
        return 0.0 if first == second else 1.0
    return math.dist(first, second) / math.dist((0, 0, 0), (255, 255, 255))


def palette(source_png: Path, output_png: Path) -> Palette:
    ground, ink, accent, texture = _sample(source_png)
    their_ground, their_ink, their_accent, their_texture = _sample(output_png)
    return Palette(
        source_background=ground, output_background=their_ground,
        source_ink=ink, output_ink=their_ink,
        source_accent=accent, output_accent=their_accent,
        background_delta=_delta(ground, their_ground),
        ink_delta=_delta(ink, their_ink),
        accent_delta=_delta(accent, their_accent),
        source_texture=texture, output_texture=their_texture,
    )


# --------------------------------------------------------------------------
# T6 inline detail
# --------------------------------------------------------------------------

INLINE_KINDS = ("link", "code", "mark", "strong", "em")


@dataclass(frozen=True)
class Inline:
    """Links, code spans, badges and marks: present in the source, kept or not."""

    found: dict[str, int]
    of: dict[str, int]
    missing: tuple[str, ...]

    @property
    def rate(self) -> float:
        total = sum(self.of.values())
        return sum(self.found.values()) / total if total else 1.0


def inline(source: Projection, output: Projection) -> Inline:
    theirs: dict[str, Counter[str]] = {kind: Counter() for kind in INLINE_KINDS}
    for run in output.runs:
        if run.inline in theirs:
            theirs[run.inline][normalise(run.text)] += 1

    found = {kind: 0 for kind in INLINE_KINDS}
    of = {kind: 0 for kind in INLINE_KINDS}
    missing: list[str] = []
    for run in source.runs:
        if run.inline not in of:
            continue
        of[run.inline] += 1
        key = normalise(run.text)
        if theirs[run.inline][key]:
            theirs[run.inline][key] -= 1
            found[run.inline] += 1
        else:
            missing.append(f"{run.inline}: {run.text}")
    return Inline(found=found, of=of, missing=tuple(missing[:40]))


# --------------------------------------------------------------------------
# One document, all six
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentScore:
    """Every axis for one document, plus what it took to get them."""

    name: str
    split: str
    width: int
    source_height: int
    output_height: int
    completeness: Completeness
    order: Order
    layout: Layout
    typography: Typography
    palette: Palette | None
    inline: Inline
    notes: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None

    @property
    def hard_tier_ok(self) -> bool:
        """Whether T1, T2 and T3 are all clean enough to let a phase pass.

        A threshold on each, rather than a sum: the tier's whole purpose is that
        one of them going backwards cannot be paid for by another going forward.
        """
        return (
            self.completeness.ok
            and self.order.tau >= 0.99
            and self.layout.beside_agreement >= 0.99
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_document(source: Source, output_html: Path, *, work: Path,
                   root: Path | None = None) -> DocumentScore:
    """Score one converted document against the page it was converted from.

    Both sides go through `project()` at the **Source Image's own width**, and
    the output is screenshotted at that width too, so every proportion compared
    here is compared at matched width. The source's height comes from the PNG on
    disk rather than from re-rendering its HTML: the PNG is what the model was
    actually shown, and four of the five original documents no longer re-render
    to their screenshot byte for byte.
    """
    from PIL import Image

    png = source.png_path(root)
    width, height = Image.open(png).size
    source_text = source.html_path(root).read_text(encoding="utf-8")
    output_text = output_html.read_text(encoding="utf-8")

    mine = project(source_text, width=width, label=f"{source.name}/source")
    theirs = project(output_text, width=width, label=f"{source.name}/output")

    work.mkdir(parents=True, exist_ok=True)
    shot = work / f"{source.name}_render.png"
    swatch: Palette | None
    try:
        screenshot(output_text, shot, width=width, height=max(1, theirs.height))
        swatch = palette(png, shot)
    except Exception:
        swatch = None

    return DocumentScore(
        name=source.name,
        split=("iterate" if source.name in ITERATE else "sweep"),
        width=width,
        source_height=height,
        output_height=theirs.height,
        completeness=completeness(mine, theirs),
        order=order(mine, theirs),
        layout=layout(mine, theirs, source_height=height),
        typography=typography(mine, theirs),
        palette=swatch,
        inline=inline(mine, theirs),
    )
