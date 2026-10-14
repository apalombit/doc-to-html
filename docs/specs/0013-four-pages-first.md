# Four pages first — the receipt, the certificate, pricing and the ticket — then two guards and one sweep

**Status: planned 2026-10-14, not started. Issue #36.** Seven repairs, each
traced to its cause at the baseline with its prediction written down,
then one full sweep, `S9-sweep`, over all twenty-one documents. The
handover prompt at the end is the one to start a session with.

Alessandro's decisions, 2026-10-14:

1. **`S8-sweep` is the baseline**, frozen as `tests/frozen/s8-result/`. Its
   README has the provenance and the three loops, each proved 21 of 21.
2. **Four pages first:** `receipt_0010`, `certificate_0021`,
   `pricing_0017` and `ticket_0020`, as he named them after reviewing
   `S8-sweep`:
   - **receipt:** "missing cost of items in table";
   - **pricing:** "messed up whole page layout with scattered sections
     instead of 3 cards";
   - **ticket:** "missing content and overall layout extraction
     complicated by oriented document";
   - **certificate:** "size of page vertical instead of horizontal …
     main line ordering not consistent … bottom 3 subcolumns rendered as
     one with mixed up text".

   Steps 1–5 are those four pages. Steps 6 and 7 are two smaller repairs
   from spec 0012's sweep, kept at a lower priority.
3. **Then one full sweep.** No sweep in between.
4. **Everything else is cleared.** This covers:
   - spec 0012 §7's list;
   - the faults on `S8-sweep`'s sheets that this spec does not name;
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
- **Say which bytes.** Step 5 bumps `RECTIFIER_VERSION`, which changes one
  field in every document's embedded IR. From then on, "byte-identical"
  means identical except that field, as at spec 0012 step U.

**The loops, all proved on `s8-result/` at `ba0c110`'s code:**

| loop | command | what it can measure |
|---|---|---|
| rederive | `tools/rederive.py tests/frozen/s8-result --label <L>` | every step downstream of the wire: looks, structure, render |
| replay | `tools/replay_run.py tests/frozen/s8-result --label <L>` | the wire and mapper too; marks a call whose prompt, picture or schema moved **ASKED DIFFERENTLY — not a measurement** |
| replay with a swap | `... --documents D --swap D:NN=<answer file>` | a call asked differently whose new question was **already asked somewhere**: serve that answer, and it is a measurement |
| layout front | `tools/layout_front.py <out> --documents sweep` | rectify, the detector and every model-free layout stage, no model |

