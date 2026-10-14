"""Zones from a trained layout detector, run as ONNX on the CPU.

The layout pass is the least stable step in the pipeline, and every measurement
says the instability is structural rather than a wording bug. Three prompt
instructions have been measured ignored. Resolution does nothing — runs 26-28
returned byte-identical geometry at 384, 512 and 862. Model swaps changed the
failure rather than removing it. A measured region ceiling worked as a lever and
was read as a target, costing `invoice_0001` its zero-mismatch Conversion twice.

At `DTH_LAYOUT_LONG_EDGE=384`, Qwen3-VL's patch-16 encoder with a 2x2 spatial
merge resolves the whole of `invoice_0001` into roughly **12x8 visual tokens**,
so a 3px panel border is a tenth of one token — and the coordinates are then
decoded as text, with no localization objective anywhere in the loop. A detector
has neither problem. It sees the full-resolution Rectified Image, it was trained
against IoU, and it returns the same boxes for the same pixels every time.

**Measured before it was written.** `tools/detector_probe.py` scored both
candidates on all five fixtures against the shared ruler in `geometry_score`, at
nine confidences, raw and post-processed — `debug/runs/65-detector-bakeoff`. At
one threshold across the whole corpus, with no per-page tuning:

| arm | conf | worst covered | splits | zones vs 6, 10, 2, 5, 9 |
|---|---|---|---|---|
| `heron` + outermost | 0.40 | **1.00** | **0** | 6, 14, 3, 6, 17 |
| `doclayout_yolo` + outermost | 0.15 | **1.00** | **0** | 6, 12, 3, 6, 14 |
| `doclayout_yolo` raw | 0.40 | 0.61 | 0 | 5, 9, 2, 7, 13 |
| `heron` raw | 0.60 | 0.45 | 44 | 16, 52, 4, 12, 22 |

The VLM, for scale: worst covered 0.42 across the same five, 173 splits, and
187s on `invoice_0001` against this module's 0.6s.

**Only what a detector can honestly report is reported.** `Kind` is a
placeholder, because `_classify` overwrites every Kind from the Zone's own crop
moments later and scores 6/6 doing it. `Role` is very nearly a placeholder too:
it is a CSS class in `render.py` and nothing else — the Probes navigate by
`RowRole`, one level down, so a Zone whose Role is wrong cannot cost
`invoice_0001` its 385.00 column sum.

**Off unless asked for.** `DTH_LAYOUT_DETECTOR` unset means the Engine set is
built exactly as it was, and a run is byte-identical to one from before this
existed.
"""

from __future__ import annotations

import ast
import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ..ir import BBox, Kind, Role, Zone
from ..preprocess import ImageArray, _cv2, content_ink, snap_to_ink
from ..wire import bands_from_boxes

MODELS = Path(__file__).resolve().parent.parent.parent.parent / "models"
"""Where `tools/fetch_layout_models.py` puts the weights. Gitignored."""

FLOOR = 0.05
"""Everything at or above this leaves a detector, before any threshold.

Inference runs once per page and thresholding is a filter over its result, so a
low floor costs nothing and lets `tools/detector_probe.py` sweep nine
confidences from one forward pass.
"""


class DetectorUnavailable(RuntimeError):
    """The weights are missing, or `onnxruntime` is not installed."""


@dataclass(frozen=True)
class Detection:
    """One box a detector reported, in normalised page coordinates.

    `label` is the detector's own class name, kept verbatim rather than mapped to
    a `Kind`. Two vocabularies agreeing would be an invention: nothing downstream
    reads it, because the Kind that matters comes from the crop.
    """

    left: float
    top: float
    right: float
    bottom: float
    label: str
    score: float


class Detector(Protocol):
    """A source of boxes from pixels, with no model call and no prompt."""

    name: str
    license: str
    confidence: float

    def detect(self, image: ImageArray) -> list[Detection]:
        """Every detection at or above `FLOOR`, in normalised coordinates."""
        ...


CONTAINED = 0.70
"""How much of a box must lie inside a larger one before it is that one's inside.

Not 1.0, because detector edges disagree by a few pixels on boxes that plainly
nest, and not 0.5, because two Zones side by side in a Band can share a third of
their area without either containing the other.
"""


def outermost(found: list[Detection]) -> list[Detection]:
    """Keep the containers, drop what they contain.

    **This is the change that made either detector usable, and it was measured
    before it was believed.** Both models describe a panel and then describe the
    rows printed inside it. Raw, that costs `heron` everything: 137 to 231 boxes
    on pages holding 6 and 10 regions. But the shortfall is not a detection
    failure — on `invoice_0002` the ink view shows **no unclaimed ink at all**
    while a third of it sits under two boxes. Nothing is missed; the level is
    wrong, at every confidence, so no threshold reaches it.

    Keeping the container is the one-line reading of "a panel and the rows
    printed inside it are one region" that the vision layout prompt spent three
    runs asking a model to perform and being ignored about. Applied, both detectors
    reach covered 1.00 and splits 0 on all five fixtures.

    Ties go to area, so of two boxes that contain each other — one region found
    twice under two class names — the larger survives.
    """
    order = sorted(range(len(found)), key=lambda i: -_area(found[i]))
    kept: list[int] = []
    for index in order:
        if not any(_covered_by(found[index], found[other]) >= CONTAINED
                   for other in kept):
            kept.append(index)
    return [found[index] for index in sorted(kept)]


def open_unsure_containers(kept: list[Detection], confident: list[Detection],
                           mask: ImageArray) -> list[Detection]:
    """A container of text holding a picture the detector is surer of than
    of the container is its parts — spec 0013, step 4.

    `prefer_container`'s rule, on the boxes `outermost` kept: a picture is a
    region of its own, and gathered into a text Zone it is read as text.
    `certificate_0021`'s signature row is a `key_value_region` at 0.40, the
    threshold itself, over two signature blocks at 0.60 and 0.50 and the
    seal between them, a `picture` at 0.90. Kept, the row was one Zone, read
    as one paragraph, the two signatures' lines interleaved round the
    seal's.

    The parts are the outermost of the confident boxes the container holds,
    each surer than it, carrying `SPLIT_INK` of its ink between them, so no
    ink leaves every crop. **Without the picture the rule is too wide**, and
    was measured so over all twenty-one: a container less sure than each of
    its parts also opens `invoice_0002`'s pairs into their fourteen words,
    `nonlatin_0014`'s totals line into label and value, and darkdeck's and
    the ticket's pictures. With it, it opens the certificate's row alone.
    """
    out: list[Detection] = []
    for parent in kept:
        inside = [box for box in confident if box is not parent
                  and _covered_by(box, parent) >= CONTAINED]
        parts = outermost(inside)
        if (parent.label != "picture" and len(parts) >= 2
                and any(part.label == "picture" for part in parts)
                and all(part.score > parent.score for part in parts)
                and _ink_share(mask, parts) >= SPLIT_INK * _ink_share(mask, [parent])):
            out.extend(parts)
        else:
            out.append(parent)
    return out


