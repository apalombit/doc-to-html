# Look like the document

**Status: open. Threads 0, A-1, 2/B, A0, A1, A2 and A3 closed; the open issues are next.**
`docs/status.md` is the live state. Opened 2026-09-17. Tracking issue **#30**. This spec changes what the project is
measured against. It supersedes ADR 0002, retires `acceptance.compare()` and the
five typed fixture builders, and replaces a single mismatch total with a six-axis
rubric under a hard content ratchet.

**One sentence:** the acceptance harness is saturated — it scores two fixtures as
perfect matches while one of them has deleted every column header of its only
table — so the target moves from *structural agreement with a typed reference* to
*visual and content correspondence with the source document*.

---

## What changed under this spec's feet — read this first

Everything below rests on one scope change, made explicit so no number in the
older specs is mistaken for a number here.

**The old target was: does the IR agree with a hand-typed reference IR.**
`acceptance.compare()` pairs Zones by geometry and scores Kind, Role, Title and
RowRole against `tests/fixtures/*.py`. A total of 10 findings on run 84 was the
project's steering signal.

**The new target is: does the rendered output look and read like the source
document.** Compared against `example/*.html` and `example/*.png` directly.

Consequences that must be internalised before reading further:

- **Every finding count in specs 0001-0006 is now doubly dead.** They already
  predated the geometry-aligned comparison and the re-derived rectangles; they now
  also measure a quantity this project no longer optimises.
- **`acceptance.compare()` and `tests/fixtures/*.py` are deleted** in Thread 0.
  `geometry_score.align()` survives as a component of the new T3.
- **A "match" under the old harness is not evidence of anything.** Two fixtures
  held one, and the section below says what they actually produced.

---

## Problem statement — what the pictures show

Taken by opening `debug/runs/84-rule-not-a-line/<fixture>/05_rendered.png` beside
`01_layout_input.png` for all five fixtures, and `debug/runs/81-new-defaults/` for
one before/after. **`debug/runs/` is gitignored and will be cleared**, so Thread 0
freezes the five output documents into the repository before anything is deleted
(see *Thread 0, step 1*). Until it does, this section is the only record.

### The harness and the pixels now disagree, in both directions

**`sample_table_0003` scores `match` and has lost every column header.**

The source table's header row reads `Country | ISO | Population | GDP (USD M) |
Currency`. The output has no header row. In its place, the caption, twice. From
`dump/qwen3-vl_4b/sample_table_0003/04_table.json`:

```json
{"role": "header", "cells": ["Population and GDP (millions of USD)", "", "", "", ""]}
```

The causal chain is exact, and every link in it shipped as an improvement:

1. `DTH_CAPTION_PASS` lifts the caption into `Zone.title` — but does **not**
   withhold it from the crop handed to the table Extractor.
2. `with_grid(titled=)` subtracts the caption's printed line from the row budget,
   so `04_table.prompt.txt` ends: *"This region has been measured from the page:
   it holds 16 rows and 5 columns. Return exactly 16 rows."*
3. The crop still shows 17 printed lines. The model obeyed the count and dropped
   one. It dropped the real header and kept the caption.

Five column names — the entire semantic key of the table — deleted, and the
harness reports a full match, because it compares `RowRole` sequences and never
compares cell **content**. This is the same class of bug as
`wire._without_empty_rows` filtering on `if row.cells`: the check counts rows, not
what is in them.

**Run 81 → 84 improved the score 23 → 10 and made `sample_css_0004` visibly
worse.** Run 81's render shows `Card heading` once. Run 84's shows it twice —
once in the shaded `h2.zone-title` bar, once again as the body's first `heading`
Block. `DTH_CAPTION_PASS` sets `Zone.title` and nothing removes the corresponding
Block. It occurs in three of five fixtures, roughly eight places, and scores zero
findings because `Zone.title` is compared for equality and the body is never
compared against it.

**This is the failure the whole spec exists to prevent:** a metric that moved the
right way while the artefact moved the wrong way, with nothing in the harness
able to say so.

### The full catalogue, from the images

**Content loss and duplication** — top of the rubric, and currently unmeasured:

- `sample_table_0003`: table header row destroyed (above).
- Titles duplicated: `invoice_0002` ×3, `sample_css_0004` ×2,
  `sample_semantic_0005` ×4.
- `invoice_0002`'s header became a Pairs panel repeating itself — `Invoice | With
  Credit` beneath a caption bar reading `Invoice With Credit`.
- `invoice_0001`: `Invoice #: 123` split at the wrong point — label `Invoice`,
  value `#: 123`.
- Logos absent. `invoice_0001`'s coloured mark renders as a dashed placeholder;
  `invoice_0002`'s ACME block is simply gone.

**Structure:**

- `sample_semantic_0005`: `Tags: html, web, standards` — one inline line — became
  a three-item bulleted list. The Benefits list lost two of three bullets to a
  neighbouring Zone.
- Paragraphs carry the source image's line wrapping as hard breaks. **This is the
  schema, not a bug:** `Block.lines: list[Cell]` and `render.py:334` is
  `"<br>".join(...)`. A paragraph in this IR *is* a list of lines, so no output
  can ever reflow.

**Inline — total loss.** Every link is plain text (`Anchor links`, the nav items,
`editor@example.com`, the tag list). Every code span is plain text (`<style>`,
`<head>`, `<article>`, `<nav>`). `sample_css_0004`'s blue `CSS` badge, inline with
the `h1`, became a separate line reading `css`.

