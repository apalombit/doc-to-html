---
name: visual-review
description: Look at a run's rendered output beside the source document and come back with findings a person can act on. Use when reviewing what a conversion produced, comparing a run against the previous one, checking whether a render still matches its page, or when a change is about to be judged on scores alone.
---

# Visual review

**Look at the artefact, not only at the number.** A measure can saturate and
then invert while every number improves: `sample_table_0003` scored a full
match having deleted every column header of its only table, and nobody had
opened a render beside its source in eighty runs. `report.html` answers *what
do the numbers say*. This answers *what does it look like*, and the two catch
different things — on 2026-09-21 a single pass found nine cross-cutting faults
that **no scored axis had reported**.

The evidence, the rationale and the open gaps are in
[`docs/agents/visual-review.md`](../../../docs/agents/visual-review.md). Read
it when you want to know *why*; this file is *how*.

## Three rules that bind every run of this skill

- **The reference is the PNG**, never the re-rendered source HTML. The
  screenshot is what the model was shown. Four of the five original documents
  re-render 6.9–14.1% different from their own screenshots on this machine.
- **Every panel is laid out at the source's width.** A page compared against
  itself at two widths is two different pages.
- **Judgements are pairwise and in-session only.** A reading from another
  session is not comparable with yours and must never join it in a table. Both
  images go in front of you now, or the comparison is not made. Every sheet and
  form carries a stamp for exactly this reason.

## Steps

### 1. Build the sheets

```
python tools/visual_review.py debug/runs/<label>                         # against the source
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py --pair <source.png> <render.html> --out <dir>
```

**Pass `--previous` whenever a previous run exists.** Source against render
says how far the output sits from the page; render against render says whether
it *moved*, which is the comparison the T1 ratchet is built on and the only one
that can catch a change that improved the numbers and damaged the page.

Writes to `<run>/_review/`: one PNG per document (several, `-p1`/`-p2`, for a
tall one), `findings.json` to answer, `review.md` mirroring it for a person,
and `numbers.md`. An existing `findings.json` is never overwritten.

*Done when* every document the run converted has a sheet, or is named in
`review.md`'s **Skipped** list.

### 2. Open every sheet

Read each PNG, **one at a time, all of them**. This is the only step that finds
anything, and it is the only step that cannot be delegated to a number.

*Done when* every file listed in step 1 has been opened. A document you did not
open is not a document you reviewed — leave its axes unanswered rather than
guessing them from `numbers.md`.

### 3. Trace each fault to its cause before writing it down

"The page looks grey" was one bucketing bug. "The cards are missing" and "the
page is tinted" were *the same* ground-measurement bug, and reporting them
separately would have produced two wrong fixes.

- **A uniform zero is a bug in the instrument, not a finding about the corpus.**
  `boxed` came back `False` on all fifteen documents. Suspect the instrument
  before the subject.
- **Check the honesty findings against what you can see.** A document that
  declared "18.5% of ink unread" and looks it is the honesty rule working.
- **A document that looks bad and one that measures bad are different lists.**
  `catalogue_0015` has the corpus's best `height_ratio` and is missing its page
  title and most of its prices.

### 4. Answer `findings.json`

Per document, per axis: `match` / `minor` / `major`, and **one sentence naming
an element**, not an impression. Then `worst` and `owner` — which thread or
phase owns the fault, or `new`.

`owner` is what makes the output actionable rather than a list of complaints:
it sorts faults into *fix now*, *already scheduled*, and *nobody knew about
this*.

With `--previous`, the extra `changed` axis takes `better` / `same` / `worse`
against the middle panel. **A `worse` is a ratchet event** — say what content or
chrome was there before and is not now.

An axis the rubric does not declare is accepted and reported as a trial axis.
Add one when a fault has no home; do not bend a fault into an axis that does
not fit it.

*Done when* every opened document has every axis answered, an `owner`, and no
note that could have been written from `numbers.md` alone.

### 5. Tally, and name the blind spots

```
python tools/visual_review.py debug/runs/<label> --check
```

Rewrites `review.md` from your answers with three things: **faults no scored
axis reported** — a `major` sitting beside scored ratios that are all at 1.000,
which is the `sample_table_0003` failure stated as a fact rather than against a
threshold somebody chose; **which axes fired**; and the owner tally.

*Done when* you have reported, in the conversation: the worst fault per
document, the blind spots, the owner tally, and — with `--previous` — every
`worse`.

## The rubric is provisional

`content`, `order`, `columns`, `chrome`, `type`, `colour`, `rhythm`. Two passes
behind it. **Do not freeze it**: `--check` reports which axes never fired so a
later session can cut the ones that do not earn their context, and trial axes
are kept rather than rejected. It does not score out of ten and it never
tabulates across sessions.
