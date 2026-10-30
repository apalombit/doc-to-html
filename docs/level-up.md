# Level up — conversion that holds on documents it has never seen

**Status: decided 2026-10-24 (§8); the variability agreed the same day
(§4.7).** Next: build the corpus (L1b), [spec 0020](specs/0020-the-corpus.md),
issue #43, run in a fresh chat. Three tracks: the corpus, its
measurement with a judge (§4.9), and the parser-first PoC (P1). Branches
`main`, `develop` and `level-up`; the work continues on `level-up`.

## Gist — keep this in mind

**The converter is a workshop.** Its eyes are good: the detector and the
VLM learned from millions of pages. Its tools are hand-made: about 14,500
lines and 265 dials, tuned on 21 pages. On ten new pages the eyes still
read the words, but the tools cut the structure wrong on nine.

**Q1 — test set.** Practise on many pages, decide on a fixed set, keep a
sealed exam.

- Pages are written from cards drawn at random inside agreed bounds:
  eight families of document, every layout feature several times in
  different kinds, English and the Latin languages (§4.7).
- A first batch of 600, about 100 of them real PDFs, in three pools of
  200: **dev** to look at, a **panel** to decide on, and a **vault**
  nobody opens until a milestone.
- **The judge is Claude**, with the review skill held to criteria agreed
  with you (§4.9, `agents/review-criteria.md`).

**Q2 — architecture.** Hire a craftsman, keep our painter.

- **Parser first.** GLM-OCR's own pipeline (its layout model, then its
  reader) cuts the page into blocks and reads them. It learned from
  millions of pages. Its reader alone read the probe's pages about as
  completely as ours, about 65 times faster; the whole pipeline's time is
  measured in P1.
- **We keep the painting**: style measured from pixels, and the renderer.
- **The painter's dials** are fitted on the corpus, not set by eye.

**The options weighed** (§5.2):

| option | ELI5 | verdict |
|---|---|---|
| keep adding rules | one more hand-made tool per broken page | stop as the main loop |
| a pipeline per document type | a workshop for invoices, another for menus | no: each sees a sliver of the pages, and something must sort them first |
| future-ideas: layout proposals | try several cuts, keep the best | later, if faults remain |
| future-ideas: the judge | an examiner who marks the render against the source | **yes, now**, as the measuring instrument (L2) |
| reader swap | new eyes, same hand-made tools | only as a control arm: the faults are in the tools |
| **parser first** | a craftsman cuts and reads; we paint | **yes: the PoC (P1)** |
| a parser as a checker | a second pair of eyes for the examiner | yes, inside the judge |
| fit, don't set | set each dial from hundreds of labelled pages, not one | yes, after the corpus (L5) |
| one big model, picture to HTML | ask a genius to redraw the page | no: not local, and it drops or invents words |

**Why parser first, ahead of the future-ideas loops.** The probe's faults
sit in the part a parser replaces. The future-ideas loops improve *how* we
tune; parser first changes *what* we tune. It still waits for the corpus,
because without one no comparison can tell a gain from luck.

**Rules of thumb:**

- a rule needs several pages of its kind behind it, never one;
- a page that is looked at is a practice page;
- a real PDF joins only if its HTML redraws its own picture.

**Branch history.** `develop` was cut from `scaffold` at `99110c2`, the
S14 baseline, and `level-up` from `develop`.

Alessandro asked for a step back from page-by-page review: take stock of
the project, then answer two questions with one aim — **conversion quality
that generalises to documents not yet seen, not a better result on the 21.**

1. Grow the test set by 5–10 pages at a time, or move to ~1000 documents in
   categories, sampled whenever a conversion is run? Picture-level
   difficulty (shading, skew) stays out until conversion itself is good.
2. The converter is one pipeline for every page. `future-ideas.md` weighed
   other architectures. Which, if any?

**Every number here was measured in this session, on 2026-10-24.** Past
runs are not cited. The two exceptions are the frozen baseline, re-derived
and re-scored today, and the specs' own text, quoted as text.

---

## 0. The answers on one screen

| question | answer |
|---|---|
| Is recent work overfit? | **Yes, and the probe in §3 shows it.** Rules are written for named pages, and 21 pages cannot tell a general rule from a fix for one page. The six "held-out" pages have been the focus of most specs since 2026-10-14, so nothing unseen is measured any more (§2). |
| What happens on pages it has never seen? | **Words survive, structure breaks.** Nine of ten new pages have a fault that changes how the page reads: a table cut short or flattened, columns interleaved, cells in the wrong column, a block lost or invented. Of six tuned pages drawn at random, none do (same day, same judge). Two of spec 0019's rules misfire on new pages, and a fixed corpus fault returns. A 0.9B document model read the same pages about as completely as the whole pipeline, about 65 times faster (§3). |
| **Q1** — grow by 5–10, or ~1000? | **~1000, generated from a taxonomy, used as three pools:** a *dev pool* you look at, a fixed *panel* you decide on, and a *vault* nobody looks at. The first batch is 600 pages, 200 per pool, about 100 of them real PDFs. Each model-side change converts the 200-page panel once (about 27 h today, which is why the baseline runs on 30–40 pages). Anything downstream is replayed over it in minutes. Adding 5–10 pages moves no estimate, and each added page becomes a tuning target within days (§4). |
| **Q2** — change the architecture? | **Yes: a parser-first pipeline, built as a PoC on its own branch and measured against today's.** Today about 14,500 lines of hand-written rules and 265 tuned constants carry the generality, all set on 21 pages or fewer. Established document parsers (GLM-OCR, PaddleOCR-VL, MinerU2.5; about 1B parameters, small enough for the 8 GB M1) return layout, reading order, tables and formulas, learned from millions of pages. Let one produce the content and structure (the side holding 63 of the constants). Map its blocks into our IR. Keep our own work where no parser competes: style measured from pixels, and the renderer. That looks side holds 135 constants, and they get *fitted* on the generated corpus instead of hand-set; its HTML supplies the labels for free. No pipeline per document type (§5). |
| Next steps | **L1a** agree the corpus's variability (done) → **L1b** build the corpus → **L2** measurement and a judge → **L3** an honest baseline on a limited set → **P1** the GLM-OCR parser-first PoC → **P2** the decision → **L5** fit what is left (§6) |
| Decisions | taken 2026-10-24, §8 |

