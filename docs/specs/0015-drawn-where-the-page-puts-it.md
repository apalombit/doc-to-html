# Every line read, and drawn where the page puts it — the ticket and the certificate first

**Status: done and decided. Steps 1–3 were judged by eye; `S11-sweep` held
§6's prediction to the byte, with six pages better, fifteen the same and
none worse. Alessandro took it as the baseline on 2026-10-17, frozen as
`tests/frozen/s11-result/`. Issue #38, closed.** Three steps, in order,
each judged by eye, then one full sweep, `S11-sweep`, over all twenty-one
documents. The handover prompt at the end, marked *current*, is the one to
start a session with.

Alessandro's decisions, 2026-10-15:

1. **`S10-sweep` is the baseline**, frozen as `tests/frozen/s10-result/`.
2. **Groups 1, 2 and 3 of the recap after `S10-sweep`, in that order**:
   lines nobody reads; lines forced into label → value; things the page
   sets side by side drawn stacked or out of place.
3. **`ticket_0020` and `certificate_0021` are the focus.** They are the two
   pages whose *layout* is plainly not the page's. The ticket is "messy and
   totally inconsistent". The certificate's signature row should be three
   columns, and it is drawn as one. Each step is judged first on those two,
   and §1 says, fault by fault, what this spec does to them and what it does
   not.
4. **Everything else is cleared.** The other recap groups (marks and badges,
   misreads, emphasis), spec 0014's directions and the wordmark question are
   not queued. They return only if he names them.
5. **General repairs, not per-page ones** (his ask on 2026-10-14, still
   standing). Every step below is a rule about a kind of page, and each one
   is measured over all twenty-one.

---

## How to work

- **By eye.** Every step ends with sheets for the pages it moved, against
  the step before. Judge each page better / same / worse in one sentence
  that names the element. **Ticket and certificate first, every step.**

  ```
  tools/visual_review.py <run> --previous <previous step's run>
  ```
- **Scores are recorded, never gating, never argued from.** The one number
  read is the report's `vanished` list, as a pointer to a page to open.
- **The six held-out pages** (`corpus.NEW`: letter, pricing, paper,
  timetable, ticket, certificate) are reported in their own lines.
- **Each step is its own commit.** Every new step that writes the IR goes
  into `tools/rederive.py`.
- **Report each step** with what the pages look like and the `report.html`
  path. Continue unless a page got worse; if one did, stop, show it, and
  ask.
- **Each step names its prediction before it is measured.**

**The loops**, proved on `s10-result/` at `b493477`'s code; see its README:

