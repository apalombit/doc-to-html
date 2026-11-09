# Status — 2026-11-09 (**the baseline is `tests/frozen/s14-result/`; the corpus is built (spec 0020); L2 is done (spec 0021); L3, the honest baseline, is done (spec 0022, issue #45 closed): every one of 37 unseen pages has a major fault; next is P1, the GLM-OCR parser-first PoC, spec 0023**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-23,
when Alessandro took spec 0019's sweep `S14-sweep` as the baseline,
frozen as `s14-result/` (issue #42 closed), and cleared every open item.
Updated 2026-10-24, when he decided the level-up plan
([`level-up.md`](level-up.md) §8), 2026-10-30, when spec 0020 built
the corpus (issue #43 closed), 2026-11-07, when spec 0021 closed L2
(issue #44 closed), and 2026-11-09, when spec 0022 closed L3 (issue #45
closed).

Reading order for a fresh session:
1. `CLAUDE.md`'s **READ THIS FIRST**;
2. [`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md),
   which is authoritative;
3. this file;
4. [`level-up.md`](level-up.md)'s Gist, §6 and §8: the plan from
   2026-10-24, and what comes next;
5. [`specs/0022-the-honest-baseline.md`](specs/0022-the-honest-baseline.md)'s
   "Outcome", the ranked fault classes P2 decides against and the prompt
   that starts P1; [`specs/0021-measurement-and-the-judge.md`](specs/0021-measurement-and-the-judge.md)'s
   "Where L2 stands", what the checks and the judge are; and
   [`agents/review-criteria.md`](agents/review-criteria.md), the
   criteria every review is judged by;
6. [`specs/0019-steady-checked-structured-styled.md`](specs/0019-steady-checked-structured-styled.md)'s
   "Outcome — the steps" and "Outcome — the sweep", the last conversion
   work done.

If you are going to look at output — and you should — use the
**`visual-review` skill**.

Branches `main`, `develop` and `level-up`, all on the remote since
2026-10-24; work continues on `level-up`, and `scaffold` is retired into
`develop`. **1702 tests pass (1 skipped), `mypy src/` clean**: measured
2026-11-09 on `level-up`, at the end of spec 0022. The conversion code
is still `a0d73c9`'s in what it answers: spec 0020 added the corpus
factory, and spec 0021 the batch runner and a 3-minute limit on each
model call; `tools/replay_run.py` reproduces `s14-result/` 21 of 21 byte
for byte on 2026-11-09, at the end of spec 0022, which changed the
checks and not the conversion.

**How work is judged — Alessandro, 2026-10-12, for spec 0011; carried
over by specs 0012 to 0019.**
- **By eye.** Every step's sheets are opened against the previous step's,
  and each page is judged better / same / worse.
- **Scores** are produced and recorded, and **never gate a step or carry an
  argument**. The ratchet below is reported, not a gate.
- **The one number still read** is the report's `vanished` list, as a
  pointer to a page to look at.
- **The six held-out pages** are reported in their own lines.

He checks every run himself too.

**Since 2026-10-24, by the criteria** in
[`agents/review-criteria.md`](agents/review-criteria.md): the render looks
like the page, never guess, every line as printed, net gain ships. Claude
is the judge, over the checks' faults (`tools/measure_run.py`); his calls
come through the one-issue-at-a-time page
(https://claude.ai/artifact/RpUd3a7ioGjdNWBLyqM6JD) and are recorded in
`agents/review-issues.json`.

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
              DECIDED 2026-10-19: S13-sweep the baseline, frozen as s13-result/
Reset       2026-10-19, Alessandro: everything not in spec 0019 cleared.
Spec 0019   One grouping however the page is pictured, the structure the
              IR lacks, the page's looks, readings checked — issue #42:
              A0 the jitter check                         DONE
              A1 container or parts on what the page draws DONE, kept at
                 the checkpoint; A2 had no pages
              B1 spanning cells  B2 raised marks  B3 display lines
              B4 a pair's separator                       each DONE
              C1 every entry placed and measured  C2 weight as measured
              C3 chips and discs  C4 drop caps  C5 faces  each DONE
              D1 tesseract's reading kept                 DONE
              the second pass's repairs (a78513f)         DONE
              D2 the third reading                        DONE; a disputed
                 Cell drawn plain, Alessandro 2026-10-22
              D3 nonlatin's footer                        recorded
              S  S14-sweep on a0d73c9, 2026-10-23: prediction held to the
                 byte; 14 pages better, 7 same, none worse
              DECIDED 2026-10-23: S14-sweep the baseline, frozen as s14-result/
Reset       2026-10-23, Alessandro: every open item cleared, spec 0019's
              four directions included. Nothing is open.
LEVEL-UP    2026-10-24, Alessandro: docs/level-up.md, branch level-up.
              L1a the variability                     AGREED 2026-10-24
Spec 0020   The corpus, L1b — issue #43: 631 pages, every one passing;
              573 generated (130 parts of a document), 27 real PDF
              pages, the 31 in dev; pools dev / panel / vault sealed
              DONE 2026-10-30
Spec 0021   Measurement and the judge, L2 — issue #44: the checks,
              the batch runner, one command, the review skill, the
              issue page; dev converted on 98 pages; five rounds of
              Alessandro's calls, 53 of 58 agreed, the checks built
              to them                                   DONE 2026-11-07
Spec 0022   The honest baseline, L3 — issue #45: L3-baseline over 41
              panel pages (five real PDF), 37 converted, 4 timed out;
              every page reviewed: a major fault on 37 of 37, three
              in four made reading the page; round 7, 15 of 15
              agreed; six check issues fixed      DONE 2026-11-09
              P1 the GLM-OCR parser-first PoC, spec 0023 NEXT
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s14-result/`, DECIDED 2026-10-23

**Twenty-one documents, 811 answers.** The first 755 are `s13-result/`'s,
byte for byte and in order. The other 56 are D2's third readings, on 17
pages.
- Sweep `S14-sweep`, commit `a0d73c9`, 2026-10-23 08:17 to 10:55
  (**2h38m**), shipped defaults, 40%/60% CPU/GPU.
- Alessandro took it after review: against `S13-sweep`, fourteen pages
  better, seven the same, none worse.
- Its registered prediction held to the byte.

Proved on 2026-10-23, at `a0d73c9`:
- `tools/replay_run.py tests/frozen/s14-result`: **21 of 21
  byte-identical, 0 asked differently**;
- `tools/rederive.py` over it: **21 of 21 byte-identical files**;
- the rederive scored: **21 documents, 0 differing fields** against its
  `scores.json`;
- its 811 answers against the sweep's `trace.json`: 0 differ.

Score against it:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s14-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The baselines before it

- **`s13-result/`** — spec 0018's sweep, `S13-sweep`. The baseline
  2026-10-19 to 2026-10-23. Its `scores.json` is spec 0018's 0b scorer's,
  which measures the source in its paper's frame.
- **`s12-result/`** — spec 0016's sweep, `S12-sweep`. The baseline
  2026-10-18 to 2026-10-19. Its `scores-paper-frame.json` is its re-score
  by spec 0018's 0b scorer, against which `S13-sweep` was scored.
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

Means over `S14-sweep`, against `s13-result/scores.json`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.992 → 0.994 | 0.991 → 0.993 | 0.997 → 0.999 |
| precision | 0.990 → 0.992 | 0.988 → 0.989 | 0.996 → 0.998 |
| join recall | 0.963 → 0.967 | 0.965 → 0.969 | 0.958 → 0.964 |
| tau | 0.982 → 0.984 | 0.990 → 0.990 | 0.964 → 0.972 |
| beside agreement | 0.874 → 0.870 | 0.894 → 0.901 | 0.825 → 0.795 |
| height ratio | 1.050 → 1.043 | 1.027 → 1.022 | 1.107 → 1.096 |
| alignment agreement | 0.804 → 0.810 | 0.841 → 0.842 | 0.712 → 0.731 |
| scale error | 0.223 → 0.223 | 0.168 → 0.168 | 0.359 → 0.359 |

- **`vanished`: 24 → 15 words**, none newly vanished.
- **Three ratchet legs below `s13-result/`**, each traced in the spec's
  §3: the certificate's and the catalogue's beside, and the report's
  precision.
- **Grouping:** the jitter check keeps 751 of 848 Zones (0.886), and the
  twins 914 of 1080 (0.846). Both were A1's. The target, ≥ 0.95, is not
  met.

---

## What the last work shipped

### Spec 0022 — the honest baseline, L3, 2026-11-08 to 2026-11-09

Measurement only; no conversion code changed (the replay of
`s14-result/` is still 21 of 21 byte-identical). It shipped the L3 run's
calls (`agents/review-calls/L3-baseline.json`), round 7 on the issue
page, and six fixes to the checks (`checks.py`, and `Word.joined` in the
projection), each pinned on a dev page. The spec's "Outcome" is the
record and the reference P2 decides against. The run's 37 renders and
1577 answers are frozen in `tests/frozen/l3-baseline/`: panel pages,
read by no test.

### Spec 0019 — steady, checked, structured, styled, 2026-10-19 to 2026-10-23

One commit a step. The spec's "Outcome — the steps" has each step's pages
and measures.

- **A0** `1397ed4`: `tools/layout_front.py --jitter` — Zones kept under
  four invisible perturbations of the page's own picture.
- **A1** `d0c7eea`: four decisions the detector took on a score crossing,
  now taken on what the page draws. Jitter 0.749 → 0.886, twins
  0.759 → 0.846, the corpus as shot unmoved. Kept at the checkpoint, and
  A2 had no pages.
- **B1** `2f43e43`, `spans.read`: a ruled grid's second lines join the
  cell above, and an entry spans the empty slots its drawn cell covers
  (the timetable).
- **B2** `204db2a`, `raised.read`: superscripts as `sup` Runs (paper,
  report).
- **B3** `34820e9`, `display.read`: a display line centred and apart, and
  its `(n)` (paper's equation).
- **B4** `e208701`, `separator.read`: the colon a label is printed with,
  and the bar between pairs (the invoices, nonlatin, catalogue).
- **C1** `5a7ee93`: type on a fill read on the fill's crop; marks placed
  on their glyphs; a chip told from heavy type.
- **C2** `87fc1be`: an element the stylesheet draws bold is drawn regular
  where its entry measured regular (`Zone.title_bold`).
- **C3** `f90dbd3`: a chip at a line's end on that line; a disc and its
  ring (`Furniture.disc`, `Furniture.ring`; the certificate's seal).
- **C4** `1f9f556`, `dropcap.read`: a drop cap, drawn as the page's
  `::first-letter` (the newsletter).
- **C5** `9671acf`: `SCRIPT_JOINED` 0.6 → 0.82, into the measured gap
  (the certificate's signature).
- **D1** `2b31497`: the words that placed a Cell kept as its second
  `Reading`, engine `tesseract`.
- **The second pass's repairs** `a78513f`: a Conversion that locates
  twice, and a rederive of a rederive, draw what the first pass drew.
- **D2** `a0d73c9`, `ladder` and `Conversion._climb_ladders`: a Cell
  whose two readings are 1–4 characters apart is read a third time, and
  two of three settle it. On the sweep: 56 asked, 7 repaired, 8 disputed.
  **A disputed Cell is drawn as the page prints it**, its other readings
  in its title (Alessandro, 2026-10-22).
- **D3**, recorded: nonlatin's footer names another company, 18
  characters away. No near-miss rule reaches it.

**The sweep, `S14-sweep`** (commit `a0d73c9`, 2h38m, 811 calls):
- the prediction held to the byte;
- **fourteen pages better, seven the same, none worse**;
- the replay and the rederive of it each reproduce it, 21 of 21.

### Spec 0018 — the strip, photographed pages, the straightening step, 2026-10-19

Part 0 (the render re-photographed, the scorer in the paper's frame, the
box pictures), A1 (ink against its local ground), B0 (the twins), B1 (a
card's edge two lines deep) and C1 (an outline holds the page) shipped.
A2, C2 and C4 were dropped, and C3 skipped. `S13-sweep` drew three pages
better and none worse; it is `s13-result/`. The spec's outcome has each
step.

### Earlier

Specs 0008–0017 and the corpus widening: each spec's "Outcome" sections,
and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — the level-up plan, decided 2026-10-24

**Alessandro cleared every open item on 2026-10-23**, spec 0019's four
ranked directions included. They stay in the spec's outcome, as record.

**On 2026-10-24 he decided the level-up plan**
([`level-up.md`](level-up.md) §8). Its aim is conversion that holds on
pages nobody has tuned on, not a better result on the 21. A probe on ten
never-seen pages ([`level-up-probe/`](level-up-probe/README.md)) found a
structural fault on 9 of 10, against 0 of 6 tuned pages drawn at random,
judged the same day.

In order (`level-up.md` §6):

1. **L1a — the variability, agreed 2026-10-24** (§4.7, table 3): the
   eight families, tilted toward forms, receipts and doctors' notes;
   English, Italian, French and the other Latin languages; one page per
   document; figures in.
2. **L1b — the corpus, done 2026-10-30**
   ([spec 0020](specs/0020-the-corpus.md), issue #43 closed). 631 pages,
   every one passing its validator:
   - 573 written by Claude from cards drawn inside the agreed bounds.
     130 of them are parts of a document and 50 are fragments
     (Alessandro, 2026-10-25 and 2026-10-27).
   - 27 real PDF pages, each with an HTML twin admitted by a gate. He
     stopped them there on 2026-10-27.
   - The 21 and the ten probe pages, carded by hand.

   The fewer PDF pages and the parts differ from the plan. He accepted
   both on 2026-10-30, and `level-up.md` §8 records it as decision 7.

   They are dealt into dev (231), panel (200) and vault (200), and the
   L3 set is 41 panel pages (36, and the five PDF pages not dense,
   Alessandro 2026-11-08). `doc_to_html.corpus.names("dev" | "panel" |
   "l3")` returns a pool, and the vault refuses unless unsealed.
3. **L2 — measurement and the judge, done 2026-11-07**
   ([spec 0021](specs/0021-measurement-and-the-judge.md), issue #44
   closed). It built:
   - the checks, from the HTML of both sides: words, cells, structure,
     order, lines, height, beside, overprint, alignment, type, looks and
     rules;
   - the batch runner, with a 20-minute page limit and a 3-minute call
     limit, and one command, `tools/measure_run.py`;
   - the review skill evolved to the criteria, and the issue page, one
     issue at a time, through which Alessandro made five rounds of calls.

   Dev is converted on 98 pages. The checks still miss a group drawn
   wholly below the one printed beside it and a list torn by a gap
   (spec 0021, "Where L2 stands"): a review looks for both by eye.
4. **L3 — the honest baseline, done 2026-11-09**
   ([spec 0022](specs/0022-the-honest-baseline.md), issue #45 closed).
   Today's pipeline over the 41 pages of `corpus/l3-subset.txt`, 6.6
   hours; 37 converted, 4 timed out (a dense form, a PDF invoice, two
   card grids). Claude reviewed every page; Alessandro agreed all 15
   spot checks of round 7.
   - **Every one of the 37 pages has a major fault**: 14.5 a generated
     page, 43.5 a PDF page.
   - **Three majors in four are made reading the page** (extract, layout,
     locate, rectify: 495), one in four drawing it (render and the cv
     passes: 156).
   - The ranked classes, in the spec's outcome: words lost and invented
     (24 pages each), side by side drawn as a stack (13), fills split per
     Zone (12), numbers as bullets, ticks lost, misreads, bold and sizes.
   - Six check issues the review found are fixed and pinned on dev.
5. **P1 — the parser-first PoC, next: spec 0023**, from spec 0022's
   last prompt, on its own branch: GLM-OCR's latest, whole pipeline (its
   layout model and its reader), then an adapter into the IR, then our
   looks and renderer, against L3-baseline class by class. **Local
   models only.**
6. **P2 — the decision**, then **L5 — fit what is left** instead of
   setting it by hand.

Each step gets its spec and issue when it starts. Pick up nothing outside
this plan unless he names it.

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
  `s5-result/`, `s6-result/`, `s7-result/`, `s8-result/`, `s9-result/`,
  `s10-result/`, `s11-result/`, `s12-result/`, `s13-result/` — all kept as
  record — and **`s14-result/`, the baseline** since 2026-10-23,
  twenty-one documents.
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
- **A disputed Cell is drawn as the page prints it** — Alessandro,
  2026-10-22. Its other readings go in its title and `data-alt`, never a
  ground or a mark the page does not print.
- **A second pass draws what the first drew.** `tools/rederive.py` over
  its own output reproduces it, 21 of 21. A Conversion locates a second
  time after a third reading changes a Cell, so a step that cannot read
  its own output breaks a run, not only the loop.

## Measured and not shipped — record, not a queue

Spec 0019's, each in its outcome:
- **A1's rule as worded** — a container only if the page draws it or it
  holds ink its parts do not. It measured 0.726 on the jitter check and
  moved 13 pages as shot, because a paragraph over its own lines fails
  both tests.
- **D1's second reading as every word in the box.** tesseract's reads of
  texture and rules beside a figure (`216.08 &ta`) put 471 Cells on the
  model's side. The run that placed the Cell is the reading.
- **`spans.read` before `raised`.** The grid's rules carry no Zone until
  `furniture.place`, so the timetable lost its grid. It runs after
  `furniture.place`.
- **A disputed Cell flagged** with a tinted ground and an orange
  underline (the render's drawing until D2). It flagged five pages and
  hid cv's email on its sidebar (`S19-D2-targeted`). It is drawn plain.

Earlier specs':

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
    --documents sweep --previous tests/frozen/s14-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
python tools/twins.py debug/twins --check     # rectify + layout front on the twins, ~13 min, no model
python tools/layout_front.py <out> --documents all --jitter   # Zones kept under four invisible perturbations, no model
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**A sweep outlasts a two-hour background task** — `S7-sweep` took 2h16m,
`S8-sweep` 2h12m, `S9-sweep` 2h16m, `S10-sweep` 2h21m, `S11-sweep` 2h22m,
`S12-sweep` 2h22m, `S13-sweep` 2h20m, `S14-sweep` 2h38m (811 calls). Start it detached and wait on its log, and **never edit
`tools/iterate.sh` while a sweep is running**: bash reads the script as
it goes, and `S8-sweep`'s script died after its bake-off on a line the
edit had shifted:
`nohup env PATH="$PWD/.venv/bin:$PATH" FIXTURE=sweep sh -c 'tools/iterate.sh <label>; echo "SWEEP EXIT $?"' > <log> 2>&1 & disown`.
A document that raises keeps its answers in the dump, and `tools/replay_run.py`
converts it once the bug is fixed, with no model call.

**Three offline loops, each proved before it was used, and a sweep. Say which
produced any number you report.** Start them from the baseline,
`tests/frozen/s14-result/`. On 2026-10-23 `tools/replay_run.py` and
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
