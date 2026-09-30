# Status — 2026-09-30 (the queue: **N1 done, gate met; `q5-result/` the floor and the control; N2 next**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-09-30, when
N1 of the open-issues queue closed.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **836 tests pass, `mypy src/` clean.**

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
            continued: N1-N4 model-free, then Q6, Q7, N5
              N1 DONE 2026-09-30, offline, gate MET 8 of 8      N2 <- next
Thread 3/C  Repair loop (re-scoped first)
Thread 4/D  Human corrections (unscheduled)
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

### The live faults, worst first

The visual review of `Q5-40-sweep`, all fifteen sheets, is the source for
what follows as much as the scores are; `debug/runs/Q5-40-sweep/_review/`
while it lasts.

**1. `cv_0013`'s sidebar comes apart.** On the whole picture the detector no
longer boxes the dark sidebar as one picture: each item is its own Zone, 31
Zones where the truncated picture gave 13. The skills `Revit` and `Python` are
classified as figures, so their words are `alt` and not printed; the sidebar
interleaves with the main column Band by Band, **tau 0.562**; its labels draw
at h1 size; height **3.20**. The truncated picture hid this.

**2. Side-by-side content stacks or scatters** — beside `form_0007` 0.059,
`catalogue_0015` 0.252, `menu_0012` 0.348, `newsletter_0008` 0.500; and
`darkdeck_0009`'s aside, whose bullets scatter through the main column. A2
established most of it is **inside one Zone**, so no renderer reaches it, and
that reading direction for a multi-Band column region is an IR gap — see
"Closed, with evidence".

**3. Words lost or misread.** `catalogue_0015` keeps 84.3% — its title and
two cards' bodies — and `form_0007` 86.2%, with four of its five section
headings; `darkdeck_0009` loses its aside's two headings. Misreadings the
review would not let pass: **`statement_0006` prints two wrong amounts**,
1,144.30 as 1,141.30 and 216.08 as 210.08; **`nonlatin_0014`'s footer names a
company that does not exist**, `Αγγελίδης Μπραγκαντής Α.Ε.` for `Αιγαίο
Μηχανική Α.Ε.`. Smaller: `form_0007`'s footer (`Castletown` ×2, `ferpost`),
`menu_0012`'s `cheril`, `receipt_0010`'s `A0000000031010` one zero short. A-1
established the pipeline cannot declare loss inside a line. **Do not build a
third detector without a new kind of evidence.**

**4. Doubled text.** `statement_0006` prints `Totals for the period` twice: a
sliver Zone overlaps the transactions table in one Band, which also makes
the snap refuse that document and squeezes the table to about 70% of the
width.
`nonlatin_0014` prints its total `12.437,82` twice. *Not* a fault, though the
numbers call it one: `report_0011`'s precision counts every section and
footnote number as invented, because the source draws them with CSS counters
and `<ol>` markers that `project()` cannot see.

**5. The findings panel reports losses that did not happen — found by the
review; no score sees it.** The false Shortfalls are gone since N1. What is
left: "content nothing read" fires on ink that is not text — `cv_0013`'s dark
sidebar fill, **26.1%** of the page's ink, boxed at the sidebar's full extent
though every item in it was boxed and drawn; `receipt_0010`'s paper edge and
dashed rules, **23.0%**, bounded by the whole page. `shortfall`'s own
docstring names the cost: a finding that fires on correct behaviour is how the
whole list stops being read.

**6. Drawn, though the page does not have it** — found by the review. Yellow
`<mark>` highlights on `cv_0013`'s `native` and `nonlatin_0014`'s `myDATA`
(A1's inline pass; T6 counts marks found, not marks invented, and this is Q7's
`12345` again, where it can be seen). `catalogue_0015`'s `each` squeezed into a
one-letter column in two cards and printed downward, `e / a / c / h`.

**7. Height.** `cv_0013` 3.20, `menu_0012` 2.57, `receipt_0010` 2.26,
`statement_0006` 2.05, `newsletter_0008` 2.01. **Body type is 16px on every
page** where the sources set 9–16px — deferred with Q3's evidence.

---

## What the last step shipped

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

## Next — the rest of the queue, re-measured on the whole pictures

The ready prompt is [`specs/0007-handover.md`](specs/0007-handover.md), "The
open-issues queue, continued — Q6, Q7 and what the whole pictures showed".
**Each gate is still agreed with Alessandro before any code.** Cheapest
first — the first four need no model. **N1 is done**, above.

**N2 — next. "Content nothing read" on ink that is not text** — `cv_0013`'s sidebar
fill, `receipt_0010`'s paper edge and rules (live fault 5).
`preprocess._without_panels` already takes solid blocks out of the deskew
vote; whether the same cut belongs in `uncovered_regions` is the question.
Both documents' honesty accounts cite those findings today, as N1's two
did, so measure the tally before and after.

**N3. `statement_0006`'s sliver Zone** — `Totals for the period` boxed on its
own at 0.042–0.170 across, 0.927–0.935 down, inside the table's box, so the
line prints twice, the snap is refused and the table is squeezed. A layout
question, measurable with `tools/layout_front.py` for nothing.

**N4. `catalogue_0015`'s `each`, one letter to a line** — a renderer
question, measurable by re-rendering the control.

**Q6. `nonlatin_0014` — its premise is gone.** On the whole picture the
full-width Zone that re-read three pairs no longer exists: the title Zone
stops at 0.377 across, `ΑΦΜ` and `ΔΟΥ` are no longer doubled, and `ΤΠΥ =
2026/0417` is read in its own box. What is left is the total `12.437,82`
printed twice — the table prompt asks for 10 rows where the page prints 9,
the Title's band counted as a row, and the model pads the tenth by repeating
the total, the padding `wire._without_repeated_header` already drops when it
is a header — and the misread Greek, the invented footer name among it.

**Q7. `invoice_0001`'s `Invoice` / `#: 123`, and the false marks** — A1's
`12345`, and now `cv_0013`'s `native` and `nonlatin_0014`'s `myDATA`, drawn
as yellow highlights. Model questions; probe the crop, then `--swap` the
answer into a replay of the control before spending a sweep.

**N5. `cv_0013`'s split sidebar** — its skills read as figures, and its
reading order, which is the IR gap below. Say which part is which before
building.

**After the queue:** the next floor decision, then Thread 3/C's re-scoping
gate.
Thread 4/D stays unscheduled.

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

## Deferred deliberately — not new faults

- **Body type size and Title sizes** — measured in Q3 at the sources' *own*
  sizes and both cross the T1 ratchet on T3 `beside`. Reopening is a scorer
  question about `beside`'s half-overlap test, or waits on the content-losing
  documents; not an estimator question. `style.py`'s module docstring has the
  table. Until then a Title or body drawn at the wrong size is this, not new.
- **`catalogue_0015`'s `OK-330` and `Oak drawer runner`** stay at `h1` size.
  `OK-330` is white type on a dark badge and its line measures the badge's
  height, above 1.44em, so the rule leaves it; `Oak drawer runner` is its
  Zone's *second* heading Block, and only the leading one is sized.
- **Thread 3/C** stays gated on its re-scoping classification. The conversion
  is deterministic, so a loop re-reading the same crop gets the identical wrong
  answer back.

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
