# Nothing is missing

**Status: closed — history, not work in flight.** Change 1 shipped as
`DTH_CAPTION_PASS`, on by default. Changes 2 and 3 were superseded by spec
0006; Changes 4 and 5 were retired on 2026-09-18 by spec 0007's Thread 0,
with the harness they were measured against. Issue #28 is closed.
Continues `0004-check-the-box-against-the-ink.md` (issue #20), which ended by
finding that "geometry is broken on four of the five fixtures" and calling that
"a bigger problem than anything this spec set out to address". This is that
problem, measured — and the answer turns out to be that geometry is no longer
where the errors are.

**What changed under this spec since it was written.** The detector is now the
**default** (`DTH_LAYOUT_DETECTOR=heron`), which this spec listed as out of
scope pending a run of the default path for comparison. That run was taken: the
vision path raises `MappingError` on three of the five fixtures and matches none.
`config.DEFAULT_LAYOUT_DETECTOR` carries the table.

**The current baseline is `debug/runs/75-detector-all/`, on the shipped default:
44 mismatches, one full match, all five convert, `covered` 1.00 and `splits` 0
everywhere.** `CLAUDE.md` holds the per-fixture table.

**Do not quote a run number from the body below.** Every figure in this file
predates the current default, most of the runs it names no longer exist on disk,
and several of them differ from each other on more than one flag. The *arguments*
and *mechanisms* are what this file is for. When a number is needed, take a run:
`FIXTURE=all tools/iterate.sh <label>`. The model is not bit-reproducible, so two
runs of one configuration differ by a few mismatches — **a small delta is not a
result.**

---

## What changed under this spec's feet

The VLM layout pass was replaced by a trained ONNX detector, behind
`DTH_LAYOUT_DETECTOR`, default off. That is already built and is the premise of
everything below, not a proposal in it. The one-paragraph version:

At `DTH_LAYOUT_LONG_EDGE=384`, Qwen3-VL's patch-16 encoder with a 2x2 spatial
merge resolves the whole of `invoice_0001` into roughly **12x8 visual tokens** —
a 3px panel border is a tenth of one token — and the coordinates are then decoded
as text with no localization objective anywhere in the loop. That is the
mechanism behind three ignored prompt instructions, a resolution sweep that moved
nothing across 2.25x the linear pixels, and a measured region ceiling that was
read as a target. `engines/detector.py` has the full account.

**Geometry, VLM against detector, same ruler, all five fixtures:**

| | worst `covered` | total `splits` | `invoice_0001` IoU | layout cost |
|---|---|---|---|---|
| VLM (`qwen3-vl:4b`, snapped) | 0.42 | 173 | 0.909 | 187s, once 2498s |
| `heron` + post-passes | **1.00** | **0** | **0.915** | **0.6s, on CPU** |

## Problem Statement

`tools/iterate.sh` with the detector on, all five fixtures, run 69:

| fixture | structure | seconds |
|---|---|---|
| `invoice_0001` | **match** | 186.0 |
| `invoice_0002` | 20 off | 273.0 |
| `sample_css_0004` | 10 off | 151.1 |
| `sample_semantic_0005` | 14 off | 329.6 |
| `sample_table_0003` | 2 off | 155.3 |

`invoice_0002` had never completed a Conversion before run 67. `invoice_0001`
holds at zero mismatches, its column-sum Probe reconciling at 385.00.

**The 46 mismatches share one shape: nothing is ever lost.** Coverage is 1.00 and
`splits` is 0 on every fixture, and there are zero Failures, zero skeletons and
zero rejected steps in the whole run. Every mismatch is content that arrived and
was then **mis-grouped or mis-named**. That is a different failure class from the
VLM's, which dropped content, and it is why the remaining work is small.

### The 46, by root cause

| cause | count | owner |
|---|---|---|
| title reported as `None` | 11 | classify |
| band grouping and count | 14 | layout (*echo*, see below) |
| Kind | 12 | classify |
| Role | 5 | split |
| Zone count | 3 | layout |
| Row Roles | 1 | knock-on of title |

**Half of them — 23 of 46 — are the classifier, not the detector.**

### 1. `zone.title` has never been populated. Not once, on any fixture

**36 classify calls in run 69, 36 empty titles.** Every fixture, every Zone.

It is not a crop problem. `sample_table_0003`'s table Zone spans
`(0.037, 0.119, 0.892, 0.952)` against a reference of
`(0.020, 0.110, 0.980, 0.970)` — the caption is plainly inside the picture the
classifier was shown, and the model returns `""` anyway. The same holds for
`invoice_0002`'s five panels after the heading merge put each `section_header`
inside its Zone: zones 2, 3, 5 and 6 all begin at their heading's top edge, and
all four titles came back `None`.

**One knock-on makes this worth more than eleven.**
`with_grid(prompt, grid, titled=bool(zone.title))` subtracts a row for a titled
table, because a Title is a printed line and not a row. `title` is always `None`,
so **that subtraction has never fired in production**. On `sample_table_0003` the
prompt therefore asked for 17 rows on a 16-row table and got a spurious trailing
`header`. Both of that fixture's two mismatches trace to this one cause, so
fixing titles should take it to a full match.

This is a latent gap the detector work surfaced rather than caused: no fixture
that previously converted end to end had a titled Zone.

### 2. Over-splitting — about seven real errors, reported as seventeen

**Band mismatches are an echo, not a cause.** One extra Zone shifts every Band
index after it, so 14 band lines plus 3 zone-count lines come from roughly seven
grouping decisions. Counting them as 17 independent problems would badly
mis-rank this work.

The seven, by mechanism:

- **`HEADING_GAP` is set too tight.** It ships at 0.05 of page height.
  `sample_css_0004`'s two heading-to-body gaps are **0.058 and 0.065**, and the
  reference has each heading and its body as one Zone — so they should merge and
  do not. The bound was chosen before any Conversion had run, from geometry
  alone, and it was a guess in the wrong direction. Measured properly now:

      merge   0.011 0.024 0.025 0.028 0.029 0.030 0.032 0.038 0.040 0.044 0.058 0.065
      leave   0.081 0.147

  The boundary is between **0.065 and 0.081**.

- **Headings the class list cannot see.** `sample_semantic_0005`'s "TL;DR" is
  labelled `text` by the detector, not `section_header`, so `attach_headings`
  never considers it and the aside arrives as two Zones.

- **Sibling runs.** Three `list_item` boxes stand as three Zones where the
  reference has one list, with gaps of 0.008. Also `text` + `list_item` pairs
  that belong to one prose Zone.

- **One region merged that should not be.** `sample_css_0004` returns the header
  text and the logo as a single box where the reference has two Zones side by
  side in Band 0. This is the only *under*-split in the corpus, and
  `invoice_0002`'s 9-against-10 is the same sign.

### 3. Kind — 12, entirely the classifier

Two patterns, both worth naming:

- **prose <-> list confusion**: four of `sample_semantic_0005`'s five.
- **`invoice_0002`'s panels return `table` where the reference says `pairs`.**
  This answers a question `CLAUDE.md` records as open. Run 50 rewrote the
  `CLASSIFY_PROMPT` pairs clause specifically so a stacked panel could be `pairs`
  again, and noted "Nobody has run `invoice_0002` to check". **This is that
  check, and the rewrite did not work.**

### 4. Role — 5, and the remainder is semantic

The rule "the top Band of a page is its header" cleared `invoice_0001` entirely.
What is left is *"the second Band is also header"* (`invoice_0002` x2,
`sample_css_0004` x1, `sample_semantic_0005` x1) and *"the last Band is footer"*
(`sample_semantic_0005` x1). Neither is recoverable from a Band index. Role is
semantic where the detector's class name runs out, and little rests on it —
`render.py` uses it as a CSS class and the Probes navigate by `RowRole`, one
level down.

## Where this stands, and what to do next

**Change 1 is built and measured. Changes 2-5 are not started.** Run 72 is the
current best: **45 — 0, 20, 10, 15, 0**, two full matches. Runs 69 (flag off, the
baseline), 71 (the failed first attempt) and 72 are gitignored — the numbers here
and in `config.DEFAULT_CAPTION_PASS` are the record; regenerate rather than hunt.

**Next action, and it is the one that moves the number: Change 2.** One constant,
and it is worth roughly 8 of `sample_css_0004`'s 10 — the Zone count, the Band
count, four Band lines, and it unlocks the two Titles Change 1 is already able to
read but never gets asked for. **Settle the contradiction first**:
`engines/detector.py`'s `HEADING_GAP` docstring files `sample_css_0004`'s two
gaps under `leave`, this spec files them under `merge`, and they are the same two
measurements. Re-derive them from source before touching the constant; both
documents now say so.

**Then Change 3**, which is the larger and riskier half of the same problem and
is what `invoice_0002`'s 20 is waiting on. Its captions are already correct — see
Change 1 above — and score as errors purely because the page returns 9 Zones
against a reference of 10, shifting every index after the first.

**Do not spend more effort on Titles.** Change 1's residue is three mismatches,
one of them a genuine miss (`invoice_0001` Zone 1) and two of them correct
answers about boxes the detector grouped wrongly. Both classes are downstream of
grouping.

**`DTH_CAPTION_PASS` stays off** until Changes 2/3 land. It is a net −1 on the
total today, which is not enough to justify moving a default, and the one
condition it fails — `sample_semantic_0005` 14 → 15 — is a grouping artefact that
Change 3 should remove.

## Solution

Five changes, ranked by mismatches-per-unit-of-work. The first is worth more than
the rest combined and is not a layout change.

### Change 1 — make the classifier report a Title (12 mismatches) — BUILT

**The discriminating experiment this section asks for was run, and the ask turned
out to be reachable.** Against run 69's own crops, `qwen3-vl:4b`, temperature 0:

| crop | title, bundled in `CLASSIFY_PROMPT` | title, asked alone |
|---|---|---|
| `sample_table_0003` table | `""` | "Population and GDP (millions of USD)" |
| `invoice_0002` Company Details | `""` | "Company Details" |
| `invoice_0002` Customer Details | `""` | "Customer Details" |
| `invoice_0002` Payment Method | `""` | "Payment Method" |

**4/4 alone, 0/4 bundled.** Not a fifth wording — one question per call.

The wrong Kinds on those panels share the root. Each opens with a **shaded
caption bar**, which satisfies `CLASSIFY_PROMPT`'s own `table` test ("top row set
apart — shaded, ruled off, or in bold"). Adding a clause distinguishing a caption
bar from a heading row changed **0 of 6** answers; cropping the band off moved
`table` → `pairs` on **2 of 3**, both then correct. Removing pixels worked where
wording did not, which is this project's standing lesson stated once more.

So the pass splits in two: `read_caption` sees the whole crop, `classify_zone`
sees it with the caption band withheld. The Extractor keeps the *whole* crop,
because `table_grid` counts the caption as a line and `with_grid(titled=True)`
subtracts it — stripping both would subtract it twice.

**The guard that makes it safe on a cropped Zone is structural, not a judgement.**
`preprocess.caption_band` returns `None` unless something is printed *below* the
first line, so a Zone that is only a heading is never asked and never stripped.
Over run 69's 36 crops that is **20 Zones** — all six of `sample_css_0004`'s and
eight of `sample_semantic_0005`'s. Cost is therefore +16 calls, not +36. Without
it, `sample_css_0004`'s "Card heading" would take its only line as its own Title
and then have the Extractor read the same words again as content.

**No measured numbers in `CAPTION_PROMPT`, against the obvious instinct.**
Following `DTH_TABLE_GRID_HINT` and stating the band's gap would break the
fixture this change is gated on: `sample_table_0003`'s caption sits **19px above
its table against a median line gap of 20px** — no signal at all — while
`invoice_0002`'s panels give 30/33/29 against medians of 10/7/10. One number
cannot carry both, and the model gets `sample_table_0003` right unaided. The band
is measured only to decide whether to ask, and to explain the step in the sheet.

**Control run 70 — `DTH_CAPTION_PASS` off, `invoice_0001`.** Verdict `match`. All
six Kinds identical to run 69 and all six extraction answers **byte-identical**;
the only difference in the whole dump is the absent `"title": ""`. Removing that
clause from `CLASSIFY_PROMPT` changed nothing, which is what licensed removing it
unconditionally rather than behind the flag.

### Change 1, as originally written

The single highest-value fix: one cause, 12 mismatches, a second full match, and
it revives machinery that already exists and is currently dead.

**Diagnose before prescribing.** `CLASSIFY_PROMPT` already asks for it in as many
words — *"a short heading printed at the top of this region and naming the whole
of it, such as a panel caption or a card title"* — and is ignored 36 times out of
36. That is the fourth measured instance of this model ignoring an instruction,
after the two about splitting a table row and the one about panel rows as
regions. **Before writing a fifth wording, check whether the ask is reachable**:
the project's own lesson is that this model complies with *how many* and ignores
*which*, so an instruction that asks it to *decide* differently is reachable and
one that asks it to *perceive* differently is not.

The cheap discriminating experiment is a crop where the title is unambiguous and
alone, asked as its own question. If it answers there and not in place, the
problem is the surrounding task; if it answers nowhere, the field needs a
different mechanism — a separate call, or the detector's own
`section_header` box carried through as the title text rather than re-read.

### Change 2 — retune `HEADING_GAP` from 0.05 to 0.07 (4-6 mismatches)

The data above puts the boundary between 0.065 and 0.081. 0.07 sits in it, with
**1.08x margin below and 1.16x above** — thinner than what shipped, and it must
be recorded as such in the constant's docstring rather than smoothed over. The
false case it must keep rejecting is `sample_table_0003`'s page heading over its
table, measured pre-snap at 0.081.

### Change 3 — reach the two grouping cases the class list misses (~6 mismatches)

- **Sibling runs**: consecutive same-class boxes in one column with sub-leading
  gaps become one Zone. Safe for `list_item` beside `list_item` (gaps 0.008).
- **Headings by shape, not only by class**: a short box directly above a wider
  one, at heading-like proportions, whatever the detector called it.

**This is the riskiest change here and should be gated hardest.**
`sample_semantic_0005` has two adjacent Zones at a 0.029 gap that must *not*
merge, which is inside the range the list-item case needs — so no pure gap
threshold separates them and class agreement has to carry the rule.
`geometry_score._double_count` is the guard: it counts boxes whose contents are
parted by far more whitespace than their own leading, which is precisely
over-merge. `crowded` caught the over-split; `doubles` catches its opposite.

### Change 4 — Kind (12 mismatches, classifier)

Not a layout change and probably not one change. The `pairs`-versus-`table`
question on `invoice_0002` is a live prompt thread with a failed attempt already
recorded; prose-versus-list is new and unstudied. Worth its own spec once
Change 1 has established whether this model's classification answers move to
prompt work at all.

### Change 5 — Role (3 mismatches)

Lowest value, and honestly may not be worth doing. A Zone's Role is a CSS class
and a Probe navigation aid that the Probes do not currently use. Do not invent a
geometric rule for a semantic fact.

## User Stories

1. As a reader of a converted panel, I want its printed caption to appear as the
   Zone's Title, so that the render reproduces the document's own hierarchy.
2. As the table Extractor, I want `titled` to be true when a table has a caption,
   so that `with_grid` states the right row count and no spurious header row is
   invented.
3. As a maintainer, I want a heading and the block it names to arrive as one
   Zone across the gap range the corpus actually contains, so that Band numbering
   is not thrown off by a threshold set from geometry alone.
4. As a maintainer, I want a run of list items to arrive as one list Zone, so
   that a list costs one classification and one extraction rather than three.
5. As a maintainer, I want any merge rule gated on `doubles`, so that fixing an
   over-split cannot silently ship an over-merge.
6. As a maintainer, I want each change measured against all five fixtures end to
   end, because this spec exists because #19 was never done.

## Testing Decisions

**Baseline to beat: `debug/runs/75-detector-all/` — 44 mismatches, one full
match, all five converting**, on the shipped defaults. `CLAUDE.md` holds the
per-fixture table.

**Score a change by re-running `FIXTURE=all tools/iterate.sh <label>` and
comparing the whole vector, not a single fixture** — and take the *before* run
yourself rather than reading one out of a document. If run 75 is no longer on
disk, re-take the baseline first; a change measured against a number nobody can
open has not been measured.

**Change one flag at a time.** Historical runs moved several at once and their
totals describe configurations that were neither the shipped one nor each other.

**A small delta is not a result.** The model is not bit-reproducible: two runs of
one configuration differ by a few mismatches with no code change between them.

**Offline suite baseline: 543 passed / 0 failed.** *Any* failure is a real
regression.

**Geometry is deterministic and that is now verified on real inputs**, not
assumed: runs 68 and 69 produced byte-identical mismatch lists for both shared
fixtures. A geometry change that breaks this has broken something structural.

### Pre-registered gate

Per 0004's lesson that a gate passing every field it names can still ship a
regression, every gate below carries the mandatory condition explicitly.

1. **`invoice_0001` stays a full `match`** — 6 Zones, 4 Bands, Probe 385.00.
   Mandatory for every change in this spec. *No Zone that previously converted
   stops converting.*
2. No fixture's mismatch count rises.
3. `covered` stays 1.00 and `splits` stays 0 on all five. These are what
   distinguish this failure class from the VLM's and they are not negotiable.
4. For Changes 2 and 3 specifically: **`doubles` does not rise on any fixture.**
   An over-merge is invisible to every other field here.
5. For Change 1: `sample_table_0003` reaches a full `match`, since both its
   mismatches share the cause.

## Out of Scope

- Removing the VLM layout pass, or flipping `DTH_LAYOUT_DETECTOR` on by default.
  That needs this spec's changes plus a run of the default path for comparison.
- `doclayout_yolo`. It is kept as a second implementation because that is what
  makes the first one's numbers checkable, not because it is a candidate: it
  merges `invoice_0002`'s two panels into one box, and it is AGPL-3.0.
- Extending `tools/fixture_geometry.py` to the other four fixtures (#19). The
  bakeoff did not need it — `covered`, `crowded` and `splits` come from the ink —
  but any claim about `iou` on those four still does.
- The region ceiling (`DTH_LAYOUT_REGION_HINT`), which stays dormant.
- Nesting the IR. Both the containment merge and the split produce a tree
  naturally; consuming it is its own change.

## Further Notes

**Four things that would otherwise be re-derived the hard way.**

- **`covered` counts ink claimed by *exactly one* box, not at least one.** It
  therefore falls for two opposite reasons — content missed, and content claimed
  twice — and a single number cannot say which. `tools/detector_probe.py` reports
  `crowded` beside it for that reason, and the decomposition is what showed that
  both detectors' apparent coverage failure was **entirely nesting and never a
  miss**. Without it the raw bakeoff reads as "both candidates lose".

- **`doubles` does not measure overlap.** It counts a box whose contents are
  parted by far more whitespace than its own leading — a box that *swallowed* two
  regions. It is a merge detector, and it was mis-described as an overlap
  detector in this work's own plan.

- **The split was never missing; `outermost` discarded it.** On `invoice_0001`
  heron reports `table` at 0.95 over both printed tables *and* reports each of
  them separately, at 0.22 and 0.32. Recovered, those parts score IoU 0.860 and
  0.784 against the reference where the merged box scores 0.245. **A detector's
  sub-threshold proposals are already computed** — inference runs once and
  confidence is a filter over its result — so looking below the threshold costs
  arithmetic and no second forward pass.

- **A diagnostic that cannot run must be audible.** Run 69 converted all five
  fixtures and produced **no contact sheet for any of them**:
  `tools/inspect_run.py` required `00_layout.json`, a detector run issues no
  layout call and writes none, and `iterate.sh` sent the explanation to
  `/dev/null`. The geometry it needed was in `zones_used.json` the whole time.
  Both are fixed — the guard accepts either, and the run script keeps stderr and
  warns — but the shape of the failure is the lesson: a silent `|| true` around a
  reporting tool turns a one-line fix into a run that looks like it worked.

**Two constants shipped on thin evidence, and neither should be defended without
re-measuring.** `HEADING_GAP` has ~1.1x margin either side even after Change 2.
`attach_trailing_rows` — which restored `invoice_0001`'s Probe by folding the
total row back into the line-item table — rests on **one** positive example
corpus-wide, against one negative. Both are documented as such in
`engines/detector.py`.
