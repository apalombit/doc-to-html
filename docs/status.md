# Status — 2026-09-25 (A1 closed; **A2 re-scoped, three wins shipped, one change left**)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it. It was last rewritten rather than
patched on 2026-09-25, at A1's close, and extended the same day when A2 was
stopped at its gate.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**.

Branch `scaffold`. **786 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
Phase A1    Inline runs, and hard line breaks   DONE 2026-09-25, gate NOT met
  |- reflow: wrapped lines flow                 shipped, measured clean
  |- the hyphen: soft dropped, compound kept    shipped, 15 of 15 cases
  |- inline runs asked IN the Extractor prompts crossed the ratchet, REVERTED
  \- inline runs asked as a SEPARATE pass       shipped, 8 of 42 — clause 1 open
Phase A2    Geometry — RE-SCOPED                 IN PROGRESS   <- you are here
  |- premise did not survive its own measurements: specs/0007-a2-measurements.md
  |- the column model and the merged Zone   CLOSED UNBUILT, with evidence
  |- three offline wins                     SHIPPED 2026-09-25, ratchet clean
  \- the enclosed Zone                      LEFT, and the only part worth a sweep
Phase A3    Figure pixels
Thread 3/C  Repair loop (re-scoped first)
Thread 4/D  Human corrections (unscheduled)
```

---

## The notch — DECIDED 2026-09-24

**The floor is `tests/frozen/a0-result/scores.json`.**

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-result/scores.json
```

It moved there from `a0-checkpoint` at the start of A1, on measurement rather
than argument: compared per document on all four legs the gate actually tests,
`a0-result` **dominates** `a0-checkpoint` — the floor rises on 12 of 15
documents for precision, 3 for vocabulary, 3 for beside and 1 for tau, and
falls on none. `a0-checkpoint/` and `a1-checkpoint/` are kept as record, not as
floors.

### What the ratchet actually enforces, per document

Not four ratios compared loosely. `report._ratchet_html` fails the phase on any
of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside a failure to say how far it fell; it is
not itself the comparison. **The floor never falls for any reason** — that rule
is what made A1 revert a change that improved T6.

---

## What Phase A1 shipped

### Reflow — wrapped lines flow, real lines do not

`render._lines`; `KEEPS_ITS_LINES` excludes `address` only. **Measured, not
assumed:** the multi-line counts of every other kind sum *exactly* to each
document's excess hard breaks (`newsletter_0008` 30 paragraph + 1 heading = its
+31, `darkdeck_0009` 5 + 1 item = +6, `report_0011` 5, `sample_semantic_0005`
3 + 1 quote = +4, `cv_0013` 1), and all eight multi-line `address` blocks sit in
the three documents whose sources really do print 6, 3 and 9 breaks.

**Corpus `hard_breaks` 57 → 8, and all 8 remaining are address breaks.**

### The hyphen, which the picture cannot resolve

`con-` / `firmed` is the renderer's hyphen; `nine-` / `month` is the word's own.
`newsletter_0008` has both and they are the same shape on the page. Telling them
apart is knowing English, so `render.WORDLISTS` plus light morphology decides
it — right on all 15 cases measured. **Absent a word list every hyphen is
kept**, which is the side where being wrong is free: keeping one costs nothing,
dropping one wrongly costs two source words.

### Inline runs — asked twice, in two places

**Attempt 1, inside the four Extractor prompts: reverted.**
`invoice_0002/20_pairs` went **5 pairs to 1** while a neighbouring answer in the
same document stayed byte-identical; seven documents crossed the ratchet;
`sample_semantic_0005` lost `editor`, `example`, `com` — the email address,
which is one of the links the ask exists to recover.
`engines.ollama.MARKED_CLAUSE` is kept **wired to nothing**, with the numbers in
its docstring.

**Attempt 2, a separate pass: shipped.** `DTH_INLINE_PASS`, a per-Zone `runs`
call over `prose` and `list` only. It touches no Extractor prompt, so at
`temperature: 0` every extraction answer is the one the floor already has —
verified twice by reverting attempt 1 and re-running (`invoice_0002`, all four
pairs answers byte-identical; `sample_semantic_0005`, **all 27**).

Three guards, each written against a fault the trial sweep actually produced:

