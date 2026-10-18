# Status — 2026-10-18 (**the baseline is `tests/frozen/s12-result/`; spec 0017 built, render only, Alessandro's decision pending**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-10-18,
after spec 0017's two render steps (issue #40), built on spec 0016's
sweep `S12-sweep`, which Alessandro took as the baseline the same day.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file, then
[`specs/0017-margins-and-roles.md`](specs/0017-margins-and-roles.md),
the open spec, built and awaiting his decision, and
[`specs/0016-one-grid-one-strip.md`](specs/0016-one-grid-one-strip.md)
for the ticket's history. If you are going to
look at output — and you should — use the **`visual-review` skill**.

Branch `scaffold`. **1247 tests pass (1 skipped), `mypy src/` clean** — at
`24b635c`, 2026-10-18.

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
              DECIDED 2026-10-14: S9-sweep the baseline, frozen as s9-result/
Spec 0014   Every printed line has a place — issue #37
              1 Zone.extra DONE  2 read what nobody read DONE
              3 copies alike by the Kind that keeps most — built,
                the catalogue worse: DROPPED, Alessandro 2026-10-14
              S  S10-sweep on a53f11b, 2026-10-15: prediction held to
                 the byte; 3 pages better, 18 same, none worse
              DECIDED 2026-10-15: S10-sweep the baseline, frozen as s10-result/
Reset       2026-10-15, Alessandro: everything not in spec 0015 cleared.
Spec 0015   Every line read, and drawn where the page puts it — issue #38
              ticket and certificate the focus
              1 read the lines nobody reads  2 pairs as the page prints
              them  3 side by side where the page puts it — each DONE,
              judged by eye
              S  S11-sweep on 6b1caf4, 2026-10-16: prediction held to
                 the byte; 6 pages better, 15 same, none worse
              DECIDED 2026-10-17: S11-sweep the baseline, frozen as s11-result/
