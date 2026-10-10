---
name: visual-review
description: Review a conversion run by looking at the rendered pages beside the source documents, and report findings per document on a fixed rubric. Use when asked to review a run's output, to check whether a change improved or damaged the pages, to compare a run against the previous one, or before accepting a change that has only been judged on scores.
---

# Visual review

Compare each rendered page against the document it was made from, and report
what differs, per document, on a fixed rubric.

This exists because the numbers cannot see everything. A run once scored a
document a **full match** while its only table had lost all five column
headers, because the scorer compared row *roles* and never row *content*. The
first time anyone ran this review over all fifteen documents it found nine
faults that no scored axis had reported. So: a score is not a review, and this
is the step that opens the pictures.

---

## Before you start

- **Chrome is required.** `python -c "from doc_to_html.projection import available; print(available())"` must print `True`.
- **A run directory is required**: `debug/runs/<label>/`, containing
  `dump/<model>/<document>/document.html`. A run produces one.
- **Know which previous run to compare against**, if any. `ls debug/runs/`.

---

## Step 1 — Build the sheets

```bash
# against the source only
python tools/visual_review.py debug/runs/94-borders-baseline

# against the source AND the previous run's render  <- prefer this
python tools/visual_review.py debug/runs/95-borders \
    --previous debug/runs/94-borders-baseline

# a few documents while iterating
python tools/visual_review.py debug/runs/95-borders --documents cv_0013,menu_0012

# two arbitrary files, outside any run
python tools/visual_review.py --pair example/invoice.png /tmp/mine.html --out /tmp/rev
```

**Pass `--previous` whenever a previous run exists.** Source-against-render
tells you how far the output is from the page. Render-against-render tells you
whether your change *moved* it, which is the only thing that answers "did this
help".

Everything lands in `<run>/_review/`:

| file | what it is |
|---|---|
| `NN-<document>.png` | the sheet to look at |
| `NN-<document>-p1.png`, `-p2.png` … | a tall document, cut into parts |
| `findings.json` | the form **you** fill in |
| `review.md` | the same form for a person to read |
| `numbers.md` | the scored axes, for quoting only |

---

## Step 2 — Open every sheet

Read each PNG with the Read tool, one at a time. **This is the only step that
finds anything.** Do not skip a document because its numbers look fine — the
worst document in the corpus once had the corpus's *best* height ratio.

### What you are looking at

Each sheet is one document, panels side by side, every panel at the **source's
width** so line wrapping and column behaviour are comparable:

```
┌─ SOURCE (the page) ─┬─ RENDER 94-baseline ─┬─ RENDER 95-borders ─┐
│                     │                      │                     │
│  the screenshot of  │  the previous run's  │  this run's output  │
│  the real document  │  output (--previous) │                     │
│                     │                      │                     │
└─────────────────────┴──────────────────────┴─────────────────────┘
```

- **Left is always the source.** It is the screenshot the model was shown, and
  it is the truth. Never treat the render as the reference.
- **The middle panel only appears with `--previous`.**
- A grey bar across the top of every panel names it and stamps the run and
  date. If you cannot see that bar, you are looking at the wrong file.
- **Tall documents arrive as several parts.** Part 2 of the source is paired
  with part 2 of each render by content, not by height, so the parts line up
  approximately even when a render is five times taller. Read all the parts.

---

## Step 3 — Diagnose before you write

- **Trace a fault to its cause.** "The page looks grey", "the cards are
  missing" and "the page is tinted" were once reported as three faults. They
  were two bugs, and reporting them separately would have produced three wrong
  fixes.
- **A uniform result across every document is a broken instrument, not a
  finding about the corpus.** `boxed` came back `False` on all fifteen
  documents; the detector was looking in the wrong place. Suspect the tool
  before the subject.
- **Check what the render itself admits.** A render may print its own caveats
  ("18.5% of ink unread"). Where the picture agrees with the caveat, that is
  the honesty machinery working, not a new fault.

---

## Step 4 — Fill in `findings.json`

One block per document. Every axis gets a **verdict** and a **note**.

### The severity ladder

| verdict | means |
|---|---|
| `match` | a reader comparing the two would not remark on this axis |
| `minor` | a visible difference that does not change what the document says or how it is read |
| `major` | content is missing or invented, **or** the difference changes how the document reads |

