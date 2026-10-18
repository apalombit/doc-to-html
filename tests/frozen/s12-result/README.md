# `s12-result/` — spec 0016's sweep, twenty-one documents, and **the baseline** since 2026-10-18

> **Alessandro took it as the baseline on 2026-10-18**, after reviewing
> spec 0016's sweep. By eye against `s11-result/` replayed at the code spec
> 0016 began on (`S12-0-replay`), one page is better, twenty the same and
> none worse. Work is judged by eye on the sheets. Scores are recorded and
> never gate.

## What this is

It has the same shape as `s11-result/`:

- **`documents/<name>.html`**: the twenty-one rendered output documents,
  exactly as the sweep wrote them, each carrying its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`scores.json`**: their scores, against `s11-result/`.
- **`answers/<name>.json`**: every model answer each document's Conversion
  received, in the order it was asked, each with its `asked` hashes (prompt,
  picture, schema). Written by `tools/replay_run.py debug/runs/S12-sweep
  --save-answers tests/frozen/s12-result`. **749 calls.** Every answer and
  hash was checked against the sweep's `trace.json`, and 0 differ. **All
  twenty-one files are byte-identical to `s11-result/`'s answers**: spec
  0016 changed no question the model was asked.
- **`dth_env.txt`**: the `DTH_*` variables the sweep ran under. There are
  none, so these are the shipped defaults.

## Provenance

**Sweep `S12-sweep`**, commit `3abb55d` (spec 0016 step P; its code is
`c98f2db`'s), taken 2026-10-18 16:07 to 18:30, **2h22m**, model
`qwen3-vl:4b` at 40%/60% CPU/GPU, which moves timings only. All
twenty-one documents converted, and the script ran to its end.

**Spec 0016 §7's prediction held to the byte, every clause:**
- all 749 calls `s11-result/` asked were asked alike and answered byte for
  byte the same, and nothing else was asked;
- sixteen documents rendered byte-identical to `s11-result/`, and the
  other five — catalogue, cv, form, invoice_0002, ticket —
  byte-identical to the replay at step P (`S12-P-replay`), which is steps
  1–3 drawn over `s11-result/`'s IRs.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-18 at `c98f2db`'s code:

- **Replay:** `tools/replay_run.py tests/frozen/s12-result --label
  <label>` reproduces **21 of 21 byte-identical, 0 asked differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s12-result --label
  <label>` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored, gives **21 documents, 0 differing
  fields** against `scores.json`.

## What moved against `s11-result/`

| document | what the page shows | cause |
|---|---|---|
| `ticket_0020` | **better**: the grid's columns keep one edge; `TRD` flush right on `OSL`'s line and a four-column grid, `DEPARTS` and `CLASS` over their values; one teal strip, `BOARDING PASS` on one line; the stub opens on its own strip | steps 1, 2, 3 |
| `catalogue_0015` | same: `each`, `In stock` and `NEW` 3–7px sideways | step 1 |
| `invoice_0002` | same: `Date` about 5px nearer its value | step 1 |
| `cv_0013`, `form_0007` | same: pixel-identical | step 1 (the stylesheet only) |

The other sixteen are byte-identical to `s11-result/`.

**Left on the ticket:** the halo Zone `The` / `The`, now inside the one
strip, which stands twice the page's height, and `TRD` at Title size.
Step 4a would have removed it; it was measured and dropped (spec 0016
§5).

**No ratchet leg fell.** The ticket's tau rose 0.843 → 0.947 and beside
0.262 → 0.393. `vanished`: **26 words**, as `s11-result/`; no word is
newly vanished.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s12-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
