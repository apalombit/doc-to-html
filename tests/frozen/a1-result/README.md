# `a1-result/` — the configuration Phase A1 shipped, frozen 2026-09-25

## What this is

Two things that belong together:

- **`documents/<name>.html`** — the fifteen rendered output documents of run
  `A1-11-final`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block.
- **`scores.json`** — the scores of exactly those files.

This is the right-hand column of `docs/status.md`'s "Where the corpus is as A2
begins": the shipped configuration at the close of Phase A1.

## Why it is committed, and why the documents and not only the scores

**`debug/runs/` is gitignored and gets cleared**, which is the reason every
other directory here exists. What is new is the second file set, and it is what
makes this one *usable* rather than merely quotable.

**Proved on the day it was frozen: the documents regenerate the scores
exactly.** Scored straight out of `documents/`, with nothing else from the run:

```
15 frozen documents, 15 rescored, 0 differing fields
```

Every ratio, every count, every list — `vanished`, `broken_joins`, `invented`,
all of it. So a later session does not have to take `scores.json` on trust; it
can re-derive it offline in about fifty seconds with **no model, no Ollama and
no network**, the way `tests/frozen/run84/` is used.

**And it makes renderer questions answerable without a sweep.** Re-rendering
these IRs through the shipping `render()` returned all fifteen files
byte-identical, so a renderer change can be measured against this directory
pairwise, one change apart, in one sitting. Phase A2's five prototype renderers
were measured that way and cost no model time; without this directory none of
those numbers could have been taken, and none can be re-taken once
`debug/runs/` is cleared.

## What it is not

**It is not the ratchet's floor.** The floor is `tests/frozen/a0-result/` and
this does not move it. A1's gate was NOT met, and the run below is a replay
rather than a sweep — see Provenance.

**It is not a target.** Nothing should be made to match it. It is where the
corpus stood when A2 opened, including everything wrong with it:
`receipt_0010` at 0.175 recall, `form_0007` at 0.059 `beside_agreement`,
`catalogue_0015` losing 38% of its words without declaring it.

`CLAUDE.md`'s "How runs are used here" governs this file exactly as it governs
the other four frozen directories.

## Provenance — read this before quoting anything from it

Commit `79f615e`, model `qwen3-vl:4b`.

**`A1-11-final` is a replay, not a sweep.** The model answers are
`A1-08-inline-sweep`'s — a real sweep of all fifteen, taken in one sitting —
and they were re-filtered through the fixed wire mapper, because every inline-
run guard A1 shipped is downstream of the model. The replay method was
validated on 2026-09-22 by making it reproduce `a0-result` to four decimal
places on every mean before any conclusion was drawn from it.

**One known discrepancy, stated rather than buried:** the replay rebuilt 41
spans where the model returned 43. **A confirming sweep for A1's shipped
"8 of 42" is outstanding**, and anyone quoting that figure as a measured run is
quoting it wrong. It does not affect this directory's usefulness as a control —
these files *are* what was scored — but it is why this is `a1-result` and not
a gate.

## Reproducing the scores

```
mkdir -p debug/runs/<label>/dump/qwen3-vl_4b
for f in tests/frozen/a1-result/documents/*.html; do
    n=$(basename "$f" .html)
    mkdir -p debug/runs/<label>/dump/qwen3-vl_4b/"$n"
    cp "$f" debug/runs/<label>/dump/qwen3-vl_4b/"$n"/document.html
done
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a0-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report defaults to the *iterate* five and silently scores a third
of the corpus.

## The numbers

| | `a0-result` (the floor) | this directory |
|---|---|---|
| vocabulary recall | 0.8653 | 0.8667 |
| recall (multiset) | 0.8542 | 0.8553 |
| precision | 0.9765 | 0.9787 |
| join recall | 0.8128 | 0.8229 |
| tau | 0.9381 | 0.9381 |
| beside agreement | 0.7233 | 0.7265 |
| alignment agreement | 0.7092 | 0.7217 |
| height ratio | 1.4977 | 1.4639 |
| `hard_breaks` | 57 | 8 |
| T6 inline runs | 0 of 42 | 8 of 42 |
