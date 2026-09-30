# `reshot/` — the first sweep on whole pictures; the floor and the control 2026-09-29 to 2026-09-30, **now record**

Replaced by `q5-result/` on 2026-09-30, which dominates it on every
ratcheted leg of every document: see that README.

## What this is

The same shape as `a3-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of sweep
  `Q5-10-reshot-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the scores of exactly those files.

Sweep `Q5-10-reshot-sweep`, taken 2026-09-29: all fifteen documents, model
`qwen3-vl:4b` (40%/60% CPU/GPU, which moves timings only), 486 model calls,
on committed code — commit `8f70679`, with nothing uncommitted.

## Why there is a new floor: the pictures were wrong

**The ten authored corpus pictures had been missing their last lines since
2026-09-18.** They were shot before `projection.SHOT_SLACK` existed, in the
commit that added it, and each lost its bottom 60-90px: footers,
`form_0007`'s signature line, the third footnote of `report_0011`,
`cv_0013`'s last publication, `receipt_0010`'s last three lines. The scorer
reads the source's words from the HTML, so up to 266 tokens were counted
against a model that was never shown them. Re-shot whole in `4b6d34d`; two
independent shoots agree to the pixel; `tests/test_projection.py`'s
`TestTheCorpusPictureIsItsOwnHTML` fails on every one of the old pictures.

**The whole picture then exposed a rectifier fault the blank strip had
masked.** `cv_0013`'s dark sidebar now runs the full page height, and
`deskew` rotated the straight page a full 15 degrees — the detector read the
rotated page as one photograph, 13 Zones to 1. Fixed in `8f70679`
(`preprocess._without_panels`): all fifteen pages read level, old pictures and
new. `RECTIFIER_VERSION` 3 -> 4.

**Decided by Alessandro, 2026-09-29, before the sweep:** re-shoot, take one
sweep at HEAD, make it the floor and the control. A floor measured on
pictures that do not contain the page is not a floor.

## What moved against `a3-result`, the floor it replaces

The five original documents' pictures did not change, and **all five came
back byte-identical to `a3-result` re-derived to today's code**, apart from
`"rectifier_version": 4` in the embedded IR. The ten re-shot documents:

| document | vocabulary | precision | tau | beside | height |
|---|---|---|---|---|---|
| `statement_0006` | 0.881 → 0.983 | 0.990 → **0.983** | 0.999 → 0.999 | 1.000 → 1.000 | 2.78 → 2.05 |
| `form_0007` | 0.777 → 0.862 | 0.961 → **0.953** | 0.954 → 0.956 | 0.059 → 0.059 | 0.92 → 0.99 |
| `newsletter_0008` | 0.966 → 0.996 | 0.995 → 0.997 | 0.832 → 0.861 | 0.476 → 0.500 | 1.99 → 2.01 |
| `darkdeck_0009` | 0.940 → 0.976 | 0.996 → 1.000 | 0.836 → 0.856 | 0.875 → 0.968 | 1.64 → 1.65 |
| `receipt_0010` | 0.198 → 0.988 | 1.000 → **0.990** | 1.000 → **0.800** | 1.000 → **0.871** | 1.01 → 2.10 |
| `report_0011` | 0.963 → 0.996 | 0.973 → **0.968** | 1.000 → 1.000 | 1.000 → 1.000 | 1.42 → 1.47 |
| `menu_0012` | 0.828 → 0.992 | 0.993 → 0.994 | 0.829 → 0.923 | 0.349 → **0.348** | 2.29 → 2.57 |
| `cv_0013` | 0.942 → 0.981 | 0.990 → 0.995 | 0.919 → **0.562** | 0.500 → 0.577 | 2.06 → 3.20 |
| `nonlatin_0014` | 0.918 → 0.975 | 0.914 → 0.951 | 0.959 → 1.000 | 0.912 → 1.000 | 1.63 → 1.48 |
| `catalogue_0015` | 0.617 → 0.843 | 1.000 → 1.000 | 0.943 → **0.938** | 0.288 → **0.252** | 0.97 → 1.19 |

Means over fifteen: vocabulary recall **0.8667 → 0.9708**, recall 0.8542 →
0.9664, join recall 0.8225 → 0.9434, precision 0.9851 → 0.9865; tau 0.9483 →
0.9232, beside 0.7458 → 0.7536, height 1.479 → 1.610.

**It does not dominate `a3-result`, and every fall is named here, because a
floor re-cut is the one place the ratchet is allowed to give ground.** Each is
the pipeline's own behaviour on the true picture — a different crop read
differently — not a change to the pipeline:

- **Four words stopped printing.** `cv_0013`'s `Revit` and `Python`: the
  sidebar is no longer one detected picture, so each skill is its own tiny
  Zone, and both were classified as figures, which puts their words in `alt`.
  `menu_0012`'s `chervil` is read `cheril` in the regrouped table crop.
  `catalogue_0015`'s `CP-402` badge is not read in a pairs crop that now runs
  a little lower.
- **`cv_0013` tau 0.919 → 0.562**: the same split sidebar interleaves with the
  main column Band by Band.
- **Precision**: `statement_0006` prints `Totals for the period` twice — a new
  sliver Zone overlapping the table, which is also why the snap is refused on
  that document; `form_0007` misreads its new footer (`Castletown` ×2,
  `ferpost`); `receipt_0010` reads `A000000031010`, one zero short.
  **`report_0011`'s fall is the scorer's, not the output's** — corrected
  2026-09-30; this line first said the output printed its footnotes' numbers
  as text. Every token it counts as invented is a section or footnote number
  the source draws with a CSS counter or an `<ol>` marker, which `project()`
  cannot see (spec 0007, "Why `Completeness.duplicated` is not the gate").
  On the truncated picture the footer was not read, so its `1 of 1` absorbed
  two of them; it is read now, and the third footnote's `3.` joins them. The
  output prints what the picture shows.
- **`receipt_0010`'s tau and beside** fall from values taken over 4 matched
  blocks and 0 side-by-side pairs to values taken over the whole receipt; its
  rows are drawn out of order, which spec 0007's queue, Q5, fixes.

## It is also the control

**Proved on the day it was frozen, both ways:**

- scored straight out of `documents/`: **15 documents, 0 differing fields**;
- `tools/rederive.py` over the sweep, at `8f70679`: **15 of 15 byte-identical**
  to the sweep's own documents — so it is also today's baseline, until code
  downstream of the model moves again.

Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/reshot/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.

`a3-result/` and every older directory are kept as record; none is a floor.
