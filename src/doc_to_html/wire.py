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

from typing import Any, Callable, Literal, NoReturn

from pydantic import BaseModel, Field, ValidationError

from .ir import BBox, Block, Cell, Kind, Pair, Reading, Role, Row, RowRole, Zone

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
    resolution and answers about structure. Issue #13 measured why that matters —
    a Zone asked about on its own is classified correctly at a resolution where
    the same Zone, asked about as one of seven, is not.

    Three scalars and no list: the whole question is an enum, and the flattest
    schema in this file reads the page best.
    """

    kind: Literal["table", "pairs", "prose", "list", "figure"]
    title: str = Field(
        default="",
        description="Heading printed above this region and belonging to it; "
                    "empty string if there is none",
    )
    graphic: Literal["", "logo", "chart", "signature", "stamp", "badge"] = Field(
        default="",
        description="What a figure is. Empty string for every other kind",
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


def _validate_bands(zones: list[Zone]) -> None:
    """Bands must be horizontal stripes, read top to bottom, left to right.

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


def zones_from_layout(response: LayoutResponse) -> list[Zone]:
    """Map a layout response onto Zones. Pure, and the place validation lives.

    Zones come back incomplete: this pass reports where content is, never what
    it says. They render as skeletons until an Extractor fills them.
    """
    if not response.zones:
        raise MappingError(
            "layout returned no Zones — there is nothing to show, so the "
            "Conversion cannot continue"
        )

    zones = []
    for index, wire in enumerate(response.zones):
        where = f"zone {index} ({wire.kind}, band {wire.band} column {wire.column})"
        graphic = wire.graphic.strip().lower()
        if graphic and graphic not in GRAPHIC_KINDS:
            raise MappingError(
                f"{where}: graphic {wire.graphic!r} is not one of {GRAPHIC_KINDS}"
            )
        zones.append(
            Zone(
                kind=Kind(wire.kind),
                role=Role(wire.role),
                band=wire.band,
                column=wire.column,
                bbox=_validate_box(wire, where),
                title=wire.title.strip() or None,
                graphic_kind=graphic or None,
            )
        )

    _validate_bands(zones)
    return zones


def classification_into(zone: Zone, content: str) -> Zone:
    """Apply one Zone's classification to it. Pure, and where validation lives.

    The Kind that arrives is discarded rather than reconciled. Geometry's guess
    was made from a downscaled page and is the thing this pass exists to replace;
    keeping it as a tie-breaker would reintroduce the answer being corrected.

    The Zone is *not* marked complete. A Kind is not contents — it says which
    Extractor to run, and a Zone marked complete here would never be read.
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
    zone.title = response.title.strip() or None
    zone.graphic_kind = graphic or None
    return zone


def rows_from_table(response: TableResponse, *, read: Read) -> list[Row]:
    """Map a table response onto Rows.

    Two things a schema cannot check are checked here. That the region had any
    rows at all: an empty table rendered as a table looks like a document that
    had one. And that data rows are as wide as the header, which is how a dropped
    or invented cell shows up — it shifts every value after it into the wrong
    column, and the numbers stay individually plausible.

    A summary row is allowed to be narrower. Totals rows merge cells as a matter
    of course, and rejecting that would reject the fixture this project is held
    to.

    A header row split one cell per row is put back together first — see
    `_join_split_header_row`.
    """
    if not response.rows:
        _no_content("table", "no rows")

    wire_rows = _join_split_header_row(response.rows)

    header = next((r for r in wire_rows if r.role == "header"), None)
    width = len(header.cells) if header else None

    rows = []
    for index, wire in enumerate(wire_rows):
        if width is not None and (
            len(wire.cells) > width
            or (wire.role != "summary" and len(wire.cells) != width)
        ):
            raise MappingError(
                f"table row {index} has {len(wire.cells)} cells but the header "
                f"has {width} — a dropped or invented cell shifts every value "
                "after it into the wrong column"
            )
        rows.append(
            Row(
                role=RowRole(wire.role),
                cells=[Cell(readings=[read(text)]) for text in wire.cells],
            )
        )
    return rows


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
            raise MappingError(
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
