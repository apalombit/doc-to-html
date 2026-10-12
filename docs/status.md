# Status — 2026-10-12 (**spec 0011 under way — the baseline is `tests/frozen/s5-result/`, and steps are judged by eye**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-12, after
Alessandro took `S5-sweep` as the baseline and asked for spec 0011; step 0
froze it the same day.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **996 tests pass, `mypy src/` clean.**

**How work is judged now — Alessandro, 2026-10-12, for spec 0011.** By eye:
every step's sheets are opened against the previous step's and each page
judged better / same / worse. Scores are still produced and recorded, and
**never gate a step or carry an argument**. The ratchet below is suspended
as a gate for the spec. The one number still read is the report's `vanished`
list, as a pointer to a page to look at. He checks every run himself too.

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
              Fresh sweep F1-sweep, commit 12fa2d1, shipped defaults.
Spec 0008   Page structure, opened 2026-10-10 from the F1-sweep review
              step 1  structure from pixels, offline          DONE, gate MET
              step 2  carry it in the IR and draw it, offline DONE, gate NOT met (ratchet)
              step 3  let it shape the boxes, one sweep       DONE, gate NOT met (ratchet, menu)
              sweep S3-sweep, commit 9c42d81 — DECIDED 2026-10-11: the new floor
Spec 0009   Four repairs after the structure step, one sweep — issue #32
              step 0  freeze S3-sweep as tests/frozen/s3-result/  DONE, gate MET
              A       wire row nets, nonlatin_0014, replay        DONE, gate MET
              B       cut at a grid's lane splits, darkdeck_0009  DONE offline, gate MET
              C       the detector's own sections, form + menu    DONE offline, gate MET
              D       4a page width DROPPED (gate failed); 4b separators DONE
              E       sweep S4-sweep, commit b80b7f0               DONE, gate NOT met
                      (ratchet: darkdeck_0009, menu_0012) — its floor decision
                      folded into spec 0010's
Spec 0010   Five repairs, the beside score, type at the page's size — issue #33
              0+A     vetoed caption kept, title echo keeps a value  DONE, gate MET (one exception)
              B       grid drawn as a grid, two Probes, polarity     DONE, gate MET
              C       beside by row groups                  measured and REVERTED
              D       body, Titles, headings at the page's size  DONE, D-1 NOT met (two pairs)
              E       sweep S5-sweep, commit 4a5fe3f        DONE, prediction held;
                      ratchet NOT met on five documents
                      DECIDED 2026-10-12: S5-sweep is the baseline, the five legs accepted
Spec 0011   Place every entry where the page puts it — issue #34, planned 2026-10-12
              0  freeze S5-sweep as tests/frozen/s5-result/   DONE, both loops 15 of 15
              1  rhythm: gaps from the page, Zones grouped, alignment   DONE, none worse
              2  locate every entry on the page   DONE, no page changed
              3  fields: boxes, ticks, digit boxes, underlines   DONE, the form better
              4  lines: per-entry type, colour, rules, leaders, spacing
                 4a size, weight, italic   DONE, eleven pages better
                 4b colour and chips   DONE, thirteen pages better
                 4c lines and fills between table rows   DONE, six pages better
                 4d leader dots   DONE, the menu better
                 4e spacing inside a Zone   DONE, eleven pages better
                 4f typeface class, optional   <- next
              5  one sweep, S6-sweep
```

Q1-Q4's result tables moved to
[`specs/0007-handover.md`](specs/0007-handover.md), "Outcome — Q1 to Q4".

---

## The baseline — `tests/frozen/s5-result/`, DECIDED 2026-10-12

Sweep `S5-sweep`, commit `4a5fe3f` — spec 0010's sweep, all fifteen
documents, 518 answers, frozen at spec 0011's step 0 with its documents,
scores, answers and `dth_env.txt`. Proved the day it was frozen:
`tools/rederive.py` over it **15 of 15 byte-identical**, `tools/replay_run.py`
from its answers **15 of 15 byte-identical**, and the rederive scored **15
documents, 0 differing fields** against its `scores.json`. Its README has
what moved against `s3-result/`.

It sits below `s3-result/`, the floor before it, on five legs, all accepted
by that decision:
- `darkdeck_0009` tau and beside — its P95 tile is read as a table;
- `menu_0012` — `béarnaise` read without its accent;
- `report_0011` precision — one `1` counted as surplus;
- `newsletter_0008` and `nonlatin_0014` beside — one coincidental pair each.

Spec 0010's "Outcome — step E", §5, has the table.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s5-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### `s3-result/` — the floor 2026-10-11 to 2026-10-12

Spec 0008's sweep `S3-sweep`, commit `9c42d81`, 490 answers. Frozen at spec
0009's step 0, and reproduced 15 of 15 by every loop. Three of its legs sat
below `q5-result/` by Alessandro's decision. Its README names them.

### The ones before it

`q5-result/` (2026-09-30 to 2026-10-11) dominated `reshot/` on every
ratcheted leg; `reshot/` (2026-09-29 to 2026-09-30) is the one move that gave
ground *before* it was taken, because it corrected the pictures rather than
the pipeline. Each README says what moved and why.

### What the ratchet enforces, per document

`report._ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside a failure to say how far it fell.
**For spec 0011 the ratchet is reported and does not gate** — see "How work
is judged now" above.

