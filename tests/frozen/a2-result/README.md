# `a2-result/` — Phase A2's outcome, and **the T1 ratchet's floor** since 2026-09-25

## What this is

Two things that belong together, the same shape as `a1-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of sweep
  `A2-10-enclosed-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the scores of exactly those files.

Sweep `A2-10-enclosed-sweep`, taken 2026-09-25: all fifteen documents, model
`qwen3-vl:4b`, a real sweep rather than a replay, the run Phase A2 was gated
on. Taken on commit `6369bd6` plus the uncommitted A2 change that the next
commit carries — `detector.without_enclosed` and nothing else that reaches a
Conversion.

## It is the notch — decided 2026-09-25, at A2's close

**This file is the floor**, replacing `a0-result/`. Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a2-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report defaults to the *iterate* five and silently scores a third
of the corpus.

**Why it moved, measured rather than argued.** Compared per document on the
four legs the ratchet tests, `a2-result` **dominates** `a0-result`: no document
is lower on any of them, and no word `a0-result` printed has stopped printing.

| leg | rises on | falls on |
|---|---|---|
| vocabulary recall | 1 | 0 |
| precision | 4 | 0 |
| tau | 1 | 0 |
| beside agreement | 3 | 0 |

Five source words the old floor did not print now do, all on
`newsletter_0008` (`confirmed`, `navigation`, `relined`, `slipways`,
`subscription` — A1's reflow and hyphen repair). Holding the floor at
`a0-result` would have let a later phase hand those back.

`a0-result/`, `a0-checkpoint/` and `a1-checkpoint/` are kept as record; none
of them is a floor any more.

## It is also the control

**Proved on the day it was frozen: the documents regenerate the scores
exactly.** Scored straight out of `documents/`, with nothing else from the run:

```
15 frozen documents, 15 rescored, 0 differing fields
```

So a renderer or downstream-of-the-model change can be measured against this
directory offline, one change apart, in about fifty seconds, with no model —
the loop `a1-result/` made possible, now on the shipped configuration.
**Re-derive before you rely on it**: re-rendering these IRs through the
shipping `render()` should return all fifteen files byte-identical, and a
change to `render.py` since this commit is the first reason it would not.

**And it confirms two things offline work could only predict.** The sweep's
fifteen documents were byte-identical to the prediction made from
`a1-result/`'s IRs with the four enclosed Zones removed, and every surviving
Zone's answer — inline runs included — was identical to `a1-result/`'s. So
`a1-result/`'s replayed "8 of 42" inline runs is now a measured sweep result.

## Reproducing the scores

```
mkdir -p debug/runs/<label>/dump/qwen3-vl_4b
for f in tests/frozen/a2-result/documents/*.html; do
    n=$(basename "$f" .html)
    mkdir -p debug/runs/<label>/dump/qwen3-vl_4b/"$n"
    cp "$f" debug/runs/<label>/dump/qwen3-vl_4b/"$n"/document.html
done
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a2-result/scores.json
```

## The numbers

| | `a0-result` (the previous floor) | `a2-result` (this directory, the floor) |
|---|---|---|
| vocabulary recall | 0.8653 | 0.8667 |
| recall (multiset) | 0.8542 | 0.8542 |
| precision | 0.9765 | 0.9803 |
| join recall | 0.8128 | 0.8225 |
| tau | 0.9381 | 0.9382 |
| beside agreement | 0.7233 | 0.7316 |
| alignment agreement | 0.7092 | 0.7280 |
| height ratio | 1.4977 | 1.4772 |
| `hard_breaks` | 57 | 8 |
| T6 inline runs | 0 of 42 | 8 of 42 |

**It is a floor, not a result to quote in an argument.** `CLAUDE.md`'s "How runs
are used here" governs this directory exactly as it governs the others.
