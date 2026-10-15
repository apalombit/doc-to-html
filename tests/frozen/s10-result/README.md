# `s10-result/` — spec 0014's sweep, twenty-one documents, and **the baseline** since 2026-10-15

> **Taken as the baseline by Alessandro on 2026-10-15**, after reviewing
> spec 0014's sweep. By eye against `s9-result/` replayed at the code spec
> 0014 began on (`S10-0-replay`): three pages better, eighteen the same,
> none worse. Work is judged by eye on the sheets; scores are recorded,
> never gating.

## What this is

The same shape as `s9-result/`:

- **`documents/<name>.html`** — the twenty-one rendered output documents,
  the sweep's own. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block, every Zone with its
  `extra` list since spec 0014.
- **`scores.json`** — their scores, against `s9-result/`.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked, each with its `asked` hashes (prompt,
  picture, schema). Written by `tools/replay_run.py debug/runs/S10-sweep
  --save-answers`. **735 calls.** All 735 answers and hashes were checked
  against the sweep's `trace.json`: 0 differ.
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

## Provenance

**Sweep `S10-sweep`**, commit `a53f11b` (spec 0014 step P; code as
`b493477`), taken 2026-10-15 07:35–09:56, **2h21m**, model `qwen3-vl:4b`
40%/60% CPU/GPU, which moves timings only. All twenty-one converted; the
script ran to its end.

**Spec 0014 §7's prediction held to the byte, every clause:**
- all 732 calls `s9-result/` asked were asked alike and answered byte for
  byte the same;
- the only calls beyond them are step 2's three re-reads of an unclaimed
  line, one prose call each on form, ticket and timetable;
- the eighteen unmarked documents rendered byte-identical to the replay
  at step P, `S10-P-replay`; form, ticket and timetable byte-identical to
  `S10-2`, the replay of the step's targeted run;
- no further re-read: the unclaimed list is empty on all twenty-one.

Step 3 (a grid's copies by the Kind that keeps most) was built, made the
catalogue worse, and was dropped before the sweep; nothing of it is here.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-15 at `b493477`'s code:

- **Replay:** `tools/replay_run.py tests/frozen/s10-result --label
  <label>` reproduces **21 of 21 byte-identical, 0 asked differently**.
- **Rederive:** `tools/rederive.py tests/frozen/s10-result --label
  <label>` gives **21 of 21 byte-identical files**.
- **Scores:** that rederive, scored against `s9-result/`, gives **21
  documents, 0 differing fields** against `scores.json`.

## What moved against `s9-result/`

| document | what the page shows | cause |
|---|---|---|
| `form_0007` | **better** — `Tick one category. Locker allocation is subject to availability.` under the tick boxes | step 2: the unclaimed line read on its own crop, kept in Zone 3's `extra` |
| `ticket_0020` | **better, in part** — `OSLO GARDERMOEN` printed, at the foot of Zone 3 rather than under the name | the same; `extra` is drawn before or after a Zone's body, never between its pairs |
| `timetable_0019` | **better** — the legend on one line under the grid; `Science` drawn bold | the same; the five items drawn on one line where the page prints them side by side |

**The one ratchet leg that fell, accepted:** `ticket_0020`'s tau, 0.282 →
0.238 — `OSLO GARDERMOEN` drawn at its Zone's foot is out of the page's
order.

`vanished`: **33 words**, against `s9-result/`'s 41. Back: the form's
`tick`, `one`, `allocation`, `is`, `subject`, `availability`; the ticket's
`oslo`, `gardermoen`. Nothing gone.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s10-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
