# doc-to-html

## Agent skills

### Issue tracker

Issues live as GitHub issues in `apalombit/doc-to-html`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Specs

Work in flight has a spec in `docs/specs/`, one file per piece of work, each tracked
as a GitHub issue. **Read the spec before the code** — it carries the measured
numbers and what has already been tried and rejected.

## How runs are used here — read this before quoting any number

**A run number is not evidence. Take a measurement or say you do not have one.**

This file, `docs/specs/*` and many docstrings are full of run numbers and mismatch
totals. They are kept as a record of how decisions were reached. **They are not
citable**, and no conclusion may rest on them:

- `debug/runs/` is cleared regularly, so most of those runs cannot be re-opened.
- Historical runs differed on several flags at once — `DTH_LAYOUT_DETECTOR`,
  `DTH_CAPTION_PASS`, `DTH_SNAP_ZONES`, `DTH_TABLE_GRID_HINT`,
  `DTH_LAYOUT_LONG_EDGE` — so their totals describe configurations that are
  neither the shipped one nor each other.
- The model is not bit-reproducible. Two runs of one configuration differ by a few
  mismatches, so **a small delta is not a result.**
- **Anything counted before 2026-09-11 used a different comparison**, and
  anything before 2026-09-14 used different reference rectangles. Both breaks
  are described below; together they make every older total dead.

Compare only runs taken against each other, one flag apart, in one sitting. When a
claim needs a number, run `FIXTURE=all tools/iterate.sh <label>` and use that.

## Current work

### The comparison changed — nothing counted before it is comparable

`acceptance.compare()` **pairs Zones with their references by geometry, not by
list position**, via `geometry_score.align()`. Every total in specs 0001-0005 and
in older docstrings predates this and cannot be compared with anything measured
now.

Why it changed: under `zip(expected.zones, actual.zones)` one extra Zone shifted
every later Zone against the wrong reference, so a single mis-drawn region was
reported as a wrong Kind, a wrong Role and a wrong Band on Zones that were
individually correct. `sample_css_0004` produced **10 findings from one fault**,
and the classifier deserved none of them — realigned, it agreed with its reference
on 6 of 6 regions.

What it does now:

- Geometry reports in its own terms — `region expected one region, got 2 regions:
  2, 3` / `merged into one` / `extra region`.
- Kind, Role, Title and Row Roles are compared **only where the region was found
  correctly**. A Zone that was split was never shown the picture its reference
  describes, so scoring its Kind says nothing about the classifier.
- Bands are compared only when every Zone pairs off (`Correspondence.exact`).
- Rectangles are still **not scored**. `align` asks only *which region is this*,
  at `MATCH_IOU` 0.50, and a reference claimed by exactly one box counts as
  matched however loosely it fits — a reference rectangle is a derivation, not a
  measurement, so a tighter threshold would score the derivation.

### And then the ruler changed too — this is the second break

**Every fixture's rectangles were re-derived on 2026-09-14.** Four of the five
typed a Zone's box around what is *drawn* — a card's border, a panel's shaded
caption bar, an `<aside>`'s padding — while `invoice_0001`'s are read off the
browser as the **ink**. Two conventions, one ruler, and the worst box was
`invoice_0002`'s `Services / Products` at **0.043 IoU against its own ink**: below
`MATCH_IOU`, so no correctly drawn detection could ever be paired with it and the
fixture rather than the run decided the finding.

- `invoice_0001` is untouched — it is the only one with real ground truth.
- The other four were snapped onto their own ink by
  `tools/fixture_geometry.py --snap`, which writes back into the **builders** and
  refuses `invoice_0001`. Re-run it; it is idempotent, and a second pass reporting
  IoU 1.000 is the check that it landed.
- One hand fix first: `sample_semantic_0005` Zone 2's box stopped at its `<h2>`
  while its own second Block claims the byline below it.

All five references now score `covered` 1.00 and `splits` 0 against their Source
Image. **Nothing measured before this date is comparable**, including the table
that used to sit below this line.

### The Zone convention, now that it is settled

**A heading and the content it names are one Zone, with the heading as
`Zone.title`.** `ir.Zone` never nests, so a Zone carrying a Title and its Blocks
is the IR's only vocabulary for containment — this is the model used as designed,
not DOM nesting smuggled in.

It was applied inconsistently until 2026-09-14. A card and every Bootstrap panel
were one Zone with a Title; `<header><h1>+<nav></header>` and
`<div class="col-sm-8"><h1>+<h4></div>` were two Zones in two Bands. Same shape,
opposite readings.