def without_overreaching_pictures(found: list[Detection],
                                  mask: ImageArray) -> list[Detection]:
    """Drop a `picture` that is a surer picture plus whatever stands beside it.

    **Spec 0007 Phase A3, 2026-09-26.** `invoice_0002`'s ACME tile is detected
    — `picture` at 0.76 — and so is the address printed beside it, `text` at
    0.44. Heron also draws a third box, `picture` at 0.72, round both, and
    `outermost` keeps the largest: the tile and the address became one Zone,
    read as prose, and the scorer counted the tile as lost. Found by running
    the detector's steps one at a time; the tile survives the threshold and is
    gone after `outermost`, and nothing later brings it back.

    **Two tests, together, and each is load-bearing.** Measured over every
    `picture` holding another `picture` across all fifteen documents, after the
    threshold:

        document         inner scored higher   ink outside the inner pictures
        invoice_0002     yes, 0.76 > 0.72      2,243 px   <- the tile and its address
        darkdeck_0009    yes, four of them     0 px       <- a row of four cards
        sample_css_0004  yes                   0 px
        invoice_0001     no, 0.58 < 0.80       0.87 of its ink
        sample_css_0004  no                    0.73 of its ink

    - *Scored higher*, because the detector is surer of the smaller picture
      than of the larger one. `invoice_0001` is why this is needed: its logo
      is `picture` 0.80 round an icon at 0.58 and a wordmark heron also reads
      as text, and without this test the logo is cut in two.
    - *Ink outside*, because a picture that is only smaller pictures is a
      group of them and not a picture beside something else. `darkdeck_0009`'s
      four KPI cards are that shape; splitting them is a different question
      and not this one's.

    So the rule has no constant: zero pixels against 2,243, with nothing
    between. Run offline through the whole layout stage, it changes one box on
    one document of fifteen — `invoice_0002`'s, into the tile and the address.

    Dropping the outer box is enough: `outermost`, run next, then keeps the
    tile and the box round the address as it would on any page, and the ink
    the outer box covered is all inside one or the other.
    """
    def ink_outside(outer: Detection, inner: list[Detection]) -> int:
        height, width = mask.shape[:2]

        def pixels(box: Detection) -> tuple[slice, slice]:
            left = max(0, min(width, int(round(box.left * width))))
            top = max(0, min(height, int(round(box.top * height))))
            right = max(left, min(width, int(round(box.right * width))))
            bottom = max(top, min(height, int(round(box.bottom * height))))
            return slice(top, bottom), slice(left, right)

        region = np.zeros((height, width), dtype=bool)
        region[pixels(outer)] = True
        for box in inner:
            region[pixels(box)] = False
        return int(np.logical_and(mask > 0, region).sum())

    def overreaches(outer: Detection) -> bool:
        if outer.label != "picture":
            return False
        inner = [box for box in found if box is not outer
                 and box.label == "picture"
                 and _covered_by(box, outer) >= CONTAINED]
        return (any(box.score > outer.score for box in inner)
                and ink_outside(outer, inner) > 0)

    return [box for box in found if not overreaches(box)]


def without_enclosed(found: list[Detection],
                     shape: tuple[int, int] | None = None) -> list[Detection]:
    """Drop every box lying wholly inside another, once the unions have run.

    **`outermost` runs first, and two of the steps after it undo its
    guarantee.** `attach_trailing_rows` and `attach_headings` each replace two
    boxes with their union, and a union is larger than either half — large
    enough, on three corpus documents of fifteen, to swallow a neighbour that
    is then left standing:

        statement_0006  the table grows down to its Totals row and takes in
                        the two amounts printed on it, 5,772.36 and 3,586.14
        menu_0012       `To begin` inside the menu its sibling heading joined
        cv_0013         `Senior Structural Engineer` inside EXPERIENCE

    Each of the four was read **twice** — in its own crop and again in the crop
    around it — and printed twice. `menu_0012`'s is the "To begin" echo that
    `wire._without_title_echo` could not reach, because the two readings sit in
    different Zones. And a Band is a stripe whose Zones are its columns, so one
    box inside another in the same Band is not two Zones: `wire.validate_bands`
    refused all three pages, and `DTH_SNAP_ZONES` was blamed for it. The snap
    returned these boxes unchanged; the enclosure was here.

    **Wholly inside, by its four edges — not `CONTAINED`.** Dropping a box is
    safe exactly when all of it is inside another crop, because then no ink
    leaves the page. Measured after the unions, over all fifteen documents: the
    four are inside on all four edges, and the only other overlap is
    `nonlatin_0014`'s top-right pairs box at **0.696** of its area, with nothing
    between. `CONTAINED` would sit 0.004 above it, and dropping that box loses
    `ΤΠΥ = 2026/0417`, which no other crop holds. So the test is the edges and
    there is no constant to tune.

    Of two identical boxes the first survives, so a region found twice is kept
    once rather than lost.

    **Inside to a pixel**, given the page's `shape` — spec 0013, step 4.
    `certificate_0021`'s title grew over one of the three stars under it,
    and the middle star's foot stood 0.08 px below that box: kept, it
    overlapped the title and the snap was refused for the whole page. An
    edge within a pixel of the container's is on it.
    """
    slack_y, slack_x = (1 / shape[0], 1 / shape[1]) if shape else (0.0, 0.0)

    def encloses(outer: int, inner: int) -> bool:
        if not _within(found[inner], found[outer], slack_x, slack_y):
            return False
        return _area(found[outer]) > _area(found[inner]) or outer < inner

    return [
        detection for inner, detection in enumerate(found)
        if not any(encloses(outer, inner)
                   for outer in range(len(found)) if outer != inner)
    ]


HEADINGS = frozenset({"section_header", "title", "caption",
                      "table_caption", "figure_caption"})
"""Detector classes that name the region beneath them rather than being one.

Both vocabularies are covered: `section_header` / `caption` are heron's,
`title` / `table_caption` / `figure_caption` DocStructBench's.
"""

HEADING_GAP = 0.05
"""How far below a heading its content may start, as a fraction of page height.

**The shipped rule, and a number nobody can defend.** Kept as the default until
`DTH_HEADING_RULE=relative` has been measured in a live Conversion; the
replacement is `HEADING_GAP_RATIO` below, and the evidence against this one is
recorded there rather than repeated here.

**Both of the lists this docstring used to carry were wrong**, and so was spec
0005's correction of them. They were taken post-snap, while `attach_headings`
runs on raw detections — see the order in `LayoutEngine.detect_zones` — and their
verdicts were read off the fixtures' typed rectangles rather than off the Zone
contents those rectangles were supposed to describe. Re-derived pre-snap, this
constant makes **4 wrong calls of 14**: it merges `invoice_0002`'s `Invoice`
title into the line below it and `sample_semantic_0005`'s masthead into the nav
bar, and it fails to merge either of `sample_css_0004`'s two cards.
"""

