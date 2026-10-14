# Status — 2026-10-14 (**spec 0013 done, `S9-sweep` taken — the baseline is Alessandro's decision; until then it is `tests/frozen/s8-result/`**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-14,
after `S9-sweep` closed spec 0013's work plan.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file, then
[`specs/0013-four-pages-first.md`](specs/0013-four-pages-first.md) — its
"Outcome — the sweep" and its handover prompt marked *current*. If you are
going to look at output — and you should — use the **`visual-review`
skill**.

Branch `scaffold`. **1142 tests pass (1 skipped), `mypy src/` clean** — at
`a84404c`'s code (`a3969f3` adds the spec only), 2026-10-14.

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
              DONE; S8-sweep the baseline 2026-10-14, frozen as s8-result/
Reset       2026-10-14, Alessandro: everything not in spec 0013 cleared.
Spec 0013   Four pages first — issue #36
              1 receipt 2 certificate 3 pricing 4 certificate 5 ticket
              6 paper 7 statement — each DONE, judged by eye
              S  S9-sweep on a3969f3, 2026-10-14: prediction held to the
                 byte; 7 pages better, 13 same, 1 worse (ticket)
              DECISION PENDING: whether S9-sweep becomes the baseline
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s8-result/`, until Alessandro decides on `S9-sweep`

**Twenty-one documents, 725 answers.** Sweep `S8-sweep`, commit `ba0c110`
(spec 0012 step U), 2026-10-14 00:49–03:00 (**2h12m**), shipped defaults.
Proved at `624b18f` the day spec 0013 began: replay 21 of 21
byte-identical, 0 asked differently; rederive 21 of 21 byte-identical.
**At today's code it is no longer reproduced**: spec 0013 moved nine
pages, and the replay marks seven documents asked differently — the
list §9 registered.

**The candidate — `debug/runs/S9-sweep/`**, commit `a3969f3`, 2026-10-14
11:13–13:29 (**2h16m**), 732 calls, shipped defaults, 40%/60% CPU/GPU.
Proved 2026-10-14 at that code: `tools/replay_run.py debug/runs/S9-sweep`
**21 of 21 byte-identical, 0 asked differently**; `tools/rederive.py`
over it **21 of 21 byte-identical files**. Its answers with their hashes
are saved by `tools/replay_run.py debug/runs/S9-sweep --save-answers
<dir>`. `debug/` is gitignored: **if Alessandro takes it, freeze it as
`tests/frozen/s9-result/` before anything clears `debug/runs/`.**

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The baselines before it

- **`s7-result/`** — the first sweep over twenty-one, `S7-sweep`. The
  baseline 2026-10-13 to 2026-10-14. Four of its table answers were spec
  0013 step 1's target, and `S9-sweep` returned them byte for byte.
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

## Where the corpus is — recorded, not a target

Means over `S9-sweep`, against `s8-result/`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.984 → 0.977 | 0.982 → 0.988 | 0.989 → 0.952 |
| precision | 0.988 → 0.988 | 0.988 → 0.988 | 0.990 → 0.988 |
| join recall | 0.950 → 0.945 | 0.950 → 0.960 | 0.949 → 0.905 |
| tau | 0.968 → 0.951 | 0.990 → 0.990 | 0.912 → 0.853 |
| beside agreement | 0.802 → 0.757 | 0.843 → 0.849 | 0.700 → 0.528 |
| height ratio | 1.100 → 1.069 | 1.029 → 1.028 | 1.276 → 1.171 |
| alignment agreement | 0.796 → 0.805 | 0.833 → 0.840 | 0.705 → 0.718 |
| scale error | 0.200 → 0.220 | 0.129 → 0.154 | 0.378 → 0.383 |

The six's falls are the ticket's (vocabulary 0.975 → 0.750) and the
certificate's signature row (beside 1.000 → 0.000).

**`vanished`: 40 → 41 words.** Back: the receipt's six price tokens,
`castleton`, `2022`, the ticket's `pass`. Gone: ten of the ticket's —
`nordlys`, `air`, `osl`, `oslo`, `gardermoen` and its gate note.

---

## What the last work shipped

### Spec 0013 — four pages first, `S9-sweep`, 2026-10-14

**Against `S9-0-replay` (`s8-result/` at the code it began on): seven
pages better, thirteen the same, one worse.**

- **Better:** the receipt's eight prices at the right; the certificate
  landscape, its name one line, its signature row no longer one
  interleaved paragraph; pricing's three framed cards; the statement's
  header readable on its band; cv's `2022`; paper's caption once;
  sample_semantic's tags on one line.
- **Worse:** `ticket_0020`. Its warp now holds the whole card and
  `BOARDING PASS` is read whole, but the new crops' answers lose `OSL`,
  `OSLO GARDERMOEN`, both `NORDLYS AIR` and the gate note, and an 8 px
  `equalise` halo recovered as a Zone is read as `The` / `The`.

What shipped, one commit a step:
- 1 `preprocess.table_grid`: the column count from the page's rules only
  where it rules two or more;
- 2 `render`: a frame round the page and the frames inside it padded once;
- 3 cards as framed stacks (`rhythm`, `render._cards`), a frame bridged
  through a ribbon (`furniture._bridged`), a line in two sizes
  (`Look.sizes`), a cut copy dropped (`locate.without_cut_copies`), a list
  printed on one line drawn so;
- 4 `detector`: a text container round a surer picture opened,
  `HEADING_GAP_RATIO` 1.9 → 1.77, inside to a pixel;
- 5 `preprocess.rectify`: an edge with the sheet beyond it is not the
  paper's, the outline read off the sheet's colour; `RECTIFIER_VERSION` 6;
- 6 `wire.without_title_rows`, the sixth wire-level row net;
- 7 `looks._drawn_ground`: a drawn fill under the Cell.

§9's prediction held to the byte: 0 of the calls asked the same
answered differently; the four step-1 table answers equal `s7-result/`'s.

### Earlier

Specs 0008–0012 and the corpus widening: each spec's "Outcome" sections,
and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — Alessandro's decision on `S9-sweep`

**Nothing else is open.** Spec 0013's "Outcome — the sweep" ranks five
directions from the faults left — the ticket's halo Zone and its pairs
reading, the certificate's row and seal — **as record, not as a queue:
do not pick one up unless he names it.**

If he takes `S9-sweep`: freeze it as `tests/frozen/s9-result/` (documents,
scores, answers with hashes, `dth_env.txt`, a README naming the ticket's
leg as `s8-result/`'s README names its three), prove the freeze by replay
and rederive 21 of 21, and update `CLAUDE.md`'s baseline lines.

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
  **`s8-result/`, the baseline** since 2026-10-14, twenty-one documents.
  `debug/runs/S9-sweep/` is not one until it is frozen.
  `a3-result/` was scored on pictures missing their last lines;
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
- **Do not delete the four shipped defaults or the six wire-level row nets** —
  `_without_empty_rows`, `_join_split_header_row`, `_without_repeated_header`,
  since spec 0009 `_trimmed_to_header` and `_without_repeated_total`, and
  since spec 0013 `without_title_rows`.
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
- **A colour kept on a row's measured fill** — spec 0013 step 7. Kept
  `timetable_0019`'s `B04 · Ms Ilves` teal beside its lesson's blue bar;
  a drawn furniture fill shipped instead.
- **Opening any container less sure than its parts** — spec 0013 step 4.
  Also opened `invoice_0002`'s pairs, `nonlatin_0014`'s totals line and
  two pictures; it ships only round a picture.

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
`S8-sweep` 2h12m, `S9-sweep` 2h16m. Start it detached and wait on its log, and **never edit
`tools/iterate.sh` while a sweep is running**: bash reads the script as
it goes, and `S8-sweep`'s script died after its bake-off on a line the
edit had shifted:
`nohup env PATH="$PWD/.venv/bin:$PATH" FIXTURE=sweep sh -c 'tools/iterate.sh <label>; echo "SWEEP EXIT $?"' > <log> 2>&1 & disown`.
A document that raises keeps its answers in the dump, and `tools/replay_run.py`
converts it once the bug is fixed, with no model call.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline. At
today's code they reproduce `debug/runs/S9-sweep/` byte for byte, 21 of
21 each (2026-10-14); `s8-result/` they reproduced at `624b18f`. Both
tools take a run directory as well as a frozen one.

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
