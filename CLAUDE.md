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

**`docs/specs/0001-one-image-at-a-time.md`** — issue #10.

Make `example/invoice.png` convert correctly against a real `qwen3-vl:4b`, ignoring
the other four fixtures for now. The spine works end to end; the model's reading does
not. The spec's "First: establish what is genuinely wrong" section is the live task.

Verify this is still current with `gh issue list --label ready-for-agent`; if #10 is
closed, this section is stale.
