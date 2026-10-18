# Structure first — one grid where the page sets one, one strip where it draws one

**Status: planned 2026-10-18, issue #39, not started.** Four steps, in
order, each judged by eye, then one full sweep, `S12-sweep`, over all
twenty-one documents. The handover prompt at the end, marked *current*, is
the one to start a session with.

Alessandro's decisions, 2026-10-17 and 2026-10-18:

1. **`S11-sweep` is the baseline**, frozen as `tests/frozen/s11-result/`.
2. **The ticket's layout is still inconsistent**, and it stays the focus.
3. **Structure and layout first, not text or words.** This spec moves
   rows, columns, strips and the Zones they are drawn from. Where a step
   touches reading at all, it is there only so that a structural repair
   loses no word (step 4's two guards).
4. **General repairs, not per-page ones** (his ask of 2026-10-14, still
   standing). He asked whether these rules generalise or are fitted to
   the ticket. §1's last table answers that rule by rule. Most are
   general in form but proven only on the ticket, because no other page
   in the corpus has the fault.
5. **Reset, 2026-10-18: everything not in this spec is cleared.** That
   covers spec 0015's "Directions, ranked"; the faults
   left on `S11-sweep`'s other pages (the certificate's seal, names and
   stars, the timetable's `Lunch` under its grid, sample_semantic's `Tags:`
   after its links); type at display size (`OSL`); borrowed looks
   (`NL 0482`, the catalogue's three prices); marks (the barcode, the
   plane); the stub strip's own text; bold; and every earlier queue and
   idea. None of it
   returns unless he names it. **Implement this spec's four steps and its
   sweep, and nothing else.**

---

## How to work

- **By eye.** Every step ends with sheets for the pages it moved, against
  the step before. Judge each page better / same / worse in one sentence
  that names the element. **The ticket first, every step.**

  ```
  tools/visual_review.py <run> --previous <previous step's run> --documents <moved pages>
  ```
- **Scores are recorded, never gating, never argued from.** The one number
  read is the report's `vanished` list, as a pointer to a page to open.
- **The six held-out pages** (`corpus.NEW`: letter, pricing, paper,
  timetable, ticket, certificate) are reported in their own lines.
- **Each step is its own commit, with its tests.** Every new step that
  writes the IR goes into `tools/rederive.py`. Steps 1–3 write none; they
  are render and anchoring only.
- **Report each step** with what the pages look like and the sheet paths.
  Continue unless a page got worse; if one did, stop, show it, and ask.
- **Each step names its prediction before it is measured.**

**The loops**, proved on `s11-result/` at `3c5e365`'s code (see its
README), and again on 2026-10-18 at `2f8306a` (`S12-0-replay`,
`S12-0-base`):

| loop | command | what it can measure |
|---|---|---|
| rederive | `tools/rederive.py tests/frozen/s11-result --label <L>` | every step downstream of the model: steps 1–3, and step 4's two `locate` guards |
| layout front | `tools/layout_front.py <out> --documents sweep` | the Zones, with no model. Step 4's recovery change: compare against the same tool at the step before |
| replay | `tools/replay_run.py tests/frozen/s11-result --label <L>` | the wire, the mapper and every pass. It marks a moved call **ASKED DIFFERENTLY**; that page is then not a measurement |
| a targeted run | `FIXTURE=ticket_0020 tools/iterate.sh <L>` | the model's answers on the ticket's moved crops (step 4). **A check that the step works, not the review**; the review is the sweep |

