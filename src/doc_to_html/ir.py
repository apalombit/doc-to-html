"""The IR: everything the system learned from one Source Image.

Extractors write it, Probes test it, the renderer reads it. Nothing else in the
system touches pixels or HTML.

Every coordinate in here is normalised (0.0-1.0) against the *Rectified Image*,
never the raw photograph. That is what makes Corrections durable: the rectified
image is derived deterministically from the source, so a bounding box means the
same thing across runs even when the model carves the page up differently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

IR_VERSION = 1
"""Bump when the shape below changes incompatibly. Written into every IR."""

RECTIFIER_VERSION = 2
"""Bump when rectification changes geometrically.

Corrections are anchored to coordinates in the rectified space. If rectification
starts producing a different mapping from source pixels, previously recorded
Corrections point somewhere else — so they must be treated as orphaned rather
than silently re-attached to the wrong cell.
"""


class Kind(str, Enum):
    """What a Zone's content structurally is. Drives Extractor selection."""

    TABLE = "table"
    PAIRS = "pairs"
    PROSE = "prose"
    LIST = "list"
    FIGURE = "figure"


class Role(str, Enum):
    """What a Zone plays in the Document. Orthogonal to Kind; Probes navigate by it."""

    HEADER = "header"
    BODY = "body"
    SUMMARY = "summary"
    FOOTER = "footer"


class RowRole(str, Enum):
    """The same distinction one level down. Exists only inside a TABLE Zone."""

    HEADER = "header"
    DATA = "data"
    SUMMARY = "summary"


class CellState(str, Enum):
    """How a cell's readings were settled."""

    AGREED = "agreed"
    """Every Engine that read it returned the same text."""

    RESOLVED = "resolved"
    """Engines disagreed; Escalation produced a majority."""

    DISPUTED = "disputed"
    """The Ladder was exhausted and the readings still disagree."""

    CORRECTED = "corrected"
    """A human ruled on it. The rival readings are retained regardless."""


@dataclass(frozen=True)
class BBox:
    """A rectangle in normalised Rectified Image coordinates."""

    left: float
    top: float
    right: float
    bottom: float

    def overlap_ratio(self, other: BBox) -> float:
        """Intersection over the area of `self`.

        Used to re-attach a Correction to whichever cell now occupies the pixels
        it was anchored to, after a re-run produced a different Zone structure.
        """
        ix = max(0.0, min(self.right, other.right) - max(self.left, other.left))
        iy = max(0.0, min(self.bottom, other.bottom) - max(self.top, other.top))
        area = (self.right - self.left) * (self.bottom - self.top)
        return (ix * iy) / area if area > 0 else 0.0


@dataclass
class Reading:
    """One Engine's account of what a cell says.

    `prompt_version` and `model` are recorded so a regression can be attributed
    to a specific change rather than guessed at.
    """

    engine: str
    text: str
    model: str | None = None
    prompt_version: str | None = None


@dataclass
class Cell:
    """A single readable value, and every account of it."""

    bbox: BBox | None = None
    readings: list[Reading] = field(default_factory=list)
    state: CellState = CellState.AGREED

    @property
    def text(self) -> str:
        """The accepted reading. Corrections are applied by the renderer, not here."""
        return self.readings[0].text if self.readings else ""


@dataclass
class Row:
    """A table row. `role` is what keeps summary rows out of column sums."""

    cells: list[Cell] = field(default_factory=list)
    role: RowRole = RowRole.DATA


@dataclass
class Pair:
    """A label bound to a value, as in "Invoice No: INV-2026-0184"."""

    label: Cell
    value: Cell


@dataclass
class Block:
    """A unit of content inside a non-table Zone."""

    kind: str
    """One of: heading, paragraph, address, item, caption, mark."""

    lines: list[Cell] = field(default_factory=list)


@dataclass
class Zone:
    """A top-level region of the Document.

    Zones are a flat list — never nested. Horizontal arrangement is expressed
    only through `band`: two Zones sharing a band render as columns, ordered by
    `column`.
    """

    kind: Kind
    role: Role = Role.BODY
    band: int = 0
    column: int = 0
    bbox: BBox | None = None

    title: str | None = None
    """A heading belonging to this Zone rather than standing beside it.

    Panelled documents put a caption directly above a block — "Company Details"
    over its Pairs. Modelling that as a separate Zone in its own Band happens to
    render correctly only while neighbouring panels are the same height; binding
    the heading to the block it captions holds regardless.
    """

    rows: list[Row] = field(default_factory=list)
    """Populated when kind is TABLE."""

    pairs: list[Pair] = field(default_factory=list)
    """Populated when kind is PAIRS."""

    blocks: list[Block] = field(default_factory=list)
    """Populated when kind is PROSE, LIST, or FIGURE (a caption, if any)."""

    graphic_kind: str | None = None
    """For FIGURE Zones: logo, chart, rule, signature, stamp."""

    complete: bool = False
    """False while a Zone is detected but not yet extracted.

    Drafts render from incomplete IR, so nothing downstream may assume this is
    True. See docs/adr/0002 and the Draft entry in CONTEXT.md.
    """


