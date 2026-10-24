# The unseen probe — 2026-10-24

Ten pages of kinds the corpus lacks, converted once with the shipped
defaults to see how the pipeline meets documents nobody tuned on. The
findings are in [`../level-up.md`](../level-up.md) §3.

**These pages have now been looked at.** They are dev pages from here on:
never a held-out set, and never a panel or a vault.

| file | what |
|---|---|
| `src/<page>.html`, `src/<page>.png` | the ten sources, and the screenshot each was converted from |
| `notes.md` | the by-eye notes, page by page, each fault with its stage; then the six tuned pages judged the same way, and the GLM-OCR taste test |
| `results.json` | per page: seconds, Zones, the scorer's completeness/order/layout numbers and `vanished`; GLM-OCR's whole-page and per-Zone words lost and invented |
| `scripts/probe_unseen.py` | shoot, convert (`Conversion`, default engines), render, score, build a sheet |
| `scripts/glm_taste.py` | GLM-OCR over each whole page (`Text Recognition:`), `--zones` over today's Zones, `--rescore <folder>` without asking again |
| `scripts/compare_sets.py` | the ten against the 21, same scorer |
| `scripts/probe_report.py` | one page with every sheet and the notes |
| `out/report.html` | **the page to open**: every source beside its render, the numbers and the notes |
| `out/<page>/render.html`, `out/<page>/ir.json` | each page's render and IR, as converted at `99110c2` |
| `out/scores.json` | the scorer's full output over the ten |
| `out/glm/<page>.md`, `out/glm-zones/<page>.md` | GLM-OCR's answers, whole page and per Zone, with each folder's `summary.json` |
| `out/tuned-sample/<doc>.png` | the six tuned pages' sheets, judged the same way (§3.2) |

## How it was taken

- Commit `99110c2`, shipped defaults, no `DTH_*` set. Ollama 0.34.0,
  `qwen3-vl:4b` 40%/60% CPU/GPU, on the 8 GB M1.
- One `Conversion` per page. `tools/rederive.py` and the scorer ran during
  the payslip's conversion, so its 555 s is high.
- Each page was screenshotted at its width (`WIDTHS`) by
  `projection.screenshot`, the corpus's shooter.
- The 21 for comparison: `tests/frozen/s14-result/` re-derived at
  `99110c2` (`tools/rederive.py … --label G0-s14-rederived`), then scored
  with `doc_to_html.report`.
- GLM-OCR: `glm-ocr:q8_0`, temperature 0, one call per page or per Zone,
  100% GPU.

## Re-run

```
.venv/bin/python docs/level-up-probe/scripts/probe_unseen.py      # ~80 min, needs Ollama + qwen3-vl:4b
.venv/bin/python docs/level-up-probe/scripts/glm_taste.py         # ~1 min, needs glm-ocr:q8_0
.venv/bin/python docs/level-up-probe/scripts/glm_taste.py --zones # after the probe: reads its IRs
.venv/bin/python docs/level-up-probe/scripts/compare_sets.py      # needs debug/runs/G0-s14-rederived/scores.json
.venv/bin/python docs/level-up-probe/scripts/probe_report.py      # → debug/probe/unseen-2026-10-24/report.html
```

A re-run writes to `debug/probe/unseen-2026-10-24/`, which is gitignored;
`out/` is a copy of the run this write-up describes. The crops the scripts
cut are left out.

## What it cannot tell

- **Who wrote it.** An LLM wrote the pages, as it wrote the corpus. Real
  documents will be harder.
- **How many.** Ten pages show a large gap (§3.2 of the write-up). They do
  not show how faults are distributed.
- **The judging.** It is by eye, against the source. There is no previous
  render, so no pairwise better or worse.
- **Calls.** Model calls are not counted. The default engines do not record
  them in the trace; the bake-off path does.
