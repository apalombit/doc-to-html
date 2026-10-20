"""Sequences Extractors, routes Engines, owns every retry decision.

Retry logic lives here and nowhere else. An Extractor never decides to have
another go; a Probe never triggers its own re-read. One place knows about
Escalation, which is the difference between a system you can debug and one you
cannot.

A Conversion is a session rather than a function call, because a human may be
consulted partway through. Unattended callers pass NullHandler and get exactly
one round.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from . import fields as fields_module
from . import furniture as furniture_module
from . import locate as locate_module
from . import looks as looks_module
from . import probes as probe_module
from . import rhythm as rhythm_module
from . import spans as spans_module
from . import style as style_module
from .checkpoints import Answer, CheckpointHandler, NullHandler, Question
from .config import Settings, load
from .engines.base import LayoutEngine, VisionEngine
from .engines.ollama import OllamaEngine
from .extractors import for_kind, resolution_caveat
from .ir import (
    Caveat, Document, Failure, Furniture, Gap, Kind, Role, RowRole, Shortfall, Zone,
)
from .preprocess import (
    MIN_ZONE_INK,
    MODEL_INPUT_LONG_EDGE,
    PAD_X,
    PAD_Y,
    Drawn,
    EmptyZone,
    ImageArray,
    Rectified,
    TableGrid,
    caption_band,
    content_ink,
    crop,
    crop_row_as_fraction,
    figure_pixels,
    header_band,
    ink_fraction,
    hard_lines,
    ink_share,
    printed_lines,
    snap_to_ink,
    table_grid,
    long_edge_over_input_budget,
    rectify,
    uncovered_ink,
    uncovered_regions,
    zone_pixels,
)
from .render import render
from .structure import alike, cut_at_edges, separators, structure
from .trace import Change, Disposition, Stage, Trace
from .wire import (
    MappingError,
    NotPairs,
    bands_from_boxes,
    prints,
    table_repairs,
    validate_bands,
)

log = logging.getLogger(__name__)

MAX_ROUNDS = 5
"""A backstop, not a control.

Termination comes from every unresolved item exhausting its Ladder. If this cap
ever fires, a Rung is being retried when it should not be — that is a defect
report, not a normal outcome.
"""


class Rung(str, Enum):
    """One step on a Ladder, each tried at most once per item.

    Ordered by cost. Because nothing is ever retried identically, a Conversion
    terminates by exhausting Ladders rather than by counting rounds.
    """

    READ = "read"
    """Normal read, at the resolution the Extractor chose."""

    UPSCALE = "upscale"
    """Re-crop from the Rectified Image at full resolution and enlarge."""

    OTHER_ENGINE = "other-engine"
    """Put it to a different model family."""

    ASK_HUMAN = "ask-human"
    """Last resort, and only where a CheckpointHandler is present."""


@dataclass
class EngineSet:
    """Which model does what.

    Four roles, one model behind all of them today. Classification is separate so
    a model that locates blocks well and one that reads them well need not be the
    same; audit is separate because an auditor sharing the layout model's blind
    spot cannot catch what that blind spot missed. Neither separation is being
    *used* right now — `config.DEFAULT_CLASSIFY_MODEL` records what that costs
    for classification, `DEFAULT_AUDIT_MODEL` why it is only safe while the audit
    is a no-op.

    The Orchestrator batches by model, which is what keeps a mixed set
    affordable: every classification runs together, between all the layout work
    and all the extraction work, so pointing this role at a second model costs
    two model loads for the document rather than one per Zone. Two vision models
    resident at once does not fit in 8GB.
    """

    layout: LayoutEngine
    classify: VisionEngine
    extract: VisionEngine
    audit: VisionEngine


def default_engines(settings: Settings | None = None) -> EngineSet:
    """The Engines the resolved configuration asks for.

    Which model fills which role is configuration, not code — that is what lets
    a bake-off across models, or a move to Ollama Cloud, happen without an edit
    here. See `config` and `.env.example`.
    """
    resolved = settings or load()
    return EngineSet(
        layout=_layout_engine(resolved),
        classify=OllamaEngine.from_settings(resolved, resolved.classify_model),
        extract=OllamaEngine.from_settings(resolved, resolved.extract_model),
        audit=OllamaEngine.from_settings(resolved, resolved.audit_model),
    )


RETIRED_LAYOUT = frozenset({"", "none", "off"})
"""Spellings that used to select the vision model for geometry. Retired.

Spec 0007 Thread 0 deleted the vision layout path from every Conversion. It
raised `MappingError` on three of the five documents it was measured on and
matched none of them, where the detector converts all five, and keeping it
alive meant maintaining the vision layout prompt's schema through every IR change in
Thread A for no measured benefit.

Kept as a *name* so that a `DTH_LAYOUT_DETECTOR=none` left in somebody's shell
or dotenv says so, instead of being passed to `from_name` as the name of a
detector and failing somewhere less obvious."""


def _layout_engine(settings: Settings) -> LayoutEngine:
    """A trained detector. There is no longer another option.

    `config.DEFAULT_LAYOUT_DETECTOR` carries the measurement that decided it.

    Imported inside the call so `onnxruntime` stays an optional extra: a package
    that fails at import because a detector nobody asked for is unavailable
    would make the extra mandatory in practice.
    """
    from .engines.detector import from_name

    wanted = settings.layout_detector.strip()
    if wanted.lower() in RETIRED_LAYOUT:
        raise ValueError(
            f"DTH_LAYOUT_DETECTOR={settings.layout_detector!r} asks for the "
            "vision layout pass, which spec 0007 Thread 0 retired. Unset it, "
            f"or name a detector: heron, doclayout_yolo."
        )

    return from_name(wanted,
                     settings.detector_confidence or None,
                     heading_rule=settings.heading_rule,
                     prefer_container=settings.prefer_container)


def failed(index: int, zone: Zone, error: Exception, *,
           share: float = 0.0) -> Failure:
    """Record what went wrong on one Zone, in the form both passes report.

    Classification and extraction fail differently but report identically, and
    that is the contract rather than a coincidence: an operator reading the
    render should not have to know which pass gave up on a Zone to find out that
    one did. Naming the exception type matters — `MappingError` and
    `TruncatedResponse` are different problems with different fixes.

    `share` is how much of the page's ink the Zone holds, so the finding says
    how much was lost and not only that something was. Spec 0007 Phase A-1's
    honesty rule. It defaults to zero rather than being required, because a
    caller without the pixels to hand — a replayed response, a test — should
    still be able to record the failure it has.
    """
    return Failure(
        zone_index=index,
        kind=zone.kind.value,
        reason=f"{type(error).__name__}: {error}",
        ink_share=share,
    )


def _share_of(image: ImageArray, zone: Zone) -> float:
    """How much of the page's ink this Zone holds, or zero with no geometry."""
    return 0.0 if zone.bbox is None else ink_share(image, zone.bbox)


def _box_data(zone: Zone) -> dict[str, float] | None:
    """One Zone's rectangle as plain numbers, for the Trace.

    A dict rather than the `BBox` itself because `trace.py` serialises with
    `json.dumps` and holds no knowledge of the IR — the Trace is a record of what
    happened, not a second copy of the domain model.
    """
    if zone.bbox is None:
        return None
    return {
        "left": zone.bbox.left, "top": zone.bbox.top,
        "right": zone.bbox.right, "bottom": zone.bbox.bottom,
    }


def _crop_data(image: ImageArray, zone: Zone, *,
               skip_rows: int = 0) -> dict[str, object] | None:
    """The pixels a pass was actually shown, described.

    Which pixels, at what size, with what padding — the three things needed to
    tell "the model misread this" from "the model was shown the wrong thing", and
    a distinction this project has had to make from the raw dump more than once.
    The padding is recorded rather than assumed because a reader comparing two
    runs cannot know whether `PAD_X` moved between them.

    `skip_rows` is the caption band withheld from the Kind question. The `box`
    reported is the *shown* one, its top moved down to the cut, so the contact
    sheet draws the crop the model saw rather than the Zone's full extent — the
    two differ by exactly the band whose absence is the point of the change.
    """
    if zone.bbox is None:
        return None
    pixels = zone_pixels(image, zone)[skip_rows:]
    box = _box_data(zone) or {}
    if skip_rows:
        box["top"] = crop_row_as_fraction(image, zone.bbox, skip_rows)
    return {
        "width": pixels.shape[1], "height": pixels.shape[0],
        "box": box, "pad_x": PAD_X, "pad_y": PAD_Y,
        "skip_rows": skip_rows,
        "ink_fraction": round(ink_fraction(pixels), 4),
    }


def _drawn(image: ImageArray, zone: Zone,
           furniture: Sequence[Furniture]) -> Drawn | None:
    """What the page draws over a Zone's crop — spec 0012, G3b — or None
    where nothing was found, so the counts are taken as they always were."""
    if not furniture or zone.bbox is None:
        return None
    return furniture_module.drawn(furniture, image, zone.bbox)


def _grid(image: ImageArray, zone: Zone,
          furniture: Sequence[Furniture]) -> TableGrid:
    """A table Zone's grid, measured on its crop with the page's drawing
    known. What the Extractor's prompt states and the trace records."""
    return table_grid(zone_pixels(image, zone), _drawn(image, zone, furniture))


def _grid_data(image: ImageArray, zone: Zone,
               furniture: Sequence[Furniture] = ()) -> dict[str, int] | None:
    """What the *page* says a table's shape is, beside what the model returned.

    Recorded for table Zones only, so the contact sheet can put the two claims
    next to each other — *the page has 2 rows, the model returned 4* — which is
    the whole of the Zone 4 defect stated in one line. Without it a reader has to
    count rows off a crop by eye, which is how this went unnoticed for eight runs.

    Measured here rather than handed back from `extract_zone`, which measures the
    same crop to build its prompt when `DTH_TABLE_GRID_HINT` is on. Two calls to a
    pure function on identical pixels agree by construction, and that is cheaper
    than widening a shipping signature to carry a diagnostic out.
    """
    if zone.kind is not Kind.TABLE or zone.bbox is None:
        return None
    grid = _grid(image, zone, furniture)
    return {"rows": grid.rows, "columns": grid.columns}


def _why_kept(zones: list[Zone]) -> str:
    """Which of `snapped_or_original`'s two refusals fired.

    Both return the Engine's own list, so the caller cannot tell them apart by
    identity — and they are different findings. A Zone with no geometry is a
    layout problem; Bands going invalid is the snap being overruled by the
    guard written for exactly that.

    **Unless the Bands were invalid before the snap touched them.** Until
    2026-09-25 this said "snapping made the Bands invalid" on three corpus
    documents where the snap had returned every box unchanged: the detector
    had already handed over one Zone enclosed by another, and the snap was
    blamed for a fault it only reported. See `detector.without_enclosed`.
    """
    if not zones or any(zone.bbox is None for zone in zones):
        return "a Zone has no bbox, so there was nothing to snap it to"
    try:
        validate_bands(zones)
    except MappingError as exc:
        return (f"the Engine's own Bands are invalid ({exc}), so no snap of "
                "them could be valid either")
    return "snapping made the Bands invalid, so the Engine's geometry was kept"


