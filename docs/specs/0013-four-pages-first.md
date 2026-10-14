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

### Outcome — step 2, 2026-10-14

**The first way:** `render._held` — what `.doc` holds inside a page frame
is the Zones and the frames drawn round them (`_shared`). `_page_frame`
pads to it and `_measure` sizes `.doc` to it: the certificate's `.doc` is
`padding:9px` and `max-width:918px`, the inner frame keeps its 137 px, and
the gap is counted once, by the inner frame. The second way would put the
same numbers in two places.

**The prediction held.** Rederive of `S9-1` → `S9-2`: the certificate
moved, the other twenty byte-identical.

**By eye, against `S9-1`:**
- **certificate — better:** landscape, both frames where the page draws
  them, the paragraph on three lines, the name on two where it took three.
  **One element worse:** band 1's title now stands left of centre on two
  lines with the ornament Zone (0.489–0.500) off to its right, where they
  were stacked and centred. It is step 4's stray ornament, given room to
  stand beside the title; step 4 gives it to the title's Zone.

`vanished` unchanged, 32. `debug/runs/S9-2/report.html`.

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

### Outcome — step 3, 2026-10-14

Four commits, each measured by rederive from the one before:
`S9-2` → `S9-3a` → `S9-3b` → `S9-3c` → `S9-3d`.

- **3a — a card is one framed stack.** `rhythm.frames` takes a lane of a
  one-row grid as a run, as a column's lane, so each card's Zones share
  its rectangle; the render draws such a grid lane by lane
  (`render._cards` → `_columns`, `_framed`). A frame is painted with the
  fill most of its Zones stand on (`_ground`); a Zone of another fill —
  Team's blue button — paints its own. Pricing alone moved.
- **3b — Team's frame.** The hypothesis held: the pill cut Team's top edge
  in two, x 363–443 and 557–637. `furniture._bridged` joins two pieces of
  one line where the page draws the line's colour across the gap, within
  `SAME` — tighter than any line stands off the ground. At `2 × SAME` the
  ground bridged Starter's and Business's faint bottom edges across Team's
  card; at `SAME` that gap holds 0.89 and the pill's 1.00. `furnish._frame`
  gives a frame holding exactly the Zones that share one box to that box,
  since the box takes in the ribbon and the shadow. Furniture over all 21:
  pricing gains the frame, and the timetable's column rule at x 0.452 is
  joined beside the blue `Mathematics` bar, as the page draws it — its
  drawn markup byte-identical.
