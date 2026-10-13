# `s6-result/` — spec 0011's sweep, and **the baseline** since 2026-10-13

> **Taken as the baseline by Alessandro on 2026-10-13**, after reviewing
> `S6-sweep` against `S5-sweep`: fourteen pages better, `sample_css_0004`
> the same, none worse. Work is judged by eye on the sheets; scores are
> recorded, never gating. The one number still read is a report's
> `vanished` list, as a pointer to a page to open.
>
> **Four beside legs sit below `s5-result/`, the floor before it:**
> `catalogue_0015`, `cv_0013`, `darkdeck_0009` and `menu_0012`. No
> vocabulary, precision or tau leg falls on any document. Each beside fall
> is cross-column coincidence: a line in one column sharing a row with a
> line in another, which flips when either column wraps differently. Spec
> 0011's "Outcome — step 5", §3a, has the trace.

## What this is

The same shape as `s5-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of
  sweep `S6-sweep`. Each carries its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the sweep's own scores of exactly those files, against
  `s5-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, with whether it came back truncated.
  Written by `tools/replay_run.py debug/runs/S6-sweep --save-answers`.
  518 calls.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

**Provenance.** Sweep `S6-sweep`, taken 2026-10-12 20:49–22:31.
- All fifteen documents; model `qwen3-vl:4b`, 40%/60% CPU/GPU, which moves
  timings only; 518 model calls.
- Committed code: commit `7c12935`, spec 0011 with its step 5 prediction
  registered.
- **The prediction held.** Every one of its 518 answers is byte-identical
  to `S5-sweep`'s (`s5-result/answers/`), call for call. Every document is
  byte-identical to the replay of step 4's last commit: spec 0011 changed
  nothing the model is asked.

## What it is for

**It is the baseline:** the fifteen documents today's code makes. Three
loops run over it. Each was proved on 2026-10-13, the day it was frozen, at
commit `dac286e` (docs only since `7c12935`):

- **Scores:** a rederive of `documents/`, scored against `s5-result/`, gives
  **15 documents, 0 differing fields** against `scores.json`.
- **Replay:** `tools/replay_run.py tests/frozen/s6-result --label
  S7-0-replay` serves `answers/` to a real Conversion and reproduces
  **15 of 15 byte-identical**.
- **Rederive:** `tools/rederive.py tests/frozen/s6-result --label
  S7-0-base` gives **15 of 15 identical pages, 14 of 15 byte-identical
  files**.
  - `form_0007` differs in one field of its embedded IR: Zone 5's `align`
    is `null` in the sweep and `"left"` after a rederive. `left` is the
    house default, so the page is the same.
  - The cause is step order. Step 3 (`fields.read`) turns Zone 5 from a
    table into pairs after step 1 (`rhythm.read`) has skipped it as a
    table. A rederive starts from the finished IR, so step 1 sees pairs.
  - Until that is fixed, compare this document's rederive outside its IR.

## What moved against `s5-result/`

Ratcheted legs and height, `s5-result/` → here. A blank cell did not move,
and bold is a leg that fell:

| document | vocabulary recall | precision | tau | beside | height |
|---|---|---|---|---|---|
| `catalogue_0015` | | | | 0.2874 → **0.2428** | 0.728 → 0.725 |
| `cv_0013` | | | | 0.4839 → **0.4375** | 1.666 → 1.231 |
| `darkdeck_0009` | | | | 0.6579 → **0.5827** | 1.250 → 1.148 |
| `form_0007` | | | 0.9623 → 0.9948 | 0.1667 → 1.0000 | 1.082 → 1.051 |
| `invoice_0001` | | | | | 1.085 → 1.020 |
| `invoice_0002` | | | | | 1.263 → 1.199 |
| `menu_0012` | | | | 0.4154 → **0.3881** | 1.549 → 1.306 |
| `newsletter_0008` | | | | 0.6500 → 0.8947 | 1.361 → 1.159 |
| `nonlatin_0014` | | | | 0.9853 → 0.9855 | 1.119 → 1.056 |
| `receipt_0010` | | | | | 1.889 → 1.576 |
| `report_0011` | | | | | 1.213 → 0.991 |
| `sample_css_0004` | | | | | 1.009 → 0.949 |
| `sample_semantic_0005` | | | | 0.8750 → 1.0000 | 0.856 → 0.970 |
| `sample_table_0003` | | | | | 1.228 → 1.071 |
| `statement_0006` | | | | | 1.310 → 1.151 |

Corpus means, `s5-result/` → here:
- vocabulary recall 0.9876 → 0.9876;
- precision 0.9881 → 0.9881;
- tau 0.9875 → 0.9896;
- beside 0.7638 → 0.8311;
- height ratio 1.241 → 1.107.

`vanished` is the same 26 words on the same documents.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s6-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
