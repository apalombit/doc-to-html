# Place every entry where the page puts it — rhythm, location, fields, lines

**Status: under way, issue #34. Step 0 DONE 2026-10-12; step 1 next.**

Alessandro's decisions, 2026-10-12, after reviewing sweep `S5-sweep` (spec
0010's outcome):

1. **`S5-sweep` is the baseline.** Every step is compared against it, and it
   is frozen as `tests/frozen/s5-result/` at step 0. The five legs it sits
   below `s3-result/` on (spec 0010, "Outcome — step E", §5) are accepted and
   recorded.
2. **Judge by eye, not by score — for this spec.** See "How to work" below.
   He checks every run himself as well.
3. **Implement the attack plan whole**, in the order below. The steps are not
   meant to be small; they are meant to fix the faults he named.

---

## How to work — Alessandro's operating preference for this spec

**Visual judgement decides; numbers are recorded, never gating.**

- Every step ends with sheets: `tools/visual_review.py <run> --previous
  <previous step's run>`, all fifteen documents. Open **every sheet whose
  render moved** and judge it against the source: `better / same / worse`,
  with one sentence naming the element. That judgement is the gate.
- `report.html` and `scores.json` are still produced for every run (CLAUDE.md
  requires the review surface), and the scores are **recorded in the step's
  outcome without argument**. A ratchet leg that falls is noted and accepted.
  Do not tune anything to move a score, and do not argue from one.
- **One number is still read: the report's `vanished` list** — source words
  the output stopped printing. Content must match absolutely, and a missing
  word is hard to see by eye. It is a pointer to the sheet, not a gate: open
  the page and look.
- Judgements are pairwise and in-session, as CLAUDE.md says. Never compare a
  sheet with one from another chat.
- **Each step ends with a short report to Alessandro**: what the pages look
  like now, the `report.html` path, the sheets that moved. He reviews every
  run himself. Continue to the next step unless a page got worse — then stop,
  show it, and ask.
- Commit each step on its own.

---

## 1. The faults, as Alessandro named them, and their causes

Each was traced on `S5-sweep` on 2026-10-12 by printing the IR's Zones and
measuring the source pixels. Zone indices are `S5-sweep`'s.

| document | what he saw | what is actually happening | stage |
|---|---|---|---|
| `form_0007` | fields listed one column, `label value`, where the page sets two fields side by side, each a label over a box | **Segmentation is right**: one Zone per printed section, each opening on its heading. The model reads each section as `pairs` (Zone 2: 8 pairs) with no position, and `render._pairs` stacks them in a `dl`. The page's own pixels hold the whole layout (below). | IR + Render |
| `form_0007` | the squares are missing | Tick boxes and the date-of-birth digit boxes are below `style.MIN_RECT_SHARE` (0.004), so `rectangles()` never sees them. Zone 3's list reads the five options as five lines of **one** item, with no tick state. | Style + IR |
| `newsletter_0008` | each column split into chunks | Each paragraph is its own Zone — left column Zones 6, 10, 13; middle 7, 9, 11, 15; right 8, 12, 14. On the page they sit **13–16px** apart, ink to ink. The renderer puts `.band { margin-bottom:1.75rem }` (28px) plus `p { margin-bottom:.4em }` between any two, about 40px. | Render |
| `darkdeck_0009` | right card runs to the bottom of the table, text spread out | The OPEN RISKS panel is **six Zones**, one per bullet (7, 8, 9, 11, 13, 14), each its own `<ul>`, 28px apart. The panel rectangle (643,302)-(966,610) holds all six, and `style.boxes_for` deliberately gives it to none of them: `ir.Zone` never nests, so the IR cannot say "these six share a box". | Render + IR |
| `receipt_0010` | dashed separators missing | `S5-sweep`'s receipt has **no separators**. The dashed rules lie *inside* Zone 1, one 18-row table, and `structure.separators` finds only solid wide rules *between* Zones. The centred header lines render left. | Style + Render |
| `menu_0012` | section titles not centred, spacing and type per line | Each column is one `table` Zone (Zones 1, 2: 13 and 9 rows). Section heads (`From the grill`, `PUDDINGS`) and the italic notes are rows drawn in the house table style — left-aligned, one size, a rule under every row. The page centres its heads in small capitals, sets notes small and italic, draws leader dots and no row rules. | Style + Render |

