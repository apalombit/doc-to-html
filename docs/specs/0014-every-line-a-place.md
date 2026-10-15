# Every printed line has a place — read what nobody read, read copies alike, then one sweep

**Status: done 2026-10-15 — steps 1 and 2 shipped, step 3 built and
dropped, `S10-sweep` taken; whether it becomes the baseline is
Alessandro's decision. Issue #37.** Three steps, each traced to its cause
at the baseline with its prediction written down, then one full sweep,
`S10-sweep`, over all twenty-one documents. The handover prompt marked
*current* at the end is the one to start a session with.

Alessandro's decisions, 2026-10-14:

1. **`S9-sweep` is the baseline**, frozen as `tests/frozen/s9-result/`.
2. **General repairs, not per-page ones.** He asked for "general and
   principled solutions that happen to improve" the pages, and then whether
   the proposals were overfit. Of the faults at `s9-result/`, only two
   classes recur across pages. This spec takes the larger one, **a printed
   line the Zone's reading has no place for**, and the one existing step
   that feeds it, **copies read one at a time**.
3. **Simple implementation, every step, then one sweep.** No sweep in
   between.
4. **Not in this spec:** the second class, type read as a figure. It waits
   on his call (§6).

---

## How to work

- **By eye.** Every step ends with sheets for the pages it moved, against
  the step before. Judge each page better / same / worse in one sentence
  that names the element. That judgement is the gate.

  ```
  tools/visual_review.py <run> --previous <previous step's run>
  ```
- **Scores are recorded, never gating, never argued from.** The one number
  read is the report's `vanished` list, as a pointer to a page to open.
  This spec also reads the report's **unclaimed lines**: they are what
  step 2 acts on.
- **The six held-out pages** (`corpus.NEW`: letter, pricing, paper,
  timetable, ticket, certificate) are reported in their own lines.
- **Each step is its own commit.** Every new step that writes the IR goes
  into `tools/rederive.py`.
- **Report each step** with what the pages look like and the `report.html`
  path. Continue unless a page got worse; if one did, stop, show it, and
  ask.
- **Each step names its prediction before it is measured.**
- **Say which bytes.** Step 1 adds a field to `Zone`, so every embedded IR
  gains `"extra": []` on every Zone. From then on, "byte-identical" means
  identical except that key. This is the trap A3 hit; see CLAUDE.md, "A
  clause about bytes".

**The loops**, proved on `s9-result/` at `a3969f3` (code as `a84404c`); see
its README:

| loop | command | what it can measure |
|---|---|---|
| rederive | `tools/rederive.py tests/frozen/s9-result --label <L>` | every step downstream of the model |
| replay | `tools/replay_run.py tests/frozen/s9-result --label <L>` | the wire, the mapper and every pass. It marks a moved call **ASKED DIFFERENTLY**, and a new call **ASKED MORE THAN THE RUN**. Neither is a measurement. |
| a targeted run | `FIXTURE=<a>,<b> tools/iterate.sh <L>` | the model's answers on the pages a step moved. **A check that the step works, not the review**; the review is the sweep. |

