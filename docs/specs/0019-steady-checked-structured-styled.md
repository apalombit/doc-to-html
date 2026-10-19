# One grouping however the page is pictured, the structure the IR lacks, the page's looks, and readings checked

**Status: planned 2026-10-19, issue #42; not started.**
- **The baseline** is `tests/frozen/s13-result/` (spec 0018's sweep).
- **One sweep, `S14-sweep`, at the very end.**
- **The four parts are spec 0018's four ranked directions**, taken up
  together.

## Alessandro's decisions, 2026-10-19

1. **All four directions, together, before one sweep.** Spec 0018's
   "Outcome — the sweep" ranked them:
   1. the detector's grouping, steady when the picture changes;
   2. readings inside a line;
   3. the structure the IR cannot say;
   4. looks.
2. **Nothing else is open.** Every earlier queue, list and direction is
   cleared. Do not pick up anything this spec does not name. The looks
   cleared on 2026-10-18 come back only as Part C names them.
3. **Part D spends model time.** It adds about 60 calls, half an hour, to a
   sweep. Its measured cost is below.

## Order

**Part A** grouping → **Part B** structure → **Part C** looks → **Part D**
readings → **the sweep**.

Each part reads what the one before settles:
- B, C and D work on the Zones A settles.
- D checks every placed Cell, and C places the Cells nobody placed.

So the parts run in this order, not in the directions' numbering.

---

## How to work

- **Judge by eye**, every step, against the step before:
  `tools/visual_review.py <run> --previous <run> --documents <moved>`. Each
  page gets better / same / worse and one sentence naming the element.
- **List every page whose markup moves, and open each one.**
- **Each step is its own commit, with its tests.** Every new step that
  writes the IR goes into `tools/rederive.py`.
- **A step that moves a crop or asks a new question is proved on a targeted
  run** of the pages it moves before the next step:
  `FIXTURE=<pages> tools/iterate.sh <label>`.
- **Scores are recorded, never gating, never argued from.** `vanished` is
  read as a pointer to a page to open.
- **Stop and ask Alessandro** at A1's checkpoint, if a page gets worse, or if
  a word the baseline shows vanishes. Otherwise carry on to the sweep.

| loop | what it measures | cost |
|---|---|---|
| `tools/rederive.py tests/frozen/s13-result` | render and every step downstream of the model | about a minute |
| `tools/replay_run.py tests/frozen/s13-result` | wire and passes on the recorded answers; ASKED DIFFERENTLY / ASKED MORE name the calls that moved | about two minutes |
| `tools/layout_front.py` | the CV-only layout front: Zones and structure | seconds |
| the jitter check (A0) | the layout front on the page's own picture, perturbed | about two minutes |
| `tools/twins.py debug/twins --check` | `rectify` and the layout front on photographed copies | about 13 minutes |
| targeted run | the model on the pages a step moves | minutes a page |

The measurements below were taken on 2026-10-19 over the corpus as shot
and `s13-result/`'s IRs, at `e33d246`'s code, with scratch scripts. Each
method is described closely enough to rebuild it, and A0 commits the
first.

---

## Part A — one grouping however the page is pictured (direction 1)

### §A What moves the grouping, measured

**The page's own picture, changed by what no reader would see.**
- Each corpus page's `Rectified.image` was perturbed four ways: resampled
  to 98% and back, to 102% and back, shifted 1px right and down, and
  blurred at σ 0.6.
- The layout front (`LayoutEngine.detect_zones`: the forward pass and every
  rule) ran on each.
- Its Zones were compared with the unperturbed page's: kept at IoU ≥ 0.5,
  merged into a larger one, or lost.

| | |
|---|---|
| Zones kept | **631 of 848, 0.744** |
| pages that regroup on at least one perturbation | **16 of 21** |
| how | nearly always merges: finer Zones swallowed by a coarser one |
| worst | cv 15/31, pricing 4/21 (1/21 blurred), the ticket 0/5, form 3/8, the timetable 1/3 |

- **Softness moves the grouping; position barely does.** The 1px shift
  moves few pages. Resampling and blur move most. The detector groups a
  crisp picture finely and a soft one coarsely, and a photograph is soft.
- **This is B0's fault 5 (spec 0018), without `rectify`.** It is why spec
  0018's C1 loose read, C2 and C4 each lost pages through regrouping while
  their own geometry or light was right.

**Where it enters.** Each stage of `detect_zones` was compared, page
against blurred:

| stage where the grouping first diverges | pages |
|---|---|
| `outermost` | cv, pricing, the ticket, the timetable, the report |
| `cut_at_sections` | form |
| `prefer_container` | sample_semantic |

At `outermost`, a container clears the 0.40 threshold on the softer copy:
- a `picture` over pricing's cards;
- a whole-page `picture` on the ticket;
- a `table` and a `picture` over cv's sidebar.

`outermost` keeps it and drops every part. On the crisp page the same
container scores under the threshold, and the parts stand. **The grouping
is decided by which side of 0.40 a container's score falls**, and softness
moves that score.

### §A Arms measured and rejected

| arm | Zones kept under perturbation | pages whose Zones move | why not |
|---|---|---|---|
| today | 0.744 | — | |
| forward pass on a fixed-size, softened copy (1000px wide, σ 1) | 0.837 | 16 | steady by collapsing: cv 1 Zone, the ticket 1, the catalogue 3 |
| forward pass resized with antialiasing, as Heron was trained (PIL bilinear) | 0.796 | 8 | the ticket becomes 1 Zone |
| forward pass on a sharpened copy (unsharp mask) | 0.779 | 11 | cv, form, pricing and the ticket still regroup |
| scores averaged over four perturbed passes | 0.844 | 12 | coarsens cv (16 Zones) and pricing (5) |
| five whole groupings, each Zone kept where a majority draws it | 0.880 | 12 | coarsens the same pages; five forward passes |
| `prefer_container` off | 0.732 | 7 | not the cause |
| a Zone holding two or more drawn boxes split into them | 0.741 | 1 | steadies the catalogue and the certificate only |

**No change to the picture the detector is shown steadies the grouping
without coarsening it.** The fault is a decision taken on a threshold
crossing, and Part A changes the decision.

**Recorded, not the cause:** `Heron.detect` squashes the page to 640×640
with `cv2.INTER_LINEAR`, which does not antialias when shrinking. Heron's
`preprocessor_config.json` asks for PIL bilinear (`"resample": 2`), which
does. Matching it measured 0.796 and moved 8 pages.

### Steps

**A0. The check, committed.** `tools/layout_front.py --jitter` (or a tool
beside it):
- the four perturbations above;
- per page, Zones kept / merged / lost against the page's own;
- the total.

Proved by reproducing today's 0.744, byte-identical run to run. The twins
check is the second measure.

**A1. Container or parts, decided on what the page shows, not on a score.**
Where `outermost` would keep a container over two or more confident parts,
it keeps the container only if:
- **(a) the page draws it**, as a drawn box or fill (`style.rectangles`,
  `furniture`): steady under resampling since spec 0018's B1; or
- **(b) the container holds ink none of its parts carries**: its parts
  cover less than `SPLIT_INK` of its ink.

Otherwise it keeps the parts. The same test replaces the score crossing in
`prefer_container`, and `cut_at_sections` reads its drawn sections the
same way.

- **Keep what `outermost` was built for:** a panel and the rows printed
  inside it are one region. `invoice_0002`'s panels are drawn, so (a)
  keeps them.
- **Watch what `open_unsure_containers` measured** when its own rule was
  too wide: `invoice_0002`'s pairs opened into fourteen words,
  `nonlatin_0014`'s totals line into label and value, and darkdeck's and
  the ticket's pictures opened.
- **Target:**
  - the jitter check ≥ 0.95, with no Zone lost;
  - the twins' Zones kept up from today's;
  - on the corpus as shot, the layout front's Zones unchanged, so no crop
    moves. Any page whose Zones move is opened and judged.
- **Checkpoint: stop and ask** before the targeted run, with the jitter
  table, the twins table, and every corpus page whose Zones move.

**A2. A targeted run** of every corpus page A1 moves, if any. None, if A1
meets its target as written.

**What Part A makes possible, not in this spec:** spec 0018's C2 (corners
to a tenth of a pixel) and C4 (equalise only uneven light). Each lost pages
through regrouping. Each is a retry for after this sweep, if Alessandro
names it.

