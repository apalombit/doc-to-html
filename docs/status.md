# Status — 2026-09-22 (Phase A0 closed, gate met; A1 is next)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**
(`.claude/skills/visual-review/SKILL.md`).

Branch `scaffold`, head `98c0665` plus A0's uncommitted work.
**731 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
  |- the doubled Title                          0 echoes, from 34
  |- _without_empty_rows filtered on count      fixed; 0 all-blank rows
  |- the caption band and the Extractor's crop  measured, withholding REJECTED
  \- _without_repeated_header                   new net, for a fault A0 created
Phase A1    Inline runs, and hard line breaks   NEXT   <- you are here
Phase A2/A3, Thread 3/C, Thread 4/D             unchanged
```

---

## The notch — what it is, and the open decision

**OPEN. Decide at the start of A1. Nothing is bound yet.**

### The mechanism

1. Every run writes `debug/runs/<label>/scores.json`.
2. `report.py --previous <path>` compares this run's scores against that file
   and **fails the gate if any document stopped printing a source word the
   previous file says it printed.**
3. That `--previous` file *is* the notch. It is the floor, and the only thing
   that makes "completeness may never decrease" enforceable rather than a
   slogan.
4. **`debug/runs/` is gitignored and gets cleared**, so a floor left in a run
   directory disappears. That is why floors are copied into `tests/frozen/` and
   committed.

### The state today

| directory | what it holds | is it the floor? |
|---|---|---|
| `tests/frozen/a1-checkpoint/` | where the ratchet started, Phase A-1 | no, historical |
| `tests/frozen/a0-checkpoint/` | scores from **before A0 ran** | **yes, currently** |
| `tests/frozen/a0-result/` | scores from **after A0 ran** (`100-a0-gate`) | **no** — preserved only |

### The issue

**A1 would be checked against pre-A0 numbers.** A0 raised precision
0.9342 → 0.9765 and every other axis with it. None of that is in the floor. So
A1 could hand all of it back, land exactly on A0's starting quality, and
**pass the gate** — which is precisely the failure the ratchet exists to
prevent.

### The decision

Move the floor to `tests/frozen/a0-result/` (already committed, already
verified), or leave it at `a0-checkpoint/`.

- **Move it:** A0's gain becomes permanent. Cost — every later phase answers to
  a tighter floor, and a phase that trades precision for recall on purpose has
  to argue for it explicitly.
- **Leave it:** later phases have room to trade. Cost — A0's gain is
  unprotected and can be lost silently.

Recommendation: **move it.** The ratchet is meant to be a floor that only ever
rises, and a floor that skips a phase's gains is not doing its job. But it is
a call about how much freedom A1 should have, so it is Alessandro's.

**Nothing was lost either way** — `a0-result/` is committed, so the option
stays open after `debug/` is cleared.

---

Until that is decided, ratchet A1 against the current floor:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
```

---

## What A0 did, and what it cost

Three faults were named in the brief. All three were diagnosed; **two were
fixed and the third was measured and its planned fix rejected.**

### 1. The doubled Title — fixed

A Zone carrying a Title also carried a Block, a row or a pair repeating it, in
12 of 15 documents. `wire._without_title_echo` drops a first Block / first row
/ first pair whose normalised text equals `zone.title`. The bound was measured
before the rule was written: **all 27 Block echoes were `blocks[0]`, and there
were zero near-misses** — nothing in the corpus sits just outside the rule.

**34 title echoes before, 0 after.**

### 2. `_without_empty_rows` filtered on cell count — fixed

`if row.cells` is truthy for `['', '', '', '', '']`, so the net let an
all-blank row through. It now tests content:
`any(cell.strip() for cell in row.cells)`. The net itself stays; four runs
established what it guards.

**The brief named `sample_table_0003` as the document returning a 17th blank
row. It was not.** `sample_table_0003` has 16 rows and none blank. The live
all-blank row was `report_0011` z6 row 5, `['', '', '', '']`. The bug was real
and the named document had moved.

### 3. The caption band and the Extractor's crop — REJECTED after measurement

`DTH_CAPTION_PASS` withholds the caption band from the *Kind* question and not
from the Extractor's crop, and `with_grid` subtracted one row for the caption
anyway. The agreed fix was to withhold the band from the crop too. **It was
built, measured, and reverted**, because cutting the band deletes real content:

- `darkdeck_0009` z2 is a row of four metric cards with no caption. Cutting the
  top band removed `P95 LATENCY`, `INGEST VOLUME` and `COST PER MILLION` —
  confirmed by opening the crop image, not inferred.
- The cut moved the *measured* column count on three tables.
- Widening `CaptionBand.aligns_to_grid` to a ratio instead was also rejected:
  it strips four real captions corpus-wide.

**What shipped is only the removal of `with_grid`'s subtraction.** The
arithmetic now matches the picture it is taken from. Both docstrings record
why the cut was tried and why it is not there.