Score a run against the baseline:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s9-result/scores.json
```

---

## 1. The fault — a line the Zone's reading has no place for

**Mechanism.** Classify gives each Zone one Kind, and the Extractor fills
that Kind's schema. A pairs Zone, for example, asks for label → value
only. A line of another shape inside the Zone is either **dropped** or
**forced** into the shape. Real Zones mix shapes: a form section holds tick
boxes and an instruction, a table has a legend, a card has a code, a name
and a price. So the fault grows with the corpus.

**Measured at `s9-result/`, 2026-10-14.** Each source line was compared with
the output, then traced through the IR and the model's answers:

| page | line | Zone | what happened |
|---|---|---|---|
| `form_0007` | `Tick one category. Locker allocation is subject to availability.` | pairs z3 (tick boxes) | dropped |
| `ticket_0020` | `OSLO GARDERMOEN`, `OSL` | pairs z3 | dropped |
| `ticket_0020` | `Gate closes 20 minutes before departure` | pairs z0 (the stub) | dropped |
| `timetable_0019` | the legend `Mathematics Science English Art PE` | table z2 | dropped: it is not a table row |
| `sample_semantic_0005` | `Tags:` | list z7 | dropped: a list has no place for a lead-in |
| `catalogue_0015` | `CP-402` | pairs z8 | dropped. The other 8 cards kept their code as a label with no value. |
| `darkdeck_0009` | `P95 LATENCY` / `184 ms` / `−31 ms` | pairs z3 | forced: `P95` → `LATENCY`, `184` → `ms` |
| `catalogue_0015` | every card | 9 pairs Zones | forced: 31 of 43 pairs have one side empty; the cards are drawn at least three ways |

**Two causes feed it, and each has a step:**

- **Step 2: the line is never read.** `locate.unclaimed` (spec 0012 G9)
  already finds these lines, and only reports them. At `s9-result/` it
  flags 3 lines and all 3 are real: the form's note, `OSLO GARDERMOEN`, and
  the timetable's legend.
- **Step 3: copies are forced into one Kind.** `structure.alike` (spec 0008
  step 3) gives a drawn grid's copies the majority Kind. On the catalogue
  that majority is the forcing Kind. On darkdeck it is a tie, which
  changes nothing.

Step 1 is what step 2 needs first: a Zone must be able to hold a line of
another shape, and the render must draw it.

---

## 2. Step 1 — a Zone can hold lines its Kind has no place for (offline)

**The change.**

- **`ir.Zone.extra: list[Block]`.** These are lines the Zone prints that
  its Kind's reading has no place for, each read on its own crop (step 2).
  The default is empty. Read it in `Document.from_json` as the other lists
  are.
- **`locate.cells_of` yields a Zone's `extra` lines last**, each as
  `(cell, None)`. Everything that walks a Zone's Cells then sees them:
  - locate places them;
  - `unclaimed` counts them as claims;
  - `looks.read` measures their size and colour.
- **`render._zone_body` draws each `extra` Block** with the prose Block
  renderer, inside the Zone's own container:
  - **before** the body, when the Block's first placed line lies above
    the body's first placed Cell;
  - **after** it otherwise, which includes when nothing is placed.

  Do not interleave the extra lines between pairs or rows. That stays out
  of scope (§6).

**Tests.**
- A pairs Zone with one `extra` Block placed below its pairs renders the
  Block's text after them.
- A table Zone with an `extra` Block placed above its first row renders
  the Block first.
- `cells_of` yields the `extra` lines last.
- `Document.from_json(doc.to_json())` keeps `extra`.

**Prediction.** `tools/rederive.py tests/frozen/s9-result --label S10-1`:
21 of 21 pages byte-identical to `S10-0-base`, except that each embedded IR
gains `"extra": []` on every Zone. No sheet moves.

**Done when** that holds, and the suite and mypy are clean.

### Outcome — step 1, 2026-10-14

**Step 0 proved the baseline** at `a8a64d4`: the replay `S10-0-replay` 21
of 21 byte-identical, 0 asked differently; the rederive `S10-0-base` 21 of
21 files byte-identical to `s9-result/documents/`; 1142 passed, 1 skipped;
mypy clean.

**The prediction held.** `S10-1` is 21 of 21 byte-identical to
`S10-0-base` once `"extra":[],` is taken out of the embedded IR, and the
key stands on all 217 Zones. Scored against `s9-result/scores.json`, 0
fields differ but the label and the time. No sheet moves, so none was
opened. `debug/runs/S10-1/report.html`.

What else moved with the field, each so the body is counted as before:
`_from_pairs` pairs the label and value Cells only, `_from_grid` and
`_from_ink` count the body's Cells only, and a list Continuation with
an `extra` line is drawn member by member through `_zone_body`. 1150
passed, 1 skipped; mypy clean.

---

## 3. Step 2 — read what nobody read (a new pass, the model)

**The change: `orchestrator._read_unclaimed`, called right after
`_locate` in the round.**

1. For each line in `document.unclaimed`:
   - build a transient `Zone(kind=Kind.PROSE, bbox=<the line's box>)`;
   - ask `for_kind(Kind.PROSE).extract(rectified.image, transient,
     self.engines.extract, document.hint)`.

   This is the existing prose prompt and schema, on the line's own crop.
   The crop is cut the way every Zone's is.
2. **Keep** each returned Block in `document.zones[line.zone_index].extra`,
   **unless the Zone already prints its text**. Fold the text, then check
   whether it is held in the Zone's Title or any of its Cells. This guard
   means a re-read can never print a word twice.
3. If anything was kept, **run `_locate` once more**. The new lines are
   then placed, and the unclaimed list is recomputed; those lines are now
   claimed.
4. **Trace every call.** Use `Stage.EXTRACT`, step `"unclaimed"`, and record:
   - the disposition: ACCEPTED, or REJECTED with its reason;
   - `zone_index`;
   - the line's box;
   - the text kept.
5. **When `_extract` extracts a Zone, clear its `extra`.** A later round
   then re-reads cleanly.

**No runs pass on these lines**: keep the pass to one call per line. Also
rewrite `_locate`'s docstring. Tesseract is still never a reader: it now
says where to look, and the model reads what is there.

**Why it is a separate pass.** No Extractor prompt or schema changes, so at
`temperature: 0` every existing answer is the one the baseline has. This is
CLAUDE.md's lesson "where you ask is a bigger lever than how you ask". The
inline-runs ask cost `invoice_0002` 4 of its 5 pairs when it sat inside the
Extractor prompts, and nothing once it was moved to its own pass.

**Why not widen the detector.** Measured 2026-10-14, offline over all 21:

| setting | lines flagged | real |
|---|---|---|
| as shipped (lines of 2+ words) | 3 | 3 |
| one-word lines count | 16 | 6 |
| also read the inverted polarity on every Zone | 31 | 7 |

Widening it is Phase A-1's trap: false alarms on clean pages (`bae`, `th`,
`puppincs`). Take the detector as it is. It cannot reach:
- `OSL`, 46px type that tesseract cannot see;
- the stub's lines: its white caps on teal, and the gate note, whose
  `Gate` a `GATE` Cell claims;
