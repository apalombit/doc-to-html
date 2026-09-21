# Visual Review

How to look at what this project produced, beside what it was given, and come
back with something a person can act on.

**This is the workflow to consolidate into a reusable skill.** It has run twice.
The "Known gaps" section at the end is the work; do not skip it and do not
freeze the rubric before that work is done.

---

## Why it exists

`report.html` answers *what do the numbers say*. This answers *what does it look
like*, and the two catch different things.

The project's most expensive lesson is that a measure can saturate and then
invert while every number improves. Over runs 81→84 the mismatch total went
23→10 while duplicated titles appeared in three of five documents and
`sample_table_0003` lost every column header of its only table — scored as a
**full match**, because the harness compared `RowRole` sequences and never cell
content. Nobody had opened a render beside its source in eighty runs.

It is not history. On **2026-09-21** this workflow ran over all fifteen
documents for the first time and found nine cross-cutting faults. **No scored
axis had reported any of them.** Among them:

- every white page was being rendered on `#f8f8f8`, because the palette's
  bucketing floors and `255 // 8 * 8` is 248;
- `sample_css_0004`'s whole page was tinted its *card* colour, because the
  ground was a mode over the whole image and the cards cover more area than the
  margin;
- `receipt_0010` and `menu_0012` were getting heavy beige and tan bars on
  sources that draw no fill anywhere;
- `statement_0006` printed forty-one near-identical caveat lines.

Each was found by looking. Each is now a test.

---

## Running it

```
python tools/visual_review.py debug/runs/<label>
python tools/visual_review.py debug/runs/<label> --documents cv_0013,menu_0012
```

Produces, under `<run>/_review/`:

```
NN-<document>.png   source left, render right, matched width
review.md           seven axes per document, to fill in by looking
numbers.md          the scored axes, to quote in a note
```

### The shape of it

```
  source PNG                     run's dump/<doc>/document.html
  (what the model saw)           (the IR + our CSS)
        │                                  │
        └──── headless Chrome, at the SOURCE's width ────┐
                             │                            │
                    NN-<document>.png  ← one image, side by side
                             │
                   opened with the Read tool   ← the only manual step,
                             │                   and the only one that finds anything
                             ▼
                    review.md + a ranked summary
```

### Two rules built into it, both load-bearing

**The reference is the PNG, not the re-rendered source HTML.** The screenshot is
what the model was shown and what a person compares against. Four of the five
original documents re-render 6.9–14.1% different from their own screenshots on
this machine, and `invoice2.html` additionally wants a CDN — comparing against
the HTML would show differences nobody introduced.

**Both sides are laid out at the source's width.** A page compared against
itself at two widths is two different pages. `project()` already takes this
position for scoring; the review takes the same one so the two never disagree.

---

## The rubric

`RUBRIC` at the top of `tools/visual_review.py` — one entry per axis, name and
prompt. Each gets `match` / `minor` / `major` and **one sentence naming an
element**, not an impression.

| axis | the question |
|---|---|
| `content` | anything in the source missing, anything in the render invented |
| `order` | same sequence, bound to the same headings |
| `columns` | what sits beside what — a source column rendered as a stack is `major` |
| `chrome` | borders, cards, rules, fills — drawn where the source draws them **and nowhere else** |
| `type` | is the size and weight hierarchy the same shape |
| `colour` | ground, ink, accent, shaded bands |
| `rhythm` | spacing and density |

Then **`worst fault`** and **`owner`** — which thread or phase owns it, or `new`.

`owner` is what makes the output actionable rather than a list of complaints: it
sorts faults into *fix now*, *already scheduled*, and *nobody knew about this*.
On 2026-09-21 it separated three faults that were mine and fixable that day from
six that belong to A0, A2 and A3.

### What the rubric must never become

**It does not score out of ten, and it never tabulates across sessions.**
CLAUDE.md is explicit that a rubric judgement from one session and one from
another are not comparable, and that this binds a model's visual judgements at
least as strongly as numbers. Every sheet is stamped with its run label and
date. Judge pairwise, in one sitting, or not at all.

---

## Reading the pictures well

What the 2026-09-21 pass learned about doing this, worth keeping:

- **Trace a fault to its cause before reporting it.** "The page looks grey" was
  one bucketing bug. "The cards are missing" and "the page is tinted" were *the
  same* ground-measurement bug, and reporting them separately would have
  produced two wrong fixes.
- **A uniform zero is a bug in the measurement, not a finding about the
  corpus.** `boxed` came back 0 on all fifteen; `filled` came back 0 on
  fourteen. The second was equalisation destroying the signal. Suspect the
  instrument before the subject.
- **Check the honesty findings against what you can see.** `receipt_0010`
  declared "18.5% of ink unread, 19 lines printed and 3 returned" and the
  picture agreed exactly — that is the honesty rule working. `catalogue_0015`
  lost 43% and declared nothing, which is the known undetectable case.
- **A document that looks bad and one that is measured bad are different
  lists.** `catalogue_0015` has the corpus's best `height_ratio` (1.03) and is
  missing its page title and most of its prices.

---

## Known gaps — this is the next work

1. **It cannot answer "what changed since last time".** It compares render
   against source, never render against *previous* render. That is the
   comparison the project actually cares about and the one the T1 ratchet is
   built on. **Highest-value addition.**
2. **The rubric is a guess.** Seven axes, two runs. Some may never fire and some
   fault classes may have no home. Do not freeze it into a skill until a couple
   more passes say which axes earn their place.
3. **No structured output.** `review.md` is prose. A machine-readable form
   would let findings be counted, diffed between runs, and checked against
   `scores.json` — which is how "no scored axis caught this" gets proven rather
   than asserted.
4. **Tall documents are hard to read.** `statement_0006`'s sheet is 5166px and
   the render is nine times the source's height, so the pairing is nearly
   unreadable. Needs per-section pairing, or scaling to a common height.
5. **No tests.** `tools/visual_review.py` has none. At minimum: the sheet is
   built at the source's width, a missing `document.html` is skipped rather than
   crashing, and the run label and date reach the output.
6. **It only reads a run's dump.** It cannot review an arbitrary pair of files,
   which is what a general skill would need.
