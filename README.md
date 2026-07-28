# doc-to-html

Takes a photograph or scan of a text-bearing document and produces an HTML file
that carries the same content and the same structure. An invoice and an
inventory sheet are the same kind of input: the system never classifies
documents.

**Status:** scaffold. The back half — IR, Probes, renderer — is implemented and
tested. No vision model is wired yet.

## What it aims at

Structural fidelity, not a pixel clone. A `<table>` is a real `<table>`, Zone
ordering is preserved, and side-by-side blocks stay side by side — but styling
comes from this project's stylesheet, so two invoices from different vendors
render looking like siblings rather than like their originals.

Output is one self-contained HTML file with the IR embedded in it as JSON.

## Reading order

- **[CONTEXT.md](CONTEXT.md)** — the vocabulary. Zone, Band, Kind, Role, Probe,
  Ladder, Correction. Worth reading first; the code assumes these words.
- **[docs/status.md](docs/status.md)** — what is built, what is stubbed, what is
  missing, and what was rejected.
- **[docs/adr/](docs/adr/)** — four decisions that look arbitrary without their
  reasons:
  - [0001](docs/adr/0001-no-document-types.md) — no document types
  - [0002](docs/adr/0002-structural-over-pixel-fidelity.md) — structural, not pixel, fidelity
  - [0003](docs/adr/0003-synthetic-first-evaluation.md) — synthetic-first evaluation
  - [0004](docs/adr/0004-probes-never-supply-expected-values.md) — Probes never supply expected values

## Shape

```
Source Image
  │  rectify: page quad → perspective warp → orientation → equalise
  ▼
Rectified Image ──────────────────────────────── all coordinates live here
  │  layout pass (vision): Bands, Zones, Kind, Role, bbox
  │  per-Zone extraction from full-res crops, sliced with overlap if dense
  │  coverage audit (different model family): content no Zone covers
  ▼
IR ── Probes: does a column of data rows sum to a summary row?
  │    Ladder: read → upscale → other engine → ask human
  ▼
one self-contained HTML file, IR embedded
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
| `cli.py` | thin wrapper over the library |

## Try the back half

The renderer and Probes need no model, so the fixtures exercise them today:

```bash
uv venv && uv pip install -e '.[dev]'
pytest
doc-to-html render tests/fixtures/invoice_0001.expected.json -o out.html
```

Five documents in [`example/`](example/) have hand-authored expected IR in
`tests/fixtures/` — two invoices, a statistics table, a card layout and an
article. Each is authored against the *rendered image*, deliberately not derived
from the source HTML, whose markup tree bears no relation to what a reader sees.

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