- `Tags:` and `CP-402`, which are one word each.

**Prediction.**
- The replay of `s9-result/` marks exactly three documents **ASKED MORE
  THAN THE RUN**, each by one prose call:
  - form z3, for `Tick one category. Locker allocation is subject to
    availability.`;
  - ticket z3, for `OSLO GARDERMOEN`;
  - timetable z2, for the legend.
- Nothing else is marked.

**Checked by a targeted run.** Run `FIXTURE=form_0007,ticket_0020,timetable_0019
tools/iterate.sh S10-2-check`, then sheets against `S10-1` for those three.
- **form:** prints its note under the tick boxes.
- **ticket:** prints `OSLO GARDERMOEN`.
- **timetable:** prints its legend under the grid.
- Nothing else on the three pages moved.
- The report's unclaimed list is empty for these three.

The sweep is the review.

### Outcome — step 2, 2026-10-14

**The prediction held.** The replay `S10-2-replay` marks exactly form,
ticket and timetable **ASKED MORE THAN THE RUN**, `1 prose` each, and 0
calls asked differently; all 21 pages are byte-identical to `S10-1`, since
a replayed re-read runs dry and keeps nothing.

**The replay had to learn to say so.** It marked ASKED MORE only off a
Conversion's Failures, and a pass that swallows its own error, as this one
and the inline runs do, leaves none. `tools/replay_run.asked_more` now
counts each pass's calls against the run's and names the pass.

**The targeted run `S10-2-check`** (on the step's code before the change
below; its diff beside it): every call `s9-result/` asked came back byte
for byte, 25 + 17 + 10, and one new prose call each. Form read `Tick one
category. Locker allocation is subject to availability.`, ticket `OSLO
GARDERMOEN`, both kept. The timetable read its legend as five `item`
Blocks, `Mathematics` … `PE`, and **the guard refused all five**: judged
one Block at a time, each is a word its grid prints too, though the page
prints them again, as a line.

**Changed from §3, two places:**
- **The guard judges the line, not the Block** — the call's Blocks read
  together, the unit the detector flagged and the question asked about.
- **`_extra` draws consecutive items as `_list` does**: on one line with
  the page's gap where the page prints them side by side
  (`_side_by_side`), else as a list. Five `<p>`s would have stacked it.

Measured by replaying `S10-2-check`'s own answers through that code,
`S10-2`: form and ticket byte-identical to the check run, the timetable
keeps its legend; the unclaimed list is empty on all three.

**By eye, `S10-2` against `S10-1`** (`debug/runs/S10-2/_review/`) — each
page's HTML outside the IR differs by one insertion and nothing else:
- **form — better:** the note sits under the tick boxes, small and grey,
  as the page prints it.
