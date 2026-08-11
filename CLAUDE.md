# doc-to-html

## Agent skills

### Issue tracker

Issues live as GitHub issues in `apalombit/doc-to-html`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Specs

Work in flight has a spec in `docs/specs/`, one file per piece of work, each tracked
as a GitHub issue. **Read the spec before the code** — it carries the measured
numbers and what has already been tried and rejected.

## Current work

**`docs/specs/0003-classify-from-the-crop.md`** — issue #12.

`example/invoice.png` is at **3 mismatches**, all of them a Zone getting the wrong
Kind, one of which then fails extraction. **It was at 2 before the classification
split, and the split is what put it at 3** — read run 22 below before concluding
something is broken. Four prompt attempts failed to move the original two (runs
11, 12, 13, 16; 17 reproduced 16 exactly), and three broke Band numbering as a
side effect.

It is not wording. The blocking experiment (issue #13, `tools/classify_probe.py`,
runs 18-20) measured **three** causes where 0003 argued one:

- **Zone 1 — isolation.** Asked on its own it answers `pairs` correctly even at
  96x38px; it only answers `prose` when asked as one of seven regions.
- **Zone 4 — resolution, but only for a model that can use it.** `qwen3.5:4b`
  flips `pairs`->`table` between layout scale and its crop. `qwen3-vl:4b` answers
  `pairs` at both, 6/6, with the shaded heading row plainly legible.
- **Neither alone fixes Zone 4** — the crop alone and the model swap alone both
  leave it wrong.

**It is not the crop either, and that is now measured rather than assumed.** Run
42 (`tools/classify_truth_probe.py`) handed the classifier the *exact* Zone
rectangles read off `example/invoice.html`, and Zones 3 and 4 came back `pairs`
and `pairs` — identical to what the model's own boxes produce. **Perfect geometry
does not move either mismatch.** So what is left for Zone 4 is the model, which
is #19, and for Zone 3 the isolation mechanism below.

So 0003 concluded the fix was the split **plus** a classification pass routable
to its own model, defaulting to `qwen3.5:4b`. **The routing shipped; the model
swap did not** — see the decision below.

**#13, #14 and #15 are done.** `OllamaEngine.classify_zone` classifies one Zone
from its own crop, and the Orchestrator now runs geometry → classify → extract.
**#16 is next.**

### Run 22 — the split, measured end to end for the first time

`debug/runs/22-split-first-e2e/` at commit `9c300b8`, against
`debug/runs/21-fresh-invoice-qwen3vl/` at `ffd2761`, the commit before the split.
Same model, same fixture, `DTH_LAYOUT_LONG_EDGE=384`, both at 41%/59% CPU/GPU —
comparable with each other, not with a whole-GPU run.

| Zone | Expected | Run 21 | Run 22 | |
|---|---|---|---|---|
| 1 | `pairs` | `prose` | `pairs` | ✓ **fixed** |
| 3 | `prose` | `prose` | `pairs` | ✗ **new** |
| 4 | `table` | `pairs` | `pairs` | ✗ unchanged |

Zones 0, 2 and 5 were and remain correct. Both predictions held: isolation fixed
Zone 1, and Zone 4 still needs a model that can use the crop — `qwen3-vl:4b` is
now 7/7 wrong on it. What no one predicted is Zone 3.

**Isolation cuts both ways — this is the fourth mechanism, and 0003 does not
have it.** Zones 2 and 3 are the two address blocks in Band 1. Zone 2 is
`Sparksuite, Inc.` / a street / a city and still reads `prose`. Zone 3 is
`Acme Corp.` / `John Doe` / `john@example.com` — no street, no city — and asked
alone, with no neighbour to compare against, it reads `pairs`. Narrowing the
question also removes the evidence that lives *between* Zones. **Do not "fix"
this by widening the prompt's `prose` cue on the strength of one run**; 0002
records four failures of exactly that move. The options are in 0003.

The wrong Kind then cost the content: Zone 3 went to the Pairs extractor, which
raised `MappingError` on an unlabelled value. The failure contract held — that
Zone renders as a skeleton with an "Unresolved" finding, the other five convert.

**Classification costs ~95s per document**: 6 calls, 15.8s mean, 17.4s worst,
against a 219.3s baseline. The document total rose only 27.2s, and that discount
is an artefact of the wrong Kinds routing three Zones to the cheaper Pairs prompt
instead of Prose. **Quote the 95s, not the 12%.**