---

## 1. Where the project is

### 1.1 State

| | |
|---|---|
| target | the render looks and reads like the source (spec 0007, unchanged since 2026-09-17) |
| baseline | `tests/frozen/s14-result/`: 21 documents and 811 recorded answers, taken 2026-10-23 |
| open work | none; every item was cleared 2026-10-23 |
| how a step is judged | by eye, against a sweep of all 21 (about 2½ h). Scores are recorded but never gate; the `vanished` list is read as a pointer to a page |
| corpus | 21 HTML pages and their screenshots: 15 tuned on from the start, plus 6 added 2026-10-13 as "held out" |
| code | 28,848 lines in `src/`, 1,294 test functions, 5,318 lines of tools |
| git | all 232 commits exist only on this machine. The private remote holds `main` (the initial commit) and nothing else |

### 1.2 How a page is converted

```
picture
 ├ rectify: page outline, warp, equalise                   CV, hand-set
 ├ Zones: the trained detector `heron` (Docling's, ONNX)   LEARNED
 │   + snap to ink, enclosure, cover the page, regrouping  hand-set
 ├ per Zone, qwen3-vl:4b through Ollama:                   LEARNED (general VLM)
 │   Title, Kind, content (table / pairs / prose / list),
 │   inline runs, re-reads of unclaimed lines, third readings
 ├ wire: answers → IR, six row nets                        hand-set
 ├ tesseract: where each word sits, a second reading       LEARNED (classic OCR)
 ├ about 20 CV passes: structure, furniture, rhythm,       hand-set
 │   locate, fields, looks, spans, raised marks, display
 │   lines, drop caps, separators, style record
 └ render: IR → semantic HTML styled by measured style     hand-set
```

The learned parts (detector, VLM, tesseract) were trained on millions of
pages by other people. Everything marked hand-set was written in this
project and tuned on this corpus.

### 1.3 Where the code is

