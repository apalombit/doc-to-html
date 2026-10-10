# Read the page's structure before its boxes

**Status: open — step 1 DONE 2026-10-10, gate MET; step 2 next.** Opened 2026-10-10, Alessandro's decision,
after reviewing the fresh sweep `F1-sweep`. Tracking issue **#31**. It works
under spec 0007's target and ratchet; nothing in 0007 changes.

**One sentence.** Nothing in the converter decides what the page's layout is —
it emerges from where the detector put its boxes, and the IR can only say which
boxes share a row — so this spec adds **one small step** that records the
page's structure, and then lets the renderer and the boxes follow it.

**Keep it small.** The aim is to find out whether a simple structure step fixes
the worst-failed documents. Build nothing the five target documents do not
need. If simple is not enough, that is a finding, and the next spec's evidence.

---

## Why — what the review of `F1-sweep` showed

Measured 2026-10-10 on `debug/runs/F1-sweep` (commit `12fa2d1`, shipped
defaults, all fifteen). **Re-take these before relying on them** — `debug/` is
cleared, and a run is not citable.

The visual review's largest cross-cutting fault was layout: side-by-side
regions collapse or interleave. On three documents it is most of what is wrong.

| document | the source | what the converter made | why |
|---|---|---|---|
| `cv_0013` | a dark sidebar (⅓) beside a main column (⅔), each a stack of sections | 31 Zones in 21 Bands; the columns interleave, and several sidebar items run the full width | Bands are rows, so each sidebar item is paired with whatever main-column item sits at its height |
| `menu_0012` | a centred masthead; a body of two columns, each two titled sections; a footer | the body is **one** `table` Zone, x 0.04–0.96, read across — `To begin \| Main courses` as one header row, the main courses printed under `From the grill` | the detector boxes the whole body, and nothing says it is two columns |
| `catalogue_0015` | a title over a rule; a 3×3 grid of identical cards; a footer | the nine card boxes are right, but the first card's box (y 0.04–0.36) swallows the page title, and the nine cards were read as 5 `pairs`, 3 `table`, 1 `prose` | nothing marks a header, and nothing says the nine are one design |

`darkdeck_0009` (an aside panel scattered through the main column, 14 Zones in
10 Bands) and `newsletter_0008` (three columns read band by band) fail the
same way as `cv_0013`.

**Where it lives in the code.** `wire.bands_from_boxes` turns boxes into
`(band, column)` rows; `Document.bands()` groups them; `render.render` draws
each Band as one `.band` flex row. `ir.Zone`'s `band` and `column` are all the
IR knows about layout. Phase A2 named this gap and left it unbuilt
(`0007-a2-measurements.md` §4): *the Band model says what is beside what, and
never which way the region is read.*

---

## The idea

**One step** that reads the rectified page and returns its structure. In step
1 it may look at the pixels and at the detector's boxes, and at nothing else.

**What it returns — the minimum.** A list of **regions**, top to bottom, each a
box and a `flow`:

- `single` — one column, read down. Today's behaviour, and the default.
- `columns` — N columns, each read top to bottom, with the x positions that
  split them.
- `grid` — rows of side-by-side items, read across. Today's Bands are already
  right here; a grid also says whether its items are **copies of one design**.

**No deeper nesting than page → region → column.** If the targets need more,
that is the "Then decide" question at the end, not this spec.

**Signals, cheapest first — pixels only in step 1:**

- full-width rules and wide horizontal gaps → header, body, footer;
- drawn boxes from `style.rectangles`, already built, and measured in its
  docstring exact on `catalogue_0015` (9 cards) and `darkdeck_0009` (5);
- full-height fills — `cv_0013`'s dark sidebar;
- a vertical gutter running the full height of a region.

**Where the pixels cannot decide, the region stays `single`** — today's
behaviour, so nothing gets worse. Do not stack heuristics to force an answer:
A2 §7 showed `menu_0012`'s gutter cannot be told from a two-column table's
inside one box. If step 1 cannot get the menu, step 3 asks the model **one
closed question** about that region — *how many columns, read down or
across* — the kind of question this model answers reliably (counts, not
positions).

