# Status — 2026-09-29 (the open-issues queue: **Q1–Q4 done, Q5 next**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-09-29, when
Q4 of the open-issues queue closed.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **813 tests pass, `mypy src/` clean** — 26 fewer than Q3's
839, each a test of the vision layout pass Q4 deleted.

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
              Q1 DONE 2026-09-27, offline, gate MET
              Q2 DONE 2026-09-28, offline, gate MET
              Q3 DONE 2026-09-29, offline, RE-SCOPED, gate MET
              Q4 DONE 2026-09-29, offline, no output change, gate MET
                                                                   Q5 <- next
Thread 3/C  Repair loop (re-scoped first)
Thread 4/D  Human corrections (unscheduled)
```

---

## The floor — `tests/frozen/a3-result/`, DECIDED 2026-09-26

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a3-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five and says nothing about the other ten.

**It moved from `a2-result` at A3's close, on measurement.** `a3-result`
dominates it per document on every ratcheted leg — rises on 2 (precision),
1 (tau) and 1 (beside), falls on none — and the set of source words not
printed is identical on all fifteen.

**The floor stays here — decided 2026-09-27.** Open issues 1–3 hold against
it on all four legs for all fifteen, and were not frozen as a new floor.

**Its scores are the ratchet; its IRs are older than the code.** Scored
straight out of the directory, **0 differing fields**. A plain re-render no
longer reproduces its documents — `"header_fill":null` is in every IR now, and
issues 1–3 changed what the code makes of the same answers. **The baseline
for any change is `python tools/rederive.py tests/frozen/a3-result --label
<label>`**, which reproduced the arm issues 1–3 were gated on byte for byte on
all fifteen. Its README has the rest.

### What the ratchet enforces, per document

`report._ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside a failure to say how far it fell. **The
floor never falls for any reason.**

---

## Where the corpus is — at the floor

| | mean |
|---|---|
| vocabulary recall | 0.8667 |
| recall (multiset) | 0.8542 |
| precision | 0.9851 |
| join recall | 0.8225 |
| tau | 0.9483 |
| beside agreement | 0.7458 |
| height ratio | 1.4791 |
| `hard_breaks` | 5, all real address breaks |
| `figures_lost` | **0** |
| T6 inline runs | 8 of 42 |

### The live faults, worst first

**1. Some documents lose most of their words.** Four documents print every
source word; these lose the most:

| document | words kept | declared? |
|---|---|---|
| `receipt_0010` | **19.8%** | yes — its table is flagged 19 lines printed, 2 read |
| `catalogue_0015` | 61.7% | **no** |
| `form_0007` | 77.7% | **no** |
| `menu_0012` | 82.8% | no |
| `statement_0006` | 88.1% | no |

A3's visual review names what is gone, in this session's pictures:
`catalogue_0015`'s prices and stock notes and its title `Hardwood fittings`;
`form_0007`'s section headings `2.`–`5.`; `cv_0013`'s name `Ines Halloran`;
`darkdeck_0009`'s captions `OPEN RISKS` and `DECISIONS WANTED`;
`report_0011`'s `TABLE 1 — MOVEMENTS AND REVENUE BY BERTH`.

A-1 established the pipeline can declare *structural* loss and cannot declare
loss *inside a line*, and that two pixel-side detectors were built and
rejected. **Do not build a third without a new kind of evidence.**

**2. Side-by-side content stacks** — `form_0007` 0.059, `catalogue_0015`
0.288, `menu_0012` 0.349, `newsletter_0008` 0.476, `cv_0013` 0.500. A2
established that most of it is **inside one Zone**, so no renderer reaches it;
see "Closed, with evidence".

**3. Height.** `statement_0006` 2.78, `menu_0012` 2.29, `cv_0013` 2.06,
`newsletter_0008` 1.99 — a symptom of 1 and 2. **Body type is 16px on every
page** where the sources set 11–16px; Q3 measured why that stays for now,
and its heading sizes bring `cv_0013` to 2.01 and `newsletter_0008` to 1.88,
measured offline.

**4. Invented and doubled text.** `nonlatin_0014` at precision 0.914: misread
Greek, three pairs read twice, and the total `12.437,82` printed twice.
Everything else is at 0.961 or better.

**5. Reading order** wobbles on `newsletter_0008` (0.832) and `darkdeck_0009`
(0.836). `menu_0012`'s 0.829 at the floor is 0.956 with Q1, measured offline.

---

## What the last step shipped

