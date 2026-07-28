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

from pydantic import BaseModel, Field

from .ir import BBox, Cell, Kind, Reading, Role, Row, RowRole, Zone

Read = Callable[[str], Reading]
"""Turns cell text into a Reading carrying its engine, model and prompt version.

Injected so the mapping functions stay pure: provenance belongs to whatever did
the reading, and a mapper that reached for it would need an Engine to test.
"""

GRAPHIC_KINDS = ("logo", "chart", "signature", "stamp", "badge")
"""What a figure may be. `stamp`, `signature` and `badge` are Marks: their text
is document content and is captured. A logo is a Graphic and its wordmark is
part of the artwork, so it is not."""


class MappingError(ValueError):
    """A schema-valid response that does not describe the page.

    Always names the Zone it was reading, so a failure points at a region of the
    document rather than at a line of parser.
    """


class WireZone(BaseModel):
    """One region, as a model reports it. Flat on purpose: scalars only."""

    kind: Literal["table", "pairs", "prose", "list", "figure"]
    role: Literal["header", "body", "summary", "footer"]
    band: int = Field(description="Horizontal stripe, numbered from 0 at the top")
    column: int = Field(description="Position within the band, from 0 at the left")
    left: float
    top: float
    right: float
    bottom: float
    title: str = Field(description="Heading printed above and belonging to this "
                                   "region; empty string if there is none")
    graphic: str = Field(description="For a figure: one of logo, chart, "
                                     "signature, stamp, badge. Empty otherwise")


class LayoutResponse(BaseModel):
    """The layout pass: where the regions are, and nothing about their contents."""

    zones: list[WireZone]


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
            if earlier.bbox and later.bbox and not _overlaps_vertically(
                earlier.bbox, later.bbox
            ):
                raise MappingError(
                    f"band {index}: Zones in columns {earlier.column} and "
                    f"{later.column} do not overlap vertically, so they are not "
                    "side by side"
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
    """
    if not response.rows:
        _no_content("table", "no rows")

    header = next((r for r in response.rows if r.role == "header"), None)
    width = len(header.cells) if header else None

    rows = []
    for index, wire in enumerate(response.rows):
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


def _no_content(kind: str, what: str) -> NoReturn:
    raise MappingError(
        f"{kind} Zone came back with {what} — the layout pass said there is "
        "content here, so an empty answer is a failure rather than a finding"
    )


def contents_into(zone: Zone, content: str, *, read: Read) -> Zone:
    """Validate an extraction response for this Zone's Kind and fill it in.

    One function rather than a branch in the Engine: which schema a Kind is read
    with, and how that answer becomes IR, are the same decision and belong
    together.
    """
    if zone.kind is Kind.TABLE:
        zone.rows = rows_from_table(
            TableResponse.model_validate_json(content), read=read
        )
    else:
        raise NotImplementedError(f"{zone.kind.value} extraction not yet wired")

    zone.complete = True
    return zone


EXTRACTION_SCHEMAS: dict[Kind, type[BaseModel]] = {
    Kind.TABLE: TableResponse,
}
"""What each Kind is asked for. A Kind absent here has no Extractor yet."""
