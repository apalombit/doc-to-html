"""Where every entry sits on the page — spec 0011, step 2.

**Why it exists.** Since spec 0008 the IR knows where every Zone sits and
nothing about where anything inside one sits: `ir.Cell.bbox` existed from the
first IR and was never set. Everything inside a Zone — the form's field grid,
which line is centred, where a rule falls between two rows — is drawn in the
house style because nothing records the page's. This fills `Cell.bbox` for
every Cell it can place: a Block's lines, a row's cells, a pair's label and
value. Steps 3 and 4 read it.

**tesseract is a locator, never a reader.** Its words are matched against the
model's and only their boxes are kept. Its text is never printed, never added
and never substituted — on `form_0007` it reads `fernpost` and `CTS` where the
model read `fempost` and `CT9`, and neither reading reaches the page from
here. A Cell nothing matches keeps `bbox = None` and renders exactly as it
did.

**What it is shown.** Each Zone's crop of `Rectified.plain`, in the Zone's own
polarity — the split `style.type_mask` uses — with every straight stroke
longer than `RULE_GLYPHS` glyph heights erased, scaled so a body glyph is
`TARGET_GLYPH` pixels tall. The erasing is what makes a form readable:
measured on `form_0007`'s applicant section on 2026-10-12, tesseract on the
plain crop returns no word of `Whitlock`, `Marion Elspeth` or `CT9 4RD` — each
sits inside a drawn box, and the box hides it from tesseract's line finder in
every page segmentation mode tried (3, 6, 11) — while on the crop with the
boxes' edges erased it returns all three. `style.type_mask`'s own rule
deletion was tried first and loses thin letters: `Whit ock`, `E speth`.

**How a Cell is matched.** Both sides are folded to letters and digits — case,
accents, spaces and punctuation dropped, because tesseract reads `62 ms` as
`62ms` and `At risk` as `Atrisk` — and each Cell takes the run of consecutive
words on one line most similar to it, character by character, at
`MIN_SIMILARITY` or above. **Digits must agree**: where the Cell holds digits,
the run's digits are the same digits in the same order, so `1,180.00` can
never land on `1,238.50`. Repeated text — `Healthy` five times in one column
— is settled by position: the run nearest the height the Cell's row has
already been placed at, or else the first unclaimed one below the Cell
before it.

**When the words fail**, the ink: a table cell from where its row and its
column cross (`_from_grid`), a pair's label or value from its partner's line
(`_from_pairs`), and a prose or list Zone's lines when they count alike with
its Cells (`_from_ink`) — the letter-spaced small capitals tesseract
misreads. A Zone still short of a Cell is first read again turned over.

Measured 2026-10-12 over `s5-result/`: 847 of 868 Cells placed, every box on
its own words in the overlays (`tools/locate_overlay.py`); spec 0011's step
2 outcome names the 21 misses.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np

from .ir import BBox, Cell, CellState, Document, Kind, Reading, Unclaimed, Zone
from .preprocess import PAD_X, ImageArray, _cv2, content_ink, crop_origin, zone_pixels
from .style import body_glyph, dominant, type_lines, type_mask
from .wire import MARKS

TESSERACT = "tesseract"
"""The binary, looked up on `PATH` — no Python dependency."""

FLAGS = ("--oem", "1", "--psm", "6", "-c", "preserve_interword_spaces=1")
"""Pinned once. The LSTM engine, one uniform block of text per crop — the
Zone is already one block, and its line structure is what keeps a Cell's run
on one line. tesseract is deterministic for a fixed input and fixed flags;
`OMP_THREAD_LIMIT=1` is set on every call so that holds under threads too."""

TARGET_GLYPH = 30.0
"""How tall, in pixels, a body glyph is scaled to before it is read. The
spec's figure: tesseract reads the corpus's 9-12px glyphs poorly."""

RULE_GLYPHS = 2.0
"""A straight stroke inked over this many glyph heights is a rule or a box's
edge, never a letter — a lowercase `l` is about one glyph tall, a form's box
2.7, its width tens."""

PAD = 20
"""White border added round a crop, in scaled pixels; tesseract finds no
line that touches the image's edge."""

MIN_SIMILARITY = 0.7
"""How alike, character by character, a Cell and a run of words must be."""

TIE = 0.05
"""Runs within this much of the best are equally good, and position decides."""

GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")


def available() -> bool:
    return shutil.which(TESSERACT) is not None


def fold(text: str) -> str:
    """Letters and digits only, lower case, accents dropped — what a Cell and
    a word are compared as."""
    decomposed = unicodedata.normalize("NFKD", text)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c for c in bare.casefold() if c.isalnum())


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


@dataclass(frozen=True)
class Word:
    """One word tesseract found, folded, and where it sits on the page."""

    text: str
    box: BBox
    line: tuple[int, int, int]
    confidence: float = 100.0
    """tesseract's own, 0 to 100. Read only by `unclaimed`."""
    raw: str = ""
    """What tesseract printed, before folding — spec 0019, B4: `Created:`
    where `text` is `created`. Read only by `separator.read`."""


LEADER_DOT = 0.35
"""A mark no taller than this many glyph heights, and no wider than one, may
be a leader dot or a dash."""

LEADER_RUN = 4
"""How many such marks, evenly spaced on one line, make a leader or a dashed
rule. A sentence's full stop is one; an ellipsis is three."""


