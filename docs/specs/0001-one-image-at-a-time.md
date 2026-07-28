# Make one image work: `example/invoice.png`

**Status:** open. Tracked as GitHub issue #10.

## Why this exists

Issue #1's slice is built and its nine children are closed. Everything below the
model is tested and green — 278 tests, offline, no Ollama. What was never tested is
the only thing a model does: read a page.

The first real runs found four faults in the harness (fixed, see `c659986`) and one
in the pipeline (the layout budget, see below). `invoice_0001` now runs all eight
passes end to end against `qwen3-vl:4b` without aborting. It does not yet produce a
correct IR.

**This ticket narrows to one image until that image is right.** Chasing five
documents across three models at ~5 minutes a run spends attention faster than it
buys evidence.

## Scope

- **`example/invoice.png` only.** The other four fixtures stay in the suite as
  regression cover and are otherwise ignored.
- **`qwen3-vl:4b` only** as the working model. `qwen3-vl:2b` is a comparison at the
  end, not during iteration — it truncated mid-string and is a second variable.
- Success is `acceptance.compare()` returning no mismatches for `invoice_0001`.

## What is measured, not assumed

All on an 8 GB M1, nothing else resident, `DTH_LAYOUT_LONG_EDGE=512`:

| | |
|---|---|
| Whole document, 8 passes | **322.9s** |
| Layout pass | 85.2s |
| Table pass (×2) | 42.2s mean |
| Prose pass (×4) | 31.9s mean |
| Pairs pass (×1) | 25.5s |
| Resident | 2743 MB |

Two facts about the environment that invalidate measurements if ignored:

- **Memory presents as latency.** With an unrelated `llama3.2:3b` resident, one
  layout pass took 180s and timed out; alone, 4.5s. Run `ollama ps` first, always.
- **The answer arrives on `message.thinking`, not `message.content`,** for
  `qwen3-vl`. Handled in `transport.py`; do not "fix" it back.

## The diagnosis

The layout pass returns **schematic geometry**: plausible-looking boxes that
partition the page rather than locate its content. Actual output for `invoice.png`:

```
0 prose   header b0c0 (0.00, 0.00, 1.00, 0.25)   full width — encloses zone 1
1 pairs   header b0c1 (0.75, 0.00, 1.00, 0.25)
2 prose   body   b1c0 (0.00, 0.25, 0.75, 0.45)
3 prose   body   b1c1 (0.75, 0.25, 1.00, 0.45)
4 table   body   b2c0 (0.00, 0.45, 1.00, 0.65)
5 table   body   b3c0 (0.00, 0.65, 1.00, 0.85)
6 prose   footer b4c0 (0.00, 0.85, 1.00, 1.00)   nothing is printed here
```

Every coordinate is on a 0.05 grid; the strips tile the page top to bottom. The
consequences are all downstream of this:

- Zone 0 is labelled `prose` because the strip contains the logo *and* the invoice
  details. Expected: a `figure` with `graphic=logo`.
- Zone 6 is the severed bottom third of the line-items table, relabelled
  `prose`/`footer`. This is what makes Zone count 7 against an expected 6, and Band
  count 5 against 4.
- Extraction crops therefore cover the wrong pixels, which is why the line-items
  table came back with a duplicated header row and one row of zero cells, failing
  the width check and so producing no Probe.

**Correction, 2026-07-28.** This section previously said Zone 6 was "invented" and
that "nothing is printed here". That is false, and it was false when written. The
crop that region sent to the model contains `Domain name (1 year)  $10.00` and
`Total: $385.00`, and `07_prose.json` returned exactly those. Reference Zone 5 runs
0.63–0.95; the model returned 0.65–0.85 and cut the table **through the middle of a
row**. The error was reached by reasoning about normalised rectangles instead of
looking at the pixels they name — which is what `tools/inspect_run.py` now exists to
prevent.

**The mapper cannot currently catch this.** Tiling strips satisfy every
plausibility rule it has: Bands descend the page, columns run left to right, and
same-Band Zones overlap vertically. This is the "schema-valid nonsense" failure
mode issue #1 anticipated, arriving in a form the checks do not cover.

