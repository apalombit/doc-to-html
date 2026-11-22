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
| 1 | **three measurements, offline, before any build** — (a) the parser's order against the source's DOM order (from the HTML files, no Chrome, no model); (b) the source trees of the sampled pages (Chrome, seconds a page), and their depth; (c) optionally, the layout model alone on 5 pages (`glm-ocr.md` §5, way 2): do its raw candidates add anything the order and pixels do not? | the numbers in this spec; **if the order is unreliable, it becomes a tie-break only; if pages rarely nest deeper than two levels, 3d stays in the render's vocabulary** |
| 2 | ③a, the skeleton and its check, D2 only; scored against the source trees and judged by eye on 5 random pages, 5 more if unclear | a net gain in parts found, by eye, and no page worse that is not named |
| 3 | ③b and 3d: grouping inside the parts, drawn | the 5 pages drawn better by eye |
| 4 | 3c: grid parts read as tables, on 5 random form pages | the forms' fields in their grid |
| 5 | 3e: one size per role | 5 random pages nearer the source's sizes by eye |
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
