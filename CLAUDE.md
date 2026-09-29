# doc-to-html

## Agent skills

### Issue tracker

Issues live as GitHub issues in `apalombit/doc-to-html`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Visual review

**Look at the output, not only at the numbers.** The `visual-review` skill
(`.claude/skills/visual-review/`) builds one sheet per document — source,
optionally the previous run's render, and this run's render, all at the source's
width — and a rubric to answer by opening them. Run over all fifteen documents
on 2026-09-21 it found nine cross-cutting faults that **no scored axis had
reported**.

`doc_to_html.review` is the code and `tests/test_review.py` pins it;
`tools/visual_review.py` is the command line. `--previous <run>` is the
render-against-render comparison the T1 ratchet is built on; `--check` tallies
the answered `findings.json` and names every `major` that sits beside scored
ratios all at 1.000. `docs/agents/visual-review.md` is the record: the evidence
behind the rules, what the rubric must never become, and the remaining gaps.
**The rubric is not frozen** — seven axes with two passes behind them, and a
trial axis is kept rather than rejected.

### Specs

Work in flight has a spec in `docs/specs/`, one file per piece of work, each tracked
as a GitHub issue. **Read the spec before the code** — it carries the measured
numbers and what has already been tried and rejected.

---

## READ THIS FIRST — the target changed on 2026-09-17

**`docs/specs/0007-look-like-the-document.md` is authoritative. Where this file
disagrees with it, the spec wins.** Its tracking issue is **#30**.

The project no longer optimises agreement between the IR and a hand-typed
reference IR. **It optimises whether the rendered output looks and reads like the
source document.** `acceptance.compare()`, `tests/fixtures/*.py` and every
mismatch total this file used to carry are deleted.

**Why, in one paragraph.** Someone finally opened
`debug/runs/84-rule-not-a-line/<fixture>/05_rendered.png` beside
`01_layout_input.png`. `sample_table_0003` scored a **full match** while having
deleted all five of its table's column headers — the harness compares `RowRole`
sequences and never compares cell *content*. And runs 81→84 improved the total
23→10 while *introducing* duplicated titles in three of five documents. The
measure had saturated, and past that point it was steering the wrong way. Spec
0007 carries the full evidence, including the exact JSON and the exact prompt
line that caused the deletion.

**Work order — one thread at a time, each ending at a gate:**

```
Thread 0    Scorer, corpus, report        DONE 2026-09-18
Phase A-1   Nothing loses content quietly DONE 2026-09-19, gate NOT met
Thread 2/B  Style record (all CV, zero model calls)   DONE 2026-09-22
              palette, per-Zone chrome, borders, clipping, width reservation
              and ink contrast all shipped; page width measured-not-drawn;
              type scale deferred with its numbers in style.py
Phase A0    Stop the bleeding          DONE 2026-09-22, gate MET
              its pre-registered T1 = 1.00 gate was disproved and replaced
              from tests/frozen/a0-checkpoint/ before any code changed
Phase A1    Inline runs, and hard line breaks   DONE 2026-09-25, gate NOT met
              reflow shipped and measured clean; inline runs asked INSIDE the
              Extractor prompts crossed the ratchet and were reverted, then
              re-asked as a SEPARATE pass (DTH_INLINE_PASS) which holds the
              ratchet and reaches only 8 of 42 — clause 1 is the open one
Phase A2    Geometry — RE-SCOPED            DONE 2026-09-25, gate MET
              its premise did not survive its own measurements — two thirds of
              the fault is inside one Zone, and every renderer replacement
              tried lost on the hard tier. The column model and the merged Zone
              are CLOSED UNBUILT; three offline wins shipped; the enclosed Zone
              shipped as detector.without_enclosed — it was the detector's own,
              not the snap's, and every enclosed Zone was a duplicate.
              docs/specs/0007-a2-measurements.md is the record.
Phase A3    Figure pixels                   DONE 2026-09-26, gate MET
              a FIGURE Zone carries its crop (Zone.pixels) and is drawn; what
              was read off it is alt text. invoice_0002's ACME tile split out
              by detector.without_overreaching_pictures. figures_lost 2 -> 0
Open issues 1-3 DONE 2026-09-26, offline, ratchet holds 15 of 15
              caveat lines aggregated, header-row fills measured, the
              AVAILABILITY Title echo dropped; issue 4 went to the type scale
Queue       Q1-Q7 in docs/status.md "Next", in order, go given 2026-09-27
              model-free first (menu thead, empty header cell, type scale,
              Thread 0's seam), then the three that cost model time
              Q1 DONE 2026-09-27, Q2 DONE 2026-09-28, both offline,
              both gate MET; Q3 DONE 2026-09-29, re-scoped to heading
              sizes on measurement, gate MET; Q4 DONE 2026-09-29, the
              vision layout pass deleted, no output change   Q5 <- next
Thread 3/C  Repair loop (re-scoped against A+B residuals first)
Thread 4/D  Human corrections (unscheduled)
```

