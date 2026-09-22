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
Phase A0    Stop the bleeding                          <- next
              its T1 = 1.00 gate is disproved; set the replacement from
              tests/frozen/a0-checkpoint/ before changing any code
Phase A1/A2/A3  Inline runs, geometry, figure pixels
Thread 3/C  Repair loop (re-scoped against A+B residuals first)
Thread 4/D  Human corrections (unscheduled)
```

**2/B ran before A0** and closed on 2026-09-22. `docs/status.md` indexes what
it shipped and where each measurement lives.

`docs/specs/0007-handover.md` holds a ready prompt per thread and the full
scope of Phase A-1.

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
would have caught all three faults that shipped as improvements.

**T1 reports three numbers, and the third is not decoration.** Recall and
precision are token multisets, so they cannot see text that is all present, in
the right order, and *cut in the wrong place*: `Invoice #: 123` read as label
`Invoice` and value `#: 123` scores 1.000, 1.000 and tau 1.000.
`join_recall` — the adjacent-word pairs — is the only one that catches it, and
`Completeness.broken_joins` names the join that was cut.

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

**A third exception, added 2026-09-22: `tests/frozen/a0-checkpoint/`** — Phase
A0's starting notch, and the floor for A0 and everything after it. Its README
states its provenance exactly, including that its model answers come from a
real sweep and its renders from `tools/remeasure_style.py` at a later commit,
and why that is sound. `a1-checkpoint/` stays as A-1's notch.

**The second exception, added 2026-09-20: `tests/frozen/a1-checkpoint/`.** It
holds Phase A-1's checkpoint scores, which are **the T1 ratchet's starting
notch**, and it is committed for one reason — the notch was set on a run
directory, and `debug/` is gitignored and gets cleared, so the floor every later
phase is measured against was living in the one place guaranteed not to survive.
Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a1-checkpoint/scores.json
```

Its README states the provenance exactly, including that the run was taken from
an uncommitted tree and why the numbers are sound anyway. **It is a floor, not a
result to quote in an argument** — the distinction the rest of this section is
about.

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

**Author the next document to it.** Note that spec 0007's Phase A0 adds a second
rule on top: a Zone carrying a Title must **not** also carry a Block repeating it.
Today it does, in three of five documents.

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

**`_without_empty_rows` has a real bug, and Phase A0 fixes it** — it filters on
`if row.cells`, truthy for `['', '', '', '', '']`, so `sample_table_0003` returns
a 17th row of empty strings. The drop tests cell **count**, not cell **content**.
Fix the condition; do not delete the net.

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
  then withholds the caption band from the Kind question. Note that it withholds
  the band from the *Kind* question only — **not from the Extractor's crop**, and
  that omission is what deletes `sample_table_0003`'s header row. Phase A0.
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
  `DTH_LAYOUT_LONG_EDGE`, which served only that pass, is gone;
  `preprocess.LAYOUT_LONG_EDGE` is the remaining constant and is not a setting.
- **The probes bound to the retired reference**: `layout_probe.py` (measured
  the vision pass), `snap_probe.py`, `classify_truth_probe.py`,
  `fixture_geometry.py` (derived rectangles *for* the expected IR) and
  `write_expected_ir.py`. `cv_layout_probe.py` and `detector_probe.py` are
  **kept** and repointed — see the OpenCV rectangle finder note above, which
  Thread 2/B needs.

**One thing Thread 0 did not finish, named so it is not mistaken for done.**
`OllamaEngine.detect_zones` and `LAYOUT_PROMPT` are still in the tree as the
seam the recorded-response suite replays against, documented as that. They are
unreachable from a Conversion, so nothing they ask for can influence any
output. Removing the seam means replacing the layout stage of nine test
modules; it is bookkeeping, not a measurement question.

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
  the page, not merely with each other.

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