**Layout proportion.** `sample_semantic_0005`'s TL;DR aside is ~35% of the width
in the source and ~50% in the output, because `render.py:39` is
`.band > * { flex: 1 1 12rem }` — columns are **always** equal, and no width
exists in the IR to be wrong about. Height inflation against source aspect, at
each output's own width:

| fixture | source aspect | output aspect | height inflation |
|---|---|---|---|
| `invoice_0002` | 1.620 | 1.051 | **+54%** |
| `sample_table_0003` | 1.391 | 1.150 | +21% |
| `sample_css_0004` | 1.475 | 1.240 | +19% |
| `sample_semantic_0005` | 0.816 | 0.699 | +17% |
| `invoice_0001` | 1.533 | 1.456 | +5% |

**Not a defect:** the dark backgrounds. `tools/inspect_run.py:352` shells out to
headless Chrome with no colour-scheme flag, so it inherits the host's dark mode
and `render.py:29`'s `@media (prefers-color-scheme: dark)` fires. Thread 0 pins
the flag. It does mean every visual comparison eyeballed in this project to date
was against an inverted page.

### Why more of the same will not help

| The page has | The IR has |
|---|---|
| inline runs (link, code, em, badge) | `Cell.text: str` — a flat string |
| colour, background, borders, rules | nothing |
| font family, size, weight | `Block.kind`, an 8-value enum |
| alignment | nothing |
| column proportions | `band: int`, `column: int` |
| reflowable paragraphs | `lines: list[Cell]` joined by `<br>` |
| a logo | `graphic_kind: str` — a label, no pixels |

Every visual gap listed above is in the right-hand column. The remaining 10
findings of run 84 are all in the left-hand column of a table whose right-hand
column is empty. **Grouping and Kind are finished as a place to spend effort.**

---

## The criteria

### Six axes, scored source-image against rendered-output

| # | Axis | Asks |
|---|---|---|
| 1 | **Completeness** | Is every printed string present, exactly once? Nothing invented? |
| 2 | **Order & grouping** | Right reading order; things that belong together are together; nothing orphaned |
| 3 | **Layout skeleton** | What sits beside what; column proportions; height ratio at matched width |
| 4 | **Typographic weight** | Heading hierarchy visible; emphasis where the source has it; alignment |
| 5 | **Palette & texture** | Background, ink, accent, shaded bands, borders, cards, rules |
| 6 | **Inline detail** | Links, code spans, badges, marks |

### Priority when they conflict

**Axes 1, 2 and 3 are a hard tier.** A regression on any of them fails the phase
regardless of what improved elsewhere. Axes 4 and 5 are a soft tier, traded off
against each other and judged on net movement. Axis 6 is last.

**The T1 ratchet: completeness may never decrease between phases, for any
reason.** This single rule catches all three of the faults that shipped as
improvements — the deleted table header, the duplicated titles, and the
`invoice_0001` label mis-split. It is not a target to optimise; it is a floor to
never cross.

### How each axis is measured

Axes 1–3 are **deterministic code** and are the spine that stays comparable
across sessions. Axes 4–6 are deterministic where the quantity is measurable and
judged where it is not.

- **T1 Completeness** — normalised token recall and precision, `project(source)`
  against `project(output)`. Recall < 1.00 means content was lost; precision <
  1.00 means content was duplicated or invented. **Both must reach 1.00 and stay
  there.**
- **T2 Order** — Kendall tau between the two projections' text sequences.
- **T3 Layout** — pairwise side-by-side relations (for each pair of content items,
  do they share a row in both), plus column-width ratios within ±15%, plus
  `height_ratio` at matched width. Deliberately *relational*, not IoU: a box 20px
  off is not a finding, and chasing IoU is the overfit this spec is escaping.
  `geometry_score.align()` is reused here.
- **T4, T5** — measurable parts computed (heading size ratios, alignment from ink
  centroid, sampled palette deltas); the rest judged.
- **T6** — counted: links, code spans and marks present in `project(source)` and
  absent from `project(output)`.

### Judgement, and its honest limits

The judge is Claude, reading the comparison report's image pairs directly. Two
rules, both borrowed from what this project already learned about run numbers:

- **Pairwise, in one sitting.** The verdict is *previous output vs new output,
  both against the source, side by side, now* — never an absolute score compared
  against a score from another session. A 3.5 today and a 3.7 next week are not
  comparable and must never be tabulated as though they were.
- **Justification, not a number.** Each axis gets a sentence naming what was seen.
  The sentence is the auditable artefact; the score is a convenience.

---

## Ground truth

**The expected answer is already on disk.** `example/invoice.png` is a screenshot
of `example/invoice.html` — `tools/fixture_geometry.py:56` records it re-rendering
at 0.74% of pixels differing. So the reference is not typed, it is *derived*:

```
example/foo.html  ──render in Chrome──>  project() ─┐
                                                    ├──> diff ──> T1..T4, T6
output document.html ─render in Chrome──> project() ─┘

screenshot(output, width=source_width)  vs  example/foo.png  ──> T5
```

`project()` is **one function applied to both sides**, returning a normalised
view: text runs in reading order, block roles, and rectangles from Chrome client
rects.

**It must never compare raw markup.** Demanding the output reproduce the source's
div nesting or its Bootstrap class names is a worse overfit than the one being
escaped. The projection is what a reader perceives, not how the author typed it.

