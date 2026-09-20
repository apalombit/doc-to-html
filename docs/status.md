# Status — 2026-09-20 (Phase A-1 done; Thread 2/B, increment 1 in the tree)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then
[`specs/0007-handover.md`](specs/0007-handover.md) (the per-thread prompts and
the full Phase A-1 scope). This file is the summary, not the source.

Branch `scaffold`. 636 tests pass, `mypy src/` clean. Phase A-1's code is in
the tree and its checkpoint scores are frozen at `tests/frozen/a1-checkpoint/`;
Thread 2/B's first increment — palette and page width — is in the tree behind
`DTH_STYLE_RECORD`, default on.

---

## Where we are

**Thread 0 is complete and its gate is met.** The project no longer optimises
agreement with a hand-typed reference IR; it measures whether the rendered
output looks and reads like the source document. The measure, the corpus and
the review surface all exist and are tested.

**Phase A-1 is built and its three causes are fixed. Its gate is NOT met**, and
the reason is now measured rather than suspected — see below. Checkpoint run
`88-a1-checkpoint`, all fifteen documents, taken 2026-09-19 in one sitting. It
is the ratchet's starting notch by decision 1 below, and the report says so:
there is no previous run to compare it against, because no earlier run was
taken in this sitting.

**Thread 2/B is next, ahead of A0 — decided 2026-09-20.** A0 moves precision
(0.91–0.98 across the corpus), which is real but small, and its own gate is
disproved (below). Meanwhile `height_ratio` runs from 1.03 to **3.70** and the
renderer draws a card round every titled Zone on roughly ten documents. 2/B is
also the only remaining thread that adds **no model call**, so it is
deterministic, testable offline, and cannot threaten the ratchet A-1 just set.

**A0's pre-registered gate is dead, and is not being replaced yet.** T1 = 1.00
on the sweep set is disproved by A-1's own checkpoint: `receipt_0010` sits at
recall 0.175 and `catalogue_0015` at 0.571, and none of A0's three faults — a
deleted table header, a Title repeated in its own body, a hard line break —
touches either. The replacement is set **when A0 begins, from that sitting's
measurements**. The number has moved twice already; guessing a third value now
is how it moves a fourth time.