HEADING_GAP_RATIO = 1.77
"""How much further below a heading its content may sit than the heading sits
below whatever precedes it.

**A heading is closer to what it names than to what it follows.** That is the
whole rule, and it is a fact about typesetting rather than about these five
pages, which is what `HEADING_GAP` never was.

The measurement, pre-snap, heron at 0.40, over all 14 heading cases in the
corpus, with each verdict read from the fixture builder's Zone *contents*:

    gap alone       merge  0.011 0.024 0.028 0.029 0.030 0.038 0.040 0.044 0.056 0.064
                    leave  0.025 0.032 0.081 0.147          <- interleaved

No absolute threshold separates those, and the best one possible still gets two
wrong. Nor does either candidate spec 0006 proposed: `gap / heading height`
leaves 3 wrong and `gap / median line gap` leaves 3 and is undefined on 6 of 14,
because a single-line box has no leading of its own to divide by.

Against the gap above, they separate: every true merge sits at **1.293 or less**
(`Company Details` over its panel body) and the nearest false one at **2.89**
(`sample_table_0003`'s page title over the table that is not its body). 1.9 is
central, with 1.47x margin below and 1.52x above, against `HEADING_GAP`'s 1.13x.

**It is a plateau rather than a point**, which is the part worth trusting: every
combination of this in {1.4, 1.6, 1.9, 2.2, 2.5, 2.8} with `HEADING_GAP_MAX` in
{0.08, 0.10, 0.12} produces an identical answer on all five fixtures.

**Two cases it still gets wrong, and they cost nothing.** `invoice_0002`'s
`Invoice` and `sample_semantic_0005`'s `The Weekly Digest` are page titles above
a metadata line, and both merge when the reference says leave. Simulated end to
end, un-merging them changes no finding on either fixture — the references split
`<header><h1>+<nav>` into two Zones while making `<div class="card"><h2>+<p>` one,
and that inconsistency is a fixture question, filed in spec 0006 and deliberately
not answered inside a geometry change.

**1.9 became 1.77 in spec 0013's step 4, taken again over all twenty-one.**
The true merges now reach **1.664** (`letter_0016`'s signature over its name
and title) with `cv_0013`'s name at 1.552, and the nearest leave is
**1.873**: `certificate_0021`'s name, set 0.020 below `This is to certify
that` and 0.038 above the paragraph its sentence runs on into, which 1.9
drew into that paragraph's Zone. Next is `invoice_0002`'s `Services /
Products` at 1.992. 1.77 is the geometric middle of 1.664 and 1.873, and
over the twenty-one the layout front moves the certificate alone.
"""

HEADING_GAP_MAX = 0.10
"""An outer bound on the ratio, as a fraction of page height.

`HEADING_GAP_RATIO` is the test; this only says that no heading names a region a
tenth of a page away however much white space precedes it. It exists for one
real case — `invoice_0002`'s `Services / Products`, whose own panel is empty, so
the nearest box below it is the *next* section's body at a gap of 0.147.

The window is 0.064 (the widest true merge, `sample_css_0004`'s second card) to
0.147, so 0.10 has 1.56x below and 1.47x above. Without it the ratio alone has to
carry that case and its upper bound tightens to 1.992, which is where the old
1.13x-margin problem starts again.
"""


def attach_headings(found: list[Detection], *,
                    relative: bool = False) -> list[Detection]:
    """Fold each heading into the region it names.

    Run 67 is why this exists. With every heading standing as its own Zone,
    `invoice_0002` came back with all five of its panel titles reported as
    `None` — `Company Details`, `Customer Details`, `Services / Products`,
    `Comments / Notes`, `Payment Method` — because `_classify` reads a Zone's
    title off that Zone's own crop, and the crop no longer contained it.

    So this is not tidying the zone count. It is putting the title back inside
    the picture the classifier is shown, which is the only way `zone.title` can
    be populated at all, and `with_grid` then subtracts the Title's line from the
    row count it states.

    **A heading claims at most one region and a region at most one heading.**
    Both directions matter: without the first, two panel captions in a column
    swallow the same block; without the second, a heading merges into a region
    that already has one above it.

    `relative` picks which test decides how far is too far: `HEADING_GAP` by
    default, `HEADING_GAP_RATIO` against the gap above when set. Everything else
    here is the same either way — the flag changes one predicate, not the
    claiming.
    """
    order = sorted(range(len(found)), key=lambda i: (found[i].top, found[i].left))
    claimed: dict[int, int] = {}
    for index in order:
        if found[index].label not in HEADINGS:
            continue
        target = _region_below(found, index, relative=relative)
        if target is not None and target not in claimed.values():
            claimed[index] = target

    merged, absorbed = [], set(claimed)
    for index in order:
        if index in absorbed:
            continue
        heading = next((h for h, t in claimed.items() if t == index), None)
        merged.append(found[index] if heading is None
                      else _union(found[heading], found[index]))
    return merged


def _region_below(found: list[Detection], heading: int, *,
                  relative: bool = False) -> int | None:
    """The nearest non-heading box under this one, near enough to belong to it.

    "Under" is any horizontal overlap at all rather than a share of the width:
    a panel caption is short and left-aligned while the block it names is
    indented, and requiring 30% overlap missed `Company Details` over its own
    panel by three percentage points.

    **Nearness is decided after the candidate is chosen, not while choosing
    it.** The nearest box below a heading is the only one that can be its body,
    so the distance test belongs to that box rather than to the search — and
    written the other way, a heading whose body is too far away silently adopts
    the box below *that* one instead.
    """
    above = found[heading]
    below = [
        index for index, box in enumerate(found)
        if index != heading
        and box.label not in HEADINGS
        and box.top >= above.bottom - 0.01
        and min(box.right, above.right) > max(box.left, above.left)
    ]
    if not below:
        return None

    nearest = min(below, key=lambda index: (found[index].top, found[index].left))
    gap = found[nearest].top - above.bottom
    if not relative:
        return nearest if gap <= HEADING_GAP else None
    return (nearest if gap <= HEADING_GAP_RATIO * _gap_above(found, heading)
            and gap <= HEADING_GAP_MAX else None)


def _gap_above(found: list[Detection], heading: int) -> float:
    """White space between this heading and whatever is printed above it.

    **The top of the page counts as a box.** Without that fallback the rule is
    not total: four of the corpus's fourteen headings have nothing above them
    that overlaps horizontally — a panel title in the right-hand column, a
    masthead — and their gaps below are non-monotonic in every absolute measure
    (leave at 0.025, leave at 0.032, *merge* at 0.044, leave at 0.081), so no
    threshold can order them. Measured to the page edge they separate with the
    same ratio as everything else.

    **Never negative.** "Above" tolerates the same 0.01 of overlap `_region_below`
    does, because detector edges disagree by a few pixels on boxes that plainly
    stack — so a box that slightly overlaps this heading would otherwise return a
    negative distance, and a negative threshold rejects even a region the heading
    sits directly on top of. No box in the corpus reaches that; it is clamped so
    the rule cannot invert rather than because something inverted it.
    """
    box = found[heading]
    above = [
        other.bottom for index, other in enumerate(found)
        if index != heading
        and other.bottom <= box.top + 0.01
        and min(other.right, box.right) > max(other.left, box.left)
    ]
    return max(0.0, box.top - max(above) if above else box.top)


