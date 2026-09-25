# `a0-result/` — Phase A0's outcome — **superseded as the floor, 2026-09-25**

> **This is no longer the T1 ratchet's floor.** At Phase A2's close the floor
> moved to `tests/frozen/a2-result/scores.json`, which dominates this file on
> every ratcheted leg of every document. See `docs/status.md`, "The floor".
> This directory is kept as the record of what A0 reached. Do not point
> `--previous` here. Where the text below says "the floor", read "the floor
> from 2026-09-24 to 2026-09-25".

## What this is

`scores.json` from sweep `100-a0-gate`, taken 2026-09-22: all fifteen
documents, model `qwen3-vl:4b`, the run Phase A0 was gated on.

## Why it is committed

**`debug/runs/` is gitignored and gets cleared.** A0's numbers lived only
there, and re-taking them costs a ~90-minute sweep. Copying the file is
reversible and costs nothing; losing it is not and does not.

## It is the notch — decided 2026-09-24, at the start of Phase A1

**This file is the floor.** Alessandro took the decision that `docs/status.md`
had left open; that section now records it, and the two were updated together.
Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-result/scores.json
```

**Why it moved, measured rather than argued.** The two candidates were compared
per document on all four legs the gate actually tests, because the gate is per
document and strict. `a0-result` **dominates** `a0-checkpoint`: no document is
lower on vocabulary recall, precision, tau or beside agreement. The floor rises
on 12 of 15 documents for precision, 3 for vocabulary, 3 for beside and 1 for
tau, and falls on none. So the move surrenders nothing — it removes only A1's
freedom to hand A0's gains back.

`tests/frozen/a0-checkpoint/` is **not** retired as a record; it is simply no
longer the floor.

**It is a floor, not a result to quote in an argument.** `CLAUDE.md`'s "How runs
are used here" governs this file exactly as it governs the other three.

## The numbers

| | `a0-checkpoint` (the previous floor) | `a0-result` (this file, the floor) |
|---|---|---|
| vocabulary recall | 0.8599 | 0.8653 |
| recall (multiset) | 0.8513 | 0.8542 |
| precision | 0.9342 | 0.9765 |
| join recall | 0.8088 | 0.8128 |
| tau | 0.9356 | 0.9381 |

## Provenance

A real sweep, all fifteen, one sitting, on the tree committed alongside it.
Reviewed with the `visual-review` skill against `99-a0-heading-guard`: no
`worse` on any document, two `better`, and no `major` beside scored ratios all
at 1.000.
