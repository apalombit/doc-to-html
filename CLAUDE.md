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

**`docs/specs/0002-structure-not-geometry.md`** — issue #11.

`example/invoice.png` is at **3 mismatches** against a real `qwen3-vl:4b`, with the
column-sum Probe reconciling at 385.00 and every string read correctly. What is left
is the document's *shape*: a wide two-column table header is either split one row per
column, or mislabelled `pairs` so its cells are read across the row.

`docs/specs/0001-one-image-at-a-time.md` (issue #10) is the history — the measured
numbers, and everything already tried and rejected. Read 0002 for what is wrong now,
0001 for how we got here.

Runs live in `debug/runs/<label>/`, newest highest. Each carries the prompt, host,
resolution and every raw answer that produced it. **Open a run's `index.html` before
changing a prompt** — `tools/inspect_run.py` builds it from a `--dump` without
calling Ollama, and reasoning about the page from coordinates instead of pixels
produced both retracted conclusions in 0001.

One turn of the loop: `DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>`, ~3 min.

Verify this is still current with `gh issue list --label ready-for-agent`; if #11 is
closed, this section is stale.
