# The page's skeleton first: step 3 top-down

**Status: open, 2026-11-22, issue #48, branch `skeleton` (cut from
`l5`).** The one active piece of work (Alessandro, 2026-11-22: "go for
this spec now - ignore main plan and focus as active items only on this
marking rest as parked"). Everything else is parked, below.

**Read first**, in order: `CLAUDE.md`'s READ THIS FIRST;
[`../glm-ocr.md`](../glm-ocr.md), **what GLM-OCR gives and does not give,
the facts this spec rests on**; [`0024-l5-on-d2.md`](0024-l5-on-d2.md)'s
"Outcome — the phase" and part two §1, §10, §13 and §14 (the grouping
patches this spec replaces); [`../agents/review-criteria.md`](../agents/review-criteria.md);
then this spec.

---

## 1. The conversion, and the step this spec changes

```
page picture
 ① layout     GLM-OCR (PP-DocLayoutV3)    the blocks, a label each, a reading order
 ② reader     GLM-OCR (glm-ocr:latest)    each block's text; tables as HTML
 ③ adapter    ours                        blocks → the IR: Zones, and which sit side by side
 ④ measuring  ours                        the looks from the pixels
 ⑤ render     ours                        the HTML
```

**This spec changes ③** (and, at its end, one rule in ④). ① and ②
read exactly as now.

## 2. Why ③

**The faults.** Counted on the 231 dev pages at spec 0024's part two
start (`L5-F13`'s checks): a page drawn taller than the source on 84
pages, side by side drawn under on 32, order interleaved or a word drawn
over another on 9. Spec 0024 mended five forms of one fault, each with a
rule and a constant: a Zone inside another cut at its top (`NESTED`
0.8), boxes one over the other stacked, a held box banded under its
holder (`HELD` 0.8), the lanes (`parted`, `CUT` 0.02), the stacks'
indent (`INDENT` 0.05). c0493 came out worse from one of them.

**The cause, two assumptions:**

1. **The page is rows of boxes side by side, and a box never holds
   another** (`ir.Zone` never nests; `Zone.band` and `Zone.column`).
   Real pages are boxes inside boxes: a card holding an icon, a panel
   holding a table, a sidebar holding stacked parts.
2. **Structure is built bottom-up, two pieces at a time.**
   `adapter.groups_of` sorts the parser's ~19 blocks a page by
   position and joins pairs (aligned, gap ≤ `STACK_GAP` lines, nothing
   between, crossing nothing); `wire.bands_from_boxes` then bands the
   results from their boxes. Each decision sees two boxes, never the
   page, so one wrong join spreads (c0402's caption dragged column 1
   across column 2).

**And GLM-OCR cannot hand us the structure** (`glm-ocr.md` §3): its
post-processing deletes every box 80% inside another, none of its 25
labels is a container, and on dev only 37 boxes inside another survive,
34 of them pictures. **But it gives two signals we do not use**
(`glm-ocr.md` §4): a **learned reading order**, which reads column by
column on 141 of 231 pages and which `groups_of` ignores, and **role
labels** (`header`, `footer`, `number`, `figure_title`, `aside_text`,
`doc_title` vs `paragraph_title`).

## 3. The design: one idea

**Read the page's structure first, top-down, from three independent
signals, checked against each other; where they disagree, keep today's
grouping for that part.**

| signal | from | what it says |
|---|---|---|
| the pixels | drawn frames, fills and rules (`parser_first.containers`, `furniture`); empty gaps measured on the ink, rules removed (`preprocess.content_ink`) | where the page draws or leaves its parts |
| the reading order | the parser's `index` | which blocks belong together, and in which direction a part is read |
| the boxes and roles | the parser's boxes and labels | what each piece is; the page's edges; a caption's figure |

### 3a. A new step: the skeleton (③a), before grouping

Recursive cuts over the parser's blocks inside a part, the page first:

1. **Drawn containers first.** A frame or fill holding two blocks or
   more is a part; at this level it is cut as one piece, and cut again
   inside.
2. **Then the empty gaps**, across (a full-width gap) or down (a
   full-height gutter), measured on the ink; the boxes are hints only
   (they are generous and miss small type).
3. **The direction the order agrees with.** A cut is taken where the
   parts it makes are each read in one run of the parser's order: A1 A2
   | B1 B2 is two columns; A1 B1 | A2 B2 is two rows. Where both agree,
   the wider gap.
4. **The roles bind:** `header`, `footer` and `number` go with the
   page's top and bottom rows; a `figure_title` is never cut from its
   figure.
5. **Stop** at one block; at a **grid** (the parts share their column
   edges across rows, or drawn rules make a lattice: a form's fields);
   or where no cut is found.

**The fault cases, each handled by a rule about structure, never about
a kind of page:**

| case | handling |
|---|---|
| a heading across two columns | cut across first wherever a full-width gap exists; the heading is its own row |
| a figure straddling a gutter | take the cut that crosses the fewest blocks; a block it crosses is lifted out as its own part |
| a form's grid of fields | stop at the grid; it is one part, read in 3c |
| the parser's boxes generous, or missing small type | gaps measured on the ink |
| no direction agrees with the order | the part is kept flat: today's grouping inside it, and recorded |

**The check, at the end of ③a.** Every block in exactly one part; no
cut through a block that was not lifted; reading the tree in order
agrees with the parser's order; every drawn container holding two
blocks is a part. **A part that fails falls back to today's grouping,
and is recorded**, so the worst case is today's. The recorded parts
are where alternatives or an iterating agent would pay later (parked);
their count says whether they are needed.

### 3b. Grouping inside each part (③b)

Today's `groups_of` and `zone_of`, run inside each part, so a group
never crosses a part's edge. Zones stay the leaves; measuring and the
looks work on them unchanged.

### 3c. A grid part read as a table

A part ③a calls a grid is cropped whole and read once by the reader in
its own table mode (`Table Recognition:`, `glm-ocr.md` §5, way 3),
instead of pieced from its fragments. One reader call per grid, decided
once: the flow stays one pass. The parser's weights, prompts and
settings are untouched; we choose the crop and the mode.

### 3d. Drawing the tree (⑤)

First through the render's own vocabulary: the skeleton's top cuts as
`Document.regions` (stretches and their lanes), and each lane's rows
and columns taken from the tree instead of re-banded from the boxes
(`render._columns` re-bands today, with `wire.under_holders`). **A
nested render** (the tree drawn as nested boxes) only if step 1 shows
the pages nest deeper than that vocabulary holds.

**What it replaces, for D2:** `adapter._unnested`, `adapter._stacked`,
`wire.under_holders`, `parser_first.parted` and `uncut`, the D2 use of
`wire.bands_from_boxes`, and most of their constants. Today's pipeline
keeps them: the replay of `s14-result/` stays 21 of 21.

### 3e. One size per role (④, last)

Sizes are measured per line, which is noisy (spec 0024 §5: 19–42% of
lines differ from their own Block by 0.06 or more). With the roles: every
block of one role on the page is measured together and drawn at the
role's size (the median); a block keeps its own only where it differs
clearly. Last, because it is the looks, and only once the skeleton
ships.

## 4. The yardstick: the source's own tree

Every corpus page is HTML, so its true box tree is in its source: the
elements that draw a box (a border or a background) and the ones that
set children side by side (flex, grid, columns), each with the page
region it covers, read in Chrome. **The skeleton is scored against it**:
a source part is found when the set of parser blocks whose centres fall
inside it is one part of ours; a part of ours that splits a source part,
or joins two, is a miss. Then by eye, on the same pages.

## 5. How it is worked — Alessandro, 2026-11-22

- **5 random pages** (seed recorded) from the dev pages with the fault,
  drawn from `L5-F13`'s checks (`debug/runs/L5-F13/checks/`): `height`
  84 pages, `beside: drawn under` 32, `order` and `overprint` 9. A page
  whose fault is gone at today's code is replaced by the next draw.
  **If unclear, 5 more; then decide**, and give up a direction that
  does not work.
- **No full-set runs** to test anything, and no conversion beyond the
  reader calls 3c needs on its 5 pages.
- **Testing minimal**: the tests of the files changed, the replay of
  `s14-result/` when shared code changes, `mypy src/`; the full suite
  only at the close.
- **Structure only.** Judged by eye on the arrangement: are the parts
  where the page puts them? No style checks, no minor things that do
  not change the conversion.
- Report each change as page / before / after, one line of what
  changed and one of the result.

## 6. Steps

| step | what | done when |
|---|---|---|
| 0 | this spec, `glm-ocr.md`, issue #48, branch `skeleton`; the rest parked | done 2026-11-22 |
| 1 | **three measurements, offline, before any build** — (a) the parser's order against the source's DOM order (from the HTML files, no Chrome, no model); (b) the source trees of the sampled pages (Chrome, seconds a page), and their depth; (c) optionally, the layout model alone on 5 pages (`glm-ocr.md` §5, way 2): do its raw candidates add anything the order and pixels do not? | the numbers in this spec; **if the order is unreliable, it becomes a tie-break only; if pages rarely nest deeper than two levels, 3d stays in the render's vocabulary** — done 2026-11-22: the order a signal, not a veto; 3d in the vocabulary; way 2 closed (outcome below) |
| 2 | ③a, the skeleton and its check, D2 only; scored against the source trees and judged by eye on 5 random pages, 5 more if unclear | a net gain in parts found, by eye, and no page worse that is not named — done 2026-11-22: 31 of 32 source parts found against today's 15; 4 pages better by eye, 1 the same (outcome below) |
| 3 | ③b and 3d: grouping inside the parts, drawn | the 5 pages drawn better by eye — done 2026-11-22: 4 better, c0274 the same, none worse (outcome below) |
| 4 | 3c: grid parts read as tables, on 5 random form pages | the forms' fields in their grid — done 2026-11-22: 2 better, 3 the same, none worse, after two guards (outcome below) |
| 5 | 3e: one size per role | 5 random pages nearer the source's sizes by eye — done 2026-11-22, in tables: 2 of 10 nearer, 8 the same, none worse (outcome below) |
| 6 | close: outcome here, `docs/status.md`, `CLAUDE.md`, the full suite, `main` fast-forwarded, the issue closed, a handover prompt | — |

One commit a step, its outcome written here.

## 7. Parked, 2026-11-22

Not to be picked up while this spec is open:
- the level-up milestone (the phase on the panel, then the vault):
  `level-up.md` §6, row M1, and spec 0024's last prompt;
- the reading: crops enlarged (`glm-ocr.md` §5, way 5), words lost or
  misread in small type;
- bold and colour inside a line (a measure per word);
- frames and fills (81 dev pages);
- the named worse pages of spec 0024: c0012, c0075, c0493, c0538;
- the later strategies: alternatives proposed at the parts the check
  records; an agent converting until satisfied.

## 8. Rules

- **Local models only.** Never pass `unseal=True`.
- **No panel page is used in a test or to tune anything**, c0001 and
  c0002 above all; a fault seen on a panel page is reproduced on a dev
  page first.
- **Today's pipeline stays as it is**: every change is D2's alone
  (`adapter.ENGINE`, or D2's own steps); the replay of `s14-result/`
  stays 21 of 21.
- **The parser's weights, prompts and settings untouched** (`glm-ocr.md`
  §5): we choose crops and modes, never its settings.
- **Run nothing Alessandro has not asked for**, beyond this spec's steps.
- One conversion at a time, nothing beside it; Chrome jobs finished
  before a model call. Never edit `src/` while a batch runs.
- Judge by eye (`review-criteria.md`); a number is a pointer to a page.

---

## Outcome — step 1, the three measurements, 2026-11-22

All offline but (b)'s Chrome and (c)'s layout model on the CPU; no call
to the reader. (a) and (b) are `tools/skeleton_check.py order` and
`trees`; (c) needs the parser's own Python and is described below.

### (a) The parser's order against the source's DOM order: reliable, with local errors

Each of the 231 dev pages' text regions (`L5-D2-dev`) placed in its HTML
file's word stream by the n-grams of its words that occur once on the
page (trigrams, else bigrams, else words); 4,555 of 4,889 regions placed
(93%), 228 pages with two or more. Then Kendall's tau between the
DOM positions and (1) the parser's `index`, (2) a top-to-bottom,
left-to-right sort, which is what `groups_of` walks.

| | parser's order | position sort |
|---|---|---|
| pages where it is the DOM's order exactly | **137** of 228 | 67 |
| tau, median | **1.000** | 0.928 |
| pages with tau under 0.7 | 1 | 34 |
| adjacent steps backward, all pages | **244** | 870 |

On the 165 pages where the two orders differ, the parser's is nearer
the DOM on **145**, the sort on 15, 5 tied. The 15 are mostly grids of
fields (c0020, c0071, c0153, form_0007, c0112): the source writes them
row by row and the parser reads them column by column, both a right
reading. **But the parser errs locally**: 244 steps backward on 91
pages. c0263, a dashboard of nine sections in three rows, is read
interleaved at the sections' edges (`STOCKPORT SITE` before the last
milestone); c0541 reads the caption under the chart before the
sidebar beside it.

**What it changes.** The order stays a signal, not a tie-break only;
but it cannot veto a cut, because it errs on 91 pages. §3a's rule 3
becomes:
- **one cut at a time**, the page first (a recursive cut, not every
  gap at once), so a gap that lines up across two columns by chance is
  never taken while the gutter between them stands;
- each possible cut is scored by the pairs of blocks it sets against
  the parser's order (a block of the first part read after one of the
  second); **the fewest wins**, the wider gap on a tie;
- **a cut down must set no more pairs against the order than reading
  the part by position does**: rows of label | value read across are
  never cut into a labels column and a values column;
- a cut across is taken even against the order when it is the only one
  (c0541, c0263: the parser's errors, not the page's).

### (b) The source trees of 5 random fault pages: 1 to 5 deep

Drawn from the 93 dev pages with a `height`, `beside, drawn under`,
`order` or `overprint` major in `L5-F13` (seed **48**, `random.Random(48).sample`):
c0511, c0274, c0093, c0514, c0504. Each still has its fault at `c2359de`
(drawn from its recorded regions, checks re-run): height on all five
(1.13 to 1.44). Their trees, read in Chrome: an element that draws a
frame on four sides or a fill unlike its ground, or sets two block
children side by side, and each child of the latter (a lane); a table
is one leaf unless its cells hold such elements (c0511's ticket is a
layout table).

| page | nodes | depth | side by side, nested | box in box | what is deepest |
|---|---|---|---|---|---|
| c0274 | 3 | 1 | 0 | 0 | three tables |
| c0514 | 6 | 3 | 1 | 1 | the frame round the date / seal / signature row |
| c0504 | 27 | 4 | 2 | 1 | the columns; a title and its dates on one line |
| c0093 | 44 | 5 | 2 | 2 | the columns; a fieldset round rows of field boxes |
| c0511 | 18 | 5 | 2 | 3 | the stub's fill round four framed fields; a 2×2 field grid |

**What it changes.** The render's vocabulary holds a stretch's lanes,
Zones side by side in a lane, and a box round one Zone or round a run
of one lane (`rhythm.frames`). That holds c0274, c0514 and c0504 whole.
c0093 and c0511 go deeper only in grids of fields (3c: a grid read as a
table, one Zone in its frame) and in c0511's stub, a fill holding four
frames: **a box inside a box is the one thing the vocabulary lacks.**
So **3d stays in the render's vocabulary**, as planned; the nested
render is not built.

### (c) The layout model alone: nothing the order and the pixels do not give

`glmocr.layout.PPDocLayoutDetector` on the 5 pages, our config as it
is, `apply_layout_postprocess` wrapped only to record what it is given:
**159 candidates over the threshold, 140 kept**. The 19 deleted are the
same block under a second label (10: IoU 0.8 or more with a kept box,
`doc_title` under `header`, `text` under `footer`) or one line cut from
a kept block (9). **None holds two kept blocks**: no container. Way 2
is closed.

## Outcome — step 2, the skeleton and its check, 2026-11-22

`src/doc_to_html/skeleton.py`, D2's alone and not yet called by any
conversion: the replay of `s14-result/` cannot move. As §3a, with step
1's change: **one cut at a time**, the page first. At each part, the
drawn boxes holding two blocks or more are units; the candidate cuts
are the gaps across and the gutters down between the units' ink
(`snapped`: each block's box drawn in to its ink, rules removed, fills
read against their own ground); each is scored by the share of block
pairs it sets against the parser's order, the fewest first, the wider
gap on a tie; a cut down setting more pairs against the order than
reading by position is refused; a block lifted across a gutter is a
last resort. Then the check (§3a), which keeps a failing part flat.

**Mended on the way**, each found on the 5 pages and pinned by a test:
- a lifted cut beat a clean gap across because its gutter was wider:
  c0514's certificate number, a full-width line, was put in the
  signature's column. A lift is now taken only where every clean cut
  sets blocks against the order;
- a drawn box holding every block of its part was never used (c0514's
  header band and its frame); it is now the part's one unit;
- the header and footer peel took the footer out of the frame that holds
  it (c0514); a drawn box holding a body block keeps its edge blocks;
- a fieldset's legend sits on its frame's top rule, its centre just
  outside (c0093's `PART 1`, `PART 3`, `SIGN HERE`): a block set on a
  box's top edge, within its width, is held by it;
- a top `number` (c0093's `2024`) was left out of the header row;
- a grid: rows each cut into the same columns, or columns each cut into
  the same rows, every cell three blocks or fewer, each cell's start or
  end within half a line of its run's (c0511's four fields, `Venue` read
  with its label and `Date` without: tops apart, feet together). Two
  bullet lists side by side are not a grid.

**Scored** against the source trees (`tools/skeleton_check.py score
c0511,c0274,c0093,c0514,c0504 --label SK-2`): a source part of two
blocks or more is found when one part holds exactly its blocks.
Today's parts are its Zones, its Bands' Zones side by side, and the
measured stretches and their lanes.

| page | source parts | today | skeleton | by eye, the skeleton's parts against today's |
|---|---|---|---|---|
| c0511 | 5 | 1 | **5** | better: the ticket's frame, the stub's fill \| the main column, the 2×2 fields a grid, ADMISSION \| GETTING HERE; today's Bands cross the stub and the main column (`HOS-0048213` banded with the title) |
| c0093 | 13 | 10 | **13** | better: the header strip's three lanes, both columns of fieldsets, each fieldset whole with its legend; today misses `2024`'s lane, PART 2 and SIGN HERE |
| c0514 | 5 | 2 | **5** | better: the band, the frame, the date \| seal \| signature row; today misses the frame and the row |
| c0504 | 9 | 2 | **8** | better: photo \| name, main column \| sidebar, each job's title \| dates; today's Bands cross the two columns (PROFILE banded with E-MAIL). Missed: SKILLS, a heading over chips with no drawn box: grouping's, inside the part (3b) |
| c0274 | 0 | 0 | 0 | the same: three tables and a heading, nothing to cut |
| **all** | **32** | **15** | **31** | **4 better, 1 the same, none worse** |

No part fell back flat, none was lifted and every drawn container of
two blocks is a part, on all 5: the check and the lift have run on
synthetic pages only (`tests/test_skeleton.py`, ten tests, each failing
without its rule). `mypy src/` clean.

## Outcome — step 3, grouping inside the parts, drawn from the tree, 2026-11-22

D2 now lays every page out from its skeleton (`parser_first.from_regions`
→ `adapter.laid_out`); a page whose skeleton is kept flat whole is drawn
by today's `document_of`, unchanged. In the render's vocabulary, as step 1
found it holds:

- **grouping inside the parts** (3b, `adapter._Laid.group`): `groups_of`,
  `zone_of` and `_titled` on each run of plain sibling parts (a heading
  and the paragraphs under it are three parts and one Zone), never across
  a drawn box, a lane or a grid's cell. A drawn box holding two blocks is
  the skeleton's part already, so `groups_of`'s card rule is not given it:
  inside c0511's stub it joined the times to the number under the
  barcode, and drew them beside the barcode. A box round one block (a
  chip) still sets it apart;
- **placed from the tree** (3d, `_Laid.place`): a part's rows are Bands
  one under the other; a cut down is one Band, a column a part; **a cut
  down not inside another, its parts holding several Zones, is a
  `columns` Region** with `Region.banded` set, its splits where each
  lane's blocks begin; a grid is drawn by its rows. `render._columns`
  takes a banded Region's lane rows from `Zone.band` and `Zone.column`
  instead of re-banding the boxes (`bands_from_boxes(under_holders(…))`);
  `parser_first.measure` keeps a laid-out page's stretches instead of
  reading them (`structure`, `uncut`, `parted`);
- **frames from the skeleton's boxes** (`_Laid.frames`): the first
  redraw lost c0514's certificate frame, c0511's ticket border and c0093's
  PART 2 and SIGN HERE fieldsets, because `rhythm.frames` shares a frame
  only among Zones in one lane, and the skeleton's Regions put them in
  several. A Zone now takes the outermost box holding a banded Region
  (c0511's ticket, c0514's certificate), else the innermost box holding
  it; a box round one Zone is its own. A lane draws only the frames that
  cross none of its Region's splits (`render.SPLIT_SLACK`): otherwise
  each lane of c0514's signature row drew the certificate again, padded
  from its top (the page 2.24 times the source's height), and c0511's
  main lane padded from the ticket's left edge (a word a line, 6.6 times).
  A box inside such a box is not drawn: c0511's 2×2 field boxes, which
  today does not draw either.

`Region.banded` is written only where it is set, so today's embedded IR
is byte for byte as before. **Replay of `s14-result/`: 21 of 21
byte-identical, 0 asked differently.**

**By eye**, `tools/d2.py SK-3 --previous SK-0 --sheets` (source, today,
skeleton), the 5 pages of step 2:

| page | before (today) | after | |
|---|---|---|---|
| c0511 | stub and main banded across each other: `HOS-0048213` beside the title, the doors-open lines on a fill beside the fields, the programme at the right, the footer full width | the ticket's frame; the stub a lane on its fill, every line and the barcode in it; the main lane: header, title, the four fields in two rows, the programme under them, ADMISSION \| GETTING HERE, the footer | **better** |
| c0093 | `TAX YEAR ENDED DEC. 31` dropped under the header strip at the right | the header strip three lanes, the line under `2024` in its lane; both columns of fieldsets, each framed with its legend | **better** |
| c0514 | the seal stacked over the date, the signature at the right, a long rule between | the band; the certificate's frame; date \| seal \| signature side by side | **better** |
| c0504 | `2015 to 2018` and `2012 to 2015` drawn far below their jobs, gaps in the main column | each job's dates beside its title; the main column and the sidebar as printed | **better** |
| c0274 | three tables and a heading | the same | same |

Left on these pages, not structure: c0504's name drawn at the right of
its photo's box (the header's two lanes are right, the photo's box is
drawn too wide); c0511's stub fill ends above the ticket's foot; type and
weights.

`tests/test_skeleton.py`, four more tests, each failing without its
rule (a banded Region, no card rule across a picture, the outer frame,
`banded` written only where set); the render's two rules are pinned by
the replay (today's) and by eye (D2's) only. `mypy src/` clean.

## Outcome — step 4, a grid part read as a table, 2026-11-22

A part the skeleton calls a grid is cropped whole and read once by
GLM-OCR's reader in its table mode: `tools/glmocr_read.py`, run by the
parser's Python, uses the SDK's own crop (`crop_image_region`), request
(`PageLoader.build_request_from_image`, task `table`) and call
(`OCRClient.process`). No layout model runs, and the parser's weights,
prompts and settings are untouched. `parser_first.grids_of` names the grids
(the part's box joined with its blocks' boxes, on 0–1000).
`read_grids` reads them, and `with_grids` puts each table in its
fragments' place in the reading order. `convert` reads the grids after the
parse, and `attempt` records them (`01_grids.json`, pass `grids`); the
offline loop reads only grids it has not recorded
(`tools/d2.py --grids`). Each read took 1.0–2.3 s.

**The sample.** Of the 25 dev pages that draw a form, 6 have a grid
part. The parser already reads many field grids as tables itself
(c0093's PART 1). Five were drawn at random, seed 4825: form_0007, c0008,
c0012, c0096 and c0024.

**The first read lost content on two pages**, and two guards came out of
it:

- **c0012**: the grid of the date and signature lines held the
  signature's picture, and the table dropped it. A grid holding a picture
  larger than a mark (`MARK`, 2 lines either way; `readable`) is not read.
  c0008's tick boxes are marks and stay in.
- **c0024**: the header's grid held the barcode, and the table dropped
  both the barcode and `Exam no. 0482-117-B`. A table that drops a word
  its text fragments hold keeps the fragments. A picture's content is not
  a printed word: the barcode reads as an empty code fence.

**By eye**, `tools/d2.py SK-4c --previous SK-4b --sheets`, against step 3:

| page | before (step 3) | after | |
|---|---|---|---|
| c0096 | the inspection's header fields, pieced from fragments, drawn as one ragged run | the fields in two aligned columns, as printed | **better** |
| c0008 | the checklist's items in one column, the tick boxes lost | the checklist's columns, each item with its tick box | **better** |
| form_0007 | the next-of-kin fields in their grid | the same grid, its value boxes drawn as a table's rule | same |
| c0012 | — | not read (the picture guard) | same |
| c0024 | — | not read (both guards) | same |

The three tables read under the guards are the first read's tables byte
for byte. Step 4 changes D2's code only (`parser_first`, `tools/d2.py`,
`tools/glmocr_read.py`), so today's pipeline is untouched.
`tests/test_skeleton.py` has four more tests, and each fails without its
rule: the table in the fragments' place, a lost word, a picture larger
than a mark, a picture's content. `mypy src/` is clean.

## Outcome — step 3 mended, on a second draw, 2026-11-22

Step 5's sample (seed 250005, the first 5 of the 210 dev pages with
`sizes out of proportion` at `L5-F13`) was first drawn as it stands and
against the commit before the skeleton (`fb5be09`, run `SK-5-0`), and
two of the five were **worse** with the skeleton. Both were mended in the
drawing, not the skeleton, whose parts were right on both:

- **A fill round a banded row is no lane's own** (`render._across`,
  `_columns.lane_fill`). probe_datasheet's header strip is one banded
  Region, [DATASHEET · REV C over the title] | [VERIDIAN]. The VERIDIAN
  lane took the whole strip as its fill and was inset from the strip's
  left edge (800 px each side), which pressed the title's lane to one
  word a line. As frames already did in step 3, a fill that crosses a
  split is drawn round the row.