**It was worth 5 geometry findings, and the proof it was a definitional
disagreement rather than a page-reading failure is that fixing the code and
fixing the references land on exactly the same total.** The detector groups these
regions; insisting they were two meant it could not be right.

**Author the next fixture to it.** One open inconsistency remains and is
deliberate: `sample_semantic_0005` Zone 1 keeps `Why semantic HTML matters` as a
`heading` Block rather than as its Title. That is the same question on a second
axis — *where* the heading goes, not *whether* it shares a Zone — and it is not
settled.

### The baseline: run 81

**`debug/runs/81-new-defaults/` is the current baseline and the only citable
measurement.** 2026-09-14, `qwen3-vl:4b`, all five fixtures, shipped defaults and
**no `DTH_*` axis set** — `dth_env.txt` carries only `DTH_LAYOUT_LONG_EDGE`, so
this measures the defaults themselves rather than an arm. Open
`debug/runs/81-new-defaults/<fixture>/index.html`.

| fixture | findings | geometry | title | kind | role | rows | covered | splits | doubles | Zones v ref |
|---|---|---|---|---|---|---|---|---|---|---|
| `invoice_0001` | **match** | – | – | – | – | – | 1.00 | 0 | 0 | 6 v 6 |
| `invoice_0002` | 9 | 2 | 6 | 1 | – | – | 1.00 | 0 | 3 | 9 v 9 |
| `sample_semantic_0005` | 7 | 2 | 3 | 1 | 1 | – | 1.00 | 0 | 1 | 9 v 8 |
| `sample_css_0004` | 4 | 2 | 2 | – | – | – | 1.00 | 0 | 0 | 4 v 5 |
| `sample_table_0003` | 2 | – | 1 | – | – | 1 | 1.00 | 0 | 0 | 2 v 2 |
| | **22** | **6** | **12** | **2** | **1** | **1** | | | | |

`invoice_0001` renders every string — no skeletons, no Failures, no Caveats — and
its column-sum Probe reconciles at **385.00**.

**60 model calls, down from 72.** Grouping correctly is cheaper as well as
righter: every Zone that stops being split is one classify-plus-extract pair that
never happens.

**Titles are the largest category by a distance — 12 of 22 — and that is the
point.** They went 7 → 9 → 12 as geometry went 16 → 11 → 6. A region that is
grouped correctly gets its Title compared **for the first time**, and nothing
writes `zone.title` on the shipped path. Every one of the 12 is reachable by
`DTH_CAPTION_PASS`, which no split region was. **A rising Title count is how this
corpus reports progress**, and reading a fixture's total in isolation will get
that backwards: `sample_css_0004` reads 4 here against 3 in run 80, because both
cards are now whole and both card Titles are therefore scored, where run 80 had
one card split and only one Title compared.

**Predict the geometry column before spending a run.** It is deterministic —
`align()` over `LayoutEngine.detect_zones` — and has come back exact four times
running. Spend model time only on the half that needs it. Two conventions to keep
straight: raw `align()` counts `fragments + merged + spurious + missing` and gives
**4** here, while the acceptance total adds the per-document zone-count finding
and gives **6**. Same geometry, two accounting rules.

**Re-score without a new Conversion.** The IR is in
`debug/runs/81-new-defaults/dump/qwen3-vl_4b/<fixture>/document.html`, in the
`doc-ir` script block. Unescape `<\/` to `</`, then
`compare(BUILDERS[fixture](), Document.from_json(payload))` — note `from_json`
takes the decoded object, and `compare` returns a plain list.

**This table expires when the directory does** — `debug/runs/` is gitignored.
Re-take with `FIXTURE=all tools/iterate.sh <label>` rather than quoting it.

### How the two defaults were chosen — 79, 80, 81 in one sitting

Run 79 was the baseline on the corrected ruler with both flags off (23). Run 80
set `DTH_PREFER_CONTAINER=1` and nothing else (21, geometry 11 → 6). Run 81 is
both flags flipped to default, measured as the shipped path (22, geometry 6).

**The pair was chosen by reading the documents, not by the totals**, and that is
the transferable part. `DTH_HEADING_RULE=relative` and `DTH_PREFER_CONTAINER=1`
reach **the same 6 geometry findings alone and together**. The documents do not
agree: under the container rule alone `sample_css_0004` comes back with 5 Zones
and its first card still split; with both, 4 Zones and both cards whole, the
zone-count finding simply standing in for the split finding. **Do not read equal
totals as equal answers.**

