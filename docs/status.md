# Status — 2026-09-21 (Thread 2/B: palette, per-Zone chrome and the review skill shipped; borders next)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file, then
[`agents/visual-review.md`](agents/visual-review.md) if you are going to look at
output — and you should.

Branch `scaffold`. **669 tests pass, `mypy src/` clean.**

---

## Where we are

Thread 0 (scorer, corpus, report) and Phase A-1 (nothing loses content quietly)
are done; A-1's honesty gate was **not** met and the reason bounds later work —
see "What A-1 settled" in CLAUDE.md. **Thread 2/B is in progress**: the palette
and per-Zone chrome have shipped, page width is measured but deliberately not
drawn, and the border detector is the next increment.

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      IN PROGRESS   <- you are here
  |- palette + page width                       DONE 2026-09-20
  |- per-Zone chrome (fills, title bars)        DONE 2026-09-21
  |- review workflow -> reusable skill          DONE 2026-09-21
  |- borders (Zone.boxed is 0 on all fifteen)   NEXT
  \- type scale                                 deferred, reasons below
Phase A0    Stop the bleeding                   after 2/B
Phase A1/A2/A3, Thread 3/C, Thread 4/D          unchanged
```

**The T1 ratchet's notch is `tests/frozen/a1-checkpoint/scores.json`.** Ratchet
against it by path; `debug/` is gitignored and gets cleared.

---

## The big change this session: we started looking at the output

`tools/visual_review.py` builds a source-beside-render sheet per document plus a
seven-axis rubric. On 2026-09-21 it ran over **all fifteen** documents and found
nine cross-cutting faults. **No scored axis had reported any of them.**

**That is now a standing rule: any run whose output will be reviewed covers all
fifteen documents, not the iterate five.** The five are all light-grounded, all
similar, and none of the ten documents authored after the target changed.
Alessandro is willing to wait the ~90 minutes. `iterate` remains fine for a
throwaway check nobody will draw a conclusion from.

**A renderer-only change needs no new model run.** Everything pixel-derived —
the Style Record, Zone chrome — can be measured post-hoc and the IRs re-rendered
offline, so one sweep serves many render iterations. That is how three fixes
were verified across fifteen documents this session with zero model time.

The workflow is now the **`visual-review` skill**
(`.claude/skills/visual-review/`), backed by `doc_to_html.review` and
`tests/test_review.py`. [`agents/visual-review.md`](agents/visual-review.md) is
the record behind it: the evidence for its rules, what the rubric must never
become, and what it still cannot do.

---

## Thread 2/B — what has shipped

All CV, **zero model calls**, behind `DTH_STYLE_RECORD` (default on), named
explicitly on the bake-off's `Conversion` so the arm is provably armed.

### Palette

`style.measure()` returns ground, ink, accent and shade. Four findings hold it
up, each of which a future session would otherwise waste a day rediscovering:

- **Colour is measured on `Rectified.plain`, never the equalised image.** CLAHE
  is what makes faint type legible and what makes colour unreadable.
  `darkdeck_0009`'s first KPI card stands **31** channel-sum from its page in
  the source and **5** after equalisation — under `SAME_COLOUR`, so every card
  on that page read as unfilled — and the page's true `(18,22,28)` read as
  `(0,0,6)`. `rectify` now keeps an un-equalised copy at identical geometry.
- **The ink *mask* still comes from the equalised image.** Which pixels are type
  is exactly what equalisation is for. `receipt_0010` is the corpus's only
  photographed page and its paper is not uniformly white: thresholded on plain
  pixels, the texture reads as ink and the render sets pale grey type on a
  black-printed receipt. Mask from one array, colour from the other, identical
  geometry.
- **The ground is the page, not the biggest thing on it** — measured over the
  outer 6% frame (`MARGIN_SHARE`). `sample_css_0004` is white paper carrying two
  large `#f6f8fa` cards; a mode over the whole image returned the card colour,
  which tinted the entire render *and* made the cards undetectable, since a fill
  equal to the ground is not a fill.
- **`dominant()` reports the bucket's real colour, `modal()` its identity.**
  Bucketing floors, so `255 // 8 * 8` = 248 and every white page rendered on
  `#f8f8f8`. A comparison only needs the bucket; emitted CSS needs the colour.
  `scoring` keeps `modal`; `style` uses `dominant`.

`MIN_INK_CONTRAST = 0.35` refuses to claim an ink with too little contrast
against its page. Real corpus inks sit at 0.51 and above; `receipt_0010`'s false
reading sat at 0.23. Refusing is honest — the house ink is a known-safe default
and a measurement that weak is not evidence.

### Per-Zone chrome