**The common cause.** Since spec 0008 the IR knows where every *Zone* sits;
it knows nothing about where anything *inside* a Zone sits. `ir.Cell.bbox`
exists and is never set. Everything inside a Zone — the form's grid, the
spacing between rows and paragraphs, which line is centred, which is italic,
where a rule falls — is drawn in the house style, because nothing records
the page's. And *between* Zones the renderer uses one fixed gap, though the
Zones' boxes are known.

### What the pixels already give, measured 2026-10-12

**The form's whole field layout.** `style.rectangles()` on `form_0007`
finds 13 field boxes: 371×27 half-width ones in two columns (x 28–399 and
421–792) and 764×27 full-width ones. With `MIN_RECT_SHARE` lowered to
0.00005 it also finds:
- the 8 date-of-birth digit boxes, 21×23 at y 209;
- 5 tick boxes, 14×14 at y 457, in section 2;
- 3 tick boxes, 14×14 at y 942, in section 5;
- one 16×6 speck of noise.

Section 1's 8 pairs match its 8 fields one for one, counting the digit comb
as one field. Section 3 has 2 boxes and 2 underline fields: `Highest level…`
and the medical-condition lines. Section 4 was read as a 4-row table — `Name |
Relationship`, `Peter Whitlock | Father`, `Daytime telephone | Alternative
telephone`, `01632 960 774 |` — over 4 boxes.

**Every line's position, from tesseract.** `/opt/homebrew/bin/tesseract`
5.5.2 is installed, with `eng` and `ell` among its languages. Run on
`form_0007`'s page it returns every printed line with word boxes in **0.37s**.
Its own reading is poor on small capitals and a few words (`appticanr
beraits`, `Postoode`, `Altemative`, `1][4][olfe]`). That does not matter for
locating, because its text is only matched against the model's, never used.

**Spacing from the page — probed, offline, not committed.** Each Band's
`margin-bottom` was set to `max(0, page ink gap − 1.3 × body_px)` — the ink
gap less the leading and paragraph margin CSS adds around a line's ink —
inside lanes and between page rows. It was run through `tools/rederive.py` over
`S5-sweep`, whose plain rederive reproduces `S5-sweep` byte for byte. Looked
at:
- **Newsletter:** each column reads as continuous text with paragraph spacing
  like the source.
- **darkdeck:** the right card is compact and ends where its text ends.
- **Heights against the source:** newsletter 1.36 → 1.13, cv 1.67 → 1.32,
  report 1.21 → 1.02, form 1.08 → 1.00.
- **One fault:** `sample_css_0004`'s gap between its cards grew (1.01 → 1.17),
  because a card's padding is counted twice. The Zone is snapped to its text,
  so the measured gap includes the card's inset, and the render adds its own
  padding again. **Around a drawn box, measure from the box's edges.**

---

## 2. Design constraints

- **ADR 0002 and 0005: positions drive structure, never absolute
  placement.** A located entry gives grid tracks, a field's box, an alignment,
  a size, a gap. It never becomes `position:absolute`. A `<table>` stays a
  `<table>`, a pair stays a `dt`/`dd`.
- **ADR 0001: no document types.** "A value drawn inside a box", "a run of
  digit boxes", "a tick box", "a dashed rule", "a centred line" are page
  constructs found on any page. Nothing branches on "form" or "receipt".
- **The words are the model's.** The locator (tesseract) only says *where*.
  Its text is used to match and never printed, never added, never
  substituted.
- **Zero model calls.** Every step is downstream of the model. So each is
  measured offline over `S5-sweep`'s answers, by replay or rederive, in
  minutes. A step that changes a crop or a prompt is outside this spec.
- **Deterministic.** tesseract is deterministic for fixed input and flags.
  Pin the flags in one place.
- **Every new step that writes the IR goes into `tools/rederive.py`** —
  and into `tools/remeasure_style.py` if it is a style measurement. Otherwise
  the loop measures yesterday's code. A renderer-only change needs no step.
- **A new stage sits after every model call.** The inline-runs pass (`runs`
  answers) asks one question per prose and list Zone *after* extraction.
  Merging or splitting Zones before it changes the questions and the
  replay is marked ASKED MORE THAN THE RUN. Group Zones, do not merge them.
  The Zones and their indices stay; probes, caveats and findings refer to
  them.

---

## 3. Work plan