**The notch now lives in the repository.** A-1's checkpoint scores are the T1
ratchet's floor and were sitting in `debug/runs/`, which is gitignored and gets
cleared. They are frozen at **`tests/frozen/a1-checkpoint/scores.json`**, and a
checkpoint ratchets against them by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a1-checkpoint/scores.json
```

## Phase A-1 — what landed

| cause | fix | evidence, taken this sitting |
|---|---|---|
| a table read then discarded | `wire.rows_from_table` reconciles instead of raising: short rows padded with cells carrying **no Reading**, long rows kept whole, `table_repairs` declares both | fires on `darkdeck_0009` — *"row 7 came back 4 cell(s) short of the header's 5 and was padded rather than discarded"*; that Zone used to be abandoned |
| light ink on dark ground | `preprocess.ground_is_dark` + `rectify` turning the page over **before** `equalise` | `darkdeck_0009` goes from **1 detected region to 13**, and converts at recall 0.929 |
| ink outside every box | `orchestrator.recovered_zones` gives it a Zone; `preprocess.uncovered_regions` bounds it to its own ink and measures it | `nonlatin_0014` recovers its title; the original five gain nothing, which is right — their coverage was already complete |
| loss declared without saying how much | `ir.Shortfall`, plus `ink_share` on `Gap` and `Failure`; `honesty.py` joins the scorer's ground truth to the pipeline's self-reporting and gates the run | `receipt_0010` now declares *"Zone 1 (table) was read short — 19 printed lines, 3 returned [50% of the page's ink]"* where it used to say "may be a mark" |

**Two corrections to the scoping, both found by measuring and neither
inherited.**

- **`receipt_0010` is not a coverage failure.** On the shipped configuration
  the detector covers that page — three Zones, the middle one holding 50% of
  its ink — and the only ink outside every box is a dotted rule 1px tall. Its
  loss is content covered and then read short. Same for `form_0007`'s title,
  whose ink lies inside a neighbouring Zone's padded crop. The document where
  cause 2 is real is `nonlatin_0014`.
- **Gap findings were measured over the wrong thing, twice.** The rectangle
  rather than the ink (a page-spanning box reported 100% of the page's ink
  where the truth was 18%), and then the uncovered total rather than the page's
  (a 2px sliver reported 100%). Both are fixed in `uncovered_regions`, and a
  third instance — `ir._decode_document` dropping `ink_share` on the way back
  in, so a Gap whose own note read 18.5% reported 0.0 to anything reading the
  IR — is fixed in the decoder.

## Phase A-1's gate — failed, and why

**Nine of fifteen documents still lose content quietly.** The gate is wired
into `report.html` and is failing honestly, which is the mechanism working;
what it has established is a ceiling on the rule itself.

**The loss that remains is *within* lines, and no line count can see it.**
Every quiet-loss document returned **as many printed lines as the crop holds,
or more**, while losing words inside them: `catalogue_0015` read 28 lines where
20 are printed and lost 43% of its tokens; `menu_0012` read 31 for 18 and lost
17%.

**Two pixel-side detectors were built and measured before this was concluded,
and both were rejected** for firing on correct documents while missing the
worst real loss — ink per character against the page median (`sample_css_0004`
lost nothing and peaks at 6.2x; `catalogue_0015` lost 43% and peaks at 2.6x),
and characters expected from ink normalised by the Zone's own type height
(`invoice_0001` lost nothing and reads 3.4x; `newsletter_0008` reads 8.0x
having lost 5.7%). `honesty.py`'s docstring carries the table. **Do not build a
third without a new kind of evidence.**

**What would reach it** is two readings of one crop compared against each
other. The IR already has `CellState.DISPUTED` and the Ladder, and
`_climb_ladders` already says it waits on a second Engine. That is model time
and a decision for a later thread.

**What this settles about Thread 3/C.** 3/C's gate classifies each residual
error as (a) the IR cannot express it, (b) a pass read it wrong and would again,
or (c) it needs a second look at the whole page — and the repair loop is built
**only if (c) is a material share**. This residue is **(b)**: the conversion is
deterministic at `temperature: 0`, so a loop re-reading the same crop gets the
identical wrong answer back. **Do not plan on 3/C to recover recall**, and do
not let that hope justify deferring reading quality. On current evidence 3/C
closes unbuilt, the way spec 0006's Change 3 did.

## One docs fault found while planning 2/B — 2026-09-20

**The OpenCV rectangle finder is not in the tree and never was.** `CLAUDE.md`,
spec 0007 and ADR 0005 each told the next session it existed, worked, and must
not be rebuilt. `git log -S findContours` across all history returns exactly one
introduction — `preprocess.find_page_quad`, page-edge detection for
rectification. `tools/cv_layout_probe.py`'s `zones_from_morphology` dilates ink
into blocks and cannot see a drawn border.

Spec 0006 Change 3 measured it in a scratch script that was never committed, and
three documents carried the claim forward as fact. **Thread 2/B has to build
it**, and the two things recorded about it — the panel and card counts, and the
0.80-of-the-page guard — are a starting point to re-measure rather than results
to cite. All three documents are corrected.

It is the same fault this project keeps recording about itself, turned inward:
*a claim that nothing verifies*. The `dth_env.txt` lesson says prove the arm was
armed before believing a null result; this says prove the code is there before
planning around it.

## Thread 2/B increment 1 — palette and page width — 2026-09-20

**What shipped.** `style.py` measures a page's ground, ink, accent and shaded
furniture from its own pixels — no model call, ADR 0005 — and `Document.style`
carries them into the render, which emits a second `<style>` overriding the
house palette. Behind `DTH_STYLE_RECORD`, default on, named explicitly on the
bake-off's `Conversion` so the arm is provably armed rather than resolved a
second time from the environment. **`Document.page_px` is measured, traced and
round-tripped but the renderer does not act on it** — see the width section
below, which is the run's main result.

Two details that are decisions rather than plumbing:

- **`inverted` is passed, not inferred.** `rectify` has already turned a
  light-on-dark page over, so `darkdeck_0009` arrives at `measure` as a light
  page. Measuring it as it stands reports white paper for a near-black
  document.
- **`--muted` and `--rule` are derived from the measured pair, not fixed.**
  `#666` and `#e0e0e0` are grey-on-white by design; on a black ground the muted
  text goes near-invisible and the hairline rule becomes the brightest thing on
  the page. On a white ground the derivation lands within 3/255 of the
  constants it replaces, so the fourteen light documents do not move.

