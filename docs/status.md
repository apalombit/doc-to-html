# Status

Snapshot of what exists, what does not, and what is known to be missing. Updated
at checkpoints; `CONTEXT.md` holds the vocabulary and `docs/adr/` the decisions,
neither of which belongs here.

## Where this is, in one paragraph

**The PoC works end to end and is two mismatches from correct on one image.** A
Source Image is rectified, laid out by a vision Engine, extracted Zone by Zone
from full-resolution crops, checked by Probes and rendered as one self-contained
HTML file with the IR embedded. Offline, all five fixtures convert with no
Failures. Against a real `qwen3-vl:4b`, `example/invoice.png` converts through
every pass in ~175s and lands at **2 mismatches**: every string on the page is
read correctly and the column-sum Probe reconciles at 385.00, but two Zones get
the wrong Kind.

### What the PoC is deliberately proving, and what it is not

The bet this whole slice tests is narrow: **that a 3–4B vision model on 8GB of
unified memory can recover a document's structure well enough to rebuild it as
HTML, without any per-document-type code.** So the scope is one image, one model,
one page, vision only. Not multi-page, not photographs, not handwriting, not
tesseract, not a correction UI — all of those are listed under "Known gaps" and
none of them is in flight.

The measure of success is `example/invoice.png` at **0 mismatches** against a real
model, then the same prompts held to the other four fixtures without regressing.

### What is being worked on right now

**`docs/specs/0003-classify-from-the-crop.md` — issue #12.** Both remaining
mismatches are the layout pass giving a Zone the wrong Kind, and issue #13
measured why: the pass is being asked two different questions about two different
things at once.

- Zone 1 (`Invoice #` / `Created` / `Due`) is fixed by **isolation** — asked on
  its own it answers `pairs` correctly even at 96×38px; it only answers `prose`
  when asked as one of seven regions.
- Zone 4 (a shaded `Payment Method | Check #` row over one data row) needs **both**
  a full-resolution crop **and** a model that can use it: `qwen3.5:4b` flips
  `pairs`→`table` between the two resolutions, `qwen3-vl:4b` answers `pairs` at
  both, 6/6.

So the fix is to split the layout pass into geometry and classification, and to
let classification run on its own model. Progress: #13 and #14 are done — the
Engine can classify one Zone from its crop, and nothing calls it yet. #15 wires
it into the Orchestrator, and is next.

| Issue | | |
|---|---|---|
| **#10** | open | Make one image work: `invoice.png`. The live epic. |
| **#12** | open | Classify from the crop. The current spec, child of #10. |
| #13, #14 | closed | Experiment; `classify_zone` behind `VisionEngine`. |
| **#15** | open | **Next.** Orchestrator runs geometry → classify → extract. |
| #16 | open | Re-record the five fixtures. Shares a branch with #15; the suite is red between them by design. |
| #17 | open | Delete Kind from the layout prompt. |
| #18 | open | Show each classification beside its crop. |
| #19 | open | Measure latency and all five fixtures. |

