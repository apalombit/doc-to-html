# Group at the right level

**Status: complete.** Closed on run 81 — the corpus at **22 findings, geometry
6**, down from 26 and 16 when this spec opened. Supersedes spec 0005's Changes 2
and 3, whose mismatch counts were written against a comparison that no longer
exists. 0005's Change 1 (Titles) is built; its Changes 4 and 5 are untouched and
stay where they are. No GitHub issue: every measurement is in this file.

| change | outcome |
|---|---|
| **1 — relative heading gap** | **Ships on** as `DTH_HEADING_RULE=relative`. Measured live one flag apart (78 v 76) before the default moved. Both of this spec's proposed separators measured *worse* than the constant they would have replaced; what shipped is a third test, the gap below a heading against the gap above it, bounded by `HEADING_GAP_MAX`. |
| **2 — choose a segmentation over the existing pool** | **Ships on** as `DTH_PREFER_CONTAINER=1`, for *stacked* contents only. Measured live one flag apart (80 v 79): 23 findings to 21, geometry 11 to 6, ten fewer model calls. The spec's own prefer-the-parts half measured strongly negative and was rejected. |
| **3 — drawn container ink as a signal** | **Built, measured, not shipped — and not in the tree.** The rectangle finder works exactly as predicted, and wired in it produces **byte-identical boxes on all five fixtures**. Its stated worth was spent by Change 2. Do not rebuild it expecting a different answer. |

**The ruler had to be fixed before any of it could be believed**, and that is the
most transferable part: four fixtures typed their Zone rectangles around what was
*drawn* while one read the *ink*, and the worst box scored 0.043 IoU against its
own ink — below `MATCH_IOU`, so no correct detection could ever pair with it.

**Tests that came with it:** `TestJudgingTheGapAgainstTheGapAbove` and
`TestAdoptingAContainerTheThresholdDropped` in `tests/test_layout_detector.py`,
`TestTheHeadingRule` and `TestPreferringAContainer` in `tests/test_config.py`, and
`TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion` in `tests/test_bakeoff.py`
— the last of which exists because a flag reached `Settings`, was recorded in the
run directory, and never reached the detector. Suite green at 573.

**What this spec leaves open**, decomposed by measurement rather than estimated:
two stacked splits with **no container anywhere in the pool** at any confidence,
and two side-by-side merges whose parts already clear the threshold and are
discarded by `outermost`. **Titles became the largest category as this spec
closed — 13 of 23 once the last convention question was settled — because
grouping a region correctly is what makes its Title comparable in the first
place.** That was not a cost: it was the whole of what `DTH_CAPTION_PASS` then
took, 23 findings to 10 over runs 82-84. See `config.DEFAULT_CAPTION_PASS`.

**One sentence:** the detector segments *ink* and the references segment *DOM*, so
regions come back at the wrong level of nesting — and that one fault accounts for
two thirds of everything the acceptance harness reports.

---

## What changed under this spec's feet — read this first

`acceptance.compare()` **no longer pairs Zones by list position.** It pairs them
by geometry, via `geometry_score.align()`. This matters before any number in this
file is read:

- Every mismatch count in specs 0001-0005 was taken under the old comparison,
  where one extra Zone shifted every later Zone against the wrong reference. Those
  totals are **not comparable** with anything measured from here on.
- Under the old comparison `sample_css_0004` reported 10 mismatches from *one*
  geometry fault, and the classifier deserved none of them — it agreed with its
  reference on 6 of 6 regions once realigned.
- Geometry now reports in its own terms: `region expected one region, got 2
  regions: 2, 3`. Kind, Role, Title and Row Roles are compared **only where the
  region was found correctly**, because a Zone that was split was never shown the
  picture its reference describes.
- Band structure is compared only when every Zone pairs off
  (`Correspondence.exact`), since which Zones share a row is a claim about Zones
  both documents agree exist.

The rectangles are still **not scored**. `align` asks one question — *which region
is this* — at `MATCH_IOU` 0.50, with a reference claimed by exactly one box
counting as matched however loosely it fits. A reference rectangle is a derivation
rather than a measurement, so scoring how closely one fits would be measuring the
derivation.

Offline suite: **564 passed / 0 failed.** Any failure is a real regression.