---

## Part B — the structure the IR cannot say (direction 3)

Each step adds one thing the IR cannot express today, filled from the page
and drawn. **No prompt changes:** each is CV, wire or render.

**B1. Cells that span.**
- **Evidence:**
  - `timetable_0019`'s table answer gives each printed line as a row: the
    subject, then the room. A lesson that runs two slots is text in the
    first slot and blanks in the next.
  - The IR has no span. The render clips Monday's 09:00 `Mathematics` under
    a white box, sets Tuesday's 10:00 `Science` across two columns, and
    loses PE's second hour.
  - `Lunch`, a row the page draws across the grid, is drawn under it.
- **The rule:**
  - **(i)** A row whose key column is empty, and whose cells lie inside the
    drawn cells of the row above, is that row's second printed line. It is
    joined into those cells as their second line.
  - **(ii)** A cell whose drawn cell (fill or rules) covers the slots
    below it, those slots empty, spans those rows. The same holds across
    columns: `Registration and tutor time`.
  - **(iii)** A row the page draws across the whole grid with one text is
    one spanning cell in its place: `Lunch`.
- **The IR and render:** `Cell.span` (rows, columns), drawn as `rowspan`
  and `colspan`.
- **Proved by:** the timetable by eye. Every other table byte-identical
  unless it draws a span.

