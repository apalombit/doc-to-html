# Spec 0007 — handover prompts

One prompt per thread, to be pasted into a fresh session. **Run them in order,
one at a time.** Each thread ends at a gate that must be met before the next
prompt is used.

**Why these exist:** they scope a fresh session to **one thread**, and they carry
the two or three things about each thread that are easy to get subtly wrong.
`CLAUDE.md` was rewritten on 2026-09-17 so that a fresh session is pointed at
spec 0007 rather than at the retired harness — its "READ THIS FIRST" section now
carries the target change, the six axes, the T1 ratchet and the thread order. So
these prompts no longer need to argue against it; they only need to say which
thread to do.

---

## Thread 0 — the ruler, the corpus, and the report — **DONE 2026-09-18**

Landed. The prompt is kept below as a record of what was asked for.

**What exists now:** `corpus.py` (fifteen documents, *iterate* / *sweep*),
`projection.py` (`project()`, one function over both sides, colour scheme
pinned light), `scoring.py` (six axes, T1/T2/T3 hard tier, T1 a ratchet),
`report.py` (`debug/runs/<label>/report.html`). Unit tests in
`tests/test_scoring.py` and `tests/test_projection.py` run offline against
`tests/frozen/run84/`.

**Three things a later thread should know**, all of them surprises:

1. The scorer reports the Zone-Title duplication in **four** documents where
   the spec says three. It is right: `sample_table_0003`'s caption is repeated
   by the same mechanism and the spec had filed it separately under the lost
   header.
2. Three faults were in the *rendering harness*, not the IR — inherited dark
   mode, a 500px layout floor, and a screenshot at exactly the page height
   dropping its last row. See `CLAUDE.md`'s first lesson. Each is pinned by a
   test.
3. T1 as specified — token recall and precision — **cannot see the
   `invoice_0001` label mis-split**, which the spec's ratchet paragraph claims
   it catches: `Invoice #: 123` read as label `Invoice`, value `#: 123` has
   exactly the right tokens in the right order. `Completeness.join_recall`, the
   adjacent-word pairs, is what catches it, and it is reported beside recall
   and precision for that reason.

**What Thread 0 did not finish:** `OllamaEngine.detect_zones` and
`LAYOUT_PROMPT` survive as the seam the recorded-response suite replays
against. They are unreachable from a Conversion. Removing them means replacing
the layout stage of nine test modules and is bookkeeping, not a measurement
question.

<details>
<summary>The prompt as it was given</summary>

```
Read docs/specs/0007-look-like-the-document.md in full before anything else.
CLAUDE.md's "READ THIS FIRST" section summarises it; the spec is authoritative.

Implement Thread 0 only. Stop at its exit gate and report. Do not start Thread 1/A.

Order matters in Step 1 — freeze before you delete, and COPY, never move. Verify
debug/runs/84-rule-not-a-line/ still exists before touching anything; it held all
five dump/qwen3-vl_4b/*/document.html files as of 2026-09-17, and nothing but you
will have changed it. If it has been cleared, stop and say so: the frozen set is
the only record of the faults the scorer must be able to find, and it cannot be
reconstructed without re-running. Leave run 84 itself intact when you are done.

Two things in Thread 0 that are easy to get subtly wrong, both called out in the
spec:

- project() must compare a normalised view — text runs in reading order, block
  roles, client rects — and never raw markup. If the scorer starts demanding our
  output reproduce the source's div nesting or class names, it has become a worse
  overfit than the one being escaped.

- The report at debug/runs/<label>/report.html is a required deliverable, not a
  nicety. One page, every document, source left and render right at matched
  width, intermediate steps collapsed. Alessandro reviews this file and will not
  navigate per-fixture folders. tools/inspect_run.py's per-fixture index.html
  stays as it is; it answers a different question.

The exit gate is three things: the scorer independently reports run 84's three
known faults against tests/frozen/run84/ without being told they are there; the
report renders all fifteen documents in one page; a checkpoint run exists.

When the gate is met, take the checkpoint run and stop. I will review the report
before Thread 1/A starts.
```

</details>

---

## Thread 1/A — the IR

Use only after Thread 0's gate is met and its checkpoint report has been
reviewed.

### What the Thread 0 checkpoint changed about this thread

Read this before running the prompt below. Three things came out of the
checkpoint sweep that were not knowable when A0 was scoped, because A0 was
scoped against the original five.

**1. A0's stated gate is now out of reach, and the number needs a decision.**
The prompt below pre-registers *T1 = 1.00 recall and precision on the sweep
set*. That was written when the sweep set did not exist. On the checkpoint,
several of the ten new documents lose most of their content outright — whole
Zones rejected, not cells mis-split — and no amount of fixing A0's three
content faults reaches 1.00 on them. The three faults A0 names are real and
still worth fixing first; what cannot stand is the *scope* of the number
attached to them. **Do not quietly relax it, and do not quietly fail it.**
Either re-register A0's gate as 1.00 on the *iterate* set with the sweep set
reported but not gating, or split the whole-Zone failures out as their own
phase ahead of A0. That is Alessandro's call, not the thread's.