Closed and not coming back: **#1** (the end-to-end slice — built) and **#11**
(structure-not-geometry — took invoice.png from 3 mismatches to 2 and handed the
rest to #12).

The specs are the memory, and carry what was tried and rejected:
`0001-one-image-at-a-time.md` (run history), `0002-structure-not-geometry.md`
(the four rejected prompt attempts), `0003-classify-from-the-crop.md` (current).
Runs are on disk in `debug/runs/`, newest highest, and are gitignored.

Everything below describes the ground this stands on.

## Module state

| Module | State | Notes |
| --- | --- | --- |
| `ir.py` | **implemented** | Bands, Kind/Role, Row Roles, Title, Corrections, Failures, Caveats, versioning, JSON round-trip |
| `wire.py` | **implemented** | Wire schemas for all five passes; layout mapping with geometric validation |
| `engines/transport.py` | **implemented** | The one call to Ollama, and the suite's only fake |
| `probes.py` | **implemented** | column-sum, row-product, number parsing across both decimal conventions |
| `render.py` | **implemented** | IR → self-contained HTML, tolerates partial IR, content-driven column alignment |
| `checkpoints.py` | **implemented** | `Question`/`Answer`, `NullHandler`, `ScriptedHandler` |
| `config.py` | **implemented** | Every `.env.example` variable, with a code default and recorded provenance; the only reader of the environment |
| `acceptance.py` | **implemented** | What "structurally correct" means, in one place. Used by the harness and the bake-off |
| `bakeoff.py` | **implemented** | Opt-in measurement of real models. Run partially; see "What the first bake-off found" |
| `cli.py` | **partial** | `render`, `config` and `convert` work end to end; `--review` exits cleanly |
| `preprocess.py` | **implemented** | Page-quad detection, perspective warp, deskew, illumination flattening, cropping, slice planning. Owns `zone_pixels`, so the classifier and the Extractors cut identical pixels. Slice *stitching* is not built |
| `engines/base.py` | **implemented** | `VisionEngine` (five methods) and `BoxEngine` Protocols — the seam everything else depends on |
| `engines/ollama.py` | **partial** | `detect_zones`, `classify_zone` and `extract_zone` for all five Kinds are real, with the truncation retry; `read_cell` and `audit_coverage` raise |
| `engines/tesseract.py` | **stub** | deliberately — see "Open questions" |
| `extractors.py` | **implemented** | All five crop their Zone and hand it to the Engine; only `TableExtractor.stitch` raises |
| `orchestrator.py` | **partial** | Layout, extraction with the failure contract, and Probes run. **Does not call `classify_zone` yet** — that is #15. The Coverage Audit and the Ladder are deliberate no-ops for this slice |

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

**`TARGET_LONG_EDGE` is a ceiling, not a target.** The ticket said "the long edge
resized to the working resolution"; `resize_long_edge` never enlarges, so the five
fixtures stay at their own size and only a photograph bigger than 3508px is
scaled. Enlarging adds no detail and multiplies the cost of every crop taken from
it. A deliberate reading of "working resolution" as a cap, pinned by
`test_a_small_screenshot_is_not_enlarged`.

**No graphic kind covers a handwritten annotation.** `CONTEXT.md`'s **Mark** entry
names one as an example, but `wire.GRAPHIC_KINDS` offers only `logo`, `chart`,
`signature`, `stamp` and `badge`, so a model has nowhere to report one. Adding a
value is cheap; deciding what to call it without colliding with the glossary's
`_Avoid_` list for Mark is the part that needs a moment's thought.

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

- **Whether tesseract earns a place.** The slice runs vision-only and is
  therefore the control condition. Its accuracy is the number tesseract has to
  beat.
- **Which model wins — partly answered, and the answer is "not one model".**
  `qwen3-vl:4b` reads text correctly on `invoice.png` but cannot tell a shaded
  heading row from a label/value pair at any resolution (issue #13, 6/6 wrong).
  `qwen3.5:4b` gets that Kind right from a full-resolution crop, and is 3.4GB
  against 3.3GB, so it fits the same budget. **Its geometry has never been
  measured** — it has not run the layout pass or touched the other four fixtures.
  #19 is where that happens. Until then "classification wants a different model
  from extraction" is a measured claim about two Zones, not about the pipeline.
- **Whether the latency is tolerable.** `invoice_0001` converts in ~175s on
  `qwen3-vl:4b` with the whole GPU. Adding one classification call per Zone is
  #15's cost and #19 measures it. Tolerable for a batch, not for an interactive
  tool — and memory pressure can make any of these figures 40x worse, so no
  number taken without checking `ollama ps` first means anything.
- **Whether the split is even the cheapest fix.** Untested rival: one pass at a
  higher `LAYOUT_LONG_EDGE` on `qwen3.5:4b` might fix Zone 4 with no extra call
  per Zone at all. The isolation finding argues against it — Zone 1 needs the
  question narrowed, not the page enlarged — but that is an argument, not a
  measurement. Recorded in spec 0003.
- **Multi-page.** A Conversion is strictly one Source Image; admitting page 2
  means growing the IR a `pages` array and revising every fixture.

## What the first bake-off found

Four things, none of which argument would have produced.

**Memory is the binding constraint, and it presents as latency.** With an
unrelated `llama3.2:3b` resident, one layout pass took **180s and timed out**. With
nothing else loaded, the same pass took **4.5s**. A 40x difference from memory
pressure alone, on a machine with 8 GB and ~76 MB free. Any latency figure taken
without checking `ollama ps` first is meaningless.

**Ollama routes `qwen3-vl`'s structured output to the reasoning channel.** With
`think=False` the model answers correctly and quickly, but the JSON arrives in
`message.thinking` with `message.content` empty. Reading only `content` — the
obvious thing, and what the transport did — makes a working model indistinguishable
from a hang. `Response.answer` now takes whichever channel carried it.

**`think=False` is not reliably honoured.** On one document `qwen3-vl:2b` answered
with no reasoning at all; on another it spent 5,609 characters reasoning and never
answered, filling a 4096-token budget. `ThinkingNotDisabled` names that case
because a bigger budget buys more reasoning, which is the opposite of the fix.

**The layout pass had never been downscaled.** `MODEL_INPUT_LONG_EDGE` was 1024 and
every fixture is smaller, so the documented "layout runs on a downscaled page"
design was a no-op. `LAYOUT_LONG_EDGE` (512) now separates the layout budget from
extraction's, and that alone is what got `invoice_0001` through all eight passes
without aborting — 322.9s for the whole document on `qwen3-vl:4b`.

**The layout pass returned schematic geometry.** Boxes came back snapped to a 0.05
grid, tiling the page in uniform strips rather than locating content — one strip
being full-width and enclosing the Zone beside it. The mapper's plausibility
checks cannot catch that, because tiling strips satisfy all of them.

*Since fixed enough to stop being the cause.* The boxes are now roughly right and
every string reads correctly; what is left is **IoU 0.56**, with Zones 0–3
identical at 384/512/768/862 — the geometry pass emitting a prior instead of
measuring. That is a real defect and is **explicitly out of scope** for spec 0003,
which is about Kind, not boxes. Nothing is in flight against it.

Two claims I made earlier here were wrong and are withdrawn. "Neither candidate
follows the Band and column instruction" was generalised from one document — on
`invoice_0001` the 4B model numbers Bands correctly. And deriving Bands from
geometry, proposed as the fix, is **worse** in a measured case: on
`sample_table_0003` the 2B model's boxes overlap vertically and derivation collapses
two Bands into one.

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
five-method Protocol, so adopting any of them later is a change behind a seam
rather than a rewrite. The thing that would make it a rewrite is letting Ollama
calls leak into Extractors.

## Running what exists

```bash
uv venv && uv pip install -e '.[dev]'
pytest                        # 327 tests, no model, no Ollama, no network
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