- **ticket — better:** `OSLO GARDERMOEN` is printed. It stands at the
  foot of its Zone, after `GROUP 2`, not under `OSL`: placed at 0.495,
  below the Zone's first placed Cell, and between pairs is §6's.
- **timetable — better:** the legend is one grey line under the grid.
  `Science` is drawn bold, where the page sets all five regular; the
  swatches are not drawn.

`vanished` against `s9-result/`: form 7 → 1 (`fernpost`, a misread §6
names), ticket 10 → 8 (`oslo`, `gardermoen` back), timetable 1 → 1
(`lunch`). `debug/runs/S10-2/report.html`. 1166 passed, 1 skipped;
mypy clean.

---

## 4. Step 3 — copies take the Kind that keeps the most of a line

**Cause, measured.** `structure.alike` gives a drawn grid's copies the
majority Kind, and changes nothing on a tie. Grid regions at `s9-result/`:

| page | copies classified | majority today | result |
|---|---|---|---|
| `catalogue_0015` | 5 pairs, 3 table, 1 prose | pairs, all 9 | `CP-402` dropped; 31 of 43 pairs one-sided; cards drawn ≥3 ways |
| `darkdeck_0009` | 2 prose, 2 pairs | tie: unchanged | two tiles drawn as prose, two as pairs; `P95` → `LATENCY` |
| `nonlatin_0014` | 2 pairs | pairs | fine |
| `pricing_0017` | 17 prose | prose | fine |

Majority picks what most copies were read as. A forcing Kind (pairs,
table) loses whatever its shape cannot hold.

**The change.** In `structure.alike`, the copies take the Kind, **among
those the copies were given**, that comes first in `KEEPS`:

```python
KEEPS = (Kind.PROSE, Kind.LIST, Kind.PAIRS, Kind.TABLE, Kind.FIGURE)
```

The docstring states the order:
- prose keeps every line as printed;
- a list keeps lines as items, with no lead-in;
- pairs keep only what fits label → value;
- a table keeps only what fits its grid;
- a figure keeps nothing as text, so it is chosen only when every copy
  is one.

This is "put the repair on the side where being wrong is free", applied to
Kinds: a lost line is a recall fault, a lost structure only a precision one.
No constant, and ties need no rule of their own. Spec 0008 chose the
majority to fix three catalogue tables that lost most of their words;
prose fixes that too.

**Prediction.**
- `catalogue_0015`: all 9 cards prose. Card z7 was classified prose.
- `darkdeck_0009`: all 4 tiles prose.
- `nonlatin_0014` and `pricing_0017` unchanged.
- The replay of `s9-result/` marks **catalogue and darkdeck ASKED
  DIFFERENTLY**:
  - the 9 card extractions, pairs to prose;
  - darkdeck z3 and z5;
  - the runs calls that follow them.

  Nothing else is marked.

**The risk, named.** A card's price row (`£4.20   each   In stock`, spread
across the card) may come back as one prose line and lose its spread. If a
card is worse by eye than at `S10-1`, stop and show it.

**Checked by a targeted run.** Run `FIXTURE=catalogue_0015,darkdeck_0009
tools/iterate.sh S10-3-check`, then sheets against `S10-1`.
- **catalogue:** the nine cards are drawn alike, and every card prints its
  code.
- **darkdeck:** the four tiles are drawn alike, and `P95 LATENCY` is one
  line.

### Outcome — step 3, 2026-10-14: built, measured, dropped

**Alessandro's decision, 2026-10-14: drop step 3 and sweep steps 1-2.**
Its diff is kept beside the check run, `debug/runs/S10-3-check/
uncommitted.diff`; nothing of it was committed.

**The catalogue got worse.** `S10-3-check` against `S10-1`
(`debug/runs/S10-3-check/_review/00-catalogue_0015.png`): all nine cards
read as prose, and prose drops the white-on-dark code badges that pairs
read — `BR-114`, `IR-207`, `IR-212`, `CP-418` and `SC-501` gone, `CP-402`
still missing; the price rows come back as stacked lines or bulleted
items, their spread across the card lost; `OK-330` lost `NEW`. `vanished`
on the page 1 → 9 tokens. Every call asked as `s9-result/` asked it was
answered alike, 29 of 29: the loss is the 18 new prose calls' own.
**`KEEPS`' premise, that prose keeps every printed line, is refuted on
the one page it moved.**

