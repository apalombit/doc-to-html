# Visual Review — the record

**To actually review a run, use the skill:
[`.claude/skills/visual-review/`](../../.claude/skills/visual-review/SKILL.md).**
It carries the procedure, the commands, the form and the rules.

This file is the record behind it: why the project has this step at all, what
its rules were measured against, and what the tool still cannot do. Nothing
here is needed to run a review.

---

## Why the project has this step

A measure can saturate and then invert while every number improves. Over runs
81→84 the mismatch total went 23→10 while duplicated titles appeared in three
of five documents and `sample_table_0003` lost every column header of its only
table — scored as a **full match**, because the harness compared `RowRole`
sequences and never cell content. Nobody had opened a render beside its source
in eighty runs.

On **2026-09-21** the review ran over all fifteen documents for the first time
and found nine cross-cutting faults. **No scored axis had reported any of
them.** Four examples, each now a test:

- every white page was being rendered on `#f8f8f8`, because the palette's
  bucketing floors and `255 // 8 * 8` is 248;
- `sample_css_0004`'s whole page was tinted its *card* colour, because the
  ground was a mode over the whole image and the cards cover more area than
  the margin;
- `receipt_0010` and `menu_0012` were getting heavy beige and tan bars on
  sources that draw no fill anywhere;
- `statement_0006` printed forty-one near-identical caveat lines.

---

## Rubric 2 — faults, not axes (spec 0021, 2026-10-30)

**What changed and why.** Rubric 1 asked seven axes (content, order,
columns, chrome, type, colour, rhythm) a verdict each. The criteria
agreed with Alessandro on 2026-10-24 (`review-criteria.md`) ask for
something else: each **fault**, its class, its severity, the element it
touches, and the stage that made it, so faults can be counted per feature
and per stage across hundreds of pages. Three things made that possible:

- **The exact checks** (`doc_to_html.checks`) read both sides from HTML at
  the source's width and find what the source HTML settles: words, cells,
  rules, structure, order, lines, height, alignment, type. On the 31 known
  pages they catch the three faults the probe found by eye and no number
  saw. These are the lab report's results under Flag, the quiz's cells
  merged by missing rules, and the recipe's steps among its ingredients.
  On all 231 dev pages read against themselves they find nothing.
- **The form arrives filled in** with the checks' faults, numbered as boxed
  on the sheet. Claude confirms or rejects each by looking, since markup
  can still fool a check, and adds what the HTML cannot settle: what sits
  beside what, frames and fills, figures.
- **Sampling.** A page is opened when a check finds a major a reader must
  confirm (cells, rules, structure, order), when a change moved it, or as
  one of two per family. The rest are counted. Step 7 of spec 0021
  measures the rule against a full review of the 31.

**Retired with rubric 1:**
- **`owner`.** On 2026-09-21 it told faults fixable that day from faults
  belonging to a phase. Every phase is closed and the level-up ranks what
  to fix next from the roll-up instead.
- **The rule about deferred faults.** Nothing is deferred any more: every
  fault is reported with its severity.

**Fixed:** `numbers.md`'s table header. Two adjacent string literals
glued the header's end to the rule row before `*` repeated the pair, so
the table had nine header rows.

---

## Why the skill's rules are what they are

**The left panel is the PNG, not the re-rendered source HTML.** Four of the
five original documents re-render 6.9–14.1% different from their own
screenshots on this machine, and `invoice2.html` additionally wants a CDN.
Comparing against the HTML would show differences nobody introduced. The
checks do read the source HTML, which is how they are exact. Where the HTML
and the picture disagree, as on those five, the sheet shows it.

**Every panel is laid out at the source's width.** `projection.project()`
already takes this position for scoring; the review and the checks take the
same one so the three never disagree.

**Pairwise and in-session only.** CLAUDE.md is explicit that a rubric
judgement from one session and one from another are not comparable, and
that this binds a model's visual judgements at least as strongly as
numbers. Alessandro's calls on the review page are the exception by
design: they are kept (`docs/agents/review-calls/`) to re-test the
checklist against, never tabulated beside Claude's.

**The stage is read, never guessed.** A fault's stage decides what gets
fixed. The picture alone cannot tell a Zone drawn round two groups from a
model that read one group wrong; the IR and the trace can.

---

## Reading the pictures well

- **Trace a fault to its cause before reporting it.** "The page looks grey"
  was one bucketing bug. "The cards are missing" and "the page is tinted" were
  *the same* ground-measurement bug.
- **A uniform result across the corpus is a broken instrument.** `boxed` came
  back 0 on all fifteen and `filled` on fourteen; the second was equalisation
  destroying the signal, the first was the detector looking at a crop the rule
  is not in.
- **A document that looks bad and one that measures bad are different lists.**
  `catalogue_0015` has the corpus's best `height_ratio` (1.03) and is missing
  its page title and most of its prices.

---

## What the tool cannot do

Known limits, so a reviewer allows for them. Not scheduled work.

1. **The checks see the HTML, not the picture.** Where a page's HTML no
   longer re-renders to its picture (the five originals), a check's lines
   are the HTML's. A PDF page's checks read its twin, which the corpus
   gate admitted against the picture.
2. **Boxes on a photographed page do not land on the photograph.**
   `ticket_0020`'s source is read flat, as the scorer reads it, so its
   source boxes are drawn on a picture that is warped.
3. **The part pairing is approximate and does not say how approximate.**
   `BLEND` is a trade between pairing content and bounding height; a sheet
   does not report how far its two parts actually drifted. Tiles pair by
   the words instead, and only on a dense page.
4. **Findings are not diffed between runs.** Two `findings.json` files could
   be compared, a `major` there last time and not now, and are not.
   Whatever does it must not become a cross-session table.