- **A part's Zones are banded as `document_of` bands a page's**
  (`_Laid.stack` → `_stacked`), and a box inside text goes under it.
  c0407's drop capital was banded where it stands, inside its paragraph,
  so it was drawn as a column beside it and the paragraph fell to one
  word a line. **Only text holds** (`wire.under_holders`' new `holds`,
  given only by D2): c0008's number badges lie inside the parser's table,
  which prints their numbers, and moving them under it scattered them
  down the page.

| page | before the skeleton (`SK-5-0`) | the skeleton, as committed (`SK-5a`) | mended | |
|---|---|---|---|---|
| probe_datasheet | header as printed; 0.99 | title one word a line, VERIDIAN off the right; 1.51 | header as printed; 1.03 | **mended** (same as before) |
| c0407 | the two columns; drop cap a bar under its paragraph; 1.14 | paragraph one word a line beside the drop cap; 3.70 | the two columns as before; 1.41 | **mended** (same as before) |
| c0439 | the header strip in two pieces, the right one over the right column; `Ordering code` beside its table | the strip whole; the title over its table | the same | **better** |
| c0246 | the header fill in two pieces; the footer in the left column | the strip and the footer full width, as printed | the same | **better** |
| c0198 | `PACKING SLIP` above `EMBER LAMP WORKS`; the three address columns as printed | the top row as printed; the address row broken (`SHIP TO` on its own, `ORDERED BY` in the wrong lane) | the same | **mixed** |