## First: establish what is genuinely wrong (the current task)

**Directive, 2026-07-28.** The spine working end to end is an acceptable place to be
and slowness is accepted for now. Before any prompt or geometry is changed,
establish which reported mismatches are real defects in the generated document and
which are artefacts of how `compare()` counts. Do not fix anything until that is
settled.

### What the first analysis found

`compare()` reported **6 mismatches** for `invoice_0001` against `qwen3-vl:4b`. They
trace to **4 independent root causes**, so the count overstates the damage:

| Root cause | Reported as |
|---|---|
| **(a)** Zone 0's box `(0,0,1,0.25)` encloses Zone 1 rather than locating the logo | `zone 0: kind expected figure, got prose` |
| **(b)** Zone 6 `(0,0.85,1,1)` is invented — best overlap with any real region is IoU 0.26, against a *table* | `Zone count 7 vs 6`, `Band count 5 vs 4` |
| **(c)** The payment table's header row is read twice | `zone 4: Row Roles ['header','data'] -> ['header','header','data']` |
| **(d)** The line-items table returns a row of 0 cells, so the whole Zone is rejected | `zone 5: Row Roles [...] -> []`, `Probe results [...] -> []` |

**Superseded, 2026-07-28, after looking at the crops.** There are not four
independent root causes. There is **one**, and each of the four is a crop-boundary
artefact of it: the layout pass partitions the page on a fixed grid, so every Zone
edge falls where the grid says rather than where the content ends.

| Was | What the crop shows |
|---|---|
| (a) logo read as prose | `got 0` spans the full width, taking the logo *and* the invoice details, and enclosing `got 1` |
| (b) "invented" Zone 6 | the line-items table cut at 0.85, mid-row. A **split**, not an invention |
| (c) header read twice | `got 4` is 0.45–0.65 against a reference of 0.48–0.60; the crop bleeds the *next* table's `Item \| Price` header into its bottom edge |
| (d) zero-cell row | `got 5`'s bottom edge clips the `Domain name` row in half; the model emitted an empty row for what it could not read |

Fixing the grid is therefore one change, not four. Read
`debug/runs/01-baseline-stripes/index.html` before disagreeing with this.

### Two weaknesses in the measurement itself

**`compare()` aligns Zones by list index.** Inserting a single spurious Zone into an
otherwise *perfect* document produces **13 mismatches**. Segmentation differences
cascade through every subsequent index, so mismatch count is not a measure of how
wrong a document is, and two runs cannot be ranked by it. This run escaped the
cascade by luck: the model's Zones 0–5 happened to stay index-aligned with the
reference.

This is fine for the acceptance harness, whose only question is "zero or not". It is
useless for iterating, which needs to know whether a change made things better.

**There is no geometric measure at all.** IoU against the reference boxes, which
`compare()` never computes:

```
model 0 prose -> ref 0 figure  IoU=0.16      model 4 table -> ref 4 table  IoU=0.56
model 1 pairs -> ref 1 pairs   IoU=0.40      model 5 table -> ref 5 table  IoU=0.60
model 2 prose -> ref 2 prose   IoU=0.29      model 6 prose -> matches nothing (0.26)
model 3 prose -> ref 3 prose   IoU=0.54
```

Only 2 of 7 boxes exceed 0.5. That is the schematic-tiling problem as a number, and
it is a *continuous* signal — exactly what iterating needs and what a pass/fail
count cannot give.

**But IoU alone is the measure that produced the error above.** `model 6 -> matches
nothing (0.26)` is arithmetically right and is precisely what led to "Zone 6 is
invented". Best-overlap matching **cannot represent a split**: when one reference
Zone becomes two model Zones, the second scores low against everything, and any
match-or-spurious rule files it under spurious. Automating this step as originally
written would have automated the mistake.

What distinguishes the two is *asymmetric coverage* — how much of a box sits inside
a reference Zone, and how much of a reference Zone any single box accounts for.
`tools/inspect_run.py` reports both, and it is the second that names the fault:

```
want 5 (table/body) is only 62% covered by any single model box
```

### Next steps, in order

1. ~~Align Zones by geometry, not index, for diagnosis.~~ **Done, and narrowed.**
   `tools/inspect_run.py` reports per-box IoU *and* asymmetric coverage. Coverage is
   the load-bearing half; IoU alone misleads, as above. `compare()` is untouched and
   stays index-aligned for acceptance, whose only question is "zero or not".
2. **Look at the pixels before reasoning about the numbers.**
   `tools/inspect_run.py` turns a `--dump` into a contact sheet: the page as the
   model saw it, the boxes drawn on it, and every crop beside the text it returned.
   It reads the dump and never calls Ollama, so the five-minute run is paid once.
3. **Fix the prompt, which is what causes the grid.** See below.

The horizontal-disjointness check is now redundant as a *diagnostic* — the contact
sheet shows Zone 0 enclosing Zone 1 at a glance — but still worth having in
`wire._validate_bands` as a *guard*, so this class of answer fails by name instead
of rendering confidently wrong.

## The prompt asks for the grid it gets

`LAYOUT_PROMPT` in `engines/ollama.py`. Three things in it produced the tiling, and
all three were rewritten on 2026-07-28:

1. **"Divide the page into top-level regions"** — *divide* is partition language:
   exhaustive, non-overlapping, covering everything. Now "find the regions of
   content printed on this page", with an explicit paragraph saying regions need not
   cover the page and that blank paper belongs to no region.
2. **"number the horizontal stripes of the page from 0 at the top"** — the prompt
   used the word *stripes* for what Band means, and stripes are exactly what came
   back. Band is a *grouping* of regions; it is now described as one, with "they are
   not stripes of the page, they need not be the same height, and they need not
   touch one another".
3. **Nothing asked for a tight box.** The old text said only "the region's bounding
   box as fractions of the page". Now: the smallest rectangle containing everything
   printed in the region, measured against the ink rather than a grid, plus two
   rules — no edge may cut through a line of text or a table row, and no region may
   contain or overlap another.

The model was doing what it was told. That is the finding.

## Runs

Every turn is a whole document from scratch against a real `qwen3-vl:4b`, nothing
else resident. `tools/iterate.sh <label>` does one, and refuses to start if
`ollama ps` is not empty. Each turn's directory carries the prompt that produced
it, so the two can be compared without a git archaeology session.

| Run | Change | Mismatches | Mean IoU | Total | Directory |
|---|---|---|---|---|---|
| 01 | "divide the page", "stripes", no tightness rule | 6 | 0.40 | 322.9s | `debug/runs/01-baseline-stripes/` |
| 02 | all three rewritten | 8 | 0.27 | 290.6s | `debug/runs/02-tight-boxes/` |
| 03 | + horizontal-overlap guard, + "two grids are two regions" | aborted | **0.47** | 69.8s | `debug/runs/03-guard-and-table-split/` |
| 04 | + `graphic` closed to a Literal | aborted | 0.44 | 88.3s | `debug/runs/04-graphic-enum/` |
| 05 | + "columns inside a region are not regions", + heading-row test for `table` | 5 | 0.53 | 192.7s | `debug/runs/05-columns-are-not-regions/` |
| 06 | `DTH_LAYOUT_LONG_EDGE=384` | **3** | **0.56** | 251.6s | `debug/runs/06-sweep-384/` |
| 06 | `DTH_LAYOUT_LONG_EDGE=768` | 8 | 0.33 | 243.5s | `debug/runs/06-sweep-768/` |
| 06 | `DTH_LAYOUT_LONG_EDGE=862` (native, no downscale) | 5 | 0.53 | 194.5s | `debug/runs/06-sweep-862/` |
| 07 | Cloud probe, `gemma4:31b` + `minimax-m3` | n/a | n/a | n/a | `debug/cloud/` |
| 08 | `minimax-m3` via Ollama Cloud, whole pipeline | 9 | 0.26 | 81.2s | `debug/runs/08-cloud-minimax-m3/` |
| 09 | + asymmetric crop pad, `PAD_X=0.03` | 5 | 0.56 | 172.8s | `debug/runs/09-crop-pad/` |
| 10 | + "a horizontal rule is not a row" | **3** | **0.56** | 176.0s | `debug/runs/10-no-rule-rows/` |