### The queue so far — each offline, one change apart, against `rederive.py`'s baseline

**The baseline, proved before use:** `python tools/rederive.py
tests/frozen/a3-result --label Q-00-base` holds the ratchet on four legs for
all fifteen; `statement_0006` carries 3 caveats; `header_fill` sits on exactly
`nonlatin_0014` z4, `statement_0006` z3, `invoice_0001` z4 and z5;
`darkdeck_0009` z2 has no Title.

**Q1 — `menu_0012`'s section headings, 2026-09-27, gate MET.** `render._table`
now leaves a header row with data rows on both sides where it is, inside
`<tbody>` as `<th>` cells; any other header row still goes to `<thead>`.
Renderer only — no IR change, no `STYLESHEET` change, so `rederive.py` gains no
step.

| clause | result |
|---|---|
| `menu_0012` z1: `From the grill`, `Main courses`, `Puddings` each directly above its first dish; no `<thead>`; embedded IR byte-identical | 3 of 3 |
| `sample_table_0003`: header still in `<thead>` above `United States`; file byte-identical | yes |
| the other 13 byte-identical to the baseline, whole file | 13 of 13 |
| ratchet vs `a3-result`, four legs, fifteen | holds |
| `menu_0012` score fields that moved | tau 0.829 → **0.956**; `ink_delta` 0.345 → 0.314, `output_ink`, `output_texture` (the grey band left the screenshot); `column_error` 0.0688 → 0.0693. Words, joins, beside and height unchanged. |
| visual review, all fifteen, `--previous` the baseline | `menu_0012` `better`, 14 `same`, no `worse` |
| tests, mypy | 828 pass, clean |

**Q2 — `statement_0006`'s empty seventh column, 2026-09-28, gate MET.** Baseline
`Q-10-base`: `rederive.py` at the Q1 commit, byte-identical to the Q1 arm on
all fifteen.

**The description was wrong, and the IR said so.** The header was never read
a cell wide: the model read it six wide, like every row, and returned the
caption `Transactions in date order` as a first header row **seven** wide.
`rows_from_table` takes the width from the first header, so the real header
and all forty rows were padded to seven — and then `_without_title_echo`
dropped the caption row as an echo of the Title, leaving the padding behind.
The proof is in the IR: the header's own seventh cell carries no Reading.
`statement_0006` z3 was the only table in the corpus with a padded cell.
`receipt_0010`'s twenty-cell row is a different fault — every cell was read,
nineteen of them empty, the model's own answer — and **went to Q5 by
decision**, since Q5 re-reads that crop.

`wire.repadded`, called where `_without_title_echo` drops a table's first row:
the trailing Reading-less Cells come off and each row is padded again against
the header that is left. Nothing read is removed; where no row was dropped it
returns every row unchanged. **`tools/rederive.py` applies it to every table**
(step 1).

| clause | result |
|---|---|
| `statement_0006` z3: header 7 → 6, 40 data rows 7 → 6, 0 Reading-less cells (was 41); summary row, all 42 rows and every read cell's text unchanged | yes |
| `statement_0006` caveats 3 → 2, the padding sentence gone; probes, `header_fill`, Shortfalls unchanged | yes |
| the other 14 byte-identical to the baseline, whole file | 14 of 14 |
| ratchet vs `a3-result`, four legs, fifteen | holds |
| `statement_0006` score fields that moved | `height_ratio` 1.577 → 1.546, `alignment_agreement` 0.935 → 0.968, `output_texture`. Words, joins, tau, beside and column fields unchanged. |
| `contents_into` test and a replayed `sample_table_0003` Conversion with a caption row one cell wider than its header | both pass |
| visual review, all fifteen, `--previous` the baseline | `statement_0006` `better`, 14 `same`, no `worse` |
| tests, mypy | 830 pass, clean |

**Q3 — the type scale, re-scoped to heading sizes, 2026-09-29, gate MET.**
Baseline `Q-20-base`, `rederive.py` at the Q2 commit, byte-identical to the Q2
arm on all fifteen.

**Re-scoped on measurement, by decision.** The full type scale was measured
with the answer in hand — today's IRs re-rendered at each source's own CSS
sizes, the ceiling any estimator could reach — and **crosses the T1 ratchet
in every form but one**: body type on 3 documents, Titles and headings on 1,
both on 2, all on T3 `beside`. Only shrinking oversized heading Blocks holds.
`style.py`'s module docstring has the table and the mechanism.

