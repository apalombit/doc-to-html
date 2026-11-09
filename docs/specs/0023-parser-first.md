# Parser first: GLM-OCR's whole pipeline, an adapter, our looks

**Status: open, 2026-11-09.** Step P1 of the level-up plan
([`../level-up.md`](../level-up.md) §5.3, §6 and decision 2 of §8), from
spec 0022's last prompt. Its issue is #46. Four questions for Alessandro
were asked on the issue page (round 8) and all four agreed, 2026-11-09; his calls are under "Decisions".

- **It builds one new arm, D2**, beside today's pipeline, on branch
  `poc-parser-first`: GLM-OCR's own pipeline cuts the page into blocks
  and reads them; a new adapter maps the blocks into the IR; today's
  style record, looks, furniture and renderer draw it.
- **It converts the L3 set once with D2** and compares the result with
  `L3-baseline` (spec 0022's outcome, frozen in
  `tests/frozen/l3-baseline/`) class by class, by the same checks, judge
  and criteria. That comparison is what P2 decides on.
- **Today's pipeline does not move.** D2 adds modules and a batch arm;
  nothing a Conversion runs changes, and the replay of `s14-result/`
  stays 21 of 21 byte for byte.

**Why.** L3 found a major fault on 37 of 37 unseen pages, and three
majors in four are made reading the page: extract, layout, locate,
rectify (spec 0022, "Where the majors are made"). That is the side a
parser trained on millions of pages would take over. P1 measures whether
it does better there, and what it costs on the side we keep.

## Read first, in order

1. `CLAUDE.md`'s READ THIS FIRST, and [`../status.md`](../status.md).
2. [`../level-up.md`](../level-up.md): the Gist, §5.3, §6 and §8.
3. [`0022-the-honest-baseline.md`](0022-the-honest-baseline.md)'s
   "Outcome": the ranked fault classes, the majors by stage, what the
   checks still miss.
4. [`../agents/review-criteria.md`](../agents/review-criteria.md).
5. This spec, end to end.

---

## GLM-OCR, re-checked 2026-11-09

Against `level-up.md` §8 ("GLM-OCR, as of 2026-10-24").

| | 2026-10-24 | 2026-11-09 | changed? |
|---|---|---|---|
| SDK on PyPI | `glmocr` 0.1.5 (2026-04-08) | 0.1.5, still the latest release | no |
| SDK repository | — | `main` at `0288f96` (2026-10-14), three commits past v0.1.5 | see below |
| layout model | PP-DocLayoutV3 | `PaddlePaddle/PP-DocLayoutV3_safetensors`, last changed 2026-09-30; 25 labels; reading order from the model's own `order_seq` | no |
| reader | `glm-ocr:latest` on Ollama | `latest` = `bf16`, digest `89d735dd9c07`, 2.7 GB (F16, 891M + a 434M projector, needs Ollama ≥ 0.30); `q8_0` `6e5935a916fc` unchanged | pulled today; not used before |
| local serving | `ollama_generate`, `/api/generate` | the same; the SDK's Ollama guide unchanged | no |
| licences | code Apache-2.0, model MIT, layout Apache-2.0 | the same (GitHub, Hugging Face) | no |
| Ollama here | — | 0.34.0 | — |

**What is new, and what it means here:**

- **`main` drops no chart.** v0.1.5's formatter skips every region whose
  content is empty, and a chart or picture region has none, so a chart
  vanished from the output. `20ad544` (2026-04-16) keeps them. D2 uses
  **`main` at `0288f96`**, pinned, not the PyPI release. The other two
  commits: an empty prompt defaults to `Text Recognition:` in Ollama
  mode (`cef4d0e`; the pipeline always sends one), and a file-read fix in
  the separate web backend (`0288f96`).
- **The SDK's base install requires PyMuPDF**, which is AGPL-3.0;
  `glmocr/utils/image_utils.py` imports it at the top.
  `pyproject.toml` keeps PyMuPDF out of this project. So the SDK lives
  in **its own virtual environment, outside the repository**
  (`~/.venvs/glmocr`), and runs as a subprocess. Nothing in `src/`
  imports it, and nothing of it is shipped. If P2 takes D2, this is a
  question to answer then.