### Run 02 — the three prompt rewrites. Aimed correctly, not yet a win.

**Both headline numbers got worse and the change was still right.** Mismatch count
is not a measure of how wrong a document is (see above), and mean IoU falls when
boxes become *too small* just as it does when they sprawl. What the pictures show:

Fixed, and these are the things the run was aimed at:

- **No grid.** Coordinates are no longer snapped to 0.05 and no longer tile.
- **Nothing invented.** The page is no longer covered edge to edge; the spurious
  footer Zone is gone.
- **No edge cuts a table row.** The line-items table arrives whole, and for the
  first time the model returned a `summary` row — `Total: $385.0` — so a
  column-sum Probe *runs*. It failed, but it exists, which it never did before.

Broken, and all of it newly visible because the grid stopped hiding it:

- **Two Zones are byte-identical.** `got 4` and `got 5` are both
  `pairs/body (0.05,0.38,0.94,0.46)`, band 2, columns 0 and 1, and returned
  identical content. The prompt says "no two regions may overlap" in as many
  words. Saying it is not enough — this needs the guard in `wire._validate_bands`.
- **The two tables merged.** `got 6` spans 0.48–0.92, covering the payment table
  *and* the line items as one region. This is why the Probe fails: the payment
  table's `100` joins the price column, and 100+300+75+10 = 485, not 385.
- **Boxes are too short, and the middle band sits too high.** `got 2` and `got 3`
  are 0.20–0.34 against a reference of 0.27–0.41 — placed over the whitespace
  *above* the addresses. `got 0` is 0.10–0.14 for a wordmark spanning 0.06–0.17.
  Coverage tells this apart from the old failure: `got 0` is 100% inside its
  reference Zone, where the baseline's was 16%. Right neighbourhood, wrong size.
- **Digit truncation, and it is not a layout fault.** `$300.00` came back as
  `$300.0`, `$75.00` as `$75.0`, `1000` as `100`. The extraction prompt did not
  change; the crop it is given did, from a half-table to a 29KB whole one. Watch
  whether this follows crop size — if it does, it is an argument for the slicing
  that `preprocess.slice_points` already plans and nothing yet uses.

**Cost:** 290.6s against 322.9s. The layout pass got *slower* — 115.8s against
85.2s, on 1524 characters of reasoning — while every extraction pass got faster on
tighter crops.

### Run 03 — the best layout so far, stopped by a field typed `str`

Two changes: `_overlaps_horizontally` in `wire._validate_bands`, and one sentence
telling the prompt that two stacked grids each with a heading row are two regions.

The layout is the best yet on every measure that matters:

- **Six Zones, which is the expected count.** No duplicates — the guard's target
  disappeared without the guard having to fire.
- **Zone 0 came back as `figure`.** First time. Runs 01 and 02 both read the
  wordmark as prose.
- **The two tables separated**, into `got 4` (0.41–0.53) and `got 5` (0.54–0.87).
  One sentence did that.
- **Mean IoU 0.47**, against 0.40 for the baseline and 0.27 for run 02.
- **69.8s for the layout pass**, the fastest of the three.

And it aborted before extracting anything:

```
MappingError: zone 0 (figure, band 0 column 0):
  graphic 'SPARKSUIT' is not one of ('logo', 'chart', 'signature', 'stamp', 'badge')
```

**`WireZone.graphic` was typed `str`.** `kind` and `role` are `Literal[...]`, so
constrained decoding makes an invalid value *impossible* for them; `graphic` named
its five allowed values only in the field description, so the model was free to
answer with what it had just read off the logo. Now
`Literal["", "logo", "chart", "signature", "stamp", "badge"]`. The runtime check in
`zones_from_layout` stays, for an Engine that cannot constrain, and has its own
test reaching it through `model_construct`.