**#18's main complaint is gone.** `tools/inspect_run.py` used to name the crops
with geometry's discarded Kind, so checking Zone 3 meant opening
`zone_03_prose.png` for a Zone the classifier called `pairs`. A `--dump` now
carries `zones_used.json` — the Zones the Document actually held — and the
contact sheet prefers it, so crop filenames and the geometry report both carry
the Kind that was converted.

**`DTH_CLASSIFY_MODEL` defaults to `qwen3-vl:4b` — one model in every step.**
0003 argued for defaulting it to `qwen3.5:4b`; that was **decided against on
2026-07-29**, and the split shipped without the model swap. The reasoning is not
that the probe was wrong but that it was thin: `qwen3.5:4b` has never run the
layout pass, never touched the other four fixtures, and never converted a
document, so making it a default would generalise from one measurement on one
fixture. It was expected to fix **Zone 1 only**, taking two mismatches to one —
**measured in run 22, and the answer is three.** Zone 1 was fixed, Zone 4 was not,
and Zone 3 broke. Evaluating models per step, and combinations across steps, is
#19.

**The replay suite is red right now, and that is #15's expected outcome** — 49
failures across `test_table_extraction`, `test_acceptance`, `test_pairs_and_prose`,
`test_list_and_figure` and `test_bakeoff`. Replay serves recorded responses by
order, so the extra call per Zone means every fixture's classification call eats
what was recorded as its extraction answer. #16 re-records them. Do not treat
those failures as a defect, and do not fix them anywhere but #16.

Run 22 is **one run, on one fixture, at a degraded CPU/GPU split**. #19 still owes
two runs each on a whole GPU and the same numbers for the other four fixtures —
no prompt change has ever been measured against them, and a change that decides
`table` against `pairs` differently has two likely casualties there.

Nothing about `qwen3.5:4b`'s **geometry** has been measured — it has never run the
layout pass or touched the other four fixtures. #19 is where that happens, and it
is also where the cheaper untested rival belongs: one pass at a higher
`LAYOUT_LONG_EDGE` on `qwen3.5:4b`, which would need no split at all. **Run 22
strengthens that rival's case** — a single pass is the only one of the two that
can see both address blocks at once.

### `docs/specs/0004-check-the-box-against-the-ink.md` — issue #20, built, and its premise refuted

0004 asked whether the crop a Kind is judged from is the Zone at all, and spent
#21-#27 building the means to answer it. All seven are closed. **The answer is
that the crops were never the problem**, and the way that was established matters
more than the spec's own conclusions.

**The ruler was bent, and it was bending every number in the project.** The Zone
rectangles in the fixtures were typed by hand. `tools/fixture_geometry.py` now
reads `invoice_0001`'s off `example/invoice.html` as the browser lays it out —
the union of the client rects of every text node and image, plus 1px for
antialiasing. The typed boxes were **0.66 IoU from the truth**. The other four
fixtures are still hand-typed and their geometry numbers still cannot be trusted.