---

## The measurement this spec starts from

**Superseded twice — once by this spec's own work.** The table that stood here was
run 75's IR re-scored, and it is dead for two reasons: `debug/runs/` is gitignored
and cleared, and every reference rectangle moved when the ruler was fixed (see
"The ruler had to be fixed first", below).

The live baseline is **`debug/runs/76-fixtures-baseline/`**, taken 2026-09-14 on
the shipped defaults over all five fixtures, and `CLAUDE.md` carries its table.
In summary: **26 findings, of which 16 are geometry** — so the one-sentence claim
at the top of this file still holds, at roughly two thirds.

**The geometry half needs no Conversion.** It is deterministic, so derive it with
`align()` over `LayoutEngine.detect_zones` and spend a run only on the model's
half. Both changes below were pre-registered that way and both came back exact.

### The fault, by direction

On the shipped rule, against the corrected references:

| fixture | splits | merges | extra regions | net |
|---|---|---|---|---|
| `sample_semantic_0005` | 4 | 1 | 1 | 13 v 9 — over-split |
| `sample_css_0004` | 2 | 1 | 0 | 6 v 5 — over-split |
| `invoice_0002` | 1 | 2 | 1 | 9 v 10 — **both directions at once** |

**The "references with no region" column is gone, and its disappearance is the
result.** It used to hold 3, 1 and 3 — references nothing could be paired with —
and every one of them was the ruler rather than the detector. Fixing the
rectangles turned them into merges, which is the fault that is really there.

The bias is not "always finer". `invoice_0002` under-segments (its two header
Zones swallowed into one region) and over-segments (the footer cut in two) on the
same page. The fault is *wrong level*, which goes either way — so a fix that only
ever merges will trade one column of this table for another.

### What it costs in the output

`sample_css_0004`'s source has a card:

```html
<div class="card">
  <h2>Card heading</h2>
  <p>Cards are reusable layout containers…</p>
</div>
```

The reference makes that **one Zone** with `title="Card heading"`. Zones never
nest (`ir.Zone`), so one Zone carrying a Title and its Blocks is the IR's only
vocabulary for containment — the reference is not inventing DOM nesting, it is
using the model as designed.

The shipped rule emits two sibling Bands instead. Three losses, and the third is
the one that makes this a real defect rather than a scoring artefact:

1. The grouping is gone — no panel, no border; the `titled` CSS class can never
   fire.
2. `render._block` renders every `heading` block as `<h1>`, so the card's `<h2>`
   becomes a page-level heading and the document outline flattens. A Title renders
   as `<h2 class="zone-title">` — correct level by construction.
3. **The second card lost its heading entirely.** Its dump returned
   `{"kind": "paragraph", "lines": ["Another card"]}`. Alone in a crop with no
   body beneath it, the model had nothing to contrast against. Cutting a heading
   off its body destroys the evidence that it *is* a heading.

---

## Change 1 — make the heading gap relative, not a fitted constant

**Status: built, behind `DTH_HEADING_RULE=relative`, default off.** What follows
is what the work found, because most of what this section originally proposed
turned out to be wrong.

**Step 1 was the whole of it.** Run pre-snap, heron at 0.40, all five fixtures,
all 14 heading cases, with each verdict read from the fixture *builder's* Zone
contents rather than from its typed rectangle:

```
gap    MERGE 0.011 0.024 0.028 0.029 0.030 0.038 0.040 0.044 0.056 0.064
       leave 0.025 0.032 0.081 0.147                    <- interleaved
```

**Both documents this spec asked to be reconciled were wrong.** `HEADING_GAP`'s
docstring files 0.025/0.028/0.032 under `merge` — two are `leave` — and
0.056/0.064 under `leave`, where both are `merge`. Spec 0005 is right about
`sample_css_0004` and wrong about the rest. Shipped, `0.05` makes **4 wrong calls
of 14**.

**Both of Step 2's candidates measure worse than the constant they would
replace.** Best threshold achievable by each, over the same 14:

| test | wrong | note |
|---|---|---|
| `gap` (what ships, at 0.05) | 4 | |
| `gap` (best possible threshold) | 2 | still fitted, 1.27x margin |
| `gap ÷ heading box height` | 3 | |
| `gap ÷ median line gap` | 3 | and undefined on 6 of 14 — a single-line box has no leading |