**Darkdeck: §4's premise was wrong.** `structure.alike` runs after
classify, and classify answered `pairs` for all four tiles. Two became
prose only later, by `_reread_as_prose` after extraction; the "2 prose,
2 pairs" of §4's table was read off the final IR. So step 3 never reaches
darkdeck: 61 of 61 calls alike, the page byte-identical.

---

## 5. Work plan

| step | what | runs on | done when |
|---|---|---|---|
| 0 | prove the baseline — DONE | replay, rederive, suite | replay `S10-0-replay` 21 of 21 byte-identical, 0 marked; rederive `S10-0-base` 21 of 21; 1142 passed, 1 skipped; mypy clean |
| 1 | `Zone.extra`: IR, `cells_of`, render — DONE | rederive | 21 of 21 identical but `"extra": []` |
| 2 | read what nobody read — DONE | replay, a targeted run | §3's three calls marked, no other; the three lines printed |
| 3 | copies take the Kind that keeps most | replay, a targeted run | **DROPPED** 2026-10-14: the catalogue worse, darkdeck out of its reach — see its outcome |
| P | register §7's prediction in this spec — DONE | replay at the last commit | the marked calls written down before the sweep |
| S | **`S10-sweep`**: all 21, shipped defaults, started detached — DONE 2026-10-15 | the model | §7 checked; all 21 sheets opened against `S10-0-replay`; the outcome written |

---

## 6. Not in this spec — record

- **Type read as a figure** (`cv_0013`'s `Revit` and `Python`,
  `ticket_0020`'s `NORDLYS AIR`). Since A3 these are drawn from their own
  pixels, so the reader sees them; they are pictures, not text. The
  pixels separate type from art: chart, barcode and seal have no type
  line, while cv's measure exactly like their prose siblings. But
  SPARKSUITE and ACME are `<img>` wordmarks, and they measure as type too.
  The fix waits on **Alessandro's decision: is a wordmark text?** The
  invariant "what is read off a Graphic is alt, never printed" holds
  until then.
- **Copies beyond drawn grids.** cv's skill list is four copies, two of them
  read as figures. Its Zones measure 0.019–0.043 of the page tall, and no
  simple detector groups them.
- **Placing extra lines between pairs or rows.** Step 1 draws them before
  or after the body only.
- **An "other lines" field in every extraction schema.** One extra field
  cost `invoice_0002` 4 of 5 pairs, and it would move every extraction
  call.
- **Misreads where the schema had the slot.** These are statement's
  `Quillton`, `210.08` and `1,141.30`; `fempost` twice; `Castletown`; the
  Greek footer; the receipt's AID; the timetable's hatched `Lunch`. At
  `temperature: 0` a re-ask returns the same answer.

---

## 7. The sweep's prediction — registered at step P, 2026-10-14

**From the replay at `b493477`'s code, `S10-P-replay`** (steps 1 and 2;
step 3 dropped): exactly form, ticket and timetable marked **ASKED MORE
THAN THE RUN**, `1 prose` each; 0 calls asked differently; all 21 pages
byte-identical to `S10-1`.

- **Every call `s9-result/` asked is asked alike and answered byte for
  byte as `s9-result/answers/` holds it** — all 732.
- **The calls beyond it are only the three re-reads**, one prose call
  each on form, ticket and timetable: 735 calls in all. Nothing is
  asked differently.
- **The eighteen unmarked documents render byte-identical to
  `S10-P-replay`**, embedded IR included — catalogue and darkdeck among
  them.
- **The three re-reads answer as `S10-2-check`'s did** — same prompt,
  picture and schema at `temperature: 0` — so **form, ticket and
  timetable render byte-identical to `S10-2`**: the form's note under its
  tick boxes, `OSLO GARDERMOEN` at the foot of the ticket's Zone 3, the
  timetable's legend on one line under its grid.
- **No further re-read**: with no Kind moved, no new unclaimed line.

So all 21 pages are predicted to the byte.

Then report the sweep in the error-analysis format:
1. the five pages first (form, ticket, timetable, catalogue, darkdeck),
   each against its line in §1 — catalogue and darkdeck as left by step
   3's drop;
2. the six held-out pages in their own lines;
3. where it gained;
4. the faults left, by stage;
5. the directions, ranked;
6. a recommendation.

Whether `S10-sweep` becomes the baseline is Alessandro's decision.

### Outcome — the sweep, `S10-sweep`, 2026-10-15

