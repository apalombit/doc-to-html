# Status — 2026-09-25 (A2 closed, gate MET; **A3 next**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. Last rewritten 2026-09-25, at
A2's close, when the floor moved to `a2-result`.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **796 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
Phase A1    Inline runs, and hard line breaks   DONE 2026-09-25, gate NOT met
Phase A2    Geometry — re-scoped                DONE 2026-09-25, gate MET
Phase A3    Figure pixels                                          <- next
Thread 3/C  Repair loop (re-scoped first)
Thread 4/D  Human corrections (unscheduled)
```

---

## The floor — `tests/frozen/a2-result/`, DECIDED 2026-09-25

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a2-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` the report
scores the iterate five and says nothing about the other ten.

**It moved from `a0-result` at A2's close, on measurement.** `a2-result`
dominates it per document on every ratcheted leg — rises on 1 (vocabulary),
4 (precision), 1 (tau) and 3 (beside), falls on none — and prints five
`newsletter_0008` words the old floor did not.

**It is also the control.** It holds the fifteen documents beside their
scores; scored straight out of the directory, **0 differing fields**, and
re-rendering its IRs through `render()` gives all fifteen byte-identical. A
change downstream of the model is measured against it offline in about fifty
seconds. Its README has the recipe.

### What the ratchet enforces, per document

`report._ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside a failure to say how far it fell. **The
floor never falls for any reason** — the rule that made A1 revert a change
that improved T6.

---

## Where the corpus is — at the floor

| | mean |
|---|---|
| vocabulary recall | 0.8667 |
| recall (multiset) | 0.8542 |
| precision | 0.9803 |
| join recall | 0.8225 |
| tau | 0.9382 |
| beside agreement | 0.7316 |
| height ratio | 1.4772 |
| `hard_breaks` | 8, all real address breaks |
| T6 inline runs | 8 of 42, confirmed by a real sweep |

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

A-1 established the pipeline can declare *structural* loss and cannot declare
loss *inside a line*, and that two pixel-side detectors were built and
rejected. **Do not build a third without a new kind of evidence.**

**2. Side-by-side content stacks** — `form_0007` 0.059, `catalogue_0015`
0.288, `menu_0012` 0.349, `newsletter_0008` 0.476, `cv_0013` 0.500. A2
established that most of it is **inside one Zone**, so no renderer reaches it;
see "Closed, with evidence".

**3. Height.** `statement_0006` 2.78, `menu_0012` 2.29, `cv_0013` 2.06,
`newsletter_0008` 1.99 — a symptom of 1 and 2 plus the deferred type scale.

**4. Invented text.** `nonlatin_0014` at precision 0.914, mostly misread Greek
plus the overlap on the open list. Everything else is at 0.947 or better.

**5. Reading order** wobbles on `newsletter_0008` (0.832), `menu_0012`
(0.829), `darkdeck_0009` (0.836), `invoice_0002` (0.849).

---

## What the last two phases shipped

### Phase A2 — gate MET, 7 of 7, sweep `A2-10-enclosed-sweep`

The record is [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md);
§8 is the enclosed Zone.

| change | what it fixes |
|---|---|
| `detector.without_enclosed` | a box lying wholly inside another, by its four edges, dropped after the unions. `attach_trailing_rows` and `attach_headings` had grown a box over a neighbour and left it standing, on three documents; all four enclosed Zones were duplicates — `5,772.36`, `3,586.14`, `To begin`, `Senior Structural Engineer`. Bands now valid on 15 of 15. |
| `orchestrator._why_kept`, `report._snap_note` | the snap was blamed for invalid Bands it had not touched — it returned those boxes unchanged. The report reads **"The Bands are valid everywhere"**. |
| `render._numeric_columns` skips empty cells | a sparse money column votes on the cells that hold something — `statement_0006`'s "Paid out", 42 cells |
| `render._speaks_for_its_column` | one cell decides a column only when it is the column — `cv_0013`'s `2015` above three blanks |
| `dl.pairs { overflow-wrap:anywhere }` | `cv_0013`'s sidebar email was clipped; `clipped` 1 → 0 |

**The sweep reproduced the offline prediction on every scored field and every
document byte for byte**, so an upstream change that only *removes* a Zone is
measurable by replay. Clause 4 was restated before the sweep, with evidence:
`cv_0013`'s rise to 0.500 is a pair leaving the scored set, not coming back.
Visual review: 3 `better`, 12 `same`, no `worse`.

### Phase A1 — gate NOT met, on clause 1 only

| change | what it fixes |
|---|---|
| `render._lines` reflow | wrapped lines flow; `KEEPS_ITS_LINES` is `address` only. `hard_breaks` 57 → 8. |
| the hyphen — `render.WORDLISTS` | `con-`/`firmed` joined, `nine-`/`month` kept; right on 15 of 15. No word list → every hyphen kept, the side where being wrong is free. |
| `DTH_INLINE_PASS` | inline runs asked in a **separate** per-Zone pass. Asked inside the Extractor prompts it crossed the ratchet on seven documents and was reverted; `engines.ollama.MARKED_CLAUSE` stays wired to nothing, with the numbers. |
| guards `_covers_everything`, `_splits_a_word`, `keep_runs`, one span one Cell | each written against a fault the trial sweep produced. `keep_runs`'s threshold is "every word" — the marked share is bimodal, junk at exactly 1.000. |
| `render._SEAM`, `Document.from_json` | a word joined across two marked lines split into two text nodes; `Reading.runs` came back as dicts |

**Clause 1 (21 of 42 inline runs) reached 8**, all `link` or `code` in `prose`:
the model returns no `strong`, `em` or `mark` anywhere. Clause 4 was restated
after firing where the fault had not happened, and put to Alessandro first.

---

## Next

### 1. Phase A3 — figure pixels  <- next

A `FIGURE` Zone carries its crop rather than a `graphic_kind` label; logos
currently render as dashed placeholders (`invoice_0001`, `receipt_0010`'s
barcode) or vanish (`invoice_0002`'s ACME tile). **No prompt is written for it
yet** in [`specs/0007-handover.md`](specs/0007-handover.md).

### 2. Open, and nothing owns it

- **The across-Zone echo, the half A2 did not reach.** `darkdeck_0009` prints a
  caption `AVAILABILITY` above a table whose first column header is
  `AVAILABILITY`. The two Zones do not overlap, and `_without_title_echo`
  compares a Block against its own Zone's Title only.
- **`nonlatin_0014`'s overlapping Zones** — left open by decision in A2. Its
  full-width Zone is 0.70 over the top-right pairs box, across two Bands, and
  re-reads three of its four pairs. Not an enclosure: the outside part holds
  `ΤΠΥ = 2026/0417`, so dropping either box loses it. Removing the overlap
  means cutting a box, which changes a crop and costs a sweep.
- **`statement_0006`'s 41 near-identical caveat lines** should aggregate to one.
  Ours, from A-1, no model time.
- **`receipt_0010`'s untested lead.** `preprocess.resize_long_edge` never
  enlarges, and this document rectifies to **335×547**, so the extractor sees
  ~300px across 19 lines of monospace. ~6 minutes to probe, and it is the worst
  document in the corpus.
- **`nonlatin_0014`'s dark-blue table header row** renders on white. Do not
  build a third detector; point `chrome()`'s title-band measurement at the row
  `RowRole.header` already names.
- **`invoice_0001`'s `Invoice` / `#: 123`** — a Pair label/value boundary. It
  needs the Pairs Extractor to choose a different split point.