def _union(first: Detection, second: Detection) -> Detection:
    """One box over both, keeping the more confident label.

    The label is only ever read by `tools/detector_probe.py`, so which one wins
    decides nothing — but a merged box labelled `section_header` would read, in
    a contact sheet, as though a caption had swallowed a table.
    """
    stronger = first if first.score >= second.score else second
    return Detection(
        left=min(first.left, second.left), top=min(first.top, second.top),
        right=max(first.right, second.right),
        bottom=max(first.bottom, second.bottom),
        label=stronger.label, score=stronger.score,
    )


TRAILING_GAP = 0.03
TRAILING_HEIGHT = 0.30
"""When a strip printed under a table is that table's last row.

`invoice_0001`'s total is set below the line-item rules and heron reports it
separately, as a `key_value_region` — so the table Zone reaches 0.883 where the
reference reaches **0.932**, and the Zone that should carry the summary row
carries none. Run 67 shows the consequence: the column-sum Probe reported
nothing where it had reported 385.00, because `probes.py` reconciles a table's
`SUMMARY` rows against its `DATA` rows and both have to be in one Zone.

**One positive example, and it is worth saying so.** Across all five fixtures
exactly two boxes sit under a table sharing its span:

    the total row       gap 0.017   height 0.12x the table    <- belongs to it
    the second table    gap 0.040   height 2.33x the table    <- does not

Both bounds separate them with room, and the class test rules the second one out
on its own — a table under a table is the next table. But a rule fitted to one
example is a rule with one example behind it, whatever its margins, and this
project has a docstring about generalising from exactly that.
"""

SPLITTABLE = frozenset({"table"})
"""Which classes may be taken apart again after `outermost` has closed them.

**One class, deliberately.** `outermost` exists because both detectors describe
a panel and then its rows, and undoing that is undoing the change that made
either usable. Two tables stacked with no gap between them are the one case
where the container is genuinely two regions and not one region described twice:
tables do not nest in these documents, so a `table` holding `table`s is a fact
about the page rather than the same region found under two names.

Swept across all five fixtures with no class restriction, the rule fires on
`text` holding `text` — that is, on prose split into its printed lines — which
is exactly the failure `outermost` prevents.
"""

SPLIT_INK = 0.98
"""How much of a region's ink its parts must carry before they replace it.

The test that separates a real split from a spurious one. On `invoice_0001` the
two proposed sub-tables carry **1.00** of the merged box's ink and are the right
answer; on `sample_table_0003` two low-confidence proposals carry **0.46**, and
that is one table with two fragments guessed inside it.
"""


def split_containers(kept: list[Detection], pool: list[Detection],
                     mask: ImageArray) -> list[Detection]:
    """Take a region apart where the detector already proposed its parts.

    **The split was never missing — `outermost` discarded it.** On
    `invoice_0001` heron reports `table` at 0.95 over both printed tables, and
    also reports the Payment Method table at 0.22 and the line-item table at
    0.32. Keeping the container threw the second pair away, and run 67 shows
    what that cost: one Zone holding two header rows, the total row exiled into
    a Zone of its own, and the column-sum Probe reconciling nothing where it had
    reported 385.00.

    So the fast non-model split is the detector's own suppressed proposals,
    filtered by three tests it has to pass together — same class as the parent,
    no overlap between the parts, and `SPLIT_INK` of the parent's ink between
    them. Recovered this way the parts score IoU 0.860 and 0.784 against the
    reference rectangles, where the merged box scores 0.245.

    Sub-threshold detections are read here on purpose. They are already computed
    — inference runs once and confidence is a filter over its result — so this
    costs arithmetic and no second forward pass.
    """
    split = []
    for parent in kept:
        parts = _parts_of(parent, pool)
        if len(parts) >= 2 and _ink_share(mask, parts) >= (
                SPLIT_INK * _ink_share(mask, [parent])):
            split.extend(parts)
        else:
            split.append(parent)
    return split


SECTIONED = frozenset({"form", "document_index"})
"""Which containers the detector's own section proposals may take apart —
spec 0009, step C. The two classes the corpus measures holding sections.

`SPLITTABLE`'s reason binds here too. Over all fifteen pages, the two rules
below fire on exactly two containers with this scope — `form_0007`'s `form`
and `menu_0012`'s `document_index` — and with no class restriction the
side-by-side rule fires on twelve more pages, every one a line of `text`, a
footer or a page header cut into its words.
"""


def cut_at_sections(kept: list[Detection], pool: list[Detection],
                    confidence: float,
                    drawn: Sequence[BBox] = ()) -> list[Detection]:
    """Cut a container at the section headings the detector found inside it.

    **`outermost` dropped them.** `form_0007` is one `form` at 0.97 over the
    whole form, and heron also reports a `section_header` on each printed
    section's heading bar — `2. MEMBERSHIP CATEGORY` and the three after it —
    which `outermost` discarded as the container's insides. Read as one
    Zone, the section headings vanished and the two-column fields became one
    list. Cut there, each part begins with its heading: the Zone convention,
    a heading and what it names one Zone.

    **Two or more headings below the container's first line**, so a
    container that opens with its only heading — every `menu_0012` column —
    stays whole. The cut falls midway between a heading and the content
    above it, so a heading bar is never sliced.

    **A heading inside a drawn rectangle is a field's value, not a section.**
    Heron labels `17 Bellwether Lane, Castleton`, printed inside the address
    field, `section_header` at 0.54 — within the real headings' 0.48-0.67,
    with the same `list_item` twin. `style.rectangles` finds that field
    around it and finds nothing around any of the five real headings, which
    sit on shaded bars. Cut there, the `Address` label and its value would
    be read in two Zones.
    """
    cut: list[Detection] = []
    for parent in kept:
        inside = [box for box in pool if box is not parent
                  and box.score >= confidence
                  and _covered_by(box, parent) >= CONTAINED]
        content = [box for box in inside if box.label not in HEADINGS]
        first = min((box.top for box in content), default=parent.bottom)
        tops = sorted({
            box.top for box in inside
            if box.label == "section_header" and box.top > first
            and not any(rect.left <= box.left and rect.top <= box.top
                        and box.right <= rect.right and box.bottom <= rect.bottom
                        for rect in drawn)
        })
        if parent.label not in SECTIONED or len(tops) < 2:
            cut.append(parent)
            continue
        edges = [parent.top, *(_gap_middle(top, content) for top in tops),
                 parent.bottom]
        cut.extend(replace(parent, top=upper, bottom=lower)
                   for upper, lower in zip(edges, edges[1:]))
    return cut