c0198's address row is the parser's table either way. Before the
skeleton, `EMBER LAMP WORKS` was taken as that table's Title (`_titled`).
Now it is the page's masthead, as printed, and the table's crop starts
at the table. On that crop `locate` (tesseract) no longer places
`SHIP TO` and puts `ORDERED BY` a line low, so the render no longer
joins the two rows. That is a measuring effect, not a skeleton decision;
it is named, not mended.

Step 3's five pages and step 4's three do not move (`SK-5f` against
`SK-3` and `SK-4c`), except two small pictures held in a text line on
c0008 and form_0007 (badge 20, a ☒), now drawn under their line: the
same structure. **Replay of `s14-result/`: 21 of 21 byte-identical, 0
asked differently.** `tests/test_skeleton.py` has three more tests, and
each fails without its rule. `mypy src/` is clean.

## Outcome — step 5, one size per role, in tables, 2026-11-22

The sample is seed 250005: the 210 dev pages with `sizes out of
proportion` at `L5-F13`, the first 5 (c0246, probe_datasheet, c0407,
c0198, c0439), then the next 5 (c0589, c0475, c0276, pricing_0017,
c0518) to look for harm. The "before" is today's code with the mends
above (`SK-5f`, and `SK-5h0` drawn at `9086e85`).