def snapped_or_original(image: ImageArray, zones: list[Zone]) -> list[Zone]:
    """The Engine's Zones with their boxes moved onto the ink, or unchanged.

    **On by default as of run 49** — shipped once, reverted for a measured reason,
    kept as a setting so the revert could be re-examined rather than inherited,
    and turned back on once the two changes below removed what it had cost.

    Gate 1 passed on every field it was written to read — `covered` 0.82 -> 0.99,
    `splits` 46 -> 0, `zones` unchanged, and nothing worse on any of the five
    fixtures. Run 39 then converted the invoice with it wired in and went from
    **3 mismatches to 6**: Zone 5, the line-item table and the best box on the
    page at 0.83 IoU, stopped extracting — `table row 2 has 0 cells but the
    header has 2` — which also lost the column-sum Probe, the only arithmetic
    check the document has.

    Run 45 repeated that at a later commit and got the same six mismatches by the
    same route, so the regression is real and reproducible rather than one bad
    decode. What it costs is also narrower than the revert recorded, and both
    halves matter to whoever picks this up next:

    - All twelve classifications across the two snapped runs came back
      **identical** to run 43's unsnapped ones. The snap moves none of the
      document's three Kind mismatches and breaks none — consistent with run 42,
      which found the same from the true rectangles.
    - The table answers differ from run 43's by exactly **one row**, a spurious
      empty `data` row after `Website design`, in the same slot both times. That
      one row is the whole of the regression.

    **That one row is now gone twice over, which is what let this default back
    on.** `wire._without_empty_rows` drops a zero-cell row before the width check
    — a row with no cells has no value to put in the wrong column — and
    `DTH_TABLE_GRID_HINT` stops the model emitting it at all: run 49's raw table
    answers carry no empty row on either table.

    So the gate Gate 1 was missing — *no Zone that previously converted stops
    converting* — is met rather than argued around: run 49 has zero Failures,
    every Zone complete, and the column-sum Probe reconciling. Still one fixture;
    see `config.DEFAULT_SNAP_ZONES` for what that does and does not license.
    """
    boxes = [zone.bbox for zone in zones]
    if not zones or any(box is None for box in boxes):
        return zones

    snapped = snap_to_ink(image, [box for box in boxes if box is not None])
    moved = [replace(zone, bbox=box) for zone, box in zip(zones, snapped)]
    try:
        validate_bands(moved)
    except MappingError as exc:
        log.warning(
            "snapping the layout boxes to the ink made the Bands invalid (%s), "
            "so the Conversion continues on the geometry as the Engine returned "
            "it", exc,
        )
        return zones
    return moved


GAP_IS_CONTENT = 0.05
"""Above this share of the page's ink, a Gap is content rather than a mark.

A mark is a stamp, a signature, a logo's flourish — a small thing. Nothing that
holds a twentieth of everything printed on a page is one, and calling it one is
what let `receipt_0010` lose 77 of 103 tokens under a finding that hedged.

The threshold decides only the *wording* of a finding; the share is printed
either way, so a reader is never relying on where this sits.
"""

MIN_RECOVERED_INK = 0.02
"""How much of the page's ink a region must hold to be worth reading.

Below this it is not a block somebody missed; it is the edge of one. Measured
over the corpus on 2026-09-19, the only three documents with any uncovered ink
at all: `nonlatin_0014`'s unread title holds 0.037, `form_0007`'s 0.032, and
`receipt_0010`'s leftover dotted rules 0.015.
"""

MIN_RECOVERED_PX = 8
"""And it must be at least this tall, or there is nothing there to read.

**The guard the measurements asked for, and the one that is easy to leave
out.** Re-bounding a region to its own ink can produce a box two pixels tall —
`form_0007`'s is 2px by 585px — and that is not a region that was missed. It is
the top and bottom overflow of glyphs whose bodies lie inside a neighbouring
Zone's padded crop, which is to say ink the Extractor *was* shown. Promoting it
to a Zone would crop two pixels of paper, ask a vision model what it says, and
get an answer, which is the failure `empty_zone` exists to prevent arriving by
a new route.

Eight pixels is under the height of any line of type on a rectified page in
this corpus and over the height of a glyph's overflow, and nothing in the
corpus sits near it: the regions measured are 2px, 1px and 15px.
"""

MAX_RECOVERED = 6
"""How many Zones one page may gain from uncovered ink.

A ceiling on a repair: a detector that has missed six separate regions has
not missed a block, it has failed, and adding a seventh Zone is not the answer
to that. The largest are
kept, because ink area is the only ranking available before anything is read.
"""

MAX_RECOVERED_SHARE = 0.80
"""A recovered box covering more than this much of the page is the page.

The same guard, and the same number, as the OpenCV rectangle finder's. It was
written there because an unguarded whole-page rectangle took `invoice_0001` from
6 Zones to 1; here it stops a page whose detector returned almost nothing from
being "recovered" as a single Zone holding everything, which is exactly the
silent whole-page failure `darkdeck_0009` already showed.
"""


def _ink(rectified: Rectified) -> ImageArray:
    """The picture the ink measures take — `Rectified.ink`, spec 0018, A1:
    each fill the page draws read against its own ground."""
    return rectified.ink if rectified.ink is not None else rectified.image


def _ground(rectified: Rectified, document: Document, zones: Sequence[Zone]) -> None:
    """Set `Rectified.ink` for these Zones: every fill none of them holds
    read as ground (`furniture.grounded`). Without the page's furniture —
    no Style Record — the ink measures read `image`, as before."""
    if not document.furniture:
        rectified.ink = None
        return
    plain = rectified.plain if rectified.plain is not None else rectified.image
    rectified.ink = furniture_module.grounded(
        rectified.image, plain, document.furniture, inverted=rectified.inverted,
        held=[zone.bbox for zone in zones if zone.bbox is not None])


def recovered_zones(image: ImageArray, zones: list[Zone]) -> list[Zone]:
    """The Zones, plus one for each substantial patch of ink none of them covers.

    **What this fixes.** `uncovered_ink` has always been able to see content the
    layout pass missed — it is the only check in the system that can — and until
    spec 0007 Phase A-1 the only thing done with it was to print a Gap saying so
    and carry on. On `receipt_0010` that meant keeping the header and dropping
    everything from the first line item to the barcode, 77 of 103 tokens, under
    a finding that called it a possible mark. The ink was found. Nothing read it.

    **The repair is to ask, not to assume.** A recovered box becomes an ordinary
    Zone with a placeholder Kind, so `_classify` decides what it is from its own
    crop and an Extractor reads it, exactly as for a detected region. Nothing
    here judges content.

    Five guards, each refusing in the direction that costs least:

    - `uncovered_regions`' own `MIN_GAP_AREA`, which is what separates a patch
      from a stray word.
    - `MIN_RECOVERED_INK` and `MIN_RECOVERED_PX`, which together are the
      difference between a block somebody missed and the two-pixel overflow of
      glyphs whose bodies are inside a neighbouring crop.
    - `MAX_RECOVERED_SHARE`, so a box that is the page is not mistaken for a
      region of it.
    - `MAX_RECOVERED`, so a detector that failed wholesale is reported rather
      than papered over.
    - **Bands must stay valid.** The combined boxes are renumbered by
      `bands_from_boxes` and validated; a recovered box that cannot sit in a
      legal Band is dropped — the one holding least ink first — until the rest
      can. A Zone recovered at the cost of invalidating the page's whole Band
      structure is not a repair.

    Returns the Zones unchanged when nothing qualifies, which is the normal
    answer on a page the detector covered — all five original documents.
    """
    boxes = [zone.bbox for zone in zones if zone.bbox is not None]
    if len(boxes) != len(zones) or not zones:
        # Nothing to subtract from, so nothing here can be called uncovered.
        return zones

    height = image.shape[0]
    found = [
        (box, share) for box, share in uncovered_regions(image, boxes)
        if (box.right - box.left) * (box.bottom - box.top) <= MAX_RECOVERED_SHARE
        and share >= MIN_RECOVERED_INK
        and (box.bottom - box.top) * height >= MIN_RECOVERED_PX
    ]
    # Ranked by the ink each holds rather than by area, so the ceiling keeps the
    # regions that carry the most content and not the ones that are widest.
    found.sort(key=lambda item: item[1], reverse=True)
    candidates = [box for box, _ in found[:MAX_RECOVERED]]

    while candidates:
        combined = zones + [
            Zone(kind=Kind.PROSE, role=Role.BODY, bbox=box) for box in candidates
        ]
        placed = bands_from_boxes([zone.bbox for zone in combined
                                   if zone.bbox is not None])
        renumbered = [
            replace(zone, band=band, column=column)
            for zone, (band, column) in zip(combined, placed)
        ]
        # A recovered Zone landing in Band 0 is a header, matching
        # `detector._role`'s rule that the top Band of a page is its header.
        # Only ever a promotion: a detected Zone that keeps a Role it was given
        # by its own class name keeps it, because that reading is better
        # evidence than a Band index. Role is a CSS class in `render.py` and
        # nothing navigates by it, so little rests on either.
        renumbered = [
            replace(zone, role=Role.HEADER if zone.band == 0 else zone.role)
            if zone.role is Role.BODY else zone
            for zone in renumbered
        ]
        try:
            validate_bands(renumbered)
        except MappingError as exc:
            log.info("a recovered region cannot sit in a valid Band (%s), so "
                     "the one holding least ink is dropped and the rest "
                     "retried", exc)
            candidates.pop()
            continue
        return renumbered
    return zones


SHORTFALL_RATIO = 0.6
"""How much of a crop's printed lines a reading may fail to return before the
Zone is reported as read short.

**Deliberately coarse, and coarse in one direction.** `printed_lines` counts
bands of ink and a reading counts rows, pairs or lines, and the two disagree
honestly all the time: a wrapped table cell is two printed lines in one row, a
caption is a line that is no row at all, and a `pairs` region puts a label and
its value on one line. Every one of those makes the reading look short when it
is not. So this is set where only a gross shortfall survives — a reading that
returned less than three fifths of what is printed, and at least
`SHORTFALL_LINES` lines fewer.

The number it exists to catch is not near the boundary: `statement_0006`'s
discarded table was 36 rows against 2, and `darkdeck_0009` was a whole page
against one Zone's worth. A finding that fires on a wrapped cell would be a
finding nobody reads.
"""

SHORTFALL_LINES = 2
"""And at least this many lines short, so a one-line disagreement cannot trip it.

**Two rather than three, and the measurement that moved it.** On the A-1 smoke
run over `darkdeck_0009`, taken 2026-09-19, the per-Zone counts were within one
line either way on ten of thirteen Zones — Zones 0 and 3 read *more* lines than
are printed, which is what a wrapped line looks like from this side — and Zone 4
read **one of its three**. At three lines short that Zone said nothing and the
document lost 7% of its tokens in silence; at two it declares itself.

One line short stays invisible on purpose. The counts genuinely disagree by one
in both directions, so a finding there would fire on correct readings, and a
list of findings that includes correct readings is a list nobody finishes.

**Tables and pairs only, since 2026-09-30.** A prose or list Zone is counted in
its Extractor's own unit and held to `SHORTFALL_HARD_LINES`.
"""

