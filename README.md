# doc-to-html

Takes a photograph or scan of a text-bearing document and produces an HTML file
that carries the same content and the same structure. An invoice and an
inventory sheet are the same kind of input: the system never classifies
documents.

**Status: working proof of concept, being rebuilt against a new measure.** A
Source Image is rectified, laid out, classified and extracted Zone by Zone from
full-resolution crops, checked by Probes and rendered. Photographs distorted by
known amounts come back straight.

**The target changed on 2026-09-17, and the reason is worth a paragraph.** The
project used to be scored on whether the IR agreed with a hand-typed reference
IR. That measure saturated and then inverted: it scored `sample_table_0003` a
**full match** while that document had deleted every column header of its only
table, because it compared row *roles* and never compared cell *content*. Over
the same stretch of runs the total improved 23 → 10 while duplicated titles
appeared in three of five documents. Nobody had opened a rendered page beside
its source in eighty runs.

**So the project is now measured on whether the rendered output looks and reads
like the source document**, compared against `example/*.html` and `example/*.png`
directly. See
**[docs/specs/0007-look-like-the-document.md](docs/specs/0007-look-like-the-document.md)**
(issue #30) — it is the live spec and the plan.

## What it aims at

Structural fidelity **and** measured style — not a pixel clone, and no longer
structure alone. A `<table>` is a real `<table>` and Zone ordering is preserved;
palette, type scale, borders and column proportion are measured from the Source
Image's pixels rather than invented by a stylesheet. Absolute-positioned
facsimile stays rejected: it is brittle under skew and semantically inert. See
[ADR 0005](docs/adr/0005-style-is-measured-from-the-pixels.md), which supersedes
part of [ADR 0002](docs/adr/0002-structural-over-pixel-fidelity.md).

Output is one self-contained HTML file with the IR embedded in it as JSON.

## How it is measured

Six axes, scored source-image against rendered-output by
`doc_to_html.scoring`:

| # | axis | asks |
|---|---|---|
| 1 | **Completeness** | Is every printed string present, exactly once? Nothing invented? |
| 2 | **Order & grouping** | Right reading order; things that belong together are together |
| 3 | **Layout skeleton** | What sits beside what; column proportions; height ratio at matched width |
| 4 | **Typographic weight** | Heading hierarchy; emphasis; alignment |
| 5 | **Palette & texture** | Background, ink, accent, shaded bands, borders, cards |
| 6 | **Inline detail** | Links, code spans, badges, marks |

**Axes 1-3 are a hard tier**: a regression on any of them fails a phase
regardless of what improved elsewhere. **Completeness is a ratchet** — it may
never decrease between phases, for any reason.

**Ground truth is derived, not typed.** `example/invoice.png` is a screenshot of
`example/invoice.html`, so the expected answer is already on disk. One
`project()` function runs over the source page and the rendered output alike —
returning text in reading order, a role per block, and rectangles from the
browser's own client rects — and the two projections are diffed. It never
compares markup: demanding that the output reproduce the source's `div` nesting
would be a worse overfit than the one being escaped.

Adding a document is therefore writing an HTML file and running
`tools/shoot_corpus.py`. That is what let the corpus leave five.

## Reading order

- **[CONTEXT.md](CONTEXT.md)** — the vocabulary. Zone, Band, Kind, Role, Probe,
  Ladder, Correction. Worth reading first; the code assumes these words.
- **[docs/status.md](docs/status.md)** — what is built, what is stubbed, what is
  missing, and what was rejected.
- **[docs/specs/](docs/specs/)** — the piece of work currently in flight, with its
  measured numbers. Start here if you are picking the project up.
- **[docs/adr/](docs/adr/)** — five decisions that look arbitrary without their
  reasons:
  - [0001](docs/adr/0001-no-document-types.md) — no document types
  - [0002](docs/adr/0002-structural-over-pixel-fidelity.md) — structural, not pixel, fidelity
  - [0003](docs/adr/0003-synthetic-first-evaluation.md) — synthetic-first evaluation
  - [0004](docs/adr/0004-probes-never-supply-expected-values.md) — Probes never supply expected values
  - [0005](docs/adr/0005-style-is-measured-from-the-pixels.md) — style is measured from the pixels

## Shape

```
Source Image
  │  rectify: page quad → perspective warp → orientation → equalise
  ▼
Rectified Image ──────────────────────────────── all coordinates live here
  │  layout: a trained ONNX detector finds the Zones — no model call
  │  classification (per-Zone full-res crop): Kind, Title
  │  per-Zone extraction from full-res crops, sliced with overlap if dense
  │  coverage audit (different model family): content no Zone covers   [not built]
  ▼
IR ── Probes: does a column of data rows sum to a summary row?
  │    Ladder: read → upscale → other engine → ask human
  ▼
one self-contained HTML file, IR embedded
  │
  ▼
project() over the output and over example/foo.html ── six axes ── report.html
```

Layout: `src/doc_to_html/`

| | |
|---|---|
| `ir.py` | the IR. Everything else reads or writes this |
| `preprocess.py` | Source Image → Rectified Image; slice planning |
| `engines/` | sources of readings from pixels — Ollama, tesseract |
| `extractors.py` | one per Kind. No autonomy, no retries |
| `orchestrator.py` | sequences Extractors, routes Engines, owns the Ladder |
| `probes.py` | arithmetic checks, type-agnostic |
| `render.py` | IR → HTML. Tolerates a partial IR |
| `checkpoints.py` | where a human is asked; `NullHandler` for unattended runs |
| `wire.py` | what a model is asked for, and how it becomes IR |
| `corpus.py` | what the corpus is — fifteen documents, *iterate* and *sweep* |
| `projection.py` | `project()` — one page as a reader sees it, off the browser |
| `scoring.py` | the six axes, between two projections |
| `report.py` | `report.html` — source vs render, every document, one page |
| `bakeoff.py` | opt-in conversion of the corpus with real models |
| `cli.py` | thin wrapper over the library |

## Try it

The suite replaces exactly one thing — the call to Ollama — with responses
recorded in `tests/responses/`. Everything else is the code that ships:

```bash
uv venv && uv pip install -e '.[dev]'
pytest                        # no model, no Ollama, no network
```

The scorer's own tests need headless Chrome and nothing else — they run over
`tests/frozen/run84/`, five output documents kept from the run that prompted
spec 0007, and they check that the scorer finds that run's known faults without
being told where to look.

With Ollama running and a model pulled, the front half works too:

```bash
doc-to-html config                                  # what resolved, and from where
doc-to-html convert example/invoice.png -o out.html
tools/iterate.sh my-label                           # one document, end to end
FIXTURE=sweep tools/iterate.sh my-gate              # all fifteen
```

Either way, open `debug/runs/<label>/report.html`.

Fifteen documents live in [`example/`](example/), each an HTML file and a
screenshot of it: two invoices, a statistics table, a card layout, an article, a
bank statement, an application form, a newspaper page, a dark report, a thermal
receipt, a corporate report, a restaurant menu, a CV, a Greek invoice and a
product grid. Each carries one awkward feature the others do not —
`doc_to_html.corpus` names it.

[`docs/status.md`](docs/status.md) tracks what is implemented, what is stubbed,
and what is known to be missing.

## Constraints worth knowing

Development targets an 8 GB M1, which caps local vision models at roughly 4 GB —
`qwen3-vl:2b`, `qwen3-vl:4b` and `granite3.2-vision` are in range; `deepseek-ocr`
at 6.7 GB is not. Two vision models cannot stay resident simultaneously, so the
Orchestrator batches work by model rather than alternating.

Ollama Cloud is a configuration change rather than an architectural one — but it
is a different *host*, not a different trust boundary. Images do leave the machine.

## Deliberately not decided

- **Whether tesseract earns a place.** The first end-to-end slice runs
  vision-only and is therefore the control condition that answers it.
- **Multi-page.** A Conversion is strictly one image. Admitting page 2 means
  growing the IR a `pages` array and revising every fixture — a known cost,
  accepted for now.
- **Free-text feedback interpreted by an LLM.** Checkpoints take structured
  answers plus a note passed verbatim into the next prompt. When interpretation
  arrives, its job is to map prose onto the structured answers, not to edit the
  IR directly.