**2. The whole-Zone failures are a different fault from the three A0 names.**
A0's three faults are content being *mis-read* — a header dropped, a title
repeated, a line broken. What the new documents show is content never being
*attempted*: a table Extractor raising `MappingError` on a row-width mismatch
and the Zone being abandoned. Those are unrelated causes, and lumping them
together under "stop the bleeding" will make A0 look like it failed when its
own three fixes worked.

**3. `DTH_SNAP_ZONES` is silently not applying to a meaningful share of the
corpus.** On the checkpoint it moved boxes onto their ink and then invalidated
the Bands on four of the fifteen documents, so those four converted on the
Engine's unsnapped geometry. Two shapes: a full-width Zone with a narrow box
strictly inside it (enclosure the validator is right to refuse), and two Zones
snapping onto nearly the same span. Both are A2 questions about *grouping*
before they are snap questions. **The snap is one of the four defaults that
must not be deleted** — the finding is that it is not being applied, which is
a different fact from it being harmful. Worth surfacing in `report.html` as a
finding rather than leaving it in `bakeoff.stderr.txt`.

```
Read docs/specs/0007-look-like-the-document.md, then implement Thread 1/A only.
Stop at its gate.

Phase A0 first and on its own — the three content faults plus the
wire._without_empty_rows `if row.cells` bug. Take a checkpoint run at the end of
A0 before starting A1: A0's gate is T1 = 1.00 recall and precision on the sweep
set, and it is the ratchet's starting notch, so every later phase is measured
against it. Not "improved" — 1.00.

Then A1 (inline runs), A2 (align, width, page width), A3 (figure pixels).

The T1 ratchet applies between every phase. If a phase improves its own axis and
lowers completeness, it has failed and must be reworked, whatever else moved.
This is the rule that would have caught all three of A0's faults shipping as
improvements in the first place.

Report at A0's checkpoint and again at Thread A's gate.
```

---

## Thread 2/B — the style record

```
Read docs/specs/0007-look-like-the-document.md, then implement Thread 2/B only.
Stop at its gate.

All CV, zero added model calls — this is decided, not a starting position. Do not
add a style prompt or a style pass call. Colour, type size, borders, widths and
alignment are all measurable from pixels already in hand, and the spec's table
says how each one is obtained.

The OpenCV rectangle finder built for spec 0006 Change 3 is reused here. It works
— it located exactly invoice_0002's four panels and sample_css_0004's two cards —
and was shelved only because Change 2 had already spent its value on grouping.
Keep its guard: a rectangle covering more than 0.80 of the page is the page.

Font family is de-prioritised and does not gate the phase. Cheap guess, sans
fallback, move on.

Primary target is height_ratio moving toward 1.0 across the sweep set.
invoice_0002 was at 1.54. Report at the gate.
```

---

## Thread 3/C — the repair loop

```
Read docs/specs/0007-look-like-the-document.md, then run Thread 3/C's re-scoping
gate FIRST, before writing any loop code.

Classify every residual error left after Threads A and B as (a) the IR still
cannot express it, (b) a pass got it wrong and would again, or (c) it needs a
second look at the whole page. Report that classification and stop.

Build the loop only if (c) is a material share. If it is not, close this thread
unbuilt and write the classification into the spec as its evidence — the way spec
0006's Change 3 closed. Do not build a loop to fix residuals that are actually
(a) or (b); widening the IR or fixing the pass is cheaper and deterministic.

If it is built: the loop may re-interpret what was read, never re-read it. Text
content is not in its mutable surface. A loop permitted to rewrite text is a loop
permitted to invent it, and T1 is the axis that matters most.
```

---

## Thread 4/D — human corrections

Unscheduled. Revisit when real photographs enter the corpus, since that is the
case where derived ground truth is unavailable and a human ruling is the only
ground truth there is.

---

## Standing rules for every thread

- **Never cite a run you cannot open.** `debug/runs/` is gitignored and cleared.
  Re-take with `FIXTURE=all tools/iterate.sh <label>` rather than quoting.
- **Compare only runs taken against each other, one change apart, in one
  sitting.** This applies to Claude's visual judgements at least as strongly as
  to numbers: a rubric score from one session and a rubric score from another are
  not comparable and must never be tabulated together.
- **Every checkpoint produces a report at `debug/runs/<label>/report.html`.**
- **`CLAUDE.md` was rewritten on 2026-09-17** to point at this spec. What it does
  *not* yet carry is a baseline, because none exists under the new criteria — the
  first one comes from Thread 0's checkpoint. Add it then, and not before.
- **Run 84 is read-only.** Thread 0 copies from it; nothing modifies or removes
  it. If it has changed, an agent changed it.