**Adding a document becomes: write `foo.html`, screenshot it, done.** No Python,
no transcription. That is what lets the corpus leave five.

**Known limitation, stated plainly:** this makes the scorer **synthetic-only by
construction**. A photograph has no source HTML and cannot be scored on T1–T4 or
T6 at all. `preprocess.*` — deskew, illumination correction, rectification,
page-edge detection — is therefore **unexercised by anything this spec builds**,
and may rot silently. Thread 2/B's colour sampling assumes flat illumination and
will read a shadow gradient as the page colour. **Revisit trigger:** when T1
holds at 1.00 across a full phase on the sweep set, build the degradation
generator ADR 0003 already describes (skew, blur, shadow, JPEG noise applied to
the rendered source, ground truth unchanged).

---

## The comparison report

**One page, one place, every document, side by side.** Written to
`debug/runs/<label>/report.html` — the run root, not per-fixture folders.

Required, because reviewing five documents currently means opening five folders:

- **Every document in one scrollable page**, source image left, rendered output
  right, both at matched width so proportions are directly comparable.
- **Scores above each pair**, with the delta against the previous run, and any
  T1/T2/T3 regression flagged as a phase-gate failure.
- **The intermediate steps that matter, inline and collapsed** — detected boxes
  over the source, and the crops that produced any Zone with a finding. Expanded
  only on click, so the default view is purely source-vs-output.
- **Self-contained**: images inlined or referenced relatively, so the file can be
  moved or published without breaking.

`tools/inspect_run.py`'s per-fixture `index.html` **stays as it is** — it is the
execution-order trace and it is the right tool for diagnosing one document. The
report is the comparative view across all of them, and answers a different
question. Both are generated by the same run.

---

## Threads

```
Thread 0    Scorer, corpus, report        gate: reports run 84's faults unaided   DONE
Phase A-1   nothing loses content quietly gate: the honesty rule                  DONE, gate NOT met
Thread 2/B  Style record (CV)             gate: height_ratio -> 1.0, palette delta   DONE bar the type scale
Thread 1/A  The rest of the IR
   A0         stop the bleeding           gate: RE-SCOPED ON ENTRY, see below     DONE, gate MET
   A1         inline runs, hard breaks    gate: set on entry                       DONE, gate NOT met
   A2         geometry — RE-SCOPED        gate: set on entry, see 0007-a2-measurements.md   DONE, gate MET
   A3         figure pixels               gate: set on entry                       DONE, gate MET
Open issues  one at a time, cheapest first (docs/status.md "Next")               <- next
Thread 3/C  Repair loop                   gate: re-scoped against A+B residuals
Thread 4/D  Human corrections             unscheduled
```

**2/B moved ahead of A0 on 2026-09-20**, on A-1's checkpoint evidence. A0 moves
precision (0.91–0.98 across the corpus) — real but small — while `height_ratio`
runs from 1.03 to **3.70** and the renderer cards every titled Zone on roughly
ten documents. 2/B is also the only thread that adds no model call, so it is
deterministic, testable offline, and cannot threaten the ratchet A-1 just set.

**`Document.page_px` is measured in 2/B and drawn in A2** — it moved out of A2
on 2026-09-20 and measurement sent it back. The reasoning for moving it was
that `render.py` caps every page at a 52rem house column (~832px) while 9 of
the 15 sources are wider, up to 1164px. Carrying the true width does close that
gap, and it costs `invoice_0002` `beside_agreement` 0.640 → 0.295 — **the hard
tier** — for `height_ratio` 1.63 → 1.60 on that same document and nothing on
the other four. The cause is `flex:1 1 12rem` approximating the source's
columns by accident, which is A2's band model, so 2/B keeps the measurement and
A2 gets the rule. **`Zone.align` never moved**; it stays in A2 too. All of it
is recorded so none of it reads as drift.

Checkpoint runs after **0, A-1, B, A0, A, C**. Each produces a comparison report.

---

### Thread 0 — the ruler, the corpus, and the report — **DONE 2026-09-18**

**What landed**, and the three places it differs from what is written below.

- `corpus.py`, `projection.py`, `scoring.py`, `report.py`. Unit tests in
  `tests/test_scoring.py` and `tests/test_projection.py`, offline against
  `tests/frozen/run84/`.
- **The scorer finds the Title duplication in four documents, not three.** It
  is right and this spec was not: `sample_table_0003`'s caption is repeated by
  the same mechanism, and this spec filed it separately under the lost header
  because that is what someone noticed rather than what is there.
- **T1 as specified cannot see the `invoice_0001` mis-split.** The ratchet
  paragraph below claims it catches all three shipped faults; `Invoice #: 123`
  read as label `Invoice`, value `#: 123` has exactly the source's tokens in
  the source's order, so recall, precision and tau are all perfect.
  `Completeness.join_recall` — the adjacent-word pairs — is what catches it,
  and it is reported beside the other two for that reason.
- **Three faults were in the rendering harness, not the IR**, and none was
  visible in any number: headless Chrome inheriting the host's dark mode, a
  500px layout floor that cropped a narrow document's own screenshot, and a
  screenshot at exactly the page height dropping its last row while
  `project()` still reported that row present. The last is T1 and the pixels
  disagreeing about whether content exists — the failure this spec warns about,
  arriving from the tooling. See `CLAUDE.md`'s first lesson.
