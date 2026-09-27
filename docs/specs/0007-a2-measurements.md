# Phase A2 — what the measurements say, before any code

**Taken 2026-09-25, in one sitting, against one control.** Branch `scaffold`,
head `a720482`. No code was changed to produce anything here: every number is
the shipped pipeline, or a prototype renderer run over the shipped pipeline's
own recorded answers.

**Why this file exists.** A2's prompt in
[`0007-handover.md`](0007-handover.md) scopes the phase as *geometry: columns,
alignment, clipping*, on the premise that side-by-side content renders stacked
because the renderer stacks it. **That premise is wrong for most of the corpus,
and the two routes that do work are blocked by a fault that is neither columns
nor alignment.** A2 was stopped at this point rather than built, and this is the
record it was stopped on.

---

## The control, and the harness that produced every number

The control is `A1-11-final` — the shipped configuration, the right-hand column
of `docs/status.md`'s "Where the corpus is as A2 begins".

**The harness was proved before it was used**, which is the rule A1 established.
Re-rendering the control's own embedded IRs with the shipped `render()` gives
**fifteen byte-identical `document.html` files**, and re-scoring those gives
**zero differing fields** across all fifteen documents — every ratio, every
count, every list. One cycle is about **50 seconds** and calls no model.

That makes every renderer question in A2 answerable offline, which is what let
four different renderers be measured in one sitting. It also means the
prototypes below are *pairwise, one change apart, in one sitting* — the only
kind of comparison this project permits.

---

## 1. Two thirds of the fault is not the renderer's to fix

Each side-by-side pair the source draws and the output does not was attributed
to whether its two source blocks fall in **different IR Zones** — where the
renderer decides the arrangement — or **inside one Zone**, where grouping
decided it long before the renderer saw anything.

| document | missing | across Zones | inside one Zone |
|---|---|---|---|
| `catalogue_0015` | 31 | 24 | 7 |
| `menu_0012` | 28 | 0 | **28** |
| `form_0007` | 21 | 0 | **21** |
| `newsletter_0008` | 8 | 8 | 0 |
| `darkdeck_0009` | 8 | 1 | 7 |
| `invoice_0002` | 6 | 5 | 1 |
| `nonlatin_0014` | 6 | 4 | 2 |
| `cv_0013` | 5 | 5 | 0 |
| **total** | **113** | **47** | **66** |

**The two worst documents in the corpus are entirely inside-Zone.**
`form_0007` at `beside_agreement` 0.059 and `menu_0012` at 0.349 have **zero**
across-Zone misses between them. `menu_0012`'s two menu columns are one
full-width `table` Zone of 24 rows; `form_0007`'s two-column form is one
`pairs` Zone of 24 pairs. No arrangement of Zones can put content side by side
that the IR holds as one Zone's linear run.

---

## 2. Four renderers, measured. The shipped one wins.

Each row re-renders the control's IRs and changes nothing else.

| renderer | beside | tau | clipped | height |
|---|---|---|---|---|
| **shipped `flex:1 1 12rem`** (control) | **0.7265** | **0.9381** | **1** | 1.4639 |
| proportional grid tracks from `Zone.bbox` | 0.6814 | 0.9381 | 4 | 1.5776 |
| column runs — Bands sharing lanes merged | 0.6908 | 0.9155 | 3 | 1.4244 |
| column runs, type shrunk to match height | 0.6628 | 0.9215 | 1 | **1.0284** |
| proportional `flex-grow`, disjoint Bands only | 0.7231 | 0.9381 | 1 | 1.4610 |

**Placing Zones at their measured proportions makes the page worse.** Narrow
tracks make our content taller than the source's, so blocks that shared a row
stop overlapping vertically and `_beside` stops seeing them. Clipping trebled,
1 → 4, on renders whose sources clip nothing. This is the same finding run
`89-style-record` reached from the other side, and `render._style_css`'s note —
*"A2 gives a Band a real column model instead of `flex:1 1 12rem`"* — is the
thing now measured and refused.

**The closest variant still crosses the ratchet.** Proportional `flex-grow`,
applied only to Bands whose Zones are horizontally disjoint, costs 0.0034 of
`beside_agreement` overall and gains `invoice_0002` 0.640 → 0.653 — but
`catalogue_0015` falls 0.262 → 0.227 and `form_0007` 0.059 → 0.029. Two
documents down is two documents down.