def leaders(ink: ImageArray, glyph: float) -> ImageArray:
    """The leader dots and dashed rules in a binary ink image, as a mask.

    `menu_0012` joins each dish to its price with a dotted leader, and
    tesseract reads the dots as letters — `oo`, `nnnnnnnn` — and takes the
    price down with them: `goo` for `9.50`, and `Lamb cutlets` not read at
    all. Small marks, one line, four or more, each gap under one glyph.
    """
    cv2 = _cv2()
    count, _, stats, centres = cv2.connectedComponentsWithStats(ink, connectivity=8)
    small = [i for i in range(1, count)
             if stats[i][3] <= LEADER_DOT * glyph and stats[i][2] <= glyph]
    rows: dict[int, list[int]] = {}
    for i in small:
        rows.setdefault(int(centres[i][1] // max(1.0, LEADER_DOT * glyph)), []).append(i)
    out = np.zeros_like(ink)
    for members in rows.values():
        members.sort(key=lambda i: stats[i][0])
        run = [members[0]] if members else []
        for i in members[1:] + [-1]:
            previous = run[-1] if run else None
            if (i != -1 and previous is not None and stats[i][0]
                    - (stats[previous][0] + stats[previous][2]) <= glyph):
                run.append(i)
                continue
            if len(run) >= LEADER_RUN:
                for j in run:
                    x, y, w, h = stats[j][:4]
                    out[y:y + h, x:x + w] = 255
            run = [i] if i != -1 else []
    return out


def _prepared(image: ImageArray, zone: Zone, glyph: float, *,
              inverted: bool = False) -> tuple[ImageArray, float]:
    """The Zone's crop as tesseract is shown it, and the scale it was given.

    `inverted` reads the other polarity: white type on a dark chip inside a
    light Zone — `catalogue_0015`'s SKU badges — is erased with the chip's
    fill as a rule, and only turned over is it type on paper."""
    cv2 = _cv2()
    pixels = zone_pixels(image, zone)
    grey = (cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY) if pixels.ndim == 3
            else pixels).astype(np.uint8)
    threshold, _ = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if (float((grey <= threshold).mean()) > 0.5) != inverted:
        grey = 255 - grey
        threshold = 255 - threshold
    ink = ((grey <= threshold) * 255).astype(np.uint8)
    reach = max(8, int(RULE_GLYPHS * glyph))
    rules = (cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (reach, 1)))
             | cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, reach))))
    rules = cv2.dilate(rules | leaders(ink, glyph), np.ones((3, 3), np.uint8))
    clean = grey.copy()
    clean[rules > 0] = 255
    scale = max(1.0, TARGET_GLYPH / glyph)
    big = cv2.resize(clean, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(big, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT,
                              value=255), scale


def words(image: ImageArray, zone: Zone, *, glyph: float,
          languages: str = "eng", inverted: bool = False,
          marks: bool = False) -> list[Word]:
    """Every word tesseract finds in one Zone, boxes on the page, folded.
    `marks` keeps the tokens that fold to nothing, a `|` or a lone `:`, with
    an empty `text` — spec 0019, B4."""
    assert zone.bbox is not None
    prepared, scale = _prepared(image, zone, glyph, inverted=inverted)
    x0, y0 = crop_origin(image, zone.bbox)
    return _read(image, prepared, scale, (x0, y0), languages=languages,
                 key=int(inverted), marks=marks)


def _read(image: ImageArray, prepared: ImageArray, scale: float, origin: tuple[int, int],
          *, languages: str, key: int, marks: bool) -> list[Word]:
    """tesseract's words in a prepared crop, put back on the page. `key`
    leads each word's `line`, so lines of two reads are never one."""
    cv2 = _cv2()
    height, width = image.shape[:2]
    x0, y0 = origin
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "zone.png"
        cv2.imwrite(str(path), prepared)
        # Through `env`, so the child gets the one variable and this module
        # reads no environment — `config` is the only place that does.
        out = subprocess.run(
            ["env", "OMP_THREAD_LIMIT=1", TESSERACT, str(path), "stdout",
             *FLAGS, "-l", languages, "tsv"],
            capture_output=True, text=True, check=False).stdout
    found = []
    for row in out.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or not cols[11].strip():
            continue
        if not (text := fold(cols[11])) and not marks:
            continue
        left, top, wide, tall = (int(v) for v in cols[6:10])

        def page_x(v: float) -> float:
            return float((x0 + (v - PAD) / scale) / width)

        def page_y(v: float) -> float:
            return float((y0 + (v - PAD) / scale) / height)

        found.append(Word(text, BBox(page_x(left), page_y(top),
                                     page_x(left + wide), page_y(top + tall)),
                          (key, int(cols[2]) * 1000 + int(cols[3]),
                           int(cols[4])), float(cols[10]), cols[11].strip()))
    return found


FILL_SIDE = 1.5
"""The smallest fill type is read off, in body glyphs, both ways — spec
0019, C1: `sample_css_0004`'s `CSS` badge is 2.2 glyphs tall. Narrower
than `furniture.FILL`'s 3, which finds the page's furniture, not a chip."""

FILL_COVER = 0.75
"""How much of its box a fill covers, its holes filled — as
`furniture.FILLED`: a disc pi over four, a rounded chip more."""

FILL_GROUND = 36
"""Channel-sum by which a fill stands off its Zone's ground — as
`furniture.GROUND_SAME`."""


def fills(image: ImageArray, zone: Zone, glyph: float) -> list[BBox]:
    """The solid areas of colour inside a Zone that type may be knocked out
    of — a chip, a pill, a disc: off the ground at the edge of the Zone's
    crop, `FILL_SIDE` glyphs or more both ways once type is opened away,
    covering `FILL_COVER` of their box, their middle inside the Zone.

    The crop runs a glyph past the Zone's box, and its ground is read at
    the crop's edge: `sample_css_0004`'s badge runs past its Zone's right
    edge, and `certificate_0021`'s seal fills 0.79 of its Zone's box, so
    the Zone's commonest colour is the seal's own gold."""
    cv2 = _cv2()
    assert zone.bbox is not None
    height, width = image.shape[:2]
    reach = int(np.ceil(glyph))
    left = max(0, int(zone.bbox.left * width) - reach)
    top = max(0, int(zone.bbox.top * height) - reach)
    right = min(width, int(np.ceil(zone.bbox.right * width)) + reach)
    bottom = min(height, int(np.ceil(zone.bbox.bottom * height)) + reach)
    pixels = image[top:bottom, left:right]
    if pixels.ndim != 3 or pixels.size == 0:
        return []
    edge = np.concatenate([pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]])
    ground = np.array(dominant(edge.reshape(-1, 1, 3)))
    off = (np.abs(pixels.astype(int) - ground).sum(axis=2) > FILL_GROUND).astype(np.uint8)
    size = max(3, int(round(glyph / 2)))
    solid = cv2.morphologyEx(off, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    found = []
    for index in range(1, count):
        x, y, w, h, _ = (int(v) for v in stats[index])
        middle = ((left + x + w / 2) / width, (top + y + h / 2) / height)
        if (w < FILL_SIDE * glyph or h < FILL_SIDE * glyph
                or not (zone.bbox.left <= middle[0] <= zone.bbox.right
                        and zone.bbox.top <= middle[1] <= zone.bbox.bottom)):
            continue
        shape = (labels[y:y + h, x:x + w] == index).astype(np.uint8)
        outline, _ = cv2.findContours(shape, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        whole = np.zeros_like(shape)
        cv2.drawContours(whole, outline, -1, 1, thickness=-1)
        if int(whole.sum()) < FILL_COVER * w * h:
            continue
        found.append(BBox((left + x) / width, (top + y) / height,
                          (left + x + w) / width, (top + y + h) / height))
    return found


def fill_words(image: ImageArray, box: BBox, *, glyph: float,
               languages: str = "eng", key: int = 2) -> list[Word]:
    """The words knocked out of one fill, read on the fill's own crop with
    its type drawn dark on white — spec 0019, C1: each pixel inside the
    fill's outline as dark as it stands off the fill's colour, and every
    pixel outside it white. Turned over whole, `certificate_0021`'s gold
    seal is a grey disc between black corners, and tesseract reads `©`
    off it; drawn so, `GUILD`, `GTE`, `2026`."""
    cv2 = _cv2()
    height, width = image.shape[:2]
    x0, y0 = int(box.left * width), int(box.top * height)
    pixels = image[y0:int(np.ceil(box.bottom * height)), x0:int(np.ceil(box.right * width))]
    if pixels.ndim != 3 or pixels.size == 0:
        return []
    colour = np.array(dominant(pixels))
    apart = np.abs(pixels.astype(int) - colour).sum(axis=2)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (apart <= FILL_GROUND).astype(np.uint8), connectivity=8)
    if count < 2:
        return []
    shape = (labels == 1 + int(np.argmax(stats[1:, 4]))).astype(np.uint8)
    outline, _ = cv2.findContours(shape, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    inside = np.zeros_like(shape)
    cv2.drawContours(inside, outline, -1, 1, thickness=-1)
    if not inside.any():
        return []
    full = max(1.0, float(np.percentile(apart[inside > 0], 99)))
    dark = np.where(inside > 0, np.clip(apart * 255.0 / full, 0, 255), 0)
    grey = (255 - dark).astype(np.uint8)
    scale = max(1.0, TARGET_GLYPH / glyph)
    big = cv2.resize(grey, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    prepared = cv2.copyMakeBorder(big, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=255)
    return _read(image, prepared, scale, (x0, y0), languages=languages,
                 key=key, marks=False)


SYMBOL = re.compile(r"[^\w\s]+")
"""A line of marks only — `★`, `✦`, `•` — which tesseract does not read."""


def _from_marks(image: ImageArray, zone: Zone,
                placed: list[BBox | None]) -> list[BBox | None]:
    """Unplaced lines of marks only, from the glyphs no placed Cell holds,
    in reading order, when the two count alike — spec 0019, C1:
    `certificate_0021`'s three `★` under its title."""
    cells = cells_of(zone)
    wanted = [index for index, ((cell, _), box) in enumerate(zip(cells, placed))
              if box is None and SYMBOL.fullmatch(cell.text.strip() or " ")]
    if not wanted:
        return placed
    cv2 = _cv2()
    assert zone.bbox is not None
    mask = (np.asarray(type_mask(image, zone)) > 0).astype(np.uint8)
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, zone.bbox)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    held = [box for box in placed if box is not None]
    glyphs = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        box = BBox((x0 + x) / width, (y0 + y) / height,
                   (x0 + x + w) / width, (y0 + y + h) / height)
        if area < 4 or any(box.overlap_ratio(other) > 0.5 for other in held):
            continue
        glyphs.append(box)
    if len(glyphs) != len(wanted):
        return placed
    glyphs.sort(key=lambda box: (round((box.top + box.bottom) / 2 * height / 4), box.left))
    out = list(placed)
    for index, box in zip(wanted, glyphs):
        out[index] = box
    return out


def cells_of(zone: Zone) -> list[tuple[Cell, int | None]]:
    """A Zone's Cells in reading order, each with its table row or None;
    then a table cell's second lines, `Cell.below` (spec 0019, B1), each
    with its row; and then the lines its Kind has no place for,
    `Zone.extra`, each with None (spec 0014, step 1). After the body, so a
    body Cell's position in this list is the one `_from_grid` and
    `_from_pairs` count it by; and in it, so they are placed, claim their
    line in `unclaimed`, and are measured by `looks.read` like any other
    Cell — a second pass over a table whose lines `spans.read` joined
    places and measures what the first did."""
    return (_body_of(zone)
            + [(line, index) for index, row in enumerate(zone.rows)
               for cell in row.cells for line in cell.below]
            + [(cell, None) for block in zone.extra for cell in block.lines])


def superscript(character: str) -> bool:
    """A superscript digit or sign, `¹` or `⁺` — not a letter: `™` and `ª`
    are drawn raised already, and are words."""
    decomposition = unicodedata.decomposition(character)
    if not decomposition.startswith("<super>"):
        return False
    base = chr(int(decomposition.split()[1], 16))
    return not base.isalpha()


def _built(zone: Zone) -> set[int]:
    """Every Cell of a table `spans.read` built, by id — spec 0019, B1: one
    whose lines it joined or whose cells it spans. Placed on the model's
    rows, each box is the grid's; placed again on the joined rows, the
    repeated subjects of `timetable_0019` find other rows. So once built,
    the table keeps its boxes and its readings whole.

    **Built means boxed** — spec 0024, C. Arm D2's tables come from the
    parser's HTML with their spans and second lines and no box at all,
    and taken for built they were never placed: on the dev pages, 3662
    of their 3746 Cells unplaced, against 77 of 3133 in the other
    tables. `spans.read` boxes every Cell it builds."""
    cells = [c for row in zone.rows for cell in row.cells for c in (cell, *cell.below)]
    if not any(cell.span is not None or cell.below for row in zone.rows
               for cell in row.cells):
        return set()
    if all(c.bbox is None for c in cells):
        return set()
    return {id(c) for c in cells}


def unraised(cell: Cell) -> str:
    """A Cell's text without its raised marks — spec 0019, B2's `sup` Runs
    and the superscripts they hold: tesseract reads a mark apart from its
    line, or as `°` or `’`, and a Cell is matched to its words, and its
    readings compared, by its words alone. `report_0011`'s `2027.³` is
    read `2027.°`, `paper_0018`'s `Solberg¹` `Solberg'`. The same before
    `raised.read` has made the marks Runs as after."""
    text = "".join(run.text for run in cell.runs if run.kind != "sup")
    return "".join(c for c in text if not superscript(c))


WORD_BREAK = re.compile(r"[\s/·,]+")
"""Where a Cell's text parts into the words tesseract would read apart:
spaces, and the separators the corpus sets between words without them."""


def whole_words(text: str) -> list[str]:
    """A text's words, each folded — spec 0015, step 1. Whole words, because
    by letters alone `OSL` is inside `OSLO GARDERMOEN`."""
    return [word for part in WORD_BREAK.split(text) if (word := fold(part))]


def _run_of(wanted: list[str], words_: list[str]) -> bool:
    return any(words_[start:start + len(wanted)] == wanted
               for start in range(len(words_) - len(wanted) + 1))


def _alike(wanted: str, text: str) -> bool:
    """Whether `wanted` is, at `MIN_SIMILARITY`, the whole of `text` or a
    stretch of it as long as itself — folded, character by character."""
    if len(wanted) >= len(text):
        return SequenceMatcher(None, wanted, text, autojunk=False).ratio() >= MIN_SIMILARITY
    return any(SequenceMatcher(None, wanted, text[start:start + len(wanted)],
                               autojunk=False).ratio() >= MIN_SIMILARITY
               for start in range(len(text) - len(wanted) + 1))


def holds(zone: Zone, text: str) -> bool:
    """Whether the Zone already prints `text` — the guard that keeps a line
    read again from printing a word twice. An empty text is held.

    **Word for word** inside its Title, inside any one of its Cells, or
    inside one Block, row or pair read together — spec 0014, step 2, by
    whole words since spec 0015, step 1.

    **Or alike to a text that has no place on the page** — an unplaced
    Cell, or the Title, which is never placed — spec 0015, step 1. A line
    nobody claims in a Zone that holds such a text may be that text,
    misread: tesseract reads `catalogue_0015`'s display-size `£22.40` as
    `99` and `darkdeck_0009`'s `$2.14` as `914`, flags them, and the line is
    read again. Measured over the twenty-one at `s10-result/`: each of the
    seven misread lines sits in a Zone with one unplaced Cell or a Title,
    and none of the five lines the reading lost does, but for the ticket's
    `OSL`, whose Zone's unplaced `NL 0482` is nothing like it. Alike to
    *any* Cell would refuse `OSL` itself: it reads 0.86 alike to the `OSLO`
    of `OSLO GARDERMOEN`, which is placed — printed elsewhere, so not
    this line."""
    wanted = whole_words(text)
    if not wanted:
        return True
    entries = [zone.title or ""] + [cell.text for cell, _ in cells_of(zone)]
    entries += [" ".join(cell.text for cell in block.lines)
                for block in zone.blocks + zone.extra]
    entries += [" ".join(cell.text for cell in row.cells) for row in zone.rows]
    entries += [f"{pair.label.text} {pair.value.text}" for pair in zone.pairs]
    if any(_run_of(wanted, whole_words(entry)) for entry in entries):
        return True
    placeless = [zone.title or ""] + [cell.text for cell, _ in cells_of(zone)
                                      if cell.bbox is None]
    folded = "".join(wanted)
    return any(_alike(folded, fold(entry)) for entry in placeless if fold(entry))


def _body_of(zone: Zone) -> list[tuple[Cell, int | None]]:
    if zone.kind is Kind.TABLE:
        return [(cell, index) for index, row in enumerate(zone.rows)
                for cell in row.cells]
    if zone.kind is Kind.PAIRS:
        return [(cell, None) for pair in zone.pairs
                for cell in (pair.label, pair.value)]
    return [(cell, None) for block in zone.blocks for cell in block.lines]


WRAP_RUNS = 3
"""Across a line break, how many runs from each first word are compared:
those whose length is nearest the Cell's. Every run on one line is."""


def _runs(found: Sequence[Word], length: int) -> Iterator[tuple[int, int, str]]:
    """Runs of consecutive words, in tesseract's reading order: first, last,
    joined. Every run on the first word's line, and — because a Cell wraps,
    `report_0011`'s paragraphs over two lines and `newsletter_0008`'s over
    five — the `WRAP_RUNS` runs onto later lines nearest the Cell's length.
    A run never crosses from one polarity's read into the other's."""
    longest = int(length * 1.5) + 3
    for first in range(len(found)):
        joined = ""
        wrapped: list[tuple[int, int, str]] = []
        for last in range(first, len(found)):
            if found[last].line[0] != found[first].line[0]:
                break
            joined += found[last].text
            if found[last].line == found[first].line:
                yield first, last, joined
            else:
                wrapped.append((first, last, joined))
            if len(joined) > longest:
                break
        wrapped.sort(key=lambda run: abs(len(run[2]) - length))
        yield from wrapped[:WRAP_RUNS]


def _candidates(target: str, found: Sequence[Word]) -> list[tuple[float, int, int]]:
    """(similarity, first, last) for every run that could be this Cell."""
    digits = _digits(target)
    out = []
    for first, last, joined in _runs(found, len(target)):
        if abs(len(joined) - len(target)) > max(2, 0.4 * len(target)):
            continue
        if digits and _digits(joined) != digits:
            continue
        score = SequenceMatcher(None, target, joined, autojunk=False).ratio()
        if score >= MIN_SIMILARITY:
            out.append((score, first, last))
    return sorted(out, key=lambda c: (-c[0], c[1]))


def _union(found: Sequence[Word], first: int, last: int) -> BBox:
    boxes = [word.box for word in found[first:last + 1]]
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def place(zone: Zone, found: Sequence[Word],
          runs: list[tuple[int, int] | None] | None = None) -> list[BBox | None]:
    """Each of the Zone's Cells' boxes, in `cells_of` order, or None. Given
    `runs`, each placed Cell's run of `found` — first and last — is put in
    it: the words that placed it, its second reading (spec 0019, D1).

    A Cell whose text no other Cell in the Zone shares, with one best place,
    takes it — best match first. The rest go in reading order, by position:
    a table cell the equally good run nearest its row's height, within the
    row's own height of it; any other Cell the first one between the Cells
    placed before and after it. A place outside those bounds is refused and
    the Cell left unplaced: `nonlatin_0014` prints `Καθαρή αξία` in its
    white header, which tesseract does not read, and in a total below,
    which it does, and the header must not take the total's. A word is
    claimed once.
    """
    cells = cells_of(zone)
    folded = [fold(unraised(cell)) for cell, _ in cells]
    repeated = {text for text in folded if text and folded.count(text) > 1}
    # The Cells `spans.read` built keep the boxes it gave them — spec 0019,
    # B1: a second pass over a joined grid draws what the first did.
    built = _built(zone)
    options = [_candidates(text, found) if text and id(cell) not in built else []
               for text, (cell, _) in zip(folded, cells)]
    used: set[int] = set()
    placed: list[BBox | None] = [cell.bbox if id(cell) in built else None
                                 for cell, _ in cells]

    def free(first: int, last: int) -> bool:
        return not any(i in used for i in range(first, last + 1))

    def tied(index: int) -> list[tuple[int, int]]:
        # The runs as good as the best, one per place: a run overlapping a
        # better one is that place read with a word more or less, not a
        # second place — `This review covers` and `scope This review
        # covers` are one paragraph, not two.
        best = options[index][0][0]
        out: list[tuple[int, int]] = []
        for score, first, last in options[index]:
            if score >= best - TIE and free(first, last) and all(
                    last < f or first > l for f, l in out):
                out.append((first, last))
        return out

    def take(index: int, first: int, last: int) -> None:
        used.update(range(first, last + 1))
        placed[index] = _union(found, first, last)
        if runs is not None:
            runs[index] = (first, last)

    deferred = []
    for index in sorted(range(len(cells)),
                        key=lambda i: (-(options[i][0][0] if options[i] else 0), i)):
        if not options[index]:
            continue
        places = tied(index)
        if len(places) == 1 and folded[index] not in repeated:
            take(index, *places[0])
        elif places:
            deferred.append(index)

    def middle(box: BBox) -> float:
        return (box.top + box.bottom) / 2

    def tall(box: BBox) -> float:
        return box.bottom - box.top

    for index in sorted(deferred):
        places = tied(index)
        if not places:
            continue
        row = cells[index][1]
        level = [b for (_, r), b in zip(cells, placed)
                 if row is not None and r == row and b is not None]
        if level:
            height = float(np.median([middle(b) for b in level]))
            reach = max(tall(b) for b in level)
            near = [c for c in places
                    if abs(middle(_union(found, *c)) - height) <= reach]
            if not near:
                continue
            choice = min(near, key=lambda c: abs(middle(_union(found, *c)) - height))
        else:
            if row is not None:
                before = [b for (_, r), b in zip(cells, placed) if r is not None
                          and r < row and b is not None]
                after = [b for (_, r), b in zip(cells, placed) if r is not None
                         and r > row and b is not None]
            else:
                before = [b for b in placed[:index] if b is not None]
                after = [b for b in placed[index + 1:] if b is not None]
            floor = middle(before[-1]) - tall(before[-1]) if before else -1.0
            ceiling = middle(after[0]) + tall(after[0]) if after else 2.0
            between = [c for c in places
                       if floor <= middle(_union(found, *c)) <= ceiling]
            if not between:
                continue
            choice = min(between, key=lambda c: c[0])
        take(index, *choice)
    return placed


def _from_grid(image: ImageArray, zone: Zone,
               placed: list[BBox | None]) -> list[BBox | None]:
    """An unplaced table cell, from the ink where its row and its column
    cross: the row's height from its placed cells, the column's width from
    the same column's placed cells in other rows. `menu_0012`'s prices whose
    words came back wrong, and a cell tesseract merged with its neighbour."""
    if zone.kind is not Kind.TABLE or None not in placed:
        return placed
    assert zone.bbox is not None
    cells = _body_of(zone)
    where = [(index, column) for index, line in enumerate(zone.rows)
             for column in range(len(line.cells))]
    mask = np.asarray(type_mask(image, zone)) > 0
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, zone.bbox)
    out = list(placed)
    for index, ((cell, _), (row, column)) in enumerate(zip(cells, where)):
        if out[index] is not None or not cell.text.strip():
            continue
        across = [b for (r, _), b in zip(where, placed) if r == row and b]
        down = [b for (_, c), b in zip(where, placed) if c == column and b]
        if not across or not down:
            continue
        top = int(min(b.top for b in across) * height) - y0
        bottom = int(np.ceil(max(b.bottom for b in across) * height)) - y0
        left = int(min(b.left for b in down) * width) - x0
        right = int(np.ceil(max(b.right for b in down) * width)) - x0
        patch = mask[max(0, top):max(0, bottom), max(0, left):max(0, right)]
        rows_, cols_ = np.where(patch)
        if not len(rows_):
            continue
        out[index] = BBox((x0 + max(0, left) + cols_.min()) / width,
                          (y0 + max(0, top) + rows_.min()) / height,
                          (x0 + max(0, left) + cols_.max() + 1) / width,
                          (y0 + max(0, top) + rows_.max() + 1) / height)
    return out


def _from_pairs(image: ImageArray, zone: Zone,
                placed: list[BBox | None]) -> list[BBox | None]:
    """An unplaced label or value of a pairs Zone whose partner is placed,
    from the ink on the partner's line on the other side of it — only where
    the Zone's placed pairs mostly set the value beside its label on one
    line. `nonlatin_0014`'s IBAN, whose `0`s tesseract reads as `O`, and the
    `ΔΟΥ` it reads not at all. A form sets its value under the label, and
    takes nothing from here."""
    if zone.kind is not Kind.PAIRS or None not in placed:
        return placed
    assert zone.bbox is not None
    # The pairs only: `Zone.extra`'s lines come after them and have no partner.
    body = len(_body_of(zone))
    both = [(label, value) for label, value in zip(placed[0:body:2], placed[1:body:2])
            if label is not None and value is not None]
    beside = sum(1 for label, value in both
                 if label.right <= value.left
                 and min(label.bottom, value.bottom) > max(label.top, value.top))
    if not both or 2 * beside <= len(both):
        return placed
    mask = np.asarray(type_mask(image, zone)) > 0
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, zone.bbox)
    # A label ends where the values' column starts, not where its own value
    # was read from: tesseract reads `Πειραιά` and not the `Α΄` before it.
    column = float(np.median([value.left for _, value in both]))
    out = list(placed)
    for index, (cell, _) in enumerate(_body_of(zone)):
        partner = placed[index ^ 1]
        if out[index] is not None or partner is None or not cell.text.strip():
            continue
        top = max(0, int(partner.top * height) - y0)
        bottom = max(0, int(np.ceil(partner.bottom * height)) - y0)
        if index % 2:
            left, right = int(np.ceil(partner.right * width)) - x0, mask.shape[1]
        else:
            left, right = 0, int(min(partner.left, column) * width) - x0
        patch = mask[top:bottom, max(0, left):max(0, right)]
        rows_, cols_ = np.where(patch)
        if not len(rows_):
            continue
        out[index] = BBox((x0 + max(0, left) + cols_.min()) / width,
                          (y0 + top + rows_.min()) / height,
                          (x0 + max(0, left) + cols_.max() + 1) / width,
                          (y0 + top + rows_.max() + 1) / height)
    return out