| guard | the fault |
|---|---|
| `_covers_everything` | a span covering a whole line |
| `_splits_a_word` | `T` marked, matching **`Tuesday`**'s `T` → `<strong>T</strong>uesday`. The page read correctly; T1 reported `tuesday` gone. **One word, and it failed the ratchet.** |
| `keep_runs` | a pull quote returned as **22 one-word `strong` marks** — every mark is a text-node boundary, so a shredded line loses every join in it |
| one span, one Cell | `invoice_0001`'s `12345` stamped on two different address lines |

**`keep_runs`'s threshold is "every word", and the corpus put it there.** Across
every marked Cell the marked share is bimodal with an empty band: genuine marks
**0.077–0.333** plus one at **0.750** (`editor@example.com`, three of its four
words), junk at **exactly 1.000**. A tidier 0.5 was tried first and threw that
email away.

### Two faults fixed on the way

- **`render._SEAM`** — joining a word across two marked lines left
  `<strong>…con</strong><strong>firmed…</strong>`. The page read `confirmed`
  correctly and `project()` walks **text nodes**, so T1 called a printed word
  missing. A fault invisible in the picture and loud in the measurement.
- **`Document.from_json`** rebuilt `Reading.runs` as plain dicts, which a
  dataclass accepts silently and which fails much later on the first
  `run.text`. It would have broken `remeasure_style`, `honesty.document_in`,
  `inspect_run` and `cli --ir`.

### A1's gate — NOT MET, on clause 1 alone

| clause | result |
|---|---|
| 1 inline runs ≥ 21 of 42, all 8 documents | **FAILED — 8 of 42, on 2 of 8** |
| 2 the five split words print whole | MET |
| 3 spurious hard breaks fall | MET — all four documents to 0 |
| 4 no over-joining | MET *(clause restated — see below)* |
| 5 the ratchet holds | MET |
| 6 structure, tests, mypy | MET |

**Clause 1 is the phase's real result, and the ceiling is the model.** It
returned **no `strong`, `em` or `mark` anywhere**, and nothing at all in `pairs`
or `table`. `strong` and `em` are 20 of the 42 and are derived from
*appearance* — the shape `CLAUDE.md`'s own lesson predicts.

**Clause 4 was restated after firing on a document where the fault had not
happened.** As written it compared `hard_breaks` counts; but `hard_breaks`
counts `<br>` **elements wherever they sit**, and `nonlatin_0014`'s source four
are in an address block and a date block (`example/nonlatin.html` 47–48, 53–54)
while the two the output lost were in Greek paragraphs that genuinely wrap. It
now reads: **every `<br>` the output still draws sits in a block whose kind
keeps its lines, and no such block lost one** — verified, 8 = 8, exactly the
address blocks. Restating a pre-registered clause after seeing the result is a
real hazard; it was put to Alessandro with the evidence before anything changed.

---

## Where the corpus is as A2 begins

Against the floor. The right-hand column is the shipped configuration.

| | floor (`a0-result`) | now |
|---|---|---|
| vocabulary recall | 0.8653 | 0.8667 |
| recall | 0.8542 | 0.8553 |
| precision | 0.9765 | 0.9787 |
| **join recall** | 0.8128 | **0.8229** |
| tau | 0.9381 | 0.9381 |
| beside agreement | 0.7233 | 0.7265 |
| alignment agreement | 0.7092 | 0.7217 |
| height ratio | 1.4977 | 1.4639 |
| **`hard_breaks`** | 57 | **8** |
| **T6 inline runs** | 0 of 42 | **8 of 42** |

**Read the right column carefully.** `A1-08-inline-sweep` is a real run of all
fifteen and is what every guard was measured on. The numbers above come from
**replaying that run's own marks through the fixed mapper** (`A1-11-final`),
which is sound because every guard is downstream of the model — but the replay
rebuilt 41 spans where the model returned 43. **A confirming sweep is
outstanding, and anyone quoting 8 of 42 as a measured run is quoting it wrong.**

### The live faults, worst first

**1. Some documents lose most of their words.** Not the pipeline — five
documents are at 100%.

| document | words kept |
|---|---|
| `receipt_0010` | **19.8%** |
| `catalogue_0015` | 61.7% |
| `form_0007` | 77.7% |
| `menu_0012` | 82.8% |
| `statement_0006` | 88.1% |

**2. It declares only some of that.** The run flagged four Zones as read short,
including `receipt_0010`'s table (19 printed lines, 2 returned). It said nothing
about `catalogue_0015` or `form_0007`. **A-1 established the pipeline can
declare structural loss and cannot declare loss inside a line, and that two
pixel-side detectors were built and rejected. Do not build a third without a new
kind of evidence.**