- **A1's one false mark** — `invoice_0001`'s `12345`, worth 0.0029 of
  `join_recall`.

### 3. Raising A1's clause 1, if anyone wants to

The cheapest untried lever is the one Thread 2/B used for colour: **measure
weight and monospace off the pixels rather than asking.** That needs
word-level ink segmentation the project does not have.

---

## Closed, with evidence — do not reopen without a new kind

All in [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md).

- **The column model.** Four renderers measured offline, all worse on the hard
  tier; with height held at the source's own it was still below the control.
  **Proportional widths** were re-measured after the enclosure fix and lower
  `cv_0013` 0.500 → 0.474 while crossing the ratchet on `form_0007`.
- **The merged Zone** — `menu_0012`'s two menu sections as one table,
  `form_0007`'s two-column form as one pairs list, 49 of the 66 inside-Zone
  pairs. Three pixel-side tests, none separates them from genuine two-column
  tables. **Do not build a fourth**; if reopened it is a *model* question asked
  as "how many regions", and its own phase.
- **`alignment_agreement` as a gate.** Flipping 42 cells to right-aligned moved
  it 0.935 → 0.935. Alignment is gated on a count of named columns, in the DOM.
- **Reading direction for a multi-Band column region** is an **IR gap**, not a
  renderer choice: the same merge takes `newsletter_0008` tau 0.832 → 0.968 and
  `catalogue_0015` 0.943 → 0.562.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session counts.
  **The exceptions are committed files:** `tests/frozen/run84/`,
  `a1-checkpoint/`, `a0-checkpoint/`, `a0-result/`, `a1-result/` — all kept as
  record — and **`a2-result/`, the floor and the control.**
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

## Deferred deliberately — not new faults

- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size.
- **Figures as placeholders** are A3.
- **Thread 3/C** stays gated on its re-scoping classification. The conversion
  is deterministic, so a loop re-reading the same crop gets the identical wrong
  answer back.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a2-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

**Three offline loops, each proved before it was used. Say which produced any
number you report.**

- **Downstream of the model** — renderer, style, wire. Re-render
  `tests/frozen/a2-result/`'s IRs and score them; `tools/remeasure_style.py`
  does the pixel-measured fields. Cannot move anything the model decided.
- **Recorded answers through the shipping mapper** — validated to four decimal
  places on 2026-09-22. Make it reproduce the floor first, every time.
- **The layout stage** — detector, `_cover_the_page`, snap — is all CV and runs
  offline in ~10 seconds for all fifteen; A2 proved it reproduces a sweep's
  boxes exactly. A layout change that only **removes** Zones is then predictable
  from the control's IRs, because no surviving Zone's crop or prompt moves; A2's
  sweep matched that prediction byte for byte. A change that **moves** a box
  changes a crop, and costs a sweep.
