# Visual Review

How to look at what this project produced, beside what it was given, and come
back with something a person can act on.

**The procedure is a skill: [`.claude/skills/visual-review/`](../../.claude/skills/visual-review/SKILL.md).**
Invoke it to review a run. This file is the record behind it — why it exists,
what its rules were measured against, and what it still cannot do.

---

## Why it exists

`report.html` answers *what do the numbers say*. This answers *what does it
look like*, and the two catch different things.

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

## The evidence behind the skill's three rules

**The reference is the PNG, not the re-rendered source HTML.** The screenshot
is what the model was shown and what a person compares against. Four of the
five original documents re-render 6.9–14.1% different from their own
screenshots on this machine, and `invoice2.html` additionally wants a CDN —
comparing against the HTML would show differences nobody introduced.

**Both sides are laid out at the source's width.** A page compared against
itself at two widths is two different pages. `project()` already takes this
position for scoring; the review takes the same one so the two never disagree.

**Pairwise and in-session only.** CLAUDE.md is explicit that a rubric
judgement from one session and one from another are not comparable, and that
this binds a model's visual judgements at least as strongly as numbers. Every
sheet and every form is stamped with its run label and date for that reason,
and `summarise()` carries the stamp through to the report.

---

## The rubric

`RUBRIC` in `src/doc_to_html/review.py` — one entry per axis, name and prompt.
Each gets `match` / `minor` / `major` and **one sentence naming an element**,
not an impression.

| axis | the question |
|---|---|
| `content` | anything in the source missing, anything in the render invented |
| `order` | same sequence, bound to the same headings |
| `columns` | what sits beside what — a source column rendered as a stack is `major` |
| `chrome` | borders, cards, rules, fills — drawn where the source draws them **and nowhere else** |
| `type` | is the size and weight hierarchy the same shape |
| `colour` | ground, ink, accent, shaded bands |
| `rhythm` | spacing and density |
| `changed` | **only with `--previous`**: `better` / `same` / `worse` against the previous render |

Then **`worst fault`** and **`owner`** — which thread or phase owns it, or `new`.

`owner` is what makes the output actionable rather than a list of complaints: it
sorts faults into *fix now*, *already scheduled*, and *nobody knew about this*.
On 2026-09-21 it separated three faults that were mine and fixable that day from
six that belong to A0, A2 and A3.

### What the rubric must never become

**It does not score out of ten, and it never tabulates across sessions.** Judge
pairwise, in one sitting, or not at all.

**It is not frozen.** Seven axes, two passes. `--check` reports which axes never
fired, so a later session can cut the ones that do not earn their context; and
an axis the rubric does not declare is **accepted and counted as a trial axis**
rather than rejected, so trying an eighth needs no code change. Freeze it when
the firing record says which seven, not before.

---

## Reading the pictures well

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

## What closed the 2026-09-21 gap list

Five of the six gaps are closed; `doc_to_html.review` holds the code and
`tests/test_review.py` pins it. What each one cost is worth keeping, because
two of the fixes were found by *using* the tool rather than by reasoning about
it.

1. **"What changed since last time" — closed.** `--previous <run>` adds the
   previous run's render as a middle panel and the `changed` axis to the form.
   Source-against-render says how far the output sits from the page;
   render-against-render says whether it *moved*, which is the comparison the
   T1 ratchet is built on.
2. **The rubric is a guess — deliberately still open.** See above.
3. **Structured output — closed.** `findings.json` is the answered form;
   `--check` tallies it, writes `review.md` back out, and names the **faults no
   scored axis reported**: a `major` sitting beside scored ratios all at 1.000.
   One is not a threshold somebody chose; it is the ceiling, which is where
   `sample_table_0003` stood having deleted every column header of its only
   table. A filled `findings.json` is never overwritten by a rebuild.
4. **Tall documents — closed, after two wrong answers.** A sheet is cut into
   parts, each bounded by `MAX_SHEET_PX` (1600 — an image reaches the reviewer
   downsampled to about 1568px on its long edge, so `statement_0006`'s 5166px
   sheet arrived at 30% scale with 10px type rendered at 3px). *Cutting by
   height* pairs part 2 of the source with part 2 of nothing in particular.
   *Cutting by ink mass* pairs the content and then produced a **3316px part**,
   because 84% of that render's ink is in its first 1900 rows and the 3200 rows
   after it are the sparse repeated caveats. `BLEND` is half of each, and
   `plan()` then adds parts until the cap is actually met — five sheets, the
   tallest 1631px.
5. **Tests — closed.** `tests/test_review.py`, none of which needs a browser:
   the screenshot function is injected. They pin matched width, the skipped
   document, the stamp reaching every output, the cut landing in a gutter and
   following ink, dark-grounded pages being read the right way up, the label
   bar being **drawn** rather than merely reserved (it had been reserved and
   left blank), and — found by running the thing — that a summary with no
   `scores.json` says *not checked* rather than claiming the numbers noticed.
6. **Reviewing an arbitrary pair — closed.** `--pair <source.png> <render>`,
   outside any run directory.

---

## Known gaps — what is still missing

1. **The rubric is still a guess.** Gap 2 above, left open on purpose. `--check`
   now collects the evidence; a couple more passes decide.
2. **`changed` is judged by eye, not measured.** Three panels on one sheet is
   what makes the comparison possible; nothing yet diffs the two renders'
   pixels or projections to point at *where* they differ, so a small regression
   in a dense document can still be missed.
3. **Findings are not diffed between runs.** Two `findings.json` files could be
   compared — a `major` that was there last time and is not now, and the
   reverse — but they are not, and doing it must not become a cross-session
   table, which is the whole constraint.
4. **The pairing is approximate and says so, but does not say how
   approximate.** `BLEND` is a trade, not a measurement; a sheet does not
   report how far its two parts actually drifted apart.
