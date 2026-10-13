# Draw what the page draws — its marks, lanes, width and type

**Status: planned 2026-10-13, not started. Issue #35.** This is the report
notebook Alessandro asked for after the sweep over the widened corpus: every
fault found, traced to its cause, grouped into what should be solved
together, and the pipeline and workflow changes the run argues for. It is
the handover material for implementing it from a cleared chat: §5 is the
plan, group by group, and the last section is the prompt to start with.

**Reading order for the implementing session:** decisions and "How to work"
below → §1 (what each page shows, and why) → §3 (the groups) → §4 (the
workflow changes) → §5 (the plan) → §8 (where things are in the code) →
§9 (rules).

Alessandro's decisions, 2026-10-13:

1. **`S7-sweep` is the baseline, all twenty-one documents**, frozen as
   `tests/frozen/s7-result/`. Its README has the provenance and the three
   loops, each proved 21 of 21.
2. **The findings card leaves the page:** "move it out of the document
   entirely (into report.html only)".
3. **A photographed page is drawn at its paper's share of the picture:**
   "draw the photographed receipt at the paper's share of the picture
   preserving aspect as possible". It applies to every page `rectify` finds
   photographed, so the ticket too.
4. **The corpus grows by adding:** "add new ones to be meaningfully
   different, do not replace the ones we have". Six were added on
   2026-10-13 and are held out — see "How to work".
5. This notebook groups the faults "to solve together" and explores
   whether the workflow needs steps added or changed. §3 is the grouping,
   §4 the workflow.
6. **Implement the groups in order, one after another, then one full
   end-to-end sweep at the end** to see the result — "we sweep at the end
   to check if improved wrt timetable". No sweep in between. §5 is the
   plan.

---

## How to work

**Carried over from spec 0011:**

- **By eye.** Every step ends with sheets for **all twenty-one documents**
  against the previous step: `tools/visual_review.py <run> --previous
  <previous step's run>`. Open every sheet whose render moved. Judge each
  page better / same / worse, with a sentence naming the element. That
  judgement is the gate.
- **Scores are recorded, never gating, never argued from.** The one number
  read is the report's `vanished` list: a pointer to a page to open, because
  content must match absolutely.
- **Report each step to Alessandro**: what the pages look like, the
  `report.html` path, the sheets that moved. Continue unless a page got
  worse; then stop, show it, ask. Commit each step.

**New for this spec: the six are held out.** `letter_0016`, `pricing_0017`,
`paper_0018`, `timetable_0019`, `ticket_0020` and `certificate_0021` were
authored after every measure in the pipeline was tuned. In their first
conversion they found four measures that held on the fifteen and fail on a
page they had not seen (§1b). So:

- Develop each step on the fifteen.
- Then open the six's sheets and **report them in their own lines**.
- A change that fixes a fault on the fifteen and breaks one of the six is
  tuned to the fifteen, not general. Say so; do not ship it as a win.

---

## 1. What the review found

### 1a. Alessandro's notes on `S6-sweep` — the fifteen, unchanged in `S7-sweep`

`S7-sweep` reproduced the fifteen byte for byte, so his notes stand. Each
was traced on 2026-10-13.

| document | what he saw | what is actually happening | group |
|---|---|---|---|
| `statement_0006` | an "Unresolved" card on top | this system's findings panel: two Probes that did not reconcile, because the model misread `1,144.30` and `216.08` | G1 |
| `receipt_0010` | the same card | the findings panel: 2.1% of the page's ink outside every region | G1 |
| `nonlatin_0014` | `myDATA` highlighted | the inline-runs pass returned a `mark` run; the page prints no highlight | G2 |
| `cv_0013` | (same, found in the analysis) | `native` highlighted, the same way | G2 |
| `newsletter_0008` | layout there, "minor lines and style elements" missing | its two vertical column rules are found by `structure._rules` and drawn nowhere | G3 |
| `darkdeck_0009` | the four tiles different heights | the source's `.tiles` is a flex row that stretches its tiles to one height; the render sizes each to its own content | G4 |
| `darkdeck_0009` | the risks card runs to the bottom of the column beside it | the page is drawn in an 832px column (`.doc { max-width:52rem }`) against the source's 1000px, so the card's text wraps longer | G5 |
| `menu_0012` | section titles not centred | a row cell's alignment does not come from its box, and small capitals are drawn at x-height (10.9px against 15px) | G6, G7 |
| `menu_0012` | the right column's notes on the dish's line, the left column's under it | the right column was read as a three-column table (caveat on Zone 2), so each note is a cell beside its dish | later (§7) |
| `cv_0013` | sidebar text not centred in the dark box | the sidebar lane is drawn with no inset; the source pads it 26px 20px | G4 |
| `cv_0013` | no dark line under the main column's section titles | `main h2 { border-bottom:2px solid }`. The rule finder finds all three; `structure.separators` keeps only rules outside every Zone, and these are inside one. The sidebar's own rules are not found at all, because the finder compares each pixel with the page's ground, and on a dark fill every pixel differs from it | G3 |
| `catalogue_0015` | the layout inside each card | `.card .foot` sets price, unit and stock on one line; the card is read as pairs and drawn stacked | G4, G6 |
| `catalogue_0015` | the picture's texture and colour | the picture area is a hatched fill (`repeating-linear-gradient`) with no type, so no Zone holds it and nothing draws it | G3 |

### 1b. The six new pages — held out, their first conversion

Sheets in `debug/runs/S7-replay/_review/`.

