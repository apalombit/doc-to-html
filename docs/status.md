# Status — 2026-10-19 (**spec 0018 done; `S13-sweep` waits on the baseline decision; the baseline is still `tests/frozen/s12-result/`**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-19,
after spec 0018's sweep `S13-sweep` (issue #41). Alessandro decides whether
it becomes the baseline.

Reading order for a fresh session:
1. `CLAUDE.md`'s **READ THIS FIRST**;
2. [`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md),
   which is authoritative;
3. this file;
4. [`specs/0018-strip-twins-rectify.md`](specs/0018-strip-twins-rectify.md):
   its "Outcome — the sweep", then "Handover — after the sweep", which
   starts the next session.

If you are going to look at output — and you should — use the
**`visual-review` skill**.

Branch `scaffold`. **1287 tests pass (1 skipped), `mypy src/` clean** — at `91a72e1`, the sweep's commit, 2026-10-19.

**How work is judged — Alessandro, 2026-10-12, for spec 0011; carried
over by specs 0012 to 0018.**
- **By eye.** Every step's sheets are opened against the previous step's,
  and each page is judged better / same / worse.
- **Scores** are produced and recorded, and **never gate a step or carry an
  argument**. The ratchet below is reported, not a gate.
- **The one number still read** is the report's `vanished` list, as a
  pointer to a page to look at.
- **The six held-out pages** are reported in their own lines.

He checks every run himself too.

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
              DONE; S8-sweep the baseline 2026-10-14
Reset       2026-10-14, Alessandro: everything not in spec 0013 cleared.
Spec 0013   Four pages first — issue #36
              DONE; S9-sweep the baseline 2026-10-14
Spec 0014   Every printed line has a place — issue #37
              DONE; S10-sweep the baseline 2026-10-15
Reset       2026-10-15, Alessandro: everything not in spec 0015 cleared.
Spec 0015   Every line read, and drawn where the page puts it — issue #38
              DONE; S11-sweep the baseline 2026-10-17
Reset       2026-10-18, Alessandro: everything not in spec 0016 cleared.
Spec 0016   Structure first — one grid, one strip — issue #39
              DONE; S12-sweep the baseline 2026-10-18, frozen as s12-result/
Spec 0017   Margins from the type, one size per role — issue #40
              render only; DECIDED 2026-10-19: kept
Spec 0018   The strip as the page draws it, photographed pages, the
              straightening step — issue #41, 2026-10-19:
              0a the render re-photographed + overlay   DONE
              0b the scorer in the paper's frame        DONE
              0c the box pictures on the rectified page DONE
              A1 ink against its local ground           DONE
              A2 a strip one container                  DROPPED
              B0 the twins, model-free                  DONE
              B1 a card's edge read two lines deep      DONE
              C1 an outline holds the page              DONE
              C2 corners at full resolution             DROPPED
              C3 cubic warp                             SKIPPED
              C4 equalise only uneven light             DROPPED
              S  S13-sweep on 91a72e1: prediction held to the byte;
                 3 pages better (ticket, pricing, cv), 18 same, none worse
              DECISION PENDING: S13-sweep as the baseline
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s12-result/`, DECIDED 2026-10-18

**Twenty-one documents, 749 answers**, byte-identical to `s11-result/`'s.
Sweep `S12-sweep`, commit `3abb55d` (spec 0016 step P; code `c98f2db`),
2026-10-18 16:07 to 18:30 (**2h22m**), shipped defaults.

**Score against `scores-paper-frame.json`, not `scores.json`, since
2026-10-19.** Spec 0018's 0b scorer measures the source in its paper's
frame. It re-scored `s12-result/`, and only the ticket moved (4 fields).
The README has them.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s12-result/scores-paper-frame.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The candidate — `S13-sweep`, 2026-10-19, not yet frozen

- **The run.** Commit `91a72e1` (code `e33d246`'s), 18:42 to 21:02,
  **2h20m**, 755 calls, 40%/60% CPU/GPU. It lives in `debug/runs/S13-sweep`;
  **do not clear it before Alessandro decides.**
- **The prediction held to the byte.** All 755 calls were asked and
  answered as registered: 749 of `s12-result/`'s and `S13-A1-run`'s for cv,
  pricing and the ticket. All 21 pages are byte-identical to their
  predicted render. The sweep's own replay is 21 of 21, 0 asked
  differently.
- **By eye against `S12-sweep`:** the ticket, pricing and cv better,
  eighteen the same, none worse.
- **Ratchet, reported:** one leg below, pricing's beside 0.629 → 0.600.
- **`vanished`:** 26 → 24.

The spec's "Handover — after the sweep" says how to freeze it if he takes
it.

### The baselines before it

- **`s11-result/`** — spec 0015's sweep. The baseline 2026-10-17 to
  2026-10-18.
- **`s10-result/`**, **`s9-result/`**, **`s8-result/`**, **`s7-result/`**,
  **`s6-result/`**, **`s5-result/`**, **`s3-result/`**, **`q5-result/`**,
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

Means over `S13-sweep`, against `s12-result/scores-paper-frame.json`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.990 → 0.992 | 0.991 → 0.991 | 0.988 → 0.997 |
| precision | 0.989 → 0.990 | 0.988 → 0.988 | 0.989 → 0.996 |
| join recall | 0.961 → 0.963 | 0.965 → 0.965 | 0.949 → 0.958 |
| tau | 0.982 → 0.982 | 0.990 → 0.990 | 0.963 → 0.964 |
| beside agreement | 0.853 → 0.874 | 0.877 → 0.894 | 0.791 → 0.825 |
| height ratio | 1.048 → 1.050 | 1.028 → 1.027 | 1.099 → 1.107 |
| alignment agreement | 0.805 → 0.804 | 0.843 → 0.841 | 0.711 → 0.712 |
| scale error | 0.226 → 0.223 | 0.165 → 0.168 | 0.377 → 0.359 |

- **Moved:** the ticket, cv, pricing and the catalogue.
- **`vanished`: 26 → 24 words.** The ticket's `nordlys` and `air` are back,
  and no word is newly vanished.
- **The spec's §4 lists the misreads** the `invented` lists show: the
  statement's 216.08 read 210.08, nonlatin's footer naming another
  company, and others.

---

## What the last work shipped

### Spec 0018 — the strip, photographed pages, the straightening step, 2026-10-19

One commit a step.

**Part 0, the tools:**
- **0a** `592175b`: `doc_to_html.review` re-photographs the render of a
  warped page onto its outline and adds an overlay. An unwarped page's
  sheet is byte-identical.
- **0b** `69e6390`: `project(flat=True)` measures the source in its paper's
  frame, and `s12-result/scores-paper-frame.json` is the re-scored baseline.
- **0c** `038b99c`: the per-page index shows `Rectified.image` and the boxes
  on it, as the detector saw them.

**A1** `7aadacc`, `45604de`: `furniture.grounded` — ink measured against
its local ground.
- A solid fill is paper, and type on it is ink by its contrast with the
  fill. Its blended edge is paper.
- A fill one Zone holds whole is that Zone's. A fill with no type is a
  mark.
- The ticket's halo Zone and its `The` / `The` are gone, the strip is one
  row, and `TRD` is display size.
- **The knock-ons, repaired:**
  - `structure._columns`: a divider is crossed only past its stroke's
    width;
  - `render._on_its_ground`: cv's sidebar;
  - `locate`: a re-read line's `read_from`;
  - `Document.to_data`: the IR without the null `read_from`.

**B0** `0961c70`: `tools/twins.py`, five photographed twins of every
corpus page with exact truth.
- `--check` is model-free and takes about 13 minutes. It reports
  `rectify` against the truth, and Zones kept against the page as shot,
  carried into one frame.
- **Not corpus** — Alessandro, 2026-10-19.

**B1** `aa6d252`: `style._bordered` reads each card edge two lines deep
(`EDGE_DEPTH`), so a resampled card is still a card. A rule is never a box.

**C1** `8aed639`: an outline holds the page.
- Paper is told from desk against the desk read at the picture's edge, and
  a shadow is desk.
- An outline that leaves paper outside is grown to it, or refused. The
  strict reading comes first.
- cv's twins: 307px out → 1.2–1.35px. No corpus outline moves.
  `RECTIFIER_VERSION` is 7.

**Dropped, each on Alessandro's decision after a targeted run:**
- **A2** — the merged strip read stacked again;
- **C2** — corners exact, the receipt and the ticket worse;
- **C4** — six of eight pages worse, words vanished.

**C3** was skipped. "Measured and not shipped" below has each.

**The lesson the three drops share:** the detector regroups a page whose
picture changes (B0's fault 5). Every step that changed the picture had
its own aim right and lost pages through grouping. That is direction 1 in
the spec's outcome.

### Spec 0017 — margins from the type, one size per role, 2026-10-18

**Render only, no sweep.**
- The ticket's field grid sits 22px in from the card's edge, and the
  stub's text 20px off the perforation.
- `PASSENGER` is a muted label, and the stub's values are one size.
- Kept 2026-10-19, issue #40 closed.
- Commits: 1 `1c869fd`, 2 `24b635c`.

### Spec 0016 — structure first, `S12-sweep`, 2026-10-18

One grid per line-drawn Zone, one grid across side-by-side Zones, a drawn
strip one container, and two `locate` guards. One page better (the
ticket), twenty the same. Taken as the baseline, `s12-result/`. Issue #39
closed.

### Earlier

Specs 0008–0015 and the corpus widening: each spec's "Outcome" sections,
and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — the baseline decision, then nothing open

- **Alessandro decides whether `S13-sweep` becomes the baseline.** If he
  takes it, it is frozen as `tests/frozen/s13-result/`. The spec's
  "Handover — after the sweep" is the prompt for that session.
- **The spec ranks four directions:**
  1. the detector's grouping, steady under a changed picture;
  2. readings inside a line;
  3. structure the IR does not carry;
  4. looks.

  **None is queued** until he names one.

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
  `s5-result/`, `s6-result/`, `s7-result/`,
  `s8-result/`, `s9-result/`, `s10-result/`, `s11-result/` — all kept as record — and
  **`s12-result/`, the baseline** since 2026-10-18, twenty-one documents.
  `a3-result/` was scored on pictures missing their last lines;
  quote it only as that.
- **The committed corpus picture is a screenshot of its own HTML.**
  `TestTheCorpusPictureIsItsOwnHTML` re-shoots the ten authored pages and
  compares them to the pixel. When a page or the shooter changes, re-shoot
  with `tools/shoot_corpus.py --force` and re-cut the floor on a sweep — the
  scores of a picture that changed are not comparable with anything before it.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **The twins are a model-free check, not corpus** — Alessandro,
  2026-10-19. `tools/twins.py --check` measures `rectify` and the layout
  front on photographed copies; nothing scores against them.
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

Spec 0018's three drops each moved the picture or the boxes and lost pages
through the detector's grouping (the spec has each in full):
- **A drawn strip one container** — A2. `furniture.strips` and
  `structure.one_per_strip` merged the ticket's strip into one Zone. On
  that crop the caption pass took `NORDLYS AIR` for its Title, and the two
  were drawn stacked; the stub's panes were lost (`S13-A2-run`). The cut
  alone was mixed (`S13-A2c-run`).
- **Corners at full resolution** — C2. Every outlined twin came within
  0.01–0.23px, and the ticket within 0.08–0.30px of its CSS corners. But
  the receipt's crop moved and its table lost its rows, and the ticket's
  main pane split into five Zones (`S13-C2-run`). **C3**, cubic warp, was
  skipped on the same decision.
- **Equalise only uneven light** — C4. The light read off the paper alone
  judges every corpus page even and every shaded twin uneven, and lifts no
  ink anywhere. But with nothing divided, 15 pages' crops moved. On
  `S13-C4-run` six of eight pages were worse: the catalogue lost five SKU
  chips, the ticket its gate note, and the timetable its grid. The
  detector, the snap and the crops lean on ink the old division invents.
  The diff is not kept; the spec describes the rule exactly.

- **No Zone from a drawn fill's edge** — spec 0016, 4a. Recovery
  ignoring the solid fills `_measure_style` finds removes the ticket's
  halo Zone and nothing else (layout front, all 21), but the body glyph
  then measures 9.0px and tesseract's first read of the stub changes:
  the gate note's re-read crop held its one confident word and was read
  `autos before`, and a word of the stub strip's text was re-read as
  `NORDLYS` (`S12-4-ticket`).
- **A re-read crop boxed by every unclaimed word of its line** — spec
  0016, the fix 4a called for. It repairs the gate note's crop, and
  `timetable_0019`'s legend, two overlapping lines, was read whole twice
  and printed twice (`S12-5-check`).

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
- **A grid's copies take the Kind that keeps most of a line** — spec
  0014 step 3, `S10-3-check`. All nine catalogue cards read as prose
  lost five code badges and their price rows' spread; darkdeck's tiles
  are four `pairs` when copies are read alike, out of its reach. Its
  diff is beside the check run.
- **Spec 0015 step 1's first forms** — a claim by letters alone (it let
  `Mathematics` claim the timetable's legend), a guard alike to *any*
  Cell (it refused `OSL`, 0.86 to `OSLO`), a guard on tesseract's own
  text (it cannot separate `99` and `914`). Step 3b's reach for a
  container's edge as well as a drawn rule moved 24 of the catalogue's
  crops. The spec's step outcomes have each.
- **The re-read's guard judged one Block at a time** — spec 0014 step 2.
  It refused the timetable's legend, five items each a word its grid
  prints; the guard judges the line read together instead.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all twenty-one, ~2¼ h — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~20 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s12-result/scores-paper-frame.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
python tools/twins.py debug/twins --check     # rectify + layout front on the twins, ~13 min, no model
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**A sweep outlasts a two-hour background task** — `S7-sweep` took 2h16m,
`S8-sweep` 2h12m, `S9-sweep` 2h16m, `S10-sweep` 2h21m, `S11-sweep` 2h22m,
`S12-sweep` 2h22m, `S13-sweep` 2h20m. Start it detached and wait on its log, and **never edit
`tools/iterate.sh` while a sweep is running**: bash reads the script as
it goes, and `S8-sweep`'s script died after its bake-off on a line the
edit had shifted:
`nohup env PATH="$PWD/.venv/bin:$PATH" FIXTURE=sweep sh -c 'tools/iterate.sh <label>; echo "SWEEP EXIT $?"' > <log> 2>&1 & disown`.
A document that raises keeps its answers in the dump, and `tools/replay_run.py`
converts it once the bug is fixed, with no model call.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline,
`tests/frozen/s12-result/`. On 2026-10-18 `tools/replay_run.py` and
`tools/rederive.py` over it each reproduced it byte for byte, 21 of 21. Both
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