**B2. Raised marks.**
- **Evidence:**
  - `paper_0018`: the model reads `Solberg¹`, `Achterberg²`, `common.¹` as
    Unicode superscripts. Drawn inline, they look like body digits and
    score as `solberg1` (six cells).
  - `report_0011`: the model drops two footnote marks (`side by side.¹`,
    `basin.²`), and reads the third as a line of its own, `3`, drawn
    `2027. 3`.
- **The rule:**
  - **(i)** Superscript characters are drawn raised and apart from their
    word, as their own Run: a Run kind `sup`, added to `ir.INLINE_KINDS`
    and to the scorer's. The characters are not changed.
  - **(ii)** A mark the reading dropped or set apart. Where tesseract's
    words on the line (`locate`) show a small raised glyph after a word —
    under 0.7 of the line's x-height, its top above the x-height — its
    digit joins that word as a `sup` Run. A line holding only that digit
    folds into the line before it.
  - **Never a word the page does not print.**
- **Proved by:** paper and report by eye; `invented` loses `solberg1` and
  its kind.

**B3. Display lines.**
- **Evidence:** `paper_0018`. The model reads `Δh = α √F` and `(1)` as
  lines of their own, and the render's reflow joins them into the
  paragraph.
- **The rule:** a line the page prints centred in its column, set apart
  above and below, is not reflowed. A line holding only `(n)`, printed
  flush right on that line, is its number.
- **The IR and render:** a display flag on the line and its number. Drawn
  centred, the number flush right.
- **Proved by:** paper by eye. No other page has a centred, set-apart line
  inside a paragraph, which is checked over the corpus.

**B4. A pair's separator, as printed.**
- **Evidence:**
  - `invoice_0001` prints `Created:` and `Due:`, and `invoice_0002` prints
    `NO: 554775/R1 | Date: 01/01/2015`.
  - The model returns the labels without the colon, and the render draws
    none.
- **The rule:**
  - The separator the page prints at the label's end is kept on the
    pairs: tesseract's raw text there, `:`. A bar printed between pairs is
    kept likewise.
  - `locate.Word` keeps the raw text beside the folded one; today it keeps
    the folded text only.
- **Proved by:** both invoices by eye; every other pairs Zone checked for a
  separator it does not print.

---

## Part C — the page's looks (direction 4)

**§C Why looks go missing.** A look is measured only for an entry `locate`
placed.

| entry | why it has no look |
|---|---|
| the certificate's seal: `GUILD`, `GTE`, `2026` | white on a gold disc; never placed |
| the certificate's stars | a mark; never placed |
| `sample_css_0004`'s `CSS` badge | white on blue; never placed |
| the ticket's `OSL` | placed as an extra line, never measured: drawn at body size |

The render then falls back to defaults:
- **seal:** an orange text box;
- **stars:** black;
- **badge:** plain `css` on its own line;
- **`OSL`:** body size.

**C1. Every printed entry placed, and every placed entry measured.**
- **Type on a fill inside a Zone** — a chip, a pill, a disc — is read in the
  other polarity on that fill's own crop. Today `locate` turns a whole Zone
  over, and only where the first read left a Cell unplaced.
