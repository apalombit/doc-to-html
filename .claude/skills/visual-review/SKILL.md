---
name: visual-review
description: Review a conversion run by looking at the rendered pages beside the source documents. The exact checks run first and arrive filled in; Claude confirms each by looking, names its stage, adds what the HTML cannot settle, and ranks the fault classes. Use when asked to review a run's output, to check whether a change improved or damaged the pages, to compare a run against the previous one, or before accepting a change judged only on scores.
---

# Visual review

Open each rendered page beside the document it was made from, and report
its **faults**, each with its class, severity, element and stage. The
criteria are `docs/agents/review-criteria.md` (agreed with Alessandro,
2026-10-24): **the render must look like the page.** Every severity below
comes from there.

The numbers cannot see everything. A document once scored a full match
after its only table lost all five column headers. The first review over
all fifteen documents found nine faults no scored axis had reported. A
score is not a review: this is the step that opens the pictures.

---

## Before you start

- **Chrome is required.** `python -c "from doc_to_html.projection import available; print(available())"` must print `True`.
- **A run directory is required**: `debug/runs/<label>/`, holding
  `dump/<model>/<page>/document.html`. A sweep or `tools/batch.py` makes
  one.
- **Know the previous run**, if any (`ls debug/runs/`). Pairwise is the
  stronger review.

---

## Step 1 — One command

```bash
python tools/measure_run.py debug/runs/<label>                       # against the source
python tools/measure_run.py debug/runs/<label> --previous debug/runs/<older>
python tools/measure_run.py debug/runs/<label> --all                 # open every page
```

It runs the exact checks on every page (`doc_to_html.checks`, spec 0021).
They need no model: both sides are read from the HTML at the source's
width. A page's checks are kept until its output or the checks' code
changes. Then it picks the pages to open, builds their sheets and writes
the form.

| file | what it is |
|---|---|
| `checks/report.md` | what the checks found: by class, family and feature, words lost and invented, pages opened and why |
| `checks/<page>.json` | one page's faults, with their boxes |
| `_review/NN-<page>.png` (`-p2` …) | the sheet: source, previous render, this render |
| `_review/NN-<page>-tileK.png` | a dense page's strip of the source over the same strip of the render, full scale |
| `_review/NN-<page>-diff.png` | with `--previous`: this render faded, red where it differs from the previous one |
| `_review/findings.json` | **the form you answer**, the checks' faults filled in |
| `_review/review.md` | the same form for a person |

**Which pages are opened**:
- every page where a check finds a major in **cells, rules, structure or
  order**, which a reader must confirm;
- every page a change **moved** (its render differs from the previous
  run's);
- **two more per family**, drawn by seed.

A page flagged only by words, lines, height, alignment or type is counted
in the report, not opened. Those checks read the HTML exactly.

---

## Step 2 — Read the report, then open every sheet

`checks/report.md` first: it says what to expect. Then read each opened
page's PNGs with the Read tool, one at a time, tiles and diff included.
**This is the step that finds anything.**

```
┌─ SOURCE (the page) ─┬─ RENDER <older> ─┬─ RENDER <label> ─┐
│  the screenshot:    │  --previous only │  this run        │
│  the truth          │                  │                  │
└─────────────────────┴──────────────────┴──────────────────┘
```

- **Left is always the source**, the picture the model was shown.
- **Each fault a check found is a numbered magenta box** on the source and
  on this render. The number is its `n` in the form. Its tag stands left
  of the box and is see-through, so a marker under it still shows.
- A grey bar names each panel and stamps the run and date. No bar means
  the wrong file.
- **Tall pages arrive in parts**, paired by content. Read them all.
- **Tiles** come with a page whose body type would reach you too small to
  read (`review.LEGIBLE_PX`). Each strip of the render is found by where
  the source's words landed, not by height.

---

## Step 3 — Answer `findings.json`

One entry per page; `opened: true` are yours. For each **fault a check
found** (`"from": "check"`):

- `call`: **`confirmed`** if the picture shows it, **`rejected`** if it
  does not. Markup can still fool a check. A rejection needs `why`: one
  sentence on what the picture shows instead.
- `stage`: where it was made. Use one of `rectify, layout, caption,
  classify, extract, inline runs, re-read, third reading, wire, locate,
  render`, or `cv:<pass>` for a CV pass (`cv:furniture`). **Read it from
  the page, never guess it from the picture.** The IR is
  `document.html`'s `<script id="doc-ir">`, and `trace.json` sits beside it.
  `python tools/inspect_run.py <run>/dump/<model>/<page> --source <png>`
  draws each step. Which Zone holds the words? What did the model answer
  for that crop? What did the wire make of it?

**Add every fault the checks cannot see**, with `"from": "review"`, the
next `n`, and `check` set to one of these areas:

| area | major | minor |
|---|---|---|
| `words` | a word or number lost, invented, changed or merged | — |
| `structure` | a cell in the wrong row or column; a label over its value flattened; numbered steps as bullets; content under the wrong heading; two blocks interleaved | the right look from the wrong HTML |
| `layout` | a line breaking at another word; height off by more than 10%; alignment changed; **what sits beside what** (a source column drawn as a stack) | height off by up to 10% |
| `type` | the wrong face class; sizes out of proportion; bold printed regular | italics, letterspacing, small caps |
| `looks` | the wrong ground; a colour that carries meaning lost; a fill, band, frame or rule missing | a colour off within its family; chips as plain text; a legend's swatches missing |
| `figures` | — | any figure missing or imperfect: logos, barcodes, icons, signatures, photos |

Each added fault takes `fault` (its class, a few words: `beside`,
`fill missing`), `severity`, `element` (the words, quoted), `note`,
`features` (the page's card features it bears on, from the manifest),
`stage`.

**A note names the element, quotes the text, and says where.**

```
✗  "the table looks wrong"
✓  "the four results 6.4, 231, 84, 92 sit under Flag, one column right of Result"
```

With `--previous`, each page also takes `changed`, `better / same /
worse`, and `changed_note` saying what moved. A `worse` says exactly what
was there before and is not now. `worst` is the `n` of the page's worst
fault.

**Across the run, `ranked`**: the fault classes in the order to fix them,
each `{"check", "fault", "why"}`. Majors first, then the biggest visible
gain for the effort. The reasoning goes in `why`.

---

## Step 4 — Tally and report

```bash
python tools/visual_review.py debug/runs/<label> --check
```

It rewrites `review.md` with the ranked classes, the pages where the
review **overturns a check** (a fault rejected, or a major added), every
`worse`, and what is still unanswered (a call missing, a major with no
stage). It refuses a form of another rubric.

Then report in the conversation:
1. the ranked fault classes, with pages touched and why;
2. the pages where you overturn a check, for Alessandro to spot-check,
   with the three known-fault pages and two at random (spec 0021,
   decision 2); in a pairwise review, every page called worse, plus two
   at random;
3. every `worse`, with what was lost.

---

## Rules that bind every run of this skill

- **The left panel is the truth**: the screenshot, never the re-rendered
  source HTML.
- **Every panel is laid out at the source's width.**
- **Pairwise and in-session.** A call from another session is not
  comparable with yours and never goes in one table with it. Every sheet is
  stamped with its run and date for this reason.
- **No scores out of ten.** Faults, with the criteria's severities.
- **Never guess a stage.** If the IR and the trace do not say, write
  `null` and say why in the note.
- **A uniform result is a broken instrument.** A check firing on every
  page, or never, is suspected before the pages are.
- **Every disagreement with Alessandro changes the checklist**: this skill,
  or a check, re-tested on all his past calls
  (`docs/agents/review-calls/`).
