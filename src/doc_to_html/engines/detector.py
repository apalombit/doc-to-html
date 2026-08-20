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
from dataclasses import dataclass
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
    printed inside it are one region" that `LAYOUT_PROMPT` has spent three runs
    asking a model to perform and being ignored about. Applied, both detectors
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


HEADINGS = frozenset({"section_header", "title", "caption",
                      "table_caption", "figure_caption"})
"""Detector classes that name the region beneath them rather than being one.

Both vocabularies are covered: `section_header` / `caption` are heron's,
`title` / `table_caption` / `figure_caption` DocStructBench's.
"""

HEADING_GAP = 0.05
"""How far below a heading its content may start, as a fraction of page height.

**Measured on the four fixtures that have headings at all.** Every gap that
should close and every gap that should not, sorted:

    merge      0.011  0.024  0.025  0.028  0.029  0.030  0.032  0.038  0.040  0.044
    leave      0.056  0.064  0.081  0.147

0.05 sits in the gap, with 1.13x margin below and 1.13x above — thin, and stated
rather than hidden. The widest true attachment is a panel caption over an
indented block; the narrowest false one is a heading whose own panel is empty, so
the nearest box below it belongs to the *next* section.

A fraction of page **height** rather than of the short edge or of pixels, because
that is what separated the two groups: in raw pixels they overlap (a 32px gap
that should close, a 30px gap that should not), since these fixtures scale their
type with the page.

**This docstring and `docs/specs/0005` disagree, and the spec is right.** The two
gaps listed above under `leave` as 0.056 and 0.064 are `sample_css_0004`'s two
heading-to-body gaps, measured there as 0.058 and 0.065 — and the reference has
each heading and its body as **one** Zone, so they belong under `merge`. They
were filed here as "leave" before any Conversion had run, from geometry alone.
That mistake is the whole of spec 0005's Change 2: with them moved, the boundary
sits between 0.065 and 0.081 rather than around 0.05, and `sample_css_0004`'s two
headings fail to merge because this constant is too tight.

**Do not retune this without settling the disagreement first**, and settle it by
re-deriving the gaps rather than by trusting either list. Whichever way it lands,
one of the two documents is currently wrong and a reader who consults only the
other will draw the opposite conclusion.
"""


def attach_headings(found: list[Detection]) -> list[Detection]:
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
    """
    order = sorted(range(len(found)), key=lambda i: (found[i].top, found[i].left))
    claimed: dict[int, int] = {}
    for index in order:
        if found[index].label not in HEADINGS:
            continue
        target = _region_below(found, index)
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


def _region_below(found: list[Detection], heading: int) -> int | None:
    """The nearest non-heading box under this one, near enough to belong to it.

    "Under" is any horizontal overlap at all rather than a share of the width:
    a panel caption is short and left-aligned while the block it names is
    indented, and requiring 30% overlap missed `Company Details` over its own
    panel by three percentage points.
    """
    above = found[heading]
    below = [
        index for index, box in enumerate(found)
        if index != heading
        and box.label not in HEADINGS
        and box.top >= above.bottom - 0.01
        and box.top - above.bottom <= HEADING_GAP
        and min(box.right, above.right) > max(box.left, above.left)
    ]
    if not below:
        return None
    return min(below, key=lambda index: (found[index].top, found[index].left))


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


def attach_trailing_rows(found: list[Detection]) -> list[Detection]:
    """Fold a table's summary row back into the table.

    The mirror of `attach_headings` and deliberately not the same function: a
    heading is recognised by its *class*, and this by its *proportions*. Merging
    them into one rule would hide that one of them is a fact about the
    vocabulary and the other a fact about the page.

    Guarded three ways, all of which must hold: the region above is a table, the
    strip below is not (so a table stacked under a table stays its own region),
    and the strip is both close to it and a small fraction of its height.
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
        and 0 <= box.top - table.bottom <= TRAILING_GAP
        and (box.bottom - box.top) <= TRAILING_HEIGHT * height
        and min(box.right, table.right) > max(box.left, table.left)
    ]
    if not below:
        return None
    return min(below, key=lambda index: found[index].top)


def _parts_of(parent: Detection, pool: list[Detection]) -> list[Detection]:
    """Same-class boxes inside `parent` that do not overlap each other.

    Greedy by confidence, so of two proposals for the same part the surer one
    wins and the other is excluded by the overlap test rather than by a rule
    about which came first.
    """
    if parent.label not in SPLITTABLE:
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

    Satisfies the same `detect_zones` seam `OllamaEngine` does, and ignores both
    of its optional arguments — which the Protocol already permits. `hint` is
    prose for a language model. `region_ceiling` is a rescue for a model that
    invents regions, and this does not: it returned 6 regions on the page that
    holds 6 and 12 to 14 on the page that holds 10, where the VLM once returned
    72.

    **Bands are always derived here.** `DTH_DERIVE_BANDS` exists because the VLM
    reports Bands of its own that may be believed instead; a detector reports
    none, so there is nothing to choose between. `bands_from_boxes` matches all
    five fixtures' expected IR.

    **Snapping is always applied**, for the same reason `DTH_SNAP_ZONES` is on:
    raw detector edges clip glyphs, which is 6 split masses of ink on
    `invoice_0001` and 44 across the corpus. Snapping takes every one of them to
    zero without moving coverage.
    """

    def __init__(self, detector: Detector, confidence: float | None = None) -> None:
        self.detector = detector
        self.confidence = detector.confidence if confidence is None else confidence
        self.name = f"detector:{detector.name}"
        self.model = detector.name

    def detect_zones(self, image: ImageArray, hint: str | None = None,
                     region_ceiling: int | None = None) -> list[Zone]:
        """Detections to Zones, in four steps that each undo one known error.

        The order is not arbitrary. `outermost` first, because everything after
        it assumes one box per region. Then `split_containers`, which needs the
        *unfiltered* pool to find the parts it restores. Then `attach_headings`,
        last of the three because it must see the split's output — on
        `sample_table_0003` the caption belongs to a table that only exists once
        the split has run.
        """
        pool = self.detector.detect(image)
        found = outermost([d for d in pool if d.score >= self.confidence])
        found = split_containers(found, pool, content_ink(image))
        found = attach_trailing_rows(found)
        found = attach_headings(found)
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


def from_name(name: str, confidence: float | None = None) -> LayoutEngine:
    """The named detector, or a message naming the ones that exist."""
    if name not in DETECTORS:
        raise DetectorUnavailable(
            f"unknown layout detector {name!r}; "
            f"known: {', '.join(sorted(DETECTORS))}"
        )
    return LayoutEngine(DETECTORS[name], confidence)