**What is deliberately not in it: the type scale.** Measured across the corpus
on 2026-09-20 — per-Zone pooled ink-band mode is a median 0.93 of the true CSS
size, inside 0.75–1.13 on thirteen of fifteen — but `catalogue_0015` reads
**2.40×** and no confidence signal tried separates it from `form_0007`, whose
0.40 agreement accompanies an accurate estimate. Shipping it would set 24px type
on a document whose real body is 10px, and `catalogue_0015` currently has the
corpus's best `height_ratio` at 1.03. The numbers and the rejected signals are
in `style.py`'s module docstring.

### Page width: measured, and held back — it fails the hard tier

**This is the increment's main result and it reverses a boundary decision made
on 2026-09-20.** Width moved from A2 into 2/B on the reasoning that nine of
fifteen sources are wider than the old 832px column, so those pages render
narrower and therefore taller. The reasoning was sound and the measurement does
not support it.

Run `89-style-record` (the five, `qwen3-vl:4b`, 2026-09-20) against the notch:

| document | `beside_agreement` | `height_ratio` |
|---|---|---|
| `invoice_0002` | 0.640 → **0.295** | 1.63 → 1.60 |
| the other four | unchanged | unchanged |

`beside_agreement` is **T3, the hard tier**, and the rule is that a regression
there fails a phase regardless of what improved elsewhere. What it bought was
`height_ratio` 1.63 → 1.60 on that same document and nothing at all on the
other four.

**Isolated, not inferred.** That run's own IR was re-rendered four ways —
palette and width, palette only, width only, neither — with the model's answers
held fixed. `beside_agreement` is 0.640 in both arms without the width and
0.295 in both arms with it. The palette is not involved.

**The cause is the band model, not the width.** Naming the lost pairs shows our
`dl` rows re-wrapping at the wider column and drifting out of line with the
source's panels: `Email` beside `Phone`, `Phone` beside `One Microsoft Way`,
and six more the source has side by side stop overlapping vertically in ours.
`flex:1 1 12rem` was approximating the source's columns by accident, and the
true width takes the accident away. **Column shares and `Zone.align` stayed in
A2** — so the item should not have moved, and it moves back.

**What would have to become true** (written down so it is re-tried rather than
forgotten, per the `DTH_CAPTION_PASS` lesson): A2 gives a Band a real column
model, and `invoice_0002`'s `beside_agreement` at the source's width matches or
beats its value at 52rem. `Document.page_px` stays measured and in the IR
waiting for that; only the CSS rule is withheld, and `render.py` carries the
same note.

### Where the height actually is: the card chrome

Measured offline in this sitting over the five committed `tests/frozen/run84/`
outputs — re-rendered from their own embedded IR, scored through `project()`,
no model involved:

| document | `height_ratio` with width | with the cards also flattened |
|---|---|---|
| `invoice_0001` | 1.11 | 1.06 |
| `invoice_0002` | 1.45 | 1.11 |
| `sample_css_0004` | 1.25 | 0.97 |
| `sample_semantic_0005` | 1.27 | 0.92 |
| `sample_table_0003` | 1.21 | 1.17 |

The card chrome `section.titled` draws round every titled Zone is four to eight
times the width's effect, and unlike the width it does not touch `beside`
relations. **That is where 2/B's gate is won.**

**And the fix must be per-Zone.** Flattening every card takes two documents past
1.0 to 0.97 and 0.92 — a blanket removal overshoots as badly as the blanket card
does. That is the detector increment's justification: build it, do not simply
delete the CSS.

### What the palette did — run `89b-palette-only`, the shipped configuration