- **A mark** (★ ✦ •) is placed by its glyph's ink.
- **Every placed line is measured, extras included:** `OSL`'s size.
- **Proved by:** the certificate, sample_css and the ticket by eye.
  `vanished` gains no word.

**C2. Weight as measured, never by element.**
- **Evidence:** `menu_0012`'s title, `newsletter_0008`'s masthead and
  headline, `certificate_0021`'s title, `report_0011`'s title and
  `receipt_0010`'s header row are regular on the page and bold in the
  render. The render's `h1`, `h2`, `th` and caption are bold by default.
- **The rule:** bold only where the entry's look says bold.
- **Proved by:** each page named, by eye; every page re-rendered and every
  moved page opened.

**C3. Shapes the page draws round type.**
- **A chip on a line is drawn on that line.** `sample_css`'s badge sits
  beside its Title, not on a line below.
- **A disc is drawn as a disc**, with its fill and its ink. A fill is a
  disc when its ink fills about π/4 of its box: the certificate's seal.
- **Proved by:** both pages by eye.

**C4. Drop caps.**
- **Evidence:** `newsletter_0008`. The model reads the first paragraph as
  `he stretch of towpath between Bridge Street`, a heading, and loses the
  `T`.
- **The rule:**
  - A glyph two or more body lines tall, at a paragraph's top left, is
    that paragraph's first letter.
  - It is read on its own, by tesseract on the glyph's crop.
  - It is put back before the paragraph's first word, and that first line
    rejoins its paragraph.
  - It is drawn floated, as tall as the page draws it.
- **Proved by:** the newsletter by eye. `vanished` gains no word; the
  missing `T` is a word the page prints.

**C5. Faces and colours, once placed.** C1 places the entries, and
`looks` already measures:
- **colour:** the stars' gold;
- **face:** the certificate's signature `S. Okonkwo`, which `face=script`
  should catch as it does the name above it.

Check both; build nothing new unless one is missed.

---

## Part D — readings checked by a second reader (direction 2)

**§D A second reading already exists.** `locate` reads every Zone with
tesseract to place its Cells. The words inside a placed Cell's box are a
second reading of that Cell, taken today and thrown away.

**Measured over `s13-result/`'s 1,070 placed Cells.** Each is folded whole
(letters and digits) and compared with the source page's text:

| the two readings | Cells |
|---|---|
| alike, or tesseract read nothing in the box | 976 |
| different, the model right | 72 |
| different, tesseract right | **14** |
| different, both on the page | 7 |
| different, neither | 1 |

**The 14 are the sweep's misreads:**
- the statement's 216.08, 1,144.30, `Lindow` and `Quillon` twice;
- `fernpost` twice; `Councillor`; `adipisicing`; `chervil`;
- nonlatin's `Έλεγχος`, `επίβλεψης`, `aigaio`, and its footer.

**Confidence does not separate them.** Tesseract is at 90 or above on 9 of
the 14 and on 13 of the 72.

**Distance does.** 13 of the 14 differ from the model's reading by 1–4
characters. The fourteenth is nonlatin's footer, a different company's
name 20 characters away.

**A third reading arbitrates, measured.** The 59 Cells within 3 characters
of tesseract were each read again by the model on the Cell's own crop,
with the prose prompt, as `_read_unclaimed` reads a line. Taking what two
of the three readings agree on:
- **6 of the 12 true misreads are repaired:** the statement's four,
  `fernpost` on the form, and `Councillor`;
- **none of the 41 the model had right is changed;**
- **in 5 the third reading misreads anew** (`tempost`, `cheru`): there is no
  majority, and the model's reading stands;
- **cost: 31 s a call**, at 40%/60% CPU/GPU.

**D1. The second reading, kept.**
- **What:** for each placed Cell, `locate` keeps tesseract's text, raw and
  unfolded, as a second `Reading` (engine `tesseract`). Cells whose
  readings fold alike are `AGREED`.
- **Why it is safe:** no text changes, so every page renders as before.
- **Proved by:** rederive, byte-identical outside the embedded IR.

**D2. The third reading, where the two are near.**
- **Which Cells:** those whose readings differ by at most 4 characters,
  folded. That threshold is set from the distribution: it holds 13 of the
  14 true misreads and 69 Cells in all.