| step | what | runs on | targets |
|---|---|---|---|
| 0 | freeze `S5-sweep` as `tests/frozen/s5-result/` | — | the baseline |
| 1 | **Rhythm** — gaps from the page, Zones grouped, alignment | rederive | newsletter, darkdeck, menu heads, receipt header, statement/nonlatin/invoice meta, cv, report |
| 2 | **Locate** — every entry's box on the page | rederive (new IR field) | enables 3 and 4 |
| 3 | **Fields** — boxes, tick boxes, digit boxes, underlines | rederive | form |
| 4 | **Lines** — per-entry type, colour, rules inside Zones, leaders, spacing | rederive | menu, receipt, catalogue, darkdeck, statement |
| 5 | one sweep, `S6-sweep`, all fifteen | the model | the record |

The order is the dependency order. Step 1 needs no location and is proved.
Steps 3 and 4 need step 2.

### Step 0 — freeze the baseline

Copy `S5-sweep`'s fifteen documents, its `scores.json` (against `s3-result/`),
its answers and its `dth_env.txt` into `tests/frozen/s5-result/`, the way spec
0009's step 0 froze `s3-result/` (read that README and copy its shape). The
README names:
- the provenance: commit `4a5fe3f`, 518 answers byte-identical to `S4-sweep`'s;
- the five legs below `s3-result/`, accepted 2026-10-12;
- that **for spec 0011 scores are recorded, not gated**.

Prove that `tools/replay_run.py tests/frozen/s5-result` reproduces it 15 of 15
byte for byte, and that `tools/rederive.py` over it does too. Repoint the
floor in CLAUDE.md, `docs/status.md` and `tools/replay_run.py`'s usage. Keep
`s3-result/` as record.

**Done when:** both loops reproduce 15 of 15.

**Outcome — step 0, 2026-10-12: DONE.** `tests/frozen/s5-result/` holds
`S5-sweep`'s fifteen documents, its `scores.json` against `s3-result/`, its
518 answers and its empty `dth_env.txt`. At commit `72477f2`:
`tools/replay_run.py` over it **15 of 15 byte-identical** (13s);
`tools/rederive.py` over it **15 of 15 byte-identical** (`S6-0-base`, 5s);
that rederive scored against `scores.json`, **15 documents, 0 differing
fields**. The 518 answers are byte-identical to `S4-sweep`'s, checked on
both runs' traces. The baseline is repointed in CLAUDE.md, `docs/status.md`
and `tools/replay_run.py`; `s3-result/`'s README is marked record.
`debug/runs/S6-0-base` is the baseline as a run directory, and step 1's
sheets use it as `--previous`.

### Step 1 — Rhythm: the page's gaps, its groups, its alignment

**1a. Gaps from the page.** Between consecutive rows — page Bands, the Bands
inside a lane, a grid's rows — draw the page's own gap. Use the formula
probed above, `max(0, ink gap − 1.3 × body_px)` px. Where a Zone has its own
drawn box, measure from the box, not from its snapped text.
- Record each Zone's drawn frame in the IR: a new `Zone.frame: BBox | None`,
  set in `_measure_chrome` from `style.boxes_for`, which already computes it.
- Add it to `remeasure_style.py`.
- `.band`'s fixed `margin-bottom:1.75rem` becomes the fallback for a Zone with
  no box. The probe's code is not kept; the formula is the whole of it.
- Check that `render._with_separators` still puts a rule inside the gap.

**1b. Zones that continue one another are drawn as one.** Two consecutive
Zones in one lane continue one another when all of these hold:
- the later one has no Title;
- they have the same Kind (prose with prose, list with list);
- they have the same fill;
- their left edges agree;
- the gap between them is no more than about 1.6 × the line pitch measured in
  the Zone above.

Record it as a group — `Zone.group: int | None`, Zones with one value forming
one run — decided after every model call, from boxes and pixels only.
- **Render a group as one `<section>`:** a list group as one `<ul>`, a prose
  group as consecutive paragraphs, under the first Zone's Title.
- **A drawn box that holds exactly one group is that group's frame.**
  `boxes_for` refused darkdeck's panel because six Zones claimed it. Six Zones
  in one group is one claimant, so the card is drawn once around OPEN RISKS
  and DECISIONS WANTED.
- **Do not merge Zones in the IR.** Indices must stay stable, and merging
  before the runs pass changes what the model is asked (§2).
