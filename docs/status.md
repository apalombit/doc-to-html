# Status — 2026-10-10 (**reset: nothing queued; fresh sweep `F1-sweep` for Alessandro's review**; `q5-result/` the floor)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-10, when
N4 shipped and Alessandro cleared every open task and idea.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **845 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22; heading sizes 2026-09-29
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
Phase A1    Inline runs, and hard line breaks   DONE 2026-09-25, gate NOT met
Phase A2    Geometry — re-scoped                DONE 2026-09-25, gate MET
Phase A3    Figure pixels                       DONE 2026-09-26, gate MET
Open issues 1-3 DONE 2026-09-26 offline; 4 -> the type scale
Queue       Q1-Q7, in order, go given 2026-09-27
              Q1-Q4 DONE 2026-09-27 to 2026-09-29, offline, gates MET
              the corpus pictures re-shot whole, floor re-cut   2026-09-29
              Q5 DONE 2026-09-30, sweep Q5-40-sweep, gate MET 8 of 8
            continued: N1-N4 model-free
              N1 DONE 2026-09-30, offline, gate MET 8 of 8
              N2 DONE 2026-09-30, offline, gate MET 8 of 8
              N3 DONE 2026-10-10, offline, gate MET 7 of 7
              N4 DONE 2026-10-10, offline, gate NOT met on the ratchet;
                 shipped on Alessandro's decision, the exception recorded
Reset       2026-10-10, Alessandro: every open task and idea cleared —
              Q6, Q7, N5, the live-fault list, Thread 3/C, Thread 4/D.
              Nothing is queued. Fresh sweep F1-sweep, commit 12fa2d1,
              shipped defaults; the next work comes from his review of it.
```

Q1-Q4's result tables moved to
[`specs/0007-handover.md`](specs/0007-handover.md), "Outcome — Q1 to Q4".

---

## The floor — `tests/frozen/q5-result/`, DECIDED 2026-09-30

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/q5-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five and says nothing about the other ten.

**It is the floor and the control since 2026-09-30, Alessandro's decision.**
Sweep `Q5-40-sweep`: the fifteen documents today's code makes, with the
answers that made them. It dominates `reshot/` on every ratcheted leg of
every document — fourteen byte-identical, and `receipt_0010`'s tau 0.800 →
1.000 and beside 0.871 → 1.000 with recall and precision unchanged — the
condition every floor move but one has met. Scored straight out of the
directory, **15 documents, 0 differing fields**; `tools/rederive.py` over it
reproduces it **15 of 15 byte for byte**, and so does `tools/replay_run.py`
from its committed `answers/`; `tools/layout_front.py`'s Zones match its IRs
on 15 of 15. Its README says what moved against `reshot/`: the receipt, and
nothing else.

### The one before it — `reshot/`, 2026-09-29 to 2026-09-30

**It moved from `a3-result` because the pictures were wrong, not the
pipeline.** The ten authored corpus pictures were shot before
`projection.SHOT_SLACK` existed and each was missing its bottom 60-90px, so
up to 266 tokens were scored against a model never shown them. They were
re-shot, one sweep was taken at HEAD, and **Alessandro decided in advance
that it would be the floor.** It is the one floor that does not dominate the
one before it; its README names every leg on which it falls below
`a3-result` and why — four words and `cv_0013`'s reading order among them.

It was also the control until Q5 moved the receipt's Zones: `rederive.py`
re-applies what works on the IR, not the detector, so over `reshot/` it
cannot reproduce today's receipt.

### What the ratchet enforces, per document

`report._ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside a failure to say how far it fell. **The
floor never falls for any reason** — `reshot/` is the one move that gave
ground, decided in advance and accounted for leg by leg.

**One standing exception since N4, 2026-10-10, Alessandro's decision:**
`catalogue_0015` T3 beside sits below the floor, 0.2523 → 0.2364. The broken
render's letter-stacked `each` held four agreements by overlapping its
neighbours' price rows; drawn on one line it cannot. Every report against
`q5-result/` names it. It is accepted; nothing else is.

---

## Where the corpus is — at the floor, `q5-result/`

| | mean |
|---|---|
| vocabulary recall | 0.9708 |
| recall (multiset) | 0.9664 |
| precision | 0.9865 |
| join recall | 0.9434 |
| tau | 0.9366 |
| beside agreement | 0.7622 |
| height ratio | 1.621 |
| `hard_breaks` | 5 |
| `figures_lost` | **0** |
| T6 inline runs | 8 of 42 |

