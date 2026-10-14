# `s9-result/` — spec 0013's sweep, twenty-one documents, and **the baseline** since 2026-10-14

> **Taken as the baseline by Alessandro on 2026-10-14**, after reviewing
> spec 0013's sweep. By eye against `s8-result/` replayed at the code spec
> 0013 began on (`S9-0-replay`): seven pages better, thirteen the same, one
> worse — the ticket, traced in spec 0013's "Outcome — the sweep". Work is
> judged by eye on the sheets; scores are recorded, never gating.

## What this is

The same shape as `s8-result/`:

- **`documents/<name>.html`** — the twenty-one rendered output documents,
  the sweep's own. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`scores.json`** — their scores, against `s8-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, each with its `asked` hashes (prompt,
  picture, schema). Written by `tools/replay_run.py debug/runs/S9-sweep
  --save-answers`. **732 calls.** All 732 answers and hashes were checked
  against the sweep's `trace.json`: 0 differ.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

## Provenance

**Sweep `S9-sweep`**, commit `a3969f3` (spec 0013 step P; code as
`a84404c`), taken 2026-10-14 11:13–13:29, **2h16m**, model `qwen3-vl:4b`
40%/60% CPU/GPU, which moves timings only. All twenty-one converted; the
script ran to its end.

**Spec 0013 §9's prediction held, every clause:**
- every call asked as `s8-result/` asked it answered byte for byte the same;
- the calls asked differently were exactly the registered ones: one table
  call each in receipt, statement, cv, nonlatin and paper; 25 of the
  certificate's 28; all 17 of the ticket's;
- the four step-1 table answers are byte-identical to `s7-result/`'s;
- the fourteen unmarked documents rendered byte-identical to the replay at
  step P.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-14 at `a3969f3`'s code:

- **Replay:** `tools/replay_run.py tests/frozen/s9-result --label
  S10-0-replay` reproduces **21 of 21 byte-identical, 0 asked
  differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s9-result --label
  S10-0-base` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored against `s8-result/`, gives **21
  documents, 0 differing fields** against `scores.json`.

## The page worse than `s8-result/`, accepted

| document | what the page shows | cause, traced |
|---|---|---|
| `ticket_0020` | `OSL`, `OSLO GARDERMOEN`, both `NORDLYS AIR` and the gate note gone; a teal band printing `The` / `The`; the stub drawn above the body | its warp now holds the whole card (spec 0013 step 5), and the new crops' answers lose lines: the stub and the left body read as `pairs`, the header as a logo, an 8 px `equalise` halo recovered as a Zone |

Also short of the page, not worse: the certificate's signature row stacks
(one `single` region) and its seal is drawn as a text chip.

`vanished`: **41 words**, against `s8-result/`'s 40. Back: the receipt's
six price tokens, `castleton`, `2022`, the ticket's `pass`. Gone: ten of
the ticket's.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s9-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