def _gap_middle(top: float, content: list[Detection]) -> float:
    """Midway between a heading's top and the content printed above it."""
    above = [box.bottom for box in content if box.bottom <= top]
    return (top + max(above)) / 2 if above else top


def split_side_by_side(kept: list[Detection], pool: list[Detection],
                       mask: ImageArray, confidence: float) -> list[Detection]:
    """Split a container into same-class parts that stand side by side.

    **`split_containers`' rule, turned on its side.** `menu_0012` is one
    `document_index` at 0.76 over both menu columns, and heron also reports
    each column, at 0.55 and 0.68, side by side. Read as one Zone, the two
    columns became one table with its headings paired across (`To begin |
    Main courses`). Split, each column is a Zone, and the two stand in one
    Band, which the band render draws side by side.

    **Side by side only — not `_stacked`**, the signal `prefer_container`
    already trusts: parts that sit one above another are one region printed
    as lines. And the headings standing above the parts, inside the
    container and outside every part, come out with them, as detections of
    their own: `attach_headings` runs next and folds each into the part it
    names. They count in the ink test, which `SPLIT_INK` would otherwise
    fail, since the two parts alone leave the headings' ink behind.
    """
    split: list[Detection] = []
    for parent in kept:
        parts = _parts_of(parent, pool, SECTIONED)
        if len(parts) >= 2 and not _stacked(parts):
            headings = [box for box in pool
                        if box.label == "section_header" and box.score >= confidence
                        and _covered_by(box, parent) >= CONTAINED
                        and all(_covered_by(box, part) < CONTAINED for part in parts)]
            if _ink_share(mask, parts + headings) >= (
                    SPLIT_INK * _ink_share(mask, [parent])):
                split.extend(parts + headings)
                continue
        split.append(parent)
    return split


PAGE_LEVEL = frozenset({"form"})
"""Detector classes that describe the sheet of paper rather than a region on it.

`heron` reports `form` at a very low score over most of a document, and on
`sample_css_0004` over **the whole of it** — `(0.001, 0.000, 0.998, 1.000)`. It
is a true statement and a useless one: every region on the page is inside it, so
`prefer_container` offered the chance would collapse the document to one Zone.

Not a substitute for `CONTAINER_HEIGHT`, which catches the same shape wearing a
different label — `picture` at 0.06, also spanning the full page. Each is worth
one finding on top of the other; both are kept.
"""

CONTAINER_HEIGHT = 0.25
"""How tall a sub-threshold container may be before it is not a Zone, as a
fraction of page height.

**The guard that keeps `invoice_0001` at zero**, which is the one condition spec
0006 makes mandatory. Without it `prefer_container` adopts a `table` at 0.09
spanning **0.444** of the page — both printed tables read as one region, undoing
what `split_containers` exists to do — and a `picture` at 0.06 spanning **1.000**.

Measured over every candidate the rule considers on all five fixtures:

    adopt      0.039  0.048  0.092  0.124        <- correct, every one
    refuse     0.444  1.000                      <- both wrong

0.25 sits between them with **2.0x margin below and 1.8x above**, and it is a
plateau rather than a point: every value from 0.15 to 0.35 gives an identical
answer on all five fixtures. That is the widest margin any constant in this
project rests on, and it is stated here rather than smoothed over.

**It bounds the candidate, not the Zone.** `sample_table_0003`'s table is 0.83 of
its page and is one Zone; nothing here forbids that. The bound says only that a
region the detector was *unsure* about, spanning a quarter of the page, is not
evidence enough to overrule boxes it was sure about.
"""


def _stacked(parts: list[Detection]) -> bool:
    """Whether these boxes sit one above another rather than side by side.

    **The signal that decides which way to regroup, and the only one that
    worked.** Over every case in the corpus, boxes inside a container that are
    stacked belong to one region printed as lines — a list, a quote over its
    attribution, a footer block — while boxes that sit side by side are a *Band*
    the detector drew one rectangle around. Class agreement separates none of
    them: two of the five correct merges hold mixed classes.

    Read as "no two of them are vertical neighbours", so a single box is stacked
    trivially and the caller's two-box minimum is what makes that moot.
    """
    return not any(
        min(first.bottom, second.bottom) > max(first.top, second.top)
        and min(first.right, second.right) <= max(first.left, second.left)
        for first in parts for second in parts if first is not second
    )


def _spans_two_things(box: Detection, mask: ImageArray,
                      leading: float | None) -> bool:
    """Whether this box holds two masses parted by far more white than its own
    leading — `geometry_score`'s `doubles` test, asked before the fact.

    That field is how the pre-registered gate detects over-merge after a run.
    Asking the same question of a candidate *before* adopting it is the cheapest
    way to not cause one, and it reuses the factor rather than choosing another.
    """
    from ..geometry_score import DOUBLE_GAP_FACTOR, _gaps_down, _pixel_rect

    height, width = mask.shape[:2]
    left, top, right, bottom = _pixel_rect(
        BBox(box.left, box.top, box.right, box.bottom), width, height)
    gaps = _gaps_down(mask[top:bottom, left:right])
    if not gaps:
        return False
    own = statistics.median(gaps) if len(gaps) >= 2 else leading
    return own is not None and max(gaps) > DOUBLE_GAP_FACTOR * own


