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

**1. A0's stated gate was out of reach, and has been re-scoped — decided
2026-09-19.** The prompt below pre-registers *T1 = 1.00 recall and precision
on the sweep set*, written when the sweep set did not exist. Several of the
ten new documents lose most of their content outright, and no amount of fixing
A0's three content faults reaches 1.00 on them. **Alessandro's decision: split
the whole-Zone failures out as their own phase ahead of A0** — Phase A-1
below. A0 keeps its three faults.

**Superseded 2026-09-20 on the second half of that sentence.** A0 does *not*
keep its 1.00: A-1 ran, and the checkpoint disproves the number rather than
merely rebasing it — `receipt_0010` at recall 0.175 and `catalogue_0015` at
0.571, neither touched by any of A0's three faults. A0's gate is set on entry,
against precision. See the A-1 outcome section below.

**2. The whole-Zone failures are a different fault from the three A0 names,
and they are now Phase A-1.** A0's three faults are content being *mis-read* —
a header dropped, a title repeated, a line broken. What the new documents show
is content never surviving at all. Lumping them together would make A0 look
like it failed when its own three fixes worked.

### Phase A-1 — nothing silently loses content

Runs before A0. Scoped from the Thread 0 checkpoint, reviewed document by
document on 2026-09-19. **Three causes, all in scope, plus an honesty rule.**

**Cause 1 — a table is read, then discarded whole.** `MappingError: table row
1 has 6 cells but the header has 7`. The rows came back; one row disagreed
with the header on width and the entire Zone was abandoned. This alone is
almost all of `statement_0006` (36 transaction rows, recall 0.097) and a chunk
of `cv_0013`. The content existed and was thrown away, so it is the cheapest
recall in the corpus. Reconcile the row against the header — pad short, flag
long — rather than rejecting the Zone. **`wire._without_empty_rows` is a
related but separate net and must not be deleted**; its own `if row.cells` bug
is A0's, not A-1's.

**Cause 2 — content outside every detected box is dropped, and the finding
understates it.** `receipt_0010` keeps its header and loses everything from
the first line item to the barcode: 77 of 103 tokens, reported as *"Content
found outside every detected region: found by ink coverage, so it may be a
mark."* Also `form_0007` and `nonlatin_0014`, where the missing piece is the
document's own title. Two things wrong: the detector does not cover the page,
and the finding calls a majority of the document a possible mark.

**Cause 3 — the whole page comes back as one Zone, silently.**
`darkdeck_0009`: one Zone, recall 0.201, **no finding at all**. Cause is
established, not suspected: `preprocess._ink()` thresholds with
`cv2.THRESH_BINARY_INV + THRESH_OTSU`, which treats dark pixels as ink, and
`darkdeck.png` is 96.2% below mid-grey, so nearly the whole page reads as one
ink blob. The document was checked first and is fair — ordinary contrast,
ordinary structure, and it scores perfectly against itself. **Detect ground
polarity and invert before thresholding.** Thread 2/B computes modal
background anyway, so the test is shared; do not build a second one.

**The honesty rule, which is the phase's real gate.** Content that does not
reach the output must produce a finding that says so and says how much. A
silent loss is worse than a loud failure: `darkdeck_0009` lost 80% of its
document and reported nothing, and `receipt_0010` lost 75% and called it a
mark. **A-1 is not done while any document can lose content quietly.** Pair
the phase with a test that asserts, over the sweep set, that a drop in token
recall is accompanied by a finding naming the Zone.

**Gate.** No document loses content without saying so, and the three causes
above are fixed. T1 is reported on the sweep set but **A-1 does not gate on
1.00** — that stays A0's, measured after this phase lands. The T1 ratchet
applies from A-1's checkpoint onward.

### Outcome — 2026-09-19: three causes fixed, gate NOT met

