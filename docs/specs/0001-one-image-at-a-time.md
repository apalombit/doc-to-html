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
- Zone 6 is invented — the totals row ends around y=0.92 and the rest is whitespace.
  This is what makes Zone count 7 against an expected 6, and Band count 5 against 4.
- Extraction crops therefore cover the wrong pixels, which is why the line-items
  table came back with a duplicated header row and one row of zero cells, failing
  the width check and so producing no Probe.

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

Every one corresponds to something genuinely wrong — this is not an over-read of a
correct document. Cause (b) is also what displaces `Total: $385.00` into body text
under a spurious "Domain name (1 year)" heading in the render. But (a) and (b) are
one segmentation failure counted three times, and the missing Probe is purely a
consequence of (d).

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

### Next steps, in order

1. **Align Zones by geometry, not index, for diagnosis.** Match each produced Zone to
   its best-overlapping reference Zone, and report unmatched Zones on both sides as
   *spurious* and *missed*. This separates "wrong segmentation" from "wrong reading"
   — currently indistinguishable — and stops one error inflating into thirteen.
   Keep `compare()` as it is for acceptance; this is a second, diagnostic view.
2. **Report mean IoU and per-Zone IoU** alongside it, so a prompt change can be
   judged better or worse rather than argued about.
3. **Only then** touch the prompt or the checks. The four root causes above are the
   list to work through, and (b) — the invented Zone — is the one to take first,
   since it causes three of the six reported symptoms and the visible displacement of
   the total.

Item 1 is where the horizontal-disjointness check below belongs: Zone 0 enclosing
Zone 1 is cause (a), and a mapper that rejected it would have turned a confidently
wrong render into a named failure.

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
