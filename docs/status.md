# Status — 2026-10-14 (**the baseline is `tests/frozen/s8-result/`; spec 0013 planned, not started — the only open work**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-14,
after Alessandro took `S8-sweep` as the baseline and cleared every other
open item.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file, then
[`specs/0013-five-repairs-after-s8.md`](specs/0013-five-repairs-after-s8.md),
the only open work. If you are going to look at output — and you should —
use the **`visual-review` skill**.

Branch `scaffold`. **1114 tests pass (1 skipped), `mypy src/` clean** — at
`ba0c110`'s code, 2026-10-14.

**How work is judged — Alessandro, 2026-10-12, for spec 0011; carried
over by specs 0012 and 0013.** By eye: every step's sheets are opened
against the previous step's and each page judged better / same / worse.
Scores are produced and recorded, and **never gate a step or carry an
argument**. The ratchet below is reported, not a gate. The one number still
read is the report's `vanished` list, as a pointer to a page to look at.
The six held-out pages are reported in their own lines. He checks every
run himself too.

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
Queue       Open issues 1-3, Q1-Q5, N1-N4       DONE 2026-09-26 to 2026-10-10
Reset       2026-10-10, Alessandro: every open task and idea cleared.
Spec 0008   Page structure — issue #31          DONE; S3-sweep the floor 2026-10-11
Spec 0009   Four repairs, one sweep — issue #32 DONE; folded into 0010's decision
Spec 0010   Five repairs, type at the page's size — issue #33
              DONE; S5-sweep the baseline 2026-10-12
Spec 0011   Place every entry where the page puts it — issue #34
              DONE; S6-sweep the baseline 2026-10-13
Corpus      Six held-out documents added 2026-10-13, fifteen kept
              DONE; S7-sweep over all 21 the baseline 2026-10-13
Spec 0012   Draw what the page draws — issue #35
              G1-G9, step U, sweep S8-sweep on ba0c110: 18 pages better, 3 worse
              DECIDED 2026-10-14: S8-sweep the baseline, frozen as s8-result/
Reset       2026-10-14, Alessandro: everything not in spec 0013 cleared —
              spec 0012 §7's list, the faults on S8-sweep's sheets 0013
              does not name, every earlier queue and idea.
Spec 0013   Five repairs after S8 — issue #36, planned 2026-10-14
              1 column count only where ruled   2 the caption row at the wire
              3 type on a drawn fill keeps its colour   4 certificate's groups
              5 pricing's cards — then ONE sweep, S9-sweep. NOT STARTED
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s8-result/`, DECIDED 2026-10-14

**Twenty-one documents, 725 answers.** Sweep `S8-sweep`, commit `ba0c110`
(spec 0012 step U), 2026-10-14 00:49–03:00 (**2h12m**), shipped defaults.
Taken by Alessandro after review: against `s7-result/`, eighteen pages
better and three worse — receipt, statement, certificate — each traced in
spec 0012's "Outcome — the sweep" and repaired by spec 0013.

Proved the day it was frozen, at `ba0c110`'s code:
- `tools/replay_run.py tests/frozen/s8-result`: **21 of 21 byte-identical,
  0 asked differently**.
- `tools/rederive.py` over it: **21 of 21 byte-identical files** — the
  `form_0007` field that differed at `s7-result/` no longer does.
- the rederive scored against `s7-result/`: **21 documents, 0 differing
  fields**.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The baselines before it

- **`s7-result/`** — the first sweep over twenty-one, `S7-sweep`. The
  baseline 2026-10-13 to 2026-10-14. Four of its table answers are spec
  0013 step 1's target.
- **`s6-result/`**, **`s5-result/`**, **`s3-result/`**, **`q5-result/`**,
  **`reshot/`** and the A-phase directories — each README says what it is
  and why its floor moved.

### What the ratchet reports, per document

`report._ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

**Reported, not a gate**, while work is judged by eye.

---

## Where the corpus is — at the baseline, recorded, not a target

Means over `s8-result/`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.984 | 0.982 | 0.989 |
| precision | 0.988 | 0.988 | 0.990 |
| join recall | 0.950 | 0.950 | 0.949 |
| tau | 0.968 | 0.990 | 0.912 |
| beside agreement | 0.802 | 0.843 | 0.700 |
| height ratio | 1.100 | 1.029 | 1.276 |
| alignment agreement | 0.796 | 0.833 | 0.705 |
| scale error | 0.200 | 0.129 | 0.378 |

**`vanished`: 40 words.** Spec 0013 names the ones it repairs: the
receipt's eight prices, the statement's `castleton` and cv's `2022`, all
from step U's column count.

---

## What the last work shipped

### Spec 0012 — draw what the page draws, `S8-sweep`, 2026-10-14

**The pages, against `s7-result/`: eighteen better, three worse.**

- **Better, the six:** the timetable's lesson rows and every room line
  back; pricing's three cards as three lanes, the middle one whole; the
  ticket's stub beside the pass; paper's title once, small capitals,
  justification and its equation; the letter's green rule and script
  signature.
