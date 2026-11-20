"""A reader's line that holds two printed lines, cut where the page breaks it — arm D2.

Spec 0024, part two, direction 3. GLM-OCR often returns two printed lines
as one line of text: c0055's `FULL NAME` over `Priya Raghunathan` comes
back `FULL NAME Priya Raghunathan`, c0191's `Pay date` over `08/19/2024`
as `Pay date 08/19/2024`. On a random 30 of the 97 dev pages with a
line-break major, 40 of the 59 faults found in the parser's raw text
were joins of this kind inside one line of its text.

`locate` places each of the reader's lines on tesseract's words, so a
line it joined is placed on a box two printed lines tall. Here tesseract
reads that Zone again, and where the words inside one placed line stand
on two printed lines or more, the line is cut between them: each part
becomes a line of its own, placed on its own words. The words of the
parts are the reader's, never tesseract's; tesseract says only where the
page breaks. A line is cut only where most of its words match
tesseract's, in order: matched in order, they run down the printed lines
and never back.

Nothing is drawn differently by the cut alone: the render keeps a line
of a paragraph broken only where the page sets it short of its lane
(`render._broken`), so a wrapped paragraph cut at its printed line ends
is still reflowed, and an `address` keeps its lines as printed.

Model-free, and D2's alone: `parser_first.measure` calls it straight
after `locate.locate`, so each part is measured by the passes after it
like any placed line, and nothing of today's pipeline runs it.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from . import locate, looks
from .ir import BBox, Block, Cell, Document, Kind, Reading, Run
from .render import SIZE_STEP
from .style import body_glyph

TALL = 1.8
"""A placed line this many body glyphs tall or more is looked into. One
printed line is placed 1.0-1.5 glyphs tall at the body's size; c0191's
`Earnings Statement`, one line of large type, is 2.0, and stays one line
because its words stand on one."""

MATCHED = 0.5
"""The share of a line's words, at least, that must match tesseract's
words in its box, in order, for the line to be cut."""

OVERLAP = 0.5
"""Two words stand on one printed line where their heights overlap by this
share of the shorter or more. tesseract's own line numbers are not used:
over the 123 tall placed lines of the random 30 dev pages, it numbered
one printed line as two on 7 — c0355's `Inês Marques Feixeira`, c0509's
`C · 14 · 22` — and each would have been cut."""


def restore(plain: np.ndarray, document: Document) -> list[list[Cell]]:
    """Cut every placed line of a prose Zone's Blocks that stands on two
    printed lines or more. Returns the parts of each line cut, for
    `apart` once the looks are measured."""
    glyph = body_glyph(plain, document.zones)
    if not glyph or not locate.available():
        return []
    height = plain.shape[0]
    cuts: list[list[Cell]] = []
    for zone in document.zones:
        if zone.bbox is None or not zone.complete or zone.kind in (Kind.TABLE, Kind.FIGURE):
            continue
        if not any(_tall(cell, height, glyph) for block in zone.blocks for cell in block.lines):
            continue
        greek = any(locate.GREEK.search(cell.text) for block in zone.blocks for cell in block.lines)
        found = [word for word in locate.words(plain, zone, glyph=glyph,
                                               languages="ell+eng" if greek else "eng")
                 if word.text]
        for block in zone.blocks:
            lines: list[Cell] = []
            for cell in block.lines:
                parts = _parts(cell, found) if _tall(cell, height, glyph) else None
                lines += parts or [cell]
                if parts:
                    cuts.append(parts)
            block.lines = lines
    return cuts


def apart(document: Document, cuts: Sequence[Sequence[Cell]]) -> int:
    """Set each part of a cut line in a Block of its own where it is
    printed in another look than the part before it — bold against
    regular, or sizes `render.SIZE_STEP` or more apart — and measure the
    gaps again. Returns how many Blocks were added.

    A Block is drawn in one look (`render._common_look`): c0444's
    `Rump of Dorset lamb £24.50`, bold, over `Anchovy crumb, white beans,
    salsa verde.`, regular, cut into two lines of one paragraph, were
    drawn both regular and on one line. Lines in one look stay one Block
    and reflow as a paragraph does."""
    follows = {id(part): id(before) for parts in cuts for before, part in zip(parts, parts[1:])}
    added = 0
    for zone in document.zones:
        blocks: list[Block] = []
        for block in zone.blocks:
            starts = [0] + [index for index in range(1, len(block.lines))
                            if follows.get(id(block.lines[index])) == id(block.lines[index - 1])
                            and _other_look(block.lines[index - 1], block.lines[index])]
            ends = starts[1:] + [len(block.lines)]
            for number, (start, end) in enumerate(zip(starts, ends)):
                blocks.append(block if len(starts) == 1 else replace(
                    block, lines=block.lines[start:end], size=block.size if number == 0 else None,
                    gap=block.gap if number == 0 else None))
            added += len(starts) - 1
        zone.blocks = blocks
    if added:
        looks._blocks(document)
    return added


def _other_look(one: Cell, other: Cell) -> bool:
    first, second = one.look, other.look
    if first is None or second is None:
        return False
    if first.bold is not None and second.bold is not None and first.bold != second.bold:
        return True
    return (first.size is not None and second.size is not None
            and abs(first.size - second.size) >= SIZE_STEP)


def _tall(cell: Cell, height: int, glyph: float) -> bool:
    return (cell.bbox is not None and bool(cell.text.strip())
            and (cell.bbox.bottom - cell.bbox.top) * height >= TALL * glyph)


def _parts(cell: Cell, found: Sequence[locate.Word]) -> list[Cell] | None:
    """The cell cut at the page's line breaks, or None where it stands on
    one printed line or its words cannot be followed down the lines."""
    box = cell.bbox
    assert box is not None
    inside = [word for word in found
              if box.left <= (word.box.left + word.box.right) / 2 <= box.right
              and box.top <= (word.box.top + word.box.bottom) / 2 <= box.bottom]
    rows = _printed_lines(inside)
    if len(rows) < 2:
        return None
    tokens = list(re.finditer(r"\S+", cell.text))
    theirs = [(locate.fold(word.raw or word.text), row)
              for row, words in enumerate(rows) for word in words]
    matcher = difflib.SequenceMatcher(None, [locate.fold(t.group()) for t in tokens],
                                      [text for text, _ in theirs], autojunk=False)
    row_of: list[int | None] = [None] * len(tokens)
    for mine, other, size in matcher.get_matching_blocks():
        for k in range(size):
            row_of[mine + k] = theirs[other + k][1]
    foldable = sum(1 for t in tokens if locate.fold(t.group()))
    if sum(r is not None for r in row_of) < max(2, MATCHED * foldable):
        return None
    # A word tesseract did not match goes with the word before it; one
    # before any match, with the first.
    first = next(r for r in row_of if r is not None)
    filled: list[int] = []
    for r in row_of:
        filled.append(r if r is not None else (filled[-1] if filled else first))
    spans: dict[int, list[int]] = {}
    for index, row in enumerate(filled):
        spans.setdefault(row, []).append(index)
    if len(spans) < 2:
        return None
    return [_piece(cell, tokens[indices[0]].start(), tokens[indices[-1]].end(), rows[row])
            for row, indices in spans.items()]


def _printed_lines(words: Sequence[locate.Word]) -> list[list[locate.Word]]:
    """Words grouped by the printed line they stand on, top to bottom, each
    left to right."""
    rows: list[list[locate.Word]] = []
    for word in sorted(words, key=lambda w: (w.box.top, w.box.left)):
        for row in rows:
            if any(_same_line(word.box, other.box) for other in row):
                row.append(word)
                break
        else:
            rows.append([word])
    rows.sort(key=lambda row: min(w.box.top for w in row))
    return [sorted(row, key=lambda w: w.box.left) for row in rows]


def _same_line(one: BBox, other: BBox) -> bool:
    shared = min(one.bottom, other.bottom) - max(one.top, other.top)
    shorter = min(one.bottom - one.top, other.bottom - other.top)
    return shorter > 0 and shared >= OVERLAP * shorter


def _piece(cell: Cell, start: int, end: int, words: Sequence[locate.Word]) -> Cell:
    """The part of a cell from `start` to `end` of its text, placed on the
    words of its printed line."""
    reading = cell.readings[0]
    readings = [replace(reading, text=reading.text[start:end],
                        runs=_cut_runs(reading.runs, start, end))]
    raw = " ".join(word.raw for word in words if word.raw)
    if raw and any(r.engine == locate.SECOND for r in cell.readings[1:]):
        readings.append(Reading(engine=locate.SECOND, text=raw))
    return Cell(bbox=BBox(min(w.box.left for w in words), min(w.box.top for w in words),
                          max(w.box.right for w in words), max(w.box.bottom for w in words)),
                readings=readings, state=cell.state)


def _cut_runs(runs: Sequence[Run], start: int, end: int) -> list[Run]:
    """The Runs over `start` to `end` of their text, each kept as marked."""
    out, at = [], 0
    for run in runs:
        left, right = max(start, at), min(end, at + len(run.text))
        if left < right:
            out.append(replace(run, text=run.text[left - at:right - at]))
        at += len(run.text)
    return out

