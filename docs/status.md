# Status

Snapshot of what exists, what does not, and what is known to be missing. Updated
at checkpoints; `CONTEXT.md` holds the vocabulary and `docs/adr/` the decisions,
neither of which belongs here.

**The whole path is connected and no model has ever run down it.** A Source Image
is rectified, laid out by a vision Engine, extracted Zone by Zone, checked by
Probes and rendered as one self-contained HTML file with the IR embedded. All
five fixtures convert with no Failures, and photographs distorted by known
amounts come back straight. The suite runs offline against recorded responses
with no model installed — which is exactly why the bake-off exists: everything
below the model is tested, and the model is not.

## Module state

| Module | State | Notes |
| --- | --- | --- |
| `ir.py` | **implemented** | Bands, Kind/Role, Row Roles, Title, Corrections, Failures, versioning, JSON round-trip |
| `wire.py` | **implemented** | Wire schemas for all five passes; layout mapping with geometric validation |
| `engines/transport.py` | **implemented** | The one call to Ollama, and the suite's only fake |
| `probes.py` | **implemented** | column-sum, row-product, number parsing across both decimal conventions |
| `render.py` | **implemented** | IR → self-contained HTML, tolerates partial IR, content-driven column alignment |
| `checkpoints.py` | **implemented** | `Question`/`Answer`, `NullHandler`, `ScriptedHandler` |
| `config.py` | **implemented** | Every `.env.example` variable, with a code default and recorded provenance; the only reader of the environment |
| `acceptance.py` | **implemented** | What "structurally correct" means, in one place. Used by the harness and the bake-off |
| `bakeoff.py` | **implemented** | Opt-in measurement of real models. Never run — no model has been pulled |
| `cli.py` | **partial** | `render`, `config` and `convert` work end to end; `--review` exits cleanly |
| `preprocess.py` | **implemented** | Page-quad detection, perspective warp, deskew, illumination flattening, cropping, slice planning. Slice *stitching* is not built |
| `engines/base.py` | **implemented** | `VisionEngine` and `BoxEngine` Protocols — the seam everything else depends on |
| `engines/ollama.py` | **partial** | `detect_zones` and `extract_zone` for all five Kinds are real, with the truncation retry; `read_cell` and `audit_coverage` raise |
| `engines/tesseract.py` | **stub** | deliberately — see "Open questions" |
| `extractors.py` | **implemented** | All five crop their Zone and hand it to the Engine; only `TableExtractor.stitch` raises |
| `orchestrator.py` | **partial** | Layout, extraction with the failure contract, and Probes run; the Coverage Audit and the Ladder are deliberate no-ops for this slice |

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
detect and the documented fallback is what fires. Seam 2 —
`tests/test_rectification.py`, which distorts a fixture by known amounts —
carries the rectifier's correctness alone. Landmarks come back within 8px of
where they sit in the undistorted rectification, on an 862px-wide page.

**Orientation is not corrected, only tilt.** A page photographed sideways or
upside down stays that way. Telling 90° from 270° means knowing which way up the
text runs, which means reading it — an Engine's job, and a rectifier that guesses
wrong ruins every coordinate in the IR. Deliberately narrower than the ticket
asked for.

**Nothing tells an operator their photograph was not warped.** `Rectified.warped`
records it and only tests read it. An unwarped photograph of a page shot at an
angle explains a bad render, and the render does not say so.

**No real photographs, no multi-page, no handwriting** in the fixtures. The
distortions Seam 2 uses are synthetic: geometry, not paper texture, camera noise
or focus. Real photographs arrive with the synthetic corpus generator, which
depends on the slice existing first.

**Extracted cells carry no bounding box.** The extraction schemas are flat and
ask for text, not per-cell geometry, so `Cell.bbox` is None for everything a
model read. Corrections anchor to cell geometry, which nothing in this slice
creates — but a Correction UI needs this before it can work.

**`Structural Fidelity` is a glossary term with no code referent.** This is
correct: it names a standard that lives in `docs/adr/0002`, not a code concept.
Recorded here so it is not "fixed" later.

## Open questions, deliberately unanswered

The first three now have somewhere to be answered rather than argued:
`python -m doc_to_html.bakeoff`. Nobody has run it, because no model has been
pulled on this machine. **Every number below is still an estimate.**

- **Whether tesseract earns a place.** The slice runs vision-only and is
  therefore the control condition. Its accuracy is the number tesseract has to
  beat.
- **Which model wins.** `qwen3-vl:2b` at 1.9 GB would let the extraction and
  audit models stay resident together; `qwen3-vl:4b` is likely more accurate.
  Measurement, not argument, settles this.
- **Whether the refinement loop's latency is tolerable.** Roughly 90s for a
  first round on an 8 GB M1, plus an audit pass per page — a guess, not a
  measurement. A conversion makes one layout pass plus one per Zone, which is
  3 to 11 passes per fixture.
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
pytest                        # 273 tests, no model, no Ollama, no network
mypy                          # strict, over src/

doc-to-html config            # what resolved, and from where
doc-to-html render tests/fixtures/invoice_0001.expected.json -o out.html
doc-to-html convert example/invoice.png -o out.html   # needs Ollama
```

Two generated artifacts are committed and have tools that rewrite them. Both are
checked by the suite, so drift is caught rather than discovered:

```bash
python tools/write_expected_ir.py    # tests/fixtures/*.expected.json
python tools/record_responses.py     # tests/responses/
```

The bake-off needs a running Ollama with the models pulled, and is the only thing
here that does:

```bash
python -m doc_to_html.bakeoff --fixtures invoice_0001 --models qwen3-vl:4b
```

Python is pinned to 3.12 via `.python-version`. All declared dependencies
install cleanly there, including OpenCV 5.0.
