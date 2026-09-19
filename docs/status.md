# Status — 2026-09-19

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then
[`specs/0007-handover.md`](specs/0007-handover.md) (the per-thread prompts and
the full Phase A-1 scope). This file is the summary, not the source.

Branch `scaffold`, clean at **`dba0b9e`**. 565 tests pass, `mypy src/` clean.

---

## Where we are

**Thread 0 is complete and its gate is met.** The project no longer optimises
agreement with a hand-typed reference IR; it measures whether the rendered
output looks and reads like the source document. The measure, the corpus and
the review surface all exist and are tested.

**Thread 1/A has not started.** Its first phase has been re-scoped from the
checkpoint review and is approved but not begun. Nothing in `src/` has been
changed to improve any score.

## Thread 0 — done, with the gate evidence

| | |
|---|---|
| `corpus.py` | fifteen documents, HTML + screenshot each, split *iterate* (the original five) / *sweep* (all fifteen) |
| `projection.py` | `project()` — one page as a reader perceives it, off headless Chrome. One function, both sides. |
| `scoring.py` | `score_document()` — six axes. T1/T2/T3 hard tier, T1 a ratchet. |
| `report.py` | `debug/runs/<label>/report.html` — the review surface |

The three gate conditions, all met:

1. **The scorer finds run 84's faults unaided.** `tests/test_scoring.py`, no
   model, no network. Asked only general questions it reports
   `sample_table_0003`'s deleted column headers, a Zone Title repeated inside
   its own body in four documents, four surplus hard breaks on
   `sample_semantic_0005`, and `invoice | 123` as a broken join that recall,
   precision and tau all score 1.000.
2. **The report renders all fifteen in one page** — verified structurally,
   fifteen `<section class="doc">`, one per document.
3. **A checkpoint run exists** — `85-thread-0-checkpoint`, taken 2026-09-18.

**The checkpoint run itself is gone or going.** `debug/runs/` is gitignored and
gets cleared. Its numbers are not re-citable and nothing below rests on them —
what is recorded here is *structural* and re-derivable: which fault, which
cause, which line of code. Re-take a sweep when you need numbers.

## What the checkpoint showed, reviewed document by document

Reviewed by Alessandro against the sources on 2026-09-19, render beside
source, all fifteen. **T1 was clean on none of them.** The ten new documents
fail in ways the original five never exposed, and they are four unrelated
causes, not one:

| cause | documents | signature |
|---|---|---|
| Table read, then discarded whole | `statement_0006`, `cv_0013` | `MappingError: table row 1 has 6 cells but the header has 7` |
| Content outside every detected box, dropped | `receipt_0010`, `form_0007`, `nonlatin_0014` | finding says *"may be a mark"* — on the receipt that is 77 of 103 tokens |
| Whole page detected as **one** Zone, silently | `darkdeck_0009` | one Zone, **no finding at all** |
| Columns collapse to one | `form`, `menu`, `cv`, `catalogue`, `newsletter` | `beside_agreement` 0.03–0.40 |

**Two findings that change what the fix costs, both established by looking:**

- **`statement_0006` did not fail to read its table.** The model returned all
  36 transaction rows correctly and the pipeline threw them away because one
  row disagreed with the header on cell count. The content existed. This is
  the cheapest recall in the corpus and it is a reconciliation bug, not a
  perception problem.
- **`darkdeck_0009` is not a bad document.** It was checked for fairness
  first — ordinary contrast, ordinary structure, and it scores perfectly
  against itself. The cause is ours and it is exact: `preprocess._ink()`
  thresholds with `cv2.THRESH_BINARY_INV + THRESH_OTSU`, which treats dark
  pixels as ink, and `darkdeck.png` is **96.2%** below mid-grey, so nearly the
  whole page reads as one ink blob.

## Two corrections made to standing documents

- **The conversion is reproducible, and `CLAUDE.md` said the opposite.**
  `transport.py` asks Ollama for `temperature: 0`, and the five original
  documents came back **byte-identical** to the copies frozen in
  `tests/frozen/run84/` — all five, md5 for md5, on a later commit and with
  the model partly on the CPU. This matters in the dangerous direction: a
  byte-identical arm means **the change did nothing**, not that noise swamped
  it. Scoped to this machine and model; says nothing about the other ten
  documents, which have no prior run.
