# `s7-result/` — the first sweep of twenty-one documents; the baseline 2026-10-13 to 2026-10-14, superseded by `s8-result/`

> **Record since 2026-10-14.** Spec 0012's sweep, `s8-result/`, is the
> baseline by Alessandro's decision. Four of this directory's table
> answers are spec 0013's target for step 1: receipt, statement, cv and
> nonlatin, served with `--swap`.

> **Taken as the baseline by Alessandro on 2026-10-13**, after the sweep
> that added six held-out documents to the corpus. Nothing in the pipeline
> changed between `s6-result/` and this sweep except the corpus, so the
> fifteen are `s6-result/`'s, byte for byte, and the six are their first
> conversion. Work is judged by eye on the sheets; scores are recorded,
> never gating.

## What this is

The same shape as `s6-result/`, over twenty-one documents:

- **`documents/<name>.html`** — the twenty-one rendered output documents.
  Each carries its own IR in its `<script type="application/json"
  id="doc-ir">` block.
- **`scores.json`** — their scores, against `s6-result/`. The six new
  documents have no previous and are scored alone.
- **`answers/<name>.json`** — every model answer each document's Conversion
  received, in the order it was asked. Written by `tools/replay_run.py
  debug/runs/S7-sweep --save-answers`. **751 calls**: the fifteen's 518 and
  the six's 233 (letter 50, pricing 88, paper 39, timetable 10, ticket 16,
  certificate 30).
- **`dth_env.txt`** — the `DTH_*` the sweep was taken under: none, the
  shipped defaults.

**Each call's `asked` hashes were added on 2026-10-13, spec 0012 step 0** —
a hash of its prompt, its picture and its schema, so `tools/replay_run.py`
can mark a call today's code asks differently. Taken from a replay at
`92ec769` plus step 0's hash recorder, which asks exactly what the sweep
asked: the only change to `src/` since `639d882` is `9cd4ae2`'s, in
`looks.read`, after every call. Checked against the sweep's own record: all
**751 prompts** hash as `S7-sweep`'s `trace.json` recorded them, and every
answer, `truncated` and `error` is unchanged — the key was added and
nothing else moved.

## Provenance — two commits, said exactly

**Sweep `S7-sweep`**, commit `639d882` (the six documents added, no
pipeline change), taken 2026-10-13 09:04–11:20, **2h16m**, model
`qwen3-vl:4b` 54%/46% CPU/GPU, which moves timings only.

- **The registered prediction held.** All fifteen original documents asked
  the calls `S6-sweep` asked, every answer byte-identical to
  `s6-result/answers/`, and every `document.html` byte-identical to
  `s6-result/documents/`.
- **`pricing_0017` raised after its 88 calls**, in `looks.read`: a Cell box
  `locate` drew a pixel past its Zone's crop cut the page's pixels and the
  Zone's mask to different shapes (13 by 22 against 13 by 21). A bug from
  spec 0011 step 4a that no page of the fifteen reached.
- **Commit `9cd4ae2` fixed it** and is the code these files are from.
  `tools/replay_run.py debug/runs/S7-sweep` at that commit converts pricing
  from its 88 recorded answers — no call beyond them — and reproduces the
  other twenty documents byte for byte. So `documents/` is that replay
  (`S7-replay`), and twenty of its files are the sweep's own.

## What it is for

**It is the baseline:** the twenty-one documents today's code makes. Three
loops run over it, each proved on 2026-10-13 at commit `9cd4ae2`:

- **Replay:** `tools/replay_run.py tests/frozen/s7-result --label S8-0-replay`
  reproduces **21 of 21 byte-identical**. Since spec 0012 step 0 moved
  `_read_rhythm` after `_read_fields`, a replay gives `form_0007` Zone 5
  `align: "left"` where this file has `null` — the page is the same — and
  0 calls asked differently.
- **Rederive:** `tools/rederive.py tests/frozen/s7-result --label S8-0-base`
  gives **21 of 21 identical pages, 20 of 21 byte-identical files**.
  `form_0007` differs in one field of its embedded IR, as at `s6-result/`:
  Zone 5's `align` is `null` here and `"left"` after a rederive, because
  step 3 (`fields.read`) turns the Zone from a table into pairs after step 1
  (`rhythm.read`) skipped it as a table. The page is the same. **Spec 0012
  step 0 put fields before rhythm in both**, and a replay and a rederive
  have agreed byte for byte on all 21 since.
- **Scores:** that rederive, scored against `s6-result/`, gives **21
  documents, 0 differing fields** against `scores.json`.

## The six new documents — held out

`letter_0016`, `pricing_0017`, `paper_0018`, `timetable_0019`, `ticket_0020`
and `certificate_0021` were authored after every measure in the pipeline was
tuned, to carry formatting the fifteen lack. Spec 0012 §1b has what each
page shows and why. Their `vanished` words, recorded:

| document | vanished | what it is |
|---|---|---|
| `timetable_0019` | 24 | **lost**: five of seven lesson rows, every room line, `Lunch` — the grid hint asked for 4 rows |
| `paper_0018` | 3 | not lost: `Achterberg²` is printed with a Unicode superscript and scored as one token |
| `letter_0016` | 1 | `haldenpryce` read as `hal denpryce` |
| `ticket_0020` | 1 | `PASS` read as `FOUR` |

The fifteen's `vanished` is `s6-result/`'s 26 words, unchanged. All 21: 55.

Score against it by path:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s7-result/scores.json
```

`--documents sweep` is not optional: without a `fixtures.txt` in the run
directory the report scores the *iterate* five and says nothing about the rest.