**What the faults were.** A line's size is measured in whole pixels on a
body glyph of 8 to 11 px, so one pixel is 0.09 to 0.12 of the body. On
the first five pages the faults are of two kinds:

- **A table cell 3 or 4 px off its peers**, which the page prints in one
  size: c0198's backordered row (grey italic) and its total row at 0.50
  among rows at 1.00, its `Ship` header at 0.62 among headers at 1.00;
  c0439's `Hexagon size` at 0.62 in a column at 1.00, and its `Range`
  header at 0.75. This is what a per-role median reaches.
- **In prose, not a group's outlier**, so a median does not reach it:
  - c0246's three drug names measure 1.22, 1.11 and 1.11, and those
    under `render.SIZE_STEP` (0.15) are drawn at the body's size;
  - probe_datasheet's intro is not measured;
  - c0439's title, white on its strip, measures 1.00;
  - c0407's `pequenos e prazos curtos.`, whose only tall letter is a
    `t`, measures 0.82.

  These are the measure and the draw threshold (spec 0024 §5), named
  here and not mended.

**What shipped** (`parser_first.table_sizes`, D2 only, right after
`looks.read`): each table's header, data and summary Cells are drawn at
the median of their column's Cells of that role, where at least `PEERS`
(3) are measured, else at the median of the role's. A column keeps a
size of its own (a price larger than its item); a Cell does not.

