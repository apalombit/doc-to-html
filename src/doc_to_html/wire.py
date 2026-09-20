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
shape, not sense — it cannot say that a bounding box lies on the page, that two
Zones numbered as one Band actually sit side by side, or that a row has as many
cells as the header. Those are checked here, and a failure names the Zone and
raises rather than being coerced into an empty result: a silently sparse
Document looks exactly like a sparse document.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Literal, NoReturn

from pydantic import BaseModel, Field, ValidationError

from .ir import BBox, Block, Cell, Kind, Pair, Reading, Role, Row, RowRole, Zone

log = logging.getLogger(__name__)

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
A Graphic — a logo, a chart's plotted area — is a placeholder holding its position,
and a logo's wordmark is part of the artwork rather than content.

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


class WireZone(BaseModel):
    """One region, as a model reports it. Flat on purpose: scalars only."""

    kind: Literal["table", "pairs", "prose", "list", "figure"]
    role: Literal["header", "body", "summary", "footer"]
    band: int = Field(description="Which group of side-by-side regions this "
                                  "belongs to, numbered from 0 at the top")
    column: int = Field(description="Position within the band, from 0 at the left")
    left: float
    top: float
    right: float
    bottom: float
    title: str = Field(description="Heading printed above and belonging to this "
                                   "region; empty string if there is none")
    graphic: Literal["", "logo", "chart", "signature", "stamp", "badge"] = Field(
        default="",
        description="What a figure is. Empty string for every other kind",
    )
    """Closed, so constrained decoding cannot produce anything else.

    Described as a free string with its values named only in the description,
    `qwen3-vl:4b` answered `"SPARKSUIT"` — the text it had read off the wordmark.
    That is the failure this project uses constrained decoding to make
    impossible, and it survived here because the field was typed `str`. The
    runtime check in `zones_from_layout` stays as belt and braces for an Engine
    that cannot constrain."""


class LayoutResponse(BaseModel):
    """The layout pass: where the regions are, and nothing about their contents."""

    zones: list[WireZone]


