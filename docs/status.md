# Status

Snapshot of what exists, what does not, and what is known to be missing. Updated
at checkpoints; `CONTEXT.md` holds the vocabulary and `docs/adr/` the decisions,
neither of which belongs here.

## Where this is, in one paragraph

**The PoC works end to end and `example/invoice.png` now converts with zero
mismatches.** A Source Image is rectified, laid out by a vision Engine, classified
Zone by Zone from its own crop, extracted from the same crop, checked by Probes
and rendered as one self-contained HTML file with the IR embedded. Against a real
`qwen3-vl:4b` the invoice matches its expected IR exactly — all six Kinds right,
every string on the page rendered, no skeletons, no Failures, and the column-sum
Probe reconciling at 385.00. Run 49, `debug/runs/49-table-grid-hint/`, taken with
`DTH_SNAP_ZONES=1`.

**Everything below this paragraph predates that result** and describes the
document at 2 and 3 mismatches. It is kept as the record of how the count moved
and what was rejected on the way; `CLAUDE.md` and
`docs/specs/0003-classify-from-the-crop.md` carry the current state. The three
standing caveats are that only this one fixture is measured, that the shipped
default has `DTH_SNAP_ZONES` off so `convert()` out of the box is unmeasured, and
that the replay suite is red by design until #16 re-records it.