### 4. `_without_repeated_header` — a net for a fault A0 itself created

A heading guard in `detector._trailing_row` (headings are no longer absorbed
as trailing rows, which recovered `What Q4 commits to`) shortened
`darkdeck_0009`'s table crop to 8 ink bands. The prompt then asked for 8 rows
where the table has 7 — a caption band is counted and is not a row — and the
model **padded by repeating the header**. Same on `report_0011`.

Restoring `with_grid`'s subtraction is what deleted `sample_table_0003`'s
headers in the first place, so the repair is at the wire instead: a second
`role == "header"` row whose cells spell the same as the first is dropped.
**A dropped row is a recall fault; a surplus row is only a precision one**, and
that asymmetry is why the net sits on this side.

### The measurement that forced the gate to change

Removing a title echo **lowers multiset recall without losing anything**: the
echo was numerically covering for a genuine occurrence elsewhere that was never
read. So the ratchet's recall leg is now **distinct tokens**, not the multiset.
`Completeness.vocabulary_recall` and `Completeness.vanished` are the two new
fields, and `report._stopped_printing()` is the one place that decides — both
`_gate_html` and `_summary_table` call it, because a green summary row above a
failed gate is how a ratchet stops being believed.

**`Completeness.duplicated` is not the gate and cannot be.** It totals 29 over
twelve documents and is **empty for `report_0011`**, which visibly prints all
eight of its numbered headings twice. Three independent mechanisms make it
blind; it saw 30 echoes and missed 18. The gate counts echoes structurally, off
the IR.

---

## A0's gate — the result

Sweep `100-a0-gate`, all fifteen, against `tests/frozen/a0-checkpoint/`.