Score a run against the baseline:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
```

**Where each step runs.** Steps 1, 2, 3, 6 and 7 are measured offline,
on the baseline's answers. Steps 4 and 5 change what the model is shown;
their pages are answered at the sweep. They come after the offline steps
of the four pages, so every offline step is measured one change apart.

---

## 1. The receipt — the column count only where the table draws its columns

**What the page shows.** At `s8-result/`, `receipt_0010` has lost all
eight item prices. The summary values sit in the middle of the page, not
at its right. This is not a table-layout fault; the table hint is the
cause. The same cause costs:
- `statement_0006` its readable header and its caption;
- `cv_0013` the year `2022`.

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
- otherwise the columns are counted as before step U:
  `table_grid(crop).columns`, the projection of `content_ink(crop)` with
  nothing cleared;
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
  pages byte-identical to the replay at spec 0012 step U. Take the same
  swap at step 0, before any change, and keep it: it needs only committed
  files, and its four pages are the ones expected. Opened that day beside
  the source, its receipt prints all eight prices at the right, with each
  modifier (`oat milk`, `extra butter`) indented under its item and the
  summary values at the right.
- **paper's 5 × 1 was never asked.** Its answer comes at the sweep.
- The other sixteen documents are byte-identical to `s8-result/`.

**Done when, on the sheets:** the receipt prints its eight prices; the
statement's header reads light on its dark band under its caption; cv
prints `2022`; no other page moved but paper's, and paper is judged at the
sweep.

### Outcome — step 1, 2026-10-14

**Step 0 proved the baseline** at `624b18f`: the replay `S9-0-replay`
21 of 21 byte-identical, 0 asked differently; the rederive `S9-0-base` 21
of 21 files byte-identical. The swap at that code, `S9-0-swap`, moved the
receipt, the statement and cv, and left nonlatin byte-identical.

**The prediction held.** The replay `S9-1-replay` marks exactly the five
calls, each `prompt` only. The four prompts hash equal to `s7-result/`'s,
picture and schema too; paper's new prompt is the same text as cv's
(5 × 1), never asked of its picture. `S9-1` — the replay with the four
`s7-result/` answers swapped in — renders the four pages byte-identical to
`S9-0-swap`, and the other seventeen byte-identical to `s8-result/`.

**By eye, against `S9-0-replay`:**
- **receipt — better:** all eight prices at the right, `oat milk` and
  `extra butter` indented under their items, the summary values at the
  right.
- **statement — better:** `Transactions in date order` back over the
  table, the header row white on its dark band, and the paid-out column no
  longer a row out from 12 Aug.
- **cv — better:** `2022` beside `Diploma, Timber Design`.
- every other page byte-identical; paper is judged at the sweep.

`vanished` 40 → 32: the receipt's six price tokens, `castleton`, `2022`
back; nothing left. `debug/runs/S9-1/report.html`.

---

## 2. The certificate — its width inside two frames

**What the page shows.** At `s8-result/`, `certificate_0021` is drawn
portrait where the page is landscape. Its text runs in a column about 360
px wide inside a 1000 px page, so every line wraps several times. The name
alone takes three lines.

**Cause, measured — the render, not the grouping.** The certificate
draws two frames: a 6 px double outer frame and a 1 px inner one, both in
its furniture.
- **The outer frame.** `render._page_frame` draws it as `.doc`'s border,
  padded from the frame **to the content** — the union of the Zones —
  `padding:44px 154px 39px 146px`. `render._measure` caps `.doc` at the
  content's width, `max-width:636px`.
- **The inner frame** is drawn inside `.doc` as a `frame` row
  (`render.py`, `_Row("frame", …)`). It is padded from itself **to the
  content** too — `padding:30px 137px 30px`.
- So the gap between the frames and the text is counted twice.
  636 − 2 × 137 − 2 leaves about 360 px for the text.

**The change.** Count the gap once. Either:
- pad `.doc` from the outer frame to the inner frame when one lies inside
  it;
- or widen `.doc` by the inner frame's padding and border.

Choose by which keeps both frames where the page draws them at the
source's width.

**Prediction:** rederive of `s8-result/` moves `certificate_0021` only.
- Measured 2026-10-14: it is the one page with a page frame
  (`furnish.anchor(document).page`), and the one with a large frame
  inside it.
- `darkdeck_0009` also draws a `frame` row but has no page frame, so it
  must stay byte-identical.
- The certificate comes out landscape, near the source's 1000 × 612, its
  body lines wrapping where the page wraps them.

**Done when:** the certificate is drawn landscape, both frames where the
page draws them, its paragraph on the page's three lines.

---

## 3. Pricing — three cards, not scattered sections

**What the page shows.** At `s8-result/`, `pricing_0017`:
- three lanes, but each card's parts sit in separate bands that run
  across the lanes. Team's price sits far below its name, and Starter's
  and Business's features start at different heights;
- Business's price `£29 / user / month` is drawn about three times body
  size on two lines;
- Team's price is drawn at body size, where the page sets each price's
  figure large and its unit small;
- Team's blue emphasised frame is not drawn;
- the Monthly / Annual toggle is drawn as a bulleted column with a stray
  `Sav`, where the page prints one pill-shaped switch on one line.

**Cause, measured** (`s8-result/`'s IR):
- **Parts in bands.** Region 2 (0.249–0.899) is a grid split at
  0.345 / 0.655. Its 17 Zones sit in bands 2–9, and each band holds parts
  of different cards — band 4 holds Starter's `3 projects`, Team's
  feature list and Business's `✓ Unlimited projects`. A Zone's `column`
  is its index within its band, not its card. The render lays out band by
  band, so a card is never one stack.
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
- **The toggle.**
  - Zone 1 is a `list` of three items, `Monthly`, `Annual` and `Sav`, all
    on one printed line (tops 0.185–0.188). It is drawn as a bulleted
    column, though the page prints no bullet.
  - `Annual` has its dark pill (a furniture fill, drawn as a chip).
  - `Sav` is the cut start of Zone 2's `Save 20% with annual billing`,
    located at 0.499, inside Zone 2's box and outside its own Zone's
    (0.341–0.488).

**The change, in four parts, each measured by rederive:**
- **3a.** In a grid region of copies, assign each Zone to the lane its box
  falls in by the region's splits, not by its band's column index. Draw
  each lane as one stack — its Zones in reading order — inside the frame
  the page draws around them.
- **3b.** Find Team's frame.
- **3c.** A line set in two sizes:
  - either a size per Run, an IR field written in `looks`;
  - or the line's size taken from its longer part.

  Measure both on pricing, and on any other page whose price lines carry
  a unit, before choosing.
- **3d.** The toggle:
  - list items the page prints side by side on one line, with no marker
    printed, are drawn on one line without markers;
  - a Cell located inside another Zone's box, whose text starts that
    Zone's line, is a cut-off copy and goes. Its words are printed by the
    Zone it belongs to, so no word can vanish.

  Name every page each rule touches from the IR before measuring.

**Prediction:** pricing moves, and any page the IR names for 3a or 3d.
Every other page is byte-identical.

**Done when:** pricing draws three cards, each one framed stack in the
page's order, Team's frame blue; each price's figure large and its unit
small; the toggle one line with `Annual` in its pill; no page worse.

---

## 4. The certificate — its groups on the unwarped page

**What the page shows.** At `s8-result/`, `certificate_0021`:
- the two signatures, the seal and the certificate number are one
  orange-boxed paragraph, their lines interleaved: `S. Okonkwo Dr Samuel
  Okonkwo DIRECTOR OF STUDIES GUILD GTE 2026 H. Brandt …`;
- the name `Eleanor Ashworth-Reyes` is drawn as the body's heading, at
  twice its size, where the page sets it as its own line of script;
- a stray ornament is drawn between the stars and `This is to certify
  that`.

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
- give the name its own Zone, the signature row its three Zones plus the
  number, and the ornament to the title's Zone;
- not move any other document's Zones.

**Prediction:**
- The layout front over all 21 moves the certificate's Zones only. Every
  other document's Zones are identical to `s8-result/`'s IR, band, column
  and box.
- The replay marks the certificate ASKED DIFFERENTLY or ASKED MORE THAN
  THE RUN, and nothing else.
- **The certificate's answers come at the sweep.**

**Done when:** the layout front shows the groups the page prints; the
pages are judged at the sweep.

---

## 5. The ticket — the paper's whole outline

**What the page shows.** At `s8-result/`, `ticket_0020`:
- `BOARDING PASS` reads `BOARDING FOUR`;
- the stub's own `NORDLYS AIR` header is missing;
- the main header is a cut-down band.

**Cause, measured — the outline, not the alignment.** `rectify` already
aligns a photographed page: it finds the paper's quadrilateral
(`preprocess.find_page_quad`), warps it flat, and levels the text
(`deskew`). The warp levels the ticket's text well. **The quadrilateral
is wrong:**
- `find_page_quad` takes the largest convex four-cornered contour of Canny
  edges on a **greyscale** copy. In grey, the ticket's teal header is 84
  and the slate desk 64, a weak edge; the white body against the teal is
  strong.
- So the found top edge runs from the header's top-left corner (53, 53)
  to the bottom of the stub's header at the right (848, 69). It slopes
  the opposite way to the ticket.
- The warp then shears the page and cuts `BOARDING PASS` through its
  middle. The model read the lower half as `FOUR`.
- It also drops the stub's header, and clips the first letters of the
  left margin (`ASSENGER`, `LIGHT`, `ATE`), the stub's right edge
  (`SEAT 12A`) and `departure` at the foot.

**Measured, 2026-10-14:**
- **Each edge of the found quadrilateral, against the desk's colour.**
  4 px outside each edge, sampled along its length, the share of pixels
  further than `SHEET_APART` from the surround:

  | page | top | right | bottom | left |
  |---|---|---|---|---|
  | `receipt_0010` | 0.00 | 0.00 | 0.00 | 0.00 |
  | `ticket_0020` | **0.86** | 0.20 | 0.34 | 0.33 |

  The receipt's every edge has the desk beyond it. The ticket's top edge
  has sheet beyond it on 86% of its length.
- **The outline by colour.**
  - Prototype: everything further than `SHEET_APART` from the surround,
    closed, its largest component, the hull, four corners.
  - It gives the ticket (54, 57), (845, 45), (845, 341), (54, 353). That
    is the whole teal header and the stub's header, at the ticket's true
    slope; drawn on the picture, it follows the outline.
  - On the receipt it gives a quad within 2 px of today's.

**The change.** In `rectify`, an edge of the found quadrilateral with the
sheet's colour beyond it is not the paper's edge. There, take the
quadrilateral from the colour silhouette instead. A quadrilateral every
edge of which has the desk beyond it is kept exactly as found, so the
receipt's pixels do not move. Pick the threshold from the gap measured
above, 0.00 against 0.20 and more. Bump `RECTIFIER_VERSION`.
**Orientation is out of scope:** telling 90° from 270° means reading the
text (`rectify`'s docstring).

**Prediction:**
- The layout front over all 21 moves the ticket's Zones only. The
  receipt's rectified pixels are byte-identical, and so are every other
  page's.
- Every IR differs in `rectifier_version` alone, except the ticket.
- The replay marks the ticket ASKED DIFFERENTLY or ASKED MORE THAN THE
  RUN, and nothing else.
- **Its answers come at the sweep.** Expected there:
  - the header whole, so `BOARDING PASS` is read from a whole line;
  - the stub's `NORDLYS AIR`;
  - the margins' first letters, `SEAT 12A` and `departure`.

**Done when:** the layout front's rectified ticket holds its whole outline
— headers, margins, foot — and no other page moved. The page is judged at
the sweep. Whatever is still missing there, such as the stub's block
code, is reported and is not built in this spec.

---

## 6. Lower priority — a table row that spells its Zone's Title goes

**What the page shows.** `paper_0018` prints `Table I. Site summary` twice:
once as the table's caption, and again as a bold row under the table.

**Cause, measured.** The Zone's Title is `TABLE I. SITE SUMMARY`. The
model, told 5 rows, returned the four the page has, plus
`['Table I. Site summary', '', '', '']` with role `header`. Across all 21
documents of `s8-result/`, **this is the only table row whose non-empty
cells together spell their Zone's Title** under `wire._spell`. Step 1
changes paper's table prompt, so the row may not come back at the sweep.
The net is the general case.

**The change.** A wire-level net beside `_without_repeated_header` drops
such a row. It goes in `wire.py`, applied with the Title rules
(`_without_title_echo`, `_title_is_its_header_cell`), and in
`tools/rederive.py`. The Title still prints every word, so no word can
vanish. It does not touch `_title_is_its_header_cell`: there the Title is
dropped and the row kept, because the row carries the table's other
headers.

**Prediction:** rederive and replay of `s8-result/` move `paper_0018`
only.

**Done when:** at `s8-result/`'s answers, paper prints its caption once.

---

## 7. Lower priority — type on a drawn fill keeps its colour

**What the page shows.** At `s8-result/`, `statement_0006`'s transaction
header row is invisible: dark type on a dark band. Step 1 removes this
page's trigger; this step is the general case.

**Cause, measured.**
- The band is a furniture fill, `(22, 32, 43)`, drawn by the renderer
  since spec 0012 G3a.
- The six header Cells have `look.color = None`, so they take the page's
  ink, which is also `(22, 32, 43)`.
- `looks.read` measured their white and then dropped it. It keeps a Cell's
  colour only where the ground under the Cell matches `_drawn_ground`, the
  ground the render draws there. `_drawn_ground` knows the Zone's
  `header_fill` and `fill`, not the furniture.

Across `s8-result/`, **the statement's six header Cells are the only
non-empty Cells lying on a furniture fill and drawn within 60 of its
colour**.

**The change.** `_drawn_ground` also returns a furniture fill the render
draws under the Cell, so a colour measured on that fill is kept.

**Prediction:** rederive of `s8-result/` moves `statement_0006` only.

**Done when:** at `s8-result/`'s answers, the statement's header is
readable, light on its band.

---

## 8. Work plan

| step | page | what | runs on | done when |
|---|---|---|---|---|
| 0 | — | prove the baseline; take step 1's swap and keep it | replay, rederive | 21 of 21 byte-identical each, 0 asked differently |
| 1 | **receipt** (statement, cv) | the column count only where ruled | replay with swaps | §1's five calls marked, no other; four prompts equal to `s7-result/`'s; the four pages as step 0's swap |
| 2 | **certificate** | its width inside two frames | rederive | certificate only moves; drawn landscape |
| 3 | **pricing** | 3a lanes as framed stacks, 3b Team's frame, 3c two sizes, 3d the toggle | rederive | pricing three cards; only the pages named from the IR move |
| 4 | **certificate** | its groups on the unwarped page | layout front, replay | the certificate's Zones only move |
| 5 | **ticket** | the paper's whole outline | layout front, replay | the ticket's outline whole; every other page's pixels unchanged |
| 6 | paper | the caption row at the wire | replay, rederive | paper only moves |
| 7 | statement | type on a drawn fill keeps its colour | rederive | statement only moves |
| P | — | register §9's prediction in this spec | replay at the last commit | the list of calls asked differently written down before the sweep |
| S | — | **`S9-sweep`**: all 21, shipped defaults, started detached | the model | §9 checked; all 21 sheets opened against `S9-0-replay`; the outcome written in the error-analysis format, the four pages first |

**What the final review compares.** Build the baseline in run layout once:

```
tools/replay_run.py tests/frozen/s8-result --label S9-0-replay
```

Then compare with:

```
tools/visual_review.py debug/runs/S9-sweep --previous debug/runs/S9-0-replay
```

---

## 9. The sweep's prediction — to register at step P

Write it from the replay at the last commit. It will have this form:

- **Every call the replay does not mark comes back byte-identical** to
  `s8-result/answers/`. A miss names a change that moved something it was
  not meant to.
- **The calls it marks are only:**
  - the five table calls of step 1;
  - the certificate's, from step 4;
  - the ticket's, from step 5.
- **The four table answers of step 1 come back byte-identical to
  `s7-result/`'s.** Their prompts and pictures equal `s7-result/`'s, so at
  `temperature: 0` the model gives the answer it gave then. A miss here
  says the hash check was wrong.
- **Every unmarked document renders byte-identical** to the replay at the
  last commit, its embedded IR included.

Then report the sweep in the error-analysis format:
1. the four pages first, each against Alessandro's note on it;
2. then the six held-out pages in their own lines;
3. where it gained;
4. the faults left, by stage;
5. the directions, ranked;
6. a recommendation.

Whether `S9-sweep` becomes the baseline is Alessandro's decision.

---

## 10. Where things are

| what | where |
|---|---|
| the grid count, ruled rows and columns | `preprocess.table_grid`, `_rows_as_ruled`, `_columns_as_ruled`; the drawing `furniture.drawn` → `preprocess.Drawn`; measured in `orchestrator._grid`; stated in `engines/ollama.with_grid` |
| the page's width and frames | `render._measure`, `render._page_frame`; the inner frame's `_Row("frame", …)`; `furnish.anchor` |
| grid regions, lanes, splits | `structure._grids`, `EMPHASIS`; the render's `_grid`, `_columns`, `_lane`, `_lane_fill` |
| furniture: rules, frames, fills | `furniture.find`, `_frames`, `_fills`; drawn by the render |
| a Cell's look, size and colour | `looks.read` (the loop over `cells_of(zone)`), `_drawn_ground`, `_ink`; `render._look` |
| the snap and its refusal | `orchestrator` (`DTH_SNAP_ZONES`, "made the Bands invalid") |
| the paper's outline | `preprocess.rectify`, `find_page_quad`, `surround_of`, `SHEET_APART`, `warp_to_quad`; `ir.RECTIFIER_VERSION` |
| the wire's row nets and Title rules | `wire._without_repeated_header` and the other four row nets; `_without_title_echo`, `_title_is_its_header_cell`, `_title_starts_its_block`, `_spell` |
| the loops | `tools/rederive.py`, `tools/replay_run.py`, `tools/layout_front.py`, `tools/visual_review.py` |

**A Zone printer is worth writing first**, in a scratch script. Load each
document's IR from `<script id="doc-ir">` with `ir.Document.from_json`,
and print each Zone's index, kind, band and column, box, Title and first
line. Every cause above was found with one.

**The run directory's `01_layout_input.png` and `02_model_boxes.png` show
the original picture, not the rectified one.** On the ticket the boxes
look misplaced because of that. To see what the detector saw, draw the
Zones on `rectify(path).image` yourself. Its channels are BGR.

---

## 11. Rules that bind

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
  and the five wire row nets. Steps 3d and 6 add nets that drop only
  words printed elsewhere on the page.
- Leave `debug/runs/84-rule-not-a-line/` intact. Never score against
  `tests/documents/SAMPLE_DOCUMENTS`.

---

## Handover prompt — implement spec 0013, four pages first, then one sweep (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0013-four-pages-first.md end to end — the only open work,
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
Then take step 1's swap (spec §1) and keep it as its target.

Alessandro's priority is four pages: receipt_0010, certificate_0021,
pricing_0017, ticket_0020. Each cause is measured in the spec. The steps,
in order:
1 receipt — the table's column count only where the table draws its
  columns; measured by replay with s7-result's four table answers swapped
  in, once their prompts hash equal to s7-result's (also statement, cv);
2 certificate — its width inside two frames: the frame-to-text gap is
  counted twice (render._page_frame and the inner frame), so the page is
  drawn portrait;
3 pricing — three cards: lanes by the region's splits drawn as framed
  stacks, Team's frame, a price line in two sizes, the toggle on one line;
4 certificate — its groups on the unwarped page: trace the layout front
  stage by stage first;
5 ticket — the paper's whole outline in rectify: an edge with the sheet
  beyond it is not the paper's edge, take the colour silhouette there;
  the receipt's pixels must not move;
6 and 7, lower priority — paper's caption row at the wire; type on a
  drawn fill keeps its colour (statement).

Judge every step by eye: sheets for all 21 against the previous step's
run, each moved page better / same / worse with a sentence; the six
held-out pages in their own lines; scores recorded, never argued from;
vanished read as a pointer. Each step its own commit; every new
IR-writing step added to tools/rederive.py. Report each step with what
the pages look like and the report.html path; continue unless a page got
worse, then stop, show it, ask.

Then register §9's prediction in the spec, and run ONE sweep, S9-sweep,
over all 21: about 2h15m, started detached (docs/status.md's loop has
the line). Do not touch tools/iterate.sh while it runs. Check the
prediction, open all 21 sheets against S9-0-replay, and report in the
error-analysis format: the four pages first, each against Alessandro's
note on it, then the six held-out pages in their own lines. Whether
S9-sweep becomes the baseline is Alessandro's decision. The standing
rules are CLAUDE.md's and the spec's §11.
```