`reshot/`, the floor before it, differs on three rows and one document: its
tau 0.9232, beside 0.7536 and height 1.610 are `receipt_0010` before Q5.

### The live faults — cleared 2026-10-10

The list drawn from `Q5-40-sweep`'s review was cleared with the queue. The
next one comes from Alessandro's own review of `F1-sweep`.

---

## What the last step shipped

### N4 — a label with no value spans the row, `12fa2d1`, 2026-10-10, **gate NOT met on clause 3; shipped on Alessandro's decision**

**The IR was right and the renderer was not.** `catalogue_0015`'s Zones 5 and
8 hold `£28.00 | each` and `£18.75 | each`. A pairs Zone is a grid of
`auto 1fr`, and a pair with **no value** still put its label in the `auto`
column, so `Suffolk pattern, 265 mm, beeswax | ""` sized that column to the
whole card and left the `1fr` column a few pixels, where `overflow-wrap:
anywhere` (A2's guard against clipping) broke `each` after every letter.
`render._pairs` now marks such a label `alone` and the stylesheet draws it
across both columns, so only a label with a value sizes the label column.
`TestALabelWithNoValueDoesNotSizeTheLabelColumn` pins it in the browser, and
fails without the rule.

Measured offline: `N4-00-base` → `N4-01-proto`, both `rederive.py` over the
N3 replay, which the base reproduces 15 of 15.

| # | clause | result |
|---|---|---|
| 1 | `catalogue_0015` Zones 5 and 8: `each` drawn on one line, beside its price | **holds** |
| 2 | the eleven documents with no value-less pair render pixel-identical; their HTML differs only in the stylesheet; every embedded IR identical | **holds** — `cv_0013` and `invoice_0002` pixel-identical too; only catalogue and form move |
| 3 | ratchet against the floor, four legs, all fifteen | **FAILS** — `catalogue_0015` T3 beside 0.2523 → 0.2364 |
| 4 | `clipped` 0 on all fifteen — A2's guard holds | **holds** |
| 5 | visual review, fifteen sheets, `--previous` the baseline: catalogue `better`, none `worse` | **holds** — catalogue `better`, form `same`, thirteen pixel-identical |
| 6 | a test pins the rule; tests and mypy clean | **holds** — 845, clean |

**Why beside fell: the broken render was rewarded for being broken.** Stacked
a letter to a line, `each` was a block four lines tall, and it overlapped the
price rows of the cards beside it — `£7.40` and `per metre` in row 2, `£5.60`
and `6 left` in row 3 — four pairs the source also has side by side. On one
line it overlaps only its own price: those four go, and two genuine ones
arrive (`In stock` beside `£5.60` and `6 left`). 28 of 111 → 26 of 110. No
word moved and no other leg on any document fell. The row-2 pairs cannot come
back while `OK-330`'s Title is drawn as two large headings, which push its
price 46px below its neighbours'. T5's `ink` on catalogue moved 128 → 192
grey: a modal flip, the card border outnumbering the text on a page 53px
shorter, not a colour change.

### N3 — a totals row across the table's edge, `8e1c0f8`, 2026-10-10, **gate MET, 7 of 7**

**The detector put it there.** heron ends `statement_0006`'s transactions
table at 0.9300, through the middle of its own totals row, and reports
`Totals for the period` as text at 0.9255–0.9352. Starting 0.0045 above the
edge, it was never a strip *under* the table for `attach_trailing_rows`; not
wholly inside, `without_enclosed` kept it. In the table's Band it printed the
line a second time, refused the snap for the page, and squeezed the table
into two thirds of the width. `detector._trailing_row` now also takes a strip
that starts below the table's top and ends below its bottom, under every
other guard.

**Measured with no model, and why that is enough.** `tools/layout_front.py`:
exactly `statement_0006` changes, 6 Zones to 5, and its five remaining boxes
are identical to full precision — the detector's own snap had already put
them on their ink, so the snap the sliver blocked moves nothing. A change
that only removes a Zone moves no crop, so `tools/replay_run.py` measures it
— over a scratch copy of the control's answers with the sliver's three calls
(classify, prose, runs) taken out. The Conversion then asks exactly the other
17, with byte-identical prompts, nothing asked beyond the run and nothing
unserved. The replay baseline, unmodified, equals `rederive.py`'s arm 15 of
15, so the two loops agree on today's code.

| # | clause | result |
|---|---|---|
| 1 | `statement_0006`: 5 Zones; `Totals for the period` printed once; 42 rows, column-sum reconciles | **holds** |
| 2 | layout front: the other fourteen's Zones identical; statement's five boxes identical to full precision | **holds** |
| 3 | replay asks exactly the 17 remaining calls, prompts byte-identical | **17 of 17** |
| 4 | the other fourteen byte-identical; statement precision 0.9827 → 0.9903, height 2.05 → 1.60, columns within tolerance 0.559 → 1.000, and their companions | **holds** — 14 of 14 |
| 5 | ratchet against the floor, four legs, fifteen; the report's snap line names no document | **holds; none** |
| 6 | visual review, fifteen sheets, `--previous` the replay baseline | **no `worse`** — fourteen `same`, statement `better` |
| 7 | tests, mypy | **843, clean** |

**A caveat on the offline loop.** On a run built by `rederive.py` the report's
"The Bands are valid everywhere" is vacuous: `_snap_note` reads refusals from
`trace.json`, and `rederive.py` writes none. Replays and sweeps write one.

### N2 — the Gap audit reads type, `1a720ef`, 2026-09-30, **gate MET, 8 of 8**

**Two stages put ink that is not type where the audit looks.** On
`receipt_0010` the page warp keeps 2px of the grey ground round the paper, a
frame along all four edges: 23.0% of the page's ink. On `cv_0013`, `equalise`
takes the dark sidebar for uneven light and blows it out, leaving dark halos
round every item and along the panel's edge: 26.1% of the page's ink between
the Zone boxes. Fixing either stage moves the pixels the model is shown and
costs a sweep. The audit is where the false finding is made, and fixing it
there is free.

`preprocess.uncovered_regions(type_only=True)` takes off, before the boxes:
the page's outermost rows and columns while each is inked over
`PAGE_EDGE_INK` (half) of its length — the receipt 0.97-1.00, every other
page 0.00-0.03 — and solid blocks, `_without_panels` at the page's scale with
a margin of one `PANEL_SPAN`, because the halo fades over several pixels (at
deskew's one-pixel margin three fragments of it stayed as findings).
**Only the audit asks for it** — `orchestrator.gaps`, shared by `_audit` and
`tools/rederive.py`, which gains the step. Recovering Zones reads the ink as
before, since a solid block no box covers may be a lost figure; on the corpus
the two agree, Zones identical either way. That narrows what was proposed —
the cut was put to Alessandro as sitting in the shared mask — and changes no
output.

Measured by `tools/rederive.py` over the control, one change apart from N1's
arm (`N1-02-shipped`); the Gap step, run with no cut, reproduces that arm 15
of 15:

| # | clause | result |
|---|---|---|
| 1 | `cv_0013`: one Gap, 0.6%, hedged | **holds** — from 5, the 26.1% among them |
| 2 | `receipt_0010`: one Gap, the dashed rule, 2.1%, hedged | **holds** — from 2 |
| 3 | the other thirteen byte-identical; the two differ only in the panel and the IR's `gaps`; fields only height and T5 texture | **holds** — 13 of 13, and those 6 fields |
| 4 | `tools/layout_front.py`: Zones identical | **15 of 15** |
| 5 | ratchet against the floor, four legs, fifteen; honesty tally | **holds; 4 / 8, unchanged** |
| 6 | `rederive.py` gains the Gap step and reproduces the baseline with no cut | **15 of 15** |
| 7 | visual review, fifteen sheets, `--previous` N1's arm | **no `worse`** — thirteen `same`, the two panels `better` |
| 8 | tests, mypy | **840, clean** |

### N1 — the Shortfall counts lines as the Extractor does, `4d4bccd`, 2026-09-30, **gate MET, 8 of 8**

**The model was right.** `PROSE_PROMPT` asks for the lines the document
*breaks* — "a line that runs to the right-hand edge and continues below it
has merely wrapped, and is one line" — and both paragraphs read whole were
answered to the letter. `orchestrator.shortfall` compared them against
`printed_lines`, which counts every line the type wraps onto. And
`darkdeck_0009` Zone 4 was right by the same accident: "Open risks" over one
bullet wrapped onto two lines, a one-line loss read as two. Its twin, Zone 10
— "Decisions wanted" over one bullet — was reported by nothing.

`preprocess.hard_lines` counts in the Extractor's unit: a printed line ending
within `WRAP_TOLERANCE` (0.15) of the widest line's end, with another below
it, is a wrap. **There is no empty band** — over every prose and list Zone of
the control, wraps stop up to 0.104 of the width short and deliberate breaks
as close as 0.007 (`invoice_0001`'s right-aligned address) — so the tolerance
sits above every wrap and an ambiguous line counts as wrapped, the side that
can only silence a finding. With wraps gone, a prose or list Zone fires at one
line short (`SHORTFALL_HARD_LINES`); tables and pairs are untouched at two.
Counting printed lines at one short would have fired on eight Zones, six of
them wraps.

Gate agreed before any code, measured by `tools/rederive.py` over the
control, one change apart from its baseline (`N1-00-base`, 15 of 15
byte-identical to `q5-result/`, 0 differing score fields):

| # | clause | result |
|---|---|---|
| 1 | `darkdeck_0009`: exactly Zones 4 and 10, each 2 printed / 1 read | **holds** |
| 2 | `invoice_0002`, `newsletter_0008`: no Shortfall | **holds** |
| 3 | the other twelve byte-identical to the baseline | **12 of 12** |
| 4 | the three differ only in the findings panel and the IR's `shortfalls`; score fields only height, T5 ink and texture, `newsletter_0008`'s `split_regions` 1 → 0 | **holds** — the 14 fields the scratch arm predicted, and no others |
| 5 | ratchet against the floor, four legs, fifteen | **holds** |
| 6 | honesty tally 6 declared / 6 quiet → 4 / 8 | **4 / 8** |
| 7 | visual review, fifteen sheets, `--previous` the baseline | **no `worse`** — twelve `same`, the three panels `better` |
| 8 | tests, mypy | **836, clean** |

**Clause 6 is the truth, not a regression, Alessandro's decision.**
`invoice_0002` and `newsletter_0008` were "declared" only by the false
Shortfalls. What they actually lose — `adipisicing` and `blanditiis` misspelt
inside Zone 7's paragraph, and `councillor` — is loss inside a line, which A-1
established no finding can see.

### The corpus pictures, re-shot whole — `4b6d34d`, 2026-09-29

All ten authored pictures were missing their bottom 60-90px: footers,
`form_0007`'s signature line, `report_0011`'s third footnote, `cv_0013`'s last
publication, `receipt_0010`'s last three lines. They were shot before
`SHOT_SLACK`, in the commit that added it, and `shoot_corpus.py --check` could
not see it because it scores the HTML against itself. Re-shot with `--force`;
two independent shoots agree to the pixel; **`test_projection`'s
`TestTheCorpusPictureIsItsOwnHTML` fails on every one of the old pictures.**

### Deskew on type alone — `8f70679`, 2026-09-29

On the whole picture `cv_0013`'s dark sidebar runs the page's full height.
`skew_angle` scores angles by how sharply the ink stacks into lines, and a
full-height panel adds nothing at level and a wedge once tilted — so the
score rose with every step and a straight page was rotated the full 15°. The
detector read the rotated page as one photograph: **13 Zones to 1**.
`preprocess._without_panels` takes solid blocks out of the vote. All fifteen
pages read level, old pictures and new; the tilt tests still straighten ±1.5°
and ±4°, with and without a panel. `RECTIFIER_VERSION` 3 → 4.

### The floor re-cut — `031ba3a`, 2026-09-29

Sweep `Q5-10-reshot-sweep`, 486 model calls. The five unchanged originals
came back **byte-identical** to `a3-result` re-derived, but for
`rectifier_version`: the conversion is still deterministic. Vocabulary recall
over fifteen **0.8667 → 0.9708**; `receipt_0010` 0.198 → 0.988 with no change
to the pipeline at all. What fell, and why, is in
[`tests/frozen/reshot/README.md`](../tests/frozen/reshot/README.md) — which
was corrected on 2026-09-30 about `report_0011`, whose fall is the scorer's.

### Q5 — `receipt_0010`, `2d918df`, 2026-09-30, **gate MET, 8 of 8**

**Its premise did not survive measurement.** Enlarging the crop 2.6× changed
no answer. On the truncated picture the receipt collapsed under the table
prompt's grid sentence, "19 rows and **1 columns**" — a wrong count, from
dashed rules and a centred line bridging every gutter — and read every line
with no count at all. On the whole picture its crop no longer holds the
centred line, and it reads every row *with* the count. What was left was
drawing it, and three changes, each measured one apart:

| change | effect |
|---|---|
| `render._table`: a header row stays in place once the table opens with a header; summaries go to `<tfoot>` only when nothing follows them | the receipt's `AID`/`Auth` rows and its `Card`/`Change` lines were drawn out of order. Replayed over the floor: **14 of 15 byte-identical**, receipt tau 0.800 → 1.000, beside 0.871 → 1.000 |
| `probes`: a column-sum totals the DATA rows above the first SUMMARY row; `tools/rederive.py` gains the step | the false "did not reconcile" (4426 — quantities summed with a card number) becomes **26.45 = 26.45** |
| `detector.prefer_container`: a container never takes in a picture | the farewell line, barcode and last three lines were one prose Zone and **the barcode, drawn since A3, was not drawn**. Layout front: exactly the receipt moves, 3 → 5 Zones |

**The gate, written before sweep `Q5-40-sweep` and committed as `d9a0d39`.**
The sweep ran on that commit: 491 model calls, 2h01m, the model 54%/46%
CPU/GPU.

| # | clause | predicted | result |
|---|---|---|---|
| 1 | receipt rows in printed order in the DOM; no `<tfoot>` (replaces its tau and beside, decided 2026-09-29) | holds | **holds** |
| 2 | receipt column-sum reconciles, 26.45 = 26.45 | holds | **holds** |
| 3 | receipt barcode drawn from its pixels; `THANK YOU` and the three lines printed as text | holds | **holds** — one figure Zone with its pixels, one `<img>`, all four lines as text |
| 4 | receipt: no word stops printing, precision does not fall | 0.9877, 0.9903 | **0.9877, 0.9903**, nothing newly vanished |
| 5 | the other fourteen byte-identical to the floor | 14 of 14 | **14 of 14**; the receipt byte-identical to its prediction run, `Q5-30-receipt` |
| 6 | ratchet against `reshot`, four legs, fifteen | holds | **holds**, fifteen of fifteen |
| 7 | visual review, all fifteen, `--previous` the floor's sweep | no `worse` | **none** — fourteen `same`, the receipt `better` |
| 8 | tests, mypy | 833, clean | **833, clean** |

Not ratcheted, and fell: the receipt's `columns_within_tolerance` 0.875 →
0.775 — the farewell, the barcode and the last three lines are now three
blocks, each drawn at the left where the source centres it (`Zone.align`,
deferred).

### Measured and kept: the one-column grid hint

Withholding a grid that measures one column was the first thing Q5 built. On
the re-shot corpus **five of fifteen tables** measure one column where the
page prints two to six. Each was asked again with no count and the floor
replayed with the answers: **`menu_0012` stopped printing 30 words** and
`statement_0006` lost `Castleton`. The count of rows is what the model obeys,
so the hint stays; `config.DEFAULT_TABLE_GRID_HINT` records the measurement,
and `test_a_one_column_count_is_still_stated` pins it.

### The floor and the control frozen, and a fourth loop — 2026-09-30

`tests/frozen/q5-result/` holds `Q5-40-sweep`'s documents, scores and — a
first — its answers; Alessandro made it the floor the same day. **`tools/replay_run.py`** serves a run's or a frozen
directory's answers to today's code through a real Conversion, and with
`--swap` one new answer; it is how the withheld hint was measured. Proved on
the day: 15 of 15 byte-identical from the sweep and again from `q5-result/`;
14 of 15 over the floor's sweep, the receipt flagged as asking what that run
never did. `bakeoff.write_dump` is the dump writer both share.

---

## Next — nothing queued

**Cleared 2026-10-10 by Alessandro**, to restart from a clean end-to-end run.
Q6, Q7 and N5, the live-fault list, Thread 3/C's re-scoping gate and Thread
4/D are all off the list. What they found stays where it was written — the
specs, the handover, this file's history — as record, not as work.

**`debug/runs/F1-sweep/report.html`** is the fresh sweep: commit `12fa2d1`,
shipped defaults, no `DTH_*` set, all fifteen documents. Alessandro reviews
it himself and decides what comes next. **Until he does, start nothing.**

---

## Closed, with evidence — do not reopen without a new kind

All in [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md), except
the last two entries.

- **The column model.** Four renderers measured offline, all worse on the hard
  tier. **Proportional widths** lower `cv_0013` 0.500 → 0.474 while crossing
  the ratchet on `form_0007`. A3's tile sitting in the middle third of an
  equal-column band is this question, not a new one.
- **The merged Zone** — `menu_0012`'s two menu sections as one table,
  `form_0007`'s two-column form as one pairs list. Three pixel-side tests, none
  separates them. **Do not build a fourth**; if reopened it is a *model*
  question asked as "how many regions", and its own phase.
- **`alignment_agreement` as a gate.** Flipping 42 cells moved it 0.935 →
  0.935. Alignment is gated on a count of named columns, in the DOM.
- **Reading direction for a multi-Band column region** is an **IR gap**, not a
  renderer choice: the same merge takes `newsletter_0008` tau 0.832 → 0.968 and
  `catalogue_0015` 0.943 → 0.562.
- **The vision layout pass** — deleted in Q4, 2026-09-29, after Thread 0 took
  it out of every Conversion: it raised `MappingError` on three of the five
  documents it was measured on and matched none, where the detector converts
  all fifteen. If reopened it is a new pass with its own schema and prompt,
  measured against `tools/layout_front.py`'s boxes, not a restoration.
- **Withholding a one-column grid from the table prompt** — Q5, 2026-09-29.
  Five of fifteen tables measure one column; asked with no count and
  replayed, `menu_0012` stops printing 30 words and `statement_0006` loses
  `Castleton`. The model obeys the count of *rows*; the wrong count of
  columns costs less than no count. `config.DEFAULT_TABLE_GRID_HINT` has the
  numbers. If reopened, it is the *column* count that is measured better — a
  gutter test that dashed rules and a centred line cannot bridge — not the
  hint that is withheld.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session counts.
  **The exceptions are committed files:** `tests/frozen/run84/`,
  `a1-checkpoint/`, `a0-checkpoint/`, `a0-result/`, `a1-result/`,
  `a2-result/`, `a3-result/`, `reshot/` — all kept as record — and
  **`q5-result/`, the floor and the control.** `a3-result/` was scored on pictures missing their last
  lines; quote it only as that.
- **The committed corpus picture is a screenshot of its own HTML.**
  `TestTheCorpusPictureIsItsOwnHTML` re-shoots the ten authored pages and
  compares them to the pixel. When a page or the shooter changes, re-shoot
  with `tools/shoot_corpus.py --force` and re-cut the floor on a sweep — the
  scores of a picture that changed are not comparable with anything before it.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the four shipped defaults or the three wire-level row nets** —
  `_without_empty_rows`, `_join_split_header_row`, `_without_repeated_header`.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.**
- **Any reviewed run is a full sweep**, all fifteen documents.
- **Rubric judgements are pairwise and in-session only.**
- **Marking may never change the words.** `wire._runs_for` can only cut the
  string it is given and `ir.Cell.runs` discards Runs that do not spell the text
  back. Two independent checks, and both must stay.
- **What is read off a Graphic is `alt`, never printed.** Printing it is how
  `sparksuite` and `logo` were invented.

## Measured and not shipped — record, not a queue

- **Body type size and Title sizes** — measured in Q3 at the sources' *own*
  sizes; both cross the T1 ratchet on T3 `beside`. `style.py`'s module
  docstring has the table. A Title or body drawn at the wrong size is this,
  not a new fault — `catalogue_0015`'s `OK-330` and `Oak drawer runner`
  included: the first is white type on a dark badge whose line measures above
  1.44em, the second its Zone's *second* heading Block, and only the leading
  one is sized.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/q5-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.**

- **Downstream of the model** — renderer, style, probes. `tools/rederive.py
  tests/frozen/q5-result --label <base>` builds today's baseline; build the
  changed arm the same way with the change in place, score both, and pass the
  baseline as `--previous` to the visual review. **A new downstream step that
  writes the IR must be added to `rederive.py`.** Cannot move anything the
  model decided.
- **Recorded answers through a real Conversion** — `tools/replay_run.py
  tests/frozen/q5-result --label <label>`, committed in Q5 after the loop had
  lived in scratch scripts since 2026-09-22. Everything between an answer and
  the page — wire, mapper, every pass — on the control's own answers, in under
  a minute; `--swap <doc>:<NN>=<answer.json>` serves one new answer. A
  document marked ASKED MORE THAN THE RUN is not a measurement.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
