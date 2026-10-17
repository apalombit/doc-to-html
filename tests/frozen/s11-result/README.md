# `s11-result/` — spec 0015's sweep, twenty-one documents, and **the baseline** since 2026-10-17

> **Alessandro took it as the baseline on 2026-10-17**, after reviewing
> spec 0015's sweep. By eye against `s10-result/` replayed at the code spec
> 0015 began on (`S11-0-replay`), six pages are better, fifteen the same
> and none worse. Work is judged by eye on the sheets. Scores are
> recorded and never gate.

## What this is

It has the same shape as `s10-result/`:

- **`documents/<name>.html`**: the twenty-one rendered output documents,
  exactly as the sweep wrote them. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block. Since spec 0015, each
  `unclaimed` entry also carries its `reach`.
- **`scores.json`**: their scores, against `s10-result/`.
- **`answers/<name>.json`**: every model answer each document's Conversion
  received, in the order it was asked, each with its `asked` hashes (prompt,
  picture, schema). Written by `tools/replay_run.py debug/runs/S11-sweep
  --save-answers tests/frozen/s11-result`. **749 calls.** Every answer and
  hash was checked against the sweep's `trace.json`, and 0 differ.
- **`dth_env.txt`**: the `DTH_*` variables the sweep ran under. There are
  none, so these are the shipped defaults.

## Provenance

**Sweep `S11-sweep`**, commit `6b1caf4` (spec 0015 step P; its code is
`3c5e365`'s), taken 2026-10-15 23:13 to 2026-10-16 01:35, **2h22m**,
model `qwen3-vl:4b` at 40%/60% CPU/GPU, which moves timings only. All
twenty-one documents converted, and the script ran to its end.

**Spec 0015 §6's prediction held to the byte, every clause:**
- all 735 calls `s10-result/` asked were asked alike and answered byte for
  byte the same;
- the only other calls are fourteen re-reads of unclaimed lines: catalogue
  2, darkdeck 1, menu 2, receipt 1, sample_semantic 1, ticket 4,
  timetable 3;
- the fourteen unmarked documents rendered byte-identical to the replay at
  step P (`S11-P2-replay`), and the seven marked ones byte-identical to
  `S11-P2-check`, the replay of step 1's targeted run.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-17 at `3c5e365`'s code:

- **Replay:** `tools/replay_run.py tests/frozen/s11-result --label
  <label>` reproduces **21 of 21 byte-identical, 0 asked differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s11-result --label
  <label>` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored, gives **21 documents, 0 differing
  fields** against `scores.json`.

## What moved against `s10-result/`

| document | what the page shows | cause |
|---|---|---|
| `ticket_0020` | **better**: the stub is a pane beside the pass; the field grids are drawn as grids; `OSL` and the gate note are printed; `OSLO GARDERMOEN` is under the name | steps 3b, 2a/2b, 1b/1c, 2d |
| `certificate_0021` | **better**: the signature row is one line, `S. Okonkwo`, the seal, `H. Brandt` | step 3a, the page's lanes |
| `catalogue_0015` | **better**: all nine cards alike, each price on its card's line; three prices placed by inference are drawn small | step 2b |
| `invoice_0002` | **better**: the Comments and Payment panels at the page's widths; the `NO` line compact | step 3a, `_placed`'s cap |
| `sample_semantic_0005` | **better**: TL;DR at the page's width; `Tags:` printed, but on its own line after the links | steps 3a, 1a |
| `timetable_0019` | **better**: `Lunch` printed, but under the grid instead of in its 13:20 row | step 1a |

The other fifteen look the same. Four are byte-identical to the replay's
render. The rest differ only in band lane shares, the `dd.line` rule or
the embedded IR.

**The ratchet legs that fell, accepted:** `timetable_0019`'s tau, 0.963 →
0.954, and beside, 0.992 → 0.984. Both come from `Lunch` being drawn under
the grid.

`vanished`: **26 words**, down from `s10-result/`'s 33. The words back are
the ticket's `20`, `before`, `closes`, `departure`, `minutes` and `osl`,
and the timetable's `lunch`. No word is newly vanished.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s11-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