---

## 3. Height is not the blocker, and that is now measured

The handover says the height is a symptom and not to chase it. It is stronger
than that: **height was removed as a variable and the fault stayed.**

Row 4 above holds the corpus at `height_ratio` **1.0284** — essentially the
source's own height, down from 1.4639, with `menu_0012` 2.34 → 1.41,
`newsletter_0008` 1.99 → 1.07 and `statement_0006` 2.83 → 1.13. At that height
`beside_agreement` is **0.6628**, *below* the control.

So the type scale — deferred to 2/B — is not standing in A2's way, and nothing
in A2 should be deferred pending it.

---

## 4. Merging Bands into columns is right for a newspaper and wrong for a grid

The same change, one run, opposite documents:

| document | tau before | tau after |
|---|---|---|
| `newsletter_0008` | 0.832 | **0.968** |
| `darkdeck_0009` | 0.836 | **0.962** |
| `catalogue_0015` | 0.943 | **0.562** |
| `sample_semantic_0005` | 0.953 | 0.860 |

A newspaper column flows down and is read down; a card grid is read across. Our
Band order is row-major, which is right for `catalogue_0015`'s nine-card grid
and wrong for `newsletter_0008`'s three columns. **Nothing in the IR
distinguishes them** — both are Bands of Zones at the same lanes — and the two
discriminators tried (lane raggedness, equal lane occupancy) each classify one
of the two documents wrongly.

This is a real IR gap and it should be named as one rather than guessed at: the
Band model can say *what is beside what* and cannot say *which way the region
is read*.

---

## 5. The enclosed Zone — one fault under two symptoms

**A Band holding two Zones whose horizontal spans overlap.** Four of them, in
three documents, each an exact containment — the narrower box lies wholly
inside the wider:

| document | band | the enclosure |
|---|---|---|
| `cv_0013` | 0 | `0.38–0.58` contains `0.38–0.57` |
| `menu_0012` | 1 | `0.04–0.96` contains `0.22–0.30` |
| `statement_0006` | 2 | `0.03–0.97` contains `0.64–0.70` |
| `statement_0006` | 2 | `0.03–0.97` contains `0.91–0.96` |

**These are the same three documents whose snap is discarded.** The sweep's
`bakeoff.stderr.txt` logs `DTH_SNAP_ZONES is on` fifteen times and
`snapping the layout boxes to the ink made the Bands invalid` **three** times,
and the three rejection messages quote exactly the spans above. `validate_bands`
refuses the snapped geometry, so those three convert on unsnapped boxes.

**Correction to A2's prompt: it is three of fifteen, not four.** The prompt
says "silently not applying to four of the fifteen documents". Counted in the
one sweep that can be opened, it is three documents and four enclosed pairs —
which is very likely where the four came from.

**It also blocks the one renderer change that helped.** `cv_0013` is the single
document proportional width improved — `beside_agreement` 0.450 → 0.556, both
taken before the wrap fix moved its baseline to 0.474 — and
the guarded variant cannot apply it, because band 0 is one of the four. The
enclosure is upstream of the snap, upstream of the column widths, and upstream
of any lane model.

Resolving it is a **grouping** change: it decides which crops are extracted, so
it is upstream of the model and **cannot be measured by replay**. It costs a
sweep.

**Corrected in §8, measured the same day:** the snap returns these boxes
unchanged — the enclosure is the detector's own — and resolving it only
*removes* crops, so its effect *was* predictable offline.

---

## 6. `alignment_agreement` cannot gate this work

`render._numeric_columns` counts empty cells in its vote, so
`statement_0006`'s "Paid out" column reads 5 numbers in 40 rows and is not
right-aligned, when it is 5 of 5 among the cells that hold anything.

Ignoring empty cells moves **42 cells** in that document — 92 `.num` cells to
134 — and removes **all seven** of its `right→left` alignment disagreements.

`alignment_agreement` moves **0.935 → 0.935**. Exactly nothing.

