# `s3-result/` — spec 0008's sweep, and **the floor and the control** since 2026-10-11

> **Three legs sit below `q5-result/`, the floor before it, by decision.**
> Alessandro accepted them on 2026-10-11 after reviewing the sweep: T3
> beside on `cv_0013` (0.5769 → 0.4000) and `darkdeck_0009` (0.9677 →
> 0.8148), the price of reading their columns as columns rather than as the
> Band render's cross-column rows; and precision on `catalogue_0015`
> (1.0000 → 0.9940), one `×` read as `x` on a spec line that was not printed
> at all before. **N4's recorded exception is gone:** `catalogue_0015`'s
> beside is 0.2727 here, above `q5-result/`'s 0.2523. No leg on this
> directory sits below its own floor — it *is* the floor.

## What this is

The same shape as `q5-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of
  sweep `S3-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the sweep's own scores of exactly those files, against
  `q5-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, with whether it came back truncated:
  written by `tools/replay_run.py debug/runs/S3-sweep --save-answers`.
  490 calls.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

Sweep `S3-sweep`, taken 2026-10-10: all fifteen documents, model
`qwen3-vl:4b` (54%/46% CPU/GPU, which moves timings only), 490 model calls,
1h31m wall clock, on committed code — commit `9c42d81`, spec 0008 step 3.

## What it is for

**It is the control:** the fifteen documents today's code makes, so every
"unchanged" in a gate is measured against it. Four loops run over it, and
each was proved on 2026-10-11, the day it was frozen, at commit `8329bad`
(docs only since `9c42d81`):

- scored straight out of `documents/`: **15 documents, 0 differing fields**
  against `scores.json`;
- `tools/rederive.py tests/frozen/s3-result --label S3-base`: **15 of 15
  byte-identical** to `documents/`. `debug/runs/S3-base` is this directory
  as a run directory, and spec 0009's sheets use it as `--previous`;
- `tools/replay_run.py tests/frozen/s3-result`, serving `answers/` to a real
  Conversion: **15 of 15 byte-identical**;
- and `tools/layout_front.py`'s Zones match its IRs' band, column and bbox on
  **15 of 15**.

**It is also the floor**, Alessandro's decision on 2026-10-11, with the three
legs above accepted below `q5-result/`.

## What moved against `q5-result/`

Seven documents. Four by spec 0008 (its "Outcome" sections), and three by
N1–N4, which changed what the code makes from the same answers between
`q5-result/` (2026-09-30) and spec 0008. The other eight score identically.
Ratcheted legs and height, `q5-result/` → here; a blank cell did not move:

| document | vocabulary recall | precision | tau | beside | height |
|---|---|---|---|---|---|
| `catalogue_0015` | 0.8435 → **0.9913** | 1.0000 → **0.9940** | 0.9379 → 1.0000 | 0.2523 → 0.2727 | 1.190 → 1.068 |
| `cv_0013` | | | 0.5616 → 0.9838 | 0.5769 → **0.4000** | 3.203 → 1.965 |
| `darkdeck_0009` | | | 0.8556 → 0.9805 | 0.9677 → **0.8148** | 1.654 → 1.315 |
| `newsletter_0008` | | | 0.8615 → 1.0000 | 0.5000 → 0.7000 | 2.008 → 1.668 |
| `statement_0006` | | 0.9827 → 0.9903 | | | 2.046 → 1.600 |
| `invoice_0002` | | | | | 1.436 → 1.309 |
| `receipt_0010` | | | | | 2.260 → 2.163 |

Bold is a leg that fell. No word `q5-result/` printed stops being printed
here: `Completeness.vanished` gains nothing on any document, and seventeen
distinct words it held on `catalogue_0015` are printed again.

Corpus means, `q5-result/` → here: vocabulary recall 0.9708 → 0.9806, recall
0.9664 → 0.9779, precision 0.9865 → 0.9866, join recall 0.9434 → 0.9538, tau
0.9366 → 0.9864, beside 0.7622 → 0.7549, height ratio 1.621 → 1.441.
`hard_breaks` 5, `figures_lost` 0, T6 inline runs 8 of 42.

Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s3-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