- **Better, the fifteen:** no findings card on any page; highlights only
  where the page draws one; the rules, side bars, frames, hatches and
  fills each page draws; tiles one height; each page at its own width; the
  receipt and the ticket at their paper's share; entries aligned from
  their boxes; small capitals and script.
- **Worse:**
  - `receipt_0010` lost its price column;
  - `statement_0006`'s header row is drawn in its band's own colour;
  - `certificate_0021`'s signature row is one boxed paragraph and its name
    a three-line heading.

What shipped:
- G1–G9 are downstream of the model, each measured offline and judged by
  eye in its turn.
- Step U is upstream:
  - the grid and the printed lines counted with the page's drawing known;
  - a frame is not a sheet;
  - a dashed vertical rule makes a lane;
  - an emphasised copy is still a copy, and no grid split crosses a drawn
    box.

§6's prediction held:
- 636 calls asked the same, every answer byte-identical;
- the calls asked differently, exactly the registered ones.

### Earlier

Specs 0008–0011 and the corpus widening: each spec's "Outcome" sections,
and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — spec 0013, the only open work

[`specs/0013-five-repairs-after-s8.md`](specs/0013-five-repairs-after-s8.md),
issue #36, planned 2026-10-14. Five repairs, each traced to its cause at
`s8-result/` with its prediction written down, then one sweep:

1. **The column count only where the table draws its columns.** Of the
   seven tables step U re-counted, only the timetable's columns come from
   drawn rules. The four that undercount the page were obeyed by dropping
   or merging a column.
   - Measurable with no model for receipt, statement, cv and nonlatin:
     their prompts return to `s7-result/`'s, and its answers are swapped
     in.
   - Paper's new count is answered at the sweep.
2. **A table row spelling its Zone's Title goes**, at the wire: paper's
   caption printed twice.
3. **Type on a drawn fill keeps its colour** (`looks._drawn_ground`): the
   statement's header.
4. **The certificate's groups on the unwarped page**: the layout front,
   traced stage by stage.
5. **Pricing's cards as cards**: lanes as framed stacks, Team's frame, a
   price line in two sizes.

Then `S9-sweep` over all 21. Its handover prompt is the one to start from.
**Nothing else is open:** Alessandro cleared every other item on
2026-10-14.

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
  `a2-result/`, `a3-result/`, `reshot/`, `q5-result/`, `s3-result/`,
  `s5-result/`, `s6-result/`, `s7-result/` — all kept as record — and
  **`s8-result/`, the baseline** since 2026-10-14, twenty-one documents. `a3-result/` was scored on pictures missing their last lines;
  quote it only as that.
- **The committed corpus picture is a screenshot of its own HTML.**
  `TestTheCorpusPictureIsItsOwnHTML` re-shoots the ten authored pages and
  compares them to the pixel. When a page or the shooter changes, re-shoot
  with `tools/shoot_corpus.py --force` and re-cut the floor on a sweep — the
  scores of a picture that changed are not comparable with anything before it.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Never edit a script a running sweep reads** — `tools/iterate.sh` above
  all. Bash reads a script as it goes; `S8-sweep`'s died after its bake-off.
- **Do not delete the four shipped defaults or the five wire-level row nets** —
  `_without_empty_rows`, `_join_split_header_row`, `_without_repeated_header`,
  and since spec 0009 `_trimmed_to_header` and `_without_repeated_total`.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.**
- **Any reviewed run is a full sweep**, all twenty-one documents.
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
FIXTURE=sweep tools/iterate.sh <label>        # all twenty-one, ~2¼ h — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~20 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**A sweep outlasts a two-hour background task** — `S7-sweep` took 2h16m,
`S8-sweep` 2h12m. Start it detached and wait on its log, and **never edit
`tools/iterate.sh` while a sweep is running**: bash reads the script as
it goes, and `S8-sweep`'s script died after its bake-off on a line the
edit had shifted:
`nohup env PATH="$PWD/.venv/bin:$PATH" FIXTURE=sweep sh -c 'tools/iterate.sh <label>; echo "SWEEP EXIT $?"' > <log> 2>&1 & disown`.
A document that raises keeps its answers in the dump, and `tools/replay_run.py`
converts it once the bug is fixed, with no model call.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline,
`tests/frozen/s8-result/`. On 2026-10-14 `tools/replay_run.py` and
`tools/rederive.py` over it each reproduced it byte for byte, 21 of 21. Both tools take a
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
  a minute; `--swap <doc>:<NN>=<answer file>` serves one new answer — a
  measurement when the call's new question was already asked somewhere,
  as spec 0013 step 1 uses `s7-result/`'s answers. A
  document marked ASKED MORE THAN THE RUN is not a measurement. It serves
  by pass and order, and **since spec 0012's step 0 it hashes every call's
  prompt, picture and schema**: a document whose calls moved is marked
  ASKED DIFFERENTLY — not a measurement, naming each call. That list is
  what a sweep's prediction is registered from.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