- **Not finished:** `OllamaEngine.detect_zones` and `LAYOUT_PROMPT` survive as
  the seam the recorded-response suite replays against. Unreachable from a
  Conversion; removing them means replacing the layout stage of nine test
  modules.

Nothing else can be believed until this exists. It builds the measure, grows the
corpus past the five documents the system was built against, and produces the
review surface.

**Step 1 — freeze the evidence, then delete the old harness.** In this order:

1. Copy run 84's five `dump/qwen3-vl_4b/*/document.html` into
   `tests/frozen/run84/`, with a README stating each one's known faults. These
   become offline inputs for developing the scorer **with no model calls**, and
   they are the permanent record of the problem statement above once
   `debug/runs/` is cleared.
2. Delete `src/doc_to_html/acceptance.py`, `tests/fixtures/*.py`,
   `tests/test_fixture_0002.py`, and every test that depends on them.
3. Keep `geometry_score.py`. `align()` is reused by T3.
4. Delete the vision layout path: `DTH_LAYOUT_DETECTOR=none`, its prompt, and
   `DTH_LAYOUT_LONG_EDGE` (which exists only to serve it, has no docstring, and
   ships at a value no recorded run used). It raises `MappingError` on three of
   five fixtures, matches none, and would otherwise need maintaining through every
   IR change in Thread A for no measured benefit. Closes issue #17, whose thread
   already said to re-scope it because the pass it edits may not survive.

This is deliberately delete-first. The risk is being blind to regressions during
Thread 0; the frozen outputs in step 1 are the mitigation, and they cover it
because Thread 0's own correctness is judged by whether the scorer reports faults
already established by eye.

**Step 2 — `project()` and the scorer.** One function, both sides, per *Ground
truth* above. Unit-tested against `tests/frozen/run84/`: the scorer must
independently report the deleted table header, the eight duplicated titles, and
the hard line breaks, without being told they are there. **That is Thread 0's exit
gate.**

**Step 3 — the comparison report**, per *The comparison report* above.

**Step 4 — pin the Chrome colour scheme** to light in `tools/inspect_run.py` and
`tools/fixture_geometry.py`, so every comparison from here is fair.

**Step 5 — grow the corpus to ~15.** Authored here rather than collected, for
three reasons: no licensing question, deterministic re-rendering, and guaranteed
ground truth. **Named limitation:** documents authored here risk being documents
that are easy to author. The mitigation is that each is modelled on a real-world
archetype and deliberately carries the awkward feature named beside it, and that
the list was chosen from the blind spots of the existing five rather than from
what is convenient to write.

| new document | archetype | what it breaks that the current five do not |
|---|---|---|
| `statement_0006` | bank statement | 40+ rows, zebra striping, right-aligned currency, running balance, a summary row |
| `form_0007` | application form | labelled input boxes, checkboxes, ruled fill-in lines, empty values, a two-column field grid |
| `newsletter_0008` | newspaper page | three columns, serif body, drop cap, pull quote, hairline column rules |
| `darkdeck_0009` | dark report page | light ink on dark ground — breaks the CV assumption that pages are light, and every binarisation default |
| `receipt_0010` | thermal receipt | narrow portrait aspect, monospace, centred header, dotted separators |
| `report_0011` | corporate report | heading hierarchy h1–h4, numbered sections, footnotes, a small table set inside prose |
| `menu_0012` | restaurant menu | leader dots between item and price, two columns, decorative rules, mixed type sizes |
| `cv_0013` | CV | asymmetric ~30/70 sidebar split — the direct test of Thread A2's column widths |
| `nonlatin_0014` | invoice, Greek or Cyrillic | non-Latin script, different text metrics, OCR and VLM assumptions |
| `catalogue_0015` | product grid | 3×3 repeated sibling cards, image placeholders, shaded card backgrounds |

**Step 6 — split the corpus.** *iterate* = the original five (~17 min of model
time, run on every change). *sweep* = all fifteen (~50 min, run at phase gates).
Per-document model time on `qwen3-vl:4b` measured from run 84's `trace.json`:
`invoice_0002` 301s, `sample_semantic_0005` 300s, `invoice_0001` 174s,
`sample_table_0003` 132s, `sample_css_0004` 128s.

**Exit gate:** the scorer reports run 84's three known faults on the frozen
outputs, unaided; the report renders all fifteen documents in one page; a
checkpoint run exists.

---

### Thread 1/A — the IR

Raises the ceiling. Nothing in Threads B or C can exceed what the IR can express,
so this is the precondition for both.

**Phase A0 — stop the bleeding.** The content faults, first, because
completeness is the top of the rubric and all of them are currently *shipped
behaviour*.

1. **Table header loss.** The caption is lifted into `Zone.title` but stays in the
   crop, while the row budget is reduced for it. Either withhold the caption band
   from the Extractor's crop as well as from the Kind question, or stop
   subtracting from the row count. Withholding is correct — it makes the picture
   and the arithmetic agree, rather than agreeing with each other about a picture
   neither has seen.
2. **Title duplication.** A Zone carrying a Title must not also carry a Block
   repeating it. This is a schema rule, enforced in `wire.py` where the Title is
   bound, not a filter in `render.py` — the IR should not be able to hold the
   contradiction in the first place.