- **What not to group:** a Zone carrying a Title starts a new group. That keeps
  DECISIONS WANTED as its own list under its own heading, inside the same card.
  Check the cv sidebar, the menu and the receipt on their sheets; none should
  regroup wrongly.

**1c. Alignment from the page** (ADR 0005 lists alignment as measured). Two
measurements, both from ink, no location needed:
- **Where a Zone sits in its container** — the page's content width, or its
  lane. The newsletter masthead, the menu masthead and the receipt header are
  centred on the page. Statement's `Account…` block, `nonlatin_0014`'s `ΤΠΥ
  2026/0417` block, `invoice_0001`'s `Invoice #` block and darkdeck's `Q3 2026
  · INTERNAL` sit at the right edge.
- **How its lines align** — right edges agree with lefts varying → right;
  centres agree → centre. And **where the Title line sits over the Zone's
  extent**: the menu's `To begin` and `Main courses` are centred over their
  columns.

New fields `Zone.align` and `Zone.title_align`, each one of `left / centre /
right`. Render with `text-align`, and a Zone that does not span its row pushed
to its side. **Set the tolerance from the distribution across the corpus** —
the `keep_runs` lesson in CLAUDE.md — not from a round number.

**Done when** the sheets show:
- `newsletter_0008`'s columns read as continuous text;
- `darkdeck_0009`'s risks card is one compact card with two lists;
- `sample_css_0004`'s card gap is no larger than the source's;
- the mastheads and the menu's section titles are centred;
- the meta blocks sit right;
- no page is worse.

### Step 2 — Locate: every entry's box on the page

A new module, `locate.py`, and a stage after `_measure_type`. It fills
`Cell.bbox` (page-normalised, the same frame as `Zone.bbox`) for every Cell
it can place: Block lines, row cells, pair labels and values, list items.
- **Input:** the Zone's crop of `Rectified.plain`, in the Zone's own polarity
  (invert a dark-ground Zone — the logic `style.type_mask` already uses).
  Upscale so that body text is about 30px tall, since tesseract reads 11–16px
  type poorly.
- **Run:** tesseract via `subprocess` (no new Python dependency), TSV output,
  word boxes. The language comes from the model's text: `ell+eng` where it
  holds Greek. Flags are pinned once.
- **Match:** each Cell's normalised tokens to a contiguous span of OCR words,
  by fuzzy similarity (character-level; digits must agree). A Cell's box is
  the union of its span's word boxes.
