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

RECTIFIER_VERSION = 3
"""Bump when rectification changes geometrically.

Corrections are anchored to coordinates in the rectified space. If rectification
starts producing a different mapping from source pixels, previously recorded
Corrections point somewhere else — so they must be treated as orphaned rather
than silently re-attached to the wrong cell.

**3** is spec 0007 Phase A-1 turning a light-on-dark page over before
equalisation — see `preprocess.ground_is_dark`. The coordinates are untouched,
so this bump is stricter than the rule above requires; the *values* at those
coordinates change, and a human ruling made against a dark page was made against
different pixels.
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


INLINE_KINDS = ("text", "link", "code", "strong", "em", "mark")
"""What a `Run` may be. `text` is unmarked; the rest are `scoring.INLINE_KINDS`.

The set is closed and it matches the scorer's, so a kind that cannot be scored
cannot be produced.
"""


@dataclass(frozen=True)
class Run:
    """A stretch of a Cell's text set apart from the rest of it.

    **Added in Phase A1, 2026-09-24.** Before it, a Cell was a flat string and
    every link, code span and badge in the corpus was lost — T6 scored 0 of 42
    across eight documents, a 100% loss, because nothing downstream of the
    model could express one.

    A Run is display, never content: `"".join(run.text for run in runs)` is the
    Cell's text, so marking cannot add or remove a word. `Cell.runs` enforces
    that by falling back to one unmarked Run whenever the parts do not spell
    the whole.
    """

    text: str
    kind: str = "text"


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
    runs: list[Run] = field(default_factory=list)
    """How the text is marked up, or empty for text that carries no marking.

    Empty is not "unknown" — it is the ordinary case, and it renders exactly as
    this Reading rendered before Runs existed.
    """


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

    @property
    def runs(self) -> list[Run]:
        """The accepted reading's marked-up form, or one unmarked Run.

        **Marking may never change the words.** If the Runs do not concatenate
        to exactly `text`, they are discarded in favour of the plain text: a
        model that returns a span not present in what it read must not be able
        to edit the reading through the back door. That check is the reason
        this is a property rather than a stored field.
        """
        text = self.text
        runs = self.readings[0].runs if self.readings else []
        if runs and "".join(run.text for run in runs) == text:
            return list(runs)
        return [Run(text=text)] if text else []


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
    """One of: heading, paragraph, address, item, caption, quote, attribution,
    mark. The closed set a model may return is `wire.WireBlock.kind`."""

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
    """For FIGURE Zones, one of `wire.GRAPHIC_KINDS`.

    A decorative rule is not among them: a Separator produces no Zone at all.
    """

    pixels: str | None = None
    """A FIGURE Zone's own pixels, as a base64 PNG. See `preprocess.figure_pixels`.

    **Added in spec 0007 Phase A3, 2026-09-26.** Before it a FIGURE Zone was a
    label, and the render stood a dashed placeholder where the logo was — the
    scorer counted `invoice_0001`'s logo as lost, and the placeholder printed
    words the page shows only as pixels: `sparksuite`, and `logo` on
    `receipt_0010`'s barcode.

    **Embedded rather than a file beside the document**, decided on entry: a
    rendered file is copied alone into `tests/frozen/` and into the ratchet's
    run directories, and an image beside it would fail to load there and be
    scored as lost again. Measured over the corpus the cost is 6.1 KB for the
    logo, 0.7 KB for the barcode and 1.5 KB for the ACME tile, each carried
    twice — once here and once in the `<img>`.

    `None` for every other Kind, and for a figure with no box to crop.
    """

    fill: tuple[int, int, int] | None = None
    """The Zone's own background, where the source draws one. See `style.chrome`.

    `None` means the Zone sits directly on the page, which is what most Zones in
    the corpus do — so an unmeasured Zone and a plain one render identically,
    and nothing invents a fill.
    """

    title_fill: tuple[int, int, int] | None = None
    """The Title band's own background, where it differs from the Zone's.

    Separate from `fill` because they are separate observations and the
    renderer got this exact thing wrong: it shaded every Zone Title
    unconditionally, painting a full-width blue banner across
    `sample_css_0004`'s cards and heavy grey bars over `receipt_0010`, which
    draws no fill anywhere on the page.
    """

    header_fill: tuple[int, int, int] | None = None
    """A table's header row's own background, where it differs from the rows
    under it. The title bar's measurement, pointed at the row `RowRole.header`
    names — see `preprocess.header_band`.

    `nonlatin_0014` prints its header row white on `#1c4f7c`, and the renderer
    drew every header row on the house's pale `--shade` whatever the source did.
    """

    boxed: bool = False
    """Whether the source draws a rule around this Zone. See `style.chrome`.

    `False` by default for the same reason as `fill`: `render.py` borders every
    titled Zone unconditionally, and the default must not reintroduce the fault
    it exists to fix.
    """

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

    ink_share: float = 0.0
    """How much of the page's printed ink is in here, from 0 to 1.

    Spec 0007 Phase A-1's honesty rule: a finding about missing content has to
    say *how much*. Without it, one sentence — "found by ink coverage, so it may
    be a mark" — stood over every Gap at every size, which is right about a
    stray glyph and a lie about a page.

    **Of the uncovered ink, not of the rectangle**, and `preprocess`
    `uncovered_regions` is what measures it. On `receipt_0010` the grouping
    kernel welds the page's leftover edges into one component whose box is the
    whole page; measured over the box it holds 100% of the page's ink, and
    measured over the pixels, 18%.
    """


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
    ink_share: float = 0.0
    """How much of the page's printed ink this Zone holds. See `Gap.ink_share`."""


