# Check the box against the ink

**Status: closed — built, and the premise below is refuted.** Issue #20 is
closed, as are its children #21-#27. Read this header before the spec — the body
is left as written, because what it argued and how it turned out are both worth
having, but three of its load-bearing claims are false and one of its conclusions
inverts once the measurement is done properly.

**Treat runs before 50 as superseded and do not cite them as evidence.** Every
run this spec argues from — 26-28, 32, 42 — is below that line.

The problem it ended on — "geometry is broken on four of the five fixtures", a
bigger problem than anything this spec set out to address — is measured in
`0005-nothing-is-missing.md`, and the answer is that geometry is no longer where
the errors are: `covered` 1.00 and `splits` 0 on all five.

**1. The crops were never the problem.** Run 42
(`tools/classify_truth_probe.py`) handed the classifier the exact Zone
rectangles read off `example/invoice.html`. Zones 3 and 4 came back `pairs` and
`pairs` — identical to what the model's own boxes produce. Perfect geometry does
not move either mismatch, so nothing in this spec could have fixed them. Six
calls, and they were affordable before any of this was built rather than after.

**2. The reference this spec measures against was 0.66 IoU from the truth.**
Every number below — the 0.56, the 0.475, the resolution sweep — is scored
against rectangles typed by hand. `tools/fixture_geometry.py` now derives
`invoice_0001`'s from the source HTML. Against those, the *snapped* geometry
scores **0.909 IoU, 0.99 covered, 0 splits**. The decision rule in
"Implementation Decisions" reads 0.62 against the typed boxes and says "grouping
is the problem, build Family 2"; against the truth it reads 0.909 and says "keep
the VLM pass". **This spec was one bad ruler away from sending the project into
rebuilding geometry it did not need to rebuild.**

**3. Zone 4's crop is not crowded.** The Problem Statement says it overshoots
"into its neighbours' ink above and below". Measured: the box is rows 231-355,
its ink is rows 284-298 and 319-330 — its own two lines — and rows 231-283 and
331-354 are blank. The nearest neighbour ink stops 8px above and resumes 13px
below. The overshoot is into margin.

**4. Gate 1 passed and shipping it cost the document.** `covered` 0.82 -> 0.99,
`splits` 46 -> 0, `zones` unchanged, nothing worse on any of five fixtures. Wired
in, the invoice went from 3 mismatches to 6: the line-item table stopped
extracting and took the column-sum Probe with it. **No field in Gate 1 can see
extraction.** The snap is reverted and kept. Any gate that re-wires it must
include *no Zone that previously converted stops converting* — which is the
lesson here, and it is about how gates are written, not about snapping.

**What the spec got right.** The ruler was the right thing to build; it is what
made all four findings above measurable. `covered` and `splits` do separate
"sloppy edges" from "wrong page" — Gate 3's XY-cut arm scored `covered` 1.00
while describing the page wrongly, and only the Band comparison caught it.
Stage 0's pre-registered calibration fired exactly as designed and demoted `iou`
at 0.701, which is the mechanism that led to deriving real ground truth.

**What it also found, outside its own question.** Geometry is broken on four of
the five fixtures: `invoice_0002` returns no answer at all, and three of the
others fail Band validation. That is in `debug/runs/36-fixture-sweep/` and it is
a bigger problem than anything this spec set out to address.

---