`style.heading_sizes`, run by `Conversion._measure_type` after
`_measure_chrome` and by `tools/rederive.py` through `remeasure`: a Zone's
leading heading Block, its line's 90th-percentile glyph height over the page's
median, recorded as the new `Block.size` in ems when below 1.44em (0.9 of the
`h1`'s 1.6em, in the empty band between 20.4px and 24.9px measured over all
fifteen). `invoice_0002`'s "75px band" was the ACME tile's edge inside the
crop inking every row — `type_lines` clears such a wall only when the band is
several lines tall, and parts touching lines only into pieces of one size.

| clause | result |
|---|---|
| exactly 8 heading Blocks on 5 documents sized, each within ±30% of the source's own size | 8: `catalogue_0015` `AUTUMN LIST…` 0.74em, `cv_0013` both job titles 1.00em, `darkdeck_0009` `Q3 2026 · INTERNAL` 0.84em, `invoice_0002` `Acme Corporation` 1.00em and `Services / Products` 1.27em, `newsletter_0008` `VOL. CLII, NO. 31` 0.78em and the drop-cap line 1.16em. Each 0.74–1.18 of its source's own size in ems. |
| no other heading Block sized | yes |
| the other 10 identical outside the IR; inside, by the new key alone | 10 of 10; the 5 touched IRs also differ by the key alone |
| ratchet vs `a3-result`, four legs, fifteen | holds |
| `darkdeck_0009` beside vs baseline, agreed in advance | 0.978 → 0.968 — `Platform review` beside `Q3 2026 · INTERNAL`, held only by the oversized label; floor 0.875 |
| no named document further from height 1 | `cv_0013` 2.058 → 2.009, `invoice_0002` 1.476 → 1.436, `newsletter_0008` 1.994 → 1.878; the other two unchanged |
| unit, render and replayed-Conversion tests | pass — `invoice_0001` replayed with its sender's address opened by a heading: sized at body size |
| visual review, all fifteen, `--previous` the baseline | 5 `better`, 10 `same`, no `worse`; `type` majors 4 → 1 |
| tests, mypy | 839 pass, clean |

**What moved that the gate did not name, and why.** `catalogue_0015`'s T5
`output_ink` flipped from near-black to light grey, `ink_delta` 0.031 →
0.627, with no colour on the page changed. T5 takes the modal marked pixel of
a **600px thumbnail**; the 25.6px `AUTUMN LIST…` was what kept solid ink the
mode, and at its measured size antialiased greys outnumber it 347 to 328. T5
measured type size there, not colour.

**Q4 — Thread 0's leftover seam, 2026-09-29, gate MET.** Baseline `Q-30-base`,
`rederive.py` at the Q3 commit, byte-identical to the Q3 arm on all fifteen.
Agreed scope: **the whole retired vision layout pass**, not only the two names
the brief gave — with `LAYOUT_PROMPT` gone, `DTH_LAYOUT_REGION_HINT` would
have been a flag read and acted on by nothing.

**What went.** `OllamaEngine.detect_zones`, `LAYOUT_PROMPT`, `with_regions`;
the wire schema `LayoutResponse`/`WireZone` with `zones_from_layout` and its
box check; the Orchestrator's region-ceiling rescue (`_region_ceiling`,
`_layout_again`); `DTH_LAYOUT_MODEL`, `DTH_DERIVE_BANDS`,
`DTH_LAYOUT_REGION_HINT`; `OllamaEngine.layout_long_edge` and
`preprocess.LAYOUT_LONG_EDGE`; `region_ceiling` off `LayoutEngine` and the
detector. None reached a Conversion after Thread 0, so they were removed
rather than refused by name — `config.py`'s retirement paragraph says so.
**What stayed:** `bands_from_boxes`, `validate_bands`, `GRAPHIC_KINDS` (the
detector and Orchestrator use them), and `count_regions` as a ruler.

**What replaced it.** The recorded-response suite hands the layout stage
fixed Zones: `tests/replay.py`'s `FixedLayout` serves each fixture's
`tests/responses/<fixture>/geometry.json`, frozen from its `layout.json`
through the old mapper and round-trip equal on all five.
`convert_recording(image, replies)` finds a fixture's geometry from its
image; `engines_replaying(transport, geometry(fixture))` names it.
`tools/record_responses.py` writes `geometry.json` and derives the committed
five exactly. Tools: `inspect_run.py` reads an old dump's layout answer as
plain JSON and draws the page whole by default; `cloud_probe.py` lost its
layout question; `iterate.sh` no longer stamps `layout_long_edge.txt`.

