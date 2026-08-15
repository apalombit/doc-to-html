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

**`example/invoice.png` (`invoice_0001`) converts with 0 mismatches.** Run 49,
`debug/runs/49-table-grid-hint/`. Every string on the page reaches the render, no
Zone renders as a skeleton, no Failures, no Caveats, and the column-sum Probe
reconciles at 385.00.

| | run 43 | 46 | 47 | 48 | **49** |
|---|---|---|---|---|---|
| mismatches | 3 | 1 | 1 | 1 | **0** |
| Kinds correct | 4/6 | 4/6 | 6/6 | 6/6 | **6/6** |
| strings rendered | 13/25 | 25/25 | 25/25 | 25/25 | **25/25** |
| skeletons / failures | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |
| geometry IoU / covered / splits | 0.56 / 0.82 / 46 | 0.91 / 0.99 / 0 | — | — | 0.91 / 0.99 / 0 |

**Read `docs/specs/0003` for the measurements.** What follows is the state and
the lessons, not the history.

### What got it there — five changes, each measured

1. **`DTH_SNAP_ZONES`** — move each Zone's box onto its own ink. Geometry 0.56 ->
   0.91 IoU. It fixes **no** Kind (twelve classifications identical across two
   snapped runs) and on its own it once *cost* the line-item table. Default
   **on**: changes 2 and 5 removed that cost, and run 49 was taken with it set.
2. **Zero-cell rows dropped** before the table width check. That check exists
   because a row with the wrong number of cells shifts values into wrong columns;
   a row with *none* has nothing to shift. Runs 39 and 45 both lost the whole
   table and the Probe to one such row.
3. **`NotPairs` re-routes to prose.** The Pairs Extractor's "this region was not
   Pairs" is a diagnosis, not a complaint, and nothing acted on it. Now
   `_reread_as_prose` does.
4. **`CLASSIFY_PROMPT` makes typesetting decisive** rather than an aside. Three
   experiments proved the *heading's words* were deciding `table` vs `pairs`
   — 12/12 under a crossover with the layout held pixel-identical.
5. **`DTH_TABLE_GRID_HINT`** — measure the table crop and state its grid in the
   prompt ("this region holds 2 rows and 2 columns"). Default **on**. This is
   what closed the last gap.

Changes 2 and 3 are now dormant safety nets: run 49 needed neither. **Do not
delete them on one run** — four runs established the behaviour each guards.

### The lesson that generalises

**Two prompt attempts to stop the model splitting a wide table row failed. A
count worked.** Runs 13 and 48 both issued *behavioural* instructions — do not
split a printed row — and run 48's answers were **byte-identical** to the run
before it. The model is not deciding to split; it does not read the two ends of
an 800px-wide row as one line, so an instruction has nothing to act on.

The asymmetry was in the data all along: the prompt has always said "give every
data row the same number of cells as the header row" and the model has always
obeyed *that* exactly. **It complies with how many, and ignores which line.**
When an instruction is being ignored, check whether it is asking the model to
decide differently or to perceive differently — only the first is reachable.

### Runs explain themselves now

`src/doc_to_html/trace.py` records every step of a Conversion — model calls *and*
decisions — each with a required `disposition` saying what became of its answer.
`tools/inspect_run.py` renders it as the pipeline in execution order:
GIVEN / ASKED / ANSWERED / HANDLED / RESULT per step, with the crop inline and
prompts collapsed. **Open `debug/runs/<label>/index.html` and read top to bottom.**

Before this, run 46's sheet showed 1 prompt and 6 answers out of 14 calls — and
those 6 were the classification verdicts, under a heading reading "What each crop
returned". `trace.json` is in the dump for programmatic use. Dumps without one
fall back and label themselves as reconstructed.

### What is open, honestly

- **The suite is red: 49 failures.** Replay serves recorded responses by order,
  and classification added a call per Zone, so every fixture's classify call eats
  what was recorded as its extraction answer. Expected, tracked as **#16**, and
  the only correct place to fix it. 393 pass. *Any count other than 49/393 is a
  real regression.*
- **Four fixtures are unmeasured** against every change above (**#19**).
  `invoice_0002` returns no geometry at all — both repeats died with
  `ThinkingNotDisabled` despite `think=False` being sent.
- **The new `CLASSIFY_PROMPT` regresses `invoice_0002`**, turning its two panel
  Zones from `pairs` to `table`: those panels stack label above value and the new
  rule wants them on one line. Shipped as the default on one fixture's evidence,
  deliberately.

### Three things that would otherwise be re-derived the hard way

- **Do not read a geometry IoU for any fixture except `invoice_0001`** without
  first deriving its rectangles from source, as `tools/fixture_geometry.py` does.
  The typed boxes are 0.605-0.854 against their own ink.
- **Do not gate a geometry change on geometry fields alone.** Gate 1 in spec 0004
  was pre-registered, passed every field it named, and shipped a regression that
  cost a Zone and a Probe. Any such gate must include *no Zone that previously
  converted stops converting*.
- **A Zone's Title is a band of ink that is not a row.** `table_grid` counts
  printed lines, so a titled table measures one row too many — `sample_table_0003`
  gives 17 against a true 16. `with_grid` subtracts. Both numbers were right;
  they counted different things.

### The loop

`DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>` — one document, ~4 min on a
whole GPU and much longer when Ollama puts the model partly on CPU, which it
reports in `ollama_ps_after.txt`. `FIXTURE=all` runs all five. Runs live in
`debug/runs/<label>/`, which is **gitignored** — regenerate rather than hunt.
Nothing in the suite reads a run directory.