| page | verdict | what is right | what is wrong |
|---|---|---|---|
| `paper_0018` | **close** | serif read; two columns; the bar chart from its pixels; the three-rule table; the footnote | title printed twice; small-capital heads bold and left; the equation run into its paragraph; no rule between the columns; justified text and indents lost; authors left, not centred |
| `letter_0016` | **close** | letterhead and address blocks side by side; date block; paragraphs; footer rule | the 3px green letterhead rule thin and grey; `hal denpryce` drawn as a blue link; `08812274` highlighted; script signature drawn italic sans; `Enc.` and `cc:` joined; addressee bold; justified text lost; lines 786px wide against 707 |
| `certificate_0021` | words all there, **look lost** | body centred; the two signature blocks either side | every line gold; sans for Georgia; double frame, signature lines, name rule and round seal missing; heads left; the course name not bold; `Helena Brandt COURSE LEADER` on one line |
| `ticket_0020` | words mostly there, **layout lost** | photographed page read; labels over values | every line teal; `BOARDING PASS` read `BOARDING FOUR`; the stub stacked, not beside; `OSL` and `TRD` small; the QR block and the plane lost; drawn as a full white page |
| `pricing_0017` | **broken** | heading, subline and note; most of the tick lists | three cards drawn as two lanes, the middle card halved (`MOST POPUL` / `OST POPULAR`, `£12` apart from `/ user / month`); Starter's text inside Team's card; the Monthly/Annual toggle a bulleted list |
| `timetable_0019` | **content lost** | title, tutor line, header row | five of seven lesson rows, every room line, `Lunch` and the legend gone — **24 words vanished** — and the table marked complete |

**Their causes, each measured on 2026-10-13:**

- **Timetable — the grid count.** `preprocess.table_grid` on the extraction
  crop measures **4 rows and 1 column** for a table of 8 rows and 6 columns,
  and the prompt asks for exactly that. The model returned 4 rows, as it
  always does with a count. Two reasons, both drawn decoration:
  - the dark header fill runs the table's full width, so the projection
    across finds one band, one column;
  - the 4px colour bars of the double lessons span two rows each, and with
    the hatched lunch band they join 09:00 to 14:10 into one row band.
- **Timetable — no warning.** `printed_lines` is the same projection, so the
  shortfall check counted 4 printed lines, met 3 rows read, and found
  nothing missing. The check and the hint share their blind spot.
- **Pricing — two lanes.** `style.rectangles` finds all three cards. The
  middle one measures 0.300 × 0.650 of the page and the others 0.291 ×
  0.627: its 2px accent border, its shadow and its ribbon make it bigger.
  `SAME_SIZE` (0.01) then matches only the outer two as copies. A grid of
  two puts its split halfway between them, at **0.50**, which runs through
  the middle card, and spec 0009 B cuts its Zones there.
- **Certificate — gold.** `rectify` marks the page **`warped`**: its double
  frame is taken for the edges of a photographed sheet. On a photographed
  page each entry's colour and weight are deliberately left unread, so
  every entry draws in the page's ink. The page's ink is the dominant
  colour of every ink pixel, and gold — frame, seal, ornaments, the guild's
  name — is **27%** of them.
- **Certificate — sans.** Measured `sans`, cause not traced. Retake it after
  the photograph test is fixed: the warp resamples the page, which may be
  what blurs the serifs.
- **Ticket — teal.** A real photograph, correctly `warped`. Its ink is
  teal, because the two teal strips are **24.5%** of its ink pixels and the
  dark type 11.5%.
- **Ticket — the stub.** Its divider is a light dashed rule, and the rule
  finder finds **0 rules** on the page, so nothing makes a lane.
- **Paper — the title twice.** The caption pass took the first printed line
  of the two-line title as the Zone's Title. The Block holds the whole
  title. `wire._without_title_echo` removes exact repeats only.
- **Letter — the rule.** `Document.separators` is a list of heights. A rule
  has no extent, thickness, colour or style in the IR, so every rule is
  drawn as the house's thin grey line across the page.
- **Certificate — the lines not drawn.** The rule finder finds 3 rules;
  `separators()` keeps only rules wider than half the page, and the name
  rule (440px) and signature lines (250px) are narrower.
- **Not traced:** whether the equation, `Enc.`/`cc:` and `Helena Brandt` /
  `COURSE LEADER` were joined by the model or by the reflow. Trace before
  building G6's second item.

### 1c. Two faults on many pages — both decided

**The findings card**, on 9 of 21 pages:

| document | what the card says |
|---|---|
| `certificate_0021` | 32.5% of the page's ink outside every region — the frame |
| `ticket_0020` | 14.2% outside every region — the QR block, the plane, the stub's strip |
| `pricing_0017` | five patches outside every region, 0.5% to 3.2% each |
| `form_0007` | 2.9% outside every region |
| `receipt_0010` | 2.1% outside every region |
| `cv_0013` | 0.6% outside every region |
| `statement_0006` | two Probes that did not reconcile |
| `darkdeck_0009` | two Zones classified pairs and re-read as prose |
| `menu_0012` | two tables whose rows came back wider than their header |

**Highlights**: six `mark` runs on four pages — `cv_0013` `native`,
`nonlatin_0014` `myDATA`, `letter_0016` `08812274`, and `pricing_0017`
`POPULAR`, `£144` and `14-day`. **None of the twenty-one sources prints a
highlight.**

### 1d. Measured across all twenty-one, recorded

**Width.** The extent of the ink across each page, source against render:

- every render spans 769–831px except `receipt_0010` (467) and
  `invoice_0002` (808): the house's 832px column;
