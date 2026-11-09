# `p1-d2-l3/` — arm D2's renders of the 41 L3 pages, the reference L5 starts from

> **Panel pages. No test reads this directory, and nothing is tuned on
> it**, c0001 and c0002 above all (spec 0020's seal; spec 0023's rules).
> It is here so that L5's changes to D2 can be compared with the run P2
> decided on, page by page, after `debug/` is cleared.

## What this is

- **`documents/<page>.html`**: the 41 rendered output documents, exactly
  as the run wrote them. Each carries its IR in its `<script
  type="application/json" id="doc-ir">` block.
- **`regions/<page>.json`**: the parser's raw regions for each page, as
  the run recorded them (`00_regions.json` in the dump): index, label,
  `bbox_2d` on a 0–1000 scale, content. One parser call a page; they are
  to D2 what `answers/` is to today's pipeline.
- **`pages.jsonl`**: each page's time, the parser's time, calls and
  verdict, as the batch runner wrote them.
- **`dth_env.txt`**: the `DTH_*` variables the run took. It is empty, so
  these are the shipped defaults.

The calls the review made on these renders are in
`docs/agents/review-calls/P1-D2-L3.json`, numbered as the checks
numbered them on the day; spec 0023's "Outcome — steps 4 to 6" compares
them with `l3-baseline/`'s.

## Provenance

**Run `P1-D2-L3`**:
- commit `1cb0e47`, `tools/batch.py --arm d2`, branch `poc-parser-first`;
- taken 2026-11-09 14:06 to 14:24, **18 minutes**;
- GLM-OCR's SDK at `0288f96`, self-hosted, model `glm-ocr:latest`
  through Ollama, `parser/glmocr.yaml`; one page at a time, a 20-minute
  page limit;
- the 41 pages of `corpus/l3-subset.txt`.

**41 converted, none timed out.**

## What it reproduces

Measured on `poc-parser-first` after `7729990`, 2026-11-09, with no
model: each page's `regions/<page>.json` through
`parser_first.from_regions` and `render.render`, as `tools/d2.py` does,
gives **41 of 41 documents byte-identical** to `documents/`. So a change
to the adapter or the looks side is measured one change apart from this
run with no parser call, as `tools/rederive.py` does for today's
pipeline.