@dataclass
class Shortfall:
    """A Zone that was read, and read short.

    The finding with no other home. A Failure has no content and renders a
    skeleton; a Caveat has content and a qualifier on how it was obtained. This
    is a Zone that has content, is marked `complete`, is named by no Failure —
    and holds visibly less than the crop it was read from. Every other check in
    the system passes it, because every other check reasons from the answer
    outward and the answer is internally consistent.

    Filed under "Unresolved" in the render rather than under "Read with a
    caveat", because content that did not arrive is not a qualifier on content
    that did. That distinction is the whole of spec 0007 Phase A-1's honesty
    rule: `darkdeck_0009` lost 80% of its document and said nothing at all.

    `printed_lines` is measured off the pixels by `preprocess.printed_lines` and
    is a floor, not an expectation — a wrapped cell is two printed lines in one
    row. See `orchestrator.shortfall` for how coarse the comparison deliberately
    is.
    """

    zone_index: int
    kind: str
    printed_lines: int
    read_lines: int
    ink_share: float = 0.0


@dataclass
class Caveat:
    """Something worth knowing about *how* a Zone was read, on one that was read.

    The opposite of a Failure rather than a milder version of it: a Failure has no
    content and renders a skeleton, a Caveat has content and a note. Keeping them
    apart is what stops a render saying a Zone "could not be read" directly above
    the content it read.
    """

    zone_index: int
    kind: str
    note: str


@dataclass
class Style:
    """What the page looks like, measured from its own pixels. See ADR 0005.

    Part of the IR rather than a renderer detail, for the reason ADR 0005
    gives: a stylesheet cannot react to a quantity nothing records. The
    renderer reacts to this exactly as it reacts to Kind, Role and Title.

    Every field has a default that is the renderer's own existing look, so a
    `Document` with no Style — a hand-built one in a test, an older IR read back
    off disk — renders as it always did.

    `accent` and `shade` are `None` when the page has neither, and that is a
    statement rather than a gap: a page with no hue anywhere must not have one
    invented for it, because the scorer will then find an accent in our output
    that the source does not have. See `style.MIN_ACCENT_SHARE`.
    """

    page_bg: tuple[int, int, int] = (255, 255, 255)
    ink: tuple[int, int, int] = (26, 26, 26)
    accent: tuple[int, int, int] | None = None
    shade: tuple[int, int, int] | None = None


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

    page_px: int | None = None
    """How wide the Source Image is, so the render can be that wide.

    `render.py` used to cap every document at a 52rem house column — about
    832px — and nine of the fifteen corpus sources are wider than that, up to
    1164px. Those pages rendered narrower than the source and therefore taller,
    which inflated `height_ratio`, which is the single best diagnostic the
    scorer produces. Width is carried and height is left to fall out; ADR 0005
    records why a *fixed* height is refused.

    `None` renders at the house column, so a Document built without one looks
    as it always did.
    """

    style: Style | None = None
    """The page's palette, measured from its pixels. `None` means not measured."""

    zones: list[Zone] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    probes: list[ProbeResult] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    caveats: list[Caveat] = field(default_factory=list)
    shortfalls: list[Shortfall] = field(default_factory=list)

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


