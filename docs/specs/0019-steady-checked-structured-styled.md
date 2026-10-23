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

## Outcome — the steps

One commit a step, each with its tests. Every step was proved offline
before the next, and every page whose markup moved was opened against
the step before:
- through D1, `tools/rederive.py` and `tools/replay_run.py` over
  `s13-result/` agreed 21 of 21, with 0 asked differently;
- D2 asks the model, and was proved by two targeted runs.

No step shipped a page worse, and none made a word the baseline shows
vanish. D2's first drawing did make pages worse, and Alessandro
decided it (below).

### Part A — grouping

**A0** `1397ed4`: the jitter check, `tools/layout_front.py --jitter`.
- Each page's `Rectified.image` perturbed four ways no reader would see
  (98% and back, 102% and back, 1px right and down, blur at sigma 0.6),
  `detect_zones` run on each, and the page's Zones counted kept
  (IoU ≥ 0.5), merged (0.9 inside a larger one) or lost.
- At the spec's start: **635 of 848 kept, 0.749; 16 of 21 pages
  regrouping.** Every page figure §A names is this check's, to the Zone.

**A1** `d0c7eea`: four decisions the detector took on a score crossing,
taken on the page. **Checkpoint: Alessandro kept it, 2026-10-20, and no
A2 was run.**
- `without_unsure_tall_containers`: a container taller than
  `CONTAINER_HEIGHT`, less sure than a part it holds and holding no
  graphic, does not overrule its parts (cv's sidebar, pricing's cards).
