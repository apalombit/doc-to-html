# `a3-result/` — Phase A3's outcome — **superseded as the floor, 2026-09-29**

> **This is no longer the T1 ratchet's floor.** On 2026-09-29 the floor moved
> to `tests/frozen/reshot/`, when the ten authored corpus pictures were found
> missing their last lines and re-shot whole, and on 2026-09-30 to
> `tests/frozen/q5-result/`. Kept as the record of what A3 reached, measured
> on the cut-short pictures. Do not point `--previous` here. Where the text
> below says "the floor", read "the floor from 2026-09-26 to 2026-09-29".

## What this is

Two things that belong together, the same shape as `a2-result/`:

- **`documents/<name>.html`** — the fifteen rendered output documents of sweep
  `A3-10-figure-pixels-sweep`, each carrying its own IR in its
  `<script type="application/json" id="doc-ir">` block. The IR now carries a
  FIGURE Zone's pixels (`Zone.pixels`, a base64 PNG), so the three figures
  re-render from this directory alone.
- **`scores.json`** — the scores of exactly those files.

Sweep `A3-10-figure-pixels-sweep`, taken 2026-09-26: all fifteen documents,
model `qwen3-vl:4b`, a real sweep rather than a replay, the run Phase A3 was
gated on. Taken on commit `0dc1679` plus the uncommitted A3 change that the
next commit carries — `Zone.pixels`, `preprocess.figure_pixels`,
`Conversion._draw_figures`, the drawn `render._figure`, and
`detector.without_overreaching_pictures`.

## It is the notch — decided 2026-09-26, at A3's close

**This file is the floor**, replacing `a2-result/`. Ratchet against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a3-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report defaults to the *iterate* five and silently scores a third
of the corpus.

**Why it moved, measured rather than argued.** Compared per document on the
four legs the ratchet tests, `a3-result` **dominates** `a2-result`: no document
is lower on any of them, and the set of source words not printed is identical
on all fifteen.

| leg | rises on | falls on |
|---|---|---|
| vocabulary recall | 0 | 0 |
| precision | 2 — `invoice_0001`, `receipt_0010` | 0 |
| tau | 1 — `invoice_0002` | 0 |
| beside agreement | 1 — `invoice_0002` | 0 |

Holding the floor at `a2-result` would have let a later phase print
`sparksuite` and `logo` again, and hand back `invoice_0002`'s reading order.

`a2-result/`, `a1-result/`, `a0-result/`, `a0-checkpoint/` and
`a1-checkpoint/` are kept as record; none of them is a floor any more.

## It is also the control

**Proved on the day it was frozen: the documents regenerate the scores
exactly.** Scored straight out of `documents/`, with nothing else from the run:

```
15 frozen documents, 15 rescored, 0 differing fields
```

and re-rendering each embedded IR through the shipping `render()` returns
**15 of 15 byte-identical**. So a renderer or downstream-of-the-model change is
measured against this directory offline, one change apart, in about fifty
seconds, with no model. **Re-derive before you rely on it**: a change to
`render.py` since this commit is the first reason it would not reproduce.

**Since 2026-09-26 (`07ad13f`) a plain re-render no longer reproduces it, and
the documents are older than the code.** `Zone.header_fill` puts
`"header_fill":null` into every embedded IR, so a re-render differs from all
fifteen by that key alone — remove it and all fifteen are identical. And open
issues 1–3 changed what the code makes of the same model answers. **The
baseline for a change one apart from today's code is**

```
python tools/rederive.py tests/frozen/a3-result --label <label>
```

which re-applies every step downstream of the model to these IRs and
reproduced, byte for byte on all fifteen, the arm issues 1–3 were gated on.
The scores here stay the floor; they were never re-derived.

**And it confirms what the offline work predicted.** 14 of the 15 documents
are byte-identical to the prediction made from `a2-result/`'s IRs with the
figure pixels attached; every model answer outside `invoice_0002` is identical
to `a2-result/`'s. `invoice_0002` is the one document whose layout changed —
the ACME tile split out of the box round it — so it could only be measured by
the sweep.

## Reproducing the scores

```
mkdir -p debug/runs/<label>/dump/qwen3-vl_4b
for f in tests/frozen/a3-result/documents/*.html; do
    n=$(basename "$f" .html)
    mkdir -p debug/runs/<label>/dump/qwen3-vl_4b/"$n"
    cp "$f" debug/runs/<label>/dump/qwen3-vl_4b/"$n"/document.html
done
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/a3-result/scores.json
```

## The numbers

| | `a2-result` (the previous floor) | `a3-result` (this directory, the floor) |
|---|---|---|
| vocabulary recall | 0.8667 | 0.8667 |
| recall (multiset) | 0.8542 | 0.8542 |
| precision | 0.9803 | 0.9851 |
| join recall | 0.8225 | 0.8225 |
| tau | 0.9382 | 0.9483 |
| beside agreement | 0.7316 | 0.7458 |
| alignment agreement | 0.7280 | 0.7283 |
| height ratio | 1.4772 | 1.4791 |
| `hard_breaks` | 8 | 5 |
| `figures_lost` | 2 | 0 |
| T6 inline runs | 8 of 42 | 8 of 42 |

`hard_breaks` 8 → 5 is `invoice_0002`'s company block: the source prints it as
four `<li>` items, and the narrowed crop now reads four lines where it used to
read one address block with three `<br>`.

**It is a floor, not a result to quote in an argument.** `CLAUDE.md`'s "How runs
are used here" governs this directory exactly as it governs the others.
