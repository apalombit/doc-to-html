# Status

Snapshot of what exists, what does not, and what is known to be missing. Updated
at checkpoints; `CONTEXT.md` holds the vocabulary and `docs/adr/` the decisions,
neither of which belongs here.

**As of the first checkpoint commit: the back half is real, the front half is
stubs.** No Source Image has ever been converted. Everything below the Engines —
the IR, the Probes, the renderer — is implemented and covered by 61 tests that
run offline with no model installed.

## Module state

| Module | State | Notes |
| --- | --- | --- |
| `ir.py` | **implemented** | Bands, Kind/Role, Row Roles, Title, Corrections, versioning, JSON round-trip |
| `probes.py` | **implemented** | column-sum, row-product, number parsing across both decimal conventions |
| `render.py` | **implemented** | IR → self-contained HTML, tolerates partial IR, content-driven column alignment |
| `checkpoints.py` | **implemented** | `Question`/`Answer`, `NullHandler`, `ScriptedHandler` |
| `config.py` | **implemented** | Every `.env.example` variable, with a code default and recorded provenance; the only reader of the environment |
| `cli.py` | **partial** | `render` and `config` work end to end; `convert` reaches unimplemented code; `--review` exits cleanly |
| `preprocess.py` | **stub** | `slice_points()` implemented and tested; `rectify()` raises |
| `engines/base.py` | **implemented** | `VisionEngine` and `BoxEngine` Protocols — the seam everything else depends on |
| `engines/ollama.py` | **stub** | all four methods raise |
| `engines/tesseract.py` | **stub** | deliberately — see "Open questions" |
| `extractors.py` | **stub** | all five registered, all raise |
| `orchestrator.py` | **stub** | Ladder, Rungs and the round loop are written; layout, ladder and feedback raise |

## Fixtures

Five documents, each with hand-authored expected IR. All are clean screenshots,
so they exercise structure and say nothing about photographs.

| Fixture | Zones | Bands | Probes | Covers |
| --- | --- | --- | --- | --- |
| `invoice_0001` | 6 | 4 | column-sum ✓ 385.00 | A totals row inside its table. The only fixture with a passing Probe. |
| `invoice_0002` | 10 | 6 | none | Dense Pairs, titled panels, an empty section, no arithmetic anywhere |
| `sample_table_0003` | 2 | 2 | none | 15 rows, thousands separators, Title on a table, no summary row |
| `sample_css_0004` | 5 | 4 | none | Captioned cards, a badge, inline code, decorative rules producing nothing |
| `sample_semantic_0005` | 9 | 8 | none | Bulleted list, nav bar, blockquote with attribution, two-column callout |

"None" is asserted, not incidental: a document with nothing to reconcile must
attract no Probe rather than a failing one.

Two traps preserved on purpose. Fixture 0002's bank account is
`MO123456789456123` — letter O, not zero, near-identical at render size, and
with no arithmetic anywhere to catch a misreading. Fixture 0003's thousands
separators move a value three orders of magnitude if misread.

## Known gaps

**Ollama Cloud is plumbed but unverified.** `config.py` resolves the host and
API key and `OllamaEngine.client_kwargs()` carries them to the client, so a
cloud host needs no code change. Nobody has run a Conversion against it.

**Rectification is untestable against the fixture set.** All five sources are
white documents filling a white frame, so no page quadrilateral exists to
detect and the documented fallback is what fires. Seam 2 — synthetically skewed
images — carries the rectifier's correctness alone.

**No photographs, no skew, no multi-page, no handwriting** in the fixtures.
Those arrive with the synthetic corpus generator, which depends on the slice
existing first.

**`Structural Fidelity` is a glossary term with no code referent.** This is
correct: it names a standard that lives in `docs/adr/0002`, not a code concept.
Recorded here so it is not "fixed" later.

## Open questions, deliberately unanswered

- **Whether tesseract earns a place.** The first slice runs vision-only and is
  therefore the control condition. Its accuracy is the number tesseract has to
  beat.
- **Which model wins.** `qwen3-vl:2b` at 1.9 GB would let the extraction and
  audit models stay resident together; `qwen3-vl:4b` is likely more accurate.
  Measurement, not argument, settles this.
- **Whether the refinement loop's latency is tolerable.** Roughly 90s for a
  first round on an 8 GB M1, plus an audit pass per page.
- **Multi-page.** A Conversion is strictly one Source Image; admitting page 2
  means growing the IR a `pages` array and revising every fixture.

## Rejected, with reasons recorded

- **Agent frameworks** (LangGraph, CrewAI). Extractors are deliberately
  autonomy-free and all retry policy lives in one Orchestrator — the property
  those frameworks exist to remove. The control flow is ~60 lines.
- **LiteLLM.** Its value is one interface across providers; this project is
  Ollama-only, and local vs cloud is already the same API. It would also put a
  translation layer between us and Ollama's constrained decoding, which is the
  thing that makes malformed JSON impossible, and re-normalise image passing.
  If a frontier model is ever wanted, it goes behind `VisionEngine` as one more
  class.
- **A database.** The IR travels inside the HTML file.

Both framework rejections rest on the same insurance: `VisionEngine` is a
four-method Protocol, so adopting any of them later is a change behind a seam
rather than a rewrite. The thing that would make it a rewrite is letting Ollama
calls leak into Extractors.

## Running what exists

```bash
uv venv && uv pip install -e '.[dev]'
pytest                                    # 61 tests, no model needed
doc-to-html render tests/fixtures/invoice_0001.expected.json -o out.html
```

Python is pinned to 3.12 via `.python-version`. All declared dependencies
install cleanly there, including OpenCV 5.0.
