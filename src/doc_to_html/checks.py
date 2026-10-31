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

import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .factory.fonts import CANDIDATES, GENERIC
from .projection import Detail, Frames, Projection, Rect, Table, Word, project
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

GLUE = 1.0
"""Pixels between two words' ink below which they are one printed word: a
superscript in its own element (`10<sup>9</sup>`), a bold first syllable
(`<b>con</b>firmed`).

Measured on the 31 known pages, both sides, 2026-10-30: two words next to
each other on one line stand 0 px apart (83 pairs) or 2 px and more (7,985
pairs), never between."""

RUN_TOKENS = 2
"""Tokens a stretch of one group must hold to count when two groups are
tested for interleaving. A single token out of place is an alignment
artefact more often than a moved block."""

CHECK_FEATURES: dict[str, tuple[str, ...]] = {
    "words": ("fmt.", "list.ticks"),
    "cells": ("table.",),
    "rules": ("table.",),
    "structure": ("table.", "list."),
    "order": ("arr.", "list."),
    "lines": ("text.", "kv."),
    "height": ("arr.",),
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
                    and -1.0 <= gap < GLUE:
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


# --- words ------------------------------------------------------------------


def _marks(words: Iterable[Word]) -> Counter[str]:
    return Counter(ch for word in words for ch in word.text if ch in MARKS)


def _first_word(side: _Side, token: str, unmatched: Iterable[int]) -> Rect | None:
    for index in unmatched:
        if side.tokens[index] == token:
            return side.box(side.owner[index])
    return None


def _check_words(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
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
    unmatched_source = [i for i in range(len(source.tokens)) if i not in alignment.pairs]
    unmatched_output = [j for j in range(len(output.tokens)) if j not in matched_output]
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
    for mark, count in sorted((_marks(source.words) - _marks(output.words)).items()):
        faults.append(Fault("words", "mark lost", "major", mark,
                            f"{count} printed and not drawn"))
    for mark, count in sorted((_marks(output.words) - _marks(source.words)).items()):
        faults.append(Fault("words", "mark invented", "major", mark,
                            f"{count} drawn and not printed"))
    faults += _check_spelling(source, output, alignment)
    return faults


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
    (`AQ7-MB-W` read `AQ7–MB–w`). Small capitals are not judged."""
    count_source = Counter(source.owner)
    count_output = Counter(output.owner)
    seen: set[tuple[int, int]] = set()
    faults: list[Fault] = []
    for i, j in sorted(alignment.pairs.items()):
        first, second = source.owner[i], output.owner[j]
        if (first, second) in seen or count_source[first] != 1 or count_output[second] != 1:
            continue
        seen.add((first, second))
        was, now = source.words[first], output.words[second]
        if was.small_caps or now.small_caps:
            continue
        printed = _printed(was, source.text(first)), _printed(now, output.text(second))
        if printed[0] != printed[1]:
            faults.append(Fault("words", "spelling", "major",
                                f"{printed[0]} → {printed[1]}",
                                source_box=source.box(first), output_box=output.box(second)))
    return faults


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
    landed: Counter[int] = Counter()
    rows: list[tuple[int, int]] = []
    cols: list[tuple[int, int]] = []
    for index, tokens_ in held.items():
        cell = table.cells[index]
        for i in tokens_:
            if i not in alignment.pairs:
                continue
            out_cell = output.words[output.owner[alignment.pairs[i]]].cell
            if out_cell is None:
                continue
            landed[out_cell[0]] += 1
            out = output.detail.tables[out_cell[0]].cells[out_cell[1]]
            if cell.rowspan == 1:
                rows.append((cell.row, out.row))
            if cell.colspan == 1:
                cols.append((cell.col, out.col))
    if not landed:
        return []
    other = output.detail.tables[landed.most_common(1)[0][0]]
    row_map = _fill(_majority_map(rows), table.rows)
    col_map = _fill(_majority_map(cols), table.cols)

    def out_row_edge(row: int) -> int | None:
        if row == table.rows:
            last = row_map.get(row - 1)
            return None if last is None else max(
                (c.row + c.rowspan for c in other.cells if c.row <= last < c.row + c.rowspan),
                default=last + 1)
        return row_map.get(row)

    def out_col_edge(col: int) -> int | None:
        if col == table.cols:
            last = col_map.get(col - 1)
            return None if last is None else max(
                (c.col + c.colspan for c in other.cells if c.col <= last < c.col + c.colspan),
                default=last + 1)
        return col_map.get(col)

    missing: dict[str, list[str]] = defaultdict(list)
    drawn: Counter[str] = Counter()

    def where(row: int, col: int) -> str:
        index = table.slot(row, col)
        return table.cells[index].text[:24] if index is not None else ""

    for row in range(table.rows):
        for col in range(table.cols + 1):
            if not table.vertical_rule(row, col) or row not in row_map:
                continue
            edge, out_row = out_col_edge(col), row_map[row]
            if edge is None:
                continue
            kind = "frame" if col in (0, table.cols) else "between cells"
            drawn[kind] += 1
            if not other.vertical_rule(out_row, edge):
                missing[kind].append(f"{where(row, col - 1)} | {where(row, col)}".strip(" |"))
    for row in range(table.rows + 1):
        for col in range(table.cols):
            if not table.horizontal_rule(row, col) or col not in col_map:
                continue
            edge, out_col = out_row_edge(row), col_map[col]
            if edge is None:
                continue
            kind = "frame" if row in (0, table.rows) else "between cells"
            drawn[kind] += 1
            if not other.horizontal_rule(edge, out_col):
                missing[kind].append(f"{where(row - 1, col)} / {where(row, col)}".strip(" /"))
    faults = []
    for kind, examples in missing.items():
        faults.append(Fault(
            "rules", "cells merged as drawn" if kind == "between cells" else "frame missing",
            "major", "; ".join(examples[:3]),
            f"{len(examples)} of the {drawn[kind]} rules the page draws {kind} are not drawn",
            source_box=table.box, output_box=other.box))
    return faults


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
        groups.append((f"section {source.projection.blocks[heading].text[:30]!r}",
                       list(range(start, end))))
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
            theirs = [(alignment.pairs[i], "a") for i in held_a if i in alignment.strong] + \
                     [(alignment.pairs[i], "b") for i in held_b if i in alignment.strong]
            if _interleaves(theirs):
                faults.append(Fault(
                    "order", "interleaved", "major", f"{name_a} and {name_b}",
                    "their words alternate in the output's reading order",
                    source_box=_union(source.words[source.owner[i]].rect for i in held_a + held_b)))
    faults += _check_headings_over(source, output, alignment)
    return faults


def _check_headings_over(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """A block under another heading in the output than in the source.

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
        landed = _landed_block(output, alignment, indexes)
        if landed is None or landed not in out_starts:
            continue
        over = [h for h in out_headings if h in out_starts and out_starts[h] < out_starts[landed]]
        if not over:
            continue
        theirs = heading_of_out.get(max(over, key=lambda h: out_starts[h]))
        if theirs is not None and theirs != mine and theirs in headings:
            found.append((f"printed under {source.projection.blocks[mine].text[:30]!r}, "
                          f"drawn under {source.projection.blocks[theirs].text[:30]!r}",
                          source.projection.blocks[block].text[:40],
                          source.projection.blocks[block].ink))
    return _grouped("order", "under another heading", "major", found)


# --- lines ----------------------------------------------------------------------


def _check_lines(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    """Every line breaking where the page breaks it. Judged on word pairs
    that sit next to each other on both sides: two words on one printed
    line drawn on two (a break added), two printed lines drawn as one (a
    break lost), and two printed rows from different blocks drawn on one
    line (a label printed over its value, flattened)."""
    added: dict[int, int] = Counter()
    lost: dict[int, int] = Counter()
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
        if same_block and same_line and not out_same:
            added[block] += 1
        elif same_block and not same_line and out_same:
            lost[block] += 1
        elif not same_block and out_same and not _same_row(source.words[a].rect,
                                                            source.words[b].rect):
            joined[block] += 1
    texts = {block.index: block for block in source.projection.blocks}
    changed = sorted(set(added) | set(lost))
    faults = _grouped("lines", "broken differently", "major",
                      [("lines break at other words", texts[block].text[:40], texts[block].ink)
                       for block in changed])
    if faults:
        faults[0] = Fault(**{**asdict(faults[0]), "note": (
            f"{sum(added.values())} breaks added and {sum(lost.values())} of "
            f"{sum(breaks[block] for block in changed)} lost, in {len(changed)} "
            f"block{'s' if len(changed) > 1 else ''}")})
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


TEXT_ALIGN = {"left": "left", "start": "left", "justify": "left", "-webkit-left": "left",
              "center": "centre", "-webkit-center": "centre",
              "right": "right", "end": "right", "-webkit-right": "right"}
"""A block's computed `text-align`, as the line's alignment when the line
sits in the block's own box. Justified reads as left: its full lines fill
the box and its last line is set left."""


def alignment_of(line: Rect, frames: Frames | None) -> str | None:
    """Where a line sits in the first frame wider than it: `left`, `centre`,
    `right`, or `full` when it fills it. None with no frame to judge by.

    In the block's own box, its `text-align` says, which is what an
    indented or hanging first line would otherwise mislead. In an
    ancestor's box — a shrink-wrapped flex item, a chip — where the line's
    ink sits in it."""
    if frames is None:
        return None
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


def _frames(side: _Side) -> dict[int, Frames]:
    return {frames.block: frames for frames in side.detail.frames}


def _check_alignment(source: _Side, output: _Side, alignment: Alignment) -> list[Fault]:
    mine, theirs = _frames(source), _frames(output)
    changed: dict[int, Counter[str]] = defaultdict(Counter)
    for line, indexes in source.line_words.items():
        held = [i for i, owner in enumerate(source.owner) if owner in indexes]
        out_lines = Counter(output.line_of[output.owner[alignment.pairs[i]]]
                            for i in held if i in alignment.pairs)
        if not out_lines:
            continue
        was = alignment_of(source.line_box(line), mine.get(line[0]))
        out_line = out_lines.most_common(1)[0][0]
        now = alignment_of(output.line_box(out_line), theirs.get(out_line[0]))
        if was in (None, "full") or now in (None, "full") or was == now:
            continue
        changed[line[0]][f"{was} → {now}"] += 1
    texts = {block.index: block for block in source.projection.blocks}
    return _grouped("alignment", "alignment", "major",
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
    body_theirs = _mode(word.font_px for word in output.words)
    texts = {block.index: block for block in source.projection.blocks}
    pairs_by_block: dict[int, list[tuple[Word, Word]]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for i, j in alignment.pairs.items():
        first, second = source.owner[i], output.owner[j]
        if (first, second) in seen:
            continue
        seen.add((first, second))
        word = source.words[first]
        pairs_by_block[word.block].append((word, output.words[second]))
    faces, sizes, bold, heavy, slant = [], [], [], [], []
    for block, pairs in sorted(pairs_by_block.items()):
        text, ink = texts[block].text[:40], texts[block].ink
        printed = Counter(face_class(w) for w, _ in pairs).most_common(1)[0][0]
        drawn = Counter(face_class(w) for _, w in pairs).most_common(1)[0][0]
        if printed in JUDGED_FACES and drawn in JUDGED_FACES and printed != drawn:
            faces.append((f"{printed} printed, {drawn} drawn", text, ink))
        was = _relation(_mode(w.font_px for w, _ in pairs), body_mine)
        now = _relation(_mode(w.font_px for _, w in pairs), body_theirs)
        if was != now:
            sizes.append((f"printed {_said(was)}, drawn {_said(now)}", text, ink))
        if any(w.weight >= 600 and other.weight < 600 for w, other in pairs):
            bold.append(("bold printed, regular drawn", text, ink))
        if any(w.weight < 600 and other.weight >= 600 for w, other in pairs):
            heavy.append(("regular printed, bold drawn", text, ink))
        if sum(w.italic != other.italic for w, other in pairs) > len(pairs) / 2:
            slant.append(("italic printed upright" if pairs[0][0].italic
                          else "upright printed italic", text, ink))
    faults = _grouped("type", "wrong face", "major", faces)
    faults += _grouped("type", "sizes out of proportion", "major",
                       sizes + _hierarchy(pairs_by_block, body_mine, texts))
    faults += _grouped("type", "bold lost", "major", bold)
    faults += _grouped("type", "weight added", "minor", heavy)
    faults += _grouped("type", "italics", "minor", slant)
    return faults


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
        if any(sizes[block][0] > sizes[other][0] * (1 + SIZE_MARGIN)
               and sizes[block][1] < sizes[other][1] for other in large):
            found.append(("printed larger than a heading drawn larger than it",
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
          spellings: dict[str, str] | None = None) -> PageCheck:
    """Every check, source against output. Both read with `detail=True`."""
    mine = _side(source, spellings)
    theirs = _side(output)
    alignment = align(mine.tokens, theirs.tokens)
    faults = _check_words(mine, theirs, alignment)
    for table in mine.detail.tables:
        if table.rows >= 2 and table.cols >= 2:
            faults += _check_table(table, mine, theirs, alignment)
    faults += _check_lists(mine, theirs, alignment)
    faults += _check_headings(mine, theirs, alignment)
    faults += _check_order(mine, theirs, alignment)
    faults += _check_lines(mine, theirs, alignment)
    height, ratio = _check_height(theirs, picture_height)
    faults += height
    faults += _check_alignment(mine, theirs, alignment)
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
    return check(mine, theirs, picture_height=height, page=page,
                 features=page_features(page), spellings=spellings_for(page))