The count went up, not down. The classification split (#12) was predicted to take
it from 2 to 1; run 22 measured 3. It fixed the Zone it was designed to fix and
broke one it was not designed to touch — see below, and
`docs/specs/0003-classify-from-the-crop.md` for the numbers.

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

**`docs/specs/0003-classify-from-the-crop.md` — issue #12.** Every remaining
mismatch is a Zone getting the wrong Kind. When there were two of them, issue #13
measured why: the layout pass is being asked two different questions about two
different things at once.

- Zone 1 (`Invoice #` / `Created` / `Due`) is fixed by **isolation** — asked on
  its own it answers `pairs` correctly even at 96×38px; it only answers `prose`
  when asked as one of seven regions.
- Zone 4 (a shaded `Payment Method | Check #` row over one data row) needs **both**
  a full-resolution crop **and** a model that can use it: `qwen3.5:4b` flips
  `pairs`→`table` between the two resolutions, `qwen3-vl:4b` answers `pairs` at
  both, 6/6.

So the fix is to split the layout pass into geometry and classification, and to
make classification routable to its own model. Progress: #13, #14 and #15 are
done — the Engine can classify one Zone from its crop, and the Orchestrator now
runs geometry → classify → extract.

**The routing shipped; the model swap did not.** `DTH_CLASSIFY_MODEL` defaults
to `qwen3-vl:4b`, one model in every step — decided 2026-07-29, against 0003's
recommendation. Not because the probe was wrong but because it was thin:
`qwen3.5:4b` has never run the layout pass, touched the other four fixtures, or
converted a document, so defaulting to it would generalise from one measurement
on one fixture. Evaluating models per step and combinations across steps is #19.

**Run 22 is the first conversion with the split, and it made `invoice_0001`
worse: 2 mismatches → 3.** Baseline is run 21 at the commit before the split;
same model, same fixture, same long edge, both at the same 41%/59% CPU/GPU split.

- **Zone 1 is fixed**, `prose` → `pairs`, exactly as the isolation finding
  predicted.
- **Zone 4 is unchanged.** `qwen3-vl:4b` answers `pairs` from a crop where the
  shaded heading row is plainly legible — now 7/7 wrong, counting this run.
  It needs a different model, which is #19.
- **Zone 3 regressed**, `prose` → `pairs`, and this was not predicted by anything.
  Zones 2 and 3 are the two address blocks in Band 1. Zone 2 (`Sparksuite, Inc.`
  / a street / a city) still reads `prose`; Zone 3 (`Acme Corp.` / `John Doe` /
  `john@example.com`) has no street and no city in it, and asked with no
  neighbour to compare against it reads `pairs`. **Isolation cuts both ways** —
  narrowing the question also removes the evidence that lives between Zones. That
  is a fourth mechanism on top of #13's three, and 0003 did not have it.
- **A wrong Kind is not confined to the Kind.** Zone 3 went to the Pairs
  extractor and raised `MappingError` on an unlabelled value. The failure
  contract held — that Zone renders as a skeleton with an "Unresolved" finding,
  the other five convert — but the document lost a block it used to render.

**Classification costs ~95s per document**: 6 calls, 15.8s mean, 17.4s worst, on
a 219.3s baseline. The document total rose only 27.2s, and that discount is an
artefact of the wrong Kinds — three Zones went to the cheaper Pairs prompt
instead of Prose. Quote the 95s.

**The replay suite is red, by design**: replay serves recorded responses by
order, so the extra call per Zone puts all five fixtures out of step. #16
re-records them and is next.

**A second spec is now open against the same three mismatches from the other
end** — `docs/specs/0004-check-the-box-against-the-ink.md`, issue #20. 0003 asks
which model names a Zone's Kind; 0004 asks whether the crop that Kind is judged
from is the Zone at all. Runs 26-32 measured geometry itself at **mean best IoU
0.56**, invariant to resolution and worse under prompt framing, with no check
anywhere comparing a box to ink. Its first gate decides whether #12's and #19's
comparisons are being run on inputs that are themselves wrong.

| Issue | | |
|---|---|---|
| **#10** | open | Make one image work: `invoice.png`. The live epic. |
| **#12** | open | Classify from the crop. The current spec, child of #10. |
| #13, #14, #15 | closed | Experiment; `classify_zone` behind `VisionEngine`; the Orchestrator driving it. |
| **#16** | open | **Next.** Re-record the five fixtures. Shares a branch with #15; the suite is red between them by design. |
| #17 | open | Delete Kind from the layout prompt. |
| #18 | open | Show each classification beside its crop. |
| #19 | open | Measure latency and all five fixtures. |
| **#20** | open | Check the box against the ink — spec 0004. Geometry itself, measured: IoU 0.56 on the shipped path, and its Gate 1 decides whether #12/#19 are measuring the wrong inputs. |

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
| `config.py` | **implemented** | Every `.env.example` variable, with a code default and recorded provenance; the only reader of the environment. `DTH_CLASSIFY_MODEL` is the one role that does not default to the layout model |
| `acceptance.py` | **implemented** | What "structurally correct" means, in one place. Used by the harness and the bake-off |
| `bakeoff.py` | **implemented** | Opt-in measurement of real models. Run partially; see "What the first bake-off found" |
| `cli.py` | **partial** | `render`, `config` and `convert` work end to end; `--review` exits cleanly |
| `preprocess.py` | **implemented** | Page-quad detection, perspective warp, deskew, illumination flattening, cropping, slice planning. Owns `zone_pixels`, so the classifier and the Extractors cut identical pixels. Slice *stitching* is not built |
| `engines/base.py` | **implemented** | `VisionEngine` (five methods) and `BoxEngine` Protocols — the seam everything else depends on |
| `engines/ollama.py` | **partial** | `detect_zones`, `classify_zone` and `extract_zone` for all five Kinds are real, with the truncation retry; `read_cell` and `audit_coverage` raise |
| `engines/tesseract.py` | **stub** | deliberately — see "Open questions" |
| `extractors.py` | **implemented** | All five crop their Zone and hand it to the Engine; only `TableExtractor.stitch` raises |
| `orchestrator.py` | **partial** | Geometry, classification and extraction run in that order, each with the failure contract, plus Probes. Classification is routable to its own model and runs once per Conversion. The Coverage Audit and the Ladder are deliberate no-ops for this slice |

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
- **Which model wins — still open, and shipping as one model until it is not.**
  `qwen3-vl:4b` reads text correctly on `invoice.png` but cannot tell a shaded
  heading row from a label/value pair at any resolution (issue #13, 6/6 wrong;
  7/7 counting run 22's full conversion).
  `qwen3.5:4b` gets that Kind right from a full-resolution crop, and is 3.4GB
  against 3.3GB, so it fits the same budget. **Its geometry has never been
  measured** — it has not run the layout pass or touched the other four fixtures.
  So "classification wants a different model from extraction" remains a measured
  claim about two Zones, not about the pipeline, and #15 shipped the *ability* to
  act on it rather than the act: one model fills all three roles today, and
  `DTH_CLASSIFY_MODEL` is what a future answer changes. #19 is where the
  evaluation — per step, and across combinations — happens.
- **Whether the latency is tolerable.** `invoice_0001` converts in ~175s on
  `qwen3-vl:4b` with the whole GPU. Adding one classification call per Zone costs
  **~95s per document** — 6 calls at 15.8s mean, measured in run 22 at a 41%/59%
  CPU/GPU split, so the absolute figures are inflated but the ratio to that run's
  own baseline is not. The "it is only one enum out" argument does not hold: the
  cost is encoding the crop and prefilling the prompt, and classification pays it
  in full and then makes the Extractor pay it again on the same pixels. #19 still
  owes two runs on a whole GPU. Tolerable for a batch, not for an interactive
  tool — and memory pressure can make any of these figures 40x worse, so no
  number taken without checking `ollama ps` first means anything.
- **Whether the split is even the cheapest fix.** Untested rival: one pass at a
  higher `LAYOUT_LONG_EDGE` on `qwen3.5:4b` might fix Zone 4 with no extra call
  per Zone at all. The isolation finding argues against it — Zone 1 needs the
  question narrowed, not the page enlarged — but that is an argument, not a
  measurement. Recorded in spec 0003, and run 22 strengthens the rival's case: a
  single pass is the only one of the two that can see two address blocks at once.
- **What a Zone judged alone is owed.** Run 22's Zone 3 says a Kind decided from
  one crop can be wrong precisely because it is alone — the block beside it was
  the evidence. Three candidate answers, none measured: widen `CLASSIFY_PROMPT`'s
  `prose` cue (which is the move 0002 records four failures of, so not on one
  run); give the classifier the Role and Band position it already has and does
  not use; or treat a neighbourless Kind as provisional and let something else
  break the tie, which is what the Coverage Audit was for. #19 decides.
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