What run 81 changed in the output, against run 79:

- **`sample_semantic_0005`: 13 Zones → 9** (reference 8). `TL;DR` was being cut
  into a Pairs Zone rendering `<dt>TL</dt><dd>DR</dd>` — the string did not exist
  anywhere in run 79's IR — and is now a heading over its paragraph. The
  blockquote was two Zones, a bare paragraph and a `heading` reading `W3C HTML5.2
  specification`; it is now one Zone, `quote` + `attribution`. The colophon was a
  footer Zone plus a Pairs Zone holding `Contact = editor@example.com`, and is now
  one Zone with the address intact.
- **`sample_css_0004`: 6 Zones → 4.** Both cards were heading-Zone-plus-paragraph-
  Zone; both are now whole, and `Another card` is read as a `heading` rather than
  a `paragraph`.
- **`invoice_0002`: unchanged**, zone for zone. Its two faults are the
  side-by-side merge and the split footer, and neither flag addresses either.

**One new finding, and it is real:** `sample_semantic_0005` zone 7 reports `role
expected footer, got body`. `_role` reads `Role` off the Band index and the class
name, so regrouping moved a Band under it. Small — `Role` is a CSS class in
`render.py` and the Probes navigate by `RowRole` — but it is the first sign that
Band-derived Role is sensitive to grouping changes.

### What the baseline says

**The layout detector is the default.** `DTH_LAYOUT_DETECTOR=heron` ships on; the
vision layout pass is reachable as `DTH_LAYOUT_DETECTOR=none` — *the word, not an
empty string, which resolves back to the default.* Measured one flag apart, all
five fixtures: the vision path raises `MappingError` on three of them and matches
none. `config.DEFAULT_LAYOUT_DETECTOR` carries that table.

**`covered` is 1.00 and `splits` is 0 on every fixture**, so nothing is ever lost.
Every remaining finding is content that arrived and was mis-grouped or mis-named —
a different failure class from the vision path, which dropped content.

**Grouping is now the minority of what is left** — 6 of 22, down from 16 of 26,
and **Titles are the largest category at 12.** That is the shape of the corpus
changing, not a rounding: every grouping fix so far converted geometry findings
into Title findings, which is progress, because a Title is reachable and a split
region is not.

**What grouping is left is four faults, and they were decomposed rather than
estimated.** Two are stacked splits — `invoice_0002`'s footer and
`sample_semantic_0005`'s Benefits list — and neither has a container anywhere in
the detection pool at any confidence: the only pool box covering either spans the
whole page. That closes `prefer_container` out honestly; it took every over-split
that had a container. The other two are side-by-side merges, `invoice_0002`'s
logo-plus-address and `sample_css_0004`'s title-plus-badge, and those are **not** a
threshold problem: both sets of parts already clear 0.40 (`section_header` 0.68 +
`picture` 0.63; `picture` 0.76 + `text` 0.44) and `outermost` discards them in
favour of the container. The fix would be a condition on `outermost`, and
`docs/specs/0006` records why the narrow version of it still measures 4 → 10.

**Every `missing` is gone since the ruler was fixed.** Before it, three of
`invoice_0002`'s references matched nothing at all — not because the detector had
not found them, but because their typed rectangles were too far off their own ink
to be paired with anything. They now report as one `merged` finding, which is the
fault that is actually there. A `missing` reappearing is a real signal again.

**`docs/specs/0006` is closed out** and carries the measurements for all three of
its changes. It supersedes 0005's Changes 2 and 3. 0005's Change 1 (Titles) is built; its Changes 4 and 5 are untouched and
are now worth 2 and 0 findings respectively. Specs 0001-0004 are closed history.

**0006 is finished. Changes 1 and 2 ship on; Change 3 was built, measured, and
not shipped.**

- **Change 1, `DTH_HEADING_RULE=relative`.** The blocker it carried is cleared,
  and the answer was that *both* documents were wrong and both of the spec's
  proposed replacements measure worse than the constant they would have replaced.
  What shipped is a third test — the gap below a heading against the gap
  **above** it, bounded by `HEADING_GAP_MAX`. See `config.DEFAULT_HEADING_RULE`
  for the table and `HEADING_GAP_RATIO` for the derivation.
- **Change 2, `DTH_PREFER_CONTAINER=1`.** Adopts a sub-threshold container over a
  *stacked* group of boxes. Measured live one flag apart before flipping.