SHORTFALL_HARD_LINES = 1
"""How many lines short a prose or list Zone must be: one, because its printed
lines are counted as its Extractor counts them, by `preprocess.hard_lines`.

The disagreement `SHORTFALL_LINES` leaves room for is a wrapped line, and for
these two Kinds it is gone: `PROSE_PROMPT` asks for the lines the document
breaks, not the lines the type wraps onto, and `hard_lines` counts the same.
**Measured over the control, `tests/frozen/q5-result/`, on 2026-09-30.**
Counting printed lines at two short, `invoice_0002` Zone 7 and
`newsletter_0008` Zone 15 were reported — each one paragraph read whole, every
word there. Counting printed lines at one short would have reported eight
Zones, six of them a paragraph or a bullet that wrapped. Counting hard lines at
one short reports exactly two, `darkdeck_0009` Zones 4 and 10, and each lost
its heading — `Open risks` and `Decisions wanted`, a bullet wrapped under each.
The second of those was reported by nothing before.
"""


def read_lines(zone: Zone) -> int:
    """How many lines of content this Zone's reading came back with.

    Counted per Kind because the Kinds count differently, and a Title counts as
    the printed line it is: `printed_lines` sees it, so a comparison that did
    not would report every captioned Zone as one line short.
    """
    lines = 1 if zone.title else 0
    if zone.kind is Kind.TABLE:
        return lines + len(zone.rows)
    if zone.kind is Kind.PAIRS:
        return lines + len(zone.pairs)
    return lines + sum(len(block.lines) for block in zone.blocks)


def body_px(image: ImageArray, zones: list[Zone], source_width: int) -> float | None:
    """The body size to draw, in the source's pixels, to the half pixel.

    Measured on the rectified image and scaled by the source's width over its
    width, because the render is laid out at the source's width — so a
    photographed page, warped to its paper, is sized as that paper filling
    the page. See `style.EM_PER_GLYPH`.
    """
    glyph = style_module.body_glyph(image, zones)
    if glyph is None or not image.shape[1]:
        return None
    return float(round(glyph * style_module.EM_PER_GLYPH
                       * source_width / image.shape[1] * 2) / 2)


def shortfall(image: ImageArray, zone: Zone, index: int,
              furniture: Sequence[Furniture] = ()) -> Shortfall | None:
    """Whether this Zone was read short of what is printed in it.

    The honesty rule's last mile, and the only check in the system that can see
    a Zone which was read, marked complete, and came back holding a fraction of
    its own crop. Everything else reasons from the answer outward, so a reading
    that dropped thirty rows is internally consistent with itself.

    **`figure` Zones are exempt, and that is not a loophole.** A Graphic's
    wordmark is part of the artwork and is deliberately not read — see
    `wire.MARKS` — so a logo tile reads as several printed lines and zero
    content by design. Flagging it would put a finding on correct behaviour, and
    a finding that fires on correct behaviour is how the whole list stops being
    read.

    An incomplete Zone is exempt too: it already has a Failure naming it, and
    two findings for one loss is one finding too many.

    **A prose or list Zone is counted in the unit its Extractor was asked
    for** — lines the document breaks, a wrapped line once — and so is held
    to one line short, not two. See `SHORTFALL_HARD_LINES` for what that
    changed on the corpus.
    """
    if zone.kind is Kind.FIGURE or not zone.complete or zone.bbox is None:
        return None
    crop = zone_pixels(image, zone)
    # Spec 0012, G3b: the lines counted without the rules the page draws.
    drawn = _drawn(image, zone, furniture)
    if zone.kind in (Kind.PROSE, Kind.LIST):
        printed, margin = hard_lines(crop, drawn), SHORTFALL_HARD_LINES
    else:
        printed, margin = printed_lines(crop, drawn), SHORTFALL_LINES
    got = read_lines(zone)
    if printed - got < margin or got >= SHORTFALL_RATIO * printed:
        return None
    return Shortfall(
        zone_index=index, kind=zone.kind.value,
        printed_lines=printed, read_lines=got,
        ink_share=ink_share(image, zone.bbox),
    )


def gaps(image: ImageArray, zones: list[Zone]) -> list[Gap]:
    """Type no Zone covers, each patch with how much of the page's ink it holds.

    `Conversion._audit` says what this can and cannot see. Asked `type_only`,
    so the page's own edge and a panel's solid fill are not reported as
    content — see `preprocess._uncovered_mask` for the two findings that did.
    """
    boxes = [zone.bbox for zone in zones if zone.bbox is not None]
    # The note says how the finding was made, because that is what bounds
    # how far to trust it — a threshold on dark pixels found this, so a
    # small patch may be a Mark rather than lost content.
    #
    # **And it says how much, which it did not until spec 0007 Phase A-1.**
    # The old note was "found by ink coverage, so it may be a mark" at every
    # size, and on `receipt_0010` that sentence stood over three quarters of
    # the document. A hedge that is right about a stray glyph is a lie about
    # a page, so the hedge is now attached to the size it is true of.
    # The share is of the *uncovered ink*, not of the rectangle. Asked about
    # the rectangle, `receipt_0010`'s grouped edge scraps come back as the
    # whole page holding 100% of its ink — a finding that would be false in
    # the one direction this phase exists to prevent.
    return [
        Gap(bbox=box, ink_share=share,
            note=(
                f"{share * 100:.1f}% of this page's printed ink is in here "
                + ("— far too much to be a mark, so this is content nothing "
                   "read" if share >= GAP_IS_CONTENT else
                   "— found by ink coverage, so it may be a mark")
            ))
        for box, share in uncovered_regions(image, boxes, type_only=True)
    ]


def empty_zone(image: ImageArray, zone: Zone) -> EmptyZone | None:
    """Whether this Zone's crop is blank, and so holds nothing to classify.

    The first check in the pipeline that reads the pixels back. Every other
    safeguard compares the model's answer to another part of the model's answer,
    so a Zone placed where nothing is printed satisfies all of them: it can sit
    in a legal Band, carry a plausible Kind, and reach an Extractor.

    What that costs is measured. In `debug/runs/25-invoice-qwen35-longedge768/`
    the geometry pass returned six boxes that passed `validate_bands` and
    collapsed every region to a single line; two of the crops carried 0.0% ink.
    The classifier was asked what Kind of content a blank image holds and said
    `prose`; the prose Extractor was handed the same blank image and returned
    "The following is a sample paragraph. Heading". Neither call malfunctioned.
    Both were asked a question with no true answer, and a question with no true
    answer gets an invented one.

    So this rejects the question rather than the answer, and it returns the
    exception instead of raising it because the caller is a loop that must record
    a Failure and carry on to the next Zone — one blank crop does not cost the
    document.

    Returns None for a Zone with no bbox: that is `NoGeometry`'s business, and
    `zone_pixels` reports it with the better message.
    """
    if zone.bbox is None:
        return None
    fraction = ink_fraction(zone_pixels(image, zone))
    if fraction >= MIN_ZONE_INK:
        return None
    return EmptyZone(
        f"the crop for this Zone is blank — {fraction * 100:.2f}% ink, under the "
        f"{MIN_ZONE_INK * 100:.2f}% a Zone must carry. Geometry placed a region "
        "where nothing is printed, so there is nothing here to read"
    )


def classification_caveat(image: ImageArray, zone: Zone) -> str | None:
    """Whether this Zone's Kind was decided below the resolution it deserved.

    The counterpart of `resolution_caveat`, over the same pixels — but a
    different loss, and therefore a different test. Extraction shrunk past the
    budget can drop rows, so it measures height. A Kind decided on a shrunk crop
    loses the evidence that separates two Kinds — a shaded heading row over a
    data row, against two label/value lines, is a distinction made of a few
    pixels of grey — and that goes just as readily to a horizontal shrink, so
    this measures the long edge. See `long_edge_over_input_budget`: sharing
    extraction's height test here would say nothing about the full-width Zone,
    which is the commonest shape in the project.

    The Zone keeps the Kind either way. A degraded reading beats none, and a
    Zone with no Kind has no Extractor to route it to — so this is a note on an
    answer, not a rejection of one.

    Here rather than beside `resolution_caveat` in `extractors.py` because this
    is not an Extractor's business: the classification pass has no Extractor,
    and each caveat sits with the pass that earns it.
    """
    longest = long_edge_over_input_budget(image, zone)
    if longest is None:
        return None
    return (
        f"classified at reduced resolution: the crop's {longest}px long edge is "
        f"over the model's {MODEL_INPUT_LONG_EDGE}px input budget, so the Kind "
        "was decided on a shrunk crop"
    )


