# Structure, not geometry: the last three mismatches on `invoice.png`

**Status:** open, at **2 mismatches — after a repair in the mapper, not from the
model**. See the honesty note under runs 14/15 before quoting that number.
Continues `0001-one-image-at-a-time.md`,
which holds the run history, the measured numbers, and everything already tried
and rejected. Read this file for *what is wrong now*; read 0001 for *how we got
here*.

## Where runs 14 and 15 got to — read this first

`debug/runs/14-join-split-heading/` and `15-…-repeat`, `qwen3-vl:4b`,
`DTH_LAYOUT_LONG_EDGE=384`, ~175s. **2 mismatches**, the same two both times:

```
zone 1: kind expected pairs, got prose
zone 4: kind expected table, got pairs
```

The header split is **fixed**, and not in the prompt: `wire._join_split_header_row`
puts back together a header row the model still returns one cell per row. Zone
5's Row Roles are `[header, data, data, data, summary]`, `Price` sits on `Item`'s
row, and the column-sum Probe reconciles at 385.00.

**Read that honestly.** The model has not improved. Run 14's raw
`06_table.json` still contains `["Item", ""]` and `["", "Price"]`, exactly as
run 10's did; the acceptance criterion "Zone 5's Row Roles are `[header, data,
data, data, summary]`" is now satisfied by this project's own repair rather than
by anything the model returned. That is a legitimate fix — the wrongness was
ours to correct once characterised — but 3 → 2 measures the *pipeline*, not the
model, and comparing it against runs 01–13 compares two different things.

**Both remaining defects are Kinds from the layout pass, and the section below
says why prompt wording is not the lever for them.**

### The layout Kind block is frozen

Three attempts to change which Kind a Zone gets, each aimed at nothing else, each
leaving the layout unmappable for a reason in a *different* part of the answer:

| Run | Edit to the Kind definitions | Result |
|---|---|---|
| 11 | added "the heading row names **the columns**" | each table returned **once per column**, byte-identical boxes. Rejected: `two Zones share column [0,1,0,1]`. |
| 12 | dropped the phrase "names the columns"; added "one region however many columns it has" | all nine Zones collapsed to two Bands, both tables merged into one box, seven Zones in `band 0`. Rejected. |
| 16 | five words added to `prose` alone, one line, **no growth** | four Zones in `band 0`, column order `[0,1,2,3]` against lefts `0.05, 0.75, 0.05, 0.75`. Rejected. |
| 17 | **run 16 repeated verbatim** | *identical* failure: same message, same column order, same lefts. Rejected. |

Runs 11, 12, 16 and 17 touched this block: all four rejected. Runs 13, 14 and 15
did not: all three mapped.

The variable is **not length** — run 16 grew nothing and still broke Bands. The
working hypothesis is that this pass is at capacity, and that asking it to
classify more carefully is paid for out of the Band and column instruction
further down.

**How far that is established, precisely.** One wording (run 16) is now repeated
and reproduced exactly, which satisfies 0001's standing rule for *that* wording:
adding five words to `prose` reliably breaks Band numbering on this document.
The two other wordings, runs 11 and 12, are still single runs. So "**this
particular edit breaks Bands**" is established; "**any edit to this block breaks
Bands**" is a generalisation from three points and should be treated as the
working hypothesis it is — 0001 line 478 records a withdrawn claim of that same
class, *"the two `kind` confusions are capacity, not the prompt"*.

Run 17 also disposes of the CPU-offload confound for this result. It ran at
475.3s against run 16's 220.0s — more than twice as slow, at `41%/59% CPU/GPU` —
and returned the identical answer. Consistent with 0001's finding that offload
costs latency and not correctness.

One claim to state carefully: run 11 is often summarised as "the Kind was
fixed". What is true is that the `Payment Method` block came back `table` rather
than `pairs`. It is *not* the expected Zone 4 — that answer has nine Zones with
each table duplicated, so the indices do not correspond — and the layout was
rejected before mapping, so no extractor ever ran against it. Suggestive, not
established.

`tests/test_pairs_and_prose.py` now pins the Kind block verbatim as a tripwire.
**The next edit there should be deleting that test as part of splitting the
pass** — not another wording.

## Where run 10 got to

`debug/runs/10-no-rule-rows/` — `qwen3-vl:4b`, `DTH_LAYOUT_LONG_EDGE=384`, 176.0s.

- **3 mismatches**, down from 6 at the baseline.
- **The column-sum Probe reconciles**: `computed 385.00, stated 385.00, ok true`.
- **Every string on the page is read correctly** — `SPARKSUITE`, all three
  addresses, all four currency values with their trailing zeros.

The text is right. The numbers are right. The arithmetic checks out. What is left
is the document's *shape*.

## Defect by step