class ClassifyResponse(BaseModel):
    """What one Zone structurally is, decided from that Zone's own crop.

    Separate from `WireZone` rather than a subset of it, because the two passes
    are asked different questions about different pixels: geometry sees the whole
    page downscaled and answers about position, this sees one region at full
    resolution and answers about structure. See `CLASSIFY_PROMPT` for what was
    measured about that difference.

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


class WireRow(BaseModel):
    """One table row: a role and a flat list of cell strings."""

    role: Literal["header", "data", "summary"]
    cells: list[str]


class TableResponse(BaseModel):
    """A `table` Zone. Row Roles are asked for here because they are visible on
    the page — a shaded top row, a ruled-off total — and are what later keep a
    summary row out of a column sum."""

    rows: list[WireRow]


class WirePair(BaseModel):
    label: str
    value: str


class PairsResponse(BaseModel):
    """A `pairs` Zone: label/value bindings in reading order."""

    pairs: list[WirePair]


class WireBlock(BaseModel):
    """One block of text. `lines` preserves the line structure a reader sees, so
    a three-line address does not arrive as one run-on string."""

    kind: Literal[
        "heading", "paragraph", "address", "item", "caption", "quote",
        "attribution", "mark",
    ]
    lines: list[str]


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


def _validate_box(wire: WireZone, where: str) -> BBox:
    """A box must lie on the page and enclose some area.

    Coercing a bad box to something plausible would put content at coordinates
    nothing was read from, and every Correction anchored there afterwards would
    point at the wrong pixels.
    """
    values = {"left": wire.left, "top": wire.top,
              "right": wire.right, "bottom": wire.bottom}
    for name, value in values.items():
        if not 0.0 <= value <= 1.0:
            raise MappingError(f"{where}: {name}={value} is off the page")
    if wire.left >= wire.right or wire.top >= wire.bottom:
        raise MappingError(f"{where}: box encloses no area ({values})")
    return BBox(wire.left, wire.top, wire.right, wire.bottom)


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

    **Why derive at all, rather than take what the model said.** Band numbering
    is the part of the layout answer this project has watched break most often:
    five of the six prompt changes ever made to `LAYOUT_PROMPT` broke it, each
    time as collateral on a change that never mentioned it. And it is the one
    part that is fully determined by an answer the model already gives — the
    boxes. Runs 55 and 56 are the clearest case: correct boxes, correctly
    alternating columns, and a Band index that failed to increment between the
    first two rows, which cost both documents the whole Conversion.

    The model's own numbering is not lost: it is in the raw layout answer, which
    every run dumps as `00_layout.json`, so before and after stay comparable.
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

    It has two jobs now, depending on where the numbering came from. On the
    model's own numbering — the default — it is what it always was, the check
    below. Under `DTH_DERIVE_BANDS` it cannot fire, because the numbers are
    derived from the very boxes it checks them against; there it is a check on
    the derivation, and the day that rule is changed it is what says so.

    This is the check that catches a model which numbered Bands by reading order
    rather than by position, or grouped two Zones as side by side when one sits
    well below the other. Either produces geometry that is schema-valid and
    describes no page.
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


def zones_from_layout(response: LayoutResponse, *,
                      derive_bands: bool = False) -> list[Zone]:
    """Map a layout response onto Zones. Pure, and the place validation lives.

    Zones come back incomplete: this pass reports where content is, never what
    it says. They render as skeletons until an Extractor fills them.

    `derive_bands` replaces the model's Band and column numbering with numbering
    worked out from its own boxes — see `bands_from_boxes`. **Off by default**,
    which keeps this function's behaviour what it has always been: the model's
    numbering, checked by `validate_bands` and rejected when it describes no
    page. See `config.DEFAULT_DERIVE_BANDS` for what turning it on is measured
    against, and for what it has not been measured against, which is a live
    Conversion.
    """
    if not response.zones:
        raise MappingError(
            "layout returned no Zones — there is nothing to show, so the "
            "Conversion cannot continue"
        )

    boxes, built = [], []
    for index, wire in enumerate(response.zones):  # noqa: B007
        where = f"zone {index} ({wire.kind}, band {wire.band} column {wire.column})"
        graphic = wire.graphic.strip().lower()
        if graphic and graphic not in GRAPHIC_KINDS:
            raise MappingError(
                f"{where}: graphic {wire.graphic!r} is not one of {GRAPHIC_KINDS}"
            )
        boxes.append(_validate_box(wire, where))
        built.append((wire, graphic))

    # Band and column either come from the boxes or are taken as the model gave
    # them. See `bands_from_boxes` for the rule and the five fixtures it was
    # measured against. Everything else in the answer is the model's either way.
    placed = (
        bands_from_boxes(boxes) if derive_bands
        else [(wire.band, wire.column) for wire in response.zones]
    )
    zones = [
        Zone(
            kind=Kind(wire.kind),
            role=Role(wire.role),
            band=band,
            column=column,
            bbox=box,
            title=wire.title.strip() or None,
            graphic_kind=graphic or None,
        )
        for (wire, graphic), box, (band, column) in zip(built, boxes, placed)
    ]

    if derive_bands:
        moved = sum(
            1 for wire, (band, column) in zip(response.zones, placed)
            if (wire.band, wire.column) != (band, column)
        )
        if moved:
            log.info("DTH_DERIVE_BANDS is on: %d of %d Zones renumbered from "
                     "their boxes", moved, len(zones))

    validate_bands(zones)
    return zones


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
    `_join_split_header_row`.
    """
    if not response.rows:
        _no_content("table", "no rows")

    wire_rows = _join_split_header_row(_without_empty_rows(response.rows))
    if not wire_rows:
        _no_content("table", "nothing but empty rows")

    header = next((r for r in wire_rows if r.role == "header"), None)
    width = len(header.cells) if header else None

    rows = []
    for wire in wire_rows:
        cells = [Cell(readings=[read(text)]) for text in wire.cells]
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

    Returns one sentence per repaired row, each naming the row and how much.
    Empty for a table that needed none, which is the normal case.
    """
    header = next((row for row in zone.rows if row.role is RowRole.HEADER), None)
    if header is None:
        return []
    width = len(header.cells)
    notes = []
    for index, row in enumerate(zone.rows):
        if row.role is RowRole.SUMMARY:
            continue
        unread = sum(1 for cell in row.cells if not cell.readings)
        if unread:
            notes.append(
                f"row {index} came back {unread} cell(s) short of the header's "
                f"{width} and was padded rather than discarded — the values it "
                "does have may sit in the wrong columns"
            )
        elif len(row.cells) > width:
            notes.append(
                f"row {index} came back with {len(row.cells)} cells against the "
                f"header's {width} and was kept whole — every value is present, "
                "and the surplus means some of them may sit in the wrong columns"
            )
    return notes


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


def _without_empty_rows(rows: list[WireRow]) -> list[WireRow]:
    """Drop rows carrying no cells at all, before anything is checked.

    A row with **zero** cells is not the failure the width check below exists to
    catch. That check's reason is that "a dropped or invented cell shifts every
    value after it into the wrong column" — which is a statement about a row that
    has *some* cells and the wrong number of them, where there is no way to tell
    which column each surviving value belongs to. A row with none carries nothing
    to place, so dropping it moves no value into a wrong column. Every other row
    keeps the cells it arrived with.

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
    one cell out of two is still ambiguous and is still rejected. This only ever
    removes a row that says nothing.
    """
    return [row for row in rows if row.cells]


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
        pairs.append(Pair(label=Cell(readings=[read(label)]),
                          value=Cell(readings=[read(value)])))
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
            Block(kind=wire.kind, lines=[Cell(readings=[read(line)]) for line in lines])
        )
    return blocks


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
    return zone


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
