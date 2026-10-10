# `q5-result/` — Q5's sweep, and **the floor and the control** since 2026-09-30

> **One leg sits below this floor by decision.** Since N4, 2026-10-10,
> `catalogue_0015`'s T3 beside is 0.2364 against this directory's 0.2523:
> the render it froze broke `each` one letter to a line, and the tall broken
> word overlapped four of its neighbours' rows. Alessandro accepted the
> crossing; every report against this directory names it, and no other leg
> may fall. See `docs/status.md`, "What the ratchet enforces".
>
> **Nor is it still exactly what today's code makes.** N1–N4 (2026-09-30 to
> 2026-10-10) changed four things downstream of the model — Shortfalls, Gaps,
> `statement_0006`'s Zones and the pairs grid. `F1-sweep`, taken 2026-10-10,
> is today's code end to end; whether it becomes the control is Alessandro's
> decision.

## What this is

The same shape as `reshot/`, plus the answers:

- **`documents/<name>.html`** — the fifteen rendered output documents of sweep
  `Q5-40-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the scores of exactly those files, against `reshot/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, with whether it came back truncated:
  the sweep's `trace.json` calls with their prompts dropped, written by
  `tools/replay_run.py --save-answers`. The first frozen directory to carry
  them.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

Sweep `Q5-40-sweep`, taken 2026-09-30: all fifteen documents, model
`qwen3-vl:4b` (54%/46% CPU/GPU, which moves timings only), 491 model
calls, on committed code — commit `d9a0d39`, whose code is `2d918df`'s; the
commit between them wrote Q5's gate into `docs/status.md` before the sweep
started.

## What it is for

**It is the control:** the fifteen documents today's code makes, so every
"unchanged" in a gate is measured against it. Three loops run over it with no
model, and each was proved on the day it was frozen:

- scored straight out of `documents/`: **15 documents, 0 differing fields**;
- `tools/rederive.py tests/frozen/q5-result`: **15 of 15 byte-identical** to `documents/` — `reshot/` cannot do
  this for `receipt_0010`, because Q5's `detector.prefer_container` rule gives
  the receipt two more Zones and `rederive.py` does not re-run the detector;
- `tools/replay_run.py tests/frozen/q5-result`, serving `answers/` to a real
  Conversion: **15 of 15 byte-identical**, and 15 of 15 again from the sweep's own traces;
- and `tools/layout_front.py`'s Zones match its IRs' band, column and bbox on
  15 of 15.

**It is also the floor**, Alessandro's decision on 2026-09-30. Against
`reshot/`, the floor it replaces: fourteen documents are byte-identical, and
`receipt_0010` is no lower on any ratcheted leg — tau 0.800 → 1.000, beside
0.871 → 1.000, vocabulary recall and precision unchanged at 0.9877 and 0.9903.
So it dominates `reshot/` on every ratcheted leg of every document, the
condition every floor move before `reshot/` met.

## What moved against `reshot/`

Only `receipt_0010`, by Q5's three changes (spec 0007's handover, "Outcome —
Q5"): its rows are drawn in printed order with no `<tfoot>`, its column-sum
reconciles at 26.45, and its barcode is drawn from its pixels in a Zone of its
own, between the farewell line and the last three lines — 3 Zones became 5 and
11 model calls 16. Fields that moved on it:

| field | `reshot/` | here |
|---|---|---|
| tau | 0.800 | **1.000** |
| beside agreement | 0.871 over 31 pairs | **1.000** over 29 |
| height ratio | 2.10 | 2.26 — the barcode's height |
| `columns_within_tolerance` | 0.875 | 0.775 |
| `column_error` | 0.078 | 0.125 |
| `alignment_agreement` | 0.489 | 0.533 |
| `short_lines` | 1 | 4 |

The two column fields are not ratcheted and fell for a reason the review saw:
the farewell, the barcode and the last three lines are now three blocks, each
drawn at the left where the source centres it (`Zone.align`, deferred). Every
other document: 0 differing fields.

Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/q5-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