---

## Where the corpus is — at the baseline, `S5-sweep` (recorded, not a target)

| | mean |
|---|---|
| vocabulary recall | 0.9876 |
| recall (multiset) | 0.9860 |
| precision | 0.9881 |
| join recall | 0.9599 |
| tau | 0.9875 |
| beside agreement | 0.7638 |
| height ratio | 1.241 |
| `hard_breaks` | 5 |
| `figures_lost` | **0** |
| T6 inline runs | 8 of 42 |

### The live faults — cleared 2026-10-10

The list drawn from `Q5-40-sweep`'s review was cleared with the queue. The
next one comes from Alessandro's own review of `F1-sweep`.

---

## What the last step shipped

### Spec 0010 — five repairs, the beside score, type at the page's size, `S5-sweep`, 2026-10-11 — ratchet NOT met on five documents

**The pages.** Every page sets its body at about the source's size, and its
mastheads and titles at their printed sizes. The pages are about a sixth
shorter (mean height 1.435× → 1.241×). `darkdeck_0009` is complete again,
with `$2.14`, `OPEN RISKS` and `DECISIONS WANTED` back, and its four tiles
stand four across. `form_0007` heads all five sections. `report_0011`'s
table carries its caption. `statement_0006` opens by naming the two amounts
it misread. `cv_0013`'s sidebar labels are small capitals again. Of the
fifteen sheets against `S4-sweep`, 13 are better, 2 the same and none worse.

**What shipped, by step** (spec 0010, an "Outcome" section per step):

- **A** — a caption the grid veto refused, which the reading then drops,
  becomes the Zone's Title (`Orchestrator._restore_vetoed_captions`). The
  title-echo rule keeps a pair's value when only its label repeats the
  Title.
- **B** — a `grid` region is drawn as a CSS grid, in reading order. Two
  Probes, detection only: a running balance names the rows where it breaks,
  and a column within 1% of a stated total is reported. Type is measured in
  its Zone's own polarity, on `Rectified.plain`.
- **C** — T3 `beside` by row groups was measured and **reverted**. A
  source's row groups are fragments, not column stretches.
- **D** — `Style.body_px` is 1.33 × the width-weighted median glyph height.
  `Zone.title_size` is the printed size, and heading Blocks are sized both
  ways. `tools/remeasure_style.py` measures all three.

**The prediction held:** the sweep asked the questions `S4-sweep` asked, and
its documents are byte-identical to `S5-D3-replay`, 15 of 15, with every
one of its 518 answers byte-identical to `S4-sweep`'s. 1h44m, 40%/60%
CPU/GPU.

**The ratchet against `s3-result/` falls on five documents.** None of them
is content lost by this spec:

