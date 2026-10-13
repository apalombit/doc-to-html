# Status — 2026-10-13 (**the corpus is twenty-one; the baseline is `tests/frozen/s7-result/`; spec 0012 planned, not started**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-13,
after the first sweep over twenty-one documents.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file, then
[`specs/0012-draw-what-the-page-draws.md`](specs/0012-draw-what-the-page-draws.md),
the only open work. If you are going to look at output — and you should —
use the **`visual-review` skill**.

Branch `scaffold`. **1014 tests pass, `mypy src/` clean.**

**How work is judged — Alessandro, 2026-10-12, for spec 0011.** By eye:
every step's sheets are opened against the previous step's and each page
judged better / same / worse. Scores are produced and recorded, and **never
gate a step or carry an argument**. The ratchet below is reported, not a
gate. The one number still read is the report's `vanished` list, as a
pointer to a page to look at. He checks every run himself too. **Spec 0012
asks him to confirm it carries over.**

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
              Fresh sweep F1-sweep, commit 12fa2d1, shipped defaults.
Spec 0008   Page structure — issue #31          DONE; S3-sweep the floor 2026-10-11
Spec 0009   Four repairs, one sweep — issue #32 DONE; folded into 0010's decision
Spec 0010   Five repairs, type at the page's size — issue #33
              DONE; S5-sweep the baseline 2026-10-12
Spec 0011   Place every entry where the page puts it — issue #34
              0 freeze S5-sweep   1 rhythm   2 locate   3 fields
              4 lines: 4a size, weight, italic  4b colour  4c rules
                       4d leaders  4e spacing  4f typeface
              5 sweep S6-sweep, prediction held, 14 pages better
              DECIDED 2026-10-13: S6-sweep the baseline, frozen as s6-result/
Corpus      Six held-out documents added 2026-10-13 — letter, pricing,
              paper, timetable, ticket, certificate — fifteen kept
            Sweep S7-sweep over all 21, prediction held on the fifteen;
              pricing's crash fixed downstream, 9cd4ae2
              DECIDED 2026-10-13: S7-sweep the baseline, frozen as s7-result/