- **`DTH_SNAP_ZONES` is silently not applying to four of fifteen documents.**
  It moves the boxes onto their ink, the Bands then fail validation, and the
  Conversion falls back to unsnapped geometry. Two shapes: a full-width Zone
  with a narrow box strictly inside it, and two Zones landing on nearly the
  same span. Both are *grouping* questions before they are snap questions.
  The snap is one of the four defaults that must not be deleted — the finding
  is that it is **not being applied**, which is a different fact from it being
  harmful.

## Next — Phase A-1, scoped and approved, not started

Full scope is in `specs/0007-handover.md`. In brief: **a new phase ahead of
A0**, because A0's three faults are content being *mis-read* while these are
content not surviving at all, and merging them would make A0 look like it
failed when its own fixes worked.

All three content-loss causes above are in scope. **The phase's real gate is
the honesty rule:** content that does not reach the output must produce a
finding that says so and says how much. `darkdeck_0009` lost 80% of its
document and reported nothing; `receipt_0010` lost 75% and called it a
possible mark. A-1 is not done while any document can lose content quietly.

A-1 reports T1 on the sweep set but does **not** gate on 1.00 — that stays
A0's, measured after A-1 lands.

**Deferred on purpose, with the reason, so they are not read as new faults:**

- **The renderer's cards wait for Thread 2/B.** `render.py`'s
  `section.titled` borders every titled Zone unconditionally, so a flowing
  document like `report_0011` renders as a stack of cards and the source is
  never consulted. 2/B measures borders from pixels and will draw a card only
  where the source has one; an interim guess would be undone. Expect
  card-chopped renders until then.
- **Column collapse waits for A2.** Accepted interim state: **content
  complete and reading order correct, in one column.** So A1 (inline) runs
  before A2 (geometry). Do not trade T1 for column shape.

## Open — needs Alessandro, before or at A-1's start

1. **Where the ratchet's starting notch sits.** A-1 will move T1 on documents
   A0 is supposed to gate, so A0's "1.00 on iterate" would be measured against
   a different baseline than the spec assumes. Proposal: take A-1's checkpoint
   as the notch and re-baseline A0 against it. This is the second
   pre-registered number this work has had to move, so it should be set
   deliberately rather than inferred.
2. **The honesty rule may fail documents that currently pass.**
   `invoice_0001` scores T1 1.000 and has a broken join; `sample_css_0004`
   scores 1.000 recall with two duplicated titles. Enforced strictly, some of
   the original five start producing findings they do not produce today. That
   is correct behaviour, but it will look like a regression the first time it
   appears on the report.

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in the current
  session counts. A run number is not evidence. The one exception is
  `tests/frozen/run84/`: committed inputs, scored offline, tabulated in its
  own README.
- **`debug/runs/84-rule-not-a-line/` must be left intact.** Verified present
  and untouched as of 2026-09-19.
- **`tests/documents/SAMPLE_DOCUMENTS` is test input only — never score
  against it.** Doing so rebuilds the harness spec 0007 deleted.
- **Do not delete** the two dormant safety nets (`wire._without_empty_rows`,
  `_reread_as_prose`) or the four shipped defaults (`DTH_SNAP_ZONES`,
  `DTH_TABLE_GRID_HINT`, `CLASSIFY_PROMPT`, `_reread_as_prose`).
  `_without_empty_rows` has a real `if row.cells` bug — that is **A0's** to
  fix, not A-1's, and the net stays.
- **Keep the OpenCV rectangle finder** for Thread 2/B, with its
  >0.80-of-the-page guard.
- **`project()` compares a normalised view** — text runs in reading order,
  block roles, client rects — and never raw markup. A scorer that demands our
  output reproduce the source's div nesting or class names is a worse overfit
  than the one being escaped.
- **`report.html` is a required deliverable of every run**, not a nicety.

## The loop

```
tools/iterate.sh <label>                  # one document, shipped defaults
FIXTURE=iterate tools/iterate.sh <label>  # the five, ~17 min
FIXTURE=sweep   tools/iterate.sh <label>  # all fifteen, ~90 min, at a phase gate
```

A sweep took ~90 minutes on 2026-09-18, not the ~50 the old note estimated —
that figure predated the ten new documents. Then open
`debug/runs/<label>/report.html`.