def _colour(value: Any) -> tuple[int, int, int] | None:
    return None if value is None else (int(value[0]), int(value[1]), int(value[2]))


def _style(data: dict[str, Any] | None) -> Style | None:
    if not data:
        return None
    ground = _colour(data.get("page_bg")) or (255, 255, 255)
    ink = _colour(data.get("ink")) or (26, 26, 26)
    return Style(page_bg=ground, ink=ink,
                 accent=_colour(data.get("accent")),
                 shade=_colour(data.get("shade")))


def _bbox(data: dict[str, Any] | None) -> BBox | None:
    return BBox(**data) if data else None


def _reading(data: dict[str, Any]) -> Reading:
    """One Reading, with its Runs rebuilt as Runs.

    `Reading(**data)` would leave `runs` a list of plain dicts, which survives
    construction — a dataclass validates nothing — and fails much later, on the
    first `run.text` inside `Cell.runs`. Everything that reads an IR back out of
    a rendered file goes through here: `tools/remeasure_style.py`,
    `honesty.document_in`, `tools/inspect_run.py` and `cli --ir`.
    """
    fields = dict(data)
    runs = fields.pop("runs", []) or []
    return Reading(
        **fields,
        runs=[Run(text=r["text"], kind=r.get("kind", "text")) for r in runs],
    )


def _cell(data: dict[str, Any]) -> Cell:
    return Cell(
        bbox=_bbox(data.get("bbox")),
        readings=[_reading(r) for r in data.get("readings", [])],
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
        pixels=data.get("pixels"),
        # Named one by one, like every other field here, and the reason is on
        # record: A-1 shipped a decoder that silently dropped `Gap.ink_share`
        # because this function builds each object field by field.
        fill=_colour(data.get("fill")),
        title_fill=_colour(data.get("title_fill")),
        header_fill=_colour(data.get("header_fill")),
        boxed=data.get("boxed", False),
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
            # Field by field rather than `Gap(**g)` because `bbox` is a nested
            # object — which is also how `ink_share` came to be dropped on the
            # way back in, so that a Gap whose own note read "18.5% of this
            # page's printed ink" reported the share as 0.0 to anything reading
            # the IR instead of the prose. A finding and the number beside it
            # disagreeing is the exact shape of fault Phase A-1 exists to
            # remove, arriving through a decoder.
            Gap(bbox=BBox(**g["bbox"]), note=g.get("note"),
                resolved=g.get("resolved", False),
                ink_share=g.get("ink_share", 0.0))
            for g in data.get("gaps", [])
        ],
        page_px=data.get("page_px"),
        # Tuples come back from JSON as lists, so a `Style(**data["style"])`
        # would put `[255, 255, 255]` where a colour belongs and the renderer
        # would emit `rgb([255, 255, 255])`. A-1 shipped the same class of bug
        # once already, in this same function, by building `Gap` field by field
        # and forgetting one.
        style=_style(data.get("style")),
        failures=[Failure(**f) for f in data.get("failures", [])],
        caveats=[Caveat(**c) for c in data.get("caveats", [])],
        shortfalls=[Shortfall(**s) for s in data.get("shortfalls", [])],
    )


def cell(text: str, engine: str = "fixture", bbox: BBox | None = None) -> Cell:
    """Build a settled single-reading Cell. Convenience for fixtures and tests."""
    return Cell(bbox=bbox, readings=[Reading(engine=engine, text=text)])