| | floor | 100-a0-gate |
|---|---|---|
| **vocabulary recall** (the ratchet's leg) | 0.8599 | **0.8653** |
| recall (multiset) | 0.8513 | 0.8542 |
| **precision** | 0.9342 | **0.9765** |
| join recall | 0.8088 | 0.8128 |
| tau | 0.9356 | 0.9381 |

Five clauses, all met:

1. **0 title echoes**, from 34.
2. `sample_table_0003` returns `Country | ISO | Population | GDP (USD M) | Currency` and 16 rows.
3. **0 all-blank rows** corpus-wide.
4. **0 repeated header rows** corpus-wide.
5. **The ratchet holds**: no document stopped printing a source word it printed at the floor, and precision ≥ 0.975.

**Offline replay was validated as a technique on the way.** Post-model changes
were predicted by replaying a run's recorded answers through the shipping
mapper, and sweep 100 confirmed the prediction to four decimal places on every
mean. The conversion is deterministic at `temperature: 0`, so this is sound for
anything downstream of the model — and for nothing upstream of it.

---

## What the corpus looks like as A1 begins

Reviewed document by document on 2026-09-22 against the sources, all fifteen,
`--previous debug/runs/99-a0-heading-guard`. Findings in
`debug/runs/100-a0-gate/_review/` — **that directory is under `debug/` and will
be cleared**; the tables below are what survives.

| | mean over fifteen |
|---|---|
| `vocabulary_recall` | 0.865 |
| `recall` | 0.854 |
| `precision` | 0.977 |
| `join_recall` | 0.813 |
| `tau` | 0.938 |

Worst fault per document, from the rubric:

| document | worst axis | what it is | owner |
|---|---|---|---|
| `receipt_0010` | content | everything below `Order 00418` — all eight items, all totals, the barcode. **Declared** by the render | open, see below |
| `catalogue_0015` | content | the page title `Hardwood fittings`, and eight of twelve cards lose price, unit and stock line | open, see below |
| `cv_0013` | content | `Ines Halloran` and `STRUCTURAL ENGINEER` absent; every sidebar value clipped mid-word | A2 |
| `menu_0012` | content | `To begin` printed **twice**, across two Zones; three section headings hoisted out of the menu | **new — see below** |
| `nonlatin_0014` | colour | the table's dark-blue header row renders on white | open, unscheduled |
| `statement_0006` | rhythm | 41 near-identical caveat lines fill two screens | A-1 residue |
| `darkdeck_0009`, `form_0007` | columns | cards and paired fields collapse to one stack | A2 |
| `report_0011`, `sample_semantic_0005`, `newsletter_0008`, `catalogue_0015` | type | three heading levels render at one size | 2/B |
| `invoice_0001`, `invoice_0002` | content | the logo blocks render as placeholders | A3 |
| `sample_css_0004`, `sample_table_0003` | chrome | a blue rule, a badge chip, zebra striping not drawn | 2/B |

Owner tally over fifteen: **2/B 5, new 4, A2 3, A3 2, A-1 1.**

**Two `better`s on the `changed` axis, no `worse`:**

- `darkdeck_0009` — 99 printed `COMPONENT | OWNER | AVAILABILITY | P95 | STATUS` twice; 100 prints it once.
- `report_0011` — 99 printed `Berth | Movements | Revenue £000 | Change` twice; 100 prints it once.

**No fault sat beside all-1.000 scored ratios.** Every `major` in the review has
at least one scored ratio below 1.000 next to it, which is the first time that
has been true.

**`sample_table_0003` is a full match** — five column headers, sixteen rows, no
blank row. That is the document spec 0007 was opened on.

---

## Next, in order

### 1. Phase A1 — inline runs, and hard line breaks  <- next

The prompt is in [`specs/0007-handover.md`](specs/0007-handover.md).
**Hard line breaks moved into A1 from A0** during A0's scoping, and the review
above is full of them: `newsletter_0008` reads `the borough council con-` /
`firmed on Tuesday`, `report_0011` reads `prepared under the terms` / `of the
1987 order`. `join_recall` at 0.813 is the axis that sees this, and it is the
weakest of the four.

`invoice_0001` shows the other half: `Invoice #: 123` is cut into a label
`Invoice` and a value `#: 123`, scoring 1.000 recall, 1.000 precision and
1.000 tau. Only `join_recall` and `Completeness.broken_joins` see it.

### 2. Found in A0's review, nothing owns it

- **`menu_0012` prints `To begin` twice, in two different Zones.**
  `_without_title_echo` cannot see this: it compares a Block against *its own*
  Zone's Title, and these are two Zones that each read the same printed line.
  The same shape appears on `darkdeck_0009`, where a caption line
  `AVAILABILITY` is printed above a table whose first column header is
  `AVAILABILITY`. **A0 closed the within-Zone echo; the across-Zone one is
  open and was not visible until the within-Zone one was gone.**

### 3. Open, unscheduled, and cheap — unchanged from before A0

- **`statement_0006`'s 41 near-identical caveat lines** should aggregate to
  one. Ours, from A-1, no model time, and it fills two of that document's three
  review sheets.
- **`receipt_0010`, the corpus's worst document, has one untested lead.**
  `preprocess.resize_long_edge` never enlarges — its docstring argues enlarging
  "adds no detail" — and `receipt_0010` rectifies to **335x547**, by far the
  smallest page, so the extractor sees ~300px across 19 lines of monospace.
  True of information, possibly false of legibility. One document, ~6 minutes
  to probe.
- **`nonlatin_0014`'s table header row.** Do not build a third detector; point
  `chrome()`'s existing title-band measurement at the row `RowRole.header`
  already names.
- **`catalogue_0015` at 0.571 recall.** Eight of twelve cards lose their price
  line and the loss is **not declared**. Nothing owns it. A-1 established that
  the pipeline cannot declare loss *inside a line* and that two pixel-side
  detectors were built and rejected — do not build a third without a new kind
  of evidence.

### 4. Then A2 / A3, Thread 3/C, Thread 4/D — unchanged

---

## Standing note: a detector change shipped inside A0

The heading guard in `detector._trailing_row` is detector-level work, which is
A2 territory, and it shipped inside A0 because it was the cause of a named A0
fault (`What Q4 commits to` was being absorbed as a trailing row). **Its blast
radius was measured before it shipped**: 2 headings wrongly absorbed and 4
non-headings correctly absorbed, including `invoice_0001`'s `$385.00` total,
which still attaches in `100-a0-gate`. Sweep 100 showed no movement beyond
those two headings. Had it shown more, the right call was to hand it to A2.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session
  counts. Three exceptions, all committed files: `tests/frozen/run84/`,
  `tests/frozen/a1-checkpoint/` and `tests/frozen/a0-checkpoint/`.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the two dormant safety nets or the four shipped defaults** —
  and there are now **three** wire-level nets: `_without_empty_rows`,
  `_join_split_header_row` and `_without_repeated_header`. Each invents nothing
  and discards nothing.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.**
- **Any reviewed run is a full sweep**, all fifteen documents.
- **Rubric judgements are pairwise and in-session only.**

## Deferred deliberately — not new faults

- **Column collapse** waits for A2. Content complete and reading order correct,
  in one column, is the accepted interim state.
- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size.
- **`Zone.align`** stays in A2.
- **Figures as placeholders** stay in A3.
- **`cv_0013`'s clipped sidebar values** stay in A2.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

**A renderer-only or pixel-only change needs no new run.**
`tools/remeasure_style.py <sweep> --label <new>` re-measures the Style Record
and re-renders from a sweep's own embedded IRs with zero model calls. It cannot
move anything the model decided — a prompt, an extractor or the layout still
costs a sweep — and it says so. **It does not serve A0 or A1**, both of which
change prompts and extraction.

**A post-model change can be verified without a sweep by offline replay** —
feed a run's recorded answers back through the shipping mapper. Validated on
2026-09-22 to four decimal places on every mean. Upstream of the model it
proves nothing.
