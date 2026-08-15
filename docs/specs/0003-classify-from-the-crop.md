# Classify from the crop, not from the downscaled page

**Status:** open, and **amended by measurement twice** — runs 18, 19 and 20
(issue #13, the blocking probe), then run 22 (the first end-to-end conversion
with the split, which made it worse). Continues `0002-structure-not-geometry.md`,
which holds the run history and the four rejected prompt attempts. Read this for
*what to build*, and read "What the first end-to-end run measured" before
believing any prediction in it.

## What the blocking experiment measured

The premise below was tested before anything was built, as story 10 asked. It is
**half right, and the half that is wrong is the half this spec argued hardest**.
Both Zones, both resolutions, three repeats each, constrained decoding, the Kind
definitions cut verbatim out of `LAYOUT_PROMPT`:

| Zone | Expected | `qwen3-vl:4b` at layout scale | at its crop | `qwen3.5:4b` at layout scale | at its crop |
|---|---|---|---|---|---|
| 1 | `pairs` | `pairs` ✓ | `pairs` ✓ | `pairs` ✓ | `pairs` ✓ |
| 4 | `table` | `pairs` ✗ | `pairs` ✗ | `pairs` ✗ | **`table` ✓** |

Three separate mechanisms, and this spec had conflated them:

1. **Zone 1 is fixed by isolation, not by resolution.** Asked on its own it comes
   back `pairs` in all twelve of its calls — including the six at 96×38, the size
   this spec called too small to see the colons. Asked as one of seven regions it
   comes back `prose` in runs 13, 14 and 15. The evidence always survived; the
   *question* was crowded. So
   "both are correct readings of the evidence the model was given" is **false for
   Zone 1**, and splitting the pass fixes it for a reason this spec did not give.
2. **Zone 4 is fixed by resolution, but only for a model that can use it.**
   `qwen3.5:4b` reads it `pairs` at 365×60 and `table` at 819×135 — exactly the
   effect this spec predicted. `qwen3-vl:4b` reads it `pairs` at both, six times
   out of six, with the shaded heading row plainly visible at full resolution.
3. **Neither change alone fixes Zone 4.** The crop alone leaves it wrong; the
   model swap alone, at layout scale, leaves it wrong. Only both together fix it.

`qwen3.5:4b` is 3.4GB against `qwen3-vl:4b`'s 3.3GB, so it is inside the same
budget on the same 8GB machine, and it is already installed.

**What this changes about the plan.** The split is still the right shape and its
two halves are both load-bearing — but classification must be routable to its own
model, and that routing is now the difference between fixing one mismatch and
fixing two rather than a convenience. It does not change what to build below;
it changes why, and it changes the default.

> **The default was reversed on 2026-07-29, after #15 shipped.**
> `DTH_CLASSIFY_MODEL` defaults to `qwen3-vl:4b`: one model in every step. The
> routing this section argues for was built and is what makes the setting exist;
> the model swap it recommends was declined for now.
>
> The reason is the paragraph immediately below this one — "what it does not
> license". A default is a claim about every document, and the evidence for
> `qwen3.5:4b` is two Zones of one fixture in a standalone probe, with its
> geometry, its behaviour on the other four fixtures, and its end-to-end
> conversion all still unmeasured. Shipping it as the default would be the
> generalisation this spec warned against two paragraphs later, made by the
> spec itself.
>
> **This is a deferral, not a refutation.** The probe stands; #19 evaluates
> models per step and combinations across steps, and is free to reinstate this
> recommendation with numbers behind it. Until then the honest prediction for
> the split is **2 mismatches → 1**: Zone 1's cause is isolation, which the
> split cures, and Zone 4's is a model that cannot use the crop, which it does
> not.
>
> **Run 22 measured that prediction and it is wrong — the answer is 3, not 1.**
> Both of its clauses held; a third Zone this prediction did not consider broke.
> See the next section.

**What it does not license.** Every number here is from `invoice_0001`'s two bad
Zones. `qwen3.5:4b` has never run the geometry pass, never been measured on the
other four fixtures, and never converted a document end to end. That it names two
Kinds correctly is not evidence it lays out a page as well — see 0001 on
generalising from one measurement.