Checkpoint `88-a1-checkpoint`, all fifteen, scores frozen at
`tests/frozen/a1-checkpoint/`. The three causes are fixed and declaration now
carries magnitude — `receipt_0010` says *"Zone 1 (table) was read short — 19
printed lines, 3 returned [50% of the page's ink]"* where it used to say "may be
a mark". `darkdeck_0009` went from **1 detected region to 13**.

**Nine of fifteen still lose content quietly, and the reason is a ceiling on the
rule rather than a missing fix.** The remaining loss is *within* lines: every
quiet-loss document returned as many printed lines as its crop holds or more
while dropping words inside them — `catalogue_0015` read 28 lines where 20 are
printed and lost 43% of its tokens. Two pixel-side detectors were built and
measured and both were rejected for firing on clean documents while missing the
worst real loss; the table is in `src/doc_to_html/honesty.py`. **Do not build a
third without a new kind of evidence.**

**What this settles about Thread 3/C, written out because the shorthand was
useless.** 3/C's gate classifies each residual as (a) the IR cannot express it,
(b) a pass read it wrong and would again, or (c) it needs a second look at the
whole page — and the loop is built **only if (c) is a material share**. This
residue is **(b)**: the conversion is deterministic at `temperature: 0`, so a
loop re-reading the same crop gets the identical wrong answer back. **Do not
plan on 3/C to recover recall**, and do not let that hope justify deferring
reading quality. On this evidence 3/C closes unbuilt, as spec 0006's Change 3
did. What would actually reach intra-line loss is two readings of one crop
compared — `CellState.DISPUTED` and the Ladder already exist for it, and
`_climb_ladders` already says it waits on a second Engine.

**Two decisions were Alessandro's, were asked, and are now taken — 2026-09-19.**
Both bound during A-1's implementation. Recorded here with what was rejected,
because both move a pre-registered number.

1. **The ratchet's starting notch is A-1's checkpoint.** Every phase from A-1
   onward is measured against it, and **A0's "T1 = 1.00 on the sweep set" is
   re-baselined and measured after A-1 has landed** rather than against the
   number the spec pre-registered. *Rejected:* leaving the notch at A0, which
   would have let A-1 make large T1 moves with no floor under them — an A-1
   sub-change losing content on one document while gaining on another would
   have had nothing to catch it, which is the exact failure the ratchet exists
   for. This is the second pre-registered number this work has moved, which is
   why it is written down rather than inferred.

2. **The honesty rule covers loss and only loss** — token recall, and content
   that never arrived. *Rejected:* covering all of T1. Two reasons, and the
   second is the decisive one. Duplication is a precision fault and a mis-split
   is a join fault, and neither is content that failed to arrive:
   `invoice_0001` at recall 1.000 with a broken join has lost nothing. And the
   pipeline has no ground truth, so it cannot know it split `Invoice #: 123` at
   the wrong point — a rule requiring it to say so would be a rule no pipeline
   change could meet. Those two faults stay **A0's to fix**, and A0 fixes them
   rather than announcing them.

   **So the worry that prompted the question does not materialise:**
   `invoice_0001` and `sample_css_0004` produce no new findings under this
   scope, and nothing on the report reads as a regression that is not one.

### Deferred deliberately, with the reason

- **The renderer's card treatment waits for Thread 2/B.** `render.py`'s
  `section.titled` gives every titled Zone a border and shaded title bar
  unconditionally, so a flowing document like `report_0011` renders as a stack
  of cards and the source is never consulted. It affects roughly ten
  documents. **2/B now runs before A0, so this is the next thing fixed rather
  than a standing deferral:** 2/B measures borders from pixels and draws a card
  only where the source has one.
- **Column collapse waits for A2.** `form_0007`, `menu_0012`, `cv_0013`,
  `catalogue_0015` and `newsletter_0008` put side-by-side content into one
  column (`beside_agreement` 0.03–0.40). Accepted interim state: **content
  complete and reading order correct, in one column.** So A1 (inline) runs
  before A2 (geometry). Do not trade T1 for column shape.

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
A0 before starting A1.

A0's gate is NOT "T1 = 1.00 on the sweep set" any more, and it is NOT the
ratchet's notch. Both were superseded: the notch is Phase A-1's checkpoint,
committed at tests/frozen/a1-checkpoint/, and the 1.00 is disproved — A-1 left
receipt_0010 at recall 0.175 and catalogue_0015 at 0.571, and none of A0's three
faults touches either document. SET A0's GATE ON ENTRY, from measurements taken
in that sitting, against precision (0.91-0.98 at the A-1 checkpoint), which is
what A0 actually moves. Do not inherit a number from this file.

Then A1 (inline runs), A2 (align, column width), A3 (figure pixels). Page width
is no longer here: it moved into Thread 2/B, which runs before A0.

The T1 ratchet applies between every phase. If a phase improves its own axis and
lowers completeness, it has failed and must be reworked, whatever else moved.
This is the rule that would have caught all three of A0's faults shipping as
improvements in the first place.

Report at A0's checkpoint and again at Thread A's gate.
```

---

## Thread 2/B — the style record — **DONE 2026-09-22, bar the type scale**

Moved ahead of A0 on 2026-09-20. A0 moves precision (0.91–0.98) while
`height_ratio` runs 1.03–3.70 and the renderer cards every titled Zone on ~10
documents; 2/B is also the only thread adding no model call, so it is
deterministic and cannot threaten the ratchet A-1 set.

```
Read docs/specs/0007-look-like-the-document.md, then implement Thread 2/B only.
Stop at its gate.

All CV, zero added model calls — this is decided, not a starting position. Do not
add a style prompt or a style pass call. Colour, type size, borders and widths are
all measurable from pixels already in hand, and the spec's table says how each one
is obtained.

THE RECTANGLE FINDER HAS TO BE BUILT. This prompt used to say it existed and must
be reused. It is not in the tree and never was — `git log -S findContours` returns
only preprocess.find_page_quad, which is page-edge detection for rectification,
and tools/cv_layout_probe.py's zones_from_morphology dilates ink into blocks and
cannot see a drawn border. Spec 0006 Change 3 measured it in a scratch script that
was never committed. Two things were recorded about it and both are a starting
point to RE-MEASURE rather than results to cite: that it found exactly
invoice_0002's four panels and sample_css_0004's two cards, and the guard that a
rectangle covering more than 0.80 of the page is the page.

Two scope boundaries, both decided rather than drifted:
  - Document.page_px is MEASURED here and DRAWN by A2. It moved into this thread
    on 2026-09-20 and the measurement sent it back the same day: run
    89-style-record set .doc to the source's width and invoice_0002's
    beside_agreement fell 0.640 -> 0.295, the hard tier, for height_ratio
    1.63 -> 1.60 on that one document and nothing on the other four. Isolated by
    re-rendering that run's own IR four ways with the palette held fixed. The
    cause is flex:1 1 12rem approximating the source's columns by accident, so
    it is A2's band model. page_px is in the IR, traced and round-tripped;
    render._style_css holds the note and what would have to become true.
  - Zone.align does NOT move either. It stays in A2, even though ADR 0005's
    table lists alignment here.

Reuse rather than re-implement: preprocess.ground_level/ground_is_dark (the shared
modal-background test, written in A-1), preprocess.content_ink/ink_bands for the
type scale, scoring._modal for the bucketed mode, preprocess.zone_pixels for crops.

Font family is de-prioritised and does not gate the phase. Cheap guess, sans
fallback, move on.

Gate: height_ratio toward 1.0 across the sweep set, palette delta falls, and
T1/T2/T3 do not regress against tests/frozen/a1-checkpoint/scores.json — pass it
to the report with --previous, because debug/runs is cleared and the notch lives
in the repository now. Expect width alone not to close the height gap: menu_0012
is 760px wide, inside the house column, and still sits at 2.77.
```

---

## Phase A0 — stop the bleeding — **DONE 2026-09-22, gate MET**

Ran 2026-09-22, after Thread 2/B, against
`tests/frozen/a0-checkpoint/scores.json`. **Outcome, the reverted caption-crop
cut and the two corrections to the problem statement are in spec 0007 under
"A0's result".** Commit `cc39022`. The prompt below is kept as the record of
what was asked; A1's prompt is the next section.

**Its pre-registered `T1 = 1.00` gate is disproved, not merely moved.**
`receipt_0010` sits at 0.175 recall and `catalogue_0015` at 0.571, and none of
A0's three faults touches either. The prompt below asks for the replacement to
be set from the checkpoint's own numbers, before any code changes.

**One warning that matters more than the rest**, because it is this project's
own recurring fault pointed at A0: `Completeness.duplicated` — the obvious
thing to gate the doubled Title on — **under-reports it**. It totals 29
repeated strings over twelve documents and comes back **empty for
`report_0011`, which prints all eight of its numbered headings twice** and
whose `output_tokens` are 477 against the source's 459. Gating on a measure
that cannot see the fault is exactly what spec 0007 was opened over.

```
Read CLAUDE.md's "READ THIS FIRST", then docs/status.md, then
docs/specs/0007-look-like-the-document.md (authoritative where anything
disagrees). Implement Phase A0 only. Stop at its gate and report.

Branch scaffold at 09f56d3. 699 tests, mypy src/ clean. Thread 2/B is closed
bar the type scale; do not redo any of it.

SET THE GATE FIRST, FROM MEASUREMENTS, BEFORE CHANGING ANY CODE.
A0's pre-registered T1 = 1.00 is disproved: receipt_0010 is at 0.175 recall and
catalogue_0015 at 0.571 and A0 touches neither. tests/frozen/a0-checkpoint/ is
the starting notch (means: recall 0.851, precision 0.934, join_recall 0.809,
tau 0.936). Propose the replacement, say what each clause is for, and get it
agreed before you write anything.

Beware the obvious gate. Completeness.duplicated totals 29 over twelve
documents and is EMPTY for report_0011, which visibly prints all eight of its
numbered headings twice. Find out why before gating on that field. If it
cannot see the fault, fix the measure or gate on something else — improving a
measure that is blind in a direction is unconstrained in that direction, which
is the whole reason this spec exists.

THREE FAULTS, ALL DIAGNOSED. Take them in this order:

1. THE DOUBLED TITLE — 12 of 15 documents, the corpus's most pervasive visual
   fault. A Zone carrying a Title must not also carry a Block repeating it.
   DTH_CAPTION_PASS sets Zone.title and nothing removes the corresponding
   Block. Worst on report_0011 (8 headings, each twice, the duplicate rendered
   LARGER than the title level so the hierarchy inverts).

2. wire._without_empty_rows FILTERS ON `if row.cells`, which is truthy for
   ['', '', '', '', '']. sample_table_0003 gets a 17th row of empty strings.
   The drop tests cell COUNT, not cell CONTENT. Fix the condition. DO NOT
   DELETE THE NET — four runs established the behaviour it guards, two of
   which lost a whole table and the 385.00 Probe to one such row.

3. DTH_CAPTION_PASS withholds the caption band from the KIND question but NOT
   from the Extractor's crop, while with_grid(titled=) subtracts the caption's
   printed line from the row budget. The crop still shows 17 lines, the prompt
   says "return exactly 16", and the model drops the real header and keeps the
   caption. sample_table_0003 still has no column headers today — verify that
   in the current output before you touch it. Arithmetic and picture must both
   agree with the page, not merely with each other.

MEASURING IT. A0 changes prompts and extraction, so it needs a real sweep:
FIXTURE=sweep tools/iterate.sh <label>, all fifteen, ~90 minutes. Alessandro
has said he will wait. tools/remeasure_style.py DOES NOT serve A0 — it reuses
the model's answers and cannot move anything A0 changes. Say which of the two
produced any number you report.

REVIEWING IT. Use the visual-review skill, with --previous pointing at the
baseline you took. Read every sheet. The doubled title is a "content" major on
9 of 15 today; it should be a match afterwards.

STANDING RULES.
- Never cite or analyse a past run. Only a run taken in your session counts.
  Three exceptions, all committed: tests/frozen/run84/,
  tests/frozen/a1-checkpoint/, tests/frozen/a0-checkpoint/.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the two dormant safety nets or the four shipped defaults.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html.
- Rubric judgements are pairwise and in-session only.

DEFERRED — do not "fix" and do not read as new faults: column collapse (A2),
the type scale (its own increment), Zone.align (A2), figures as placeholders
(A3), cv_0013's clipped sidebar values (A2, render.PAIRS_REM says why).

ALSO OPEN, NOT A0's, DO NOT ABSORB THEM:
- statement_0006's 41 near-identical caveat lines should aggregate to one.
  Ours, from A-1, no model time. Offer it; do not do it inside A0.
- receipt_0010 is the worst document (0.175 recall) and has one untested lead:
  preprocess.resize_long_edge never enlarges, and receipt_0010 rectifies to
  335x547, so the extractor sees ~300px across 19 monospace lines. A decision
  change, not a perception instruction. One document, ~6 min to probe.
- nonlatin_0014's dark-blue table header row renders unshaded. Do not build a
  third detector; point chrome()'s existing title-band measurement at the row
  RowRole.header already names.

Ask before binding anything docs/status.md leaves open.
```

---

## Phase A1 — inline runs, and hard line breaks — **DONE 2026-09-25, gate NOT met**

**Result, in brief.** The reflow half shipped and is measured clean: corpus
`hard_breaks` **57 → 8** (the 8 remaining are real address breaks),
`join_recall` **0.8128 → 0.8229**, ratchet holds. The inline half was asked
twice — **inside** the Extractor prompts, where it crossed the ratchet on seven
documents and was reverted, and then as a **separate pass**
(`DTH_INLINE_PASS`), which holds the ratchet and reaches **8 of 42**.

**Clause 1 wanted 21 and is the one open clause.** The model returns no
`strong`, `em` or `mark` anywhere and nothing in `pairs` or `table`, so the
ceiling is the model rather than the plumbing. `docs/status.md` carries the
full result, the guards and their measured thresholds.

**The lesson worth carrying into A2:** *where* you ask is a bigger lever than
*how* you ask. Same model, same words, moved out of the Extractor prompts into
a pass of its own — from seven documents crossing the ratchet to none.

The prompt A1 was run from follows, kept as record.


```
Implement Phase A1 of spec 0007. Stop at its gate and report.

Read, in order: CLAUDE.md's "READ THIS FIRST", then docs/status.md, then
docs/specs/0007-look-like-the-document.md. The spec is authoritative where
anything disagrees.

Branch scaffold, head cc39022. 731 tests pass, mypy src/ clean. Phase A0 closed
2026-09-22 with its gate met; do not redo any of it.

DECIDE THE NOTCH FIRST, BEFORE ANY CODE. docs/status.md has a section called
"The notch" stating the mechanism, the current state and the open decision in
full. A1 currently ratchets against tests/frozen/a0-checkpoint/ — the floor A0
CLEARED, not the level A0 REACHED — so A1 could hand back A0's precision gain
(0.9765 -> 0.9342) and still pass. tests/frozen/a0-result/ holds A0's actual
scores and is committed and ready. Put the choice to Alessandro and get an
answer before you write anything.

SET A1'S GATE FROM MEASUREMENTS, BEFORE CHANGING ANY CODE. Propose it, say what
each clause is for, and get it agreed. A0's gate is the model: three of its five
clauses were counts of a named structure rather than ratios, because a ratio
cannot say WHICH strings came back. join_recall is the axis A1 moves and it sits
at 0.8128, the weakest of the four — but do not gate A1 on join_recall alone.
Spec 0004 pre-registered a gate on exactly the fields its change was designed to
move, passed every one, and shipped a regression.

A1'S SCOPE, TWO MIGRATIONS OF THE SAME STRUCTURES:

1. Cell.text: str becomes a sequence of runs (text | link | code | em | strong |
   mark). Currently a 100% loss — links, code spans and badges are absent from
   every document that has one. Raises T6 from zero. sample_semantic_0005 and
   sample_css_0004 are the documents with the most to gain.

2. Block.lines: list[Cell] joined by <br> becomes reflowable text. Moved here
   from A0 on 2026-09-22 because both rewrite the same structures.

   The evidence is in A0's review: newsletter_0008 renders "the borough council
   con-" / "firmed on Tuesday", carrying the SOURCE's justified hyphenation into
   the output as real breaks; report_0011 renders "prepared under the terms" /
   "of the 1987 order". invoice_0001 is the other half — "Invoice #: 123" is cut
   into a label "Invoice" and a value "#: 123" and scores 1.000 recall, 1.000
   precision, 1.000 tau. Only join_recall and Completeness.broken_joins see it.

KEEP THE PER-LINE CELLS REACHABLE. They are what Correction anchors to and what
makes each reading a ground-truth label. Reflowing must not delete them.

A1 changes the IR and the mapper, so it needs a real sweep — all fifteen,
~90 min. tools/remeasure_style.py does NOT serve A1. If a change is entirely
downstream of the model, verify it first by replaying a run's recorded answers
through the shipping mapper — validated on 2026-09-22 to four decimal places on
every mean — and only then spend the sweep.

Review with the visual-review skill, --previous against your own baseline.

OPEN, NOT A1'S, DO NOT ABSORB THEM:
- The across-Zone title echo. menu_0012 prints "To begin" twice and
  darkdeck_0009 prints a caption "AVAILABILITY" above a table whose first column
  header is "AVAILABILITY". A0 closed the WITHIN-Zone echo; this is the other
  one and nothing owns it.
- statement_0006's 41 near-identical caveat lines (A-1 residue).
- receipt_0010's untested preprocess.resize_long_edge lead — 0.175 recall,
  rectifies to 335x547, ~6 minutes to probe.
- nonlatin_0014's dark-blue table header row.
- catalogue_0015 at 0.571 recall, loss NOT declared. A-1 established the
  pipeline cannot declare loss inside a line and that two pixel-side detectors
  were built and rejected. Do not build a third without a new kind of evidence.

DEFERRED — do not "fix" and do not read as new faults: column collapse (A2), the
type scale (2/B, its own increment), Zone.align (A2), figures as placeholders
(A3), cv_0013's clipped sidebar values (A2).

STANDING RULES:
- Never cite or analyse a past run. Only a run taken in this session counts.
  Four exceptions, all committed files: tests/frozen/run84/, a1-checkpoint/,
  a0-checkpoint/ and a0-result/.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the three wire-level row nets or the four shipped defaults.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html.
- Any reviewed run is a full sweep, all fifteen.
- Rubric judgements are pairwise and in-session only.
- Ask before binding anything docs/status.md leaves open.
```

---

## Phase A2 — re-scoped 2026-09-25 — **DONE 2026-09-25, gate MET**

**Result, in brief.** Sweep `A2-10-enclosed-sweep`, seven of seven clauses, the
ratchet held on all fifteen. **The enclosure was the detector's, not the
snap's**: `attach_trailing_rows` and `attach_headings` grew a box over a
neighbour and left the neighbour standing, and the snap returned those boxes
unchanged. All four enclosed Zones were duplicates of text the enclosing Zone
already read. `detector.without_enclosed` drops a box lying wholly inside
another, by its edges, after the unions — exactly those four go.

**The sweep reproduced the offline prediction on every scored field of every
document**, so an upstream change that only *removes* a Zone is measurable by
replay after all. Clause 4 was restated before the sweep, and clause 2 as drafted
below would have passed without moving a box. `docs/status.md`, "Phase A2's
result", has the gate and the numbers; `0007-a2-measurements.md` §8 has the
evidence.

**The lesson worth carrying into A3:** *a check that reports a fault is not
where the fault is.* The snap was blamed on three documents for a step it
performed without moving a box, because it was the only thing that ran
`validate_bands`. Before fixing the component a finding names, run the stages
one at a time and see which one introduces it.

The prompt A2 was run from follows, kept as record.

**Its first scope did not survive its own measurements.** A2 was written as
*geometry: columns, alignment, clipping*, on the premise that side-by-side
content stacks because the renderer stacks it. Measured before any code was
written: **two thirds of the fault is inside one Zone**, four renderers were
built and scored offline and **the shipped one wins**, and the two routes that
did work are blocked by a fault that is neither columns nor alignment.
`docs/specs/0007-a2-measurements.md` is the full record and **is required
reading before this prompt**. The column model and the merged Zone are **closed
unbuilt**, with evidence, the way spec 0006's Change 3 closed.

**Three wins shipped on 2026-09-25**, all proved offline against
`tests/frozen/a1-result/`: the sparse numeric column, the clipped sidebar, and
the snap finding surfaced in `report.html`. What is left is one change, and it
is the only thing in A2 worth a sweep.

The prompt A2 was originally run from is kept below the new one, as record.

```
Implement Phase A2 of spec 0007, re-scoped. Stop at its gate and report.

Read, in order: CLAUDE.md's "READ THIS FIRST", then docs/status.md, then
docs/specs/0007-a2-measurements.md — which is A2's own evidence and says what
has already been tried and refused — then
docs/specs/0007-look-like-the-document.md. The spec is authoritative where
anything disagrees.

Branch scaffold, head 6369bd6. 786 tests pass, mypy src/ clean. Phase A1 closed
2026-09-25 with its gate NOT met on clause 1 only; do not redo any of it.
A2's own three offline wins shipped in that commit — do not redo them either.

THE NOTCH IS SETTLED. Ratchet against tests/frozen/a0-result/scores.json:

    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
        --documents sweep --previous tests/frozen/a0-result/scores.json

--documents sweep is not optional. Without a fixtures.txt in the run directory
the report silently defaults to the iterate five and scores a third of the
corpus.

MEASURE OFFLINE FIRST, AGAINST THE FROZEN CONTROL. tests/frozen/a1-result/
holds the fifteen documents the shipped configuration produced AND their
scores, and the scores re-derive from the documents exactly — 15 documents,
0 differing fields. Copy each documents/<name>.html to
debug/runs/<label>/dump/qwen3-vl_4b/<name>/document.html and score it; the
directory's README has the recipe. One cycle is about 50 seconds and calls no
model. A renderer or mapper change that has not been through that loop has not
been measured.

A2'S SCOPE — ONE CHANGE. THE ENCLOSED ZONE.

A Band is a horizontal stripe and its Zones are its columns, so two Zones in
one Band that overlap horizontally are not two Zones. There are four such
pairs, in three documents, each an exact containment:

    cv_0013        band 0   0.38-0.58 contains 0.38-0.57
    menu_0012      band 1   0.04-0.96 contains 0.22-0.30
    statement_0006 band 2   0.03-0.97 contains 0.64-0.70
    statement_0006 band 2   0.03-0.97 contains 0.91-0.96

They are one fault under two symptoms, and both matter:

  - wire.validate_bands refuses the snapped geometry on exactly these three
    documents, so DTH_SNAP_ZONES — one of the four shipped defaults — applies
    to twelve of fifteen. report.html now says so on every run; that surface
    was built on 2026-09-25 and is where you read the count.
  - they block the one renderer change that helped. Giving a Band's Zones a
    flex-grow from their measured widths lifted cv_0013's beside_agreement
    0.450 -> 0.556, and the guarded form cannot apply it to cv_0013 because
    band 0 is one of the four. Both numbers were taken against the control as
    it stood BEFORE the wrap fix; cv_0013 now sits at 0.474, so treat 0.556 as
    evidence that the route is live and NOT as a target — re-measure it.

The rule needs no detector and no model: it is arithmetic on boxes that are
already in the IR. What it must decide is what to DO with an enclosure — drop
the inner box, merge it into the outer, or re-band it — and that decision
changes which crops are extracted, which is upstream of the model. So the rule
is developed and measured offline on the frozen control's own boxes, and only
then does it cost a sweep.

DO NOT TRADE T1 FOR GEOMETRY. Dropping an enclosed Zone deletes whatever was
read from it. The accepted interim state has always been "content complete and
reading order correct, in one column". The ratchet enforces it and has already
caught regressions worth a single word.

SET A2'S GATE FROM MEASUREMENTS, BEFORE CHANGING ANY CODE. Propose it and get
it agreed. Three things this phase already learned about writing one:

  - Make most clauses COUNTS OF NAMED STRUCTURES, not ratios. A0's model.
  - alignment_agreement is NOT gateable, and that is measured rather than
    suspected: flipping 42 cells to right-aligned in statement_0006 moved it
    0.935 -> 0.935, because a right-aligned cell in a cramped table has no
    slack and re-reads as `fill`. The ratio is a function of our own column
    widths. Clause 5 below is the shape that works.
  - A1's clause 4 was a proxy and fired on a document where the fault had not
    happened. State the fault directly and per document.

A PROPOSED GATE, TO ARGUE WITH RATHER THAN ADOPT:

  1. No Band holds two Zones whose horizontal spans overlap. 4 pairs -> 0,
     the four named above, per document.
  2. DTH_SNAP_ZONES applies to all fifteen. report.html's snap line reads
     "applied everywhere"; it reads "did not apply to 3 of 15" today.
  3. Named side-by-side pairs that must come back, listed per document BEFORE
     the run. cv_0013's 5 cross-Zone misses are the ones the enclosure blocks.
  4. layout.clipped stays at 0 for all fifteen, and no document rises above its
     source_clipped.
  5. Every table column whose non-empty data cells are all numbers is
     right-aligned — checked in the DOM, counted, not via _alignment. It is 21
     such columns over 18 table Zones today, 254 cells; none may stop being
     right-aligned.
  6. The ratchet holds against a0-result on all four legs, all fifteen.
  7. Structure, tests, mypy clean.

CLOSED. DO NOT REOPEN EITHER WITHOUT NEW EVIDENCE:

  - The column model. Four renderers measured offline in one sitting, all worse
    on the hard tier: proportional grid tracks cost beside_agreement
    0.7265 -> 0.6814 and trebled clipping; merging Bands into column runs cost
    tau. Height was eliminated as the explanation — held at height_ratio
    1.0284, beside_agreement was still 0.6628, below the control. Measurements
    doc section 2 and 3.
  - The merged Zone. menu_0012's two menu sections as one table and form_0007's
    two-column form as one pairs list are 49 of the 66 inside-Zone pairs, and
    three pixel-side tests were built and none separates them. form_0007's Zone
    has ZERO interior gutters. menu_0012's one gutter is 38px against a 1px
    runner-up locally, and 22 Zones that must NOT be split rank above it by
    share. A third test — do the printed lines straddle the gutter — puts
    menu_0012 at 0.86, between two genuine tables. DO NOT BUILD A FOURTH
    DETECTOR. If it is reopened it is a MODEL question asked as "how many
    regions", and its own phase. Measurements doc section 7.

OPEN, NOT A2'S, DO NOT ABSORB THEM:
- Reading direction for a multi-Band column region. An IR gap: the Band model
  says what is beside what and never which way a region is read, and the same
  merge takes newsletter_0008 from tau 0.832 to 0.968 and catalogue_0015 from
  0.943 to 0.562. Measurements doc section 4.
- The across-Zone title echo (menu_0012 "To begin" twice, darkdeck_0009
  "AVAILABILITY").
- statement_0006's 41 near-identical caveat lines.
- receipt_0010 at 19.8% words kept, and its untested resize_long_edge lead.
- nonlatin_0014's dark-blue table header row, and its ~8.6% invented words.
- catalogue_0015 at 61.7%, loss NOT declared. A-1 established the pipeline
  cannot declare loss inside a line and that two pixel-side detectors were
  built and rejected. Do not build a third without a new kind of evidence.
- invoice_0001's "Invoice" / "#: 123" — a Pairs label/value boundary.
- A confirming sweep for A1's shipped 8 of 42, and its one false mark.

DEFERRED — do not "fix" and do not read as new faults: the type scale (2/B, its
own increment, and A2 measured that nothing here waits on it), figures as
placeholders (A3), Thread 3/C.

STANDING RULES:
- Never cite or analyse a past run. Only a run taken in this session counts.
  Five exceptions, all committed files: tests/frozen/run84/, a1-checkpoint/,
  a0-checkpoint/, a0-result/ — the floor — and a1-result/ — the control.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the four shipped defaults or the three wire-level row nets.
- Marking may never change the words: wire._runs_for can only cut the string it
  is given and ir.Cell.runs discards Runs that do not spell the text back.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html.
- Any reviewed run is a full sweep, all fifteen.
- Rubric judgements are pairwise and in-session only.
- Ask before binding anything docs/status.md leaves open.
```

### The three wins shipped on 2026-09-25

All measured offline against `tests/frozen/a1-result/`, one change apart, in
one sitting. Corpus: **`clipped` 1 → 0**, `beside_agreement` **+0.0033**,
`alignment_agreement` **+0.0019**, every T1 leg and `tau` **unmoved**, ratchet
clean.

| change | what it fixes |
|---|---|
| `render._numeric_columns` skips empty cells | a sparse money column votes on the cells that hold something. `statement_0006`'s "Paid out" was 5 numbers in 40 rows and stayed left; it is 5 of 5 among the non-empty. **42 cells**, corpus `.num` 212 → 254. |
| `render._speaks_for_its_column` | one cell decides a column only when it *is* the column. `cv_0013`'s `2015` above three blanks right-aligned eight cells the source does not. Changes **exactly one** of the corpus's eighteen table Zones and leaves `invoice_0001`'s genuine one-row table alone. |
| `dl.pairs dt, dl.pairs dd { overflow-wrap:anywhere }` | a value too long for its column wraps instead of being hidden. `section.filled` sets `overflow:hidden`, so `cv_0013`'s sidebar cut off an email at 256px of the 368px it wanted — recall said present, the picture did not contain it. |
| `report._snap_note` / `_snap_html` | the snap rejection, read off `trace.json` and shown beside the ratchet and the honesty gate. Reads **"did not apply to 3 of 15"** today and names the enclosure on each. Off the trace rather than into the IR on purpose: a finding drawn in the page would move `height_ratio` for a reason that is not about the document. |

### A2's original prompt, kept as record

```
Implement Phase A2 of spec 0007. Stop at its gate and report.

Read, in order: CLAUDE.md's "READ THIS FIRST", then docs/status.md, then
docs/specs/0007-look-like-the-document.md. The spec is authoritative where
anything disagrees.

Branch scaffold, head a720482. 769 tests pass, mypy src/ clean. Phase A1 closed
2026-09-25 with its gate NOT met on clause 1 only; do not redo any of it and do
not try to raise clause 1 as part of A2 — it is listed separately in
docs/status.md under "Raising clause 1, if anyone wants to".

THE NOTCH IS SETTLED. Ratchet against tests/frozen/a0-result/scores.json. It is
not an open question any more and it is not to be re-cut to make a run pass:

    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
        --previous tests/frozen/a0-result/scores.json

SET A2'S GATE FROM MEASUREMENTS, BEFORE CHANGING ANY CODE. Propose it, say what
each clause is for, and get it agreed. Two things A1 learned about writing one:

  - A0's model still holds: make most clauses COUNTS OF NAMED STRUCTURES, not
    ratios. A ratio cannot say WHICH thing came back.
  - A1's clause 4 was written as a proxy — "hard_breaks must not fall below
    source_hard_breaks" — and it fired on a document where the fault had not
    happened, because that count ignores WHERE the breaks are. State the fault
    directly and per document, or the clause will fail for the wrong reason.
    Do not gate A2 on beside_agreement alone; spec 0004 pre-registered a gate
    on exactly the fields its change moved, passed every one, and shipped a
    regression.

A2'S SCOPE — geometry only:

1. Column collapse. Side-by-side content renders stacked. beside_agreement as
   A2 begins: form_0007 0.06, catalogue_0015 0.26, menu_0012 0.35, cv_0013
   0.45, newsletter_0008 0.48, invoice_0002 0.64. This is why menu_0012 and
   newsletter_0008 render roughly TWICE as tall as their sources (height_ratio
   2.34 and 1.99) — the height is a symptom, so do not chase it directly.

2. Zone.align.

3. cv_0013's clipped sidebar values (layout.clipped is 1 there).

DO NOT TRADE T1 FOR COLUMN SHAPE. The accepted interim state has always been
"content complete and reading order correct, in one column". A2 improves the
shape of content that already converts; it may not lose a word to do it. The
ratchet enforces that and it has already caught two real regressions this
phase, each on a single word.

MEASURE BEFORE YOU BUILD, AND CHECK THE HARNESS FIRST. A1's whole method:
offline replay of a run's recorded answers through the shipping mapper, but
ONLY after proving the replay reproduces tests/frozen/a0-result/ exactly.
Geometry is largely downstream of the model — the detector's boxes and the
renderer's layout both are — so a great deal of A2 may be measurable with no
model running at all. tools/remeasure_style.py re-renders from a sweep's own
embedded IRs. Establish what A2 can measure offline BEFORE booking a sweep.

A KNOWN A2 FINDING, ALREADY MEASURED, DO NOT REDISCOVER IT: DTH_SNAP_ZONES is
silently not applying to four of the fifteen documents. It moves boxes onto
their ink and then invalidates the Bands, so those four convert on unsnapped
geometry. Two shapes: a full-width Zone with a narrow box strictly inside it,
and two Zones snapping onto nearly the same span. Both are questions about
GROUPING before they are questions about the snap. The snap is one of the four
shipped defaults and must not be deleted — the finding is that it is not being
APPLIED, which is a different fact from it being harmful. Surface it in
report.html as a finding rather than leaving it in bakeoff.stderr.txt.

OPEN, NOT A2'S, DO NOT ABSORB THEM:
- The across-Zone title echo (menu_0012 "To begin" twice, darkdeck_0009
  "AVAILABILITY").
- statement_0006's 41 near-identical caveat lines.
- receipt_0010 at 19.8% words kept, and its untested resize_long_edge lead.
- nonlatin_0014's dark-blue table header row, and its ~8.6% invented words.
- catalogue_0015 at 61.7%, loss NOT declared. A-1 established the pipeline
  cannot declare loss inside a line and that two pixel-side detectors were
  built and rejected. Do not build a third without a new kind of evidence.
- invoice_0001's "Invoice" / "#: 123" — a Pairs label/value boundary.
- A confirming sweep for A1's shipped 8 of 42, and its one false mark.

DEFERRED — do not "fix" and do not read as new faults: the type scale (2/B, its
own increment), figures as placeholders (A3), Thread 3/C.

STANDING RULES:
- Never cite or analyse a past run. Only a run taken in this session counts.
  Four exceptions, all committed files: tests/frozen/run84/, a1-checkpoint/,
  a0-checkpoint/ and a0-result/ — the last being the floor.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the four shipped defaults or the three wire-level row nets.
- Marking may never change the words: wire._runs_for can only cut the string it
  is given and ir.Cell.runs discards Runs that do not spell the text back. Both
  checks stay.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html.
- Any reviewed run is a full sweep, all fifteen.
- Rubric judgements are pairwise and in-session only.
- Ask before binding anything docs/status.md leaves open.
```

---

## Phase A3 — figure pixels — **DONE 2026-09-26, gate MET**

**Measured 2026-09-25 from `tests/frozen/a2-result/`, before any A3 code.**
The scorer counts a figure as an `<img>`, `<svg>` or `<canvas>` the page
actually draws. By that measure the corpus loses exactly **two**, and they are
two different faults:

| document | the figure | what happens to it | where the fix sits |
|---|---|---|---|
| `invoice_0001` | the Sparksuite logo, an `<img>` | a FIGURE Zone exists (`graphic_kind` `logo`) and renders as a dashed `<figure class="omitted">` captioned with its read text | **downstream** of the model — the crop is already in hand |
| `invoice_0002` | the black ACME tile, an `<img>` | the detector finds it (`picture`, 0.76) and `outermost` drops it inside a larger `picture` box that also holds the company text; that box becomes a **prose** Zone | **upstream** — a grouping change that moves a crop |

Two more that the scorer does not count, and both matter to the eye:

- **`receipt_0010`'s barcode** is a CSS `div` in the source, so it is not a
  scored figure. It has a FIGURE Zone and renders as a placeholder reading
  `logo`.
- **The placeholders' own text is invented text.** `sparksuite` is
  `invoice_0001`'s *only* invented token, and `logo` is one of
  `receipt_0010`'s. The source holds neither as text — only as pixels.

```
Implement Phase A3 of spec 0007. Stop at its gate and report.

Read, in order: CLAUDE.md's "READ THIS FIRST", then docs/status.md, then the
Phase A3 paragraph of docs/specs/0007-look-like-the-document.md, then section 8
of docs/specs/0007-a2-measurements.md for its METHOD (the layout stage run
offline, one step at a time). The spec is authoritative where anything
disagrees.

Branch scaffold, at or after c4e9ffb. 796 tests pass, mypy src/ clean. A2
closed 2026-09-25 with its gate met; do not redo any of it.

THE FLOOR IS tests/frozen/a2-result/, and it is also the control:

    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
        --documents sweep --previous tests/frozen/a2-result/scores.json

--documents sweep is not optional. The directory holds the fifteen documents
beside their scores; they re-score with 0 differing fields and re-render
byte-identical. Its README has the recipe.

WHAT A3 IS. A FIGURE Zone carries its crop, not just a graphic_kind label, and
the render draws it. The handover's A3 section has the measurements: two lost
figures, two different faults.

  (a) invoice_0001's logo and receipt_0010's barcode already ARE FIGURE Zones
      and render as placeholders. Carrying the crop is downstream of the model.
      Measure it offline against a2-result BEFORE any sweep — and prove the
      harness first: re-rendering a2-result's IRs unchanged must return all
      fifteen byte-identical. The crop comes from rectify(<png>) and
      preprocess.zone_pixels, which is what the Conversion used.
  (b) invoice_0002's ACME tile is detected (picture, 0.76) and swallowed by
      outermost into a larger picture box holding the company text. Splitting
      it out NARROWS the text Zone's crop, so that Zone's reading can change:
      it costs a sweep and the ratchet applies. The layout stage runs offline
      in ~10 seconds for all fifteen — prove it reproduces a2-result's boxes
      first, then measure which documents any rule touches. A2 found a rule
      that changes exactly the boxes it names is worth more than a clever one.

DECIDE ON ENTRY, WITH ALESSANDRO, BEFORE ANY CODE:
  - How the IR carries pixels. Embedded (e.g. base64 PNG in the Zone) keeps the
    document and report self-contained and round-trips through
    Document.from_json; a file beside the document does not. Say what each
    costs in IR size across the corpus — measure it.
  - What happens to a placeholder's read text. "SPARKSUITE" and "logo" are
    invented tokens today. Drawing the pixels instead would remove them; keeping
    the reading as alt text keeps it reachable without printing it.
  - Whether (b) is in A3 or its own change. It is a grouping fault, not a
    rendering one.

SET A3'S GATE FROM MEASUREMENTS, BEFORE CHANGING CODE, and get it agreed. Make
most clauses counts of named structures, per document. A proposal to argue
with, not adopt:
  1. figures_lost 2 -> 0, named: invoice_0001's logo, invoice_0002's tile.
  2. receipt_0010's barcode is drawn from its pixels.
  3. The invented placeholder words go: sparksuite, logo.
  4. Every document with no FIGURE Zone and no changed box renders
     byte-identical to a2-result.
  5. The ratchet holds against a2-result, four legs, all fifteen.
  6. Visual review, all fifteen sheets, --previous against the control.
  7. Structure, tests, mypy.

THE LESSON A2 PAID FOR: the check that reports a fault is not where the fault
is. Run the stages one at a time and find the one that introduces it before
fixing the one that names it.

CLOSED — DO NOT REOPEN WITHOUT A NEW KIND OF EVIDENCE: the column model and
proportional widths, the merged Zone (menu_0012, form_0007), alignment_agreement
as a gate. docs/status.md "Closed, with evidence" says why.

OPEN, NOT A3'S, DO NOT ABSORB THEM (docs/status.md "Open"):
- darkdeck_0009's AVAILABILITY across-Zone echo.
- nonlatin_0014's overlapping Zones (re-reads three pairs) and its unshaded
  table header row.
- statement_0006's 41 near-identical caveat lines.
- receipt_0010 at 19.8% words kept, and its untested resize_long_edge lead.
- catalogue_0015 at 61.7%, loss not declared — do not build a third detector.
- invoice_0001's "Invoice" / "#: 123" Pair boundary, and A1's false mark 12345.

DEFERRED — do not "fix" and do not read as new faults: the type scale (2/B's
own increment), Thread 3/C, column collapse inside one Zone.

STANDING RULES:
- Never cite or analyse a past run. Only a run taken in this session counts.
  The exceptions are the committed tests/frozen/ directories, each for what its
  README says it is.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the four shipped defaults or the three wire-level row nets.
- Marking may never change the words: wire._runs_for and ir.Cell.runs both stay.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html.
- Any reviewed run is a full sweep, all fifteen.
- Rubric judgements are pairwise and in-session only.
- Ask before binding anything docs/status.md leaves open.
```

### Outcome — 2026-09-26, sweep `A3-10-figure-pixels-sweep`: gate MET, 8 of 8

**Decided on entry, with Alessandro:** pixels embedded in the IR (a file
beside the document would not survive the copy into `tests/frozen/`); what is
read off a Graphic becomes `alt`, not printed; the ACME tile in A3, in the
same sweep, because a sweep was needed anyway to prove the pixels arrive
through a Conversion and the two changes touch disjoint documents.

| # | clause | result |
|---|---|---|
| 1 | `figures_lost` 2 → 0, named | 0 — `invoice_0001`'s logo and `invoice_0002`'s tile drawn |
| 2 | `receipt_0010`'s barcode drawn from its pixels | yes |
| 3 | `sparksuite` and `logo` gone | yes; precision 1.000 on both documents |
| 4 | restated — the twelve untouched documents byte-identical outside the embedded IR, and inside it differing only by `"pixels": null` | 12 of 12 |
| 5 | `invoice_0002`'s address Zone still reads its four lines | yes, verbatim and in order — as four blocks where the floor had one |
| 6 | ratchet vs `a2-result`, four legs, fifteen | holds; nothing falls |
| 7 | visual review, `--previous` the control | 3 `better`, 12 `same`, no `worse` |
| 8 | tests, mypy | 809 pass, clean |

**What the measurements corrected before any code:**

- **The crop is not `zone_pixels`.** It pads for the reader's sake, and on the
  ACME tile the pad pulls in `Acm`, `Soft`, `Field`, `info` from the address
  beside it. The drawn crop is the unpadded box — which holds all the ink on
  all three figures, none in a 3px ring outside — on `Rectified.plain`.
- **Clause 4 as first written could not hold.** A rule added to `STYLESHEET`
  changes all fifteen documents' bytes, so the figure's styling is inline; and
  a new `Zone` field puts `"pixels": null` into every embedded IR, so the
  clause was restated before the sweep and put to Alessandro.
- **`outermost` introduced the tile's loss**, found by running the detector's
  steps one at a time. The general shape — a container over a higher-scored
  box — is every panel over its lines. The narrow one, a `picture` over a
  higher-scored `picture` with ink outside it, fires on `invoice_0002` alone:
  2,243 px against exactly 0 on the other two candidates. `invoice_0001`'s
  logo is why the score test is needed, `darkdeck_0009`'s card row why the ink
  test is.

**The sweep matched the offline prediction byte for byte on 14 of 15.**
`invoice_0002` moved more than predicted: its narrowed crop read the company
block as the source's four lines rather than one address block, which is
where tau 0.849 → 1.000 and beside 0.640 → 0.854 come from — and where the one
new fault comes from: `Acme Corporation` read as a `heading`, drawn as the
largest text in the header band. Carried to the open issues.

**A comparison mistake worth not repeating.** Reading the floor's IR back
through today's `Document` adds the new field to it too; strip it from both
sides, or compare the raw JSON, before calling two IRs different.

**Floor moved to `tests/frozen/a3-result/`, 2026-09-26** — it dominates
`a2-result` per document on every ratcheted leg.

---

## Next — the open issues, one at a time — **NEXT**

`docs/status.md` "Next" lists seven, cheapest first. **The first four need no
model call**: each is downstream of the model, so it is measured against
`a3-result` offline, one change apart, in about fifty seconds. The last three
move a crop or ask the model something, and each costs a sweep.

```
Work the open issues of spec 0007. Take them one at a time, in the order
docs/status.md "Next" gives, starting with the first four. Stop after the
fourth — or earlier, at any issue whose measurements say it needs model time —
and report.

Read, in order: CLAUDE.md's "READ THIS FIRST", then docs/status.md, then the
Phase A3 "Outcome" in docs/specs/0007-handover.md. The spec is authoritative
where anything disagrees.

Branch scaffold, at or after the commit closing A3. 809 tests pass, mypy src/
clean. Do not redo any of A3.

THE FLOOR IS tests/frozen/a3-result/, and it is also the control:

    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
        --documents sweep --previous tests/frozen/a3-result/scores.json

--documents sweep is not optional. Prove the control before using it:
re-rendering its IRs through render() must return 15 of 15 byte-identical, and
scoring them straight out of the directory must give 0 differing fields. Its
README has the recipe.

THE FOUR, EACH MEASURED OFFLINE AGAINST a3-result, ONE CHANGE APART:
  1. statement_0006's 41 near-identical caveat lines aggregate to one.
  2. nonlatin_0014's dark-blue table header row renders on white. Point
     chrome()'s title-band measurement at the row RowRole.header names; do not
     build a detector.
  3. darkdeck_0009's across-Zone echo: caption AVAILABILITY above a table
     whose first column header is AVAILABILITY. _without_title_echo only
     compares a Block with its own Zone's Title.
  4. invoice_0002's "Acme Corporation", new at A3: a bold body-size line read
     as a heading block and drawn as h1, now the largest text in the header
     band. If the honest fix is sizing headings from their own ink, that is
     the deferred type scale (2/B) — say so rather than smuggle it in.

FOR EACH ONE, BEFORE ANY CODE:
  - Find the stage that introduces it, not the one that reports it.
  - Measure which documents a candidate rule touches, across all fifteen. A
    rule that changes exactly what it names beats a clever one.
  - Propose a gate of counts of named structures, per document, and get it
    agreed with Alessandro. Always include: the ratchet holds against
    a3-result on four legs, all fifteen; every document the rule does not
    name is unchanged — and say precisely what "unchanged" means before
    measuring (outside the embedded IR? a new IR field puts a key in every
    document; a STYLESHEET rule changes every document's bytes).

A wire rule must also be proven to run inside a Conversion — a replayed
Conversion test — because a rule measured on IRs offline is not yet a rule the
pipeline applies. Zone.title_fill shipped and never fired for a phase.

Visual review: a renderer or wire change needs no sweep. Copy a3-result's
documents into a run directory, build the changed arm beside it, and run the
visual-review skill with --previous the copy. All fifteen sheets.

ISSUES 5-7 COST MODEL TIME — do not start them in this session without
Alessandro's go: receipt_0010's resize_long_edge probe, nonlatin_0014's
overlapping Zones, invoice_0001's Pair boundary and A1's false mark.

CLOSED — DO NOT REOPEN WITHOUT A NEW KIND OF EVIDENCE: the column model and
proportional widths, the merged Zone (menu_0012, form_0007), alignment_agreement
as a gate, a third loss detector. docs/status.md "Closed, with evidence".

STANDING RULES:
- Never cite or analyse a past run. Only a run taken in this session counts.
  The exceptions are the committed tests/frozen/ directories, each for what its
  README says it is.
- Leave debug/runs/84-rule-not-a-line/ intact.
- Never score against tests/documents/SAMPLE_DOCUMENTS.
- Do not delete the four shipped defaults or the three wire-level row nets.
- Marking may never change the words: wire._runs_for and ir.Cell.runs both stay.
- What is read off a Graphic is alt text, never printed.
- project() compares a normalised view, never raw markup.
- Every run must produce debug/runs/<label>/report.html. A sweep on
  uncommitted code saves git diff HEAD beside it.
- Any reviewed run is a full sweep, all fifteen, or the offline equivalent.
- Rubric judgements are pairwise and in-session only.
- Ask before binding anything docs/status.md leaves open.
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
