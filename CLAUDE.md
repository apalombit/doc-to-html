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

**All five fixtures convert. Two are full matches.** Best measurement is run 72,
`DTH_LAYOUT_DETECTOR=heron DTH_CAPTION_PASS=1 FIXTURE=all`:

| | `invoice_0001` | `invoice_0002` | `sample_css_0004` | `sample_semantic_0005` | `sample_table_0003` | total |
|---|---|---|---|---|---|---|
| run 69 — flag off, the baseline | **0, match** | 20 | 10 | 14 | 2 | 46 |
| **run 72 — caption pass on** | **0, match** | 20 | 10 | 15 | **0, match** | **45** |

`invoice_0001` renders every string, no skeletons, no Failures, no Caveats, and
its column-sum Probe reconciles at 385.00. Geometry is the same in both runs:
`covered` 1.00, `splits` 0, `doubles` 0/3/0/1/0.

**The remaining 45 are dominated by Zone grouping, not by reading.** Nothing is
lost on any fixture — every mismatch is content that arrived and was mis-grouped
or mis-named. `invoice_0002` cannot fall below 20 while it returns 9 Zones
against a reference of 10, and `sample_css_0004` cannot gain a Title while each
heading stands as its own Zone.

**Read `docs/specs/0005` first — it has the current numbers and the ranked
work.** `docs/specs/0003` is history: treat runs before 50 as superseded and do
not cite them as evidence.

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

- **The suite is green: 537 pass, 0 fail.** *Any failure is a real regression.*
  Issue **#16** is fixed: `ReplayTransport` holds one queue per `pass_name`
  instead of one flat list, so a pass added in front of extraction no longer
  eats the answers recorded for it. That was the whole of the 49 red tests. Four
  of them were not the ordering at all and are worth knowing about, because each
  had been masked by it:
  - `test_a_table_is_read_from_a_crop_and_not_from_the_page` derived its expected
    crop from the *typed* fixture box, but `DTH_SNAP_ZONES` ships on and the
    Extractor sees the snapped box.
  - two failure-contract tests picked payloads that are no longer failures — an
    unlabelled pair is now a `NotPairs` *diagnosis* and gets re-read as prose,
    and an empty `pairs` answer is allowed for a Zone carrying a Title.
  - `test_a_bulleted_list_becomes_a_real_list` counted `<ul>` across the whole
    page, which also counts the findings block.
- **All five fixtures are measured** (**#19**), by runs 67-72 with
  `DTH_LAYOUT_DETECTOR=heron`. `invoice_0002` converts — the VLM layout pass was
  what could not produce geometry for it. Best vector, run 72 with
  `DTH_CAPTION_PASS=1`: **45 — 0, 20, 10, 15, 0**, two full matches. Run 69's 46
  — 0, 20, 10, 14, 2 is the flag-off baseline. See `docs/specs/0005`.
- **`DTH_CAPTION_PASS` works and still ships off.** It reads each Zone's Title in
  its own call, then withholds the caption band from the Kind question. It took
  `sample_table_0003` to a full match — the Title revives `with_grid(titled=)`,
  dead in production until then — and fixed three `invoice_0002` Kinds. It stays
  off because it cannot yet lower the total: the remaining errors are Zone
  grouping, not titles.
- **The `invoice_0002` panel question is answered, and the run 50 rewrite did not
  work.** Run 50 dropped the *same-line* half of the `pairs` clause so a stacked
  panel could be `pairs` again, and recorded that nobody had checked. Run 69
  checked: the panels still came back `table`. The cause is not that clause —
  each panel opens with a **shaded caption bar**, which satisfies the `table`
  entry's own "top row set apart" test. Withholding the bar fixes it; a prompt
  clause explaining the difference moved 0 of 6.
- **Titles are correct on more Zones than the score shows.** `invoice_0002`'s
  panels and `sample_semantic_0005`'s two headings return the right caption for
  the box they were given, and score as mismatches because the detector groups
  those boxes differently from the reference. Do not chase them as title bugs.

### The lesson run 71 cost, and it is not about captions

**When a model answers a closed question the same way every time, check whether
the schema can express the true answer before rewording the question.**
`CaptionResponse` first asked a boolean — is this line a heading? — and got
`true` on **8 of 8** crops. It was not being ignored. That prompt's test for a
heading was word for word `CLASSIFY_PROMPT`'s test for a table's top row, so a
heading row satisfied both and there was no other answer available. Run 71 cut
two heading rows off `invoice_0001`, costing a Kind, a summary row and the 385.00
Probe. Offering a third value — `caption` / `header` / `content` — took the same
model from 4/11 to 8/11 with no change to the reasoning asked of it.

`header` and `content` do exactly the same thing in the pipeline. The distinction
exists only so the model has somewhere to put the answer; **do not collapse the
enum back to a boolean.**

### Four things that would otherwise be re-derived the hard way

- **A prompt rule that bundles two tests will be credited with the wrong one.**
  `pairs` required the label "on the same line as the value it names" — a
  geometric test and a semantic one in one sentence. Spec 0003 credits the whole
  clause with fixing Zone 3, so it read as untouchable; in fact only the semantic
  half was doing that, and the geometric half was the sole cause of the
  `invoice_0002` panel regression. Run 50 dropped the geometric half and every
  one of the 13 answers stayed **byte-identical**. Before defending a clause,
  check whether it is one rule or two wearing one sentence.
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