**A cheaper rival this did not test.** If Zone 4 needs pixels and `qwen3.5:4b`
can use them, then *one* pass at a higher `LAYOUT_LONG_EDGE` on that model might
fix it without a second call per Zone at all — no extra latency, no recording
churn, no split. Nothing here rules that out: the isolation finding says Zone 1
needs the question narrowed rather than the page enlarged, which is an argument
against it, but it is an argument and not a measurement. Two runs of
`DTH_LAYOUT_LONG_EDGE=768 MODEL=qwen3.5:4b tools/iterate.sh` would settle it, and
it is the first thing to try if the split's latency turns out to be the objection
0003 predicts it will be.

## What the first end-to-end run measured

Run 22 (`debug/runs/22-split-first-e2e/`, commit `9c300b8`) is the first
conversion to run geometry → classify → extract against a real model. Run 21
(`debug/runs/21-fresh-invoice-qwen3vl/`, commit `ffd2761`) is the matching
baseline from the commit before the split landed. Same model, same fixture, same
`DTH_LAYOUT_LONG_EDGE=384`, and — checked in both `ollama_ps_after.txt` — both at
a 41%/59% CPU/GPU split, so the two are comparable with each other and neither is
comparable with a whole-GPU run.

**`invoice_0001` went from 2 mismatches to 3.**

| Zone | Expected | Run 21, no split | Run 22, split | |
|---|---|---|---|---|
| 0 | `figure` | `figure` | `figure` | ✓ |
| 1 | `pairs` | **`prose`** | **`pairs`** | ✓ fixed |
| 2 | `prose` | `prose` | `prose` | ✓ |
| 3 | `prose` | `prose` | **`pairs`** | ✗ **new** |
| 4 | `table` | **`pairs`** | **`pairs`** | ✗ unchanged |
| 5 | `table` | `table` | `table` | ✓ |

Both clauses of the prediction held exactly. Zone 1's cause was isolation and the
split cured it. Zone 4's cause is a model that cannot use the crop, and
`qwen3-vl:4b` answered `pairs` again from a crop where the shaded
`Payment Method | Check #` heading row is plainly legible — 7/7 now, counting
this run against the probe's six.

**A fourth mechanism, on top of the three above: isolation cuts both ways.**
Zones 2 and 3 are the two
address blocks in Band 1, both expected `prose`, and the split separated them:

| Zone | The crop, in full | Asked alone |
|---|---|---|
| 2 | `Sparksuite, Inc.` / `12345 Sunny Road` / `Sunnyville, CA 12345` | `prose` ✓ |
| 3 | `Acme Corp.` / `John Doe` / `john@example.com` | `pairs` ✗ |

Nothing about Zone 3 changed except what the model could see beside it. On the
whole page these two read as a matched pair of address blocks in the same Band;
cut out on its own, Zone 3 contains no street and no city, and `CLASSIFY_PROMPT`
offers "addresses" as its only cue for a block of this shape. Three lines of
company, person and contact, judged with no neighbour to compare against, is a
defensible `pairs`.

So this spec's whole argument — a Zone is classified better when the question is
narrowed to it alone — **has a cost it never named**. Narrowing the question also
removes the evidence that lives between Zones. Zone 1 gained more than it lost;
Zone 3 lost more than it gained. Two Zones is not enough to say which way the
trade goes in general, and #19 is where that gets measured across the other four
fixtures.

**A wrong Kind is not confined to the Kind.** Zone 3, classified `pairs`, went to
the Pairs extractor, which raised `MappingError: pairs Zone entry 1 has no label,
only 'john@example.com'` — an unlabelled value is not a Pair. That is the third
mismatch in the count. The failure contract held: Zone 3 renders as an empty
skeleton with an "Unresolved" finding at the top of the document, and the other
five Zones convert intact. The contract working is the good news here; the
document still lost a block it used to render correctly.

