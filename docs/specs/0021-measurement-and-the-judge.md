# Measurement and the judge: checks from the HTML, a batch runner, the review evolved

**Status: approved 2026-10-30, issue #44; being built.** The decisions
are at the end.
- **This is step L2** of the level-up plan
  ([`../level-up.md`](../level-up.md) §6), on branch `level-up`. Its
  outline is spec 0020's "What comes after this spec", L2.
- **It is written to be run in a fresh chat.** Everything it needs is here
  or linked.
- **It builds** the instrument every later step is measured with:
  - exact checks from the source HTML, with no model (§C);
  - a batch runner that converts a pool, detached and resumable;
  - one command that runs the checks over a run, reports them per family
    and per feature, and builds the review;
  - the visual-review skill, evolved to the criteria agreed on
    2026-10-24 ([`../agents/review-criteria.md`](../agents/review-criteria.md));
  - a private review page where Alessandro agrees or disagrees.
- **It changes no conversion code** (`level-up.md` §6: L1–L3 change none).
  No module a `Conversion` runs is edited. The proof at the end of every
  step that touches measurement code: `tools/replay_run.py` and
  `tools/rederive.py` over `tests/frozen/s14-result/` still give 21 of 21
  byte-identical, and its re-score still gives 0 differing fields.

**Why.** Nobody can open 200 sheets at every step. Words are already
checked exactly. Arrangement is not, and the probe's three worst faults
show how blind the numbers are to it (measured below):
- the lab report moves four results into the Flag column with tau 1.000;
- the quiz merges its fill-in cells with tau 1.000, beside 1.000 and no
  word lost;
- the recipe interleaves its method with its ingredients, and tau 0.766
  says only that something moved.

Each of these is derivable from the source HTML, which every corpus page
has. What the HTML cannot settle is left to Claude's review, by the agreed
criteria.

## Read first, in order

1. `CLAUDE.md`'s READ THIS FIRST.
2. [`../status.md`](../status.md).
3. [`../level-up.md`](../level-up.md): the Gist, §4.5, §4.9, §6, §7 and
   §8.
4. [`../agents/review-criteria.md`](../agents/review-criteria.md): what the
   checks and the review judge by. **Every severity in this spec is that
   table's**, except two it does not name, marked *inferred* in §C.
5. [`0020-the-corpus.md`](0020-the-corpus.md): "Outcome — the corpus" and
   "What comes after this spec".
6. [`../agents/visual-review.md`](../agents/visual-review.md) and
   `.claude/skills/visual-review/SKILL.md`: the skill this spec evolves.
7. This spec, end to end.

---

## Facts, measured 2026-10-30

Each was measured in the session that wrote this spec. Re-check any of
them before relying on it.

**The code.**
- **1567 tests pass (1 skipped), `mypy src/` clean**, on `level-up` at
  `aed2d1c`.
- **No conversion code has changed since `a0d73c9`**, the S14 sweep's
  commit. `git diff --stat a0d73c9 HEAD -- src/` touches only
  `corpus.py`, `factory/` and `projection.py` (spec 0020: the payload
  sent in chunks). So `tests/frozen/s14-result/`'s 21 documents and the
  probe's ten renders (`docs/level-up-probe/out/`, taken at `99110c2`,
  the same conversion code) are both today's output for their pages.
- **`projection.project()` reads text nodes only.** Per block it gives a
  role, the font size, weight, italic, mono, colours and one box per line.
  It gives **no box per word, no table grid, no rule a cell draws, and no
  list marker** (neither `::marker` nor `::before` content).
- **The renderer never writes `<ol>`** (no `<ol` in `src/`). It draws
  tables as `<table>` with `rowspan` and `colspan`, pairs as `<dl>`, lists
  as `<ul>`, and a disputed Cell as `span.disputed`: 7 of them across
  `s14-result/`'s 21 documents.
- **Four tools resolve a page through `corpus.SOURCES`**, the 21:
  `bakeoff.load_corpus`, `report.build`, `review.build` and
  `tools/rederive.py`. A manifest page (`c0001`, `probe_quiz`) fails in
  all four today.
