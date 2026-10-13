"""What a model is asked for, and how it becomes IR.

Each pass declares a Pydantic model describing the response it wants. That
model's JSON Schema goes to Ollama as `format`, so generation is constrained
during decoding and the response is schema-valid by construction — malformed
JSON is prevented rather than parsed around.

**A wire schema is not the IR, deliberately.** The IR carries per-Engine
readings, provenance, Disputed states and Corrections, none of which a model
produces. And heavily constrained decoding degrades content quality as schema
complexity rises: a 4B model asked for something flat reads the page better than
the same model asked for something nested. So every wire schema here is a list
of records of scalars, and nothing more.

The mapping functions are where validation actually lives. A schema guarantees
shape, not sense — it cannot say that two Zones numbered as one Band actually
sit side by side, or that a row has as many cells as the header. Those are checked here, and a failure names the Zone and
raises rather than being coerced into an empty result: a silently sparse
Document looks exactly like a sparse document.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Callable, Literal, NoReturn

from pydantic import BaseModel, Field, ValidationError

from .ir import BBox, Block, Cell, Kind, Pair, Reading, Row, RowRole, Run, Zone

Read = Callable[[str], Reading]
"""Turns cell text into a Reading carrying its engine, model and prompt version.

Injected so the mapping functions stay pure: provenance belongs to whatever did
the reading, and a mapper that reached for it would need an Engine to test.
"""

GRAPHIC_KINDS = ("logo", "chart", "signature", "stamp", "badge")
"""What a figure may be. The closed set, and the only values `Zone.graphic_kind`
may take."""

MARKS = frozenset({"signature", "stamp", "badge"})
"""Which of those are Marks rather than Graphics.

A Mark carries document meaning, so its text is captured and it renders as itself.
A Graphic — a logo, a chart's plotted area — is drawn from its own pixels, and a
logo's wordmark is part of the artwork rather than content: it goes to the
image's `alt`, not onto the page. See `render._figure`.