Reset       2026-10-18, Alessandro: everything not in spec 0016 cleared.
Spec 0016   Structure first — one grid, one strip — issue #39
              the ticket's layout the focus, structure not words:
              1 one column grid per line-drawn Zone      DONE
              2 one grid across side-by-side Zones       DONE
              3 a drawn strip is one container           DONE
              4 4b/4c, two locate guards                 DONE
                4a no Zone from a fill's edge — the ticket's re-reads
                lost words; DROPPED, Alessandro, with the crop fix it
                called for (the timetable's legend twice)
              S  S12-sweep on 3abb55d, 2026-10-18: prediction held to
                 the byte; 1 page better (ticket), 20 same, none worse
              DECIDED 2026-10-18: S12-sweep the baseline, frozen as s12-result/
Spec 0017   Margins from the type, one size per role — planned 2026-10-18
              from his review of S12-sweep's ticket, issue #40; render
              only, measured by rederive over s12-result/:
              1 margins from the type (1a row inset, 1b box to type)  DONE
              2 one size per role (2a groups, 2b Title as a label)    DONE
              ticket better, catalogue same (1px), nineteen identical
              DECISION PENDING; directions 3 and 4 (photographed pages,
              Zones from drawn containers) a spec of their own after it
```

Each spec has an "Outcome" per step; Q1-Q4's and N1-N3's result tables are
in [`specs/0007-handover.md`](specs/0007-handover.md).

---

## The baseline — `tests/frozen/s12-result/`, DECIDED 2026-10-18

**Twenty-one documents, 749 answers**, byte-identical to `s11-result/`'s.
Sweep `S12-sweep`, commit `3abb55d` (spec 0016 step P; code `c98f2db`),
2026-10-18 16:07 to 18:30 (**2h22m**), shipped defaults. Alessandro took
it after review: against `s11-result/`, the ticket better, twenty the
same, none worse; no ratchet leg fell.

Proved on 2026-10-18, at `c98f2db`'s code:
- `tools/replay_run.py tests/frozen/s12-result`: **21 of 21
  byte-identical, 0 asked differently**;
- `tools/rederive.py` over it: **21 of 21 byte-identical files**;
- the rederive scored: **21 documents, 0 differing fields** against its
  `scores.json`;
- its 749 answers against the sweep's `trace.json`: 0 differ.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s12-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five.

### The baselines before it

- **`s11-result/`** — spec 0015's sweep, `S11-sweep`. The baseline
  2026-10-17 to 2026-10-18. `S12-sweep` answered its 749 calls byte for
  byte and asked nothing else.
- **`s10-result/`** — spec 0014's sweep, `S10-sweep`. The baseline
  2026-10-15 to 2026-10-17. `S11-sweep` answered its 735 calls byte for
  byte and asked fourteen more.
- **`s9-result/`** — spec 0013's sweep, `S9-sweep`. The baseline
  2026-10-14 to 2026-10-15; `S10-sweep` answered its 732 calls byte for
  byte and asked three more.
- **`s8-result/`** — spec 0012's sweep, `S8-sweep`. The baseline for
  2026-10-14 until spec 0013's sweep.
- **`s7-result/`** — the first sweep over twenty-one, `S7-sweep`. The
  baseline 2026-10-13 to 2026-10-14.
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

Means over `s11-result/`, against `s10-result/`:

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.982 → 0.990 | 0.991 → 0.991 | 0.960 → 0.988 |
| precision | 0.988 → 0.989 | 0.988 → 0.988 | 0.988 → 0.989 |
| join recall | 0.951 → 0.961 | 0.965 → 0.965 | 0.914 → 0.949 |
| tau | 0.949 → 0.977 | 0.990 → 0.990 | 0.847 → 0.946 |
| beside agreement | 0.757 → 0.837 | 0.849 → 0.877 | 0.528 → 0.737 |
| height ratio | 1.074 → 1.045 | 1.029 → 1.028 | 1.186 → 1.089 |
| alignment agreement | 0.802 → 0.799 | 0.840 → 0.844 | 0.705 → 0.686 |
| scale error | 0.220 → 0.227 | 0.154 → 0.165 | 0.383 → 0.383 |

Moved: ticket, certificate, catalogue, timetable, sample_semantic,
invoice_0002, cv. The fifteen's scale error is the catalogue's: its
three prices placed by inference are drawn small.

**`vanished`: 33 → 26 words.** Back: the ticket's gate note (`gate` was
already printed elsewhere, so five words) and `osl`, and the timetable's
`lunch`. No word is newly vanished.

---

## What the last work shipped

### Spec 0017 — margins from the type, one size per role, 2026-10-18

**Render only, no sweep.** `tools/rederive.py` over `s12-result/`
(`S13-1`, `S13-2`), against `S12-sweep`'s renders, by eye. Every IR is
byte-identical to the baseline's.

- **Better: the ticket.** The field grid sits 22px in from the card's
  edge and the stub's text 20px off the perforation (step 1);
  `PASSENGER` is a muted label as in the stub, `NL 0482` is drawn at its
  row's 1.50, and the stub's values are one size (step 2).
- **Same: the catalogue**, one line 1px lower. **Nineteen byte-identical.**
- Step 1's first version moved five more pages, three for the worse —
  `paper_0018`'s centred title, `sample_semantic_0005`'s bullets,
  `cv_0013`'s `REGISTRATION` — each closed off by an exclusion (spec 0017).
- Commits: 1 `1c869fd`, 2 `24b635c`.

### Spec 0016 — structure first, `S12-sweep`, 2026-10-18

**Against `S12-0-replay`: one page better, twenty the same, none
worse.** Commit `3abb55d`, 749 calls, 2h22m. §7's prediction held to the
byte: every call asked and answered as `s11-result/`, sixteen pages
byte-identical to it, the other five as steps 1–3 draw them. Taken as
the baseline, `s12-result/`, 2026-10-18. Issue #39 closed.

- **Better: the ticket.** Its grid columns keep one edge; `TRD` flush
  right on `OSL`'s line and a four-column grid with `DEPARTS` / `CLASS`
  over their values; one teal strip with `BOARDING PASS` on one line;
  the stub opens on its strip.
- **Left on it:** the halo Zone `The` / `The` on the strip, now inside
  the one strip at twice the page's height, and `TRD` at Title size —
  both step 4a's, dropped.
- **Same:** catalogue and invoice_0002 move a few pixels (step 1's
  shared column edges); cv and form pixel-identical.
- **Scores, recorded:** the ticket's tau 0.843 → 0.947, beside 0.262 →
  0.393. `vanished` 26 → 26.

What shipped, one commit a step:
- 1 `34b0d97` `render._placed`: one set of column edges per Zone
  (`_aligned`, `_edges`), minmax tracks, no `auto` track, a lone entry
  wraps;
- 2 `c8fe221` `render._one_grid` / `_grid_unit` / `_title_line`: unframed
  side-by-side pairs Zones sharing two printed lines drawn as one grid,
  Titles as lines; `_habit`, an unplaced label over its value where the
  page's every placed pair is so;
- 3 `dba3591` `render._filled`: a solid fill holding rows drawn once
  behind them; `furnish.Anchors.bands`, a fill across a Zone's top as its
  band; `render._heading_size`;
- 4 `b03555e`, `c98f2db` `locate.display_words` (a one-character word
  blocks nothing) and `locate._from_lines` (a claimed line boxed by all
  its words). 4a and the crop fix: measured, dropped — below.

### Spec 0015 — every line read, and drawn where the page puts it, `S11-sweep`, 2026-10-16

Taken as the baseline, `s11-result/`, 2026-10-17. Issue #38 closed.

**Against `S11-0-replay` (`s10-result/` replayed at the code the spec
began on): six pages better, fifteen the same, none worse.** Commit
`6b1caf4`, 749 calls, 2h22m. §6's prediction held to the byte: all
735 calls `s10-result/` asked were answered alike, fourteen re-reads
fell where registered, and every page was byte-identical to its
predicted render.

- **Better:** the ticket (the stub a pane of its own, the field grids
  as grids, `OSL` and the gate note printed, `OSLO GARDERMOEN` under the
  name); the certificate (its signature row one line, three lanes); the
  catalogue (nine cards alike); invoice_0002 (the panels at the page's
  widths); sample_semantic (TL;DR at the page's width, `Tags:`
  printed); the timetable (`Lunch` printed).
- **Left on the two focus pages:** the ticket has no display type for
  `OSL` and `TRD`, its header bar is in pieces with the `The` strip,
  and its stub header and barcode are missing. The certificate has its
  seal as a text chip, its names flush left under centred rules, and
  black stars. The spec's "Outcome — the sweep" has §1's tables row by
  row, the faults by stage and the directions ranked — record only,
  cleared on 2026-10-18.
- **Ratchet, reported:** the timetable's tau 0.963 → 0.954 and beside
  0.992 → 0.984, both from `Lunch` drawn under the grid instead of in
  its row.

What shipped, one commit a step:
- 1 `3e35c27` `locate.unclaimed` widened: one-word lines, claims by
  half the words and half their letters, a display read at the page's
  scale, a crop that stops short of claimed words (`Unclaimed.reach`),
  and the guard `locate.holds` after the call. `tools/replay_run`
  compares calls by hash wherever they fall;
- 2 `b48b7b2` `render._printed_lines` by position, entries with no box
  placed from their mates' column or before the next entry, a lone label
  drawn as a line, extra lines among the printed lines; `3c5e365`
  `locate._from_lines` places an extra line on the line it claims;
  `357b183` an extra heading set like the body is drawn as a line;
- 3 `a8bc381` a band's units take the page's lanes (`render._lanes`,
  extent = box, frame and anchored rules), and a drawn divider reaches
  what it parts (`structure._columns`).

### Spec 0014 — every printed line has a place, `S10-sweep`, 2026-10-15

Taken as the baseline, `s10-result/`, until 2026-10-17.
**Against `S10-0-replay` (`s9-result/` at the code it began on): three
pages better, eighteen the same, none worse.** Commit `a53f11b`, 735
calls, 2h21m. §7's prediction held to the byte: all 732 calls
`s9-result/` asked answered alike, three re-reads beyond them, every
page as predicted. The unclaimed list is empty on all 21.

- **Better:** the form's note under its tick boxes; the ticket's `OSLO
  GARDERMOEN` (at the foot of its Zone, not under the name); the
  timetable's legend on one line under its grid.
- **Ratchet, reported:** the ticket's tau 0.282 → 0.238, from that
  line's place. `vanished` 41 → 33, nothing gone.

What shipped, one commit a step:
- 1 `ir.Zone.extra`: lines a Zone's Kind has no place for; `cells_of`
  yields them last; `render._zone_body` draws them before or after the
  body;
- 2 `Conversion._read_unclaimed`: each line `locate.unclaimed` flags is
  read on its own crop with the prose prompt, kept unless the Zone
  already prints the line (`locate.holds`); `tools/replay_run` counts a
  pass's calls, so a swallowed new call is marked ASKED MORE;
- 3 copies alike by the Kind that keeps most — **built and dropped**:
  prose lost five of the catalogue's code badges and its price rows'
  spread, and darkdeck's tiles are four `pairs` when copies are read
  alike, so it never reached them.

### Spec 0013 — four pages first, `S9-sweep`, 2026-10-14

Seven pages better, thirteen the same, the ticket worse; taken as the
baseline, `s9-result/`. Its "Outcome — the sweep" has the detail.

### Earlier

Specs 0008–0012 and the corpus widening: each spec's "Outcome" sections,
and `specs/0007-handover.md` for the A phases and the queue.

---

## Next — nothing open

Spec 0016 is done and `S12-sweep` is the baseline. Every other item was
cleared on 2026-10-18 and none is queued until Alessandro names it.

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
    --documents sweep --previous tests/frozen/s12-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**A sweep outlasts a two-hour background task** — `S7-sweep` took 2h16m,
`S8-sweep` 2h12m, `S9-sweep` 2h16m, `S10-sweep` 2h21m, `S11-sweep` 2h22m. Start it detached and wait on its log, and **never edit
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
