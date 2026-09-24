# `a0-result/` — Phase A0's outcome, preserved. **NOT the ratchet's notch.**

## What this is

`scores.json` from sweep `100-a0-gate`, taken 2026-09-22: all fifteen
documents, model `qwen3-vl:4b`, the run Phase A0 was gated on.

## Why it is committed

**`debug/runs/` is gitignored and gets cleared.** A0's numbers lived only
there, and re-taking them costs a ~90-minute sweep. Copying the file is
reversible and costs nothing; losing it is not and does not.

## What it is NOT

**It is not the T1 ratchet's floor, and nothing ratchets against it.** The
floor is still `tests/frozen/a0-checkpoint/scores.json`. Whether to move the
floor here is an open decision — see `docs/status.md`, "The notch". Do not
point `--previous` at this directory on the assumption that it is the notch;
if the decision is taken, say so here and in `docs/status.md` at the same time.

## The numbers

| | `a0-checkpoint` (the floor) | `a0-result` (this file) |
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