### The axes, with what each verdict looks like

| axis | the question | `minor` looks like | `major` looks like |
|---|---|---|---|
| `content` | is anything in the source missing from the render, or anything in the render not in the source | the footer's copyright line is gone | the whole dark sidebar is absent, including the name |
| `order` | same things, same sequence, bound to the same headings | two label/value pairs in the header are swapped | the last two bullets of the Benefits list appear under the *next* heading |
| `columns` | what sits beside what | the aside is half the width where the source gives it a third | the source's two columns render as one stack |
| `chrome` | borders, cards, rules, fills — drawn where the source draws them **and nowhere else** | a card's rule is drawn but its fill is missing | every titled section is drawn as a bordered card; the source draws two |
| `type` | is the size and weight hierarchy the same shape | `h2` and `h3` render at the same size | body type is 2–3× the source, so the page runs three times the height |
| `colour` | ground, ink, accent, shaded bands | ink is `#555` where the source is `#1a1a1a` | the whole page is rendered on the *card's* colour |
| `rhythm` | spacing and density | paragraph spacing is roughly doubled | forty-one near-identical lines fill the page |
| `changed` | **only with `--previous`**: `better` / `same` / `worse` against the middle panel | — | a `worse` is a ratchet event: say exactly what was there before and is not now |

### Writing a note that is worth reading

**Name the element. Quote the text. Say where on the page.** One sentence.

```
✗  "content — major — a lot of text is missing."
✗  "chrome — minor — the styling looks off."
✗  "type — major — the typography is wrong."

✓  "content — major — the whole dark left sidebar is absent: the name
    'Ines Halloran', the contact block and the skills list."
✓  "chrome — major — all six sections are drawn as bordered grey cards;
    the source draws no border anywhere on this page."
✓  "type — major — body copy renders at roughly 24px against the source's
    10px, which is what makes the page run to five screens."
```

A note that could have been written from `numbers.md` without opening the
picture has not done the job.

### `worst` and `owner`

- `worst` — the axis carrying the worst fault on that document.
- `owner` — where the fault was last worked on, or `new` when nothing has
  touched it. Every phase is closed and nothing is queued since 2026-10-10, so
  `owner` no longer means *already scheduled*. The areas, for reference:
  doubled titles and content loss → `A0`; column collapse and alignment →
  `A2`; heading and label sizes, including a bold body line drawn as `h1` →
  the type scale, `2/B`; figures → `A3`. Figures are drawn from their pixels
  since A3 and repeated caveat lines are one line since 2026-09-26, so either
  one coming back is a regression.

`owner` separates *a known fault, already worked on* from *nobody knew about
this* — what gets fixed next is Alessandro's decision.

**An axis the rubric does not declare is accepted and counted as a trial
axis.** If a fault has no home, add one rather than bending it into an axis
that does not fit.

---

## Step 5 — Tally and report

```bash
python tools/visual_review.py debug/runs/95-borders --check
```

This rewrites `review.md` from your answers and prints:

- **faults no scored axis reported** — a `major` sitting beside scored ratios
  that are all at 1.000, which is the "full match with the headers deleted"
  failure, caught;
- **which axes fired**, and which never did;
- **the owner tally**.

Then report in the conversation, and nowhere else:

1. the worst fault per document, one line each;
2. every `worse` on the `changed` axis, with what was lost;
3. the faults no scored axis reported;
4. the owner tally.

---

## Rules that bind every run of this skill

- **The left panel is the truth.** It is the screenshot the model was shown.
  Never compare against a re-rendered source HTML — several corpus documents
  re-render 7–14% different from their own screenshots on this machine, and
  one wants a CDN this machine does not fetch.
- **Every panel is laid out at the source's width.** A page compared against
  itself at two widths is two different pages.
- **Judge pairwise and in-session.** A verdict from another session is not
  comparable with yours and must never be put in the same table. Both images
  go in front of you now, or the comparison is not made. Every sheet is
  stamped with its run and date for this reason.
- **No scores out of ten.** The output is observations, not a grade.
- **Do not report the deliberately deferred as new faults**: column collapse,
  the type scale and `Zone.align`. Record them with their owner and move on.
- **The rubric is provisional.** Seven axes with a handful of passes behind
  them. `--check` reports which never fired so it can be cut down later. Do
  not treat the current seven as settled.