**By eye**, `tools/d2.py SK-5g --previous SK-5f` and
`SK-5h --previous SK-5h0`:

| page | before | after | |
|---|---|---|---|
| c0198 | the backordered row and the total row at half the body's size, `Ship` small | each at the body's size, as printed | **better** |
| c0439 | `Hexagon size` and the `Range` header small | at the body's size, as printed | **better** |
| c0246, probe_datasheet, c0407 | no table size fault | — | same |
| c0589, c0475, c0276, pricing_0017, c0518 | their tables at one size | the same (their HTML moved on sizes under the draw threshold) | same |

One more fault is visible now that the backordered row is drawn at full
size: it draws bold where the page prints grey italic. That weight was
measured before; it was only too small to see.

Step 5 changes D2's code only. `tests/test_skeleton.py` has three more
tests, each failing without its rule (a Cell off its column, a header
row too short for its columns, a column's own size). `mypy src/` is
clean.

---

## Decisions — Alessandro

| # | asked | decided |
|---|---|---|
| 1 | step 3 first, before words or colours | **Decided** (2026-11-22): "i think this is crucial first step before missing/mispelled words or colours"; one-shot conversion for now, the iterating or alternatives strategies for later |
| 2 | this spec, everything else parked | **Decided** (2026-11-22): "go for this spec now - ignore main plan and focus as active items only on this marking rest as parked" |
| 3 | how it is tested | **Decided** (2026-11-22): 5 random pages, 5 more if unclear; no full-set runs; testing minimal; no style checks or minor things |
| 4 | where it runs | **Decided** (2026-11-22): from another chat, from the prompt below |

---

## The prompt to start this spec

> Start spec 0025, `docs/specs/0025-page-skeleton.md` (issue #48, branch
> `skeleton`, cut from `l5`): the page's skeleton first, conversion step
> 3 rebuilt top-down. It is the only active work; everything else is
> parked (its §7). Read `CLAUDE.md`'s READ THIS FIRST, then
> `docs/glm-ocr.md` (what GLM-OCR gives and does not give: a flat list
> of leaf blocks by design, a learned reading order, role labels, its
> table mode), then the spec end to end, and spec 0024's "Outcome — the
> phase" and part two §10, §13 and §14.
>
> 1. **Step 1, the three measurements, offline**: the parser's reading
>    order against each dev page's DOM order (from the HTML files and
>    `debug/runs/L5-D2-dev/`'s recorded regions; no Chrome, no model);
>    the source trees of 5 random pages from the fault pool (Chrome)
>    and their depth; optionally the layout model alone on those 5
>    (`glm-ocr.md` §5, way 2). Write the numbers into the spec and what
>    they change in the design.
> 2. **Step 2, the skeleton and its check**, D2 only, scored against the
>    source trees and judged by eye on 5 random pages from the fault
>    pool (seed recorded), 5 more if unclear. Then steps 3 to 5 as the
>    spec orders them, one commit a step.
>
> Rules: local models only; never pass `unseal=True`. No panel page in
> a test or to tune anything. Today's pipeline stays as it is: the
> replay of `s14-result/` stays 21 of 21. The parser's weights, prompts
> and settings untouched. **No full-set runs; 5 random pages, 5 more
> if unclear, then decide.** Testing minimal: the changed files' tests,
> the replay when shared code moves, `mypy src/`; the full suite at the
> close only. Structure only: no style checks, nothing minor. Run
> nothing he has not asked for. Report each change as page / before /
> after, one line of what changed, one of the result. Keep replies
> short: bullets, facts, no filler.