def prefer_container(kept: list[Detection], pool: list[Detection],
                     mask: ImageArray, confidence: float) -> list[Detection]:
    """Adopt a sub-threshold container over the stack of boxes it holds.

    **The mirror of `split_containers`, and the other half of the same fact.**
    That function re-opens a container the threshold kept; this one restores a
    container the threshold *dropped*. Both read detections below the confidence
    floor on purpose — inference runs once per page and confidence is a filter
    over its result, so this costs arithmetic and no second forward pass.

    The five over-splits left in the corpus all have their container already in
    the pool, at 0.05 to 0.27 against a 0.40 threshold and IoU 0.55 to 0.97
    against the reference. `outermost` never saw them: it runs on the boxes that
    survived the threshold, so a container the detector was unsure about is gone
    before the question of nesting is asked.

    Every guard below is load-bearing — dropping either the class rule or the
    `doubles` test costs a finding, and dropping `CONTAINER_HEIGHT` costs
    `invoice_0001` its zero-mismatch Conversion.

    **Runs after `attach_headings`**, which is not cosmetic: before it, a
    candidate spanning a heading and its body re-does that merge with a
    detector-drawn box instead of the union, and three of this rule's adoptions
    were doing exactly that.

    **A container never takes in a picture** — spec 0007's queue, Q5,
    2026-09-29. A container here is a region of text whose parts the threshold
    split, and a picture is a region of its own: gathered into a text Zone it
    is read as text, or not at all. On the re-shot `receipt_0010` a 0.09
    `picture` took the farewell line, the barcode and the three lines under it
    as one Zone, which was read as prose — so the barcode, drawn from its pixels
    since A3, was drawn no longer. Refusing the *container's* label is not
    enough, and was measured not to be: a 0.15 `key_value_region` over the same
    stack is adopted instead and snaps to the identical box. Over all fifteen
    pages that stack is the only adoption with a picture among its parts; the
    other six gather key-value, footnote and page-footer boxes.
    """
    from ..geometry_score import _gaps_down, _pixel_rect

    height, width = mask.shape[:2]
    pooled = [
        gap for box in kept
        for gap in _gaps_down(mask[
            _pixel_rect(BBox(box.left, box.top, box.right, box.bottom),
                        width, height)[1]:
            _pixel_rect(BBox(box.left, box.top, box.right, box.bottom),
                        width, height)[3],
            _pixel_rect(BBox(box.left, box.top, box.right, box.bottom),
                        width, height)[0]:
            _pixel_rect(BBox(box.left, box.top, box.right, box.bottom),
                        width, height)[2]])
    ]
    leading = statistics.median(pooled) if pooled else None

    claimed: set[int] = set()
    adopted: list[Detection] = []
    candidates = [d for d in pool
                  if d.score < confidence and d.label not in PAGE_LEVEL
                  and d.bottom - d.top <= CONTAINER_HEIGHT]
    # Largest first, so a container that holds another container's boxes claims
    # them before the smaller one can, and `claimed` settles the overlap.
    for candidate in sorted(candidates, key=lambda d: -_area(d)):
        inside = [index for index, box in enumerate(kept)
                  if index not in claimed
                  and _covered_by(box, candidate) >= CONTAINED]
        if len(inside) < 2:
            continue
        parts = [kept[index] for index in inside]
        if not _stacked(parts):
            continue
        if any(part.label == "picture" for part in parts):
            continue
        # The parts must account for the candidate's ink, and the candidate must
        # bring none of its own — the second test is what stops it reaching past
        # them into a neighbour.
        if _ink_share(mask, [candidate]) > 1.02 * _ink_share(mask, parts):
            continue
        if _ink_share(mask, parts) < SPLIT_INK * _ink_share(mask, [candidate]):
            continue
        if _spans_two_things(candidate, mask, leading):
            continue
        claimed.update(inside)
        adopted.append(candidate)

    return adopted + [box for index, box in enumerate(kept)
                      if index not in claimed]


def attach_trailing_rows(found: list[Detection]) -> list[Detection]:
    """Fold a table's summary row back into the table.

    The mirror of `attach_headings` and deliberately not the same function: a
    heading is recognised by its *class*, and this by its *proportions*. Merging
    them into one rule would hide that one of them is a fact about the
    vocabulary and the other a fact about the page.

    Guarded four ways, all of which must hold: the region above is a table, the
    strip below is neither a table (so a table stacked under a table stays its
    own region) nor a heading, and the strip is both close to it and a small
    fraction of its height.

    **The heading guard was added in spec 0007 Phase A0, 2026-09-22, and it is
    the fix for a content loss the T1 ratchet caught.** A heading *names the
    region beneath it rather than being one* — that is `attach_headings`' whole
    premise and this module's own vocabulary — so it can never be the last row
    of the region above, however close it sits and however short it is. Without
    the guard this rule ran first and ate the heading, and `attach_headings`
    then had nothing left to attach to the paragraph below.

    Measured over all fifteen documents: **2 absorptions were headings and 4
    were not.** The two were `darkdeck_0009`'s `What Q4 commits to` and
    `report_0011`'s table caption, both `section_header`; the four are the case
    this rule exists for and are untouched, `invoice_0001`'s `key_value_region`
    — the `Total: $385.00` strip — among them.

    **A row across the table's bottom edge is a trailing row too — N3,
    2026-09-30.** On the whole picture heron ends `statement_0006`'s
    transactions table at 0.9300, through the middle of its own totals row,
    and reports `Totals for the period` at 0.9255-0.9352. It started 0.0045
    above the edge, so it was never *under* the table; and it was not wholly
    inside, so `without_enclosed` kept it. It became a Zone of its own in the
    table's Band: the line printed twice, the snap was refused for the whole
    page, and the table was drawn in two thirds of the width beside it. So a
    strip now qualifies when it starts below the table's top and ends below
    its bottom, under every other guard here. Over all fifteen documents it
    changes exactly that page: 6 Zones to 5, no other box moved, since the
    detector's own snap had already put every box on its ink.
    """
    absorbed: set[int] = set()
    merged: list[Detection] = []
    for index, box in enumerate(found):
        if index in absorbed:
            continue
        trailing = _trailing_row(found, index, absorbed)
        if trailing is None:
            merged.append(box)
        else:
            absorbed.add(trailing)
            merged.append(_union(box, found[trailing]))
    return merged


def _trailing_row(found: list[Detection], parent: int,
                  absorbed: set[int]) -> int | None:
    table = found[parent]
    if table.label not in SPLITTABLE:
        return None

    height = table.bottom - table.top
    below = [
        index for index, box in enumerate(found)
        if index != parent and index not in absorbed
        and box.label not in SPLITTABLE
        and box.label not in HEADINGS
        # Under the table, or across its bottom edge — see `attach_trailing_rows`.
        and box.top > table.top and box.bottom > table.bottom
        and box.top - table.bottom <= TRAILING_GAP
        and (box.bottom - box.top) <= TRAILING_HEIGHT * height
        and min(box.right, table.right) > max(box.left, table.left)
    ]
    if not below:
        return None
    return min(below, key=lambda index: found[index].top)


def _parts_of(parent: Detection, pool: list[Detection],
              labels: frozenset[str] = SPLITTABLE) -> list[Detection]:
    """Same-class boxes inside `parent` that do not overlap each other.

    Greedy by confidence, so of two proposals for the same part the surer one
    wins and the other is excluded by the overlap test rather than by a rule
    about which came first. Only a parent whose class is in `labels`.
    """
    if parent.label not in labels:
        return []

    inside = [box for box in pool
              if box is not parent and box.label == parent.label
              and _covered_by(box, parent) >= CONTAINED
              and _area(box) < 0.9 * _area(parent)]

    chosen: list[Detection] = []
    for box in sorted(inside, key=lambda b: -b.score):
        if all(_covered_by(box, other) < 0.30 and _covered_by(other, box) < 0.30
               for other in chosen):
            chosen.append(box)
    return sorted(chosen, key=lambda b: b.top)


def _ink_share(mask: ImageArray, boxes: list[Detection]) -> float:
    """Share of the page's ink these boxes cover between them."""
    height, width = mask.shape[:2]
    ink = mask > 0
    total = int(ink.sum())
    if total == 0:
        return 0.0

    claimed = np.zeros((height, width), dtype=bool)
    for box in boxes:
        left = max(0, min(width, int(round(box.left * width))))
        top = max(0, min(height, int(round(box.top * height))))
        right = max(left, min(width, int(round(box.right * width))))
        bottom = max(top, min(height, int(round(box.bottom * height))))
        claimed[top:bottom, left:right] = True
    return float(np.logical_and(ink, claimed).sum()) / total


def _area(box: Detection) -> float:
    return max(0.0, box.right - box.left) * max(0.0, box.bottom - box.top)