Run `89-style-record`'s conversions re-rendered through the shipped renderer
(width withheld) and re-scored against the notch in the same sitting. **T1, T2
and T3 are identical to the notch on all five documents** — the ratchet holds
and the hard tier is clean, which is what a zero-model-call thread should be
able to promise.

| document | `ink_delta` | `accent_delta` |
|---|---|---|
| `sample_css_0004` | 0.496 → **0.031** | 1.000 → **0.031** |
| `sample_semantic_0005` | 0.471 → **0.000** | 1.000 → **0.318** |
| `sample_table_0003` | 0.282 → **0.220** | — |
| `invoice_0002` | unchanged | — |
| `invoice_0001` | 0.188 → **0.345** | — |

`invoice_0001` is the one document the measured palette makes worse, and the
disagreement is about scale rather than about the page. Its body ink measures
`(72,72,72)` at full resolution; `scoring._sample` thumbnails the page to 600px
before taking its mode and reads `(112,112,112)`. Both are correct about what
they sampled. **Matching the scorer's sampling rather than the page's pixels was
rejected** — it would be measuring the measurement, and the three documents that
improved did so by measuring the page.

## Checkpoint numbers — run `88-a1-checkpoint`, 2026-09-19

Citable only against a run taken in the same sitting. There was no such earlier
run, which is why the report says "no previous run" rather than showing deltas
against a run from another day.

| document | T1 recall | T1 prec | T2 tau | T3 beside | T3 height | declares its loss |
|---|---|---|---|---|---|---|
| `invoice_0001` | 1.000 | 0.980 | 1.000 | 1.00 | 1.14 | nothing lost |
| `invoice_0002` | 0.966 | 0.923 | 0.849 | 0.64 | 1.63 | **no** |
| `sample_table_0003` | 0.974 | 0.981 | 1.000 | 1.00 | 1.26 | **no** |
| `sample_css_0004` | 1.000 | 0.917 | 1.000 | 1.00 | 1.26 | nothing lost |
| `sample_semantic_0005` | 0.990 | 0.936 | 0.953 | 0.88 | 1.22 | **no** |
| `statement_0006` | 0.928 | 0.970 | 0.999 | 1.00 | 3.70 | **no** |
| `form_0007` | 0.729 | 0.939 | 0.954 | 0.03 | 1.09 | yes |
| `newsletter_0008` | 0.943 | 0.945 | 0.832 | 0.40 | 3.19 | yes |
| `darkdeck_0009` | 0.929 | 0.980 | 0.799 | 0.87 | 2.26 | yes |
| `receipt_0010` | 0.175 | 0.692 | 1.000 | 1.00 | 1.39 | yes |
| `report_0011` | 0.948 | 0.912 | 1.000 | 1.00 | 2.30 | **no** |
| `menu_0012` | 0.833 | 0.951 | 0.829 | 0.35 | 2.77 | **no** |
| `cv_0013` | 0.882 | 0.974 | 0.917 | 0.45 | 2.43 | **no** |
| `nonlatin_0014` | 0.900 | 0.914 | 0.959 | 0.91 | 1.82 | **no** |
| `catalogue_0015` | 0.571 | 1.000 | 0.943 | 0.23 | 1.03 | **no** |

**T1 is reported, not gated** — A0 owns the 1.00, measured after A-1. The
`beside` and `height` columns are the deferred work below and must not be read
as A-1 regressions: column collapse waits for A2 and the renderer's cards for
Thread 2/B.

The model was 54%/46% CPU/GPU for this run. That affects timings only.

## Thread 0 — done, with the gate evidence

| | |
|---|---|
| `corpus.py` | fifteen documents, HTML + screenshot each, split *iterate* (the original five) / *sweep* (all fifteen) |
| `projection.py` | `project()` — one page as a reader perceives it, off headless Chrome. One function, both sides. |
| `scoring.py` | `score_document()` — six axes. T1/T2/T3 hard tier, T1 a ratchet. |
| `report.py` | `debug/runs/<label>/report.html` — the review surface |

The three gate conditions, all met:

1. **The scorer finds run 84's faults unaided.** `tests/test_scoring.py`, no
   model, no network. Asked only general questions it reports
   `sample_table_0003`'s deleted column headers, a Zone Title repeated inside
   its own body in four documents, four surplus hard breaks on
   `sample_semantic_0005`, and `invoice | 123` as a broken join that recall,
   precision and tau all score 1.000.