def _between(lines: list[tuple[int, int]], placed: list[BBox | None],
             y0: int, height: int) -> list[tuple[int, tuple[int, int]]]:
    """Each run of unplaced Cells beside the printed lines lying between the
    placed Cells either side of it, where the two count alike — spec 0012,
    G8. `paper_0018`'s title is set on two lines and held as one Cell, so
    the Zone counts one line more than it has Cells, and its author and
    affiliation lines, which tesseract misreads, sit between a placed
    heading and a placed e-mail line: three lines, three Cells."""
    out: list[tuple[int, tuple[int, int]]] = []
    index = 0
    while index < len(placed):
        if placed[index] is not None:
            index += 1
            continue
        end = index
        while end < len(placed) and placed[end] is None:
            end += 1
        before, after = placed[index - 1] if index else None, \
            placed[end] if end < len(placed) else None
        floor = before.bottom if before else -1.0
        ceiling = after.top if after else 2.0
        inside = [line for line in lines
                  if floor < (y0 + (line[0] + line[1]) / 2) / height < ceiling]
        if len(inside) > end - index:
            inside = _touching(inside)
        if len(inside) == end - index:
            out.extend(zip(range(index, end), inside))
        index = end
    return out


def without_cut_copies(document: Document) -> list[tuple[int, str]]:
    """Drop each line of a Block placed on another Zone's line whose text it
    starts — a cut-off copy of words that Zone prints whole — and say which,
    as (Zone, text). Spec 0013, step 3d.

    `pricing_0017`'s toggle read a third item, `Sav`, placed at 0.499 —
    outside its own Zone (0.341–0.488) and on the first letters of the Zone
    beside it, `Save 20% with annual billing`. Its words are all printed by
    that Zone, so dropping it can lose none. Measured over the twenty-one
    at `S9-3c`, it is the only Cell lying on another Zone's line that it
    starts. A line placed in its own Zone, or not starting the one it lies
    on, stays."""
    dropped: list[tuple[int, str]] = []
    for index, zone in enumerate(document.zones):
        if zone.bbox is None:
            continue
        for block in zone.blocks:
            kept = []
            for line in block.lines:
                if _cut_copy(line, zone, index, document):
                    dropped.append((index, line.text))
                else:
                    kept.append(line)
            block.lines = kept
        zone.blocks = [block for block in zone.blocks if block.lines]
    return dropped


