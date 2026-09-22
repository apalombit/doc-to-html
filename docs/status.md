# Status — 2026-09-22 (Thread 2/B closed bar the type scale; A0 is next)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**
(`.claude/skills/visual-review/SKILL.md`).

Branch `scaffold`, head `09f56d3`. **699 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
  |- palette + page width                       DONE 2026-09-20
  |- per-Zone chrome (fills, title bars)        DONE 2026-09-21
  |- review workflow -> reusable skill          DONE 2026-09-21
  |- borders + the title-bar ordering bug       DONE 2026-09-21
  |- clipping, width reservation, ink contrast  DONE 2026-09-22
  \- type scale                                 deferred, reasons in style.py
Phase A0    Stop the bleeding                   NEXT   <- you are here
Phase A1/A2/A3, Thread 3/C, Thread 4/D          unchanged
```

**A0's starting notch is `tests/frozen/a0-checkpoint/scores.json`**, committed
2026-09-22. Ratchet against it by path. `tests/frozen/a1-checkpoint/` stays as
Phase A-1's notch and the record of where the ratchet began.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
```

---

## What the corpus looks like as A0 begins

Reviewed document by document on 2026-09-22 against the sources, all fifteen.
Findings in `debug/runs/96-borders-guarded/_review/` — **that directory is
under `debug/` and will be cleared**; the tables below are what survives.

| | mean over fifteen |
|---|---|
| `recall` | 0.851 |
| `precision` | 0.934 |
| `join_recall` | 0.809 |
| `tau` | 0.936 |

| # | fault | documents | owner |
|---|---|---|---|
| 1 | **Every Zone Title printed twice** | 12 of 15 | **A0, next** |
| 2 | **Severe content loss** — `receipt_0010`, `catalogue_0015`, `form_0007`, `darkdeck_0009` | 4 | A0 / A-1 residue |
| 3 | Type scale 2–3x too large | ~all | 2/B, deferred |
| 4 | Columns collapse | 6 of 15 | A2, known |
| 5 | ~~No border is ever drawn~~ | — | **fixed 2026-09-21** |
| 6 | Figures are dotted placeholders | 3 | A3 |
| 7 | **Caveat spam** — `statement_0006` prints 41 near-identical lines | 1 | **A-1 residue, ours, OPEN** |
| 8 | `cv_0013` sidebar values clipped (`PAIRS_REM` declined) | 1 | A2 |
| 9 | `nonlatin_0014`'s dark-blue table header row renders unshaded | 1 | 2/B follow-up, unscheduled |

Severe content loss, in order:

| document | what is missing |
|---|---|
| `receipt_0010` | every line item and total — ~75%, recall **0.175**. **Declared** |
| `catalogue_0015` | the page title, most prices and stock badges — recall **0.571**. Not declared |
| `form_0007` | section headings 2–5; five sections flattened into one pairs list. recall 0.729 |
| `darkdeck_0009` | the `STATUS` column and its Healthy/At risk pills |

**`cv_0013` is no longer on that list.** Its sidebar was reported as lost and
was in fact rendered invisible — dark ink on a dark fill. Fixed 2026-09-22;
only "Ines Halloran" and "STRUCTURAL ENGINEER" are genuinely absent.

**Best result:** `nonlatin_0014` — Greek complete, both columns, panels and
caption bars correct. **Worst:** `receipt_0010`.

---

## What Thread 2/B shipped

All CV, **zero model calls**, behind `DTH_STYLE_RECORD` (default on). The
measurements and the rejected alternatives live in the docstrings; this is the
index.

| what | where the evidence is |
|---|---|
| Palette — ground, ink, accent, shade | `style.py` module docstring, `measure()` |
| Colour off `Rectified.plain`, ink mask off the equalised image | `Rectified.plain` |
| Per-Zone fill and title bar | `style.chrome`, `SAME_COLOUR` |
| **Borders** — `style.rectangles`, `box_around`, `boxes_for` | `rectangles()`, `PAGE_SHARE`, `MIN_RECT_SHARE` |
| **One rectangle, one Zone** | `boxes_for()` |
| **Chrome measured after `_classify`** | `orchestrator._measure_chrome` |
| **Clipping reported** | `scoring.Layout.clipped` |
| **Width reservation** `COLUMN_REM` = 6 | `render.COLUMN_REM`, a narrow window |
| **`PAIRS_REM` = 0**, measured and declined | `render.PAIRS_REM` |
| **Ink against the Zone's own fill** | `render._readable_on`, `MIN_ON_FILL` |
| Page width measured, **not drawn** | `render._style_css` |
| Accent declared, **not spent** | `render._style_css` |
| Type scale measured, **not shipped** | `style.py` module docstring |

Two findings from this thread are the kind a later session would otherwise
rediscover the hard way:

- **`Zone.title_fill` had shipped and never once fired.** `_measure_chrome`
  ran before `_classify`, which is where the caption pass sets `Zone.title`,
  so `title_rows` was 0 on every Zone of every document — 0 of 119. A stage's
  *position* is as much a way for a feature not to arrive as an unread flag.
- **`project()` had always measured `clipped` and nothing read it.** It fires
  on exactly the renders whose content is cut off at the right edge and on
  none of the fifteen sources.

---

## Next, in order

### 1. Phase A0 — stop the bleeding  <- next

The prompt is in
[`specs/0007-handover.md`](specs/0007-handover.md) under **Phase A0**. Three
named faults, one of them the corpus's most pervasive.

**A0's `T1 = 1.00` gate is disproved, not merely moved:** `receipt_0010` sits
at 0.175 recall and `catalogue_0015` at 0.571, and none of A0's three faults
touches either. Set the replacement from `tests/frozen/a0-checkpoint/`.

### 2. Open, unscheduled, and cheap

- **`statement_0006`'s 41 near-identical caveat lines** should aggregate to
  one. Ours, from A-1, no model time, and it fills three of that document's
  five review sheets.
- **`receipt_0010`, the corpus's worst document, has one untested lead.**
  `preprocess.resize_long_edge` never enlarges — its docstring argues
  enlarging "adds no detail" — and `receipt_0010` rectifies to **335x547**, by
  far the smallest page, so the extractor sees ~300px across 19 lines of
  monospace. True of information, possibly false of legibility. It is a
  *decision* change rather than a perception instruction, which is the kind
  the model complies with. One document, ~6 minutes to probe.
- **`nonlatin_0014`'s table header row.** Do not build a third detector;
  point `chrome()`'s existing title-band measurement at the row `RowRole.header`
  already names. After A0.

### 3. Then A1 / A2 / A3, Thread 3/C, Thread 4/D — unchanged

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session
  counts. Three exceptions, all committed files: `tests/frozen/run84/`,
  `tests/frozen/a1-checkpoint/` and `tests/frozen/a0-checkpoint/`.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the two dormant safety nets or the four shipped defaults.**
  `wire._without_empty_rows` has a real bug; it is A0's to fix, and the net
  stays.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.**
- **Any reviewed run is a full sweep**, all fifteen documents.
- **Rubric judgements are pairwise and in-session only.**

## Deferred deliberately — not new faults

- **Column collapse** waits for A2. Content complete and reading order correct,
  in one column, is the accepted interim state.
- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size.
- **`Zone.align`** stays in A2.
- **Figures as placeholders** stay in A3.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

**A renderer-only or pixel-only change needs no new run.**
`tools/remeasure_style.py <sweep> --label <new>` re-measures the Style Record
and re-renders from a sweep's own embedded IRs with zero model calls. It cannot
move anything the model decided — a prompt, an extractor or the layout still
costs a sweep — and it says so.
