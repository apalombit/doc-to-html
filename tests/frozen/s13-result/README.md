# `s13-result/` — spec 0018's sweep, twenty-one documents, and **the baseline** since 2026-10-19

> **Alessandro took it as the baseline on 2026-10-19**, after reviewing
> spec 0018's sweep. By eye against `S12-sweep`, three pages are better
> (the ticket, pricing, cv), eighteen the same and none worse. Work is
> judged by eye on the sheets. Scores are recorded and never gate.

## What this is

It has the same shape as `s12-result/`:

- **`documents/<name>.html`**: the twenty-one rendered output documents,
  exactly as the sweep wrote them. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`scores.json`**: their scores, taken by spec 0018's 0b scorer, which
  measures the source in its paper's frame. It was scored against
  `s12-result/scores-paper-frame.json`, so no separate paper-frame file is
  needed here.
- **`answers/<name>.json`**: every model answer each document's
  Conversion received, in the order it was asked, each with its `asked`
  hashes (prompt, picture, schema). **755 calls.**
  - Written by `tools/replay_run.py debug/runs/S13-sweep --save-answers
    tests/frozen/s13-result`.
  - Every answer and hash was checked against the sweep's `trace.json`,
    and 0 differ.
  - **Eighteen files are byte-identical to `s12-result/`'s.** cv, pricing
    and the ticket are asked as A1's targeted run `S13-A1-run` asked them:
    A1 moved their crops. cv 97 → 105 calls, the ticket 22 → 20, pricing
    70 as before.
- **`dth_env.txt`**: the `DTH_*` variables the sweep ran under. There are
  none, so these are the shipped defaults.

## Provenance

**Sweep `S13-sweep`**:
- commit `91a72e1` (spec 0018's registered prediction; its code is
  `e33d246`'s);
- taken 2026-10-19, 18:42 to 21:02, **2h20m**;
- model `qwen3-vl:4b` at 40%/60% CPU/GPU, which moves timings only.

All twenty-one documents converted, and the script ran to its end.

It measures spec 0018's Part 0, A1, B1 and C1. A2, C2 and C4 were each
measured on a targeted run and dropped on Alessandro's decision, and C3
was skipped.

**The spec's registered prediction held to the byte, every clause:**
- all 755 calls were asked and answered as registered;
- eighteen documents rendered byte-identical to `S13-P-replay` (a replay
  of `s12-result/` at the sweep's code);
- cv, pricing and the ticket rendered byte-identical to `S13-P-a1replay`
  (a replay of `S13-A1-run`'s answers).

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-19 at `91a72e1`, whose code is
`e33d246`'s:

- **Replay:** `tools/replay_run.py tests/frozen/s13-result --label
  <label>` reproduces **21 of 21 byte-identical, 0 asked differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s13-result --label
  <label>` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored, gives **21 documents, 0 differing
  fields** against `scores.json`.

Score later runs against it:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s13-result/scores.json
```

## What moved against `s12-result/`

| document | what the page shows | cause |
|---|---|---|
| `ticket_0020` | **better**: the halo row `The` / `The` gone; the strip one row at the page's height, `NORDLYS AIR` printed again; `TRD` at display size | A1 |
| `pricing_0017` | **better**: "Start a 14-day trial" drawn bold, white and at its size on the blue button | A1 |
| `cv_0013` | **better**, slightly: each sidebar section a Zone on the navy, a rule under its label as the page draws it | A1 |
| `catalogue_0015` | same: one line 1px lower | spec 0017 |

The other seventeen draw the same markup.
- The stylesheet gained rules for a strip type stands on, which only cv
  and the ticket draw.
- The IR's `rectifier_version` is 7 (C1); no corpus page's outline moved.

**One ratchet leg is below `s12-result/scores-paper-frame.json`:**
pricing's beside 0.629 → 0.600. The TEAM card's foot grows with its button
drawn at size. Against the same file, the ticket's beside rose 0.588 →
0.818 and vocabulary recall 0.950 → 1.000.

**`vanished`: 24 words**, from 26. The ticket's `nordlys` and `air` are
back, and no word is newly vanished.

Spec 0018's "Outcome — the sweep" lists the faults left against the
originals, by stage, and ranks four directions.
