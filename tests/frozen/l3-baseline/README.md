# `l3-baseline/` — L3's renders of the 41 panel pages, the reference P2 decides against

> **Panel pages. No test reads this directory, and nothing is tuned on
> it**, c0001 and c0002 above all (spec 0020's seal; spec 0022's rules).
> It is here so that P1's arm can be compared with today's pipeline page
> by page, and replayed, after `debug/` is cleared.

## What this is

- **`documents/<page>.html`**: the 37 rendered output documents, exactly
  as the run wrote them. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`answers/<page>.json`**: every model answer each page's Conversion
  received, in the order it was asked, each with its `asked` hashes
  (prompt, picture, schema). **1577 calls.**
  - Written by `tools/replay_run.py debug/runs/L3-baseline --save-answers
    tests/frozen/l3-baseline`.
  - Every answer and hash was checked against the run's `trace.json`, and
    0 differ.
- **`pages.jsonl`**: each of the 41 pages' time, model time, calls and
  verdict, as the batch runner wrote them.
- **`dth_env.txt`**: the `DTH_*` variables the run took. It is empty, so
  these are the shipped defaults.

The calls the review made on these renders are in
`docs/agents/review-calls/L3-baseline.json`, numbered as the checks
numbered them on the day; spec 0022's "Outcome" ranks them.

## Provenance

**Run `L3-baseline`**:
- commit `2bb94af`, with the conversion code as at `7b00482`;
- taken 2026-11-08 17:52 to 2026-11-09 00:26, **6.6 hours**;
- model `qwen3-vl:4b`, one page at a time, a 20-minute page limit;
- the 41 pages of `corpus/l3-subset.txt`: the 36 panel pages, plus the
  five PDF pages that are not dense.

**37 converted, 4 timed out** and have no render here: c0034, c0196,
c0291, c0456. Six converted pages had a Zone read short: c0074, c0129,
c0272, c0388, c0431, c0555.

## What it reproduces

Measured on `18cd828`, 2026-11-09:

- `tools/replay_run.py tests/frozen/l3-baseline --label <label>
  --documents <the 36>`: **36 of 36 byte-identical, 0 asked
  differently.**
- **c0129 cannot be replayed**: its call 61 (`prose`) raised in the run
  (`CallTooLong`, not finished after 180 s), and a raise cannot be served
  back. Its render is here all the same.
- `tools/rederive.py` over it: 35 of 37 files byte-identical. On c0467
  and c0523 the drawn HTML is identical. Only the embedded IR differs, at
  seven edges of pair boxes (label and value), each moved by under half
  a pixel.
