# Margins from the type, one size per role

**Status: done and kept, 2026-10-19, issue #40 closed** — Alessandro: "useful per se but minor improvements". Next: spec 0018.
Both steps are render-only: no model call, no IR change, no sweep. They are
measured with `tools/rederive.py` over `tests/frozen/s12-result/`, and every
one of the 21 rederived IRs is byte-identical to the baseline's.

Alessandro's decisions, 2026-10-18:

1. **`S12-sweep` is the baseline**, frozen as `tests/frozen/s12-result/`.
2. **On the ticket:** "just cropped anyway on left side and right side and
   upper title section layout inconsistent as main text style in the body
   but overall improved". The analysis that followed ranked five general
   directions. **He chose 1 and 2 now**, render-only, and **3 and 4 as a
   spec of their own once 1 and 2 are confirmed useful**. The five were:
   1. margins from the type;
   2. one size per role;
   3. photographed pages laid out like shot ones;
   4. Zones from the drawn containers;
   5. the strip's own type.
3. **Rotation is not the ticket's cause.** On the CV-only layout front,
   the same pass gives 6 Zones rotated, 17 unrotated on its desk and 15
   unrotated as a plain screenshot, and none of the three is right. Turned
   1.5° on a desk, 7 of the 20 comparable corpus pages keep fewer than
   three quarters of their Zones. That is direction 3's evidence, not
   this spec's.

---

## How to work

