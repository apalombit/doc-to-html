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

`example/invoice.png` is at **2 mismatches**, both the layout pass giving a Zone the
wrong Kind. Four prompt attempts failed to move them (runs 11, 12, 13, 16; 17
reproduced 16 exactly), and three broke Band numbering as a side effect.

It is not wording. The blocking experiment (issue #13, `tools/classify_probe.py`,
runs 18-20) measured **three** causes where 0003 argued one:

- **Zone 1 — isolation.** Asked on its own it answers `pairs` correctly even at
  96x38px; it only answers `prose` when asked as one of seven regions.
- **Zone 4 — resolution, but only for a model that can use it.** `qwen3.5:4b`
  flips `pairs`->`table` between layout scale and its crop. `qwen3-vl:4b` answers
  `pairs` at both, 6/6, with the shaded heading row plainly legible.
- **Neither alone fixes Zone 4** — the crop alone and the model swap alone both
  leave it wrong.

So 0003 concluded the fix was the split **plus** a classification pass routable
to its own model, defaulting to `qwen3.5:4b`. **The routing shipped; the model
swap did not** — see the decision below.

**#13, #14 and #15 are done.** `OllamaEngine.classify_zone` classifies one Zone
from its own crop, and the Orchestrator now runs geometry → classify → extract.
**#16 is next.**

**`DTH_CLASSIFY_MODEL` defaults to `qwen3-vl:4b` — one model in every step.**
0003 argued for defaulting it to `qwen3.5:4b`; that was **decided against on
2026-07-29**, and the split shipped without the model swap. The reasoning is not
that the probe was wrong but that it was thin: `qwen3.5:4b` has never run the
layout pass, never touched the other four fixtures, and never converted a
document, so making it a default would generalise from one measurement on one
fixture. Expect this default to fix **Zone 1 only** — Zone 1's problem is being
asked about as one of seven regions, which the split cures; Zone 4 needs a model
that can use the crop, and `qwen3-vl:4b` answered `pairs` 6/6 at full
resolution. **Two mismatches should become one, not zero.** Evaluating models
per step, and combinations across steps, is #19.

**The replay suite is red right now, and that is #15's expected outcome** — 49
failures across `test_table_extraction`, `test_acceptance`, `test_pairs_and_prose`,
`test_list_and_figure` and `test_bakeoff`. Replay serves recorded responses by
order, so the extra call per Zone means every fixture's classification call eats
what was recorded as its extraction answer. #16 re-records them. Do not treat
those failures as a defect, and do not fix them anywhere but #16.

Nothing here has been measured against a real model yet: no conversion has run
with the split, so the +1 call per Zone has no latency number and the predicted
"two mismatches becomes one" is a prediction, not a result. That is #19.

Nothing about `qwen3.5:4b`'s **geometry** has been measured — it has never run the
layout pass or touched the other four fixtures. #19 is where that happens, and it
is also where the cheaper untested rival belongs: one pass at a higher
`LAYOUT_LONG_EDGE` on `qwen3.5:4b`, which would need no split at all.

`docs/specs/0002-structure-not-geometry.md` (issue #11, now closed) is the history
— the measured numbers, the four rejected prompt attempts, and the header-row join
that took invoice.png from 3 mismatches to 2. `0001-one-image-at-a-time.md`
(issue #10, the open epic) is older history still.

Runs live in `debug/runs/<label>/`, newest highest. Each carries the prompt, host,
resolution, the CPU/GPU split and every raw answer that produced it. **Open a run's
`index.html` before changing a prompt** — `tools/inspect_run.py` builds it from a
`--dump` without calling Ollama, and reasoning about the page from coordinates
instead of pixels produced both retracted conclusions in 0001.

One turn of the loop: `DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>`, ~3 min.
`FIXTURE=all` runs all five fixtures — no prompt change has ever been measured
against the other four.

Verify this is still current with `gh issue list --state open`. If **#12** is
closed, this section is stale. If #15 is closed but #16 is open, expect a red
suite and read #16 before assuming something is broken.