Commit `a53f11b`, 07:35–09:56 (**2h21m**), shipped defaults, **735
calls**, the model 40%/60% CPU/GPU. All twenty-one converted.

**The prediction held to the byte, every clause:**
- all 732 calls `s9-result/` asked were asked alike and answered byte for
  byte the same;
- the only calls beyond them are the three re-reads, one prose call each
  on form, ticket and timetable;
- the eighteen unmarked documents render byte-identical to
  `S10-P-replay`; form, ticket and timetable byte-identical to `S10-2`;
- no further re-read: the unclaimed list is empty on all 21.

`tools/replay_run.py debug/runs/S10-sweep` reproduces 21 of 21
byte-identical, 0 asked differently; `tools/rederive.py` over it 21 of 21
byte-identical files.

**By eye, all 21 sheets against `S10-0-replay`
(`debug/runs/S10-sweep/_review/`): three pages better, eighteen the
same, none worse.** The eighteen differ from `S10-0-replay` by the empty
`"extra"` key alone.

**1. The five pages, against their lines in §1**

| page | §1's line | now |
|---|---|---|
| form | the note under the tick boxes, dropped | **better** — `Tick one category. Locker allocation is subject to availability.` under the tick boxes, small and grey, as printed |
| ticket | `OSLO GARDERMOEN`, `OSL` and the gate note, dropped | **better, in part** — `OSLO GARDERMOEN` printed, at the foot of Zone 3 after `GROUP 2` rather than under the passenger's name; `OSL` and the gate note still gone, as §3 said the detector cannot reach them |
| timetable | the legend, dropped | **better** — `Mathematics Science English Art PE` on one grey line under the grid. `Science` drawn bold, the page sets all five regular; the swatches are not drawn |
| catalogue | `CP-402` dropped; the cards forced into pairs | **same** — step 3 dropped; `CP-402` still missing, the cards drawn three ways |
| darkdeck | `P95` → `LATENCY`, `184` → `ms` | **same** — step 3 never reached it: its tiles are four `pairs` when copies are read alike |

**2. The six held-out pages** — recorded, not argued from:

| page | by eye | vocabulary recall | tau | beside |
|---|---|---|---|---|
| certificate | same | 1.000 → 1.000 | 1.000 → 1.000 | 0.000 → 0.000 |
| letter | same | 0.995 → 0.995 | 1.000 → 1.000 | 1.000 → 1.000 |
| paper | same | 0.985 → 0.985 | 1.000 → 1.000 | 0.547 → 0.547 |
| pricing | same | 1.000 → 1.000 | 0.880 → 0.880 | 0.629 → 0.629 |
| ticket | better, in part | 0.750 → 0.800 | 0.282 → 0.238 | 0.000 → 0.000 |
| timetable | better | 0.982 → 0.982 | 0.957 → 0.963 | 0.991 → 0.992 |

The ticket's tau is the one ratchet leg that fell: `OSLO GARDERMOEN`
drawn at its Zone's foot is out of the page's order. Reported, not a
gate.

`vanished` 41 → 33: back — the form's `tick`, `one`, `allocation`,
`is`, `subject`, `availability`; the ticket's `oslo`, `gardermoen`.
Nothing gone. Means against `s9-result/` (all 21 / the fifteen / the
six): vocabulary recall 0.977 → 0.982 / 0.988 → 0.991 / 0.952 → 0.960;
join recall 0.945 → 0.951 / 0.960 → 0.965 / 0.905 → 0.914; tau 0.951 →
0.949 / 0.990 → 0.990 / 0.853 → 0.847; precision and beside unmoved.

**3. Where it gained**

| page | gain |
|---|---|
| form | **its note** — six words out of `vanished`, 7 → 1 |
| ticket | **the route** — `OSLO GARDERMOEN` printed, 10 → 8 |
| timetable | **its legend** — on one line, under the grid |

**4. The faults left, by stage** — this spec's class first