So the premise of Step 2 does not hold, and **Step 1's table is the reason to
know that rather than to choose between them**. That is what the step was for.

**What shipped instead: `gap_below ÷ gap_above`.** A heading sits closer to what
it names than to what it follows. Every true merge in the corpus is at **1.293**
or below, the nearest false one at **2.89**. `gap_above` falls back to the
distance to the top of the page, which is what makes the rule total: four of the
14 headings have no box above them that overlaps horizontally, and their gaps
below are non-monotonic (leave 0.025, leave 0.032, **merge** 0.044, leave 0.081),
so no absolute threshold can order them.

`HEADING_GAP_RATIO = 1.9` with `HEADING_GAP_MAX = 0.10` as the outer bound —
Step 3's second option, and the docstring says so. Margins ~1.5x each side
against `HEADING_GAP`'s 1.13x, and verified as a **plateau**: ratio ∈ {1.4 … 2.8}
× max ∈ {0.08, 0.10, 0.12} all give one identical answer on all five fixtures.

**Two cases it still gets wrong, and they cost nothing.** `invoice_0002`'s
`Invoice` and `sample_semantic_0005`'s `The Weekly Digest`, both page titles over
a metadata line. Simulated end to end, un-merging them changes no finding on
either fixture. They are unreachable because the references are inconsistent
about them — see "The fixture question this opened", below.

**Measured offline**, against the corrected references, counted as
`acceptance.compare` counts:

| fixture | `absolute` | `relative` |
|---|---|---|
| `invoice_0001` | 0 | 0 |
| `invoice_0002` | 5 | 5 |
| `sample_table_0003` | 0 | 0 |
| `sample_css_0004` | 4 | **2** |
| `sample_semantic_0005` | 7 | 7 |
| | **16** | **14** |

`covered` 1.00, `splits` 0, `doubles` unchanged on all five in both arms.

**Measured live, run 78 against run 76, one flag apart in one sitting:** the
prediction held exactly. `sample_css_0004` geometry **4 to 2**, its two new Title
findings appeared as expected, and its total stayed **4**. The other four
fixtures came back finding-for-finding identical. Corpus total **26 either way**,
geometry **16 to 14**.

What the count cannot show, and is the actual result:

- **The second card's heading is recovered** — the third loss listed above. It
  returned `{"kind": "paragraph", "lines": ["Another card"]}` on the baseline and
  comes back as a `heading` block over its paragraph with the rule on.
- Each card is **one Zone**, so the grouping exists in the render.
- **Four fewer model calls** on that fixture, 12 passes to 8.

**The second loss above is still not fixed**, and the merge should not be read as
having fixed it: `render._block` still emits `<h1>` for a `heading` block, so both
cards flatten the outline. That needs `zone.title` populated, which is the caption
pass.

**So the default does not flip on this run.** Two geometry findings on one fixture
with the total flat is a structural case, not a numeric one. `DTH_CAPTION_PASS`
measured on top of this is what would make it one — and it is now reachable,
which it was not while the regions were split.

**Gate.** The five at the bottom of this file, plus: `sample_css_0004`'s two
`split across 2` findings go away and its `zone 1` under-split does **not** become
a merge that swallows anything.

---

## The ruler had to be fixed first, and it was

**This was not in the spec, and nothing downstream of it could be measured
without it.** Four of the five fixtures typed a Zone's rectangle around what is
*drawn* — a card's border, a panel's shaded caption bar, an `<aside>`'s padding —
while `invoice_0001`'s are read off the browser as the **ink**. Two conventions,
one ruler.

| fixture | mean typed-vs-ink IoU | worst box | splits in the reference itself |
|---|---|---|---|
| `invoice_0001` | — exact — | — | 0 |
| `sample_table_0003` | 0.854 | 0.845 | 0 |
| `sample_semantic_0005` | 0.758 | 0.445 (`TL;DR`) | 4 |
| `invoice_0002` | 0.659 | **0.043** (`Services / Products`) | **25** |
| `sample_css_0004` | 0.605 | 0.260 (`Another card`) | 1 |