| document | leg | floor → `S5-sweep` | cause |
|---|---|---|---|
| `darkdeck_0009` | tau, beside | 0.9805 → 0.9192, 0.8148 → 0.6579 | the P95 tile read as a table; the scorer pairs its `P95` and `184 ms` with the component table's |
| `menu_0012` | vocabulary, precision | 0.9922 → 0.9844, 0.9938 → 0.9877 | `béarnaise` read without its accent (spec 0009's crop) |
| `report_0011` | precision | 0.9679 → 0.9663 | the caption's `1`, counted surplus against `<ol>` footnote numbers |
| `newsletter_0008` | beside | 0.7000 → 0.6500 | one coincidental pair across two columns |
| `nonlatin_0014` | beside | 1.0000 → 0.9853 | one coincidental pair across two columns |

Corpus means, `s3-result/` → `S5-sweep`: vocabulary 0.9806 → 0.9876,
precision 0.9866 → 0.9881, join recall 0.9538 → 0.9599, tau 0.9864 →
0.9875, beside 0.7549 → 0.7638, height 1.4405 → 1.2405.

### Spec 0009 — four repairs, one sweep, `S4-sweep`, 2026-10-11 — final gate NOT met

**The pages.** `menu_0012` reads down two columns under their own headings
(tau 0.923 → 0.994). `form_0007` is cut into five sections at the headings
the detector found. `nonlatin_0014`'s grand total lines up and prints once.
Eleven pages draw their sources' rules (`Document.separators`).
`darkdeck_0009`'s tile box is cut at the grid's splits. It fell below the
floor at that sweep, and spec 0010 repaired it. Two wire row nets came in:
`_trimmed_to_header` and `_without_repeated_total`. The receipt's paper
width was dropped on a failed gate. Spec 0009 has an "Outcome" per step.

**The lesson it repeats.** As first committed, the separator pass ran before
any Zone had a Kind, so its table-border test saw no tables. A stage's
position is as much a way for a feature not to arrive as an unread flag.

### Spec 0008 — the page's structure, steps 1-3, 2026-10-10, sweep `S3-sweep`

**What it built.** `structure.structure()` reads the page's regions off its
pixels and its boxes — `single`, `columns` (lanes read down) or `grid`
(identical drawn boxes read across). `Document.regions` carries them; the
renderer draws a `columns` region as lanes side by side, each read top to
bottom, a lane painted with its Zones' common fill. A Zone crossing a grid's or
a column region's edge is cut there, and a grid's copies take the Kind most of
them were given. The spec's three "Outcome" sections have every table.

**What it fixed, sweep `S3-sweep` against F1-sweep:**

| document | what changed | tau | other |
|---|---|---|---|
| `cv_0013` | sidebar one dark strip beside the CV, read down | 0.56 → **0.98** | height 2.98 → 1.96 |
| `darkdeck_0009` | the risks panel one column beside the main text | 0.86 → **0.98** | height 1.68 → 1.32 |
| `newsletter_0008` | three columns read down | 0.86 → **1.00** | beside 0.50 → 0.70 |
| `catalogue_0015` | title printed; nine cards a 3×3 grid, all `pairs` | 0.94 → **1.00** | vocabulary recall 0.84 → **0.99**, 29 words back |

Eleven documents render pixel-identical to F1-sweep, `menu_0012` among them.
The offline loops predicted the sweep byte for byte on 14 of 15; the fifteenth
was the one whose crops changed.

**Where it falls short — the decision.** The ratchet against `q5-result/`
fails on three legs: T3 beside on `cv_0013` (0.5769 → 0.4000) and
`darkdeck_0009` (0.9677 → 0.8148), and `catalogue_0015` precision (1.000 →
0.994, one `×` read as `x` on a spec line that was not printed at all before).
The beside falls are the Band render's cross-column coincidences, which a
column render does not reproduce; both renders that keep them were built and
measured, and look less like the page (spec, "Outcome — step 2").
`catalogue_0015`'s beside rises to 0.2727, above the floor, so N4's recorded
exception no longer applies. **`menu_0012` is unchanged**: neither the pixels
nor a closed model question, probed in two shapes on twenty crops, tells its
columns from a table (spec, "Outcome — step 3").

Corpus means, `q5-result/` → `S3-sweep`: vocabulary recall 0.9708 → 0.9806, recall
0.9664 → 0.9779, precision 0.9865 → 0.9866, join recall 0.9434 → 0.9538,
tau 0.9366 → **0.9864**, beside 0.7622 → 0.7549, height 1.621 → 1.441.

### Before it — N4 — a label with no value spans the row, `12fa2d1`, 2026-10-10, **gate NOT met on clause 3; shipped on Alessandro's decision**

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

### Before N4

N1–N3 and the Q5-era records — the corpus pictures re-shot whole, deskew on
type alone, the floor re-cut, Q5, the one-column grid hint, the floor and the
control frozen — moved on 2026-10-10 to
[`specs/0007-handover.md`](specs/0007-handover.md), "Outcome — N1 to N3, and
the Q5-era records", verbatim. Q1–Q4's are under "Outcome — Q1 to Q4".

---

## Next — spec 0011, step 4f, then the sweep

[`specs/0011-place-every-entry.md`](specs/0011-place-every-entry.md), issue
#34, and its handover prompt. **The common cause behind every fault
Alessandro named in `S5-sweep`:** the IR knows where every Zone sits and
nothing about where anything inside one sits (`Cell.bbox` is never set). The
renderer also puts one fixed 1.75rem gap between any two Zones. So the
following are all drawn in the house style:
- the form's two-column field grid, its boxes, ticks and digit boxes;
- the newsletter's paragraph spacing and darkdeck's risks card;
- the receipt's dashed rules;
- the menu's centred heads and italic notes.

The spec draws the page's own gaps and alignment (probed offline, and it
works), locates every entry with tesseract as a locator only, then draws
fields and per-line looks from it. There are no model calls until the
closing sweep.