The same sweep found **`band`'s schema description still said "Horizontal stripe"**
— a fourth place the model was told the word, missed because only the prompt was
searched. Constrained-decoding schemas are prompt surface too.

Still wrong at the end of run 03, and the list for next time:

- **Everything in the lower half sits about 0.06 too high.** `got 4` is 0.41–0.53
  against a reference of 0.48–0.60; `got 5` is 0.54–0.87 against 0.63–0.95. The
  boxes are the right shape in the right order, translated upward.
- `got 1` is `prose` where the invoice details are `pairs`.
- `got 4` is `pairs` where the payment table is a `table`.

### Run 04 — the same prompt, a different answer. One run proves nothing.

Runs 03 and 04 put the *same* layout prompt to the same model. Run 03 returned six
Zones and no duplicate. Run 04 returned seven, with `got 4` and `got 5` both
`pairs/body (0.05,0.41,0.94,0.53)` under columns 0 and 1 — the run 02 fault,
returned.

**Run 03's correct Zone count was partly luck**, and this is the most useful thing
either run produced. A single conversion is not evidence that a prompt change
worked, and this file's earlier entries should be read with that in mind. Anything
claimed on one run needs a second before it goes in the "fixed" column.

The guard did its job — a named failure rather than a document rendered
confidently wrong:

```
MappingError: band 2: Zones in columns 0 and 1 overlap horizontally
  (0.05-0.94 and 0.05-0.94) — Zones side by side cannot share horizontal space,
  and one enclosing the other is not two Zones
```

**The duplicate has a shape.** Both copies cover the payment table, and both are
`pairs`. The model appears to be reporting that region *once per column it
contains* — applying Band and column, which describe how Zones sit beside each
other, to the columns inside a single Zone. Two changes for run 05, both aimed at
that reading:

- The prompt now says the columns inside a table or pairs region are not regions,
  that two regions in a band always have different boxes, and that two regions
  about to share a box are one region.
- `table` is now "a grid of rows and columns **under a heading row** … a grid with
  a heading row is a table even if only one row of values follows it", and `pairs`
  is "label and value lines **with no heading row**". The payment block has a
  `Payment Method | Check #` heading and one data row, and was being read as pairs
  on the strength of its shortness.

### Run 05 — the Probe reconciles from a real reading

**`[('column-sum', True, '385.0')]`.** The first time a real model's reading of
this page has produced arithmetic that checks out. Also the first complete
conversion since the prompt work started: six Zones, no duplicates, all seven
passes, 192.7s against the baseline's 322.9s, mean IoU 0.53 — the best of the five
runs. The `figure` pass ran for the first time and returned `graphic: "logo"`.

Five mismatches remain, and **four of them are one cause**:

```
zone 1: kind expected pairs, got prose
zone 4: kind expected table, got pairs
zone 5: Row Roles [header, data, data, data, summary]
             -> [header, header, data, data, data, summary]
zone 4: extraction MappingError: pairs Zone entry 1 has no label, only 'Check'
document: Probe results ('column-sum', True, '385.00') -> ('column-sum', True, '385.0')
```

**The vertical offset is now the whole story.** Every box sits high, and the error
grows down the page: `got 2` is 0.24–0.39 against 0.27–0.41 (0.03), `got 5` is
0.58–0.92 against 0.63–0.95 (0.04), `got 4` is 0.41–0.56 against 0.48–0.60 (0.06).
Follow what that does:

- `got 4`'s bottom edge lands above the payment table's only data row, so the crop
  holds a heading and nothing else — which is why it is classified `pairs`, and why
  the Pairs extractor then rejected it with `entry 1 has no label, only 'Check'`.
  Two of the five findings, from one edge in the wrong place.
- `got 5`'s top edge starts above the line-items heading, catching the tail of
  `Check`, which becomes the spurious second `header` row.

So `zone 4: kind`, `zone 5: Row Roles` and the `zone 4` extraction failure are all
the same 0.05 of page. **Do not treat them as three problems.**