- **By default the pipeline discards six kinds of region**: `header`,
  `footer`, `number` (page numbers), `footnote`, `aside_text` and
  `reference` (its `label_task_mapping.abandon`). Measured on
  `probe_payslip` today: the default returns 8 regions, and with nothing
  discarded 13. The five it drops are the company name, `PAYSLIP`, the
  address, the pay period and the footer line. Under our criteria each
  is a lost line, a major. Question 4 below.

**Measured today**, the whole pipeline (layout on the CPU, the reader on
Ollama, one region at a time, nothing discarded) over five dev pages:

| page | what it is | regions | seconds |
|---|---|---|---|
| `probe_payslip` | side-by-side panels, tables | 13 | 17.0 |
| `ticket_0020` | a designed page | 28 | 7.6 |
| `c0197` | a real PDF page: a purchase order | 3 | 35.8 |
| `probe_labreport` | the probe's hardest table | 7 | 20.2 |
| `newsletter_0008` | three columns, dense | 22 | 15.2 |

Plus 3.4 s to load the layout model, once per process. Today's pipeline
took a median of 405–725 s a page on L3 (spec 0022). **Reproducible:**
two runs on the payslip returned the same eight shared regions, boxes and
text byte for byte. What each region carries: `index` (reading order),
`label` and `native_label` (one of 25), `bbox_2d` (0–1000 of the
picture), `polygon`, and `content`: text with line ends, a table as HTML
with `colspan`/`rowspan`, a formula as LaTeX, nothing for a picture.

---

## The arm D2

```
picture ─► GLM-OCR, its whole pipeline (subprocess, its own venv)
             PP-DocLayoutV3: boxes · labels · order
             glm-ocr:latest: each region read with its task prompt
                    │  blocks.json — recorded in the dump, like a model answer
                    ▼
           adapter (new): blocks ─► Zones, Blocks, Cells, Rows, each with its box
                    │
                    ▼  kept from today
           style record · furniture · chrome · type sizes · looks
                    │
                    ▼
           renderer ─► document.html  (the dump measure_run reads)
```

**Where the line is** (`level-up.md` §5.3). The parser decides what the
page says and how it is grouped; we measure how it looks and draw it.

| the parser's (not run in D2) | ours (run in D2) |
|---|---|
| the detector and its post-processing, the cover step, the snap | the style record: ground, ink, accent, body size (`style`) |
| classify, the caption pass, extract, the row nets | the furniture: rules, fills, frames (`furniture`, `furnish`) |
| locate's reading of lines, the unclaimed-lines pass | the chrome: a Zone's fill, title bar, header bar, border |
| spans, raised, display, drop caps, separators | type sizes and looks: size, weight, slant, colour (`looks`) |
| the third reading | fields' marks (`fields`), if the blocks give them a place |
| rectify's straightening and cropping | the renderer |

**rectify** is on the parser's side for this arm: its straightening is
a reading decision, and on L3 it cropped `c0300`, a flat PDF page, to one
table (69 words). The corpus pages are flat screenshots and PDF renders
(§4.8 keeps picture-level difficulty out), so GLM-OCR reads the picture
as it is, and our measuring passes read the same unwarped picture. What
rectify does for the looks (a dark page turned over, the plain and the
equalised picture) is kept.

**The adapter, as it starts.** One Zone per region, in the parser's
order, with its box; then the joins the IR's own conventions ask for,
each kept only if the dev pages show it right by eye.

| region | the IR, as it starts |
|---|---|
| `doc_title`, `paragraph_title` | a heading; the Title of the Zone it names when it stands right above it (the Zone convention, `CLAUDE.md`) |
| `text`, `content`, `abstract`, `reference_content`, `algorithm`, `vertical_text`, `aside_text`, `footnote`, `vision_footnote`, `figure_title`, `number`, `seal` | prose, one Cell per printed line as the parser returns it |
| text whose lines open with a bullet or a number | a list, the item's number kept |
| `table` | a table: its HTML's rows and cells, `th` rows as header rows, `colspan`/`rowspan` as spans |
| `display_formula`, `inline_formula` | a display line holding the parser's text |
| `image`, `chart`, `header_image`, `footer_image` | a figure, its own pixels |
| `header`, `footer` | their text, with the Zone's role |