**Steps 1 to 3 are done.** Step 1 draws the page's gaps, Continuations
and alignment; no page got worse. Step 2 sets `Cell.bbox` on 847 of 868
Cells and changes no page; its misses are named in the spec. Step 3 draws
`form_0007` as its fields — grid, boxes, comb, ticks, rules, signature
lines — and moves no other page. Step 4 measures each placed entry's own
look, each sub-step its own commit and sheets. **4a is done**: each Cell's
size, weight and slant, from its own ink (`looks.py`, `Cell.look`), drawn
on eleven pages better and none worse — weight unread on the photographed
receipt. **4b is done**: each Cell's ink and any chip it is printed on,
drawn where it differs from its element's own colour — thirteen pages
better, none worse; `Style.ink` is mis-measured on form, nonlatin and cv,
so their Titles keep the wrong ink. **4c is done for tables**: the line
under each row and its fill — the receipt's dashed rules, the menu with
none, the statement's stripes. **4d is done**: the menu's dots from each
dish toward its price. **4e is done**: rows, paragraphs and items stand as
far apart as the page sets them — eleven pages better, none worse; pairs
are not spaced yet. Next is 4f, the typeface class, optional and stopped if
not clearly right; then step 5, one sweep.

---

## Closed, with evidence — do not reopen without a new kind

All in [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md), except
the last two entries.

- **The column model.** Four renderers measured offline, all worse on the hard
  tier. **Proportional widths** lower `cv_0013` 0.500 → 0.474 while crossing
  the ratchet on `form_0007`. A3's tile sitting in the middle third of an
  equal-column band is this question, not a new one. **Reopened by spec 0008,
  2026-10-10, with the IR changed first, and built** — lanes drawn only for a
  `columns` region, whose widths are the page's.
- **The merged Zone** — `menu_0012`'s two menu sections as one table,
  `form_0007`'s two-column form as one pairs list. Three pixel-side tests, none
  separates them. **Do not build a fourth**; if reopened it is a *model*
  question asked as "how many regions", and its own phase. **Reopened by spec
  0008 at the page level, and the model question asked, 2026-10-10: it does
  not separate either.** On twenty Zones with a wide interior gutter, "how many
  columns, read down or across" got `down` 20 of 20, and "one item or separate
  items" got `one_item` 20 of 20 — the menu included, its two dish names
  copied correctly. A third shape needs a new kind of evidence.
- **`alignment_agreement` as a gate.** Flipping 42 cells moved it 0.935 →
  0.935. Alignment is gated on a count of named columns, in the DOM.
- **Reading direction for a multi-Band column region** is an **IR gap**, not a
  renderer choice — **spec 0008 is the work that fills it**: the same merge takes `newsletter_0008` tau 0.832 → 0.968 and
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
  `a2-result/`, `a3-result/`, `reshot/`, `q5-result/`, `s3-result/` — all
  kept as record — and **`s5-result/`, the baseline** since spec 0011's
  step 0. `a3-result/` was scored on pictures missing their last lines;
  quote it only as that.
- **The committed corpus picture is a screenshot of its own HTML.**
  `TestTheCorpusPictureIsItsOwnHTML` re-shoots the ten authored pages and
  compares them to the pixel. When a page or the shooter changes, re-shoot
  with `tools/shoot_corpus.py --force` and re-cut the floor on a sweep — the
  scores of a picture that changed are not comparable with anything before it.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the four shipped defaults or the five wire-level row nets** —
  `_without_empty_rows`, `_join_split_header_row`, `_without_repeated_header`,
  and since spec 0009 `_trimmed_to_header` and `_without_repeated_total`.
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

- **T3 `beside` by row groups** — spec 0010 step C, 2026-10-11. The
  half-overlap relation's connected components, meant to forgive vertical
  drift within a stretch of columns. A source's groups are fragments, not
  column stretches, so it forgave nothing it was built for. A drift-tolerant
  `beside` needs the page's own stretches; that is a scorer design question.
- **Type at the page's size shipped in spec 0010** (step D), crossing
  `beside` by one coincidental pair on two documents. Q3's oracle arm is
  recorded in `style.py`'s module docstring.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~1¾ h — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~20 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s5-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline,
`tests/frozen/s5-result/`. On 2026-10-12 both `tools/rederive.py` and
`tools/replay_run.py` over it reproduced it byte for byte. Both tools take a
run directory as well as a frozen one.

- **Downstream of the model** — renderer, style, probes. `tools/rederive.py
  <run> --label <base>` builds today's baseline; build the
  changed arm the same way with the change in place, score both, and pass the
  baseline as `--previous` to the visual review. **A new downstream step that
  writes the IR must be added to `rederive.py`.** Cannot move anything the
  model decided.
- **Recorded answers through a real Conversion** — `tools/replay_run.py
  <run> --label <label>`, committed in Q5 after the loop had
  lived in scratch scripts since 2026-09-22. Everything between an answer and
  the page — wire, mapper, every pass — on the control's own answers, in under
  a minute; `--swap <doc>:<NN>=<answer.json>` serves one new answer. A
  document marked ASKED MORE THAN THE RUN is not a measurement.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