@dataclass
class Correction:
    """A human ruling, anchored to pixels rather than to a position in the IR.

    Anchoring to geometry is what lets a Correction survive a re-run with
    different prompts: the Zone structure may change, but the Rectified Image
    does not. Every Correction is therefore also a ground-truth label.
    """

    bbox: BBox
    text: str
    replaced: str | None = None
    by: str = "human"
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ProbeResult:
    """The outcome of one arithmetic check.

    `expected` is recorded here for a human reader and for eval. It must never
    reach a prompt — see docs/adr/0004.
    """

    kind: str
    zone_index: int
    ok: bool
    computed: str | None = None
    stated: str | None = None
    detail: str | None = None


@dataclass
class Gap:
    """Content the Coverage Audit found outside every Zone."""

    bbox: BBox
    note: str | None = None
    resolved: bool = False


@dataclass
class Failure:
    """A Zone an Extractor could not fill, recorded rather than raised.

    Throwing away five Zones that extracted correctly because a sixth did not
    would destroy the evidence a run exists to produce. So the Zone stays
    incomplete, renders as a skeleton, and its reason is recorded here — which is
    what makes a skeleton in the render traceable to what went wrong rather than
    merely visible.
    """

    zone_index: int
    kind: str
    reason: str


@dataclass
class Source:
    """Provenance of the pixels."""

    path: str
    sha256: str
    width: int
    height: int
    rectified_width: int | None = None
    rectified_height: int | None = None


@dataclass
class Document:
    """The root of the IR."""

    source: Source
    ir_version: int = IR_VERSION
    rectifier_version: int = RECTIFIER_VERSION
    hint: str | None = None
    """Free prose from the operator. Reaches prompts; branches nothing."""

    zones: list[Zone] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    probes: list[ProbeResult] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)

    def bands(self) -> list[list[Zone]]:
        """Zones grouped into Bands and ordered for rendering."""
        by_band: dict[int, list[Zone]] = {}
        for zone in self.zones:
            by_band.setdefault(zone.band, []).append(zone)
        return [
            sorted(by_band[b], key=lambda z: z.column) for b in sorted(by_band)
        ]

    def correction_for(self, bbox: BBox, threshold: float = 0.5) -> Correction | None:
        """The Correction anchored to these pixels, if any.

        Matching by overlap rather than by identity is deliberate: it is what
        makes Corrections survive a layout that came out differently this run.
        """
        best, best_ratio = None, threshold
        for correction in self.corrections:
            ratio = bbox.overlap_ratio(correction.bbox)
            if ratio >= best_ratio:
                best, best_ratio = correction, ratio
        return best

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, default=_encode)

    @classmethod
    def from_json(cls, raw: str) -> Document:
        return _decode_document(json.loads(raw))


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"not JSON-serialisable: {type(value).__name__}")


def _bbox(data: dict[str, Any] | None) -> BBox | None:
    return BBox(**data) if data else None


def _cell(data: dict[str, Any]) -> Cell:
    return Cell(
        bbox=_bbox(data.get("bbox")),
        readings=[Reading(**r) for r in data.get("readings", [])],
        state=CellState(data.get("state", "agreed")),
    )


def _zone(data: dict[str, Any]) -> Zone:
    return Zone(
        kind=Kind(data["kind"]),
        role=Role(data.get("role", "body")),
        band=data.get("band", 0),
        column=data.get("column", 0),
        bbox=_bbox(data.get("bbox")),
        title=data.get("title"),
        rows=[
            Row(
                cells=[_cell(c) for c in row.get("cells", [])],
                role=RowRole(row.get("role", "data")),
            )
            for row in data.get("rows", [])
        ],
        pairs=[
            Pair(label=_cell(p["label"]), value=_cell(p["value"]))
            for p in data.get("pairs", [])
        ],
        blocks=[
            Block(kind=b["kind"], lines=[_cell(c) for c in b.get("lines", [])])
            for b in data.get("blocks", [])
        ],
        graphic_kind=data.get("graphic_kind"),
        complete=data.get("complete", False),
    )


def _decode_document(data: dict[str, Any]) -> Document:
    return Document(
        source=Source(**data["source"]),
        ir_version=data.get("ir_version", IR_VERSION),
        rectifier_version=data.get("rectifier_version", RECTIFIER_VERSION),
        hint=data.get("hint"),
        zones=[_zone(z) for z in data.get("zones", [])],
        corrections=[
            Correction(
                bbox=BBox(**c["bbox"]),
                text=c["text"],
                replaced=c.get("replaced"),
                by=c.get("by", "human"),
                at=c["at"],
            )
            for c in data.get("corrections", [])
        ],
        probes=[ProbeResult(**p) for p in data.get("probes", [])],
        gaps=[
            Gap(bbox=BBox(**g["bbox"]), note=g.get("note"), resolved=g.get("resolved", False))
            for g in data.get("gaps", [])
        ],
        failures=[Failure(**f) for f in data.get("failures", [])],
    )


def cell(text: str, engine: str = "fixture", bbox: BBox | None = None) -> Cell:
    """Build a settled single-reading Cell. Convenience for fixtures and tests."""
    return Cell(bbox=bbox, readings=[Reading(engine=engine, text=text)])