Spec 0012   Draw what the page draws — issue #35, planned 2026-10-13
              the report notebook: faults grouped G1-G9, workflow, work plan
              NOT STARTED
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s7-result/`, DECIDED 2026-10-13

**Twenty-one documents, 751 answers.** Sweep `S7-sweep`, commit `639d882`,
2026-10-13 09:04–11:20 (**2h16m**), shipped defaults.

- **The fifteen are `s6-result/`'s**, byte for byte: every one of their 518
  answers and every page. Nothing in the pipeline changed between the two
  sweeps; only the corpus did.
- **`pricing_0017` raised** after its 88 calls, in `looks.read` — a Cell
  box a pixel past its Zone's crop cut two arrays to different shapes, a
  bug from spec 0011 step 4a that no page of the fifteen reached. Commit
  `9cd4ae2` fixed it, and the frozen documents are the replay of the
  sweep's answers at that commit: pricing converts with no call beyond its
  88, and the other twenty are the sweep's own, byte for byte.

Proved the day it was frozen, at `9cd4ae2`:
- `tools/replay_run.py` from its answers: **21 of 21 byte-identical**.
- `tools/rederive.py` over it: **21 of 21 identical pages, 20 of 21
  byte-identical files** — `form_0007` differs in Zone 5's `align` inside
  its IR, the step-order effect its README names.
- the rederive scored against `s6-result/`: **21 documents, 0 differing
  fields**.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s7-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The baselines before it

- **`s6-result/`** — spec 0011's sweep `S6-sweep`, commit `7c12935`, the
  fifteen. The baseline for one day; `s7-result/` holds its fifteen byte
  for byte. Four beside legs below `s5-result/`, accepted.
- **`s5-result/`** — spec 0010's `S5-sweep`, commit `4a5fe3f`. Five legs
  below `s3-result/`, accepted 2026-10-12.
- **`s3-result/`**, **`q5-result/`**, **`reshot/`** and the A-phase
  directories — each README says what it is and why its floor moved.

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

Means over `s7-result/`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.968 | 0.988 | 0.920 |
| precision | 0.981 | 0.988 | 0.964 |
| join recall | 0.922 | 0.960 | 0.827 |
| tau | 0.942 | 0.990 | 0.822 |
| beside agreement | 0.786 | 0.831 | 0.672 |
| height ratio | 1.129 | 1.107 | 1.183 |
| alignment agreement | 0.735 | 0.785 | 0.608 |
| scale error | 0.242 | 0.189 | 0.373 |

**`vanished`: 55 words.** The fifteen's 26, unchanged since `S5-sweep`;
the timetable's **24** — five of its seven lesson rows lost to a wrong grid
count; 3 on the paper that are not lost (Unicode superscripts scored as one
token with their word); the letter's split email and the ticket's `PASS`.

**The six held-out pages, by eye:** paper and letter close; certificate
and ticket keep their words and lose their look; pricing's three cards are
drawn as two lanes with the middle one halved; the timetable loses most of
its table and says nothing. Spec 0012 §1b has each traced.

---

## What the last work shipped

### The corpus widened, and the first sweep over it — 2026-10-13

Six documents authored to carry what the fifteen lack, each an HTML file
and its screenshot, the fifteen kept as they are (`corpus.NEW`):

| document | what it carries |
|---|---|
| `letter_0016` | a coloured letterhead rule, address and date blocks, a script signature |
| `pricing_0017` | three cards stretched to one height, the middle one emphasised with a ribbon; ticks and crosses |
| `paper_0018` | two justified columns with a rule between them, small-capital heads, a numbered equation, a bar chart, a three-rule table, superscripts |
| `timetable_0019` | a grid with merged cells, tinted lessons with colour bars, a hatched lunch row, a legend |
| `ticket_0020` | a boarding pass photographed at a slant on a desk, a dashed perforation, a block code |
| `certificate_0021` | a double frame, small capitals, a script name, signature lines, a round seal |

`S7-sweep` converted all twenty-one. Three corpus guards walked every
document over a fifteen-document floor or a written-down answer; each now
names the six as held out, and writing their answers is spec 0012's step 0.

### Spec 0011 — place every entry where the page puts it, `S6-sweep`, 2026-10-12

**The pages, against `S5-sweep`: fourteen better, `sample_css_0004` the
same, none worse.** `form_0007` is drawn as its fields; `newsletter_0008`
as three serif columns; `receipt_0010` in mono with its dashed rules;
`menu_0012` with leaders and italic notes; `darkdeck_0009` with its tiles
and pills; `catalogue_0015` with its chips and badges.

What shipped, by step: the page's gaps, groups and alignment (rhythm);
every entry's box, from tesseract as a locator only (locate); the form's
boxes, ticks and digit boxes (fields); and per entry its size, weight,
slant, colour, chips, table rules and fills, leader dots, spacing and the
page's typeface class (looks, 4a–4f). All downstream of the model: the
sweep's 518 answers came back byte-identical to `S5-sweep`'s, as
registered. The spec's "Outcome — step 5" has the error analysis.

### Earlier

Specs 0008–0010 and everything before them: each spec's "Outcome"
sections, and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — spec 0012

[`specs/0012-draw-what-the-page-draws.md`](specs/0012-draw-what-the-page-draws.md),
issue #35, planned 2026-10-13 as the report notebook Alessandro asked for.
It records:

- **his notes on `S6-sweep`** and the six new pages, each traced to its
  cause (§1);
- **two faults decided:** the findings card leaves the page for
  `report.html`, and a photographed page is drawn at its paper's share of
  the picture;
- **the faults grouped into nine** that each close several at once (§3) —
  the largest, **G3**, is one new step recording everything the page draws
  that is not type, which six partial readers each see a part of today;
- **the workflow changes** (§4): where the new step sits, and a replay
  that says when a call was asked differently;
- **a work plan, decided by Alessandro 2026-10-13: the groups in order,
  one after another, then one full sweep, `S8-sweep`, over all 21** — the
  timetable's repair judged there. Each group's downstream half is measured
  offline in its turn; the upstream halves (G3b, G4's split) are built
  together in step U, just before the sweep, because no offline loop can
  measure a changed crop or prompt.

Its handover prompt is the one to start from.

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
  `s5-result/`, `s6-result/` — all kept as record — and
  **`s7-result/`, the baseline** since 2026-10-13, twenty-one documents. `a3-result/` was scored on pictures missing their last lines;
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
    --documents sweep --previous tests/frozen/s7-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**A sweep outlasts a two-hour background task** — `S7-sweep` took 2h16m. Start
it detached and wait on its log:
`nohup env PATH="$PWD/.venv/bin:$PATH" FIXTURE=sweep sh -c 'tools/iterate.sh <label>; echo "SWEEP EXIT $?"' > <log> 2>&1 & disown`.
A document that raises keeps its answers in the dump, and `tools/replay_run.py`
converts it once the bug is fixed, with no model call.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline,
`tests/frozen/s7-result/`. On 2026-10-13 `tools/replay_run.py` over it
reproduced it byte for byte, 21 of 21, and `tools/rederive.py` every page. Both tools take a
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
  document marked ASKED MORE THAN THE RUN is not a measurement. **It serves
  by pass and order and never reads the prompt or the picture**, so a change
  that asks the same number of calls differently replays the old answers
  silently — spec 0012 §4b proposes the guard.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
