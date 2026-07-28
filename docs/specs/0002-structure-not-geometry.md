# Structure, not geometry: the last three mismatches on `invoice.png`

**Status:** open. Continues `0001-one-image-at-a-time.md`, which holds the run
history, the measured numbers, and everything already tried and rejected. Read
this file for *what is wrong now*; read 0001 for *how we got here*.

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

1. **Zone 4's Kind — the mislabelled Zone.** A shaded row of short headings above
   rows of values is a `table` header, not a label-value pair. Prompt-level, in
   `LAYOUT_PROMPT`'s `table`/`pairs` definitions.

2. **The header split.** A header row spans all of the table's columns and is one
   row. Prompt-level, in `TABLE_PROMPT`.

   **Do 1 and 2 together.** Fixing 1 alone will likely relocate the bug rather than
   remove it: once Zone 4 is a `table`, its header is the same wide two-column
   header that Zone 5 already splits.

3. **Zone 1's Kind** (`prose` where the invoice details are `pairs`). Left last
   because it is one field on one Zone and costs nothing downstream — the text is
   read correctly either way.

4. **The boxes.** Not before 1–3, and not by more prompt tuning of the same shape.
   The frozen-across-resolutions result says the layout pass is not measuring the
   top of the page, so asking it more politely will not help. Two options worth
   weighing when the time comes, neither yet tried:
   - a **separate geometry pass** that only returns boxes, with classification
     asked separately — 0001 lists this as untried, and the split of capabilities
     seen between models (one localises well and classifies badly, the other the
     reverse) is evidence the two jobs do not belong in one prompt;
   - deriving Bands from geometry, which stays **closed** until IoU improves.

## Open question: a second VLM call for structure

Worth deciding before implementing 1 and 2. Both fixes assume one pass can be
talked into reading a wide header correctly. If two rounds of prompt work do not
move it, the alternative is a **dedicated pass that answers only "how many columns
does this table have, and where are their boundaries?"**, with the row reading done
against that answer.

That is a real design change — a new pass, a new schema, more latency on a document
already at 176s — so it needs a failed prompt attempt behind it first, not a guess.
Record the attempt either way, per 0001's standing rule.

## Standing rule, carried over from 0001

**One run is not evidence.** Twice in 0001 a conclusion drawn from a single run was
overturned by the next: "Zone 6 is invented", and "the Kind confusions are capacity
rather than the prompt". Repeat a result before writing it down as fixed. The one
exception was the crop pad, where the cause was demonstrated on the pixels *before*
the change was made.

## Acceptance

- [ ] Zone 4 is a `table`, and its header is one row
- [ ] Zone 5's Row Roles are `[header, data, data, data, summary]`
- [ ] The Probe still reconciles at 385.00, and every string is still read correctly
- [ ] Whatever was tried and rejected is recorded here with its cost
- [ ] The offline suite still passes; recorded responses are ground truth and are
      not regenerated to match a model's output

## How to run it

```bash
DTH_LAYOUT_LONG_EDGE=384 tools/iterate.sh <label>
```

One whole document from scratch, about three minutes. The run directory carries the
prompt, the host, the resolution, every raw answer, the geometry report, the per-Zone
crops beside the text each returned, and the rendered document. **Open its
`index.html` before changing anything** — reasoning about this page from normalised
rectangles instead of pixels is what produced both retracted conclusions in 0001.