@dataclass
class Conversion:
    """One run over one Source Image.

    Multi-page is deliberately out of scope: a Conversion is strictly one image.
    Admitting page 2 later means growing the IR a `pages` array and revising
    every fixture — a known, accepted cost rather than an oversight.
    """

    source: Path
    engines: EngineSet = field(default_factory=default_engines)
    handler: CheckpointHandler = field(default_factory=NullHandler)
    document: Document | None = None

    snap_zones: bool = field(default_factory=lambda: load().snap_zones)
    """Whether `_layout` moves each box onto its ink. See `snapped_or_original`.

    Resolved per Conversion rather than read at import, so a test or a bake-off
    arm can set the variable and get the behaviour without reloading the module.
    """

    cover_the_page: bool = field(default_factory=lambda: load().cover_the_page)
    """Whether `_layout` gives uncovered ink a Zone of its own.

    Resolved per Conversion for the same reason as `snap_zones` above, and it
    lives here rather than on the Engine because the measurement is the
    Orchestrator's: it owns the Rectified Image and the Trace. See
    `config.DEFAULT_COVER_THE_PAGE` and `recovered_zones`.
    """

    style_record: bool = field(default_factory=lambda: load().style_record)
    """Whether the page's own colours and width are measured into the IR.

    Resolved per Conversion for the same reason as `snap_zones` above. See
    `config.DEFAULT_STYLE_RECORD`, `style.measure` and ADR 0005.
    """

    caption_pass: bool = field(default_factory=lambda: load().caption_pass)
    inline_pass: bool = field(default_factory=lambda: load().inline_pass)
    """Whether `_classify` reads each Zone's Title before asking its Kind.

    Resolved per Conversion for the same reason as the two above, and it lives
    here rather than on the Engine because the band measurement that decides
    whether to ask at all is the Orchestrator's: it owns the Rectified Image and
    the Trace, so measuring once here is what keeps the crop the model saw and
    the crop `trace.json` describes provably the same pixels. See
    `config.DEFAULT_CAPTION_PASS`.
    """

    trace: Trace = field(default_factory=Trace)
    """What this Conversion did, step by step. See `trace.py`.

    Always on, with no flag: it is an append-only list, the cost is nil, and a
    diagnostic that is off by default is off on the run you needed it for. The
    passes only ever append — nothing here reads it back — so an Event that is
    wrong or missing still leaves the Document byte-identical.
    """

    classification_ran: bool = field(init=False, default=False)
    """Whether the classification pass has happened yet. See `_classify`.

    A flag rather than something derived from the Zones, which is how `_layout`
    knows: a Zone carries no mark saying whether it was classified, and the Kind
    it holds cannot say either, since a Zone that failed classification keeps
    whatever Kind it arrived with.

    `init=False` on this and the three below: they are bookkeeping the passes
    write as they go, not something a caller configures.
    """

    unclassified: set[int] = field(init=False, default_factory=set)
    """Zones whose classification call raised, by index.

    Their Kind is unknown, so extraction has no question to ask about them and
    skips them. Held here rather than derived from `document.failures` because
    `_extract` rebuilds that list every round.
    """

    classification_failures: list[Failure] = field(init=False, default_factory=list)
    """Failures classification recorded, kept across rounds.

    Classification runs once and extraction runs every round, so `_extract`
    clearing the Document's Failures would erase these on round two. Keeping
    them here makes classification the owner of its own findings and `_extract`
    merely the thing that puts them back.
    """

    classification_caveats: list[Caveat] = field(init=False, default_factory=list)
    """Caveats classification recorded, kept across rounds. See above.

    Two lists rather than one of `Failure | Caveat`: they are put back into two
    separate fields of the Document, so one list would only be sorted back out
    by type at the other end.
    """

    vetoed: dict[int, str] = field(init=False, default_factory=dict)
    """Captions the model read and `CaptionBand.aligns_to_grid` refused, by
    Zone index — kept for `_restore_vetoed_captions` after extraction."""

    def run(self) -> Document:
        """Rectify, lay out, classify, extract, probe, audit, refine."""
        started = time.perf_counter()
        rectified = rectify(self.source)
        self.trace.record(
            Stage.RECTIFY, "rectify", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            path=rectified.source.path, sha256=rectified.source.sha256,
            source_width=rectified.source.width,
            source_height=rectified.source.height,
            rectified_width=rectified.image.shape[1],
            rectified_height=rectified.image.shape[0],
            warped=rectified.warped,
        )
        hint = self._ask_opening()

        document = Document(source=rectified.source, hint=hint)
        self.document = document
        self._measure_style(rectified, document)

        for round_number in range(MAX_ROUNDS):
            self._layout(rectified, document)
            self._classify(rectified, document)
            self._draw_figures(rectified, document)
            self._extract(rectified, document)
            # After `_extract`, and so after `_classify`. The caption pass sets
            # `Zone.title`, which says how many of a region's first rows a
            # title bar could occupy; the extraction sets the rows, and a row
            # named `header` is where a header bar is looked for. Before
            # either, the stage measures a bar nothing has named — which is
            # how `title_fill` came to be set on none of 119 Zones.
            self._measure_chrome(rectified, document)
            self._measure_type(rectified, document)
            self._find_separators(rectified, document)
            self._locate(rectified, document)
            self._read_unclaimed(rectified, document)
            self._read_fields(rectified, document)
            self._place_furniture(rectified, document)
            self._read_rhythm(rectified, document)
            self._read_looks(rectified, document)
            self._read_spans(rectified, document)

            document.probes = probe_module.run(document)
            for probe in document.probes:
                self.trace.record(
                    Stage.PROBE, probe.kind,
                    Disposition.ACCEPTED if probe.ok else Disposition.REJECTED,
                    zone_index=probe.zone_index,
                    ok=probe.ok, computed=probe.computed, stated=probe.stated,
                    detail=probe.detail,
                )
            self._audit(rectified, document)
            self._climb_ladders(rectified, document)

            answer = self._ask_convergence(document)
            if answer.is_empty:
                # Nothing new entered the system. Re-running identical passes
                # over identical pixels would reproduce the Draft as it stands.
                self.trace.record(
                    Stage.RENDER, "converged", Disposition.ACCEPTED,
                    round=round_number,
                    zones=len(document.zones),
                    incomplete=sum(1 for z in document.zones if not z.complete),
                    failures=len(document.failures),
                    caveats=len(document.caveats),
                    seconds=time.perf_counter() - started,
                )
                break
            self._apply(answer, document)
        else:
            raise RuntimeError(
                "round cap reached: a Rung is being retried. See MAX_ROUNDS."
            )

        return document

    def _ask_opening(self) -> str | None:
        """Collect a Hint: prose for prompts that branches no code path.

        If an answer here ever starts selecting an Extractor or a template, ADR
        0001 has been reversed by accident.
        """
        answer = self.handler.ask(
            Question(
                kind="opening",
                text="Anything I should know about this document?",
            )
        )
        return answer.note or None

    def _measure_style(self, rectified: Rectified, document: Document) -> None:
        """Read the page's palette and width off its pixels. See `style.measure`.

        Once per Conversion, outside the round loop and before `_layout`,
        because nothing it measures depends on where the Zones are: the ground,
        the ink and the accent are the page's, and the width is the Source
        Image's. When the border and card detector arrives it will need a
        *second* step, after layout, because a Zone's own fill is a per-Zone
        measurement — the two are not one pass that got moved.

        **The width is the source's, not the rectified image's.** `rectify`
        resizes the long edge to `TARGET_LONG_EDGE` for the model's benefit, so
        the rectified width is an artefact of that resize; what the reader saw
        is `rectified.source.width`, and `height_ratio` is scored against the
        source screenshot.

        **The polarity flag is passed through rather than re-derived.**
        `rectify` already turned a light-on-dark page over, so the image here is
        dark-ink-on-light whatever the page was. Measuring it as it stands would
        report every dark page as a light one; `inverted` is what lets `measure`
        turn the answer back.

        Recorded either way, like `_cover_the_page`: a run whose render came out
        the house colours needs to be able to say whether the step was off or
        measured white.
        """
        if not self.style_record:
            self.trace.record(
                Stage.RECTIFY, "style_record", Disposition.SKIPPED,
                enabled=False,
                reason="DTH_STYLE_RECORD is off, so the render keeps the house "
                       "palette and its fixed 52rem column",
            )
            return

        started = time.perf_counter()
        # `plain`, never `image`. See `Rectified.plain`: equalisation is what
        # makes faint type readable and colour unreadable, and this is the pass
        # that reads colour.
        plain = rectified.plain if rectified.plain is not None else rectified.image
        # Spec 0012, G3a: everything the page draws that is not type, found
        # first, so the ink is measured over type only. See `furniture`.
        document.furniture = furniture_module.find(
            plain, inverted=rectified.inverted, read=rectified.image)
        measured = style_module.measure(
            plain,
            inverted=rectified.inverted,
            read=rectified.image,
            without=furniture_module.mask(document.furniture, plain.shape),
        )
        document.style = measured
        document.page_px = rectified.source.width
        self.trace.record(
            Stage.RECTIFY, "style_record", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            enabled=True,
            page_px=document.page_px,
            inverted=rectified.inverted,
            page_bg=list(measured.page_bg),
            ink=list(measured.ink),
            accent=None if measured.accent is None else list(measured.accent),
            shade=None if measured.shade is None else list(measured.shade),
            furniture=len(document.furniture),
        )

    def _measure_chrome(self, rectified: Rectified, document: Document) -> None:
        """What the source draws around each Zone. See `style.chrome`.

        A *second* style step, after layout rather than with `_measure_style`,
        and the split is real: the palette is the page's and needs no Zones,
        while a fill and a border are per-region and need the boxes.

        **It runs after `_classify`, and it used to run before it.** The
        earlier order was chosen so that a Kind changing on a later round could
        not silently change what colour a card was — but this measures no Kind,
        so the argument protected nothing, and it cost the feature beside it.
        `title_rows` comes from `Zone.title`, `Zone.title_fill` is only ever set
        when `title_rows` is non-zero, and the caption pass that sets a Title is
        inside `_classify`. Measured on the 2026-09-21 baseline sweep:
        `zone_chrome` at trace seq 6, the first `read_caption` at seq 7, and
        `title_fill` set on **0 of 119 Zones** across the corpus. The bar had
        shipped, been tested offline and never once fired in a conversion —
        which is this project's own lesson that a flag that does not arrive
        looks exactly like a flag that does nothing.

        Moving it moves no model call: this stage asks the model nothing, and
        nothing between the two reads `fill`, `title_fill` or `boxed`. So the
        answers are unchanged and the effect is measurable offline.

        **It runs after `_extract` too, since 2026-09-26, for the same reason
        one stage later.** A table's header bar is looked for on the row
        `RowRole.header` names, and no Zone has rows until it is extracted.
        Nothing in `_draw_figures` or `_extract` reads what this sets, and
        re-measuring chrome off `tests/frozen/a3-result/`'s *extracted* IRs
        reproduced all fifteen documents byte for byte — so the move changes
        no fill, title bar or border anywhere in the corpus.

        `title_rows` comes from `caption_band`, which already measures a crop's
        first printed line for the caption pass. Nothing new is asked of the
        pixels; the same band that decides whether to *ask* for a Title decides
        how much of the region the bar could occupy. `header_rows` comes from
        `header_band`, the next printed line down when the Zone has a Title.
        """
        if not self.style_record or document.style is None:
            return

        started = time.perf_counter()
        measured = 0
        plain = rectified.plain if rectified.plain is not None else rectified.image
        # Rules are read off the whole page, once. A Zone's crop is snapped
        # onto its content ink and `content_ink` deletes borders by name, so
        # the rule a card is drawn with is not in that crop to be found.
        drawn = style_module.rectangles(
            plain, ground=document.style.page_bg, inverted=rectified.inverted)
        # One rectangle, one Zone: a box several Zones sit inside belongs to
        # their grouping and to none of them. See `style.boxes_for`.
        own = style_module.boxes_for([z.bbox for z in document.zones], drawn)
        # And a box a run of one lane shares is that run's — spec 0011, 1a.
        framed = rhythm_module.frames(document.zones, drawn, document.regions)
        for index, zone in enumerate(document.zones):
            zone.frame = framed[index]
            if zone.bbox is None:
                continue
            # The bands are measured on the ink picture and the colour on the
            # plain one — the same geometry, so the same crop twice.
            read = zone_pixels(_ink(rectified), zone)
            band = caption_band(read)
            names_a_header = (zone.kind is Kind.TABLE and bool(zone.rows)
                              and zone.rows[0].role is RowRole.HEADER)
            crop = zone_pixels(plain, zone)
            found = style_module.chrome(
                crop, ground=document.style.page_bg,
                inverted=rectified.inverted,
                title_rows=band.bottom if band is not None and zone.title else 0,
                header_rows=(header_band(read, titled=bool(zone.title))
                             if names_a_header else None),
                bordered=own[index] is not None,
            )
            zone.fill, zone.title_fill, zone.header_fill, zone.boxed = (
                found.fill, found.title_fill, found.header_fill, found.bordered
            )
            if (found.fill or found.title_fill or found.header_fill
                    or found.bordered):
                measured += 1
        self.trace.record(
            Stage.LAYOUT, "zone_chrome", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            zones=len(document.zones), with_chrome=measured,
            rectangles=len(drawn),
            detail=[
                {"zone": i, "fill": z.fill, "title_fill": z.title_fill,
                 "header_fill": z.header_fill, "boxed": z.boxed,
                 "frame": None if z.frame is None else [
                     round(v, 4) for v in (z.frame.left, z.frame.top,
                                           z.frame.right, z.frame.bottom)]}
                for i, z in enumerate(document.zones)
            ],
        )

    def _measure_type(self, rectified: Rectified, document: Document) -> None:
        """How large each leading heading is printed. See `style.heading_sizes`.

        After `_extract`, because it sizes a *Block*, and a Zone has none until
        it is extracted — the stage position that kept `title_fill` and
        `header_fill` from ever firing, avoided by construction. Nothing after
        it reads `Block.size` but the renderer, so it moves no model answer.

        Every Block is set, not only the ones measured, so a later round
        cannot keep a size its heading no longer earns.
        """
        if not self.style_record:
            return

        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        sizes = style_module.heading_sizes(plain, document.zones)
        for zone, size in zip(document.zones, sizes):
            for position, block in enumerate(zone.blocks):
                block.size = size if position == 0 else None
        body = body_px(plain, document.zones, rectified.source.width)
        if document.style is not None:
            document.style.body_px = body
        for zone, title in zip(document.zones,
                               style_module.title_sizes(plain, document.zones)):
            zone.title_size = title
        self.trace.record(
            Stage.LAYOUT, "heading_sizes", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            body_px=body,
            zones=len(document.zones),
            sized=sum(1 for size in sizes if size is not None),
            detail=[{"zone": index, "size": size}
                    for index, size in enumerate(sizes) if size is not None],
        )

    def _draw_figures(self, rectified: Rectified, document: Document) -> None:
        """Give every FIGURE Zone its own pixels. See `preprocess.figure_pixels`.

        **After `_classify`, for the reason `_measure_chrome` is:** the Kind is
        decided there, and a step placed before the thing it depends on ships
        and never fires — `Zone.title_fill` did exactly that for a phase. Set
        on every round and cleared on any Zone that is not a figure, so a Kind
        that changes between rounds cannot leave a picture behind.

        Asks the model nothing, so it cannot move an answer: every other Zone's
        crop and prompt are what they were.
        """
        started = time.perf_counter()
        drawn = []
        for index, zone in enumerate(document.zones):
            zone.pixels = (figure_pixels(rectified, zone)
                           if zone.kind is Kind.FIGURE else None)
            if zone.pixels:
                drawn.append({"zone": index, "graphic": zone.graphic_kind,
                              "base64_bytes": len(zone.pixels)})
        self.trace.record(
            Stage.LAYOUT, "figure_pixels",
            Disposition.ACCEPTED if drawn else Disposition.SKIPPED,
            seconds=time.perf_counter() - started,
            figures=len(drawn), detail=drawn,
            reason=None if drawn else "no Zone was classified as a figure",
        )

    def _layout(self, rectified: Rectified, document: Document) -> None:
        """Detect Zones — Band, column, Role, bbox — with the layout detector.

        It still returns a Kind as well, and that Kind is not used: `_classify`
        overwrites every one of them from the Zone's own crop moments later.

        Run once per Conversion, not once per round. A later round refines what
        is *in* the Zones; re-detecting them would discard everything extracted
        so far in exchange for the same boxes.

        A detector that fails is recorded and the failure re-raised, rather
        than carried on from with no Zones: a plausible partial layout looks
        like a sparse document and is worse than an error.
        """
        if document.zones:
            return

        mark, started = self.trace.next_call, time.perf_counter()
        try:
            zones = self.engines.layout.detect_zones(rectified.image, document.hint)
            failure: Exception | None = None
        except (MappingError, RuntimeError) as error:
            zones, failure = [], error
        call, made = self.trace.calls_since(mark)
        self.trace.record(
            Stage.LAYOUT, "detect_zones",
            Disposition.REJECTED if failure else Disposition.ACCEPTED,
            seconds=time.perf_counter() - started, call=call, calls=made,
            zones=len(zones), boxes=[_box_data(zone) for zone in zones],
            reason=f"{type(failure).__name__}: {failure}" if failure else None,
        )
        if failure is not None:
            raise failure

        # Spec 0018, A1: the ink measures read each fill the Zones stand on
        # as ground — the cover step, the snap and the cut below.
        _ground(rectified, document, zones)
        zones = self._cover_the_page(rectified, zones)

        if self.snap_zones:
            log.info("DTH_SNAP_ZONES is on: moving %d boxes onto their ink", len(zones))
            before = [_box_data(zone) for zone in zones]
            started = time.perf_counter()
            snapped = snapped_or_original(_ink(rectified), zones)
            kept = snapped is zones
            self.trace.record(
                Stage.SNAP, "snap_to_ink",
                Disposition.KEPT if kept else Disposition.OVERRIDDEN,
                seconds=time.perf_counter() - started,
                enabled=True, reverted=kept,
                reason=_why_kept(zones) if kept else None,
                before=before, after=[_box_data(zone) for zone in snapped],
                changed=[
                    Change(path=f"zones[{index}].bbox", before=was, after=now)
                    for index, (was, now) in enumerate(
                        zip(before, [_box_data(zone) for zone in snapped])
                    )
                    if was != now
                ],
            )
            zones = snapped
        else:
            self.trace.record(
                Stage.SNAP, "snap_to_ink", Disposition.SKIPPED,
                enabled=False,
                reason="DTH_SNAP_ZONES is off, so the Engine's boxes are used "
                       "as returned",
            )
        document.zones = zones
        self._read_structure(rectified, document)
        if self._cut_at_regions(rectified, document):
            self._read_structure(rectified, document)
        # Every later ink measure reads the fills the final boxes stand on.
        _ground(rectified, document, document.zones)

    def _read_structure(self, rectified: Rectified, document: Document) -> None:
        """The page's regions, read off the final boxes — spec 0008. See
        `structure.structure`.

        Here, once the boxes are final, because the regions are a fact about
        where those boxes sit; nothing a model is asked reads them, so this
        moves no answer. It needs the page's ground, which the Style Record
        measures, so with `DTH_STYLE_RECORD` off the page renders as Bands, as
        it always did.
        """
        if document.style is None:
            self.trace.record(
                Stage.LAYOUT, "structure", Disposition.SKIPPED,
                reason="no Style Record, so no page ground to read regions off")
            return
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        document.regions = structure(
            plain, [zone.bbox for zone in document.zones if zone.bbox is not None],
            ground=document.style.page_bg, inverted=rectified.inverted,
            furniture=document.furniture)
        self.trace.record(
            Stage.LAYOUT, "structure", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            regions=[{"top": round(r.top, 4), "bottom": round(r.bottom, 4),
                      "flow": r.flow.value,
                      "splits": [round(x, 4) for x in r.splits],
                      "rows": r.rows} for r in document.regions],
        )

    def _find_separators(self, rectified: Rectified, document: Document) -> None:
        """The wide rules the page draws between its Zones — spec 0009, step D.
        See `structure.separators`.

        **Here, after `_extract`, and not with the regions.** It tells a
        table's border by the table Zone's row rules, so it needs Kinds; in
        `_read_structure`, during layout, every Zone is still the detector's
        placeholder `prose`, and `sample_table_0003`'s and `report_0011`'s
        borders were drawn as separators. Found by replaying the floor's
        answers beside `rederive.py`, which works on finished IRs and could
        not see it. Nothing a model is asked reads them.
        """
        if document.style is None:
            return
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        document.separators = separators(
            plain, document.zones, ground=document.style.page_bg,
            inverted=rectified.inverted)
        self.trace.record(
            Stage.LAYOUT, "separators", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            separators=[round(y, 4) for y in document.separators])

    def _place_furniture(self, rectified: Rectified, document: Document) -> None:
        """Which Zone holds each rule the page draws — spec 0012, G3a. See
        `furniture.place`.

        **After `_read_fields`**, the last step that moves a Zone's box: it
        widens a form's Zone to its marks. Nothing a model is asked reads it.
        """
        furniture_module.place(document.furniture, document.zones)
        self.trace.record(
            Stage.LAYOUT, "furniture", Disposition.ACCEPTED,
            found=len(document.furniture),
            placed=[item.zone for item in document.furniture])

    def _read_rhythm(self, rectified: Rectified, document: Document) -> None:
        """Which Zones continue one another, and how each one's lines sit —
        spec 0011, step 1. See `rhythm.read`.

        **After `_find_separators`**: a run may not cross a rule the page
        draws, and it reads Kinds, Titles, fills and frames, all set by now.
        **And after `_read_fields`** — spec 0012 step 0 — which can turn a
        table into pairs and widen a box to its marks: read before it,
        `form_0007`'s Zone 5 was skipped as a table and drawn as pairs with
        no alignment, and `tools/rederive.py`, which meets the Zone already
        pairs, disagreed with the Conversion by that one field. Nothing a
        model is asked reads what it sets, so it moves no answer.
        """
        if document.style is None:
            return
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        rhythm_module.read(plain, document)
        self.trace.record(
            Stage.LAYOUT, "rhythm", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            detail=[{"zone": i, "group": z.group, "align": z.align,
                     "title_align": z.title_align}
                    for i, z in enumerate(document.zones)
                    if z.group is not None or z.align or z.title_align])

    def _locate(self, rectified: Rectified, document: Document) -> None:
        """Where every Cell sits on the page — spec 0011, step 2 — and which
        printed lines no Cell claims, spec 0012, G9. See `locate.locate`.

        **tesseract is never a reader here.** Its words are matched against
        the model's and only their boxes kept; and where a line of its words
        is claimed by no Cell, it says where to look, and the model reads
        what is there — `_read_unclaimed`, spec 0014, step 2. Its own words
        are never printed. Every round re-locates from scratch, because a
        Correction can change a Cell's text, and `_read_unclaimed` runs this
        once more when it keeps a line. Without tesseract on `PATH` it places
        nothing, finds no line, says so, and every Cell renders as it did.
        """
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        placed, cells = locate_module.locate(plain, document)
        # Spec 0013 step 3d: a line placed on another Zone's line, whose
        # text it starts, is a cut-off copy of words that Zone prints.
        copies = locate_module.without_cut_copies(document)
        unplaced = [{"zone": index, "text": cell.text[:60]}
                    for index, zone in enumerate(document.zones)
                    if zone.kind is not Kind.FIGURE
                    for cell, _ in locate_module.cells_of(zone)
                    if cell.bbox is None and cell.text.strip()]
        if not locate_module.available():
            self.trace.record(
                Stage.LAYOUT, "locate", Disposition.REJECTED,
                reason=f"no `{locate_module.TESSERACT}` on PATH", cells=cells)
            return
        self.trace.record(
            Stage.LAYOUT, "locate", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            placed=placed, cells=cells, unplaced=unplaced,
            cut_copies=[{"zone": zone, "text": text[:60]} for zone, text in copies],
            unclaimed=[{"zone": line.zone_index, "words": line.words,
                        "top": round(line.bbox.top, 3)}
                       for line in document.unclaimed])

    def _read_unclaimed(self, rectified: Rectified, document: Document) -> None:
        """Read each printed line no Cell claims on its own crop, and keep
        what its Zone does not print in `Zone.extra` — spec 0014, step 2.

        `locate.unclaimed` finds the lines — the form's note under its tick
        boxes, a ticket's `OSLO GARDERMOEN`, a timetable's legend — and
        until this pass only reported them. Each is read with the prose
        prompt and schema every prose Zone is read with, on a crop cut as
        every Zone's is — since spec 0015, step 1, stopping short of the
        words of its line a Cell claims, so the reading does not repeat
        them (`Unclaimed.reach`). **A separate pass, after extraction**: no Extractor
        prompt or schema changes, so at `temperature: 0` every answer given
        before is given again — CLAUDE.md, "where you ask is a bigger lever
        than how you ask". One call per line, and no inline runs asked.

        What was read is kept **unless the Zone already prints it**
        (`locate.holds`), so a line read again is never printed twice. It
        is judged as the line it was read from, its Blocks read together:
        `timetable_0019`'s legend comes back as five items, each a word
        its grid prints, and judged one Block at a time it was refused
        whole, though the page prints those words a second time.
        If anything was kept, `_locate` runs once more: the new lines are
        placed, the unclaimed list is recomputed, and they claim their own
        line. A call that raises costs that line alone, which stays on the
        unclaimed list. `_extract` clears a Zone's `extra` when it reads
        the Zone again.
        """
        kept = 0
        for line in list(document.unclaimed):
            zone = document.zones[line.zone_index]
            transient = Zone(kind=Kind.PROSE, bbox=line.bbox)
            # Spec 0015, step 1: cut short of the words of its line a Cell
            # claims (`Unclaimed.reach`), and otherwise exactly as before.
            pixels = (crop(rectified.image, line.reach, pad_x=0.0) if line.reach
                      else zone_pixels(rectified.image, transient))
            mark, started = self.trace.next_call, time.perf_counter()
            try:
                self.engines.extract.extract_zone(pixels, transient, document.hint)
            except Exception as error:
                call, made = self.trace.calls_since(mark)
                self.trace.record(
                    Stage.EXTRACT, "unclaimed", Disposition.REJECTED,
                    zone_index=line.zone_index, seconds=time.perf_counter() - started,
                    call=call, calls=made, box=_box_data(transient), words=line.words,
                    error=f"{type(error).__name__}: {error}",
                    reason="the line was not read, and stays unclaimed",
                )
                continue
            # The line read together, as the detector found it: the
            # timetable's legend comes back five items, each a word its grid
            # prints too, and the page prints them again.
            read = [" ".join(cell.text for cell in block.lines)
                    for block in transient.blocks]
            held = locate_module.holds(zone, " ".join(read))
            texts, refused = ([], read) if held else (read, [])
            if not held:
                # Spec 0018, A1: printed where it was read from, whatever
                # tesseract's next read makes of the line.
                for block in transient.blocks:
                    block.read_from = line.bbox
                zone.extra.extend(transient.blocks)
            kept += len(texts)
            call, made = self.trace.calls_since(mark)
            self.trace.record(
                Stage.EXTRACT, "unclaimed",
                Disposition.ACCEPTED if texts else Disposition.REJECTED,
                zone_index=line.zone_index, seconds=time.perf_counter() - started,
                call=call, calls=made, box=_box_data(transient), words=line.words,
                kept=texts, refused=refused,
                changed=[Change(path=f"zones[{line.zone_index}].extra",
                                before=None, after=text) for text in texts],
                reason=None if texts else
                "the Zone already prints what was read" if refused else
                "nothing was read",
            )
        if kept:
            self._locate(rectified, document)

    def _read_fields(self, rectified: Rectified, document: Document) -> None:
        """The marks the page draws for its entries — boxes, digit combs,
        tick boxes, rules — attached to the pairs they belong to: spec 0011,
        step 3. See `fields.read`.

        **After `_locate`**, whose Cell boxes say which mark is whose, and
        after `_find_separators`, since a rule a field claims stops being
        one. Nothing a model is asked reads what it sets.
        """
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        before = [zone.kind for zone in document.zones]
        fields_module.read(plain, document)
        self.trace.record(
            Stage.LAYOUT, "fields", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            fields=[{"zone": index, "label": pair.label.text[:40],
                     "marks": [mark.kind for mark in pair.marks]}
                    for index, zone in enumerate(document.zones)
                    for pair in zone.pairs if pair.marks],
            rebuilt=[{"zone": index, "was": was.value}
                     for index, (was, zone) in enumerate(zip(before, document.zones))
                     if zone.kind is not was])

    def _read_looks(self, rectified: Rectified, document: Document) -> None:
        """How each placed entry is printed — its size, weight, slant,
        colour and any chip, from its own ink: spec 0011, step 4. See `looks.read`. After
        `_locate`, whose boxes it measures inside. It also unmarks a `mark`
        run the page draws no highlight behind — spec 0012, G2. Nothing a
        model is asked reads what it sets."""
        started = time.perf_counter()
        plain = rectified.plain if rectified.plain is not None else rectified.image
        marked = sum(1 for zone in document.zones
                     for cell, _ in locate_module.cells_of(zone)
                     for run in cell.runs if run.kind == "mark")
        looks_module.read(plain, document, photographed=rectified.warped,
                          inverted=rectified.inverted)
        cells = [cell for zone in document.zones
                 for cell, _ in locate_module.cells_of(zone) if cell.look is not None]
        self.trace.record(
            Stage.LAYOUT, "looks", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started, measured=len(cells),
            unmarked=marked - sum(1 for zone in document.zones
                                  for cell, _ in locate_module.cells_of(zone)
                                  for run in cell.runs if run.kind == "mark"),
            bold=sum(1 for cell in cells if cell.look and cell.look.bold),
            italic=sum(1 for cell in cells if cell.look and cell.look.italic),
            chips=sum(1 for cell in cells if cell.look and cell.look.fill))

    def _read_spans(self, rectified: Rectified, document: Document) -> None:
        """A ruled grid's cells as the page draws them: second lines joined,
        lines read on their own put in their cells, and each cell over the
        empty slots it covers — spec 0019, B1. See `spans.read`. After
        `_read_looks`, so every line keeps the look measured on its ink."""
        started = time.perf_counter()
        rows = sum(len(zone.rows) for zone in document.zones)
        spans_module.read(document)
        self.trace.record(
            Stage.LAYOUT, "spans", Disposition.ACCEPTED,
            seconds=time.perf_counter() - started,
            joined=rows - sum(len(zone.rows) for zone in document.zones),
            spanning=sum(1 for zone in document.zones for row in zone.rows
                         for cell in row.cells if cell.span is not None))

    def _cut_at_regions(self, rectified: Rectified, document: Document) -> bool:
        """Cut a Zone that crosses the edge of a grid or a column region — spec
        0008, step 3. See `structure.cut_at_edges`. Returns whether it cut."""
        try:
            cut = cut_at_edges(_ink(rectified), document.zones, document.regions)
        except MappingError as error:
            self.trace.record(Stage.LAYOUT, "cut_at_regions", Disposition.REJECTED,
                              reason=f"{type(error).__name__}: {error}")
            return False
        if cut is document.zones:
            return False
        self.trace.record(
            Stage.LAYOUT, "cut_at_regions", Disposition.ACCEPTED,
            before=[_box_data(zone) for zone in document.zones],
            after=[_box_data(zone) for zone in cut])
        document.zones = cut
        return True

    def _cover_the_page(self, rectified: Rectified,
                        zones: list[Zone]) -> list[Zone]:
        """Give ink no detected box covers a Zone of its own. See `recovered_zones`.

        Runs before the snap rather than after it, so a recovered box is snapped
        onto its own ink by the same pass that snaps every other box — one place
        that moves a box onto its ink, not two.

        Recorded either way: a step that ran and found nothing and a step that
        was switched off are different facts, and a Conversion that lost
        content needs to be able to say which.
        """
        if not self.cover_the_page:
            self.trace.record(
                Stage.LAYOUT, "cover_the_page", Disposition.SKIPPED,
                enabled=False,
                reason="DTH_COVER_THE_PAGE is off, so ink outside every "
                       "detected box is reported as a Gap and not read",
            )
            return zones

        before = [_box_data(zone) for zone in zones]
        started = time.perf_counter()
        covered = recovered_zones(_ink(rectified), zones)
        gained = len(covered) - len(zones)
        if gained:
            log.info("DTH_COVER_THE_PAGE is on: %d region(s) of ink no detected "
                     "box covers became Zones", gained)
        self.trace.record(
            Stage.LAYOUT, "cover_the_page",
            Disposition.OVERRIDDEN if gained else Disposition.KEPT,
            seconds=time.perf_counter() - started,
            enabled=True, recovered=gained,
            before=before, after=[_box_data(zone) for zone in covered],
            reason=None if gained else (
                "every patch of ink is inside a detected box, or none that is "
                "not could be placed in a valid Band"
            ),
        )
        return covered

    def _read_caption(self, rectified: Rectified, document: Document,
                      index: int) -> int:
        """Take this Zone's Title off its first printed line. Returns rows to skip.

        Runs before the Kind question and hands it a number, because the two want
        opposite pixels: the Title needs the caption band in frame and the Kind is
        measurably wrong while it is there. See `config.DEFAULT_CAPTION_PASS`.

        **The Extractor is deliberately not given this number** — spec 0007
        Phase A0, 2026-09-22, and it was tried the other way first. Withholding
        the band from extraction as well deletes real content wherever this pass
        took a Title from something that was not a caption, and it has no
        reliable test for that; `engines.ollama.OllamaEngine.extract_zone`
        carries the measurement and the three documents it was rejected on. The
        caption is therefore read twice, and `wire._without_title_echo` drops
        the second copy after the fact.

        **The band measurement decides whether to ask at all**, and that guard is
        structural rather than a judgement: `caption_band` returns `None` unless
        something is printed *below* the first line, so a Zone that is only a
        heading — 20 of run 69's 36 crops — is never asked and never stripped.
        Without it such a Zone would take its only line as its own Title and then
        have the Extractor read the same words again as its content.

        A failure here costs the Title and nothing else. The Zone keeps its full
        crop and goes on to be classified, because a Kind is what routes it to an
        Extractor and a missing Title is not worth a skeleton.
        """
        zone = document.zones[index]
        if not self.caption_pass or zone.bbox is None:
            return 0

        band = caption_band(zone_pixels(_ink(rectified), zone))
        if band is None:
            self.trace.record(
                Stage.CLASSIFY, "read_caption", Disposition.SKIPPED,
                zone_index=index, kind=zone.kind.value,
                lines=1, reason="the crop holds one band of ink, so there is "
                                "nothing printed below the first line and no "
                                "caption to lift off it",
            )
            return 0

        mark, started = self.trace.next_call, time.perf_counter()
        try:
            document.zones[index] = self.engines.classify.read_caption(
                rectified.image, zone, document.hint
            )
        except Exception as error:
            call, made = self.trace.calls_since(mark)
            self.trace.record(
                Stage.CLASSIFY, "read_caption", Disposition.REJECTED,
                zone_index=index, seconds=time.perf_counter() - started,
                call=call, calls=made, kind=zone.kind.value,
                error=f"{type(error).__name__}: {error}",
                consequence="the Zone keeps no Title and is classified on its "
                            "whole crop, caption included",
            )
            return 0

        titled = document.zones[index]
        call, made = self.trace.calls_since(mark)

        # The ink may refuse a caption, and may never assert one. A heading row
        # has one cell per column of the values below it; a caption spans the
        # region and ignores that grid, so equal column counts either side of the
        # cut mean the model has named a table's heading row. Refusing costs at
        # most a Title, while accepting a false one costs a Kind, a row and a
        # Probe — run 71 spent all three on `invoice_0001`. The veto is therefore
        # only ever pointed at the expensive side. See `CaptionBand`.
        refused = titled.title if band.aligns_to_grid else None
        vetoed = refused is not None
        if refused is not None:
            titled.title = None
            self.vetoed[index] = refused

        taken = titled.title is not None
        self.trace.record(
            Stage.CLASSIFY, "read_caption",
            Disposition.ACCEPTED if taken else Disposition.KEPT,
            zone_index=index, seconds=time.perf_counter() - started,
            call=call, calls=made,
            changed=([Change(path=f"zones[{index}].title",
                             before=None, after=titled.title)] if taken else []),
            crop=_crop_data(rectified.image, titled),
            title=titled.title, kind=titled.kind.value,
            band_top=band.top, band_bottom=band.bottom,
            gap_below=band.gap_below, median_gap=band.median_gap,
            lines=band.lines, cut_row=band.cut_row if taken else 0,
            head_columns=band.head_columns, body_columns=band.body_columns,
            vetoed=refused if vetoed else None,
        )
        return band.cut_row if taken else 0

    def _classify(self, rectified: Rectified, document: Document) -> None:
        """Decide each Zone's Kind from that Zone's own crop.

        A pass of its own, between geometry and extraction, because the two
        questions want different pixels: where a block is, is coarse work on a
        downscaled page, while what a block *is* can turn on a shaded heading row
        that the downscale removes. Issue #13 measured both halves — a Zone asked
        about on its own is classified correctly at a resolution where the same
        Zone asked about as one of seven is not, and a Zone needing glyphs needs
        the crop *and* a model able to use it. Hence a separate pass and a
        separate model.

        Once per Conversion, for the same reason `_layout` is: the Kind of a
        block does not change between rounds, and re-asking would spend a call
        per Zone to be told again what the same pixels are.

        A Zone whose call raises is a Failure on that Zone alone, following the
        contract extraction already keeps — one bad crop does not cost the
        document. It is then left out of extraction: with no Kind there is no
        question to ask about it, and asking anyway would route it on geometry's
        guess, which is the guess this pass exists to stop trusting.

        **Two calls per Zone under `DTH_CAPTION_PASS`, and two Events.** The
        Title is read first, from the whole crop, and the caption band it names is
        then withheld from the Kind question — see `_read_caption`. They are
        recorded as separate steps rather than one step making two calls because
        the contact sheet renders one call per Event, so a merged step would show
        the first prompt and hide the second.
        """
        if self.classification_ran:
            return
        self.classification_ran = True

        for index, zone in enumerate(document.zones):
            was = zone.kind.value
            skip_rows = self._read_caption(rectified, document, index)
            # Re-read rather than trusting the loop variable: the caption pass
            # fills its Zone in place today, and a Zone rebuilt there instead
            # would silently drop the Title on the way to the Kind question.
            zone = document.zones[index]
            mark, started = self.trace.next_call, time.perf_counter()
            try:
                empty = empty_zone(_ink(rectified), zone)
                if empty is not None:
                    self.trace.record(
                        Stage.CLASSIFY, "empty_zone", Disposition.SKIPPED,
                        zone_index=index,
                        ink_fraction=ink_fraction(zone_pixels(_ink(rectified), zone)),
                        threshold=MIN_ZONE_INK, kind=was, reason=str(empty),
                    )
                    raise empty
                document.zones[index] = self.engines.classify.classify_zone(
                    rectified.image, zone, document.hint, skip_rows=skip_rows
                )
            except Exception as error:
                # The Kind recorded here is the one geometry guessed, which this
                # pass exists to distrust — but it is the only one there is, and
                # a Failure saying nothing about what it failed on is worse than
                # one saying "the thing geometry took for a table". #17 removes
                # geometry's guess, and then this becomes the Kind's default.
                call, made = self.trace.calls_since(mark)
                self.trace.record(
                    Stage.CLASSIFY, "classify_zone", Disposition.REJECTED,
                    zone_index=index, seconds=time.perf_counter() - started,
                    call=call, calls=made, kind=was,
                    error=f"{type(error).__name__}: {error}",
                    consequence="left out of extraction: with no Kind there is "
                                "no question to ask about this Zone",
                )
                self.unclassified.add(index)
                self.classification_failures.append(
                    failed(index, zone, error,
                           share=_share_of(rectified.image, zone))
                )
                continue

            classified = document.zones[index]
            call, made = self.trace.calls_since(mark)
            self.trace.record(
                Stage.CLASSIFY, "classify_zone", Disposition.ACCEPTED,
                zone_index=index, seconds=time.perf_counter() - started,
                call=call, calls=made,
                changed=[Change(path=f"zones[{index}].kind",
                                before=was, after=classified.kind.value)],
                crop=_crop_data(rectified.image, classified,
                                skip_rows=skip_rows),
                kind_before=was, kind_after=classified.kind.value,
                title=classified.title, graphic=classified.graphic_kind,
                skip_rows=skip_rows,
                over_input_budget=long_edge_over_input_budget(
                    rectified.image, classified
                ),
            )

            note = classification_caveat(rectified.image, classified)
            if note is not None:
                self.classification_caveats.append(
                    Caveat(zone_index=index, kind=classified.kind.value, note=note)
                )
                self.trace.record(
                    Stage.CLASSIFY, "classify_caveat", Disposition.ACCEPTED,
                    zone_index=index, kind=classified.kind.value, note=note,
                )

        self._read_copies_alike(document)

    def _read_copies_alike(self, document: Document) -> None:
        """A grid's copies are read as one Kind, before anything is extracted —
        spec 0008, step 3. See `structure.alike`."""
        changes = alike(document.zones, document.regions,
                        frozenset(self.unclassified))
        if not changes:
            return
        self.trace.record(
            Stage.CLASSIFY, "copies_alike", Disposition.OVERRIDDEN,
            changed=[Change(path=f"zones[{index}].kind",
                            before=document.zones[index].kind.value,
                            after=kind.value)
                     for index, kind in sorted(changes.items())])
        for index, kind in changes.items():
            document.zones[index].kind = kind

    def _read_runs(self, rectified: Rectified, document: Document,
                   index: int) -> None:
        """Mark this Zone's links, code spans and emphasis. Costs nothing if it fails.

        **A separate pass on purpose — see `config.DEFAULT_INLINE_PASS`.** The
        same question asked inside the Extractor prompts crossed the T1 ratchet
        and was reverted; `engines.ollama.MARKED_CLAUSE` keeps the numbers.
        Asking it here touches no Extractor prompt, so extraction answers are
        unchanged, and a failure costs marking and nothing else.

        `prose` and `list` only, and only once a Zone has blocks to mark: every
        run the first attempt recovered came from those two Kinds, and tables
        and pairs returned none at all while taking the worst of the damage.

        A raised exception is recorded and swallowed. The Zone keeps its text —
        which is all of its content — so there is nothing here worth failing a
        Zone over.
        """
        zone = document.zones[index]
        if not self.inline_pass or zone.bbox is None:
            return
        if zone.kind not in (Kind.PROSE, Kind.LIST) or not zone.blocks:
            self.trace.record(
                Stage.EXTRACT, "read_runs", Disposition.SKIPPED,
                zone_index=index, kind=zone.kind.value,
                reason="the inline pass asks only prose and list Zones that "
                       "came back with blocks to mark",
            )
            return

        mark, started = self.trace.next_call, time.perf_counter()
        try:
            document.zones[index] = self.engines.extract.read_runs(
                rectified.image, zone, document.hint
            )
        except Exception as error:
            call, made = self.trace.calls_since(mark)
            self.trace.record(
                Stage.EXTRACT, "read_runs", Disposition.REJECTED,
                zone_index=index, seconds=time.perf_counter() - started,
                call=call, calls=made, kind=zone.kind.value,
                error=f"{type(error).__name__}: {error}",
                consequence="the Zone keeps every word it read and renders "
                            "with no inline marking",
            )
            return

        call, made = self.trace.calls_since(mark)
        marked = sum(1 for block in document.zones[index].blocks
                     for cell in block.lines
                     for run in cell.runs if run.kind != "text")
        self.trace.record(
            Stage.EXTRACT, "read_runs", Disposition.ACCEPTED,
            zone_index=index, seconds=time.perf_counter() - started,
            call=call, calls=made, kind=zone.kind.value, runs=marked,
        )

    def _extract(self, rectified: Rectified, document: Document) -> None:
        """Fill each incomplete Zone from a full-resolution crop of it.

        Partial output is the useful output. A Zone that cannot be read is
        recorded as a Failure and left incomplete — it renders as a skeleton,
        which is unmistakably "this did not work" in a way that silently absent
        content is not — and the remaining Zones are still extracted.

        A Zone that *was* read but only at reduced resolution gets a Caveat
        instead, which is a different thing and not a milder Failure: it keeps its
        content, because degraded content beats none, and calling it a failure
        would have the render say a Zone could not be read directly above the
        content it read.

        The lists are rebuilt each round rather than appended to, so a Zone read
        successfully on round two does not keep round one's Failure. What
        classification found is seeded back in, because that pass ran once and
        its findings are as true on round two as they were on round one.
        """
        document.failures = list(self.classification_failures)
        document.caveats = list(self.classification_caveats)
        for index, zone in enumerate(document.zones):
            if zone.complete or index in self.unclassified:
                continue

            # Spec 0014, step 2: what `_read_unclaimed` kept was read beside
            # the reading this replaces.
            zone.extra = []
            extractor = for_kind(zone.kind)
            asked = zone.kind.value
            mark, started = self.trace.next_call, time.perf_counter()
            try:
                # Spec 0012, G3b: a table's grid is measured here, where the
                # page's drawing is known, and stated to the model as it is.
                grid = (_grid(_ink(rectified), zone, document.furniture)
                        if zone.kind is Kind.TABLE else None)
                extractor.extract(
                    rectified.image, zone, self.engines.extract, document.hint,
                    grid=grid,
                )
            except NotPairs as diagnosis:
                self._record_extract(index, asked, extractor, rectified, zone,
                                     mark, started, Disposition.REROUTED,
                                     error=f"{type(diagnosis).__name__}: {diagnosis}",
                                     furniture=document.furniture)
                try:
                    self._reread_as_prose(rectified, document, index, diagnosis)
                except Exception as error:
                    document.failures.append(
                        failed(index, zone, error,
                               share=_share_of(rectified.image, zone))
                    )
                    continue
            except Exception as error:
                self._record_extract(index, asked, extractor, rectified, zone,
                                     mark, started, Disposition.REJECTED,
                                     error=f"{type(error).__name__}: {error}",
                                     furniture=document.furniture)
                document.failures.append(
                    failed(index, zone, error,
                           share=_share_of(rectified.image, zone))
                )
                continue
            else:
                self._record_extract(index, asked, extractor, rectified, zone,
                                     mark, started, Disposition.ACCEPTED,
                                     furniture=document.furniture)
                self._read_runs(rectified, document, index)

            note = resolution_caveat(rectified.image, zone)
            if note is not None:
                document.caveats.append(
                    Caveat(zone_index=index, kind=zone.kind.value, note=note)
                )
                self.trace.record(
                    Stage.EXTRACT, "resolution_caveat", Disposition.ACCEPTED,
                    zone_index=index, kind=zone.kind.value, note=note,
                )

            # A table whose rows were reconciled against its header says so.
            # Read back off the IR rather than reported out of `wire.py` — see
            # `wire.table_repairs` for why that seam stays where it is.
            for repair in table_repairs(zone) if zone.kind is Kind.TABLE else []:
                document.caveats.append(
                    Caveat(zone_index=index, kind=zone.kind.value, note=repair)
                )
                self.trace.record(
                    Stage.EXTRACT, "table_repair", Disposition.ACCEPTED,
                    zone_index=index, kind=zone.kind.value, note=repair,
                )

        self._restore_vetoed_captions(document)
        self._measure_shortfalls(rectified, document)

    def _restore_vetoed_captions(self, document: Document) -> None:
        """A caption the veto refused, which the reading then dropped, is the
        Zone's Title after all — spec 0010, step A1.

        **The veto keeps its job and loses only its side effect.** It refuses
        a Title so that the Kind is asked on the whole crop, heading row
        included, which is what it is for: equal column counts either side of
        the cut can mean a table's heading row. But a structured reading has no
        slot for a line that spans the region, so a refused caption that really
        was one vanished from the page. Over sweep `S4-sweep` the veto fired
        five times and every one was a caption — letter-spaced capitals count
        as many columns as the body under them — and four of the five were
        then printed nowhere: `darkdeck_0009`'s `OPEN RISKS` and `DECISIONS
        WANTED`, `form_0007`'s `2. MEMBERSHIP CATEGORY` and `report_0011`'s
        `TABLE 1 — MOVEMENTS AND REVENUE BY BERTH`.

        **Only where nothing in the Zone prints it**, so a heading row the veto
        rightly refused and the reading kept as a row is never doubled. The
        fifth, `P95 LATENCY`, came back as a pair's label and value and stays
        as read. Nothing is invented: the model read the line as a caption, and
        the page prints it.
        """
        for index, refused in sorted(self.vetoed.items()):
            if index >= len(document.zones):
                continue
            zone = document.zones[index]
            if zone.title or not zone.complete or prints(zone, refused):
                continue
            zone.title = refused
            self.trace.record(
                Stage.EXTRACT, "vetoed_caption", Disposition.ACCEPTED,
                zone_index=index, kind=zone.kind.value, title=refused,
                changed=[Change(path=f"zones[{index}].title",
                                before=None, after=refused)],
                reason="the caption the grid veto refused is printed nowhere "
                       "in the reading, so it is the Zone's Title",
            )

    def _measure_shortfalls(self, rectified: Rectified,
                            document: Document) -> None:
        """Which Zones came back holding less than their own crop.

        **Over every complete Zone, not only the ones this round extracted.**
        The loop above skips a Zone that is already complete, so computing this
        inside it would record a shortfall on round one and lose it on round
        two — the same shape as the bug `classification_failures` exists to
        avoid, and invisible today only because an unattended Conversion
        converges in one round. A finding that disappears when a later round
        happens to run is worse than one that was never made, because the run it
        vanishes from is the run somebody trusted.
        """
        document.shortfalls = []
        for index, zone in enumerate(document.zones):
            short = shortfall(_ink(rectified), zone, index, document.furniture)
            if short is None:
                continue
            document.shortfalls.append(short)
            self.trace.record(
                Stage.EXTRACT, "shortfall", Disposition.REJECTED,
                zone_index=index, kind=zone.kind.value,
                printed_lines=short.printed_lines,
                read_lines=short.read_lines,
                ink_share=short.ink_share,
                consequence="the Zone was read, and read short: the finding "
                            "says so rather than the render quietly holding "
                            "less than the page",
            )

    def _record_extract(self, index: int, asked: str, extractor: object,
                        rectified: Rectified, zone: Zone, mark: int,
                        started: float, disposition: Disposition,
                        error: str | None = None,
                        furniture: Sequence[Furniture] = ()) -> None:
        """One Event for one extraction attempt, however it ended.

        A method rather than three copies inline because the four exits from the
        loop above — read, re-routed, refused, raised — must record the *same*
        fields or the sheet's per-Zone view develops holes exactly where a Zone
        went wrong, which is the only place anybody looks.

        The wire-level repairs — the split-header join and the empty-row drop —
        are deliberately *not* recorded here. They happen inside `wire.py`, which
        maps a response without knowing which Zone index it belongs to, and
        threading a collector down through `contents_into` would put diagnostic
        plumbing in the shipping path for something the sheet can obtain safely:
        the raw answer is in the Call and the mappers are pure, so
        `tools/inspect_run.py` re-runs those same functions on that same input and
        reports the difference. What is recorded here is the count each Kind ended
        with, which is the other half of that comparison.
        """
        call, made = self.trace.calls_since(mark)
        self.trace.record(
            Stage.EXTRACT, "extract", disposition,
            zone_index=index, seconds=time.perf_counter() - started,
            call=call, calls=made,
            kind_asked=asked, extractor=type(extractor).__name__,
            crop=_crop_data(rectified.image, zone),
            grid=_grid_data(_ink(rectified), zone, furniture),
            rows=len(zone.rows), pairs=len(zone.pairs), blocks=len(zone.blocks),
            complete=zone.complete, error=error,
            changed=[Change(path=f"zones[{index}].complete",
                            before=False, after=True)] if zone.complete else [],
        )

    def _reread_as_prose(self, rectified: Rectified, document: Document,
                         index: int, diagnosis: NotPairs) -> None:
        """Read a Zone again as prose, because the Pairs Extractor says it is.

        The one place a Kind decided by classification is overturned later, and it
        is overturned on evidence rather than on a second opinion: an unlabelled
        value means there is no label printed beside it, which is a fact about the
        page. The classifier had only the crop; this had the crop *and* what the
        model read off it.

        What it recovers is measured. On `invoice_0001` Zone 3 is the
        `Acme Corp.` / `John Doe` / `john@example.com` block — prose, classified
        `pairs` in every run ever taken. The Pairs mapper rejected it on the
        unlabelled email, and because the mapper raises before anything reaches
        the Zone, all three lines were discarded, including the two that had
        bound correctly. The Zone rendered as an empty skeleton.

        Kind is corrected on the Zone rather than left as classified, so the
        Document records what it was actually converted as and the renderer
        reaches for the right template. The Caveat is what keeps that honest: an
        operator reading the render can see the Kind was overturned and by what.
        Not a Failure, because the Zone has its content — a Failure here would put
        "this could not be read" directly above the text that was read, which is
        the confusion `_extract` already avoids for reduced-resolution reads.

        One extra call, only on this failure path. Narrow on purpose: `pairs` is
        the only Kind whose Extractor can produce evidence about the Kind itself,
        so there is no symmetric rule to write for the others and inventing one
        would be guessing.
        """
        zone = document.zones[index]
        log.info(
            "Zone %d was classified %s, and the Pairs Extractor disagrees (%s) — "
            "reading it again as prose", index, zone.kind.value, diagnosis,
        )
        was = zone.kind.value
        zone.kind = Kind.PROSE
        mark, started = self.trace.next_call, time.perf_counter()
        for_kind(Kind.PROSE).extract(
            rectified.image, zone, self.engines.extract, document.hint
        )
        call, made = self.trace.calls_since(mark)
        self.trace.record(
            Stage.EXTRACT, "reroute", Disposition.REROUTED,
            zone_index=index, seconds=time.perf_counter() - started,
            call=call, calls=made,
            changed=[Change(path=f"zones[{index}].kind",
                            before=was, after=Kind.PROSE.value)],
            trigger=f"{type(diagnosis).__name__}: {diagnosis}",
            kind_before=was, kind_after=Kind.PROSE.value,
            blocks=len(zone.blocks),
            lines=sum(len(block.lines) for block in zone.blocks),
            complete=zone.complete,
        )
        document.caveats.append(
            Caveat(
                zone_index=index,
                kind=Kind.PROSE.value,
                note=(
                    f"classified {was}, re-read as prose: the {was} Extractor "
                    f"found an unlabelled value, which is evidence the region is "
                    f"not {was} — {diagnosis}"
                ),
            )
        )

    def _audit(self, rectified: Rectified, document: Document) -> None:
        """Find content no Zone covers.

        Every other safeguard catches content that is *wrong*. This is the only
        one that catches content that is *absent* — a failure which otherwise
        leaves the IR internally consistent and every Probe passing.

        **Two layers, and only the cheaper one is built.**

        What runs is `uncovered_ink`: dark pixels the Zones do not account for,
        grouped and reported as Gaps. It is not a model, which is the entire
        reason it is allowed to run — an auditor sharing the layout model's
        weights shares the blind spot that caused the miss, and would pass every
        document while reporting confidence it has not earned. A threshold on
        pixels shares nothing with the model, so it cannot be fooled the same
        way. Measured on `example/invoice.png`: correct geometry produces no Gaps
        and the sliver geometry of `debug/runs/25-invoice-qwen35-longedge768/`,
        which lost the entire line-item table, produces Gaps over 21% of the
        page.

        What is *not* built is the Coverage Audit proper. Ink is not content:
        this cannot tell a stamp from a lost paragraph, and it is entirely blind
        to a Zone that covers its content and reads it wrongly — which is the
        larger half of the problem. `OllamaEngine.audit_coverage` still raises,
        `DTH_AUDIT_MODEL` still names the layout model and is still never sent
        anywhere, and `config.DEFAULT_AUDIT_MODEL` still needs re-pointing at a
        second family before that method is written. Nothing here discharges that
        debt; it narrows the window in which the debt is invisible.
        """
        # `_read_fields` can widen a Zone's box to its marks, and so change
        # which fills the Zones hold — spec 0018, A1.
        _ground(rectified, document, document.zones)
        document.gaps = gaps(_ink(rectified), document.zones)

    def _climb_ladders(self, rectified: Rectified, document: Document) -> None:
        """Advance every unresolved item one Rung.

        Probe findings are used here to decide *which* cells to look at again,
        at what resolution, with which Engine. Their expected values never reach
        a prompt: a failed Probe cannot distinguish a misread line item from a
        misread total, so supplying the expected value would force agreement
        with whichever number happened to be wrong. See docs/adr/0004.

        Nothing to climb yet. Only one Engine reads each cell in this slice, so
        no two readings can disagree, so no cell is ever Disputed. Escalation
        arrives with a second Engine and not before.
        """
        return

    def _ask_convergence(self, document: Document) -> Answer:
        """Show a Draft beside the Source Image and ask whether it is converging."""
        return self.handler.ask(
            Question(
                kind="convergence",
                text="Does this match the document?",
                options=["looks right", "keep refining"],
                draft_html=render(document),
            )
        )

    def _apply(self, answer: Answer, document: Document) -> None:
        """Fold a structured answer into the IR; carry a note into the next prompt.

        A note is appended to the Hint rather than interpreted. That is the whole
        of it for now: interpreting prose is a later milestone, and when it
        arrives its job is to map prose onto the structured `choice` values, not
        to edit the IR.
        """
        if answer.note:
            document.hint = (
                f"{document.hint}\n{answer.note}" if document.hint else answer.note
            )


def convert(source: Path | str, *, handler: CheckpointHandler | None = None,
            engines: EngineSet | None = None) -> Document:
    """Convert one Source Image. The library entry point.

    The CLI, the eval harness and any future UI all come through here, so what
    gets measured is what ships.
    """
    conversion = Conversion(
        source=Path(source),
        engines=engines or default_engines(),
        handler=handler or NullHandler(),
    )
    return conversion.run()