3. **`wire._without_empty_rows` filters on cell count, not cell content.**
   `if row.cells` is truthy for `['', '', '', '', '']`, so an all-blank row
   survives the net that exists to drop it. Fix the condition; the net stays.

**Hard line breaks moved to A1 — decided 2026-09-22, and this list is three
items rather than four because of it.** `Block.lines: list[Cell]` joined by
`<br>` makes reflow impossible by construction, and it is a real fault:
`newsletter_0008` emits 31 `br` against a source with none. It is also a schema
change to `Block.lines`, and A1 already rewrites `Cell.text` into a run
sequence — doing both at once is one migration through those structures instead
of two. A0 keeps the three faults that stop content being lost or doubled.

### A0's gate — set 2026-09-22, from measurements taken before any code changed

The pre-registered `T1 = 1.00` was disproved on 2026-09-20 and is not replaced
by another ratio. **Three of the five clauses below are counts of a named
structure rather than a ratio**, for the reason this spec exists: a ratio cannot
say *which* strings came back.

Every number was measured offline over `tests/frozen/a0-checkpoint/`'s own
output IRs — edited, re-rendered and re-scored with no model call — so each
clause is a prediction that can be checked rather than a target chosen to be
reachable.

**1. Title echoes go to zero.** A Zone carrying a Title must not also carry a
first Block, a first row, or a first pair repeating it. **34 today** — 27
Blocks, 5 table row-0s, 2 pair-0s — across 12 of the 15 documents. Measured in
the IR, so it needs no source, no OCR agreement and no model.

**2. `sample_table_0003` returns its five column headers.** `Country | ISO |
Population | GDP (USD M) | Currency`, and 16 rows. Today row 0 is the caption
`Population and GDP (millions of USD)` tagged `header` and all five column
headers are absent — the fault this spec was opened over, still shipped.

**3. No table Zone carries an all-blank row.** One today: `report_0011` z6
row 5 = `['', '', '', '']`.

**4. The T1 ratchet holds — re-pointed to distinct tokens.** No source token the
output shows today may stop being shown, on any document; `tau` and
`beside_agreement` may not fall. See the section below: this changes the
ratchet's measure, and why it had to change is itself an A0 finding.

**5. Precision reaches 0.975 mean and falls on no document.** 0.934 at the
checkpoint; removing the echoes alone predicts **0.977**. This is the
"0.91 to 0.98 against precision" the handover asked for, derived rather than
guessed.

**Standing, unchanged:** A-1's honesty gate must not newly fail, and the visual
review's content axis must move from major to match on the doubled title,
judged pairwise against a baseline render in one sitting.

### Why the ratchet's recall leg is now distinct tokens

**Decided 2026-09-22, and it is a change to this spec's central invariant.**

Removing a doubled Title *lowers* multiset token recall on six of the fifteen
documents — 0.851 to 0.848 overall, at most 0.019 on any one. Nothing leaves the
page. The cause is that the echo was **numerically standing in for a genuine
occurrence elsewhere that the output never read**: `newsletter_0008` prints
"Castleton Chronicle" twice on the page, in the masthead and in the footer; the
output printed it twice *in the masthead Zone*, and the multiset was satisfied.
Remove the echo and the count reports what was always true — the footer copy is
missing. The same shape holds on `darkdeck_0009`, `report_0011`,
`statement_0006`, `form_0007` and `sample_table_0003`.

Measured over all fifteen: **no source token goes from present to absent on any
document**, and `tau` is unchanged on every one.

So the ratchet's stated intent — *no content that previously converted stops
converting* — is intact, and its measure was tripping on bookkeeping. Taken
literally on the multiset it would have **forbidden A0's correct fix on six
documents for making the page right**, which is the same failure, in the same
direction, as the three this spec catalogues.

Multiset recall and precision stay reported on `report.html`, where a fall is
worth reading. The **floor** is the distinct-token one, and the report names
every token that vanished, so the clause that fails says what it caught.

*Rejected:* keeping the multiset floor and taking A0 as a written exception —
that sets the precedent that the ratchet is overridable by argument, which is
what it exists to prevent. *Also rejected:* leaving the echo in place wherever
removing it would drop multiset recall — not implementable, since the pipeline
has no source, and it would leave the fault on the two documents that show it
worst.

### Why `Completeness.duplicated` is not the gate

**The obvious field under-reports, and finding out why was A0's first task.**
`_duplicated_strings` reports only strings the *source projection* also carries
and compares whole blocks. It sees 30 excess repeats at the checkpoint and
**misses 18**:

- **`report_0011`, 8 — all of them.** Its section numbers are CSS `::before`
  counters, so `project()` cannot see them: the source block is
  `Purpose and scope`, the model reads the picture and returns
  `1. Purpose and scope`, `have` is 0, and the detector switches off for exactly
  the document that prints all eight of its headings twice.
- **`nonlatin_0014`, 6.** The source sets its date line as one block and the
  output splits it into five, so no output block's text matches a source
  block's.
- **`invoice_0002`, 1.** `Comments / Notes` lives inside its paragraph block in
  the source.

Any OCR slip, punctuation difference or blocking difference between the model's
reading and the source's markup turns it off. A measure blind in a direction is
unconstrained in that direction, so the gate counts the structure in the IR
instead.

### A0's result — sweep `100-a0-gate`, 2026-09-22, **gate MET**

All fifteen, against `tests/frozen/a0-checkpoint/`.

