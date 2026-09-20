# The T1 ratchet's starting notch — Phase A-1's checkpoint

`scores.json` here is the run `88-a1-checkpoint`, all fifteen documents, taken
2026-09-19. **It is the notch every later phase is measured against**, by the
decision recorded in `docs/specs/0007-handover.md` under Phase A-1.

## Why it is committed rather than left in the run directory

`debug/` is gitignored and gets cleared. The notch was made the ratchet's floor
and then left in the one place guaranteed not to survive — so a later phase
would have ratcheted against "whatever `scores.json` happens to be newest under
`debug/runs/`", which is a different quantity every time somebody clears the
directory.

Point a checkpoint at this file explicitly:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a1-checkpoint/scores.json
```

## Provenance, stated exactly

- **Run:** `88-a1-checkpoint`, `qwen3-vl:4b`, fifteen documents, one process.
- **Taken:** 2026-09-19 16:28 UTC.
- **Machine:** the model was **54%/46% CPU/GPU** for this run. That affects
  timings only; the answers are unchanged.
- **Code:** the run started from an **uncommitted working tree** on top of
  `c5fb73f`, carrying Phase A-1's changes before they were committed. It
  therefore corresponds to no single commit, and saying so is the point — see
  below for why the numbers are still sound.

## Why these numbers are sound despite that

**The scorer was not modified at any point in that session.** `scoring.py` and
`projection.py` are untouched by Phase A-1; the changes were to `preprocess.py`,
`wire.py`, `orchestrator.py`, `ir.py`, `render.py`, `report.py` and
`bakeoff.py`, and `scoring.py` imports none of the first three. So `scores.json`
is a clean application of an unchanged scorer to the documents the run
produced.

**The conversions ran in one process**, so all fifteen were converted by one
snapshot of the code — `tools/iterate.sh` loads the model once for the whole
set. Three edits were made to the working tree *after* that process started and
did not reach it:

1. `ir._decode_document` gaining `Gap.ink_share` — affects reading findings
   back out of the IR, not any score.
2. `orchestrator._measure_shortfalls` moving out of the per-Zone loop —
   behaviourally identical for a single-round Conversion, which is what an
   unattended run is.
3. `bakeoff.py` reporting shortfalls on stdout — a print, nothing else.

None of the three can move a number in this file.

## What the run showed

Phase A-1's three content-loss causes were fixed and **its honesty gate
failed**: nine of fifteen documents lost content without declaring it, because
the remaining loss is *within* lines and no line count can see it. The full
account is in `docs/status.md`; the evidence against two rejected detectors is
in `src/doc_to_html/honesty.py`.

**T1 is the ratchet. T2 and T3 are the rest of the hard tier.** The `height` and
`beside` columns in this file are the deferred work — column collapse waits for
A2, the renderer's cards for Thread 2/B — and a later run improving them is the
plan, not a surprise.

## The other frozen set

`tests/frozen/run84/` is a different thing and stays as it is: five *output
documents* from run 84, used to develop the scorer offline with no model. This
directory holds *scores*, not documents, and exists to be ratcheted against.