- `SHEET`: a box over the whole page is the sheet, never a region (the
  ticket's whole-page picture).
- `trimmed_to_drawn`: a container the page draws is as large as the page
  draws it (the timetable's grid climbing over the line above).
- `style.outlined`: `cut_at_sections` reads a field only from a box with
  a line round it (form's softened heading bars).

| | before | A1 |
|---|---|---|
| jitter, Zones kept | 635 / 848 (0.749) | 751 / 848 (0.886) |
| pages regrouping | 16 | 14 |
| twins, Zones kept | 820 / 1080 (0.759) | 914 / 1080 (0.846) |
| corpus as shot | | layout front 21 of 21 byte-identical |

- **The target, ≥ 0.95, is not met.** The rest is spread over four
  causes the page does not signal: `prefer_container` adopting other
  boxes on soft copies (pricing's lists, report's footnotes, newsletter),
  the detector's own boxes moving (cv's two lines as one, the statement's
  and receipt's tables over the line below), softness flipping which box
  scores higher (pricing's left card, invoice_0002's logo), and report's
  title and subtitle as one box.
- **The rule as worded is not built.** "A container only if the page
  draws it or it holds ink its parts do not" measured 0.726 and moved 13
  pages as shot — a paragraph over its own lines fails both tests.
- Lost rose 28 → 36: Zones of cv's, pricing's and the ticket's copies
  that sat inside the container that swallowed them, their lines under
  0.40 on the soft copy. `_cover_the_page` gives that ink a Zone in a
  Conversion.
- **A2 had no pages**: A1 moves no Zone on any page as shot.

### Part B — structure

| step | commit | what it does | pages, by eye |
|---|---|---|---|
| B1 cells that span | `2f43e43` | `spans.read`: a ruled grid's second lines join the cell above (`Cell.below`), a line inside an empty drawn cell is its text, and an entry spans the empty slots its drawn cell covers (`Cell.span`, `rowspan` / `colspan`) | timetable better: rooms under subjects, the four double lessons over two slots, Registration and Lunch across the days |
| B2 raised marks | `204db2a` | `raised.read`: a superscript is its own `sup` Run; a small raised glyph the reading dropped or set apart is read on its own crop | paper better (six marks raised as printed; vanished 3 → 0, invented 5 → 0); report better (`side.¹`, `basin.²` back, `2027.³` for `2027. 3`) |
| B3 display lines | `34820e9` | `display.read`: a line centred in its column and apart above and below is `Cell.display` `line`, its `(n)` `number` | paper better: the equation centred and apart, `(1)` flush right on it |
| B4 a pair's separator | `e208701` | `separator.read`: the colon a label is printed with, the bar between two pairs (`Pair.separator`, `Pair.divider`), off tesseract's raw text | invoice_0001, invoice_0002, nonlatin, catalogue better |

### Part C — looks

| step | commit | what it does | pages, by eye |
|---|---|---|---|
| C1 every entry placed and measured | `5a7ee93` | type on a fill read on the fill's own crop; marks placed on their glyphs; a chip told from heavy type by its inked frame | certificate (gold stars on one line), sample_css (the badge a blue chip), ticket (`OSL` at 3.89), timetable (day heads at the page's size) better; nonlatin, catalogue, pricing, statement same |
| C2 weight as measured | `87fc1be` | an element the stylesheet draws bold — `h1`, `h2`, `th`, a total — is drawn regular where its entry measured regular; `Zone.title_bold`; a two-size line is no part of the page's regular weight; marks folded before the page is measured | eleven better (newsletter's masthead, certificate's title, report's title and caption, invoice_0002's panel titles, cv, pricing, letter, catalogue, timetable, nonlatin's subtotals, paper's section heads, statement's tile labels); form, darkdeck, sample_css, sample_table same |
| C3 shapes round type | `f90dbd3` | a chip at a line's end drawn on that line; a fill covering π/4 of its box within 0.05 is a disc (`Furniture.disc`), and the ring clear round it is measured (`Furniture.ring`) | sample_css better (the badge beside `Sample HTML`); certificate better (the seal a gold disc in its 2px ring, 4px clear, as its CSS draws it) |
| C4 drop caps | `1f9f556` | `dropcap.read`: a letter two lines deep or more at a paragraph's top left, its lines set beside it, is its first letter; the Blocks beside it one paragraph; drawn as the page's `::first-letter` | newsletter better: the `T` floated four lines deep, the first line back in its paragraph (the broken join `street` / `and` mended) |
| C5 faces and colours | `9671acf` | checked: the stars' gold measured; the signature `S. Okonkwo` missed — `SCRIPT_JOINED` 0.6 → 0.82, into the measured gap (script 0.20–0.75, italic type 0.90–1.03), and a script line is one size | certificate better: `S. Okonkwo` in the script face, one size |

- **C2 leaves four regular entries bold**, each measured: `menu_0012`'s
  title (2.14 the page's regular stem), the newsletter's headline
  (1.53), the receipt's header rows (a photographed page, whose weights
  are not read) and nonlatin's titles (not measured). The stem measure
  does not hold at display sizes.
- **C3's disc and ring** are the only fill over the twenty-one inside
  0.735–0.835 of its box; the next, invoice_0002's rounded logo, covers
  0.871.

### Part D — readings

**D1** `2b31497`: the words that placed a Cell kept as its second
`Reading`, engine `tesseract` — the run `place` matched, or, where a
fallback placed the Cell, tesseract's sure words inside its box. Every
page byte-identical outside its embedded IR.

| over `s13-result/` rederived | Cells |
|---|---|
| placed | 1,061 |
| alike, or nothing read | 985 |
| different, the model right | 51 |
| different, tesseract right | **14** — the spec's fourteen |
| different, both on the page | 10 |
| different, neither | 1 |

- 13 of the 14 are within 4 characters, folded; 58 Cells in all.
- Every word in the box, unfiltered, was tried first: tesseract's reads
  of texture and rules beside a figure (`216.08 &ta`) put 471 Cells on
  the model's side. The run that placed the Cell is the reading.

**The repairs D2's re-locate called for** `a78513f`: a Conversion that
locates a second time, and `tools/rederive.py` run over its own output,
must draw what the first pass drew. Four pages did not (report,
timetable, paper and a shortfall's line count): `spans.read` moved
before `rhythm` and `looks`; `locate` keeps the boxes of the Cells spans
built and matches a Cell by its words without its raised marks
(`locate.unraised`); `dropcap` places an existing cap again. Rederive of
a rederive: 21 of 21 identical. Paper and timetable same by eye.

**D2** `a0d73c9`: `ladder` and `Conversion._climb_ladders`. A Cell whose
two readings are 1–4 characters apart, folded, its raised marks left
out, is read once more by the model on its own crop. Two of the three
agreeing settle it (`RESOLVED`). With no majority it is `DISPUTED`, and
the model's text is drawn. A Cell that changed is placed and measured
again. The line a drop cap is set into is skipped: its box holds the
cap's ink.

Targeted runs `S19-D2-targeted` (the spec's seven pages, darkdeck and
sample_table) and `S19-D2c-targeted` (newsletter, paper, report, whose
calls the repairs moved), each replayed through the commit's code:

| page | asked | repaired | the model's kept | disputed | by eye |
|---|---|---|---|---|---|
| statement | 8 | 5 — 1,144.30, 216.08, Quillon ×2, Lindow | 3 | 0 | better |
| form | 6 | 1 — `fernpost` | 4 | 1 | better |
| newsletter | 3 | 1 — `Councillor` | 2 | 0 | better |
| cv | 3 | 0 | 2 | 1 | same |
| menu | 6 | 0 | 5 | 1 | same |
| nonlatin | 7 | 0 | 4 | 3 | same |
| invoice_0002 | 2 | 0 | 0 | 2 | same |
| paper | 5 | 0 | 5 | 0 | same |
| report | 1 | 0 | 1 | 0 | same |
| darkdeck, sample_table | 0 | | | | byte-identical |
| **all** | **41** | **7** | **26** | **8** | |

- **No word newly vanished.** `fernpost`, `144`, `216`, `lindow`,
  `quillon` and `councillor` came back.
- **The model's reading kept wrongly once:** nonlatin's `επίβλεψης`,
  where the third reading sided with the model.
- **Disputed, the model drawn:** cv's `fempost` (third `tempost`), menu's
  `chorvil` (`cheru`), nonlatin's `aigaiio`, `Έλευθος` and `Α' Πειραιά`
  (the third set a Latin `A`), invoice_0002's `mainl` and its Lorem
  paragraph, and form's footer, where the third reading was the page's
  (`Castleton`) but tesseract's `Incomptete` kept it from a majority.
- **Stopped and asked, 2026-10-22.** The render drew a disputed Cell on a
  tinted ground with an orange underline, which no page prints. Five
  pages were flagged, and on cv's dark sidebar the email could not be
  read. **Alessandro: drawn as the page prints it**, the other readings
  kept in its title and `data-alt`. With that, cv, menu, nonlatin and
  invoice_0002 are byte-identical to before D2 outside the IR.
- **Found on the run:** paper's footnote `²Delta … Delft`, read a third
  time without its `²`, was disputed. `settle` now compares the model's
  words as `due` does, its raised marks left out.

**D3** — out of reach, recorded: nonlatin's footer, the model's
`Αγγελίδης Μπραγκαντής Α.Ε.` against tesseract's `Αιγαίο Μηχανική Α.Ε.`,
18 characters apart. No near-miss rule reaches it; it stays the model's
reading, `AGREED`, with tesseract's kept beside it.

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

### The sweep's prediction — registered 2026-10-23

Taken at `a0d73c9`, the sweep's commit, from `tools/replay_run.py
tests/frozen/s13-result --label S14-prediction`: 0 asked differently,
and on all 21 pages every call `s13-result/` asked is asked again alike.

1. **811 calls: the baseline's 755, then 56 third readings** on 17
   pages. The 755 are asked alike and answered byte for byte as
   `s13-result/answers/`. The third readings per page:
   - statement 8, nonlatin 7, form 6, menu 6, paper 5, catalogue 4;
   - cv 3, newsletter 3, ticket 3, invoice_0002 2, receipt 2,
     timetable 2;
   - certificate, letter, pricing, report, sample_css 1 each.

   §D counted 69 when the spec was written. At `a0d73c9`, 57 Cells are
   within 4 characters, folded, their raised marks left out. Less the
   newsletter's cap line, that leaves 56.
2. **Four pages ask nothing new**, and their renders are byte-identical
   to `S14-prediction`'s: darkdeck, invoice_0001, sample_semantic and
   sample_table.
3. **Nine pages were asked their third readings on a targeted run**, and
   are asked alike at this commit:
   - statement, nonlatin, form, menu, cv and invoice_0002, from
     `S19-D2-targeted`;
   - paper, newsletter and report, from `S19-D2c-targeted`.

   Their renders are byte-identical to those runs replayed at
   `a0d73c9`.
4. **Eight pages are not predicted:** catalogue, certificate, letter,
   pricing, receipt, sample_css, ticket and timetable. Their 15 third
   readings were never asked. Everything before those readings is the
   replay's.

The jitter check at `a0d73c9` is A1's, unchanged: **751 of 848 kept
(0.886)**, with 14 of 21 pages regrouping. No step after A1 touches the
detector.

### Outcome — the sweep, `S14-sweep`, 2026-10-23

The run:
- commit `a0d73c9`, 08:17 to 10:55 (**2h38m**);
- 811 calls, the model 40%/60% CPU/GPU;
- report `debug/runs/S14-sweep/report.html`, scored against
  `s13-result/scores.json`;
- sheets against `S13-sweep` in `debug/runs/S14-sweep/_review/`, each
  page's verdict in its `findings.json`.

**The prediction held to the byte.**
- `s13-result/`'s 755 answers came back byte for byte, in order, on all
  21 pages, and the 56 third readings came on the 17 pages registered,
  each page's count as registered.
- The four pages asked nothing new are byte-identical to `S14-prediction`,
  and the nine asked on a targeted run are byte-identical to those runs'
  replays at `a0d73c9`.
- The sweep's own replay is 21 of 21 byte-identical, with 0 asked
  differently, and `tools/rederive.py` over it reproduces 21 of 21.

**By eye: fourteen pages better, seven the same, none worse.** Markup
moved on nineteen pages. On all 21 the stylesheet lost the disputed
flag's ground and underline.

#### 1. The targeted pages

| page | part | verdict | what the sheet shows |
|---|---|---|---|
| timetable | B1 | **better** | rooms under subjects; the four double lessons over two slots; Registration and Lunch across the days; day heads at the page's size |
| paper | B2, B3, C2 | **better** | the equation centred and apart, `(1)` flush right on it; the affiliations' marks raised; section heads regular small caps |
| report | B2, C2 | **better** | the title regular, as printed; `side.¹`, `basin.²`, `2027.³` raised |
| invoice_0001 | B4 | **better** | `Created:`, `Due:` keep their colons |
| invoice_0002 | B4, C2 | **better** | `NO: … \| Date:` keeps its colons and bar; the panel titles regular |
| certificate | C1, C2, C3, C5 | **better** | the seal a gold disc in its ring; the stars gold on one line; `S. Okonkwo` in script at one size; the title regular |
| sample_css | C1, C3 | **better** | the `CSS` badge a blue chip beside `Sample HTML` |
| newsletter | C2, C4, D2 | **better** | the `T` a drop cap four lines deep and the first line in its paragraph; masthead, footer and `RIVERSIDE` regular; `Councillor` |
| statement | C2, D2 | **better** | 1,144.30, 216.08, `Lindow`, `Quillon` twice, as printed; the tiles' labels regular |
| nonlatin | B4, C2 | **better** | the subtotals regular; `Ημερομηνία:` and `Λήξη:` keep their colons |
| ticket | C1 | **better** | `OSL` at display size |
| menu | D2 | same | only `chorvil`'s title moved: it is disputed, drawn as read |

#### 2. The other pages

| page | verdict | what |
|---|---|---|
| form | **better** | `fernpost`, as printed (D2) |
| cv | **better** | the Software list's four entries alike in weight (C2) |
| letter | **better**, slightly | the addressee's name regular, as printed (C2) |
| catalogue | same | the footer's `Orders:` keeps its colon; one line 1px lower |
| darkdeck | same | the tiles' labels a touch lighter |
| pricing | same | one heading's weight, nothing visible |
| receipt, sample_semantic | same | markup unchanged |
| sample_table | same | a bold-by-default heading's explicit 700 dropped |

#### 3. Scores, recorded

| | all 21 | the fifteen | the six new |
|---|---|---|---|
| vocabulary recall | 0.992 → 0.994 | 0.991 → 0.993 | 0.997 → 0.999 |
| precision | 0.990 → 0.992 | 0.988 → 0.989 | 0.996 → 0.998 |
| join recall | 0.963 → 0.967 | 0.965 → 0.969 | 0.958 → 0.964 |
| tau | 0.982 → 0.984 | 0.990 → 0.990 | 0.964 → 0.972 |
| beside agreement | 0.874 → 0.870 | 0.894 → 0.901 | 0.825 → 0.795 |
| height ratio | 1.050 → 1.043 | 1.027 → 1.022 | 1.107 → 1.096 |
| alignment agreement | 0.804 → 0.810 | 0.841 → 0.842 | 0.712 → 0.731 |
| scale error | 0.223 → 0.223 | 0.168 → 0.168 | 0.359 → 0.359 |

- **`vanished`: 24 → 15 words, none new.** Back: the statement's `144`,
  `216`, `lindow`, `quillon`; form's `fernpost`; the newsletter's
  `councillor`; paper's `achterberg`, `delta`, `department`.
- **The ratchet, reported — three legs below the baseline:**
  - **certificate's beside, 1.000 → 0.556:** the scorer matched 14 of its
    blocks where it matched 11, and measures 9 pairs where it measured 2.
    The signature blocks now count, and they are flush left under their
    rules where the page centres them (§5).
  - **catalogue's beside, 0.901 → 0.851:** the only markup that moved is
    two headings' weights, a 1px margin and the footer's `Orders:`. By
    eye nothing changes what sits beside what.
  - **report's precision, 0.966 → 0.962:** two more `invented` digits,
    `1` and `2` — the raised footnote markers the page prints and the
    render now draws.

#### 4. Grouping — the jitter check and the twins

| | at the spec's start | `S14-sweep`'s commit |
|---|---|---|
| jitter, Zones kept | 635 / 848 (0.749) | **751 / 848 (0.886)** |
| pages regrouping | 16 | 14 |
| twins, Zones kept | 820 / 1080 (0.759) | **914 / 1080 (0.846)** |

Both are A1's numbers. No later step touches the detector. The target,
≥ 0.95, is not met.

#### 5. Faults left against the originals, by stage

Read off all 21 sheets on 2026-10-23.

**Readings:**

| page | the page prints | the render prints | state |
|---|---|---|---|
| nonlatin | its own company in the footer | `Αγγελίδης Μπραγκαντής Α.Ε.` | agreed, 18 apart (D3) |
| nonlatin | `Έλεγχος`, `aigaio`, `επίβλεψης`, `επέχει` | `Έλευθος`, `aigaiio`, `επιβλέψεις`, `επιτεύγει` | two disputed; `επίβλεψης` confirmed wrongly by the third reading; `επέχει` not near |
| form | `Castleton` twice, in the footer | `Castletown` | disputed: the third reading was the page's, and tesseract's `Incomptete` kept it from a majority |
| cv | `fernpost` | `fempost` | disputed (third `tempost`) |
| menu | `chervil`, `béarnaise` | `chorvil`, `bearnaise` | `chorvil` disputed |
| invoice_0002 | `adipisicing`, `blanditiis`, `MO123…` (a letter O) | `adipiscing`, `blanditiiis`, `M0123…` (a zero) | the paragraph disputed; the bank codes not near |
| receipt | the AID | one zero short | not near |

**Structure the render draws differently:**

| page | fault |
|---|---|
| report | the table at full width, where the page sets it narrower |
| certificate | the names and roles flush left under their rules, where the page centres them |
| letter | the sign-off's lines spread apart; `office@hal denpryce.example` split |
| darkdeck | the P95 tile split, `184` apart from `ms` |
| sample_semantic | the tag links above `Tags:`, their commas gone |
| cv | `Revit` and `Python` indented and smaller than the two above them |

**Looks:**

| page | fault |
|---|---|
| menu | the title bold where the page sets it regular; `PUDDINGS` a ruled heading; the leaders stop short of the prices |
| newsletter | the headline bold where the page sets it regular |
| receipt | bold where the page is regular |
| paper | `Brekke` and `64` bold where printed regular; `Abstract—` and the e-mail lose their italic and monospace |
| certificate | the course title regular where printed bold; the roles plain caps where the page letter-spaces small caps; `★` for `✦` |
| cv | the first job title regular where printed bold, its company line not italic |
| report | `1.1.1` bold where printed italic |
| invoice_0002 | `With Credit` at the title's size, where the page sets it smaller and lighter |
| catalogue | three prices small and regular; OK-330's chip lost; CP-402's chip missing |
| timetable | tints by row, where the page tints by subject; the legend without swatches |
| pricing | the buttons drawn as text; ticks and crosses as bullets; the prices left-set where the page centres them |
| ticket | no plane, no barcode; the stub's strip drawn empty; the values not bold |
| letter | the wordmark sans where the page sets a serif |
| sample_css | the cards' padding tighter; `<style>` and `<head>` without their code ground |

#### 6. Directions, ranked

| # | direction | why | evidence |
|---|---|---|---|
| 1 | **Shapes and weights the page draws** — buttons, chips, swatches, a bold-or-regular measure that holds at display sizes | §5's looks table is the longest list on the sheets, and spread over 14 pages | pricing's buttons, the catalogue's chips, the timetable's legend; C2's four bold entries |
| 2 | **Readings settled word by word** | Two of the eight disputed Cells have a majority word by word: form's footer (`Castleton` from tesseract and the third, `Incomplete` from the model and the third), and nonlatin's `Α' Πειραιά` once a Latin `A` folds to a Greek `Α`. The other six read three ways | the sweep's 8 disputed Cells |
| 3 | **Grouping under a changed picture** | 0.886 against a 0.95 target. It still blocks any change to `rectify`, and the ticket regroups on every twin | §4; A1's four remaining causes |
| 4 | **Widths and alignment the page sets** | a narrower table, names centred under rules, a sign-off's spacing | §5's structure table |

#### 7. Recommendation

Take `S14-sweep` as the baseline. It draws fourteen pages better and none
worse, its prediction held to the byte, and no word newly vanishes. Its
three ratchet legs below the baseline are each traced in §3: two are the
scorer seeing more of a page now drawn closer to it, and one is a raised
mark the page prints. Freeze it as `tests/frozen/s14-result/` with its
811 answers. **The decision is Alessandro's.**

**Decided 2026-10-23: Alessandro took `S14-sweep` as the baseline.**
It was frozen as `tests/frozen/s14-result/` with its 811 answers, and
proved at `a0d73c9`:
- the answers against the sweep's traces: 0 differ;
- replay: 21 of 21 byte-identical, 0 asked differently;
- rederive: 21 of 21;
- the rederive scored: 0 differing fields.

**The same day he cleared every open item**, §6's four directions
included. Nothing is open; pick up nothing he does not name.

---

## Handover — after the sweep (carried out 2026-10-23)

> Spec 0019 (`docs/specs/0019-steady-checked-structured-styled.md`, issue
> #42) is done, and its sweep `S14-sweep` waits on Alessandro's baseline
> decision. Read `CLAUDE.md`'s READ THIS FIRST, `docs/status.md`, then the
> spec's "Outcome — the sweep".
>
> **If he takes `S14-sweep`**, freeze it as `tests/frozen/s14-result/` the
> way `s13-result/` was frozen. Do it from `debug/runs/S14-sweep`, which
> must not be cleared first:
> - `documents/`;
> - `answers/`, 811 calls, via `tools/replay_run.py debug/runs/S14-sweep
>   --save-answers tests/frozen/s14-result`;
> - `scores.json`, scored against `s13-result/scores.json`;
> - `dth_env.txt`;
> - a README stating its provenance and its three ratchet legs below
>   `s13-result/` (the spec's §3).
>
> Then prove it:
> - `tools/replay_run.py tests/frozen/s14-result` — 21 of 21
>   byte-identical, 0 asked differently;
> - `tools/rederive.py` over it — 21 of 21;
> - scored, 0 differing fields.
>
> Point `CLAUDE.md`, `docs/status.md` and the report command's `--previous`
> at it, and close issue #42.
>
> **If he does not,** `s13-result/` stays the baseline. Record his reason in
> the spec.
>
> Nothing else is open. The spec's directions are ranked, not queued: pick
> up none unless he names it.

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
