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

It is not wording, it is **resolution**: layout classifies at 384px, where the
evidence does not survive — Zone 1 is 73x33px for three lines whose colons are
about one pixel each. The fix is to split the pass and classify each Zone from its
**full-resolution crop**, which the Extractor already takes seconds later.

**Start with the blocking experiment in 0003**: ask the model the Kind question
against the two crops already on disk. If it answers `prose` and `pairs` again, the
spec is void and the problem is the model, not the pixels.

`docs/specs/0002-structure-not-geometry.md` (issue #11) is the history — the
measured numbers, the four rejected prompt attempts, and the header-row join that
took invoice.png from 3 mismatches to 2. `0001-one-image-at-a-time.md` is older
history still.

Runs live in `debug/runs/<label>/`, newest highest. Each carries the prompt, host,
resolution, the CPU/GPU split and every raw answer that produced it. **Open a run's
`index.html` before changing a prompt** — `tools/inspect_run.py` builds it from a
`--dump` without calling Ollama, and reasoning about the page from coordinates
instead of pixels produced both retracted conclusions in 0001.

One turn of the loop: `DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>`, ~3 min.
`FIXTURE=all` runs all five fixtures — no prompt change has ever been measured
against the other four.

Verify this is still current with `gh issue list --label ready-for-agent`; if #11 is
closed, this section is stale.
