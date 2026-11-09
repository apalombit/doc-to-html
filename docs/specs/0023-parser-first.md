# Parser first: GLM-OCR's whole pipeline, an adapter, our looks

**Status: open, 2026-11-09.** Step P1 of the level-up plan
([`../level-up.md`](../level-up.md) §5.3, §6 and decision 2 of §8), from
spec 0022's last prompt. Its issue is #46. Four questions for Alessandro
are on the issue page (round 8); his calls go under "Decisions".

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
| 1 | Q1: the branch's base | — |
| 2 | Q2: the build pages, then the L3 set | — |
| 3 | Q3: the time for the 41 pages | — |
| 4 | Q4: read what GLM-OCR discards | — |