- **The hard cases**, each seen in the corpus:
  - **Repeated text** — `Healthy` five times, `CRD` dozens: use the Cell's
    order, its row index against the row bands, and its column against the
    column edges.
  - **Zones whose columns tesseract reads across** — the form's `Family name
    Given names` came back as one line: match per Cell, not as one sequence.
  - **Letter-spaced capitals tesseract misreads**: fall back to the Zone's
    ink lines (`style.type_lines`) in reading order.
  - **The photographed receipt.**
- **A Cell left unplaced stays `None`.** The renderer must treat it exactly as
  today.

**The check is a picture, not a number.** Write an overlay per document: the
source image with every located box drawn and labelled with its Cell's first
word. Open all fifteen. Every box should sit on its own words.
- Sanity check against the corpus's own truth: `projection.project()` of the
  source HTML gives each text block's box, so a located Cell whose text
  matches a source block should land on it. Report how many Cells were placed
  per document as a diagnostic, not a gate.
- Nothing in the render changes in this step. The HTML moves only inside the
  embedded IR (see "A clause about bytes" in CLAUDE.md).

**Done when** the overlays show the boxes on their text on all fifteen pages,
with the misses named.

### Step 3 — Fields: the form's grid, boxes, ticks and digit boxes

**3a. Find the marks** inside each Zone's box, from pixels:
- **value boxes** — `rectangles()` with a size floor relative to body text,
  not to the page;
- **digit combs** — three or more equal small boxes in a row with gaps under
  half a box;
- **tick boxes** — a square about the size of the text's x-height to
  cap-height, beside a label;
- **underline fields** — a horizontal rule under a label's line with no text
  on it, or with the value on it.

**Tick state** is the ink inside the box's interior, excluding its border,
measured over every tick box in the corpus. **Set the threshold in the gap of
that distribution.** The page ticks `Full rowing`, `Locker required`, `I can
swim…` and `I accept the club rules`.

**3b. Put the reading into them.** With the located Cells from step 2:
- A pair whose value lies inside a box is a field: `label` above, value in the
  box.
- A list item's lines that sit each beside a tick box become one option per
  box, with its state.
- A table whose alternate rows sit above and inside boxes is a grid of fields
  — Zone 5's four rows become `Name: Peter Whitlock`, `Relationship: Father`,
  `Daytime telephone: 01632 960 774`, `Alternative telephone: —`.

Nothing is invented or dropped: every word placed is a word the model read. IR
fields such as `Pair.box`, `Pair.mark` (`box / comb / tick / line`) and
`Pair.ticked` — name them in the step, and keep them generic.

**3c. Draw them.** A Zone of fields is a CSS grid whose tracks are the page's,
clustered from the boxes' x-extents: two half-width columns, and full-width
fields spanning both.
- each field: a small muted label over a bordered box holding the value;
- a comb: a row of small boxes, one digit each;
- a tick box: a bordered square, crossed when ticked;
- an underline field: its value on a bottom rule;
- signature lines: an empty rule with the label beneath, as printed.

**Done when** `form_0007`'s sheet shows the page's two-column field grid,
boxes, digit boxes and ticks in the right boxes; no other page moves unless
it draws such marks; and no page is worse.

### Step 4 — Lines: what each entry looks like

With every Cell placed, measure per entry, from its own pixels (ADR 0005 —
never asked):

| sub | what | where it shows |
|---|---|---|
| 4a | **size, weight, italic.** Size is the glyph height in ems of the body (`style.glyph_height`). Bold means the stroke width is clearly above the Zone's median — find the gap in the distribution. Italic means the slant angle that best sharpens the vertical ink profile is above the upright ones. | catalogue names bold and prices large; darkdeck tile values large and bold; statement summary figures; the menu's small italic notes |
| 4b | **colour and fill** — the entry's modal ink, and a fill behind it when its box sits on one | statement red/green amounts; catalogue `3 left` and `Back order`, its dark SKU chips and orange NEW badges; darkdeck's green/red deltas and its Healthy / At risk pills |
| 4c | **rules inside a Zone** — solid, dashed or double — between located rows or blocks. A dashed rule is a row of three or more equal short dashes spanning most of the Zone. **Row rules only where the page draws them**, and alternate-row shading where it shades. | the receipt's dashed rules between its groups and its rule above TOTAL; the menu with no row rules; the statement's zebra rows |
| 4d | **leader dots** — a dotted run between a row's first cell and its last on one line | the menu's dish lines |
| 4e | **spacing inside a Zone** — the gap between located paragraphs, items and rows, as step 1a does between Zones | paragraph spacing in prose, list items, the receipt's line pitch |
| 4f | **typeface class, optional and last** — serif, sans or mono, from stroke terminals and from equal advance widths for mono. ADR 0005 de-prioritises family, so stop if it is not clearly right. | newsletter, menu, report and sample_semantic are serif; the receipt is mono |

Each sub-step is its own commit and its own sheets. A sub-step whose sheets
show no page better is dropped and recorded.

**Done when** the targets above look like their sources on the sheets and no
page is worse.

### Step 5 — one sweep, `S6-sweep`

All fifteen, shipped defaults. Nothing in steps 1–4 changes a crop or a
prompt, so **predict that the answers come back byte-identical to
`S5-sweep`'s** and the HTML byte-identical to step 4's last replay. Register
that before the sweep finishes. Open all fifteen sheets against `S5-sweep`'s.
Record the scores. Report what the pages look like, in spec 0009's §7 format,
leading with the pages. Whether `S6-sweep` becomes the baseline is
Alessandro's decision.

---

## 4. What this spec does not fix

| fault | why not |
|---|---|
| `menu_0012` `béarnaise`; `form_0007` `fempost`; `statement_0006` 1,141.30 and 210.08 | the model's reading of the pixels |
| `form_0007`'s `Tick one category. Locker allocation is subject to availability.` — not read | the list reading dropped a non-item line (Extract) |
| `newsletter_0008`'s drop cap turning the first sentence into a heading | Extract |
| `darkdeck_0009`'s P95 tile read as a three-row table | Classify → Extract |
| `cv_0013`'s first job title run together with its employer | Extract |

**Two follow-ons step 2 makes possible, neither in this plan** — Alessandro's
call after it lands:
1. **A second reading.** Where tesseract's words disagree with the model's on
   digits, that is the `CellState.DISPUTED` the IR has always had a word for
   and never a second Engine to produce. It is the only route seen to the
   statement's misreads.
2. **Lines no entry claims.** A located OCR line that matches no Cell is ink
   the model did not read — the form's tick note is one. *Reported*, never
   inserted. That is new evidence for the honesty question Phase A-1 closed:
   "do not build a third detector without a new kind of evidence".

---

## 5. Where things are — a map for the session that implements this

| what | where |
|---|---|
| stage order of a Conversion | `orchestrator.Conversion.run`: `_layout` → `_classify` → `_draw_figures` → `_extract` (then `_restore_vetoed_captions`, `_measure_shortfalls`) → `_measure_chrome` → `_measure_type` → `_find_separators` → probes → `_audit` |
| Zone frames, fills, title bars | `_measure_chrome`, `style.chrome`, `style.rectangles`, `style.boxes_for` |
| type measurement | `style.type_mask`, `type_lines`, `glyph_height`, `body_glyph`, `title_sizes`, `heading_sizes`; `orchestrator.body_px` |
| regions and lanes | `structure.structure`, `ir.Region` (`lane_of`, `holds`); separators: `structure.separators` |
| rendering | `render._body` (page rows) → `_columns` (lanes) / `_grid` → `_band` → `_zone` → `_pairs` / `_table` / blocks; `_with_separators`; `_style_css`; `STYLESHEET` (`.band` margin is the fixed gap) |
| the loops | `tools/rederive.py <run> --label X` (IR-only, about a minute — add every new IR-writing step to it); `tools/replay_run.py <run> --label X` (answers through a real Conversion, about 13s — refuses an existing label, so remove the directory first); `tools/remeasure_style.py` |
| review | `tools/visual_review.py <run> --previous <run> [--documents a,b]`; fill `_review/findings.json`, then `--check` |
| scoring (recorded only) | `python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b --documents sweep --previous tests/frozen/s5-result/scores.json` |

**A Zone printer worth writing first** (the one used for §1 was a scratch
script): load the embedded IR from a run's `document.html` (`id="doc-ir"`,
`ir.Document.from_json`), and print each Zone's index, kind, band/column,
bbox, title, fill, boxed, and its rows/pairs/blocks. Nearly every question in
this spec starts there.

---

## 6. Rules that bind

- The operating preference at the top: **by eye, numbers recorded**.
- **Never cite a past run.** Take every picture and number in the session
  that reports it.
- **Any reviewed run is a full sweep's worth of documents** — all fifteen
  sheets, every one that moved opened.
- Commit each step. A step whose sheets show a page worse is reverted or
  repaired before the next, and recorded.
- **Do not reopen** anything in `docs/status.md`'s "Closed, with evidence"
  without a new kind of evidence. Located entries are new evidence for some of
  it — say so when that is the argument.

---

## Handover prompt — start of spec 0011 (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0011-place-every-entry.md — the only open work, issue #34.

In one line: since spec 0008 the IR knows where every Zone sits and
nothing about where anything inside a Zone sits, so the form's field grid,
the spacing between paragraphs and Zones, centred lines, italic notes and
dashed rules are all drawn in the house style. This spec draws the page's
own gaps and alignment, locates every entry on the page, then draws fields
and per-line looks from it — all downstream of the model.

Alessandro's operating preference for this spec, 2026-10-12: judge every
step by opening the sheets, not by scores. Scores are recorded, never
gating, never argued from; the only number read is the report's `vanished`
list, as a pointer to look. He checks every run himself too.

First check debug/runs/S5-sweep still exists — it is the baseline and the
only copy of its answers until step 0 freezes it as
tests/frozen/s5-result/. If it is gone, say so before anything else (it
can be remade: FIXTURE=sweep tools/iterate.sh on commit 4a5fe3f reproduces
it at temperature 0, about 1h45m).

Then do step 0, then steps 1 to 4 in order, each its own commit and its
own sheets against the previous step, reporting each to Alessandro with
what the pages look like and the report.html path; continue unless a page
got worse. Step 5 is one sweep. The standing rules are CLAUDE.md's and the
spec's §6.
```
