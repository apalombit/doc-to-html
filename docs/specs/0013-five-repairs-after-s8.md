# Five repairs after `S8-sweep` — the column count, the caption row, ink on a fill, the certificate's groups, pricing's cards

**Status: planned 2026-10-14, not started. Issue #36.** Five repairs, each
traced to its cause at the baseline, then one full sweep, `S9-sweep`, over
all twenty-one documents. The handover prompt at the end is the one to
start a session with.

Alessandro's decisions, 2026-10-14:

1. **`S8-sweep` is the baseline**, frozen as `tests/frozen/s8-result/`. Its
   README has the provenance and the three loops, each proved 21 of 21.
2. **Implement directions 1–5 of spec 0012's "Outcome — the sweep", then
   one full sweep.** No sweep in between.
3. **Everything else is cleared.** This covers:
   - spec 0012 §7's list;
   - the faults on `S8-sweep`'s sheets that 1–5 do not name;
   - every earlier queue and idea.

   This spec is the only open work. Do not pick up anything else unless
   Alessandro names it.

---

## How to work

- **By eye.** Every step ends with sheets for all twenty-one documents
  against the step before. Open every sheet whose render moved, and judge
  each page better / same / worse with a sentence naming the element. That
  judgement is the gate.

  ```
  tools/visual_review.py <run> --previous <previous step's run>
  ```
- **Scores are recorded, never gating, never argued from.** The one number
  read is the report's `vanished` list: a pointer to a page to open.
- **The six held-out pages** (`corpus.NEW`: letter, pricing, paper,
  timetable, ticket, certificate) are reported in their own lines. A
  change that helps the fifteen and breaks one of the six is tuned, not
  general; say so.
- **Each step is its own commit.** Every new step that writes the IR goes
  into `tools/rederive.py`.
- **Report each step** with what the pages look like and the `report.html`
  path. Continue unless a page got worse; then stop, show it, ask.
- **Each step names its prediction before it is measured**: which pages
  move, and that every other page is byte-identical. The predictions below
  come from measurements taken on 2026-10-14 against `s8-result/`.

**The loops, all proved on `s8-result/` at `ba0c110`'s code:**

| loop | command | what it can measure |
|---|---|---|
| rederive | `tools/rederive.py tests/frozen/s8-result --label <L>` | every step downstream of the wire: looks, structure, render |
| replay | `tools/replay_run.py tests/frozen/s8-result --label <L>` | the wire and mapper too; marks a call whose prompt, picture or schema moved **ASKED DIFFERENTLY — not a measurement** |
| replay with a swap | `... --documents D --swap D:NN=<answer file>` | a call asked differently whose new question was **already asked somewhere**: serve that answer, and it is a measurement |
| layout front | `tools/layout_front.py <out> --documents sweep` | the detector and every model-free layout stage, no model |

