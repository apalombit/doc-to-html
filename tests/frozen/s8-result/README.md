# `s8-result/` — spec 0012's sweep, twenty-one documents, and **the baseline** since 2026-10-14

> **Taken as the baseline by Alessandro on 2026-10-14**, after reviewing
> spec 0012's sweep. By eye against `s7-result/`: eighteen pages better,
> three worse. Each worse page is traced in spec 0012's "Outcome — the
> sweep", and spec 0013 is the work that repairs them. Work is judged by eye
> on the sheets; scores are recorded, never gating.

## What this is

The same shape as `s7-result/`:

- **`documents/<name>.html`** — the twenty-one rendered output documents,
  the sweep's own. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`scores.json`** — their scores, against `s7-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, each with its `asked` hashes (prompt,
  picture, schema). Written by `tools/replay_run.py debug/runs/S8-sweep
  --save-answers`. **725 calls.** All 725 answers and hashes were checked
  against the sweep's `trace.json`: 0 differ.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

## Provenance

**Sweep `S8-sweep`**, commit `ba0c110` (spec 0012 step U), taken
2026-10-14 00:49–03:00, **2h12m**, model `qwen3-vl:4b` 40%/60% CPU/GPU,
which moves timings only. All twenty-one converted.

The script stopped after the bake-off, because `tools/iterate.sh` was
edited while bash was reading it. `ollama ps`, `inspect_run.py` and the
report were run by hand over the finished dump. Nothing in `documents/` or
`answers/` comes from that hand step.

**Spec 0012 §6's prediction held:**
- 636 calls asked the same as `s7-result/` answered byte for byte the same;
- the calls asked differently were exactly the registered ones:
  - the certificate, 21 of 22 calls;
  - pricing, 60 of 70;
  - one table call each in cv, nonlatin, paper, receipt, statement, ticket
    and the timetable;
- the twelve unmarked documents rendered byte-identical to the replay at
  step U.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-14 at `ba0c110`'s code:

- **Replay:** `tools/replay_run.py tests/frozen/s8-result --label
  S9-0-replay` reproduces **21 of 21 byte-identical, 0 asked
  differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s8-result --label
  S9-0-base` gives **21 of 21 byte-identical files**. `form_0007`'s old
  one-field difference is gone: spec 0012 step 0 put fields before rhythm
  in both.
- **Scores:** that rederive, scored against `s7-result/`, gives **21
  documents, 0 differing fields** against `scores.json`.

## The three pages worse than `s7-result/`, accepted

| document | what the page shows | cause, traced |
|---|---|---|
| `receipt_0010` | all eight item prices gone | the table hint said 2 columns where the page has 3 |
| `statement_0006` | the transactions' header row drawn in its band's own colour; the caption gone; `Castleton` read `Castletown` | the hint said 5 columns of 6; the model folded the caption into a 7-cell header row |
| `certificate_0021` | the signature row one boxed paragraph; the name a three-line heading | its layout on the unwarped page |

`vanished`: **40 words**, against `s7-result/`'s 55. The timetable got 23
back; the receipt lost 6 tokens (its prices), the statement `castleton`
and cv `2022`.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s8-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