The Pairs extractor rejecting a Zone the layout pass called Pairs is worth noting on
its own: a check written for one purpose caught a misclassification upstream of it,
by name, instead of emitting plausible nonsense.

**One trailing character is dropped from every value.** `$300.00` → `$300.0`,
`$75.00` → `$75.0`, `1000` → `100`, `Total: $385.00` → `Total: $385.0`. Consistent,
and it is the *last* character every time rather than a misread digit.

**Solved in run 07, and it was none of the things suspected here.** The guess
recorded above — "suspect the truncation retry in `engines/ollama.py` before
suspecting the model's eyesight" — was wrong, and so was the follow-up guess that a
second model family would exonerate our code. The crop is **clipping the last
character off the image**. Zone boxes come back with `right=0.94` while the
right-aligned prices run to about 0.97, and `preprocess.crop`'s 0.01 pad is 8.6px
on an 862px page — narrower than the character it needs to rescue. Every model read
the crop correctly; the crop was short. See below.

### Run 06 — the layout resolution sweep. More pixels bought worse localisation.

Four resolutions, same prompt, same model, each cold. The question from the
"cheapest first" list was whether more pixels buys real localisation or just more
tokens. **It buys neither reliably, and the best result came from the smallest
input.**

| Long edge | Mismatches | Mean IoU | Layout | Notes |
|---|---|---|---|---|
| **384** | **3** | **0.56** | 112.5s | Best. Row Roles correct, no extraction failure |
| 512 | 5 | 0.53 | 66.0s | Run 05 |
| 768 | 8 | 0.33 | 92.2s | Worst. Eight Zones, no Probe at all |
| 862 (native) | 5 | 0.53 | 71.6s | Indistinguishable from 512 |

At 384 the vertical offset largely disappears. `got 5` is 0.64–0.92 against a
reference of 0.63–0.95 — IoU 0.83 and 100% covered, the best any box has scored.
`got 4` reaches 0.63 and finally contains the payment table's data row, which
removes both the spurious `header` in Zone 5's Row Roles *and* the Pairs
extractor's rejection. Three findings gone from one edge landing in the right
place, exactly as run 05 predicted they would.

Three mismatches remain, and none is geometric:

```
zone 1: kind expected pairs, got prose      the invoice details
zone 4: kind expected table, got pairs      the payment table
document: Probe ('column-sum', True, '385.00') -> ('column-sum', True, '385.0')
```

**Do not read "smaller is better" as settled.** The relationship is not monotonic —
768 is worse than both its neighbours, and 862 is indistinguishable from 512 — and
runs 03 and 04 already showed this model answering the same prompt two ways. What
*is* striking is that Zones 0–3 come back with byte-identical coordinates at every
resolution and in every run since 03. The variance is confined to the lower half of
the page. Before 384 becomes the default, repeat it: one run is not evidence, and
this file has already recorded one conclusion that a second run overturned.

### Run 07 — two cloud models, and the truncation solved by looking at a crop

Ollama Cloud, `tools/cloud_probe.py`, raw answers in `debug/cloud/`. Not wired into
the pipeline: **no cloud vision model honours `format`.** `gemma4:31b` returns its
own `box_2d` detection format regardless of the schema given, and `minimax-m3`
returns markdown-fenced JSON as a bare array. Making a Conversion accept either
means loosening the shared mapper to tolerate fences and top-level arrays, and
constrained decoding making malformed JSON impossible is load-bearing here. So the
questions were asked directly and normalised in the script; `wire.py` is untouched.

Access, for the record: `qwen3.5:397b` and `kimi-k3` answer **403, "requires a
subscription"**. The first is the one worth having — same family as the local
`qwen3-vl:4b` at roughly a hundred times the parameters, which would separate
capacity from prompt inside one lineage instead of across two.

**The trailing-character truncation is ours, and it is the crop.** Both cloud
models, asked for the same line-items crop, returned exactly what `qwen3-vl:4b`
returns: `$300.0`, `$75.0`, `$10.0`, `Total: $385.0`. `minimax-m3` also returned
the header as `Pric`. Three families agreeing was not three models sharing a flaw —
they were all reading the same clipped image. Cropping the page by hand at the two
right edges settles it:

```
right = 0.95 (box 0.94 + 0.01 pad)   Pric    $300.0   $75.0   $10.0   Total: $385.0
right = 0.98 (reference 0.97 + pad)  Price   $300.00  $75.00  $10.00  Total: $385.00
```

`preprocess.crop`'s docstring already names this failure — "a bounding box drawn by
a model routinely clips a descender or the last character of a line" — and the pad
that exists to prevent it is **0.01, or 8.6px on this page**, narrower than the
character it is meant to rescue. This is the horizontal twin of the vertical offset:
the boxes are short on the right by about 0.03.

**The two `kind` confusions are capacity, not the prompt.** `minimax-m3`, given the
*unmodified* `LAYOUT_PROMPT`, returned six regions and got every Kind right —
including the two the 4B has never managed: the invoice details as `pairs`, and the
payment block as `table`. The prompt is not ambiguous. Further prompt work aimed at
those two Kinds is effort spent against a 4B model's ceiling.

Worth noting the split, because it argues against "just use a bigger model":
`minimax-m3` classifies perfectly and localises *worse* than `qwen3-vl:4b` — its
payment table is 0.35–0.45 against a reference of 0.48–0.60. Geometry and
classification are not the same capability and do not arrive together.

### Run 08 — the same cloud model through the whole pipeline, and a retraction

**"The two `kind` confusions are capacity, not the prompt" is withdrawn.** It was
drawn from the single probe above. Driven through the whole pipeline, `minimax-m3`
called Zones 2 and 3 `pairs` where they are `prose` — right in the probe, wrong
here, same model and same prompt. The question is open, not answered. This is the
second time a conclusion in this file has come from one run and not survived the
next.

Reaching a cloud model at all needed `engines/lenient.py` — an opt-in repair layer
(`DTH_LENIENT_DECODING=1`, off by default) that wraps the **Transport**, which
`transport.py` already names as the one seam to replace. `wire.py` is untouched, so
"malformed JSON is impossible" stays true where the project leans on it. It
unwraps a markdown fence and wraps a bare array under the schema's sole array
property — both lossless — and makes exactly **one inference**, documented as such:
pulling a closed-vocabulary value out of a phrase, whole-word and case-insensitive,
only when one candidate appears. `minimax-m3` answered `graphic: "SPARKSUITE logo"`,
which a model honouring `format` could not have.

The run itself argues against cloud: **9 mismatches against the local 4B's 3, mean
IoU 0.26 against 0.56**, no Probe, and four Zones lost to `TruncatedResponse`.
Twelve passes ran for six Zones because five were retries — the dump shows why, and
it is the interesting part. `minimax-m3` answers in a different format every time:
`00_layout.json` is a YAML bullet list, `01_layout.json` is fenced JSON,
`02_figure.json` is the single word `graphic`. Without `format` it does not
reliably produce structured output at all.

Access, again: the model actually worth testing — `qwen3.5:397b`, the local model's
own family at roughly a hundred times the scale — answers 403 without a
subscription. **Recommendation: do not pursue cloud further.** Keep the leniency
layer; it is opt-in and carries 20 tests.

### Runs 09 and 10 — the Probe reconciles at 385.00

`preprocess.crop`'s pad is now **asymmetric**: `PAD_X = 0.03`, `PAD_Y = 0.01`. A
uniform bump would have undone run 06. Side-by-side Zones sit 0.37 apart on this
page; stacked Zones sit 0.01 apart, at 0.63 and 0.64 between the two tables, so a
0.03 vertical pad would overlap them and re-create the split-table failure that
took five runs to remove.

Run 09 recovered every clipped character — `Item | Price`, `$300.00`, `$75.00`,
`$10.00`, `Total: $385.00` — and left the geometry byte-identical to run 06, which
is the right blast radius: the layout pass never sees the crop pads. **This one
needed no repeat run.** The cause is mechanical and was demonstrated on the pixels
before the change: the character was outside the crop at `right=0.95` and inside it
at `0.98`.