Score a run against the baseline:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
```

---

## 1. The column count only where the table draws its columns

**What the pages show.** At `s8-result/`:
- `receipt_0010` has lost all eight item prices;
- `statement_0006`'s header row cannot be read, and its caption has gone;
- `cv_0013` has lost `2022`.

**Cause, measured.** Spec 0012 step U counted each table's grid with the
page's drawing known (`preprocess.table_grid(crop, drawn)`), and the count
is stated in the Extractor's prompt (`engines/ollama.with_grid`).
Measured on every table Zone of `s8-result/` (2026-10-14):

| table | before step U | at `s8-result/` | vertical rules drawn | the page | the answer |
|---|---|---|---|---|---|
| `timetable_0019` | 4 × 1 | 9 × 6 | **7** | 6 columns | every row back |
| `nonlatin_0014` | 10 × 1 | 10 × 4 | 0 | 4 | page unchanged |
| `statement_0006` | 43 × 1 | 43 × 5 | 0 | 6 | caption folded into a 7-cell header |
| `receipt_0010` | 18 × 1 | 18 × 2 | 0 | 3 | price column dropped |
| `cv_0013` | 5 × 1 | 5 × 3 | 0 | 4 | `2022` dropped |
| `paper_0018` | 1 × 1 | 5 × 3 | 1 | 4, under a caption | caption printed again as a row |
| `ticket_0020` | 9 × 2 | 8 × 2 | 1 | — | as before |

- **Only the timetable's columns come from rules the page draws**
  (`_columns_as_ruled`, two rule places or more).
- The other five moved because the projection was taken with the rules
  cleared and the dark fill left out. Four of those undercount the page,
  and the model obeyed each count by dropping or merging a column.
- At 1 column, the old count was so wrong that the model ignored it and
  read every column.
- **A near count is obeyed; an absurd one is not.**

The table calls in question differ from `s7-result/`'s **in the prompt
only**: the picture and schema hashes are equal.

**The change.** In `preprocess.table_grid` with `drawn`:
- columns come from the rules only where the table draws two vertical
  rules or more;
- otherwise the columns are counted as before step U: the projection of
  `content_ink(crop)` with nothing cleared, `table_grid(crop).columns`;
- rows keep step U's count.

**Prediction:**

- The replay of `s8-result/` marks **exactly five calls** ASKED
  DIFFERENTLY. Every other call is unmarked.

  | document | call | prompt becomes |
  |---|---|---|
  | `receipt_0010` | `10_table` | 18 × 1 |
  | `statement_0006` | `14_table` | 43 × 1 |
  | `cv_0013` | `79_table` | 5 × 1 |
  | `nonlatin_0014` | `20_table` | 10 × 1 |
  | `paper_0018` | `34_table` | 5 × 1 |

- **The first four prompts hash equal to `s7-result/`'s** recorded
  `asked.prompt` for the same call. Check this, call by call. Where it
  holds, `s7-result/`'s answer is the model's answer to today's question
  at `temperature: 0`. Serving it with `--swap` is then a measurement:

  ```
  # each <file> holds s7-result/answers/<doc>.json calls[NN]["answer"]
  tools/replay_run.py tests/frozen/s8-result --label <L> \
      --documents receipt_0010,statement_0006,cv_0013,nonlatin_0014 \
      --swap receipt_0010:10=<file> --swap statement_0006:14=<file> \
      --swap cv_0013:79=<file> --swap nonlatin_0014:20=<file>
  ```

  **Checked 2026-10-14:** that swap at `ba0c110`'s code renders all four
  pages byte-identical to the replay at step U (`S8-U-replay`). Take the
  same swap at step 0, before any change, and keep it: it needs only
  committed files, and its four pages are the ones expected:
  - the receipt with its prices;
  - the statement with its header light on its band and its caption back;
  - cv with `2022`.
- **paper's 5 × 1 was never asked.** Its answer comes at the sweep.
- The other sixteen documents are byte-identical to `s8-result/`.

**Done when, on the sheets:** the receipt prints its eight prices; the
statement's header reads light on its dark band under its caption; cv
prints `2022`; no other page moved but paper's, and paper is judged at the
sweep.

---

## 2. A table row that spells its Zone's Title goes

**What the page shows.** `paper_0018` prints `Table I. Site summary` twice:
once as the table's caption, and again as a bold row under the table.

**Cause, measured.** The Zone's Title is `TABLE I. SITE SUMMARY`. The
model, told 5 rows, returned the four the page has, plus
`['Table I. Site summary', '', '', '']` with role `header`. Across all 21
documents of `s8-result/`, **this is the only table row whose non-empty
cells together spell their Zone's Title** under `wire._spell`.

**The change.** A wire-level net beside `_without_repeated_header` drops
such a row. It goes in `wire.py`, applied with the Title rules
(`_without_title_echo`, `_title_is_its_header_cell`), and in
`tools/rederive.py`. The Title still prints every word, so no word can
vanish, which puts the repair on the side where being wrong costs
nothing. It does not touch `_title_is_its_header_cell`: there the Title is
dropped and the row kept, because the row carries the table's other
headers.

**Prediction:** rederive and replay of `s8-result/` move `paper_0018`
only; the other twenty are byte-identical.

**Done when:** paper prints its caption once, and its table holds its
header and three rows.

---

## 3. Type on a drawn fill keeps its own colour

**What the page shows.** At `s8-result/`, `statement_0006`'s transaction
header row is invisible: dark type on a dark band.

**Cause, measured.**
- The band is a furniture fill, `(22, 32, 43)`, drawn by the renderer
  since spec 0012 G3a.
- The six header Cells have `look.color = None`, so they take the page's
  ink, which is also `(22, 32, 43)`.
- `looks.read` measured their white and then dropped it. It keeps a Cell's
  colour only where the ground under the Cell matches `_drawn_ground`, the
  ground the render draws there. `_drawn_ground` knows the Zone's
  `header_fill` and `fill`, not the furniture. This Zone has no
  `header_fill`, because the answer's header row is the folded 7-cell one.

Across `s8-result/`, **the statement's six header Cells are the only
non-empty Cells lying on a furniture fill and drawn within 60 of its
colour**.

**The change.** `_drawn_ground` also returns a furniture fill the render
draws under the Cell, so a colour measured on that fill is kept. That is
the root. A guard at the render is optional; if built, keep it narrow:
never set text in its own ground's colour.

**Prediction:** rederive of `s8-result/` moves `statement_0006` only. Its
header reads light on the band; every other page is byte-identical. After
step 1 the statement's answer is `s7-result/`'s, and its header is light
already. This step still stands, as the general case.

**Done when:** at `s8-result/`'s answers, the statement's header is
readable, and no other page moved.

---

## 4. The certificate's groups on the unwarped page

**What the page shows.** At `s8-result/`, `certificate_0021`:
- the two signatures, the seal and the certificate number are drawn as one
  orange-boxed paragraph;
- the name `Eleanor Ashworth-Reyes` is a bold heading at twice its size,
  on three lines, where the page sets it on one line of script;
- the page is drawn tall and narrow, its content in about half the frame's
  width.

The frames, serif and dark ink it gained in spec 0012 stay.

**Cause, measured.** The layout front gives **7 Zones**, with no model
(`tools/layout_front.py`, 2026-10-14). The detector's grouping changed
once the page stopped being warped (spec 0012 step U):

| | `s7-result/` (warped) | `s8-result/` (unwarped) |
|---|---|---|
| Zones | 9 | 7 |
| the name | its own Zone | the Title of the body paragraph's Zone (0.186–0.814 × 0.366–0.582) |
| signatures, seal, number | three Zones in one band, the number a fourth | one figure Zone, 0.178–0.806 × 0.658–0.884 |
| an ornament | in the title's Zone | also a Zone of its own, 0.489–0.500 × 0.260–0.278, inside the title Zone's span |

The snap is refused on this page:

```
snapping the layout boxes to the ink made the Bands invalid (band 1: Zones
in columns 0 and 1 overlap horizontally (0.28-0.72 and 0.49-0.50) ...)
```

Every box on the page is therefore left as the detector returned it,
unsnapped. That stray ornament Zone is the first lead. **Trace stage by
stage before changing anything**: find which stage merges the signature
row and the name.

**The change.** Whatever the trace shows. It must:
- give the name its own Zone, and the signature row its three Zones plus
  the number;
- not move any other document's Zones.

**Prediction:**
- The layout front over all 21 moves the certificate's Zones only. Every
  other document's Zones are identical to `s8-result/`'s IR, band, column
  and box.
- The replay marks the certificate ASKED DIFFERENTLY or ASKED MORE THAN
  THE RUN, and nothing else.
- **The certificate's answers come at the sweep.** Trace the tall, narrow
  drawing once the Zones are right; it may follow from the grouping.

**Done when:** the layout front shows the groups the page prints; the
pages are judged at the sweep.

---

## 5. Pricing's cards as cards

**What the page shows.** At `s8-result/`, `pricing_0017`:
- three lanes, but each card's parts sit in separate bands that run
  across the lanes. Team's price sits far below its name, and Starter's
  and Business's features start at different heights;
- Business's price `£29 / user / month` is drawn about three times body
  size on two lines;
- Team's price is drawn at body size, where the page sets each price's
  figure large and its unit small;
- Team's blue emphasised frame is not drawn.

**Cause, measured** (`s8-result/`'s IR):
- **Parts in bands.** Region 2 (0.249–0.899) is a grid split at
  0.345 / 0.655. Its 17 Zones sit in bands 2–9, and each band holds parts
  of different cards — band 4 holds Starter's `3 projects`, Team's
  feature list and Business's `✓ Unlimited projects`. The render lays out
  band by band, so a card is never one stack.
- **Frames.** The furniture records Starter's and Business's frames
  (0.044–0.335 and 0.665–0.956 × 0.262–0.889) but **not Team's**. Its top
  edge is broken by the `MOST POPULAR` ribbon, which is a hypothesis to
  check. No Zone carries a `frame`.
- **Two sizes on one line.** A Look is one per Cell:
  - Business's line `£29 / user / month` is one Cell at size 3.33;
  - Team's `£12 / user / month` has no size;
  - Starter's `£0` is 3.33 on its own.
  
  `ir.Run` has `text` and `kind` only, so the IR cannot say "the figure
  large, the unit small".

**The change, in three parts, each measured by rederive:**
- **5a.** In a grid region of copies, draw each lane as one stack — its
  Zones in reading order — inside the frame the page draws around them.
- **5b.** Find Team's frame.
- **5c.** A line set in two sizes:
  - either a size per Run, an IR field written in `looks`;
  - or the line's size taken from its longer part.

  Measure both on pricing, and on any other page whose price lines carry
  a unit, before choosing.

**Prediction:** the steps move pricing, and any page whose grid region of
copies has lanes of several Zones. Name each such page from the IR before
measuring. Every other page is byte-identical.

**Done when:** pricing draws three cards, each one framed stack in the
page's order, Team's frame blue; each price's figure large and its unit
small; no page worse.

---

## 6. Work plan

| step | what | runs on | done when |
|---|---|---|---|
| 0 | prove the baseline: replay and rederive of `s8-result/` | replay, rederive | 21 of 21 byte-identical each, 0 asked differently |
| 1 | the column count only where ruled | replay with swaps | §1's five calls marked, no other; four prompts equal to `s7-result/`'s; the four pages byte-identical to a replay of `s8-result/` at the step-0 commit with the same four answers swapped in — committed inputs only |
| 2 | the caption row at the wire | replay, rederive | paper only moves |
| 3 | type on a drawn fill keeps its colour | rederive | statement only moves, at `s8-result/`'s answers |
| 4 | the certificate's groups | layout front, replay | the certificate's Zones only move |
| 5 | pricing's cards: 5a stacks, 5b Team's frame, 5c two sizes | rederive | pricing as a page of three cards, no page worse |
| P | register §7's prediction in this spec | replay at the last commit | the list of calls asked differently written down before the sweep |
| S | **`S9-sweep`**: all 21, shipped defaults, started detached | the model | §7 checked; all 21 sheets opened against `s8-result/`'s run layout; the outcome written in the error-analysis format |

**What the final review compares.** Build the baseline in run layout once:

```
tools/replay_run.py tests/frozen/s8-result --label S9-0-replay
```

Then compare with:

```
tools/visual_review.py debug/runs/S9-sweep --previous debug/runs/S9-0-replay
```

---

## 7. The sweep's prediction — to register at step P

Write it from the replay at the last commit. It will have this form:

- **Every call the replay does not mark comes back byte-identical** to
  `s8-result/answers/`. A miss names a change that moved something it was
  not meant to.
- **The calls it marks are only:**
  - the five table calls of step 1;
  - the certificate's, from step 4.
- **The four table answers of step 1 come back byte-identical to
  `s7-result/`'s.** Their prompts and pictures equal `s7-result/`'s, so at
  `temperature: 0` the model gives the answer it gave then. A miss here
  says the hash check was wrong.
- **Every unmarked document renders byte-identical** to the replay at the
  last commit.

Then report the sweep in the error-analysis format:
1. the pages first, with the six in their own lines;
2. where it gained;
3. the faults left, by stage;
4. the directions, ranked;
5. a recommendation.

Whether `S9-sweep` becomes the baseline is Alessandro's decision.

---

## 8. Where things are

| what | where |
|---|---|
| the grid count, ruled rows and columns | `preprocess.table_grid`, `_rows_as_ruled`, `_columns_as_ruled`; the drawing `furniture.drawn` → `preprocess.Drawn`; measured in `orchestrator._grid`; stated in `engines/ollama.with_grid` |
| the wire's row nets and Title rules | `wire._without_repeated_header` and the other four row nets; `_without_title_echo`, `_title_is_its_header_cell`, `_title_starts_its_block`, `_spell` |
| a Cell's colour, kept or dropped | `looks.read` (the loop over `cells_of(zone)`), `_drawn_ground`, `_ink` |
| furniture: rules, frames, fills | `furniture.find`, `_frames`, `_fills`; drawn by the render |
| the snap and its refusal | `orchestrator` (`DTH_SNAP_ZONES`, "made the Bands invalid") |
| grid regions, lanes, splits | `structure._grids`, `EMPHASIS`; the render's `_grid`, `_columns`, `_lane`, `_lane_fill` |
| a Cell's look in the render | `render._look` |
| the loops | `tools/rederive.py`, `tools/replay_run.py`, `tools/layout_front.py`, `tools/visual_review.py` |

A Zone printer is worth writing first, in a scratch script. Load each
document's IR from `<script id="doc-ir">` with `ir.Document.from_json`,
and print each Zone's index, kind, band and column, box, Title and first
line. Every cause above was found with one.

---

## 9. Rules that bind

- "How to work" above.
- **Never cite a past run.** Take every picture and number in the session
  that reports it. The committed frozen directories are the exception, for
  what their READMEs say they are.
- **Any reviewed run covers all twenty-one documents.**
- **Never edit `tools/iterate.sh`, or any script a running sweep reads.**
  `S8-sweep`'s script died after its bake-off that way.
- ADR 0001 (no document types) and ADR 0002/0005 (positions drive
  structure, never `position:absolute`) hold.
- **Marking may never change the words.** Keep the four shipped defaults
  and the five wire row nets. The net in step 2 is a sixth.
- Leave `debug/runs/84-rule-not-a-line/` intact. Never score against
  `tests/documents/SAMPLE_DOCUMENTS`.

---

## Handover prompt — implement spec 0013, then one sweep (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0013-five-repairs-after-s8.md end to end — the only open work,
issue #36. Everything not in it was cleared by Alessandro on 2026-10-14;
do not pick anything else up unless he names it.

The baseline is tests/frozen/s8-result/ (spec 0012's sweep, 21
documents, 725 answers, Alessandro's decision 2026-10-14). Prove it
before any change:
- tools/replay_run.py tests/frozen/s8-result --label S9-0-replay
  reproduces 21 of 21 byte-identical, 0 asked differently;
- tools/rederive.py tests/frozen/s8-result --label S9-0-base gives 21 of
  21 byte-identical files;
- the suite: 1114 passed, 1 skipped; mypy src clean.

Then the five steps, in order, each traced and predicted in the spec:
1 the column count only where the table draws its columns — measured by
  replay with s7-result's four table answers swapped in, once their
  prompts hash equal to s7-result's;
2 a table row spelling its Zone's Title goes, at the wire (paper);
3 type on a drawn fill keeps its colour (looks._drawn_ground; statement);
4 the certificate's groups on the unwarped page — trace the layout
  front stage by stage first;
5 pricing's cards as cards: lanes as stacks in their frames, Team's
  frame, a price line in two sizes.

Judge every step by eye: sheets for all 21 against the previous step's
run, each moved page better / same / worse with a sentence; the six
held-out pages in their own lines; scores recorded, never argued from;
vanished read as a pointer. Each step its own commit; every new
IR-writing step added to tools/rederive.py. Report each step with what
the pages look like and the report.html path; continue unless a page got
worse, then stop, show it, ask.

Then register §7's prediction in the spec, and run ONE sweep, S9-sweep,
over all 21: about 2h15m, started detached (docs/status.md's loop has
the line). Do not touch tools/iterate.sh while it runs. Check the
prediction, open all 21 sheets against S9-0-replay, and report in the
error-analysis format, leading with the pages, the six in their own
lines. Whether S9-sweep becomes the baseline is Alessandro's decision.
The standing rules are CLAUDE.md's and the spec's §9.
```
