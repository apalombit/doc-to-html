# Four repairs after the structure step, one sweep

**Status: under way, issue #32 — steps 0, A, B, C and D done 2026-10-11
(B's and C's sweep clauses wait for step E; C1 corrected and confirmed; D's
4a dropped on a failed gate, 4b shipped). Step E, the sweep, next.**
Alessandro's decision, taken on
2026-10-11 after reviewing sweep `S3-sweep` (spec 0008's outcome):

1. **`S3-sweep` becomes the floor.** Freeze it first.
2. **Then, in this order:** #2 wire row nets → #1 cut at a grid's inner
   splits → #3 the detector's own sections → (#4 page width, judged useful).
3. **Then one end-to-end sweep** measures all of them together.
4. **The menu's richer layout spec is deferred.** #3 may make it moot.

It works under spec 0007's target and ratchet. Spec 0008 is closed. Its
design record and every step's outcome are in
[`0008-page-structure.md`](0008-page-structure.md).

**Keep it small.** Each repair reuses something already built and fixes one
named fault on named documents. If a repair needs more machinery than its
section describes, stop and report. That is a finding, not a failure.

---

## 1. What spec 0008 changed (the code this plan builds on)

| step | code | what it does |
|---|---|---|
| 1 | `structure.structure(image, boxes, *, ground, inverted) -> list[Region]` (new module `src/doc_to_html/structure.py`) | Reads the page's regions off its pixels and its Zones' boxes, top to bottom. **`grid`** = a full lattice of identical drawn boxes, at least 2 columns. **`columns`** = a drawn divider (a panel's side, a full-height fill, a vertical rule) with one block beside two stacked blocks. **`single`** otherwise. |
| 2 | `ir.Flow`, `ir.Region(top, bottom, flow, splits, rows)`, `Document.regions`; `render._columns` | The IR carries the regions. The renderer draws a `columns` region as flex lanes, each read top to bottom. Every other page renders exactly as before. |
| 3 | `structure.cut_at_edges` via `orchestrator._cut_at_regions`; `structure.alike` via `_read_copies_alike` | A Zone crossing a grid or column region's **top or bottom edge** is cut there. A grid's copies take the majority Kind. |
| — | `tools/rederive.py` step 7 | Re-derives regions offline. |

Commits: `230fafb` (step 1), `0f749d2` (step 2), `9c42d81` (step 3), and
`6e0b9ed` (docs). 860 tests pass and mypy is clean.

**What was measured and rejected in spec 0008** (do not rebuild these):

- A whitespace gutter as column evidence (A2 §7).
- Columns without a drawn divider: they invent columns on 5 of the 10 untouched documents.
- Two column renders that keep T3 `beside`: one opens big gaps, the other makes pages 3–6× too tall.
- A closed model question for the menu's columns: `qwen3-vl:4b` gave the same answer on 20 of 20 crops, in two wordings.

---

## 2. Where spec 0008 gained (S3-sweep against the old floor `q5-result/`)

| document | gain |
|---|---|
| `cv_0013` | **Large.** The sidebar is a real column, read down. tau 0.56 → 0.98, height 3.0× → 2.0×. |
| `catalogue_0015` | **Largest content gain.** The title is back, 29 words are back (vocabulary recall 0.84 → 0.99), and all nine cards are read alike. |
| `darkdeck_0009` | **Medium.** The aside is a column, and the page is shorter (height 1.68× → 1.32×). The tiles and two headings are still wrong (§3). |
| `newsletter_0008` | **Reading order only.** tau 0.86 → 1.00, almost the same by eye. |
| other eleven | **None, by design.** They have no drawn columns or grids. |

Corpus means, `q5-result` → `S3-sweep`: vocabulary recall 0.971 → 0.981,
tau 0.937 → 0.986, height ratio 1.62 → 1.44. **Below the old floor, accepted:**
T3 `beside` on `cv_0013` (0.58 → 0.40) and `darkdeck_0009` (0.97 → 0.81),
which is the price of reading columns as columns, and one precision token on
`catalogue_0015`. N4's recorded exception is gone: `catalogue_0015`'s
`beside` rose to 0.273.

---

## 3. Remaining faults, by conversion stage (S3-sweep)

Scores are from `debug/runs/S3-sweep/scores.json`, which becomes
`tests/frozen/s3-result/scores.json` in step 0. The "evidence" column was
measured 2026-10-11 on S3-sweep's IRs and on the detector's raw output for the
same pixels. The detector is CV and deterministic.

| document | what's wrong | stage | evidence |
|---|---|---|---|
| `form_0007` | The whole form is one Zone. The section headings vanish, and the two-column fields become one list. | **Layout.** One box holds six sections. | **Worst document:** vocabulary 0.862, `beside` 0.059. `vanished` holds 18 words, including `category`, `contact`, `declaration`, `emergency`, `signature`. Zone 2 runs y 0.091–0.941 at full width. |
| `menu_0012` | The two columns are read as one table, with headings paired across (`To begin \| Main courses`). | **Layout** (same cause) | tau 0.923, `beside` 0.348, height 2.57× (the worst). Zone 1 is a `table` at x 0.04–0.96, with 26 rows of 2 cells under a 1-cell header. |
| `darkdeck_0009` | The four KPI tiles come out as one 4-column table. Content is complete; the shape is wrong. | **Layout.** One box spans the 1×4 grid that step 1 already found. | Zone 2 runs x 0.050–0.872, y 0.202–0.276, inside grid region y 0.182–0.293 with splits 0.264 / 0.5 / 0.737. |
| `darkdeck_0009` | `OPEN RISKS` and `DECISIONS WANTED` are gone. | **Extract.** The list reading drops the heading line. | `vanished`: `decisions open risks wanted` |
| `nonlatin_0014` | The total row is one cell too wide, and an extra row repeats `12.437,82`. The totals do not line up with the table. | **Extract → wire.** The model padded the rows, and no net catches this shape. | Zone 4, header 4 cells: `['', '', '', 'Συνολικό πληρωτέο', '12.437,82']`, then `['', '', '', '', '12.437,82']`. `duplicated`: `12.437,82` ×2. The source prints it once (`example/nonlatin.html:103`). |
| `receipt_0010` | Drawn 500px wide where the paper is 335px. Small monospace type comes out large and sans, the dashed rules are missing, and the header row has shading the source doesn't have. | **Style / render** | height 2.16×. The only warped page: source 500px, flattened page 335px. Every other document's flattened width equals its source width. |
| 13 of 15 | Separator rules are never drawn. | **Render** | `structure._rules` finds 24 wide (≥ 0.5 page) horizontal rules between Zones. **0** `<hr>` appear in any output. The receipt's dashed rules are not among them, because each dash is its own component. |
| many | Mastheads and titles are too small. | **Render** (the type scale, "measured, not shipped") | sheets |

### The new evidence for #3, measured 2026-10-11

The split was never missing: `outermost` discarded it. That is
`split_containers`' own lesson, and here it repeats.

- **`form_0007`.** Heron reports `form` at **0.97** over x 0.031–0.968,
  y 0.090–0.961. Inside it are **six `section_header` detections**
  (scores 0.48–0.67), one per printed section. Their tops are at y 0.096,
  0.250, 0.392, 0.473, 0.698 and 0.839, and each starts at x 0.041–0.047.
  `outermost` keeps the container and drops them.
- **`menu_0012`.** Heron reports `document_index` at **0.76** over
  x 0.043–0.956, y 0.229–0.821. Inside it are two `document_index` boxes
  **side by side**: x 0.043–0.476 (y 0.272–0.822, 0.55) and x 0.523–0.955
  (y 0.281–0.788, 0.68). Section headers sit above each, at x 0.216 and
  x 0.672 (y 0.227), and one more is at x 0.693, y 0.553.
  - `split_containers` cannot use them for two reasons. `SPLITTABLE` is
    `{"table"}` only, and `SPLIT_INK` 0.98 fails because the headings sit
    outside the two parts.
- Re-running the detector on the big Zone's crop finds the same parts, so the
  crop re-run adds nothing. The page-scale pool already holds them, at no
  second forward pass.
- **Why `SPLITTABLE` is one class** (its docstring): unrestricted, the split
  fires on `text` holding `text`, which is prose cut into its lines. Any
  widening must be scoped and must prove it fires nowhere else.

---

## 4. Directions, ranked by gain for cost — what this spec does

| # | stage | change | why | cost / how measured | order here |
|---|---|---|---|---|---|
| 2 | **Wire** | Two row nets: trim a too-wide row's **leading empty** cells to the header's width; drop a summary row that only repeats the cell above it. | `nonlatin_0014`'s totals line up and the duplicate goes. Same shape as the shipped `_without_repeated_header`. | **Offline:** `replay_run.py` over `s3-result/`'s answers. No crop moves. | **A** |
| 1 | **Layout** | Also cut a Zone at a **grid region's inner splits**, not only at its top and bottom. | `darkdeck_0009`'s tiles become four cards, read alike. Reuses step 1's grid, so nothing new to detect. | `layout_front.py` predicts that only `darkdeck_0009` moves. Crops move, so the sweep measures it. | **B** |
| 3 | **Layout** | Keep the detector's own sections: cut a container at the `section_header`s it holds, and split a container into same-class parts that sit **side by side**. | Largest remaining loss: `form_0007` and `menu_0012` share one cause. The evidence is the detector's suppressed proposals (§3), a new kind. Pixels and the 4B model are exhausted. | `layout_front.py` must show it fires on those two documents only and splits no table. Crops move, so the sweep measures it. | **C** |
| 4 | **Style / render** | 4a: draw a photographed page at its flattened paper's width. 4b (optional): draw the separators `structure._rules` already finds. | 4a fixes the receipt's width and height. 4b puts separators on 13 documents. Content cannot change. | **Offline:** `rederive.py` over `s3-result/`. | **D** |
| 5 | **Extract** | The list extractor keeps a heading line (`OPEN RISKS`). | 4 words on `darkdeck_0009`. | A prompt change risks every other answer (A1's lesson). | **not now** |
| — | Render | The type scale | Large visual gain on most pages. | It is not structure work. It once crossed T3 `beside`, so re-measure it against the new floor in its own piece of work. | **not now** |

**Not worth more effort:** recovering `beside` on `cv_0013` and
`darkdeck_0009`. Both alternatives were measured and look worse.

**Menu richer layout spec: deferred.** Revisit only if #3 leaves `menu_0012`
paired across its columns. Its targets would be `menu_0012` and whatever #3
leaves of `form_0007`. It would need a stronger model than `qwen3-vl:4b`.
`gemma4:31b-cloud` is installed, but it sends page images out, so that is
Alessandro's call.

---

## 5. Work plan

Each step has its gate written below, **registered before any code**. After
each step, report against the gate in the §7 format and carry on to the next
step. **If a gate fails, stop and ask Alessandro.** Do not argue a failed gate
into a pass. Commit each step on its own, as spec 0008 did.

### Step 0 — freeze `S3-sweep` as `tests/frozen/s3-result/`

**First check that `debug/runs/S3-sweep` still exists.** If it was cleared,
say so before anything else. Re-taking it costs about 1½ hours (it took 1h32m,
490 model calls) and must be at commit `9c42d81`'s code.

Same shape as `q5-result/`. Its README is the template.

- `documents/<name>.html`: the fifteen files from
  `debug/runs/S3-sweep/dump/qwen3-vl_4b/<name>/document.html`.
- `scores.json`: S3-sweep's own, scored against `q5-result/`.
- `answers/`: `python tools/replay_run.py debug/runs/S3-sweep --save-answers tests/frozen/s3-result`.
- `dth_env.txt`: S3-sweep's, which is empty, meaning the shipped defaults.
- `README.md`. Provenance: sweep `S3-sweep`, 2026-10-10, commit `9c42d81`,
  `qwen3-vl:4b`, 54%/46% CPU/GPU, 490 calls. It also names the three legs below
  `q5-result/` that Alessandro accepted (§2), and says N4's exception is gone.

**Prove the four loops on it, as `q5-result/` did:**

1. Scored straight out of `documents/`: 15 documents, 0 differing fields.
2. `tools/rederive.py tests/frozen/s3-result --label S3-base`: 15 of 15
   byte-identical to `documents/`. **Keep `debug/runs/S3-base`.** It is the
   floor as a run directory, and step E's sheets use it as `--previous`.
3. `tools/replay_run.py tests/frozen/s3-result`: 15 of 15 byte-identical.
4. `tools/layout_front.py`: its Zones match the IRs' band, column and bbox on
   15 of 15.

**If one of the four misses**, the README names which document and why
(`reshot/`'s README is the precedent). It is not silently re-cut.

Then move the floor everywhere it is named:

- CLAUDE.md: the frozen-directory table and the "ratchet against" command.
- `docs/status.md`.
- The default in any tool that names `q5-result`: `tools/replay_run.py`,
  `orchestrator.py` and `preprocess.py` mention it. Change docstrings only
  where they state the floor; their history stays.
- `tests/test_structure.py` reads boxes from `q5-result/`. Leave it unless
  repointing changes no assertion.

**Gate 0:** all four loops reproduce, or the README states the exception. The
floor is named as `s3-result/` everywhere it is stated. The suite passes.

#### Outcome — step 0, 2026-10-11, gate MET

`debug/runs/S3-sweep` was still there (commit `9c42d81`, empty
`dth_env.txt`, 54%/46% CPU/GPU, 490 calls by the bake-off's per-pass table,
the same count `answers/` holds). Frozen as `tests/frozen/s3-result/`.

| # | clause | result |
|---|---|---|
| 1 | scored straight out of `documents/` | **holds** — 15 documents, 0 differing fields against `scores.json` |
| 2 | `rederive.py` → `S3-base` | **holds** — 15 of 15 byte-identical; `debug/runs/S3-base` kept, with its own report |
| 3 | `replay_run.py` from `answers/` | **holds** — 15 of 15 byte-identical |
| 4 | `layout_front.py` Zones vs the IRs | **holds** — band, column and bbox match on 15 of 15 |
| 5 | the floor named as `s3-result/` everywhere it is stated | **holds** — CLAUDE.md (table, command, loop paragraphs), `docs/status.md`, `tools/replay_run.py`'s usage; `q5-result/`'s README marked record |
| 6 | suite passes | **holds** — 860, mypy clean |

`orchestrator.py` and `preprocess.py` name `q5-result/` only as where a
measurement was taken, so they stay. `tests/test_structure.py` stays on
`q5-result/`'s boxes: repointed, `test_the_catalogue_title_is_cut_out_of_the_first_card`
fails, because the title is already cut out in `s3-result/`.

Against `q5-result/`, seven documents moved: spec 0008's four, and
`invoice_0002`, `receipt_0010` and `statement_0006` by N1–N4. The README
tabulates them.

### Step A — #2, two wire row nets (`nonlatin_0014`)

**Where:** `wire.rows_from_table`, after
`_without_repeated_header(_join_split_header_row(_without_empty_rows(...)))`
(`src/doc_to_html/wire.py`, about line 561). Two functions in the same shape
as the three nets already there, each with a docstring holding the
measurement:

- **Trim to the header.** A non-header row wider than the header loses
  **leading empty** cells until it fits. It **never drops a non-empty cell.**
  `menu_0012`'s 2-cell rows under a 1-cell header carry text in both cells and
  must be untouched. The existing `table_repairs` Caveat already reports
  those rows.
- **Drop a repeated total.** A `summary` row is dropped when every non-empty
  cell in it equals the cell in the same column of the row directly above it.
  That row says nothing new. Run it after the trim, so the columns compare.

Because these change the IR, add the IR-level equivalent to
`tools/rederive.py` step 1, beside `repadded` (CLAUDE.md: "any new downstream
step that writes the IR must be added to `rederive.py`").

**Measure:** `tools/replay_run.py tests/frozen/s3-result --label S4-A-replay`,
then the report with `--previous tests/frozen/s3-result/scores.json`, then
open `nonlatin_0014`'s sheet.

**Gate A:**

1. In `nonlatin_0014`'s table, every row has 4 cells. `Συνολικό πληρωτέο |
   12.437,82` sits in the same two columns as `ΦΠΑ 24% | 2.407,32`, and
   `12.437,82` prints once. Check it in the picture, not only in the IR.
2. The other 14 documents are byte-identical to `s3-result/`.
3. No ratchet leg falls on `nonlatin_0014`, and precision rises.
4. Tests pin both nets, including two negatives: a non-empty cell is never
   trimmed, and a summary row that adds any new cell is kept. Suite and mypy
   are clean.

#### Outcome — step A, 2026-10-11, gate MET

`wire._trimmed_to_header` and `wire._without_repeated_total`, run in that
order after `_without_repeated_header`; `wire.retrimmed` is the IR-level
pair, added to `tools/rederive.py` step 1. Measured by replay,
`S4-A-replay`, over `s3-result/`'s answers.

| # | clause | result |
|---|---|---|
| 1 | every row 4 cells; the grand total under `ΦΠΑ 24% \| 2.407,32`; `12.437,82` once — in the picture | **holds** — sheet opened beside `S3-base`: totals in the label and figure columns, printed once, the table now the page's width as in the source |
| 2 | the other 14 byte-identical | **holds** — 14 of 15 |
| 3 | no ratchet leg falls on `nonlatin_0014`; precision rises | **holds** — precision 0.9510 → **0.9652**; recall, tau, beside unchanged; `duplicated` empty; height 1.479 → 1.426 |
| 4 | tests pin both nets and the two negatives; suite and mypy | **holds** — six tests in `TestATotalsRowPaddedOnTheLeft`; 866 pass, mypy clean |

`rederive.py` over `s3-result/` now reaches the replay's bytes on 15 of 15,
so the IR-level pair matches the wire-level one.

**Two guards narrower than the rule as written**, each on the side where
being wrong is cheaper, and neither changes what fires on the corpus:

- The trim acts only where the header's width is the table's — at least as
  many rows of that width as wider ones. `menu_0012` and `cv_0013` both read
  a one-cell header over wider rows; trimming to it would move values left.
- A total is dropped only under another summary row. A total equal to the
  one data row above it is a real shape, and dropping it loses a number.

Over every table answer in `s3-result/`, both nets fire on `nonlatin_0014`
alone: two wide rows opening empty, one repeated total.

### Step B — #1, cut at a grid's inner splits (`darkdeck_0009`)

**Where:** `structure.cut_at_edges`. Today it cuts at region tops and bottoms.
Add one thing: a Zone lying inside a `grid` region whose box crosses one of
the region's lane splits (`Region.splits`) is cut there too, vertically. Each
part is snapped, dropped below `MIN_ZONE_INK` and re-banded exactly as the
existing cut does. `alike` then reads the copies alike, unchanged.

Predicted, from S3-sweep's boxes: only `darkdeck_0009` Zone 2 is cut, into 4.
`catalogue_0015`'s nine cards each sit inside one cell, and `nonlatin_0014`'s
two panels each sit inside one half, so neither moves.

**Measure:** `python tools/layout_front.py <out>` (model-free, about 11 s),
compared with `s3-result/`'s IRs. Then replay: `darkdeck_0009` should come
back **ASKED MORE THAN THE RUN**. That is expected, because its crops moved,
and the sweep measures it.

**Gate B:**

1. Layout front: `darkdeck_0009`'s tile box becomes 4 Zones, one per tile,
   each in its own lane of the grid region. The other 14 documents' Zones are
   identical to `s3-result/` (band, column, bbox).
2. Replay: 14 documents byte-identical, and `darkdeck_0009` marked as asking
   more.
3. Tests pin it on a synthetic grid and on `darkdeck_0009`'s boxes. Suite
   and mypy are clean.
4. *Checked in the sweep (step E):* the four tiles render as four cards side
   by side. `P95 LATENCY`, `INGEST VOLUME` and `COST PER MILLION` all print.
   A0 once lost exactly these words by cutting this band, so open the crops.

#### Outcome — step B, 2026-10-11, gate MET offline (clause 4 waits for the sweep)

`structure.cut_at_edges` also cuts a part a grid holds at the grid's lane
splits, through `_across_lanes`; nothing else changed. Measured on the layout
front, then by replay over `s3-result/`'s answers, `S4-B-replay`.

| # | clause | result |
|---|---|---|
| 1 | `darkdeck_0009`'s tile box → 4 Zones, one per lane; the other 14 identical | **holds** — x 0.050–0.133, 0.287–0.368, 0.523–0.619, 0.759–0.872, lanes 0–3, one Band; the regions read back unchanged; 14 of 15 match `s3-result/` |
| 2 | replay: 14 byte-identical, `darkdeck_0009` asks more | **holds** — 14 identical to `S4-A-replay` (13 to `s3-result/`, plus `nonlatin_0014` as step A left it); darkdeck asked 55 calls against 50 |
| 3 | tests on a synthetic grid and on darkdeck's boxes; suite and mypy | **holds** — three tests in `TestTheStructureShapesTheBoxes`; 869 pass, mypy clean |
| 4 | *sweep:* four cards side by side, the three labels print | waits for step E |

The four crops were opened as the model will be shown them: each holds its
whole tile — label, figure and change — so the cut falls in the gutters, not
through the labels A0 once lost.

### Step C — #3, the detector's own sections (`form_0007`, `menu_0012`)

**Where:** `engines/detector.py`, in `LayoutEngine.detect_zones`'s step
order. Two candidate rules. Build the smaller one that meets the gate; if one
rule covers both documents, prefer it.

- **Sections.** A container holding **two or more** `section_header`
  detections below its own first line is cut at each one's top. Each part
  begins with its heading, which is the Zone convention: a heading and the
  content it names are one Zone, with the heading as its Title. That covers
  `form_0007`.
- **Side-by-side parts.** A container whose same-class parts sit **side by
  side** (not `_stacked`, the signal `prefer_container` already trusts) is
  split into them. Each heading just above a part is joined to that part, so
  `attach_headings` must run after. The ink test counts the headings with the
  parts. That covers `menu_0012`. Its two columns then stand in one Band,
  which the band render already draws side by side; no `columns` region is
  needed.

**Respect `SPLITTABLE`'s reason.** Scope any widening to what the corpus
measures (`form`, `document_index`, `section_header`). Prove on all fifteen
that it fires nowhere else, and above all that it splits no table:
`sample_table_0003`, `statement_0006`, `nonlatin_0014` Zone 4,
`darkdeck_0009` Zone 9, `receipt_0010` Zone 1, and both invoices' tables.

**Measure:** layout front first (a box overlay per moved document, opened and
looked at), then replay, which marks the moved documents as asking more.

**Gate C:**

1. Layout front: `form_0007`'s Zone 2 becomes one Zone per printed section.
   There are six; a sliver above the first heading may go to `MIN_ZONE_INK`.
   Each starts at its heading.
2. Layout front: `menu_0012`'s body becomes two side-by-side Zones, or four
   if the sections rule also cuts each column. No Zone spans both columns.
3. Every other document's Zones are identical to `s3-result/`, and no table
   is split.
4. Tests pin it on the two documents' raw detections and on a negative: a
   `text` holding `text`, and a table with a caption, stay whole. Suite and
   mypy are clean.
5. *Checked in the sweep:* `form_0007`'s six section headings print,
   vocabulary recall rises from 0.862, and `beside` rises from 0.059.
   `menu_0012`'s courses read down each column, with `To begin` no longer
   beside `Main courses` in one row. Height falls from 2.57×.

**Stop rule.** If no rule separates these two without moving another
document's Zones, stop. Record what was tried in this spec. That result is
the evidence for the deferred richer layout spec.

#### Outcome — step C, 2026-10-11, gate MET offline (clause 5 waits for the sweep) — with one correction to clause 1

Both rules, each scoped to `SECTIONED = {form, document_index}`, in
`engines/detector.py` after `split_containers`: `split_side_by_side` and
`cut_at_sections`. Measured on the layout front, then by replay over
`s3-result/`'s answers, `S4-C-replay`. The stop rule did not fire.

**Clause 1 counted a detection that is not a section.** The form prints
**five** sections, `1. APPLICANT DETAILS` to `5. DECLARATION`. Heron's sixth
`section_header` (y 0.250, 0.54) is `17 Bellwether Lane, Castleton` — the
address field's *value*, labelled like the real headings (0.48-0.67, the same
`list_item` twin), so nothing in the pool tells it apart. Cut there, section 1
splits between `Address` and its value. What does tell it apart is the page:
`style.rectangles` finds the address field drawn round it and nothing round
any of the five real headings, which sit on shaded bars. So `cut_at_sections`
skips a heading inside a drawn rectangle — one predicate on a finder already
built, and the one piece of machinery beyond the section above. Clause 1 is
read as its own words have it: one Zone per printed section, each starting at
its heading.

| # | clause | result |
|---|---|---|
| 1 | `form_0007`'s Zone 2 → one Zone per printed section, each starting at its heading | **holds, five** — y 0.091, 0.386, 0.468, 0.692, 0.833, each opening on its heading bar; the address stays in section 1 with its label. The spec's "six" counted the field value above |
| 2 | `menu_0012`'s body → two side-by-side Zones; none spans both columns | **holds** — x 0.045-0.475 and 0.525-0.955, one Band, each opening on `To begin` / `Main courses`; the title and subtitle are one Zone above |
| 3 | every other document's Zones identical; no table split | **holds** — 13 identical to step B's layout front; every named table among them |
| 4 | tests on the two pages' raw detections and the negatives; suite and mypy | **holds** — nine tests in `TestTheDetectorsOwnSections`, among them a `text` holding headings, a table with a caption, stacked parts; 877 pass, mypy clean |
| 5 | *sweep:* section headings print, vocabulary and beside rise on the form; the menu reads down each column, height falls | waits for step E |

Replay: `form_0007` (20 calls against 12) and `menu_0012` (13 against 10)
ask more, as predicted; the other 13 identical to `S4-B-replay`.

Over all fifteen pages, scoped, the two rules fire on these two containers
only; unscoped, the side-by-side rule fires on twelve more pages, every one
a line, footer or page header cut into words — `SPLITTABLE`'s reason, measured
again.

### Step D — #4, the page width (`receipt_0010`), and optional separators

**4a, judged useful.** Only `receipt_0010` was flattened from a photograph
(`Rectified.warped`, 500px → 335px). Draw `.doc` at the flattened page's
width **for a warped page only**.

- The renderer deliberately ignores `page_px` today: `render.py`, about line
  276. Setting every page to its source width cost `invoice_0002`'s `beside`
  0.640 → 0.295. Scoping to warped pages leaves those 14 alone.
- Carry the width as one new IR field set only when warped (e.g.
  `Document.paper_px`), and add it to `rederive.py`, which already rectifies.
- A3's lesson about bytes: the other 14 then differ **only by that one null
  key inside the embedded IR**. Say so in the gate, and strip it from both
  sides when comparing.

**4b, optional, one attempt.** Carry the wide horizontal rules that
`structure._rules` finds between Zones, and draw each as a rule between the
Bands it separates.

- Filter out a table's own border, which sits just outside its snapped box
  (`darkdeck_0009` y 0.789, `sample_table_0003` y 0.964).
- It moves 13 renders, and T5 samples the whole screenshot.
- **Ship only if `rederive.py` shows no ratchet leg falling on any of the 13
  and the sheets look closer to their sources.** Otherwise record the
  measurement here and drop it. It does not help the receipt.

**Measure:** `tools/rederive.py tests/frozen/s3-result --label S4-D-rederive`,
then the report and the sheets.

**Gate D:**

1. 4a: `receipt_0010` renders at the paper's width, and its height ratio
   falls from 2.16×.
2. 4a: no ratchet leg falls on it.
3. 4a: the other 14 are byte-identical outside the embedded IR, and inside
   it differ by the new key only.
4. If 4b ships: no ratchet leg falls on any document, and each moved sheet
   was opened.
5. Tests and mypy are clean.

#### Outcome — step D, 2026-10-11: 4a measured and dropped (gate D1 failed); 4b shipped

**4a — the receipt at its paper's width — fails D1, and Alessandro dropped
it.** Built as `Document.paper_px`, set only on a warped page, drawn as
`.doc { max-width }`, and measured by rederive over `s3-result/`
(`S4-D-rederive`, against `S4-A-rederive`):

| # | clause | result |
|---|---|---|
| D1 | receipt at the paper's width; height ratio falls from 2.16× | **FAILS** — drawn at 335px, height ratio **2.163 → 2.233**, `clipped` 0 → 1 |
| D2 | no ratchet leg falls on it | holds — and only because the projection still reads clipped text |
| D3 | the other 14 identical outside the IR, inside by the new null key only | holds, 14 of 14 |

In the picture the receipt got worse: at 335px the type is still the
render's large sans, not the receipt's small monospace, so the price column
was cut off the page, `29/08/2026` and `CONTACTLESS` were clipped, and more
names wrapped. **What would have to become true:** the receipt's type drawn
at its own size — the type scale, "measured, not shipped" in `docs/status.md`
— and only then its width. The diff is not kept in the tree.

**4b — drawn separators — ships.** `structure.separators` finds each wide
horizontal rule (≥ 0.5 of the page) that lies in no Zone and is not a table's
own border; `Document.separators` carries them, set in `_read_structure` and
by `rederive.py` step 7; the renderer draws one bordered `div` per gap
between drawn rows that holds a rule, inside the gap the rows already leave.
Measured by rederive, `S4-D-separators` against `S4-D-base` (rederive at the
step-C commit, which reproduces `S4-A-rederive` 15 of 15).

| # | clause | result |
|---|---|---|
| D4 | no ratchet leg falls on any document; each moved sheet opened | **holds** — no leg falls on any of the fifteen against `s3-result/`; all eleven moved sheets opened beside `S4-D-base`, each rule where the source draws one, none worse |
| D5 | tests and mypy | **holds** — `TestTheRulesBetweenZones`, seven tests; 885 pass, mypy clean |

21 of the spec's 24 rules are drawn-eligible, on eleven pages (the spec's
"13" counted pages with any wide rule; `cv_0013`'s, `receipt_0010`'s and
`invoice_0001`'s sit inside Zones): newsletter's double masthead rule draws
as one. Two things the first measurement found and the shipped one fixes:

- **A table's border is told by its row rules *and* its nearness.** Width
  alone dropped `nonlatin_0014`'s masthead and footer rules, which are as
  wide as its table's rows; a border lies within one row pitch of the
  table's box (0.012, 0.011, 0.005 against pitches 0.051, 0.036, 0.021).
- **A `div`, not an `<hr>`, and no height of its own.** Drawn as `<hr>` with
  a margin, every moved page grew ~29px and `hard_breaks` rose on all eleven
  — `projection` counts an `<hr>` as a forced break, where the sources
  mostly draw these rules as borders. As shipped, heights move 1-4px and
  `hard_breaks` does not move.

Fields that moved besides height: T5 `output_texture` on all eleven, and
`output_ink` on `catalogue_0015` and `sample_css_0004`, whose `ink_delta`
falls (closer) 0.439 → 0.376 and 0.341 → 0.318 — a modal shift in the ink
sample, the rule now among the inks. The rules are drawn light
(`var(--rule)`) where some sources draw them dark; that is a remaining
difference, not measured here.

**A stage-position fault, found before the sweep and fixed in its own
commit.** As first committed, `separators` ran inside `_read_structure`,
during layout — before any Zone has a Kind, so the table-border test saw
none and a Conversion drew `sample_table_0003`'s and `report_0011`'s table
borders. `rederive.py` works on finished IRs and could not see it; replaying
the floor's answers through today's code beside it did (10 of 15 agreeing
where 12 should). It now runs in `Conversion._find_separators`, after
`_measure_type`; replay and rederive agree on 12 of 15, the three that
differ being the three whose crops moved; a test converts
`sample_table_0003` with the detector's placeholder Kinds and fails without
the move. The first sweep was stopped minutes in and restarted.

**Step C's correction is confirmed**, Alessandro, 2026-10-11 ("go as
recommended"): five sections for the form, and the drawn-field predicate.

### Step E — one sweep, all fifteen

```
FIXTURE=sweep tools/iterate.sh S4-sweep            # about 1½ h; say so before starting
python -m doc_to_html.report debug/runs/S4-sweep --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s3-result/scores.json
python tools/visual_review.py debug/runs/S4-sweep --previous debug/runs/S3-base
```

`S3-base` is step 0's rederive proof: the frozen floor as a run directory,
which is what `--previous` reads. If it has been cleared, re-make it from a
`git worktree` at the step-0 commit. Rederive renders with whatever code is
checked out, so at the current commit it would already carry steps A and D.

**Predicted:**

- Documents that move: `nonlatin_0014` (A), `darkdeck_0009` (B), `form_0007`
  and `menu_0012` (C). `receipt_0010` (D) no longer: 4a was dropped.
- Everything else is byte-identical at `temperature: 0`, because no crop of
  theirs moves.
- 4b shipped, so the eleven pages with a drawn separator move too, in the
  render only: `catalogue_0015`, `darkdeck_0009`, `form_0007`,
  `invoice_0002`, `menu_0012`, `newsletter_0008`, `nonlatin_0014`,
  `report_0011`, `sample_css_0004`, `sample_semantic_0005`,
  `statement_0006`. Every embedded IR gains a `separators` key.

**Final gate:**

1. The ratchet against `s3-result/` holds on every leg of every document. A
   fall is reported with its cause and goes to Alessandro, as spec 0008's
   did.
2. Each step's sweep-checked clause (B4, C5) holds in the picture. D1 went
   with 4a.
3. Every document not predicted to move is byte-identical. If one moved,
   explain it before anything else.
4. All fifteen sheets were opened, pairwise against `S3-base`, in this
   session.

**After the sweep:** write the outcome into this spec, in §7's format. Rewrite
`docs/status.md`. Leave a handover prompt at the end of this file. Whether
`S4-sweep` becomes the next floor is Alessandro's decision.

---

## 6. Rules that bind

- **The floor is `tests/frozen/s3-result/`** once step 0 lands. Always score
  with `--documents sweep`.
- **Never cite a past run.** Take the measurement in this session. The S3
  numbers above are quoted from what becomes the frozen floor, and are re-read
  from it.
- **Any reviewed run covers all fifteen documents.** Visual judgement is
  pairwise and made in the same session.
- **Look at the pictures**, not only the numbers. Every gate clause about a
  page is checked in its picture.
- **Measure offline before spending the sweep:** replay for A, the layout
  front for B and C, rederive for D. The sweep is spent once, at E.
- **Do not reopen** anything in `docs/status.md`'s "Closed, with evidence"
  without a new kind of evidence. #3's evidence is new: the detector's
  suppressed proposals were never examined for these two documents.

---

## 7. How to report the outcome

Alessandro asked for this format. Use it for each step's gate report and for
the sweep's outcome. Use compact tables, one line per cell, and name the
conversion stage each fault belongs to.

1. **Gate.** Table: `# | clause | result`, with the number or picture that
   decides each clause.
2. **Where it gained.** Table: `document | gain`, with one bold word, one
   line, and the number that moved.
3. **Remaining faults, by conversion stage.** Table: `document | what's wrong
   | stage | evidence`.
4. **Directions, ranked by gain for cost.** Table: `# | stage | change | why
   | cost / how measured`, plus one line of "not worth more effort".
5. **Decision for Alessandro**, if any, then a one- or two-line
   **recommendation**.

Lead with what the pages look like, then the numbers.

---

## Handover prompt

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0009-four-repairs-one-sweep.md — the only open work. It carries
spec 0008's changes, the S3-sweep analysis, and the plan with every gate.

In one line: S3-sweep becomes the floor, then four small repairs, each
reusing something already built, then one sweep measures them together.

Order: step 0 freeze S3-sweep as tests/frozen/s3-result/ (first check
debug/runs/S3-sweep still exists; if not, say so before anything else);
A wire row nets (nonlatin_0014), offline; B cut at a grid's inner splits
(darkdeck_0009); C the detector's own sections (form_0007, menu_0012);
D the photographed page at its paper's width (receipt_0010), with drawn
separators as one optional attempt; E one sweep, S4-sweep, about 1½ hours.

The gates are in the spec. Do not re-propose them. After each step, report
against its gate in the spec's §7 format and carry on. If a gate fails, stop
and ask. Measure offline before the sweep: replay for A, the layout front
for B and C, rederive for D. Commit each step on its own.

Open a tracking issue for spec 0009 with gh first, as each spec has one.
The menu's richer layout spec stays deferred unless step C's stop rule fires.

The standing rules are CLAUDE.md's and the spec's §6. Never cite a past run;
take the measurement. Look at the pictures, not only the numbers.
```
