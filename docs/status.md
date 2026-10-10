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

### Before N4

N1–N3 and the Q5-era records — the corpus pictures re-shot whole, deskew on
type alone, the floor re-cut, Q5, the one-column grid hint, the floor and the
control frozen — moved on 2026-10-10 to
[`specs/0007-handover.md`](specs/0007-handover.md), "Outcome — N1 to N3, and
the Q5-era records", verbatim. Q1–Q4's are under "Outcome — Q1 to Q4".

---

## Next — nothing queued

**Cleared 2026-10-10 by Alessandro**, to restart from a clean end-to-end run.
Q6, Q7 and N5, the live-fault list, Thread 3/C's re-scoping gate and Thread
4/D are all off the list. What they found stays where it was written — the
specs, the handover, this file's history — as record, not as work.

**`debug/runs/F1-sweep/report.html`** is the fresh sweep: commit `12fa2d1`,
shipped defaults, no `DTH_*` set, all fifteen documents. Alessandro reviews
it himself and decides what comes next. **Until he does, start nothing.**

What it measured, 2026-10-10, scored against the floor — facts, not a review:

- **15 of 15 converted**, 488 model calls, 1h43m.
- **Byte-identical, 15 of 15, to the offline prediction** — `rederive.py`
  over N3's replay with N4's renderer. The offline loops predicted the sweep
  exactly.
- **The ratchet names only the recorded exception**, `catalogue_0015` T3
  beside. The report's "Phase A-1" lines are the standing honesty tally the
  floor also carries.
- Corpus means against the floor: vocabulary recall, recall, join recall and
  tau unchanged (0.9708, 0.9664, 0.9434, 0.9366); precision 0.9865 → 0.9870;
  beside 0.7622 → 0.7611; height 1.621 → 1.549. Seven documents moved, each
  by one of N1–N4 — findings panels, `statement_0006`'s sliver, catalogue's
  cards.

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
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~1¾ h — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~20 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/q5-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from a fresh sweep such as
`debug/runs/F1-sweep`, not from `q5-result/`: N1–N4 changed what today's code
makes from the floor's answers, and `rederive.py` cannot re-apply N3's
detector change. Both tools take a run directory as well as a frozen one.

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
