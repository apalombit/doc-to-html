# Status — 2026-09-26 (A3 closed, gate MET; **the open issues next**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-09-26, at
A3's close, when the floor moved to `a3-result`.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **809 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
Phase A1    Inline runs, and hard line breaks   DONE 2026-09-25, gate NOT met
Phase A2    Geometry — re-scoped                DONE 2026-09-25, gate MET
Phase A3    Figure pixels                       DONE 2026-09-26, gate MET
Open issues One at a time, cheapest first                          <- next
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

**It is also the control.** Scored straight out of the directory, **0
differing fields**; re-rendering its IRs through `render()` gives **15 of 15
byte-identical**, figures included, because the IR now carries their pixels.
Its README has the recipe.

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
`newsletter_0008` 1.99 — a symptom of 1 and 2 plus the deferred type scale.

**4. Invented and doubled text.** `nonlatin_0014` at precision 0.914: misread
Greek, three pairs read twice, and the total `12.437,82` printed twice.
Everything else is at 0.961 or better.

**5. Reading order** wobbles on `newsletter_0008` (0.832), `menu_0012`
(0.829), `darkdeck_0009` (0.836).

---

## What the last phase shipped

### Phase A3 — gate MET, 8 of 8, sweep `A3-10-figure-pixels-sweep`

The record is [`specs/0007-handover.md`](specs/0007-handover.md), "Phase A3",
section "Outcome".

| change | what it fixes |
|---|---|
| `Zone.pixels`, `preprocess.figure_pixels` | a FIGURE Zone carries its own crop as a base64 PNG — the unpadded box on `Rectified.plain`, turned back over on a dark page. Embedded, decided on entry: a file beside the document would not survive the copy into `tests/frozen/`. |
| `Conversion._draw_figures` | fills it after `_classify`, every round |
| `render._figure` draws an `<img>` | `invoice_0001`'s logo and `receipt_0010`'s barcode drawn instead of dashed placeholders. What was read off a Graphic goes to `alt`, so `sparksuite` and `logo` leave the page; precision 1.000 on both. Styling is inline, so no other document's bytes move. |
| `detector.without_overreaching_pictures` | `invoice_0002`'s ACME tile was swallowed by `outermost` into a larger `picture` round the tile and its address. A `picture` holding a higher-scored `picture` *and* ink outside it is dropped first: 2,243 px outside on `invoice_0002`, exactly 0 on the only two other candidates. Changes one box on one document; tau 0.849 → 1.000, beside 0.640 → 0.854. |

Clause 4 was restated before the sweep, with evidence, and put to Alessandro:
a new `Zone` field puts `"pixels": null` in every IR, so the twelve untouched
documents are byte-identical *outside* the embedded IR and differ inside it by
that key alone. 12 of 12. Visual review: 3 `better`, 12 `same`, no `worse`.

---

## Next — the open issues, one at a time

**The ready prompt is in [`specs/0007-handover.md`](specs/0007-handover.md),
"Next — the open issues".** Ordered cheapest first: the first four need no
model call and are measured against `a3-result` offline.

1. **`statement_0006`'s 41 near-identical caveat lines** should aggregate to
   one. Ours, from A-1. Renderer / findings only.
2. **`nonlatin_0014`'s dark-blue table header row** renders on white. Do not
   build a third detector; point `chrome()`'s title-band measurement at the row
   `RowRole.header` already names.
3. **The across-Zone echo.** `darkdeck_0009` prints a caption `AVAILABILITY`
   above a table whose first column header is `AVAILABILITY`. The two Zones do
   not overlap, and `_without_title_echo` compares a Block against its own
   Zone's Title only.
4. **`invoice_0002`'s `Acme Corporation`, new at A3.** The narrowed crop reads
   the bold line as a `heading` block and the render draws every heading block
   as `h1`, so it is now the largest text in the header band, above
   `Invoice With Credit`. The source prints it at body size. Sizing a heading
   from its own ink is the deferred type scale (2/B) — say so if the fix goes
   there.
5. **`receipt_0010`'s untested lead** — the worst document in the corpus.
   `preprocess.resize_long_edge` never enlarges, and this page rectifies to
   **335×547**, so the extractor sees ~300px across 19 lines of monospace.
   ~6 minutes to probe; a change moves crops and costs a sweep.
6. **`nonlatin_0014`'s overlapping Zones** — left open by decision in A2. Its
   full-width Zone is 0.70 over the top-right pairs box and re-reads three of
   its four pairs; the outside part holds `ΤΠΥ = 2026/0417`, so dropping
   either box loses it. Cutting a box changes a crop and costs a sweep.
7. **`invoice_0001`'s `Invoice` / `#: 123`** — a Pair label/value boundary the
   Pairs Extractor chooses. **A1's one false mark**, `12345`, worth 0.0029 of
   `join_recall`. Both are model questions.

**Not in the list, deliberately:** `catalogue_0015`'s undeclared loss (no
third detector), and raising A1's clause 1, whose cheapest lever — measuring
weight and monospace off the pixels — needs word-level ink segmentation the
project does not have.

---

## Closed, with evidence — do not reopen without a new kind

All in [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md).

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

- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size. Open issue 4 may be the
  first thing it fixes.
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

- **Downstream of the model** — renderer, style, wire. Re-render
  `tests/frozen/a3-result/`'s IRs and score them; `tools/remeasure_style.py`
  does the pixel-measured fields. Cannot move anything the model decided. To
  review it visually, copy `a3-result/documents/` into a run directory and pass
  that as `--previous`.
- **Recorded answers through the shipping mapper** — validated to four decimal
  places on 2026-09-22. Make it reproduce the floor first, every time.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 and A3 both proved it reproduces a
  sweep's boxes exactly. A layout change that only **removes** Zones is
  predictable from the control's IRs; one that **moves** a box changes a crop,
  and costs a sweep.