`style.chrome()` measures a region's fill, its Title band's fill, and whether it
is bordered. `Zone.fill` / `Zone.title_fill` / `Zone.boxed` carry them and
`render._zone` draws **only what was measured**.

**`section.titled` is gone.** Having a caption no longer implies a card. The old
rule drew a bordered panel with a shaded bar round every titled Zone — on
roughly ten of fifteen documents whose sources draw nothing of the kind.

Bars now land correctly on `invoice_0002` (3), `nonlatin_0014` (2),
`form_0007` (1) and `invoice_0001` (table headers); `report_0011`,
`sample_table_0003` and `menu_0012` correctly get nothing.

`SAME_COLOUR` is **18**, not 24. `sample_css_0004`'s `#f6f8fa` cards sit 21 from
white and missed by three. Swept at 24/18/15/12/9: 18 gains exactly those two
cards and `sample_semantic_0005`'s TL;DR aside, all three real fills, and
changes no other document at any value. Flat from 18 down to 9 — **a plateau,
not an edge**, which matters more than the number.

### Three inventions removed, each reported from a picture

- **`--shade` is derived from the measured pair, never the measured page-wide
  shade.** It put beige bars on `receipt_0010` and tan on `menu_0012`, whose
  sources draw no fill anywhere, and came out accent blue on `cv_0013`. Two
  discriminators were built to tell a real band from texture — coverage share,
  and the longest run of mostly-that-colour rows — and **neither separated
  them** (`receipt_0010` 2.7% against `invoice_0002`'s real 1.9%; runs of 0-2
  across the board). A-1's rule applies: **no third detector without a new kind
  of evidence.** Real fills still travel per Zone, inline, where they are
  accurate. A derived shade can never introduce a hue.
- **The accent is declared and not spent.** Colouring `h1` turned all of
  `sample_css_0004`'s navy headings blue; underlining `h1` instead drew three
  rules `sample_semantic_0005` does not have. Where a page *puts* its accent is
  a detection problem, not a palette one. The token stays so a later pass can
  spend it without re-measuring.
- **Page width is measured and not drawn.** See below.

### Page width — measured, and back in A2's hands

It moved from A2 into 2/B on 2026-09-20 and measurement sent it back the same
day. Setting `.doc` to the source's width cost `invoice_0002`
`beside_agreement` **0.640 -> 0.295** — the hard tier — and bought
`height_ratio` 1.63 -> 1.60 on that one document and nothing on the other four.

**Isolated, not inferred:** that run's own IR was re-rendered four ways —
palette and width, palette only, width only, neither — with the model's answers
held fixed. 0.640 in both arms without the width, 0.295 in both arms with it.

The cause is the band model: at the wider column our `dl` rows re-wrap and drift
out of line with the source's panels, so pairs the source has side by side
(`Email` beside `Phone`, and six more) stop overlapping vertically.
`flex:1 1 12rem` was approximating the source's columns by accident and the true
width removes the accident. **`Document.page_px` stays measured and in the IR;
only the CSS rule is withheld.** `render._style_css` carries the note and what
would have to become true.

### The type scale — deferred, with the reason

Per-Zone pooled ink-band mode is a median **0.93** of the true CSS size, inside
0.75-1.13 on thirteen of fifteen. But `catalogue_0015` reads **2.40x** and no
confidence signal tried separates it from `form_0007`, whose 0.40 agreement
accompanies an accurate estimate. Shipping it would set 24px type on a document
whose real body is 10px, and `catalogue_0015` currently has the corpus's best
`height_ratio` at 1.03. Numbers and rejected signals are in `style.py`'s module
docstring.

---

## What the whole corpus looks like — 2026-09-21

Full write-up and the paired images: `debug/runs/92-sweep-chrome/_review/review.md`
and `debug/runs/93-sweep-fixed/_review/`. **Those directories are under `debug/`
and will be cleared** — the table below is the part that survives.

| # | fault | documents | owner |
|---|---|---|---|
| 1 | **Every Zone Title printed twice** — once as the Title, once as a Block repeating it | 13 of 15 | **A0**, documented |
| 2 | **Severe content loss** | 5, below | A0 / A-1 residue |
| 3 | **Type scale 2-3x too large** — main driver of height | ~all | 2/B, deferred |
| 4 | Columns collapse | 10 of 15 | A2, known |
| 5 | **No border is ever drawn** (`Zone.boxed` = 0 on all fifteen) | all | **2/B, next** |
| 6 | Figures are dotted placeholders | 3 | A3 |
| 7 | **Caveat spam** — `statement_0006` prints 41 near-identical lines | 1 | **A-1 residue, ours** |

Severe content loss, in order:

| document | what is missing |
|---|---|
| `receipt_0010` | every line item and total — ~75%. **Declared**: 18.5% of ink unread, 19 lines printed / 3 returned |
| `cv_0013` | the entire dark sidebar's content, and the name "Ines Halloran" |
| `catalogue_0015` | the page title, most prices and stock badges — ~43%. **Not declared** (quiet intra-line loss) |
| `form_0007` | section headings 2-5; five sections flattened into one pairs list |
| `darkdeck_0009` | the `STATUS` column and its Healthy/At risk pills |

**Best result:** `nonlatin_0014` — Greek complete, two columns, caption bars
correct, two single-letter slips. **Worst:** `cv_0013`.

---

## Next, in order — decided 2026-09-21

### 1. Harden the review workflow into a reusable skill — DONE 2026-09-21

Five of the six gaps closed. **`--previous <run>` is the one that mattered**:
each sheet now carries source, the previous run's render and this run's render,
and the form gains a `changed` axis taking `better` / `same` / `worse` — the
render-against-render comparison the ratchet is built on, which the workflow
could not make before.

Also: `findings.json` as the answered form and `--check` to tally it, naming
every `major` that sits beside scored ratios all at 1.000 (the
`sample_table_0003` failure, stated against the ceiling rather than a threshold
somebody chose); tall documents cut into capped, content-paired parts;
`--pair` for two arbitrary files; and twenty-six tests, none of which needs a
browser.

**The rubric stays open on purpose** — seven axes, two passes. `--check` reports
which axes never fired, and an undeclared axis is kept as a trial rather than
rejected, so the evidence accumulates without anyone having to edit the module.

Two of the fixes were found by *using* the tool rather than reasoning about it:
an ink-mass cut left `statement_0006` a 3316px part, and a summary with no
`scores.json` claimed the numbers had caught everything.

### 2. Finish 2/B: the border detector  <- next

`Zone.boxed` is `False` on all fifteen documents. The likely cause is named and
**unverified**: `DTH_SNAP_ZONES` snaps each box onto its **ink**, which sits
inside any border the source drew, so `_bordered`'s edge test never sees the
rule. Verify that before changing the test — dilating the crop by a few pixels
before measuring edges is the obvious first attempt.

It has to be **built**, not reused: the OpenCV rectangle finder three documents
claimed was in the tree is not there and never was. What survives as knowledge
rather than code — a finder was observed to locate `invoice_0002`'s four panels
and `sample_css_0004`'s two cards and nothing on the other three, with a guard
that a rectangle covering more than 0.80 of the page is the page — is a starting
point to **re-measure**, not a result to cite. Record the number taken in that
sitting.

Note `style.chrome` already finds fills correctly on `darkdeck_0009` (7),
`sample_css_0004` (2), `invoice_0002` (1), `cv_0013` (1) and
`sample_semantic_0005` (1), so borders are the missing half, not the whole job.

### 3. Then A0 — starting with the doubled Title

The single most pervasive visual fault in the corpus, 13 of 15 documents, and
already diagnosed: a Zone carrying a Title must not also carry a Block repeating
it. A0's other two faults are `wire._without_empty_rows` filtering on
`if row.cells` (truthy for `['', '', '', '', '']`) and `DTH_CAPTION_PASS`
withholding the caption band from the Kind question but **not** from the
Extractor's crop — which is what deletes `sample_table_0003`'s column headers.

**A0's pre-registered `T1 = 1.00` gate is disproved, not merely moved:**
`receipt_0010` is at 0.175 recall and `catalogue_0015` at 0.571, and none of
A0's three faults touch either. Set its replacement from A0's own starting
measurements when A0 begins.

### Also worth doing, unscheduled

`statement_0006`'s forty-one near-identical caveat lines should aggregate to
one. Ours, from A-1, cheap, and it dominates that document's render.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session counts.
  Two exceptions, both committed files: `tests/frozen/run84/` and
  `tests/frozen/a1-checkpoint/`.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the two dormant safety nets or the four shipped defaults.**
  `wire._without_empty_rows` has a real bug; it is A0's to fix, and the net stays.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.** Alessandro reviews
  that file and will not navigate per-fixture folders.
- **Any reviewed run is a full sweep**, all fifteen documents.
- **Rubric judgements are pairwise and in-session only** — never tabulated
  across sessions.

## Deferred deliberately — not new faults

- **Column collapse** waits for A2. Accepted interim state: content complete and
  reading order correct, in one column. Do not trade T1 for column shape.
- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size.
- **`Zone.align`** stays in A2, even though ADR 0005's table lists alignment
  under B.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — default for anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a1-checkpoint/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check   # after answering findings.json
```

A renderer-only change needs no new run: copy a sweep's directory, re-measure
the pixel-derived fields, re-render from the embedded IRs, and review that.