**2/B ran before A0** and closed on 2026-09-22; **A0 closed the same day;
A1 closed 2026-09-25 with its gate NOT met; A2 closed the same day with its
gate met; A3 closed 2026-09-26 with its gate met; open issues 1–3 closed
offline the same day, and on 2026-09-27 the floor was kept at `a3-result`**
— see `docs/status.md`, "What the last step shipped".
`docs/status.md` indexes what each shipped and where every measurement lives.
**The ratchet's floor is `tests/frozen/a3-result/` since 2026-09-26**, moved
there from `a2-result/` at A3's close — see `docs/status.md`, "The floor".

`docs/specs/0007-handover.md` holds a ready prompt per thread and the full
scope of Phase A-1. **"The open-issues queue, continued — Q5 to Q7" is the
next one to use.**

**[`docs/status.md`](docs/status.md) is the live status — read it second, after
this section.** It says what is done, what the last checkpoint showed, what is
deferred and why, and what is still waiting on a decision. It is maintained,
not archived: when it goes stale, rewrite it rather than banner it.

### What Thread 0 built, and where it lives

| module | what it is |
|---|---|
| `corpus.py` | what the corpus is: fifteen documents, an HTML file and a screenshot each, split *iterate* / *sweep* |
| `projection.py` | `project()` — one page as a reader perceives it, read off headless Chrome. **One function, both sides.** |
| `scoring.py` | `score_document()` — six axes between two projections. T1/T2/T3 hard tier, T1 a ratchet. |
| `report.py` | `debug/runs/<label>/report.html` — the review surface |

**`report.html` is what gets reviewed.** One page, every document, source left
and render right at matched width, scores above each pair with the delta
against the previous run, intermediate steps collapsed.
`tools/inspect_run.py`'s per-fixture `index.html` stays as it is and answers a
different question: how one document was converted, step by step.

**The scorer is developable with no model running.** `tests/frozen/run84/`
holds run 84's five output documents, copied in before `debug/runs/` was
cleared, and `tests/test_scoring.py` is Thread 0's exit gate: asked only
general questions, the scorer finds the deleted table header, the repeated Zone
Titles and the hard line breaks.

**Adding a document is writing an HTML file and running
`tools/shoot_corpus.py`.** No Python, no transcription. That is what let the
corpus leave five.

### The new criteria, in brief

Six axes scored source-image against rendered-output: **1 Completeness,
2 Order & grouping, 3 Layout skeleton, 4 Typographic weight, 5 Palette & texture,
6 Inline detail.** Axes 1–3 are a hard tier — a regression on any of them fails a
phase regardless of what improved elsewhere.

**The T1 ratchet: completeness may never decrease between phases, for any
reason.** Not a target to optimise; a floor never to cross. It is the rule that
would have caught all three faults that shipped as improvements. **Its recall
leg is `vocabulary_recall` as of 2026-09-22** — see below, and spec 0007's
"Why the ratchet's recall leg is now distinct tokens" for what moved it.

**T1 reports four numbers, and none of them is decoration.** Recall and
precision are token multisets, so they cannot see text that is all present, in
the right order, and *cut in the wrong place*: `Invoice #: 123` read as label
`Invoice` and value `#: 123` scores 1.000, 1.000 and tau 1.000.
`join_recall` — the adjacent-word pairs — is the only one that catches it, and
`Completeness.broken_joins` names the join that was cut.

**`vocabulary_recall` is the fourth, and as of Phase A0 it is the one the
ratchet is on.** Distinct source words the output still prints *somewhere*,
against the multiset's how many times. The change was forced by measurement:
removing a doubled Zone Title lowers multiset recall on six of the fifteen
documents while nothing leaves the page, because the echo had been standing in
numerically for a genuine occurrence elsewhere that the output never read.
`newsletter_0008` prints "Castleton Chronicle" in its masthead and its footer;
the output printed it twice in the masthead. Both are reported and a multiset
fall is worth reading — the **floor** is *no word the page shows stops being
shown*, and `Completeness.vanished` names what a failure caught.

Ground truth is **derived, not typed**: `example/foo.png` is a screenshot of
`example/foo.html`, so the expected answer is already on disk. One `project()`
function runs over source and output alike and the projections are diffed. Adding
a document is writing an HTML file — which is what lets the corpus leave five.

**The source and its screenshot agree exactly for the ten authored documents
and approximately for four of the original five.** Only `invoice.html` still
re-renders to its screenshot (0.74% of pixels differing); the other four differ
by 6.9–14.1%, in content *height* rather than position, because of fonts on
this machine — and `invoice2.html` additionally wants a CDN. So `height_ratio`
is measured against the **PNG's** own height, which is what the model was
shown, while T3's relations and column shares come from the re-rendered source.

### The review surface

**Every run produces `debug/runs/<label>/report.html`** — one page, every
document, source left and render right at matched width, intermediate steps
collapsed. This is what Alessandro reviews; he will not navigate per-fixture
folders. `tools/inspect_run.py`'s per-fixture `index.html` stays as it is and
answers a different question: how one document was converted, step by step.

---

## How runs are used here — read this before quoting any number

**A run number is not evidence. Take a measurement or say you do not have one.**

This file, `docs/specs/*` and many docstrings are full of run numbers and mismatch
totals. They are kept as a record of how decisions were reached. **They are not
citable**, and no conclusion may rest on them:

- `debug/runs/` is cleared regularly, so most of those runs cannot be re-opened.
- Historical runs differed on several flags at once, so their totals describe
  configurations that are neither the shipped one nor each other.
- Historical totals are not comparable *even where the pipeline is*, for the
  reasons above and below. **On the determinism question specifically, the old
  claim here was wrong and has been measured:** `transport.py` asks Ollama for
  `temperature: 0`, and on 2026-09-18 the five original documents came back
  **byte-identical** to the copies frozen in `tests/frozen/run84/` — all five,
  md5 for md5, on a later commit and with the model partly on the CPU. So on
  one machine, one model and one pipeline, *the conversion is reproducible*,
  and a byte-identical arm means **the change did nothing** rather than "noise
  swamped it". That is a legitimate comparison rather than a cited run: the
  frozen files are committed inputs, and the run was taken in the same sitting.
  It also confirms from the other side that the CPU/GPU split moves timings
  only. **This licenses nothing across machines, Ollama versions or models**,
  and says nothing about the other ten documents, which have no prior run.
- **Every total recorded before 2026-09-17 also measures a quantity this project
  no longer optimises.** Three separate breaks — the comparison changed
  (2026-09-11), the reference rectangles changed (2026-09-14), and the target
  changed (2026-09-17). Together they make every older number dead.

Compare only runs taken against each other, one change apart, in one sitting.
**This applies to Claude's visual judgements at least as strongly as to numbers:**
a rubric score from one session and a rubric score from another are not
comparable and must never be tabulated together. Judge pairwise — previous render
against new render, both against the source, side by side, now.

**The one exception, and it is narrow.** Scores over `tests/frozen/run84/` *are*
citable: the inputs are committed files, the scorer runs offline over them with
no model, and `tests/frozen/run84/README.md` tabulates them. They are the fixed
point every later measurement can be described against. Nothing from a *run* —
including `scores.json` — joins that exception, because a run involves the
model. A run's `report.html` computes its delta against the previous run's
`scores.json`, which is the pairwise comparison this section asks for, taken
automatically and in one sitting.

**The other exceptions are the frozen directories, and each exists because
`debug/` is gitignored and gets cleared.** Every one is a committed file whose
README states its provenance exactly. Quote them only for what their README
says they are.

| directory | what it is | role now |
|---|---|---|
| `run84/` | run 84's five output documents | the scorer's offline test input |
| `a1-checkpoint/` | Phase A-1's checkpoint scores, the ratchet's first notch | record |
| `a0-checkpoint/` | A0's starting notch | record |
| `a0-result/` | the scores A0 reached, sweep `100-a0-gate` | record — the floor 2026-09-24 to 2026-09-25 |
| `a1-result/` | A1's fifteen documents beside their scores | record — A2's control |
| `a2-result/` | A2's fifteen documents beside their scores, sweep `A2-10-enclosed-sweep` | record — the floor and A3's control 2026-09-25 to 2026-09-26 |
| **`a3-result/`** | **A3's fifteen documents beside their scores, sweep `A3-10-figure-pixels-sweep`** | **the floor and the control, from 2026-09-26** |