- **By eye**, the ticket first, against `S12-sweep` (whose renders are
  `s12-result/`'s documents):

  ```
  tools/rederive.py tests/frozen/s12-result --label <label>
  tools/visual_review.py debug/runs/<label> --previous debug/runs/S12-sweep --documents <moved>
  ```
- **A page moves only if its markup moves.** Every step lists the pages
  whose HTML differs from the baseline (outside the embedded IR), and each
  one is opened.
- Scores are not taken. Nothing in the IR moves, so no word can vanish.

---

## §1 What the ticket shows, and why

From `s12-result/ticket_0020.html`, its IR and its markup.

| on the page | in the render | cause | step |
|---|---|---|---|
| The field grid is set 22px in from the card's edge | It is drawn against the card's edge | The row's left edge is the strip's: the fill and the wordmark crop run to the paper's edge (`z1` at x 0.000). A row of one unit draws that unit at the row's left, wherever its type starts | **1a** |
| The stub's text is set 21px in from the perforation | It touches the perforation, `padding-left:0px` | The stub is one Zone whose box starts on the perforation (x 0.736) and its type at 0.762. `_placed` sets each line from the leftmost entry, so the box's inset to its type is lost | **1b** |
| `NL 0482` is set like `14 OCT 2026`, `07:35` and `08:05` | It is drawn at the body's size beside them at 1.50 | `locate` never placed it, so it has no measured look | **2a** |
| The stub's five values are one size | 1.25 and 1.38, mixed | The measure's noise: 0.12 em nine times in ten (`SIZE_STEP`) | **2a** |
| `PASSENGER` is a grey label, as in the stub | Bold, in the page's ink, the one label not muted | The caption pass lifted it into Zone 3's Title. Measured 0.88 among labels of 0.88 and 1.0, it is set as they are | **2b** |

---

## Step 1 — margins from the type

**1a. A row keeps its first unit's inset from the row's left edge**
(`render._indent_in_row`, `_indented`). The row's left edge is the left
of its reach (`_span`). Where the first unit stands in from it by more
than `ALIGN_SLACK` body ems, it is drawn that far in:
- in pixels where it is the row's only part;
- otherwise as a share of the row, which its lane gives up.

**Not** for:
- a unit set centred or flush right, whole or by its Blocks
  (`_block_aligns`), which `text-align` places;
- a list, whose box starts at its marker or at its text as the detector
  drew it;
- a unit inside a frame other Zones share, which `_framed` pads to it.

**1b. A Zone drawn by its printed lines keeps the inset from its box to its
type** (`_placed`). `margin-left` on `.placed` where the box starts more
than `ALIGN_SLACK` short of the leftmost entry. **Not** in a frame, a card,
or on a fill: a painted lane already pads to the type (`_columns`, spec
0012 G4).

**The first version moved five more pages, three for the worse**, each found
by opening its sheet:

| page | what it did | the exclusion it called for |
|---|---|---|
| `paper_0018` | its centred title, pushed 185px in by its own centring, wrapped one word early | units centred by their Blocks |
| `pricing_0017`, `certificate_0021` | centred headers and body moved off the page's centre (by eye no visible change on these two) | the same |
| `sample_semantic_0005` | its second and third bullets, a Zone of their own boxed from their text, stood 24px in from the first | lists |
| `cv_0013` | `REGISTRATION` in the painted sidebar stood in twice, 15px | 1b not on a fill |

**Measured, with the exclusions:** only the ticket's markup moves, the
other 20 byte-identical. On the ticket the field grid section takes
`margin-left:22px`, and the stub's `.placed` takes `margin-left:20px`.
**By eye: better.** The grid sits in from the card's left edge and the
stub's text off the perforation, where the source sets them.

**How general it is.** The rule is general in form and, on the corpus,
proven only on the ticket: no other page has a row whose edge is set by a
fill or a figure that runs further out than its type, nor a line-drawn
Zone boxed wider than its type off a fill. The five first-version moves
are what any page with centred Blocks, lists or a painted lane would have
done. The exclusions are why it moves nothing else.

---

## Step 2 — one size per role

**2a. A role's group is drawn at one size** (`render._role_sizes`).
- **The group.** The entries of one role, label or value, linked by
  sharing a printed line or a column (`_aligned`): a grid's values are one
  group and its labels another.
- **When it applies.** Where at least `PEERS` (3) of a group are measured.
- **What changes.** Every entry with no size, or one within `SIZE_STEP` of
  the group's median, takes the median. A size further from it than the
  noise is the page's own and stays.
- **Entries outside any group.** A Title or a Zone's extra lines.
- **The IR keeps what was measured.** The render draws the group's size.

**The first version only traded the stub's sizes.** Each entry took the
median of its own line and column. `C14` went to 1.25 just as
`HALVORSEN / A` went to 1.38. The group rule settles all five values at
1.38.

**2b. A Title measured as its labels are is the first value's label**
(`_title_as_label`, `_title_label`). The rule fires when:
- the first pair has a value and no label;
- the Title is set at the Zone's left;
- its size is within `SIZE_STEP` of the other labels' median, at least
  `PEERS` measured;
- its ink is within `COLOUR_APART` of theirs.

It is then drawn as a label line over the value (in `_printed_lines`, so
in a lone Zone and in a grid of several), and not as a heading.
`darkdeck_0009`'s `COST PER MILLION`, 0.7 over labels of 0.9 in red, stays
a Title; so does `TRD`, whose size was not measured.

**Measured:** two pages' markup moves.
- **`ticket_0020`:**
  - `PASSENGER` becomes `<span class="label">`;
  - `NL 0482` goes from body size to 1.50;
  - the main grid's `2` goes from 1.38 to 1.50;
  - the stub's `HALVORSEN / A` and `2` go from 1.25 to 1.38;
  - line spacing moves 1px.
- **`catalogue_0015`:** one line's `margin-top`, 4px → 5px.

**By eye:**
- **ticket: better.** One label style across both panes, and the values
  one size in each grid.
- **catalogue: same.** The 1px is not visible.

**Left as it was:** the catalogue's three small prices (`£9.80`,
`£28.00`, `£22.40`). Each is the one value of its role in its own card,
so no group reaches it. Their peers are the same entries in the other
cards, which are copies. A group across copies is a separate rule, and
not taken here.

---

## Outcome

Steps 1 and 2 together, `S13-2-proto` against `S12-sweep`. Only the
ticket and the catalogue's markup move, and only the ticket visibly:
- **`ticket_0020`: better.** The type stands where the card and the
  perforation set it, `PASSENGER` is a label, and its values are one size
  per grid.
- **`catalogue_0015`: same.**
- **The other nineteen: byte-identical.**

**Left on the ticket, for the next spec (directions 3 and 4) or for
Alessandro to name:**
- the halo Zone `The` / `The`, which makes the strip about three times
  its height;
- `NORDLYS AIR` drawn as a picture;
- the stub's strip text;
- `OSL` and `TRD` at body size;
- the barcode and the plane.