def _cut_copy(line: Cell, zone: Zone, index: int, document: Document) -> bool:
    folded = fold(line.text)
    if line.bbox is None or not folded or zone.bbox is None:
        return False
    x = (line.bbox.left + line.bbox.right) / 2
    y = (line.bbox.top + line.bbox.bottom) / 2

    def holds(box: BBox | None) -> bool:
        return box is not None and box.left <= x <= box.right and box.top <= y <= box.bottom

    if holds(zone.bbox):
        return False
    return any(holds(other.bbox) and holds(cell.bbox) and fold(cell.text).startswith(folded)
               and fold(cell.text) != folded
               for number, other in enumerate(document.zones) if number != index
               for cell, _ in cells_of(other))


def _touching(lines: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Printed lines with no blank row between them, as one — spec 0013,
    step 3c. `type_lines` parts touching lines at the valleys of their ink,
    and a line set in two sizes has valleys of its own: `pricing_0017`'s
    `£12 / user / month` came out three lines for one Cell, and was never
    placed. Measured over every prose and list Zone of the twenty-one at
    `S9-3b`, the next nearest two lines stand is three blank rows."""
    out: list[tuple[int, int]] = []
    for top, bottom in lines:
        if out and top <= out[-1][1] + 1:
            out[-1] = (out[-1][0], bottom)
        else:
            out.append((top, bottom))
    return out


def _from_ink(image: ImageArray, zone: Zone,
              placed: list[BBox | None]) -> list[BBox | None]:
    """Unplaced lines of a prose or list Zone, from its printed lines, when
    the two count alike — over the Zone, or else between the placed Cells
    either side (`_between`)."""
    if zone.kind not in (Kind.PROSE, Kind.LIST) or None not in placed:
        return placed
    assert zone.bbox is not None
    mask = np.asarray(type_mask(image, zone)) > 0
    lines = type_lines(mask)
    if zone.title:
        lines = lines[1:]
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, zone.bbox)
    # The Blocks' lines only, which are in the order the page prints them;
    # `Zone.extra`'s come after them, wherever they are printed, and are
    # placed by their words.
    own = placed[:len(_body_of(zone))]
    pairs = (list(enumerate(lines)) if len(lines) == len(own)
             else _between(lines, own, y0, height))
    out = list(placed)
    for index, (top, bottom) in pairs:
        if out[index] is not None:
            continue
        columns = np.where(mask[top:bottom + 1].any(axis=0))[0]
        if len(columns):
            out[index] = BBox((x0 + columns.min()) / width, (y0 + top) / height,
                              (x0 + columns.max() + 1) / width,
                              (y0 + bottom + 1) / height)
    return out


def _from_lines(zone: Zone, found: Sequence[Word],
                placed: list[BBox | None]) -> list[BBox | None]:
    """An unplaced line of the Zone's `extra` on the printed line it claims
    — spec 0015, 2d. A line in `extra` was read again from a printed line
    no Cell claimed (`unclaimed`), and it claims that line back by the same
    test, `_claims`: of the line's confident words no placed Cell covers,
    half the words and half their letters are its own. Its words may still
    not match it run for run: tesseract reads the ticket's `Gate closes 20
    minutes before` as `gate user minutes before`, and its digits do not
    agree; and `OSL` is read only by `display_words`. Each line is
    claimed once, in reading order.

    **The box is the whole printed line** — spec 0016, 4c: the confident
    words decide which line a Cell claims, and every word of that line not
    already taken is its box. With the ticket's halo Zone taken out and its
    body measured at 9.0px, tesseract reads the gate note's first line as
    `gre` 5, `90` 39, `141` 0, `4` 0, `before` 95; boxed by `before` alone,
    the note was drawn one word to a line.

    **A line no words claim is printed where it was read from** — spec
    0018, A1, `Block.read_from`: the model read it off that line's crop.
    With the halo Zone gone, tesseract reads the gate note's first line as
    `gre`, `sc`, `before`; `before` alone claims nothing, and the line was
    drawn after `departure`, the line below it. One line to a Block only:
    the lines of a Block read from one crop do not each stand where all of
    them were read."""
    body = len(_body_of(zone))
    if None not in placed[body:]:
        return placed
    taken = [box for box in placed if box is not None]
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for word in found:
        if (word.confidence >= CONFIDENT and len(word.text) >= 2
                and not _covered(word, taken)):
            lines.setdefault(word.line, []).append(word)
    out = list(placed)
    for index, (cell, _) in enumerate(cells_of(zone)):
        if index < body or out[index] is not None or not cell.text.strip():
            continue
        mine = set(whole_words(cell.text))
        key = next((key for key, words_ in lines.items() if _claims(mine, words_)), None)
        if key is not None:
            lines.pop(key)
            whole = [word for word in found if word.line == key and not _covered(word, taken)]
            out[index] = _union(whole, 0, len(whole) - 1)
    # Spec 0018, A1: a line no words claim is printed where it was read from.
    at = len(out) - sum(len(block.lines) for block in zone.extra)
    for block in zone.extra:
        if (block.read_from is not None and len(block.lines) == 1
                and out[at] is None and block.lines[0].text.strip()):
            out[at] = block.read_from
        at += len(block.lines)
    return out


CONFIDENT = 60.0
"""tesseract's confidence, 0 to 100, at or above which an unclaimed word
counts. Measured 2026-10-13 over all twenty-one at `S8-8-echo`, as the mean
over a line's letters: the lines nothing reads — `timetable_0019`'s lost
rows and the form's `Tick one` — stand at 65-97; what tesseract makes of a
QR code, a hatch or letter-spaced capitals, at 0-48."""

UNCLAIMED_WORDS = 1
"""How many confident words of two letters or more make a line. Two until
spec 0015, step 1, because one word alone is how a misread Title
(`puppincs` for `Puddings`) looks. But a line the reading lost can be one
word: `sample_semantic_0005`'s `Tags:`, `timetable_0019`'s `Lunch`, the
second line of the ticket's gate note. Measured over the twenty-one at
`s10-result/`: seven one-word lines, those three and four misreads of Cells
with no place, which `holds` refuses once they are read."""

TURNED_WORDS = 2
"""The same, for a line of the turned-over read (`Word.line[0]` 1), which
keeps two. Turned over, a light Zone's paper reads as junk: replayed over
the twenty-one at `s10-result/`, it raised four one-word lines, `bae`, `ον`,
`bb` and `ag`, and nothing else — as reading the other polarity on every
Zone raised seventeen lines, sixteen of them junk (spec 0015, §2)."""


def _covered(word: Word, boxes: Sequence[BBox]) -> bool:
    """Whether the word's centre lies in a placed Cell's box, give or take
    `SLACK`."""
    x = (word.box.left + word.box.right) / 2
    y = (word.box.top + word.box.bottom) / 2
    return any(box.left - SLACK <= x <= box.right + SLACK
               and box.top - SLACK <= y <= box.bottom + SLACK for box in boxes)


SLACK = 0.003
"""A page fraction: a word's centre this far outside a Cell's box is still in
it, for a box placed from the ink rather than from the words."""


def _claims(text: set[str], words_: Sequence[Word]) -> bool:
    """Whether one Cell's or Title's words, `text`, spell at least half of a
    line's distinct words **and** half their letters — whole words (spec
    0015, step 1).

    Word by word, because a word tesseract is unsure of is left out of the
    line: `nonlatin_0014`'s `Ανάλυση παρεχόμενων υπηρεσιών` keeps its first
    and last word and is still its table's Title. Distinct, because the
    timetable's lost `12:20 Art English PE English` is not the Cell
    `English` twice over. **Whole words**, because by letters `osl` is
    inside `oslogardermoen`, and the ticket's `OSL` was claimed by the line
    under it. **Half the letters**, because a short word is a small claim:
    the ticket's `gate before` was claimed by the Cell `GATE`, one word of
    two and four letters of ten. **And half the words**, because one long
    word is not a line either: by letters alone `timetable_0019`'s legend,
    `Mathematics Science PE`, is claimed by the Cell `Mathematics`, eleven
    letters of twenty, and is never read."""
    distinct = {word.text for word in words_}
    spelt = {word for word in distinct if word in text}
    return (2 * len(spelt) >= len(distinct)
            and 2 * sum(len(word) for word in spelt) >= sum(len(word) for word in distinct))


def unclaimed(zone: Zone, found: Sequence[Word],
              boxes: Sequence[BBox]) -> list[tuple[BBox, int, BBox]]:
    """The lines of a Zone's words no Cell claims: each line's box, how many
    words it holds, and the box it is read again from — spec 0012, G9.

    A word counts when tesseract is `CONFIDENT` of it and it has two letters
    or more, and it is claimed when it lies in any placed Cell's box on the
    page. A line of `UNCLAIMED_WORDS` or more unclaimed words is still
    claimed when one of the Zone's Cells, or its Title, spells half its
    words and half their letters (`_claims`): a Cell placed on the wrong ink, or one placed
    nowhere, still has its line read. One text at a time and never the
    Zone's words pooled, because the rows the timetable lost hold `Science`
    and `English` too, each a Cell of a row it read.

    **The box it is read from** is the line's padded as every crop is
    (`preprocess.PAD_X`, `PAD_Y`), but stopping halfway into the gap before
    any word of the same line a Cell claims — spec 0015, step 1. Padded
    whole, a line partly claimed brings its claimed words into the crop and
    the reading repeats them: `Tags:` beside its list's `HTML`, the
    timetable's `Lunch` beside `13:20`. A line with no claimed word near it
    is read from exactly the crop it was before.

    **Its box is its confident words, not all of its line's** — spec 0016,
    step 4, measured and dropped. Boxed by every unclaimed word on it, the
    ticket's gate note was read whole where tesseract was sure of one word,
    but `timetable_0019`'s legend, two overlapping lines, was read whole
    twice, and printed twice."""
    texts = [words_ for words_ in [set(whole_words(zone.title or ""))]
             + [set(whole_words(cell.text)) for cell, _ in cells_of(zone)] if words_]
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for word in found:
        if (word.confidence >= CONFIDENT and len(word.text) >= 2
                and not _covered(word, boxes)):
            lines.setdefault(word.line, []).append(word)
    out = []
    for key, words_ in lines.items():
        least = TURNED_WORDS if key[0] == 1 else UNCLAIMED_WORDS
        if len(words_) < least or any(_claims(text, words_) for text in texts):
            continue
        box = _union(words_, 0, len(words_) - 1)
        claimed = [word.box for word in found
                   if word.line == key and _covered(word, boxes)]
        left = max([box.left - PAD_X] + [(other.right + box.left) / 2
                                         for other in claimed if other.right <= box.left])
        right = min([box.right + PAD_X] + [(other.left + box.right) / 2
                                           for other in claimed if other.left >= box.right])
        out.append((box, len(words_), BBox(left, box.top, right, box.bottom)))
    return out


DISPLAY_GLYPH = TARGET_GLYPH
"""The glyph height, in page pixels, `display_words` reads a Zone as if its
body type were: shown at the page's own scale, and with only straight
strokes longer than `RULE_GLYPHS` of these erased."""


def display_words(image: ImageArray, zone: Zone, first: Sequence[Word], *,
                  languages: str = "eng") -> list[Word]:
    """The Zone's words read a second time, for type the first read erased —
    only where the first read found no word it was `CONFIDENT` of. Spec
    0015, step 1.

    The first read erases every straight stroke longer than `RULE_GLYPHS`
    body glyphs as a rule, and a display letter's stem is longer than that:
    on `ticket_0020`, whose body glyph is 8px, `OSL` is erased down to
    scraps tesseract reads as `ry` and `it` at confidence 0-38. Read at
    the page's own scale with only strokes over 2 × `DISPLAY_GLYPH` pixels
    erased, it is `osl` at 96 — and erasing less on the upscaled crop finds
    it too, so it is the erasing and not the scale. Unrestricted, the second
    read also raises eleven fragments of headings the first read had; kept
    only where the first found nothing confident, it raises `OSL` alone over
    the twenty-one at `s10-result/`. Its words sit on lines of their own
    (`Word.line[0]` 2), so no line joins the two reads.

    **A one-character word blocks nothing** — spec 0016, 4b. With the
    ticket's halo Zone taken out the first read finds a `5` at 93 over
    `OSL`, and `OSL` was lost; a confident first-read word blocks the
    display read only if it is two characters or more."""
    sure = [word.box for word in first if word.confidence >= CONFIDENT and len(word.text) >= 2]
    return [replace(word, line=(2,) + word.line[1:])
            for word in words(image, zone, glyph=DISPLAY_GLYPH, languages=languages)
            if not any(word.box.overlap_ratio(box) > 0 for box in sure)]


SECOND = "tesseract"
"""The engine of a Cell's second reading — spec 0019, D1."""


def _second(cell: Cell, run: Sequence[Word]) -> None:
    """Keep the words that placed a Cell as its second Reading — spec 0019,
    D1: the run of tesseract's words `place` matched it to, raw, as
    tesseract printed them. `locate` reads them to place the Cell and until
    spec 0019 threw them away. No text changes: every reader takes the
    first Reading. A Cell a third reading settled (`RESOLVED`, `DISPUTED`)
    or a human ruled on keeps the readings it has."""
    if cell.state is not CellState.AGREED or not cell.readings:
        return
    text = " ".join(word.raw for word in run if word.raw)
    if text:
        cell.readings.append(Reading(engine=SECOND, text=text))


def _inside(box: BBox, found: Sequence[Word]) -> list[Word]:
    """The words tesseract is sure of inside a box no run placed — a grid's
    cell, a box drawn from the ink — in reading order: `statement_0006`'s
    `216.08`, which no run matches since its digits are not the model's
    `210.08`. Its unsure words there are the texture and rules of the page,
    `&ta` beside the figure."""
    return sorted(
        (word for word in found if word.confidence >= CONFIDENT
         and box.left <= (word.box.left + word.box.right) / 2 <= box.right
         and box.top <= (word.box.top + word.box.bottom) / 2 <= box.bottom),
        key=lambda word: (word.line, word.box.left))


def _without_second(cell: Cell) -> None:
    """A Cell's second reading taken off before it is placed again, so a
    later round or a rederive keeps one, of the words now in its box."""
    if cell.state is CellState.AGREED and len(cell.readings) > 1:
        cell.readings[1:] = [r for r in cell.readings[1:] if r.engine != SECOND]


def locate(image: ImageArray, document: Document) -> tuple[int, int]:
    """Set `Cell.bbox` on every Cell that can be placed — and None on every
    one that cannot, so a later round keeps no stale box. Returns (placed,
    cells). `image` is `Rectified.plain`."""
    # A mark — a badge, a stamp, a signature — is a figure whose text is
    # printed type: spec 0019, C1, `certificate_0021`'s seal.
    zones = [z for z in document.zones
             if z.bbox is not None and z.complete
             and (z.kind is not Kind.FIGURE or z.graphic_kind in MARKS)]
    built = {key for zone in document.zones for key in _built(zone)}
    for zone in document.zones:
        for cell, _ in cells_of(zone):
            if id(cell) in built:
                continue
            cell.bbox = None
            _without_second(cell)
    document.unclaimed = []
    glyph = body_glyph(image, document.zones)
    if not zones or not glyph or not available():
        return 0, sum(1 for z in document.zones for cell, _ in cells_of(z)
                      if cell.text.strip())

    def language(zone: Zone) -> str:
        greek = any(GREEK.search(cell.text) for cell, _ in cells_of(zone))
        return "ell+eng" if greek else "eng"

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        read = list(pool.map(
            lambda z: words(image, z, glyph=glyph, languages=language(z)), zones))
        # The other polarity, only where the first read left a Cell unplaced.
        short = [i for i, (z, found) in enumerate(zip(zones, read))
                 if any(box is None and fold(cell.text) for (cell, _), box
                        in zip(cells_of(z), place(z, found)))]
        again = list(pool.map(
            lambda i: words(image, zones[i], glyph=glyph,
                            languages=language(zones[i]), inverted=True), short))
    # Turned over, tesseract still reads some of the first polarity's type:
    # `statement_0006`'s one `BAC` came back twice and two Cells took it. The
    # same word in the same place is one word.
    for i, more in zip(short, again):
        first = read[i]
        read[i] = first + [extra for extra in more if not any(
            extra.text == seen.text and extra.box.overlap_ratio(seen.box) > 0.5
            for seen in first)]
    # Type knocked out of a fill inside the Zone, read on the fill's own
    # crop turned over, where a Cell is still unplaced — spec 0019, C1.
    # Kept apart from the Zone's words: they place Cells, and claim no line
    # for `unclaimed`, which would ask the model for it.
    filled: list[list[Word]] = [[] for _ in zones]
    for i, (zone, found) in enumerate(zip(zones, read)):
        if not any(box is None and fold(cell.text) for (cell, _), box
                   in zip(cells_of(zone), place(zone, found))):
            continue
        for n, fill in enumerate(fills(image, zone, glyph)):
            more = fill_words(image, fill, glyph=glyph, languages=language(zone), key=2 + n)
            filled[i] += [extra for extra in more if not any(
                extra.text == seen.text and extra.box.overlap_ratio(seen.box) > 0.5
                for seen in read[i] + filled[i])]
    # Display type the first read erased as rules: for the unclaimed lines,
    # and for the extra lines read from them (`_from_lines`) — never to place
    # a Cell of the body.
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        display = list(pool.map(
            lambda pair: display_words(image, pair[0], pair[1],
                                       languages=language(pair[0])), zip(zones, read)))
    placed = total = 0
    for zone, found, more, chips in zip(zones, read, display, filled):
        words_ = list(found) + chips
        runs: list[tuple[int, int] | None] = [None] * len(cells_of(zone))
        boxes = place(zone, words_, runs)
        for fallback in (_from_grid, _from_pairs, _from_ink, _from_marks):
            boxes = fallback(image, zone, boxes)
        boxes = _from_lines(zone, list(found) + more, boxes)
        for (cell, _), box, run in zip(cells_of(zone), boxes, runs):
            cell.bbox = box
            placed += box is not None
            total += bool(cell.text.strip())
            if box is not None and id(cell) not in built:
                _second(cell, words_[run[0]:run[1] + 1] if run is not None
                        else _inside(box, words_))
    located = [cell.bbox for zone in document.zones for cell, _ in cells_of(zone)
               if cell.bbox is not None]
    ink = content_ink(image) > 0
    height, width = ink.shape[:2]
    index_of = {id(zone): index for index, zone in enumerate(document.zones)}
    whole = float(ink.sum()) or 1.0
    for zone, found, more in zip(zones, read, display):
        if zone.kind is Kind.FIGURE:
            # A mark's type is its own; it claims no line for another Zone.
            continue
        for box, count, reach in unclaimed(zone, list(found) + more, located):
            inside = ink[int(box.top * height):int(np.ceil(box.bottom * height)),
                         int(box.left * width):int(np.ceil(box.right * width))]
            document.unclaimed.append(Unclaimed(
                zone_index=index_of[id(zone)], bbox=box, words=count,
                ink_share=round(float(inside.sum()) / whole, 4), reach=reach))
    document.unclaimed.sort(key=lambda u: (u.zone_index, u.bbox.top))
    return placed, total