**That reversed 0004's central decision.** Its rule keys on the snapped IoU: at
or above 0.75 the model's grouping was right and only its arithmetic was wrong,
so keep the VLM geometry pass; at or below 0.65, rebuild geometry from scratch
(the spec's "Family 2").

| snapped geometry scored against | IoU | the rule says |
|---|---|---|
| the typed reference | 0.62 | rebuild geometry |
| the true rectangles | **0.909** | keep the VLM pass |

Snapping the existing model's answer reaches 0.91 IoU, 0.99 `covered` and 0
`splits` against the truth. **It was never a grouping problem. It was a
measurement problem, and it had been one since run 24.**

**Gate 1 passed and shipping it cost the document.** `covered` 0.82 -> 0.99,
`splits` 46 -> 0, Zone count unchanged, nothing worse on any fixture — every
condition the gate was written to check. Wired in, run 39 went from **3
mismatches to 6**: Zone 5, the line-item table, stopped extracting (`table row 2
has 0 cells but the header has 2`) and took the column-sum Probe with it. **None
of the gate's fields can see extraction.** Reverted in run 40, back to 3 off.
`snap_to_ink` and `snapped_or_original` are kept, tested and unwired. Any gate
that re-wires them must include *no Zone that previously converted stops
converting*.

**Geometry is broken on four of the five fixtures**, which nobody knew because
nobody had measured them (run 36, `tools/layout_probe.py --fixtures all`):

| fixture | zones | covered | splits | Bands valid? |
|---|---|---|---|---|
| invoice_0001 | 6 | 0.82 | 46 | yes |
| **invoice_0002** | — | — | — | **no answer at all** |
| sample_css_0004 | 6 | 0.60 | 1 | no |
| sample_semantic_0005 | 10-11 | 0.26 | 131 | no |
| sample_table_0003 | 3 | 1.00 | 4 | no on one repeat |

`invoice_0002` returns nothing: both repeats died with `ThinkingNotDisabled`,
15,727 characters of reasoning and no answer, **despite `think=False` already
being sent**. Three of the other four fail Band validation. Every conclusion in
0002, 0003 and 0004 rests on `invoice_0001`, the one document where geometry
works at all.

**Gate 3 failed.** The XY-cut arm produces six Zones and `covered` 1.00 — better
than the model — while merging the two stacked tables into one Band and splitting
it by column. The middle of that table region holds 27 ink pixels of the page's
13,850, so two narrow strips really do contain almost all the ink. **A single
number would have called that a win**, which is why the six fields are never
reported alone.

**The layout answer is not deterministic.** Runs 32/33/34 returning identical
geometry was read as proof that it is; run 36's two repeats differ — `covered`
0.82/0.81, `splits` 46/51. Stable to two decimals on the coordinates, not
identical call to call.

What 0004 leaves behind and is worth keeping: `doc_to_html.geometry_score` (one
six-field ruler behind every tool — `zones`, `iou`, `covered`, `splits`,
`doubles`, `valid`), `snap_to_ink`, `tools/fixture_geometry.py`,
`tools/snap_probe.py`, `tools/classify_truth_probe.py`, and the XY-cut arm.

`docs/specs/0002-structure-not-geometry.md` (issue #11, now closed) is the history
— the measured numbers, the four rejected prompt attempts, and the header-row join
that took invoice.png from 3 mismatches to 2. `0001-one-image-at-a-time.md`
(issue #10, the open epic) is older history still.

Runs live in `debug/runs/<label>/`, newest highest. Each carries the prompt, host,
resolution, the CPU/GPU split and every raw answer that produced it. **Open a run's
`index.html` before changing a prompt** — `tools/inspect_run.py` builds it from a
`--dump` without calling Ollama, and reasoning about the page from coordinates
instead of pixels produced both retracted conclusions in 0001.

**`debug/` is gitignored, and runs 21-32 were deleted on 2026-08-11 as stale.**
Anything above referring to them is history, not something you can open. Nothing
in the suite reads a run directory any more — `tests/test_layout_guards.py` used
to, which meant it passed on one machine and failed on every other; its geometry
is written out as literals now, like every other test here. Regenerate rather
than hunt: one turn of the loop is one document.

One turn of the loop: `DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>`, ~4 min
since classification added a call per Zone. `FIXTURE=all` runs all five fixtures —
no prompt change has ever been measured against the other four.

Verify this is still current with `gh issue list --state open`. If **#12** is
closed, this section is stale. If #15 is closed but #16 is open, expect a red
suite and read #16 before assuming something is broken.

**Where this stands, and what to do next.** `invoice.png` is at 3 mismatches and
all three are classification: Zone 3 `prose` read as `pairs`, Zone 4 `table` read
as `pairs`, and Zone 3's extraction failing as a consequence. Run 42 proved
neither moves under perfect geometry. Zone 4 has been wrong in every run ever
taken, and #13 measured `qwen3.5:4b` answering it correctly 6/6 from the same
crop. **That makes per-step model routing (#19) the only open lead on this
document**, and it is now a much narrower question than when #19 was written:
not "is the crop wrong" but "which model answers this crop".

Two things that would otherwise be re-derived the hard way:

- **Do not read a geometry IoU for any fixture except `invoice_0001`** without
  first deriving its rectangles from source, the way `tools/fixture_geometry.py`
  does. The typed boxes are 0.605-0.854 against their own ink.
- **Do not gate a geometry change on geometry fields alone.** Gate 1 was
  pre-registered, passed on every field it named, and shipped a regression that
  cost a Zone and a Probe.