| loop | command | what it can measure |
|---|---|---|
| rederive | `tools/rederive.py tests/frozen/s10-result --label <L>` | every step downstream of the model — steps 2 and 3 |
| replay | `tools/replay_run.py tests/frozen/s10-result --label <L>` | the wire, the mapper and every pass. It marks a moved call **ASKED DIFFERENTLY** and a new call **ASKED MORE THAN THE RUN**; neither is a measurement |
| a targeted run | `FIXTURE=<a>,<b> tools/iterate.sh <L>` | the model's answers on the pages a step moved — step 1. **A check that the step works, not the review**; the review is the sweep |

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s10-result/scores.json
```

**The prototypes** behind §1's pictures are in
`debug/runs/_prototypes-0015/` (gitignored — if it has been cleared, the
text below is enough): `reach.py` (step 3b), `extent.py` (3a), `lines.py`
(2a, 2b), the measuring scripts `shares.py`, `wraps.py`, `placed.py`,
`zones.py`, and `widen.py` / `widen2.py` / `widen.json` (step 1). Each
patches today's code from the outside; none is the implementation.

---

## 1. The two pages, inspected at `s10-result/`

### `ticket_0020` — a photographed boarding pass

**Rotation is not the cause, and no rotation step is needed.** `rectify`
finds the paper's outline and straightens it (spec 0013, step 5): the
900×403 photograph becomes an upright 799×305 card, and every Zone box sits
on its own ink. The faults are all in how the straightened card is *read
and laid out*.

| what the reader sees | cause, at the stage that introduces it | in this spec |
|---|---|---|
| The stub (passenger, flight, seat, gate, group) is drawn in the header row, top right, and the pass body is pushed below a teal strip | The card is two panes split by a dashed perforation, but `structure._columns` never makes it a divider. The stub's box starts on the rule's own stroke (left 0.736, rule centre 0.737), so the stub counts as *crossing* it. The rule starts below the header bar (0.167), so the blocks beside it are the passenger block and the route block, which sit side by side, not stacked, and `_independent` fails. The page stays one `single` region, and the stub (top 0) joins band 0 | **3b** |
| The flight / date / boarding / gate / seat / group grid (label above value, three across) is drawn as one long label: value list | `render._printed_lines` gives up when any entry is unplaced, and `NL 0482` is unplaced (tesseract reads it as `nl 0429`) | **2b** |
| In the stub, `SEAT 12A` and `GROUP 2` are drawn below and right of `GATE C14`, not beside `FLIGHT` and `GATE` | `_printed_lines` forms lines from entries in the **model's order**, and the model listed the stub's pairs column by column | **2a** |
| `OSLO GARDERMOEN` is drawn at the foot of the passenger block, not under the name | spec 0014 draws a Zone's `extra` before or after its body only | **2d** |
| `OSL` is missing | Nobody reads it. The model's pairs answer has no place for it, and tesseract misses it at `locate`'s upscaled glyph size; read at the page's own scale, it finds it | **1c** |
| The gate note `Gate closes 20 minutes before departure` is missing | `locate.unclaimed` judges it claimed: half its words (`gate`, `20`, `minutes`) are spelt in other Cells | **1b** |
| `TRD` is drawn as a small title | type: a display-size Title drawn at title size | not in this spec |
| The barcode, the plane icon | marks: no step draws a drawn mark inside a pairs Zone | not in this spec |
| The stub's own teal header and its `NORDLYS AIR` | white type on the stub's fill is never read; reading the other polarity everywhere was measured and rejected (17 flags, 16 junk) | not in this spec |
| A teal strip printed `The` / `The` | an `equalise` halo strip under the header bar became a Zone, and the model read `The` off an empty crop. One page | not in this spec |
| `DEPARTS 08:05`, `CLASS Economy` drawn label beside value | both labels are unplaced, and neither 2b rule reaches them (no line-mate, and the next entry in reading order is their own value) | not in this spec |

**Prototyped offline, 3b + 2a + 2b together** (rederive of `s10-result/`
with `reach.py`, then `lines.py`): the stub stands beside the pass, the
header bar is over the left pane only, and the page's height is close to
the source's. The passenger block's grid draws in three columns, and the
stub's `FLIGHT | SEAT`, `GATE | GROUP` sit on their lines. What is left is
the "not in this spec" rows above, with a gap where `OSL` and the plane
are. **3b changes no page but the ticket. 2a and 2b change no page but the
ticket** (the catalogue's cards need 2b's second branch, not prototyped).

### `certificate_0021` — a framed certificate

| what the reader sees | cause | in this spec |
|---|---|---|
| The signature row is drawn as two rows: `S. Okonkwo` with the seal beside it, then `H. Brandt` alone below, its rule across the whole page | The three units of band 4 are each `.band > * { flex:1 1 12rem }` with a 2rem gap: 3 × 192 + 2 × 32 = **640px**, and the page's content box is **636px**. The third wraps. Measured in Chrome, it is **the only band that wraps in the corpus** (one of 30 multi-unit bands) | **3a** |
| The seal is a text chip `GUILD GTE 2026` | marks: a seal is a figure drawn as its reading | not in this spec |
| The names and roles are set flush left under their signatures, not centred | `Zone.align` measured `left` on both signature Zones | not in this spec |
| `S. Okonkwo` is drawn as a bold heading with a small `S.` | type: the signature's sizes are mis-measured, and its face is not read as script (Brandt's is) | not in this spec |
| The stars are black `★`, the small caps are capitals, and the course name has lost its bold | marks, emphasis | not in this spec |

**Prototyped offline, 3a** (`extent.py`): the three units stand in one row,
`S. Okonkwo` left, the seal centred, `H. Brandt` right, each starting where
the page starts it, and the page's height is close to the source's. **A
lane taken from the units' ink boxes alone was tried first and is
wrong.** The page centres each name under a 0.25-wide signature rule, the
ink box is the name, and `H. Brandt`'s lane came out 16% of the row, one
word per line. The extent that works is the unit's box together with its
frame and the rules anchored to it, which are the page's own lanes.

### What this spec will and will not do to them

- **The ticket stops being "totally inconsistent".** Two panes as on the
  paper, the field grids as grids, `OSL` and the gate note printed (if step
  1's lines are read as predicted), `OSLO GARDERMOEN` under the name. Still
  missing or off: the barcode, the plane, the stub's header, `TRD`'s and
  `OSL`'s display size, the `The` strip.
- **The certificate's signature row becomes three columns.** Still off:
  the seal drawn as text, the names not centred, `S. Okonkwo`'s type.

---

## 2. Step 1 — read the lines nobody reads (group 1; new calls)

**The fault, after spec 0014.** `locate.unclaimed` flags a line no Cell
claims, and `_read_unclaimed` reads it on its own crop. At `s10-result/`
it flags nothing, yet lines are still missing:

| page | line | why it is not flagged |
|---|---|---|
| `sample_semantic_0005` | `Tags:` | one word; `UNCLAIMED_WORDS` is 2 |
| `timetable_0019` | `Lunch` (the hatched row) | one word |
| `ticket_0020` | the gate note's `departure` (its second line) | one word |
| `ticket_0020` | `Gate closes 20 minutes before` | `_claims` counts half the distinct words, and `gate`, `20` and `minutes` are spelt in other Cells |
| `ticket_0020` | `OSL` | tesseract does not read it at `locate`'s upscaled glyph size (`TARGET_GLYPH`); it does at the page's own scale |
| `catalogue_0015` | `CP-402` | white on dark; known miss, stays |

**Measured over all twenty-one at `s10-result/`, 2026-10-15**
(`widen.py`, `widen2.py`):

- **1a. One-word lines** (`UNCLAIMED_WORDS` 2 → 1): **7 flags on 6
  pages.** Real: `Tags:`, `departure`, `Lunch`. The other four are
  tesseract misreads of Cells the Zone already prints: catalogue `9200` and
  `99`, darkdeck `914`, menu `puppincs`. **The re-read's guard must refuse
  those four.** Today `locate.holds` is an exact substring test on folded
  text; it needs the fuzzy match `place` already uses (`MIN_SIMILARITY`
  0.7).
- **1b. Claims by whole words, weighted by letters** — a line is claimed
  when Cells spell at least half of its *letters*, word for word. This adds
  the gate note (`gate before` left unclaimed), and two misread Cells the
  guard must refuse: the receipt's AID and the ticket's `nl 0429`.
  **Whole words are required.** By substring, `osl` is claimed by
  `oslogardermoen`.
- **1c. A second tesseract read at the page's own scale**, where the first
  read found no confident word. It finds `OSL` (confidence 96), and reads
  `NL 0482` correctly besides. Unrestricted, it also raises 11 fragments
  of headings. The restriction "only where the first read had no confident
  word" is the candidate; measure it.
- **1d. The re-read crop is the unclaimed words' own box**, not the line
  padded by `PAD_X` (0.03 of the page). On a line partly claimed, the
  padded crop takes in the claimed words and the answer repeats them.
- **Measured and rejected:** reading the other polarity on every Zone, 17
  flags of which 16 are junk. So `CP-402` stays missing.

**Prediction.** Only re-read calls are new, one per kept flag, on the pages
whose new flags survive the guard. Those pages are marked **ASKED MORE**,
and no existing call is asked differently. The lines printed are `Tags:`,
`Lunch`, the gate note (one line or two) and `OSL`. The four misreads add
nothing. Check with a targeted run on the flagged pages.

**Where to look.** `locate.unclaimed`, `CONFIDENT`, `UNCLAIMED_WORDS`,
`_claims`, `_covered`, `words` (its `glyph` scaling); `locate.holds`;
`orchestrator._read_unclaimed`; `preprocess.crop`.

---

## 3. Step 2 — pairs drawn as the page prints them (group 2; offline)

**The fault.** A pairs Zone is drawn line by line as the page prints it
(`render._printed_lines` → `_placed`, spec 0012 G4) **only when every entry
is placed**. Otherwise it falls back to a `dl` list. Its lines are formed in
the model's order, not the page's. And 40 lines across six pages are
labels with an empty value and no mark: lines forced into label → value
(catalogue 31; invoice_0002's four bank lines; the form's `OFFICE USE` and
`Date stamp`; cv's `REGISTRATION`; darkdeck's `+9%`; the letter's date).

**Measured at `s10-result/`** (`placed.py`): seven pairs Zones the page
prints as a grid are drawn as lists because one entry is unplaced. They
are four of the catalogue's nine cards (`BR-118`, `IR-212`, `OK-330`,
`SC-501`: the price or the code unplaced) and the ticket's passenger block.
The form's two are drawn by `_fields`. So **the catalogue draws its nine
copies two ways**: on those four the price is small and muted, `each` and
`In stock` are stacked, and `NEW` sits under the code. One Zone, the
ticket's stub, has lines in model order that differ from the page's.

- **2a. Lines by position.** Entries join a line by vertical overlap with
  any line, not only the last, and a line reads left to right. Prototyped:
  changes only the ticket's stub.
- **2b. An unplaced entry gets the place its neighbours imply.** Two rules,
  in order:
  1. the partner's column, on the line where its partner's line-mates keep
     the same role. The ticket's `NL 0482` goes under `FLIGHT`, on the line
     of `14 OCT 2026` and `07:35`. Prototyped: changes only the ticket.
  2. otherwise, on the line of the next placed entry in reading order,
     before it. The catalogue's `£9.80` goes on the line of `each`, and
     `OK-330` on the line of `NEW`. **Not prototyped.** The four catalogue
     cards are its target: predict they draw as the other five.
- **2c. A label with no value and no mark is a line**, drawn in its own
  look and not as a label (`class="label"`, `dt`, `--muted` fallback). The
  visible gain is mostly where the Zone is drawn as a `dl`, since `_placed`
  already takes each Cell's measured colour. Measure it on the six pages
  and say plainly if it changes nothing visible.
- **2d. A Zone's `extra` lines take their place among the printed lines**,
  by position, where the Zone is drawn by `_placed`. The ticket's `OSLO
  GARDERMOEN` goes under the name, and after step 1, `OSL` goes above it.
  Elsewhere `extra` stays before or after the body, as spec 0014 drew it.

**Prediction.** Rederive changes the ticket and the catalogue's four cards,
plus whatever 2c moves on its six pages. No other page changes outside its
embedded IR. **No word changes**: 2b infers positions, never text.

**Where to look.** `render._pairs`, `_printed_lines`, `_placed`,
`PLACED_CSS`, `_fields`; `locate._from_pairs`; `render._extra`.

---

## 4. Step 3 — side by side where the page puts it (group 3; offline)

- **3a. A band's units in the page's lanes.** Each unit of a `_band` row
  gets `flex:<lane> 1 0` in place of the stylesheet's `flex:1 1 12rem`.
  Its lane runs from where the page starts it to where the page starts the
  next one, and the last runs to the row's right edge. Its extent is its
  box together with its `frame` and the rules `furniture.place` anchored to
  its Zones. A unit already set flush right (`flex:0 1 auto`) keeps that.
  **Keep `COLUMN_REM`'s reservation:** a table's `min-width` still makes
  the row wrap where the table needs the room, which is why the wrap exists.

  Prototyped (`extent.py`), placements measured in Chrome at the source's
  width, all twenty-one. Seven pages' rows moved:
  - **0 rows wrap.** The certificate's was the only one.
  - **Within about 0.03 of where the page starts each unit:** the
    certificate, `invoice_0002`'s two panel rows (taken from their
    frames), the newsletter's masthead, menu, nonlatin, and the ticket's
    two rows.
  - **Two rows overshoot by about 0.07, and the step must fix both.**
    - `sample_semantic_0005`'s TL;DR panel lands at 0.67 where the page
      starts it at 0.60 (it was 0.52). Its side bar is anchored by
      `furnish.anchor`, not by `Furniture.zone`, so the prototype's
      extent missed it.
    - `invoice_0002`'s header row puts the ACME mark at 0.77 where the
      page has 0.69 (it was 0.60).

    In both, the lanes were measured across the units' own span rather
    than the row's. **Take the extent from what the render draws for the
    unit (`furnish.anchor`), and the lanes across the row's span on the
    page (`_span`, as `_stack` uses).**
  - Statement's, darkdeck's and cv's tables did not move.
- **3b. A drawn divider parts what it stands between.** In
  `structure._columns`:
  - A block that only reaches into the rule's own stroke does not cross it.
    Use the rule's `left`/`right`, not its centre.
  - The divider reaches as far as the blocks beside it: the stretch grows
    to the blocks it touches until it stops changing.

  Prototyped (`reach.py`): **changes no page but the ticket**, and only
  both together do. Either alone changes nothing. The ticket becomes one
  `columns` region, 0–1, split at 0.737.

  **Regions are read during layout**, before classify. A region spanning
  the whole page cuts no Zone (`cut_at_edges`), and `alike` reads grids
  only. So no crop should move. **Prove it with a replay** (0 asked
  differently) before trusting the rederive.

**Prediction.** 3a moves the seven pages above, each toward the page; 3b
moves only the ticket. The replay marks nothing.

**Where to look.** `render._band`, `_unit`, `_unit_box`, `STYLESHEET`'s
`.band` rules, `COLUMN_REM`, `_grid` (lanes from splits — the model to
copy); `structure._columns`, `_broken`, `_independent`, `_extended`;
`furnish.anchor`; `Furniture.zone`, `Zone.frame`.

---

## 5. Work plan

| step | what | runs on | done when |
|---|---|---|---|
| 0 | prove the baseline | replay, rederive, suite | replay 21 of 21 byte-identical, 0 marked; rederive 21 of 21; 1166 passed, 1 skipped; mypy clean |
| 1 | read the lines nobody reads: 1a–1d | replay, a targeted run | the flagged pages ASKED MORE and nothing else; `Tags:`, `Lunch`, the gate note, `OSL` printed; the four misreads refused |
| 2 | pairs drawn as the page prints them: 2a–2d | rederive | ticket and catalogue judged by eye; no word changed |
| 3 | side by side where the page puts it: 3a, 3b | rederive, then a replay for 3b | certificate's row in one line; ticket in two panes; replay 0 asked differently |
| P | register §6's prediction in this spec | replay at the last commit | the marked calls written down before the sweep |
| S | **`S11-sweep`**: all 21, shipped defaults, started detached | the model | §6 checked; all 21 sheets opened against `S11-0-replay`; the outcome written |

---

## Outcome — steps 1 to 3, 2026-10-15

Step 0 proved the baseline at `b912ee5`: `S11-0-replay` 21 of 21
byte-identical, 0 asked differently; `S11-0-base` 21 of 21 files; 1166
passed, 1 skipped; `mypy src` clean.

### Step 1 — `3e35c27`, read the lines nobody reads

Built as §2 has it, with four changes the measurements forced:

- **A Cell claims a line with half its words *and* half their letters.**
  Letters alone let the Cell `Mathematics` claim the timetable's legend,
  `Mathematics Science PE` (11 letters of 20), and the legend was never
  read again; the replay caught it as its crop moving. Words alone let
  `GATE` claim `gate before`.
- **The turned-over read keeps two words.** Its one-word lines over the
  twenty-one were `bae`, `ον`, `bb`, `ag`, all junk — the other polarity's
  16-of-17 again.
- **1c is rule erasure, not scale.** The first read erases every straight
  stroke over two body glyphs (16px on the ticket); `OSL`'s stems are
  longer. `display_words` erases only strokes over 60px.
- **The guard is the model's reading, after the call** (`locate.holds`):
  word for word against any entry, or alike (`MIN_SIMILARITY`) to a text
  with no place — an unplaced Cell or the Title. Alike to *any* Cell
  refuses `OSL` (0.86 to the placed `OSLO`); tesseract's own text cannot
  separate `99` and `914`, display prices it misreads. So the pages
  flagged only by misreads are ASKED MORE too, and print nothing.
- **1d** (`Unclaimed.reach`): the crop stops halfway to a claimed word of
  its line, and is byte-identical where none is near.
- `tools/replay_run.py` also says whether every call the run asked was
  asked again alike, by hash, wherever it falls: new re-reads sort among
  spec 0014's, and pairing by order called the old ones moved.

**Targeted run `S11-1-check`**, seven pages: all 193 calls `s10-result/`
asked on them answered byte for byte the same, 14 re-reads beyond.
Kept: `Tags:`, `Lunch`, `Gate closes 20 minutes before` and `departure`,
`OSL`. Refused: `£28.00`, `£22.40`, `$2.14`, `Puddings`, `The Copper Pot`,
`AID A00000000031010`, `NL 0482`, `m 9C — weekly`, `Science English`.
**By eye**: ticket, timetable better; sample_semantic's `Tags:` printed
as an `h1` — fixed in `357b183` (`render._as_set`: an extra heading set
neither bold nor larger than the body is a line); catalogue, darkdeck,
menu, receipt the same (IR only).

### Step 2 — `b48b7b2`, pairs drawn as the page prints them

- **2b's second rule needed two conditions.** As written it put
  `darkdeck_0009`'s `$2.14` on the line of `+9%`, which the page prints
  under it. Now: only where the entry's partner, if placed, is on that
  line, and the line has room before the entries it precedes — a glyph.
  The catalogue's four prices and `OK-330` keep their lines.
- **2d needed its lines placed** — `3c5e365`, `locate._from_lines`: an
  extra line no word run places goes on the uncovered line it claims by
  `unclaimed`'s own test, the display read included. The gate note
  (read by tesseract `gate user minutes before`) and `OSL` were drawn
  after the lines without it.
- **2c is visible on one page.** cv, form, invoice_0002, letter: the line
  already carried its ink inline; darkdeck's `$2.14` turns from muted to
  ink.

**By eye** (rederive `S11-2` against `S11-0-base`): ticket better (stub
on its lines, the passenger grid three across, `OSLO GARDERMOEN` under
the name); catalogue better (all nine cards alike; the four inferred
prices still small — no measured look); darkdeck slightly better; cv,
form, invoice_0002, letter the same. No word changed.

### Step 3 — `a8bc381`, side by side where the page puts it

- **3b's reach for drawn rules only.** On the layout stage's boxes a
  container's edge reaching further turned the catalogue's card frames
  into column regions and moved 24 of its crops — the prototype, run on
  final boxes by rederive, could not see it. Restricted, the replay
  asks nothing differently and only the ticket's region moves.
- **3a as written, plus a cap on `_placed`.** Given its page lane,
  `invoice_0002`'s `NO 554775/R1  Date 01/01/2015` spread its tracks over
  two thirds of the row; a pairs Zone drawn by its lines is now no wider
  than its type on the page.

**By eye** (rederive `S11-3b` against `S11-2`): certificate better (the
signature row one line — `S. Okonkwo`, the seal, `H. Brandt`); ticket
better (two panes) with one element worse, `BOARDING PASS` wrapping in
its lane because it is drawn larger than the page prints it (type, out
of scope); sample_semantic better (TL;DR at the page's start);
invoice_0002 better (panels, ACME mark, the `NO` line compact); twelve
pages the same, none worse.

Reports, scores recorded: `debug/runs/S11-1-check/report.html`,
`S11-2/report.html`, `S11-3b/report.html`.

---

## 6. The sweep's prediction — registered 2026-10-15 at step P

From the replays at `3c5e365` (the code `S11-sweep` runs; 1201 passed,
1 skipped, `mypy src` clean): `S11-P2-replay`
(`s10-result/`'s answers) and `S11-P2-check` (`S11-1-check`'s answers).

1. **749 calls**: all 735 `s10-result/` asked, asked alike (prompt,
   picture, schema) and answered byte for byte the same, and **14
   re-reads** beyond them — catalogue 2, darkdeck 1, menu 2, receipt 1,
   sample_semantic 1, ticket 4, timetable 3. Nothing else asked
   differently or more.
2. **The fourteen unmarked pages** render byte-identical to
   `S11-P2-replay`: certificate, cv, form, invoice_0001, invoice_0002,
   letter, newsletter, nonlatin, paper, pricing, report, sample_css,
   sample_table, statement.
3. **The seven marked pages** render byte-identical to `S11-P2-check`,
   each re-read answered as `S11-1-check`'s was: kept `Tags:`, `Lunch`,
   `Gate closes 20 minutes before`, `departure`, `OSL`; the other nine
   refused.

Then report the sweep in the error-analysis format:
1. **ticket and certificate first**, each against its table in §1, row by
   row;
2. the other pages each step moved (catalogue, sample_semantic,
   invoice_0002, timetable and the rest of 3a's seven);
3. the six held-out pages in their own lines;
4. where it gained;
5. the faults left, by stage;
6. a recommendation.

Whether `S11-sweep` becomes the baseline is Alessandro's decision.

---

## Outcome — the sweep, `S11-sweep`, 2026-10-16

`S11-sweep` on `6b1caf4` (the code of `3c5e365`), 2026-10-15 23:13 to
2026-10-16 01:35 (**2h22m**), shipped defaults, the model 40%/60%
CPU/GPU. Report: `debug/runs/S11-sweep/report.html`. Sheets against
`S11-0-replay`: `debug/runs/S11-sweep/_review/`.

**§6's prediction held to the byte.** 749 calls. All 735 calls
`s10-result/` asked were asked alike and answered byte for byte the
same, and the fourteen re-reads fell where registered, with no errors.
All twenty-one pages are byte-identical to the predicted ones: fourteen
to `S11-P2-replay`, seven to `S11-P2-check`.

**By eye, against `S11-0-replay`: six pages better, fifteen the same,
none worse.**

### The ticket, row by row against §1

| §1 row | at `S11-sweep` |
|---|---|
| stub in the header row, pass under a teal strip (3b) | **fixed**: the stub is its own pane beside the pass; height 1.439 → 1.052 |
| passenger grid drawn as one list (2b) | **fixed**: three across, label over value; `NL 0482` placed by inference, drawn small |
| stub's `SEAT`, `GROUP` below `GATE` (2a) | **fixed**: `FLIGHT  SEAT`, `GATE  GROUP` on their lines |
| `OSLO GARDERMOEN` at the foot (2d) | **fixed**: under `OSL`, under the name |
| `OSL` missing (1c) | **fixed at body size**: read and placed, but `look` is empty, so it is not drawn at display size |
| gate note missing (1b) | **fixed**: at the stub's foot, three lines where the page has two |
| `TRD` a small title | unchanged (§7) |
| barcode, plane | unchanged (§7) |
| stub's teal header, its `NORDLYS AIR` | unchanged (§7); `nordlys air` is one of the two words still vanished, since the main bar is drawn as a picture |
| teal strip `The` / `The` | unchanged (§7): z5, a prose Zone under the header bar |
| `DEPARTS`, `CLASS` label beside value | unchanged |

New: `BOARDING PASS` wraps in its lane. It is a `heading` block, drawn
bold at heading size, where the page sets it in small spaced capitals.
The header bar is three teal pieces (wordmark picture, `BOARDING PASS`,
the `The` strip), not one bar.

### The certificate, row by row against §1

| §1 row | at `S11-sweep` |
|---|---|
| signature row drawn as two rows (3a) | **fixed**: one row, `S. Okonkwo` left, the seal centred, `H. Brandt` right; height 1.377 → 1.126 |
| the seal a text chip | unchanged, and the chip now wraps to two lines in the centre lane |
| names flush left under their rules | unchanged: `Zone.align` is `left` on z5 and z6, measured against the name's ink box |
| `S. Okonkwo` a bold heading, small `S.` | unchanged |
| black stars, capitals for small caps, course name not bold | unchanged |

### The other pages

| page | by eye |
|---|---|
| catalogue | **better**: nine cards alike, each price on its card's line. Three prices (`£9.80`, `£28.00`, `£22.40`) are placed by inference and have no look, so they are drawn small; scale error 0.063 → 0.219 is that |
| invoice_0002 | **better**: Comments and Payment panels at the page's widths; the `NO` line compact |
| sample_semantic | **better**: TL;DR at the page's width. `Tags:` is printed, but on its own line after the links |
| timetable | **better**: `Lunch` printed, but under the grid instead of in its 13:20 row; tau 0.963 → 0.954 and beside 0.992 → 0.984 come from that position |
| darkdeck | same: `$2.14` a shade brighter, still small |
| the other fourteen | same. Paper, report, sample_css and sample_table are byte-identical to the replay's render. The rest differ only in band lane shares (3a), the `dd.line` rule (2c) or the embedded IR |

**The six held out:** ticket better, certificate better, timetable
better; letter, paper and pricing the same.

**Recorded, not argued from.** `vanished` 33 → 26: back are the gate
note's five words, `osl` and `lunch`; no word is newly vanished.
Ratchet legs that fell: the timetable's tau and beside, both from
`Lunch`'s place. Means against `s10-result/`, for the six held out:
tau 0.847 → 0.946, beside 0.528 → 0.737, height ratio 1.186 → 1.089.

### Did the two pages improve?

**Yes, in arrangement. Both now have the page's layout.** The ticket has
its two panes, its grids and its reading order. The certificate has its
signature row on one line. Both are about as tall as the source.

**The ticket still does not read as a boarding pass at a glance.** Four
things cause that, and spec 0015 fixed none of them:

- no display type: `OSL` and `TRD` are the page's visual anchor;
- the header bar is broken into pieces, with the `The` strip under it;
- the stub has no teal header;
- the barcode is missing.

The certificate's layout is now consistent. What is left is emphasis
and marks: the seal as a figure, the names centred under their rules,
gold stars, small caps.

### Faults left, by stage

| page | what the page shows | stage | evidence |
|---|---|---|---|
| ticket, catalogue | entries placed by inference drawn small and plain (`NL 0482`, three prices) | Style | no `bbox`, so `look` is empty; catalogue scale error 0.219 |
| ticket | `OSL` at body size; the page prints it at display size | Style | the display read places it, but `look.size` is `None` |
| ticket | header bar in three teal pieces, plus the `The` strip | Layout | z1 picture, z2 prose with a fill, z5 a halo-strip prose Zone |
| ticket | `BOARDING PASS` bold, too large, wrapping | Classify → Render | z2's block is `heading`, size 1.06 |
| certificate | names flush left under centred rules | Style | `align` is measured against the ink box, not the unit's extent |
| timetable, sample_semantic | extra lines drawn after a table or list (`Lunch`, `Tags:`) | Render | 2d places extras on their line in `pairs` Zones only |
| certificate, ticket | seal as a text chip; barcode and plane missing | Render (marks) | §7, cleared |
| ticket | stub header unread | Extract | other polarity rejected, 17 flags of which 16 junk |

### Directions, ranked by gain for cost

| # | stage | change | why | cost |
|---|---|---|---|---|
| 1 | Style | an entry with no measured look takes one: from its own box where it has one (`OSL`), else from the mates it lines up with | finishes steps 1–2 on the ticket and catalogue | rederive |
| 2 | Style | measure `align` against the unit's extent (box, frame, anchored rules), not its ink | certificate names centred; 3a's extent already exists | rederive |
| 3 | Render | extras placed on their row in table and list Zones too | `Lunch` in its row, `Tags:` before its links | rederive |
| 4 | Classify → Render | a `heading` block set no larger than the body, in caps, drawn as a line | `BOARDING PASS`; measure over all 21 | rederive |
| 5 | Layout | a drawn bar's fill as one container; a halo strip with no ink dropped | the ticket's header bar; removing the `The` Zone removes a call, which can be predicted | replay, then a sweep |

Marks (the seal, barcode, plane, stars, ticks) and the wordmark stay
cleared. They return only if Alessandro names them.

**Recommendation.** Take `S11-sweep` as the baseline: the prediction
held to the byte, six pages are better, none worse, and no word is
newly vanished. If the ticket and certificate stay the focus,
directions 1–3 are one offline spec.

---

## 7. Not in this spec

Named so they are not mistaken for misses. None is queued.

- **Marks and badges** — the ticket's barcode and plane, the certificate's
  seal and stars, pricing's ticks, timetable's swatches.
- **Type at display size** — `TRD`, `OSL`, `S. Okonkwo`.
- **Alignment inside a unit** — the certificate's names under their rules.
- **The ticket's stub header** — white type on a fill; the other polarity
  was rejected.
- **The ticket's `The` strip** — one page.
- **Misreads where the reading had a place** (`fempost`, `Quillton`, …) and
  **emphasis** (footnote markers, drop cap, small caps).
- **Type read as a figure / is a wordmark text** — cleared 2026-10-15 with
  the rest; it returns only if Alessandro names it.

---

## 8. Rules that bind

- "How to work" above, and CLAUDE.md's.
- **Never cite a past run.** The committed frozen directories are the
  exception, for what their READMEs say.
- **Any reviewed run covers all twenty-one documents.** Step 1's targeted
  run is a check, not a review.
- **Never edit `tools/iterate.sh`, or any script a running sweep reads.**
- **Marking may never change the words.** Keep the four shipped defaults
  and the six wire row nets. Step 1 adds only lines the page prints and
  the Zone does not; step 2 infers positions, never text.
- **What is read off a Graphic is `alt`, never printed.**
- Leave `debug/runs/84-rule-not-a-line/` intact. Never score against
  `tests/documents/SAMPLE_DOCUMENTS`.

---

## Handover prompt — implement spec 0015, then one sweep (record)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0015-drawn-where-the-page-puts-it.md end to end — the only
open work, issue #38. Do not pick anything else up unless Alessandro
names it; everything else was cleared on 2026-10-15.

Focus: ticket_0020 and certificate_0021. Their layout is plainly not the
page's, and §1 of the spec lists every fault on each with its cause and
whether this spec touches it. Judge every step on those two first.

The baseline is tests/frozen/s10-result/ (spec 0014's sweep, 21
documents, 735 answers). Prove it before any change (step 0):
- tools/replay_run.py tests/frozen/s10-result --label S11-0-replay
  reproduces 21 of 21 byte-identical, 0 marked;
- tools/rederive.py tests/frozen/s10-result --label S11-0-base gives 21
  of 21 byte-identical files;
- the suite: 1166 passed, 1 skipped; mypy src clean.

The steps, in order (the spec has the measurements and the prototypes,
in debug/runs/_prototypes-0015/ if not cleared):
1 read the lines nobody reads — locate.unclaimed widened: one-word lines,
  claims by whole words weighted by letters, a second read at the page's
  own scale where the first found nothing confident, the re-read crop
  tight on the unclaimed words, and a fuzzy guard so a misread of a
  printed Cell is refused. Prediction: only new re-read calls (ASKED
  MORE), Tags:, Lunch, the ticket's gate note and OSL printed; catalogue
  9200/99, darkdeck 914, menu puppincs refused. Check with a targeted run
  on the flagged pages.
2 pairs drawn as the page prints them — _printed_lines by position, an
  unplaced entry placed from its partner's line-mates or else before the
  next placed entry, a value-less unmarked label drawn as a line, extra
  lines placed among the printed lines. Offline. Prediction: the ticket's
  grids as grids, the catalogue's four list-drawn cards as the other
  five; no word changes.
3 side by side where the page puts it — a band's units in the page's
  lanes (extent = box + frame + anchored rules; COLUMN_REM kept), and a
  drawn divider that reaches the blocks it parts and is not crossed by a
  block on its stroke. Offline; prove 3b with a replay, 0 asked
  differently. Prediction: the certificate's signature row in one line,
  the ticket in two panes, seven pages' rows toward the page.

Judge every step by eye: sheets against the previous step's run, each
moved page better / same / worse with a sentence; the six held-out pages
in their own lines; scores recorded, never argued from; vanished read as
a pointer. Each step its own commit; every new IR-writing step added to
tools/rederive.py. Report each step with what the pages look like and
the report.html path; continue unless a page got worse, then stop, show
it, ask.

Then register §6's prediction in the spec (step P) and run ONE sweep,
S11-sweep, over all 21: about 2h20m, started detached (docs/status.md's
loop has the line). Do not touch tools/iterate.sh while it runs. Check
the prediction, open all 21 sheets against S11-0-replay, and report in
the error-analysis format — ticket and certificate first, each against
its table in §1, row by row. Whether S11-sweep becomes the baseline is
Alessandro's decision.
```

