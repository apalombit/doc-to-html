# The strip as the page draws it, photographed pages, and the straightening step

**Status: planned 2026-10-19, issue #41; not started.** The baseline is
`tests/frozen/s12-result/`; today's code draws it with spec 0017's two render
steps. One sweep, at the very end.

## Alessandro's decisions, 2026-10-18 and 2026-10-19

1. **Spec 0017 is kept** (#40 closed): "useful per se but minor improvements".
2. **The ticket's banner is still wrong:** "the top title banner had and has
   incorrect two line layout not consistent to original (like The / The)".
   §1 traces it.
3. **Directions 3 and 4, as proposed, banner first.** Part A is the banner,
   from both. Part B is the rest of 3: photographed pages laid out like shot
   ones.
4. **The straightening step:** "explore what this step does and how to
   improve it considering its implications", added after 3 and 4. §2 is the
   exploration and Part C the improvements.
5. **Rotate the render, not the original:** "have the render rotated ... so
   that any document preprocessing steps ... are conceptually applied so
   that we can compare 1v1 to original document". The review and the scorer
   compare in the photograph's frame (§3, Part 0). They come first, so
   Parts A–C are judged with them.
6. **"Sweep only at the end of all."** One sweep, `S13-sweep`, after Part C.
   Every step before it is proved offline and on a targeted run.

## Order

**Part 0** the tools → **Part A** the banner → **Part B** photographed pages
→ **Part C** the straightening step → **the sweep**.

---

## How to work

- **Judge by eye**, the ticket first, every step, against the step before:
  `tools/visual_review.py <run> --previous <run> --documents <moved>`. Each
  page gets better / same / worse and one sentence naming the element.
- **List every page whose markup moves, and open each one.** Spec 0017's
  first rule looked local and fired on five other pages, three of them for
  the worse.
- **Each step is its own commit, with its tests.** Every new IR-writing step
  goes into `tools/rederive.py`.
- **A step that moves a crop is proved on a targeted run** of the pages it
  moves (`FIXTURE=<pages> tools/iterate.sh <label>`) before the next step.
  The replay serves answers by order and cannot say which moved crop is
  answered differently (spec 0016 §5).
- **Scores are recorded, never gating, never argued from.** `vanished` is
  read as a pointer to a page to open.
- **Stop and ask** if a page gets worse, if a word the baseline shows
  vanishes, or at B0's checkpoint. Otherwise carry on to the sweep.

| loop | what it measures | cost |
|---|---|---|
| `tools/rederive.py tests/frozen/s12-result` | render and every step downstream of the model | about a minute |
| `tools/replay_run.py tests/frozen/s12-result` | wire and passes on the recorded answers; ASKED DIFFERENTLY names the calls that moved | about a minute |
| `tools/layout_front.py` | the CV-only layout front: Zones and structure | seconds |
| `tools/twins.py --check` (B0) | rectify and the layout front on photographed copies, against the truth | about a minute |
| targeted run | the model on the pages a step moves | minutes a page |

---

## §1 The banner: why it comes back as two rows

Traced on `s12-result/ticket_0020`, 2026-10-18 and 2026-10-19.

| # | stage | what happens | measured |
|---|---|---|---|
| 1 | `rectify` → `equalise` | Divides lightness by an estimate of the light: a 15px closing, then a blur. The teal strip is wider than 15px, so it is taken for a shadow and lifted to near white. A dark fringe is left round its letters and along its lower edge | 8.16% of the page goes from ink to not ink (§2a) |
| 2 | `content_ink` | The fringe is darker than `INK_LEVEL` and is not a rule, so it is content | rows 39–43 at the strip's foot |
| 3 | `_cover_the_page` | Ink that no box covers becomes a Zone: z5 [0.209–0.733, 0.108–0.141], 8px tall | trace: `recovered 1` |
| 4 | classify, prose | The model reads `The`, twice, off an empty crop | IR z5 |
| 5 | render | `_filled` draws z5 as the strip's second row | the strip 80px tall against the source's 41px |
| 6 | style | z5 enters the body measure, giving 8.0px where it is 9.0. `TRD` then measures over `LARGEST_EM` and its size is refused | spec 0016 §1 |

**The fringe comes from `equalise`, not from the rotation.** The unrotated
ticket, shot as a plain screenshot, recovers a halo Zone too.

**Two of the banner's faults are not caused by the picture.** Each was
checked with two classify calls:
- `NORDLYS AIR` is `figure` on the equalised crop and on the plain one. That
  is the model's reading of a letter-spaced wordmark.
- The stub's strip, cropped alone, is `prose` either way. Its text goes
  unread because it lies inside the stub's one pairs Zone. A2 cuts that Zone
  at the strip's edge.

---

## §2 The straightening step, `preprocess.rectify`

| step | what it does | measured | consequence |
|---|---|---|---|
| 1 outline | `find_page_quad`: Canny on a copy of at most 800px, then the largest convex 4-gon covering 25–97% of the frame. `surround_of` refuses one with the same colour on both sides. `sheet_outline` re-reads the outline off the sheet's colour where the sheet runs past an edge | **Ticket:** corners 0.8–2.9px from the truth; its edges slope −1.34° to −1.36° where the pass slopes −1.50°. **Twins:** 3.1–5.4px on 17 pages, and **308px on cv**, whose dark sidebar is taken for desk | Up to 0.17° of tilt is left (step 4). A wrong outline cuts content |
| 2 warp | `warp_to_quad`: `warpPerspective`, linear interpolation, sized from the outline | **Twins:** warped to the true corners, the page differs from the shot page by a half to two thirds of today's MAD. Cubic takes about 8% more off (§2b) | Every edge is resampled |
| 3 polarity | `ground_is_dark` turns a light-on-dark page over | darkdeck | — |
| 4 deskew | projection profile at 800px, 0.5° steps over ±15°; rotates only for 0.25° or more | **Twins:** −0.17° to +0.14° is left after the warp, under both the threshold and the step. darkdeck, with no outline, is straightened by it (−1.50°) | A residual under 0.25° is never corrected |
| 5 equalise | lightness ÷ illumination (a 15px closing, blurred), then CLAHE (clip 2.0, 8×8 tiles) | Every corpus page's paper is flat: p5–p95 within 0–11 levels on all 21. Equalise still lifts fills and invents ink (§2a) | What decides the Zones and what the model reads is not the page |
| 6 resize | at most 3508px on the long edge; never enlarges | no corpus page is that large | — |

**Who reads which picture.**
- **`Rectified.image`, equalised:** the detector, `_cover_the_page`,
  `content_ink`, the shortfall and the model's crops.
- **`Rectified.plain`:** colour, style, `locate` and `looks`.

### §2a What `equalise` does to the corpus

Measured 2026-10-19 over each page's `rectify`. Ink is grey under
`INK_LEVEL` (200).
- **Lifted:** the share of the page that is ink in `plain` and not after
  equalise.
- **Invented:** the share that is ink only after it.

| page | lifted | invented | mean ΔL | what it is |
|---|---|---|---|---|
| `cv_0013` | **16.44%** | 0.13% | 41.0 | the navy sidebar blown out in pale blotches, dark halos round every item |
| `ticket_0020` | **8.16%** | 0.60% | 13.5 | both teal strips, a fringe round the letters and along the foot |
| `timetable_0019` | 1.15% | 0.11% | 10.9 | its filled cells |
| `paper_0018` | 0.71% | 0.24% | 1.3 | the figure's bars |
| `darkdeck_0009` | 0.26% | 0.00% | 19.2 | its tiles, after the page is turned over |
| `certificate_0021` | 0.18% | 0.00% | 6.1 | the seal |
| `catalogue_0015` | 0.00% | **1.23%** | 6.5 | card borders thickened, card shadows made ink, the hatching sharpened |
| `receipt_0010` | 0.00% | 0.85% | 1.4 | the paper's edge on its desk |
| the other 13 | ≤ 0.09% | 0.03–0.27% | 0.2–4.4 | antialiased type a shade darker |

The rest of the pipeline is tuned to these pictures:
- the cover step, the snap and the printed-line counts;
- `INK_LEVEL`'s own rationale: "available here only because the Rectified
  Image has already been intensity-equalised";
- `_uncovered_mask`, whose docstring records cv's halos.

**This is why C4 comes after A1.** Until a fill counts as ground, a fill
left as printed would be solid ink to every one of those measures.

### §2b The twins, as far as they have been measured

Measured 2026-10-19 with a scratch script. It is not committed; B0 builds
the tool from this description.
- **A twin:** a corpus picture turned 1.5° (PIL `rotate`, bicubic,
  `expand`) and pasted on a slate desk, (60, 65, 72), with a 50px margin.
  Its true corners follow from the turn.
- **The residual:** the rotation that `cv2.findTransformECC`
  (`MOTION_EUCLIDEAN`) needs to carry the straightened page onto the shot
  one.
- **MAD:** the mean grey difference between the two once aligned.

| page | found corners, linear | true corners, linear | true corners, cubic |
|---|---|---|---|
| `invoice_0001` | −0.101° / 4.49 | +0.000° / 2.25 | 0.000° / 2.05 |
| `newsletter_0008` | −0.090° / 16.34 | 0.000° / 9.94 | 0.000° / 9.26 |
| `letter_0016` | +0.144° / 10.55 | +0.006° / 6.06 | +0.006° / 5.56 |
| `certificate_0021` | −0.172° / 10.02 | 0.000° / 4.75 | +0.001° / 4.25 |
| `pricing_0017` | −0.141° / 6.81 | +0.002° / 3.57 | +0.002° / 3.33 |
| 12 others | −0.11° to +0.09° | within ±0.007° | within ±0.006° |

Four pages are not in that table:
- **cv:** 308px off, its sidebar cut away;
- **darkdeck:** no outline (a dark page on a dark desk), so deskew corrects
  it;
- **ticket and receipt:** already photographs, on desks of their own.

**The layout front on the same twins**, 2026-10-18, CV only, IoU ≥ 0.5
against the Zones as shot:
- **7 of 20 comparable pages** keep fewer than three quarters of their
  Zones: form 2/8 (its six sections become one Zone), cv 6/31, receipt 1/5,
  menu 1/4, timetable 1/3, sample_css 2/4, sample_semantic 6/9.
- **3 lose their structure:** cv's columns, catalogue's grid and nonlatin's.

**The twins' limits.** A flat turn on a uniform desk: no perspective, no
shading, no lens. B0 adds shading and perspective, because C4 cannot be
measured without uneven light.

---

## §3 A tilted photograph confounds the comparison

Measured 2026-10-19. The corpus's one tilted source is `ticket_0020`, with
`transform:rotate(-1.5deg)`; the other matches for `transform` are
`text-transform`.

- **The scorer.** `project()` reads boxes with `getClientRects`. On a rotated
  element that returns upright boxes round tilted lines, so `TRD` stands
  15px above `OSL`. The same output, `S13-2-proto`'s ticket, scores
  **beside 0.393** against the tilted source and **0.588** against the same
  HTML untilted. Column error goes 0.158 → 0.189; tau stays 0.947. About a
  third of the ticket's measured `beside` disagreement is the tilt.
- **The review.** The sheets set a tilted photograph beside a straight
  render, as much as about 20px apart across the card. Nothing can be laid
  over anything, and offsets of that size cannot be seen by eye.
- **The per-page index.** `tools/inspect_run.py`'s `01_layout_input` is the
  source picture, captioned "the page as the layout pass saw it". It is not
  that, for a photographed page or for any equalised one. `02_model_boxes`
  draws boxes taken in the straightened frame on that picture, so on the
  ticket they stand on the desk.

**Rotate the render, not the original.**
- **The reference stays untouched.** Straightening the original would apply
  the pipeline's own `rectify` to it, and `rectify`'s errors would vanish
  from the comparison. Part C changes `rectify`.
- **The render goes through the outline `rectify` used.** A wrong outline
  then shows as misregistration instead of being hidden.

**Prototype, 2026-10-19.** The ticket's render was warped into the
photograph's frame by that outline, onto its surround. An overlay shows the
source's ink in cyan and the render's in red. It shows at a glance:
- the strip's extra row, as a red band that pushes the body down about 25px;
- the grid's rows landing nearly on the source's;
- the large `OSL` and `TRD`, the barcode and the plane, in cyan only.

---

## Part 0 — compare in the photograph's frame (§3)

Review and scoring tools only. No model call, and no change to a conversion.

**0a. The review re-photographs the render.**
- **What.** For a page whose picture is warped (`Rectified.warped`),
  `doc_to_html.review` adds a second row to its sheet: this run's render
  re-photographed, and the overlay. With `--previous`, the previous render
  gets the same pair.
- **The mapping.** The render's paper rectangle is where `.doc` is drawn:
  `Source.paper` × the picture's size (spec 0012, G5). It is mapped onto the
  outline by the homography of their four corners
  (`cv2.getPerspectiveTransform`). It is drawn with `warpPerspective`, cubic
  interpolation, onto `Source.surround`. A render taller than its paper
  overhangs, and that overhang is information.
- **One outline.** `rectify` and the review take the outline from one
  function, factored out of `rectify` as it stands. No pixel changes, and
  `RECTIFIER_VERSION` does not move.
- **The overlay.** Source grey in the red channel, render grey in green and
  blue. Cyan is source only, red is render only, dark is both.
- **Unwarped pages.** Their sheets stay byte-identical to today's.

**0b. The scorer measures the source in its paper's frame.**
- **What.** On the source side only, `project()` undoes any rotation, skew
  or perspective the page sets on itself before it measures. An element
  whose computed `transform` has a non-zero off-diagonal, or that sets a
  perspective, gets `none`. A pure translation stays.
- **Why that is exact.** A transform moves no layout, and the corpus's
  ground truth is its HTML.
- **Expected.** Only the ticket's scores move (beside about 0.39 → 0.59 on
  `S13-2-proto`'s render). No other source sets such a transform.
- **The baseline's scores move with it.** Re-score `s12-result/` with the
  new scorer into a file of its own, committed beside `scores.json` with a
  README line. The sweep's `--previous` is that file, so its deltas measure
  the conversion and not the scorer.

**0c. The per-page index shows what the layout pass saw.**
- `01_layout_input` becomes `Rectified.image`, warped and equalised, as the
  detector is given it.
- `02_model_boxes` is drawn on it, so each box stands where it was found.
- The source picture stays, as a panel of its own.

**Proved by:**
- tests for each of 0a, 0b and 0c;
- every unwarped page's sheet byte-identical;
- by eye, the ticket's sheet: the overlay registers the card's edges on the
  photograph's.

---

## Part A — the banner (directions 3 and 4)

**A1. Ink is measured against its local ground.**
- **The rule.** A solid fill the page draws, as `furniture` finds it on the
  plain picture, is ground. Its edge, as far as it is blended, is not ink.
  Type on the fill is ink by its contrast with the fill.
- **Applies to:** `content_ink` and the measures built on it: the cover
  step, the snap and the printed-line counts.
- **Expected:**
  - on the ticket, z5 is never recovered and the strip is one row;
  - the body measure is 9.0px, and `TRD` is no longer refused;
  - cv's sidebar halos stop being ink.
- **Handle in this step the knock-on that killed spec 0016's 4a.** Without
  z5 the body measure moves, `locate`'s re-reads move, and the gate note
  lost words. Prove A1 on a targeted run before A2: the ticket, plus every
  page whose Zones or body measure it moves on the layout front. `vanished`
  must gain no word.

**A2. A drawn strip is one container at the layout stage.**
- **The rule.** After the detector, the pieces inside one solid fill become
  one Zone: `NORDLYS AIR` and `BOARDING PASS`. A Zone that crosses a fill's
  edge is cut there, which separates the stub's strip from its body.
- **Expected:**
  - one header Zone per strip;
  - the stub strip's text read in its own crop;
  - no second row.
- **Not expected:** `NORDLYS AIR` read as text (§1).
- It moves crops, so it is proved on a targeted run.

**A2 was measured and dropped — Alessandro, 2026-10-19.** Built as written:
`furniture.strips` found each piece of a solid fill, by its own colour, that
carries one printed line; `structure.one_per_strip`, after the snap, cut a
Zone at a strip's top and bottom edges and merged the Zones whose middles lay
in one strip.
- **First, it fired beyond the ticket.** It cut `form_0007`'s section bars
  and `nonlatin_0014`'s panel heads from the content under them, one cut
  leaving a 1px Zone. Restricted to fills that two Zones at least stand on, it
  moved the ticket alone on the layout front.
- **Targeted run `S13-A2-run`: worse.** On the merged crop, the caption pass
  read `NORDLYS AIR` as the Zone's Title and `BOARDING PASS` as a heading
  block, and the two were drawn stacked: the strip was two rows tall again.
  The stub's strip did read `NORDLYS AIR`. The stub's body was read as a table
  titled `PASSENGER`, and the perforation's two panes were lost. With the stub
  cut, the two strips sit in one row and the two bodies in another, so
  `_columns` finds no independent lanes.
- **The cut alone, `S13-A2c-run`: mixed.** The strip stayed one row and the
  stub's `NORDLYS AIR` was drawn. The panes were still lost, the gate note
  rose under the fields, and `BOARDING PASS` stood mid-strip, not flush right.
- **A1 alone already meets the banner's aim:** one strip row, no `The`. The
  stub's `NORDLYS AIR` stays unread, and since the main strip prints the same
  word, nothing vanishes. The code was removed.

---

## Part B — photographed pages laid out like shot ones (direction 3)

**B0. The twins, committed.** `tools/twins.py` builds each twin's picture and
its truth. The pictures go under `debug/`; the tool and its fixed parameters
are committed. The set, for each corpus page:
- turned 0.5°, 1.5° and 3° on a desk;
- the 1.5° turn with a soft shading gradient and a shadow;
- one with a mild perspective.

`--check` is model-free and reports two things:
- **`rectify` against the truth:** corner error, residual tilt, MAD, and the
  ink outside the outline;
- **the layout front against the page as shot:** Zones kept at IoU ≥ 0.5,
  and the structure regions.

It is proved byte-identical run to run. §2b's numbers should be its first
rows.

**Checkpoint: stop and ask.** Write B0's findings into this spec as B1's
list. For each fault give the stage it starts in and the number of twins
that show it. Then ask Alessandro before building B1. **Only faults that
recur across twins qualify**, each repaired by a general rule. Ask him the
same time whether twins join the corpus: each is scored against its own
HTML, and six held-out twins would add about 40 minutes to every sweep. Not
done unless he says so.

### B0's findings — B1's list, 2026-10-19

**What B0 built.** `tools/twins.py` draws five twins of every corpus page,
105 in all, under `debug/twins/`. Each twin is drawn by one homography with
cubic interpolation, so its truth is exact (`tests/test_twins.py`). `--check`
runs the layout front 231 times and takes about 13 minutes, not one. It
writes `check.json` and `check.md`, and was proved byte-identical run to
run. Two things were added to the description above, each because the first
pass misled:
- **Every Zone is carried back into the shot picture's frame** before it is
  compared, through `rectify`'s own warp and turn and the twin's truth.
  Compared in normalised coordinates, a page `rectify` leaves on its desk
  lost every Zone for its coordinates alone: darkdeck read 4–7 of 17 that
  way and receipt 1 of 5, against 12–13 and 4 carried back. §2b's receipt
  figure was this artefact.
- **A merge is counted apart from a loss**, and the layout front is also run
  on the twin **straightened through its true corners**. What is still lost
  there is lost to resampling, not to the outline.

**Against §2b.** Corners 3.0–5.7px out on 85 twins (§2b: 3.1–5.4). Residual
tilt −0.207° to +0.096°. cv is 307px out, and darkdeck has no outline; both
agree with §2b. The MADs are not §2b's: §2b turned its twins with PIL, these
use one homography. Their ratios hold:
- through the found corners, 2.1–5.4× the MAD through the true ones;
- cubic takes 12–35% off, against §2b's 8%.

| # | fault | stage it starts in | twins | whose |
|---|---|---|---|---|
| 1 | **The outline is 3.0–5.7px out** at every corner, read on the 800px copy; up to 0.21° of tilt left; the MAD 2.1–5.4× the true corners' | `rectify` 1, `find_page_quad` | 85 of 85 with an outline | C2 |
| 2 | **`warp_to_quad` flattens the page one pixel short**: its target puts the corner pixels at 0 and w − 1, w being the distance between their centres, so even true corners give a page W − 1 wide | `rectify` 2 | every warped page | C2 |
| 3 | **cv's outline cuts its sidebar**: 307px in, 87% of the page's ink outside it; Zones 10 of 31 kept (17 lost), columns → single. Through the true corners 23–25 of 31 | `rectify` 1, the navy sidebar taken for desk | 5 of 5 | C1 |
| 4 | **darkdeck has no outline**: a dark page on a dark desk, so the page is laid out on its desk. deskew finds the exact turn on all five. Grid and columns → single; Zones 12–13 of 17, 4–5 merged | `rectify` 1 | 5 of 5 | C1 |
| 5 | **The detector regroups a page that is only resampled.** Through the true corners as well as the found ones: form's five sections become one Zone (kept 2–8 of 8), sample_css 2 of 4, sample_semantic 5 of 9 (2 lost), statement 4 of 5, report 10–12 of 14, menu 1–4 of 4, invoice_0001 4–6 of 6, certificate 3–8 of 8, ticket 0–4 of 5. The cover step, the snap and the cut move none of it: the detector's own count already differs | the detector, on `Rectified.image` | 16 of 21 pages, on 1 to 5 of their twins | B1 |
| 6 | **Card grids lost once resampled**: catalogue's 3×3 → single, columns or 2 lanes; nonlatin's 2 → single; pricing's 3 once; newsletter's columns once | `style.rectangles`, `_bordered` — not `SAME_SIZE`, see B1 | catalogue 5, nonlatin 3, pricing 1, newsletter 1 | B1 |
| 7 | **pricing's feature lines read inside their cards**: 4 of 21 kept, the other 17 inside the card's one Zone, no line lost. A coarser grain, arguably the page's | the detector | 5 of 5 | — |
| 8 | **Uneven light**: the shaded twin's MAD is 12–15 above its unshaded twin's, and menu keeps 1 of 4 on it | `equalise` | 17 of 17 measured | C4 |

**Read by stage.** Faults 1–4 and 8 are already Part C's. B1's own are 5
and 6:
- **6** has a general rule: a tolerance in pixels of resampling, not a share.
- **5** is the largest and has no rule yet. The same page, resampled twice,
  comes back from the detector grouped differently. A rule after the
  detector would have to say what parts a Zone the page draws as several,
  as form's drawn section bars do. That is A2's cut, which was dropped for
  the ticket.

**Alessandro's decision, 2026-10-19:** B1 repairs fault 6 alone. The twins
stay a model-free check and do not join the corpus.

**B1. Repair what B0 found**, stage by stage. Each repair is measured by
B0, then by the layout front on the corpus, then on a targeted run. Already
known, for that list:
- form's sections merged into one Zone;
- cv cut by its outline (C1's);
- catalogue's and nonlatin's grids lost once their card rectangles are
  resampled (`structure.SAME_SIZE`, 0.01).

**B1 — done, 2026-10-19: fault 6.** Its premise was wrong. On the twins
the cards that `style.rectangles` found agree in size to 0.002, well inside
`SAME_SIZE`. What failed was finding them: 6, 2, 4, 0 and 4 of catalogue's
9 cards on its five twins.
- **The cause.** Each card's component was there at its size, and
  `_bordered` refused it. It read each edge on the component's outermost
  line, and resampling spreads a 1px rule over two lines, the outer one the
  blur's fringe: the first card's bottom and left edges were inked on 75% and
  66% of their length, under `BORDER_RUN`.
- **The repair.** `EDGE_DEPTH` 2: each point of an edge is the more inked of
  its outer two lines. One knock-on, guarded in the same step: catalogue's
  page-wide rule, thickened by resampling past `MIN_RECT_SHARE`, became a
  rectangle that was all edge. A component that `content_ink`'s own
  separator test calls a rule is never a box.
- **Measured.**
  - Every corpus page as shot keeps exactly its rectangles, and the layout
    front is byte-identical on all 21, so no crop moves.
  - On the twins, catalogue's 3×3 grid, nonlatin's 2 lanes and pricing's 3
    are now found on every unshaded twin, and catalogue keeps 13 of 13 Zones.
  - The four grids still lost are all on the shaded twin. One measured
    ground colour cannot hold a page under a light gradient: fault 8, on
    the plain picture, which C4's `equalise` does not reach.

---

## Part C — the straightening step

Each step is measured on the twins against the truth, then by the corpus's
layout front. Each bumps `RECTIFIER_VERSION`, moves every crop of every page
it touches, and is proved on a targeted run of those pages.

**C1. An outline that never cuts content and never takes a shadow for
paper.**
- **A shadow is not paper.** A shadow is the surround made darker on every
  channel; a sheet is not. The ticket's bottom-left corner sits in its
  shadow and is 2.9px out, its worst. The shadow is the likely cause; show
  it.
- **An outline must hold the content.** Where ink that is not desk lies
  outside the outline, grow the outline to that ink or refuse it. This is
  cv's twin.
- **Target:** every twin's corners within 1px, and no content outside the
  outline.

**C1 — done, 2026-10-19.**
- **The rule.** Paper is told from desk against the desk read at the
  picture's own edge (`DESK_BAND`).
  - **Desk** is a pixel within `DESK_SPREAD` (12) of the desk, or the desk
    darkened alike on every channel, to `SHADOW_TINT`: a shadow.
  - **An outline must hold the page.** One that leaves more than `OUTSIDE`
    (0.2%) of the picture as paper outside it is grown to the paper read that
    way (`sheet_outline`, `loose`), or refused.
  - The strict reading comes first. The loose reading is used only where the
    strict outline leaves paper outside.
- **cv's twins.** The navy sidebar stands 24 from the desk, under
  `SHEET_APART`, and is darker on every channel but not alike, so it is
  paper, not a shadow.
  - corners: 307px out → 1.2–1.35px;
  - paper outside the outline: 87% → under 0.06%;
  - Zones kept: 10 of 31 → 21–30;
  - columns kept on all five.
- **No corpus page's outline moves.** The layout front differs only by
  `RECTIFIER_VERSION`, now 7.
- **First built loose everywhere: worse.** The ticket's colour outline was
  read loose too, and its top-right corner moved 3px. On the targeted run
  `S13-C1-run` the detector then split the main pane into five Zones: `OSL`
  a figure, the plane a figure, the field grid a table. The page was drawn
  about 1.5× too tall, with `OSL` out of the text. That is fault 5. Alessandro
  chose strict first, loose only where the strict outline leaves paper out.
- **The shadow, shown.**
  - On the ticket, the shadow under the foot is 0.64–0.66 of the desk on
    each channel. At 21–25 from the surround it was always under
    `SHEET_APART` and never taken for paper.
  - The ticket's worst corner is 1.89px from its true corners, computed from
    its HTML. That is the 800px colour fit: at x = 800 its top side sits at
    35.0 where the edge is at 36.8. It is C2's to repair.
  - The receipt's outline took its soft shadow ring, 2px a side, for paper.
- **Not met here:** 85 twins' corners are still 3.0–5.7px out (C2's).
  darkdeck still has no outline. Deskew finds its exact turn on all five
  twins, but it is laid out on its desk: deskew is its straightener, as the
  spec has it.

**C2. Corners at full resolution.**
- **The change.** Refine each side at full resolution, to sub-pixel, along
  its normal. Today the outline is read on the 800px copy and scaled up.
- **The bound, measured:** with true corners the residual is 0.000° and the
  MAD falls to between a half and two thirds of today's (§2b).
- **Deskew stays.** It is the only straightener for a page with no outline
  (darkdeck). On a page with an outline, it must not rotate a page C2 left
  level.

**C3. Cubic interpolation in the warp**, as deskew already uses. Measured at
true corners: MAD about 8% lower on every page.

**C4. Equalise only uneven light, and never a fill.**
- **The division needs a cause.** Every corpus page's paper is flat (§2a).
  Divide by the illumination only where the paper's own level is measured to
  vary across the page. B0's shaded twin sets how much variation counts.
- **A fill is not the light.** Estimate the illumination from the paper
  alone, so a fill is never taken for a shadow.
- **CLAHE is measured on its own.** Does it invent the catalogue's ink?
- **It needs A1:** a fill left as printed is ground only once A1 says so.
- **Expected:**
  - cv's sidebar and the ticket's strips reach the detector and the model as
    printed;
  - the halos are gone at their source;
  - the catalogue's borders and shadows stop being ink.
- **The widest step in the spec: it changes the picture of every page.**
  Measure it on the layout front and the twins first. Then take a targeted
  run of the pages §2a names (cv, ticket, timetable, catalogue) before the
  sweep.

---

## The sweep

**One sweep, `S13-sweep`, all 21 pages, after C4.**
- **Register the prediction first**, from the replay's ASKED DIFFERENTLY
  list, as specs 0012–0016 did. C4 changes every picture, so expect every
  page to be asked differently.
- **Run it detached**, as `docs/status.md`'s loop says, and do not edit
  `tools/iterate.sh` while it runs.
- **Score it** against Part 0b's re-scored baseline.
- **Build the sheets** with Part 0a's overlays:
  `--previous debug/runs/S12-sweep`.
- **Report in the error-analysis format:** gains, faults by stage,
  directions ranked, recommendation. The ticket first, then each page
  better / same / worse, in one sentence each.
- **The baseline decision is Alessandro's.**

---

## Handover prompt

> Implement and run spec 0018, `docs/specs/0018-strip-twins-rectify.md`
> (issue #41), in this fresh session.
>
> **Read first, in order:** `CLAUDE.md`'s READ THIS FIRST; `docs/status.md`;
> the spec, end to end. The baseline is `tests/frozen/s12-result/`, drawn by
> today's code with spec 0017's render steps. Nothing outside the spec is
> open: do not pick up anything it does not name.
>
> **Order:** Part 0 (0a, 0b, 0c), then A1, A2, B0, B1, C1, C2, C3, C4. Then
> one sweep, `S13-sweep`, over all 21, and nothing in between. Each step is
> its own commit with its tests. Every new step that writes the IR goes into
> `tools/rederive.py`.
>
> **Part 0 first**, so the rest is judged with it. Use the re-photographed
> render and the overlay on every photographed page, and score against the
> re-scored baseline 0b writes.
>
> **Each step:** prove it offline (rederive, replay, layout front, and the
> twins from B0 on). A step that moves a crop also needs a targeted run of
> the pages it moves (`FIXTURE=<pages> tools/iterate.sh <label>`). Judge by
> eye, the ticket first, against the step before. List every page whose
> markup moves, open each one, and give each a sentence: better, same or
> worse. Scores are recorded, never gating; `vanished` is a pointer to a page
> to open.
>
> **A1 is the risky step:** spec 0016's 4a lost words when the halo Zone
> went. Handle the body measure and `locate`'s re-reads inside A1, and prove
> them on a targeted run before A2.
>
> **Stop and ask Alessandro** at B0's checkpoint (B1's list, and whether
> twins join the corpus), if a page gets worse, or if a word the baseline
> shows vanishes. Otherwise carry on.
>
> **The sweep:** register its prediction from the replay's ASKED DIFFERENTLY
> list first, and start it detached. Do not edit `tools/iterate.sh` while it
> runs. Score with `--documents sweep` against 0b's re-scored baseline, and
> build the sheets with `--previous debug/runs/S12-sweep`. Report in the
> error-analysis format, the ticket first. Then rewrite `docs/status.md`,
> add the spec's outcome section, and leave the baseline decision to
> Alessandro.
