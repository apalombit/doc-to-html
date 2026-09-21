# Visual Review — the record

**To actually review a run, use the skill:
[`.claude/skills/visual-review/`](../../.claude/skills/visual-review/SKILL.md).**
It carries the procedure, the commands, the rubric and the rules.

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

## Why the skill's rules are what they are

**The left panel is the PNG, not the re-rendered source HTML.** Four of the
five original documents re-render 6.9–14.1% different from their own
screenshots on this machine, and `invoice2.html` additionally wants a CDN.
Comparing against the HTML would show differences nobody introduced.

**Every panel is laid out at the source's width.** `projection.project()`
already takes this position for scoring; the review takes the same one so the
two never disagree.

**Pairwise and in-session only.** CLAUDE.md is explicit that a rubric
judgement from one session and one from another are not comparable, and that
this binds a model's visual judgements at least as strongly as numbers.

**`owner` on every finding.** On 2026-09-21 it separated three faults that
were fixable that day from six belonging to A0, A2 and A3. Without it the
output is a list of complaints.

**The rubric is not frozen.** Seven axes, a handful of passes. `--check`
reports which axes never fired so the set can be cut on evidence, and an
undeclared axis is kept as a trial rather than rejected, so trying an eighth
needs no code change.

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

## What the tool still cannot do

Kept here because it is the next piece of work on the instrument, not because
a reviewer needs it.

1. **The rubric is still a guess.** `--check` now collects the firing record;
   a few more passes decide which axes stay.
2. **`changed` is judged by eye.** Three panels on one sheet make the
   comparison possible, but nothing diffs the two renders' pixels or
   projections to point at *where* they differ, so a small regression in a
   dense document can still be missed.
3. **Findings are not diffed between runs.** Two `findings.json` files could
   be compared — a `major` that was there last time and is not now — and are
   not. Whatever does it must not become a cross-session table.
4. **The part pairing is approximate and does not say how approximate.**
   `BLEND` is a trade between pairing content and bounding height; a sheet
   does not report how far its two parts actually drifted.