Band and column come from the boxes: regions that share a stretch of
the page's height and sit apart in it are side by side. There is no
pairs region; a label and its value arrive as a two-column table or as
lines. What to make of them is decided on the dev pages.

**What we iterate on**: the adapter and the looks side, never the
parser's weights, its prompts or its thresholds. Its configuration is
fixed in one committed file (`parser/glmocr.yaml`): local Ollama, the
layout model on the CPU, one region at a time, and nothing discarded if
Alessandro agrees (question 4).

**The offline loop.** The parser's blocks are recorded in each page's
dump. A tool re-runs the adapter and the looks side over a run's
recorded blocks with no model, the way `tools/rederive.py` re-runs
today's downstream steps, so each change to the adapter is judged on the
build pages in seconds. The parser runs once per build page.

**What D2 writes**: `debug/runs/<label>/` as a batch does, under
`dump/glm-ocr_latest/`, so `tools/measure_run.py`, the review and the
issue page read it unchanged. `pages.jsonl` keeps each page's seconds.

---

## Four questions for Alessandro

On the issue page, round 8
(https://claude.ai/artifact/RpUd3a7ioGjdNWBLyqM6JD); none was asked in
rounds 1–7 (`../agents/review-issues.json`).

**Q1 — branch from `level-up`, not `develop`?**
- §5.3 says `develop`. But the corpus, the checks, the batch runner, the
  review tooling and `l3-baseline/` all live on `level-up`, made after
  `develop` was cut. From `develop` the PoC would have none of them.
- **Claude proposes `poc-parser-first` from `level-up`** at its head.
  `level-up` itself takes nothing of D2 until P2 decides.

**Q2 — build on eleven dev pages, then the L3 set?**
- **Claude proposes the dev pages the plan already names for a risk**:
  §5.3's risk table names the probe's flyer, quiz, payslip, recipe and
  datasheet and the corpus's ticket, pricing and catalogue; §3.4 names
  the lab report. Plus **dev's two real PDF pages of the kinds in the
  L3 set**: `c0071` (application form) and `c0197` (purchase order).
- Picked by that rule, not by looking. All are dev pages; no panel page
  is opened before the L3 run.
- Then the 41 pages of `corpus/l3-subset.txt`, once, with the adapter
  frozen.

**Q3 — the time for the 41 pages.**
- Measured today, the parser alone takes 8–36 s a page on five dev
  pages. Our looks and render add a little; the build pages measure the
  whole arm before the run.
- At a minute a page the 41 take about 40 minutes; at the worst
  measured page, under 30. Today's took 6.6 hours.
- **Claude proposes**: the same 20-minute page limit as `L3-baseline`,
  so timeouts compare; the time measured on the build pages and given
  to you before the run; started without a separate go if it is under
  two hours, and stopped to ask if it is over.

**Q4 — read the headers, footers and footnotes GLM-OCR discards?**
- Its default discards six kinds of region, page headers and footers,
  footnotes and page numbers among them. On the payslip that is five
  printed lines: the company name, `PAYSLIP`, the address, the pay period
  and the footer.
- **Claude proposes reading them**, as text with a header or footer role:
  one line of its configuration, not its weights or its layout. Without
  it D2 loses words on most pages by design, and the comparison would
  measure the setting, not the parser.

---

## Steps

### Step 0 — the spec, the issue, round 8

This spec; issue #46; round 8 on the issue page. His calls go under
"Decisions" and into `review-issues.json`.

### Step 1 — the branch, the parser, the arm

- `poc-parser-first` from the base Q1 settles.
- The parser: `~/.venvs/glmocr` with `glmocr[selfhosted]` at `0288f96`;
  `parser/glmocr.yaml`; `tools/glmocr_parse.py`, run by that venv's
  Python, picture in and `blocks.json` out.
- The arm: a converter for `doc_to_html.batch` that runs the parser in a
  subprocess, the adapter, the looks side and the renderer, and records
  the blocks, the seconds and a trace; `tools/batch.py --arm d2`.

### Step 2 — the adapter and the looks, on the build pages

- The parser once over the build pages (Q2); then the offline loop.
- Each change judged by eye: the render beside its source, and beside
  the previous iteration's render. A rule kept only if it holds on more
  than one page, and every page it moves is opened.
- Unit tests on blocks built by hand and on dev pages only.
- What each iteration changed, and what it fixed, recorded in this
  spec's outcome.

### Step 3 — freeze, prove, time

- The adapter frozen at a commit.
- Proved on that commit: `tools/replay_run.py tests/frozen/s14-result`
  21 of 21 byte-identical, 0 asked differently; `tools/rederive.py` 21
  of 21; the test suite and `mypy src/`.
- Every Chrome job finished; nothing beside the run.
- The time for the 41, from the build pages, given to Alessandro (Q3).

### Step 4 — the L3 run

```
nohup env PATH="$PWD/.venv/bin:$PATH" python tools/batch.py \
    P1-D2-L3 --arm d2 --pages l3 > debug/P1-D2-L3.log 2>&1 & disown
python tools/batch.py P1-D2-L3 --status
```

One page at a time, the 20-minute page limit. A timeout is recorded and
not retried.

### Step 5 — the measurement and the review

- `python tools/measure_run.py debug/runs/P1-D2-L3 --all`.
- Claude reviews every converted page by the criteria, as spec 0022
  did: each check's fault confirmed or rejected by looking, its stage
  named, the faults no check raises added by eye (spec 0022's "What the
  checks still miss"). Calls in `docs/agents/review-calls/P1-D2-L3.json`.
- D2's stages, for the majors: **parser: layout** (a box, a label or
  the order), **parser: reading** (a region's text or table), **adapter**
  (our mapping), and the drawing side's as in L3 (`cv:looks`,
  `cv:furniture`, `cv:zone_chrome`, `cv:heading_sizes`, `render`).

### Step 6 — the comparison, his spot checks, P2's question

- D2 against `L3-baseline`, on the same 41 pages:
  - the ranked classes side by side, pages touched and times;
  - majors per page, by origin, density and family;
  - majors by stage, reading side against drawing side;
  - the PDF pages, and the timeouts, in their own lines;
  - seconds per page.
- Page by page: better, same or worse, with the element named.
- His spot checks on the issue page, round 9: every page where Claude's
  call overturns a check, and two at random, as decided for L3.
  **Where his calls disagree with the checks, stop and ask.**
- Then P2's question, for him: keep today's, take D2, or a mix (which
  side from which arm).

### Step 7 — close

This spec's outcome; `docs/status.md`; `CLAUDE.md`; `level-up.md` §6;
the issue closed; a handover prompt for P2 or L5, facts re-measured.

---

## Rules

- **Local models only.** GLM-OCR runs on this machine through Ollama;
  nothing leaves it.
- **Never pass `unseal=True`.** The vault stays sealed.
- **No panel page is used in a test or to tune the adapter**, `c0001`
  and `c0002` above all. The L3 run is taken once, with the adapter
  frozen. A fault found there is reproduced on a dev page before
  anything is changed for it, and a second L3 run is his call.
- **Today's pipeline on `level-up` stays as it is**: the replay of
  `s14-result/` stays 21 of 21, on both branches.
- One conversion at a time, nothing beside it; every Chrome job finished
  before a conversion starts.
- Stop and ask before any conversion longer than two hours, and wherever
  his calls disagree with the checks.
- Judge by eye (`review-criteria.md`); a number is a pointer to a page.

## Outcome — steps 1 to 3, 2026-11-09

### What was built (`poc-parser-first`, `8f518c1`, `1e49926`)

- **The parser**: `~/.venvs/glmocr` (`glmocr[selfhosted]` at `0288f96`,
  torch 2.15, transformers 5.22, PyMuPDF 2.1, none of it in this
  project's venv); `parser/glmocr.yaml`; `tools/glmocr_parse.py`, which
  writes the reader's **raw** regions (before the SDK's markdown
  formatter, which adds `## `, invents a bullet between two bulleted
  lines and doubles line ends: the recipe's `For the dressing` became
  `- For the dressing`).
- **The adapter**, `adapter.py`; **the arm**, `parser_first.py`
  (`flat`: rectify without warp or deskew; `containers`; `measure`,
  today's measuring passes; `uncut`); `tools/d2.py`, the offline loop;
  `tools/batch.py --arm d2`. 17 unit tests on regions built by hand,
  `tests/test_adapter.py`.
- **The passes D2 runs after the adapter**: the furniture, the palette,
  the regions (`structure`), each Zone's chrome, the type sizes, the
  separators, `locate.locate` (tesseract as a locator only; it places the
  parser's Cells and reads nothing new), `furniture.place`,
  `rhythm.read`, `looks.read`, each figure's pixels. Not run:
  `without_cut_copies` (it deletes a Cell), `spans`, `raised`,
  `display`, `dropcap`, `separator`, `fields`, the unclaimed lines.

### The adapter, iteration by iteration, on the eleven build pages

Each judged by eye, source beside render, against the iteration before.

| # | change | what it fixed, and where |
|---|---|---|
| v0 | one Zone per region | the payslip whole, both tables, header and footer; every other page cut too fine |
| v1 | a line end the reader writes is kept (the reader joins a paragraph's wrapped lines itself) | the payslip's three fields no longer run onto one line |
| v2 | grouping: a drawn box's regions one Zone; a column stack one Zone | the catalogue's prices drawn (they had been put in one grid cell with `each` and covered by its box); the recipe's ingredients one list |
| v3 | a stack needs a shared edge, not an overlap | chips stopped joining headings: the recipe's ingredients beside its method |
| v5 | left or centre edges only; a ragged right edge meets a chip's by chance | the recipe's title over its chips (height 1.54 → 1.05) |
| v6–7 | a box no wider than a card (0.45 of the page) is one Zone; a wider box only bounds the stacks | c0071's two sections side by side (1.92 → 1.07); the catalogue's cards kept whole |
| v8 | a heading over its table is its Title, found by position, not reading order | the payslip's EARNINGS table back beside DEDUCTIONS (1.23 → 0.96); `CO₂`, `200°C` |
| v9 | a heading opens a stack and may stand two lines above it | the datasheet's key features under their heading, beside the specification table (1.47 → 1.09) |
| v10 | boxes inset half a line for banding only | the lab report's header off its table's row |
| v11 | a cell's line ends kept as `Cell.below` | the lab report's patient box, each label over its value |
| v12 | a region of lanes that cuts a parser block is drawn as one flow | pricing's cards, one picture to the parser, drawn at full width (0.54 → 1.04); **one page only**, and byte-identical elsewhere |

v4 (a region alone in a drawn box joins no stack) is kept but moved
nothing: the recipe's pill chips are not furniture `furniture.find`
reports.

### What is left on the build pages, by side

- **The parser's layout**: pricing's three cards read as one picture,
  never read as text; the ticket, a tilted photograph (picture-level
  difficulty, kept out of the corpus, §4.8), cut and ordered wrong.
- **The parser's reading**: `√` for ✓ and the last tick lost, `A07` for
  `AQ7` (datasheet); `Gross pay£4,098.08`, label and value run together
  (payslip); `[1 m]` for `[1 mark]` (quiz); card 1's `In stock` not read
  (catalogue); a line-end hyphen dropped when it joins lines
  (`ninemonth`, newsletter, read for timing only).
- **The drawing side, shared with today's pipeline**: the flyer's display
  title drawn small and dark, its pill a band; table rows' shading
  (datasheet, lab report); the lab report's red flags grey; the
  catalogue's prices small and its rows' colours; the recipe's hanging
  step numbers; the datasheet's monospace; form fields' frames (c0071),
  the PDF order form's ruled boxes (c0197).

### Proved on the frozen adapter, 2026-11-09

- `tools/replay_run.py tests/frozen/s14-result`: **21 of 21
  byte-identical, 0 asked differently**; `tools/rederive.py`: **21 of
  21**. Today's pipeline is untouched.
- A fresh parse of two build pages through `batch.py --arm d2`
  reproduced the offline loop's regions and HTML byte for byte.
- `mypy src/` clean; **1719 tests pass, 1 skipped** (L3's 1702 and
  `test_adapter.py`'s 17), 16:44. `parser_first.PARSER_PYTHON` is a fixed
  path: the environment is read only in `config.py`.

## Outcome — steps 4 to 6, 2026-11-09: D2 against L3-baseline

### The run

- **`P1-D2-L3`**, `batch.py --arm d2` on `1cb0e47`, the 41 pages of
  `corpus/l3-subset.txt`, one page at a time, 2026-11-09 14:06 to 14:24:
  **18 minutes, 41 of 41 converted, none timed out.** 26 s a page on
  average; medians by density: sparse 19 s (14 pages), medium 25 s (20),
  dense 38 s (7). The parser's own share: median 13.9 s.
- `L3-baseline` took **6.6 hours**, 577 s a page, and lost c0034,
  c0196, c0291 and c0456 to the 20-minute limit.

### The review

- `measure_run.py --all`, then every page opened, its sheet beside its
  parser regions (`dump/glm-ocr_latest/<page>/00_regions.json`) and its
  IR. Calls: `docs/agents/review-calls/P1-D2-L3.json`.
- **1184 check faults called: 1176 confirmed, 8 rejected** on 6 pages;
  **47 added** that no check raises. Every major carries its stage.
- **A major fault on 41 of 41 pages**, as on L3's 37 of 37.
- The stages: **parser: layout** (a box, a label, the order), **parser:
  reading** (a region's text or table), **adapter** (our mapping),
  **locate**, and the drawing side's `cv:*` and `render`.

### Side by side, on the 37 pages both converted

| | L3-baseline | D2 |
|---|---|---|
| majors | 651 | 660 |
| majors per page | 17.6 | 17.8 |
| major classes per page | 7.3 | 6.6 |
| PDF pages (c0074, c0082, c0272, c0300) | 43.5 | 30.2 |
| generated pages (33) | 14.5 | 16.3 |
| dense / medium / sparse | 27.3 / 19.9 / 10.6 | 21.3 / 22.8 / 10.4 |
| seconds a page | 577 | 26 |

By family, majors per page, L3 → D2: correspondence and legal 9.8 → 5.5,
credentials 9.8 → 6.5, presentation 12.2 → 9.8, fragments 13.5 → 12.8,
reference 22.3 → 16.3, reports 25.8 → 26.6, publishing 10.0 → 14.0,
forms 33.8 → 36.8, transactional 16.2 → 25.0.

**The four pages L3 lost to the limit**, D2's majors: c0034 64 (a dense
tax form, read whole but its tables unmeasured), c0196 153 (PDF: read to
its first header rows), c0291 25 (the card grid read as one table),
c0456 23. **The fifth PDF page**, c0196, is D2's worst page.

### Where the majors are made

| side | D2, 41 pages | D2, the 37 | L3, the 37 |
|---|---|---|---|
| **the parser** (D2) / reading the page (L3) | parser: reading 442, layout 183 = **625** | **413** | 495 |
| **ours** | adapter 106, cv:looks 86, render 46, locate 40, cv:zone_chrome 9, cv:heading_sizes 8, the rest 6 = **300** | **247** | 156 |

### The fault classes, side by side

Pages touched / times, standing faults, on the 37; D2's stages from the
calls file.

| class | L3 | D2 | D2 made at |
|---|---|---|---|
| words: lost | 24 / 182 | 15 / 313 | parser reading (a box taken for one table, only its grid read: c0097, c0196, c0300), parser layout (lines in no region), adapter (c0070's broken table HTML; `$` amounts read as maths) |
| words: invented | 24 / 178 | 7 / 27 | parser reading; adapter (LaTeX drawn as source, c0382) |
| words: changed | 10 / 15 | 15 / 40 | parser reading: names, accents (c0064, c0129), numbers |
| words: merged | 0 / 0 | 6 / 21 | parser reading: spaces dropped (`250mg`, `Sample:48`) |
| structure: numbers as bullets | 10 / 12 | 0 / 0 | — |
| structure: marker changed | 16 / 20 | 7 / 11 | parser reading |
| beside: drawn under | 9 / 9 | 11 / 12 | adapter: a column's second Zone banded after the tall one beside it |
| lines: broken differently | 13 / 13 | 24 / 25 | parser reading (two lines written as one), render |
| lines: rows joined | 3 / 3 | 10 / 10 | parser reading: a label and the line under it as one |
| type: bold lost | 26 / 26 | 31 / 32 | cv:looks (bold runs inside a line: no inline-runs pass), locate |
| type: sizes out of proportion | 33 / 67 | 33 / 67 | cv:looks, parser reading, locate |
| looks: fill drawn another shape | 12 / 14 | 9 / 9 | adapter: a band read as several regions |
| rules: cells merged as drawn | 9 / 13 | 10 / 16 | render, locate |
| cells: wrong column | 5 / 17 | 4 / 7 | parser reading |
| height | 37 / 37 | 36 / 36 | adapter, render |

### Page by page, D2 against L3, both against the page

Judged by eye, the three side by side.

- **Better, 13**: c0032 (the list's numbers kept), c0069 (header whole,
  every field in its table), c0074 (no doubled fragments of lines 1-2),
  c0082 (no invented placeholder text), c0243 (the header and the table
  whole), c0252 (the medication table readable row by row), c0316 (no
  doubled header), c0342 (the side panel beside the map), c0405 (the
  facts row and numbered steps kept), c0431 (the sidebar in order),
  c0467 (the chart a picture, not loose numbers), c0476 (the 3×2 dish
  grid kept), c0515 (no overprinted fields).
- **Worse, 7**: c0064 (the QUADRO badge lost, the 2×2 fields as rows,
  accents dropped), c0070 (six rows lost: the reader's broken
  `colspan="5>`), c0097 (the sidebar and both questions lost: one table
  region, its grid alone read), c0115 (the Date/Register lines in no
  region), c0129 (names and numbers misread, the chart pushed down),
  c0387 (the pull quote and a paragraph drawn at the foot, a paragraph
  red), c0441 (the company name and the legend line in no region).
- **The same, 17**: c0121, c0128, c0234, c0272, c0300, c0334, c0343,
  c0356, c0382, c0388, c0485, c0523, c0527, c0547, c0555, c0575, c0596.
- **Converted only by D2, 4**: c0034, c0196, c0291, c0456.

### Found on our side, not fixed

Each must be reproduced on a dev page before anything changes (Rules):

- **`locate` leaves a D2 table unmeasured.** `locate._built` takes any
  table with a span or a second line in a cell for one `spans.read`
  built, and keeps its boxes: the adapter's tables have no boxes, so
  every Cell stays unplaced and nothing in it is measured (366 of 869
  table Cells, 12 pages): bold, size, alignment, row rules and fills.
- **`plain` takes `$` amounts for inline maths** (c0034, c0291, c0456,
  c0121): the spaces between two amounts closed up.
- **A reader's malformed table HTML** drops the rest of the table
  (c0070, one missing quote).
- **Display formulas drawn as LaTeX** (c0382); the reader's bold markers
  dropped (`<strong>`) or drawn (`**Action:**`); `4^{1}$` drawn as written.
- **Banding**: two Zones stacked in a column beside a taller one; the
  second gets a band of its own after the tall one (7 pages).

## What P1 does not do

- No change to the parser's weights, prompts or thresholds.
- No D1 arm (today's Zones read by GLM-OCR) unless D2's result needs
  telling apart: is a gain in its layout or in its reading (§5.3)?
- No fitting of the looks side's constants: that is L5.
- No vault, and no panel page beyond the L3 set.

---

## Decisions — Alessandro

| # | asked | decided |
|---|---|---|
| 1 | Q1: the branch's base | **`level-up`** (round 8, 2026-11-09): `poc-parser-first` cut from its head |
| 2 | Q2: the build pages, then the L3 set | **Agreed** (round 8): the eleven dev pages, then the 41 once, the adapter frozen |
| 3 | Q3: the time for the 41 pages | **Agreed** (round 8): the 20-minute page limit; the time from the build pages given before the run; started if under two hours, his go if over |
| 4 | Q4: read what GLM-OCR discards | **Agreed** (round 8): all six kinds read as text, headers and footers with their role |