2. **The report renders all fifteen in one page** — verified structurally,
   fifteen `<section class="doc">`, one per document.
3. **A checkpoint run exists** — `85-thread-0-checkpoint`, taken 2026-09-18.

**The checkpoint run itself is gone or going.** `debug/runs/` is gitignored and
gets cleared. Its numbers are not re-citable and nothing below rests on them —
what is recorded here is *structural* and re-derivable: which fault, which
cause, which line of code. Re-take a sweep when you need numbers.

## What the checkpoint showed, reviewed document by document

Reviewed by Alessandro against the sources on 2026-09-19, render beside
source, all fifteen. **T1 was clean on none of them.** The ten new documents
fail in ways the original five never exposed, and they are four unrelated
causes, not one:

| cause | documents | signature |
|---|---|---|
| Table read, then discarded whole | `statement_0006`, `cv_0013` | `MappingError: table row 1 has 6 cells but the header has 7` |
| Content outside every detected box, dropped | `receipt_0010`, `form_0007`, `nonlatin_0014` | finding says *"may be a mark"* — on the receipt that is 77 of 103 tokens |
| Whole page detected as **one** Zone, silently | `darkdeck_0009` | one Zone, **no finding at all** |
| Columns collapse to one | `form`, `menu`, `cv`, `catalogue`, `newsletter` | `beside_agreement` 0.03–0.40 |

**Two findings that change what the fix costs, both established by looking:**

- **`statement_0006` did not fail to read its table.** The model returned all
  36 transaction rows correctly and the pipeline threw them away because one
  row disagreed with the header on cell count. The content existed. This is
  the cheapest recall in the corpus and it is a reconciliation bug, not a
  perception problem.
- **`darkdeck_0009` is not a bad document.** It was checked for fairness
  first — ordinary contrast, ordinary structure, and it scores perfectly
  against itself. The cause is ours and it is exact: `preprocess._ink()`
  thresholds with `cv2.THRESH_BINARY_INV + THRESH_OTSU`, which treats dark
  pixels as ink, and `darkdeck.png` is **96.2%** below mid-grey, so nearly the
  whole page reads as one ink blob.

## Two corrections made to standing documents

- **The conversion is reproducible, and `CLAUDE.md` said the opposite.**
  `transport.py` asks Ollama for `temperature: 0`, and the five original
  documents came back **byte-identical** to the copies frozen in
  `tests/frozen/run84/` — all five, md5 for md5, on a later commit and with
  the model partly on the CPU. This matters in the dangerous direction: a
  byte-identical arm means **the change did nothing**, not that noise swamped
  it. Scoped to this machine and model; says nothing about the other ten
  documents, which have no prior run.
- **`DTH_SNAP_ZONES` is silently not applying to four of fifteen documents.**
  It moves the boxes onto their ink, the Bands then fail validation, and the
  Conversion falls back to unsnapped geometry. Two shapes: a full-width Zone
  with a narrow box strictly inside it, and two Zones landing on nearly the
  same span. Both are *grouping* questions before they are snap questions.
  The snap is one of the four defaults that must not be deleted — the finding
  is that it is **not being applied**, which is a different fact from it being
  harmful.

## Next — Thread 2/B increment 2, the border and card detector

Full scope is in `specs/0007-handover.md`. **This is now the thread's main
event rather than a tidy-up**, on the measurement in the increment-1 section
above: flattening the cards moves `height_ratio` four to eight times as far as
the page width did, and `height_ratio` is what 2/B is gated on.

It has to be **built**, not reused — the OpenCV rectangle finder three
documents said was in the tree is not, see the docs-fault section above. Ground
truth needs no model and is on disk: `invoice_0002` has four panels,
`sample_css_0004` two cards, `catalogue_0015` nine, and `invoice_0001`,
`sample_table_0003` and `sample_semantic_0005` have **none**. The zero case is
the one that matters — a detector that cards everything is the fault being
fixed, and the flattening measurement says a detector that cards *nothing*
overshoots to 0.92 on `sample_semantic_0005`.