**3. Columns land in the wrong place — this is A2, and it is now the biggest
visual fault.**

| document | side-by-side | height vs source |
|---|---|---|
| `form_0007` | **0.06** | 0.92 |
| `catalogue_0015` | 0.26 | 0.97 |
| `menu_0012` | 0.35 | **2.34** |
| `cv_0013` | 0.45 | 1.77 |
| `newsletter_0008` | 0.48 | 1.99 |
| `invoice_0002` | 0.64 | 1.42 |

Things printed side by side come out stacked, which is why `menu_0012` and
`newsletter_0008` render roughly twice as tall as their sources.

**4. Invented text.** `nonlatin_0014` adds ~8.6% words that are not on the page,
mostly misread Greek. Everything else is under 5%.

**5. Reading order** wobbles on `newsletter_0008` (0.83), `menu_0012` (0.83),
`darkdeck_0009` (0.84), `invoice_0002` (0.85).

---

## Next, in order

### 1. Phase A2 — re-scoped to the enclosed Zone  <- next

**Its prompt is rewritten** in [`specs/0007-handover.md`](specs/0007-handover.md)
around the one change that is left. The original prompt is kept below it as
record.

#### Shipped 2026-09-25, measured offline against `tests/frozen/a1-result/`

Corpus: **`clipped` 1 → 0**, `beside_agreement` **+0.0033**,
`alignment_agreement` **+0.0019**, every T1 leg and `tau` **unmoved**, ratchet
clean. `cv_0013`'s `height_ratio` 1.77 → 2.14, which is a wrapped address
taking the lines it needs.

| change | what it fixes |
|---|---|
| `render._numeric_columns` skips empty cells | `statement_0006`'s "Paid out" is 5 numbers in 40 rows and stayed left-aligned; among the non-empty it is 5 of 5. **42 cells**, corpus `.num` 212 → 254. |
| `render._speaks_for_its_column` | one cell decides a column only when it *is* the column. `cv_0013`'s `2015` over three blanks right-aligned 8 cells the source does not. Changes **one** of the corpus's eighteen table columns; `invoice_0001`'s real one-row table is untouched. |
| `dl.pairs { overflow-wrap:anywhere }` | `section.filled` sets `overflow:hidden`, so `cv_0013`'s sidebar hid an email at 256px of the 368px it wanted. Recall said present; the picture did not contain it. |
| `report._snap_note` | the snap rejection, off `trace.json`, beside the ratchet and the honesty gate. **"did not apply to 3 of 15"**, naming the enclosure on each. |

#### Left, and the only part worth a sweep

**The enclosed Zone** — four pairs in three documents, each a Band holding a
narrow box wholly inside a wide one. It is why `DTH_SNAP_ZONES` reaches twelve
of fifteen, and it blocks the one renderer change that helped (`cv_0013`
`beside_agreement` 0.450 → 0.556 under proportional widths). The rule is
arithmetic on boxes already in the IR; what it does with an enclosure changes
which crops are extracted, which is what costs the sweep.

### 1b. Closed unbuilt, with evidence

The prompt is in [`specs/0007-handover.md`](specs/0007-handover.md). It owns
columns, `Zone.align`, and `cv_0013`'s clipped sidebar values. The table above
is its starting measurement.

The record is [`specs/0007-a2-measurements.md`](specs/0007-a2-measurements.md).
**Do not reopen either without a new kind of evidence.** In brief:

- **66 of the 113 missing side-by-side pairs are inside one Zone**, so no
  renderer can reach them. `form_0007` (0.059) and `menu_0012` (0.349), the two
  worst documents, are **entirely** inside-Zone.
- **Four renderers were built and scored offline and the shipped one wins.**
  Placing Zones at their measured proportions costs `beside_agreement`
  0.7265 → 0.6814 and trebles clipping; merging Bands into columns costs tau.
- **Height is not the blocker.** Held at `height_ratio` 1.0284,
  `beside_agreement` was still 0.6628 — below the control.
- **One fault sits under both symptoms:** four *enclosed Zones* in three
  documents (`cv_0013`, `menu_0012`, `statement_0006`), each a Band holding a
  narrow box wholly inside a wide one. They are the same three documents whose
  `DTH_SNAP_ZONES` is discarded — **three of fifteen, not four as A2's prompt
  says** — and they block the one renderer change that helped.
