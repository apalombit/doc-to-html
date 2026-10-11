# Status — 2026-10-11 (**spec 0009 under way, issue #32**; the floor is `s3-result/`)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-11, at
spec 0009's step 0, which froze `S3-sweep` as the floor.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **860 tests pass, `mypy src/` clean.**

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
              D       page width (+ separators), rederive         <- D next
              E       one sweep
```

Q1-Q4's result tables moved to
[`specs/0007-handover.md`](specs/0007-handover.md), "Outcome — Q1 to Q4".

---

## The floor — `tests/frozen/s3-result/`, DECIDED 2026-10-11

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s3-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five and says nothing about the other ten.

**It is the floor and the control since 2026-10-11, Alessandro's decision**
after reviewing sweep `S3-sweep` — spec 0008's outcome, commit `9c42d81`:
the fifteen documents today's code makes, with the 490 answers that made
them. Frozen at spec 0009's step 0 and proved that day: scored straight out
of the directory, **15 documents, 0 differing fields**; `tools/rederive.py`
over it reproduces it **15 of 15 byte for byte**, and so does
`tools/replay_run.py` from its committed `answers/`; `tools/layout_front.py`'s
Zones match its IRs on 15 of 15. `debug/runs/S3-base` is the rederive proof
kept as a run directory — the `--previous` for spec 0009's sheets.

**Three legs sit below `q5-result/`, the floor before it, by that decision:**
T3 beside on `cv_0013` (0.5769 → 0.4000) and `darkdeck_0009` (0.9677 →
0.8148) — the Band render's cross-column coincidences, which a column render
does not reproduce — and precision on `catalogue_0015` (1.0000 → 0.9940), one
`×` read as `x` on a spec line printed for the first time. Its README names
them and what else moved. **N4's exception is gone:** `catalogue_0015`'s
beside is 0.2727, above `q5-result/`'s 0.2523.

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

`vocabulary_recall` is reported beside a failure to say how far it fell. **The
floor never falls for any reason.** No standing exception sits against
`s3-result/`.

---

## Where the corpus is — at the floor, `s3-result/`

| | mean |
|---|---|
| vocabulary recall | 0.9806 |
| recall (multiset) | 0.9779 |
| precision | 0.9866 |
| join recall | 0.9538 |
| tau | 0.9864 |
| beside agreement | 0.7549 |
| height ratio | 1.441 |
| `hard_breaks` | 5 |
| `figures_lost` | **0** |
| T6 inline runs | 8 of 42 |

### The live faults — cleared 2026-10-10

The list drawn from `Q5-40-sweep`'s review was cleared with the queue. The
next one comes from Alessandro's own review of `F1-sweep`.

---

## What the last step shipped

### Spec 0009 step C — the detector's own sections, 2026-10-11, gate MET offline

`form_0007`'s one `form` box is cut at the section headings heron found
inside it — five Zones, one per printed section, each opening on its heading
— skipping a heading inside a drawn field (the address value, which heron
also calls `section_header`). `menu_0012`'s one `document_index` is split
into the two columns heron also proposed, side by side in one Band, each with
its heading. Scoped to `form` and `document_index`; fires on those two pages
only. Spec, "Outcome — step C".

### Spec 0009 step B — cut at a grid's lane splits, 2026-10-11, gate MET offline

`structure.cut_at_edges` also cuts a box a grid holds at the grid's splits:
`darkdeck_0009`'s one box over four metric tiles becomes four Zones, one per
lane, each crop holding its whole tile. Layout front: 14 others identical.
Its crops moved, so the replay asks more there and step E's sweep measures
it. Spec, "Outcome — step B".

### Spec 0009 step A — two wire row nets, 2026-10-11, gate MET

`nonlatin_0014`'s totals: a summary row padded on the left loses its leading
empty cells to the header's width (`wire._trimmed_to_header`), and a summary
repeating the one above it goes (`wire._without_repeated_total`). By replay:
the grand total sits under `ΦΠΑ 24%`, `12.437,82` prints once, precision
0.9510 → 0.9652, the other 14 byte-identical. `wire.retrimmed` brings old IRs
up to it in `rederive.py`. Spec, "Outcome — step A".

### Spec 0009 step 0 — `S3-sweep` frozen as the floor, 2026-10-11

`tests/frozen/s3-result/`: the sweep's fifteen documents, its scores against
`q5-result/`, its 490 answers and its (empty) `dth_env.txt`. All four loops
reproduce it 15 of 15 — scored (0 differing fields), rederive, replay, layout
front. The floor is named as `s3-result/` in CLAUDE.md, here and in
`tools/replay_run.py`'s usage. `tests/test_structure.py` stays on
`q5-result/`'s boxes: repointed, its catalogue-title test fails, because that
title is already cut out in `s3-result/`. Its README has the table of what
moved against `q5-result/` — seven documents, three of them by N1–N4.

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

## Next — spec 0009, step D

**The only open work is
[`specs/0009-four-repairs-one-sweep.md`](specs/0009-four-repairs-one-sweep.md)**,
issue #32 — it carries spec 0008's changes, the S3-sweep analysis by
conversion stage, and the plan with every gate registered:

```
0  freeze S3-sweep as tests/frozen/s3-result/, move the floor   DONE
A  wire row nets — nonlatin_0014's totals                        offline, replay   DONE
B  cut at a grid's inner splits — darkdeck_0009's tiles          layout front      DONE
C  the detector's own sections — form_0007, menu_0012            layout front      DONE
D  a photographed page at its paper's width — receipt_0010       offline, rederive <- next
   (+ drawn separators, one optional attempt)
E  one sweep, S4-sweep, about 1½ hours, report against s3-result/
```

The menu's richer layout spec is deferred unless step C's stop rule fires.

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
  `a2-result/`, `a3-result/`, `reshot/`, `q5-result/` — all kept as record —
  and **`s3-result/`, the floor and the control.** `a3-result/` was scored on pictures missing their last
  lines; quote it only as that.
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
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~1¾ h — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~20 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s3-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from `tests/frozen/s3-result/`,
which today's code reproduces 15 of 15 on all three loops (2026-10-11);
`debug/runs/S3-base` is its rederive, kept as a run directory. Both tools
take a run directory as well as a frozen one.

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
