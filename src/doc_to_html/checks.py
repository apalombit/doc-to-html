"""The derived checks: exact, from the source HTML, with no model.

Spec 0021, step 2 (§C). The scorer counts words; it cannot see a result
moved into the next column (the probe's lab report, tau 1.000), cells
merged by rules the output leaves out (the quiz: tau 1.000, beside 1.000,
the output's grid identical to the source's), or a method interleaved with
its ingredients (the recipe). Each of those is derivable from the source
HTML, which every corpus page has. This module derives them.

**Both sides are read the same way**: `project(..., detail=True)` at the
source picture's width, the source flat (as the scorer does). Every check
works on what a reader sees — where a word's ink fell, which rules are
drawn — never on how the markup is nested.

**One word alignment is the backbone.** The source's tokens in reading
order are aligned with the output's (`align`), and every other check looks
a source word up through it. The words check alone needs no alignment: it
is a multiset, so a word printed elsewhere is not lost, and a word printed
once where the source prints it twice is.

**Every severity is `docs/agents/review-criteria.md`'s**, and three more
decided by Alessandro for spec 0021: regular drawn bold and a list marker
changed are minor (2026-10-30); a tick-box glyph lost or changed (`MARKS`)
and a word's case or inner mark changed (the strict spelling comparison)
are major (2026-10-31), as a changed word is.

**Thresholds** are set from the 31 known pages' distributions, each
histogram in its constant's docstring.
"""

from __future__ import annotations

import itertools
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence, Set
from dataclasses import asdict, dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .factory.fonts import CANDIDATES, GENERIC
from .projection import Detail, Frames, Projection, Rect, Table, TableCell, Word, project
from .scoring import normalise, tokens

REPO = Path(__file__).resolve().parent.parent.parent

TWIN_SPELLINGS = REPO / "corpus" / "twin-spellings.json"
"""Words a PDF page's twin spells as its text layer does, where the picture
prints them otherwise: c0082's `specifc` for `specific` (spec 0020's
outcome). Mapped to the picture's spelling before anything is compared, so
a converter that reads the picture right is not called wrong."""

MARKS = frozenset("☐☑☒✓✔✕✖✗✘□■▢▣")
"""Tick-box glyphs: ☐ ☑ ☒ ✓ ✔ ✕ ✖ ✗ ✘ □ ■ ▢ ▣. The scorer's tokens drop
them, so a box drawn empty where the page ticks it is invisible to every
number. Counted here as content: 24 of dev's 32 `list.ticks` pages print
their ticks as text (`projection.ListItem.ticked_text`). Major, Alessandro,
2026-10-31: a ticked box read as empty changes what the form says."""

FACE_CLASS: dict[str, str] = {
    **{name: kind for name, (kind, _) in CANDIDATES.items()},
    **GENERIC,
    "-apple-system": "sans", "BlinkMacSystemFont": "sans", "Segoe UI": "sans",
    "SFMono-Regular": "mono", "Consolas": "mono", "ui-monospace": "mono",
}
"""Each face's class: the corpus's allow-list (`factory.fonts`), CSS's
generics, and the system stacks the renderer names. A face not here is
classed by whether it draws monospaced, else not judged."""

JUDGED_FACES = ("serif", "sans", "mono", "script")
"""The classes the criteria name. A display face is judged by the review."""

SIZE_MARGIN = 0.05
"""How much larger or smaller than the page's body a block must be set to
count as larger or smaller.

Measured on the 31 known pages' sources, 2026-10-30, blocks by their size
over the page's body size: 0.92: 79, 0.93: 19, none at 0.94–0.95, 0.96:
26, 1.00: 873, 1.04: 5, none at 1.05–1.06, 1.07: 3, 1.08: 19. The margin
sits in the two empty bands either side of the body. (0.15 was the first
guess, and it fell in the middle of the 0.85 and 1.15 clusters.)"""

SIZE_SEEN = 0.10
"""How much a line's own size, printed against drawn, must change for a
size fault: form_0007's 'OFFICE USE', 11 px printed and 10.8 px drawn,
crossed the body's margin and cannot be seen (Alessandro, review round
1, 2026-11-07)."""

HEIGHT_NOTICED = 0.01
"""How far off the picture's height a render may be before it is a minor
fault; past 10% it is a major (the criteria).

Measured on the 31 known pages' renders, 2026-10-30, how far each is off
its picture: 0.1% (one page), then 1.5% and more, through 0.89 to 1.44.
The line sits in that empty band."""

FRAME_SLACK = 4.0
"""Pixels a box must exceed a line's width by to say where the line sits in
it.

Measured on the 31 known pages, both sides, 2026-10-30, how much wider a
line's own block is than the line: 0 px on 379 lines (shrink-wrapped), 1
px on 12, 2 on 7, 3 on 2, then 4 on 11 and more beyond. A box under 4 px
wider is the line's own shrink-wrap and says nothing; the dip at 3 px is
the nearest thing to an empty band."""

ALIGN_SLACK = 3.0
"""Pixels a line's two margins in its frame may differ by and still be
centred, or each fall short by and still fill it.

Measured on the 31 known pages, both sides, 2026-10-30, for lines placed in
an ancestor's box: the two margins differ by 0 px on 15 lines, 1 on 9, 2 on
1, never by 3, then by 4 on 2, 5 on 5, and by 11 px or more."""

PLACE_SLACK = 2.0
"""Pixels a line may be drawn from where it is printed, past what its
width change explains, and still keep its alignment to the eye: the
alignment the frames say is then the render's HTML, not its look. A
line's frame on the render is often not the page's (a Zone's box starts
at its ink: c0492's names, centred in their halves on both, read as
set left).

Measured over the review's calls, 2026-11-01, the lines of every
alignment change the check made on the 31 and dev's 83, justified
aside: in rejected groups, 28 lines moved under 1 px and 7 under 2, none
from 2 to 3, then 2 from 3 to 4; in confirmed groups 44 under 1 px (a
column's widest number, in place while the rest move), 3 under 2, 3
from 2 to 3."""

GLUE = 1.0
"""Pixels between two words' ink below which they are one printed word: a
superscript in its own element (`10<sup>9</sup>`), a bold first syllable
(`<b>con</b>firmed`). Never a generated word (`::before`, a counter): its
box is estimated beside the text it precedes, not measured, so the recipe's
step number in its own 34 px column read as glued to "Heat" (spec 0021,
step 7's review).

Measured on the 31 known pages, both sides, 2026-10-30: two words next to
each other on one line stand 0 px apart (83 pairs) or 2 px and more (7,985
pairs), never between."""

REGISTERED = 0.8
"""Share of the source's word boxes that must hold ink in the picture for
its boxes to be drawn on it (`PageCheck.registered`). Below it the HTML no
longer lays out as its picture does, and a box would mark blank paper.

Measured on the 31 known pages, 2026-10-31, a word box holding ink when its
crop of the picture spans 64 grey levels: sample_table_0003 0.022 and
invoice_0002 0.326 (whose HTML wants a CDN), then nothing until pricing
0.917 and timetable 0.922, and the other 27 from 0.963 to 1.000."""

LAYOUT_CHECKS = ("lines", "beside", "overprint", "alignment", "type")
"""The checks that read where the source's HTML lays its words out, and how
large: withheld on a page whose HTML does not register with its picture
(`REGISTERED`). Its words, its tables, lists and order are the DOM's and
hold; its line breaks, alignment and type are another layout's. Five of
invoice_0002's faults were this, rejected in review 2026-10-31.

"""

RUN_TOKENS = 2
"""Tokens a stretch of one group must hold to count when two groups are
tested for interleaving. A single token out of place is an alignment
artefact more often than a moved block."""

SECTION_SLACK = 12.0
"""How far left of its heading a block may start and still be in its
section, in pixels: a hanging number or a bullet's indent outdented a
little. A block starting further left is not under that heading's column,
whatever the HTML's order: c0565's full-width footer, after the right
column's 'Next steps' in the source, is no part of that section."""

COLUMN_TOUCH = 0.1
"""Two runs of words are in different columns if they share no more of
their width than this share of the narrower: c0552's '−19 %', drawn 36 px
into the left column's 392 (9%) under the right column's chart, is still
beside it to the eye."""

DRIFT_LINES = 2.0
"""How far, in the source's lines, a run drawn in the next column may sit
off where the page puts it from the run before it, and still be drawn as
printed (`_placed_as_printed`). c0221's and the recipe's columns drift by
1.2 and 1.8 lines where the render spaces them differently;
probe_datasheet's key features sit 15 lines off, drawn below the table
they print beside."""

CHECK_FEATURES: dict[str, tuple[str, ...]] = {
    "words": ("fmt.", "list.ticks"),
    "cells": ("table.",),
    "rules": ("table.",),
    "structure": ("table.", "list."),
    "order": ("arr.", "list."),
    "lines": ("text.", "kv."),
    "height": ("arr.",),
    "beside": ("arr.", "kv."),
    "overprint": ("arr.", "kv."),
    "alignment": ("arr.", "kv."),
    "type": ("type.",),
}
"""The page features each check bears on, by prefix: a fault is tagged with
the page's features that match, so the report counts per feature."""


@dataclass(frozen=True)
class Fault:
    """One fault a check found: what, how bad, which words, where."""

    check: str
    fault: str
    severity: str
    element: str
    note: str = ""
    source_box: Rect | None = None
    output_box: Rect | None = None
    features: tuple[str, ...] = ()
    places: tuple[Rect, ...] = ()
    """Each element's box on the source, when one fault names several: the
    blocks a type or alignment change touches, so a sheet can mark each."""


@dataclass(frozen=True)
class PageCheck:
    """Every check on one page."""

    page: str
    faults: tuple[Fault, ...]
    height_ratio: float
    unread: int
    source_tokens: int
    output_tokens: int
    matched_tokens: int
    notes: tuple[str, ...] = ()
    body_px: float = 0.0
    """The source's body size, the size most of its words are set at: what
    decides whether a sheet needs zoomed tiles (`review.dense`)."""
    anchors: tuple[tuple[float, float], ...] = ()
    """(source y, output y) of matched words, top to bottom, one per source
    line: how a strip of the source finds the same strip of the render, where
    the two run to different heights (`review.tiles`)."""
    registered: float = 1.0
    """Share of the source's word boxes holding ink in the picture: whether
    the HTML lays out as its picture does, so its boxes can be drawn on it
    (`REGISTERED`)."""

    @property
    def majors(self) -> tuple[Fault, ...]:
        return tuple(fault for fault in self.faults if fault.severity == "major")

    def count(self, check: str | None = None, *, severity: str | None = None) -> int:
        return sum(1 for fault in self.faults
                   if (check is None or fault.check == check)
                   and (severity is None or fault.severity == severity))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _grouped(check: str, fault: str, severity: str,
             found: Iterable[tuple[str, str, Rect]], unit: str = "block") -> list[Fault]:
    """One fault per kind of change on a page, naming its elements: twenty
    digit boxes drawn left of centre are one finding, not twenty."""
    by_key: dict[str, list[tuple[str, Rect]]] = defaultdict(list)
    for key, text, box in found:
        by_key[key].append((text, box))
    faults = []
    for key, items in by_key.items():
        texts = [text for text, _ in items]
        element = "; ".join(texts[:3]) + (f"; and {len(texts) - 3} more" if len(texts) > 3 else "")
        faults.append(Fault(check, fault, severity, element,
                            f"{key} ({len(items)} {unit}{'s' if len(items) > 1 else ''})",
                            source_box=items[0][1], places=tuple(box for _, box in items)))
    return faults