| role | lines | modules |
|---|---|---|
| page heuristics (CV and rules) | 10,069 | preprocess, structure, furniture, furnish, rhythm, locate, fields, looks, spans, raised, display, dropcap, separator, style, ladder, probes |
| renderer | 4,400 | render |
| orchestration, wire, IR | 5,149 | orchestrator, wire, ir, extractors, checkpoints |
| model glue and detector post-processing | 2,887 | engines/* |
| measurement and tooling | 6,343 | projection, scoring, report, review, bakeoff, trace, corpus, config, honesty, geometry_score, cli |

`src/` grew from **9,316 lines on 2026-09-18** (spec 0007's first commit)
to **28,848 on 2026-10-23**. That is three times the code in five weeks, on
15, then 21, pages.

### 1.4 What is strong — keep all of it

- **Determinism and replay.** At `temperature: 0`, a conversion repeats to
  the byte. `replay_run.py` and `rederive.py` re-measure a downstream change
  without the model. Today the baseline re-derived for all 21 pages in 2
  minutes and was re-scored in under 3.
- **Ground truth derived, not typed.** A page is an HTML file plus its
  screenshot. That is what makes a big corpus possible at all.
- **Content is checked absolutely.** `vanished` names every source word the
  render no longer prints.
- **Every step is traced**, and the review tooling (sheets, report) is
  mature.

These are exactly the assets that make a larger corpus affordable (§4.5).

### 1.5 What is weak structurally

- **The rules are a cascade.** The detector's Zones condition every later
  pass, and the later passes' gates were tuned to the Zones the detector
  happens to return on these 21 pictures. Change the picture invisibly and
  the Zones change, and with them the downstream rules' behaviour. Measured
  today with the jitter check (resample 98% and 102%, shift 1 px, blur
  σ 0.6): **751 of 848 Zones kept, and 14 of 21 pages regroup** on at
  least one of the four.
  Spec 0018 dropped three steps for this one reason: each moved the picture
  or the boxes and lost pages through regrouping.
- **Steps are not local.** One removed Zone moved a page-wide measure and
  changed tesseract's reading of another pane (spec 0016, 4a). Every
  constant tuned on one page is therefore also a constant on every other
  page.
- **A module per spec step.** `display`, `dropcap`, `raised`, `spans` and
  `separator` are each named after a step of spec 0019, and each was built
  for one to four named pages. The probe found two of them, `raised` and
  `spans`, misfiring on new pages (§3).

---

## 2. Is recent work overfit? What the repository shows

Measured on `99110c2` today.

| measure | value | what it says |
|---|---|---|
| tuned module-level constants | **265** | thresholds and slacks, each set while looking at specific pages |
| lines in `src/` that name a corpus page | **≈ 810** | rules are justified by the page they were fitted on |
| lines in `tests/` that name a corpus page | **≈ 575** | tests pin page-specific behaviour |
| lines in `src/` naming the six "held-out" pages | **≈ 190** | the held-out set is in the code |
| specs focused on held-out pages | 0013 (certificate, pricing, ticket), 0015 (ticket, certificate), 0016 (ticket), 0018 (the ticket's banner); 0019's targeted pages include four of the six | **the held-out set has been a development set since 2026-10-14** |
| spec 0016 §1's own table | of its 8 rules, **6 fire on the ticket only**, 1 moves five pages, and 1 changes nothing elsewhere | most new rules have one page behind them |

**Why the loop produces this (no fault of any one step).** Each step goes
the same way. Look at 21 sheets, name a fault on a page, write a rule, and
keep it if no page gets worse.

- **"No page worse" cannot tell a general rule from a page fix.** A rule that
  fires on one page and stays silent on 20 always passes it.
- **The gates are tuned until the rule fires where it should.** Spec 0016 §1
  says so plainly: "The gates were chosen while checking which pages fire".
- **The corpus is both training set and test set.** That is curve-fitting in
  the plain sense. With enough free constants, any 21 points can be passed
  through.

**ELI5.** Twenty-one students sit the same exam every week, and the teacher
rewrites the lessons after each sitting to fix the questions they got wrong.
Scores rise. Whether a new student would pass is a different question, and
nothing in the loop asks it.

---

## 3. The probe: ten pages it has never seen

**How it was taken.**

- **Pages.** Ten written today, each a kind the corpus lacks: payslip, lab
  report, nutrition label, recipe card, board minutes, event flyer, quiz
  sheet, product datasheet, contract and printed email. They are clean
  screenshots, 500–940 px wide, made the corpus's own way.
- **Conversion.** At `99110c2` with the shipped defaults, one `Conversion`
  per page, making the calls a sweep makes. Scored by the report's scorer,
  with one sheet per page.
- **To look:** open
  [`level-up-probe/out/report.html`](level-up-probe/out/report.html),
  which shows all ten sheets on one page with the notes. The sources, the
  notes, the scripts and every output are committed in
  [`level-up-probe/`](level-up-probe/README.md).
- **Caveat.** An LLM (Claude) wrote these pages, as it wrote the corpus.
  Real documents will be harder, so read this as the smallest the gap can
  be.

### 3.1 Page by page, by eye against the source

| page | the worst faults (stage) | words lost |
|---|---|---|
| payslip | the `Gross pay` row falls out of its table (layout: the box ends a row early); the year-to-date table is flattened into one line of text; the summary boxes lose their frame; `PAYSLLIP` is printed above `PAYSLIP` (caption) | 0 |
| lab report | four results move into the Flag column, so every word is present and the table means something else (extract); label-over-value fields are set side by side; `NP-2291` → `NP-229 I` | 1 |
| nutrition label | the big `230` is drawn as an inverted picture at the bottom (layout); the footnote is printed twice, the copy corrupted (`The %s Daily Value (DV) told you…`); sub-rows lose their indent; the thick bars become thin rules | 0 |
| recipe | the two columns are cut into 14 Zones in 10 Bands and interleaved; the method steps become bullets with their numbers inline, one inside the ingredients list (layout); a truncated title `METH`; `SERVES 4` loses its `4` | 0\* |
| minutes | `Chair: Margaret Ellison` is lost (extract, pairs); the action table's row numbers are drawn as superscripts (spec 0019's raised-mark rule misfiring) | 1 |
| flyer | the orange top band is read as the word `The`, twice (the ticket's halo fault, on a new page); the pill button is drawn as a full-width band; a stray bullet; italics the page does not use | 0 |
| quiz | the fill-in table's empty cells are merged into spans (spec 0019's span rule misfiring); the equation breaks into `H2 H2 / O2 O2 / H2O`; the answer circles come back as `O`, as bullets, or not at all | 0 |
| datasheet | the feature list beside the spec table is cut into one Zone per line, and five items land under the table, leaving a hole (layout; the recipe's fault again) | 0 |
| contract | the two signature columns collapse into one: `For the Provider`, its column and every rule are gone, and two labels are printed over each other; clauses 1.2 and 1.3 become bullets | 0\* |
| email | the attachment chips collide; otherwise faithful | 0 |

\* A word was lost that `vanished` cannot see. It is printed elsewhere on
the page, and `vanished` is a set.

### 3.2 Against the tuned pages: same day, same judge, same criterion

The criterion is **a structural fault**: a fault that changes how the page
reads. That means a table cell in the wrong column, a row out of its
table, columns interleaved, or a block lost, merged or invented.

| | six of the 21, drawn at random | the ten unseen |
|---|---|---|
| pages with a structural fault | **0 of 6** (form, invoice_0001, receipt, sample_table, statement, timetable) | **9 of 10** (all but the email) |
| other faults seen | a misread footer word (form), one digit short (receipt), looks | looks, misreads |

The scorer, the same day (recorded, not the argument):

| set | pages | pages losing no word | words lost | words invented | tau | mean height error |
|---|---|---|---|---|---|---|
| all 21 (S14, re-derived today) | 21 | 14 | 15 | 24 | 0.984 | 0.062 |
| the ten unseen | 10 | 7 | 5 | 32 | 0.942 | 0.160 |

0 of 6 against 9 of 10 is a gap large enough to show on 16 pages (Fisher's
exact test, p < 0.001). A small gap would not show at all.

### 3.3 What it says

- **The words come through.** On unseen pages, words are lost no more
  often than on tuned ones. The general VLM reads unfamiliar pages well,
  and that is the learned part doing its job.
- **Structure does not.** Nine of ten pages break somewhere between the
  picture and the IR. The layout stage cuts a table short, merges a table
  with its neighbour, interleaves two columns, or splits a list into one
  Zone per line. Pairs lose a member, and a table's cells shift. These are
  the hand-set stages.
- **Rules fitted on the 21 misfire on new pages.** The raised-mark rule
  hits table row numbers, the span rule hits a table left empty on
  purpose, and the italics rule fires where the page has none. Faults
  fixed for one corpus page come back on others: the flyer's `The` is the
  ticket's halo, and its button drawn as a band is pricing's.
- **The content check has blind spots that matter at scale.** Shifted
  cells, a lost `4` and a lost heading are all invisible to `vanished`. The
  cell check (§4.5) and the judge are not optional.
- **Faults follow phenomena, not document types.** A column of short lines
  beside a taller block breaks both the recipe and the datasheet. Empty
  table cells break both the lab report and the quiz. That is what the
  taxonomy's tags count (§4.7).
- **Cost.** 4.9 to 14 minutes a page (mean 8.2), on 4 to 28 Zones. The
  quiz's 28 Zones took 14 minutes.

### 3.4 GLM-OCR, a taste — not a decision

GLM-OCR (0.9B; `glm-ocr:q8_0` on Ollama; 2.5 GB, wholly on the M1's GPU)
read the same ten pictures. One prompt per call, temperature 0, scored
with the project's tokenizer.

| arm | seconds a page | words lost | structure returned |
|---|---|---|---|
| today's pipeline | 292–838 (mean 493) | 1 word each on 2 pages, plus 2 hidden (§3.1) | IR, then styled HTML, with §3.1's faults |
| GLM-OCR, whole page, `Text Recognition:` | 4–10 (mean 7.5) | a line each on 2 pages: the quiz's `Total: ___ / 10`, the email's top bar; one misread (`POE` → `P0E`) | plain lines only |
| GLM-OCR on today's Zones, `Table Recognition:` on tables | 3–10 | where a Zone holds a table *and* something else, the table prompt returns only the table: the lab report's patient box (22 words) is dropped | HTML tables with a header row and spanning section rows; the quiz's equation as correct LaTeX |

- **Reading.** A 0.9B document model reads these pages about as completely
  as the whole pipeline does, and about 65 times faster.
- **Not a drop-in for today's Zones.** Asked for a table, it returns the
  table only. It needs a layout step that hands it one kind of block at a
  time: its own (PP-DocLayoutV3) or a better one. That makes it D2, not D1
  (§5).
- **The hardest table beats it too.** The lab report's Result and Flag
  columns confuse it just as they confuse qwen3-vl:4b.
- **It changes Q1's arithmetic.** At about 10 s a page to read, a
  1000-page pool takes hours, not days, if a parser-first pipeline holds
  up (§4.5).

---

## 4. Q1 — the test set

### 4.1 Recommendation

**Build a generated corpus of the order of 1000 pages from a taxonomy, and
use it as three pools, never as one.** Start at 600 pages, 200 per pool,
about 100 of them real PDFs (Alessandro, 2026-10-24). Grow to ~1000 once
the generator's pages look varied enough. The 21 existing pages and the
ten probe pages join the dev pool. Keep clean screenshots, as
you said; picture-level difficulty stays a separate preprocessing track.

### 4.2 Why 5–10 more pages does not help

**The arithmetic.** Say a step is judged by the share of pages it makes
better (or the share that look right). How far off can that share be, by
chance alone, on n pages? Below is the 95% margin when the share is near
half:

| pages | ± margin | |
|---|---|---|
| 21 | ±21 points | today |
| 31 | ±18 | today + 10 |
| 50 | ±14 | |
| 100 | ±10 | |
| 200 | ±7 | one panel |
| 300 | ±6 | |
| 1000 | ±3 | |

Ten more pages buy about 4 points. A panel of 200 buys about 14.

**A worked example.** Suppose a change makes 1 page in 10 better and 1 in 50
worse.

- **On 21 pages** you expect about 2 better and 0 or 1 worse. That is
  indistinguishable from a change that does nothing.
- **On 100 pages** you expect about 10 better and 2 worse. A sign test puts
  that at p ≈ 0.02, which is a real result.

**Absorption.** A page that is looked at every step becomes a page that is
tuned on. The six added on 2026-10-13 were held out for one day.

**Support per fault class.** With 21 pages, most kinds of fault (cells that
span, a total row, a label printed over its value) have one or two
instances. A rule then has one or two pages behind it, which is the spec
0016 table. With 1000 tagged pages, every kind of fault in the taxonomy has
dozens.

### 4.3 Three pools — what each is for

| pool | size to start | who looks | used for |
|---|---|---|---|
| **dev** | 200 + the 31 | anyone, page by page | diagnosing faults, prototyping a rule, by-eye work as today |
| **panel** | 200, fixed | aggregates by default; single pages only as a sampled audit | deciding: does a change ship? Same pages before and after |
| **vault** | 200 | nobody, until a milestone | the honest number: how does it do on pages nobody has tuned on? Once opened, it joins dev and a fresh vault is generated |

**ELI5 of the vault.** It is the sealed exam paper. You may practise on
anything else, but you sit this one only when you claim a level, and once
it has been seen it is a practice paper.

### 4.4 Fixed panels, not fresh random draws per run

Your "random subselection" is right for building each pool. To decide a
change, though, **compare the same pages before and after** (a paired
comparison). If each run draws a new random sample, every comparison
carries the noise of two different samples. That noise is larger than most
single steps.

- **Sampling.** Draw the panel stratified, so that every category and every
  phenomenon in the taxonomy (§4.7) has its quota.
- **Refreshing.** Draw a new panel at each milestone, so it does not slowly
  become a tuning set too.

### 4.5 What it costs

Conversion is the binding cost. Today a page takes **4.9 to 14 minutes
(mean 8.2)** on this machine, measured on the probe.

| what | pages | conversion today | downstream change, offline |
|---|---|---|---|
| today's sweep | 21 | about 2½ h | about 5 min (rederive + score) |
| one panel | 200 | **about 27 h** | about 50 min |
| the full pool, at a milestone | 1000 | **about 5½ days** | about 4 h |
| for scale: reading alone with a ~1B parser (§3.4) | 1000 | about 2 h for the reading; the rest of a parser-first conversion is unmeasured until P1 | — |

**At 200 pages, a panel conversion with today's pipeline takes more than a
day.** That is why the honest baseline (L3) runs on 30–40 pages (decision
1), and one reason the PoC matters: its reader alone is about 65 times
faster.

The rule that keeps this affordable: **a model-side change costs one panel
conversion, and anything downstream of the model costs a replay.** That
second loop is what the project already has (`rederive.py`,
`replay_run.py`). Its per-page cost measured today is about 6 s to re-derive
and about 8 s to score.

**Review cost is the second constraint.** Nobody can open 100 sheets per
step. On the panel:

- the content checks are automatic and already trusted: `vanished`,
  invented words, broken joins;
- **a cell check is needed on top.** The probe's lab report keeps every word
  while four results move into the Flag column (§3), and `vanished` cannot
  see that. On generated pages both sides are HTML, so "each source cell's
  words sit in the same row and column of the output" is derivable;
- the rest needs the **review** (§4.9): Claude, by the criteria agreed on
  2026-10-24, on the pages the checks flag and a sample. You check every
  page it calls worse, plus two at random.

That is why L2 evolves the review skill together with the panel (§6).

### 4.6 Where the pages come from

| source | ground truth | realism | cost | role |
|---|---|---|---|---|
| **generated HTML** from the taxonomy: an LLM writes each page from a spec card (category + phenomena + style family + width); several generators and template families so no single author's style dominates | the HTML, exactly as today | synthetic | small. Only text prompts leave the machine, never images | **the bulk: dev, panel, vault** |
| **real born-digital PDFs**: [DocLayNet](https://huggingface.co/datasets/docling-project/DocLayNet) (80,863 pages, 6 categories, CDLA-Permissive-1.0); [SafeDocs CC-MAIN-2021-31](https://digitalcorpora.org/cc-main-2021-31-pdf-untruncated/) (about 8 million real PDFs from the web) | the PDF's own text layer: every word, its box, size and weight. Needs a `project()` for PDFs | real | one new module; licensing to check per source | **a 10–20% slice of each pool**, the guard against an LLM-authored style |
| external yardsticks: [OmniDocBench](https://huggingface.co/datasets/opendatalab/OmniDocBench) (981 PDF pages, 9 types); [Design2Code](https://arxiv.org/abs/2403.03163) (484 real web pages) | their own annotations | real | reading their formats | occasional comparison with published systems, not the main loop |

**A real PDF page joins only if its ground truth holds** (decision 3): it is
converted to HTML, and admitted only if that HTML **re-renders to the
PDF's own picture** and its text **matches the PDF's text layer**. That is
the invariant the corpus already enforces (`TestTheCorpusPictureIsItsOwnHTML`),
so the existing scorer works on it unchanged. A page that fails is
dropped, never patched by hand.

**Generated pages pass a validator before they count**:

- the screenshot renders;
- the page scores perfectly against itself (`shoot_corpus.py --check`);
- every word the DOM holds has ink under it (the newsletter's lesson);
- no external resources;
- no near-duplicate already in the pool.

### 4.7 The variability — agreed 2026-10-24 (L1a)

**Agreed with Alessandro on 2026-10-24.** His answers are table 3; the
rest of the proposal stands.

**Drawn at random, inside chosen bounds.**

- **A card per page.** Each page is written from a card: a kind (table 1),
  3–6 features (table 2), a style family, a width and a language.
- **Cards are drawn at random** inside each family's quota (table 3). A
  coverage check then tops up any feature with too few pages: each
  feature must appear on several pages **in at least three different
  kinds**, so that a fault can be pinned on the feature rather than on
  the kind.
- **Pools are split at random**, stratified by family, so dev, panel and
  vault share one mix.
- **ELI5.** A driving test does not use random streets. Its route passes
  every kind of junction a few times, in different neighbourhoods; which
  street serves each junction can be left to chance.

**Table 1 — kinds.** They decide what gets written and how results are
reported. They never reach the converter, so ADR 0001 (no document types)
stands. The 31 dev pages already touch every family, two to six pages
each (in brackets).

| family | kinds (examples) |
|---|---|
| transactional | invoice, **receipt**, statement, payslip, purchase order, utility bill, packing slip (invoice ×2, receipt, statement, payslip) |
| forms | application, numbered-box tax-style form, questionnaire, patient intake form, exam sheet, checklist (form, quiz) |
| correspondence and legal | letter, memo, email printout, notice, contract, referral letter (letter, email, contract) |
| reports | corporate report page, lab report, minutes, inspection report; **clinical: a doctor's visit note, a discharge summary, a prescription, laid out as tables and fields** (report, lab report, minutes) |
| publishing | newsletter, magazine page, paper page, textbook page, manual page, recipe, FAQ (newsletter, paper, recipe, two samples) |
| reference | catalogue, price list, menu, timetable, calendar, datasheet, nutrition label (catalogue, menu, timetable, datasheet, nutrition, a table sample) |
| credentials | CV, certificate, ticket, invitation (cv, certificate, ticket) |
| presentation | slide, flyer, pricing page, brochure panel (darkdeck, pricing, flyer) |

**Table 2 — features, and why each is in** (the probe page that broke on
it, §3.1). Faults are counted per feature.

| axis | values | why |
|---|---|---|
| arrangement | one column, two or three columns, a sidebar, a cards grid, framed panels side by side, centred | recipe, datasheet, contract |
| tables | ruled grid, spanning cells, section rows, totals, **empty cells**, zebra stripes, indented sub-rows, long | lab report, quiz, payslip, nutrition |
| key–value | inline, label over value, two pairs per line, leader dots, boxed | minutes, lab report, payslip |
| lists and numbering | bullets, numbers, nested, ✓/✗ and tick boxes, hanging clause numbers, big step numbers | recipe, quiz, contract |
| text | justified, footnotes, superscripts and subscripts, formulas, quotes, drop caps | quiz, nutrition |
| looks | sans, serif, mono, script and display faces; small caps; weights; colours; a dark ground; bands, chips, buttons, dashed or double rules | flyer, nutrition, email |
| figures | logos, charts, barcodes, signatures, photos | none in the probe |
| size and density | 500–1200 px wide; a sparse flyer to a dense statement | quiz (28 Zones) |
| language and formats | English, Italian, French, Spanish, Portuguese: accents, apostrophes, guillemets; number, date and currency formats (`1.234,56 €`, `24/10/2026`) | lab report (`NP-2291`), datasheet (part numbers) |
| authoring style | hand-written CSS, framework-like classes, table-based legacy HTML, print-like (from a PDF) | so no single author's habits become the corpus |

**ELI5 of features.** A sentence like "the converter gets table totals
wrong on 14 of the 31 pages that have one" is a fault class with evidence.
"The ticket looks wrong" is one page.

**Table 3 — agreed, Alessandro, 2026-10-24:**

| # | question | agreed |
|---|---|---|
| 1 | **Weights** | The eight families, none under 10%, tilted toward forms, receipts and doctors' notes laid out like tables, with variety kept. Of 600: forms 100, transactional 100 (receipts about 40), reports 100 (clinical notes about 40), the other five families 60 each |
| 2 | **Languages** | English, Italian, French and the other Latin languages (Spanish, Portuguese). No Greek, Cyrillic, CJK or right-to-left for now. Share proposed: English about three quarters; Italian and French about 50 pages each; Spanish and Portuguese about 25 each |
| 3 | **Figures** | In, as pictures carried over (logo, chart, barcode, signature, photo). The words inside a chart are not asked for |
| 4 | **Pages** | One page per document. Multi-page later |
| 5 | **Real PDFs** | About 100 of the 600, about 33 per pool: public pages with a text layer (government forms, annual-report pages, manuals, papers). Each one admitted only through the §4.6 gate, so none misleads development. They count toward their family's quota |
| 6 | **First batch** | 600 pages: 200 dev, 200 panel, 200 vault, cards drawn at random inside the quotas |

### 4.8 Picture-level difficulty stays out — agreed

It is a preprocessing question, and mixing it in muddies every conversion
measurement. `rectify` and the twins stay their own track, as today. One
consequence: `ticket_0020` is a *photographed* card (turned 1.5° on a desk).
Keep it in dev, out of any panel.

### 4.9 The judge — Claude, held to your criteria

**Decided 2026-10-24.** The judge is Claude, using the visual-review
skill, evolved in L2 after the corpus is built. It is not a local model.
**What it judges by** was agreed in five rounds of questions and lives in
[`agents/review-criteria.md`](agents/review-criteria.md): the render must
look like the page; never guess; every line breaks where printed; net gain
ships; and a severity for each kind of fault.

**ELI5.** An examiner who marks to your scheme. You re-mark every paper it
fails and two at random; where you disagree, the scheme changes.

**Why the panel needs one.** Nobody can open 200 sheets at every step.
Words are already checked automatically and exactly: `vanished`, invented
words, broken joins. Arrangement and looks are not. The probe's lab report
kept every word while four results moved into the Flag column (§3.1), and
an earlier measure called a page whose table had lost all five headers a
full match.

**Two layers, the exact one first.**

| layer | what it checks | how |
|---|---|---|
| **derived checks**, no model | words; each table cell in its row and column (the cell check); tables, lists and headings kept as such; reading order | against the source HTML, which every corpus page has, real PDFs included (§4.6) |
| **the review** | what the HTML cannot settle: lines and wraps, what sits beside what, frames and fills, type, alignment | Claude, looking at the sheets, by the criteria |

**How a review runs:**

1. The derived checks flag pages.
2. Claude looks at every flagged page, every page a change moved, and a
   sample per family: two-panel sheets, zoomed tiles for dense pages, and a
   highlight of where two renders differ.
3. Each fault is recorded with its feature (§4.7, table 2), the stage that
   caused it, its severity and the element.
4. A ranked roll-up: majors first, then the biggest visible gain for the
   effort, with the reasoning.
5. Alessandro checks every page called worse, plus two at random, on one
   private page with agree buttons. His calls are saved and read back to
   calibrate.

**What the skill has today, and lacks** — from running it on 2026-10-24
(S13 against S14 on three corpus pages; two probe pages against their
sources):

- **has:** sheets at the source's width, pairwise, notes that name the
  element; it catches what the numbers cannot (the lab report's shifted
  results: reading order 1.000; the recipe's interleaved steps: no word
  lost);
- **lacks:** fault classes and stages, so nothing adds up to what to fix
  next; axes that fit the criteria (structure is scattered across three,
  and type and rhythm fire "minor" everywhere); zoom on dense sheets (the
  ticket's six panels reach the reader at half size); a highlight of what
  changed; sampling for 200 pages; a form for the source-only mode. Its
  `owner` field points at phases closed in September, and `numbers.md`'s
  table is malformed.

**Guards** (`future-ideas.md` §10): the reviewer does not read with the
converter's own engine; it never supplies content (ADR 0004); its
agreement with Alessandro is measured, not assumed.

**What waits.** The rest of `future-ideas.md` (judge-led development, a
case memory, per-page fitting, promoting choices into rules) comes only
after the review has earned trust on the panel.

---

## 5. Q2 — architecture

### 5.1 "One pipeline for everything" is not the problem

ADR 0001 (no document types) holds up. A converter that routes by type is
only as general as the types written for it, and each type's pipeline would
be tuned on a fraction of an already small corpus. The probe (§3) agrees:
its faults follow phenomena (a total row, a small table, a frame), not
document types.

**The problem is where the pipeline's decisions come from.**

- The learned parts (detector, VLM, tesseract) generalise from millions of
  pages.
- The hand-set parts (about 14,500 lines, 265 constants) generalise only as
  far as the assumptions their thresholds were set on. Those were 21 pages,
  and usually one.

**The field converged on our pipeline's shape.** MinerU2.5 and PaddleOCR-VL
are both described by their authors as *layout first, then each region read
at full resolution*. That is exactly `heron`'s Zones followed by per-Zone
crops here. The difference is the middle:

- **theirs** is learned end to end on millions of pages;
- **ours** is a learned detector and a general VLM, with about 14,500 lines
  of hand-written rules between and after them.

### 5.2 Options

| # | option | where its generality would come from | verdict |
|---|---|---|---|
| — | today: a rule per fault, written while looking at the page | the 21 pages | stop as the main loop; keep it as the dev-pool workshop |
| A | per-document-type pipelines | the types someone writes | **no.** Reverses ADR 0001, splits the data, and adds a classifier to get wrong |
| B | `future-ideas.md` A: layout proposals judged per page | the judge | not yet; as that file says, only if the leftover faults demand it |
| C | `future-ideas.md` D: a judge that accepts, points, remembers and promotes | the judge's calibration against your calls | **yes, its stage 1 (the judge) as the panel's instrument.** Memory and promotion come later, and need the panel to show transfer |
| D1 | **reader swap**: a document parser reads each of today's Zones in place of qwen3-vl:4b, and every other pass stays | the parser's training, for reading only | **a control arm of the PoC, not the plan.** It leaves the hand-set middle in place, and the probe's structural faults are in that middle. The taste test shows it is not a drop-in either: with today's Zones, a table prompt drops whatever in the Zone is not the table (§3.4) |
| **D2** | **parser first**: the parser produces layout, reading order and per-block content with boxes; an adapter maps its blocks into the IR; then today's style measurement and renderer draw it (§5.3) | the parser's training, for content *and* structure | **yes: the main direction to explore, as a PoC on its own branch (P1).** The probe's faults sit in the stages D2 replaces, and the taste test read the pages completely at about 7.5 s each |
| D3 | a parser as an **extra check** only: an independent reading of the source to compare the render's words against | the parser's training, for the check | **yes, as the judge's reader.** It is how the judge reads a real picture that has no HTML. It must not be the converter's own reader (§5.3) |
| E | **fit, don't set**: thresholds and small classifiers fitted on the generated corpus, with labels read from its HTML | hundreds of labelled pages per decision | **yes, after L1–L3**, for whatever D2 leaves hand-set |
| F | end-to-end screenshot → HTML by a large VLM | the model's training | **no** as the main path: it is not local, and text fidelity is the known weakness (`future-ideas.md` §12). Perhaps as a reference arm on the panel, if images may leave the machine |

### 5.3 Parser first — the PoC

```
picture ─► document parser ─► blocks: box · category · reading order · content
           (GLM-OCR + a layout       (text, title, table as HTML, list, formula,
            model, PaddleOCR-VL,       figure, header/footer)
            or MinerU2.5)                     │
                                              ▼  adapter (new, small)
                                    IR: Zones, Blocks, Cells, with boxes
                                              │
                    ┌─────────────────────────┴──────────────────────────┐
                    ▼ kept from today                                    ▼ kept from today
          style record, furniture, looks                  semantic renderer, the trace,
          (measured from pixels, ADR 0005)                the content checks
                                              │
                                              ▼
                                            HTML
```

**What the parser takes over**:

- the layout groups;
- the Kinds;
- the reading order;
- table structure, including spans;
- formulas, superscripts, display lines;
- most of locate's line placement.

Those stages hold **63** of the 265 tuned constants: detector
post-processing, structure, rhythm, locate, spans, raised, display, drop
caps, separators and the orchestrator.

**What stays ours**: everything that makes the render look like the page.
That is the style record, fills, rules, frames, chips and type sizes, all
measured from pixels, plus the renderer. No parser does this; they emit
markdown or JSON, not a look. That side holds **135** of the constants
(style, looks, furniture, furnish, fields, render). Rectify holds 36 and
measurement 31.

**So the two directions are complements, not alternatives.** Parser-first
(D2) takes the content and structure side off hand-set rules. Fit, don't
set (E) is what the looks side needs, because no parser will ever measure
a page's chips and type sizes for us.

**Why the IR, and not markdown, is the join.** Markdown keeps the words
and drops where they sit. Without boxes there is nothing to measure a
block's look from, and nothing to put two blocks side by side with. So the
adapter keeps each block's box.

**Risks to measure, not assume**:

| risk | what to look at |
|---|---|
| parsers are trained mostly on reports, papers and forms, not on designed pages (cards, tickets, flyers) | the probe's flyer and quiz, the corpus's ticket, pricing and catalogue |
| no "pairs" Kind: a label and its value arrive as text lines | rebuild pairs from the boxes, or keep one VLM question for it |
| side-by-side panels read as one column | the probe's payslip, recipe and datasheet |
| VLM parsers can loop or invent text | `invented`, not only `vanished` |
| licences | GLM-OCR MIT, its layout model PP-DocLayoutV3 Apache-2.0; check the others before use |
| one instrument on both sides | if the converter reads with a parser, the judge reads with another engine (D3), or the two agree while both are wrong (`future-ideas.md` §10) |

**The PoC plan (P1), after L1 (decision 2).**

- **Where.** Branch `poc-parser-first` from `develop`.
- **The parser.** GLM-OCR's **own entire pipeline at its latest version**:
  the `glmocr` SDK, its PP-DocLayoutV3 layout and its reader, served
  locally by Ollama (§8). No piece of today's layout is fed into it.
- **Arms**, measured on the same pages:
  1. today;
  2. D2, the GLM-OCR pipeline, then the adapter, then our looks and
     render.
  - D1 (today's Zones read by GLM-OCR) only if D2's result needs telling
    apart: is the gain in GLM-OCR's layout, or in its reading?
- **Pages.** The corpus's dev pool and the limited baseline set (L3). The
  21 and the ten probe pages are among them.
- **Measures.** Content (`vanished`, `invented`), the cell check, tables
  kept as tables, reading order, seconds per page, and a by-eye verdict
  per page.
- **What we iterate on.** The adapter (parser blocks → IR) and the looks
  side, never the parser's weights. It is today's loop, run on a craftsman
  trained elsewhere instead of on hand-made tools.

### 5.4 Labels for free — why E is cheap here

The source HTML of every generated page already states what the pipeline
now guesses with hand-set thresholds:

| decision made today by a hand-set rule | the label in the source HTML |
|---|---|
| bold or regular (spec 0019 C2) | computed `font-weight` of the element |
| heading level, display line | element and computed font size |
| cells that span (B1) | `colspan` / `rowspan`, or grid placement |
| a chip or badge (C1, C3) | an element with a background and border-radius |
| alignment, centring | computed `text-align` and the element box |
| label over value or beside it | the boxes of the two elements |
| table, pairs, list or prose | the elements themselves |

`project()` already reads computed styles and boxes off the browser. A
fitted threshold, or a 1,000-sample logistic regression, set on dev and
accepted on the panel, replaces a constant chosen while looking at one
page. The style is still measured from pixels (ADR 0005); only the cut-off
is learned.

### 5.5 What stays

The IR, the semantic renderer, style measured from pixels, the content
ratchet, determinism and replay, the trace and the review tooling. The
pipeline's shape stays too: layout, then each region read, then measure,
then render. What changes is which stages are learned components, and how
the remaining constants get their values.

---

## 6. Sequence

In order, as decided 2026-10-24 (§8).

| step | branch | what | done when | stop if | cost |
|---|---|---|---|---|---|
| **L0** | — | `develop` cut from `scaffold`, `level-up` from it, everything pushed, `scaffold` retired | **done 2026-10-24** | — | — |
| **L1a** | `level-up` | **agree the variability** (§4.7): which kinds, features, languages and weights the corpus covers | **done 2026-10-24**: §4.7, table 3 | — | — |
| **L1b** | `level-up` | **corpus factory**, [spec 0020](specs/0020-the-corpus.md), issue #43: taxonomy file, spec cards, generator, validator, and a real-PDF gate (§4.6); 600 pages from cards drawn at random inside the quotas and topped up for coverage, about 100 of them real PDFs; split 200 / 200 / 200 into dev / panel / vault; the 21 and the ten probe pages join dev | **done 2026-10-30**: 631 pages, every one passing; 573 generated (130 of them parts of a document, Alessandro 2026-10-27), **27** real PDF pages (he stopped them there), the 31 in dev; every feature on ≥ 11 pages in ≥ 7 kinds and ≥ 2 per pool; `corpus/manifest.json`, the vault sealed in `doc_to_html.corpus` | a contact sheet of 50 looks like one author → add generators or templates first | about 6 writer-hours of Sonnet, 103–137k tokens per ten pages |
| **L2** | `level-up` | **panel measurement**, spec 0021, **next**, run from spec 0020's last handover prompt; outlined in spec 0020's "What comes after": batch conversion; a per-category and per-tag report (vanished, invented, the cell check, order); the derived checks, and the review skill evolved to the agreed criteria (§4.9): faults tagged by feature and stage, zoomed tiles, a highlight of what changed, the ranked roll-up, the page with agree buttons | one command, one report | your spot-checks keep overturning the review → change the checklist before relying on it | per run, the pages chosen |
| **L3** | `level-up` | **honest baseline as a task on a limited set** (decision 1): a fixed subset chosen so that every key tag appears a few times, e.g. 30–40 pages (about 4–5 h today); fault classes ranked by pages touched | one command; a ranked table | — | about 4–5 h |
| **P1** | `poc-parser-first` | **GLM-OCR parser-first PoC** (§5.3): its latest full pipeline, then the adapter, then our looks and render; against today's on the dev pool and L3's set | by-eye sheets, content and cell checks per page | the parser loses content that today keeps, on most pages → park it and write down why | about a week of building |
| **P2** | both | **decision**: the PoC against today's on L3's set, by fault-class rates | a decision | no gain → keep today's, go to L5 | one run per arm |
| **L5** | the winner | **fit instead of set** for what the winner still decides with constants: labels from dev HTML, accepted on the panel, confirmed on the vault at a milestone | the vault improves | panel up but vault flat → that is fitting the panel; refresh it | days |

L1–L3 change no conversion code, and L3 is the first number on pages
nobody has tuned on.

---

## 7. Working rules that would change

| today | proposed |
|---|---|
| a rule ships if no page of 21 gets worse | **net gain ships** (agreed 2026-10-24): a change that makes more pages of the panel better than worse ships, content included, and every worse page is named and goes next in line. A rule that fires on one page is a page fix, kept only if it costs nothing |
| faults are found by opening 21 sheets | faults are found in the panel report, by tag; sheets are opened on dev pages with the same tag |
| every step judged by eye on all 21 | the derived checks pre-screen the panel and Claude reviews by the agreed criteria; you check every page called worse, plus two at random |
| "held out" pages are looked at and fixed | the vault is opened only at a milestone, then retired into dev |
| a sweep is the unit of measurement | a panel conversion is the unit for model-side changes; a replay is the unit for everything downstream |

---

## 8. Decisions — Alessandro, 2026-10-24

| # | asked | decided |
|---|---|---|
| 1 | corpus track L1–L3 next? | **Yes: build the corpus properly.** The honest baseline (L3) is a task run on a **limited number of documents**, to bound runtime. Conversion time is dealt with separately |
| 2 | PoC alongside or after? | **After L1 is in place.** Then a workflow built on GLM-OCR, using **its latest version and its own entire architecture** (layout model and reader), not our Zones fed to its reader |
| 3 | who writes the pages? | **Claude writes most of them.** Real PDFs too, but **only where their ground truth is trustworthy**, so they never mislead development (§4.6) |
| 4 | the 21? | **They join the corpus as dev pages**, with the ten probe pages, all with a known render and HTML; the corpus grows from there |
| 5 | models? | **Local only, for now** |
| 6 | backup? | **Push, and tidy git** with every result and this review: done 2026-10-24. `main`, `develop` and `level-up` are on the remote; `scaffold` is retired into `develop` |

**The variability, agreed the same day** (§4.7, table 3): the eight
families, tilted toward forms, receipts and doctors' notes laid out like
tables; English, Italian, French and the other Latin languages; figures
in; one page per document; a first batch of 600, 200 per pool, about 100
of them real PDFs that must not mislead; cards drawn at random inside
those bounds.

**The review criteria, agreed the same day** in five rounds of questions
([`agents/review-criteria.md`](agents/review-criteria.md)):

- Claude is the judge, with the review skill; it evolves in L2, after the
  corpus;
- the render must look like the page, and among look-alikes the simplest
  fitting HTML wins;
- never guess: a word two readers disagree on is drawn as an "unread" box;
- a fixed page, every line breaking where printed, by explicit line ends;
- net gain ships, content included, every worse page named;
- he checks every page called worse plus two at random, on a page with
  agree buttons.

**GLM-OCR, as of 2026-10-24** (re-check at P1's start):

- **SDK:** `glmocr` 0.1.5 (PyPI, 2026-04-08), installed with
  `pip install "glmocr[selfhosted]"`.
- **Layout:** PP-DocLayoutV3, which runs on torch and can be put on the
  CPU with `--layout-device cpu`.
- **Reader:** parallel recognition per region; the output is Markdown plus
  JSON with each region's box and label.
- **Local serving:** Ollama, `pipeline.maas.enabled: false`, and `ocr_api`
  set to `localhost:11434/api/generate`, `api_mode: ollama_generate`,
  `model: glm-ocr:latest`.
- **Licences:** code Apache-2.0, model MIT, layout model Apache-2.0.
- **Taste test.** It used `glm-ocr:q8_0` with the reader alone; the PoC
  uses `latest` and the whole pipeline.

---

## 9. Sources

- This investigation's probe: [`level-up-probe/`](level-up-probe/README.md)
  holds the ten sources, the by-eye notes, the scripts and the outputs,
  with [`out/report.html`](level-up-probe/out/report.html) as the page to
  open
- [OmniDocBench, CVPR 2025](https://arxiv.org/abs/2412.07626): 981 pages, 9 document types
- [DocLayNet](https://arxiv.org/abs/2206.01062): 80,863 pages, 6 categories
- [SafeDocs CC-MAIN-2021-31-PDF-UNTRUNCATED](https://digitalcorpora.org/cc-main-2021-31-pdf-untruncated/): about 8 million real PDFs
- [Design2Code](https://arxiv.org/abs/2403.03163) and [WebSight](https://huggingface.co/blog/websight): screenshot-to-HTML benchmark and dataset
- [PaddleOCR-VL](https://arxiv.org/abs/2510.14528), [PaddleOCR-VL-1.5](https://arxiv.org/abs/2601.21957), [MinerU2.5](https://arxiv.org/abs/2509.22186), [GLM-OCR on Ollama](https://ollama.com/library/glm-ocr), [GLM-OCR's repository](https://github.com/zai-org/GLM-OCR) and its [Ollama guide](https://github.com/zai-org/GLM-OCR/blob/main/examples/ollama-deploy/README.md), [`glmocr` on PyPI](https://pypi.org/project/glmocr/), [Granite-Docling](https://www.ibm.com/granite/docs/models/docling)
- In this repository: `docs/future-ideas.md` (the judge-led loop), ADRs 0001, 0003 and 0005, and spec 0016 §1