| | floor | 100-a0-gate |
|---|---|---|
| **vocabulary recall** (the ratchet's leg) | 0.8599 | **0.8653** |
| recall (multiset) | 0.8513 | 0.8542 |
| **precision** | 0.9342 | **0.9765** |
| join recall | 0.8088 | 0.8128 |
| tau | 0.9356 | 0.9381 |

Five clauses, five met: **34 title echoes → 0**; `sample_table_0003` returns
`Country | ISO | Population | GDP (USD M) | Currency` and sixteen rows; **0**
all-blank rows; **0** repeated header rows; no document stopped printing a
source word it printed at the floor, and precision ≥ 0.975.

Reviewed with the `visual-review` skill against `99-a0-heading-guard`, all
fifteen sheets opened. **No `worse` on any document**, two `better`
(`darkdeck_0009` and `report_0011` each printed a table header row twice in 99
and print it once in 100), and — for the first time — **no `major` sitting
beside scored ratios all at 1.000.**

**What shipped:** `wire._without_title_echo`; `_without_empty_rows` testing cell
*content* rather than cell *count*; `with_grid`'s row subtraction removed;
`wire._without_repeated_header`; a heading guard in `detector._trailing_row`.

**What was built, measured and reverted — do not rebuild it.** Withholding the
caption band from the **Extractor's crop** was the agreed fix for fault 3 and it
deletes real content: `darkdeck_0009` z2 is a row of four metric cards with no
caption at all, and cutting the top band removes `P95 LATENCY`, `INGEST VOLUME`
and `COST PER MILLION` — confirmed by opening the crop image, not inferred. It
also moves the measured column count on three other tables. Widening
`CaptionBand.aligns_to_grid` to a ratio instead strips four real captions
corpus-wide. The arithmetic was corrected on the *count* side instead, which is
the cheaper of the two repairs: dropping a count can only be wrong, where
cutting a crop can destroy.

**Found by closing fault 1, and open.** The echo rule compares a Block against
*its own* Zone's Title, so two Zones that each read the same printed line still
print it twice: `menu_0012` prints `To begin` twice, and `darkdeck_0009` prints
a caption `AVAILABILITY` above a table whose first column header is
`AVAILABILITY`. Nothing owns the across-Zone case.

**Two corrections to this spec's own problem statement, both measured.**
`sample_table_0003` was named as the document returning a 17th row of empty
strings; it has 16 rows and none blank, and the live all-blank row was
`report_0011` z6 row 5. And removing a title echo *lowers* multiset recall
without anything leaving the page, which is what moved the ratchet's recall leg
to distinct tokens — see the two sections above.

### A0's notch

`tests/frozen/a0-checkpoint/`, committed 2026-09-22, with its provenance in that
directory's README. **A0's gate is not the ratchet's notch and never was** —
`tests/frozen/a1-checkpoint/` is where the ratchet started, and it stays as the
record of that.

**A0 did not re-freeze the notch, and that is a standing decision to revisit,
not a conclusion.** A1 therefore ratchets against `a0-checkpoint/` — the floor
A0 cleared, not the level A0 reached. The consequence is explicit: A1 could
give back A0's precision gain (0.9765 → 0.9342) and still pass. Freezing
`100-a0-gate`'s scores as A1's starting notch would close that, at the cost of
committing another `scores.json` and making every later phase answer to a
tighter floor.

**Phase A1 — inline runs, and hard line breaks.** `Cell.text: str` becomes a
sequence of runs (`text | link | code | em | strong | mark`), and in the same
migration `Block.lines: list[Cell]` joined by `<br>` becomes reflowable text —
moved here from A0 on 2026-09-22 because both rewrite the same structures and
doing them once is cheaper than doing them twice. The per-line Cells stay
reachable, because they are what `Correction` anchors to and what makes each
reading a ground-truth label.

The run sequence is currently a 100% loss and the most visible gap per unit of
work: links, code spans and badges are absent from every document that has
them. Raises T6 from zero.

**Phase A2 — geometry the IR cannot currently state.** *Re-scoped on
2026-09-25 by its own measurements and closed the same day, gate met — the
paragraph below is what was planned, and
[`0007-a2-measurements.md`](0007-a2-measurements.md) is what was found: two
thirds of the side-by-side fault is inside one Zone, every renderer replacement
lost on the hard tier, and what shipped was the enclosed-Zone rule plus three
renderer fixes. `Document.page_px` stays measured and undrawn.* `Zone.align`
(left/right/centre), `Zone.width` as a share of its Band, and `Document.page_px`.
Replaces `render.py:39`'s always-equal `flex: 1 1 12rem` and `render.py:36`'s
fixed 52rem house column. Directly targets T3: the TL;DR aside's 35%-vs-50% and
`invoice_0001`'s lost right-alignment.

**Page geometry decision:** the output carries the source's **width** and lets
height fall out — `.doc { width: <source>px; max-width: 100% }`. Not a fixed
height. Fixed height makes every vertical dimension a constraint that must be
simultaneously exact, which it cannot be when our text differs from the source by
one OCR slip; the result is clipping, which means **content T1 can see in the DOM
and T5 cannot see in the pixels** — two tiers disagreeing about whether content
exists. With width pinned and height free, `height_ratio` instead becomes the
single best diagnostic available: 1.54 on `invoice_0002` says the vertical rhythm
is wrong, and that is Thread B's primary target.

**Phase A3 — figure pixels.** *Closed 2026-09-26, gate met, 8 of 8 —
[`0007-handover.md`](0007-handover.md), "Phase A3", "Outcome" is the record.*
A `FIGURE` Zone carries its crop, not just a `graphic_kind` label: `Zone.pixels`,
drawn as an `<img>` with what was read off it as `alt`. `figures_lost` 2 → 0,
and `invoice_0002`'s ACME tile split out of the `picture` box that swallowed it.

**Gate for Thread A: T1 holds at 1.00; T3 and T6 improve on the sweep set;
contact sheet reviewed.**

---

### Thread 2/B — the style record

**All CV. Zero added model calls.** The argument is a lesson already in
`CLAUDE.md`: *an instruction is reachable only if it asks the model to decide
differently, not to perceive differently.* Colour is perception, and the pixels
are already in hand. Sampling a pixel is exact, free, deterministic and cannot
hallucinate; asking a 4B model what colour a band was is strictly worse on every
one of those.

| quantity | how |
|---|---|
| `page_bg`, `ink`, `accent`, `shade` | sample pixels — modal background, modal ink, most-saturated non-neutral |
| `body_px`, `heading_px`, heading scale | ink-band heights, from the banding `preprocess` already does |
| borders, rules, cards | an OpenCV rectangle finder, **which has to be built** — see the correction below. Keep the guard: a rectangle covering more than 0.80 of the page is the page. |
| page width | `Document.page_px`, carried from the Source Image — **measured here, drawn in A2.** Moved here on 2026-09-20 and returned the same day: the CSS rule costs `invoice_0002` a hard-tier `beside_agreement`. See above. |
| column widths | the detected boxes, already computed |
| alignment | ink centroid against the Zone box |
| `family: serif \| sans \| mono` | cheap stroke-terminal guess, **sans fallback** |

**Font family is explicitly de-prioritised and does not gate the phase.** If the
guess is unreliable, fall back to sans and move on; being wrong about serif costs
far less than being wrong about content, and this thread's value is in palette,
type *scale* and card treatment.

Being all-CV also means Thread B is fully deterministic, unit-testable, and
developable against `tests/frozen/run84/` with no model running.

**Correction, 2026-09-20 — the rectangle finder is not in the tree.** This spec,
`CLAUDE.md` and ADR 0005 all said it existed and must not be rebuilt. `git log
-S findContours` across all history returns only `preprocess.find_page_quad`,
which detects the page edge for rectification;
`tools/cv_layout_probe.py`'s `zones_from_morphology` dilates ink into blocks and
cannot see a drawn border. Spec 0006 Change 3 measured it in a scratch script
that was never committed, and three documents then carried the claim forward as
fact. **It has to be built here**, and the two things recorded about it — that
it found exactly `invoice_0002`'s four panels and `sample_css_0004`'s two cards,
and the 0.80-of-the-page guard — are a starting point to **re-measure**, not
results to cite.

**Gate: `height_ratio` moves toward 1.0 across the sweep set; palette delta
falls; T1/T2/T3 do not regress against `tests/frozen/a1-checkpoint/`; contact
sheet reviewed.**

**Expect width alone not to close the height gap.** `menu_0012` is 760px wide —
inside the house column, so not constrained by it — and still has
`height_ratio` 2.77. Vertical rhythm (padding, line-height, card chrome) is a
real second cause and both have to move.

---

### Thread 3/C — the repair loop

Designed here in full. **Its parameters are re-scoped after Thread B's
checkpoint, against measured residuals rather than predicted ones** — a repair
loop is a search over residual errors, and the residuals it will actually face
are the ones A and B leave behind, not the ones visible today.

**Design.**

- **Inputs per iteration:** the source image, the current render at matched
  width, and the scorer's per-axis findings. Not a free-form "make this better".
- **Mutable surface:** the style record, `Zone.kind`, `Block.kind`, `Zone.width`,
  `Zone.align`. Deliberately **not** text content — the loop may re-interpret what
  was read, never re-read it, because a loop permitted to rewrite text is a loop
  permitted to invent it.
- **Budget:** 3 iterations, revised at the re-scoping gate.
- **Stopping rule:** T5 plateau, budget exhausted, or any iteration lowering T1.
- **Hard guard:** an iteration that lowers T1 is discarded and the loop stops.
  The ratchet applies inside the loop exactly as it applies between phases.
- **Every iteration is traced** through `trace.py` with a `disposition`, like any
  other decision, and appears in the comparison report.

**Re-scoping gate, run after Thread B's checkpoint.** Classify every residual
error:

- **(a) the IR still cannot express it** → widen the IR, not a loop.
- **(b) a pass got it wrong and would get it wrong again** → fix the pass.
- **(c) it needs a second look at the whole page** → this is loop work.

**Build the loop only if (c) is a material share.** If it is not, this thread
closes unbuilt and says so, with the classification as its evidence — the same
way spec 0006's Change 3 closed.

---

### Thread 4/D — human corrections

**Unscheduled.** The hard part already exists: `Correction` is anchored to image
geometry rather than to IR positions, which is what lets a human ruling survive
the prompt changes it exists to evaluate. What is missing is a way to enter one
and somewhere to keep it.

Revisit when real photographs enter the corpus, since that is the case where
derived ground truth is unavailable and a human ruling is the only ground truth
there is.

---

## Testing decisions

**Pre-registered gates, per phase, all conditions required:**

1. **T1 ratchet** — completeness recall and precision ≥ the previous checkpoint.
   No exceptions, no trade-offs, no "but T5 improved".
2. **Target tier improves** on the sweep set — the phase's own axis, measurably.
3. **Contact sheet reviewed** — Claude scores the six axes with written
   justification per axis, pairwise against the previous render in one sitting;
   the user reviews the same page and agrees.

**The gate this replaces, and why.** Spec 0004's Gate 1 was pre-registered,
passed every field it named, and shipped a regression costing a Zone and a Probe
— because it gated a geometry change on geometry fields alone. Condition 1 above
is the general form of the fix that spec already prescribed: *no content that
previously converted stops converting.*

**Unit tests run offline** against `tests/frozen/run84/`, with no model calls, so
the scorer and the style record are testable in CI.

---

## Out of scope

- **Photographs, and the synthetic-to-real gap.** Named limitation with a named
  revisit trigger, above.
- **Absolute-positioned facsimile.** ADR 0002's rejection of positioned text runs
  stands and is not reopened: brittle under skew, and semantically inert — a
  `<table>` becomes a cloud of `<span>`s and screen readers get nothing. What this
  spec reverses is only *"no styling is ever extracted from the Source Image"*.
- **Multi-page documents.**
- **Any new model, or any change of model.** Every measurement here is on
  `qwen3-vl:4b` so that changes are attributable.

---

## Decisions taken, and what was rejected

Recorded so the next reader knows which of these were argued and which were
assumed.

| decision | rejected alternative, and why |
|---|---|
| Style is extracted; output stays semantic | *Structure-only with a smarter stylesheet* — cannot reach palette, type or column proportion, because none of them are in the IR. *Positioned facsimile* — ADR 0002's standing rejection. |
| Ground truth derived from `example/*.html` | *Reference-free via OCR* — works on photographs but OCR errors become phantom T1 failures, and there is no structural ground truth at all. *Keep typed builders* — ~30 min per document and a rewrite of all five per IR widening; the reason the corpus never left five. |
| Carry width, score height | *Fixed width and height* — clipping when our text differs from the source, and T1/T5 then disagree about whether content exists. Also destroys `height_ratio`, the best single diagnostic available. |
| Delete the old harness first | *Keep both permanently* — double maintenance and no rule for which score wins when they disagree, which is how the easier-to-move one gets optimised. *Freeze then retire* — was recommended; delete-first was chosen and the frozen outputs are the mitigation. |
| Corpus to ~15 in Thread 0 | *Expand after Thread A* — risks an IR whose style fields fit exactly these five. *Stay at five* — accepts the overfit as the price. |
| Claude judges pairwise, in one sitting | *Numbers only* — precisely the failure mode that produced runs 81→84. *Absolute scores tracked across sessions* — not comparable, for the same reason run numbers in this repository are not. |
| Thread B all-CV | *One whole-page VLM call* — asks a 4B model to report quantities the pixels state exactly, non-deterministically. |
| Thread C designed now, re-scoped after B | *Defer entirely* — loses the continuity of reasoning. *Build immediately after B* — designs against errors A and B are built to delete. |
| **A0: drop `with_grid`'s row subtraction, keep the Extractor's crop whole** | *Withhold the caption band from the crop as well* — was agreed, built, and **reverted on measurement**: it deletes `P95 LATENCY`, `INGEST VOLUME` and `COST PER MILLION` from `darkdeck_0009` z2, a card row with no caption, and moves the measured column count on three other tables. *Widen `aligns_to_grid` to a ratio* — strips four real captions corpus-wide. |
| **A0: repair the padded header at the wire** | *Restore `with_grid`'s subtraction* — that is what deleted `sample_table_0003`'s headers in the first place. A dropped row is a recall fault; a surplus row is only a precision one, so the repair goes on the side where being wrong costs less. |
| **A0: ratchet on `vocabulary_recall`** | *Multiset `recall`* — removing a doubled Title lowers it while nothing leaves the page, because the echo was standing in numerically for an occurrence elsewhere that was never read. *`Completeness.duplicated`* — blind in three independent ways; it is empty for `report_0011`, which prints all eight of its numbered headings twice. |

---

## Further notes

**Documents to supersede or amend when this lands:**

- **ADR 0002** is superseded by a new ADR. Its rejection of positioned facsimile
  survives; its claim that *"no styling is ever extracted from the Source Image"*
  does not.
- **ADR 0003** is amended: ground truth is derived from the source HTML rather
  than from typed expected IR, and the degradation generator it describes still
  does not exist.
- **`CLAUDE.md`'s baseline section** — the run 84 table, the findings breakdown,
  and "what is left, named exactly" — all describe the retired harness and must be
  rewritten against the rubric once Thread 0's first checkpoint exists.

**Tracker:** this spec needs a GitHub issue. So does `docs/specs/0006`, which
never got one. `#28` (spec 0005) and `#17` (the vision layout prompt) are both
closed by Thread 0 — 0005's remaining Changes 4 and 5 measure against a harness
that no longer exists, and #17's pass is deleted.

**Two dormant safety nets that must survive every thread here.**
`wire._without_empty_rows` and `_reread_as_prose` each guard behaviour that took
four runs to establish, and each looks like dead code on any single run. Do not
delete either while fixing the `if row.cells` bug in Phase A0 — the bug is in the
filter's condition, not in the net's existence.