`MATCH_IOU` is 0.50, so a reference at 0.043 **cannot be paired with a correctly
drawn detection at all** — the fixture, not the run, decides the finding. That
box is a full-width shaded bar over a panel whose table is empty.

**The browser cannot settle the other four, and that was checked.** Only
`invoice.html` still re-renders to its screenshot (0.74% of pixels differ). The
rest differ by 6.9–14.1% and in **content height** — different fonts, and
`invoice2.html` wants the Bootstrap CDN. `render_matches_source` refuses all four,
correctly.

So `tools/fixture_geometry.py --snap` moves the four onto their own ink with
`preprocess.snap_to_ink` — the same operation every detection goes through — and
writes the result back into the builders, which are authoritative. It refuses
`invoice_0001`, whose browser-exact boxes score 0.916 snapped and would be
downgraded by it.

One defect snapping could not reach, fixed by hand first: `sample_semantic_0005`
Zone 2's rectangle stopped at its `<h2>` while its own second Block claims the
byline printed below it — 910px of ink no reference in that fixture claimed, the
only such hole in the corpus.

**What it bought.** Every fixture's references now score `covered` 1.00 and
`splits` 0 against their own Source Image. Geometry findings under the *unchanged*
heading rule: **18 → 16**. More usefully, `missing` is now empty everywhere —
`invoice_0002`'s three references that nothing could find became one `merged`
finding, which is what the fault actually is.

**It breaks comparability with everything recorded before it**, for the second
time after `compare()` pairing by geometry. Any total in this file or in 0001-0005
that was not re-derived this way is dead.

### The fixture question this opened, and did not answer

The references split `<header><h1>+<nav></header>` and
`<div class="col-sm-8"><h1>+<h4></div>` into two Zones while making
`<div class="card"><h2>+<p></div>` and every Bootstrap panel **one** Zone with a
Title. Same shape, opposite readings. It is the source of both of the relative
rule's remaining errors.

Left alone deliberately: it changes the Zone *list* rather than the rectangles, so
`blocks`, `title`, `band`, `column` and Probe expectations all move with it — and
both affected cases cost zero findings today. It does not belong inside a geometry
change.

---

## Change 2 — choose a segmentation by score, over the pool that already exists

**Status: built as `DTH_PREFER_CONTAINER`, default off. Measured run 80 against
run 79, one flag apart: 23 findings to 21, geometry 11 to 6.**

**What this section originally proposed measured strongly negative**, and the
prototype is worth recording because the spec framed this as the largest item and
the riskiest, which was right:

| arm | per-fixture | total | gate |
|---|---|---|---|
| baseline | `[0, 5, 0, 2, 7]` | 14 | — |
| "prefer the parts" (side-by-side) | `[4, 9, 0, 4, 9]` | 26 | covered 0.945, +1 split |
| "prefer the container", unguarded | `[6, 6, 0, 3, 5]` | 20 | **`invoice_0001` 0→6** |

Only one of the two directions survived. **The over-splits are the tractable
half**; the two remaining side-by-side merges are not addressed and Change 3 is
where they would be.

**The key fact held up under measurement.** All five over-splits have their
container already in the pool, at 0.05-0.27 against a 0.40 threshold and IoU
0.55-0.97 against the reference. `outermost` never saw them: it runs on what
survived the threshold, so a container the detector was unsure about is gone
before nesting is considered. `prefer_container` is the mirror of
`split_containers` — that one re-opens a container the threshold kept, this one
restores one the threshold dropped.

### The signal that decided it, and the guard that made it safe

**`stacked` vs `side-by-side` separates the two directions perfectly**, on every
case in the corpus. Contents stacked are one region printed as lines; contents
side by side are a Band the detector drew one rectangle around. **Class agreement
separates none of them** — two of the five correct merges hold mixed classes.

**`CONTAINER_HEIGHT` is what keeps Gate 1.** Unguarded, the rule adopts a `table`
at 0.09 spanning **0.444** of `invoice_0001` — both printed tables as one region,
undoing `split_containers` — and a `picture` at 0.06 spanning **1.000** of
`sample_css_0004`. Measured over every candidate the rule considers:

    adopt      0.039  0.048  0.092  0.124        <- correct, every one
    refuse     0.444  1.000                      <- both wrong