Re-measure the inherited 0.80-of-the-page guard on `invoice_0001` while
building it and record the number taken in that sitting; it describes code that
never existed.

**After that, still in 2/B:** the type scale, gated on `height_ratio` directly
rather than on agreement with the CSS size, for the reason in the increment-1
section.

**Deferred on purpose, with the reason, so they are not read as new faults:**

- **The renderer's cards — no longer deferred, and no longer next-but-one:
  they are the item above.** `render.py`'s `section.titled` still borders every
  titled Zone unconditionally, so a flowing document like `report_0011` renders
  as a stack of cards and the source is never consulted.
- **Page width — measured and back in A2's hands.** It moved from A2 into 2/B
  on width reasoning that measurement did not support; the CSS rule costs
  `invoice_0002` a hard-tier metric and the cause is A2's band model. See the
  width section above for the isolation and for what would have to become true.
  `Document.page_px` is in the IR and traced, so A2 inherits the measurement
  rather than the work. **`Zone.align` never moved** — it stays in A2 too, even
  though ADR 0005's table lists alignment under B.
- **Column collapse still waits for A2.** Accepted interim state: **content
  complete and reading order correct, in one column.** Do not trade T1 for
  column shape.

## Decided — both open questions, 2026-09-19

Asked before either bound, and now written into
[`specs/0007-handover.md`](specs/0007-handover.md) with what was rejected.

1. **The ratchet's starting notch is A-1's checkpoint.** Every phase from A-1
   onward is measured against it, and A0's pre-registered "T1 = 1.00 on the
   sweep set" is re-baselined and measured *after* A-1. Rejected: leaving the
   notch at A0, which would have let A-1 move T1 with no floor under it.
2. **The honesty rule covers loss and only loss** — token recall, and content
   that never arrived. Duplication is a precision fault and a mis-split a join
   fault; neither is content that failed to arrive, and the pipeline has no
   ground truth with which to detect a mis-split at all. Both stay A0's to
   **fix** rather than A-1's to announce. **So the regression worry does not
   materialise:** `invoice_0001` and `sample_css_0004` produce no new findings
   under this scope.

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in the current
  session counts. A run number is not evidence. Two exceptions, both committed
  and both narrow: `tests/frozen/run84/` (five output documents, scored offline
  with no model) and `tests/frozen/a1-checkpoint/` (A-1's scores, **the T1
  ratchet's floor**). The second is a floor to ratchet against, not a result to
  quote in an argument.
- **`debug/runs/84-rule-not-a-line/` must be left intact.** Verified present
  and untouched as of 2026-09-19.
- **`tests/documents/SAMPLE_DOCUMENTS` is test input only — never score
  against it.** Doing so rebuilds the harness spec 0007 deleted.
- **Do not delete** the two dormant safety nets (`wire._without_empty_rows`,
  `_reread_as_prose`) or the four shipped defaults (`DTH_SNAP_ZONES`,
  `DTH_TABLE_GRID_HINT`, `CLASSIFY_PROMPT`, `_reread_as_prose`).
  `_without_empty_rows` has a real `if row.cells` bug — that is **A0's** to
  fix, not A-1's, and the net stays.
- **The OpenCV rectangle finder has to be BUILT in Thread 2/B** — it is not in
  the tree and never was (see the docs fault above). Keep its recorded
  >0.80-of-the-page guard, and re-measure it rather than citing it.
- **`project()` compares a normalised view** — text runs in reading order,
  block roles, client rects — and never raw markup. A scorer that demands our
  output reproduce the source's div nesting or class names is a worse overfit
  than the one being escaped.
- **`report.html` is a required deliverable of every run**, not a nicety.

## The loop

```
tools/iterate.sh <label>                  # one document, shipped defaults
FIXTURE=iterate tools/iterate.sh <label>  # the five, ~17 min
FIXTURE=sweep   tools/iterate.sh <label>  # all fifteen, ~90 min, at a phase gate
```

A sweep took ~90 minutes on 2026-09-18, not the ~50 the old note estimated —
that figure predated the ten new documents. Then open
`debug/runs/<label>/report.html`.
