# Classify from the crop, not from the downscaled page

**Status:** open. Continues `0002-structure-not-geometry.md`, which holds the run
history and the four rejected prompt attempts. Read this for *what to build*.

## Problem Statement

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

**Everything in 0002 was measured on `invoice_0001` alone**, as were runs 01–10
before it. The likeliest casualties of a `table`/`pairs` change are fixture 0002
(dense Pairs) and 0003 (a 15-row table). `FIXTURE=all tools/iterate.sh <label>`
runs the set.

**Expect the latency objection to be the one that kills this in review**, not the
correctness argument. Have the per-document number before defending it.