`tools/rederive.py` refuses a label that already exists; use a fresh one.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s11-result/scores.json
```

**The prototype** behind every measurement below is
`debug/runs/_prototypes-0016/structure-first.diff`. It applies cleanly to
`2f8306a` with `git apply`. It is gitignored; if it has been cleared, the
text below is enough. **It is a prototype, not the implementation:**
- it carries a widen-to-test switch, `DTH_PROTO_WIDE`, and `_lines_any`,
  neither of which ships;
- `furnish._over_top` writes into `Anchors.hatches`. Give the band a field
  of its own;
- its docstrings number the steps differently from this spec;
- it has no tests.

`steps-1-4.diff` beside it is the first prototype, typography included.
It is a record only: the type half is not in this spec.

---

## 1. The ticket, inspected at `s11-result/`

**What the page is.** A card with two panes, parted by a dashed
perforation. Each pane opens with a teal strip.
- **Main pane:** the strip (`NORDLYS AIR` left, `BOARDING PASS` right),
  then the passenger field. Then the route row: a large `OSL` over
  `OSLO GARDERMOEN`, a plane, a large `TRD` over `TRONDHEIM VÆRNES`. Then
  a grid of four columns, label over value, two rows deep: `FLIGHT DATE
  BOARDING DEPARTS`, then `GATE SEAT GROUP CLASS`.
- **Stub:** its own strip, the passenger field, two rows of two fields
  with the right-hand ones flush right, a barcode, and a small centred
  note.

Spec 0015 made the stub a pane. **What is left is wrong *between*
Zones**, and no change inside one Zone can reach it.

**The Zones** (straightened card, shares of the page): z0 the stub
[0.736–1, 0–1]; z1 the wordmark, a figure; z2 `BOARDING PASS`, prose; z3
[0.028–0.452, 0.180–0.836], Title `PASSENGER`; z4 [0.538–0.706,
0.354–0.849], Title `TRD`; z5 [0.209–0.733, 0.108–0.141], prose.
`furniture` finds the strip as a solid fill [0–1, 0–0.148], colour
(11, 110, 138), and the perforation as a rule at 0.736–0.738.

| what the reader sees | cause, at the stage that introduces it | step |
|---|---|---|
| The route row and the field grid are each split in two. `DEPARTS 08:05` stands a row below `BOARDING 07:35`, `CLASS Economy` below `GROUP 2`, and `TRD` is a Title over its own box instead of level with `OSL` | The detector cuts regions along white space, and the main pane's widest vertical gutter runs between grid columns 3 and 4. So z3 holds the passenger field, `OSL` and columns 1–3, and z4 holds `TRD`, `TRONDHEIM VÆRNES` and column 4. `render._band` draws each Zone as its own unit, spacing its lines from its own top. **Measured: every z4 line sits level with a z3 line**: `TRONDHEIM VÆRNES` 0.502 with `OSLO GARDERMOEN` 0.495; `08:05` 0.654 with `NL 0482` 0.650; `Economy` 0.798 with `C14` 0.789 | **2** |
| `DEPARTS` and `CLASS` are drawn beside their values, not over them | Both labels are unplaced (tesseract never boxed them), and neither of spec 0015's rules reaches them: they have no line-mate, and the next entry in reading order is their own value. Every pair on the page with both entries placed is set label over value | **2** |
| A column's entries do not keep one edge from row to row; an entry is pushed flush right where the page starts it at a column edge | `render._placed` builds each line's tracks from that line alone, and its last track is `auto`, which takes the leftover width. The stub's `SEAT` / `12A` really are flush right. The main grid's third column is not | **1** |
| The teal strip comes back in three pieces: `NORDLYS AIR` on a teal box of its own, `BOARDING PASS` as a teal heading that wraps onto two lines, and the page's ground between them | `render` draws no plain fill. Frames, hatches and a lane's fill (`_lane_fill`, the cv's sidebar) are drawn; a free solid fill is recorded and dropped. Each Zone on the strip paints its own fill, so the strip comes back as one box per Zone. `BOARDING PASS` is white on teal, so `style.heading_sizes` (which measures on the page's ground) leaves `block.size` empty, and it is drawn at the house 1.6em, where its lines measure 1.06 | **3** |
| The stub's strip is missing; its passenger field starts at the stub's top | The stub (z0) starts at the fill's top and is not filled itself, and nothing anchors a fill to the top of a Zone it is not the fill of | **3** |
| Under the strip, a second full-width teal strip is printed `The` / `The` | `equalise` leaves a halo along the strip's lower edge, and `_cover_the_page` recovers it as a Zone, z5 [0.209–0.733, 0.108–0.141]: 0.079 ink share, 8px tall. The model is asked its Kind, its prose and its runs, and reads `The` off an empty crop | **4** |
| `TRD` is drawn at title size, not display size; `PASSENGER` is measured 0.88 where it prints at about 0.77 | Not a type fault, and this spec changes no type rule. z5's halo enters the page's body measure, which comes out 8.0px instead of 9.0. At 8.0, `TRD` measures above `style.LARGEST_EM` (4.0), so the measurement is refused. With z5 gone, `TRD` measures **3.76** and `PASSENGER` **0.78**, with no other change | **4** |

**Not in this spec** (named so they are not mistaken for misses): `OSL`
drawn small (it is read as a chip; display size is type); `NL 0482` drawn
small (an entry with no measured look); the barcode and the plane
(marks); `NORDLYS AIR` on the stub's strip (white type on a fill, never
read); bold.

**What the prototype draws** (`P16-8z`: all four steps, rederived from a
copy of `s11-result/` with z5 taken out of the ticket's IR, as step 4's
recovery does). The pass reads as one card:
- one teal strip across the main pane, `NORDLYS AIR` left and `BOARDING
  PASS` right on it, with no `The`;
- the stub opens on its own strip;
- the passenger field, then the route row on one line: `OSL` over
  `OSLO GARDERMOEN` on the left, `TRD` at display size over `TRONDHEIM
  VÆRNES` on the right;
- a four-column grid, label over value, `DEPARTS` over `08:05` and
  `CLASS` over `Economy`;
- the stub's fields in two columns, the right-hand ones flush right;
- the gate note on its two printed lines.

Still off: `OSL` small, no barcode or plane, no text on the stub's strip.
That simulation stands in for step 4's real run, which asks the model
again (§5).

### Do these rules generalise?

| rule | the principle | evidence beyond the ticket | fitting risk |
|---|---|---|---|
| 1 one column grid per line-drawn Zone | a renderer fault: the last track takes the leftover width | **moves five pages**: the ticket, and catalogue, cv, form and invoice_0002, which look the same | low; one constant, `WRAPS` |
| 2 one grid across side-by-side Zones | entries the page sets on one line are drawn on one line, whatever Zone holds them | **none**: only the ticket passes the gates | **medium**. The gates were chosen while checking which pages fire. `LEVEL` decides nothing in the corpus, because no other run of units gets past the gates in front of it. With the gates relaxed, invoice_0002's framed panels merge, which is worse; so the frame / fill gate is necessary |
| 2 label over value by the page's habit | a page sets its fields one way | fires only on the ticket. The form's habit is not unanimous, so it does not fire there | medium; `HABIT` = 3 is not taken from a distribution |
| 3 a plain fill drawn once behind its rows | extends `_lane_fill` (the cv's sidebar) to a fill that holds rows rather than a lane | fires only on the ticket. Pricing's button and invoice_0002's mark do not qualify | low |
| 3 a fill across a Zone's top drawn as its band | extends spec 0011's hatch band (the catalogue's tiles) to solid fills | ticket only | low |
| 3 a heading with no measured size takes its lines' size | uses a measurement the IR already holds | ticket only | low |
| 4 no Zone recovered from a drawn fill | a fill's edge is not type | ticket only: z5 is the only Zone of its kind (layout front, all 21) | low |
| 4 two guards in `locate` | a structural repair may not lose a word | change nothing on the other twenty (rederive, all 21) | low |

---

## 2. Step 1 — one column grid per line-drawn Zone (offline)

**The fault.** `render._placed` (spec 0012 G4, spec 0015 step 2) draws a
pairs Zone line by line. Each line's `grid-template-columns` comes from
that line's starts alone, and its last track is `auto`. So a column
keeps no edge from row to row, and the last entry of a line slides to
wherever the leftover width puts it.

**The change**, in `_placed`:
- **One set of column edges per Zone.** An entry's left edge joins a
  column where entries on two or more lines start within `reach` (a body
  glyph). Its right edge joins one where only their right edges agree,
  which is how the stub sets `SEAT` / `12A` (`_aligned`).
- **Each line's tracks run between those edges** as `minmax(0, <share>fr)`,
  with no `auto` track (`_edges`). An entry set from the left starts its
  track at its column's edge. One set flush right ends its track there,
  and is drawn `justify-self:end` (`_flush`). Between two entries
  otherwise, the track changes halfway across the gap. If the edges do
  not increase, fall back to each entry's share up to the next one's
  start.
- **Wrapping.** Entries that share a line do not wrap (`white-space:
  nowrap`). A line holding one entry wraps (`span:only-child`): the first
  version set nowrap globally and cut the cv's `Chartered Engineer,
  Engineers Ireland (2019)`. An entry whose box is taller than `WRAPS`
  (2.0) of its glyph heights is printed on more than one line, and wraps
  as the page wraps it.
- `PLACED_CSS`: the grid's `column-gap` becomes each span's
  `padding-right:.3em`, so the tracks are the page's shares.

**Prediction.** Five pages move: the ticket, catalogue, cv, form and
invoice_0002. By eye, only the ticket changes: its columns keep one
edge from row to row. The other four look the same. No word changes.
The replay asks nothing differently (render only).

**Measured on the prototype** (`P16-1b` against `S12-0-base`): exactly
those five. Each of the four besides the ticket renders byte-identical to
the full prototype, so every later step moves the ticket alone.

**Where to look.** `render._placed`, `_printed_lines`, `_by_line`,
`_same_line`, `PLACED_CSS`, `_style_css`.

### Outcome — step 1, 2026-10-18

`S12-1b`, rederived from `s11-result/`, against `S12-0-base`. **The
prediction held: exactly the five pages moved.** Sheets:
`debug/runs/S12-1b/_review/`.

| page | by eye |
|---|---|
| ticket | **better**: every grid column keeps one edge — `DATE` / `14 OCT 2026`, `SEAT` / `12A`, `BOARDING` / `07:35`, `GROUP` / `2` each start together, where `07:35` and `2` stood flush right; the stub's `GROUP` / `2` share a left edge as printed |
| catalogue | same: `each`, `In stock` and `NEW` shift 3–7px sideways, no line moves |
| invoice_0002 | same: `Date` stands about 5px nearer `01/01/2015` |
| cv, form | same: pixel-identical |

**One amendment to the prototype.** A line set flush right to a column
edge short of the Zone's right kept its one `fr` track, which takes the
whole line: the ticket's `departure` went to the stub's right edge. The
remainder of the line is now an empty track, so it ends at its column's
edge as this section says, and `departure` is drawn where `S12-0-base`
drew it.

**One correction to the plan.** The stub's `SEAT` / `12A` agree on both
edges (0.943 / 0.943 left), so they are a left column, not a flush-right
one. Over the twenty-one the right-edge rule fires on three lone lines
whose right edge meets another line's — the form's `CT9 4RD`, one
catalogue card's `each`, the ticket's `departure` — each drawn ending
where the page ends it.

Scores, recorded: `vanished` 26 → 26 words; the ticket's alignment
agreement 0.618 → 0.735, the catalogue's 0.492 → 0.475. Suite 1208
passed, 1 skipped.

---

## 3. Step 2 — one grid where the page sets one, across side-by-side Zones (offline)

**The fault.** §1's first two rows: the detector's cut at a gutter split
one grid of fields into two Zones. Each is drawn as its own band unit,
and an unplaced label falls beside its value.

**The change.**
- **2a. A run of side-by-side units the page sets as one grid is drawn as
  one** (`render._one_grid`, `_grid_unit`, called from `_band`). A run is
  adjacent units of one band where:
  - each unit is one PAIRS Zone drawn by its printed lines (`_printed_lines`
    is not None);
  - nothing is drawn round or behind any of them (no `frame`, `boxed`,
    `fill` or `title_fill`), and none is text-aligned (`TEXT_ALIGN`);
  - each shares at least `LEVEL` (2) printed lines with the unit before
    it (`_same_line`).

  The run is one unit:
  - its lines are the union of the Zones' printed lines, gathered by the
    line they share;
  - one column grid (step 1) is drawn over them, with `_placed`'s band
    push off;
  - its lane is the sum of the Zones' lanes;
  - its `margin-top` comes from the earliest start among them.

  Mind `_band`'s last-unit-flush-right test when the loop stops being
  one unit per step: the prototype had to re-index it.
- **2b. Each Zone's Title becomes a line of that grid** (`_title_line`).
  The Title holds no box of its own, so the line is a box from the
  Zone's top to just above its first entry. It starts at the Zone's left,
  its right edge for a Title set flush right, or its middle for one
  centred (`title_align`). Its look is the Title's size (`title_size`,
  else 0.95), bold, `title_color` and `title_caps`. So `TRD` stands flush
  right over `TRONDHEIM VÆRNES`, level with `OSL`.
- **2c. An entry placed by inference joins its role's line.** An entry
  with no box of its own (spec 0015 2b's implied boxes) joins the nearest
  line holding a placed entry of its own role (label or value), within
  its own height. So `CLASS` takes the line of `GATE SEAT GROUP`. Place
  the placed entries first, then the implied ones.
- **2d. A label placed by the page's habit** (`_inferred`'s third rule,
  `_habit`). An unplaced label goes over its placed value where every
  pair of the page with both entries placed (at least `HABIT` = 3) sets
  its label over its value, left edges within a body glyph. Its gap and
  height are the page's medians. Likewise an unplaced value goes under a
  placed label. `_printed_lines` and `_inferred` take the `Document` for
  it.

**Prediction.** Only the ticket moves: the route row on one line, `OSL`
left and `TRD` right; the grid four columns wide, `DEPARTS` over `08:05`
and `CLASS` over `Economy`. No word changes. `TRD` is drawn at title size
until step 4, because its size is refused at `s11-result/`'s body
measure (§1).

**Widen-to-test, done on the prototype.** With the frame / fill /
text-align gates dropped, `LEVEL` at 1 and lines taken from any pairs
Zone (`DTH_PROTO_WIDE=1`, run `P16-W`), one more page fires:
invoice_0002. Its framed `Company Details` and `Customer Details` panels
merge into one grid, which is worse. The gates as written fire on the
ticket alone. **Do not ship the switch.**

**Where to look.** `render._band`, `_lanes`, `_unit`, `_top`, `_placed`,
`_printed_lines`, `_inferred`, `_in_column`, `_before_next`;
`Zone.title`, `title_size`, `title_align`, `title_color`, `title_caps`.

### Outcome — step 2, 2026-10-18

`S12-2`, rederived from `s11-result/`, against `S12-1b`. **The prediction
held: only the ticket moved.** Sheet: `debug/runs/S12-2/_review/`.

- **Ticket, better.** `TRD` stands flush right on the line of `OSL`, and
  `TRONDHEIM VÆRNES` level with `OSLO GARDERMOEN`. The grid is four
  columns: `DEPARTS` over `08:05` on the `FLIGHT DATE BOARDING` line,
  `CLASS` over `Economy` on the `GATE SEAT GROUP` line, where both stood
  beside their values a line out of step. `TRD` is drawn at Title size,
  as predicted until step 4.

Built as the prototype, without its switch: the wrapper is the first
Zone's `section` with no inner `zone-body` (whose padding is 0 outside a
card). Scores, recorded: the ticket's tau 0.843 → 0.947, beside 0.262 →
0.333; heading levels 3 → 1, because `PASSENGER` and `TRD` are drawn as
lines of the grid, not as `h2`s; `vanished` 26 → 26. Suite 1219 passed,
1 skipped.

---

## 4. Step 3 — a drawn strip is one container (offline)

**The fault.** §1's fourth and fifth rows: the strip is recorded and never
drawn, so it comes back in pieces; the stub's strip is not drawn at all;
and `BOARDING PASS` is drawn at the house heading size.

**The change.**
- **3a. A plain fill holding a run of rows is drawn once behind them**
  (`render._filled`). Rows are gathered when they are consecutive, every
  Zone in them lies inside one solid fill with no Zone of its own
  (`Furniture.zone` None, within `SLACK` 0.01), and each Zone paints no
  fill of its own or the fill's own colour (`COLOUR_APART`). Such a run is
  drawn as one `filled` row:
  - the fill as its background;
  - padding from the fill's top to the first row, and from the last row
    to its bottom;
  - ink readable on the fill (`_readable_on`).

  Apply it in `_body` after `_framed`, and per lane in `_columns`, except
  in a lane `_lane_fill` already paints whole.
- **3b. A solid fill across the top of a Zone it is not the fill of is
  drawn as that Zone's band** (`furnish._over_top`), the way spec 0011
  draws a hatched band. It applies when:
  - the Zone is not a table or a figure, and has no `fill`, `title_fill`
    or `header_fill`;
  - the fill starts at the Zone's top within 0.01, spans its width within
    0.005, and ends above its bottom.

  The band is as wide as the Zone (its frame where it has one). In
  `_placed`, the first line then starts below a **solid** band, at the
  page's distance from the Zone's top. A hatched band keeps spec 0011's
  placement: pushing it too doubled the catalogue `CP-402` card's
  offset. **Give the band its own field in `furnish.Anchors`**; the
  prototype reused `hatches`.
- **3c. A heading with no measured size takes its lines' size**
  (`render._heading_size`, used by `_drawn_size` and `_block`): the
  median of its lines' measured sizes, when every line has one. So
  `BOARDING PASS` is drawn at 1.06 and stops wrapping.

**Prediction.** Only the ticket moves: one strip behind `NORDLYS AIR` and
`BOARDING PASS`, the stub opening on its strip, `BOARDING PASS` on one
line. z5 lies inside the strip, so `The` / `The` is drawn on it at the
right, and the strip stands about twice the page's height. Step 4 removes
z5. The prototype drew exactly this (`P16-5b`, steps 1–3 over
`s11-result/`).

**Where to look.** `render._body`, `_framed`, `_columns`, `_lane_fill`,
`_stack`, `_Row`, `_readable_on`, `_drawn_size`, `_block`;
`furnish.anchor`, `_hatch`, `Anchors`; `style.heading_sizes`.

---

## 5. Step 4 — no Zone from a drawn fill's edge (layout; the ticket's calls move)

**The fault.** §1's last two rows: `_cover_the_page` recovers the strip's
`equalise` halo as a Zone, z5. Three calls are spent on it, it prints
`The` twice, and it moves the page's body measure, which refuses `TRD`'s
size.

**The change.**
- **4a. Recovery ignores the solid fills the page draws.**
  `orchestrator.recovered_zones` takes boxes to ignore, and
  `_cover_the_page` passes the solid fills `furniture.find` finds on the
  plain image. The prototype calls `find` again there. If the fills can
  be had from an earlier stage without a second pass, prefer that. Either
  way, report the time the stage takes. **Tried and rejected:**
  `uncovered_regions(type_only=True)` changes nothing on any page: the
  halo band is 8px, under `PANEL_SPAN` 9.
- **4b. A one-character word does not block the display read.** In
  `locate.display_words`, a confident first-read word blocks the display
  read only if it is at least two characters long. Without z5, the
  turned-over read finds a `5` at confidence 93 over `OSL`, and `OSL` is
  lost.
- **4c. A claimed line is boxed by all its printed words.** In
  `locate._from_lines`, the confident words decide which line a Cell
  claims, and the box is every word of that line not already taken.
  Without z5, at a body of 9.0px, the first read garbles the gate note
  (`gre` 5, `90` 39, `141` 0, `4` 0, `before` 95). The claim then boxed
  `before` alone (0.918–0.952), and the note wrapped one word per line.
  With 4c it spans 0.784–0.952, as at `s11-result/`.

4b and 4c are guards. They are in a structure-first spec because without
them, removing z5 loses `OSL` and breaks the gate note's line.

**Prediction, measured on the prototype:**
- **Layout front, all 21** (`_lf-base` against `_lf-2b`): only the
  ticket's Zones change. The ticket goes from 6 Zones to 5, losing z5;
  no other Zone moves.
- **Rederive of `s11-result/`, all 21:** 4b and 4c change nothing
  (`P16-6` against `P16-8`, byte-identical).
- **Replay of `s11-result/`, all 21, all four steps** (`P16-RA`):
  - twenty pages asked exactly as the baseline asked them. Sixteen
    render byte-identical; catalogue, cv, form and invoice_0002 match
    step 1's rederive;
  - the ticket is marked **ASKED DIFFERENTLY**: 22 calls become 19.
    z5's classify, prose and runs calls go. Three of its five re-read
    crops move: the gate note, `OSLO GARDERMOEN` and `NL 0482`. Its
    `departure` and `OSL` crops are asked as before;
  - so the replay's ticket is not a measurement. The replay serves by
    pass and order, and it served z5's `The` answer to the gate note's
    crop.

**Check with a targeted run on the ticket** (`FIXTURE=ticket_0020
tools/iterate.sh <L>`, a few minutes). Expected:
- 19 calls;
- the five re-reads answered as the gate note's two lines, `OSL`, `OSLO
  GARDERMOEN` and `NL 0482`;
- the page as `P16-8z` draws it (§1).

If a moved crop is answered differently, that is the finding. Stop, show
it, and ask before the sweep.

**Where to look.** `orchestrator.recovered_zones`, `Conversion._cover_the_page`,
`preprocess.uncovered_regions`, `MAX_RECOVERED_SHARE`,
`MIN_RECOVERED_INK`, `MIN_RECOVERED_PX`; `furniture.find`;
`locate.display_words`, `CONFIDENT`, `DISPLAY_GLYPH`, `_from_lines`,
`_claims`, `_covered`, `_union`.

---

## 6. Work plan

| step | what | runs on | done when |
|---|---|---|---|
| 0 | prove the baseline | replay, rederive, suite | replay 21 of 21 byte-identical, 0 marked; rederive 21 of 21; 1201 passed, 1 skipped; `mypy src` clean |
| 1 | one column grid per line-drawn Zone | rederive | five pages move, the ticket better by eye, the four others the same |
| 2 | one grid across side-by-side Zones; Titles as lines; implied entries on their role's line; the page's habit | rederive | only the ticket moves: route row on one line, four-column grid |
| 3 | a strip drawn once; a fill across a Zone's top as its band; a heading's size from its lines | rederive | only the ticket moves: one strip, the stub's strip, `BOARDING PASS` on one line |
| 4 | no Zone from a fill's edge; the two `locate` guards | layout front, rederive, replay, a targeted run on the ticket | only the ticket's Zones move; 4b and 4c change nothing on the twenty; the targeted run as §5 expects |
| P | register §7's prediction in this spec | a replay at the last commit, beside the targeted run | the marked calls written down before the sweep |
| S | **`S12-sweep`**: all 21, shipped defaults, started detached | the model | §7 checked; all 21 sheets opened against `S12-0-replay`; the outcome written |

---

## 7. The sweep's prediction — to be registered at step P

What step P is expected to confirm, from the prototype's replay
(§5). **Re-take every number at the last commit before writing it here.**

1. **Twenty pages**: every call `s11-result/` asked, asked alike and
   answered byte for byte the same. Nothing else asked.
2. **The ticket**: 19 calls. z5's three are gone, and its five re-reads
   are answered as the targeted run answered them.
3. **Renders**:
   - the sixteen pages no step moves render byte-identical to
     `s11-result/`;
   - catalogue, cv, form and invoice_0002 render byte-identical to the
     step-P replay;
   - the ticket renders byte-identical to the targeted run, replayed at
     step P.
4. **Calls in all: 746** if nothing else moves (749 − 3).

Then report the sweep in the error-analysis format:
1. **the ticket first**, against §1's table, row by row;
2. the other pages step 1 moved;
3. the six held-out pages in their own lines;
4. where it gained;
5. the faults left, by stage;
6. a recommendation.

Whether `S12-sweep` becomes the baseline is Alessandro's decision.

---

## 8. Not in this spec

Named so they are not mistaken for misses. None is queued.

- **Type at display size**: `OSL` (read as a chip; the prototype's
  inked-border test for chips, `CHIP_BORDER` 0.25, is in
  `steps-1-4.diff`), and `style.LARGEST_EM`. Raising the cap to 6.0 was
  fitted to `TRD` alone; with z5 gone, `TRD` fits under 4.0 anyway.
- **Borrowed looks**: an entry with no measured look takes its column
  mates' (`NL 0482`, the catalogue's three prices). The first version
  enlarged the catalogue's badges.
- **Marks**: the barcode, the plane, and the rest of spec 0015 §7's.
- **The stub strip's text**: white type on a fill. Reading the other
  polarity everywhere was measured and rejected in spec 0015.
- **Bold on photographed pages**: the ticket 10 of 13 values right, the
  receipt 10 false bold with `TOTAL` missed. Not worth more without new
  evidence.
- Everything spec 0015 §7 lists.

---

## 9. Rules that bind

- "How to work" above, and CLAUDE.md's.
- **Never cite a past run.** The committed frozen directories are the
  exception, for what their READMEs say. The prototype runs named here
  (`P16-*`, `_lf-*`) are this spec's evidence for the plan only; re-take
  each measurement at the step it belongs to.
- **Any reviewed run covers all twenty-one documents.** Step 4's targeted
  run is a check, not a review.
- **Never edit `tools/iterate.sh`, or any script a running sweep reads.**
- **Marking may never change the words.** Steps 1–3 move entries, never
  text. Keep the four shipped defaults and the six wire row nets.
- **What is read off a Graphic is `alt`, never printed.**
- **ADR 0002 stands**: the render is flow layout. Shares, tracks and
  margins come from the page's positions; nothing is placed absolutely.
- Leave `debug/runs/84-rule-not-a-line/` intact. Never score against
  `tests/documents/SAMPLE_DOCUMENTS`.

---

## Handover prompt — implement spec 0016, then one sweep (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0016-one-grid-one-strip.md end to end — the only open work,
issue #39. Alessandro cleared everything else on 2026-10-18 (spec 0015's
ranked directions, the other pages' left faults, display type, borrowed
looks, marks, the stub strip's text, bold). Implement only this spec's
four steps and its one sweep; do not pick anything else up unless he
names it, and if a step tempts you past its scope, stop and ask.

Focus: ticket_0020's layout — structure and layout, not text or words.
§1 of the spec lists every structural fault on the ticket, its cause and
the step that repairs it, and says, rule by rule, how far each one is
proven beyond the ticket. Judge every step on the ticket first.

The baseline is tests/frozen/s11-result/ (spec 0015's sweep, 21
documents, 749 answers). Prove it before any change (step 0):
- tools/replay_run.py tests/frozen/s11-result --label S12-0-replay
  reproduces 21 of 21 byte-identical, 0 marked;
- tools/rederive.py tests/frozen/s11-result --label S12-0-base gives 21
  of 21 byte-identical files;
- the suite: 1201 passed, 1 skipped; mypy src clean.
(rederive refuses a label that exists — use fresh labels.)

The prototype is debug/runs/_prototypes-0016/structure-first.diff
(applies to 2f8306a; gitignored — if cleared, the spec is enough). It
is not the implementation: drop its DTH_PROTO_WIDE switch and
_lines_any, give furnish's top band its own Anchors field, write tests.

The steps, in order:
1 one column grid per line-drawn Zone — render._placed: column edges
  shared across the Zone's lines, minmax tracks with no auto track,
  flush-right columns justify-self:end, a lone entry wraps. Offline.
  Prediction: ticket, catalogue, cv, form, invoice_0002 move; only the
  ticket visibly.
2 one grid across side-by-side Zones — render._band: unframed, unfilled,
  line-drawn PAIRS Zones sharing >= 2 printed lines drawn as one unit,
  each Title a line at its printed place, implied entries on their
  role's line, an unplaced label over its value by the page's habit.
  Offline. Prediction: only the ticket — route row on one line, a
  four-column grid.
3 a drawn strip is one container — render._filled (a solid fill drawn
  once behind the rows it holds), furnish's band across a Zone's top
  for solid fills, a heading's size from its lines. Offline. Prediction:
  only the ticket — one strip, the stub's strip, BOARDING PASS on one
  line.
4 no Zone from a drawn fill's edge — _cover_the_page ignores the solid
  fills furniture finds; locate.display_words ignores one-character
  words as blockers; locate._from_lines boxes a claimed line by all its
  words. Prove with the layout front (only the ticket's Zones move),
  rederive (4b/4c change nothing on the twenty), replay (only the
  ticket ASKED DIFFERENTLY, 22 -> 19 calls), then a targeted run on the
  ticket. Stop and ask if a moved crop is answered differently.

Judge every step by eye: sheets against the previous step's run, each
moved page better / same / worse with a sentence; the six held-out pages
in their own lines; scores recorded, never argued from; vanished read as
a pointer. Each step its own commit with its tests; every new IR-writing
step added to tools/rederive.py. Report each step with what the pages
look like and the sheet paths; continue unless a page got worse, then
stop, show it, ask.

Then register §7's prediction in the spec (step P), re-taking every
number at the last commit, and run ONE sweep, S12-sweep, over all 21:
about 2h20m, started detached (docs/status.md's loop has the line). Do
not touch tools/iterate.sh while it runs. Check the prediction, open
all 21 sheets against S12-0-replay, and report in the error-analysis
format — the ticket first, against §1's table, row by row. Whether
S12-sweep becomes the baseline is Alessandro's decision.
```
