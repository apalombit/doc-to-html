# `s14-result/` — spec 0019's sweep, twenty-one documents, and **the baseline** since 2026-10-23

> **Alessandro took it as the baseline on 2026-10-23**, after reviewing
> spec 0019's sweep. By eye against `S13-sweep`, fourteen pages are
> better, seven the same and none worse. Work is judged by eye on the
> sheets. Scores are recorded and never gate.

## What this is

The same shape as `s13-result/`:

- **`documents/<name>.html`**: the twenty-one rendered output documents,
  exactly as the sweep wrote them. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`scores.json`**: their scores, taken against `s13-result/scores.json`.
- **`answers/<name>.json`**: every model answer each document's
  Conversion received, in the order it was asked, each with its `asked`
  hashes (prompt, picture, schema). **811 calls.**
  - Written by `tools/replay_run.py debug/runs/S14-sweep --save-answers
    tests/frozen/s14-result`.
  - Every answer and hash was checked against the sweep's `trace.json`,
    and 0 differ.
  - **The first 755 are `s13-result/`'s, byte for byte and in order.**
    The other 56 are spec 0019 D2's third readings, on 17 pages. Four
    files are byte-identical to `s13-result/`'s: darkdeck, invoice_0001,
    sample_semantic and sample_table.
- **`dth_env.txt`**: the `DTH_*` variables the sweep ran under. There are
  none, so these are the shipped defaults.

## Provenance

**Sweep `S14-sweep`**:
- commit `a0d73c9`, spec 0019's last step (D2);
- taken 2026-10-23, 08:17 to 10:55, **2h38m**;
- model `qwen3-vl:4b` at 40%/60% CPU/GPU, which moves timings only.

All twenty-one documents converted, and the script ran to its end.

It measures spec 0019's A0–A1, B1–B4, C1–C5, D1, the second pass's
repairs and D2. A2 had no pages, and D3 is recorded only.

**The spec's registered prediction held to the byte, every clause:**
- the 755 baseline calls were asked and answered alike, and the 56 third
  readings came on the pages registered, each page's count as registered;
- the four pages asked nothing new rendered byte-identical to
  `S14-prediction`, a replay of `s13-result/` at the sweep's commit;
- the nine pages asked on a targeted run rendered byte-identical to those
  runs' replays at the sweep's commit.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes.
Three loops run over it, each proved on 2026-10-23 at `a0d73c9`:

- **Replay:** `tools/replay_run.py tests/frozen/s14-result --label
  <label>` reproduces **21 of 21 byte-identical, 0 asked differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s14-result --label
  <label>` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored, gives **21 documents, 0 differing
  fields** against `scores.json`.

Score later runs against it:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s14-result/scores.json
```

## What moved against `s13-result/`

Fourteen pages better:
- the timetable, paper, report, the two invoices, the certificate,
  sample_css, the newsletter, the statement, nonlatin and the ticket, as
  their parts targeted;
- form, cv and letter besides.

Seven the same: menu, catalogue, darkdeck, pricing, receipt,
sample_semantic and sample_table. Spec 0019's "Outcome — the sweep" has
each page's sentence.

**Three ratchet legs are below `s13-result/scores.json`**, each traced:
- **the certificate's beside, 1.000 → 0.556:** 9 pairs measured where 2
  were, its signature blocks now matched;
- **the catalogue's beside, 0.901 → 0.851:** a 1px margin, two heading
  weights and `Orders:`, with nothing changing what sits beside what by
  eye;
- **the report's precision, 0.966 → 0.962:** its raised footnote
  markers, printed by the page and now drawn.

**`vanished`: 15 words**, from 24, and no word is newly vanished.