**Latency, and why the honest number is not the flattering one.**

| | Passes | Total | Layout |
|---|---|---|---|
| Run 21, no split | 7 | 219.3s | 84.2s |
| Run 22, split | 13 | 246.5s | 78.9s |

Classification cost **6 calls at 15.8s mean, 17.4s worst** — about **95s of new
model time**, which is the figure to defend. The document only got **27.2s slower
(+12%)**, and that number is confounded rather than free: the Kind mix moved from
three `prose` and one `pairs` to three `pairs` and one `prose`, and extraction
fell from 135s to 73s because the Pairs prompt is cheaper than the Prose one. A
document that classifies *correctly* would not get that discount. Quote +95s
gross, not +12% net, until #19 has two runs on a whole GPU.

**This does not void the spec, and it does not vindicate it.** The split is doing
what it was built to do — Zone 1 is measured proof that a narrowed question beats
a crowded one. It has simply not bought a net improvement on the one fixture it
was designed against, and it will not until Zone 4's model question is settled
(#19) and the prompt stops losing addresses that lack a street (open, see below).

**What this leaves open.** Widening `CLASSIFY_PROMPT`'s `prose` cue is the
obvious move and is exactly the kind of move 0002 records four failures of, so it
does not get made on one run and one Zone. Two better-grounded options, both for
#19 to decide between: give the classifier the Zone's Role and Band position,
which it currently has and does not use; or accept that a Kind decided with no
neighbourhood needs a tie-break, which is what the Coverage Audit was for.

**#18 earns its place.** Checking Zone 3 meant opening a crop that
`tools/inspect_run.py` had named `zone_03_prose.png` — geometry's discarded
guess — for a Zone the classifier called `pairs`. The run directory records the
classification only in the raw dump. Do #18 before touching `CLASSIFY_PROMPT`.

## Problem Statement

*As it stood when this spec was written. It is 3 now, and the section above says
why.*

`example/invoice.png` sits at 2 mismatches, and both are the layout pass giving a
Zone the wrong Kind:

```
zone 1: kind expected pairs, got prose
zone 4: kind expected table, got pairs
```

Four prompt attempts failed to move either (runs 11, 12, 13, 16, with 17
reproducing 16 exactly). Three of them broke Band numbering — a part of the
answer they never mentioned.

The cause is not wording. **The layout pass is asked to classify at a resolution
where the evidence for the classification does not survive.** Layout runs at
`DTH_LAYOUT_LONG_EDGE=384`, so an 862×563 page becomes 384×251:

| Zone | Expected | Got | In the layout image | At its crop |
|---|---|---|---|---|
| 1 | `pairs` | `prose` | **73×33px** — 3 lines, ~11px each | 164×73px |
| 4 | `table` | `pairs` | **342×55px** — 2 rows, ~27px each | 767×124px |

Zone 1 asks "three address lines, or three `label: value` lines?" — answerable
only by seeing the colons and two fields per line. At 11px per line the colon is
about one pixel, and three right-aligned lines look like an address. Zone 4 asks
"is the top row a shaded heading, or the first label/value line?" — the shading
is a faint band at 27px.

**Both are correct readings of the evidence the model was given.** Every Kind is
decided at 2.24× less linear resolution than the crop the Extractor takes seconds
later from the same page.

> **Measured, and this paragraph is wrong.** Zone 1 answers `pairs` correctly at
> 96×38 when asked on its own, so its evidence did survive and the reasoning
> about one-pixel colons was never the cause. Zone 4's shading is plainly legible
> at 819×135 — checked by eye against the crop — and `qwen3-vl:4b` still answers
> `pairs`. Whether it is legible at 365×60 was never checked, and nothing here
> needs it to be. See the amendment at the top.

## Solution

Split the layout pass in two, and — this is the load-bearing part — **change what
the classifier looks at**:

1. **Geometry** — the page at `LAYOUT_LONG_EDGE`, returning `bbox`, `band`,
   `column` and `role` only. Low resolution is correct here; locating a block
   does not need glyphs.
2. **Classification** — one call per Zone against its **full-resolution crop**,
   returning `kind`, and the fields that depend on reading it (`title`,
   `graphic`).

Then extraction runs unchanged.

**Splitting into two calls over the same 384px page fixes nothing** — same
pixels, same answer. 0002 item 4 proposed the split as a way to improve the
boxes; this spec adopts the split for a different and better-evidenced reason.

## User Stories

1. As an operator, I want a block of `label: value` lines to be reported as
   Pairs, so that the render shows labels beside their values rather than as
   running prose.
2. As an operator, I want a two-column block under a shaded heading row to be
   reported as a Table, so that its headings are not read across the row as
   label and value.
3. As an operator, I want `Check #` to appear above `1000` rather than beside
   `Payment Method`, so that the rendered document matches the page.
4. As an operator, I want a Zone's Kind decided from the same pixels the
   Extractor will read, so that a Kind and its contents cannot disagree about
   what the block is.
5. As a developer, I want the geometry pass asked for geometry alone, so that
   editing what a Kind means cannot break Band numbering.
6. As a developer, I want Band and column numbering to stop regressing when an
   unrelated instruction changes, so that a layout that mapped yesterday still
   maps today.
7. As a developer, I want the classification question to be one small enum
   answer, so that constrained decoding makes a wrong Kind impossible rather than
   merely unlikely.
8. As a developer, I want the Orchestrator to drive geometry, classification and
   extraction, so that routing and retry stay in the one place the project puts
   them.
9. As a developer, I want classification reachable behind `VisionEngine`, so a
   different model can classify than the one that located the blocks.
10. As a developer, I want the hypothesis tested against crops already on disk
    before any pass is built, so a wrong premise costs minutes rather than a day.
11. As a developer, I want each classification recorded in the run directory
    beside the crop it saw, so a wrong Kind can be judged against the pixels.
12. As a developer, I want the added latency measured per document, so the cost
    of the extra calls is a number rather than an impression.
13. As a developer, I want the offline suite to keep passing with no model, so
    the change is verifiable without Ollama.
14. As a developer, I want the five fixtures re-recorded once, so replayed runs
    exercise the same call sequence a real run makes.
15. As a maintainer, I want the layout prompt's Kind block deleted rather than
    edited, so the tripwire test that guards it is retired deliberately.
16. As a maintainer, I want a Zone whose classification call fails to be a
    Failure on that Zone alone, so one bad crop does not cost the document.
17. As an operator, I want a Zone classified at reduced resolution to say so, so
    a degraded reading is not mistaken for an ordinary one.
18. As a maintainer, I want the effect on fixtures 0002–0005 measured, so a fix
    for one invoice is not a regression for the other four.

## Implementation Decisions

**`VisionEngine` grows a fifth method.** Chosen over hiding per-Zone calls inside
`detect_zones`, which is documented as one call on a downscaled page and would
put a loop of VLM calls where the Orchestrator cannot see, batch or retry them.

```
detect_zones(image, hint)            -> list[Zone]   # bbox, band, column, role — NO kind
classify_zones(image, zones, hint)   -> list[Zone]   # kind, title, graphic
extract_zone(image, zone, hint)      -> Zone
read_cell(...)  audit_coverage(...)                  # unchanged
```

- `detect_zones`' contract changes: it no longer returns Kind. Its docstring says
  it does, and must be corrected.
- `classify_zones` takes the **rectified image at full resolution** plus the
  Zones, and crops each itself using the same `crop()` and `PAD_X`/`PAD_Y` the
  Extractors use. One call per Zone.
- The Orchestrator runs geometry → classification → extraction.

**Two prompts replace one.** `LAYOUT_PROMPT` loses its `kind`, `title` and
`graphic` blocks entirely — deleted, not reworded. A new classification prompt
asks one question against one crop. The wire schema for classification is one
record of scalars, per this repo's rule that flat schemas read better.

**`Kind` stays the closed set.** No new Kinds. `graphic` stays the closed
`Literal` it became after the model answered `"SPARKSUITE"`.

**A failed classification is a Failure on its Zone**, following the existing
extraction contract: the other Zones still convert.

**Band validation is unaffected.** `_validate_bands` runs on the geometry pass's
output as it does now.

**Recording churn is unavoidable and is the main cost besides latency.**
`ReplayTransport` serves responses *by order*, not by matching content, so an
extra call per Zone changes the sequence for every fixture. All five fixtures
need a classification response recorded per Zone — roughly 32 new files plus
`index.json`. `tools/record_responses.py` regenerates them.

**Latency.** +1 call per Zone; 6 Zones on `invoice_0001`. The answer is one enum,
so it should sit at the cheap end, but a document already at ~175s is the
baseline to measure against.

> **Measured, run 22: it does not sit at the cheap end.** 15.8s mean and 17.4s
> worst per classification, against 4.7s for the whole Figure extraction in the
> same run. "One enum out" bounds the *output*, and the cost is dominated by
> encoding the crop and prefilling the prompt, which classification pays in full
> and then makes the Extractor pay again on the same pixels. ~95s per document
> on a 6-Zone page.

## Testing Decisions

A good test here asserts what an operator would see — the Kind a Zone ends up
with, the rows in the render — not that a particular function was called.

**Highest seam, and the one to use: `ReplayTransport`.** Everything offline
already runs through it, and it is where the new pass becomes visible as an extra
call. Prior art: `tests/test_table_extraction.py` and `tests/test_pairs_and_prose.py`
convert a fixture from recorded responses and assert on the resulting Document.

- **Kind from a crop** — replay a recorded run of `invoice_0001` and assert
  zone 1 is `PAIRS` and zone 4 is `TABLE`. This is the whole spec, expressed as
  one assertion pair.

  > **Overstated, and run 22 shows why.** `tools/record_responses.py` derives
  > recordings from the hand-authored expected IR, deliberately, so this pair
  > asserts that the *pipeline* carries a correct classification through to the
  > Document. It passes whatever a real model answers — and the real model
  > answers `pairs` for zone 4. It is a necessary test and it is not "the whole
  > spec": `tools/iterate.sh` is.
- **The classifier sees the crop, not the page** — assert the image handed to a
  classification call is larger than the one handed to the geometry call, in the
  manner of `test_a_table_is_read_from_a_crop_and_not_from_the_page`.
- **Geometry pass asks for no Kind** — assert the geometry schema has no `kind`
  property, in the manner of the existing schema tests.
- **A failed classification does not spread** — replace one classification reply
  with a broken one and assert the other Zones still convert, in the manner of
  `TestAFailureStillDoesNotSpread`.
- **The tripwire is retired deliberately** — `test_the_kind_definitions_are_frozen_pending_a_split_of_the_pass`
  must be deleted as part of this work, not edited around.
- **Real-model verification** is `tools/iterate.sh`, twice, per 0001's standing
  rule that one run is not evidence.

## Out of Scope

- **The boxes.** IoU 0.56, and Zones 0–3 identical at 384/512/768/862 — the
  geometry pass emitting a prior instead of measuring. Isolating that pass may
  make it easier to attack; expect no improvement for free, and do not let this
  spec grow to cover it.
- **Deriving Bands from geometry.** Stays closed until IoU improves.
- **The Caveat for repaired reads** (0002's open review item) — a joined header
  row and a `LenientTransport` repair are both still silent in the IR. Related,
  but its own change.
- **Multi-page, tesseract, the Ladder, the Coverage Audit.**

## Further Notes

**Kill it cheaply first.** Story 10 blocks every other story. The crops are on
disk at `debug/runs/15-join-split-heading-repeat/zone_01_prose.png` and
`zone_04_pairs.png`. Ask `qwen3-vl:4b` the Kind question against those two
directly. If it answers `pairs` and `table`, the premise holds and the rest is
mechanical. **If it answers `prose` and `pairs` again, the resolution hypothesis
is wrong and this entire spec is void** — the defect would then be the model's
grasp of the distinction, not the pixels it was shown, and the next move is a
different model rather than a different pass.

> **Done — `tools/classify_probe.py`, runs 18/19/20.** It answered `pairs` and
> `pairs`: neither branch this paragraph anticipated. The two-way split it
> proposed was too coarse, because it held the model fixed. Writing the void
> condition down still did its job — it forced the question to be asked in
> twenty minutes rather than after a day of building, and the answer redirected
> the work instead of confirming it. The probe keeps working after the split of
> the pass lands: it asks with whatever `CLASSIFY_PROMPT` currently says, so it
> keeps measuring the shipped question rather than a frozen copy of it.

**Everything in 0002 was measured on `invoice_0001` alone**, as were runs 01–10
before it. The likeliest casualties of a `table`/`pairs` change are fixture 0002
(dense Pairs) and 0003 (a 15-row table). `FIXTURE=all tools/iterate.sh <label>`
runs the set.

**Expect the latency objection to be the one that kills this in review**, not the
correctness argument. Have the per-document number before defending it.

> **The number is in, and the prediction was half right.** ~95s per document,
> +43% on the pass budget — a real objection. But it is not the one that lands
> hardest, because run 22 also took the correctness argument away: the split
> currently makes `invoice_0001` *worse*, 2 mismatches to 3. Latency is what
> would have killed a change that worked. What has to be defended first is that
> this one works at all.

---

## Run 47 — the wording was the lever, and the trace found what is left

`debug/runs/47-prompt-and-trace/`, `DTH_SNAP_ZONES=1`, long edge 384. Against run
46 on the same fixture and the same flags.

**`invoice_0001` is at 1 mismatch, and classification is 6/6.** Zone 3 comes back
`prose` on its own now — the re-route that carried it in run 46 did not fire —
and Zone 4 comes back `table` for the first time in any run ever recorded.

| | 43 | 45 | 46 | **47** |
|---|---|---|---|---|
| geometry IoU / covered / splits | 0.56 / 0.82 / 46 | 0.91 / 0.99 / 0 | 0.91 / 0.99 / 0 | 0.91 / 0.99 / 0 |
| Kinds correct | 4/6 | 4/6 | 4/6 | **6/6** |
| mismatches | 3 | 6 | 1 | **1** |
| strings in the render | 13/25 | 13/25 | 25/25 | **25/25** |
| skeletons | 2 | 2 | 0 | **0** |
| column-sum Probe | absent | absent | passes | passes |
| seconds | 209.5 | 222.9 | 221.1 | 264.5 |

### Why the old wording lost, measured three ways

The predecessor put the semantic test first — "the heading row names the columns
rather than labelling the values beside it" — and shading second, as "often
shaded or ruled off". One reads as a rule and one as a hint, so the model applied
the rule and called Zone 4 `pairs` in **8 runs out of 8**. It was not wrong to:
`Payment Method` does label the `Check` beneath it.

- **Not row count.** Zone 5 truncated to a heading plus one data row — Zone 4's
  exact shape — still answers `table`, 3/3. The "even if only one row of values
  follows it" clause was never the clause being tested.
- **Not blindness.** Asked a typesetting question alone, Zone 4 says the top row
  is set apart, 3/3. The cue was seen and outweighed.
- **The heading's words decide, and only those.** Crossing the two heading bands
  over the two data rows — layout pixel-identical, only the text differing — gives
  `table` wherever `Item | Price` is the heading and `pairs` wherever
  `Payment Method | Check #` is. **12/12, the data row contributing nothing.**

Hence the inversion, plus `pairs` requiring the label on the *same line* as its
value. That second clause is what fixed Zone 3.

### The one that is left is new, and it is not classification

```
zone 4: Row Roles expected ['header', 'data'], got ['header', 'data', 'data']
```

Zone 4's raw answer, straight off `trace.json`:

```json
{"role": "header", "cells": ["Payment Method", ""]},
{"role": "header", "cells": ["", "Check #"]},
{"role": "data",   "cells": ["Check", ""]},
{"role": "data",   "cells": ["", "1000"]}
```

**Both** rows are split across two, not just the header. The Zone is 841x59px —
two columns roughly 800px apart — which is the same "cells at opposite edges of a
wide table" defect `_join_split_header_row` exists for. That join is deliberately
`header`-only: *"a sparse data row is a real shape rather than a defect."* So the
header was rejoined and the data row was not.

Widening the join to data rows would fix this and is **not** obviously safe — two
genuinely sparse data rows would merge. The same guards the header join uses
(equal widths, no position filled twice) do hold here, so it is a candidate
rather than a refusal. Not attempted; not measured.

### What is not measured

The same wording turns `invoice_0002`'s two panel Zones from `pairs` to `table`:
those panels put each label *above* its value, so the same-line rule reads them
out of `pairs`. A real regression, shipped as the default on one fixture's
evidence, and #19's to revisit. The other three fixtures have not been run
against it at all.

---

## Run 48 — the prompt route is closed, on identical output

`debug/runs/48-table-split-guard/`, same flags as 47. `TABLE_PROMPT` gained two
things: a statement of what a row *is* on the page ("one horizontal line… its
cells can sit far apart… text at the same height belongs to the same row however
far apart it sits"), and the guard it was missing — "do not split one printed row
across two rows", which `LIST_PROMPT` has carried all along.

**The gate was pre-registered. One of four conditions failed.**

| # | condition | result |
|---|---|---|
| 1 | Zone 4 returns `header` + one data row `['Check','1000']` | ✗ still 3 rows |
| 2 | Zone 5 still converts, 5 rows, Probe reconciles at 385.00 | ✓ |
| 3 | mismatches ≤ 1 | ✓ 1 |
| 4 | render 25/25, 0 skeletons | ✓ |

**The raw answers are byte-identical to run 47's, for both tables.** Not similar —
identical, cell for cell, including Zone 5's spurious empty row. The wording moved
the model not at all.

That is the second of the two failure readings the plan named, and it is the
decisive one: the header stayed joined and the data row stayed split, so this is
not a wording that made things worse. It is a wording the model does not act on.

**Two independent attempts now, and they should be the last.** Run 13 forbade the
header split in as many words and failed — that failure is why
`_join_split_header_row` exists in `wire.py` rather than in the prompt. Run 48
argued the general case instead, on the theory that run 13 had argued too
narrowly. Same result. How this model reads a wide, short table is not reachable
from the prompt.

The prompt text is **kept** — the instruction is correct and the asymmetry with
`LIST_PROMPT` was a latent trap — but it is recorded as inert, so nobody spends
another run on it.

### What is left, and it is already validated

The remedy has to be the one thing a prompt cannot consult: the page. A
horizontal ink projection over the Zone's crop counts printed lines, and it is
right on both tables:

| Zone | crop | ink bands | rows returned | rows the page has |
|---|---|---|---|---|
| 4 | 841x59 | **2** | 4 | 2 |
| 5 | 841x166 | **5** (plus a 2px rule to filter out) | 7 | 5 |

So: generalise `_join_split_header_row` to data rows under the guards it already
uses — equal widths, no position filled twice — but merge only when the
projection shows fewer printed lines than rows returned. The pixel evidence is
what removes the "a sparse data row is a real shape" risk that kept the repair
header-only, and it replaces a special case with one uniform rule.

`content_ink` in `preprocess.py` and `_runs_of_blank` / `_slices_between` in
`tools/cv_layout_probe.py` already do this work for the XY-cut arm; promoting
them rather than rewriting them is the job.

---

## Run 49 — 0 mismatches, by telling the model the grid instead of instructing it

`debug/runs/49-table-grid-hint/`, `DTH_TABLE_GRID_HINT=1 DTH_SNAP_ZONES=1`, long
edge 384. **`invoice_0001` converts with no mismatches for the first time.**

The change: `extract_zone` measures the crop it is about to send —
`preprocess.table_grid`, an ink projection down for rows and across for columns,
no model call — and states the counts in the table prompt. Stated, not enforced;
the schema is untouched.

**All four pre-registered gate conditions held.**

| | run 48 | run 49 |
|---|---|---|
| zone 4 | 4 rows, every one halved | **2 rows** — `['Payment Method','Check #']`, `['Check','1000']` |
| zone 5 | header split + a spurious empty row | **5 clean rows**, header whole |
| mismatches | 1 | **0** |
| column-sum Probe | ok | ok, 385.00 |
| render / skeletons / failures / caveats | 25/25, 0, 0, 0 | 25/25, 0, 0, 0 |

### Why this worked where two wordings did not

Runs 13 and 48 both issued *behavioural* instructions — do not split a row, keep
a printed line together — and run 48's answers were byte-identical to the run
before it. An instruction can only change behaviour that involves a decision, and
the model is not deciding to split a wide row; it does not read the two ends of
the line as one row, so there is nothing for the instruction to act on.

A count is a different kind of statement, and the asymmetry was visible in the
data all along: the prompt has always said "give every data row the same number
of cells as the header row" and the model has always obeyed it exactly, while
ignoring every rule about where a row begins and ends. It complies with *how
many*, not with *which line*. Stating the grid speaks the language it already
answers in.

**The effect is larger than the target.** It was aimed at Zone 4's data row. It
also stopped the header split that runs 01, 05, 10 and 13 could not move, and the
spurious empty row that cost runs 39 and 45 their whole table. `wire.py`'s two
repairs did not need to fire on either table — they are now dormant safety nets
rather than load-bearing.

### What is not measured, and why the default stays off

- **One run, one fixture.** Nothing has been re-run twice, and the four other
  fixtures have not been seen.
- **The grid is only as good as the crop.** `sample_table_0003` measures 17 rows
  against a true 16, on a hand-typed Zone box CLAUDE.md flags as 0.605-0.854 IoU
  against its own ink. Turning this on by default would state that wrong number
  to the model on every run of that fixture. Whether it is a bad crop or a bad
  ruler is unresolved and is the blocker for both flipping the default and for
  the stricter option below.
- **Timings from this run are not comparable.** Ollama put the model at 41%/59%
  CPU/GPU, so 718s against run 48's 327s is memory pressure, not the prompt. The
  answers are unaffected.

### The stricter option is now less urgent, not dead

Enforcing the grid through the schema — constrained decoding making a wrong shape
structurally impossible — remains the stronger form and remains blocked on the
same 17-vs-16. It is worth less now that stating the grid works, and it would
still be worth reaching for if a fixture turns up where the model ignores the
statement. The projection stays available as a checker either way: it is the only
thing that can tell Zone 5's genuine `['', 'Total: $385.00']` from Zone 4's
cut-in-half pair, which shape alone cannot.

### Two options left open on tables, with the trigger for each

Recorded rather than built, because `invoice_0001` now returns the right shape
voluntarily and neither has a defect to fix on it today.

**Enforce the grid through the schema.** Constrained decoding already runs on
every call, so a schema built for N rows of M cells makes a wrong shape
structurally impossible — prohibition rather than persuasion.

*Do not build it yet.* It converts a survivable error into content loss: today a
wrong count is a sentence the model may disagree with and every check behind it
still runs, while under a schema it cannot violate the model must drop or invent
cells to satisfy the number. The Title finding is the argument — a band of ink
that is not a row measured `sample_table_0003` at 17 against a true 16, and was
harmless as a statement where as a constraint it would have silently deleted a
row.

*Trigger:* a fixture where the grid is stated correctly and the model still
returns a different shape. That is the point at which stating is demonstrably
insufficient and enforcing earns its risk.

**Use the projection as a checker.** When the model's row count disagrees with
the page's, record a Caveat rather than repairing anything.

Cheaper than enforcement and worth more right now: no content risk at all, and it
turns a silent structural regression into a visible finding on *any* fixture
rather than only where somebody happens to look. It is also the only mechanism
that can tell Zone 5's genuine `['', 'Total: $385.00']` from Zone 4's
cut-in-half pair, which shape alone cannot. This is the one to build first if
anything in this space is built.