- **3c — two sizes, measured both ways.** Only pricing has such lines
  (scanned over all 21; darkdeck's `4.8 bn` is one size). The line's size
  from its longer part draws every price at body size, no figure large, so
  **a size per part was chosen**, written on the Look rather than the Run
  — a Run belongs to the model's reading. `Look.sizes`: where the line
  changes size, by character. `looks._two_sizes` measures it; each part's
  glyphs must count like its letters, or a closing full stop is taken for
  a small part — it was, on twelve pages, until that check. The render
  cuts the runs there, and draws a line `TWO_SIZES` from its block's size
  at its own: Starter's `£0` beside its `/ month`. Within a block, noise
  stands at most 1.25 apart and the figure 3.0. **Team's price was never
  placed**: `type_lines` parted its line at the valleys of its own ink into
  three, so `_from_ink` counted three lines for one Cell. `locate._touching`
  takes lines with no blank row between them as one where they outnumber
  the Cells; over all 21 the next nearest two lines stand is three blank
  rows. **Say which bytes:** from 3c every Look carries `sizes`, null
  everywhere but pricing's two price lines.
- **3d — the toggle.** Rule 1 touched, from the IR: pricing's toggle and
  `sample_semantic_0005`'s `html, web, standards`, a body list printed on
  one line; its header nav is already drawn inline by the house style and
  is left to it. Rule 2 touched pricing's `Sav` only.
  `locate.without_cut_copies` runs after `locate`, in the Conversion and
  in `tools/rederive.py`.

**By eye, step by step:**
- **pricing — better at each part:** three cards, each one framed stack
  in the page's order, Team's price under its name (3a); Team's frame blue
  (3b); `£0`, `£12`, `£29` large and each unit small, the cards near one
  height (3c); `Monthly` and `Annual` in its pill on one line beside `Save
  20%`, `Sav` gone (3d). Still unlike the page, and not this step's: the
  buttons' outlines, the check marks drawn as bullets, Starter's and
  Business's centred type set left.
- **sample_semantic — better (3d):** `html web standards` on one line, as
  the page prints them, where it was a bulleted column.
- every other page byte-identical at each part, but for the null `sizes`
  from 3c and the timetable's embedded IR at 3b.

`vanished` unchanged, 32. `debug/runs/S9-3d/report.html`.

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

### Outcome — step 4, 2026-10-14

**The trace**, `detect_zones` replayed stage by stage on the rectified
page with the engine a Conversion builds. Three causes, each a knife edge:

- **The signature row — `outermost`.** A `key_value_region` at 0.40, the
  threshold itself, spans the row (0.123–0.871 × 0.656–0.843); inside it
  the two signature blocks at 0.60 and 0.50 and the seal, a `picture` at
  0.90. `outermost` keeps the container and drops the surer parts, and
  `attach_trailing_rows` then extends it over the number.
- **The name — `attach_headings`.** The name is a `section_header` 0.020
  below `This is to certify that` and 0.038 above the paragraph its
  sentence runs on into: **1.873**, under `HEADING_GAP_RATIO`'s 1.9, so it
  became that paragraph's Title.
- **The ornament — `without_enclosed`.** The title's union grew over one
  star; the middle star's foot stood **0.08 px** below that box, so it was
  not inside, was kept, overlapped the title, and `validate_bands` refused
  the snap for the whole page.

**The change**, all in `engines/detector.py`:
- `open_unsure_containers`, after `outermost`: a container of text whose
  outermost confident parts hold a `picture`, are each surer than it and
  carry `SPLIT_INK` of its ink is its parts. Without the picture condition
  it also opened `invoice_0002`'s pairs, `nonlatin_0014`'s totals line and
  darkdeck's and the ticket's pictures — measured, then narrowed.
- `HEADING_GAP_RATIO` 1.9 → **1.77**. Over all twenty-one, the true merges
  reach 1.664 (`letter_0016`'s signature over its name and title), the
  nearest leave is the certificate's 1.873, then `invoice_0002`'s 1.992.
  1.77 is their geometric middle.
- `without_enclosed` takes an edge within one pixel of the container's as
  on it, given the page's shape.

**The layout front over all 21** (`front-base` → `front-4`): the
certificate alone moves, 7 Zones to 8; the other twenty are identical in
band, column and box. The snap now applies to the certificate. Its Zones:
`GUILD OF TIMBER ENGINEERS`; the title with its three stars; `This is to
certify that` with the name; the paragraph with `Awarded on the ninth of
October, 2026`; one band of three — the left signature, the seal, the
right signature; the number.

**Not met to the letter: the name is not its own Zone.** Unmerged from
the paragraph, it is gathered by `prefer_container` with the line above,
into the detector's own 0.19 box over the two — the line it is nearest
and whose sentence it completes. Splitting it further would take a rule
against a container the detector draws round two lines, and none was
found that moves the certificate alone. Whether it reads as the page
does is the sweep's to show.

**The replay** (`S9-4-replay`): the certificate is ASKED MORE THAN THE
RUN — its answers come at the sweep — and the five table calls step 1
moved are ASKED DIFFERENTLY, as at `S9-1`. Nothing else.

**By eye** (the Zones drawn on the unwarped page, `front-base` beside
`front-4`): **certificate — better.** The signatures, the seal and the
number are four groups where they were one box, the stray star Zone is
gone inside the title's, and the name sits with its line rather than as
the paragraph's heading.

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

### Outcome — step 5, 2026-10-14

**The change**, in `preprocess`:
- `sheet_beyond` — of the quadrilateral's four edges, the largest share
  of the line `SHEET_STEP` (4 px at `DETECT_LONG_EDGE`) outside it that
  is `SHEET_APART` from the surround. Re-measured on the small copy:
  the receipt **0.00**; the ticket **0.85** (top), 0.09, 0.23, 0.42.
- `sheet_outline` — everything `SHEET_APART` from the surround, closed,
  its largest outer contour, four rough corners off the hull; then each
  side fitted to the contour along its middle eight tenths and the
  corners taken where the fitted sides meet. A hull's corners stand on
  the card's rounded corners, inside the paper, and a side between them
  leans: the prototype's left edge stood upright at x 54 while the
  ticket's runs 46 to 54. The ticket gives **(46, 56), (845, 37),
  (853, 342), (54, 361)**, every edge 0.00.
- `rectify`: where `sheet_beyond` exceeds `SHEET_BEYOND` = 0.5 — the
  middle of the band from 0.00 to 0.85 — the outline is taken if its own
  edges pass the same test, and the surround is re-read round it. A
  quadrilateral every edge of which has the desk beyond it is kept
  exactly as found. `RECTIFIER_VERSION` 6.

**Measured:**
- Rectified pixels over all 21, `image` and `plain`, against the same
  code with the test held at 0.0: **the ticket alone moves.**
- The layout front (`front-4` → `front-5`): every IR but the ticket's
  differs in `rectifier_version` alone. The ticket goes 5 Zones to 6:
  the stub whole with its `NORDLYS AIR`, `NORDLYS AIR` and `BOARDING
  PASS` each whole, the body in two — the passenger, `OSL` and the left
  fields; `TRD` with `DEPARTS` and `CLASS`.
- **One new Zone that is not content:** `cover_the_page` recovers an
  8 px strip along the foot of the teal header (0.209–0.733 ×
  0.108–0.141). It is `equalise`'s halo where the band meets the white
  card — the band's interior is blown out pale and its last rows read
  as ink. It holds no type, and it is 8 px, on `MIN_RECOVERED_PX`. The
  model will be asked what it is; that answer comes at the sweep.
- The replay (`S9-5-replay`): the ticket and the certificate ASKED MORE
  THAN THE RUN, the five table calls of step 1 ASKED DIFFERENTLY,
  nothing else.

**By eye** (the rectified ticket, old warp beside new): **ticket —
better.** The page is the whole card, level: both headers whole,
`BOARDING PASS` uncut, the stub's `NORDLYS AIR` back, the left margin's
first letters and the foot's `departure` inside the picture.

**The rederive chain is not a measurement of this page.** `S9-5`
(`S9-3d` rederived at this commit) moves the ticket alone, and what it
draws is the old Zones, cut on the old warp, measured on the new
pixels: its type sizes and places are read where the words no longer
are. The ticket's answers come at the sweep; every other page is
byte-identical.

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

### Outcome — step 6, 2026-10-14

`wire.without_title_rows` drops a table row whose non-empty cells
together spell the Zone's Title. `contents_into` applies it after
`_without_title_echo` and re-pads what is left (`repadded`);
`tools/rederive.py` applies it in its step 1. Re-measured over
`s8-result/`: one row in twenty-one documents, paper Zone 8's last,
`['Table I. Site summary', '', '', '']`, tagged `header`.

**Rederive** `S9-5` → `S9-6`: `paper_0018` alone moves; the other twenty
are byte-identical. `vanished` unchanged, 32.

**By eye — paper, better:** the bold `Table I. Site summary` row under
the table is gone; the caption prints once, small capitals above the
table, as the page sets it. `debug/runs/S9-6/report.html`.

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

### Outcome — step 7, 2026-10-14

`looks._drawn_ground` also returns a solid furniture fill holding the
Cell's middle, after a header's `header_fill`; `looks.read` passes it
the page's solid fills.

**Tried first and rejected, measured:** the row's own measured fill
(`Row.fill`), which is how the band reaches the render. It reaches every
table row on a tint: on `timetable_0019` it kept `B04 · Ms Ilves` teal
beside its lesson's blue bar, where the page prints it grey — worse, by
eye.

**Measured:**
- Rederive of `s8-result/` directly (`S9-6-s8` → `S9-7-s8`):
  `statement_0006` and `timetable_0019` move, not the statement alone as
  predicted. The statement's six header Cells take white. On the
  timetable, the Cells on its peach and green lesson fills — which
  `furniture` finds as fills — keep the colour measured on them: subjects
  their ink as before, eleven room-and-teacher lines grey, `(102, 112,
  124)`, where they were drawn in the body ink.
- The chain (`S9-6` → `S9-7`): the timetable alone; the statement's
  header is right there already, by step 1's answer. `vanished`
  unchanged, 32.

**By eye:**
- **statement (at `s8-result/`'s answers) — better:** `Date`,
  `Description`, `Type`, `Paid out`, `Paid in`, `Balance` readable, white
  on the dark band, where the band was blank.
- **timetable — better, slightly:** the room lines on the English and
  Science lessons are grey, as the page prints them and as the other
  lessons' already were; nothing else moves.

`debug/runs/S9-7/report.html`.

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

### Registered — step P, 2026-10-14, at `a84404c`

From `S9-P-replay` (`s8-result/`'s answers served to the last commit)
and `S9-P-swap` (the same, with step 1's four `s7-result/` answers
swapped in):

**The calls the replay marks — seven documents:**

| document | marked | why |
|---|---|---|
| `receipt_0010` | call 10, table, prompt | step 1 |
| `statement_0006` | call 14, table, prompt | step 1 |
| `cv_0013` | call 79, table, prompt | step 1 |
| `nonlatin_0014` | call 20, table, prompt | step 1 |
| `paper_0018` | call 34, table, prompt | step 1 — 5 × 1, never asked of its picture |
| `certificate_0021` | ASKED MORE THAN THE RUN: 8 classify for 7 recorded; pictures move from call 3 | step 4, 7 Zones to 8 |
| `ticket_0020` | ASKED MORE THAN THE RUN: 6 classify for 5; every picture moves | step 5, a new warp; 5 Zones to 6 |

Nothing else is marked. The fourteen others — catalogue, darkdeck, form,
both invoices, letter, menu, newsletter, pricing, report, sample_css,
sample_semantic, sample_table, timetable — ask every call as `s8-result/`
did.

**The prediction:**
1. **Every call not marked comes back byte-identical** to
   `s8-result/answers/`: every call of the fourteen, and every call of the
   five step-1 documents but its one table call.
2. **The four step-1 table answers come back byte-identical to
   `s7-result/`'s**, so receipt, statement, cv and nonlatin render
   byte-identical to `S9-P-swap`, their embedded IR included.
3. **The fourteen unmarked documents render byte-identical to
   `S9-P-replay`**, their embedded IR included.
4. **paper**'s table answer is new and not predicted. If it returns the
   caption as a row again, step 6 drops it; the page prints the caption
   once either way.
5. **certificate**: new answers over 8 Zones. Expected: the signatures,
   the seal and the number drawn as four groups, not one interleaved
   paragraph; the name with `This is to certify that`, not as the
   paragraph's heading; no stray ornament.
6. **ticket**: new answers over 6 Zones. Expected: `BOARDING PASS` read
   whole, the stub's `NORDLYS AIR`, the left margin's first letters,
   `SEAT 12A`, `departure`. **The 8 px strip** at the header's foot is
   asked too: expected empty, or a figure; text printed from it is
   invented, and traced to step 5's halo.

The chain the steps were judged on agrees: `S9-7` (rederived step by
step from `S9-1`) draws nineteen documents byte-identical to these two
replays, its IR differing in `rectifier_version` alone — a rederive keeps
the frozen IR's 5. The certificate and the ticket cannot be compared:
their replays stop where they are asked more.

### Outcome — the sweep, `S9-sweep`, 2026-10-14

Commit `a3969f3`, 11:13–13:29 (**2h16m**), shipped defaults, **732
calls**, the model 40%/60% CPU/GPU. All twenty-one converted.

**The prediction held, every clause:**
1. Every call asked as `s8-result/` asked it answered byte for byte the
   same — 0 differ. Asked differently: the five step-1 table calls, 25 of
   the certificate's 28, all 17 of the ticket's.
2. The four step-1 table answers are byte-identical to `s7-result/`'s;
   receipt, statement, cv and nonlatin render byte-identical to
   `S9-P-swap`.
3. The fourteen unmarked documents render byte-identical to
   `S9-P-replay`.

**By eye, all 21 sheets against `S9-0-replay`: seven pages better,
thirteen the same, one worse.**

**1. The four pages, against Alessandro's note on each**

| page | his note | now |
|---|---|---|
| receipt | the price column lost | **better** — all eight prices at the right, quantities left, `oat milk` and `extra butter` indented, the summary values right |
| certificate | portrait; the signature row one boxed paragraph; the name a three-line heading | **better** — landscape; the name one script line under `This is to certify that`; signatures, seal and number separate. **Not the page's row:** the two signatures stack down the left, the seal an orange text chip `GUILD GTE 2026` to the right |
| pricing | sections scattered | **better** — three framed cards in order, Team's frame blue, the figures large, the toggle on one line |
| ticket | `BOARDING FOUR`; the stub's header missing; a cut-down band | **worse** — `BOARDING PASS` whole, but `OSL`, `OSLO GARDERMOEN`, the stub's `NORDLYS AIR` and `Gate closes 20 minutes before departure` gone, the stub drawn at the top, and a teal band printing `The` / `The` across the page |

Also better: **statement** (`Transactions in date order` back, the
header white on its band, the paid-out column in its rows), **cv**
(`2022`), **paper** (its caption once), **sample_semantic** (`html web
standards` on one line). The same: the twelve whose drawn markup did not
move, nonlatin, and the timetable (its room lines grey, as printed — not
visible at sheet scale).

**2. The six held-out pages** — recorded, not argued from:

| page | by eye | vocabulary recall | tau | beside |
|---|---|---|---|---|
| certificate | better; the signature row stacked | 1.000 → 1.000 | 1.000 → 1.000 | 1.000 → 0.000 |
| letter | same | 0.995 → 0.995 | 1.000 → 1.000 | 1.000 → 1.000 |
| paper | better | 0.985 → 0.985 | 1.000 → 1.000 | 0.547 → 0.547 |
| pricing | better | 1.000 → 1.000 | 0.622 → 0.880 | 0.244 → 0.629 |
| ticket | **worse** | 0.975 → 0.750 | 0.892 → 0.282 | 0.418 → 0.000 |
| timetable | same | 0.982 → 0.982 | 0.957 → 0.957 | 0.991 → 0.991 |

`vanished` 40 → 41: back — the receipt's six price tokens, `castleton`,
`2022`, the ticket's `pass`; gone — ten of the ticket's: `nordlys`,
`air`, `osl`, `oslo`, `gardermoen`, and `closes`, `20`, `minutes`,
`before`, `departure` from its gate note.

Means, against `s8-result/` (all 21 / the fifteen / the six): vocabulary
recall 0.984 → 0.977 / 0.982 → 0.988 / 0.989 → 0.952; tau 0.968 → 0.951
/ 0.990 → 0.990 / 0.912 → 0.853; beside 0.802 → 0.757 / 0.843 → 0.849 /
0.700 → 0.528. The six's falls are the ticket's and the certificate's
row.

**3. Where it gained**

| page | gain |
|---|---|
| receipt | **prices** — eight back at the right; six price tokens out of `vanished` |
| statement | **header** — readable on its band; `castleton` back; the paid-out column in its rows |
| certificate | **shape** — landscape; the name one line; the row's lines no longer interleaved |
| pricing | **cards** — three framed stacks; tau 0.622 → 0.880 |
| cv | **`2022`** beside its diploma |
| paper | **caption once** |
| sample_semantic | **tags on one line** |

**4. The faults left, by stage**

| page | what the page shows | stage | evidence |
|---|---|---|---|
| ticket | a teal band printing `The` / `The` | Layout | `cover_the_page` recovered the 8 px `equalise` halo at the header's foot (step 5's outcome named it); prose answer `["The"], ["The"]` |
| ticket | `OSL`, `OSLO GARDERMOEN`, the gate note, the stub's `NORDLYS AIR` gone | Classify → Extract | the stub and the left body classified `pairs`; the pairs answers hold only label–value pairs |
| ticket | `NORDLYS AIR` drawn as a picture | Classify | the header Zone classified `figure`, `logo`; its text is `alt`, never printed |
| ticket | the stub drawn above the body | Layout → Render | the stub's Zone spans the page's height in band 0; regions read `single` |
| certificate | the signatures stacked, the seal beside one | Structure → Render | one `single` region; band 4's three Zones wrap; beside 1.000 → 0.000 |
| certificate | the seal an orange text chip | Render | figure answered `badge` with text; drawn as a chip, not its pixels |
| certificate | the course name plain, the stars black | Style | Look: bold not read on the run; the stars' colour not kept |
| pricing | buttons with no outline, check marks as bullets, Team's header left | Render | furniture of the buttons not drawn; list marks the house's |
| sample_semantic | `Tags:` and the commas missing | Extract | the list answer holds the three tags only |

**5. Directions, ranked by gain for cost**

| # | stage | change | why | cost |
|---|---|---|---|---|
| 1 | Layout | a recovered patch must hold type, not only a solid block's halo | removes the ticket's `The` / `The`, invented text | layout front offline; answers at a sweep |
| 2 | Structure | a band whose Zones stand side by side on the page is drawn as a row | the certificate's signature row; beside 0.000 | rederive offline |
| 3 | Render | a figure is drawn from its pixels whatever text it carries | the certificate's seal | rederive offline |
| 4 | Classify → Extract | a pairs Zone whose answer leaves printed lines unread is read again as prose | the ticket's `OSL`, airport, gate note, stub header | a model question; replay with swaps, then a sweep |
| 5 | Classify | a line of type in a header is not a logo | the ticket's `NORDLYS AIR` | a model question; a sweep |

**6. Recommendation.** Seven pages better, three of them Alessandro's
four, and the prediction held to the byte. The ticket is the cost: its
new crops are whole and their answers lose ten words. **Whether
`S9-sweep` becomes the baseline is Alessandro's decision**; if taken, the
ticket's leg is named here as `s8-result/`'s three were, and directions
1 and 4 are its repair.

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

## Handover prompt — after `S9-sweep`: Alessandro's decision, then the freeze (record — done 2026-10-14)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0013-four-pages-first.md's "Outcome — the sweep". Spec 0013's
work plan is done; nothing is open except Alessandro's decision on
S9-sweep. Do not pick anything up unless he names it — the five
directions in the outcome are record, not a queue.

State, re-measured 2026-10-14 at a3969f3 (code as a84404c):
- the suite: 1142 passed, 1 skipped; mypy src clean;
- debug/runs/S9-sweep/: 21 documents, 732 calls, 2h16m;
  tools/replay_run.py debug/runs/S9-sweep reproduces 21 of 21
  byte-identical, 0 asked differently; tools/rederive.py over it gives
  21 of 21 byte-identical files;
- by eye against S9-0-replay: 7 pages better (receipt, certificate,
  pricing, statement, cv, paper, sample_semantic), 13 same, 1 worse
  (ticket_0020: ten words gone, and an 8 px halo Zone read as "The").

If debug/runs/S9-sweep/ is gone, say so and stop: it cannot be remade
without a sweep.

If Alessandro takes S9-sweep as the baseline: freeze it as
tests/frozen/s9-result/ in the shape of s8-result/ — documents/,
scores.json, answers/ (tools/replay_run.py debug/runs/S9-sweep
--save-answers <dir>, with hashes), dth_env.txt, and a README giving its
provenance, the prediction it held, and the ticket's leg named as
s8-result/'s README names its three. Prove the freeze: replay and
rederive of tests/frozen/s9-result each 21 of 21 byte-identical, and
the report scored straight out of it against s8-result/. Then update
CLAUDE.md's baseline lines and docs/status.md, one commit.

If he does not, ask what he wants done with the ticket first. Whatever
comes next is his to name.
```

---

## Handover prompt — implement spec 0013, four pages first, then one sweep (record — done 2026-10-14)

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