**How "no output change" was proved with no model.** The production
Conversion was run over all fifteen with every model call refused — the real
detector and every model-free layout stage, shipped defaults, each Zone a
skeleton — in 11 seconds. At the Q3 commit it was byte-identical across two
runs and **reproduced `a3-result`'s Zone band, column and bbox on 15 of 15**,
so it is the production layout path, not an approximation of it. **It is
committed as `tools/layout_front.py`** — the same run, writing the absolute
source path a sweep records — for the next change that moves boxes (Q6).

| clause | result |
|---|---|
| production, refused-model Conversion, fifteen: `document.html` byte-identical to the Q3 commit | 15 of 15 |
| its `trace.json` identical but for `seconds`, the `measure_regions` record and the `long_edge` key | 15 of 15 — and every later record's `seq` one lower, since the list is one record shorter |
| replay, the five recorded fixtures: `document.html` byte-identical to the Q3 commit | 5 of 5 |
| `rederive.py` from `a3-result`, whole file, against `Q-30-base` | 15 of 15; 0 score fields differ |
| ratchet vs `a3-result`, four legs, fifteen | holds |
| the removed names in `src/`, `tools/`, `tests/`, `.env.example` | only `config.py`'s retirement paragraph; `test_lenient.py` keeps a local copy of the schema, renamed `RegionsResponse`, because its real cloud answers were taken against it |
| tests, mypy | 813 pass (839 less 26 deleted, each a test of the deleted pass), clean |
| visual review | replaced, by agreement, by the byte identity above |

**Deleted tests, each a test of the pass itself:** the region-ceiling rescue
(15 of `test_region_ceiling.py`'s 18; its 3 ruler tests are
`test_region_ruler.py`), 8 in `test_tracer_bullet.py` (the layout downscale,
two box checks, three graphic/title checks of the mapper, a layout returning
no Zones, geometry corresponding to nothing), and one prompt-wording or budget
test each in `test_table_extraction.py`, `test_pairs_and_prose.py` and
`test_list_and_figure.py`. **Re-pointed, assertion kept:** the Band checks
now call `validate_bands` and `bands_from_boxes` on Zones directly, the
truncation tests go through the classify pass, and "the vision model satisfies
`LayoutEngine`" became "`FixedLayout` does".

### Open issues 1–3 — 2026-09-26, offline, one change apart

Each was measured against `a3-result` with no model call: the floor's IRs
re-derived through the changed code and re-rendered. The ratchet holds on all
four legs for all fifteen after each change. Visual review of the three
together against the control: 3 `better`, 12 `same`, no `worse`. The record
is [`specs/0007-handover.md`](specs/0007-handover.md), "Next", section
"Outcome". **Every rule is also proven inside a replayed Conversion.**

| change | what it fixes |
|---|---|
| `wire.table_repairs` names rows repaired the same way in one sentence | `statement_0006`'s caveat panel, 43 lines → 3, so the statement starts on the first screen. A one-row repair keeps its old wording. |
| `Zone.header_fill`, measured by `style.chrome` on the band `preprocess.header_band` finds under a row named `RowRole.header`; `_measure_chrome` now runs **after** `_extract` | header rows drawn in the source's fill — `nonlatin_0014` white on `#1c4f7c`, `statement_0006` on `#16202b`, `invoice_0001` `#eee`. Before `_extract` no Zone has rows, so the stage could not have fired where it was. |
| `wire._title_is_its_header_cell` — a table's Title that spells the first cell of its own multi-cell header row is dropped, the row kept | `darkdeck_0009` printed `AVAILABILITY` as a caption directly above the same word as the metric row's first label. 1 of 47 titled Zones. |

**Two corrections this made to what the docs said.**

- **The `AVAILABILITY` echo was never across Zones.** It is Zone 2's own
  Title, lifted by the caption pass off the first cell of Zone 2's own header
  row; `CaptionBand.aligns_to_grid` missed it by counting the letter-spaced
  labels as 7 columns against the values' 6. The only word a titled Zone of
  the floor shares with another Zone is Zone 9's column header `AVAILABILITY`,
  which the source prints too. **No across-Zone echo is measured on the
  floor** — `menu_0012`'s `To begin` was an enclosed Zone, closed in A2.
