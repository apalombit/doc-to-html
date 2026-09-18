# Run 84's output documents, frozen

Copied — never moved — out of
`debug/runs/84-rule-not-a-line/dump/qwen3-vl_4b/<fixture>/document.html` on
2026-09-18, before spec 0007 Thread 0 deleted the harness that produced the run
and before `debug/runs/` is next cleared. Run 84 itself was left intact.

**Why they are here.** `debug/runs/` is gitignored and gets cleared, and these
five files are the only surviving artefact of the faults spec 0007 was opened
over. They are also the offline input the scorer is developed and tested
against: `tests/test_scoring.py` runs over them with **no model, no Ollama and
no network**, and it is Thread 0's exit gate.

**They are not a target.** Nothing should be made to match them. They are a
record of output that was *wrong* in three specific ways while the harness of
the day called it good.

Each file carries its own IR in a `<script type="application/json" id="doc-ir">`
block, so the Zones, their rectangles and every reading are in here too.

## What is wrong with each, established by eye before any of it was measured

| document | what to look for |
|---|---|
| `invoice_0001.html` | The logo renders as a dashed placeholder. `Invoice #: 123` is split at the wrong point — label `Invoice`, value `#: 123`. |
| `invoice_0002.html` | Titles duplicated ×3. The header became a Pairs panel repeating itself: `Invoice \| With Credit` beneath a caption bar reading `Invoice With Credit`. The ACME mark is simply gone. Height is ~1.6× the source at matched width. |
| `sample_table_0003.html` | **Every column header of its only table is deleted.** The source reads `Country \| ISO \| Population \| GDP (USD M) \| Currency`; the output's header row is the caption, which also appears above it. This scored a **full match** under the old harness. |
| `sample_css_0004.html` | `Card heading` and `Another card` each printed twice — once in the shaded title bar, once again as the body's first block. The blue `CSS` badge became a separate line reading `css`. Every code span and the anchor link are plain text. |
| `sample_semantic_0005.html` | Titles duplicated ×3. `Tags: html, web, standards` — one inline line — became a three-item bulleted list. Four hard line breaks in a source that prints none. Every one of nine links is plain text. |

## The causal chain behind the deleted table header

Every link in it shipped as an improvement, which is the point.

1. `DTH_CAPTION_PASS` lifts the caption into `Zone.title` — but does **not**
   withhold it from the crop handed to the table Extractor.
2. `with_grid(titled=)` subtracts the caption's printed line from the row
   budget, so the prompt ends: *"it holds 16 rows and 5 columns. Return exactly
   16 rows."*
3. The crop still shows 17 printed lines. The model obeyed the count and
   dropped one. It dropped the real header and kept the caption.

The harness scored it a match because it compared `RowRole` sequences and never
compared cell content.

## What the scorer says about them, unaided

Asked only general questions — no Zone index, no row number, nothing about
where to look. Reproduce with `pytest tests/test_scoring.py`.

| document | T1 recall | T1 precision | T1 joins | T2 tau | T3 beside | height |
|---|---|---|---|---|---|---|
| `invoice_0001` | 1.000 | 0.980 | 0.893 | 1.000 | 1.00 | 1.14 |
| `invoice_0002` | 0.966 | 0.923 | 0.929 | 0.849 | 0.64 | 1.63 |
| `sample_table_0003` | 0.974 | 0.981 | 0.973 | 1.000 | 1.00 | 1.26 |
| `sample_css_0004` | 1.000 | 0.917 | 1.000 | 1.000 | 1.00 | 1.26 |
| `sample_semantic_0005` | 0.990 | 0.936 | 0.958 | 0.953 | 0.88 | 1.22 |

It reports `country`, `iso` and `currency` as lost on `sample_table_0003`; a
Zone Title repeated inside its own body on **four** of the five; four hard line
breaks on `sample_semantic_0005` against zero in its source; and `invoice | 123`
as a broken join on `invoice_0001`, which recall, precision and tau all miss.

**These numbers are of these files.** They are reproducible because the files
are frozen and the scorer runs offline over them, which makes them the one set
of numbers in this repository that a later session may quote without re-taking.
Every number from a *run* remains uncitable — see `CLAUDE.md`.