- **Both were flipped together, and that pairing was measured, not assumed.**
  Either alone reaches 6 geometry findings and the pair reaches 4; more to the
  point, the container rule alone leaves `sample_css_0004`'s first card split
  while the pair leaves both cards whole. Equal totals were not equal answers.
- **Change 3 — drawn container ink — changes nothing and is not built into the
  tree.** Its premise is sound: the OpenCV rectangle finder locates exactly
  `invoice_0002`'s four panels and `sample_css_0004`'s two cards, and nothing on
  the other three pages. But those are precisely the regions Change 2 already
  resolves, and **wired in it produces byte-identical boxes on all five
  fixtures.** Do not rebuild it expecting a different answer; `docs/specs/0006`
  carries the measurement and the one guard it needed (a rectangle covering more
  than 0.80 of the page is the page, and unguarded it took `invoice_0001` from 6
  Zones to 1).

**Tracker state.** `docs/specs/0006` is the live spec and **has no GitHub issue
yet**. `docs/specs/0005` is issue #28 and is now partly superseded. The one other
open issue is **#17** — `LAYOUT_PROMPT` really does still ask for `kind`, `title`
and `graphic` — and its thread says to re-scope it before starting, because the
pass it edits may not survive. Everything else is closed: #10, #12, #16, #18, #19,
#20, #23 and #27 were all done but left open.

### What got it here, and what must not be deleted

Four shipped defaults, each documented where it lives: `DTH_SNAP_ZONES` (boxes
onto their ink, 0.56 -> 0.91 IoU, fixes no Kind), `DTH_TABLE_GRID_HINT` (state the
measured grid in the table prompt), `CLASSIFY_PROMPT` making typesetting decisive
rather than an aside, and `_reread_as_prose` acting on the Pairs Extractor's
`NotPairs` diagnosis. See each constant's docstring in `config.py`.

**Two dormant safety nets, and do not delete them on one run** — four runs
established the behaviour each guards. `wire._without_empty_rows` drops a
zero-cell row before the table width check (two runs lost a whole table and the
385.00 Probe to one such row). `_reread_as_prose` recovers a Zone the Pairs mapper
rejects wholesale.

### Runs explain themselves

`trace.py` records every step of a Conversion — model calls *and* decisions — each
with a required `disposition` saying what became of its answer.
`tools/inspect_run.py` renders it in execution order:
GIVEN / ASKED / ANSWERED / HANDLED / RESULT per step, crop inline, prompts
collapsed. **Open `debug/runs/<label>/index.html` and read top to bottom.**
`trace.json` is in the dump for programmatic use.

### What is open, honestly

- **The suite is green: 573 pass, 0 fail.** *Any failure is a real regression.*
- **A real, isolated bug in `wire._without_empty_rows`.** It filters on
  `if row.cells`, which is truthy for `['', '', '', '', '']` — a list of empty
  strings is not an empty list. `sample_table_0003` returns a 17th row,
  `{'role': 'header', 'cells': ['', '', '', '', '']}`, and it survives. The drop
  tests cell **count**, not cell **content**. That is one of that fixture's two
  findings.
- **Titles are the whole of what is left to chase, and they are one lever.**
  Twelve of the 22 findings, and **every one has the same cause**: no pass writes
  `zone.title` on the shipped path at all — `title` was removed from
  `ClassifyResponse` and `DTH_CAPTION_PASS` ships off, which the
  baseline's `trace.json` confirms with **zero `read_caption` events on all five
  fixtures**. Grouping is now fixed as far as this corpus reaches, so **the
  caption pass is the next thing to measure** — it is the only lever on the
  largest category, and the reason it was held back no longer applies.
- **`DTH_CAPTION_PASS` works and still ships off.** It reads each Zone's Title in
  its own call, then withholds the caption band from the Kind question. The Title
  revives `with_grid(titled=)`, which was dead in production until it existed. It
  stays off only because it has never been measured one flag apart against the
  current default. The second half of that reason — that it cannot help while
  regions are split — **expired with run 81**: the regions it would caption are
  now whole, and their Titles are 12 of the 22 findings.
- **`DTH_LAYOUT_LONG_EDGE` applies only on the vision path.** The detector never
  reads it. It is the one default in `config.py` with no docstring, and it ships
  at a value no recorded run used — worth settling if the vision path is ever
  defended rather than deleted.