| page | what the page shows | stage | evidence |
|---|---|---|---|
| ticket | `OSLO GARDERMOEN` at the foot of its Zone, not under the name | Render | `_extra` draws before or after the body only (§6); placed at 0.495, the Zone's first Cell at 0.230 |
| ticket | `OSL` gone | Locate | 46 px type tesseract does not read, so no line is flagged |
| ticket | the gate note gone | Locate | its `Gate` lies in a `GATE` Cell's box, so the line counts as claimed |
| ticket | both `NORDLYS AIR` drawn as pictures | Classify | type read as a figure — §6, his call |
| catalogue | `CP-402` gone; 31 of 43 pairs one-sided | Classify → Extract | pairs answers; step 3's prose lost five badges and the price spread (step 3's outcome) |
| darkdeck | `P95` → `LATENCY`; tiles drawn two ways | Extract | four `pairs` answers; two overturned to prose by `_reread_as_prose` after extraction |
| sample_semantic | `Tags:` and the commas gone | Extract | one word, under `UNCLAIMED_WORDS`; a list has no lead-in |
| timetable | `Science` in the legend drawn bold | Style | `Look.bold` set on that Cell alone; cause not traced |
| certificate | signatures stacked, the seal a text chip | Structure → Render | unmoved since `s9-result/` |

**5. Directions, ranked by gain for cost**

| # | stage | change | why | cost |
|---|---|---|---|---|
| 1 | Render | an `extra` line placed between a Zone's pairs or rows is drawn there | the ticket's route under its name; tau back | rederive offline — no model |
| 2 | Extract | when `_reread_as_prose` overturns one copy of a drawn grid, its copies are read as prose too | darkdeck's four tiles alike, `P95 LATENCY` one line — the two tiles prose already reads well | a model question per copy; a sweep |
| 3 | Style | find why one legend word measures bold | the timetable's legend | offline, on `S10-sweep`'s IR |
| 4 | Locate | a line partly inside one Cell's box is not claimed by that Cell's word alone | the ticket's gate note | layout front offline; the re-read at a sweep |

