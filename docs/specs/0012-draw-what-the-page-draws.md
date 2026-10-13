# Draw what the page draws — its marks, lanes, width and type

**Status: planned 2026-10-13, not started. Issue #35.** This is the report
notebook Alessandro asked for after the sweep over the widened corpus: every
fault found, traced to its cause, grouped into what should be solved
together, and the pipeline and workflow changes the run argues for. It is
written to be implemented from a clean chat — its last section is the
prompt to start one with.

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

---

## How to work

**Carried over from spec 0011 — confirm with Alessandro at the start that
it still applies:**

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
   - Mark the ones today's code fails as expected failures naming the step
     that fixes them. For example, pricing is a grid of three, with splits
     near 0.34 and 0.66.
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

## 5. Work plan

| step | what | runs on | pages it should move |
|---|---|---|---|
| 0 | the loop work of §4b: the six's answers in the guards, replay's ASKED DIFFERENTLY, the furniture overlay; fields before rhythm | offline | none |
| 1 | **G1** findings into `report.html` | rederive | the nine |
| 2 | **G2** highlights from pixels | rederive | cv, nonlatin, letter, pricing |
| 3 | **G3a** furniture measured, in the IR, drawn; ink over type | rederive | letter, paper, cv, newsletter, statement, sample_semantic, form, invoice_0001, catalogue, timetable, certificate, ticket |
| 4 | **G5** width and margins; a photographed page at its paper's share | rederive | all; receipt, ticket |
| 5 | **G4**'s drawing half: copies one height, lane insets, card entries | rederive | darkdeck, cv, catalogue, pricing |
| 6 | **G6** alignment from boxes, lines kept apart (trace first), justification and indent | rederive | receipt, statement, menu, invoice_0002, report, paper, certificate, letter |
| 7 | **G7** small capitals, script, face per entry | rederive | menu, newsletter, paper, certificate, letter, report, darkdeck, catalogue |
| 8 | **G8** the Title that echoes its Block's start | replay | paper |
| 9 | **G9** unclaimed located lines reported | rederive | timetable among them |
| 10 | **upstream**: G3b (grid count, photograph test, dashed lane) and G4's split. Measure with `tools/layout_front.py` and the replay; ASKED DIFFERENTLY lists what the sweep will move | offline prediction | timetable, certificate, pricing, ticket |
| 11 | **one sweep, `S8-sweep`, all twenty-one** — register the prediction before it finishes (§6) | the model | all |

**Why this order.** The offline steps come first, each measured one change
apart from `s7-result/` by rederive in about a minute. The upstream changes
come last, predicted offline as far as possible, and are spent in one sweep.

**The one judgement call — Alessandro's.** The timetable is content lost,
the most severe fault here, and its repair is in step 10. If he wants it
earlier, step 10's grid-count change can go first and take its own sweep:
2h16m more.

---

## 6. The sweep's prediction — to register before `S8-sweep` finishes

- Every call that step 10's replay does **not** mark ASKED DIFFERENTLY comes
  back byte-identical to `s7-result/answers/`.
- The documents it marks are the only ones whose answers can move. Expect
  at least the timetable (its grid hint), the certificate (its crops, once
  it is not warped), pricing (its Zones) and the ticket (its lane).
- The timetable returns its seven lesson rows.

A miss on the first clause names a step that moved something it was not
meant to.

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
| the loops | `tools/rederive.py`, `tools/replay_run.py` (`KEPT`), `tools/layout_front.py`, `tools/visual_review.py` |
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

## Handover prompt — start of spec 0012 (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0012-draw-what-the-page-draws.md — the only open work, issue
#35. It is the report notebook from the 21-document sweep: every fault
traced, grouped G1-G9, the workflow changes, and the work plan.

The baseline is tests/frozen/s7-result/ (21 documents, 751 answers). Prove
it first, before any change: tools/replay_run.py over it reproduces 21 of
21 byte-identical, and tools/rederive.py 21 of 21 identical pages (20 byte
for byte; form_0007 differs in one IR field, its README says why).

Ask Alessandro whether spec 0011's by-eye rule still applies, and whether
the timetable's repair (step 10, which needs a sweep) should go first.
Then do the work plan in order, each step its own commit and its own
sheets for all 21 against the previous step, the six held-out pages
reported in their own lines. Report each step to him with what the pages
look like and the report.html path; continue unless a page got worse.
The standing rules are CLAUDE.md's and the spec's §9.
```