One set, imported by the renderer, because the two lists drifting apart is how a
graphic kind ends up handled by code that can never receive it.
"""


class MappingError(ValueError):
    """A schema-valid response that does not describe the page.

    Always names the Zone it was reading, so a failure points at a region of the
    document rather than at a line of parser.
    """


class NotPairs(MappingError):
    """The Pairs Extractor's evidence that this Zone is not Pairs at all.

    A distinct type rather than a message the Orchestrator matches on, because
    this is the one failure in the project that carries a *diagnosis* rather than
    only a complaint: an unlabelled value is positive evidence about the Zone's
    Kind, arrived at from the full-resolution crop that the classification pass
    saw at the same size but answered differently. Everything else raised here
    says "I could not read this"; this says "you asked the wrong question".

    `_extract` acts on it by re-reading the Zone as prose. Matching on the
    message text would have worked today and broken the first time somebody
    reworded it.
    """


class ClassifyResponse(BaseModel):
    """What one Zone structurally is, decided from that Zone's own crop.

    Its own question, and never part of finding the Zones, because the two
    are about different pixels: geometry sees the whole page and answers about
    position, this sees one region at full resolution and answers about
    structure. See `CLASSIFY_PROMPT` for what was measured about that
    difference, when geometry was still a model's answer.

    Two scalars and no list, which is this module's standing rule about
    constrained decoding applied to the smallest question in the pipeline.

    **`title` used to be the third, and asking for it here is what stopped it
    ever arriving.** It came back `""` in all 36 of run 69's classify calls, on
    crops where the caption is plainly legible; asked on its own against those
    same crops it came back correct 4 times out of 4. It is now
    `CaptionResponse`'s question. See `engines.ollama.CAPTION_PROMPT`.
    """

    kind: Literal["table", "pairs", "prose", "list", "figure"]
    graphic: Literal["", "logo", "chart", "signature", "stamp", "badge"] = Field(
        default="",
        description="What a figure is. Empty string for every other kind",
    )


class CaptionResponse(BaseModel):
    """What a region's first printed line is: its caption, a heading row, or content.

    Two fields, and the reading one comes first on purpose: the model is asked to
    copy the line out before judging it, so the judgement is made against a line
    it has already read rather than against an impression of the crop.

    Kept apart from `ClassifyResponse` because the two questions want different
    pixels — this one needs the caption in frame, and the Kind question is
    measurably wrong while it is. That is the same argument that put
    classification in its own pass, applied one level further down.

    **`header` and `content` do exactly the same thing, and that is the point. Do
    not collapse this back to a boolean.** Nothing branches on which of the two
    it is; both mean "no Title, and the Kind question keeps the whole crop". The
    third value exists so the model has somewhere to *put* the answer, and that
    is the entire measured difference between the two shapes:

    | | `is_heading: bool` | this |
    |---|---|---|
    | correct on 11 run-71 crops | **4** | **8** |

    The boolean answered `true` on 8 of 8 crops — a constant rather than a
    judgement. Asked whether `"Item"` at the top of a price table is a heading,
    it has no false answer available that is not also wrong, so it said yes, and
    run 71 cut two table heading rows off `invoice_0001`: Zone 4 became a single
    data row and classified `pairs`, Zone 5 lost its summary row and with it the
    385.00 column-sum Probe. Offered `header`, the same model answers `header` on
    both.

    The lesson generalises past this field. When a model answers a closed
    question the same way every time, check whether the schema can express the
    true answer before rewording the question.
    """

    first_line: str = Field(
        description="The region's first printed line, copied exactly",
    )
    line_is: Literal["caption", "header", "content"] = Field(
        description="caption: a heading naming the whole region, not part of it. "
                    "header: the heading row of a grid, one cell per column "
                    "below. content: the region's own first line of content",
    )


class WireRun(BaseModel):
    """One stretch of a Zone's text that is set apart from the rest of it.

    **Phase A1, 2026-09-24.** Added because the schema could not express a link
    at all: `WireBlock.lines` was a list of plain strings, so every link, code
    span and badge in the corpus was dropped before anything could render it —
    T6 measured 0 of 42 across eight documents.

    It is deliberately *additive*. The model still returns the same `lines` and
    `cells` it always did, and these spans are reported beside them rather than
    inside them. An empty list, or a span that does not occur in the text,
    leaves the answer exactly as it was before Runs existed, so the worst case
    of the whole feature is no change rather than a mangled reading.
    """

    text: str = Field(
        description="The span exactly as printed, copied from the text above",
    )
    kind: Literal["link", "code", "strong", "em", "mark"]


class WireRow(BaseModel):
    """One table row: a role and a flat list of cell strings."""

    role: Literal["header", "data", "summary"]
    cells: list[str]
    marked: list[WireRun] = Field(
        default_factory=list,
        description="Spans inside this row's cells that are set apart",
    )


class TableResponse(BaseModel):
    """A `table` Zone. Row Roles are asked for here because they are visible on
    the page — a shaded top row, a ruled-off total — and are what later keep a
    summary row out of a column sum."""

    rows: list[WireRow]


class WirePair(BaseModel):
    label: str
    value: str
    marked: list[WireRun] = Field(
        default_factory=list,
        description="Spans inside this label or value that are set apart",
    )


class PairsResponse(BaseModel):
    """A `pairs` Zone: label/value bindings in reading order."""

    pairs: list[WirePair]


class RunsResponse(BaseModel):
    """What the inline pass returns for one Zone: its marked spans, or none.

    A Zone-level answer rather than a per-block one, because the pass is shown
    the Zone's own crop and the blocks are the Extractor's division of it, not
    something the model is looking at. `runs_into` places each span in whichever
    Cell contains it.
    """

    marked: list[WireRun] = Field(default_factory=list)


def _covers_everything(span: str, text: str) -> bool:
    """Whether a span is the whole of the line it sits in.

    **The guard the first attempt needed and did not have.** Asked inside the
    Extractor prompt, the model marked all five lines of `newsletter_0008`'s
    opening paragraph `strong` — the entire block. That is not emphasis, it is
    the block's own typeface, and `projection.inlineOf` agrees: it compares a
    run against *the block it sits in*, so a wholly bold paragraph yields no
    `strong` runs and a span like that could never score anyway. Dropping it
    also stops the renderer wrapping whole paragraphs in `<strong>`.
    """
    return _spell(span) == _spell(text)


def runs_into(zone: Zone, response: RunsResponse) -> Zone:
    """Attach the pass's spans to whichever Cells of this Zone contain them.

    Marking only. Every Cell keeps the text it already had — `_runs_for` cuts
    that string and never rewrites it, and `ir.Cell.runs` throws the Runs away
    if they do not spell it back. So the worst this pass can do is mark nothing.
    """
    kept = [run for run in response.marked if run.text.strip()]
    if not kept:
        return zone
    # **One span, one Cell.** The pass answers for the whole Zone, so a span
    # offered once would otherwise be stamped on every line that happens to
    # contain that text: `invoice_0001`'s `12345` marked both `12345 Sunny
    # Road` and `Sunnyville, CA 12345`, doubling one false mark into two.
    for block in zone.blocks:
        for cell in block.lines:
            if not kept:
                return zone
            usable = [run for run in kept
                      if not _covers_everything(run.text, cell.text)]
            for reading in cell.readings[:1]:
                _marked(reading, usable)
            placed = {run.text for run in cell.runs if run.kind != "text"}
            kept = [run for run in kept if run.text not in placed]
    return zone


class WireBlock(BaseModel):
    """One block of text. `lines` preserves the line structure a reader sees, so
    a three-line address does not arrive as one run-on string."""

    kind: Literal[
        "heading", "paragraph", "address", "item", "caption", "quote",
        "attribution", "mark",
    ]
    lines: list[str]
    marked: list[WireRun] = Field(
        default_factory=list,
        description="Spans inside this block's lines that are set apart",
    )


class BlocksResponse(BaseModel):
    """A `prose` or `list` Zone. One schema for both: the difference between a
    paragraph and a bullet is the block kind, not a different shape of answer."""

    blocks: list[WireBlock]


class FigureResponse(BaseModel):
    """A `figure` Zone.

    `text` is text *written on* the graphic that a reader reads — a chart's title
    and axis labels, a PAID stamp, a badge. It is empty for a logo, whose
    wordmark is part of the artwork. A chart's underlying data is never asked
    for: inferring it from the geometry of bars would put a guess in the output
    presented as a reading.
    """

    graphic: Literal["logo", "chart", "signature", "stamp", "badge"]
    text: list[str]


def schema_of(model: type[BaseModel]) -> dict[str, Any]:
    """The JSON Schema handed to Ollama as `format`."""
    return model.model_json_schema()


def bands_from_boxes(boxes: list[BBox]) -> list[tuple[int, int]]:
    """Band and column for each box, worked out from the boxes themselves.

    **The rule:** sort by top edge, then left. A new Band starts as soon as a box
    begins at or below where the *shortest* box in the current Band ended.
    Within a Band, columns run left to right.

    `min` rather than `max` is the whole of it, and the naive version is what
    made that clear. Merging a box into a Band whenever it overlaps *any* member
    chains along the page: `invoice_0002`'s address block ends at 0.135 and its
    "NO: / Date:" line begins at 0.128, a seven-thousandth overlap, and that hair
    was enough to pull a Band 1 Zone into Band 0 and everything after it up by
    one. A short member has to be able to close a Band, or one tall neighbour
    swallows the rows beneath it.

    **Measured against every ground truth in the repo.** The rule reproduces the
    hand-authored Band and column numbering of all five fixtures exactly, and
    reproduces run 50's numbering — the model's own answer on the document that
    converts at zero mismatches — so deriving costs that run nothing. The naive
    any-overlap version matched three of five.

    **Why derive at all.** Band numbering was the part of the vision layout
    pass's answer this project watched break most often: five of the six prompt
    changes ever made to that prompt broke it, each time as collateral on a
    change that never mentioned it. And it is fully determined by the boxes.
    Runs 55 and 56 were the clearest case: correct boxes, correctly alternating
    columns, and a Band index that failed to increment between the first two
    rows, which cost both documents the whole Conversion. The detector reports
    no numbering at all, so every Conversion's Bands now come from here.
    """
    order = sorted(range(len(boxes)),
                   key=lambda i: (boxes[i].top, boxes[i].left))
    bands: list[list[int]] = []
    current: list[int] = []
    for index in order:
        if current and boxes[index].top >= min(boxes[j].bottom for j in current):
            bands.append(current)
            current = []
        current.append(index)
    if current:
        bands.append(current)

    placed: dict[int, tuple[int, int]] = {}
    for band, members in enumerate(bands):
        for column, index in enumerate(sorted(members, key=lambda j: boxes[j].left)):
            placed[index] = (band, column)
    return [placed[i] for i in range(len(boxes))]


def validate_bands(zones: list[Zone]) -> None:
    """Bands must be horizontal stripes, read top to bottom, left to right.

    Every Conversion's numbering is derived from the boxes by
    `bands_from_boxes`, so what this checks is the *boxes*: `bands_from_boxes`
    puts a box that lies inside another into that one's Band, so an enclosure
    fails here however the Bands were numbered. **This docstring used to say it
    could not fire on derived Bands.** It fired on three corpus documents, and
    the claim is part of why nobody looked — see `detector.without_enclosed`.

    It was written for a model that numbered Bands by reading order rather than
    by position, or grouped two Zones as side by side when one sits well below
    the other — geometry that is schema-valid and describes no page. The snap,
    the merge and the recovery of unread ink each move boxes after the
    detector, and each is checked here.
    """
    by_band: dict[int, list[Zone]] = {}
    for zone in zones:
        by_band.setdefault(zone.band, []).append(zone)

    for index, band in sorted(by_band.items()):
        columns = [zone.column for zone in band]
        if len(set(columns)) != len(columns):
            raise MappingError(
                f"band {index}: two Zones share column {columns} — "
                "column is what orders a Band, so it cannot repeat"
            )
        ordered = sorted(band, key=lambda z: z.column)
        lefts = [z.bbox.left for z in ordered if z.bbox]
        if lefts != sorted(lefts):
            raise MappingError(
                f"band {index}: column order {columns} does not run left to "
                f"right (lefts {[round(v, 3) for v in lefts]})"
            )
        for earlier, later in zip(ordered, ordered[1:]):
            if not (earlier.bbox and later.bbox):
                continue
            if not _overlaps_vertically(earlier.bbox, later.bbox):
                raise MappingError(
                    f"band {index}: Zones in columns {earlier.column} and "
                    f"{later.column} do not overlap vertically, so they are not "
                    "side by side"
                )
            if _overlaps_horizontally(earlier.bbox, later.bbox):
                raise MappingError(
                    f"band {index}: Zones in columns {earlier.column} and "
                    f"{later.column} overlap horizontally "
                    f"({earlier.bbox.left:.2f}-{earlier.bbox.right:.2f} and "
                    f"{later.bbox.left:.2f}-{later.bbox.right:.2f}) — Zones "
                    "side by side cannot share horizontal space, and one "
                    "enclosing the other is not two Zones"
                )

    tops = [
        min(zone.bbox.top for zone in band if zone.bbox)
        for _, band in sorted(by_band.items())
        if any(zone.bbox for zone in band)
    ]
    if tops != sorted(tops) or len(set(tops)) != len(tops):
        raise MappingError(
            f"Bands do not descend the page: tops {[round(v, 3) for v in tops]} "
            "in band order. Two Bands starting at the same height are one Band."
        )


def _overlaps_vertically(one: BBox, other: BBox) -> bool:
    return min(one.bottom, other.bottom) > max(one.top, other.top)


def _overlaps_horizontally(one: BBox, other: BBox) -> bool:
    """Whether two boxes share any horizontal span.

    The counterpart to `_overlaps_vertically`, and the check that catches the two
    ways a Band can be schema-valid nonsense: a full-width Zone that *encloses*
    the Zone beside it, and two Zones returned with the same box under different
    column numbers. Both were observed against a real `qwen3-vl:4b`, the second
    after a prompt that asks for non-overlapping regions in as many words — which
    is why this is a check and not a sentence.
    """
    return min(one.right, other.right) > max(one.left, other.left)


def classification_into(zone: Zone, content: str) -> Zone:
    """Fill in one Zone's Kind from a classification response.

    Fills the Zone in place and returns it, as `contents_into` does — the two are
    the same move at different stages, and a Zone rebuilt here would drop the
    geometry the previous pass put on it.

    The Kind that arrives is discarded rather than reconciled. Geometry's guess
    was made from a downscaled page and is the thing this pass exists to replace;
    keeping it as a tie-breaker would reintroduce the answer being corrected.

    The Zone is *not* marked complete. A Kind is not contents — it says which
    Extractor to run, and a Zone marked complete here would never be read.

    **A Title now depends on the geometry box containing it.** The layout pass
    used to report a Title independently of its own box, so a box drawn tight
    still carried the caption above it; read from the crop, a caption outside the
    box is a caption nobody sees. Every titled Zone in the five fixtures has its
    Title inside its box — checked against the ground-truth geometry — so this is
    a coupling the split introduces rather than a defect it has. It becomes
    load-bearing when #17 removes the layout pass's copy, and it is the thing to
    look at first if Titles start going missing.
    """
    where = (f"zone in band {zone.band} column {zone.column}")
    try:
        response = ClassifyResponse.model_validate_json(content)
    except ValidationError as error:
        # Named with the answer rather than the field path: a Kind outside the
        # closed set means the Engine could not constrain its decoding, and
        # which value it invented is the useful half of that report.
        raise MappingError(
            f"{where}: {content.strip()[:120]} is not a classification "
            f"({error.error_count()} problems)"
        ) from error

    graphic = response.graphic.strip().lower()
    if graphic and graphic not in GRAPHIC_KINDS:
        raise MappingError(
            f"{where}: graphic {response.graphic!r} is not one of {GRAPHIC_KINDS}"
        )

    zone.kind = Kind(response.kind)
    zone.graphic_kind = graphic or None
    return zone


def caption_into(zone: Zone, content: str) -> Zone:
    """Fill in one Zone's Title from a caption response, or leave it unset.

    Fills in place and returns the Zone, as `classification_into` does. Only
    `caption` yields a Title. A `first_line` the model called `header` or
    `content` is dropped rather than stored: either way it is part of the
    region's own contents, and the Extractor is about to read it anyway.

    **A blank `first_line` takes no Title even on `caption`.** No text means no
    caption to name, and because the Orchestrator gates its crop on
    `zone.title is not None` rather than on the verdict, that same emptiness also
    means no band is cut. The two decisions cannot drift apart.

    **"Not a heading" does not clear a Title that is already there.** The VLM
    layout pass reports a Title of its own, so on that path a Zone can arrive
    carrying one; this pass adds a Title where there was none rather than
    arbitrating between two sources. Deleting the layout pass's copy is #17's
    job, and doing half of it here would make the two paths disagree about a
    field for reasons neither records. A detector run has no such copy, and that
    is the path this was measured on.

    **A Title depends on the geometry box containing it.** Read from the crop, a
    caption outside the box is a caption nobody sees, and
    `detector.attach_headings` exists to put each `section_header` inside the
    region it names. Every titled Zone in the five fixtures has its Title inside
    its box.
    """
    where = f"zone in band {zone.band} column {zone.column}"
    try:
        response = CaptionResponse.model_validate_json(content)
    except ValidationError as error:
        raise MappingError(
            f"{where}: {content.strip()[:120]} is not a caption "
            f"({error.error_count()} problems)"
        ) from error

    if response.line_is == "caption":
        zone.title = response.first_line.strip() or None
    return zone


def rows_from_table(response: TableResponse, *, read: Read) -> list[Row]:
    """Map a table response onto Rows, reconciling any row against the header.

    One thing a schema cannot check is still checked here: that the region had
    any rows at all, because an empty table rendered as a table looks like a
    document that had one.

    **Width is reconciled rather than enforced, as of spec 0007 Phase A-1.** It
    used to raise, and the cost of that is measured: on `statement_0006` the
    model returned all 36 transaction rows correctly, one of them disagreed with
    the header on cell count, `_extract` caught the `MappingError` and the whole
    Zone became a skeleton — recall 0.097 on a document whose content had
    already been read. A row a cell short is a cell that was dropped; throwing
    away the other thirty-five rows to protest about it is not a proportionate
    answer, and it is the single cheapest recall in the corpus to recover.

    What the old check was *right* about survives, and it is the reason a short
    row is padded at the **end** and marked rather than quietly filled: a
    dropped cell shifts every value after it into the wrong column, and the
    numbers stay individually plausible. So the padding is a `Cell` with no
    Reading at all — distinguishable from a cell read as empty — and
    `table_repairs` turns that into a finding naming the row and the shortfall.
    A reader is told the row is suspect; nothing is thrown away to tell them.

    - **Short row:** padded to the header's width with unread Cells.
    - **Long row:** kept whole, every cell, and flagged. Dropping the surplus
      would be the one repair here that loses content, which is the thing this
      phase exists to stop.
    - **Summary row:** left exactly as it arrived. Narrower is normal — totals
      rows merge cells as a matter of course — and this is the one allowance
      the old check already made, so padding it now would change behaviour the
      column-sum Probe was measured against for no gain.

    A header row split one cell per row is put back together first — see
    `_join_split_header_row` — and a header repeated to pad a stated row count
    is removed after that, by `_without_repeated_header`. The order matters:
    the split header must be rejoined before it can be compared with a repeat
    of itself. Then a row padded on the left loses its leading empty cells,
    `_trimmed_to_header`, and a summary repeating the one above it goes,
    `_without_repeated_total` — in that order, so the columns compare.
    """
    if not response.rows:
        _no_content("table", "no rows")

    wire_rows = _without_repeated_total(_trimmed_to_header(
        _without_repeated_header(
            _join_split_header_row(_without_empty_rows(response.rows))
        )
    ))
    if not wire_rows:
        _no_content("table", "nothing but empty rows")

    header = next((r for r in wire_rows if r.role == "header"), None)
    width = len(header.cells) if header else None

    rows = []
    for wire in wire_rows:
        cells = [Cell(readings=[_marked(read(text), wire.marked)])
                 for text in wire.cells]
        if width is not None and wire.role != "summary" and len(cells) < width:
            # An unread Cell, not an empty one. `Cell.text` is "" either way, so
            # the render is unchanged; what differs is that this one carries no
            # Reading, which is what `table_repairs` counts and what keeps the
            # pad honest rather than invisible.
            cells += [Cell(readings=[]) for _ in range(width - len(cells))]
        rows.append(Row(role=RowRole(wire.role), cells=cells))
    return rows


def table_repairs(zone: Zone) -> list[str]:
    """What reconciling this Zone's rows against its header had to do, in words.

    Derived from the Zone rather than reported out of `rows_from_table`, which
    is the same argument `_record_extract` already makes about the wire-level
    repairs: `wire.py` maps a response without knowing which Zone it belongs to,
    and threading a collector down through `contents_into` would put diagnostic
    plumbing in the shipping path. The IR already holds the evidence — a padded
    Cell has no Reading, and a long row is longer than the header — so this
    reads it back off the answer instead.

    Returns **one sentence per repair, not per row**: rows repaired the same
    way — short by the same count, or long at the same width — are named
    together. `statement_0006`'s header came back one empty cell wider than
    its 41 rows, and one sentence per row printed that single fact 41 times.
    A repair to one row keeps the sentence it always had. Empty for a table
    that needed none, which is the normal case.
    """
    header = next((row for row in zone.rows if row.role is RowRole.HEADER), None)
    if header is None:
        return []
    width = len(header.cells)
    # Keyed on what was done, so no sentence claims a shortfall a row did not
    # have. Dicts keep insertion order, which is the order of each repair's
    # first row.
    repairs: dict[tuple[str, int], list[int]] = {}
    for index, row in enumerate(zone.rows):
        if row.role is RowRole.SUMMARY:
            continue
        unread = sum(1 for cell in row.cells if not cell.readings)
        if unread:
            repairs.setdefault(("short", unread), []).append(index)
        elif len(row.cells) > width:
            repairs.setdefault(("long", len(row.cells)), []).append(index)

    notes = []
    for (repair, count), rows in repairs.items():
        if len(rows) == 1 and repair == "short":
            notes.append(
                f"row {rows[0]} came back {count} cell(s) short of the header's "
                f"{width} and was padded rather than discarded — the values it "
                "does have may sit in the wrong columns"
            )
        elif len(rows) == 1:
            notes.append(
                f"row {rows[0]} came back with {count} cells against the "
                f"header's {width} and was kept whole — every value is present, "
                "and the surplus means some of them may sit in the wrong columns"
            )
        elif repair == "short":
            notes.append(
                f"rows {_runs_of(rows)} ({len(rows)} rows) each came back "
                f"{count} cell(s) short of the header's {width} and were padded "
                "rather than discarded — the values they do have may sit in the "
                "wrong columns"
            )
        else:
            notes.append(
                f"rows {_runs_of(rows)} ({len(rows)} rows) each came back with "
                f"{count} cells against the header's {width} and were kept "
                "whole — every value is present, and the surplus means some of "
                "them may sit in the wrong columns"
            )
    return notes


def _runs_of(indices: list[int]) -> str:
    """`[1, 3, 5, 6]` as `1, 3, 5–6`: consecutive indices named as one run."""
    runs: list[list[int]] = []
    for index in indices:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    return ", ".join(
        str(run[0]) if len(run) == 1 else f"{run[0]}–{run[-1]}" for run in runs
    )


def _join_split_header_row(rows: list[WireRow]) -> list[WireRow]:
    """Put back together a header row returned one cell per row.

    A header row whose cells sit at opposite edges of a wide table is the one
    thing on `example/invoice.png` that four measured runs could not talk a real
    `qwen3-vl:4b` out of: `Item` and `Price` come back as `["Item", ""]` and
    `["", "Price"]`, so `Price` never reaches `Item`'s row. Runs 01, 05, 10 and
    13 all show it, 13 with a prompt forbidding it in as many words, which is
    what moved the fix here from the prompt.

    **Known limitation.** A genuine two-tier header — `["Q1", ""]` over
    `["", "Revenue"]`, meaning two stacked rows of headings — meets every
    condition below and is joined into one row. Nothing on the fixtures has that
    shape, and no run has ever produced one, so this is a recorded risk rather
    than a measured defect. "Invents nothing and discards nothing" is true of the
    strings; it is not a claim about the structure they were arranged in.

    Note what is *not* wrong: the width. The model returns two cells and the
    table has two columns, so it has read the shape correctly and only misplaced
    the line break. That is why the remedy 0002 sketched — a pass asking how
    many columns there are — is not the one taken; it would answer a question
    nobody got wrong.

    The rule is deliberately narrow, because a repair that guesses is worse than
    a failure that is loud:

    - Only `header` rows. Data rows bind correctly on the evidence, and a sparse
      data row is a real shape rather than a defect.
    - Only equal widths, and only where no position is filled twice. Two
      headings competing for one column are not one row split in two, and
      choosing between them would drop one silently.

    Under those conditions the join invents nothing and discards nothing: every
    string keeps the column it arrived in. Anything else is passed through
    untouched and still meets the width check below.
    """
    joined: list[WireRow] = []
    for row in rows:
        previous = joined[-1] if joined else None
        if (
            previous is not None
            and previous.role == "header"
            and row.role == "header"
            and len(previous.cells) == len(row.cells)
            and not any(a and b for a, b in zip(previous.cells, row.cells))
        ):
            joined[-1] = WireRow(
                role="header",
                cells=[a or b for a, b in zip(previous.cells, row.cells)],
            )
        else:
            joined.append(row)
    return joined


def _without_repeated_header(rows: list[WireRow]) -> list[WireRow]:
    """Drop a later header row that repeats the first one word for word.

    **The third dormant net, and the same shape as the other two: it only ever
    removes a row that says nothing new.** Added in spec 0007 Phase A0,
    2026-09-22, for a padding the T1 ratchet caught.

    The cause is arithmetic, not reading. `table_grid` counts bands of ink and
    cannot tell a caption from a heading row, so a crop whose first line is a
    caption measures one row more than the table has — and `with_grid` states
    that number. The model complies with *how many*, which is what it reliably
    complies with, and fills the surplus by repeating the header it has already
    given. Measured over the whole corpus, exactly two tables did this and both
    repeated the header verbatim: `darkdeck_0009`'s Service level table, whose
    caption was lifted into `Zone.title`, and `report_0011`'s berth table, whose
    caption was not lifted at all. Same fault either way.

    **Why the count is not simply corrected instead.** It was, until this phase:
    `with_grid(titled=True)` subtracted the caption's line while leaving it in
    the picture, so the prompt asked for 16 rows of a crop showing 17 and the
    model resolved the disagreement by dropping a *real* row —
    `sample_table_0003` lost all five column headers that way and the harness
    scored it a full match. A surplus row is a precision fault and a dropped
    row is a recall fault, and recall is the top of the rubric. So the prompt
    states what the crop holds and the surplus is removed here, after it has
    been read.

    Narrow on purpose, in the same spirit as `_join_split_header_row`:

    - Both rows must be `header`. A data row repeating another is a real shape —
      two months with identical figures — and is not this.
    - The repeat must be **verbatim**. A second heading tier differing by one
      cell is a different row and is kept.
    - Only repeats of the *first* header are dropped, so a table that genuinely
      changes its headings partway keeps both.

    **A recorded risk rather than a measured defect**, stated the way
    `_join_split_header_row` states its own: a long table that reprints its
    header partway down — as a paper form does across a page break — meets
    every condition here and loses the second copy. No document in the corpus
    has that shape, and the page would then print the heading twice while the
    output printed it once, which `Completeness.lost` would report.
    """
    first = next((row for row in rows if row.role == "header"), None)
    if first is None:
        return rows
    spelling = [_spell(cell) for cell in first.cells]
    return [
        row for row in rows
        if row is first
        or row.role != "header"
        or [_spell(cell) for cell in row.cells] != spelling
    ]


def _trimmed_to_header(rows: list[WireRow]) -> list[WireRow]:
    """Take the leading empty cells off a row wider than the header.

    **The fourth net, and the same shape: it removes only cells that say
    nothing.** Added in spec 0009, step A, 2026-10-11, for `nonlatin_0014`.
    Its header and data rows are four cells, and its totals print their label
    in the third column and their figure in the fourth. Two summary rows came
    back five wide — `['', '', '', 'Συνολικό πληρωτέο', '12.437,82']` — so the
    grand total stood one column right of `ΦΠΑ 24%` and its figure in a
    column no other row has. Measured over every table answer in
    `tests/frozen/s3-result/`, these two are the only wide rows that open
    with an empty cell.

    Narrow on purpose:

    - **Never a cell with text in it.** The trim stops at the first non-empty
      cell, so a wide row that opens with a value is kept whole and flagged by
      `table_repairs`, as before.
    - **Only where the header's width is the table's** — as many rows of the
      header's width as wider ones. `menu_0012` and `cv_0013` both read a
      one-cell header over two- and four-cell rows; there it is the header
      that is short, and trimming to it would move values into columns they
      were not read in.
    """
    header = next((row for row in rows if row.role == "header"), None)
    if header is None or not _is_the_tables_width(
            len(header.cells), [len(row.cells) for row in rows]):
        return rows
    return [
        row if row.role == "header"
        else row.model_copy(update={"cells": row.cells[
            _empty_lead(row.cells, len(header.cells)):]})
        for row in rows
    ]


def _without_repeated_total(rows: list[WireRow]) -> list[WireRow]:
    """Drop a summary row that only repeats the summary row above it.

    **The fifth net: it removes a row that says nothing new.** Added with
    `_trimmed_to_header`, which runs first so the columns compare.
    `nonlatin_0014`'s last summary row came back `['', '', '', '',
    '12.437,82']` under `Συνολικό πληρωτέο | 12.437,82`, and the page prints
    the figure once. Every non-empty cell of the row must equal the cell in
    the same column of the row directly above it, compared as `_spell` does.

    **Only a summary under a summary.** A total equal to the one data row
    above it is a real shape — an invoice of one line — and a dropped row is
    a recall fault where a surplus row is only a precision one, so that side
    keeps the row.
    """
    return [
        row for index, row in enumerate(rows)
        if not (index and row.role == "summary"
                and rows[index - 1].role == "summary"
                and _repeats(row.cells, rows[index - 1].cells))
    ]


def retrimmed(rows: list[Row]) -> list[Row]:
    """`_trimmed_to_header` then `_without_repeated_total`, on the IR.

    For `tools/rederive.py`, which brings IRs made before the two nets up to
    them. Same rules, read off each Cell's text.
    """
    header = next((row for row in rows if row.role is RowRole.HEADER), None)
    if header is not None and _is_the_tables_width(
            len(header.cells), [len(row.cells) for row in rows]):
        for row in rows:
            if row.role is not RowRole.HEADER:
                row.cells = row.cells[_empty_lead(
                    [cell.text for cell in row.cells], len(header.cells)):]
    return [
        row for index, row in enumerate(rows)
        if not (index and row.role is RowRole.SUMMARY
                and rows[index - 1].role is RowRole.SUMMARY
                and _repeats([cell.text for cell in row.cells],
                             [cell.text for cell in rows[index - 1].cells]))
    ]


def _is_the_tables_width(width: int, widths: list[int]) -> bool:
    """Whether at least as many rows are `width` wide as are wider."""
    return widths.count(width) >= sum(1 for each in widths if each > width)


def _empty_lead(cells: list[str], width: int) -> int:
    """How many leading cells can go: empty ones, and no more than the surplus."""
    cut = 0
    while len(cells) - cut > width and not cells[cut].strip():
        cut += 1
    return cut


def _repeats(cells: list[str], above: list[str]) -> bool:
    """Whether every non-empty cell equals the one in its column above."""
    filled = [(column, text) for column, text in enumerate(cells) if text.strip()]
    return bool(filled) and all(
        column < len(above) and _spell(above[column]) == _spell(text)
        for column, text in filled)


def _without_empty_rows(rows: list[WireRow]) -> list[WireRow]:
    """Drop rows carrying no content at all, before anything is checked.

    A row saying **nothing** is not the failure the width check below exists to
    catch. That check's reason is that "a dropped or invented cell shifts every
    value after it into the wrong column" — which is a statement about a row that
    has *some* values and the wrong number of them, where there is no way to tell
    which column each surviving value belongs to. A row with none carries nothing
    to place, so dropping it moves no value into a wrong column. Every other row
    keeps the cells it arrived with.

    **The test is on content, not on count — corrected in spec 0007 Phase A0,
    2026-09-22.** It was `if row.cells`, which is truthy for
    `['', '', '', '', '']`: a row of empty strings has five cells and says
    nothing, so it passed the width check on its width and rendered as a blank
    line inside the table. `report_0011`'s berth table carried one at row 5.
    The two readings of "empty" had been standing in for each other because
    every case anyone had looked at happened to be a row with literally no
    cells.

    **The net itself stays**, and the distinction matters: the finding was that
    this filter tested the wrong thing, not that it should not exist. Four runs
    established what it guards, two of which lost a whole table and the 385.00
    Probe to a single such row.

    Measured, and the reason this exists: runs 39 and 45 both converted
    `invoice_0001` on ink-snapped geometry and both returned the correct table
    plus one `{"role": "data", "cells": []}` at the same index, right after
    `Website design`. The width check rejected the row, `rows_from_table` raised,
    and the Zone rendered as an empty skeleton — losing nine correctly read
    strings, the line-item table and the column-sum Probe, the only arithmetic
    check the document has. Replaying run 45's recorded answer through this
    reproduces the fixture's Row Roles and every cell exactly, and the Probe
    reconciles at 385.00.

    Narrow on purpose, in the same spirit as `_join_split_header_row`: a row with
    one value out of two is still ambiguous and is still rejected. This only ever
    removes a row that says nothing.
    """
    return [row for row in rows if any(cell.strip() for cell in row.cells)]



def _runs_for(text: str, marked: Sequence[WireRun]) -> list[Run]:
    """Split one string into Runs at the spans the model marked.

    **Nothing here may change the words.** Each span is located in the text and
    the text is cut at it; a span that does not occur is skipped, and one that
    overlaps a span already placed is skipped. So the Runs always concatenate
    to exactly `text`, which is the invariant `Cell.runs` re-checks before
    rendering — twice, because this is the one place a model answer could
    otherwise edit a reading it was only asked to annotate.

    Longest span first, so marking both `editor@example.com` and `example.com`
    keeps the longer one rather than cutting it in half. Ties go to the
    earlier occurrence, which keeps the result independent of the order the
    model happened to list them in.
    """
    if not text or not marked:
        return []
    taken: list[tuple[int, int, str]] = []
    for run in sorted(marked, key=lambda r: (-len(r.text), r.text)):
        span = run.text.strip()
        if not span:
            continue
        start = 0
        while True:
            at = text.find(span, start)
            if at < 0:
                break
            if not any(at < end and start_ < at + len(span)
                       for start_, end, _ in taken):
                taken.append((at, at + len(span), run.kind))
                break
            start = at + 1
    if not taken:
        return []

    runs: list[Run] = []
    cursor = 0
    for start, end, kind in sorted(taken):
        if _splits_a_word(text, start, end):
            continue
        if start > cursor:
            runs.append(Run(text=text[cursor:start]))
        runs.append(Run(text=text[start:end], kind=kind))
        cursor = end
    if cursor < len(text):
        runs.append(Run(text=text[cursor:]))
    return keep_runs(runs)


def _splits_a_word(text: str, start: int, end: int) -> bool:
    """Whether marking `text[start:end]` would cut a word in half.

    **Measured, on the sweep that found it.** The inline pass marked `T` — the
    drop cap of `newsletter_0008`'s opening paragraph — and the first `T` in
    the block's text belongs to `Tuesday`. Rendered, that is
    `<strong>T</strong>uesday`: the page still reads `Tuesday`, and `project()`
    walks **text nodes**, so the word scored as `t` and `uesday` and T1
    reported `tuesday` as no longer printed. One word, and it failed the
    ratchet.

    A mark is a typographic fact about whole words. Nothing in this corpus
    emphasises half of one, so a span landing mid-word is the wrong span rather
    than an unusual one.
    """
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    head, tail = text[start], text[end - 1]
    return ((head.isalnum() and before.isalnum())
            or (tail.isalnum() and after.isalnum()))


def keep_runs(runs: list[Run]) -> list[Run]:
    """Drop marking that describes the whole passage rather than a span of it.

    **The generalisation of `_covers_everything`, and the same fault one level
    down.** Asked about `newsletter_0008`'s pull quote, the model returned
    twenty-two marks — *every word of it*, one at a time, each `strong`. That
    is the block's own typeface reported word by word, and it is expensive
    rather than merely useless: every mark is a text-node boundary, so a block
    shredded into twenty-two nodes loses every adjacent-word pair in it, and
    `join_recall` is the one T1 leg that sees it.

    So when **every** word of a Cell is marked, none of it is emphasis and all
    of it goes. **Counted across kinds together, not kind by kind** — `Country
    statistics` came back as `Country` `strong` plus `statistics` `em`, every
    word of the line, and sat at exactly 50% per kind, slipping a per-kind test
    twice over. `2021 — present` is the same shape in `cv_0013`.

    **The threshold is "all of them" because the corpus put it there, not
    because it is a round number.** Over every marked Cell of the trial sweep,
    the marked share is bimodal with an empty band in the middle: genuine marks
    run 0.077 to 0.333 — `<head>`, `<article>`, `Anchor links`, `myDATA` — with
    a single genuine outlier at 0.750, `editor@example.com`, which tokenises as
    three of a four-word line. Every junk case sits at exactly 1.000. A tidier
    looking 0.5 would have thrown that email away, and it is precisely the kind
    of span this whole phase exists to keep.

    `projection.inlineOf` reaches the same conclusion from the other side — it
    judges a run against the block it sits in, so a wholly marked block yields
    no runs at all and marks like these could never score. What they do instead
    is cost: each one is a text-node boundary, and `join_recall` sees every one.
    """
    marked = [run for run in runs if run.kind != "text"]
    if not marked:
        return runs
    words = sum(len(_WORDS.findall(run.text)) for run in runs)
    if not words:
        return runs
    if sum(len(_WORDS.findall(run.text)) for run in marked) >= words:
        return _merged([Run(text=run.text) for run in runs])
    return runs


_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _merged(runs: list[Run]) -> list[Run]:
    """Adjacent Runs of one kind as a single Run, so no text node is split."""
    out: list[Run] = []
    for run in runs:
        if out and out[-1].kind == run.kind:
            out[-1] = Run(text=out[-1].text + run.text, kind=run.kind)
        else:
            out.append(run)
    return out


def _marked(reading: Reading, marked: Sequence[WireRun]) -> Reading:
    """Attach Runs to a Reading the injected `Read` has already built.

    Kept separate so `Read` stays `Callable[[str], Reading]`: provenance is the
    Engine's business and marking is the mapper's, and nine test modules build
    a `Read` of their own.
    """
    reading.runs = _runs_for(reading.text, marked)
    return reading


def _no_content(kind: str, what: str) -> NoReturn:
    raise MappingError(
        f"{kind} Zone came back with {what} — the layout pass said there is "
        "content here, so an empty answer is a failure rather than a finding"
    )


def pairs_from_response(response: PairsResponse, *, read: Read) -> list[Pair]:
    """Map a pairs response onto Pairs.

    A Pair is a label bound to a value, so a value with no label means the region
    was not Pairs — a finding rather than something to coerce. A label with no
    value is kept, because a printed label with nothing against it is what the
    page says.
    """
    pairs = []
    for index, wire in enumerate(response.pairs):
        label, value = wire.label.strip(), wire.value.strip()
        if not label and not value:
            continue
        if not label:
            raise NotPairs(
                f"pairs Zone entry {index} has no label, only {value!r} — an "
                "unlabelled value is not a Pair, so this region was not Pairs"
            )
        pairs.append(Pair(
            label=Cell(readings=[_marked(read(label), wire.marked)]),
            value=Cell(readings=[_marked(read(value), wire.marked)])))
    return pairs


def blocks_from_response(response: BlocksResponse, *, read: Read) -> list[Block]:
    """Map a prose or list response onto Blocks.

    Blank lines are dropped: a line with nothing on it is not content, and
    keeping it puts an empty row in the render. A block left with nothing after
    that is dropped too — but a response where *every* block empties out is an
    empty answer, and the caller decides whether that is allowed.
    """
    blocks = []
    for wire in response.blocks:
        lines = [line for line in (raw.strip() for raw in wire.lines) if line]
        if not lines:
            continue
        blocks.append(
            Block(kind=wire.kind,
                  lines=[Cell(readings=[_marked(read(line), wire.marked)])
                         for line in lines])
        )
    return blocks


def _spell(text: str) -> str:
    """One spelling of a printed string. See `_same_text` for why, exactly."""
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def _same_text(one: str, other: str) -> bool:
    """Whether two printed strings are the same string.

    Unicode-normalised, whitespace collapsed, case folded — the same spelling
    rule `scoring.normalise` uses, kept here rather than imported because
    `wire.py` maps answers and must not depend on the scorer. Punctuation is
    deliberately *not* stripped: a Title and a Block that differ by a colon are
    two different printed lines, and the echo this guards against is a verbatim
    repeat.
    """
    return bool(_spell(one)) and _spell(one) == _spell(other)


def prints(zone: Zone, text: str) -> bool:
    """Whether any entry of the Zone's reading prints `text`, spelled as
    `_same_text` spells it — within one Block, one row, or one pair's label
    and value read together."""
    wanted = _spell(text)
    if not wanted:
        return True
    entries = [" ".join(cell.text for cell in block.lines) for block in zone.blocks]
    entries += [" ".join(cell.text for cell in row.cells) for row in zone.rows]
    entries += [f"{pair.label.text} {pair.value.text}" for pair in zone.pairs]
    return any(wanted in _spell(entry) for entry in entries)


def _without_title_echo(zone: Zone) -> Zone:
    """Drop a Zone's first entry when it only repeats the Zone's own Title.

    **The schema rule spec 0007 Phase A0 asks for: a Zone carrying a Title must
    not also carry a Block repeating it.** Enforced here, where the contents are
    bound to a Zone that already has its Title, rather than filtered in
    `render.py` — the IR should not be able to hold the contradiction at all,
    because anything reading the IR rather than the page would otherwise see the
    heading twice.

    **This is where the echo is actually removed, and deliberately after the
    fact.** The cause is that the caption pass lifts the first printed line into
    `Zone.title` and leaves it in the Extractor's crop, so the model is shown it
    twice and answers honestly both times. Withholding the band from the
    Extractor as well was tried first and rejected on measurement — it deletes
    real content wherever the caption pass took a Title from something that was
    not a caption, and it has no reliable test for that; the evidence is in
    `engines.ollama.OllamaEngine.extract_zone`. So the caption is read twice and
    the second copy is dropped here, which costs nothing and risks nothing.

    **Only the first entry, and only an exact repeat.** Both bounds are measured
    rather than chosen. Over the 45 titled Zones of Phase A0's checkpoint there
    were 34 echoes — 27 Blocks, 5 table row-0s, 2 pair-0s — and **every one of
    the 27 was `blocks[0]`**, with nothing at all between 0.80 similarity and an
    exact match. So a rule confined to the first entry loses none of them, and a
    rule that scanned the whole body would be free to delete a legitimate
    repetition deeper down, which is the risk not worth taking for zero
    additional catch. A table's genuine heading row survives on the same
    evidence: `darkdeck_0009`'s `AVAILABILITY` Zone has a header row reading
    `AVAILABILITY | P95 LATENCY | INGEST VOLUME | COST PER MILLION`, which is not
    its Title and is not touched, while `cv_0013`'s single-cell `EDUCATION` row
    is and goes.

    **That Zone's Title goes instead** — see `_title_is_its_header_cell`. The
    echo runs the other way there: the Title is the copy, lifted off the
    heading row's first cell, and the row is the reading that keeps its place.

    A dropped row takes its `RowRole` with it. That is correct: a caption tagged
    `header` was never the table's heading row, and the row beneath keeps
    whatever role it was given.
    """
    title = zone.title
    if not title or not title.strip():
        return zone
    if zone.blocks and _same_text(
        title, " ".join(cell.text for cell in zone.blocks[0].lines)
    ):
        zone.blocks = zone.blocks[1:]
    elif _title_starts_its_block(zone):
        zone.title = None
    elif zone.rows and _same_text(
        title, " ".join(cell.text for cell in zone.rows[0].cells)
    ):
        zone.rows = repadded(zone.rows[1:])
    elif zone.pairs and _same_text(title, zone.pairs[0].label.text) \
            and zone.pairs[0].value.text.strip():
        # Only the label repeats the Title, and the value is content the page
        # prints once: `darkdeck_0009`'s `COST PER MILLION | $2.14`, where
        # dropping the pair took `$2.14` off the page — spec 0010, step A2.
        zone.pairs[0] = Pair(label=Cell(), value=zone.pairs[0].value)
    elif zone.pairs and (
        _same_text(title, zone.pairs[0].label.text)
        or _same_text(
            title, f"{zone.pairs[0].label.text} {zone.pairs[0].value.text}"
        )
    ):
        zone.pairs = zone.pairs[1:]
    elif _title_is_its_header_cell(zone):
        zone.title = None
    return zone


def repadded(rows: list[Row]) -> list[Row]:
    """Pad each row to the header that is there, and only to it.

    `rows_from_table` takes a table's width from its first header row, and
    `_without_title_echo` runs after it — so when the row it drops is that
    first header, the padding it caused is left behind. `statement_0006`'s
    caption came back as a header row seven cells wide; the real header and
    all forty rows were read six wide, and each was padded to seven before the
    caption went. The page grew an empty seventh column, and `table_repairs`
    reported 41 rows a cell short that the model had read whole.

    So the padding is taken off — every trailing Cell with no Reading, which
    is what a pad is and what nothing read can be — and put back against the
    first header that remains, by the same rule `rows_from_table` applies. A
    row genuinely short of that header is padded exactly as before. Nothing
    read is removed, and where no row was dropped this returns every row as
    it was, because the width is the one the rows were padded to. That is
    what lets `tools/rederive.py` apply it to every table.
    """
    def read(row: Row) -> list[Cell]:
        cells = list(row.cells)
        while cells and not cells[-1].readings:
            cells.pop()
        return cells

    header = next((row for row in rows if row.role is RowRole.HEADER), None)
    width = len(read(header)) if header else None
    for row in rows:
        cells = read(row)
        if width is not None and row.role is not RowRole.SUMMARY:
            cells += [Cell(readings=[]) for _ in range(width - len(cells))]
        row.cells = cells
    return rows


def _title_starts_its_block(zone: Zone) -> bool:
    """Whether a Zone's Title is the start of its first Block, which runs on
    past it — spec 0012, G8. The caption pass read the first printed line of
    a heading set on two, and the Block holds the whole heading:
    `paper_0018`'s `Frost Heave Under Lightweight Footbridges:` over its
    Block's `Frost Heave Under Lightweight Footbridges: A Field Study of
    Three Timber Crossings`, printed twice. **The Title goes and the Block
    stays**, so the heading is printed once and whole. Only the first Block,
    as `_without_title_echo`, only a heading — a paragraph opening with the
    Title's words is a sentence, not the heading run on — and only at a
    word's end."""
    if not zone.title or not zone.blocks or zone.blocks[0].kind != "heading":
        return False
    head = _spell(zone.title)
    text = _spell(" ".join(cell.text for cell in zone.blocks[0].lines))
    return bool(head) and len(text) > len(head) and text.startswith(head) \
        and text[len(head)] == " "


def _title_is_its_header_cell(zone: Zone) -> bool:
    """Whether the Title is the first cell of this table's own heading row.

    `darkdeck_0009`'s four metric cards print their labels on one line, and
    the caption pass took the first, `AVAILABILITY`, as the Zone's Title. The
    Extractor read the same line as a heading row of four. The page prints
    the word once; ours printed it as a caption and again as the row's first
    cell, one directly above the other.

    **The grid veto was meant to catch this and counts one column short.**
    `CaptionBand.aligns_to_grid` refuses a Title when the first line has as
    many columns of ink as the lines below it. The labels are letter-spaced,
    so `P95 LATENCY` and its neighbours split at their word gaps and the line
    counts 7 columns against the values' 6. Widening the veto would change
    the crop the Kind question is shown, which is a model question; the
    extracted heading row is better evidence than a column count anyway,
    because it is the model saying the line is a grid.

    Only a `header` row, and only one carrying at least one more label than
    the Title — the Title *plus* the rest of a heading row. A caption returned
    as a row of its own with empty cells beside it is the ordinary echo and is
    dropped as a row above; a data row may name its own section. Measured on
    `tests/frozen/a3-result/`, 2026-09-26: 1 of 47 titled Zones, this one.
    """
    title = zone.title
    if not title or not title.strip() or not zone.rows:
        return False
    first = zone.rows[0]
    return (first.role is RowRole.HEADER
            and _same_text(title, first.cells[0].text if first.cells else "")
            and any(cell.text.strip() for cell in first.cells[1:]))


def contents_into(zone: Zone, content: str, *, read: Read) -> Zone:
    """Validate an extraction response for this Zone's Kind and fill it in.

    One function rather than a branch in the Engine: which schema a Kind is read
    with, and how that answer becomes IR, are the same decision and belong
    together.

    An empty answer is allowed only for a Zone carrying a Title. A titled section
    with nothing under it is a real thing on a page — "Services / Products" above
    blank space — and reporting it as a failure puts a finding in front of an
    operator with nothing to fix. Without a Title there is nothing on the page to
    explain the emptiness, so the layout and extraction passes disagree.
    """
    if zone.kind is Kind.TABLE:
        zone.rows = rows_from_table(
            TableResponse.model_validate_json(content), read=read
        )
    elif zone.kind is Kind.PAIRS:
        zone.pairs = pairs_from_response(
            PairsResponse.model_validate_json(content), read=read
        )
        if not zone.pairs and not zone.title:
            _no_content("pairs", "no pairs")
    elif zone.kind in (Kind.PROSE, Kind.LIST):
        zone.blocks = blocks_from_response(
            BlocksResponse.model_validate_json(content), read=read
        )
        if not zone.blocks and not zone.title:
            _no_content(zone.kind.value, "no text")
    elif zone.kind is Kind.FIGURE:
        figure_into(zone, FigureResponse.model_validate_json(content), read=read)
    else:
        raise NotImplementedError(f"{zone.kind.value} extraction not yet wired")

    zone.complete = True
    return _without_title_echo(zone)


def figure_into(zone: Zone, response: FigureResponse, *, read: Read) -> Zone:
    """Record what the graphic is and any text written on it.

    An empty answer is the expected one for a logo, so nothing is checked for
    emptiness here: a Graphic with no text is a Graphic, and the placeholder that
    holds its position is the whole of what the render needs. A Mark with no text
    — an illegible signature — has its presence recorded by its graphic kind
    alone, which is what a reader needs to know.
    """
    zone.graphic_kind = response.graphic
    lines = [line for line in (raw.strip() for raw in response.text) if line]
    zone.blocks = (
        [Block(kind="caption", lines=[Cell(readings=[read(line)]) for line in lines])]
        if lines
        else []
    )
    return zone


EXTRACTION_SCHEMAS: dict[Kind, type[BaseModel]] = {
    Kind.TABLE: TableResponse,
    Kind.PAIRS: PairsResponse,
    Kind.PROSE: BlocksResponse,
    Kind.LIST: BlocksResponse,
    Kind.FIGURE: FigureResponse,
}
"""What each Kind is asked for. A Kind absent here has no Extractor yet."""
