# The strip as the page draws it, photographed pages, and the straightening step

**Status: planned 2026-10-19, issue #41; not started.** The baseline is
`tests/frozen/s12-result/`. Today's code draws it with spec 0017's two render
steps.

Alessandro's decisions, 2026-10-18 and 2026-10-19:

1. **Spec 0017 is kept** (#40 closed): "useful per se but minor
   improvements". The ticket is more consistent in layout and format; the
   catalogue is the same.
2. **What is still wrong on the ticket:** "the top title banner had and has
   incorrect two line layout not consistent to original (like The / The)".
   §1 traces it.
3. **Directions 3 and 4, as proposed**, banner first. Part A is the banner,
   from 3 and 4. Part B is the rest of 3: photographed pages laid out like
   shot ones.
4. **"Explore what this step does and how to improve it, considering its
   implications", for the straightening step.** That is `preprocess.rectify`
   (§2), and its improvements come after 3 and 4 as Part C.

---

## How to work

The same as spec 0016's and 0017's, plus two things:

- **By eye**, the ticket first, against the step before.
- **Every page whose markup moves is listed and opened** (spec 0017's lesson:
  a rule that looks local fired on five other pages).
- **Each step is its own commit, with its tests.** Every new IR-writing step
  goes into `tools/rederive.py`.
- **A step that moves a crop needs a targeted run before any sweep.**
  `FIXTURE=<pages> tools/iterate.sh <label>`. The replay serves answers by
  order and cannot say which moved crop is answered differently (spec 0016
  §5).
- **New: the twins** (Part B, step B0). They are the model-free measure for
  Parts B and C, and they carry ground truth: each twin is a corpus page whose
  picture is the one we shot, turned and set on a desk.

---

## §1 The banner: why it comes back as two rows

Traced on `s12-result/ticket_0020` and its trace, 2026-10-18 and 2026-10-19.

| # | stage | what happens | measured |
|---|---|---|---|
| 1 | `rectify` → `equalise` | Equalise divides the lightness by an estimate of the light on the page (a 15px closing, then a blur). The teal strip is wider than 15px, so it is taken for a shadow and lifted to near white. Only a dark fringe is left: round its letters and along its lower edge | Over the ticket, 8.16% of the page goes from ink to not ink (§2a) |
| 2 | `content_ink` | That fringe is darker than `INK_LEVEL` and is not a rule, so it is content ink | rows 39–43 at the strip's foot |
| 3 | `_cover_the_page` | Ink no box covers becomes a Zone: z5 [0.209–0.733, 0.108–0.141], 8px tall | trace `cover_the_page`: `recovered 1` |
| 4 | classify, prose | The model reads an empty crop and answers `The`, twice | IR z5: two paragraphs `The` |
| 5 | render | `_filled` draws z5 as a second row on the strip | the strip 80px tall against the source's 41px, at x 300 |
| 6 | style | z5 enters the page's body measure: 8.0px where it is 9.0, so `TRD` measures over `LARGEST_EM` and its size is refused | spec 0016 §1 |

**The fringe is the strip's own edge as `equalise` leaves it, not the
rotation.** The unrotated ticket shot as a screenshot, with no desk and no
warp, recovers a halo Zone too (`cover_the_page` recovered 1).

**What the banner's other faults are not.** Checked 2026-10-19 with two
classify calls on the same crops:
- `NORDLYS AIR` is called `figure` on the equalised crop and on the plain
  one alike. Its picture is not why it is a logo; that is the model's
  reading of a letter-spaced wordmark (the wordmark question).
- The stub's strip, cropped alone, is `prose` either way. Its text goes
  unread because it lies inside the stub's one pairs Zone, which has no
  place for it. That is A2's case.

---

## §2 The straightening step, `preprocess.rectify`

Six steps, in order:

| step | what it does | measured | what it costs |
|---|---|---|---|
| 1 outline | `find_page_quad`: Canny on a copy of 800px at most, the largest convex 4-gon covering 25–97% of the frame. `surround_of` refuses a 4-gon with the same colour on both sides. Where the sheet's colour runs past an edge (`sheet_beyond` > 0.5), `sheet_outline` takes the outline off the sheet's colour against the desk, its sides fitted on their middle eight tenths | Ticket: corners 0.8–2.9px from the truth, its edges sloping −1.34° to −1.36° where the pass slopes −1.50°. Twins: 3.1–5.4px on 17 pages, and **308px on cv**, whose dark sidebar is taken for desk and cut off | An outline 0.15° off leaves the page tilted (row 3). A wrong outline cuts content |
| 2 warp | `warp_to_quad`: `warpPerspective`, linear interpolation, sized from the outline's edges | Twins: warped to the true corners, the page differs from the shot page by a half to two thirds as much as warped to the found ones. Cubic takes about 8% more off (§2b) | Every edge resampled; antialiased edges spread |
| 3 polarity | `ground_is_dark` turns a light-on-dark page over | darkdeck only | — |
| 4 deskew | projection profile at 800px, 0.5° steps over ±15°, rotates only for 0.25° or more | Twins: after the warp the page is still turned −0.17° to +0.14°, under its threshold and its step. darkdeck, with no outline, is straightened by it (−1.50°) | A residual under 0.25° is never corrected |
| 5 equalise | lightness ÷ illumination (a 15px closing, blurred), then CLAHE (clip 2.0, 8×8 tiles) | **Every page's paper is flat:** p5–p95 within 0–11 levels on all 21. Equalise still lifts fills away from ink and invents ink at strong edges (§2a) | What the detector, the cover step and the model are shown is not the page |
| 6 resize | to 3508px long edge at most, never larger | no corpus page is that large | — |

**Who reads which picture.** `Rectified.image` (equalised) goes to the
detector, `_cover_the_page`, `content_ink`, the shortfall and the model's
crops. `Rectified.plain` (not equalised) goes to colour, style, `locate` and
`looks`. So the equalised picture is what decides the Zones and what the
model reads.

### §2a What `equalise` does to the corpus

Measured 2026-10-19 by `rectify` over each page. Ink is grey under
`INK_LEVEL` (200).
- **lifted:** a share of the page that is ink in the plain picture and not
  ink after equalise;
- **invented:** a share that is ink only after equalise.

| page | lifted | invented | mean ΔL | what it is |
|---|---|---|---|---|
| `cv_0013` | **16.44%** | 0.13% | 41.0 | the navy sidebar blown out to pale blotches, dark halos round every item |
| `ticket_0020` | **8.16%** | 0.60% | 13.5 | both teal strips, a fringe round the letters and along the foot |
| `timetable_0019` | 1.15% | 0.11% | 10.9 | its filled cells |
| `paper_0018` | 0.71% | 0.24% | 1.3 | the figure's bars |
| `darkdeck_0009` | 0.26% | 0.00% | 19.2 | its tiles, after the page is turned over |
| `certificate_0021` | 0.18% | 0.00% | 6.1 | the seal |
| `catalogue_0015` | 0.00% | **1.23%** | 6.5 | card borders thickened, card shadows turned into ink, the hatching sharpened |
| `receipt_0010` | 0.00% | 0.85% | 1.4 | the paper's edge on its desk |
| the other 13 | ≤ 0.09% | 0.03–0.27% | 0.2–4.4 | antialiased type a shade darker |

The rest of the pipeline is tuned to these pictures. The cover step,
snapping, printed-line counts and `INK_LEVEL`'s own rationale ("available
here only because the Rectified Image has already been
intensity-equalised") all depend on them. `_uncovered_mask`'s docstring
already records cv's halos. **This is why C4 comes after A1**: until a fill
counts as ground, a fill left as it is would be solid ink to every one of
those measures.

### §2b The twins, as far as they have been measured

Measured with a scratch script, 2026-10-19; B0 commits it properly. Each
corpus picture is turned 1.5° with bicubic resampling and pasted on a slate
desk, (60, 65, 72), 50px round. Its true corners follow from the turn.

- **The residual** is the rotation `findTransformECC` (Euclidean) needs to
  carry the straightened page onto the shot one.
- **MAD** is the mean grey difference between the two once aligned.

| page | found corners + linear | true corners + linear | true corners + cubic |
|---|---|---|---|
| `invoice_0001` | −0.101° / 4.49 | +0.000° / 2.25 | 0.000° / 2.05 |
| `newsletter_0008` | −0.090° / 16.34 | 0.000° / 9.94 | 0.000° / 9.26 |
| `letter_0016` | +0.144° / 10.55 | +0.006° / 6.06 | +0.006° / 5.56 |
| `certificate_0021` | −0.172° / 10.02 | 0.000° / 4.75 | +0.001° / 4.25 |
| `pricing_0017` | −0.141° / 6.81 | +0.002° / 3.57 | +0.002° / 3.33 |
| 12 others | −0.11° to +0.09° | within ±0.007° | within ±0.006° |

Four pages are not in that table:
- **cv** (308px off: the sidebar is cut away);
- **darkdeck** (no outline, a dark page on a dark desk; deskew corrects it);
- **ticket and receipt**, whose pictures are already photographs with
  desks of their own.

The layout front on the same twins, 2026-10-18 (CV only, IoU ≥ 0.5 against
the Zones as shot):
- **7 of 20 comparable pages** keep fewer than three quarters of their
  Zones: form 2/8, cv 6/31, receipt 1/5, menu 1/4, timetable 1/3,
  sample_css 2/4, sample_semantic 6/9;
- **3 lose their structure:** cv's columns, catalogue's and nonlatin's
  grids.

**The twins' limits.** A flat turn and a uniform desk. There is no
perspective, no shading and no lens. Part B adds shading and a mild
perspective, because C4 cannot be measured without uneven light.

---

## Part A — the banner (directions 3 and 4)

**A1. Ink is measured against its local ground.** A solid fill the page
draws, as `furniture` finds it on the plain picture, is ground. Its edge,
as far as it is blended, is not ink, and type on it is ink by its contrast
with the fill.
- **Applies to:** `content_ink` and the measures built on it — the cover
  step, the snap and the printed-line counts.
- **Expected:**
  - on the ticket, z5 is never recovered and the strip is one row;
  - the body measure is 9.0px, and `TRD` is no longer refused;
  - on cv, the sidebar's halos stop being ink.
- **The knock-on that killed spec 0016's 4a must be handled in this step,
  not after it.** Without z5 the body measure moves, `locate`'s re-reads
  move, and the gate note lost words. Prove it on a targeted run of the
  ticket first. Register what `vanished` must not gain.

**A2. A drawn strip is one container at the layout stage.** After the
detector, the pieces inside one solid fill (`NORDLYS AIR`, `BOARDING PASS`)
become one Zone. A Zone that crosses a fill's edge is cut there: the stub's
strip from its body.
- **Expected:**
  - one header Zone per strip;
  - the stub strip's text read in a crop of its own;
  - no second row.
- **Not expected:** `NORDLYS AIR` read as text. It is still the model's call
  on a wordmark (§1).
- Moves crops, so a targeted run comes first.

**Then one sweep, `S13-sweep`, all 21**, with its prediction registered from
the replay's ASKED DIFFERENTLY list, as specs 0012–0016 did.

---

## Part B — photographed pages laid out like shot ones (direction 3)

**B0. The twins, committed.** `tools/twins.py` builds each twin's picture
and its truth. The set:
- each corpus page turned 0.5°, 1.5° and 3°;
- one with a soft shading gradient and a shadow;
- one with a mild perspective.

`tools/twins.py --check`, model-free, reports two things, and is proved
byte-identical run to run before it is used:
- **rectify against the truth:** corner error, residual tilt, MAD, and how
  much ink lies outside the outline;
- **the layout front against the page as shot:** Zones kept at IoU ≥ 0.5,
  and the structure regions.

**B1. Repair what B0 finds, stage by stage**, each repair measured by B0 and
then by the layout front on the corpus. Known so far:
- form's six sections merged into one Zone;
- cv cut by its outline (C1);
- catalogue's and nonlatin's grids lost when their card rectangles are
  resampled (`structure.SAME_SIZE` 0.01).

The list is B0's to write, not this spec's.

**A question for Alessandro before B ends: twins in the corpus?** A twin is
scored against its own HTML, so it needs no new ground truth. Six held-out
twins would put photographed robustness into every sweep at about 40 more
minutes a sweep. Not done unless he says so.

---

## Part C — the straightening step

Each step is measured on the twins (B0) against the truth, and by the layout
front on the corpus. **Each bumps `RECTIFIER_VERSION`**, moves every crop of
every page it touches, and so is measured offline first and swept once at
the end of Part C.

**C1. An outline that never cuts content and never takes a shadow for
paper.**
- **A shadow is not paper.** It is the surround made darker on every
  channel; a sheet is not. The ticket's bottom-left corner, in its shadow,
  is 2.9px out, its worst; the shadow is the likely cause, to be shown.
- **An outline must hold the content.** Where ink that is not the desk lies
  outside the outline, the outline is wrong: grow it to that ink or refuse
  it. This is cv's twin.
- **Target:** every twin's corners within 1px; no ink outside the outline.

**C2. Corners at full resolution.** Refine each side at full resolution, to
sub-pixel, along its normal. Today the outline is read on the 800px copy
and scaled up.
- **Bound, measured:** with true corners the residual tilt is 0.000° and the
  MAD falls to between a half and two thirds of today's (§2b).
- **Deskew stays.** It is the only straightener for a page with no outline
  (darkdeck). On a page with an outline it is checked against C2: it must
  not rotate a page C2 already left level.

**C3. Cubic interpolation in the warp.** Deskew already uses it. Measured at
true corners: MAD down about 8% on every page.

**C4. Equalise only what is unevenly lit, and never a fill.**
- **The division needs a cause.** Every corpus page's paper is flat (§2a), so
  divide by the illumination only where the paper's own level is measured to
  vary across the page (B0's shaded twin sets how much).
- **A fill is not the light.** Estimate the illumination from the paper
  alone, so a fill is never taken for a shadow.
- **CLAHE** is measured on its own: does it invent the catalogue's ink?
- **Needs A1.** With fills left as fills, they are ground only once A1 says
  so.
- **Expected:**
  - cv's sidebar and the ticket's strips are shown to the detector and the
    model as printed;
  - the halos are gone at their source;
  - the catalogue's borders and shadows stop being ink.
- **The widest step in the spec: it changes the picture of all 21 pages.**
  Measure it first on the layout front and the twins. Then take a targeted
  run of the pages §2a names (cv, ticket, timetable, catalogue) before the
  sweep.

**Then one sweep, `S14-sweep`**, after Part C, or after B and C together if
Alessandro prefers one.

---

## Handover prompt (current)

> Implement spec 0018, `docs/specs/0018-strip-twins-rectify.md` (issue #41),
> in a fresh session. Read `CLAUDE.md`'s READ THIS FIRST, then
> `docs/status.md`, then the spec end to end. The baseline is
> `tests/frozen/s12-result/`, drawn by today's code with spec 0017's render
> steps. Start with Part A, step A1. Prove it on a targeted run of the
> ticket before anything else, because spec 0016's 4a lost words the same
> way. Then A2, then sweep `S13-sweep` and report it in the error-analysis
> format. Stop and ask after the sweep, before Part B. Judge every step by
> eye, the ticket first; list and open every page whose markup moves; stop
> and ask if a page gets worse or a moved crop is answered differently. Do
> not pick up anything the spec does not name.