def _within(inner: Detection, outer: Detection,
            slack_x: float = 0.0, slack_y: float = 0.0) -> bool:
    """Whether every edge of `inner` lies on or inside `outer`, to the slack."""
    return (inner.left >= outer.left - slack_x and inner.top >= outer.top - slack_y
            and inner.right <= outer.right + slack_x
            and inner.bottom <= outer.bottom + slack_y)


def _covered_by(inner: Detection, outer: Detection) -> float:
    """Share of `inner` that `outer` covers. Asymmetric, which is the point."""
    wide = min(inner.right, outer.right) - max(inner.left, outer.left)
    tall = min(inner.bottom, outer.bottom) - max(inner.top, outer.top)
    if wide <= 0 or tall <= 0 or _area(inner) == 0:
        return 0.0
    return (wide * tall) / _area(inner)


def _session(path: Path) -> Any:
    """An ONNX Runtime session pinned to the CPU provider.

    CPU on purpose. Two vision models resident at once does not fit in 8GB, and
    the layout pass is the most expensive call in a run — putting it somewhere
    that does not contend for the GPU gives the budget back rather than
    splitting it.

    Imported inside the call so the package stays importable without the
    `detector` extra: a missing dependency should name itself at the moment
    something asks for a detector, not at `import doc_to_html`.
    """
    try:
        import onnxruntime as ort
    except ImportError as error:  # pragma: no cover - exercised by the extra
        raise DetectorUnavailable(
            "onnxruntime is not installed; pip install 'doc-to-html[detector]'"
        ) from error

    if not path.is_file():
        raise DetectorUnavailable(
            f"missing {path}\nrun: python tools/fetch_layout_models.py"
        )
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _normalise(boxes: np.ndarray, width: int, height: int) -> np.ndarray:
    """Pixel xyxy to normalised xyxy, clipped to the page.

    Clipped rather than trusted: both detectors can put an edge slightly outside
    the frame, and a box with `right > 1.0` silently widens every ink
    measurement that indexes an array with it.
    """
    scaled = boxes.astype(np.float64) / np.array([width, height, width, height])
    clipped: np.ndarray = np.clip(scaled, 0.0, 1.0)
    return clipped


class Heron:
    """Docling's layout model. RT-DETRv2, NMS-free, **Apache-2.0**.

    Seventeen classes, two of which are why it is here: `form` and
    `key_value_region`. `invoice_0002`'s boxed label/value panels are exactly
    that, and they are the structure that defeats both the VLM and the XY-cut.
    With `outermost` applied at 0.40 it labels each panel's block
    `key_value_region` and separates the two panels correctly, where
    `doclayout_yolo` runs one box across both.

    Two things about the export, read from the files beside it rather than
    hardcoded, so a re-export that changes them fails loudly:

    - the input is **`uint8`**, not float. `preprocessor_config.json` sets
      `do_rescale` and `do_normalize` false; the graph carries them.
    - `orig_target_sizes` is **(width, height)**, not the (height, width) the
      HuggingFace processor uses. Measured: with (height, width) on the 862x563
      `invoice_0001`, boxes come back with `bottom` up to 762 on a 563px page.

    **Channel order was measured and does not matter.** Feeding BGR instead of
    RGB moves this by one or two low-confidence detections and `doclayout_yolo`
    not at all. These pages are black ink on white paper, so the three channels
    carry nearly the same image. RGB is used because it is what both were
    trained on; the measurement is recorded so nobody hunts a bug that is not
    there.
    """

    name = "heron"
    license = "Apache-2.0"
    confidence = 0.40
    """Measured: the lowest confidence at which `invoice_0001` comes back as
    exactly its 6 regions with Bands matching the expected IR. Below it the page
    collapses — 5 regions at 0.30, 3 at 0.15, 1 at 0.10 — and above it nothing
    moves until 0.80."""

    folder = MODELS / "heron"
    weights = folder / "model.onnx"

    def __init__(self) -> None:
        self._model: Any | None = None
        self._names: dict[int, str] = {}
        self._size: tuple[int, int] = (640, 640)

    def _load(self) -> Any:
        if self._model is None:
            self._model = _session(self.weights)
            config = json.loads((self.folder / "config.json").read_text())
            self._names = {int(k): v for k, v in config["id2label"].items()}
            size = json.loads(
                (self.folder / "preprocessor_config.json").read_text()
            )["size"]
            self._size = (int(size["width"]), int(size["height"]))
        return self._model

    def detect(self, image: ImageArray) -> list[Detection]:
        cv2 = _cv2()
        model = self._load()
        height, width = image.shape[:2]
        # Resized, not letterboxed: RT-DETR was trained on a squashed square and
        # `orig_target_sizes` is how it undoes the aspect change itself.
        fitted = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), self._size,
                            interpolation=cv2.INTER_LINEAR)
        labels, boxes, scores = model.run(None, {
            "images": fitted.transpose(2, 0, 1)[None].astype(np.uint8),
            "orig_target_sizes": np.array([[width, height]], dtype=np.int64),
        })

        keep = scores[0] >= FLOOR
        normalised = _normalise(boxes[0][keep], width, height)
        return [
            Detection(left=float(box[0]), top=float(box[1]),
                      right=float(box[2]), bottom=float(box[3]),
                      label=self._names.get(int(cls), str(int(cls))),
                      score=float(conf))
            for box, conf, cls in zip(normalised, scores[0][keep], labels[0][keep])
        ]


class DocLayoutYolo:
    """DocLayout-YOLO, DocStructBench weights. YOLOv10, NMS-free, **AGPL-3.0**.

    Ten classes, every one a shape a *paper* has: title, plain text, figure,
    table, their captions, formulas. No concept of a form, which is what
    `invoice_0002` is made of — and it shows: with `outermost` it runs a single
    `table` box across both the Company Details and Customer Details panels,
    where `heron` separates them.

    It scores slightly better than `heron` on aggregate zone counts and slightly
    worse on the two fixtures this project actually cares about. Kept because a
    second implementation is what makes the first one's numbers checkable.

    Its confidences are worth knowing before choosing a threshold: it reports
    `invoice_0001`'s line-item table — both tables as one correct region — at
    **0.189**, while calling the four header blocks 0.88 to 0.96. A sweep
    starting at 0.2 records it as blind to tables when it is only unsure.
    """

    name = "doclayout_yolo"
    license = "AGPL-3.0"
    confidence = 0.15
    weights = MODELS / "doclayout_yolo" / "doclayout_yolo_docstructbench_imgsz1024.onnx"
    imgsz = 1024
    pad = 114

    def __init__(self) -> None:
        self._model: Any | None = None
        self._names: dict[int, str] = {}

    def _load(self) -> Any:
        if self._model is None:
            self._model = _session(self.weights)
            # The class names travel in the ONNX metadata, so they cannot drift
            # from the weights the way a list copied into this file would.
            raw = self._model.get_modelmeta().custom_metadata_map.get("names", "{}")
            parsed = ast.literal_eval(raw)
            self._names = {int(k): str(v) for k, v in dict(parsed).items()}
        return self._model

    def detect(self, image: ImageArray) -> list[Detection]:
        cv2 = _cv2()
        model = self._load()
        height, width = image.shape[:2]
        scale = min(self.imgsz / height, self.imgsz / width)
        fitted = cv2.resize(
            cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
            (int(round(width * scale)), int(round(height * scale))),
            interpolation=cv2.INTER_LINEAR,
        )
        # Padded right and bottom only, so mapping back to page coordinates is a
        # single divide by the scale with no offset to get wrong.
        canvas = np.full((self.imgsz, self.imgsz, 3), self.pad, dtype=np.uint8)
        canvas[: fitted.shape[0], : fitted.shape[1]] = fitted

        batch = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        found = model.run(None, {"images": batch})[0][0]  # (300, 6): xyxy conf cls

        keep = found[:, 4] >= FLOOR
        boxes = _normalise(found[keep, :4] / scale, width, height)
        return [
            Detection(left=float(box[0]), top=float(box[1]),
                      right=float(box[2]), bottom=float(box[3]),
                      label=self._names.get(int(cls), str(int(cls))),
                      score=float(conf))
            for box, conf, cls in zip(boxes, found[keep, 4], found[keep, 5])
        ]