| Step | State | Evidence |
|---|---|---|
| Rectify | ✅ | no defects |
| Layout — **boxes** | ⚠️ imprecise, and see below | mean IoU 0.56 |
| Layout — **kind** | ❌ 2 defects | zone 1 `prose`≠`pairs`, zone 4 `pairs`≠`table` |
| Crop | ✅ | fixed by `PAD_X`; nothing is clipped |
| Extraction — **text** | ✅ 0 defects | every string correct |
| Extraction — **structure** | ❌ 1 defect | header row emitted one row per column |
| Mapping, Probes, Render | ✅ | render is faithful to the IR it is handed |

**Every remaining defect answers "what structure is this?" — none answers "where
is it?" or "what does it say?"** That is the bracket. Effort spent on
localisation or transcription right now is effort spent on solved problems.

## The two visible defects, traced to their step

**`Price` is not on the same row as `Item`.** Extraction, table pass:

```
row 1: ["Item", ""]        row 2: ["", "Price"]
```

One header row emitted as one row per column.

**`Check #` appears on the wrong side.** *Layout*, not extraction. Zone 4 was
labelled `pairs`, so the Pairs extractor read **across** the row and paired two
header cells as label and value:

```
"Payment Method" -> "Check #"
"Check"          -> "1000"
```

The extractor did its job correctly on a Zone that was mislabelled upstream. **This
is the target**: one wrong Kind produces the whole mangled block.

## The single underlying misreading

Both defects are the **header row of a wide two-column table**, where the two cells
sit at opposite page edges (~0.04 and ~0.93) with whitespace between:

- Zone 5: the model **fails to bind** them, and emits one row per column.
- Zone 4: the model **binds them wrongly**, as label to value.

Data rows in the same table bind correctly — `Website design | $300.00` spans the
same width and is read right. It is specifically the **shaded header row**. This
has recurred in runs 01, 05 and 10, so it is a stable property of the model on this
document rather than sampling noise.

## On the boxes — a correction

An earlier reading of this called the imprecise boxes "not harmful because
extraction is complete". **That is too weak, and wrong in a way worth naming.**

The boxes are wrong in a specific, measurable way. Zone 0 is `0.10–0.14` for a
wordmark spanning `0.06–0.17` — the crop cuts the logo top and bottom, and it
transcribed correctly anyway. That is luck, not robustness.

They also condition more than the crop:

- The Band and column structure has to be **consistent with** the geometry, and
  `wire._validate_bands` accepts or rejects a whole layout on that basis. A wrong
  box can make a correct Band numbering fail, or a wrong one pass.
- The rendered layout — what sits beside what — follows Band and column. Geometry
  that disagrees with the grouping is a render that disagrees with the page.
- Deriving Bands from geometry was proposed in 0001 and **withdrawn** because the
  boxes were not good enough. That option stays closed while IoU sits at 0.56.

And the strongest evidence that this is unfinished rather than acceptable: **Zones
0–3 come back bit-identical at 384, 512, 768 and 862 px** — a 3× range in image
data, no change in the answer, and the answer is wrong. For the stereotyped top of
the page the model is emitting a prior rather than measuring. It is not currently
*causing* a mismatch on this document because the prior is roughly right here.

So: **not the cause of today's three mismatches, but an active defect with a known
failure mode** — a document whose layout does not match the prior. Fix the three
first, because they are cheap and specific; do not close the geometry question.

## What to fix, in order

**Superseded by the two sections above.** Kept because the reasoning is still
sound and only the remedies changed; the numbering is referred to elsewhere.

1. ~~**Zone 4's Kind**, prompt-level in `LAYOUT_PROMPT`.~~ **Still open, and not
   prompt-level.** Three measured attempts rejected — the Kind block is frozen.
   This now needs the same split of classification from geometry as item 4, and
   is the stronger reason to do it: item 4 was about *boxes*, and this is a
   second, independent defect with the same cause.

2. ~~**The header split**, prompt-level in `TABLE_PROMPT`.~~ **Done**, in
   `wire._join_split_header_row` rather than the prompt. Runs 14 and 15.

   The instruction to "do 1 and 2 together" was written on the expectation that
   fixing 1 would relocate the bug into Zone 4's header. The join is in the
   mapper and applies to any `table` Zone, so the intent is that Zone 4's header
   is covered the moment Zone 4 becomes one. **This is unverified**: the only run
   in which that block came back `table` is 11, which was rejected at layout, so
   no table pass has ever read Zone 4. Treat it as designed-for, not shown.

3. **Zone 1's Kind** (`prose` where the invoice details are `pairs`). **Still
   open.** Attempted in run 16 and rejected. Note the diagnosis this spec
   implied is wrong: the block is not unclear about `pairs`, whose example
   `"Invoice No: 12"` is near-identical to the page's `Invoice #: 123`. It is
   right-aligned and three lines, so it reads as an **address**, which `prose`
   claims. Still costs nothing downstream — the text is read correctly either
   way.