Run 09 then failed on a *different* fault — a row with 0 cells, which the mapper
correctly rejected, costing the Zone and the Probe. Intermittent rather than new:
the run 01 baseline had exactly this row, run 06 did not, run 09 did.
`TABLE_PROMPT` said "do not add a row that is not on the page" but never said a
**rule** is not a row, though `LAYOUT_PROMPT` has said exactly that about regions
since the beginning. Run 10 added it, plus "every row must have printed text in at
least one of its cells", and the empty row is gone.

```
"kind": "column-sum", "ok": true,
"computed": "385.00", "stated": "385.00", "detail": "column 1, 3 data rows"
```

Three mismatches remain, and **all three are the same kind of error**: the model
splitting one thing into one-per-column.

```
zone 1: kind expected pairs, got prose
zone 4: kind expected table, got pairs
zone 5: Row Roles [header, data, data, data, summary]
             -> [header, header, data, data, data, summary]
```

Zone 5's doubled header is `["Item", ""]` followed by `["", "Price"]` — one header
row reported once per column. That is the *same shape* as the duplicate Zone in run
04, where one region came back once per column it contained. The failure recurs at
two levels of the pipeline, and a fix aimed at the shape rather than at either
symptom is the thing to try next.

## Later: what to try on the prompt, cheapest first

1. **Reject horizontally overlapping Zones in one Band.** Zone 0 (0.00–1.00) encloses
   Zone 1 (0.75–1.00); two Zones side by side cannot overlap horizontally. A check
   `wire._validate_bands` does not yet make, ~5 lines, and it turns this class of
   answer into a named failure instead of a silently wrong render.
2. **Sweep `DTH_LAYOUT_LONG_EDGE`.** 512 is what made the pass parse at all; it was
   1024 (a no-op on this 862px image) before. Try 384, 512, 768 — the question is
   whether more pixels buys real localisation or just more tokens.
3. **Ask for fewer things at once.** The layout prompt asks for kind, role, band,
   column, four coordinates, title and graphic in one pass. Splitting geometry from
   classification is the obvious next move if prompting does not land.
4. **Give the prompt a worked example.** No few-shot example exists today. Cheap,
   and the grid-snapping suggests the model is reaching for a default shape rather
   than looking.

Stop at the first that gets `compare()` to zero. Record what was tried and what it
cost in this file — **including what did not work**, which is the more useful half
at ~5 minutes a run.

## Acceptance

- [ ] Zones are aligned by geometry for diagnosis, so a segmentation error is
      reported once rather than cascading through every later index
- [ ] Mean and per-Zone IoU are reported, giving a continuous signal to iterate on
- [ ] `compare(BUILDERS["invoice_0001"](), converted)` returns no mismatches against
      a real `qwen3-vl:4b`
- [ ] The column-sum Probe reconciles at 385.00 from a real reading
- [ ] Whole-document latency recorded here, and judged tolerable or not
- [ ] The 278-test offline suite still passes — recorded responses are unchanged
      ground truth and must not be regenerated to match a model's output
- [ ] Whatever was tried and rejected is written down here, with its cost

## Out of scope

The other four fixtures; `qwen3-vl:2b` and `granite3.2-vision` beyond one final
comparison; Ollama Cloud; the Coverage Audit; slice stitching; Corrections; and
deriving Bands from geometry — that last was proposed and **withdrawn**, because
on `sample_table_0003` the 2B model's boxes overlap vertically and derivation
collapses two Bands into one, which is worse than the model's own numbering.

## How to run it

```bash
ollama ps                                    # must be empty, or numbers are meaningless
DTH_LOG_LEVEL=INFO python -m doc_to_html.bakeoff \
  --fixtures invoice_0001 --models qwen3-vl:4b --dump /tmp/dth-dump
```

`--dump` writes each pass's raw answer to
`/tmp/dth-dump/qwen3-vl_4b/invoice_0001/NN_<pass>.json`. Read those before changing
a prompt: a run that reports only `MappingError` has thrown away the evidence.
