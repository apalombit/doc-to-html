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
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np

from .ir import BBox, Cell, Document, Kind, Zone
from .preprocess import ImageArray, _cv2, crop_origin, zone_pixels
from .style import body_glyph, type_lines, type_mask

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
          languages: str = "eng", inverted: bool = False) -> list[Word]:
    """Every word tesseract finds in one Zone, boxes on the page, folded."""
    assert zone.bbox is not None
    cv2 = _cv2()
    prepared, scale = _prepared(image, zone, glyph, inverted=inverted)
    height, width = image.shape[:2]
    x0, y0 = crop_origin(image, zone.bbox)
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
        if len(cols) < 12 or not (text := fold(cols[11])):
            continue
        left, top, wide, tall = (int(v) for v in cols[6:10])

        def page_x(v: float) -> float:
            return float((x0 + (v - PAD) / scale) / width)

        def page_y(v: float) -> float:
            return float((y0 + (v - PAD) / scale) / height)

        found.append(Word(text, BBox(page_x(left), page_y(top),
                                     page_x(left + wide), page_y(top + tall)),
                          (int(inverted), int(cols[2]) * 1000 + int(cols[3]),
                           int(cols[4]))))
    return found


def cells_of(zone: Zone) -> list[tuple[Cell, int | None]]:
    """A Zone's Cells in reading order, each with its table row or None."""
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


def place(zone: Zone, found: Sequence[Word]) -> list[BBox | None]:
    """Each of the Zone's Cells' boxes, in `cells_of` order, or None.

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
    folded = [fold(cell.text) for cell, _ in cells]
    repeated = {text for text in folded if text and folded.count(text) > 1}
    options = [_candidates(text, found) if text else [] for text in folded]
    used: set[int] = set()
    placed: list[BBox | None] = [None] * len(cells)

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
    cells = cells_of(zone)
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
    both = [(label, value) for label, value in zip(placed[0::2], placed[1::2])
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
    for index, (cell, _) in enumerate(cells_of(zone)):
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
        if len(inside) == end - index:
            out.extend(zip(range(index, end), inside))
        index = end
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
    pairs = (list(enumerate(lines)) if len(lines) == len(placed)
             else _between(lines, placed, y0, height))
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


def locate(image: ImageArray, document: Document) -> tuple[int, int]:
    """Set `Cell.bbox` on every Cell that can be placed — and None on every
    one that cannot, so a later round keeps no stale box. Returns (placed,
    cells). `image` is `Rectified.plain`."""
    zones = [z for z in document.zones
             if z.bbox is not None and z.kind is not Kind.FIGURE and z.complete]
    for zone in document.zones:
        for cell, _ in cells_of(zone):
            cell.bbox = None
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
    placed = total = 0
    for zone, found in zip(zones, read):
        boxes = place(zone, found)
        for fallback in (_from_grid, _from_pairs, _from_ink):
            boxes = fallback(image, zone, boxes)
        for (cell, _), box in zip(cells_of(zone), boxes):
            cell.bbox = box
            placed += box is not None
            total += bool(cell.text.strip())
    return placed, total