---

## Handover prompt — after `S11-sweep`: the baseline decision (record — done 2026-10-17)

```
Read CLAUDE.md's READ THIS FIRST, then docs/status.md, then
docs/specs/0015-drawn-where-the-page-puts-it.md's "Outcome — the
sweep". Spec 0015 is done. Its sweep, S11-sweep (commit 6b1caf4,
2026-10-16), is waiting for Alessandro's baseline decision. Do not pick
anything up unless he names it.

If he takes S11-sweep, freeze it as tests/frozen/s11-result/ the way
s10-result/ was made, before debug/runs/ is cleared:
- documents/<name>.html: the sweep's 21 document.html files;
- scores.json: debug/runs/S11-sweep/scores.json;
- answers/: tools/replay_run.py debug/runs/S11-sweep --save-answers
  tests/frozen/s11-result (it writes answers/ inside), 749 calls, every answer and hash checked against the sweep's
  trace.json, 0 differ;
- dth_env.txt, and a README with the provenance, the by-eye judgement
  (6 better, 15 same, none worse, against S11-0-replay) and the
  ratchet legs that fell: timetable tau 0.963 -> 0.954 and beside
  0.992 -> 0.984, both from where Lunch is drawn.
Prove it at HEAD before writing a word about it:
- tools/replay_run.py tests/frozen/s11-result: 21 of 21 byte-identical,
  0 marked;
- tools/rederive.py tests/frozen/s11-result: 21 of 21 byte-identical;
- the suite: 1201 passed, 1 skipped; mypy src clean.
Then point CLAUDE.md (the table of frozen directories, the report
command), docs/status.md and the loops at s11-result/, and close issue
#38 with a comment naming the outcome.

If he names next work, the outcome's "Directions, ranked" table is the
starting point. Directions 1–3 are offline (rederive): a look for
entries placed by inference, align measured against a unit's extent,
and extras placed on their row in table and list Zones. Write the spec
first, one file in docs/specs/ tracked as an issue. Judge by eye, with
ticket and certificate first if they stay the focus.
```