- **`bakeoff` writes its dump after the last page** (`write_dump` runs
  after `run` returns), so a run that dies at page 199 of 200 keeps
  nothing.
- **`numbers.md`'s table is broken by two adjacent string literals**:
  `" |\n" "|---"` join before `* 9`, so the separator row prints nine
  times, a line break inside each.

**The pools.**
- **dev, 231 pages:** 191 generated (144 whole pages, 31 parts, 16
  fragments), 9 real PDF pages, and the 31 known (the 21 and the ten probe
  pages).
- **The L3 set, 36 panel pages:** four per family across nine families
  (fragments counted as one), 9 of them parts, no PDF page.
- **The source markup on dev's 231:** `<table>` on 131 pages, `<ul>` on 76,
  `<ol>` on 43, `<dl>` on 10, `h1`–`h6` on 175, `<br>` on 129, a `::before`
  rule on 13, `counter(` on 2. **Every page carrying a `table.*` feature
  draws its table as a `<table>`**: 211 of 211 across dev and the panel.

**The 31 known pages' HTML against their pictures** (each re-shot at
its picture's width by `projection.screenshot`, the corpus's shooter):
- **26 re-render to their picture pixel for pixel**: the sixteen authored
  since 2026-09 and the ten probe pages.
- **The five originals do not**, `invoice_0001` included: heights differ
  by −39 to +76 px, and 6.6–39.4% of pixels differ by more than 30 across
  the three channels. CLAUDE.md's "only `invoice.html` still re-renders
  to its screenshot (0.74%)" is stale; step 8 corrects it.

**The cost.**
- The probe: **292–838 s a page, mean 493 s (8.2 minutes)**
  (`docs/level-up-probe/results.json`). `S14-sweep`: 21 pages in 2h38m,
  7.5 minutes a page.
- So **dev's 200 pages not yet converted take about 27 hours**, and the
  L3 set's 36 about 5 hours.

**The three known faults, as they stand in the committed outputs.**

| page | the scorer | what the output does |
|---|---|---|
| lab report | tau 1.000; vanished `109`, `2291`, `73m2`, none of them a shifted result | every row whose Flag is empty draws its result as one cell spanning Result and Flag (`colspan="2"`). Right-aligned, `6.4`, `231`, `84` and `92` land at x 428–451, under Flag's header (320–345), not Result's (268–305). In the source they sit at 316–335, in the Result column |
| recipe | tau 0.766, beside 0.588, nothing vanished | the source has ten ingredients in a `<ul>` and five steps in an `<ol>`. The output has one `<ul>` of 13 items: steps 1, 3 and 5 sit among the ingredients, each a bullet with its number printed as text; steps 2 and 4 are elsewhere |
| quiz | tau 1.000, beside 1.000, nothing vanished | **the output's table has the source's grid exactly**: 3 columns, 4 rows, no span. The merge is drawn. The source rules every cell (`td, th {border:1px solid #111}`); the output leaves out 4 of the 6 rules between body cells (Potassium: Metal\|Observation; Calcium: Observation\|Reactivity; Copper: both) |

**The quiz means a cell check on markup alone is not enough.** A reader
sees cells as the rules divide them, so the checks read the rules too.

---

## How to work

- **Each step is its own commit, with its tests.**
- **No conversion code.** Every step that touches measurement code
  (`projection`, `scoring`, `report`, `review`, `bakeoff`) ends by
  re-proving the three loops on `s14-result/`: replay 21 of 21, rederive
  21 of 21, re-score 0 differing fields.
- **`project()` stays one function, both sides.** The richer reading is
  opt-in. Without it, the payload and every existing score are unchanged.
- **A threshold is set from a distribution, in its empty band.** Every
  constant the checks need is measured on the 31 known pages, source
  against output, and the histogram goes in its docstring.
- **A rule needs several pages of its kind behind it.** Each check is
  tested on real dev pages carrying its feature, drawn by seed, never on
  one page.
- **The vault is never opened.** `unseal=True` is never passed. L2
  converts no panel page, and the checks first meet the panel in L3.