# --- the two sides, as tokens and lines ------------------------------------


@dataclass
class _Side:
    """One page read for the checks: its tokens, which word each came from,
    and each word's line."""

    projection: Projection
    detail: Detail
    tokens: list[str] = field(default_factory=list)
    owner: list[int] = field(default_factory=list)
    """Token → the first word of the printed word it came from."""
    glued: dict[int, list[int]] = field(default_factory=dict)
    """A printed word's first word → every word it was glued from (`GLUE`)."""
    line_of: dict[int, tuple[int, int]] = field(default_factory=dict)
    line_words: dict[tuple[int, int], list[int]] = field(default_factory=dict)

    @property
    def words(self) -> tuple[Word, ...]:
        return self.detail.words

    def box(self, owner: int) -> Rect:
        return _union(self.words[index].rect for index in self.glued.get(owner, [owner]))

    def text(self, owner: int) -> str:
        return "".join(self.words[index].text for index in self.glued.get(owner, [owner]))

    def line_box(self, line: tuple[int, int]) -> Rect:
        return _union(self.words[index].rect for index in self.line_words[line])


def _union(rects: Iterable[Rect]) -> Rect:
    boxes = list(rects)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _same_row(first: Rect, second: Rect) -> bool:
    """Two boxes on one line: they share more than half the shorter's height,
    `projection.linesFrom`'s own test."""
    overlap = min(first[3], second[3]) - max(first[1], second[1])
    shorter = min(first[3] - first[1], second[3] - second[1])
    return shorter > 0 and overlap > 0.5 * shorter


def _side(projection: Projection, spellings: dict[str, str] | None = None) -> _Side:
    detail = projection.detail
    if detail is None:
        raise ValueError(f"{projection.label}: read without detail=True")
    side = _Side(projection, detail)
    groups: list[list[int]] = []
    for index, word in enumerate(detail.words):
        if groups:
            last = detail.words[groups[-1][-1]]
            gap = word.rect[0] - last.rect[2]
            if last.block == word.block and _same_row(last.rect, word.rect) \
                    and not (last.generated or word.generated) and -1.0 <= gap < GLUE:
                groups[-1].append(index)
                continue
        groups.append([index])
    numbered: set[tuple[int, int]] = set()
    for group in groups:
        owner = group[0]
        side.glued[owner] = group
        item = detail.words[owner].item
        if item is not None and item not in numbered:
            numbered.add(item)
            listed = detail.lists[item[0]].items[item[1]]
            if listed.marker == "number" and listed.ordinal is not None \
                    and listed.list_style.startswith(("decimal", "none")):
                side.tokens.append(str(listed.ordinal))
                side.owner.append(owner)
        for token in tokens(side.text(owner)):
            side.tokens.append((spellings or {}).get(token, token))
            side.owner.append(owner)
    by_block: dict[int, list[int]] = defaultdict(list)
    for index, word in enumerate(detail.words):
        by_block[word.block].append(index)
    for block, indexes in by_block.items():
        line = 0
        current: Rect | None = None
        for index in indexes:
            rect = detail.words[index].rect
            if current is not None and not _same_row(current, rect):
                line += 1
                current = None
            current = rect if current is None else _union((current, rect))
            side.line_of[index] = (block, line)
            side.line_words.setdefault((block, line), []).append(index)
    return side


# --- the alignment ----------------------------------------------------------


@dataclass(frozen=True)
class Alignment:
    """Source token index → output token index, and which pairs were found
    in a run of two or more (`strong`), not one token matched alone."""

    pairs: dict[int, int]
    strong: frozenset[int]
    replaced: tuple[tuple[int, int, int, int], ...]
    """The first pass's `replace` stretches: (source from, to, output from,
    to). Where a word was changed, merged or split."""


