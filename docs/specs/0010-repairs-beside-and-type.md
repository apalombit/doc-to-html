# Five repairs, the beside score, and type at the page's size

**Status: under way, issue #33 — opened 2026-10-11.**

Alessandro's decision, taken on 2026-10-11 after the close-up error analysis
of sweep `S4-sweep` (spec 0009's outcome):

1. **Do the five offline repairs** the analysis ranked first.
2. **Then fix how T3 `beside` treats vertical drift**, so that type can be
   drawn at the page's own size without the score calling it a column fault.
3. **Then draw type at the page's size.**
4. **Then one fresh end-to-end sweep**, reported.

Whether `S4-sweep` becomes the floor was left open by spec 0009. This spec
does not decide it: every step is ratcheted against
`tests/frozen/s3-result/`, and the sweep at the end is the candidate.
`menu_0012`'s `béarnaise` (and `chervil`), read without the accent on a crop
spec 0009 moved, is accepted below the floor by that same decision.

**Keep it small.** Each step names its documents and its gate before code.

---

## 1. The evidence (S4-sweep, measured 2026-10-11 in this session)

All fifteen sheets were opened beside their sources
(`debug/runs/S4-sweep/_review/review.md`). Six documents carry a `major`.

| document | what the page shows | stage | evidence |
|---|---|---|---|
| `statement_0006` | Two amounts wrong — 1,144.30 read 1,141.30, 216.08 read 210.08 | Extract (reduced resolution) | 1156px crop over the 1024px budget. Paid out sums to 5,766.36 against 5,772.36; the running balance breaks at exactly those two rows. The column-sum Probe reports only the column that reconciles. |
| `darkdeck_0009` | `OPEN RISKS`, `DECISIONS WANTED` missing; `$2.14` gone; tiles wrap 3 + 1 | Classify (caption veto) → Extract; Wire; Render | the vetoed captions; `_without_title_echo` drops the pair `COST PER MILLION \| $2.14`; four tiles overflow a `.band` |
| `form_0007` | `2. MEMBERSHIP CATEGORY` missing; five tick boxes one bullet, the ticks lost | Classify (caption veto) → Extract | vetoed; the list reading keeps no tick state |
| `nonlatin_0014` | footer names an issuer the page never prints | Extract | a 24px crop of 7px type |
| `newsletter_0008` | opening sentence cut, its first half a heading | Extract | drop cap: `heading ['T', 'he stretch…']` |
| `cv_0013` | sidebar labels the largest type on the page | Style | `heading_sizes` measures dark-ground lines as None or 1.6–1.8× |

**The caption grid veto fired 5 times in the sweep and every one was a real
caption**: `P95 LATENCY`, `OPEN RISKS`, `DECISIONS WANTED` (darkdeck),
`2. MEMBERSHIP CATEGORY` (form), `TABLE 1 — MOVEMENTS AND REVENUE BY BERTH`
(report). Letter-spaced capitals count as many columns as the body. Four of
the five then vanish from the page.

**What layout, segmentation and classification no longer explain.** The
review found 0 major `order` faults (tau ≥ 0.95 on all fifteen) and no
column fault from the detector. Page height (mean 1.435×) does not follow
segmentation — `menu_0012` has 4 Zones at 1.93×, `receipt_0010` 5 at 2.16× —
it follows type: **every page renders its body at 16px** and every Zone
Title at 0.95em, while the sources print body at 11–16px and their titles at
17–31px.

**Why type has not been drawn at the page's size.** `style.py`'s module
docstring records the arm measured on 2026-09-29 with the sources' own CSS
sizes as an oracle: it crossed the ratchet only on T3 `beside`, whose test is
vertical overlap over half the shorter block. Resizing type changes which
neighbours overlap by half while the columns stay put. The same artefact
marks `catalogue_0015` (0.27), `menu_0012` (0.36) and `cv_0013` (0.40) low
today, and each of those pages has its columns right.

**A body size can be read off the pixels.** The width-weighted median glyph
height of a page's lines, times **1.33**, gives the source's CSS body size
within 10% on 12 of 15 documents (measured 2026-10-11 against `project()` of
each source). The three outside: `form_0007` 1.10, `darkdeck_0009` 1.18 —
both estimate *larger* — and `receipt_0010` 1.57, a photograph whose image
pixels are not CSS pixels, where the image is what the render must match.
Measured in each Zone's own polarity: inverted when its ground is dark,
which is what turns `darkdeck_0009` from 5.65px to 11px.

---

## 2. Work plan

Each step is its own commit. Offline steps are measured by **replay over
`S4-sweep`'s own answers** (`tools/replay_run.py debug/runs/S4-sweep`), which
runs today's code — wire, mapper, every pass, render — with no model call.

**Step 0 — the loop is proved first.** Replay `S4-sweep` at the commit this
spec starts on. Gate: 15 of 15 documents byte-identical to `S4-sweep`.

### Step A — two repairs at the wire (replay)

- **A1. A vetoed caption that the reading drops becomes the Title.** The veto
  keeps its job — the Kind is still asked on the whole crop. After
  extraction, if no entry of the Zone prints the vetoed line, the line is the
  Zone's Title. Nothing is invented: the model read it as a caption, and the
  page prints it.
- **A2. The title-echo rule keeps a pair's value.** When only a first pair's
  label repeats the Title, the label goes and the value stays.

| # | clause |
|---|---|
| A-1 | No document ASKED MORE THAN THE RUN |
| A-2 | `darkdeck_0009` prints `OPEN RISKS`, `DECISIONS WANTED` and `$2.14`; its two "read short" findings are gone |
| A-3 | `form_0007` prints `2. MEMBERSHIP CATEGORY`; `report_0011` prints `TABLE 1 — MOVEMENTS AND REVENUE BY BERTH` |
| A-4 | Only those three documents differ from `S4-sweep` |
| A-5 | Ratchet against `s3-result/`: no leg falls that `S4-sweep` held, on any document |

#### Outcome — step 0 and step A, 2026-10-11, gate MET with one recorded exception

**Step 0.** `S4-sweep` replayed at `153b6e9`: **15 of 15 byte-identical**
(`S5-0-replay`, 13 seconds).

**What the pages look like** (`S5-A-replay`, sheets against `S4-sweep`).
`darkdeck_0009`'s sidebar reads `OPEN RISKS` and `DECISIONS WANTED` over
their bullets and its "Unresolved" panel is gone; the cost tile prints
`$2.14`. `form_0007`'s `2. MEMBERSHIP CATEGORY` heads its section on its grey
bar. `report_0011`'s table carries its caption. The tiles still wrap (B1).

| # | clause | result |
|---|---|---|
| A-1 | no ASKED MORE | **holds** |
| A-2 | darkdeck prints the two headings and `$2.14`; no read-short finding | **holds** — vocabulary 0.9699 → 1.0000 |
| A-3 | form and report print their captions | **holds** — form vocabulary 0.9385 → 0.9462; report 0.9959 → 1.0000 |
| A-4 | only those three differ from `S4-sweep` | **holds** — 12 of 15 byte-identical |
| A-5 | no leg falls that `S4-sweep` held | **holds except one, recorded**: `report_0011` precision 0.9679 → 0.9663 |

**The exception is the scorer's, and every token added is printed on the
page.** The caption adds seven tokens, six of which the output had lost. The
seventh is the `1` of `Table 1`. The source numbers its footnotes with an
`<ol>`, whose numbers are no text node, while the output prints `1.` as
text, so the output's `1`s already exceeded the source's by eight. A
genuine `1` therefore counts as a ninth surplus. Nothing is invented. This
is the same artefact that moved the recall leg to distinct tokens.

darkdeck's tau (0.9143 → 0.9192) and beside (0.5982 → 0.5620) are below
the floor as at `S4-sweep`. They wait on B1 and C.

### Step B — three repairs downstream of the model (replay)

- **B1. A `grid` Region is drawn as a grid**: its Zones placed by row and by
  lane, lanes as wide as the page draws them, never wrapped.
- **B2. Two arithmetic Probes reach the page.** A running balance — each row's
  balance against the one above it plus its money columns — names the rows
  where it breaks. A numeric column within 1% of a stated total, when another
  column reconciles, is reported rather than hidden. Detection only: no value
  is changed, and none reaches a prompt (ADR 0004).
- **B3. Lines are measured in their Zone's own polarity** wherever type is
  sized, so a dark sidebar's labels are measured rather than defaulted to the
  house heading size.

| # | clause |
|---|---|
| B-1 | `darkdeck_0009`'s four tiles stand four across; `catalogue_0015`'s 3×3 cards and `nonlatin_0014`'s two panels look as before |
| B-2 | `statement_0006`'s page names Cordell Energy and Wexford Insurance; no Probe fails on any other document |
| B-3 | `cv_0013`'s CONTACT, SOFTWARE, LANGUAGES draw below 1.6em |
| B-4 | Ratchet against `s3-result/` holds as at A-5 |

#### Outcome — step B, 2026-10-11, gate MET

**What the pages look like** (`S5-B-replay` against `S5-A-replay`).
`darkdeck_0009`'s four tiles stand four across. `statement_0006` opens on an
"Unresolved" panel naming the balance of Cordell Energy (1,141.30) and
Wexford Insurance, and the paid-out column 6.00 short of 5,772.36.
`cv_0013`'s CONTACT, SOFTWARE, LANGUAGES and INTERESTS are small capitals
again, and the skills are body-size lines. `catalogue_0015` and
`nonlatin_0014` look as before; catalogue's grey kicker `AUTUMN LIST` is
drawn at 1.0em where it was 0.75em, measured against a body that is now
measured correctly (8px, not 10.6px).

| # | clause | result |
|---|---|---|
| B-1 | darkdeck's tiles four across; catalogue and nonlatin as before | **holds** — darkdeck height 1.580 → 1.418, beside 0.562 → 0.623 |
| B-2 | the statement names both rows; no other Probe fails | **holds** — a test runs the Probes over all fifteen floor IRs |
| B-3 | cv's labels below 1.6em | **holds** — 0.74em |
| B-4 | ratchet as at A-5 | **holds** — no leg falls that `S5-A-replay` held; beside rises on catalogue (0.273 → 0.314), cv (0.400 → 0.519) and darkdeck |

**Two things were found on the way, both in the measuring, not the idea.**
(1) The grid first wrote its Zones in IR order and placed them by CSS, so
the page looked right and reading order fell — tau 1.000 → 0.860 on
`nonlatin_0014`, 0.910 on `catalogue_0015`. The markup is now in reading
order too. (2) Type was measured on the *equalised* image, where CLAHE turns
cv's dark sidebar into a 40–250 gradient across one crop; no grey level
separates type from ground there. It is now measured on `Rectified.plain`,
binarised by Otsu with the minority class as ink. Three other headings move
by a few hundredths. `tools/remeasure_style.py` measures the same way.

**Not reachable by `rederive.py`:** A1 needs the caption the veto refused,
which only the trace holds. Replay is its loop.

### Step C — T3 `beside` by row groups (offline, scorer only)

**Today:** two blocks are beside each other when they overlap vertically by
half the shorter and are horizontally disjoint. **Proposed:** the same
relation's connected components are *row groups*, and two blocks are beside
each other when they are horizontally disjoint **within one row group**. A
two-column stretch is one group however far its columns drift; a 3×3 card
grid is three groups; a page drawn as one stack has none. The old relation
stays reported as `row_agreement`, unratcheted.

| # | clause |
|---|---|
| C-1 | `tests/test_scoring.py` passes unchanged — Thread 0's exit gate still finds the deleted header, the repeated Titles and the hard breaks |
| C-2 | A two-column page rendered as one stack scores `beside` 0 (a new test) |
| C-3 | `s3-result/` re-scored with the new scorer is written beside its README, and S4-sweep's falls and gains are reported on both scorers |
| C-4 | No document whose picture shows its columns collapsed gains `beside` |

#### Outcome — step C, 2026-10-11: measured and reverted — the row group does not do what it was for

The relation was built and every page re-scored with it: the floor's
documents (re-scored first with today's scorer, **15 documents, 0
differing fields**, `S3-floor-scored`), `S4-sweep` and `S5-B-replay`.
`row_agreement` reproduced the old `beside_agreement` exactly on all 45.

| document | floor old → new | S4-sweep old → new | S5-B old → new |
|---|---|---|---|
| `catalogue_0015` | 0.273 → 0.261 | 0.273 → 0.261 | 0.314 → 0.325 |
| `cv_0013` | 0.400 → 0.385 | 0.400 → 0.385 | 0.519 → 0.484 |
| `menu_0012` | 0.348 → 0.348 | 0.364 → 0.400 | 0.364 → 0.400 |
| `newsletter_0008` | 0.700 → 0.545 | 0.700 → 0.545 | 0.700 → 0.545 |
| `invoice_0002` | 0.854 → 0.865 | 0.854 → 0.865 | 0.854 → 0.865 |
| the other ten | unchanged | unchanged | unchanged |

**Why it fails, read off the pairs** (every disagreeing
pair listed per document):

- **A source's row groups are fragments, not column stretches.** On
  `cv_0013` a sidebar line and a main-column line overlap by half only here
  and there, so the page's "columns" are a dozen small groups and drift
  between them still breaks pairs. The premise — one group per stretch of
  columns — does not hold on the pages it was meant for.
- **Not all of the low score is drift.** `catalogue_0015`'s is mostly each
  card's one-line price row, `£4.20 | each | In stock`, drawn as three
  stacked lines — a real layout difference a reader would remark on.
  `menu_0012`'s and `cv_0013`'s *are* coincidental cross-column alignment,
  which this relation was meant to forgive and does not.

The clause it was measured on, C-4, held, and C-1 to C-3 would have. It is
reverted because it does not do its job, and no number on the floor moved
the right way for the right reason. **What a drift-tolerant `beside` would
have to be is now known:** a column is not a chain of half-overlaps; it
needs the page's own stretches, found from the blocks that span them. That
is a scorer design question, not a parameter, and it goes back to
Alessandro. **Step D is measured on today's scorer**, and if type at the
page's size crosses `beside`, the crossing is reported with the pairs that
cause it.

### Step D — type at the page's size (replay, each arm kept only if it holds)

- **D1. Body type** at 1.33 × the width-weighted median glyph height.
- **D2. Zone Titles** at their printed size, in ems of that body.
- **D3. Heading Blocks** sized both ways, no longer shrink-only.

| # | clause |
|---|---|
| D-1 | Ratchet against `s3-result/` (re-scored, C) holds on every arm kept |
| D-2 | Mean `height_ratio` moves toward 1 |
| D-3 | The eight pages whose title prints at 17–31px draw it larger than their body |

### Step E — one fresh sweep, `S5-sweep`

All fifteen, shipped defaults. Report against `s3-result/` re-scored, in
spec 0009's §7 format, with all fifteen sheets opened beside `S4-sweep`'s.
Whether it becomes the floor is Alessandro's decision.

---

## 3. Rules that bind

Spec 0009's §6, unchanged. **Never cite a past run.** Look at the pictures.
Commit each step. **A change whose gate fails is reverted and recorded, not
argued** — Alessandro asked for the sweep at the end either way, so a failed
step does not stop the plan; it is reported with its measurement.