- **The pass:** each is read by the model on its own crop, one call per
  Cell. It is a separate pass after `locate`, in the slot
  `_climb_ladders` keeps for it, so no Extractor prompt changes.
- **The outcome:**
  - a majority makes the Cell `RESOLVED`, carrying the majority's text;
  - no majority makes it `DISPUTED`, drawing the model's text with the
    others kept. The render already titles a disputed Cell with its other
    readings.
- **Proved by:** a targeted run.
  - The statement, nonlatin, form, cv, menu, newsletter and invoice_0002
    hold the misreads.
  - Darkdeck and sample_table hold only Cells the model has right; they
    show the pass harms nothing.

  The replay cannot serve these calls: it marks the pages ASKED MORE.

**D3. Out of reach, recorded.** Nonlatin's footer is 20 characters from
tesseract's reading: the model named another company. No near-miss rule
reaches it.

---

## Not in this spec

- **Spec 0018's C2 and C4.** They wait on Part A; reopen them only if
  Alessandro names them.
- **The twins joining the corpus:** no (2026-10-19).
- **Everything else**, cleared.

---

## The sweep

**One sweep, `S14-sweep`, all 21 pages, after Part D.**
- **Register the prediction first** from the replay of `s13-result/` at the
  sweep's commit:
  - every page ASKED DIFFERENTLY or ASKED MORE, named;
  - D's added calls, counted;
  - every page asked alike predicted byte-identical to its replay.
- **Budget about 2h55m:** today's 2h20m and D's 69 calls at about 31 s. Start it detached,
  as `docs/status.md`'s loop says, and do not edit `tools/iterate.sh`
  while it runs.
- **Score it** against `tests/frozen/s13-result/scores.json`.
- **Build the sheets** with `--previous debug/runs/S13-sweep`. Do not clear
  it before then.
- **Report in the error-analysis format:** gains, faults by stage,
  directions ranked, recommendation.
  - **The pages each part targets come first:** the timetable, paper,
    report, the two invoices, the certificate, sample_css, the newsletter,
    the menu, the statement, nonlatin and the ticket.
  - Then every page better / same / worse, one sentence each.
  - Then the jitter and twins tables against today's.
- **Point out clear deviations from the originals.**
- **The baseline decision is Alessandro's.**

---

## Handover prompt

> Implement and run spec 0019,
> `docs/specs/0019-steady-checked-structured-styled.md` (issue #42), in
> this fresh session.
>
> **Read first, in order:** `CLAUDE.md`'s READ THIS FIRST; `docs/status.md`;
> the spec, end to end. The baseline is `tests/frozen/s13-result/`. Nothing
> outside the spec is open: do not pick up anything it does not name.
>
> **Order:** Part A (A0, A1, A2), Part B (B1–B4), Part C (C1–C5), Part D
> (D1–D3). Then one sweep, `S14-sweep`, over all 21, and nothing in
> between.
> - Each step is its own commit with its tests.
> - Every new step that writes the IR goes into `tools/rederive.py`.
>
> **Each step:**
> - Prove it offline: rederive, replay, the layout front, the jitter check
>   (from A0) and the twins.
> - A step that moves a crop or asks a new question also needs a targeted
>   run of the pages it moves: `FIXTURE=<pages> tools/iterate.sh <label>`.
> - Judge by eye against the step before. List every page whose markup
>   moves, open each one, and give each a sentence: better, same or worse.
> - Scores are recorded, never gating. `vanished` is a pointer to a page to
>   open.
>
> **Part A is the uncertain one.** §A's measurements rule out every change
> to the picture the detector is shown. Change the decision `outermost`
> takes instead.
>
> **Stop and ask Alessandro** at A1's checkpoint, if a page gets worse, or if
> a word the baseline shows vanishes. Otherwise carry on.
>
> **The sweep:**
> - Register its prediction from the replay first, and start it detached.
> - Do not edit `tools/iterate.sh` while it runs.
> - Score with `--documents sweep` against `s13-result/scores.json`, and
>   build the sheets with `--previous debug/runs/S13-sweep`.
> - Report in the error-analysis format, the targeted pages first.
>
> Then rewrite `docs/status.md`, add the spec's outcome section, and leave
> the baseline decision to Alessandro. Point out the clear deviations from
> the originals you saw on the sheets.