def align(source: Sequence[str], output: Sequence[str]) -> Alignment:
    """Three passes. The two sequences in order; then whatever is left, in
    runs of two or more, which finds a block the output moved; then single
    tokens left on both sides, in order, which finds a word moved alone."""
    pairs: dict[int, int] = {}
    strong: set[int] = set()
    matcher = SequenceMatcher(None, list(source), list(output), autojunk=False)
    for first, second, size in matcher.get_matching_blocks():
        for k in range(size):
            pairs[first + k] = second + k
            if size >= 2:
                strong.add(first + k)
    replaced = tuple((i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes()
                     if tag == "replace")
    for least in (2, 1):
        while True:
            used = set(pairs.values())
            left_source = [i for i in range(len(source)) if i not in pairs]
            left_output = [j for j in range(len(output)) if j not in used]
            if not left_source or not left_output:
                break
            rest = SequenceMatcher(None, [source[i] for i in left_source],
                                   [output[j] for j in left_output], autojunk=False)
            found = [block for block in rest.get_matching_blocks() if block.size >= least]
            if not found:
                break
            for first, second, size in found:
                for k in range(size):
                    pairs[left_source[first + k]] = left_output[second + k]
                    if least >= 2:
                        strong.add(left_source[first + k])
            if least == 1:
                break
    return Alignment(pairs, frozenset(strong), replaced)


COPY_GAIN = 20.0
"""How much nearer, in pixels summed over a word's copies, pairing each
with the copy where its neighbours land must put them before the pairing
in order is replaced."""


def _centre(box: Rect) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _nearest_copies(source: _Side, output: _Side, alignment: Alignment) -> Alignment:
    """A word printed more than once, each copy paired with the copy drawn
    where its neighbours are drawn, not the one the reading order reaches
    first: c0345's 'Camila Park', a script signature and a bold name,
    compared signature with name and raised a wrong face both ways
    (Alessandro, review round 1, 2026-11-07). Where its neighbours land is
    the median shift of the three nearest words printed and drawn once."""
    def spans(side: _Side) -> dict[int, list[int]]:
        held: dict[int, list[int]] = defaultdict(list)
        for index, owner in enumerate(side.owner):
            held[owner].append(index)
        return held

    mine, theirs = spans(source), spans(output)
    key = {owner: (source.text(owner),) + tuple(source.tokens[i] for i in held)
           for owner, held in mine.items()}
    their_key = {owner: (output.text(owner),) + tuple(output.tokens[j] for j in held)
                 for owner, held in theirs.items()}
    whole: dict[int, int] = {}
    for owner, held in mine.items():
        landed = {output.owner[alignment.pairs[i]] for i in held if i in alignment.pairs}
        if len(landed) == 1 and all(i in alignment.pairs for i in held):
            other = landed.pop()
            if their_key[other] == key[owner] and [alignment.pairs[i] for i in held] == theirs[other]:
                whole[owner] = other
    printed = Counter(key.values())
    drawn = Counter(their_key.values())
    anchors = [(_centre(source.box(owner)), _centre(output.box(other)))
               for owner, other in whole.items()
               if printed[key[owner]] == 1 and drawn[key[owner]] == 1]
    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for owner in whole:
        if printed[key[owner]] > 1:
            groups[key[owner]].append(owner)
    if not anchors or not groups:
        return alignment

    def expected(owner: int) -> tuple[float, float]:
        x, y = _centre(source.box(owner))
        near = sorted(anchors, key=lambda a: (a[0][0] - x) ** 2 + (a[0][1] - y) ** 2)[:3]
        dx = sorted(b[0] - a[0] for a, b in near)[len(near) // 2]
        dy = sorted(b[1] - a[1] for a, b in near)[len(near) // 2]
        return x + dx, y + dy

    pairs = dict(alignment.pairs)
    for owners in groups.values():
        if len(owners) < 2 or len(owners) > 6:
            continue
        targets = [whole[owner] for owner in owners]
        want = [expected(owner) for owner in owners]

        def cost(order: Sequence[int]) -> float:
            return sum(math.dist(w, _centre(output.box(t))) for w, t in zip(want, order))

        best = min(itertools.permutations(targets), key=cost)
        if cost(targets) - cost(best) <= COPY_GAIN:
            continue
        for owner, other in zip(owners, best):
            for i, j in zip(mine[owner], theirs[other]):
                pairs[i] = j
    return replace(alignment, pairs=pairs)


# --- words ------------------------------------------------------------------


def _marks(words: Iterable[Word]) -> Counter[str]:
    return Counter(ch for word in words for ch in word.text if ch in MARKS)


def _first_word(side: _Side, token: str, unmatched: Iterable[int]) -> Rect | None:
    for index in unmatched:
        if side.tokens[index] == token:
            return side.box(side.owner[index])
    return None


CROSSES = frozenset("✕✖✗✘☒")
"""Cross marks, which a render may draw as the letter X (in a drawn box):
the look of the page with another character under it, a minor (issue N,
Alessandro, 2026-11-01). An empty box drawn as an X says it is crossed,
which the page does not: still a mark lost and a word invented."""


def _crosses_as_x(source: _Side, output: _Side, alignment: Alignment,
                  unmatched_output: Sequence[int]) -> list[tuple[int, int]]:
    """Each output token `x` drawn by no source word, paired with a source
    word carrying a cross mark where the source has nothing else between
    the same two matched neighbours: (source word, output token)."""
    crosses = [w for w, word in enumerate(source.words) if any(ch in CROSSES for ch in word.text)]
    if not crosses:
        return []
    reverse = {j: i for i, j in alignment.pairs.items()}
    used: set[int] = set()
    found = []
    for j in unmatched_output:
        if output.tokens[j] != "x":
            continue
        before = next((reverse[k] for k in range(j - 1, -1, -1) if k in reverse), None)
        after = next((reverse[k] for k in range(j + 1, len(output.tokens)) if k in reverse), None)
        if before is not None and after is not None and after != before + 1:
            # Source words between the neighbours: the x may be a misreading
            # of them (c0587's re-reads), not the cross.
            continue
        low = source.owner[before] if before is not None else -1
        high = source.owner[after] if after is not None else len(source.words)
        near = [w for w in crosses if low <= w <= high and w not in used]
        if near:
            used.add(near[0])
            found.append((near[0], j))
    return found


def _inside(box: Rect, regions: Sequence[Rect]) -> bool:
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in regions)


def _check_words(source: _Side, output: _Side, alignment: Alignment,
                 pictured: Sequence[Rect] = ()) -> list[Fault]:
    faults: list[Fault] = []
    lost = Counter(source.tokens) - Counter(output.tokens)
    invented = Counter(output.tokens) - Counter(source.tokens)
    matched_output = set(alignment.pairs.values())
    for i1, i2, j1, j2 in alignment.replaced:
        was, now = source.tokens[i1:i2], output.tokens[j1:j2]
        if not (len(was) <= 4 and len(now) <= 4):
            continue
        if any(lost[token] <= 0 for token in was) or any(invented[token] <= 0 for token in now):
            continue
        if "".join(was) == "".join(now):
            kind = "merged" if len(was) > len(now) else "split"
        else:
            kind = "changed"
        lost.subtract(was)
        invented.subtract(now)
        faults.append(Fault(
            "words", kind, "major", f"{' '.join(was)} → {' '.join(now)}",
            source_box=_union(source.box(source.owner[i]) for i in range(i1, i2)),
            output_box=_union(output.box(output.owner[j]) for j in range(j1, j2))))
    for was_word, now_word in _scripts_inline(source, output):
        was, now = tokens(source.text(was_word)), tokens(output.text(now_word))
        if all(lost[token] > 0 for token in was) and any(invented[token] > 0 for token in now):
            # A part the rest of the page also prints (c0576's 2015, a
            # year on its axis) may already stand for a copy elsewhere.
            lost.subtract(was)
            invented.subtract(token for token in now if invented[token] > 0)
            faults.append(Fault(
                "words", "mark changed", "minor",
                f"{source.text(was_word)} → {output.text(now_word)}",
                "a part printed raised or lowered, drawn inline after a mark",
                source_box=source.box(was_word), output_box=output.box(now_word)))
    unmatched_source = [i for i in range(len(source.tokens)) if i not in alignment.pairs]
    unmatched_output = [j for j in range(len(output.tokens)) if j not in matched_output]
    crossed = _crosses_as_x(source, output, alignment, unmatched_output)
    if crossed:
        invented["x"] -= len(crossed)
        unmatched_output = [j for j in unmatched_output if j not in {j for _, j in crossed}]
        faults.append(Fault(
            "words", "mark changed", "minor", "✕ → X",
            f"{len(crossed)} cross mark{'s' if len(crossed) > 1 else ''} drawn as the letter X",
            source_box=source.box(crossed[0][0]), output_box=output.box(output.owner[crossed[0][1]])))
    in_picture = [i for i in unmatched_source
                  if pictured and _inside(source.box(source.owner[i]), pictured)]
    drawn_as_picture: Counter[str] = Counter()
    for token, count in Counter(source.tokens[i] for i in in_picture).items():
        drawn_as_picture[token] = min(count, max(lost[token], 0))
        lost[token] -= drawn_as_picture[token]
    if +drawn_as_picture:
        pictured_words = sorted(+drawn_as_picture)
        total = sum(drawn_as_picture.values())
        faults.append(Fault(
            "words", "drawn as a picture", "minor",
            " ".join(pictured_words[:8]) + (" …" if len(pictured_words) > 8 else ""),
            f"{total} word{'s' if total > 1 else ''} printed as text, drawn in a figure's pixels",
            source_box=_union(source.box(source.owner[i]) for i in in_picture
                              if drawn_as_picture[source.tokens[i]] > 0)))
        unmatched_source = [i for i in unmatched_source if i not in set(in_picture)]
    for token, count in sorted(lost.items()):
        if count > 0:
            faults.append(Fault("words", "lost", "major", token,
                                f"printed {count} more time{'s' if count > 1 else ''} "
                                "than drawn",
                                source_box=_first_word(source, token, unmatched_source)))
    for token, count in sorted(invented.items()):
        if count > 0:
            faults.append(Fault("words", "invented", "major", token,
                                f"drawn {count} more time{'s' if count > 1 else ''} "
                                "than printed",
                                output_box=_first_word(output, token, unmatched_output)))
    drawn_as_x = Counter(next(ch for ch in source.words[w].text if ch in CROSSES) for w, _ in crossed)
    for mark, count in sorted((_marks(source.words) - _marks(output.words) - drawn_as_x).items()):
        faults.append(Fault("words", "mark lost", "major", mark,
                            f"{count} printed and not drawn"))
    for mark, count in sorted((_marks(output.words) - _marks(source.words)).items()):
        faults.append(Fault("words", "mark invented", "major", mark,
                            f"{count} drawn and not printed"))
    lost_dashes = _cell_dashes(source) - _cell_dashes(output, anywhere=True)
    if lost_dashes > 0:
        faults.append(Fault("words", "lost", "major", "—",
                            f"{lost_dashes} cell{'s' if lost_dashes > 1 else ''} printed "
                            "with a dash for none, drawn blank"))
    return _grouped_marks(faults + _check_spelling(source, output, alignment))


INLINE_MARKS = re.compile(r"[_^{}]")
"""What a render writes for a raised or lowered part it sets inline:
`H_2015`, `x^2`, `V_{t}`."""


def _scripts_inline(source: _Side, output: _Side) -> list[tuple[int, int]]:
    """Printed words with a part set smaller beside their first — a
    subscript or a superscript, glued (`GLUE`) — each paired with an output
    word that spells it with marks between: c0576's H₂₀₁₅ drawn `H_2015`.
    A minor, one 'mark changed' (Alessandro, review round 3, 2026-11-07:
    "formula is overall correct but misrepresented")."""
    def bare(text: str) -> str:
        return INLINE_MARKS.sub("", _EDGE.sub("", text))

    scripted: dict[str, list[int]] = defaultdict(list)
    for owner, group in source.glued.items():
        if len(group) > 1 and min(source.words[w].font_px for w in group[1:]) \
                < source.words[group[0]].font_px:
            scripted[bare(source.text(owner))].append(owner)
    found = []
    for owner in output.glued:
        text = _EDGE.sub("", output.text(owner))
        if INLINE_MARKS.search(text) and scripted.get(bare(text)):
            found.append((scripted[bare(text)].pop(0), owner))
    return found


DASHES = frozenset("—–-")
"""A cell printed as one dash says there is none, and a tokenizer that drops
punctuation cannot see it go: nonlatin_0014's travel row, two dashes drawn
as two blank cells, found by eye 2026-10-31."""


def _cell_dashes(side: _Side, *, anywhere: bool = False) -> int:
    """Words that are one dash alone: in a table cell on the source; on the
    output anywhere, where a table may be drawn some other way."""
    return sum(1 for word in side.words if word.text.strip() in DASHES
               and (anywhere or word.cell is not None))


_EDGE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def _printed(word: Word, text: str) -> str:
    if word.transform == "uppercase":
        text = text.upper()
    elif word.transform == "lowercase":
        text = text.lower()
    elif word.transform == "capitalize":
        text = text[:1].upper() + text[1:]
    return _EDGE.sub("", unicodedata.normalize("NFKC", text))


def _check_spelling(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """A word matched one for one whose printed form differs inside it: case,
    after the source's `text-transform`, or a mark between its letters
    (`AQ7-MB-W` read `AQ7–MB–w`). Small capitals are not judged.

    One for one by the whole word: every token of it paired, all into one
    output word that no other word's tokens reach and that has no others.
    A word of three tokens is judged like a word of one (issue B, the
    review of the 31: `AQ7-MB-W` skipped once words were counted by
    token)."""
    held: dict[int, list[int]] = defaultdict(list)
    for index, owner in enumerate(source.owner):
        held[owner].append(index)
    reached: dict[int, set[int]] = defaultdict(set)
    for i, j in alignment.pairs.items():
        reached[output.owner[j]].add(source.owner[i])
    count_output = Counter(output.owner)
    faults: list[Fault] = []
    for first, indexes in sorted(held.items()):
        if not all(i in alignment.pairs for i in indexes):
            continue
        landed = {output.owner[alignment.pairs[i]] for i in indexes}
        if len(landed) != 1:
            continue
        second = landed.pop()
        if reached[second] != {first} or count_output[second] != len(indexes):
            continue
        was, now = source.words[first], output.words[second]
        if was.small_caps or now.small_caps:
            continue
        printed = _printed(was, source.text(first)), _printed(now, output.text(second))
        if printed[0] == printed[1]:
            continue
        if _LETTERS.sub("", printed[0]) == _LETTERS.sub("", printed[1]):
            # The same letters with another mark between them: a curly
            # apostrophe drawn straight, an en dash drawn as a hyphen
            # (`l’11` as `l'11`, dev's French and Italian pages). A minor:
            # a look-alike mark (issue N, Alessandro, 2026-11-01).
            faults.append(Fault("words", "mark changed", "minor",
                                f"{printed[0]} → {printed[1]}",
                                source_box=source.box(first), output_box=output.box(second)))
        else:
            faults.append(Fault("words", "spelling", "major",
                                f"{printed[0]} → {printed[1]}",
                                source_box=source.box(first), output_box=output.box(second)))
    return faults


_LETTERS = re.compile(r"[\W_]", re.UNICODE)


def _grouped_marks(faults: list[Fault]) -> list[Fault]:
    """Mark changes as one fault a page: dev's French pages draw every
    apostrophe straight, one word in ten."""
    marks = [f for f in faults if f.fault == "mark changed"]
    if len(marks) <= 1:
        return faults
    rest = [f for f in faults if f.fault != "mark changed"]
    shown = sorted(set(f.element for f in marks))
    return rest + [Fault("words", "mark changed", "minor",
                         "; ".join(shown[:3]) + (f"; and {len(shown) - 3} more" if len(shown) > 3 else ""),
                         f"{len(marks)} words drawn with another mark between their letters",
                         source_box=marks[0].source_box, output_box=marks[0].output_box)]


# --- tables: cells and rules ------------------------------------------------


def _cell_tokens(side: _Side, table: int) -> dict[int, list[int]]:
    """Token indexes per cell of one table."""
    held: dict[int, list[int]] = defaultdict(list)
    for index, owner in enumerate(side.owner):
        cell = side.words[owner].cell
        if cell is not None and cell[0] == table:
            held[cell[1]].append(index)
    return held


def _output_place(output: _Side, alignment: Alignment, held: Sequence[int]
                  ) -> tuple[Rect | None, tuple[int, int] | None]:
    """Where a source cell's words landed: their ink, and the output cell
    holding most of them (None when they are in no output table)."""
    landed = [alignment.pairs[i] for i in held if i in alignment.pairs]
    if not landed:
        return None, None
    words = sorted({output.owner[j] for j in landed})
    ink = _union(output.box(w) for w in words)
    cells = Counter(output.words[w].cell for w in words if output.words[w].cell is not None)
    return ink, (cells.most_common(1)[0][0] if cells else None)


def _band(output: _Side, ink: Rect, cell: tuple[int, int] | None, axis: int) -> tuple[float, float]:
    """A column's (axis 0) or a row's (axis 1) extent in the output: its
    cell's box when it landed in an output table, else its own ink."""
    if cell is not None:
        box = output.detail.tables[cell[0]].cells[cell[1]].box
    else:
        box = ink
    return (box[0], box[2]) if axis == 0 else (box[1], box[3])


def _overlap(span: tuple[float, float], band: tuple[float, float]) -> float:
    return max(0.0, min(span[1], band[1]) - max(span[0], band[0]))


def _nearest(span: tuple[float, float], bands: dict[int, tuple[float, float]]) -> int | None:
    """The band a span sits in: most overlap, else the nearest centre."""
    if not bands:
        return None
    best = max(bands, key=lambda key: _overlap(span, bands[key]))
    if _overlap(span, bands[best]) > 0:
        return best
    middle = (span[0] + span[1]) / 2
    return min(bands, key=lambda key: abs(middle - (bands[key][0] + bands[key][1]) / 2))


def _check_table(table: Table, source: _Side, output: _Side, alignment: Alignment
                 ) -> list[Fault]:
    faults: list[Fault] = []
    held = _cell_tokens(source, table.index)
    places = {index: _output_place(output, alignment, tokens_)
              for index, tokens_ in held.items()}
    filled = [index for index, cell in enumerate(table.cells)
              if cell.text.strip() and places.get(index, (None, None))[0] is not None]
    if not filled:
        return faults

    # Columns, by the topmost cell of each, as the reader reads them.
    anchors_col: dict[int, int] = {}
    for index in sorted(filled, key=lambda k: (table.cells[k].row, table.cells[k].col)):
        cell = table.cells[index]
        if cell.colspan == 1 and cell.col not in anchors_col:
            anchors_col[cell.col] = index
    col_bands = {col: _band(output, *places[index], axis=0)  # type: ignore[arg-type]
                 for col, index in anchors_col.items()}
    anchors_row: dict[int, int] = {}
    for index in sorted(filled, key=lambda k: (table.cells[k].row, table.cells[k].col)):
        cell = table.cells[index]
        if cell.rowspan == 1 and cell.row not in anchors_row:
            anchors_row[cell.row] = index
    row_bands = {row: _band(output, *places[index], axis=1)  # type: ignore[arg-type]
                 for row, index in anchors_row.items()}

    for index in filled:
        cell = table.cells[index]
        ink, _ = places[index]
        assert ink is not None
        if cell.colspan == 1 and anchors_col.get(cell.col) != index:
            landed = _nearest((ink[0], ink[2]), col_bands)
            if landed is not None and landed != cell.col:
                faults.append(Fault(
                    "cells", "wrong column", "major", cell.text,
                    f"drawn under {table.cells[anchors_col[landed]].text!r}, printed under "
                    f"{table.cells[anchors_col[cell.col]].text!r}",
                    source_box=cell.box, output_box=ink))
        if cell.rowspan == 1 and anchors_row.get(cell.row) != index:
            middle = (ink[1] + ink[3]) / 2
            inside = [row for row, band in row_bands.items() if band[0] <= middle <= band[1]]
            if inside and cell.row not in inside:
                faults.append(Fault(
                    "cells", "wrong row", "major", cell.text,
                    f"drawn on the row of {table.cells[anchors_row[inside[0]]].text!r}, "
                    f"printed on the row of {table.cells[anchors_row[cell.row]].text!r}",
                    source_box=cell.box, output_box=ink))

    sharing: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index in filled:
        landed_in = places[index][1]
        if landed_in is not None:
            sharing[landed_in].append(index)
    for out_cell, indexes in sharing.items():
        if len(indexes) > 1:
            texts = [table.cells[index].text for index in indexes]
            faults.append(Fault(
                "cells", "merged", "major", " + ".join(texts),
                f"{len(indexes)} printed cells drawn as one",
                source_box=_union(table.cells[index].box for index in indexes),
                output_box=output.detail.tables[out_cell[0]].cells[out_cell[1]].box))

    words = [i for tokens_ in held.values() for i in tokens_ if i in alignment.pairs]
    in_table = [i for i in words if output.words[output.owner[alignment.pairs[i]]].cell is not None]
    if words and len(in_table) < len(words) / 2:
        misplaced = any(f.check == "cells" for f in faults)
        faults.append(Fault(
            "structure", "table not kept", "major" if misplaced else "minor",
            table.cells[filled[0]].text,
            "drawn outside any table" + (", its cells out of place" if misplaced
                                         else ", its look kept"),
            source_box=table.box))
    else:
        faults += _check_rules(table, source, output, alignment, held)
    return faults


def _majority_map(pairs: Iterable[tuple[int, int]]) -> dict[int, int]:
    votes: dict[int, Counter[int]] = defaultdict(Counter)
    for key, value in pairs:
        votes[key][value] += 1
    return {key: counter.most_common(1)[0][0] for key, counter in votes.items()}


def _fill(mapping: dict[int, int], size: int) -> dict[int, int]:
    """A row or a column with no words in it, placed between its neighbours
    when they sit one apart in the output."""
    filled = dict(mapping)
    for key in range(size):
        if key in filled:
            continue
        before, after = filled.get(key - 1), mapping.get(key + 1)
        if before is not None and after is not None and after - before == 2:
            filled[key] = before + 1
    return filled


def _check_rules(table: Table, source: _Side, output: _Side, alignment: Alignment,
                 held: dict[int, list[int]]) -> list[Fault]:
    """Every rule the source draws between two cells, or round its table,
    drawn at the same place in the output: the quiz's cells merged by rules
    the output leaves out."""
    landing: list[tuple[TableCell, tuple[int, int]]] = []
    for index, tokens_ in held.items():
        for i in tokens_:
            if i not in alignment.pairs:
                continue
            out_cell = output.words[output.owner[alignment.pairs[i]]].cell
            if out_cell is not None:
                landing.append((table.cells[index], out_cell))
    if not landing:
        return []
    # Each output table the source's cells landed in is judged on the rows
    # and columns that landed in it, and a rule is drawn if any of them
    # draws it: a total row drawn as a table of its own has no row in the
    # main one (c0309's Total HT), and a table drawn as five boxes is five
    # tables (c0439's specification, reviewed 2026-11-01).
    drawn_at: dict[tuple[str, int, int], bool] = {}
    for at in sorted({out_cell[0] for _, out_cell in landing}):
        for key, here in _rules_in(table, output.detail.tables[at],
                                   [(cell, out_cell[1]) for cell, out_cell in landing
                                    if out_cell[0] == at]):
            drawn_at[key] = drawn_at.get(key, False) or here

    def where(row: int, col: int) -> str:
        index = table.slot(row, col)
        return table.cells[index].text[:24] if index is not None else ""

    missing: dict[str, list[str]] = defaultdict(list)
    drawn: Counter[str] = Counter()
    for (axis, row, col), here in sorted(drawn_at.items(), key=lambda kv: (kv[0][0] != "|", kv[0][1:])):
        if axis == "|":
            kind = "frame" if col in (0, table.cols) else "between cells"
            label = f"{where(row, col - 1)} | {where(row, col)}".strip(" |")
        else:
            kind = "frame" if row in (0, table.rows) else "between cells"
            label = f"{where(row - 1, col)} / {where(row, col)}".strip(" /")
        drawn[kind] += 1
        if not here:
            missing[kind].append(label)
    most = Counter(out_cell[0] for _, out_cell in landing).most_common(1)[0][0]
    faults = []
    for kind, examples in missing.items():
        faults.append(Fault(
            "rules", "cells merged as drawn" if kind == "between cells" else "frame missing",
            "major", "; ".join(examples[:3]),
            f"{len(examples)} of the {drawn[kind]} rules the page draws {kind} are not drawn",
            source_box=table.box, output_box=output.detail.tables[most].box))
    return faults


def _rules_in(table: Table, other: Table, landed: Sequence[tuple[TableCell, int]]
              ) -> Iterator[tuple[tuple[str, int, int], bool]]:
    """Each rule the source table draws whose place the output table `other`
    holds, keyed `("|", row, col)` or `("-", row, col)`, and whether `other`
    draws it there. `landed`: the source cells whose words landed in
    `other`, with the output cell they landed in."""
    rows = [(cell.row, other.cells[index].row) for cell, index in landed if cell.rowspan == 1]
    cols = [(cell.col, other.cells[index].col) for cell, index in landed if cell.colspan == 1]
    row_map = _fill(_majority_map(rows), table.rows)
    col_map = _fill(_majority_map(cols), table.cols)

    def out_row_edge(row: int) -> int | None:
        """The output edge under source row `row - 1`: its row's top, or,
        at the table's foot or where the row below left the table, under
        the row above."""
        if row < table.rows and row in row_map:
            return row_map[row]
        last = row_map.get(row - 1)
        return None if last is None else max(
            (c.row + c.rowspan for c in other.cells if c.row <= last < c.row + c.rowspan),
            default=last + 1)

    def out_col_edge(col: int) -> int | None:
        if col < table.cols and col in col_map:
            return col_map[col]
        last = col_map.get(col - 1)
        return None if last is None else max(
            (c.col + c.colspan for c in other.cells if c.col <= last < c.col + c.colspan),
            default=last + 1)

    for row in range(table.rows):
        for col in range(table.cols + 1):
            if not table.vertical_rule(row, col) or row not in row_map:
                continue
            edge = out_col_edge(col)
            if edge is not None:
                yield ("|", row, col), other.vertical_rule(row_map[row], edge)
    for row in range(table.rows + 1):
        for col in range(table.cols):
            if not table.horizontal_rule(row, col) or col not in col_map:
                continue
            edge = out_row_edge(row)
            if edge is not None:
                yield ("-", row, col), other.horizontal_rule(edge, col_map[col])


# --- structure: lists and headings -------------------------------------------


NUMBER_FIRST = re.compile(r"^\(?(\d{1,3}([.)]|(?=[^\W\d_]))|[a-z][.)]|[ivxlc]{1,4}[.)])",
                          re.IGNORECASE | re.UNICODE)


def _item_class(marker: str, numbered: bool, ticked: bool) -> str:
    if marker != "none":
        return marker
    return "number" if numbered else ("tick" if ticked else "none")


def _check_lists(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    by_item: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, owner in enumerate(source.owner):
        holder = source.words[owner].item
        if holder is not None:
            by_item[holder].append(index)
    found: dict[tuple[int, str], list[str]] = defaultdict(list)
    boxes: dict[tuple[int, str], list[Rect]] = defaultdict(list)
    landed_in: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for (group, number), held in sorted(by_item.items()):
        item = source.detail.lists[group].items[number]
        was = _item_class(item.marker, item.numbered_text, item.ticked_text)
        out_words = [output.owner[alignment.pairs[i]] for i in held if i in alignment.pairs]
        if not out_words:
            continue
        out_items: Counter[tuple[int, int]] = Counter(
            spot for spot in (output.words[w].item for w in out_words) if spot is not None)
        if out_items:
            where = out_items.most_common(1)[0][0]
            landed_in[where].append((group, number))
            other = output.detail.lists[where[0]].items[where[1]]
            now = _item_class(other.marker, other.numbered_text, other.ticked_text)
            text_number = bool(NUMBER_FIRST.match(other.text))
        else:
            block = Counter(output.words[w].block for w in out_words).most_common(1)[0][0]
            first = min(w for w in range(len(output.words)) if output.words[w].block == block)
            text_number = bool(NUMBER_FIRST.match(output.words[first].text))
            now = "number" if text_number else "none"
            found[(group, "list not kept")].append(item.text[:40])
            boxes[(group, "list not kept")].append(item.box)
        if was == "number" and now == "bullet":
            kind = "numbers as bullets"
        elif was == "number" and now not in ("number",) and not text_number \
                and item.marker == "number":
            kind = "numbers lost"
        elif was != now and not (was == "number" and text_number):
            kind = "marker changed"
        else:
            continue
        found[(group, kind)].append(item.text[:40])
        boxes[(group, kind)].append(item.box)
    reverse = {j: i for i, j in alignment.pairs.items()}
    out_tokens: dict[tuple[int, int], list[int]] = defaultdict(list)
    for j, owner in enumerate(output.owner):
        spot = output.words[owner].item
        if spot is not None:
            out_tokens[spot].append(j)
    for (group, number), held in sorted(out_tokens.items()):
        other = output.detail.lists[group].items[number]
        if other.marker not in ("bullet", "number", "tick"):
            continue
        mapped = [reverse[j] for j in held if j in reverse]
        if mapped and all(source.words[source.owner[i]].item is None for i in mapped):
            found[(-1 - group, "marker changed")].append(f"{other.marker} added: {other.text[:30]}")
            boxes[(-1 - group, "marker changed")].append(source.box(source.owner[mapped[0]]))
    for where, items in landed_in.items():
        if len(items) > 1:
            texts = [source.detail.lists[g].items[n].text[:30] for g, n in items]
            found[(items[0][0], "items merged")].append(" + ".join(texts))
    severity = {"numbers as bullets": "major", "numbers lost": "major",
                "marker changed": "minor", "list not kept": "minor", "items merged": "minor"}
    return [Fault("structure", kind, severity[kind], "; ".join(items[:3]),
                  f"{len(items)} item{'s' if len(items) > 1 else ''}",
                  source_box=_union(boxes[(group, kind)]) if boxes[(group, kind)] else None)
            for (group, kind), items in sorted(found.items())]


def _block_words(side: _Side) -> dict[int, list[int]]:
    held: dict[int, list[int]] = defaultdict(list)
    for index, owner in enumerate(side.owner):
        held[side.words[owner].block].append(index)
    return held


def _landed_block(output: _Side, alignment: Alignment, held: Sequence[int]) -> int | None:
    blocks = Counter(output.words[output.owner[alignment.pairs[i]]].block
                     for i in held if i in alignment.pairs)
    return blocks.most_common(1)[0][0] if blocks else None


def _check_headings(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    faults = []
    held = _block_words(source)
    for block in source.projection.blocks:
        if block.role != "heading" or block.index not in held:
            continue
        landed = _landed_block(output, alignment, held[block.index])
        if landed is None:
            continue
        if output.projection.blocks[landed].role != "heading":
            faults.append(Fault("structure", "heading not kept", "minor", block.text[:60],
                                "drawn as body text; the type checks say whether it looks so",
                                source_box=block.ink, output_box=output.projection.blocks[landed].ink))
    return faults


# --- order --------------------------------------------------------------------


def _groups(source: _Side) -> list[tuple[str, list[int]]]:
    """The source's groups, each a name and its tokens: every table, every
    list, and the stretch under each heading up to the next."""
    groups: list[tuple[str, list[int]]] = []
    tables: dict[int, list[int]] = defaultdict(list)
    lists: dict[int, list[int]] = defaultdict(list)
    for index, owner in enumerate(source.owner):
        word = source.words[owner]
        if word.cell is not None:
            tables[word.cell[0]].append(index)
        if word.item is not None:
            lists[word.item[0]].append(index)
    for table, held in tables.items():
        groups.append((f"table {source.detail.tables[table].cells[0].text[:30]!r}", held))
    for group, held in lists.items():
        groups.append((f"list {source.detail.lists[group].items[0].text[:30]!r}", held))
    held_by_block = _block_words(source)
    headings = [block.index for block in source.projection.blocks if block.role == "heading"]
    order = sorted(held_by_block, key=lambda block: min(held_by_block[block]))
    for at, heading in enumerate(headings):
        if heading not in held_by_block:
            continue
        start = min(held_by_block[heading])
        ends = [min(held_by_block[h]) for h in headings[at + 1:] if h in held_by_block
                and min(held_by_block[h]) > start]
        end = min(ends) if ends else len(source.tokens)
        left = source.projection.blocks[heading].ink[0] - SECTION_SLACK
        groups.append((f"section {source.projection.blocks[heading].text[:30]!r}",
                       [i for i in range(start, end)
                        if source.projection.blocks[source.words[source.owner[i]].block].ink[0]
                        >= left]))
    del order
    return groups


def _runs(labels: Sequence[str]) -> list[tuple[str, int]]:
    runs: list[tuple[str, int]] = []
    for label in labels:
        if runs and runs[-1][0] == label:
            runs[-1] = (label, runs[-1][1] + 1)
        else:
            runs.append((label, 1))
    return runs


def _interleaves(positions: Sequence[tuple[int, str]]) -> bool:
    labels = [label for _, label in sorted(positions)]
    runs = [run for run in _runs(labels) if run[1] >= RUN_TOKENS]
    return len(_runs([label for label, _ in runs])) >= 3


def _check_order(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    faults: list[Fault] = []
    groups = _groups(source)
    for a in range(len(groups)):
        for b in range(a + 1, len(groups)):
            (name_a, held_a), (name_b, held_b) = groups[a], groups[b]
            if set(held_a) & set(held_b):
                continue
            mine = [(i, "a") for i in held_a] + [(i, "b") for i in held_b]
            if _interleaves(mine):
                continue
            if _columns_apart(source, held_a, held_b) and _columns_apart(
                    output, [alignment.pairs[i] for i in held_a if i in alignment.pairs],
                    [alignment.pairs[i] for i in held_b if i in alignment.pairs]):
                continue
            theirs = [(alignment.pairs[i], "a") for i in held_a if i in alignment.strong] + \
                     [(alignment.pairs[i], "b") for i in held_b if i in alignment.strong]
            if _interleaves(theirs):
                beside = _side_by_side(theirs, source, output, alignment)
                faults.append(Fault(
                    "order", "interleaved", "minor" if beside else "major", f"{name_a} and {name_b}",
                    "their words alternate in the output's HTML, drawn side by side as printed"
                    if beside else "their words alternate in the output's reading order",
                    source_box=_union(source.words[source.owner[i]].rect for i in held_a + held_b)))
    faults += _check_headings_over(source, output, alignment)
    return faults


def _column_of(side: _Side, held: Sequence[int]) -> Rect | None:
    """The width a group is set across, by its blocks: the lower median of
    their left edges and of their right, so one item drawn in another
    column does not move its section's (c0221's 4.4, drawn under section
    2); and their full height."""
    blocks: dict[int, list[Rect]] = defaultdict(list)
    for i in held:
        owner = side.owner[i]
        blocks[side.words[owner].block].append(side.box(owner))
    if not blocks:
        return None
    boxes = [_union(found) for found in blocks.values()]
    lefts = sorted(box[0] for box in boxes)
    rights = sorted(box[2] for box in boxes)
    middle = (len(boxes) - 1) // 2
    return (lefts[middle], min(box[1] for box in boxes), rights[middle], max(box[3] for box in boxes))


def _columns_apart(side: _Side, held_a: Sequence[int], held_b: Sequence[int]) -> bool:
    """Two groups set in different columns. Where they are on the page and
    in the render, their words alternating in the output's HTML is no
    fault a reader sees, and an item drawn in the other column is
    `under another heading` (c0221's three sections, fifteen majors for
    two items, Alessandro, review round 1, 2026-11-07)."""
    a, b = _column_of(side, held_a), _column_of(side, held_b)
    return a is not None and b is not None and _apart(a, b)


def _apart(first: Rect, second: Rect) -> bool:
    """Two boxes in different columns: they share no more than `COLUMN_TOUCH`
    of the narrower's width."""
    shared = min(first[2], second[2]) - max(first[0], second[0])
    narrower = min(first[2] - first[0], second[2] - second[0])
    return shared <= max(ALIGN_SLACK, COLUMN_TOUCH * narrower)


def _side_by_side(theirs: Sequence[tuple[int, str]], source: _Side, output: _Side,
                  alignment: Alignment) -> bool:
    """Two groups whose words alternate in the output's HTML, drawn where
    the page prints them: at every switch from one group's run to the
    other's, in the output's order, the second run sits where it is
    printed from the first — beside, below, in the same column or the next
    (`_placed_as_printed`). A render that sets columns as rows of bands
    reads them row by row: the HTML alternates and the eye does not. The right look
    from the wrong HTML, which the criteria call minor (cv_0013's
    education, reviewed 2026-10-31).

    Judged run by run, not on each group's whole extent: a section whose
    own blocks sit in both columns (c0246's header, its number at the
    right) is still drawn as printed, and one run drawn elsewhere breaks
    it — probe_datasheet's key features, printed beside the specification
    table and drawn below it; the recipe's steps, set level with the wrong
    ingredients. The review of dev, 2026-11-01, rejected 18 majors on 12
    pages of the first kind."""
    reverse = {j: i for i, j in alignment.pairs.items()}
    runs: list[tuple[str, list[int]]] = []
    for j, label in sorted(theirs):
        if runs and runs[-1][0] == label:
            runs[-1][1].append(j)
        else:
            runs.append((label, [j]))
    merged: list[tuple[str, list[int]]] = []
    for label, held in runs:
        if len(held) < RUN_TOKENS:
            continue
        if merged and merged[-1][0] == label:
            merged[-1][1].extend(held)
        else:
            merged.append((label, list(held)))
    line = 1.25 * _mode(word.font_px for word in source.words)
    stretch = output.projection.height / max(source.projection.height, 1)
    for (_, first), (_, second) in zip(merged, merged[1:]):
        drawn = [_union(output.box(output.owner[j]) for j in held) for held in (first, second)]
        printed = [_union(source.box(source.owner[reverse[j]]) for j in held) for held in (first, second)]
        if not _placed_as_printed(drawn, printed, line, stretch):
            return False
    return True


def _across(first: Rect, second: Rect) -> str:
    if not _apart(first, second):
        return "same"
    return "right" if second[0] >= first[0] else "left"


def _placed_as_printed(drawn: Sequence[Rect], printed: Sequence[Rect], line: float,
                       stretch: float = 1.0) -> bool:
    """The second run sits from the first where the page puts it: in the
    same column, above or below as printed; in the next, its top no more
    than `DRIFT_LINES` lines off where the page sets it, the page's
    distances stretched as the render stretches the whole. Columns drift
    against each other where the render spaces their lines differently —
    c0221's sections, 17 px apart after six items — and a run moved past
    what it prints beside is not drift: probe_datasheet's key features,
    printed 61 px below the specification table's top and drawn 268 px."""
    if _across(*drawn) != _across(*printed):
        return False
    if _across(*drawn) == "same":
        return (drawn[1][1] >= drawn[0][1]) == (printed[1][1] >= printed[0][1])
    shift_drawn = drawn[1][1] - drawn[0][1]
    shift_printed = (printed[1][1] - printed[0][1]) * stretch
    return abs(shift_drawn - shift_printed) <= DRIFT_LINES * line


def _heading_over(blocks: Sequence[Any], ink: Rect, candidates: Iterable[int]) -> int | None:
    """The heading a box is drawn under: of the headings above it whose
    width it shares, the lowest. `ink` is all of a block's words where they
    are drawn: a pair drawn as a label and a value is one block in the
    source and two in the render."""
    above = [h for h in candidates
             if blocks[h].ink[3] <= ink[1] + ALIGN_SLACK and not _apart(blocks[h].ink, ink)]
    return max(above, key=lambda h: blocks[h].ink[3]) if above else None


def _check_headings_over(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """A block under another heading in the output than in the source.

    Under another heading both in the output's HTML and where it is drawn
    (`_heading_over`): a render that sets columns as rows of bands holds a
    right column's block after the left column's heading in its HTML, and
    draws it under its own (c0565's table, c0208's header, reviewed
    2026-11-01). Either reading alone misleads: the HTML's order there, a
    heading set narrower than its column or out of it in the drawing. On
    the source too: where the page's HTML and its print disagree on a
    block's heading (c0063's footer, after section 6 in the HTML, printed
    under section 5), the block is not judged.

    Judged only where the block's own heading is drawn as a heading: where
    it is not, every block under it would fire, and `heading not kept`
    already names the one fault."""
    held = _block_words(source)
    out_held = _block_words(output)
    reverse = {j: i for i, j in alignment.pairs.items()}
    headings = {block.index for block in source.projection.blocks if block.role == "heading"}
    out_headings = [block.index for block in output.projection.blocks if block.role == "heading"]
    heading_of_out: dict[int, int] = {}
    for out_block in out_headings:
        mapped = Counter(source.words[source.owner[reverse[j]]].block
                         for j in out_held.get(out_block, []) if j in reverse)
        if mapped:
            heading_of_out[out_block] = mapped.most_common(1)[0][0]
    kept = set(heading_of_out.values())
    starts = {block: min(indexes) for block, indexes in held.items()}
    out_starts = {block: min(indexes) for block, indexes in out_held.items()}
    found = []
    for block, indexes in held.items():
        if block in headings or len([i for i in indexes if i in alignment.strong]) < 2:
            continue
        above = [h for h in headings if h in starts and starts[h] < starts[block]]
        if not above:
            continue
        mine = max(above, key=lambda h: starts[h])
        if mine not in kept:
            continue
        printed_under = _heading_over(source.projection.blocks, source.projection.blocks[block].ink,
                                      (h for h in headings if h != block))
        if printed_under is not None and printed_under != mine:
            continue
        landed = _landed_block(output, alignment, indexes)
        if landed is None or landed not in out_starts:
            continue
        over = [h for h in out_headings if h in out_starts and out_starts[h] < out_starts[landed]]
        if not over:
            continue
        theirs = heading_of_out.get(max(over, key=lambda h: out_starts[h]))
        if theirs is None or theirs == mine or theirs not in headings:
            continue
        drawn = [output.owner[alignment.pairs[i]] for i in indexes if i in alignment.pairs]
        placed = {output.words[owner].block for owner in drawn}
        seen = _heading_over(output.projection.blocks, _union(output.box(owner) for owner in drawn),
                             (h for h in out_headings if h in heading_of_out and h not in placed))
        if seen is None or heading_of_out[seen] == mine:
            continue
        found.append((f"printed under {source.projection.blocks[mine].text[:30]!r}, "
                      f"drawn under {source.projection.blocks[theirs].text[:30]!r}",
                      source.projection.blocks[block].text[:40],
                      source.projection.blocks[block].ink))
    return _grouped("order", "under another heading", "major", found)


# --- lines ----------------------------------------------------------------------


def _had_room(side: _Side, frames: dict[int, Frames], end: int, after: int) -> bool:
    """Whether the line ending at word `end` had room for word `after` in
    its block's content box: a break there was set, not made by the
    column's width."""
    line = side.line_of[end]
    found = frames.get(line[0])
    if found is None or not found.chain:
        return True
    box, frame, word = side.line_box(line), found.chain[0], side.box(after)
    widest = max(side.line_box(other)[2] - side.line_box(other)[0]
                 for other in side.line_words if other[0] == line[0])
    if len(found.chain) > 1 and not _justified(found) and abs((frame[2] - frame[0]) - widest) <= 1.0 \
            and (found.chain[1][2] - found.chain[1][0]) > (frame[2] - frame[0]) + 1.0:
        # A box as wide as its widest line, inside a wider one, grew to its
        # lines and would have grown before it wrapped: its breaks are set
        # (the lab report's right-hand header, 'Collected … 08:12'). Not a
        # justified block, whose every full line is as wide as its box.
        return True
    room = (frame[2] - frame[0]) - (box[2] - box[0]) - (word[2] - word[0])
    return room >= ROOM_SPARE * side.words[after].font_px


ROOM_SPARE = 0.8
"""How much room, in ems, a line must have left beside the next word for a
break before that word to count as set (`_had_room`): a space, about a
third of an em, and as much again, so a word that only just did not fit
is a wrap. c0363's 'con | una', 678 px of a 700 px column and a 21 px
word, wrapped."""


def _check_lines(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """Every line breaking where the page breaks it. Judged on word pairs
    that sit next to each other on both sides: two words on one printed
    line drawn on two (a break added), two printed lines drawn as one (a
    break lost), and two printed rows from different blocks drawn on one
    line (a label printed over its value, flattened).

    A break the column's width makes is a re-wrap, minor: a paragraph set
    in a wider column breaks at other words and loses nothing. A break
    where the line had room for the next word is set, and losing or adding
    one is major: fields printed one to a line run into a paragraph
    (c0246), a line split short (Alessandro, review round 3, 2026-11-07)."""
    mine, theirs = _frames(source), _frames(output)
    added: dict[int, int] = Counter()
    lost: dict[int, int] = Counter()
    set_breaks: set[int] = set()
    joined: dict[int, int] = Counter()
    breaks: dict[int, int] = Counter()
    for i in range(len(source.tokens) - 1):
        a, b = source.owner[i], source.owner[i + 1]
        if a == b:
            continue
        block = source.words[a].block
        same_block = source.words[b].block == block
        same_line = source.line_of[a] == source.line_of[b]
        if same_block and not same_line:
            breaks[block] += 1
        if i not in alignment.pairs or i + 1 not in alignment.pairs:
            continue
        j, k = alignment.pairs[i], alignment.pairs[i + 1]
        if k != j + 1:
            continue
        x, y = output.owner[j], output.owner[k]
        out_same = output.line_of[x] == output.line_of[y]
        if same_block and same_line and not out_same \
                and not _same_row(output.words[x].rect, output.words[y].rect):
            # Two cells side by side are two lines of two blocks, one row
            # to the eye: a pair drawn label | value (probe_minutes' Present).
            added[block] += 1
            if output.words[x].block != output.words[y].block or _had_room(output, theirs, x, y):
                # A line the render cuts into two blocks is split, not
                # wrapped: c0246's 'Diagnosi:' drawn over its text.
                set_breaks.add(block)
        elif same_block and not same_line and out_same:
            lost[block] += 1
            if _had_room(source, mine, a, b):
                set_breaks.add(block)
        elif not same_block and out_same and not _same_row(source.words[a].rect,
                                                            source.words[b].rect):
            joined[block] += 1
    texts = {block.index: block for block in source.projection.blocks}
    faults = []
    for severity, fault, blocks in (
            ("major", "broken differently", sorted((set(added) | set(lost)) & set_breaks)),
            ("minor", "re-wrapped", sorted((set(added) | set(lost)) - set_breaks))):
        found = _grouped("lines", fault, severity,
                         [("lines break at other words", texts[block].text[:40], texts[block].ink)
                          for block in blocks])
        if found:
            found[0] = Fault(**{**asdict(found[0]), "note": (
                f"{sum(added[block] for block in blocks)} breaks added and "
                f"{sum(lost[block] for block in blocks)} of "
                f"{sum(breaks[block] for block in blocks)} lost, in {len(blocks)} "
                f"block{'s' if len(blocks) > 1 else ''}")})
        faults += found
    faults += _grouped("lines", "rows joined", "major",
                       [("drawn on one line with the row printed below it",
                         texts[block].text[:40], texts[block].ink) for block in sorted(joined)])
    return faults


# --- height, alignment, type -----------------------------------------------------


def _check_height(output: _Side, picture_height: int) -> tuple[list[Fault], float]:
    ratio = output.projection.height / picture_height if picture_height else 1.0
    off = abs(ratio - 1)
    if off > 0.10:
        return [Fault("height", "height", "major", f"{ratio:.2f} of the picture's height",
                      f"{output.projection.height} px drawn against {picture_height}")], ratio
    if off > HEIGHT_NOTICED:
        return [Fault("height", "height", "minor", f"{ratio:.2f} of the picture's height",
                      f"{output.projection.height} px drawn against {picture_height}")], ratio
    return [], ratio


TEXT_ALIGN = {"left": "left", "start": "left", "justify": "justified", "-webkit-left": "left",
              "center": "centre", "-webkit-center": "centre",
              "right": "right", "end": "right", "-webkit-right": "right"}
"""A block's computed `text-align`, as the line's alignment when the line
sits in the block's own box. Justified is its own: a justified paragraph
drawn ragged was found by eye on five of the 31 (the letter, the minutes,
the CV's publications, the report, the paper), 2026-10-31, and read as left
it could not be seen. A justified block's last line is set left."""


def alignment_of(line: Rect, frames: Frames | None, *, last: bool = False) -> str | None:
    """Where a line sits in the first frame wider than it: `left`, `centre`,
    `right`, or `full` when it fills it. None with no frame to judge by.

    In the block's own box, its `text-align` says, which is what an
    indented or hanging first line would otherwise mislead. In an
    ancestor's box — a shrink-wrapped flex item, a chip — where the line's
    ink sits in it."""
    if frames is None:
        return None
    if TEXT_ALIGN.get(frames.align) == "justified":
        # Before the box test: a justified line fills its block's box, so the
        # test would pass over it to an ancestor and read it by its ink, as
        # set right (probe_minutes' items 2 and 3). One that does not fill it
        # is set left, as the last line is: a short line in a justified
        # block, a name ended by a break (c0486's 'Margaret Ellison', c0220's
        # address, reviewed 2026-11-01). Its right edge says: a first line
        # may be indented (paper_0018's abstract).
        fills = frames.chain[0][2] - line[2] <= ALIGN_SLACK
        return "justified" if fills and not last else "left"
    width = line[2] - line[0]
    for at, box in enumerate(frames.chain):
        if box[2] - box[0] >= width + FRAME_SLACK:
            if at == 0 and frames.align in TEXT_ALIGN:
                return TEXT_ALIGN[frames.align]
            left, right = line[0] - box[0], box[2] - line[2]
            if left <= ALIGN_SLACK and right <= ALIGN_SLACK:
                return "full"
            if abs(left - right) <= ALIGN_SLACK:
                return "centre"
            return "left" if left < right else "right"
    return None


def _anchor(line: Rect, aligned: str) -> float:
    if aligned == "left":
        return line[0]
    if aligned == "right":
        return line[2]
    return (line[0] + line[2]) / 2


def _moved(printed: Rect, drawn: Rect, was: str, now: str) -> float:
    """How far a line is drawn from where it is printed, at the point its
    alignment holds still: the printed alignment's or the drawn one's. A
    line set in other type keeps that point and moves the rest; a line
    drawn in part (c0551's chips, one of three) keeps neither."""
    return min(abs(_anchor(drawn, aligned) - _anchor(printed, aligned)) for aligned in (was, now))


def _justified(frames: Frames | None) -> bool:
    return frames is not None and TEXT_ALIGN.get(frames.align) == "justified"


def _last_lines(side: _Side) -> dict[int, int]:
    """Each block's last line, which a justified block sets left."""
    last: dict[int, int] = {}
    for block, line in side.line_words:
        last[block] = max(last.get(block, line), line)
    return last


def _frames(side: _Side) -> dict[int, Frames]:
    return {frames.block: frames for frames in side.detail.frames}


def _drawn_spans(source: _Side, output: _Side, alignment: Alignment) -> dict[int, Rect]:
    """Each source block where the render draws it: its matched words in
    the output block holding most of them, so a word matched to a copy
    across the page does not stretch it."""
    held: dict[int, list[int]] = defaultdict(list)
    for i, owner in enumerate(source.owner):
        if i in alignment.pairs:
            held[source.words[owner].block].append(output.owner[alignment.pairs[i]])
    spans = {}
    for block, owners in held.items():
        home = Counter(output.words[owner].block for owner in owners).most_common(1)[0][0]
        spans[block] = _union(output.box(owner) for owner in owners
                              if output.words[owner].block == home)
    return spans


def _printed_beside(side: _Side) -> set[tuple[int, int]]:
    """Pairs of blocks with a line each on one row, apart across it: a
    label and its amount, a title and the note on its line, two boxes
    side by side. Cells of one table are the cells check's."""
    table = {word.block: word.cell[0] for word in side.words if word.cell is not None}
    lines = sorted(((side.line_box(line), line[0]) for line in side.line_words), key=lambda x: x[0][1])
    pairs = set()
    for n, (box, block) in enumerate(lines):
        for other, mate in lines[n + 1:]:
            if other[1] >= box[3]:
                break
            if mate == block or not _same_row(box, other) \
                    or not (other[0] >= box[2] or other[2] <= box[0]):
                continue
            if block in table and table[block] == table.get(mate):
                continue
            pairs.add((min(block, mate), max(block, mate)))
    return pairs


def _check_beside(source: _Side, output: _Side, alignment: Alignment) -> tuple[list[Fault], set[int]]:
    """Blocks printed side by side and drawn one under the other: a label's
    amount drawn under it (c0185, c0328), a note drawn under the title it
    shares a line with (c0600), a box drawn under the one it stands beside
    (c0187). Major: the block is drawn in another place, not shifted in
    its own (Alessandro, review rounds 1 to 3, 2026-11-07). Stacked is
    sharing some of their width and none of their height; a block beside
    another only by the page's grid — the next card's text, the seal
    between two signatures — stays apart across however its lines wrap.
    Returns the faults and the blocks drawn under."""
    spans = _drawn_spans(source, output, alignment)
    texts = {block.index: block for block in source.projection.blocks}
    under: dict[int, int] = {}
    for first, second in sorted(_printed_beside(source)):
        if first not in spans or second not in spans:
            continue
        one, two = spans[first], spans[second]
        across = min(one[2], two[2]) - max(one[0], two[0])
        down = min(one[3], two[3]) - max(one[1], two[1])
        if across > 0 and down <= 0:
            lower, upper = (second, first) if two[1] >= one[3] else (first, second)
            under.setdefault(lower, upper)
    return _grouped("beside", "drawn under", "major",
                    [("printed beside, drawn under", f"{texts[lower].text[:40]} (beside "
                      f"{texts[upper].text[:25]!r})", texts[lower].ink)
                     for lower, upper in sorted(under.items())]), set(under)


OVERPRINT = 0.3
"""The share of the smaller of two words' boxes they must cover together
to be drawn one over the other (`_check_overprint`)."""


def _check_overprint(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """Two words apart on the page drawn over each other: c0166's labels
    over their values, read 'Dat01/10/2021'; the contract's second party's
    labels on the first's. Major: neither can be read (Alessandro, review
    round 1, 2026-11-07). Words the page itself sets over each other are
    not judged."""
    printed_as: dict[int, int] = {}
    for i, j in alignment.pairs.items():
        printed_as.setdefault(output.owner[j], source.owner[i])
    # A word wrapped at its hyphen has one box across both lines, over
    # every word between (cv_0013's 'per-scheme').
    drawn = sorted((output.box(owner), owner) for owner in printed_as
                   if not output.words[owner].generated
                   and all(output.words[w].lines == 1 for w in output.glued.get(owner, [owner])))
    found: dict[int, tuple[int, int]] = {}
    for n, (box, owner) in enumerate(drawn):
        for other_box, other in drawn[n + 1:]:
            if other_box[0] >= box[2]:
                break
            across = min(box[2], other_box[2]) - max(box[0], other_box[0])
            down = min(box[3], other_box[3]) - max(box[1], other_box[1])
            if across <= 0 or down <= 0:
                continue
            smaller = min((box[2] - box[0]) * (box[3] - box[1]),
                          (other_box[2] - other_box[0]) * (other_box[3] - other_box[1]))
            if across * down <= OVERPRINT * smaller:
                continue
            mine, theirs = printed_as[owner], printed_as[other]
            if mine == theirs or _area_shared(source.box(mine), source.box(theirs)) > 0:
                continue
            block = source.words[mine].block
            found.setdefault(block, (mine, theirs))
    return _grouped("overprint", "drawn over another word", "major",
                    [("two words apart on the page drawn one over the other",
                      f"{source.text(mine)} / {source.text(theirs)}", source.box(mine))
                     for _, (mine, theirs) in sorted(found.items())], unit="place")


def _area_shared(first: Rect, second: Rect) -> float:
    across = min(first[2], second[2]) - max(first[0], second[0])
    down = min(first[3], second[3]) - max(first[1], second[1])
    return max(across, 0) * max(down, 0)


def _check_alignment(source: _Side, output: _Side, alignment: Alignment,
                     moved: Set[int] = frozenset()) -> list[Fault]:
    """A line set on another side of where the page sets it: minor, a shift
    in its own column or cell — values further from their labels,
    right-aligned numbers drawn left in their column, justified text drawn
    ragged (Alessandro, review rounds 1 to 3, 2026-11-07: "a spacing
    issue… all text is there"). A block drawn in another place is the
    beside check's major, `moved`, and not reported again here."""
    mine, theirs = _frames(source), _frames(output)
    last_mine = _last_lines(source)
    last_theirs = _last_lines(output)
    on_line = Counter(output.line_of[owner] for owner in output.owner)
    changed: dict[int, Counter[str]] = defaultdict(Counter)
    for line, indexes in source.line_words.items():
        if line[0] in moved:
            continue
        held = [i for i, owner in enumerate(source.owner) if owner in indexes]
        out_lines = Counter(output.line_of[output.owner[alignment.pairs[i]]]
                            for i in held if i in alignment.pairs)
        if not out_lines:
            continue
        was_last = last_mine.get(line[0]) == line[1]
        was = alignment_of(source.line_box(line), mine.get(line[0]), last=was_last)
        out_line, there = out_lines.most_common(1)[0]
        # A printed line the render draws as several blocks on one row — a
        # menu's items, each its own link — is read whole: c0548's menu,
        # at the right on both, read by its first item alone as set left.
        drawn = _union(output.line_box(other) for other in out_lines
                       if _same_row(output.line_box(other), output.line_box(out_line)))
        now_last = last_theirs.get(out_line[0]) == out_line[1]
        now = alignment_of(drawn, theirs.get(out_line[0]), last=now_last)
        if was in (None, "full") or now in (None, "full") or was == now:
            continue
        if "justified" not in (was, now) and \
                _moved(source.line_box(line), drawn, was, now) <= PLACE_SLACK:
            continue
        kept = there >= len(held) - 1 and on_line[out_line] <= there + 1
        if {was, now} == {"left", "justified"} and (
                (was == "left" and was_last and _justified(mine.get(line[0])))
                or (now == "left" and now_last and _justified(theirs.get(out_line[0]))
                    and not kept)):
            # A justified block's last line is set left. A paragraph's last
            # line drawn mid-paragraph, or a line drawn last because the
            # output wraps otherwise, is where the paragraph or the line
            # ends: the lines and structure checks' fault, not this one's
            # (newsletter_0008, paper_0018, probe_contract). A line kept as
            # printed and drawn ragged is this one's (paper_0018's abstract).
            continue
        changed[line[0]][f"{was} → {now}"] += 1
    texts = {block.index: block for block in source.projection.blocks}
    return _grouped("alignment", "alignment", "minor",
                    [(f"printed {change.replace(' → ', ', drawn ')}", texts[block].text[:40],
                      texts[block].ink)
                     for block, counts in sorted(changed.items())
                     for change in counts])


def face_class(word: Word) -> str | None:
    known = FACE_CLASS.get(word.family) or FACE_CLASS.get(word.family.lower())
    if known:
        return known
    return "mono" if word.mono else None


def _mode(values: Iterable[float]) -> float:
    counted = Counter(round(value, 1) for value in values)
    return counted.most_common(1)[0][0] if counted else 0.0


def _relation(size: float, body: float) -> str:
    if size > body * (1 + SIZE_MARGIN):
        return "larger"
    if size < body * (1 - SIZE_MARGIN):
        return "smaller"
    return "body"


def _check_type(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    body_mine = _mode(word.font_px for word in source.words)
    body_theirs = _drawn_body(source, output, alignment, body_mine)
    texts = {block.index: block for block in source.projection.blocks}
    pairs_by_block: dict[int, list[tuple[Word, Word]]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for i, j in alignment.pairs.items():
        first, second = source.owner[i], output.owner[j]
        if (first, second) in seen:
            continue
        seen.add((first, second))
        word = source.words[first]
        if word.generated or output.words[second].generated:
            # A CSS counter's look is its marker's, not its item's: the
            # recipe's bold step numbers made every step 'bold lost'.
            continue
        pairs_by_block[word.block].append((word, output.words[second]))
    faces: list[tuple[str, str, Rect]] = []
    near: list[tuple[str, str, Rect]] = []
    sizes, bold, heavy, slant = [], [], [], []
    for block, pairs in sorted(pairs_by_block.items()):
        text, ink = texts[block].text[:40], texts[block].ink
        printed = Counter(face_class(w) for w, _ in pairs).most_common(1)[0][0]
        drawn = Counter(face_class(w) for _, w in pairs).most_common(1)[0][0]
        if printed in JUDGED_FACES and drawn in JUDGED_FACES and printed != drawn:
            # A serif set as a sans reads the same, and looks a little
            # plainer: minor. A monospace or a script lost or added is a
            # different kind of text (Alessandro, review round 4,
            # 2026-11-07, c0552).
            (near if {printed, drawn} == {"serif", "sans"} else faces).append(
                (f"{printed} printed, {drawn} drawn", text, ink))
        px_mine = _mode(w.font_px for w, _ in pairs)
        px_theirs = _mode(w.font_px for _, w in pairs)
        size_mine, size_theirs = px_mine / body_mine, px_theirs / body_theirs
        was, now = _relation(size_mine, 1.0), _relation(size_theirs, 1.0)
        if was != now and abs(math.log(size_theirs / size_mine)) > math.log(1 + SIZE_MARGIN) \
                and abs(math.log(px_theirs / px_mine)) > math.log(1 + SIZE_SEEN):
            # Moved across the margin and by more than it: 1.04 of the body
            # drawn at 1.05 crosses the line and changes nothing a reader
            # sees (cv_0013's job titles, reviewed 2026-11-01). And the
            # line's own size changed enough to see (`SIZE_SEEN`).
            sizes.append((f"printed {_said(was)}, drawn {_said(now)}", text, ink))
        if any(w.weight >= 600 and other.weight < 600 for w, other in pairs):
            bold.append(("bold printed, regular drawn", text, ink))
        if any(w.weight < 600 and other.weight >= 600 for w, other in pairs):
            heavy.append(("regular printed, bold drawn", text, ink))
        if "script" not in (printed, drawn) and \
                sum(w.italic != other.italic for w, other in pairs) > len(pairs) / 2:
            # A script face carries its own slant: a signature set italic in
            # a script face looks as printed (letter_0016, certificate_0021,
            # c0020, c0518, reviewed 2026-11-01).
            slant.append(("italic printed upright" if pairs[0][0].italic
                          else "upright printed italic", text, ink))
    faults = _grouped("type", "wrong face", "major", faces)
    faults += _grouped("type", "other face", "minor", near)
    faults += _grouped("type", "sizes out of proportion", "major",
                       sizes + _hierarchy(pairs_by_block, body_mine, texts))
    faults += _grouped("type", "bold lost", "major", bold)
    faults += _grouped("type", "weight added", "minor", heavy)
    faults += _grouped("type", "italics", "minor", slant)
    return faults


def _drawn_body(source: _Side, output: _Side, alignment: Alignment, body: float) -> float:
    """The size the output gives the words the page prints at its body size.

    Not the output's own commonest size: where two classes come near in
    count — a form's labels and its values — that mode can land on either,
    and every block of both is reported. form_0007, 2026-10-31: the labels
    the page's body, the values the render's, three faults rejected."""
    drawn = [output.words[output.owner[j]].font_px for i, j in alignment.pairs.items()
             if round(source.words[source.owner[i]].font_px, 1) == body]
    return _mode(drawn) if drawn else _mode(word.font_px for word in output.words)


def _said(relation: str) -> str:
    return {"larger": "larger than the body", "smaller": "smaller than the body",
            "body": "at the body's size"}[relation]


def _hierarchy(pairs_by_block: dict[int, list[tuple[Word, Word]]], body: float,
               texts: dict[int, Any]) -> list[tuple[str, str, Rect]]:
    """Blocks set larger than the body whose order the output reverses: a
    heading drawn smaller than the subheading under it."""
    sizes = {block: (_mode(w.font_px for w, _ in pairs), _mode(w.font_px for _, w in pairs))
             for block, pairs in pairs_by_block.items()}
    large = [block for block, (mine, _) in sizes.items() if mine > body * (1 + SIZE_MARGIN)]
    found = []
    for block in large:
        over = [other for other in large if sizes[block][0] > sizes[other][0] * (1 + SIZE_MARGIN)
                and sizes[block][1] < sizes[other][1]]
        if over:
            found.append((f"printed larger than {texts[over[0]].text[:30]!r}, drawn smaller",
                          texts[block].text[:40], texts[block].ink))
    return found


# --- the page ---------------------------------------------------------------------


def _tag(faults: Iterable[Fault], features: Sequence[str]) -> list[Fault]:
    tagged = []
    for fault in faults:
        prefixes = CHECK_FEATURES.get(fault.check, ())
        mine = tuple(feature for feature in features if feature.startswith(prefixes))
        tagged.append(Fault(**{**asdict(fault), "features": mine}))
    return tagged


def check(source: Projection, output: Projection, *, picture_height: int,
          page: str = "", features: Sequence[str] = (),
          spellings: dict[str, str] | None = None,
          pictured: Sequence[Rect] = ()) -> PageCheck:
    """Every check, source against output. Both read with `detail=True`.
    `pictured`: the regions of the page the output draws as pixels
    (`pictured_regions`), in the source's coordinates."""
    mine = _side(source, spellings)
    theirs = _side(output)
    alignment = _nearest_copies(mine, theirs, align(mine.tokens, theirs.tokens))
    faults = _check_words(mine, theirs, alignment, pictured)
    for table in mine.detail.tables:
        if table.rows >= 2 and table.cols >= 2:
            faults += _check_table(table, mine, theirs, alignment)
    faults += _check_lists(mine, theirs, alignment)
    faults += _check_headings(mine, theirs, alignment)
    faults += _check_order(mine, theirs, alignment)
    faults += _check_lines(mine, theirs, alignment)
    height, ratio = _check_height(theirs, picture_height)
    faults += height
    beside, moved = _check_beside(mine, theirs, alignment)
    faults += beside
    faults += _check_overprint(mine, theirs, alignment)
    faults += _check_alignment(mine, theirs, alignment, moved)
    faults += _check_type(mine, theirs, alignment)
    return PageCheck(page=page, faults=tuple(_tag(faults, features)), height_ratio=ratio,
                     unread=theirs.detail.unread, source_tokens=len(mine.tokens),
                     output_tokens=len(theirs.tokens), matched_tokens=len(alignment.pairs),
                     notes=tuple(source.notes) + tuple(output.notes),
                     body_px=_mode(word.font_px for word in mine.words),
                     anchors=_anchors(mine, theirs, alignment))


def _anchors(source: _Side, output: _Side, alignment: Alignment) -> tuple[tuple[float, float], ...]:
    """One matched word per source line, its top on each side, in source
    order. Only strong matches, so a stray single-token match does not pull
    a strip of the render somewhere else."""
    found: dict[tuple[int, int], tuple[float, float]] = {}
    for i in sorted(alignment.strong):
        mine, theirs = source.owner[i], output.owner[alignment.pairs[i]]
        line = source.line_of.get(mine)
        if line is not None and line not in found:
            found[line] = (source.box(mine)[1], output.box(theirs)[1])
    return tuple(sorted(found.values()))


def spellings_for(page: str) -> dict[str, str]:
    if not TWIN_SPELLINGS.exists():
        return {}
    known: dict[str, dict[str, str]] = json.loads(TWIN_SPELLINGS.read_text(encoding="utf-8"))
    return {normalise(was): normalise(now) for was, now in known.get(page, {}).items()}


def page_features(page: str) -> tuple[str, ...]:
    from .corpus import manifest

    entry = manifest().get(page, {})
    found = list(entry.get("features") or ())
    for key in ("arrangement", "type"):
        if entry.get(key):
            found.append(str(entry[key]))
    return tuple(sorted(set(found)))


def check_page(page: str, output_html: Path | str, *, root: Path | None = None) -> PageCheck:
    """One corpus page against its converted HTML, at its picture's width."""
    from PIL import Image

    from .corpus import page as corpus_page

    source = corpus_page(page)
    width, height = Image.open(source.png_path(root)).size
    mine = project(source.html_path(root), width=width, flat=True, detail=True,
                   label=f"{page}/source")
    output = output_html if isinstance(output_html, str) else output_html.read_text(encoding="utf-8")
    theirs = project(output, width=width, detail=True, label=f"{page}/output")
    found = check(mine, theirs, picture_height=height, page=page,
                  features=page_features(page), spellings=spellings_for(page),
                  pictured=pictured_regions(output, width, height))
    registered = registration(source.png_path(root), mine)
    if registered < REGISTERED:
        return replace(found, registered=registered,
                       faults=tuple(f for f in found.faults if f.check not in LAYOUT_CHECKS),
                       notes=found.notes + (
                           f"{', '.join(LAYOUT_CHECKS)} withheld: the HTML does not lay out "
                           f"as its picture (registration {registered:.2f})",))
    return replace(found, registered=registered)


_IR = re.compile(r'<script type="application/json" id="doc-ir">(.*?)</script>', re.S)


def pictured_regions(output_html: str, width: int, height: int) -> tuple[Rect, ...]:
    """The regions of the page an output draws as pixels: each figure Zone
    the render drew from the picture, from the IR it embeds, in the
    picture's coordinates, which are the source's where it registers.

    A word printed inside one is not lost to the eye: a chart's axis, a
    logo's wordmark, a map's labels are drawn, in the figure's pixels. The
    review of dev (2026-11-01) rejected 115 such words called lost on 13
    pages; they are reported as `drawn as a picture`, a figure's minor."""
    found = _IR.search(output_html)
    if found is None:
        return ()
    try:
        zones = json.loads(found.group(1)).get("zones") or ()
    except ValueError:
        return ()
    regions = []
    for zone in zones:
        box = zone.get("bbox") or {}
        if zone.get("kind") == "figure" and zone.get("pixels") and box:
            regions.append((box["left"] * width, box["top"] * height,
                            box["right"] * width, box["bottom"] * height))
    return tuple(regions)


def registration(picture: Path, source: Projection) -> float:
    """Share of the source's word boxes whose crop of the picture spans 64
    grey levels or more: ink, where a word drawn there would have put it."""
    import numpy as np
    from PIL import Image

    grey = np.asarray(Image.open(picture).convert("L"), dtype=np.int16)
    held = counted = 0
    for word in source.detail.words if source.detail else ():
        left, top, right, bottom = (int(round(value)) for value in word.rect)
        if right - left < 2 or bottom - top < 2:
            continue
        counted += 1
        crop = grey[max(top, 0):min(bottom, grey.shape[0]), max(left, 0):min(right, grey.shape[1])]
        if crop.size and int(crop.max()) - int(crop.min()) >= 64:
            held += 1
    return held / counted if counted else 1.0
