# Status — 2026-09-27 (the open-issues queue: **Q1 done, Q2 next**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-09-27, when
Q1 of the open-issues queue closed.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **828 tests pass, `mypy src/` clean.**

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
Open issues 1-3 DONE 2026-09-26 offline; 4 -> the type scale
Queue       Q1-Q7, in order, go given 2026-09-27
              Q1 DONE 2026-09-27, offline, gate MET                Q2 <- next
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
`newsletter_0008` 1.99 — a symptom of 1 and 2 plus the deferred type scale.

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

**Q2. `statement_0006`'s header was read one empty cell wide.** Model-free,
wire. Every one of its 41 rows is padded to seven cells and an empty column
trails the table. Measured: nine tables end their header in empty cells, but
only two have a header wider than any data row that was read —
`statement_0006` z3 (7 against 6) and `receipt_0010` z1 (20 cells, 19 empty,
no data row at all). `catalogue_0015`'s six have data rows read to the
header's width. A new wire net needs a replayed Conversion test, and `wire.py`'s
three row nets stay.

**Q3. The type scale — 2/B's deferred increment, carrying open issue 4.**
Model-free, but its own increment, gated on `height_ratio` directly. Every
heading Block renders as an `h1` at 1.6em: `invoice_0002`'s bold body-size
`Acme Corporation` is the page's largest text, and the review names the same
on `catalogue_0015`, `darkdeck_0009`, `cv_0013` and `newsletter_0008`.
`style.py`'s module docstring holds the numbers that deferred it —
`catalogue_0015` estimates 2.40x — and `invoice_0002`'s company block is one
75px band of ink, so a within-Zone rule cannot size it.

**Q4. Thread 0's leftover seam.** No output change. `OllamaEngine.detect_zones`
and `LAYOUT_PROMPT` are unreachable from a Conversion and survive only as what
nine test modules' layout stage replays against. Bookkeeping, not a
measurement question: fifteen of fifteen render unchanged, tests pass.

**Q5. `receipt_0010`'s untested lead** — the worst document in the corpus.
Model time. `preprocess.resize_long_edge` never enlarges, and this page
rectifies to **335×547**, so the extractor sees ~300px across 19 lines of
monospace. ~6 minutes to probe; a change moves crops and costs a sweep.

**Q6. `nonlatin_0014`'s overlapping Zones** — left open by decision in A2.
Model time. Its full-width Zone is 0.70 over the top-right pairs box and
re-reads three of its four pairs; the outside part holds `ΤΠΥ = 2026/0417`,
so dropping either box loses it. Cutting a box changes a crop.

**Q7. `invoice_0001`'s `Invoice` / `#: 123`, and A1's false mark.** Model
time. A Pair label/value boundary the Pairs Extractor chooses, and A1's one
false mark, `12345`, worth 0.0029 of `join_recall`. Both are model questions.

**Q5–Q7 touch three different documents**, so whether they share one sweep —
as A3's two changes did — is decided on entry, with Alessandro.

**After the queue:** the floor decision, then Thread 3/C's re-scoping gate.
Thread 4/D stays unscheduled.

**Not in the queue, deliberately:** `catalogue_0015`'s undeclared loss (no
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

- **The type scale is no longer deferred — it is Q3 of the queue**, gated on
  `height_ratio` directly rather than on agreement with the CSS size. Until it
  ships, a heading drawn at the wrong size is its fault, not a new one.
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