4. **The boxes.** Originally "**not before 1–3**". That ordering is now
   **withdrawn rather than met**: items 1 and 3 turned out to need the same split
   of classification from geometry that this item proposes, so holding item 4
   behind them would deadlock. Still not by more prompt tuning of the same shape.
   The frozen-across-resolutions result says the layout pass is not measuring the
   top of the page, so asking it more politely will not help. Two options worth
   weighing when the time comes, neither yet tried:
   - a **separate geometry pass** that only returns boxes, with classification
     asked separately — 0001 lists this as untried, and the split of capabilities
     seen between models (one localises well and classifies badly, the other the
     reverse) is evidence the two jobs do not belong in one prompt;
   - deriving Bands from geometry, which stays **closed** until IoU improves.

## Closed question: a second VLM call for structure

This asked whether a **dedicated pass answering "how many columns does this table
have"** should read the wide header. **It should not, and the reason retires the
question rather than deferring it.**

The column count was never wrong. The model returns `["Item", ""]` — *two* cells
for a two-column table. It has read the shape correctly and only misplaced the
line break. A pass asking how many columns there are would answer a question
nobody got wrong, and cost a whole extra VLM call on a document already at ~175s.

What was actually wrong is row segmentation, and that is repairable exactly:
`wire._join_split_header_row` joins two adjacent `header` rows of equal width that
are never both filled at the same position. Every string keeps the column it
arrived in — nothing invented, nothing dropped. Header rows only, because data
rows bind correctly; no position filled twice, because two headings competing for
one column are not one row split in two, and that case still fails loudly.

Rejected on the way, with costs:

- **`TABLE_PROMPT` told a heading row spanning all columns is one row** (run 13).
  No effect on the split, and it provoked a row with no cells at all: 3
  mismatches → 5. Reverted.
- The three layout attempts in "The layout Kind block is frozen" above.

One caveat worth a reviewer's eye: this puts a structural repair in `wire.py`,
which `engines/lenient.py` records a decision to keep strict. That decision was
about tolerating *malformed JSON* for one cloud model; this normalises
well-formed, schema-valid input under a precondition that makes it lossless. A
different question — but a judgment call, not a settled one.

## Standing rule, carried over from 0001

**One run is not evidence.** Twice in 0001 a conclusion drawn from a single run was
overturned by the next: "Zone 6 is invented", and "the Kind confusions are capacity
rather than the prompt". Repeat a result before writing it down as fixed. The one
exception was the crop pad, where the cause was demonstrated on the pixels *before*
the change was made.

## Acceptance

- [ ] Zone 4 is a `table` — **open**, and blocked on splitting the layout pass
      rather than on wording. Its header is covered the moment it is a `table`.
- [x] Zone 5's Row Roles are `[header, data, data, data, summary]` — runs 14, 15
- [x] The Probe still reconciles at 385.00, and every string is still read
      correctly — runs 14, 15
- [x] Whatever was tried and rejected is recorded here with its cost — runs 11,
      12, 13, 16
- [x] The offline suite still passes; recorded responses are ground truth and are
      not regenerated to match a model's output — 314 tests, mypy clean

Zone 1's Kind was not in the original list and remains open, for the same reason
as Zone 4.

## Open from review, not yet acted on

**The join records no Caveat, and should.** `CONTEXT.md` defines a Caveat as
"something an operator should know about *how* a Zone was read, on one that was
read… so nobody mistakes it for an ordinary reading" — which is exactly a header
row this project assembled rather than read. It is not built because the note
would have to travel from `wire.rows_from_table` out through the Extractors to
the Orchestrator, which is where `document.caveats` is filled, or else `Zone`
grows a field and `ir.py`'s versioning and every fixture follow it. Both are real
changes rather than review touch-ups. **Until it exists, a joined header is
indistinguishable in the IR from one the model got right** — and the same
argument applies to `LenientTransport`, which also repairs silently.

**A two-tier header would be joined wrongly.** Recorded in
`_join_split_header_row`'s docstring. No fixture has that shape and no run has
produced one, so it is a known risk, not a measured defect.

## Not measured, and worth knowing

Every run here is `invoice_0001` alone. `_join_split_header_row` and the reverted
prompt attempts apply to **every** document, and their effect on fixtures
0002–0005 has never been measured — as was true of runs 01–10 before them. The
offline suite cannot cover it: `tests/responses/` is frozen ground truth recorded
under an older prompt and is never re-run against the current one.

`tools/iterate.sh` now takes `FIXTURE=all` or a comma-separated set, so the sweep
is one command when it is wanted. The likeliest casualties of a `table`/`pairs`
change are 0002 (dense Pairs) and 0003 (a 15-row table).

## How to run it

```bash
DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>
```

One whole document from scratch, about three minutes. The run directory carries the
prompt, the host, the resolution, every raw answer, the geometry report, the per-Zone
crops beside the text each returned, and the rendered document. **Open its
`index.html` before changing anything** — reasoning about this page from normalised
rectangles instead of pixels is what produced both retracted conclusions in 0001.
