# `s7-result/` — the first sweep of twenty-one documents, and **the baseline** since 2026-10-13

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
  reproduces **21 of 21 byte-identical**.
- **Rederive:** `tools/rederive.py tests/frozen/s7-result --label S8-0-base`
  gives **21 of 21 identical pages, 20 of 21 byte-identical files**.
  `form_0007` differs in one field of its embedded IR, as at `s6-result/`:
  Zone 5's `align` is `null` here and `"left"` after a rederive, because
  step 3 (`fields.read`) turns the Zone from a table into pairs after step 1
  (`rhythm.read`) skipped it as a table. The page is the same.
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