- **The `invoice_0002` panel question is answered.** Each panel opens with a
  **shaded caption bar**, which satisfies `CLASSIFY_PROMPT`'s own "top row set
  apart" test for a table. Withholding the bar fixes it; a prompt clause
  explaining the difference moved 0 of 6. The earlier rewrite that dropped the
  `pairs` same-line clause was checked later and did not move it.

### Lessons that generalise

- **`dth_env.txt` proves what was exported, not what was read — and a flag that
  does not arrive looks exactly like a flag that does nothing.** `DTH_HEADING_RULE`
  reached `Settings`, was recorded in the run directory, and never reached the
  detector: `bakeoff.engines_for` builds its own `EngineSet` rather than calling
  `orchestrator._layout_engine`, and it passed `from_name` the two arguments it
  already knew about. The arm came back **byte-identical to its baseline**, which
  is the signature of a change that did nothing — so the correct reading of that
  run was very nearly the opposite of the truth. `tools/iterate.sh` runs the
  bake-off, so *every measured run in this project takes that path.*
  **Before believing a null result, prove the arm was actually armed** — assert
  the flag reached the object that acts on it, not the `Settings` that carries it.
  `TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion` now compares the two
  paths attribute by attribute so the next setting is covered before it is added.

- **An instruction is reachable only if it asks the model to decide differently,
  not to perceive differently.** Two prompt attempts to stop the model splitting a
  wide table row failed, and one run's answers were **byte-identical** to the run
  before it. The model does not read the two ends of an 800px row as one line, so
  the instruction had nothing to act on. A *count* worked: the prompt has always
  said "give every data row the same number of cells as the header row" and the
  model has always obeyed exactly that. **It complies with how many, and ignores
  which line.**
- **When a model answers a closed question the same way every time, check whether
  the schema can express the true answer before rewording the question.**
  `CaptionResponse` first asked a boolean — is this line a heading? — and got
  `true` on 8 of 8 crops, because its test for a heading was word for word
  `CLASSIFY_PROMPT`'s test for a table's top row and no other answer was
  available. A third value — `caption` / `header` / `content` — took the same
  model from 4/11 to 8/11 with no change to the reasoning asked of it. `header`
  and `content` do the same thing in the pipeline; the distinction exists only so
  the model has somewhere to put the answer. **Do not collapse it to a boolean.**
- **A prompt rule that bundles two tests will be credited with the wrong one.**
  `pairs` required the label "on the same line as the value it names" — a
  geometric test and a semantic one in one sentence. Spec 0003 credits the whole
  clause with fixing a Zone, so it read as untouchable; in fact only the semantic
  half did that, and the geometric half was the sole cause of the `invoice_0002`
  panel regression. Dropping it left all 13 answers byte-identical. Check whether
  a clause is one rule or two wearing one sentence before defending it.
- **Do not gate a geometry change on geometry fields alone.** Spec 0004's Gate 1
  was pre-registered, passed every field it named, and shipped a regression that
  cost a Zone and a Probe. Any such gate must include *no Zone that previously
  converted stops converting*.
- **A reference that cannot be matched reads as a detector failure, and may be
  the reference.** `invoice_0002`'s `Services / Products` sat at **0.043** IoU
  against its own ink, under `MATCH_IOU` 0.50, so nothing the detector drew could
  ever pair with it — and the harness reported that as three references the run
  had missed. Before believing a `missing`, score the references against their own
  Source Image: `score_geometry(refs, refs, image)` should give `covered` 1.00 and
  `splits` 0, and does on all five now. `tools/fixture_geometry.py --snap` is what
  re-derives them.
- **A Zone's Title is a band of ink that is not a row.** `table_grid` counts
  printed lines, so a titled table measures one row too many —
  `sample_table_0003` gives 17 against a true 16. `with_grid` subtracts. Both
  numbers were right; they counted different things.

### The loop

`tools/iterate.sh <label>` — one document on the shipped defaults, which is what a
status question should be answered with. `FIXTURE=all tools/iterate.sh <label>`
runs all five. Set a `DTH_*` only to change **one** axis against that baseline,
and say which one when reporting the result.

Runs live in `debug/runs/<label>/`, which is **gitignored** and gets cleared —
regenerate rather than hunt, and never quote a run you cannot open. Nothing in the
suite reads a run directory.

Ollama reports the CPU/GPU split into `ollama_ps_after.txt` and the script warns
when the model was partly on CPU. **That affects timings only** — the answers are
unchanged — so a run with the warning is still valid for mismatch counts.