DETECTORS: dict[str, Detector] = {
    Heron.name: Heron(),
    DocLayoutYolo.name: DocLayoutYolo(),
}


HEADERS = frozenset({"page_header"})
FOOTERS = frozenset({"page_footer", "footnote", "abandon"})
"""Detector class names that map to a Role other than `BODY`.

Deliberately short. `Role` is a CSS class in `render.py` and nothing else — the
Probes navigate by `RowRole`, one level down — so guessing here can cost a class
name and cannot cost a reconciliation. `abandon` is DocStructBench's name for
running heads and page numbers, which is what `FOOTER` is for.
"""


class LayoutEngine:
    """A layout pass that is a detector rather than a model.

    Satisfies `engines.base.LayoutEngine`, and ignores `hint`, which is prose
    for a language model. It returned 6 regions on the page that holds 6 and 12
    to 14 on the page that holds 10, where the deleted vision layout pass once
    returned 72 — which is what a region ceiling used to be stated to rescue.

    **Bands are always derived here.** A detector reports no Bands of its own,
    so there is nothing to believe instead. `bands_from_boxes` matches all five
    fixtures' expected IR.

    **Snapping is always applied**, for the same reason `DTH_SNAP_ZONES` is on:
    raw detector edges clip glyphs, which is 6 split masses of ink on
    `invoice_0001` and 44 across the corpus. Snapping takes every one of them to
    zero without moving coverage.
    """

    def __init__(self, detector: Detector, confidence: float | None = None,
                 *, heading_rule: str = "absolute",
                 prefer_container: bool = False) -> None:
        self.detector = detector
        self.confidence = detector.confidence if confidence is None else confidence
        self.heading_rule = heading_rule
        self.prefer_container = prefer_container
        self.name = f"detector:{detector.name}"
        self.model = detector.name

    def detect_zones(self, image: ImageArray,
                     hint: str | None = None) -> list[Zone]:
        """Detections to Zones, in steps that each undo one known error.

        The order is not arbitrary. `outermost` first, because everything after
        it assumes one box per region — and `without_overreaching_pictures`
        just before it, because a picture drawn round a surer picture and its
        neighbour is exactly what `outermost` would keep. Then `split_containers`, which needs the
        *unfiltered* pool to find the parts it restores, and its two section
        rules, `split_side_by_side` and `cut_at_sections` (spec 0009). Then
        `attach_headings`, after the split because it must see the split's
        output — `split_side_by_side` leaves headings for it to fold in; on
        `sample_table_0003` the caption belongs to a table that only exists once
        the split has run.

        `without_enclosed` last, because the unions before it can break
        `outermost`'s one-box-per-region: a grown box swallows a neighbour and
        leaves it standing, and nothing after this point would notice.
        """
        pool = self.detector.detect(image)
        ink = content_ink(image)
        confident = without_overreaching_pictures(
            [d for d in pool if d.score >= self.confidence], ink)
        found = open_unsure_containers(outermost(confident), confident, ink)
        found = split_containers(found, pool, ink)
        found = split_side_by_side(found, pool, ink, self.confidence)
        if any(box.label in SECTIONED for box in found):
            found = cut_at_sections(found, pool, self.confidence,
                                    _drawn(image))
        found = attach_trailing_rows(found)
        found = attach_headings(found, relative=self.heading_rule == "relative")
        if self.prefer_container:
            found = prefer_container(found, pool, ink, self.confidence)
        found = without_enclosed(found, image.shape[:2])
        found.sort(key=lambda d: (round(d.top, 3), d.left))

        boxes = snap_to_ink(image, [BBox(d.left, d.top, d.right, d.bottom)
                                    for d in found])
        placed = bands_from_boxes(boxes)
        return [
            Zone(
                kind=Kind.PROSE,  # a placeholder; `_classify` reads the crop
                role=_role(detection.label, band),
                band=band,
                column=column,
                bbox=box,
            )
            for detection, box, (band, column) in zip(found, boxes, placed)
        ]


def _drawn(image: ImageArray) -> tuple[BBox, ...]:
    """Every box the page draws — `style.rectangles`, on the page's ground."""
    from ..style import measure, rectangles

    return rectangles(image, ground=measure(image).page_bg)


def _role(label: str, band: int) -> Role:
    """A Zone's Role, from its class where that is decisive and its Band where
    it is not.

    **The top Band of a page is its header.** That is what both references say —
    `invoice_0001` marks its logo and its invoice numbers `header`, and nothing
    below them; `invoice_0002` marks its whole first Band the same way. Run 67
    reported four `role expected header, got body` mismatches with everything
    defaulting to `BODY`, and this rule removes all of `invoice_0001`'s.

    It does not remove all of `invoice_0002`'s: that fixture also calls its
    second Band `header` and its last `footer`, and neither is a geometric fact
    a Band index can recover. Role is semantic where the class name runs out.
    Little rests on it — `render.py` uses it as a CSS class and the Probes
    navigate by `RowRole`, one level down — so the rule is kept to what the
    corpus actually supports.
    """
    if label in HEADERS or band == 0:
        return Role.HEADER
    if label in FOOTERS:
        return Role.FOOTER
    return Role.BODY


def from_name(name: str, confidence: float | None = None, *,
              heading_rule: str = "absolute",
              prefer_container: bool = False) -> LayoutEngine:
    """The named detector, or a message naming the ones that exist."""
    if name not in DETECTORS:
        raise DetectorUnavailable(
            f"unknown layout detector {name!r}; "
            f"known: {', '.join(sorted(DETECTORS))}"
        )
    return LayoutEngine(DETECTORS[name], confidence, heading_rule=heading_rule,
                        prefer_container=prefer_container)