- **`alignment_agreement` cannot gate the work.** Flipping 42 cells to
  right-aligned in `statement_0006` moved it 0.935 → 0.935. **Alignment stays
  in A2 gated on a count of named columns, checked in the DOM** — decided
  2026-09-25.
- **The merged Zone — the 49 biggest inside-Zone pairs — cannot be found in
  the pixels.** `form_0007`'s Zone has **zero** interior gutters. `menu_0012`'s
  has one clean 38px gutter against a 1px runner-up, and **22 Zones that must
  not be split** still rank above it by share, `invoice_0001`'s two-column
  tables at 0.759 and 0.665 among them. A third test — do the printed lines
  straddle the gutter — puts `menu_0012` at 0.86, *between* two genuine tables.
  **Three pixel-side tests, three failures; do not build a fourth.** Two menu
  sections and a two-column table are the same shape, and telling them apart is
  reading the words. If it is re-opened it is a **model** question asked as
  *how many regions*, and its own phase.

**The offline loop is proved and is the reason all of that cost no model time:**
re-rendering a run's own embedded IRs gives 15 byte-identical documents and 0
differing scored fields, in about 50 seconds.

### 2. Open, and nothing owns it

- **The across-Zone title echo.** `menu_0012` prints `To begin` twice in two
  different Zones; `darkdeck_0009` prints a caption `AVAILABILITY` above a table
  whose first column header is `AVAILABILITY`. A0 closed the *within*-Zone echo;
  `_without_title_echo` compares a Block against its own Zone's Title and has
  nothing to say about a neighbour.
- **`statement_0006`'s 41 near-identical caveat lines** should aggregate to one.
  Ours, from A-1, no model time.
- **`receipt_0010`'s untested lead.** `preprocess.resize_long_edge` never
  enlarges — its docstring argues enlarging "adds no detail" — and this document
  rectifies to **335×547**, so the extractor sees ~300px across 19 lines of
  monospace. True of information, possibly false of legibility. ~6 minutes to
  probe, and it is the worst document in the corpus.
- **`nonlatin_0014`'s dark-blue table header row** renders on white. Do not
  build a third detector; point `chrome()`'s existing title-band measurement at
  the row `RowRole.header` already names.
- **`catalogue_0015` at 61.7%**, loss not declared. See fault 2 above.
- **`invoice_0001`'s `Invoice` / `#: 123`.** A **Pair label/value boundary**,
  not a `<br>` — its broken joins are `invoice|123`, `created|january`,
  `due|february`. Neither A1 migration could reach it; it needs the Pairs
  Extractor to choose a different split point.
- **A confirming sweep** for A1's shipped 8 of 42, and the one false mark left
  (`invoice_0001`'s `12345`, worth 0.0029 of `join_recall`).

### 3. Raising clause 1, if anyone wants to

The separate pass works and still reaches only 8 of 42, all `link` or `code` in
`prose`. The cheapest untried lever is the one Thread 2/B used for colour:
**measure weight and monospace off the pixels rather than asking.** That needs
word-level ink segmentation the project does not have.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session counts.
  **Five exceptions, all committed files:** `tests/frozen/run84/`,
  `a1-checkpoint/`, `a0-checkpoint/`, `a0-result/` — the floor — and
  `a1-result/`, added 2026-09-25, which is **the control, not a floor**: the
  fifteen documents A1 shipped plus their scores, proved to regenerate those
  scores exactly (0 differing fields). It is what makes a renderer change
  measurable offline in ~50 seconds without a sweep.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the four shipped defaults or the three wire-level row nets** —
  `_without_empty_rows`, `_join_split_header_row`, `_without_repeated_header`.
  Each invents nothing and discards nothing.
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
- **Figures as placeholders** stay in A3.
- **Thread 3/C** stays gated on its re-scoping classification. A-1's finding
  stands: the conversion is deterministic, so a loop re-reading the same crop
  gets the identical wrong answer back.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-result/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

**A renderer-only or pixel-only change needs no new run.**
`tools/remeasure_style.py <sweep> --label <new>` re-measures the Style Record
and re-renders from a sweep's own embedded IRs with zero model calls. It cannot
move anything the model decided.

**A post-model change can be verified without a sweep by offline replay** — feed
a run's recorded answers back through the shipping mapper. Validated to four
decimal places on every mean on 2026-09-22, and used throughout A1: the replay
harness was first made to reproduce `a0-result` exactly before any conclusion
was drawn from it. **Do that check first, every time.** Upstream of the model it
proves nothing.