---

## Targets

- **Primary:** `cv_0013`, `menu_0012`, `catalogue_0015`.
- **Secondary:** `darkdeck_0009`, `newsletter_0008`.
- **Guard:** the other ten. Nothing about them changes.

---

## The plan — three steps, in order

Each step's gate is proposed to Alessandro and agreed **before** any code, and
each step stops at its gate and reports. The gates below are proposals.

### Step 1 — the structure from pixels, checked against the source

Offline, no model, seconds per page.

- A function `structure(image, boxes) -> list[Region]`, in a new module.
- **The expected answers are written down first**: for each of the five
  targets, a handful of facts read off its source page — its regions, each
  region's flow, its column count, and the split x to within about ±0.03. The
  other ten expect no `columns` region. These are coarse page facts, not a
  reference IR; spec 0007's ban on typed references is about IR content.
- **Proposed gate:**
  - correct on `cv_0013`, `catalogue_0015`, `darkdeck_0009` and `newsletter_0008`;
  - `menu_0012` correct, or recorded as "the pixels cannot decide";
  - no `columns` region invented on the other ten;
  - tests and mypy clean.

#### Outcome — step 1, 2026-10-10, gate MET on every clause

`src/doc_to_html/structure.py`, `structure(image, boxes, *, ground, inverted)`;
pinned by `tests/test_structure.py`. Nothing in a Conversion calls it yet.

| # | clause | result |
|---|---|---|
| 1 | `cv_0013`, `darkdeck_0009`, `newsletter_0008`: the `columns` region | **holds** — 2, 2 and 3 lanes; splits 0.344, 0.643, 0.335 / 0.665 (source 0.344, 0.630, 0.346 / 0.676); **0 printed lines in the wrong region**, every line of each source read in Chrome |
| 2 | `catalogue_0015` a 3×3 grid of copies, no `columns`; `darkdeck_0009`'s tiles 1×4 | **holds** — splits 0.341 / 0.659, the grid starting below the title |
| 3 | `menu_0012` correct, or "the pixels cannot decide" | **cannot decide**, as predicted — `single`, for step 3's model question |
| 4 | no `columns` on the other ten; a grid only at `nonlatin_0014`'s panels | **holds** |
| 5 | tests and mypy clean | **holds** — 850, clean |

**How it decides.** A `grid` is a full lattice of drawn boxes of one size. A
`columns` region needs a *drawn* divider — a panel's side, a fill running the
page's height, a vertical rule — and, beside it, one block standing beside two
stacked blocks on the other side: the shape a Band cannot hold. That second
test does the work: removed, it invents columns on `invoice_0002`,
`sample_css_0004`, `statement_0006`, `form_0007`, `receipt_0010` and on
`catalogue_0015`'s cards. A whitespace gutter alone never makes a column (A2
§7), which is why the menu stays `single`.

**It reads the Zones' boxes as well as the pixels**, which the proposal said
it would not: telling `darkdeck_0009`'s aside from a float (`sample_semantic_0005`'s
TL;DR) is whether a main-column *block* runs across the panel's bottom edge,
and the pixels can say that only with a gap threshold. The test reads the
boxes committed in `tests/frozen/q5-result/`; F1-sweep's give identical answers
on all fifteen.

**The mask is "not the page's ground", not `content_ink`.** At `INK_LEVEL`
the newsletter's column rules and the deck's footer rule do not exist, and
`cv_0013`'s light sidebar type punches holes in its fill.

### Step 2 — carry it in the IR, and draw it

Offline, no model.

- **The smallest IR change that lets the renderer draw a column:**
  - `Document.regions`, and each Zone's region and lane (its column within the
    region);
  - `band` and `column` keep working for `single` and `grid`.
- **The renderer** draws a `columns` region as its lanes side by side, each a
  vertical stack of its Zones, top to bottom. Reading order follows. `single`
  and `grid` render as today.
- **Assignment:** the existing Zones of a fresh sweep (`F1-sweep`) are
  assigned to regions by their boxes. `tools/rederive.py` gains the step, per
  the standing rule that a new downstream step writing the IR goes into it.