**Ratchet against the floor by path**, and always with `--documents sweep` —
without a `fixtures.txt` the report silently scores the iterate five:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a3-result/scores.json
```

**Each floor move was measured, not argued:** the new floor was no lower than
the old on any ratcheted leg of any of the fifteen documents, and Alessandro
took the decision each time.

**A directory holding documents beside scores buys a loop, not a number.**
Scored straight out of `a3-result/`, **15 documents, 0 differing fields**. Its
IRs are older than today's code, though: **`tools/rederive.py` brings them up
to it** — re-applying every step downstream of the model — and that, not a
plain re-render, is the baseline a change is measured one apart from. It
reproduced the gated arm of open issues 1–3 byte for byte on all fifteen. So a
change downstream of the model is measured pairwise, in about a minute, with
no model. Phases A2 and A3 measured every prototype they tried that way before
spending a sweep. **Any new downstream step that writes the IR must be added
to `rederive.py`**, or the loop measures yesterday's code. It is not a target
to match.

**A floor is not a result to quote in an argument** — the distinction the rest
of this section is about.

---

## Knowledge that survives the target change

### The Zone convention

**A heading and the content it names are one Zone, with the heading as
`Zone.title`.** `ir.Zone` never nests, so a Zone carrying a Title and its Blocks
is the IR's only vocabulary for containment — this is the model used as designed,
not DOM nesting smuggled in.

It was applied inconsistently until 2026-09-14: a card and every Bootstrap panel
were one Zone with a Title, while `<header><h1>+<nav></header>` was two Zones in
two Bands. Same shape, opposite readings. **The proof it was a definitional
disagreement rather than a page-reading failure is that fixing the code and
fixing the references landed on exactly the same total.** The detector groups
these regions; insisting they were two meant it could not be right.

**Author the next document to it.** Spec 0007's Phase A0 added a second rule on
top: a Zone carrying a Title must **not** also carry a Block repeating it.
`wire._without_title_echo` enforces it, and the corpus went **34 echoes to 0**
on 2026-09-22.

**That rule is about one Zone, and no across-Zone echo is measured on the
floor.** Both examples once filed as across-Zone turned out not to be.
`menu_0012`'s `To begin` was a Zone lying wholly inside another: **A2 closed
it in the detector**, with `without_enclosed`. `darkdeck_0009`'s
`AVAILABILITY` was one Zone all along — the caption pass lifted the first cell
of Zone 2's own header row into its Title — and
`wire._title_is_its_header_cell` drops that Title and keeps the row,
2026-09-26. Over `a3-result`'s 47 titled Zones, the only Title spelled
anywhere in another Zone is `AVAILABILITY` in Zone 9's column header, which
the source prints too.

### What must not be deleted

Four shipped defaults, each documented where it lives: `DTH_SNAP_ZONES` (boxes
onto their ink, 0.56 → 0.91 IoU, fixes no Kind), `DTH_TABLE_GRID_HINT` (state the
measured grid in the table prompt), `CLASSIFY_PROMPT` making typesetting decisive
rather than an aside, and `_reread_as_prose` acting on the Pairs Extractor's
`NotPairs` diagnosis. See each constant's docstring in `config.py`.

**Two dormant safety nets, and do not delete them on one run** — four runs
established the behaviour each guards. `wire._without_empty_rows` drops a
zero-cell row before the table width check (two runs lost a whole table and the
385.00 Probe to one such row). `_reread_as_prose` recovers a Zone the Pairs mapper
rejects wholesale.

**`_without_empty_rows` filtered on cell count rather than cell content, and
Phase A0 fixed the condition — 2026-09-22.** `if row.cells` is truthy for
`['', '', '', '', '']`, so a row of empty strings passed the net that exists to
drop it and rendered as a blank line inside the table. The net itself stayed:
the finding was that it tested the wrong thing, not that it should not exist.

**There are three wire-level row nets as of 2026-09-22, not one.** Each invents
nothing and discards nothing, and each exists because a measured run lost
content without it: `_without_empty_rows` (above), `_join_split_header_row`,
and `_without_repeated_header` — which drops a second `role == "header"` row
that spells the same as the first, the padding the model produces when the
grid hint asks for more rows than the table has.

### The OpenCV rectangle finder — Thread 2/B must BUILD it

**Corrected 2026-09-20. This section used to say the finder was in the tree and
must not be rebuilt. It is not in the tree and never was.** `git log -S
findContours` across all history returns exactly one introduction, and it is
`preprocess.find_page_quad` — page-edge detection for rectification, a different
job. `tools/cv_layout_probe.py` holds `zones_from_morphology`, which dilates ink
and takes connected components; it groups ink into blocks and **cannot see a
drawn border at all**.

What spec 0006 Change 3 measured was measured in a scratch script that was never
committed, and three documents — this file, spec 0007 and ADR 0005 — then spent
a year telling the next session to reuse it. **That is the project's own
recurring fault applied to itself: a claim in the docs that nothing verifies.**
The lesson beside `dth_env.txt` is the same shape — before relying on something,
prove it is there.

What survives as *knowledge* rather than as code: a rectangle finder was
observed to locate exactly `invoice_0002`'s four panels and `sample_css_0004`'s
two cards and nothing on the other three pages, and **its guard** — a rectangle
covering more than 0.80 of the page is the page, unguarded it took
`invoice_0001` from 6 Zones to 1. Treat both as a starting point to re-measure,
not as a result to cite.

**Do not rebuild it for *grouping*** — that much is still settled, and for a
separate reason: wired into grouping, morphology produced byte-identical boxes
on all five fixtures. Thread 2/B's use is borders, rules and card treatment for
the style record, which is a different question.

### Runs explain themselves

`trace.py` records every step of a Conversion — model calls *and* decisions — each
with a required `disposition` saying what became of its answer.
`tools/inspect_run.py` renders it in execution order:
GIVEN / ASKED / ANSWERED / HANDLED / RESULT per step, crop inline, prompts
collapsed. **Open `debug/runs/<label>/<fixture>/index.html` and read top to
bottom** when diagnosing one document; open `report.html` when comparing them all.
`trace.json` is in the dump for programmatic use.

### Standing knowledge about the model and the prompts

- **The `invoice_0002` panel question is answered.** Each panel opens with a
  **shaded caption bar**, which satisfies `CLASSIFY_PROMPT`'s own "top row set
  apart" test for a table. Withholding the bar fixes it; a prompt clause
  explaining the difference moved 0 of 6.
- **`DTH_CAPTION_PASS` ships on.** It reads each Zone's Title in its own call,
  then withholds the caption band from the Kind question. It withholds the band
  from the *Kind* question only — **not from the Extractor's crop**, and that is
  correct. **Phase A0 built the withholding, measured it, and reverted it on
  2026-09-22**: cutting the top band off `darkdeck_0009` z2, a row of four
  metric cards with no caption at all, deletes `P95 LATENCY`, `INGEST VOLUME`
  and `COST PER MILLION` — confirmed by opening the crop, not inferred — and it
  moves the measured column count on three other tables. Widening
  `CaptionBand.aligns_to_grid` to a ratio instead strips four real captions.
  **What shipped is only the removal of `with_grid`'s row subtraction**, so the
  arithmetic now matches the picture it is taken from, and
  `sample_table_0003` returns all five headers and sixteen rows. Do not rebuild
  the cut; the docstrings in `engines/ollama.py` carry the numbers.
- **`preprocess._without_vertical_rules`** clears full-height columns before
  banding. Without it, a 3px `border-left` inked in every row makes a crop read as
  one unbroken band, and `TL;DR` and `Introduction` were never asked for a Title.

---

## Retired in Thread 0 — gone, and why

- **`acceptance.compare()`, `tests/test_acceptance.py`, `tests/test_fixture_0002.py`
  and every `*.expected.json`.** The typed-reference harness and its serialised
  reference. `geometry_score.align()` survives as a component of T3.
  `tests/frozen/run84/` holds run 84's five output documents, copied in before
  anything was deleted; spec 0007's problem statement is the rest of the record.
- **`tests/fixtures/` is now `tests/documents/`, and `BUILDERS` is
  `SAMPLE_DOCUMENTS`.** The hand-built `Document` objects survive **only as
  input** to render, probe and replay tests. With the comparison function and
  every serialised reference deleted, nothing can score against them. **Never
  score against them** — doing so rebuilds the harness spec 0007 deleted. They
  no longer have to be *true* IR, only plausible IR.
- **The vision layout path.** Geometry comes from a detector in every
  Conversion. `DTH_LAYOUT_DETECTOR=none` now **refuses by name** rather than
  being handed to `from_name` as if it were a detector, so a stale value in
  somebody's shell says so instead of failing somewhere obscure.
  `DTH_LAYOUT_LONG_EDGE`, which served only that pass, is gone, and Q4 took
  `preprocess.LAYOUT_LONG_EDGE` with the rest of the pass.
- **The probes bound to the retired reference**: `layout_probe.py` (measured
  the vision pass), `snap_probe.py`, `classify_truth_probe.py`,
  `fixture_geometry.py` (derived rectangles *for* the expected IR) and
  `write_expected_ir.py`. `cv_layout_probe.py` and `detector_probe.py` are
  **kept** and repointed — see the OpenCV rectangle finder note above, which
  Thread 2/B needs.

**The one thing Thread 0 did not finish was finished by Q4, 2026-09-29.**
`OllamaEngine.detect_zones`, `LAYOUT_PROMPT`, the layout wire schema, the
region-ceiling rescue and `DTH_LAYOUT_MODEL` / `DTH_DERIVE_BANDS` /
`DTH_LAYOUT_REGION_HINT` are gone. The recorded-response suite now hands the
layout stage fixed Zones — `tests/replay.py`'s `FixedLayout`, serving each
fixture's `tests/responses/<fixture>/geometry.json` — so a replayed Conversion
takes its Zones the way a real one does, from something that is not a model.
**The production layout front can be run with no model at all:** give a
Conversion engines whose transport refuses every call, and the real detector
and every model-free layout stage run, each Zone renders a skeleton, and all
fifteen take 11 seconds: `python tools/layout_front.py <out>`. It reproduces
`a3-result`'s Zone band, column and bbox on 15 of 15 and is byte-identical run
to run, and it is how Q4 proved it changed nothing. It sees no model answer —
`tools/rederive.py` is that loop — so it measures geometry changes only.

### What Phase A-1 settled, including what it could not do

Its three causes are fixed — a table reconciled against its header instead of
discarded, a light-on-dark page turned over before `equalise`, and ink no box
covers given a Zone. **Its honesty gate is not met**, and the reason bounds what
any later thread should attempt.

**The pipeline can declare structural loss and cannot declare loss inside a
line.** Nine of fifteen documents lost 2–43% of their tokens while returning *as
many printed lines as the crop holds, or more* — `catalogue_0015` read 28 lines
where 20 are printed and lost 43% of its words. Two pixel-side detectors were
built and measured against the checkpoint's own documents and both were
rejected for firing on clean documents while missing the worst real loss;
`src/doc_to_html/honesty.py` carries the table and the numbers. **Do not build a
third without a new kind of evidence.**

**What that means for Thread 3/C, stated in full because the shorthand was
useless.** 3/C's re-scoping gate classifies each residual error as (a) the IR
cannot express it, (b) a pass read it wrong and would again, or (c) it needs a
second look at the whole page — and the loop gets built **only if (c) is a
material share**. This residue is **(b)**: the conversion is deterministic at
`temperature: 0`, so a loop that re-examines the same crop gets the identical
wrong answer back. **Do not plan on the repair loop to recover recall**, and do
not let that expectation justify deferring reading quality. On current evidence
3/C closes unbuilt, exactly as spec 0006's Change 3 did.

What *would* reach intra-line loss is two readings of one crop compared against
each other — `CellState.DISPUTED` and the Ladder are already the vocabulary for
it, and `_climb_ladders` already records that it waits on a second Engine. That
is model time and a thread's decision, not a detector.

**Tracker state.** **#30** is spec 0007 and the only open issue. #29 records
spec 0006 retrospectively (closed). #28 (spec 0005) and #17 (the vision layout
prompt) were closed by Thread 0. Specs 0001–0006 are closed history.

---

## Lessons that generalise

- **The tool between you and the artefact is part of the measurement, and it
  lies quietly.** Thread 0 found three faults in the *rendering harness*, none
  visible in any number, each found by looking at a picture after the numbers
  said everything was fine. (1) Headless Chrome inherits the host's dark mode,
  so `render.py`'s `@media (prefers-color-scheme: dark)` fired and **every
  visual comparison eyeballed in this project before 2026-09-18 was an inverted
  page beside a light source**. (2) Chrome lays out no page narrower than 500px
  but crops the screenshot to the width you asked for, so a 340px document
  became a 500px layout with its right-hand column cut off. (3) A screenshot
  taken at *exactly* the page height renders the last row blank —
  `invoice_0001`'s `Total: $385.00` had zero dark pixels while `project()`
  reported it present at y 551-569. The third is the dangerous shape: **T1 and
  the pixels disagreeing about whether content exists**, which is the failure
  spec 0007 warns about, arriving from the tooling rather than from the IR. All
  three are pinned in `tests/test_projection.py`.
- **A corpus document that hides its own text is not ground truth.**
  `newsletter_0008`'s CSS multicol balanced its content into a box shorter than
  the content and cut a line in half. The text stays in the DOM, so the
  projection reports it and T1 demands the model read it, while the picture
  does not contain it. Invisible in the page height, obvious in the PNG. It now
  uses three explicit columns, which cannot do that.
- **A metric can saturate and then invert, and nothing inside it will say so.**
  Runs 81→84 moved the total 23→10. Over those same runs, duplicated titles
  appeared in three of five documents and `sample_table_0003` lost every column
  header of its only table — scored as a **full match**, because the harness
  compared `RowRole` sequences and never compared cell content. **When a measure
  cannot see a class of fault, improving it is unconstrained in that direction.**
  Nobody had opened the rendered output beside its source in eighty runs. **Look
  at the artefact, not only at the number.**
- **A change can be blocked by a fault somewhere else, and nothing will tell you
  when it stops being blocked.** `DTH_CAPTION_PASS` was built, tested and correct,
  and sat switched off for ten runs. The gate it failed was real, but the cause
  was *grouping*: the reference split those boxes, so neither half could carry a
  Title. Spec 0006 merged them and the pass then went 23 findings to 12 **with no
  change to the pass at all**. The note on the shelf said "the pass is right about
  the pixels it is shown and the pixels are wrong" — the correct diagnosis, and it
  still did not schedule the retry. **When you shelve a change, write down what
  would have to become true — and re-read that list when a neighbouring pass
  moves.**
- **`dth_env.txt` proves what was exported, not what was read — and a flag that
  does not arrive looks exactly like a flag that does nothing.** `DTH_HEADING_RULE`
  reached `Settings`, was recorded in the run directory, and never reached the
  detector: `bakeoff.engines_for` builds its own `EngineSet` rather than calling
  `orchestrator._layout_engine`. The arm came back **byte-identical to its
  baseline**, which is the signature of a change that did nothing — so the correct
  reading of that run was very nearly the opposite of the truth. `tools/iterate.sh`
  runs the bake-off, so *every measured run in this project takes that path.*
  **Before believing a null result, prove the arm was actually armed.**
  `TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion` compares the two paths
  attribute by attribute. **It happened again, found 2026-09-21:**
  `Zone.title_fill` shipped, was verified offline and had never once been set
  in a conversion, because `_measure_chrome` ran *before* the `_classify` pass
  that sets `Zone.title` and `title_rows` was therefore always zero — 0 of 119
  Zones across the corpus. A stage's *position* is as much a way for a feature
  not to arrive as an unread flag.
- **An instruction is reachable only if it asks the model to decide differently,
  not to perceive differently.** Two prompt attempts to stop the model splitting a
  wide table row failed, and one run's answers were **byte-identical** to the run
  before it. The model does not read the two ends of an 800px row as one line, so
  the instruction had nothing to act on. A *count* worked. **It complies with how
  many, and ignores which line.** This is also why Thread 2/B measures colour from
  pixels rather than asking a model for it: colour is perception, and the pixels
  are already in hand.
- **When a model answers a closed question the same way every time, check whether
  the schema can express the true answer before rewording the question.**
  `CaptionResponse` first asked a boolean — is this line a heading? — and got
  `true` on 8 of 8 crops, because its test for a heading was word for word
  `CLASSIFY_PROMPT`'s test for a table's top row and no other answer was
  available. A third value — `caption` / `header` / `content` — took the same model
  from 4/11 to 8/11 with no change to the reasoning asked of it. **Do not collapse
  it to a boolean.**
- **A prompt rule that bundles two tests will be credited with the wrong one.**
  `pairs` required the label "on the same line as the value it names" — a
  geometric test and a semantic one in one sentence. Spec 0003 credits the whole
  clause with fixing a Zone, so it read as untouchable; in fact only the semantic
  half did that, and the geometric half was the sole cause of the `invoice_0002`
  panel regression. Dropping it left all 13 answers byte-identical. **Check whether
  a clause is one rule or two wearing one sentence before defending it.**
- **Do not gate a change on the fields it was designed to move.** Spec 0004's
  Gate 1 was pre-registered, passed every field it named, and shipped a regression
  that cost a Zone and a Probe, because it gated a geometry change on geometry
  fields alone. Spec 0007's T1 ratchet is the general form of the fix: *no content
  that previously converted stops converting*, checked on every phase.
- **A reference that cannot be matched reads as a detector failure, and may be
  the reference.** `invoice_0002`'s `Services / Products` sat at **0.043** IoU
  against its own ink, under `MATCH_IOU` 0.50, so nothing the detector drew could
  ever pair with it — and the harness reported that as three references the run had
  missed. Before believing a `missing`, score the references against their own
  Source Image.
- **A Zone's Title is a band of ink that is not a row.** `table_grid` counts
  printed lines, so a titled table measures one row too many —
  `sample_table_0003` gives 17 against a true 16, and `with_grid` subtracts. Both
  numbers were right; they counted different things. **But the subtraction is only
  safe if the caption is also removed from the crop**, and it is not — which is
  exactly how the header row gets deleted. Arithmetic and picture must agree with
  the page, not merely with each other. **Phase A0 resolved it the other way
  round, 2026-09-22**: the cut was built and measured and it deletes real
  content on a Zone with no caption, so *the subtraction went* and the crop
  stayed whole. When a count and a picture disagree, changing the picture to
  match the count is the more expensive of the two repairs — it can only
  destroy, where dropping the count can only be wrong.

- **Where you ask is a bigger lever than how you ask.** A1 asked for inline
  runs twice with almost the same words. **Inside** the four Extractor prompts
  it cost `invoice_0002` a whole pairs answer — five pairs to one, a
  neighbouring answer in the same document byte-identical — and crossed the T1
  ratchet on seven documents. Moved into a **separate pass** over the same crop,
  changing no Extractor prompt, it holds the ratchet on all fifteen and costs
  nothing, because at `temperature: 0` every extraction answer is then the one
  the floor already has. Same model, same question, opposite result. When an
  extra ask damages the primary task, **move the ask before you reword it.**

- **The check that reports a fault is not where the fault is.** For a whole
  phase `DTH_SNAP_ZONES` was "not applying to 3 of 15", and A2 was scoped
  around repairing it. Run offline one stage at a time, the snap had returned
  every box on those pages **unchanged**; the enclosure came from two union
  steps in the detector, and the snap was named only because it was the one
  place `validate_bands` ran. A gate clause reading "the snap applies to 15 of
  15" would have passed without moving a box. **Before fixing the component a
  finding names, find the stage that introduces the fault** — and suspect a
  docstring that says a check "cannot fire": `validate_bands`' did, and was
  false.

- **Set a threshold from the distribution, and look for the empty band.**
  `keep_runs` drops marking that covers a whole line. The first cut was a
  tidy-looking 0.5 and it threw away `editor@example.com` — a genuine link that
  is three of its line's four words. Measured across every marked Cell of the
  trial sweep, the marked share is **bimodal with nothing in the middle**:
  genuine marks 0.077–0.333 plus that one at 0.750, junk at **exactly 1.000**.
  The threshold belongs in the gap, and "every word" needs no constant at all.
  **A round number chosen before the histogram is a guess wearing a decimal
  point.**

- **When two things look identical in the picture, the information is not in
  the picture, and neither a prompt nor a pixel will put it there.** A line
  ending `con-` and a line ending `nine-` are the same shape: one hyphen is the
  renderer's, inserted because the line wrapped, and the other belongs to the
  word. `newsletter_0008` has both. Telling them apart is knowing English, so
  the repair is a word list — and the default when there is none is to **keep**
  the hyphen, because keeping one that should have gone costs nothing (`con`
  and `firmed` score exactly as they already did) while dropping one that
  should have stayed costs two source words (`nine-month` becomes
  `ninemonth`). Same asymmetry that put `_without_repeated_header` at the wire:
  put the repair on the side where being wrong is free.

- **The ratchet earns its keep on the first replay, not at the gate.** A1's
  reflow was measured offline before a single model call. Everything improved —
  `hard_breaks` 57 to 8, `join_recall` 0.8128 to 0.8258, five documents better
  on four axes — and the ratchet failed it on **one word**, `nine`. A mean
  would have called that a clean win. **Measure downstream-of-the-model changes
  by replay before spending a sweep**; `tools/remeasure_style.py` does it, and
  it proved itself first by reproducing `a0-result` to the last digit.

- **A prompt clause is not additive just because the schema is.** A1's
  `marked` field was designed so that an empty answer left everything exactly
  as before — and it did, at the schema. The *clause asking for it* still cost
  `invoice_0002` a whole pairs answer: 5 pairs at the floor, **1** with the
  clause, a neighbouring answer in the same document byte-identical, and all
  five back the moment the clause was removed. **Asking a model for one more
  thing is a change to everything it was already doing.** Where the extra ask
  paid nothing at all — tables and pairs returned 0 usable runs — it was pure
  loss. Budget a revert, and verify it on the document that was hurt.

- **A fault can be invisible in the picture and loud in the measurement, and
  that direction is as real as the reverse.** Joining a word across two marked
  lines produced `<strong>...con</strong><strong>firmed...</strong>`. The page
  reads `confirmed` — correct to any eye — while `project()` walks **text
  nodes** and scored `con` and `firmed`, reporting a printed word as missing.
  The usual warning here is the other way round (`Total: $385.00` present in
  T1 and blank in the pixels). **Both directions mean the same thing: the tool
  between you and the artefact is part of the measurement.** `render._SEAM`.

- **A count that ignores location cannot guard a claim about location.** A1
  pre-registered "no document's `hard_breaks` may fall below its
  `source_hard_breaks`" to stop `join_recall` being gamed by joining
  everything — `join_recall` counts source bigrams *found*, so a wrong join can
  never lower it. The guard fired on `nonlatin_0014` and the fault had not
  happened: `hard_breaks` counts `<br>` **elements wherever they sit**, the
  source's four are in an address block and a date block, and the two the
  output lost were in Greek paragraphs that genuinely wrap. Same blindness that
  let a full match hide five deleted table headers. The positive form holds and
  is what should have been written: **every `<br>` still drawn is in a block
  whose kind keeps its lines, and none was lost.**

- **A clause about bytes has to say which bytes.** A3 pre-registered "every
  document with no figure renders byte-identical", and it could not hold for
  a reason that had nothing to do with figures: a new `Zone` field puts
  `"pixels": null` into every embedded IR, and a rule added to `STYLESHEET`
  lands in every render. It was restated before the sweep — identical outside
  the embedded IR, and inside it differing by that key alone — and met 12 of
  12. The same trap sprang on the comparison: reading the floor's IR back
  through today's `Document` adds the field to the floor too, so strip it
  from both sides or compare the raw JSON.

- **A fault's description is a claim, and the IR can refute it.** Open issue
  3 was filed, briefed and handed over as an *across-Zone* echo — two Zones
  reading one printed line — and scoped around a rule `_without_title_echo`
  could not reach. One print of the floor's IR showed a single Zone whose
  Title was its own header row's first cell. **Read the IR before scoping a
  fix to the description.** The same session's gate clause said only
  `height_ratio` would move when a findings panel shrank, and three palette
  fields moved too: the projection excludes the panel, and T5 samples the
  whole screenshot. **Before predicting which fields move, know what each
  axis samples.**

- **A guard can be right and still create the fault it looks like.** A0's
  heading guard stopped `attach_trailing_rows` swallowing headings, which
  recovered `What Q4 commits to` — and shortened `darkdeck_0009`'s table crop
  to 8 ink bands, so the prompt asked for 8 rows where the table has 7 and
  **the model padded by repeating the header**. The tempting fix was to restore
  `with_grid`'s subtraction, which is what deleted `sample_table_0003`'s
  headers in the first place. It went to the wire instead
  (`_without_repeated_header`), because **a dropped row is a recall fault and a
  surplus row is only a precision one** — put the repair on the side where
  being wrong costs less.

---

## The loop

```
tools/iterate.sh <label>                  # one document, shipped defaults
FIXTURE=iterate tools/iterate.sh <label>  # the five, ~17 min
FIXTURE=sweep   tools/iterate.sh <label>  # all fifteen, at a phase gate
FIXTURE=invoice_0001,cv_0013 tools/iterate.sh <label>
```

Set a `DTH_*` only to change **one** axis against that baseline, and say which
one when reporting the result.

**Open `debug/runs/<label>/report.html`.** It is built by the run, it holds
every document, and it carries the delta against the previous run's
`scores.json` plus a pass/fail on the hard tier. A run's numbers are in
`scores.json` beside it.

**Any run whose output will be reviewed is a `sweep`.** Decided 2026-09-21,
after reviewing the five found four real faults in one pass and the five turned
out to be the least representative sample in the corpus — all light-grounded,
all similar, none of the ten documents authored after the target changed. The
~90 minutes is budgeted for. `iterate` is for a throwaway check nobody will draw
a conclusion from. **A renderer-only change needs no new run at all:** every
pixel-derived field can be re-measured and the IRs re-rendered offline, so one
sweep serves many render iterations.

**Corpus split.** *iterate* = the original five. *sweep* =
all fifteen, run at phase gates. `doc_to_html.corpus` is the one place that
says which is which. **A sweep takes about 90 minutes** — measured
2026-09-18, on a machine where the model was partly on the CPU. Budget for it
before starting one. Per-document model time on `qwen3-vl:4b`, measured from
run 84: `invoice_0002` 301s, `sample_semantic_0005` 300s, `invoice_0001` 174s,
`sample_table_0003` 132s, `sample_css_0004` 128s.

**The five original documents are the ones every prompt was tuned on.** That is
why *sweep* exists and why a phase gate is not allowed to be decided on
*iterate*.

Runs live in `debug/runs/<label>/`, which is **gitignored** and gets cleared —
regenerate rather than hunt, and never quote a run you cannot open. Nothing in the
suite reads a run directory.

Ollama reports the CPU/GPU split into `ollama_ps_after.txt` and the script warns
when the model was partly on CPU. **That affects timings only** — the answers are
unchanged — so a run with the warning is still valid.