0.25 sits between with **2.0x below and 1.8x above**, on a plateau: 0.15 through
0.35 give an identical answer on all five fixtures. Widest margin any constant in
this project rests on.

All five guards are load-bearing — dropping the page-level class rule or the
`doubles` test costs a finding each.

### What it bought, beyond the count

- **Ten fewer model calls**, 72 to 62. Two fewer Zones on one fixture and eight
  on another is two fewer classify-plus-extract pairs each.
- **It ties `DTH_HEADING_RULE=relative` on the count and loses on the output.**
  Both reach 6, and so do both together — but `sample_css_0004` keeps its first
  card split under the container rule alone (5 Zones) and is whole with the
  heading rule on as well (4 Zones). The zone-count finding replaces the split
  finding, so the total hides it.
- **One new finding:** `sample_semantic_0005` zone 7 reports `role expected
  footer, got body`. Not the Band — `_role` uses that only for `band == 0`. The
  colophon was `footnote` + `key_value_region`, and `footnote` is in `FOOTERS`;
  the adopted container is a `key_value_region`, which is in neither set. **A
  container is adopted with its own class, so anything keyed on a class is
  downstream of the grouping.**

**Gate.** All of it held: `invoice_0001` a full match with the Probe at 385.00,
no fixture's count rose, `covered` 1.00, `splits` 0, `doubles` unchanged.

---

## Change 3 — feed container ink to the chooser as a signal, never a gate

**Status: built, measured, and not shipped. Its premise holds and its effect is
nil — byte-identical geometry on all five fixtures.**

**Worth, as this section originally claimed:** `sample_css_0004` to a full match.
**That worth was spent by Change 2.** This section was written when the two cards
were being split, and the drawn card border was the evidence that would join
them. Change 2 joined them from the detection pool alone, and what remains wrong
on that page is the header — which is not drawn.

### The signal is real, and it was built rather than argued about

`#f7f9fb` fill and `1px #e1e8ed` border, found with the OpenCV already in
`preprocess`: near-uniform non-white fill, or a closed four-corner contour, both
at ≥ 0.90 rectangularity and ≥ 0.003 of the page. Over the corpus it finds

    invoice_0002       4 panels (0.014-0.405, 0.429-0.985 | 0.014-0.570, 0.595-0.985)
                       + the logo's own border
    sample_css_0004    2 cards  (0.043 0.279 0.958 0.596 | 0.043 0.622 0.958 0.934)
    the other three    nothing drawn

That is exactly right, and it is exactly the set of regions **Change 2 already
resolves correctly.** Wired in as the spec asks — a drawn rectangle is a
candidate container in its own right, and a candidate coinciding with one is
exempted from the guards that exist only because an undrawn candidate cannot be
trusted — every one of the five fixtures produces **the same boxes to the last
digit**, and the corpus stays at 4 geometry findings.

**One guard it needed, and the reason to record it.** Unguarded it takes
`invoice_0001` from 6 Zones to **1** — the page's own outer rule is an
axis-aligned drawn rectangle, and the rule adopted the page as a container of
everything on it. Rejecting a rectangle covering more than 0.80 of the page fixes
it: the same fact `PAGE_LEVEL` states about the `form` class, restated about ink.
**A signal that reads the page correctly can still be the worst possible answer**
— Gate 1 caught it in the first arm measured.

### Why there is nothing left for it to decide

The four findings after Change 2 decompose cleanly, and **none of them is drawn**:

| fault | fixture | shape | reachable by? |
|---|---|---|---|
| footer cut in two | `invoice_0002` | stacked SPLIT | **no container exists** — the only pool box covering it spans the whole page |
| Benefits list cut in two | `sample_semantic_0005` | stacked SPLIT | **no container exists** — same |
| logo + address as one box | `invoice_0002` | side-by-side MERGE | parts are in the pool, **above** threshold |
| title + badge as one box | `sample_css_0004` | side-by-side MERGE | parts are in the pool, **above** threshold |

The two splits close out Change 2 honestly: it took every over-split that had a
container, and the two left have none at any threshold.

### The two merges, and the reason they are being left alone