**Original status:** open, not started — issue #20. Continues
`0003-classify-from-the-crop.md` (issue #12) by questioning its input rather than
its prompt: 0003 argues about which
model names a Zone's Kind, and this spec asks whether the crop that Kind is
judged from is the Zone at all.

**Read this before touching `LAYOUT_PROMPT` again.** Four prompt attempts are on
record as failures in 0002, and runs 26-28 add two more mechanisms that no
wording can reach.

## Problem Statement

`example/invoice.png` converts with **3 mismatches**, every one of them a Zone
carrying the wrong Kind, and one of those then failing extraction. 0003 treats
that as a classification problem. The geometry underneath it has never been
checked against the page.

**The geometry pass is one model call on a 384x251 thumbnail, and nothing
anywhere compares its answer to ink.** `_validate_box` checks a box is on the
page and encloses area; `_validate_bands` checks Bands descend and columns run
left to right. Both are checks on *legality*. A box that slices a logo in half is
legal. A box that swallows its neighbours' text is legal. A box that stops two
percent of the page short of the ink it was drawn around is legal.

Measured, run 32 (`debug/runs/32-guards-shipped-path/geometry.txt`, the shipped
path, `qwen3-vl:4b`, long edge 384) — mean best IoU **0.56** over six boxes:

| Zone | model box | expected box | what the crop is |
|---|---|---|---|
| 0 `figure` | 0.10-0.14 vertical | 0.06-0.17 | **336x34px** of a ~62px logo. IoU 0.32, reported "inside want 0 — a SPLIT" |
| 1 `pairs` | 0.75-0.94 x 0.10-0.23 | 0.70-0.96 x 0.07-0.20 | IoU 0.48, "no reference accounts for it"; want 1 only 56% covered |
| 2 `prose` | 0.05-0.38 x 0.24-0.39 | 0.04-0.35 x 0.27-0.41 | IoU 0.63 |
| 3 `prose` | right edge 0.94 | right edge 0.96 | 216x96px, a fifth of the block outside the box |
| 4 `table` | 0.41-0.63 | 0.48-0.60 | overshoots both ways into **blank margin** — see correction 3 in the header; the "neighbour ink" claim is false |
| 5 `table` | 0.05-0.92 | 0.03-0.95 | IoU 0.83, the only good one |

Three things say this is not a wording problem:

- **Every coordinate lands on a coarse grid** — 0.05, 0.10, 0.14, 0.23, 0.24,
  0.38, 0.39, 0.41, 0.63, 0.64, 0.75, 0.92, 0.94 — while `LAYOUT_PROMPT` asks in
  as many words for edges "measured against the ink rather than against a grid,
  using however many decimals that takes". The model is placing boxes on a mental
  grid, not on the page.
- **Resolution does not move it** (run 28, 2 repeats each): 384 -> 0.546,
  512 -> 0.529, 862 -> 0.529, all six Zones; 768 -> 0.246 with 18 Zones and one
  repeat failing `_validate_bands`. 2.25x the linear pixels buys nothing.
- **Framing makes it worse** (runs 26, 27): telling the model the image's exact
  pixel dimensions, and telling it that plus a worked normalisation example, were
  monotonically worse than the shipped prompt across two models and eight cells.

And the one attempt at replacing the model got a similar score describing a
different page: morphology (runs 30, 31) reaches IoU **0.475** at its best
six-region kernel by welding every row into two full-height column strips
(`0.02-0.24 x 0.47-0.91` and `0.82-0.98 x 0.47-0.97`). Its line-granularity
kernels find primitives well — 17-23 boxes that are individual lines and
label/value cells — and score ~0.2 because grouping them is the part it cannot
do.

**Consequences the operator sees.** The classification pass (0003) is asked "is
this a table or a pairs block?" about an image that contains the Payment Method
grid *plus* stray ink from the blocks above and below it — the crowding the
classification split exists to remove is baked into the pixels the split hands
over. Zone 3 is judged with a fifth of itself cut off. Zone 0 is a horizontal
band through a logo. The `qwen3-vl:4b`-is-7/7-wrong-on-Zone-4 finding, and the
whole per-step model evaluation in #19, are being measured on inputs that are
themselves 0.56 IoU wrong.

**And nobody knows whether that 0.56 is bad edges or bad grouping**, which is the
single fact that decides what to build next.

## Solution

Two families of change, staged, each with a pre-registered gate, and a decision
rule between them written down *before* the numbers arrive.

**Family 1 — check the box against ink (this spec).** Deterministic, no new
model, no new dependency, and the first three stages need **zero Ollama calls**
because 24 layout answers are already on disk.

```
Stage 0  the ruler        ink-aware score + calibrate it against the fixture
Stage 1  snap-to-ink      shrink/grow each box to the ink it was drawn around
Stage 2  ink guards       measure splits and two-mass boxes; do not enforce yet
Stage 3  XY-cut probe     recursive projection cutting, scored on the same ruler
```

**Family 2 — invert the division of labour (follow-up spec, gated on Stage 1).**
Deterministic primitives from pixels, grouping from the model: number the ink
primitives, ask the model to partition the numbers into Zones with Bands and
columns, compute each Zone's box as the union of its primitives. Boxes become
exact by construction and the model never emits a coordinate.

The gate between them is Stage 1's number, and it is stated in "Implementation
Decisions" so it cannot be re-litigated after the fact.

## User Stories

1. As an operator, I want each Zone's crop to contain the whole block it names and nothing from its neighbours, so that the Kind I get back is a judgement about my content and not about a slice of it.
2. As an operator, I want a logo Zone to contain the whole logo, so that a Graphic placeholder sits where the graphic is.
3. As an operator, I want the right-hand edge of a Zone to reach the right-aligned prices inside it, so that no reading loses its last glyph before an Extractor ever sees it.
4. As an operator, I want a Zone that swallowed its neighbour's ink to be visible as a defect rather than silently converted, so that a wrong Kind traces to a wrong box.
5. As a maintainer, I want one score for geometry that distinguishes "roughly the right regions with sloppy edges" from "confidently the wrong page", so that a bake-off cannot pick the second because it beat the first on a single number.
6. As a maintainer, I want that score to include how much of the page's ink falls inside exactly one box, so that a segmenter which covers the page with two column strips cannot score well.
7. As a maintainer, I want that score to count boxes whose edge cuts through a connected mass of ink, so that the sliced-logo failure is a number rather than something someone notices by opening a PNG.
8. As a maintainer, I want that score to count boxes holding two ink masses separated by more whitespace than the box's own line spacing, so that Zone 4's overshoot is measurable.
9. As a maintainer, I want the same scoring code behind both the probe tool and a run's contact sheet, so that a probe row and a conversion are comparable without anyone reconciling two implementations.
10. As a maintainer, I want the expected fixture boxes scored by the same ruler before anything is measured against them, so that I know how much of the model's 0.56 is the fixture being eyeballed.
11. As a maintainer, I want a snap-to-ink step that trims a box's blank margins and grows it until its edges are past the ink, so that geometry stops depending on a model's coordinate arithmetic.
12. As a maintainer, I want snap-to-ink measured against 24 layout answers already on disk before it is wired into anything, so that the first evidence costs no model time.
13. As a maintainer, I want the snap to be idempotent, so that re-running it can never drift a box.
14. As a maintainer, I want the snap to be unable to create an overlap between two Zones, so that it cannot turn a valid layout into one `_validate_bands` rejects.
15. As a maintainer, I want geometry that fails validation after snapping to fall back to the unsnapped boxes, so that a deterministic improvement can never cost a Conversion.
16. As a maintainer, I want a Separator to be excluded from what the snap grows towards, so that a box does not stretch to a horizontal rule that is explicitly not content.
17. As a maintainer, I want a blank Zone left to the existing empty-crop guard rather than "repaired" by the snap, so that two mechanisms do not both claim the same failure.
18. As a maintainer, I want the snap measured on all five fixtures, not just `invoice_0001`, so that the first geometry change in this project's history is not another finding from one page.
19. As a maintainer, I want that fixture sweep to cost layout calls only, not five full conversions, so that blast radius is answerable in minutes rather than twenty.
20. As a maintainer, I want a recursive XY-cut probe scored on the same ruler, so that "is a deterministic segmenter competitive at all" is answered by a number rather than by the morphology run everyone remembers.
21. As a maintainer, I want the XY-cut probe to emit Bands and columns natively, so that its output is comparable to the IR rather than to a bag of boxes.
22. As a maintainer, I want the split-through-ink and two-mass checks reported before they are enforced, so that a guard tuned on a soft ruler cannot start rejecting good geometry.
23. As a maintainer, I want a written decision rule mapping Stage 1's number to what gets built next, so that the follow-up is chosen by the measurement rather than by whoever reads it first.
24. As an agent picking this up, I want each stage to name the run directory its numbers must land in, so that the next agent can check the claim instead of re-running it.
25. As a reviewer, I want to know which parts of this were measured on one fixture, so that a result from `invoice_0001` is not read as a result about documents.

## Implementation Decisions

### The seams

Four, and three of them are in `tools/`:

1. **One scoring function**, new, living beside the existing probe scorer.
   Signature in domain terms: *(the boxes a method produced, the expected boxes,
   the Rectified Image) -> a score record*. Both `tools/layout_probe.py` and
   `tools/inspect_run.py`'s geometry report call it. The existing `iou` and
   `expected_boxes` helpers stay and are called by it, so run 24-32's numbers
   remain comparable.
2. **One snap function**, new, in the preprocessing module beside `ink_fraction`
   and `uncovered_ink`: *(the Rectified Image, boxes) -> boxes*. Pure, no model,
   no IR, reusing `INK_LEVEL` and the Separator filter already defined there.
3. **One re-scoring tool**, new: walks the recorded `00_layout.json` dumps under
   `debug/runs/`, re-parses each with the existing layout mapper, and prints raw
   versus snapped scores. No Ollama, no Orchestrator.
4. **One call site in the shipped path**, in the Orchestrator's geometry step,
   after the Engine returns Zones — and only if Stage 1's gate passes.

The Engine is deliberately *not* a seam: snapping belongs to every Engine's
answer, not to Ollama's, and the Orchestrator is where routing and policy already
live.

### Stage 0 — the ruler, and calibrating it

The score record carries six fields, reported together and never collapsed to
one number:

| field | definition |
|---|---|
| `zones` | how many boxes the method produced |
| `iou` | mean best IoU per produced box against the expected boxes — the number runs 24-32 already report |
| `covered` | fraction of the page's ink pixels lying inside **exactly one** box — so overlap is penalised as well as omission |
| `splits` | connected ink components crossed by any box edge |
| `doubles` | boxes containing two or more ink masses separated by a whitespace band wider than that box's own median line gap |
| `valid` | whether `_validate_bands` accepts the answer |

`doubles` scales itself off the box's own line spacing rather than a page
constant, so a dense table and an airy address block are judged by their own
leading. `splits` and `covered` use `INK_LEVEL` and the Separator filter
(`MIN_GAP_THICKNESS`, `SEPARATOR_ASPECT`) that `uncovered_ink` already uses, so a
horizontal rule is not ink for either.

**Calibrate the ruler before measuring with it.** Both fixture builders say in
as many words that their bounding boxes are "eyeballed to roughly the right
place" — so some unknown part of the model's 0.56 is the fixture, not the model.
Two things settle it, both deterministic:

- Score the **expected** boxes with the new ruler. Their `covered`, `splits` and
  `doubles` are the floor any method is measured against.
- Snap the expected boxes and compute IoU between eyeballed and snapped. **Pre-registered:
  if that mean IoU is below 0.90, `iou` is demoted to a secondary field for the
  rest of this spec** and the gates below read `covered`, `splits` and `doubles`
  instead. A ruler with 10% slop cannot referee a 10% improvement.

This tension is worth naming: ADR 0003 says the expected IR of a generated
document "is exact and costs nothing". For text it is. For geometry it is not,
because the boxes were typed by hand rather than read off the render. Deriving
exact Zone boxes from the source HTML is the honest fix and is **out of scope
here** — recorded in "Further Notes".

### Stage 1 — snap-to-ink

Per box, per edge, in this order:

1. **Trim.** Move each edge inward past blank rows/columns until it meets ink.
2. **Grow.** Move each edge outward while the boundary row/column carries ink, so
   an edge can never come to rest part-way through a line of text or a logo.
3. **Cap.** Growth stops at the midpoint between this box and the nearest other
   box on that axis, and at a fixed maximum expressed as a fraction of the page.

Properties that make it safe, each of them a test:

- **Idempotent** — snapping a snapped box changes nothing.
- **Cannot create overlap** — the midpoint cap makes it impossible for two boxes
  to grow into each other, so a layout that validated before still validates.
- **Invisible on good geometry** — a box already tight against its ink is
  returned unchanged.
- **Leaves blank Zones alone** — a crop with no ink is the existing empty-Zone
  guard's finding, not the snap's; the snap returns such a box untouched.
- **Ignores Separators** — a rule is not ink to grow towards.

**Wiring, once the gate passes:** the Orchestrator snaps the boxes the Engine
returned, re-runs Band validation, and **keeps the unsnapped boxes if the snapped
ones no longer validate**. A deterministic step must never be able to cost a
Conversion.

**Gate 1, pre-registered.** Measured on the 24 recorded `invoice_0001` layout
answers plus a fresh layout-only sweep of the other four fixtures:

- **Ship** if, on run 32's answer, `covered` rises by at least 0.10 absolute or
  `iou` rises by at least 0.10 absolute, **and** `splits` does not increase on any
  of the 24, **and** `zones` is unchanged everywhere.
- **Reject** otherwise, and record the numbers rather than tuning the algorithm
  until it passes.

**Gate 1 is also the diagnostic that chooses Family 2**, and this is the reason
the whole stage exists:

| run 32 after snapping | reading | what happens next |
|---|---|---|
| `iou` >= 0.75 | the model's *grouping* was always right; only its arithmetic was wrong | keep the VLM geometry pass; re-run #19's model comparison on snapped geometry before drawing any conclusion from it |
| `iou` <= 0.65 | grouping is the problem, and no amount of edge repair reaches it | Family 2 gets its own spec; the classification work in #12/#19 is measuring the wrong thing until it lands |
| between | both | keep the snap, and open Family 2 anyway |

### Stage 2 — guards that measure, and do not yet enforce

`splits` and `doubles` are reported in the run's geometry report and in the probe
summary. **They do not raise, do not create Findings, and do not reject a
layout in this spec.** The reason is on the record twice over: the four prompt
attempts in 0002 that were "obviously right" and cost Band numbering, and a ruler
whose own calibration is Stage 0's open question. A guard tuned against a soft
ruler rejects good geometry.

What already exists and is *not* re-litigated here: the empty-crop guard
(`MIN_ZONE_INK`) and uncovered-ink Gap detection are in flight on this branch
with tests, and they enforce. Splits and doubles join them only once there are
numbers from all five fixtures saying where the threshold is.

### Stage 3 — recursive XY-cut, as a probe only

Blind dilation failed at grouping because it has no notion of axis alternation.
Recursive projection cutting does:

```
ink profile down the page -> widest full-width whitespace gaps -> Bands
  within each Band: ink profile across -> gutters -> columns
    recurse until the largest remaining gap is under threshold
```

It is the only candidate that emits **Bands and columns natively**, which is the
IR's own vocabulary. It goes in the existing CV probe tool as another arm, scored
by Stage 0's ruler, sweeping the gap threshold the way the morphology arm swept
kernels.

**Gate 3.** It earns a follow-up spec only if it produces six Zones on
`invoice_0001` **with Bands and columns matching the expected IR** and beats the
model's snapped score on `covered` and `splits`. Beating `iou` alone is
explicitly not enough — morphology's 0.475 is the standing example of why.
Nothing here wires a non-model segmenter into the pipeline.

### The fixture sweep, cheaply

Four fixtures have never had their geometry measured by anything. They do not
need conversions to be measured: the geometry pass is **one call per fixture**.
The probe tool takes a fixture list and runs layout only, two repeats each — on
the order of eight calls and a few minutes, against roughly four minutes per full
conversion. Snapping is then applied offline to those answers at no further cost.

## Testing Decisions

A good test here asserts what an operator would see — the pixels a Zone's crop
contains — and never that a particular arithmetic step ran. Prior art is on this
branch already: `tests/test_layout_guards.py` builds synthetic arrays (blank
paper, printed paper, a photographed blank at a known noise sigma) and replays
the two *measured* layout answers as constants, then asserts the guard fires on
the sliver run and is silent on the shipped run. Every test below follows that
shape.

- **Snap-to-ink, on synthetic pages.** A box drawn across the middle of a printed
  band grows to contain the whole band. A box with a wide blank margin shrinks to
  the ink. A box already tight is returned unchanged, byte for byte. Snapping
  twice equals snapping once.
- **Snap-to-ink cannot create overlap.** Two boxes a few pixels apart, each with
  ink beyond its edge, come back non-overlapping.
- **Snap-to-ink on the measured answers, replayed as constants.** Run 32's six
  boxes and run 25's slivers, as literals in the test, asserting the direction of
  travel on each: the figure box gets taller, no box loses `_validate_bands`.
- **A Separator does not attract growth.** A box above a horizontal rule does not
  grow to include it.
- **A blank crop is left to the empty-Zone guard.** Assert the snap returns it
  unchanged and the existing guard still reports it — one failure, one owner.
- **The score record, on hand-built geometry.** A page with two printed blocks:
  perfect boxes score `covered` ~1.0, `splits` 0, `doubles` 0; one box across
  both blocks scores `doubles` 1; a box with an edge through a block scores
  `splits` 1; two column strips over a row-structured page score high `iou` and
  bad `doubles`, which is the morphology failure expressed as a test.
- **The Orchestrator's fallback.** Given geometry that snapping would make
  invalid, the Document keeps the unsnapped boxes and the Conversion completes.
- **Replay suite.** Snapping changes crop rectangles, so the recorded responses
  still replay in order but any test asserting a specific crop size needs
  checking. This is a known consequence, not a surprise: note it in the PR, and
  do not re-record anything here — #16 owns re-recording.

Not tests, but required output: every stage's numbers land in
`debug/runs/<label>/` with the usual host, model, resolution and CPU/GPU split,
so the next reader checks the claim instead of re-running it.

## Out of Scope

- **Changing `LAYOUT_PROMPT` or `CLASSIFY_PROMPT`.** Six measured attempts across
  0002 and runs 26-28 say the wording lever is short. This spec does not touch
  either prompt.
- **Model selection.** Which model runs which step is #19 and stays there — but
  see the decision rule: if snapping lifts geometry materially, #19's comparison
  should be re-run on snapped geometry rather than on today's.
- **Wiring any non-model segmenter into the pipeline.** Stage 3 is a probe. Even
  a winning XY-cut gets its own spec.
- **A pretrained layout detector** — DocLayout-YOLO, PaddleOCR, Tesseract page
  segmentation. Worth one probe as a ceiling measurement, since nobody knows
  whether 0.9 IoU is reachable on this page or whether 0.6 is what the task
  allows. It brings a new dependency class, so it is recorded and not scheduled.
- **Family 2 itself.** Specified in outline above, built only when Gate 1 says so.
- **Nesting the IR.** Both XY-cut and Family 2 produce a split tree naturally, and
  Zones are a flat list by definition. Flattening is their cost to bear here; a
  nested IR would touch every fixture and every renderer path.
- **Deriving exact fixture geometry from the source HTML.** See "Further Notes".
- **Multi-page, and anything downstream of extraction.**

## Further Notes

**The 24 free samples.** `debug/runs/*/dump/*/invoice_0001/00_layout.json` holds
24 recorded layout answers spanning every prompt attempt, both models and four
resolutions. They are 24 independent starting points for the same page, which
makes Stage 1's offline test far stronger than a single before-and-after: a snap
that helps regardless of which wrong answer it starts from is a property of the
method, not of one run.

**The eyeballed-fixture problem is bigger than this spec.** ADR 0003's argument
for synthetic-first evaluation is that a generated document's expected IR is
exact. That holds for text and does not hold for geometry, because the Zone boxes
in the fixture builders were typed by hand. `example/invoice.html` is the source
of `example/invoice.png`, so exact Zone rectangles are recoverable by rendering
it and reading element geometry — one mapping decision per Zone, made once, and
then the ruler is exact for all five fixtures. That is a real piece of work and
it would retroactively sharpen every geometry number this project has recorded.
It is out of scope here, and Stage 0's calibration exists precisely to measure how
much it matters before anyone commits to it.

**What this spec does not license.** Every number above except the morphology
sweep comes from `invoice_0001`, and most of it from a single run at a degraded
41%/59% CPU/GPU split. The fixture sweep in Stage 1 is the first time four of the
five fixtures will have had their geometry measured at all. Expect surprises
there, and expect the two-stacked-tables case (expected boxes ending at 0.60 and
starting at 0.63) to be the hardest thing for any gap-threshold method to get
right — it is the same judgement that took five runs to fix in the prompt.

**Why Family 2 is worth keeping in view even if Stage 1 wins.** The pipeline asks
the VLM for metric coordinates, which runs 26-28 show it cannot produce reliably
at any resolution or under any framing, and never asks it for the thing it is
good at, which is judging what belongs with what. Family 2 inverts that: exact
primitives from pixels, a partition from the model, boxes as unions. It also
happens to address run 22's Zone 3 regression from the other end — grouping is
asked with the whole page visible, so the evidence that lives *between* Zones is
present at grouping time, while Kind stays a per-crop question.

**Staging.** The four stages are ticket-shaped and independent enough to split
with `/to-tickets`: Stage 0 blocks Stages 1-3; Stage 1 blocks the Family 2
decision; Stages 2 and 3 are parallel once Stage 0 lands.