- **Measure:**
  - `rederive.py` baseline against the arm, both over `F1-sweep`;
  - the report against the floor;
  - the visual review, all fifteen sheets, `--previous` the baseline.
- **Proposed gate:**
  - `cv_0013`, `darkdeck_0009` and `newsletter_0008` read in the source's order
    (tau up), with the sidebar and the aside drawn as a column;
  - every document with no `columns` region byte-identical outside the
    stylesheet;
  - the ratchet holds, bar the recorded N4 exception;
  - no `worse` in the review.
- **Expect `menu_0012` and `catalogue_0015` not to move** — their faults are in
  the boxes, which is step 3.

### Step 3 — let the structure shape the boxes

One sweep, model.

- **A Zone crossing a lane boundary is split at it.** `menu_0012`'s body
  becomes two lanes, each read on its own, and the caption pass gives each
  section its Title.
- **A Zone crossing a region boundary is cut.** `catalogue_0015`'s title comes
  out of the first card.
- **Copies of one design are read alike:** one Kind for the whole group.
- **Measure:** crops change, so measure what `tools/replay_run.py` can, then
  one sweep — about 1¾ hours, stated before it starts.
- **Proposed gate:**
  - `menu_0012`: two columns, four titled sections, each price beside its dish;
  - `catalogue_0015`: the title printed, the nine cards one Kind and one shape;
  - step 2's gains kept;
  - the ratchet holds.

---

## Then decide

If the targets look like their sources after step 3, **stop**: simple was
enough. If not — the structure is wrong beyond the targets, or regions need
nesting — a richer layout model is its own spec, with these results as its
evidence: nested regions, or a skeleton asked of a model.

## Out of scope

Misreadings (`statement_0006`'s amounts, `nonlatin_0014`'s footer), heading
sizes (the type scale), lost badges, pills and colours, the findings panel's
false alarms, and a repair loop.

## What this reopens, and why that is allowed

Two entries under "Closed, with evidence" in `docs/status.md`:

- **"The column model"** was closed as four renderer-only attempts over the
  flat IR. This spec changes the IR first — the gap A2 §4 named.
- **"The merged Zone"** was closed as three pixel tests inside one box. This
  spec reads structure at the page level. A2 §7's own exit says a reopened
  merged Zone is a "how many regions" question for the model, which is step
  3's fallback.

Alessandro approved the reopening on 2026-10-10.

## Rules that bind

- **The floor** is `tests/frozen/q5-result/`, with the recorded N4 exception
  (`catalogue_0015`'s T3 beside). Always score with `--documents sweep`.
- **The offline loops start from a fresh sweep** — `F1-sweep` — not from
  `q5-result/`, which predates N1–N4. If `F1-sweep` has been cleared, say so;
  re-taking it costs about 1¾ hours.
- **Any reviewed run covers all fifteen documents.** Visual review is pairwise
  and in-session.
- **Never cite a past run** — take the measurement.
- **Each gate is agreed before code**, and a sweep's cost is stated before it
  starts.
- **Keep it small:** no step adds machinery the five targets do not need.

---

## Handover prompt

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0008-page-structure.md — the only open work.

The idea in one line: the converter never decides the page's layout, so add
one small step that records it (header / body / footer; a body that is columns
read down, or a grid read across) and let the renderer, then the boxes, follow
it. Targets: cv_0013, menu_0012, catalogue_0015, then darkdeck_0009 and
newsletter_0008; the other ten must not change. Keep it small: build nothing
the five targets do not need.

Work the spec's three steps in order. Before each, propose its gate to
Alessandro and wait for his go; after each, report against the gate and stop.
Steps 1 and 2 are offline with no model; step 3 costs a sweep (about 1¾
hours), stated before it starts.

First check that debug/runs/F1-sweep exists: it is the fresh baseline the
offline loops start from. If it has been cleared, say so before anything else.

The standing rules are CLAUDE.md's and the spec's "Rules that bind". Never
cite a past run; take the measurement. Look at the pictures, not only the
numbers.
```
