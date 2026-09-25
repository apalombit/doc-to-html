# Phase A0's starting notch — **superseded as the floor, 2026-09-24**

> **This is no longer the T1 ratchet's floor.** At the start of Phase A1 the
> floor moved to `tests/frozen/a0-result/scores.json`, which holds the scores
> A0 *reached* rather than the ones it *cleared*. See `docs/status.md`, "The
> notch — DECIDED 2026-09-24". This directory is kept as the record of where
> A0 began, the way `a1-checkpoint/` is kept. Do not point `--previous` here.

`scores.json` here is **the state of the corpus as A0 begins**: all fifteen
documents, the T1 ratchet's floor for A0 and everything after it.

Point a checkpoint at this file explicitly:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
```

## Why it is committed rather than left in the run directory

`debug/` is gitignored and gets cleared. `tests/frozen/a1-checkpoint/` exists
for the same reason and its README makes the argument in full: a floor left in
`debug/runs/` is a floor that means "whatever `scores.json` is newest", which
is a different quantity every time somebody clears the directory.

**This does not retire `a1-checkpoint/`.** That one is Phase A-1's notch and
the record of where the ratchet started. This one is where A0 starts.

## Provenance, stated exactly

- **Model answers:** run `94-borders-baseline`, `qwen3-vl:4b`, all fifteen
  documents, one process, taken **2026-09-21 20:57–22:5x** at commit
  `8d06bb8` — a clean tree. The model ran **40%/60% CPU/GPU**, which affects
  timings only.
- **Render and pixel-derived style:** **not** from that run.
  `tools/remeasure_style.py` re-measured the Style Record and re-rendered
  every document from the run's own embedded IRs at commit `09f56d3`, and
  `scores.json` was produced from those renders on **2026-09-22 04:57 UTC**.
- **So this is a hybrid, and that is deliberate.** Everything the model
  decided comes from a real sweep taken in one sitting; everything derived
  from pixels comes from the shipped code. The three changes between the two
  commits — the border finder, the `_measure_chrome` ordering fix, and the
  three renderer fixes — make **no model call** and change no prompt, so a
  real run at `09f56d3` would reproduce these numbers. The claim is checkable:
  `tools/remeasure_style.py` is deterministic and the run's IRs are in its
  dump.
- **What it is not:** a substitute for a sweep. Anything that moves a prompt,
  an extractor, or the layout still needs a real run.

## `vocabulary_recall` was added on 2026-09-22, after the file was written

Phase A0 re-pointed the T1 ratchet's recall leg from the token **multiset** to
the token **vocabulary** — see spec 0007, "Why the ratchet's recall leg is now
distinct tokens". This file predated the field, so the floor had nothing to be
measured against, and the two fields were backfilled.

**How, and why it is not a second measurement.** The same source and the same
`document.html` this file already describes were re-projected and re-scored
offline, with no model and no re-conversion, and **every number already in the
file re-measured identically** — recall, precision, `join_recall` and both token
counts, on all fifteen documents, to within 1e-9. That equality is the check:
had the artefacts drifted from what this file describes, it would have failed
rather than quietly written a number from different pixels. Nothing else in the
file changed.

| | mean over fifteen |
|---|---|
| `vocabulary_recall` | **0.860** |

## What it says, for the phase that starts here

| | mean over fifteen |
|---|---|
| `recall` | **0.851** |
| `precision` | **0.934** |
| `join_recall` | **0.809** |
| `tau` | **0.936** |

`Completeness.duplicated` totals **29 repeated source strings** across twelve
documents. **It under-reports**: `report_0011` prints all eight of its numbered
headings twice and `duplicated` comes back empty for it, while its
`output_tokens` are 477 against the source's 459. Find out why before gating
anything on that field — see the A0 prompt in `docs/specs/0007-handover.md`.