Not worth more effort: **copies taking the Kind that keeps most** — built
and measured (step 3's outcome); prose drops the catalogue's badges and
cannot reach darkdeck. The catalogue's cards need a Kind that keeps both
a white-on-dark badge and a spread price row, and none of the five
does.

**6. Recommendation.** Three pages better, eighteen the same, none worse
by eye, and the prediction held to the byte: the re-read is a general
pass that asked three calls and moved no other answer. **Whether
`S10-sweep` becomes the baseline is Alessandro's decision**; if taken,
the ticket's tau is its one leg named, and direction 1 is its repair.

---

## 8. Where things are

| what | where |
|---|---|
| the unclaimed lines | `locate.unclaimed`, `CONFIDENT`, `UNCLAIMED_WORDS`, `_claims`, `_covered`; `document.unclaimed` (`ir.Unclaimed`); recorded in `orchestrator._locate`; listed by `report.py` |
| a Zone's Cells | `locate.cells_of` |
| the pass order | `orchestrator` round loop: `_extract` … `_locate`, `_read_fields`, `_place_furniture`, `_read_rhythm`, `_read_looks` |
| a prose read of a Zone | `for_kind(Kind.PROSE).extract`; `_reread_as_prose` is the model to copy for tracing |
| a Zone's body in the render | `render._zone_body` → `_table`, `_pairs`, `_prose`, `_list`, `_figure` |
| copies read alike | `structure.alike`; `orchestrator._read_copies_alike`, after `_classify` |
| the loops | `tools/rederive.py`, `tools/replay_run.py`, `tools/visual_review.py` |

**A Zone printer is worth writing first**, in a scratch script. Load each
document's IR from `<script id="doc-ir">` with `ir.Document.from_json`, and
print each Zone's index, kind, box and title, then every Cell from
`cells_of`. Every cause in §1 was found with one.

---

## 9. Rules that bind

- "How to work" above, and CLAUDE.md's.
- **Never cite a past run.** The committed frozen directories are the
  exception, for what their READMEs say.
- **Any reviewed run covers all twenty-one documents.** The targeted runs
  of steps 2 and 3 are checks, not reviews.
- **Never edit `tools/iterate.sh`, or any script a running sweep reads.**
- **Marking may never change the words.** Keep the four shipped defaults
  and the six wire row nets. Step 2 adds only lines the page prints and
  the Zone does not.
- **What is read off a Graphic is `alt`, never printed.**
- Leave `debug/runs/84-rule-not-a-line/` intact. Never score against
  `tests/documents/SAMPLE_DOCUMENTS`.

---

## Handover prompt — after `S10-sweep`: Alessandro's decision, then the freeze (current)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0014-every-line-a-place.md's "Outcome — the sweep" and step
3's outcome. Spec 0014's work plan is done; nothing is open except
Alessandro's decision on S10-sweep. Do not pick anything up unless he
names it — the four directions in the outcome are record, not a queue.

State, re-measured 2026-10-15 at a53f11b (code as b493477):
- the suite: 1166 passed, 1 skipped; mypy src clean;
- debug/runs/S10-sweep/: 21 documents, 735 calls, 2h21m;
  tools/replay_run.py debug/runs/S10-sweep reproduces 21 of 21
  byte-identical, 0 asked differently; tools/rederive.py over it gives
  21 of 21 byte-identical files;
- by eye against S10-0-replay: 3 pages better (form, ticket, timetable),
  18 same, none worse; the ticket's tau the one ratchet leg that fell.

If debug/runs/S10-sweep/ is gone, say so and stop: it cannot be remade
without a sweep.

If Alessandro takes S10-sweep as the baseline: freeze it as
tests/frozen/s10-result/ in the shape of s9-result/ — documents/,
scores.json, answers/ (tools/replay_run.py debug/runs/S10-sweep
--save-answers <dir>, with hashes), dth_env.txt, and a README giving its
provenance, the prediction it held, and the ticket's tau leg named as
s9-result/'s README names its one. Prove the freeze: replay and rederive
of tests/frozen/s10-result each 21 of 21 byte-identical, and the report
scored straight out of it against s9-result/. Then update CLAUDE.md's
baseline lines and docs/status.md, close #37, one commit.

If he does not, ask what he wants done first. Whatever comes next is
his to name.
```

---

## Handover prompt — implement spec 0014, then one sweep (record — done 2026-10-15)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0014-every-line-a-place.md end to end — the only open work,
issue #37. Do not pick anything else up unless Alessandro names it.

The baseline is tests/frozen/s9-result/ (spec 0013's sweep, 21
documents, 732 answers, Alessandro's decision 2026-10-14). Prove it
before any change (step 0):
- tools/replay_run.py tests/frozen/s9-result --label S10-0-replay
  reproduces 21 of 21 byte-identical, 0 marked;
- tools/rederive.py tests/frozen/s9-result --label S10-0-base gives 21
  of 21 byte-identical files;
- the suite: 1142 passed, 1 skipped; mypy src clean.

The fault, measured in the spec's §1: a printed line the Zone's reading
has no place for — a form's note under its tick boxes, a table's legend,
a route under a ticket's passenger name — is dropped, or forced into
label/value. The steps, in order:
1 Zone.extra — a Zone can hold lines its Kind has no place for:
  the IR field, cells_of yields them last, render._zone_body draws
  them before or after the body. Offline: 21 of 21 identical but
  "extra": [].
2 read what nobody read — after _locate, each unclaimed line is read
  on its own crop with the existing prose prompt and kept in its
  Zone's extra unless the Zone already prints it; locate runs once
  more. A separate pass, so no existing answer moves. Prediction:
  form, ticket, timetable ASKED MORE by one call each, nothing else.
3 copies take the Kind that keeps the most of a line — structure.alike
  picks, among the Kinds the copies were given, the first in (prose,
  list, pairs, table, figure), not the majority. Prediction: catalogue
  and darkdeck ASKED DIFFERENTLY, nothing else; watch the catalogue's
  price rows.
Steps 2 and 3 are each checked by a targeted run on their pages
(FIXTURE=<pages> tools/iterate.sh <label>) — a check that the step
works, not the review.

Judge every step by eye: sheets against the previous step's run, each
moved page better / same / worse with a sentence; the six held-out
pages in their own lines; scores recorded, never argued from; vanished
and the unclaimed list read as pointers. Each step its own commit;
every new IR-writing step added to tools/rederive.py. Report each step
with what the pages look like and the report.html path; continue
unless a page got worse, then stop, show it, ask.

Then register §7's prediction in the spec (step P), and run ONE sweep,
S10-sweep, over all 21: about 2h15m, started detached (docs/status.md's
loop has the line). Do not touch tools/iterate.sh while it runs. Check
the prediction, open all 21 sheets against S10-0-replay, and report in
the error-analysis format: the five pages first (form, ticket,
timetable, catalogue, darkdeck), each against its line in §1, then the
six held-out pages in their own lines. Whether S10-sweep becomes the
baseline is Alessandro's decision. Type read as a figure is NOT in this
spec — it waits on his call (§6).
```