- **T5 samples the whole screenshot, findings panel included**, although the
  projection excludes the panel. Shortening `statement_0006`'s panel moved its
  `output_ink` and `ink_delta` (0.419 → 0.199) as well as its height — a gate
  clause predicting only the height was wrong as written.

**The floor stays `a3-result` — decided 2026-09-27.** The three changes are
downstream of the model, so a sweep would reproduce the offline arm, and
`tools/rederive.py` rebuilds that arm from the floor on demand.

---

## Next — the open-issues queue, in order — **go given 2026-09-27**

**Alessandro's plan, 2026-09-27: work every open issue, one at a time, in
this order, in a fresh session.** The ready prompt is
[`specs/0007-handover.md`](specs/0007-handover.md), "The open-issues queue".
Model-free first, cheapest first; the three that cost model time last. **Each
gate is still agreed with Alessandro before any code.**

**Q1. `menu_0012`'s section headings stack in one `<thead>`. — DONE
2026-09-27, gate met;** see "What the last step shipped".

**Q2. `statement_0006`'s empty seventh column. — DONE 2026-09-28, gate met;**
see "What the last step shipped". `receipt_0010`'s 20-cell header row went to
Q5 by decision.

**Q3. The type scale, carrying open issue 4. — DONE 2026-09-29, re-scoped to
heading sizes, gate met;** see "What the last step shipped".

**Q4. Thread 0's leftover seam. — DONE 2026-09-29, gate met;** see "What the
last step shipped".

**Q5. `receipt_0010`'s untested lead** — the worst document in the corpus.
Model time. `preprocess.resize_long_edge` never enlarges, and this page
rectifies to **335×547**, so the extractor sees ~300px across 19 lines of
monospace. ~6 minutes to probe; a change moves crops and costs a sweep.
**Carries Q2's leftover:** its table's one row came back 20 cells wide, 19
read as empty, so `Order 00418` wraps in a narrow first column. If it survives
Q5's re-read, the fix is trimming header cells no row fills — measured to
touch this table only.

**Q6. `nonlatin_0014`'s overlapping Zones** — left open by decision in A2.
Model time. Its full-width Zone is 0.70 over the top-right pairs box and
re-reads three of its four pairs; the outside part holds `ΤΠΥ = 2026/0417`,
so dropping either box loses it. Cutting a box changes a crop.

**Q7. `invoice_0001`'s `Invoice` / `#: 123`, and A1's false mark.** Model
time. A Pair label/value boundary the Pairs Extractor chooses, and A1's one
false mark, `12345`, worth 0.0029 of `join_recall`. Both are model questions.

**Q5–Q7 touch three different documents**, so whether they share one sweep —
as A3's two changes did — is decided on entry, with Alessandro. **Start them
from a clean session with the prompt in
[`specs/0007-handover.md`](specs/0007-handover.md), "The open-issues queue,
continued — Q5 to Q7".** The first sweep after Q4 is also the first run of
`tools/iterate.sh` since Q4 edited it (it no longer writes
`layout_long_edge.txt`).

**After the queue:** the floor decision, then Thread 3/C's re-scoping gate.
Thread 4/D stays unscheduled.

**Not in the queue, deliberately:** `catalogue_0015`'s undeclared loss (no
third detector), and raising A1's clause 1, whose cheapest lever — measuring
weight and monospace off the pixels — needs word-level ink segmentation the
project does not have.

---

## Closed, with evidence — do not reopen without a new kind

All in [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md), except
the last entry.

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

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session counts.
  **The exceptions are committed files:** `tests/frozen/run84/`,
  `a1-checkpoint/`, `a0-checkpoint/`, `a0-result/`, `a1-result/`,
  `a2-result/` — all kept as record — and **`a3-result/`, the floor and the
  control.**
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
    --documents sweep --previous tests/frozen/a3-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

`iterate.sh` records `HEAD` only. **When a sweep runs on uncommitted code, save
`git diff HEAD > debug/runs/<label>/uncommitted.diff` beside it**, as A3 did.

**Three offline loops, each proved before it was used. Say which produced any
number you report.**

- **Downstream of the model** — renderer, style, wire. `tools/rederive.py
  tests/frozen/a3-result --label <base>` builds today's baseline; build the
  changed arm the same way with the change in place, score both, and pass the
  baseline as `--previous` to the visual review. **A new downstream step that
  writes the IR must be added to `rederive.py`.** Cannot move anything the
  model decided.
- **Recorded answers through the shipping mapper** — validated to four decimal
  places on 2026-09-22. Make it reproduce the floor first, every time.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
