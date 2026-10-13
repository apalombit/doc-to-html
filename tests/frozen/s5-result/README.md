# `s5-result/` — spec 0010's sweep; the baseline 2026-10-12 to 2026-10-13, now record

> **Record since 2026-10-13**, when `s6-result/` became the baseline.

> **For spec 0011 the scores here are recorded, not gated.** Alessandro's
> operating preference of 2026-10-12: every step is judged by opening its
> sheets against the previous step's. The ratchet is reported and never
> decides a step. The one number still read is a report's `vanished` list,
> as a pointer to a page to open.
>
> **Five legs sit below `s3-result/`, the floor before it, by decision.**
> Alessandro accepted them on 2026-10-12 after reviewing the sweep:
> `darkdeck_0009` tau and beside (its P95 tile read as a table, whose `P95`
> and `184 ms` the scorer pairs with the component table's); `menu_0012`
> vocabulary and precision (`béarnaise` read without its accent); one
> precision token on `report_0011` (the caption's `1`, counted surplus
> against the `<ol>` footnote numbers); and one coincidental beside pair
> each on `newsletter_0008` and `nonlatin_0014`. Spec 0010's "Outcome —
> step E", §5, has the cause of each.

## What this is

The same shape as `s3-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of
  sweep `S5-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the sweep's own scores of exactly those files, against
  `s3-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, with whether it came back truncated:
  written by `tools/replay_run.py debug/runs/S5-sweep --save-answers`.
  518 calls.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

Sweep `S5-sweep`, taken 2026-10-11: all fifteen documents, model
`qwen3-vl:4b` (40%/60% CPU/GPU, which moves timings only), 518 model calls,
on committed code — commit `4a5fe3f`, spec 0010 step D. **Every one of its
518 answers is byte-identical to `S4-sweep`'s**, call for call, checked
again on 2026-10-12 against both runs' traces: spec 0010 changed nothing
the model is asked.

## What it is for

**It is the baseline:** the fifteen documents today's code makes, against
which every step of spec 0011 is opened. Three loops run over it, each
proved on 2026-10-12, the day it was frozen, at commit `72477f2` (docs only
since `4a5fe3f`):

- scored straight out of a rederive of `documents/` (below): **15
  documents, 0 differing fields** against `scores.json`;
- `tools/rederive.py tests/frozen/s5-result --label S6-0-base`: **15 of 15
  byte-identical** to `documents/`;
- `tools/replay_run.py tests/frozen/s5-result --label S6-0-replay`, serving
  `answers/` to a real Conversion: **15 of 15 byte-identical**.

## What moved against `s3-result/`

Fourteen documents. Ratcheted legs and height, `s3-result/` → here; a
blank cell did not move:

| document | vocabulary recall | precision | tau | beside | height |
|---|---|---|---|---|---|
| `form_0007` | 0.8615 → 0.9462 | 0.9527 → 0.9693 | 0.9561 → 0.9623 | 0.0588 → 0.1667 | 0.993 → 1.082 |
| `darkdeck_0009` | 0.9759 → 1.0000 | | 0.9805 → **0.9192** | 0.8148 → **0.6579** | 1.315 → 1.250 |
| `menu_0012` | 0.9922 → **0.9844** | 0.9938 → **0.9877** | 0.9232 → 0.9939 | 0.3478 → 0.4154 | 2.573 → 1.549 |
| `report_0011` | 0.9959 → 1.0000 | 0.9679 → **0.9663** | | | 1.470 → 1.213 |
| `newsletter_0008` | | | | 0.7000 → **0.6500** | 1.668 → 1.361 |
| `nonlatin_0014` | | 0.9510 → 0.9652 | | 1.0000 → **0.9853** | 1.479 → 1.119 |
| `invoice_0002` | | | | 0.8542 → 0.9348 | 1.309 → 1.263 |
| `cv_0013` | | | | 0.4000 → 0.4839 | 1.965 → 1.666 |
| `catalogue_0015` | | | | 0.2727 → 0.2874 | 1.068 → 0.728 |
| `statement_0006` | | | | | 1.600 → 1.310 |
| `receipt_0010` | | | | | 2.163 → 1.889 |
| `sample_css_0004` | | | | | 0.918 → 1.009 |
| `sample_semantic_0005` | | | | | 0.783 → 0.856 |
| `sample_table_0003` | | | | | 1.217 → 1.228 |

Bold is a leg that fell. The one word `s3-result/` printed that this
directory does not is `menu_0012`'s `béarnaise`, printed `bearnaise`.
`invoice_0001` scores identically.

Corpus means, `s3-result/` → here: vocabulary recall 0.9806 → 0.9876,
recall 0.9779 → 0.9860, precision 0.9866 → 0.9881, join recall 0.9538 →
0.9599, tau 0.9864 → 0.9875, beside 0.7549 → 0.7638, height ratio 1.441 →
1.241.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s5-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