- the sources span 299px (the receipt's paper) to 1101px
  (`invoice_0002`);
- the render is 0.73× the source's width on `invoice_0002`, 0.87× on the
  certificate and 0.89× on darkdeck, and 1.11× on the letter and 1.56× on
  the receipt.

**Rules found and drawn on the six:**

| page | rules found | vertical | inside a Zone | drawn |
|---|---|---|---|---|
| `letter_0016` | 2 | 0 | 0 | 2, as thin grey lines |
| `paper_0018` | 7 | 1 | 3 | 2 |
| `certificate_0021` | 3 | 0 | 0 | 0 |
| `pricing_0017`, `timetable_0019`, `ticket_0020` | 0 | 0 | 0 | 0 |

On the fifteen, measured at `S6-sweep` and unchanged: cv 3 rules, all inside
a Zone; newsletter 9, 2 vertical; statement 6, 4 vertical (the tiles' accent
bars); form 8, 7 inside a Zone.

**`vanished`: 55 words.** 26 are the fifteen's, unchanged since `S5-sweep`
(17 model misreads, 6 on the form's dropped line, 2 cv skills read as
pictures, 1 dropped chip). Of the six's 29, 24 are the timetable's; 3 on
the paper are not lost (Unicode superscripts scored as one token with their
word); 1 is the letter's split email and 1 the ticket's `PASS`.

---

## 2. Faults by stage

| stage | faults | pages |
|---|---|---|
| Rectify | a drawn frame taken for a photographed sheet | certificate |
| Measure, before the model | grid count joined by fills and bars; the shortfall check blind with it | timetable |
| Layout / structure | an emphasised card breaks a grid of copies, the split cuts it; a dashed divider is no lane | pricing, ticket |
| Style | ink measured over decoration; rules, frames, bars and fills not recorded; small capitals at x-height; no script face; face per page only; one face misread | certificate, ticket, letter, paper, cv, newsletter, statement, form, catalogue, timetable, menu, report |
| Render | the findings panel; one 832px column; a photographed page full-page; no lane inset; copies of uneven height; cells not aligned from their boxes; no justification or indent | all |
| Wire / inline | highlights the page does not draw; a Title echoing the start of its Block | cv, nonlatin, letter, pricing, paper |
| Extract (the model) | misreads; menu notes as a column; lines joined (not traced) | statement, ticket, letter, menu, paper, certificate |

---

## 3. The groups — what to solve together

Each group is one mechanism that closes several faults at once.

### G1 — The findings leave the page (decided)

- **Closes:** the card on 9 of 21 pages; Alessandro's statement and receipt
  notes.
- **What:** `render` stops drawing `_findings`. `report.html` shows, beside
  each document's pair, what the card said: Unresolved items, caveats and
  Probes, from the embedded IR. The IR keeps every field; only where it is
  shown moves.
- **Expect:** heights fall on those nine pages. The panel is already outside
  the projection, but height and T5 sample the screenshot.
- **Runs on:** rederive. Renderer and report only.

### G2 — A highlight only where the page draws one

- **Closes:** six `mark` runs on four pages; the `myDATA` note.
- **What:** keep a `mark` run only if the page draws a fill behind those
  words. Spec 0011 step 4b's chip measurement already finds a filled box
  round a Cell's words. Otherwise the run becomes plain text. No word
  changes: marking never changes the words (an invariant).
- **Runs on:** rederive.

### G3 — Furniture: one record of everything the page draws that is not type

This is the answer to Alessandro's question "do we have a step that checks
or does that?" for separator lines. **No.** Six readers each see part of
it, and none records what it sees:

| what exists | what it sees | what it does with it |
|---|---|---|
| `preprocess.content_ink` | thin, long components | deletes them, so type can be measured |
| `structure._rules` | rules, on the page's ground only | vertical ones become column dividers |
| `structure.separators` | wide horizontal rules outside every Zone | stores their **heights**, nothing else |
| `style.rectangles` | boxes from 0.4% to 80% of the page | frames for Zones, grids of copies |
| `looks` (4c, 4d) | rules and fills between table rows, leader dots | draws them inside tables |
| `fields` (step 3) | form boxes, tick boxes, underlines | draws the form's fields |

None records a rule's extent, thickness, colour or style (dashed, double).
None sees side bars, hatched fills, round shapes or a rule on a dark fill.
And none of the measurements of *type* — the grid count, the page's ink, the
photograph test — leaves the decoration out.

**What it is.** One new pixel-only step on the whole page, recording each
drawn mark in a new IR field, `Document.furniture`. Each record holds:
- a kind — rule, frame, side bar, fill or shape;
- a box;
- a thickness;
- a colour;
- a style — solid, dashed, dotted, double or hatched;
- the Zone or region that holds it.

It is measured in the polarity of the ground it sits on, so the cv
sidebar's rules count. For example, the letterhead becomes "a rule, x 80 to
788, 3px, green, solid", and the certificate "a frame, 6px double, gold,
round a 1px frame".

**Two halves, because their costs differ:**

| half | consumer | closes | runs on |
|---|---|---|---|
| **G3a** | the renderer draws each record as measured | the letterhead's rule; the abstract's rules; cv's title rules; the certificate's frame, name rule and signature lines; invoice_0001's rule over `Total`; the column rules of newsletter and paper; the side bars of statement's tiles, TL;DR, form's heads and timetable's lessons; the hatch of catalogue's pictures and timetable's lunch; `OFFICE USE` | rederive |
| **G3a** | `style.measure` takes the ink over type only, with the furniture masked out | the certificate's gold and the ticket's teal | rederive |
| **G3b** | `table_grid` and `printed_bands` project ink with the furniture masked out | the timetable's 4 rows and 1 column | **sweep** — it changes a prompt |
| **G3b** | `rectify`'s photograph test: a quad with the same ground on both sides is a drawn frame, not a sheet's edge | the certificate read as a photograph | **sweep** — it changes every crop |
| **G3b** | `structure` takes a dashed vertical rule as a lane divider | the ticket's stub beside its pass | **sweep** — it changes Zones |

`structure.separators` becomes the subset of the furniture that lies between
Zones, and should be folded into it rather than kept beside it.

### G4 — Boxes and lanes as the page builds them

- **A grid's split never crosses a drawn box**, and a row of drawn boxes
  whose tops align is a row of copies even when one of them is emphasised
  by its border, shadow or ribbon. Closes pricing. **Sweep**: it changes
  Zones.
- **Copies in one row are drawn one height.** Closes darkdeck's tiles and
  pricing's cards. Rederive.
- **A filled or framed lane keeps its inset**, measured from the box's edge
  to its type. Closes the cv sidebar; also the certificate inside its frame.
  Rederive.
- **A card's entries are placed by their boxes.** Closes catalogue's price,
  unit and stock on one line, and pricing's price beside its unit. Shares
  its mechanism with G6. Rederive.

### G5 — The page's width, and a photographed page at its paper's share (decided)

- **Width.** Replace the fixed 832px column (`.doc { max-width:52rem }`)
  with the source's own content width and margins, from `Source.width` and
  the ink's extent. §1d measures how far off the column is.
  - `render.py` keeps `document.page_px` and ignores it. Its comment says
    the width was shelved until "a real column model" existed. Spec 0008's
    lanes are that model, so the condition is met.
  - **Probed offline earlier in the session that wrote this spec, not
    committed:** with content width from the page, darkdeck's risks card
    ends with its text, and invoice_0002's title fits on one line.
- **A photographed page is drawn at its paper's share of the picture,
  aspect kept.** This needs the paper's quad recorded in the IR: `Rectified`
  carries `image`, `source`, `plain`, `warped` and `inverted`, and no quad.
  Closes the receipt and the ticket.
- **Runs on:** rederive. Rederive re-reads the source picture, so a new
  pixel field is offline.

### G6 — Every entry placed by its own box

Spec 0011 step 2 placed 847 of 868 entries on the fifteen. This group uses
those boxes.

- **Each Cell aligned from its own box.** Closes:
  - the receipt's quantities and totals;
  - statement's tiles;
  - menu's heads;
  - invoice_0002's labels;
  - report's footer;
  - the heads and authors of paper and certificate.
- **Lines kept apart where the page breaks them.** Closes paper's equation
  with its number flush right, the letter's `Enc.` and `cc:`, and the
  certificate's name over its title. **Trace first** whether the model or
  the reflow joined them (§1b).
- **Justified paragraphs and first-line indents**, read from where each
  line's box starts and ends. Closes paper and letter.
- **Runs on:** rederive.

### G7 — The type's own features

- **Small capitals**: a line whose letters stand no taller than its
  x-height is drawn as `small-caps` at its cap size. Closes the heads of
  menu, newsletter and paper, the certificate's title, and darkdeck's and
  catalogue's labels.
- **Script**: a fourth face class, for joined handwriting letters. Closes
  the letter's signature, and the certificate's name and signatures. It is a
  face, not a document type, so ADR 0001 holds.
- **Face per entry where it differs from the page's.** Closes the letter's
  serif name on a sans page, and report's sans table on a serif page.
- **Retake the certificate's face** once G3b's photograph test stops
  warping it.
- **Runs on:** rederive.

### G8 — A Title that echoes the start of its Block

- **What:** when a Zone's Title is the start of its first Block's first
  line, the caption pass read one line of a heading that runs to two. Keep
  the Block's full text, and drop the Title.
- **Closes:** paper's doubled title.
- **Runs on:** replay — a wire change.

### G9 — A table that loses rows says so

- **The problem:** the shortfall check and the grid hint read one
  projection, so a wrong count passes both (§1b, the timetable).
- **The witness:** give the check one that is not the projection. Spec 0011
  step 2's locator already returns every printed line's box. A located line
  inside a Zone that no Cell claims is **reported**, never inserted. This is
  spec 0011 §4's follow-on 2.
- **Why it may be built:** CLAUDE.md says not to build a third honesty
  detector "without a new kind of evidence". Located lines are that kind:
  boxes from an independent reader, matched against the model's words.
- **Runs on:** rederive for the report. G3b's fix is the repair.

---

## 4. The workflow — what to add, what to change

### 4a. In the Conversion

Today's stage order (`orchestrator.Conversion.run`):

```
rectify → _ask_opening → _measure_style → _layout → _classify →
_draw_figures → _extract (+ vetoed captions, shortfalls) →
_measure_chrome → _measure_type → _find_separators → _read_rhythm →
_locate → _read_fields → _read_looks → _audit → _climb_ladders
```

Proposed:

| change | kind | where | why |
|---|---|---|---|
| **`_find_furniture`** | **add** | right after `rectify`, before `_measure_style` | everything after it can leave the decoration out: style's ink, the grid count, structure's lanes |
| the frame test | change | `rectify` | a drawn frame is not a sheet's edge (G3b) |
| ink over type only | change | `_measure_style` | the furniture is masked out (G3a) |
| grid count and printed lines without furniture | change | `table_grid`, `printed_bands` | the timetable (G3b) |
| a split never crosses a drawn box; emphasised copies | change | `structure._grids` | pricing (G4) |
| `_find_separators` folded into the furniture | change | — | one record of rules, not two |
| unclaimed located lines reported | add | after `_locate` | G9 |
| a mark run kept only over a fill | change | `_read_looks` or the wire | G2 |
| fields before rhythm | change | `_read_rhythm`, `_read_fields` | step 3 turns `form_0007`'s Zone 5 from a table into pairs after step 1 has skipped it as a table; a rederive therefore differs in one IR field (s7-result's README) |