They are not a threshold problem. Both containers hold parts that **already clear
0.40** — `section_header` 0.68 + `picture` 0.63 on the card page, `picture` 0.76 +
`text` 0.44 on the invoice — and `outermost` discards them in favour of the
container. So the fix is a condition on `outermost`, not a pool read.

Prototyped as `prefer_parts`, the exact mirror of `prefer_container` restricted to
above-threshold parts — much narrower than this spec's original prefer-the-parts
arm, which scored 26:

| arm | per-fixture | total |
|---|---|---|
| shipped pair | `[0, 2, 0, 1, 1]` | **4** |
| + `prefer_parts` | `[0, 1, 0, 4, 5]` | 10 |

It fixes `invoice_0002`'s merge and **breaks four regions that were right**,
because the discriminator is not available. `sample_css_0004`'s Zone 2 is *one
line of prose* — "This document demonstrates inline `<style>` blocks…" — and the
detector cuts it into three side-by-side boxes at the code span. Those three are
side by side by every test that separates the header's title from its badge:
same band, horizontally disjoint, gaps of 0.006-0.009 against the header's 0.009,
comparable heights, parts filling the container's ink exactly. **`side-by-side`
told Change 2 which way to regroup; it cannot tell this rule which side-by-side
groups are Bands.**

**Reported and stopped**, under this spec's own instruction for Change 2. Two
findings on two fixtures is not worth a rule that costs six.

---

## Protocol, for every change above

- **One axis at a time.** Set exactly one `DTH_*` against the shipped defaults and
  say which one when reporting. Historical runs moved several at once and their
  totals describe configurations that are neither the shipped one nor each other.
- **A small delta is not a result.** The model is not bit-reproducible; two runs
  of one configuration differ by a few mismatches with no code change.
- **Geometry, however, is deterministic** — verified on real inputs, not assumed.
  A geometry change that breaks byte-identical repeat runs has broken something
  structural.
- **The offline suite is the fast signal:** `python -m pytest -q`, 548/0. It runs
  against recorded responses, so it measures the pipeline below the model.
- **Never quote a run you cannot open.** `debug/runs/` is gitignored and cleared.
- Derive the geometry half with `align()` rather than spending a Conversion on
  it; it is deterministic, and that makes every change here pre-registrable.

### Pre-registered gate — all of it, for every change

1. **`invoice_0001` stays a full `match`** — 6 Zones, 4 Bands, Probe 385.00.
   *No Zone that previously converted stops converting.* Mandatory, and it is the
   condition spec 0004 shipped a regression for omitting.
2. No fixture's mismatch count rises.
3. `covered` stays 1.00 and `splits` stays 0 on all five. Not negotiable.
4. `doubles` does not rise on any fixture. Over-merge is invisible to every other
   field here, and Changes 1-3 all push toward merging.
5. The offline suite stays green.

---

## Already tried, already rejected — do not re-derive

- **Prompt instructions not to split a region: measured ignored, three times.**
  Run 48's answers were byte-identical to the run before it. The model does not
  read the two ends of an 800px row as one line, so a behavioural instruction has
  nothing to act on. It complies with *how many* and ignores *which line*.
- **A measured region ceiling on the first layout call** cost `invoice_0001` its
  zero-mismatch Conversion twice — the bound is read as a target. It survives only
  as a rescue after an answer has already failed (`_layout_again`).
- **Resolution does nothing for layout.** Byte-identical geometry at 384, 512 and
  862.
- **`outermost` is load-bearing.** Removing it costs both detectors everything —
  137 to 231 boxes on pages holding 6 and 10. Change 2 must *condition* it, not
  drop it.
- **Chasing Titles.** Every remaining Title finding is downstream of grouping or
  of `DTH_CAPTION_PASS` shipping off. Fix the level first; measure the caption
  pass after.

## Out of scope

- Kind and Role (spec 0005 Changes 4 and 5). Under the new criteria they are 2 and
  0 findings respectively — there is nothing here worth spending on yet.
- Flipping `DTH_CAPTION_PASS`. It is built and works; it has never been measured
  one flag apart against the current default, and it cannot help while regions are
  split.
- Removing the VLM layout pass. It is what the offline suite replays against.