- **Judge by eye, by the criteria.** Rubric judgements are in-session and
  pairwise only, and never tabulated across sessions.
- **Stop and ask Alessandro:**
  - at this plan;
  - before any conversion run longer than two hours;
  - before building the review page (step 6), with the
    `artifact-capabilities` skill loaded first;
  - whenever his calls on the review page disagree with the checks.

---

## §C — the checks

**Exact, from the source HTML, with no model.** Both sides are projected at
the source picture's width, the source flat (as the scorer does). Each
check returns faults. A fault names:
- its **check** and its **class** (below);
- its **severity**, from `review-criteria.md`'s table;
- the **element**: the words, quoted;
- **where**: its box on the source and on the output;
- its **features**: the page's card features the check bears on
  (`table.*` for a cell, `list.*` for a list, `kv.*` for a pair's lines),
  so the report counts per feature and per family.

**Everything goes through one word alignment.** The source's words in
reading order are aligned with the output's, the way the scorer
tokenises them (case folded, punctuation between words dropped). A block
the output moved is matched in a second pass. Every check below then
looks a source word up through the alignment.

| check | a fault when | class | severity |
|---|---|---|---|
| **words** | a source word is missing, counted as a multiset (the recipe's `4` in `SERVES 4` is printed elsewhere, so the set misses it) | lost | major |
| | the output prints a word the source does not | invented | major |
| | a lost word and an invented one sit at one aligned place: `2291` → `229 I`, `g salt` → `gsalt` | changed, merged, split | major |
| | a tick-box glyph (☐ ☑ ✓ ✗ □ ■ …) lost or changed | mark lost, mark invented | major (decision 5) |
| | a matched word's case or inner mark changed: `CSS` → `css` | spelling | major (decision 6) |
| **cells** | a source cell's words do not sit in the output column holding its header, read by where the ink falls (the lab report's `6.4` under Flag) | wrong column | major |
| | they do not sit on their row's band | wrong row | major |
| | they share one output cell with a neighbour's words | merged | major |
| **rules** | a rule the source draws between two cells, or round its table, is not drawn at the same place in the output (the quiz) | cells merged as drawn; rule missing | major |
| **structure** | a source table's words are not in an output table | table not kept | minor if **cells** passes (the right look from the wrong HTML), else **cells** carries the major |
| | a list's numbers are drawn as bullets (the recipe) | numbers as bullets | major |
| | a bullet is drawn where the source draws none, or a tick drawn as a bullet | marker changed | minor, *inferred* |
| | a list's items are not one item each, the look kept | list not kept | minor |
| | a source heading is not a heading in the output | heading not kept | minor if it looks the same; the **type** checks carry it if it does not |
| **order** | the words of two source groups (a list, a table, the section under a heading) interleave in the output's reading order (the recipe) | interleaved | major |
| | a block sits under a different heading in the output | under another heading | major |
| **lines** | a source line's words are not one output line, or an output line joins two source lines (a label printed over its value, flattened) | broken differently | major |
| **height** | the output's height is off the **picture's** by more than 10% | height | major; minor up to 10% |
| **alignment** | a source line's alignment (left, centre, right) changes | alignment | major |
| **type** | a block's face class changes (serif, sans, mono, script) | wrong face | major |
| | two blocks whose source sizes are ordered are drawn in the other order | sizes out of proportion | major |
| | a word printed bold is drawn regular | bold lost | major |
| | a word printed regular is drawn bold | weight added | minor, *inferred* |
| | italics change | italics | minor |
| **unread** | an element drawn as unread or disputed | counted | reported, not a fault |

**Reading order** on the output is its DOM order, as T2 already takes it.
**Lines** are the source's own: the HTML at the picture's width.

**Spelling inside a word.** The alignment folds case and drops
punctuation between words, as the scorer does, so `AQ7-MB-W` read as
`AQ7–MB–w` (the probe's datasheet) passes it. A second, strict comparison
of each aligned pair reports a changed case or inner mark, after the
source's `text-transform` is applied, small capitals excepted. Whether it
counts as a major is decided on the 31's evidence (step 2), not here.
**Decided: major** (decision 6).

### Pages that need care

- **A PDF page** (9 in dev, 9 in the panel): its picture is the PDF's
  render and its HTML a twin, so height is measured against the PNG.
  Lines come from the twin, which the gate admitted against the picture.
- **A part** (31 in dev, 9 in the L3 set): one section of a document, cut
  at its edges. A list may open at 5 and a table may have no header row,
  so the cell check falls back to columns by position. Nothing is
  reported for content the cut removed, because the source HTML is the
  part.
- **c0082** (panel): its twin spells `specifc` and `ftness` where the
  picture prints `specific` and `fitness`. A committed table of known twin
  spellings maps the twin's word to the picture's before any comparison,
  so a converter that reads the picture right is not called wrong.
- **The five original documents**, whose HTML no longer re-renders to
  its own picture (measured above): their lines are the HTML's, not the
  picture's, and each line fault on them says so. Height is the
  picture's, as on every page.
- **`ticket_0020`**, photographed: projected flat, as the scorer does.

---

## Steps

### Step 0 — the plan

This spec, re-measured; issue #44; Alessandro's approval, with the
decisions at the end of this spec.

### Step 1 — the reading

`project(..., detail=True)` adds to the payload, on both sides:
- **words**: each word's text, ink box, block, line, weight, italic, face
  class, size and colour;
- **lines**: per block, the words of each line, and the line's alignment
  in its block's box;
- **tables**: each `<table>`'s cells by row and column (spans expanded to
  slots), each cell's box and text, and which of its four edges draws a
  visible rule (a border wider than 0, not `none` or `hidden`, from the
  cell, its row or its neighbour under `border-collapse`);
- **lists**: each `<ul>`, `<ol>` and element shown as a list item, its
  items, and each item's marker class (number, bullet, tick, none), from
  the computed `list-style-type`, `::marker`, a `::before` with content,
  or an item's text opening with `1.`, `1)` or `(a)`;
- **unread**: elements drawn as unread or disputed.

**Gate.** Without `detail`, the payload is byte-identical, and
`s14-result/` re-scores with 0 differing fields. With it, tests on dev
pages carrying each feature, drawn by seed.

### Step 2 — the checks

`doc_to_html/checks.py`: §C's table, over two readings.

**Tests, two kinds:**
- **Mutations.** A fault is injected into a real dev source page and the
  check finds it, by its class, and no other check fires. Each on several
  pages carrying the feature: a value moved one column right, two cells'
  contents swapped, a rule between two cells removed, an `<ol>` turned
  into bullets, an item moved into another list, two lines joined, a
  centred line set flush left, a serif block set sans, a bold word set
  regular, a word dropped, doubled or merged with the next, the page
  squashed.
- **Identity.** Every dev source against itself: no fault on all 231.

**Thresholds** (line overlap, alignment slack, the margin two sizes need
to count as ordered, ink inside a column) are set on the 31 known pages,
each histogram in its docstring. The strict spelling comparison is run on
the 31 here, and Alessandro decides its severity from what it found.

**Done 2026-10-30.** `checks.py`, `corpus/twin-spellings.json`,
`tests/test_checks.py`. Measured on this code:
- **Identity: 231 of 231 dev pages clean.** No fault, and every token
  matched, in 945 s (4.1 s a page).
- **The three known faults, each found by its own class.** The lab
  report: `wrong column` on exactly `231`, `6.4`, `84`, `92`, each under
  `Flag`. The quiz: `cells merged as drawn` (4 of the 17 rules between
  cells missing) and `frame missing` (11 of 14). The recipe: `numbers as
  bullets`, `numbers lost`, `interleaved` and `under another heading`.
- **Mutations**, each on pages drawn by seed: two cells swapped, a rule
  removed, bullets for numbers, an item moved into another list, two
  lines joined, a centred line set left, serif set sans, bold set regular,
  a word dropped, doubled or merged, the page made taller. Each is found
  by its class, and no check outside its allowed set fires. A mutation
  the reader cannot see (same word boxes, same height) is skipped, not
  passed.
- **Thresholds, each from an empty band on the 31.** `SIZE_MARGIN` 0.05:
  blocks over the body size, none at 0.94–0.95 or 1.05–1.06. `GLUE`
  1 px: 83 word pairs touch at 0 px and 7,985 sit ≥ 2 px apart. Each
  histogram is in its constant's docstring.
- **Over the 31, against s14-result and the probe's renders**
  (8.4 s a page beside a running conversion): `invoice_0001` alone has
  no major. Pages touched, by class: height 30 (11 major, past 10%),
  sizes out of proportion 28, lines 21, alignment 21, bold lost 19,
  weight added 16, heading not kept 10, words changed 9, invented 8, wrong
  face 7, italics 7, lost 6, list not kept 5, marker changed 5,
  interleaved 4, mark lost 3, frame missing 3, wrong column 3, spelling 2,
  split 2, cells merged as drawn 2, under another heading 2, table not
  kept 2, numbers as bullets 1, numbers lost 1.
- **Spelling:** two on the 31, `CSS → css` (sample_css) and `VG → vg`
  (menu), both a case change. Major (decision 6).
- **A tick-box glyph lost** (`MARKS`) fires on form_0007 (`✕`),
  pricing_0017 (`✓`, `✕`) and the datasheet (`✓`). Major (decision 5).
- **False alarms found on the 31 and removed**, each by a rule rather than
  a page list:
  - a superscript in its own text node read as a split word (`GLUE`);
  - a list's drawn numbers read as invented (ordinal tokens);
  - an indented first line read as right-aligned (text-align in the
    block's own box);
  - CSS counters and `::after` glyphs read as lost (generated content
    is read);
  - a heading cascade (fires only where the source heading stays one);
  - one fault per kind of change per page, with its places.

### Step 3 — the batch runner and the four tools

`tools/batch.py <label> --pages dev | l3 | <ids>`:
- **the same Conversion a sweep makes**: the bake-off's engine path (the
  lesson of `DTH_HEADING_RULE`), its residency guard, and the run's
  commit, `DTH_*` and `ollama ps` recorded;
- **one page at a time, each page's dump written when it converts**;
- **resumable**: a restart skips every page whose dump is whole, and
  never converts a page twice;
- **seconds per page** in `pages.jsonl`; a page that raises keeps its
  trace and answers, and the run goes on;
- **detached**: started with `nohup` and its log; `--status` prints pages
  done, mean seconds and the time left;
- **refuses the vault**: `corpus.names` raises `SealedError`, and the
  runner never passes `unseal`;
- writes `debug/runs/<label>/` as a sweep does, so the report, the
  replay, the rederive and the review all read it.

**The four tools resolve pages through `corpus.page`**, so a manifest page
works: `bakeoff.load_corpus`, `report.build`, `review.build`,
`tools/rederive.py`.

**Tests**: a stubbed transport, the run killed after page k and
restarted, every page converted exactly once. **Then one real page**,
about 8 minutes, to prove it end to end.

**Done 2026-10-30, proved on c0544** (run `L2-3-proof`): 638 s, 19 calls,
converted, with its dump, `pages.jsonl`, `done.txt` and the residency
split recorded. **The first page tried, c0004 (35 Zones), was stopped
after 90 minutes.** One prose call on a crop under 1 KB ran to the token
limit (2,888 s, `reason=length`, 25,560 characters). The pipeline retried
it at twice the context (16,384), on the same crop, at under a character a
second, with 64% of the model on the CPU. That is the shipped
conversion's behaviour, which L2 does not change. It means one page can
take hours, so dev's 27 hours is a floor, not an estimate. **Fixed
alongside**: `batch.py` read the environment itself, which
`TestNothingElseReadsTheEnvironment` forbids. The host and the exported
`DTH_*` now come from `config.load()`, and the resident models from the
Ollama client.

### Step 4 — one command

`tools/measure_run.py <run> [--previous <run>]`:
- runs the checks on every page of the run → `<run>/checks/`, one file a
  page and `checks.json`;
- **the report**, `<run>/checks/report.md`: faults by check and class, per
  family and per feature, pages touched and occurrences, with `vanished`
  and invented words beside them;
- **picks the pages to review** (step 5's rule) and builds their sheets;
- writes the findings form with the checks' faults filled in, for Claude
  to confirm, reject or add to;
- writes the review page's data.

**Done 2026-10-30.** `doc_to_html/measure.py`, `tools/measure_run.py`,
`tests/test_measure_run.py`. A page's checks are kept until its output or
the checks' code (`CHECKS_CODE`, hashed) changes. A page whose checks
raise is recorded and the rest go on. With `--previous`, a page whose HTML
is byte-identical is unmoved and needs no screenshot. `--all` opens every
page (step 7). The review page's data is the filled `findings.json`, read
at step 6. Over the three known-fault probe pages, each is opened for the
class naming its fault, and the form arrives with the lab report's four
results numbered and waiting for a call. On the batch runner's proof page
(c0544, dev, never converted before) the checks find the "3.1–3.3"
numbers drawn as bullets, by eye correctly.

### Step 5 — the skill evolved

`review-criteria.md`'s "What the skill must change":

- **Faults, not axes.** The seven axes become faults, each with its
  class, feature, stage, severity, element and a note naming the element.
  `RUBRIC_VERSION` goes to 2, and `summarise` refuses to merge versions.
- **The exact checks run first.** Their faults arrive filled in. Claude
  confirms each by looking, since markup can still fool a check, and adds
  what the HTML cannot settle: what sits beside what, frames and fills,
  type, alignment of blocks, looks, figures.
- **Stages** come from `level-up.md` §1.2: rectify, layout, caption,
  classify, extract, inline runs, re-read, third reading, wire, locate, a
  named CV pass, render. Claude names one by reading the page's IR and
  trace, never by guessing from the picture.
- **Sheets.** Two panels at the source's width, and:
  - each fault a check found drawn as a numbered box on both panels,
    keyed to the form;
  - **zoomed tiles** for a dense page: a strip of the source over the same
    strip of the render, at full scale. A page is dense when its body type
    would reach the reader below a legible size; the size is set from the
    31's sheets;
  - with a previous run, its render as a third panel, and **a highlight of
    where the two renders differ**, pixel for pixel at matched width.
- **Sampling.** Claude opens:
  - every page where a check finds a major in cells, rules, lists or
    order, which a reader must confirm;
  - every page a change moved (its render differs from the previous
    run's);
  - two pages per family, by seed.

  A page flagged only by words, lines or height is counted, not opened:
  those checks are exact and their criteria settled.
- **The ranked roll-up.** Fault classes (class, feature, stage), majors
  first, ranked by pages touched, then by the biggest visible gain for the
  effort, with the reasoning shown.
- **Retired**: `owner`, and the rule about deferred faults. **Fixed**:
  `numbers.md`'s table.
- `docs/agents/visual-review.md` is rewritten as the record.

**Done 2026-10-30.** `review.py` at rubric 2:
- **`AREAS`**, the criteria's six rows; a check's fault maps to its area
  (a rule missing is a look).
- **`page_entry` and `blank_findings`**: the form, each fault numbered as
  on the sheet, with a call, a stage and a why.
- **`summarise`**: refuses another rubric; ranks the classes by Claude's
  `ranked` with why, else majors first by pages touched; names the pages
  where the review overturns a check, every worse page, and what is still
  unanswered.
- **The sheets**:
  - each fault is a numbered magenta box on both panels, its tag
    see-through and to the left of the box, so a marker under it still
    shows;
  - with a previous run, `-diff.png`: this render faded, red where it
    differs, with the share of pixels;
  - a dense page gets tiles, each strip of the render found through the
    checks' word anchors (`PageCheck.anchors`), never by height.

  `LEGIBLE_PX` is set at step 7 by opening the 31's sheets.
- **`numbers.md`'s table** has one rule row. `owner` is gone.

The skill and `docs/agents/visual-review.md` are rewritten for rubric 2.
`tools/visual_review.py --check` tallies a rubric-2 form.

### Step 6 — the review page — ask first

**Stop and ask Alessandro before building it**, with the
`artifact-capabilities` skill loaded.
- **One private Artifact page with a database.** On top, the ranked fault
  classes, each with an example sheet. Then every reviewed page, with the
  checks' calls and Claude's.
- **He ticks agree or disagree on each fault and adds a note**
  (decision 4), on these pages:
  - pairwise: every page called worse, plus two at random;
  - source-only (this spec's proof, L3's baseline): every page where
    Claude's call overturns a check, the three known-fault pages, and two
    at random (decision 2).
- **Claude reads his calls back** with `ArtifactData` and keeps them in
  the repository, `docs/agents/review-calls/<run>.json`.
- **Every disagreement changes the checklist**: the skill, or a check.
  The change is re-tested on all past calls: a check by a test pinned to
  his call; the review by judging the past called pages again.
- **Where his calls disagree with the checks, Claude stops and asks.**

### Step 7 — the proof on the 31 known pages

- **The run, `K0-known31`**, takes no model:
  - the 21 are `s14-result/`'s documents;
  - the ten probe pages are `docs/level-up-probe/out/<page>/render.html`;
  - `tools/rederive.py` over each reproduces it byte for byte, measured
    here (it is proved for the 21; for the ten it is measured for the
    first time in this step).
- **One command over it**, then Claude reviews. All 31 are opened, not a
  sample, so the sampling rule is measured: would the sample have found
  what the full review found?
- **It must catch the three known faults**, each pinned in a test over
  the committed outputs:
  - the lab report's results under Flag (**cells**, wrong column);
  - the recipe's steps among the ingredients (**order**, interleaved) and
    drawn as bullets (**structure**, numbers as bullets);
  - the quiz's cells merged by missing rules (**rules**).
- **The pairwise mode is exercised too**, on `s13-result/` against
  `s14-result/`'s documents as frozen: the highlight, the sampling of
  moved pages, and better / same / worse.
- **The page is published**, and Alessandro checks it.

### Step 8 — close

The outcome; `docs/status.md`, `CLAUDE.md` and `level-up.md` §6 updated;
issue #44 closed; a handover prompt for L3, the honest baseline on
`corpus/l3-subset.txt`.

### Alongside — dev converted (decision 1)

Decided yes. Once step 3's runner is proven, dev's 200 pages
not yet converted are converted with the shipped defaults, about 27 hours
detached, while steps 4–7 are built. The checks then run over all 231,
and the review samples them by step 5's rule. It shakes the checks down on
200 pages nobody has converted before L3 meets the panel, and gives P1 its
control arm on dev.

**Started 2026-10-30 22:57**, run `L2-dev`, and **stopped 2026-10-31 07:13
on its first page** (decision 7). c0004's 101st call, a prose read of a crop
under 1 KB, ran to the token limit (794 s). The retry at 16,384 context made
the model 7.6 GB on the 8 GB machine, with swap at 5.5 of 6 GB, and it ran
7.7 hours at a character every few seconds. Chrome jobs running beside it
made it worse. The first 100 calls had run at S14's speed (median 8.6 s
against 11.8 s). **Restarted after every Chrome job** (decision 8), as a
new run, with each page stopped at 20 minutes (decision 9).

**The limit proved, 2026-10-31**, on c0028, alone:
- **with a 1-minute limit** the page was stopped at 60 s mid-call. Ollama
  logged the client gone and cancelled the task (`stop: cancel task`),
  finished the image batch it was decoding (about 10 s), and went idle
  without generating; no child process was left;
- **with the 20-minute limit** the page ran away exactly as c0004 had: a
  prose read of a crop under 1 KB (`image=0KB`) streamed for 12 minutes
  with nothing finished, and the page was stopped at 1,200 s and recorded
  as timed out.

**Restarted 2026-10-31 08:57 as `L2-dev-mixed`** (decision 10): dev's 200
in an order that alternates family, density and kind, one page at a time,
stopped by `stop.txt` after page 20 for Alessandro's look before it goes
on. `tools/batch.py L2-dev-mixed --pages <the 200, in order>`; the order is
the run's `fixtures.txt`.

**The first 20, 08:57 to 12:54**: 14 converted (median 518 s, 90 to
1,001 s), 6 timed out, none raised. The timeouts have two causes, three
pages each, c0004 both:
- **big pages**: c0427, c0312 and c0072, all dense, had 86 to 99 calls
  behind them at medians of 15 s, every one normal. c0153 converted with
  105 calls in 1,001 s, so a page of about 100 calls sits at the limit;
  4 of the 7 dense pages timed out, 2 of 10 medium, 0 of 3 sparse;
- **runaways**: one call streams on and never finishes — a 48 KB table
  crop on c0008 (35,000 characters at 621 s), a 14 KB prose crop on c0493
  (19,500 at 497 s), and c0004's call 101, the one that ran away the night
  before. **It is not a near-empty crop**: 19 calls of the 20 pages had
  crops under 1 KB and answered. The characters arrive on the reasoning
  channel, where `qwen3-vl` puts its constrained answer, so it is most
  likely an answer repeating itself; the text was lost with the page.
  Every real answer on disk is under 5,600 characters.

`DTH_TIMEOUT_S` (180 s) does not bound a call: it is the client's limit
on each read of the stream, and c0008's call ran ten minutes under it.
**Decision 11**: a limit on each call's whole time, 3 minutes, the page
limit kept at 20.

---

## On disk

```
src/doc_to_html/checks.py          the checks (§C)
src/doc_to_html/projection.py      project(..., detail=True)
src/doc_to_html/review.py          faults, tiles, highlights, sampling, roll-up
tools/batch.py                     the batch runner
tools/measure_run.py               the one command
corpus/twin-spellings.json         c0082's known twin spellings
docs/agents/review-calls/          Alessandro's calls, per run
.claude/skills/visual-review/      the skill, evolved
debug/runs/<label>/checks/         the checks and the report, per run (gitignored)
tests/test_checks.py, test_batch.py, test_measure_run.py
```

## What L2 does not do

- **No converter change.** The criteria's queue (line ends as printed,
  unread boxes) waits for whichever pipeline wins P2.
- **No local model as the judge.** Claude is the judge.
- **No panel conversion, no vault.** L3 converts the L3 set.

---

## Decisions — Alessandro, 2026-10-30

| # | asked | decided |
|---|---|---|
| 1 | convert dev in L2? | **Yes, once the runner is proven** (step 3): dev's 200 pages not yet converted, about 27 hours, detached and resumable, while steps 4–7 are built. Claude says when it starts |
| 2 | in a source-only review, which pages does he check? | **Every page where Claude's call overturns a check, the three known-fault pages, and two at random** |
| 3 | the plan | **Approved as written**: steps 1–8 in order, §C's checks, the criteria's severities, and the two *inferred* ones as minor (regular drawn bold; a bullet added, or a tick drawn as a bullet) |

**Alessandro, 2026-10-31, at step 6:**

| # | asked | decided |
|---|---|---|
| 4 | the review page as planned: one agree or disagree per checked page? | **Agree or disagree per fault**, on the pages he checks, each with a note |
| 5 | a tick-box glyph lost or changed, inferred major | **Major** |
| 6 | the strict spelling comparison: a word's case or inner mark changed | **Major**, as a changed word is |

**Alessandro, 2026-10-31, after the dev run stalled on c0004:**

| # | asked | decided |
|---|---|---|
| 7 | the dev run, 8 hours on its first page | **Stopped.** A check first: invoice_0001 converted alone in 183 s, byte-identical to `s14-result/`, so the model and the pipeline work as before |
| 8 | how to avoid the hardware limit | **Every Chrome job first, then the model conversion on its own**, nothing else running beside it |
| 9 | a page that will not finish | **Stopped at 20 minutes** and recorded as a timeout, with the reason, not retried |
| 10 | how to start the 200 | **Prove the limit on one page first, then the 200 in a mixed order, stopping after page 20** to look at the times and the timeouts; one conversion at a time |
| 11 | after the first 20: 3 big pages, 2 runaways, c0004 both | **A limit of 3 minutes on each model call**, conversion code (L2's one change to it); **the page limit stays 20 minutes**, so the biggest dense pages stay timeouts |