**Every new IR-writing step goes into `tools/rederive.py`.**

### 4b. In the loop around it

1. **A replay must say when a call was asked differently.**
   - Today `tools/replay_run.py` serves answers by pass and order, and never
     reads the prompt or the picture (`replay_run.KEPT`: "serving by pass
     and order never reads it").
   - G3b changes the timetable's prompt from 4 rows to 8 without changing
     the number of calls. A replay would serve the old 4-row answer and
     report a document that did nothing. That is CLAUDE.md's "a flag that
     does not arrive looks exactly like a flag that does nothing".
   - **Add:** freeze a hash of each call's prompt and picture beside its
     answer. Replay marks each changed call **ASKED DIFFERENTLY — not a
     measurement**.
   - Then the documents a change will move in a sweep are listed before the
     sweep, and the sweep's prediction can name them.
   - The trace already holds each call's prompt, but not its picture.
2. **Write the six's answers into the corpus guards.** Three tests hold
   them out today, each naming them (`tests/test_structure.py` `EXPECTED`,
   `tests/test_style.py`'s rectangle lists, `tests/test_back_half.py`'s
   Probes over a floor).
   - Write each answer from the source HTML: what the page *is*, not what
     the render does.
   - Mark the ones today's code fails as expected failures naming the group
     that fixes them. For example, pricing is a grid of three, with splits
     near 0.34 and 0.66 — G4, step U.
3. **A furniture overlay**, like `tools/locate_overlay.py`: the page with
   every furniture record drawn on it, so G3 is judged by eye before
   anything is drawn from it.
4. **The sweep now takes 2h16m** — 21 documents, 751 calls. A background
   task in this harness stops at 2 hours, so start the sweep detached
   (`nohup … & disown`) and wait on its log. CLAUDE.md's loop says 1¾ hours
   and fifteen documents; update it.
5. **A crash in a sweep costs no model time.** The bake-off writes every
   call's answer even when a conversion raises, and the replay converts it
   once the bug is fixed: pricing, on 2026-10-13. Keep it that way.

### 4c. What does not change

- **The corpus**: twenty-one documents through this spec. The six showed
  that held-out pages find faults; more is for after this spec, if
  Alessandro wants it.
- **The scorer and the review tool.**
- **The model and its prompts**, except where G3b, G4 and G8 change what is
  asked.

---

## 5. Work plan — group by group, then one sweep

**Decided 2026-10-13 (Alessandro): implement the groups in order, one after
another, and run one full end-to-end sweep at the end** to see the result —
the timetable's repair included. No sweep in between.

**Each group is built in two halves when it has an upstream part.**
- **The downstream half** — everything after the model's answers — is built
  in the group's turn and measured offline, one change apart from the step
  before.
- **The upstream half** — anything that changes a crop, a Zone or a prompt
  — cannot be measured by rederive or replay: those loops serve the
  baseline's answers to the baseline's questions. So the upstream halves of
  G3 and G4 are built together in step U, just before the sweep, and the
  sweep measures them.

Building an upstream half in its group's turn would leave every later
offline step measured against a mixture: some pages with the new crops and
the old answers.

| step | group | what | runs on | done when — on the sheets |
|---|---|---|---|---|
| 0 | — | the loop work of §4b: ASKED DIFFERENTLY in the replay; the six's answers in the three guards, expected failures naming their group; fields before rhythm | tests, replay, rederive | replay of `s7-result/` 21 of 21 byte-identical **and** 0 calls asked differently; rederive of `form_0007` byte-identical too |
| 1 | **G1** | the findings card off the page, into `report.html` | rederive | no page draws the card; `report.html` shows each document's findings beside its pair |
| 2 | **G2** | a `mark` run kept only over a fill | rederive | no highlight on cv, nonlatin, letter or pricing; no word changed |
| 3 | **G3a** | `_find_furniture` and `Document.furniture`; the overlay tool; the renderer draws every record; style's ink over type only | rederive | the letterhead's 3px green rule; cv's title rules, the sidebar's too; newsletter's and paper's column rules; the certificate's frame, name rule and signature lines; the side bars of statement, TL;DR, form and timetable; catalogue's and the lunch row's hatch; the certificate's and the ticket's type dark |
| 4 | **G4**, drawing | copies in a row one height; a filled or framed lane's inset; a card's entries by their boxes | rederive | darkdeck's tiles one height; cv's sidebar text inset from its edge; catalogue's price, unit and stock on one line |
| 5 | **G5** | the page's own width and margins; a photographed page at its paper's share, the quad in the IR | rederive | every page's lines wrap where the source's do; the receipt and the ticket drawn at their share of the picture |
| 6 | **G6** | each Cell aligned from its box; lines kept apart where the page breaks them (trace first); justification and indent | rederive | the receipt's totals, statement's tiles, menu's heads, invoice_0002's labels, report's footer as printed; paper's equation on its own line with its number at the right |
| 7 | **G7** | small capitals; a script face; face per entry | rederive | menu's, newsletter's and paper's heads in small capitals; the letter's signature and the certificate's name in script |
| 8 | **G8** | a Title echoing the start of its Block | replay | paper's title printed once |
| 9 | **G9** | located lines no Cell claims, reported | rederive | `report.html` names the timetable's unread rows |
| U | **G3b**, **G4**'s split | grid count and printed lines without the furniture; a frame is not a sheet; a dashed vertical rule makes a lane; a grid's split never crosses a drawn box, an emphasised copy still a copy | `tools/layout_front.py`, replay with ASKED DIFFERENTLY | the replay marks exactly the documents predicted, every other document is byte-identical to a replay at step 9's commit, and §6's prediction is registered in this spec |
| S | — | **`S8-sweep`**: all twenty-one, shipped defaults, started detached | the model | §6 checked; all 21 sheets opened against the baseline; the outcome written in §5 format |

**Order inside the plan.** G9 comes before U on purpose. At step 9 the
report names the timetable's unread rows at the baseline. If U repairs
them, the sweep's report no longer names them, and that is the test.

**What the final review compares.** Open the sweep's sheets against the
baseline: `tools/visual_review.py debug/runs/S8-sweep --previous
debug/runs/S8-0-replay`. `S8-0-replay` is `s7-result/` replayed, byte for
byte, in the run layout the review tool reads. Recreate it at step 0 if it
is gone.

---

### Outcome — the baseline, proved 2026-10-13 at `92ec769`

`tools/replay_run.py tests/frozen/s7-result --label S8-0-replay`: **21 of 21
byte-identical**. `tools/rederive.py` (`S8-0-base`): 20 of 21 byte for byte,
`form_0007` differing in Zone 5's `align` only (`null` → `"left"`), its page
identical outside the IR.

### Outcome — step 0, the loop work, 2026-10-13

- **ASKED DIFFERENTLY.** Every recorded call carries `asked`, a hash of its
  prompt, picture and schema (`trace.asked_of`, set by the bake-off's
  transport); the frozen answers keep it (`replay_run.KEPT`); the replay
  pairs today's calls with the run's by pass and order, as it serves them,
  and names each one that moved as `NN_<pass> prompt|picture|schema`.
  `s7-result/answers/` carries the hashes, taken from a replay at this
  commit — all 751 prompts hash as `S7-sweep`'s own trace recorded them.
  **Armed and proved:** a scratch wrapper adding 4 rows to the table hint
  replayed `timetable_0019` and `invoice_0001` **byte-identical on the old
  answers — the trap — and marked both ASKED DIFFERENTLY**, naming
  `09_table` and `17_table`, `18_table`.
- **Fields before rhythm**, in the Conversion and in `rederive.py`. Replay
  of `s7-result/` (`S8-0-step0`): 20 of 21 byte-identical, `form_0007`
  differing in Zone 5's `align` only, page identical; **0 calls asked
  differently, 0 unhashed**. Rederive (`S8-0-step0-rd`) and that replay
  agree **byte for byte on all 21**. No page moved, so no sheet to open.
- **The six's answers in the three guards**, written from their HTML.
  Structure: pricing a grid of three (splits 0.345, 0.655), paper two
  columns at 0.501, the ticket two lanes at its dashed rule (0.716 of the
  rectified pass), letter, timetable and certificate single. Rectangles:
  pricing 3 cards, the timetable's ruled table 1, the other four none.
  Probes: none of the six prints arithmetic, none fails. **Two expected
  failures, strict, each naming its step:** pricing (G4's split, step U)
  and the ticket (G3b's dashed rule, step U).
- **Found on the way, not in §1:** the rectified ticket cuts its top strip
  through the middle of `BOARDING PASS` — the quad `rectify` finds starts
  below the pass's top edge — so `BOARDING FOUR` is the model reading half
  a word, not a misread of a whole one. §7 files it under the model; it
  belongs to Rectify.

1020 tests pass, 2 expected failures; `mypy src/` clean.

### How each step below was measured

Each step is measured on `s7-result/` twice, at the step's commit: a
rederive (`S8-<n>-<name>`) and a replay (`S8-<n>-<name>-replay`). **The two
agree byte for byte on all 21 at every step** unless the step says
otherwise — the check that `rederive.py` carries every IR-writing step. A
page has *moved* when the report's render of it differs in a pixel from the
previous step's (`_renders/`); the sheets are built for all 21 against the
previous step (`tools/visual_review.py <run> --previous <previous run>`)
and every moved one is opened.

### Outcome — step 1, G1: the findings leave the page, 2026-10-13

`render` draws no card; `report.flagged` writes what it said — Probes,
Gaps, Failures, Shortfalls, Caveats, from the embedded IR — under "What the
conversion flagged" beside each pair in `report.html`, all 21 sections.
The page's stylesheet lost the card's rules, so every page's bytes moved;
**nine pages moved in pixels, exactly the nine that drew the card**.

| page | against step 0 |
|---|---|
| `statement_0006`, `receipt_0010`, `cv_0013`, `form_0007`, `darkdeck_0009`, `menu_0012` | **better** — the page opens on its own masthead; nothing else on it moved |
| new: `certificate_0021`, `pricing_0017`, `ticket_0020` | **better**, the same way |

`vanished` 55, unchanged. Run `S8-1-findings`, `report.html` there.

### Outcome — step 2, G2: a highlight only where the page draws one, 2026-10-13

`looks.unmarked`, inside `looks.read`: a `mark` run stays only where the
Cell's box holds a band of columns filled edge to edge in another colour
than the Cell's own ground, `HIGHLIGHT` (1.2) line heights wide; otherwise
it becomes plain text and joins its neighbours. A chip behind the whole
Cell is its ground, so a mark inside a ribbon or a button goes too.
Measured over all 1032 placed Cells first: type alone fills a column for at
most 0.71 of a line height, and the corpus's one partial fill —
`sample_css_0004`'s `<style>` code span — is 4.59.

**Six runs unmarked, on exactly the four pages; four pages moved.**

| page | against step 1 |
|---|---|
| `cv_0013` | **better** — `native` no longer on a yellow band |
| `nonlatin_0014` | **better** — `myDATA` plain, as printed |
| new: `letter_0016` | **better** — `08812274` plain |
| new: `pricing_0017` | **better** — `£144` plain; `POPULAR` and `14-day` were inside the ribbon and the button and look the same |

No word changed; `vanished` 55. Run `S8-2-marks`.

### Outcome — step 3, G3a: furniture found and drawn, 2026-10-13

**Found.** `furniture.find`, in `_measure_style` straight after `rectify`:
rules (solid, dashed, double), frames and fills (plain, hatched), from
pixels, in the polarity of whatever ground each sits on, every threshold in
glyph heights. **301 records on the 21 pages**: 228 solid rules, 7 dashed, 1
double; 33 frames and 1 double frame; 20 fills, 11 hatched. Judged by eye
first, on `tools/furniture_overlay.py`'s overlays. A barcode's bars are a
texture, not rules (`BARS`); a hatch needs 2 glyphs, a plain fill 3, so
the timetable's 22px lunch row is found.

**Placed and drawn.** `_place_furniture`, after `_read_fields`, sets each
rule's Zone. `furnish.anchor` gives each record the element whose border it
is — the page, a card, a lane, a Zone, its Title, a Block, a pair, a cell,
a row, or the gap between two rows of a stack — and `render` draws it at its
own width, style and colour. Nothing is placed by coordinates. **121 of the
301 are drawn**; the rest are drawn already by something else (a field's
box, a table's lines, a Zone's fill) or lie inside a figure.

**The ink is the type's.** `style.measure(without=furniture.mask(...))`: the
certificate's ink went gold to dark brown, the ticket's teal to near black,
form's grey to black, nonlatin's blue to black. That last one exposed a gap:
nonlatin's Titles were blue only because the page's ink was. **A Title's
own colour is now measured** — `Zone.title_color`, by `looks`, over the
first printed line above the Zone's first entry — and drawn where it differs
from the ink. `structure.separators` is kept, because `rhythm` and `fields`
read it, but the render no longer draws it. Folding it into the furniture
would move `rhythm`'s runs, so it is left.

**20 pages moved in pixels; `sample_table_0003` did not.**

| page | against step 2 |
|---|---|
| `cv_0013` | **better** — rules under the main column's three headings, under the sidebar's five, and its four skill bars. EXPERIENCE's rule is only as wide as its Zone, which shares its line with `2021 — present` |
| `catalogue_0015` | **better** — the nine hatched pictures, the SKU chips printed on them, each card's name pushed below its picture. The page runs taller, as the source does |
| `form_0007` | **better** — ink black, not grey; `OFFICE USE` boxed; the rule under the title; the five heads' bars |
| `newsletter_0008` | **better** — the two column rules, the pull quote's rules above and below |
| `statement_0006` | **better** — the four balance tiles' side bars |
| `sample_semantic_0005` | **better** — the TL;DR bar |
| `invoice_0001` | **better** — the rule over `Total` |
| `menu_0012` | **better** — the short rule under `KITCHEN & CELLAR`; `To begin` and `Main courses` brown, as printed |
| `sample_css_0004` | **better** — the rule under `Sample HTML` blue; the card titles slate |
| `receipt_0010` | **better** — dashed rules over `Till 02` and over `THANK YOU` |
| `report_0011` | **better**, minor — the rule over the footnotes dark, as printed |
| `darkdeck_0009` | **better**, partial — the rule under `Platform review`, only as wide as that Zone |
| `nonlatin_0014` | **same** — body dark and Titles blue, as before, now each measured |
| `invoice_0002` | **same** — the panels' borders in their measured grey |
| new: `certificate_0021` | **better** — dark type, not gold; the gold double frame round the page; the name rule; both signature lines. The inner frame's sides are not drawn, because the page is still read as warped: G3b |
| new: `letter_0016` | **better** — the letterhead rule 3px and green |
| new: `paper_0018` | **better** — the abstract's rules black, the column rule, the table's top rule |
| new: `ticket_0020` | **better** — the type dark, not teal; the stub's dashed divider |
| new: `timetable_0019` | **better**, minor — lesson bars on the one lesson row it reads |
| new: `pricing_0017` | **same** — the toggle's top and bottom edges drawn as two rules; the cards unchanged (G4) |

No page got worse. `nonlatin_0014` did during the step, until the Title
colour went in. `vanished` 55. Run `S8-3-furniture`.

**Left for later steps.** The certificate's inner frame is four loose rules
until G3b straightens the page. A rule under a Title that runs on past its
Zone is drawn only as wide as the Zone. The timetable's lesson tints are
found as one fill across the grid. **G3b must mask a fill by its colour, not
its box**, or `table_grid` loses the type on it.

## 6. The sweep's prediction — to register at step U, before `S8-sweep` finishes

Register it in this section, with the commit, before the sweep ends:

- **Every call that step U's replay does not mark ASKED DIFFERENTLY comes
  back byte-identical** to `s7-result/answers/`. A miss names a change that
  moved something it was not meant to.
- **The documents it marks are the only ones whose answers can move.**
  Expect at least the timetable (its grid hint), the certificate (its crops,
  once it is not warped), pricing (its Zones) and the ticket (its lane).
  Name each one, with the calls marked.
- **Every document it does not mark renders byte-identical to a replay at
  step 9's commit**, because steps 1–9 are all downstream of the model.
- **The timetable returns its seven lesson rows**, and the 24 words come
  back.

Then report the sweep in §5 of spec 0011's format: where it gained, the
faults left by stage, the directions ranked, a recommendation. Lead with
the pages, the six in their own lines.

---

## 7. Not in this spec — later, and Alessandro's call

| fault | why not now |
|---|---|
| model misreads: `BOARDING FOUR`, `hal denpryce`, statement's two figures, the fifteen's 17 words | deterministic at `temperature: 0`; only a second reading reaches them — the Ladder and `CellState.DISPUTED`, or a second Engine |
| menu's right-column notes read as a third column | Extract; a prompt change and a sweep |
| darkdeck's P95 tile as a table, cv's skills as pictures | Classify; a prompt change and a sweep |
| form's tick note dropped by the pairs read | Extract → wire; G9 will at least report it |
| newsletter's drop-cap line drawn as a heading | Extract |
| the ticket's QR block and plane | ink outside every region; a figure Zone from it is the detector's work |
| superscripts as runs (paper's affiliations, report's footnote markers) | the IR has no superscript run |

---

## 8. Where things are

| what | where |
|---|---|
| stage order | `orchestrator.Conversion.run` (§4a) |
| rectify, and `warped` | `preprocess.rectify`, `Rectified` |
| the grid count and printed lines | `preprocess.table_grid`, `printed_bands`, `content_ink`; the hint in `engines/ollama.with_grid` |
| the page's palette | `style.measure` |
| rules and boxes | `structure._rules`, `_marked`, `separators`; `style.rectangles`, `MIN_RECT_SHARE` |
| grids of copies and their splits | `structure._grids`, `SAME_SIZE`; the cut, `structure.cut_at_edges` |
| per-entry type, colour, chips, rules in tables, leaders, spacing, face | `looks.read`, `_chip`, `_rows`, `_leaders`, `_blocks`, `_face` |
| entry boxes | `locate` (spec 0011 step 2); `tools/locate_overlay.py` |
| the findings panel | `render._findings`, `_findings_block`; `report.py` |
| the page column | `render.py` `.doc { max-width:52rem }`, `page_px` |
| the loops | `tools/rederive.py`, `tools/replay_run.py` (`KEPT`), `tools/layout_front.py`, `tools/visual_review.py` — its `--previous` reads a run directory, not a frozen one, so compare against `S8-0-replay` |
| the held-out guards | `tests/test_structure.py` `EXPECTED`; `tests/test_style.py` `TestFindingBoxesInTheCorpus`; `tests/test_back_half.py` |

A Zone printer is still worth writing first: load the IR from a
`document.html` (`id="doc-ir"`, `ir.Document.from_json`) and print each
Zone's index, kind, band and column, box, Title and contents. Every trace in
§1 started from one, written in a scratch script.

---

## 9. Rules that bind

- "How to work" above: by eye, numbers recorded, the six reported in their
  own lines.
- **Never cite a past run.** Take every picture and number in the session
  that reports it. The committed frozen directories are the exception, for
  what their READMEs say they are.
- **Any reviewed run covers all twenty-one documents.**
- Commit each step. A step whose sheets show a page worse is reverted or
  repaired before the next, and recorded.
- ADR 0001 (no document types) and ADR 0002/0005 (positions drive structure,
  never `position:absolute`) hold for every group.
- **Do not reopen** anything in `docs/status.md`'s "Closed, with evidence"
  without a new kind of evidence, and say which when that is the argument.

---

## Handover prompt — implement spec 0012 group by group, then one sweep (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0012-draw-what-the-page-draws.md end to end — the only open
work, issue #35. It is the report notebook from the 21-document sweep:
every fault traced to its cause (§1), the faults grouped G1-G9 (§3), the
Conversion and loop changes (§4), and the work plan (§5).

Alessandro's decisions, 2026-10-13: implement the groups in order, one
after another — G1 findings off the page, G2 highlights from pixels,
G3a furniture, G4 boxes and lanes, G5 width and the photographed page, G6
entries by their boxes, G7 type features, G8 the title echo, G9 unread
lines reported — then step U (the upstream halves of G3 and G4, which
change crops and prompts), then ONE full sweep, S8-sweep, over all 21. The
timetable's lost rows are judged at that sweep. No sweep in between.

Before any change, prove the baseline tests/frozen/s7-result/ (21
documents, 751 answers): tools/replay_run.py over it reproduces 21 of 21
byte-identical as debug/runs/S8-0-replay, and tools/rederive.py 21 of 21
identical pages (20 byte for byte; form_0007 differs in one IR field, its
README says why). Then do step 0, the loop work, first: the replay must
mark a call ASKED DIFFERENTLY when its prompt or picture changed, or step
U cannot be predicted.

Judge every step by eye, as spec 0011 did: sheets for all 21 against the
previous step's run, each moved page better / same / worse with a
sentence; scores recorded, never argued from; the vanished list read as a
pointer. The six new pages (corpus.NEW) are held out — report them in
their own lines, and treat a fix that helps the fifteen and breaks one of
the six as tuned, not general. Each step its own commit, every new
IR-writing step added to tools/rederive.py. Report each group to
Alessandro with what the pages look like and the report.html path, and
continue unless a page got worse.

Register §6's prediction at step U, before the sweep finishes. The sweep
takes about 2h16m: start it detached (nohup ... & disown; docs/status.md's
loop has the line) and wait on its log. Then check the prediction, open
all 21 sheets against S8-0-replay, and report it in spec 0011's §5
format, leading with the pages. Whether S8-sweep becomes the baseline is
Alessandro's decision. The standing rules are CLAUDE.md's and the spec's
§9.
```