The seven disagreements are replaced by seven others: a right-aligned cell in a
cramped seven-column table has no slack between its ink and its box, so
`scoring._alignment` reads it as `fill` rather than `right`. **The ratio is a
function of our own column widths as much as of our alignment**, and it cannot
say which thing came back — the failure A0 wrote its gate against and A1's
clause 4 repeated.

Counted directly instead, the corpus has **12 right-aligned table columns**
across five documents and the output reproduces 10 — but per document the match
is wrong: `report_0011` 3 of 3 and `sample_table_0003` 2 of 2 are right,
`darkdeck_0009` is 1 of 2, `statement_0006` is **0 of 3**, and `nonlatin_0014`
draws **4 where the source has 2**.

**So alignment stays in A2, gated on a count of named columns and checked in
the DOM** — decided 2026-09-25 — not on `alignment_agreement`.

---

## 7. The merged Zone cannot be found in the pixels — probe, 2026-09-25

§1 named the merged Zone as the largest single lever in the corpus: **49 of the
66 inside-Zone pairs** are `menu_0012`'s two menu sections held as one 24-row
`table` Zone and `form_0007`'s two-column form held as one 24-pair `pairs`
Zone. Splitting them would pay three ways — the pairs, a Title for each half
(`menu_0012`'s `To begin` echo is on the open list), and a narrower crop for the
extractor.

**It was probed before it was built, on the source pixels, with no model. It is
not detectable.** Three tests, over every Zone in the corpus:

**Test 1 — is there a gutter at all.** `form_0007`'s Zone has **zero** interior
blank columns: its labels, fields and rules ink every column across the crop, so
there is no gutter to find. Half the prize is unreachable in principle.

**Test 2 — is the gutter distinctive.** `menu_0012`'s Zone has exactly one real
gutter, **38px at 0.47–0.53 of the crop**, with the next-widest gap at **1px**.
Locally that is as clean a separation as this project has ever measured. As a
*share of the inked width* it is **0.055**, and **22 Zones that must not be
split rank above it** — `invoice_0001`'s two-column tables at **0.759** and
**0.665**, `nonlatin_0014`'s pairs panel at 0.487, `darkdeck_0009`'s service
table at 0.189. Any threshold that splits the menu splits all of them.
**No empty band** — the exact opposite of the histogram that set `keep_runs`.

**Test 3 — do the printed rows straddle the gutter.** The best remaining
discriminator: a two-column table pairs a value to its row, so every line has
ink on both sides; two independent stacks should not. `menu_0012` straddles on
**0.86** of its lines, sitting *between* `report_0011`'s table at 0.83 and
`darkdeck_0009`'s at 0.88, and below `sample_table_0003`'s 0.94. It does not
separate either.

**Three pixel-side tests, three failures, and the rule applies to this probe as
much as to any other: do not build a fourth without a new kind of evidence.**

**Why, stated as the standing lesson it is an instance of.** *When two things
look identical in the picture, the information is not in the picture.* Two menu
sections side by side and a two-column table are the same shape — a gutter, with
lines of ink either side at a shared rhythm. What makes `To begin` and
`Main courses` two section headings rather than one table's data is **reading
the words**, which is the same finding as `con-`/`nine-` in A1 and the same
reason Thread 2/B measures colour from pixels and not from a model.

**So if it is asked at all, it is asked of the model**, which already has the
crop, and it is asked as *how many regions is this* — the form `count_regions`
and `DTH_TABLE_GRID_HINT` both exploit, because this model complies with **how
many** and ignores **which**. That is a prompt change upstream of extraction: a
sweep, and its own phase.

---

## 8. The enclosure is the detector's, and every enclosed Zone was a duplicate

**Taken 2026-09-25, a second sitting, before any code changed.** Branch
`scaffold`, head `6369bd6`. Everything here is the layout stage run offline —
`rectify`, the detector, `_cover_the_page`, the snap, exactly as
`Conversion._layout` calls them, with no model — or the frozen control's own
IRs. **The harness was proved first:** offline `_layout` reproduces the
control's boxes, Bands and columns on **15 of 15**, and fires the same three
snap rejections, in about ten seconds.

### §5 named the wrong culprit

**The snap moves one box in the whole corpus**, `nonlatin_0014`'s recovered
Zone. `LayoutEngine.detect_zones` already snaps every detection and derives the
Bands from the snapped boxes, and the snap is idempotent, so the orchestrator's
second pass has nothing left to move. On the three documents where it was
"rejected" it returned every box unchanged — **the geometry that shipped was
enclosed with the snap or without it**, and "`DTH_SNAP_ZONES` did not apply to
3 of 15" described a step that had done nothing either way. A gate clause
reading "the snap applies to 15 of 15" would have passed without moving a box.

**The enclosure is made by two union steps in the detector**, found by running
its steps one at a time and testing containment after each:

| document | step | what the grown box swallowed |
|---|---|---|
| `statement_0006` | `attach_trailing_rows` | the table takes its Totals strip and, with it, two amount boxes on the same line |
| `menu_0012` | `attach_headings` | `To begin`, inside the menu its sibling heading joined |
| `cv_0013` | `attach_headings` | `Senior Structural Engineer`, inside EXPERIENCE |

`outermost` — one box per region — runs *before* them, and nothing after them
checked. `wire.validate_bands` never runs on a detector's output at all; its
docstring said it *could not* fire on derived Bands, which is false for exactly
this shape and is part of why nobody looked.

### What the enclosed Zones held

**All four were duplicates** of text the enclosing Zone had already read:

| document | the inner Zone read | the enclosing Zone already had it as |
|---|---|---|
| `statement_0006` | `5,772.36`, `3,586.14` | the Totals row of the transactions table |
| `menu_0012` | `To BEGIN` | the table's Title, `To begin` |
| `cv_0013` | `Senior Structural Engineer` | line 1 of the EXPERIENCE paragraph |

`menu_0012`'s is the "To begin" half of the open across-Zone echo: the two
readings sit in different Zones, which is why `_without_title_echo` could not
reach it. `darkdeck_0009`'s `AVAILABILITY` is not an overlap and is untouched.
*(2026-09-26: it is not across Zones either — Zone 2's Title was lifted off
its own header row's first cell. Closed by `wire._title_is_its_header_cell`.)*

**So drop and merge are the same operation here.** The inner box lies wholly
inside the outer, the union of the two *is* the outer, and nothing leaves any
crop. Re-banding would keep the duplicate.

### Where the threshold goes — the empty band

Covered share of every overlapping pair after the unions, all fifteen:

    1.000  statement_0006  text in table
    1.000  statement_0006  text in table
    1.000  menu_0012       section_header in document_index
    1.000  cv_0013         section_header in text
    0.696  nonlatin_0014   section_header in key_value_region
           (nothing else overlaps at all)

The four are inside on **all four edges**. `outermost`'s `CONTAINED` 0.70 would
also catch exactly these four today, sitting **0.004** above `nonlatin_0014`'s
box — whose outside part holds `ΤΠΥ = 2026/0417`, which no other crop has. So
the rule is the edges and has no constant: `detector.without_enclosed`, run
after the unions.

`nonlatin_0014`'s is a **fifth overlap of a different shape**: its full-width
Zone re-reads three of the four pairs in the top-right box beside it
(`Ημερομηνία`, `Λήξη`, `Σειρά`), across two Bands, which is how it passes
`validate_bands` — by accident, because `_cover_the_page`'s recovered title
re-banded it. Removing that overlap means cutting a box, which changes a crop.
**Left open by decision, 2026-09-25**, not A2's.

### It was predictable offline after all

§5 said resolving the enclosure "cannot be measured by replay" because it
changes which crops are extracted. It changes that only by *removing* one:
every surviving Zone keeps its box, so its crop and prompt are unchanged and
at `temperature: 0` so is its answer. The effect is the control's IRs minus the
four Zones, re-banded and re-measured. Against the floor:

| | control | enclosed Zones dropped |
|---|---|---|
| vocabulary recall | 0.8667 | 0.8667 |
| precision | 0.9787 | **0.9803** |
| tau | 0.9381 | 0.9382 |
| beside agreement | 0.7298 | 0.7316 |
| height ratio | 1.4889 | 1.4772 |

Only the three documents move, the ratchet holds on all fifteen, and **no
side-by-side pair that agrees in the control is lost or gained on any
document.**

**Confirmed by sweep `A2-10-enclosed-sweep`, the same day:** every
`document.html` byte-identical to this prediction, every scored field equal on
all fifteen documents, and every surviving Zone's answer — inline runs included
— identical to the frozen control's. Two readings of that table need care:

- **`cv_0013`'s `beside_agreement` 0.474 → 0.500 recovers nothing.** The source
  pair `Senior Structural Engineer | 2021 — present` leaves the *scored* set:
  with the heading copy gone, that source block matches no output block. It was
  first read as a pair coming back and a gate clause was written on it; it was
  restated before the sweep, with this evidence.
- **Multiset recall dips on `menu_0012` and `cv_0013`**, A0's shape exactly:
  the source prints "Structural Engineer" four times, the output read three
  plus the echo. `vocabulary_recall`, the ratchet's leg, does not move.

### What it does not buy — re-measured, not inherited

The handover called proportional `flex-grow` "the one renderer change that
helped", blocked on `cv_0013` by the enclosure, and asked for it to be
re-measured once unblocked. With the enclosure gone every multi-Zone Band is
disjoint, so the guard has nothing left to exclude. Over the enclosed arm's
IRs, one change apart:

| `flex` on a multi-Zone Band | beside | `cv_0013` | ratchet |
|---|---|---|---|
| `1 1 12rem` (shipped) | 0.7316 | 0.500 | holds |
| `<width share> 1 12rem` | 0.7287 | **0.474** | fails on `form_0007` 0.059 → 0.029 |
| `<width share> 1 0` | 0.6939 | **0.474** | fails on four documents, `invoice_0002` 0.640 → 0.295 |

**It lowers the document it was supposed to help**, in both forms. Whatever
lifted `cv_0013` before the wrap fix is not there now. The route stays closed
with §2's column model.

---

## What this leaves A2

**Reachable offline, no sweep, each measured above:**

- the empty-cell fix to `render._numeric_columns` — 42 cells in
  `statement_0006`, and the named-column clause is how it is gated (§6)
- `layout.clipped` 1 → 0, which is `cv_0013`'s sidebar alone
- the snap rejection surfaced in `report.html` instead of `bakeoff.stderr.txt`

**Worth a sweep, and the only thing in A2 that was — shipped 2026-09-25, gate
met, sweep `A2-10-enclosed-sweep`:**

- **the four enclosed Zones** (§5, corrected by §8). A Band holding a box wholly
  inside another box is not two Zones by the Band model's own definition, so
  the rule is deterministic and needs no detector. It was written expecting to
  make the snap apply and to unblock proportional widths; §8 found the snap had
  never moved those boxes and that proportional widths lower `cv_0013` once
  unblocked. What it did do is remove four duplicated readings and make the
  Bands valid on fifteen of fifteen.

**Closed unbuilt, with the evidence above, the way spec 0006's Change 3
closed:**

- **the column model.** Four renderers, all worse on the hard tier (§2), with
  height removed as a variable (§3).
- **the merged Zone.** Three pixel-side tests, none of which separates it (§7).
  If it is re-opened it is a *model* question asked as "how many regions", not
  a CV question, and it is its own phase.

**Not A2's, and named so they are not absorbed:**

- reading direction for a multi-Band column region (§4) — an IR gap. The Band
  model says what is beside what and never which way the region is read, and the
  same merge takes `newsletter_0008` from tau 0.832 to 0.968 and
  `catalogue_0015` from 0.943 to 0.562.

## Reproducing this — the control is now frozen

The prototype renderers and the blame attribution were scratch scripts, and the
five prototype run directories are under `debug/runs/`, **which is gitignored
and gets cleared**. Those directories are not citable and the tables above are
kept as the record of how the decision was reached, in the same way as every
run number in `CLAUDE.md`.

**The control is not.** `tests/frozen/a1-result/` was committed on 2026-09-25
and holds the fifteen `document.html` files *and* their `scores.json`. Scored
straight out of that directory with nothing else from the run: **15 documents,
0 differing fields.** So every measurement above can be re-taken offline in
about fifty seconds, on any machine, with no model — which is what turns this
file from a story into evidence.

Re-deriving a prototype means re-writing the prototype renderer; re-deriving the
control means running the recipe in that directory's README.
