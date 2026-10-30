# The corpus: 600 pages, chosen by their variability

**Status: done 2026-10-30, issue #43 closed.** 631 pages, every one
passing: 573 generated (130 of them parts), 27 real PDF pages, and the
31 we had. "Outcome — the corpus" is the record. **Next is L2, spec
0021**, from the handover prompt at the end.
- **This is step L1b** of the level-up plan
  ([`../level-up.md`](../level-up.md) §6), on branch `level-up`.
- **It is written to be run in a fresh chat.** Everything it needs is here
  or linked.
- **It builds** 600 new pages, each an HTML file and the picture converted
  from it, in three pools of 200: dev, panel and vault. About 100 of them
  are real PDF pages. It also writes cards for the 31 pages we already
  have, which join dev. *As built: 27 real PDF pages, and 130 of the 573
  generated pages are parts of a document, both Alessandro's choices,
  accepted 2026-10-30 ("Outcome — the corpus").*
- **It touches no conversion code and runs no conversion.** The converter
  meets these pages after this spec, in L2 and L3.

**Why.** Twenty-one pages cannot tell a general rule from a fix for one
page. Ten pages the pipeline had never seen showed a structural fault on
nine, against none on six tuned pages judged the same day
(`level-up.md` §3). Every later step is measured on this corpus: the
review skill, the honest baseline and the GLM-OCR PoC.

## Read first, in order

1. `CLAUDE.md`'s READ THIS FIRST.
2. [`../level-up.md`](../level-up.md): the Gist; §4, the test set (§4.6
   sources, §4.7 the variability as agreed); §8, the decisions.
3. [`../agents/review-criteria.md`](../agents/review-criteria.md): what
   matters in a conversion. The corpus is built so these criteria can be
   checked against it.
4. This spec, end to end.

## Alessandro's decisions, 2026-10-24

1. **Build the corpus properly, chosen by its variability**: "docs of
   interest, not fully random". Cards are drawn at random inside agreed
   bounds (`level-up.md` §4.7, table 3).
2. **Claude writes most pages.** Real PDFs too, but **only where their
   ground truth is trustworthy**, so they never mislead development.
3. **The 21 and the ten probe pages join the corpus as dev pages.**
4. **Local models only**, for conversion. Writing pages is Claude's job
   (decision 2).
5. **The first batch is 600 pages: 200 dev, 200 panel, 200 vault.** About
   100 of them are real PDF pages, about 33 per pool.
6. **Eight families**, tilted toward forms, receipts and doctors' notes
   laid out like tables, with variety kept. **Languages:** English,
   Italian, French and the other Latin languages (Spanish, Portuguese). No
   Greek, Cyrillic, CJK or right-to-left for now. **Figures are in**, and
   minor for now. **One page per document.**
7. **The review criteria** ([`review-criteria.md`](../agents/review-criteria.md))
   bind the ground truth. Every line of a page is the line the reader
   sees, and the words a reader sees are the words the scorer reads (§B).

## The numbers to hit

| family | pages | inside it | real PDFs, about |
|---|---|---|---|
| forms | 100 | | 30 |
| transactional | 100 | receipts, about 40 | 5 |
| reports | 100 | clinical notes, about 40: visit notes, discharge summaries, prescriptions, laid out as tables and fields | 30 |
| correspondence and legal | 60 | | 10 |
| publishing | 60 | | 15 |
| reference | 60 | | 10 |
| credentials | 60 | | 0 |
| presentation | 60 | | 0 |
| **total** | **600** | | **about 100** |

The PDF column is a proposal. The real sources decide it (§P), and a
family's PDF pages count toward its quota.

*As built, 2026-10-30:* 27 PDF pages (forms 9, reports 6, publishing 5,
reference 3, transactional 2, correspondence and legal 2). The family
totals held, because each unused PDF slot became a generated card of its
family. "Outcome — the corpus" has the counts.

| language | pages, about |
|---|---|
| English | 450 |
| Italian | 50 |
| French | 50 |
| Spanish | 25 |
| Portuguese | 25 |

The language shares were proposed on 2026-10-24 and not contested; step 0
confirms them. Each page uses its language's formats for numbers, dates
and currency (`1.234,56 €`, `24/10/2026`).

**Coverage, the rule that makes the corpus worth having:** every feature
id (§F) appears on **at least 9 pages, in at least 3 different kinds, and
at least 2 in each pool**. Only then can a fault be pinned on the feature
rather than on one page or one kind.

---

## How to work

- **Every page passes the validator (§V) before it counts.**
  - A generated page that fails is rewritten or dropped.
  - A PDF page's picture and text layer are **never edited**. Only its
    HTML twin is revised; a page whose twin cannot pass is dropped.
- **Look at contact sheets, not only at the validator's output.** The
  corpus has shipped a page that hid its own text (`newsletter_0008`,
  `CLAUDE.md`'s lessons), and nothing but a picture showed it.
- **Each step is its own commit, with its tests.**
- **Seeds are fixed and recorded.** Drawing the cards and dealing the pools
  are reproducible.
- **No conversion is run in this spec.** Nobody converts a vault page, or
  opens one's conversion, until a milestone (`level-up.md` §4.3).
- **Stop and ask Alessandro:**
  - at step 0's three decisions;
  - at the pilot's contact sheets (step 3);
  - before downloading any PDF source, with its licence (step 4);
  - if the coverage rule cannot be met.

**Facts as of 2026-10-24, to re-check at step 0:**
- 1394 tests pass (1 skipped), `mypy src/` clean, on `level-up`.
- The 21 corpus PNGs average 108 KB.
- No PDF library is installed in `.venv`, and poppler is absent;
  tesseract is at `/opt/homebrew/bin/tesseract`.
- Git LFS is not installed. PyYAML is not installed, so the taxonomy is
  JSON.
- `projection.project()` reads **text nodes only** (a `TreeWalker` over
  `SHOW_TEXT`). It reads SVG `<text>` too, and it reads neither `::before`
  / `::after` content nor list markers. The scorer folds case
  (`scoring.py`, `casefold`).

---

## Steps

### Step 0 — set-up, and three decisions to ask

**Ask Alessandro:**

1. **How pages are written.**
   - *Recommended:* subagents. Each is given about 10 cards, the brief
     (§B) and the validator, writes and validates its batch, and returns
     a summary. One session's context cannot hold 500 pages, so the
     writing has to happen outside it.
   - The alternatives: a script against the Claude API, which needs a
     key; or writing in this session, which is enough for the pilot only.
2. **Storage.**
   - 600 PNGs at about 108 KB come to about 65 MB, plus HTML and PDFs.
     Git LFS is not installed.
   - *Recommended:* commit everything while the total stays under about
     150 MB.
3. **The language shares** in the table above.

**Then:**

- Install `pypdfium2` (to render, Apache-2.0 / BSD) and `pdfplumber` (the
  text layer with positions, MIT) into `.venv`. **Not PyMuPDF**, which is
  AGPL.
- **The font allow-list.** List the faces installed on this machine:
  `/System/Library/Fonts`, `/System/Library/Fonts/Supplemental` and
  `/Library/Fonts`. Group them by class: serif, sans, mono, script and
  display. A page names only allow-listed faces, so the face its HTML
  declares is the face its picture shows. That matters because the font
  class is a major criterion.
- Create the layout on disk (below).

### Step 1 — the taxonomy and the cards

- **`corpus/taxonomy.json`** holds:
  - families and their kinds (`level-up.md` §4.7, table 1);
  - the feature ids (§F), with each family's priors;
  - the style families (§S);
  - languages and shares;
  - widths per kind (500–1200 px; Chrome lays out nothing narrower than
    500), and densities.
- **`tools/corpus_cards.py`** draws the cards, seeded:
  - family by quota; kind uniformly within the family, with receipts and
    clinical notes at their shares;
  - **one** arrangement, **one** main type class, then **3–6 other
    features**, drawn by the family's priors with exclusions (a receipt is
    not three columns);
  - a style family, a width, a language and a density.
- **The coverage top-up.** While a feature misses its minimum, swap it
  into a card of a kind that does not yet carry it.
- **The PDF slots.** About 100 cards are marked `origin: pdf`, by family.
  Their features are filled in when a real page is chosen (step 4), and
  the top-up runs again then.
- **Output:** `corpus/cards.json`, plus a printed coverage table: feature
  × kind × pool.
- **Tests:** quotas met; the same seed gives the same cards; coverage met;
  no card with conflicting features.

**A card:**

```json
{"id": "c0137", "origin": "generated", "family": "reports",
 "kind": "clinical visit note", "arrangement": "arr.two_columns",
 "type": "type.sans",
 "features": ["kv.over", "table.ruled", "table.empty_cells", "text.supsub"],
 "style": "clinical-plain", "language": "it", "width": 820,
 "density": "dense"}
```

### Step 2 — the validator and the contact sheets

- **`tools/corpus_check.py <id>...`** runs §V on pages. It exits non-zero
  and names each failed check.
- **`tools/corpus_sheet.py`** builds contact sheets for looking at
  variety. Each image holds twelve thumbnails, each labelled with its id,
  kind, style and language.
- **Tests:** each check catches a planted fault: an external font, words
  inside an SVG, clipped text, a horizontal overflow, a near-duplicate,
  and generated text (`::before` content, `<ol>` auto-numbers).

### Step 3 — the pilot: 50 pages, then Alessandro looks

- **50 cards**, spanning all eight families, at least eight style families
  and all five languages.
- **Written from the brief (§B), validated and shot.**
- **The contact sheets go to Alessandro. This is the gate:**
  - do they look like documents of their kind, written by different
    hands;
  - are the cards' features visible;
  - is the content realistic?
- **If they look like one author**, add style families or rework the brief
  before scaling (`level-up.md` §6's stop rule).
- **Measure minutes per page**, writing and validation together, and
  state the estimate for the rest before going on.
- **The 50 pilot pages go to dev.** They have been looked at closely.
- **Widened to 100, Alessandro, 2026-10-25:** "inspecting a pilot set
  before generating the whole thing makes sense", with the gate at 100
  pages. The first 50 are kept; `cards.widen_pilot` draws 50 more, each
  family in its share, and all 100 go to dev.

### Step 4 — the real PDF pages (§P)

- **Propose sources**, each with its licence checked and recorded.
  Alessandro approves the list before anything is downloaded.
- **A pilot of 10** goes through the gate first, then the rest, up to
  about 100.
- **Re-run the coverage top-up** with their features filled in.

### Step 5 — the rest, in batches of 50

- Validate every page. Print the coverage table after each batch, and top
  up the gaps.
- Every few batches, take a contact sheet drawn at random from the batches
  since the last one, for variety.

### Step 6 — the 31 pages, the pools, the L3 set, and wiring it in

- **Card the 21 and the ten probe pages by hand**: family, kind, features,
  style and language.
  - Their origin is `corpus` or `probe`, and all go to dev.
  - `ticket_0020` is photographed, so it stays in dev only (`level-up.md`
    §4.8).
- **Deal the pools.**
  - Seeded and stratified by family.
  - PDF pages are dealt separately, about 33 per pool.
  - The pilot pages go to dev.
- **The L3 set: 36 panel pages**, chosen by greedy cover:
  - each family at least 4 times;
  - each table, key–value, list and arrangement feature at least twice;
  - written to `corpus/l3-subset.txt`.
- **`corpus/manifest.json`** maps each id to:
  - its pool, family, kind, features, language, width and origin;
  - the sha256 of its HTML, PNG and PDF.
- **`doc_to_html.corpus`** loads the manifest:
  - `names("dev" | "panel" | "l3")` returns pool members;
  - `names("vault")` **refuses unless asked with `unseal=True`**;
  - `SOURCES` and the existing splits stay exactly as they are.
- **Tests:**
  - manifest integrity: files exist and hashes match;
  - each page's picture is its own HTML, extending
    `TestTheCorpusPictureIsItsOwnHTML`. Measure its time; if all 600 are
    too slow for the suite, test a fixed sample of 60 and run the full
    check as a tool;
  - the vault refuses.

### Step 7 — outcome and handover

- **This spec's "Outcome — the corpus" section:**
  - counts per family, kind, feature, language and pool;
  - the coverage table;
  - time spent;
  - pages dropped, and why;
  - the PDF pages per source, with licences;
  - the contact sheets' verdicts.
- **Update** `docs/status.md`, `CLAUDE.md` and `level-up.md` §6, then close
  issue #43.
- **Write a handover prompt for L2** (spec 0021), built from "What comes
  after this spec" below.

---

## §F — the feature ids

Every card has one arrangement, one main type class, and 3–6 others. The
**auto** column is what the validator can confirm in the HTML. The rest
are confirmed on the contact sheets.

| group | ids | auto |
|---|---|---|
| arrangement, exactly one | `arr.one_column`, `arr.two_columns`, `arr.three_columns`, `arr.sidebar`, `arr.cards_grid`, `arr.panels_side_by_side`, `arr.centred` | — |
| tables | `table.ruled`, `table.spanning`, `table.section_rows`, `table.totals`, `table.empty_cells`, `table.zebra`, `table.subrows` (indented), `table.long` (25 rows or more) | a `<table>`; `colspan`/`rowspan` above 1; an empty `<td>`; the row count |
| key–value | `kv.inline`, `kv.over` (label over value), `kv.two_per_line`, `kv.leaders`, `kv.boxed` | — |
| lists | `list.bullets`, `list.numbers`, `list.nested`, `list.ticks` (✓/✗, tick boxes), `list.clauses` (hanging clause numbers), `list.big_steps` | `<ul>`/`<ol>`; a list inside a list |
| text | `text.justified`, `text.footnotes`, `text.supsub`, `text.formula`, `text.quote`, `text.drop_cap` | `text-align: justify`; `<sup>`/`<sub>`; `<blockquote>` |
| type, exactly one main class | `type.serif`, `type.sans`, `type.mono` | the computed face's class |
| type, extras | `type.display`, `type.script`, `type.small_caps`, `type.weights` (three weights or more) | — |
| looks | `look.accent`, `look.dark_ground`, `look.bands`, `look.chips`, `look.buttons`, `look.rules` (dashed or double) | a dark ground from the body's background |
| figures | `fig.logo`, `fig.chart`, `fig.code` (barcode or QR), `fig.signature`, `fig.photo`, `fig.icons` | an `<svg>` or `<img>`, with no words inside |
| formats | `fmt.eu_numbers`, `fmt.dates`, `fmt.currency` | a pattern in the text |

## §S — style families

Twelve, so that no single author's habits become the corpus. Each is
written into the taxonomy as a short description that the brief quotes to
the writer.

| style family | looks | HTML habits |
|---|---|---|
| `corporate-modern` | sans, one accent colour, cards, generous space | semantic, flex and grid |
| `government-form` | numbered boxes, black on white, small type, dense | fieldsets, tables for boxes |
| `classic-print` | serif, rules, columns, small caps | semantic |
| `retail-receipt` | mono, narrow, dashed rules, centred header | divs and `pre`-like spacing |
| `clinical-plain` | sans, teal or blue, tables and fields, flags | tables, definition lists |
| `academic` | serif, two columns, footnotes, formulas | semantic, `sup`/`sub` |
| `editorial` | display type, drop caps, pull quotes | semantic |
| `minimal-swiss` | strict grid, small sizes, lots of white | grid |
| `bold-marketing` | big type, chips, buttons, dark bands | flex |
| `legacy-table` | Verdana or Times, tables for layout, borders | nested tables |
| `utility-classes` | any | framework-like utility class names |
| `print-export` | looks exported from a word processor | absolute-looking spacing, many spans |

## §B — the brief every writer is given

Committed as `corpus/brief.md` and handed to every writer word for word,
with the card. What it says:

- **One self-contained file**, `corpus/pages/<id>.html`:
  - `<!doctype html>`, `<meta charset="utf-8">`, `<html lang>` set to the
    card's language;
  - inline `<style>` only, and no JavaScript;
  - laid out for the card's width;
  - at most 2400 px tall at that width: one page.
- **No external resources of any kind**: no `http(s)` URL, no `@import`,
  no `@font-face`, no web font. Faces come from the allow-list only.
- **Content.**
  - Realistic for the kind and the language: fictional but plausible
    names, companies, addresses and numbers.
  - Totals add up and dates agree. The language's formats are used.
  - No lorem ipsum. No real person, company, brand or logo.
- **Features.** Every feature on the card is visibly present. Others are
  added only where they come naturally.
- **Structure.** Use the HTML that fits what is drawn: a table for a
  table, lists for lists, headings for headings. The exceptions are the
  style families that say otherwise (`legacy-table`, `utility-classes`,
  `print-export`); that variety is deliberate.
- **Words the reader sees are text nodes.**
  - Step and clause numbers, footnote marks, ✓/✗ and any other symbol
    that carries meaning are written in the HTML.
  - Never generate them with CSS: no `::before`/`::after` content, no
    counters, no `<ol>` auto-numbers. The scorer reads text nodes only, so
    generated text is in the picture and not in the ground truth.
  - Plain bullets may be drawn by the browser.
- **Figures** are inline SVG with **no `<text>`**, or a `data:` PNG.
  - Words inside a figure are not ground truth.
  - A logo is shapes; its wordmark, if any, is HTML text beside it.
- **Every word in the DOM is visible.** Nothing clipped, hidden,
  overflowing, off the page, or the colour of its ground.

## §V — the validator

| # | check | how |
|---|---|---|
| 1 | it renders, at the card's width and at most 2400 px tall | `projection.screenshot` |
| 2 | **the picture is its own HTML**: a second shoot differs nowhere | as `TestTheCorpusPictureIsItsOwnHTML` |
| 3 | nothing clipped, nothing overflowing | `project()`'s `clipped` is 0; `width` equals the card's |
| 4 | every word has ink under it | each projected line box over non-ground pixels in the PNG |
| 5 | no external resources | no `http`, `@import` or `@font-face`; every face on the allow-list |
| 6 | no words inside figures | no text node under `svg`, `canvas` or `figure` |
| 7 | no generated text | no `content:` with characters; no `<ol>` without `list-style: none` |
| 8 | the card's auto-checkable features are present | §F's auto column |
| 9 | the language is the card's | a stopword count |
| 10 | not a near-duplicate | word-shingle Jaccard under 0.5, and a picture hash apart, against every accepted page |

A PDF page runs checks 5–10 on its twin. Check 2 is replaced by §P's
gate, because its picture is the PDF's render, not a screenshot.

## §P — real PDF pages, and the gate that keeps them honest

**What a PDF page is in the corpus:**
- the picture converted is **the PDF's own render**;
- the ground truth is **an HTML twin** that redraws the page and passes
  the gate.

The picture carries real typography; the twin carries the words, lines
and structure the scorer reads. The original five corpus pages work the
same way: their HTML re-renders only approximately to their picture, and
`height_ratio` is taken against the PNG's own height.

1. **Choose a page**: one page, with a text layer, not a scan.
   - Prefer pages with tables, forms and fields.
   - Avoid pages that are mostly figure.
2. **Record its provenance** in `corpus/pdf/<id>.source.json`: URL, licence,
   page number, date taken, sha256.
3. **Render it** with `pypdfium2`, scaled to a width between 900 and
   1100 px. That PNG is the picture converted.
4. **Take its text layer** with `pdfplumber`: words with their boxes,
   faces and sizes, grouped into lines.
5. **Write the twin** (Claude), with the brief's rules:
   - every line ends where the PDF's line ends, by explicit line ends;
   - the structure is real (tables, lists, headings);
   - faces come from the allow-list, at sizes and positions as close as
     flow layout allows.
6. **The gate.** A page is admitted only if all three hold. *Restated
   2026-10-25 on the pilot of 10, and again 2026-10-26 on the next ten;
   the reasons are in step 4's outcome.*
   - **words:** the twin's characters equal the text layer's, as a
     multiset. Both sides first drop white space, accents and format
     characters, unfold ligatures and compatibility forms, and fold
     case. Text set at an angle takes part in this test only;
   - **rows:** words are grouped into rows the same way on both sides:
     a word joins a row whose centre lies within half a type size of
     its middle, unless the row holds a word above or below it. The
     PDF's rows are cut into runs at every gap wider than 1.5 em and
     every step to another line or cell. Each run must be found in the
     twin as one run of text at the same place. Where the PDF's gap is
     wider than 3 em (a column or a cell), or a row starts or ends, the
     twin must break too; at a narrower gap it may run on;
   - **geometry:** each run's top, and the left of each of the twin's
     pieces, lie within 1.5% of the page's width of where the PDF sets
     the same text. Over the pilot of 10 the worst offsets were 12.4 px
     across and 10.0 px down at 1000 px, median 4 px each way, so the
     threshold stays at 1.5% (15 px).
   - **Two pointers, not tests,** listed for whoever reviews the twin:
     runs of one-line blocks that may be one paragraph cut into lines,
     or one line cut into words (`pdfpage.split_paragraphs`), and runs
     set more than 10% off the page's type size.
7. **Revise the twin, never the PDF.** A page whose twin cannot pass after
   three revisions is dropped, and the reason recorded.

**Sources.** Check every licence and record it.
- *Candidates:*
  - government forms (US federal forms are public domain; check EU and
    national ones one by one);
  - open-access papers under CC BY (arXiv, PMC);
  - DocLayNet's pages (CDLA-Permissive-1.0: financial reports, manuals,
    laws, tenders, patents), if its PDF pages can be taken one at a time
    rather than as a multi-gigabyte archive;
  - manuals and annual reports only under a licence that allows it.
- Prefer files of a few MB, fetched one at a time. Alessandro approves
  the list before downloading.

---

## On disk

```
corpus/
  taxonomy.json        families, kinds, feature ids and priors, style families,
                       languages and shares, widths
  brief.md             what every writer is given (§B)
  cards.json           every card, with the seed it was drawn with
  pages/<id>.html      the page, or a PDF page's twin
  pages/<id>.png       the picture converted: a screenshot, or the PDF's render
  pdf/<id>.pdf         a real PDF page, one page
  pdf/<id>.source.json its provenance and licence
  manifest.json        id → pool, family, kind, features, language, width,
                       origin, hashes
  l3-subset.txt        the limited baseline set, 36 panel pages
debug/corpus-sheets/   contact sheets, gitignored, rebuilt on demand
```

The 21 keep their files in `example/`, and the ten probe pages theirs in
`docs/level-up-probe/src/`. The manifest points at them where they are.

---

## What comes after this spec

Each of these is its own spec, planned when the one before it closes. The
order was decided on 2026-10-24 (`level-up.md` §6 and §8).

### L2 — measurement, and the judge (spec 0021)

**The judge is Claude, with the review skill evolved to the agreed
criteria.** It is not a local model.

1. **A batch runner.**
   - Converts a named list (`dev`, `l3`, or ids) with the shipped
     defaults, detached and resumable, with seconds per page.
   - Writes `debug/runs/<label>/` as a sweep does.
   - Refuses vault ids unless unsealed.
2. **Derived checks**, from the source HTML against the output, both
   projected. These are exact, take no model, and each is tagged with
   feature ids so the report counts per feature and per family:
   - words: `vanished` and invented, plus a multiset version, because the
     set cannot see a repeated word that is lost;
   - **the cell check**: each source table cell's words sit in the same
     row and column of an output table;
   - structure kept: tables, ordered and unordered lists, headings,
     label–value groups;
   - **lines**: every source line's words form one output line, as the
     criteria demand;
   - height within 10%; alignment per line; font class and relative size
     per block; bold where bold;
   - "unread" marks counted, once the converter draws them.
3. **The review skill, evolved** (`review-criteria.md`, "What the skill
   must change"):
   - faults tagged by feature, stage and severity;
   - two-panel sheets, zoomed tiles on dense pages, and a highlight of
     where two renders differ;
   - sampling: the pages the checks flag, the pages a change moved, and a
     sample per family;
   - the ranked roll-up: majors first, then gain for effort, with the
     reasoning;
   - `owner` retired, and `numbers.md`'s broken table fixed.
4. **The private review page with agree buttons.**
   - An Artifact with a database. Load the `artifact-capabilities` skill
     before building it.
   - Alessandro ticks agree or disagree on every page called worse and on
     two at random. Claude reads his calls back with `ArtifactData`, and
     every disagreement changes the checklist, re-tested on all past
     calls.
5. **Done when** one command runs the checks and builds the review page
   over a run.
   - It is proved on the 31 dev pages, `G0-s14-rederived` style.
   - It must catch the faults already known there: the lab report's
     shifted results, the recipe's interleaved steps, the quiz's merged
     cells.

### L3 — the honest baseline

- Today's pipeline (the S14 code) over `corpus/l3-subset.txt`: 36 pages,
  about 5 hours at the probe's 8.2 minutes a page. Start it detached.
- Measured with L2's checks and reviewed by Claude.
- **The result: ranked fault classes on pages nobody has tuned on.** It is
  the reference P2 decides against.

### P1 — the GLM-OCR parser-first PoC

- **Branch `poc-parser-first`**, cut from `develop`, with its own spec.
- **GLM-OCR, as of 2026-10-24.** Re-check every line of this at P1's
  start.
  - **SDK:** `glmocr` 0.1.5, installed with
    `pip install "glmocr[selfhosted]"` (torch 2.10 or later,
    transformers 5.3 or later).
  - **Layout:** PP-DocLayoutV3, Apache-2.0. `--layout-device cpu` keeps it
    off the GPU if the 8 GB M1 cannot hold both models.
  - **Reader:** served by Ollama, model `glm-ocr:latest`. Set
    `pipeline.maas.enabled: false`, point `ocr_api` at
    `localhost:11434/api/generate`, with `api_mode: ollama_generate`.
  - **Licences:** code Apache-2.0, model MIT.
  - The taste test used `glm-ocr:q8_0` and the reader alone. The PoC uses
    `latest` and the whole pipeline.
- **The pipeline:**
  - the picture goes through **GLM-OCR's own entire pipeline**, layout
    then reading. No piece of today's layout is fed in;
  - out come blocks: box, label and content (text; tables as HTML);
  - **the adapter** turns them into the IR: Zones, Blocks and Cells, each
    with its box;
  - then today's looks (style measured from pixels, furniture) and the
    renderer.
- **The criteria shape the adapter from the start:**
  - **every line as printed.** GLM-OCR returns paragraphs, so line ends
    must come from the picture: tesseract's line boxes, or the layout's
    lines, with the words mapped to them. This is the largest unknown;
    measure it first;
  - **never guess.** A second reader (tesseract, already in the pipeline)
    reads the same words, and a word the two disagree on is drawn as an
    "unread" box. The judge never reads with GLM-OCR;
  - **structure.** GLM-OCR's tables become Cells with their spans. Label
    and value pairs have no Kind there: rebuild them from boxes, or keep
    one VLM question for them.
- **Arms**, on the same pages:
  - today's pipeline;
  - D2, the GLM-OCR pipeline, the adapter, our looks and the renderer;
  - D1 (GLM-OCR reading today's Zones) only if D2's result needs taking
    apart: is the gain in its layout or in its reading?
- **Pages:** the dev pool, then the L3 set.
- **Measures:** L2's checks, Claude's review, and seconds per page.
- **Iterate on the adapter and the looks, never on the parser's weights.**
- **Stop if** the parser loses content that today keeps, on most pages.
  Then park it and write down why.
- **Risks to measure** (`level-up.md` §5.3):
  - designed pages (cards, tickets, flyers);
  - side-by-side panels read as one column;
  - text looped or invented;
  - the 8 GB M1's memory.

### P2 — the decision

- The PoC against today on the L3 set, by ranked fault classes, under the
  net-gain rule.
- If GLM-OCR's speed allows, the whole panel too: 200 pages becomes a
  night rather than 27 hours.

### L5 — fit, don't set

- Whatever the winner still decides with hand-set constants gets fitted:
  - labels come from dev's HTML (computed weight, sizes, `colspan`,
    alignment, boxes);
  - accepted on the panel;
  - confirmed on the vault at a milestone (`level-up.md` §5.4).

### Converter changes the review criteria queue

They are done in whichever pipeline wins P2, or in the PoC's adapter from
its start:

| criterion | change | what it reverses |
|---|---|---|
| every line as printed | explicit line ends in the render, type sized to fit | Phase A1's reflow into paragraphs |
| never guess | a word two readers disagree on drawn as an "unread" box, its reason in the HTML and the report | spec 0019 D2's plain draw |
| net gain, content included | reports name content losses and do not block | the T1 ratchet as a gate |
| a fixed page | the render is a page at the source's width | — |

---

## Outcome — the steps

### Step 0 — done 2026-10-24

**Alessandro's three decisions, 2026-10-24:**

| # | asked | decided |
|---|---|---|
| 1 | how pages are written | **subagents, two models**: each takes about 10 cards, the brief and the validator, writes and validates its batch, and returns a summary. Batches alternate between Opus and Sonnet, for `level-up.md` §4.6's "several generators". The pilot carries both, and his look at its sheets decides whether they read as different hands |
| 2 | storage | **commit everything** as plain files. Re-measured after the PDF pilot; stop and ask if the total heads past about 150 MB |
| 3 | language shares | **as proposed**: English 450, Italian 50, French 50, Spanish 25, Portuguese 25 |

**Decision 1 amended, Alessandro, 2026-10-25: the writers run on Sonnet,
and this session stays on Opus.** The three Opus pilot batches stopped at
the monthly spend limit, after 14 of their 30 pages had passed. The two
Sonnet batches had written all 20 of theirs: 17 on the first validator
run, about 26 s a page. He asked for Sonnet at `xhigh` effort. An agent
definition, `.claude/agents/corpus-writer.md`, sets it, but definitions
load when a session starts, so this session's writers ran on Sonnet at
its usual effort. The variety the second model was to bring rests on the
twelve style families and the cards' randomness. The pilot's sheets are
where that is judged.

**The facts, re-checked the same day on `level-up` at `4461fa1`:**
- 1394 tests pass, 1 skipped (10m28s); `mypy src/` clean.
- The 21 corpus PNGs average 107.6 KB. Over the 31 pages (the 21 and the
  probe's ten) a picture costs **0.16 bytes per pixel**, which is what
  the storage estimate was taken from: about 90 MB of generated PNGs,
  20–40 MB for the PDF pages, about 6 MB of HTML.
- No PDF library was in `.venv` and poppler is absent; tesseract is at
  `/opt/homebrew/bin/tesseract`. Git LFS and PyYAML are not installed.
- `project()` walks `SHOW_TEXT` text nodes only; the scorer folds case.
- One `project()` and one `screenshot()` of a probe page take 1.1 s and
  2.0 s, so the validator's two shoots and its checks come to about 6 s a
  page.

**Installed:** `pypdfium2` 5.14.0 and `pdfplumber` 0.11.10 (with
`pdfminer.six` 20260107), as the `corpus` extra in `pyproject.toml`,
locked in `uv.lock`. Nothing in `src/` that converts imports either.

**The font allow-list, `corpus/fonts.json`** (`tools/corpus_fonts.py`,
`doc_to_html.factory.fonts`). 84 candidates, classed by hand, then
measured in the corpus's own Chrome: each must resolve and cover the five
languages' accents and `€ £ « » ’ “ ” – —`. **78 kept:** 21 serif, 26
sans, 7 mono, 11 script, 13 display. Two origins:
- `apple`, shipped in `/System/Library/Fonts` and `Supplemental`;
- `open`, OFL or Ubuntu-licensed faces in `/Library/Fonts` (Lora, Open
  Sans, Source Sans, Serif and Code, Ubuntu, Playfair Display, Oswald and
  others).

Left out: Futura, DIN Alternate and two Bodoni 72 cuts lack `€`; Party LET
and Academy Engraved LET do not resolve by those names. Also left out on
purpose: the commercial and personal-use faces installed in
`/Library/Fonts` on this machine (a page in one cannot be re-shot
elsewhere, and some are licensed for personal use only), faces for
scripts the corpus does not use, and dingbats.

**Measured, and it shapes the brief:** a synthesised bold keeps the
regular's advance widths (Monaco, one face, counts one weight). A
monospaced face keeps them at every weight too, so a mono face counts one
weight however many it has. `type.weights` therefore names a face with
three or more real weights: Helvetica Neue, Avenir, Avenir Next, Gill
Sans, Optima, Skia, Source Sans and Serif, Ubuntu, Hind, Comfortaa, STIX
Two Text, Charter, Baskerville, American Typewriter, Open Sans, Playfair
Display, Oswald, Copperplate, Snell Roundhand.

**Code and tests:** `src/doc_to_html/factory/` (`browser.evaluate`, a
script run in `projection`'s Chrome with its flags; `fonts`), and
`tests/test_factory_fonts.py`, 6 tests: the list on disk is the code's,
every class has at least five faces, and on this machine every listed face
still resolves and covers the glyphs. `corpus/README.md` holds the layout
on disk.

### Step 1 — done 2026-10-24

**`corpus/taxonomy.json`** holds the eight families with their quotas and
PDF slots, 55 kinds, the 54 feature ids with a one-line note each (the
note is what the brief hands the writer), each family's priors on a 0–3
scale, each kind's overrides (widths, arrangements, density, styles, boosts,
exclusions), the twelve style families with their main-type weights, 15
exclusion pairs, the languages and the coverage rule.

- **Kinds beyond table 1's examples**, for variety inside the tilted
  families: quotation; registration and consent forms; a status report;
  a membership card. Table 1 named its kinds as examples.
- **Receipts are 40 generated cards, and so are the clinical notes**
  (visit note 14, discharge summary 13, prescription 13). Real PDF
  receipts and clinical notes would be private, so none of a family's PDF
  slots is expected to be one.
- **A locale per card**, an addition the spec did not ask for: English is
  `en-GB` or `en-US`, Portuguese `pt-PT` or `pt-BR`, so dates and
  spellings vary inside one language. Every non-English locale keeps the
  number format the spec asks for.
- **Arrangements carry a minimum width** (three columns 900, a cards grid
  760, two columns, a sidebar and side-by-side panels 700). The draw only
  offers a kind the arrangements its widths can hold. The nutrition label
  (500–640) never gets side-by-side panels, and a receipt only one column
  or centred.

**`tools/corpus_cards.py`** (`doc_to_html.factory.cards`) drew
**`corpus/cards.json` with seed 20261024**:
- 600 cards: 500 generated and 100 PDF slots, every quota exact;
- the languages dealt exactly, 450 / 50 / 50 / 25 / 25;
- the other kinds of each family within one card of each other;
- 3–6 other features per card (121, 142, 111 and 126 cards with 3, 4, 5
  and 6);
- widths from 500 to 1200 px, mean 853;
- densities 138 sparse, 207 medium, 155 dense;
- all twelve style families, from `corporate-modern` (79) to `academic`
  (13).

**The coverage top-up changed 3 cards** (`c0119`, `c0379`, `c0569`), all
for `fmt.eu_numbers`, which the draw gave only 6 pages. It is excluded on
English cards, which are three quarters of them. **The rule is met over
the 500 generated cards**: every feature id is on at least 9 pages in at
least 3 kinds. The thinnest are:
- `fmt.eu_numbers`, 9 pages in 8 kinds;
- `text.drop_cap`, 10 in 7;
- `text.formula`, 12 in 8;
- `list.big_steps`, 14 in 10;
- `look.buttons`, 15 in 9.

The per-pool half of the rule (2 in each pool) is met when the pools are
dealt, in step 6.

`fmt.eu_numbers` is thin as a card feature only: the brief has every
non-English page use its own formats. The validator records a page's
detected features beside its card's, so the per-feature counts in L2 can
use what the page shows.

**The pilot's 50 cards** are marked on the cards: 10 transactional, 7
each of forms and reports, 6 each of credentials and presentation, 5 each
of correspondence and reference, and 4 publishing. All twelve style
families are in it, and all five languages (38 English, 5 Italian, 4
French, 2 Portuguese, 1 Spanish).

**The PDF slots want 72 English pages and 28 in the other four
languages.** Step 4 chooses real pages against that. Where the sources
cannot meet it, the languages of unwritten generated cards are swapped to
keep the totals, and the swap is recorded in `cards.json`'s history.

**Tests:** `tests/test_factory_cards.py`, 20 tests:
- the quotas;
- the same seed giving the same cards, the top-up and the pilot included;
- coverage met;
- a locked card never touched;
- an impossible feature reported rather than forced;
- every card sound;
- six planted faults each named: seven features, a long table on a sparse
  page, a receipt in three columns, European numbers on an English page,
  two columns at 600 px, a feature its kind excludes;
- `cards.json` is the seeded draw but for the cards its history names.

### Step 2 — done 2026-10-24

**`tools/corpus_check.py <id>...`** (`doc_to_html.factory.check`) runs §V's
ten checks, named `renders`, `own_picture`, `fits`, `ink`,
`self_contained`, `figures`, `generated`, `features`, `language` and
`distinct`. It exits non-zero and names each failure.
- **A page that passes** gets its picture, `corpus/pages/<id>.png`, and
  its record, `corpus/checks/<id>.json`. The record holds the checks, the
  card's features and the **detected** ones, the picture's hash and both
  files' sha256.
- **A page that fails** keeps nothing. Its screenshot is left in
  `debug/corpus-check/<id>.png` for the writer to look at.
- **It takes 3.6–4.3 s a page**: a projection, one probe script, and two
  shoots.

Decisions the spec left open, each in the module's docstring:
- **Ink (4)** is measured per line box of each text node. The box's
  commonest colour is its ground, and ink is any pixel more than 48 from
  it in any channel. A box needs `max(2, 0.4% of its area)` ink pixels.
- **A stack may lead with a generic** that draws a listed face here:
  `serif`, `sans-serif`, `monospace` or `cursive` (Times, Helvetica,
  Courier, Apple Chancery). `system-ui` and `-apple-system` draw the
  unlisted SF, so a stack may not lead with them.
- **Text under a `<figure>` is a figure's words** unless it is in its
  `<figcaption>`.
- **Two additions to check 3**: no viewport-height unit and no fixed or
  sticky positioning. `project()` measures in a 3000 px window and the
  shot is taken in one as tall as the page, so such a page is laid out
  differently in the two.
- **Check 8 asks for a real `<table>`** for any `table.*` feature, and a
  real `<ul>`/`<ol>` for bullets, numbers and nesting, in every style
  family. Without them L2's cell check has nothing to derive from. The
  three loose style families keep their loose habits everywhere else.
- **The language (9)**, measured over the 31: a page of 80 words or more
  must score 2 in its language. A shorter page needs 1, or nothing in
  English: `ticket_0020`, 55 words of labels, scores 0.5 in English and
  0.5 in French. No other language may lead by 1.5 or more.
- **A near-duplicate (10)** is four-word shingles at a Jaccard of 0.5 or
  more, or a 64-bit difference hash within 3 bits. It is compared against
  every accepted page, the 21 and the ten probe pages.

**Run over the 31 pages we already have, with stand-in cards**: 10 pass
outright. The rest fail on what they really do, which matters for L2,
because their ground truth is their HTML:
- **Generated text on six pages.** That text is in the picture and not
  in the ground truth:
  - `report_0011`'s section numbers, drawn by CSS counters;
  - `form_0007`'s ✕ marks and `pricing_0017`'s ✓ marks;
  - `menu_0012`'s ❦ ornament;
  - the probe's datasheet's ✓ marks and recipe's step numbers.
- **Eight pages lead their font stack with a face that is not on the
  list.** Five of them name a face this machine lacks (Inter, Palatino
  Linotype, Source Sans Pro, Segoe UI, Cambria), so the face the HTML
  declares is not the face the picture shows. The other three lead with
  `system-ui` or `-apple-system`, which draw the unlisted SF.
- `invoice_0001` and `invoice_0002` load images and a stylesheet from the
  web; `sample_semantic_0005` sets a quotation inside a `<figure>`.
- `nonlatin_0014` is Greek, which the language check cannot read.

**No false ink failure** on any of the 31, and no near-duplicate among
them.

**`tools/corpus_sheet.py`** (`doc_to_html.factory.sheets`) builds the
contact sheets: twelve thumbnails to an image, four across. Each is
labelled with its id, kind, style family and locale, then its features,
width, density, family and writer. They go to `debug/corpus-sheets/`.

**Tests:** `tests/test_factory_check.py`, 23 tests in 41 s:
- a sound page passes every check, and what it shows is detected;
- the spec's six planted faults are each named: an external font, words
  inside an SVG, clipped text, a horizontal overflow, a near-duplicate,
  and generated text (`::before` content and an `<ol>` that numbers
  itself);
- so are eight more: an `@font-face`, a URL in an attribute, text the
  colour of its ground, the wrong language, a card feature missing, the
  wrong main face, a viewport-height unit, a page over 2400 px;
- an `<ol>` with its numbers written passes;
- the formats are detected by language, and each language reads as itself;
- the sheets come twelve to an image.

### Step 3 — the pilot, 100 pages, 2026-10-25, reviewed and kept

**Alessandro's review, 2026-10-25:** all 100 are good and stay as they
are. He asked for three additions, which step 5 takes up:
- simpler documents that are not a whole page: a table smaller than a
  page, an annotated map, a book page with a chart, a printout from a
  technical manual, a utility bill;
- keep the forms;
- random dates and names.

**100 pages, each passing the validator, checked again all together**
(near-duplicates included) at 3.6–4.1 s a page. 17 were written by Opus
and 83 by Sonnet (decision 1, amended).
- **Spread:**
  - every family, in its share: transactional 19, forms 14, reports 14,
    credentials 12, presentation 12, correspondence 10, reference 10,
    publishing 9;
  - all twelve style families, and 46 of the 53 kinds;
  - English 73, French 13, Italian 8, Portuguese 4, Spanish 2;
  - dense 39, medium 39, sparse 22.
  - Every feature is on two pages or more except `text.drop_cap`, on
    none. Its ten cards all lie outside the pilot.
- **Heights:** 442 to 1581 px, median 841. **15 MB on disk**, so about
  100 MB for the 600.

**A word floor per density (check 8), added after the first 50.** The
Sonnet pages were about half as wordy as the Opus pages at the same
density. The medians were 254–291 words dense and 177–205 medium for
Sonnet, against 570 and 404 for Opus. The floor:
- 400 words per 1000 px of width dense, 220 medium, none sparse;
- half that for nine compact kinds: certificate, ticket, invitation,
  membership card, slide, flyer, prescription, calendar and nutrition
  label.

On the first 50 pages:
- all 17 Opus pages cleared the floor, and 14 of the 33 Sonnet pages
  fell under it;
- those 14 were extended by Sonnet writers with what the kind really
  carries, from 77–423 words to 125–503, each passing on its first run;
- the brief states the floor, so the 50 that followed were written to
  it. Sonnet's medians over all 83 are now 413 words dense and 205
  medium.

**c0052 was rewritten.** It reproduced the IRS Form 1040-EZ. The brief now
says no real organisation issues a document. The new page is "Form RV-31"
of an invented state revenue office.

**Two faults found and fixed outside the pages:**
- **`projection.project()` crashed on a large page.** It returned no
  projection for a table of 40 rows by 8 columns, because its script
  spread every byte of its payload as one call's arguments. A writer
  found it on c0011, and cut that table to 6 columns by 25 rows to get
  past it.
  - The script now encodes in 32 KB chunks; `factory.browser` had the
    same line and is fixed the same way.
  - The 21 corpus sources project identically before and after, and
    `tests/test_projection.py` pins a table of 60 rows by 10 columns.
  - L2 would have met this on any dense page.
- **`pools._repair` refused a swap that only partly closed a gap.** With
  100 pages fixed in dev, it would have left dev with no drop cap.

**Minutes per page.**
- The five new batches of ten ran in parallel and took 333–554 s each,
  so about 33–55 s a page per writer, the floor making pages longer.
- 24 of the 50 passed on their first run. The commonest second run was
  the floor.
- At five writers in parallel, **the 400 generated pages left are about
  an hour to an hour and a half of writing.**

**What the sheets show, for the review:**
- **They read as documents of their kind**, and mostly from different
  hands. The strongest are the receipts (till slips, a bookseller, a
  café, a Brazilian NFC-e, Italian *scontrini*), the forms, the clinical
  notes, the tickets and the invitations. The `corporate-modern` pages
  share one look (white rounded cards, a sans and one accent) more than
  the other families do.
- **Two signs of one author, measured over the 100:**
  - **dates:** 69 pages carry an October 2026 date, and 21 are dated 24
    October 2026, the date the brief's locale table uses as its example;
  - **names:** "Okafor" is on 8 pages, "Whitcombe" on 7, "Harbour" or
    "Harbor" on 13, "Fenwick" on 6.

### Step 4 — the sources proposed 2026-10-24, approved 2026-10-25

Each licence was checked against its own statement on 2026-10-24. Every
source allows redistribution, commercial use included, so a page can be
committed to this repository. Each page's provenance and licence go in
`corpus/pdf/<id>.source.json`. Where a licence asks for attribution, it
is given there and in `corpus/pdf/ATTRIBUTION.md`.

| # | source | licence, as stated | families | languages | about |
|---|---|---|---|---|---|
| 1 | US federal agencies: IRS, SSA, CMS, USCIS and VA forms; GAO, NIST technical series, CDC and NIH publications | public domain in the US: a work of the US Government (17 U.S.C. §105). GAO prints "a work of the U.S. government and is not subject to copyright protection". NIST's SRD (reference data) products are the exception and are not used | forms, reports, transactional (sample statements and notices), reference (NIST tables, FDA label examples), publishing (CDC's MMWR, NIH News in Health), correspondence (GAO decision letters) | en-US | 55 |
| 2 | GOV.UK and HMRC forms and guidance | Open Government Licence v3.0 (Crown copyright), attribution required. It does not cover personal data, or logos and crests except where integral to a document | forms, reports, notices | en-GB | 12 |
| 3 | EUR-Lex (the Official Journal, and the standard forms annexed to regulations) and the Publications Office's brochures | Commission Decision 2011/833/EU: reuse authorised, the source acknowledged; CC BY 4.0 unless otherwise noted | forms, correspondence and legal, reports, publishing | it, fr, es, pt-PT (and en) | 15 |
| 4 | ISTAT | CC BY 4.0, "salvo diversa indicazione" (ISTAT's legal notes) | reports, reference | it | 4 |
| 5 | INSEE | Licence Ouverte 2.0 (Etalab), source "Insee" | reports, publishing | fr | 3 |
| 6 | BOE, Spain's official gazette | reuse authorised for any purpose, citing "Fuente: Agencia Estatal Boletín Oficial del Estado" with a link | correspondence and legal, forms annexed to orders | es | 4 |
| 7 | Brazil's official acts (planalto.gov.br, the Diário Oficial da União) | not protected: Lei 9.610/98 art. 8 excludes official acts and blank forms | correspondence and legal, forms | pt-BR | 3 |
| 8 | arXiv papers whose licence is CC BY 4.0, chosen paper by paper | CC BY 4.0, attribution required. The default arXiv licence is not used | publishing | en | 4 |

The last column is the number of pages planned, about 100 in all. The
languages come out at about 72 English, 11 Italian, 7 Spanish, 5 French
and 5 Portuguese, which is what the PDF slots want.

**Considered and left out:**
- **DocLayNet**: its pages come as images in a multi-gigabyte archive.
  No way was found to fetch one PDF page at a time.
- **INE Portugal**: reproduction for non-commercial purposes only.
- **PMC**: its service gives individual PDFs only for articles licensed
  for non-commercial use; arXiv covers papers.
- **Company reports and manuals**: copyright, with no open licence.

**How the pages are chosen.** One page per document, with a text layer,
not a scan, and not mostly figure; tables, forms and fields preferred. A
source PDF is fetched one file at a time, a few MB at most, into
`debug/corpus-pdf/downloads/` (gitignored). Only the one page is
committed, as `corpus/pdf/<id>.pdf`, unedited.

**The pilot of 10**, one or two from each source: an IRS form, an SSA
form, an HMRC form, a GAO report page with a table, an annexed EU
standard form in Italian, an ISTAT report page, an INSEE page, a BOE
page, an arXiv CC BY paper page, and a NIST table page.

**The code is ready** (`doc_to_html.factory.pdfpage`,
`tools/corpus_pdf.py`, `tests/test_factory_pdf.py`, 8 tests). On a PDF
printed here from an HTML page, the gate admits that page's own HTML as
its twin: 13 of 13 lines, worst offsets 3.5 px down and 0.3 px across. It
refuses a twin with a word missing, a line broken elsewhere, or every
line below its heading moved down by a widened margin.

### Step 4 — the pilot of 10, 2026-10-25, approved 2026-10-26

**Alessandro approved the list, 2026-10-25:** "keep it simple for now and
we revisit once you get 10 examples we can actually use as render cases
— if this gets complicated we drop for now to focus on synth test cases".
So PDF work stops at these ten until he looks at them; the other 90 PDF
slots stay open.

**Three sources could not be fetched, and one was a scan.** GAO, SSA and
EUR-Lex refuse a scripted download (bot protection), and NIST's 1995
edition of SP 811 has no text layer. The ten came from what could be
fetched:

| page | source | kind | rows | words | worst across | worst down |
|---|---|---|---|---|---|---|
| c0071 | HMRC form HS275, p1 (OGL v3.0) | application form | 28 | 295 | 0.0 | 3.0 |
| c0072 | IRS Form W-9, p1 (public domain) | numbered-box tax form | 64 | 950 | 1.6 | 1.0 |
| c0073 | Receita Federal request form, Acre, p1 (blank form) | application form | 24 | 133 | 0.9 | 4.0 |
| c0282 | INSEE, TEF 2019, p52 (Licence Ouverte 2.0) | corporate report page | 65 | 655 | 4.8 | 4.3 |
| c0287 | Istat, Relazione sulla performance 2025, p20 (CC BY 4.0) | corporate report page | 36 | 428 | 4.9 | 9.0 |
| c0300 | the same, p13 | status report | 35 | 274 | 10.3 | 5.1 |
| c0360 | BOE-A-2025-6771, p2 (reuse with citation) | notice | 42 | 578 | 12.4 | 9.3 |
| c0406 | arXiv:2610.31163, p24 (CC BY 4.0) | paper page | 30 | 367 | 0.1 | 3.2 |
| c0409 | INSEE, TEF 2019, p8 | textbook page | 54 | 290 | 3.2 | 10.0 |
| c0471 | NIST SP 811 (2008), p16 (public domain) | technical printout | 53 | 403 | 8.6 | 1.4 |

Offsets are in px at 1000 px wide; the tolerance is 15. Each page's
provenance is in `corpus/pdf/<id>.source.json`, and
`corpus/pdf/ATTRIBUTION.md` is written from those records
(`tools/corpus_pdf.py attribution`).

**A twin costs a writer from under a minute to seven** (Sonnet, 1 to 10 gate
runs). The cost of a PDF page is in fetching its source and in what the
gate gets wrong, and the pilot found three faults in the gate and one in
the twins. All four are fixed:
1. **The text layer's white space and accents are wrong more often than
   not**, on five of the first seven pages. HMRC's form holds
   `Whenyoumakeaclaimasanindividual,`, LaTeX's captions run their words
   together, Brazil's form reads `1.IDENTIFICAÇÃO` and `P esquisa`, and
   accents come apart (`Brynjarsd´ottir`, `λˆ`). The first gate compared
   words, so a twin had to copy those, and would then have marked a
   converter wrong for reading the picture right. **The gate now compares
   rows as a reader reads them** (§P step 6), and the twin spaces words as
   the picture shows them.
2. **Twins cut paragraphs into one block a line**, in three of the first
   six (c0287, c0300, c0406), and a fourth cut a line into words with
   `position: absolute` (c0073). Every one passed the gate, and the scorer
   groups text by its block. `pdfpage.split_paragraphs` lists such runs.
   It is a pointer, not a test, because a stack of separate items reads the
   same to geometry: over the first 200 generated pages it reports 12 runs
   of lines and 24 of words, and the lines are all footnotes, items or
   particulars.
3. **Text set at an angle has no rows.** BOE's margin and the W-9's side
   text stand on end, and pdfplumber spells their words in the order of
   their boxes (`5202` for 2025). That text is now compared by its
   characters only, never by rows or geometry.
4. **The listing a writer works from now shows rows**: each piece at its
   left, `‖` before a piece the twin must set apart and `|` before one it
   may run on, with any turned text in its last line.

**Every twin was opened beside its page** (`debug/corpus-pdf/sheets/`).
All ten read as their pages: the same words, lines, tables and boxes in
the same places, in the allow-list's nearest faces. Logos and emblems are
left out, as the brief asks. One fault was found and fixed by hand:
c0073 drew empty the three radios its page shows selected.

**Alessandro's review, 2026-10-26:** "pdf choice and conversion 10 cases
are good". The ten stay as they are.

**Alessandro's decision, 2026-10-26: go on to about 100**, from the
sources that can be fetched (US federal, GOV.UK, ISTAT, INSEE, BOE,
Brazil, arXiv CC BY), ten at a time, each ten opened beside its pages.

### Step 5 — the rest, in progress, 2026-10-25

**What changed after the pilot's review:**
- **Fragments**, a new family of 50 cards, recast from unwritten cards
  (`tools/corpus_cards.py --recast`, once, seed 20261026). Its kinds:
  standalone table, annotated map, chart with caption, diagram with
  callouts and form section, 500–1000 px wide. Recast alongside them:
  book page 8, technical printout 8, utility bill 4. Each card keeps its
  id, language and locale, and no card the pilot holds was touched: 70
  cards recast, 71 changed, all named in the cards' history.
- **No card under 500 px.** Chrome lays out no page narrower, so seven
  fragment cards moved to 500 px. c0014, written for 480 px, passed
  unchanged at 500.
- **Particulars**: each card gets its own date, three people, two places
  and two name words, drawn from its locale's lists
  (`factory.particulars`, seeded by the card's id). The names the pilot
  overused are on no list. Fragments get half the word floor.

**Rounds of 50, written by Sonnet, five writers at a time:**

| round | pages | first run passed | batch of ten, seconds |
|---|---|---|---|
| 1 | 50 | 27 | 271–388 |
| 2 | 50 | 26 of 47 reported | 222–394 |
| 3 | 50 | 33 | 274–338 |
| 4 | 50 | 26 | 304–407 |
| 5 | 37 of 50 | not reported | — |

Rounds 2 and 5 stopped at the spend limit. Round 2's batches were
handed out again, and three pages that had already passed (c0009, c0060,
c0210) kept their pages, their run counts unreported. Round 5's 37
passing pages are kept the same way, and its 13 open cards went into
the recast below. `tools/corpus_batch.py` takes a card as written once
its page has passed. A draft's failed record leaves it open.

**Two rules added to the brief after round 2, each from what the first
150 pages did:**
- **A line a reader reads as one is one block.** A number and its
  heading go in one element, never two flex items or two positioned
  boxes. `pdfpage.split_paragraphs` counts runs of one-line blocks
  side by side on one row:

  | rounds | runs | pages |
  |---|---|---|
  | pilot | 45 | 17 |
  | 1–2 | 14 | 7 |
  | 3–4 | 7 | 6 |
- **Name words are seeds**, to be used in the form a real name takes. A
  third of the first 150 pages had joined the two into one name with
  "&". Round 4 has none.

**The checker no longer re-shoots a PDF page.** `corpus_check --all` had
been treating a PDF page like a generated one, which would have
overwritten the PDF's own render with the twin's screenshot. It now
skips them, and refuses a PDF page named on its own: the gate
(`tools/corpus_pdf.py gate`) is their check.

**PDF pages, the second ten and the third (2026-10-26).** Each document's
own copyright statement was read before its page was taken, not just
its source's general licence:

| page | source | kind | rows | worst across | worst down |
|---|---|---|---|---|---|
| c0074 | IRS Form 8822, p1 | application form | 58 | 2.3 | 5.3 |
| c0075 | IRS Form 2441, p1 | numbered-box tax form | 150 | 9.4 | 8.4 |
| c0076 | HMCTS Form N1, p1 | application form | 36 | 12.5 | 1.6 |
| c0078 | Istat, survey questionnaire, p31 | questionnaire | 60 | 6.3 | 1.3 |
| c0083 | BOE-A-2025-12818, p45 | numbered-box tax form | 82 | 4.7 | 3.9 |
| c0272 | Federal Reserve, FOMC minutes, p2 | minutes | 24 | 0.1 | 3.2 |
| c0273 | BOE-A-2025-1733, p5 | status report | 127 | 7.5 | 1.8 |
| c0274 | DOE, FY 2024 performance report, p19 | status report | 68 | 10.4 | 2.7 |
| c0413 | Istat Working Paper 7/2023, p10 (CC BY 3.0 IT) | paper page | 44 | 0.6 | 2.7 |
| c0082 | DVLA, form MIS1065, p3 | application form | 15 | 0.3 | 3.5 |
| c0351 | ESFA, letter to accounting officers, p1 | letter | 38 | 0.3 | 4.9 |
| c0411 | arXiv:2610.30900, p6 (CC BY 4.0) | paper page | 97 | 10.6 | 14.7 |
| c0412 | arXiv:2610.29500, p3 (CC BY 4.0) | paper page | 118 | 5.4 | 14.3 |
| c0472 | Interior Business Center, 2026 payroll calendar, p3 | timetable | 87 | 2.4 | 7.1 |
| c0474 | NIST SP 250, fee schedule, p36 | price list | 73 | 2.2 | 4.8 |
| c0196 | GSA/Treasury, SF 1034 public voucher, p1 | invoice | 88 | 1.2 | 5.6 |
| c0197 | GSA, OF 347 order for supplies, p1 | purchase order | 101 | 0.5 | 6.3 |

Two pages were dropped (`tools/corpus_pdf.py drop`, each recorded in the
cards' history):
- **c0271**: an Ofsted report of 2011 that allowed copying "for
  non-commercial educational purposes" only, despite its source's open
  licence.
- **c0077**: IRS Schedule A, whose twin stayed one row short because of
  a fault in the gate. A word set at the end of a line ("got a benefit
  for it,"), where the line's other words sit under the row above, is
  banded into that row. The fault is left unrepaired, since PDF work
  stopped.

**The gate's rows were rebuilt on the second ten.** It had refused true
twins. The cause was banding: a browser's line boxes are taller than a
PDF's, so a twin's rows merged where the PDF's did not. Each attempt
below was run over the nineteen pages then taken:
1. cutting both sides at 3 em gaps: 13 of 19 failed;
2. matching against whole twin bands: 3 failed;
3. bands with a fixed centre and the stacking rule: 3 failed;
4. pieces cut at gaps and at jumps to another line, with hard and soft
   ends: 19 of 19 passed.

§P step 6 states the gate that shipped.

**The twins' type set back to the page's sizes.** To get past the old
banding, writers had shrunk the type. The nineteen twins' median sizes
ran 0.84–1.02 of the page's, six under 0.90. Ten twins were reset, and
they now run 0.91–1.02. The gate's type pointer (`TYPE_SIZE`, 10%) lists
any run still off.

**A known fault left in.** Some text layers drop the "fi" ligature.
c0082's spells "specifc" and "ftness", and its twin had to copy them to
pass. Because PDF work stopped and the set stays as it is, this was not
repaired: a converter that reads "specific" off that page is marked down
on three words.

**Alessandro's decision, 2026-10-27:** "keep current set of pdf as is
and not add further pdf — complete task by focusing on generated pages
now but prefer to generate a varied mix of small and large pages keeping
some good doc content variability but liberally use smaller ones now
(for instance acting like a zoom to specific doc layout item maybe to
represent more often) because we finish session tokens quickly". The
PDF set stops at 27 pages. `tools/corpus_cards.py --zoom 130` was run
once, at seed 20261024 plus the history's length:
- **The 73 open PDF slots became generated cards**, each keeping its
  family and language. Its kind is the one its family has fewest cards
  of.
- **130 cards became parts** (`cards.zoom`, `Card.scope = "part"`): one
  part of a document of their own kind, as if zoomed in or cut out,
  500–800 px wide, carrying three features. They were drawn from the
  unlocked whole cards of kinds wider than a part, in 8 families and 46
  kinds. Their word floor is halved, as a fragment's is, and the brief
  says what a part is ("A part").
- **No page that passed was touched.** The top-up kept every feature at
  its minimum, and 144 cards changed in all. The corpus is now 573
  generated and 27 PDF pages.

Of the 236 cards left after the recast, 130 are parts. Of the 106 whole
ones, 21 are fragments, 19 receipts and a few nutrition labels; the rest
are whole pages, kept for range.

**The last five rounds, 2026-10-27 to 2026-10-30**, written by a
`corpus-writer` agent (Sonnet, its brief built in) per batch of ten, up
to eight at a time:

| round | pages | first run passed | batch of ten, seconds |
|---|---|---|---|
| 6 | 18 of 60 | not reported | — |
| 7 | 60 | 24 | 553–675 |
| 8 | 80 | 45 | 457–599 |
| 9 | 9 of 78 | not reported | — |
| 10 | 69 | 26 | 507–633 |

Round 6 was stopped by an interrupt and round 9 by the spend limit. The
pages each had passed were kept, and its other cards went to the next
round. A batch of ten cost its writer 103,000–137,000 tokens.

**Two pages had been edited after their last validator run**: c0042
(round 6) and c0268 (round 9), each left by a writer stopped mid-loop.
Their records named another file. The manifest test's re-shoot found
c0042, and a hash comparison over all 600 records found both. Both were
run again and passed. `tests/test_corpus_manifest.py` now holds every
record to the files the manifest names.

**Done 2026-10-30:** all 600 cards have a passed page: 573 generated
and 27 PDF.

### Step 6 — done 2026-10-30

- **The 31 carded by hand** in `corpus/known.json`:
  - family and kind come from each page's name;
  - arrangement, main face and style were judged by eye from one sheet of
    the 31;
  - features are what the validator detects on each page;
  - density is set from words per 1000 px;
  - no locale is set, because the pages declare a language only
    (nonlatin_0014 declares `el`).

  All 31 go to dev, and their files stay where they are.
- **The deal** is `pools.deal`, seeded with the cards' seed:
  - 200 to each pool: 191 generated and 9 PDF pages each;
  - each family split within two pages;
  - the pilot in dev;
  - every feature on at least two pages in every pool.
- **The L3 set** is 36 panel pages, four from each of the nine families,
  nine of them parts. It holds no PDF page. Nine of the panel's 200 are
  PDF pages, with as many features as the rest (median 4), and the
  cover, which takes whatever page adds most, took none of them. Whether
  L3 should carry a real PDF page is a question for its spec.
- **`tools/corpus_manifest.py`** writes `corpus/manifest.json` (631
  pages: pool, card, files and their sha256) and `corpus/l3-subset.txt`.
  It refuses while any card lacks a passed page.
- **`doc_to_html.corpus`** gains three calls; `SOURCES` and the old splits
  are unchanged:
  - `names("dev" | "panel" | "l3")` returns a pool's pages;
  - `names("vault")` raises `SealedError` unless called with
    `unseal=True`;
  - `page(id)` returns any corpus page as a `Source`.
- **`tests/test_corpus_manifest.py`** checks:
  - every file's hash;
  - every record against its files;
  - the deal and the L3 set reproduced;
  - the vault refusing;
  - 60 fixed generated pictures re-shot and equal to the pixel, about a
    second each.

  `tools/corpus_check.py --all --dry` re-checks every page; it is too
  slow for the suite.

## Outcome — the corpus

Done 2026-10-30, on branch `level-up`. **631 pages, every one passing**:
600 from the cards, plus the 21 and the ten probe pages. Nobody has
converted a page, and nobody has opened a vault page since the deal. The
manifest (`corpus/manifest.json`) is the inventory.

**Checked together at the end, 2026-10-30:**
- `tools/corpus_check.py --all --dry` passed 573 of 573 generated pages,
  in 2155 s;
- `tools/corpus_pdf.py gate` passed 27 of 27 PDF twins.

### What it holds

| origin | pages | what |
|---|---|---|
| generated, whole | 393 | a whole page of its kind |
| generated, part | 130 | one part of a document of its kind, zoomed in or cut out, 500–800 px wide (Alessandro, 2026-10-27) |
| generated, fragment | 50 | a table, chart, map, form section or diagram on its own |
| PDF | 27 | a real PDF page; its picture is the PDF's render, its ground truth an HTML twin that passed the gate |
| corpus and probe | 31 | the 21 and the ten probe pages, carded by hand |

**Families and kinds** (the 600 cards): reports 96, transactional 94,
forms 91, publishing 55, correspondence and legal 54, reference 54,
credentials 53, presentation 53, fragments 50: **60 kinds**. Receipts
are 40, and the three clinical kinds 40 together, as §4.7 asked.

**Languages**: English 449 (en-US 229, en-GB 220), French 50, Italian 50,
Portuguese 26 (pt-PT 17, pt-BR 9), Spanish 25.

**Size.** Generated pages are 228–1803 px tall, median 729.
- Whole pages: median 860 px wide, 809 tall, 237 words.
- Parts: median 740 px wide, 593 tall, 200 words.
- Fragments: median 519 tall.
- By density, the median words are 357 dense, 214 medium and 138 sparse.

The corpus is 83 MB on disk.

**Pools**:

| pool | pages | generated | PDF | known |
|---|---|---|---|---|
| dev | 231 | 191 | 9 | 31 |
| panel | 200 | 191 | 9 | — |
| vault | 200 | 191 | 9 | — |

Each family is split within two pages across the pools. The L3 set is 36
panel pages, four per family.

### Coverage

The rule was every feature on at least 9 pages in at least 3 kinds, and
2 pages in every pool. **It is met for all 54 feature ids**:
- the fewest pages: `text.drop_cap` on 11 pages in 7 kinds, then
  `list.big_steps` on 12 and `fmt.eu_numbers` and `look.buttons` on 13;
- the fewest in a pool: 2, for `fmt.eu_numbers`, `look.buttons` and
  `text.drop_cap`.

Pages per feature, family by family (`tools/corpus_cards.py --table`):

```
feature                pages kinds  frm trn rep cor pub ref crd prs frag
------------------------------------------------------------------------
arr.one_column           259    54   44  46  35  33  16  26   8  13  38
arr.two_columns           91    42   19   6  21  12  14   6   3   6   4
arr.three_columns         22    15    4   0   4   0   6   8   0   0   0
arr.sidebar               83    39   11   5  14   9  13   6  16   3   6
arr.cards_grid            36    17    0   0   7   0   6   8   0  15   0
arr.panels_side_by_side    54    25   13  13  15   0   0   0   4   9   0
arr.centred               55     8    0  24   0   0   0   0  22   7   2
type.serif               201    55   30  23  30  17  30  15  22  13  21
type.sans                355    60   54  48  64  36  24  38  31  35  25
type.mono                 44    19    7  23   2   1   1   1   0   5   4
table.ruled              114    45   13  20  26   5  10  16   4   3  17
table.spanning            51    32    9   1  12   0   2   9   6   5   7
table.section_rows        43    25    6   4   9   0   6  11   0   0   7
table.totals              43    31    6  16   4   3   5   4   0   0   5
table.empty_cells         68    32   18  15  13   0   0  12   0   3   7
table.zebra               49    32    6  17   8   0   4   4   0   2   8
table.subrows             33    21    4   2  11   0   3  12   0   0   1
table.long                22    15    6   9   2   0   0   5   0   0   0
kv.inline                 86    42    9  22  13  11   2   7  14   4   4
kv.over                   96    41   18   8  16   5   4   9  20   9   7
kv.two_per_line           56    34   14  12   6   3   2   5   7   1   6
kv.leaders                52    31   11   9   8   6   2   6   4   0   6
kv.boxed                  67    32   20  19  12   2   1   2   6   2   3
list.bullets              95    43    5   8  21  16   5   9   9  11  11
list.numbers              85    39   11  10  14   9   9   4   0  11  17
list.nested               37    23    5   0  13   5   5   1   4   4   0
list.ticks                77    33   25  11  16   6   1   3   0  10   5
list.clauses              40    21   13   6   5  16   0   0   0   0   0
list.big_steps            12    10    3   0   0   0   4   0   0   5   0
text.justified            50    24    9   0  10  17  12   1   1   0   0
text.footnotes            72    35    6  13  12  12   3   9   0   2  15
text.supsub               58    32    3   6  20   2   7   6   0   3  11
text.formula              16    10    1   0   3   0   9   0   0   0   3
text.quote                31    15    0   0   2   5   9   0   5  10   0
text.drop_cap             11     7    0   0   0   4   7   0   0   0   0
type.display              64    37    9   5   5   4   6   6  14  12   3
type.script               30    19    5   0   0   5   3   2  10   5   0
type.small_caps           66    37   10   7   7  10   5   5  13   5   4
type.weights              82    44    7  11  11   6   7   9  15   8   8
look.accent              110    53   11  17  17  11   6  10  13  12  13
look.dark_ground          21    15    0   1   1   0   4   0   6   7   2
look.bands                98    47   17  22  16   8   9   4   6   7   9
look.chips                44    25    3   4   2   0   2   7  11  11   4
look.buttons              13    10    5   3   0   0   0   0   0   5   0
look.rules                91    43   10  26   9  11   5  10   9   4   7
fig.logo                  77    41   12  17   8  12   5   8   6   8   1
fig.chart                 43    18    0   5   8   0  15   0   0   5  10
fig.code                  63    30    9  22  10   0   6   4   7   5   0
fig.signature             54    26   11   9  10  14   0   0   9   0   1
fig.photo                 24    14    3   0   0   0   5   1   6   9   0
fig.icons                 67    38    5   5   3   6   8   6  13  12   9
fmt.eu_numbers            13    11    0   3   5   1   1   0   0   1   2
fmt.dates                102    47   13   9  21  13   7   4  18   7  10
fmt.currency              66    34    4  16   2   5   4  11   0  11  13
families: frm = forms, trn = transactional, rep = reports, cor = correspondence and legal, pub = publishing, ref = reference, crd = credentials, prs = presentation, frag = fragments
```

### Time and cost

- **Writing.** The batch times recorded add up to 21,297 writer-seconds,
  about 5.9 hours. Rounds 5, 6 and 9 and the PDF twins are not in that
  total, because their reports were lost. A round ran five to eight
  writers at once, so each round took the wall-clock time of its slowest
  batch, 5 to 11 minutes. In rounds 7 to 10, a batch of ten pages cost
  its writer 103,000–137,000 tokens.
- **Validator runs.** Of the 493 pages whose run counts were reported:
  - 259 (53%) passed on the first run;
  - 188 took two runs;
  - 35 took three;
  - 11 took four or five.
- **Whose writing.** The ledger (`corpus/written.json`) records all
  573 generated pages: 559 written by Sonnet and 14 by Opus, the Opus
  ones in the pilot. Its one other entry is c0471's twin.
- **Spend limits.** Rounds 2, 5 and 9 stopped at the monthly spend limit,
  and round 6 at an interrupt. Each was resumed from what had passed.

### Dropped, and why

- **c0271** (PDF): an Ofsted report of 2011 that allowed copying for
  non-commercial educational purposes only.
- **c0077** (PDF): IRS Schedule A, whose twin stayed one row short
  through a gate banding fault (step 5), left unrepaired once PDF work
  stopped.
- **No generated page was dropped.** c0042 and c0268 were re-validated
  after edits their writers made after passing.

### The PDF pages by source

Every page's own copyright statement was read before it was taken.
`corpus/pdf/ATTRIBUTION.md` names each one:

| source | licence | pages |
|---|---|---|
| US federal agencies: IRS, GSA, Federal Reserve, DOE, NIST, Interior | public domain (17 U.S.C. 105) | 10 |
| UK government (HMRC, HMCTS, DVLA, ESFA), GOV.UK | Open Government Licence v3.0 | 4 |
| Istat | CC BY 4.0 (three); CC BY 3.0 IT, as the paper states (one) | 4 |
| BOE | reuse for any purpose, with the source named | 3 |
| arXiv | CC BY 4.0, paper by paper | 3 |
| INSEE | Licence Ouverte 2.0 | 2 |
| Receita Federal, via the State of Acre | a blank form, not protected (Lei 9.610/98 art. 8 IV) | 1 |

By language: English 17, Italian 4, Spanish 3, French 2, Portuguese 1.
By family:
- forms 9;
- reports 6;
- publishing 5;
- reference 3;
- transactional 2;
- correspondence and legal 2.

### The contact sheets

- **The pilot's 100** (step 3) were reviewed by Alessandro and kept.
- **The PDF pilot's ten** (step 4) were reviewed by him: "pdf choice and
  conversion 10 cases are good".
- **Every PDF twin** was opened beside its page by Claude. Three faults
  were found:
  - c0073 drew its selected radios empty. Fixed.
  - c0412 squeezed a display fraction into its bar. Fixed 2026-10-30.
  - c0196 draws two rules through their labels. Left as it is: the
    picture converted is the PDF's own, and the twin's words and their
    places are right.
- **48 pages drawn at random from those written since the recast**
  (`debug/corpus-sheets/since-recast-*.png`, seed 20261030) were
  judged by Claude:
  - every one reads as a document of its kind;
  - each part reads as a section cut out of a larger document;
  - no two pages share a look.

### Where it differs from the plan — accepted by Alessandro, 2026-10-30

"Deviations are fine." `level-up.md` §8, decision 7, records it.

- **27 PDF pages, not about 100.** Alessandro, 2026-10-27: "keep current
  set of pdf as is and not add further pdf". Their 73 slots became
  generated cards of the same family and language.
- **130 parts and 50 fragments.** Both were Alessandro's choice:
  fragments after the pilot, parts on 2026-10-27. So 180 of the 573
  generated pages are smaller than a page.
- **The known faults.**
  - c0082's twin copies the PDF's "specifc" and "ftness", where the
    picture prints "specific" and "fitness": the text layer drops the
    ligature, and the gate counts characters.
  - The gate bands a line-end word into the row above when the line's
    other words are stacked under that row (c0077).

  Both are recorded and not repaired.

---

## Handover prompt — L2, spec 0021

Written 2026-10-30, when this spec closed. Paste it into a fresh chat.

> Plan, then build, **L2 of the level-up plan: measurement and the
> judge**, as spec 0021, on branch `level-up`. Its outline is spec
> 0020's "What comes after this spec", L2.
>
> **Read first, in order:**
> 1. `CLAUDE.md`'s READ THIS FIRST;
> 2. `docs/status.md`;
> 3. `docs/level-up.md`: the Gist, §4.9, §6, §7 and §8;
> 4. `docs/agents/review-criteria.md`;
> 5. `docs/specs/0020-the-corpus.md`: "Outcome — the corpus" and "What
>    comes after this spec";
> 6. `docs/agents/visual-review.md` and `.claude/skills/visual-review/`,
>    the skill L2 evolves.
>
> **The corpus is built and sealed.**
> - It holds 631 pages in `corpus/manifest.json`.
> - `doc_to_html.corpus.names("dev" | "panel" | "l3")` returns a pool's
>   ids, and `page(id)` returns any page as a `Source`.
> - The vault raises `SealedError`. Never pass `unseal=True`: only
>   Alessandro opens it, at a milestone.
> - Three kinds of page need care in a check:
>   - **A PDF page**: its picture is the PDF's render and its HTML a
>     twin, so measure height against the PNG.
>   - **A part**: one section of a document, cut at its edges.
>   - **c0082**: its twin spells "specifc" and "ftness" as the text
>     layer does, where the picture prints "specific" and "fitness".
>
> **Order:**
> 1. Write the spec (`docs/specs/0021-…md`) from the outline, with
>    every fact in it re-measured, and open its issue.
> 2. Ask Alessandro to approve the plan before building.
> 3. Build it, each step its own commit with its tests.
> 4. Prove it on the 31 known dev pages first. It must catch the faults
>    already known there: the lab report's shifted results, the recipe's
>    interleaved steps, the quiz's merged cells.
>
> **L2 changes no conversion code** (`level-up.md` §6: L1–L3 change none).
> It measures and reviews.
>
> **Stop and ask Alessandro:**
> - at the plan;
> - before any conversion run longer than two hours. The probe took about
>   8 minutes a page, so dev's 231 pages are about 31 hours; the batch
>   runner must be detached and resumable;
> - before building the review page (an Artifact with a database; load
>   the `artifact-capabilities` skill first);
> - whenever his calls on the review page disagree with the checks.
>
> **At the end:**
> - write the outcome;
> - update `docs/status.md`, `CLAUDE.md` and `level-up.md` §6;
> - close the issue;
> - write a handover prompt for L3, the honest baseline on
>   `corpus/l3-subset.txt`.

## Handover prompt — this spec, as it was given

> Implement spec 0020, `docs/specs/0020-the-corpus.md` (issue #43), in
> this fresh session: the corpus of 600 pages, step L1b of the level-up
> plan.
>
> **Read first, in order:**
> 1. `CLAUDE.md`'s READ THIS FIRST;
> 2. `docs/status.md`;
> 3. `docs/level-up.md`: the Gist, §4 and §8;
> 4. `docs/agents/review-criteria.md`;
> 5. the spec, end to end.
>
> Work on branch `level-up`. This spec changes no conversion code and runs
> no conversion.
>
> **Order.** Step 0 first: re-check its facts, then ask Alessandro its
> three decisions (how pages are written, with subagents recommended;
> storage; language shares). Then steps 1–7. Each step is its own commit,
> with its tests.
>
> **Stop and ask Alessandro:**
> - at step 0's decisions;
> - at the pilot's contact sheets (step 3);
> - before downloading any PDF source, with its licence (step 4);
> - if the coverage rule cannot be met.
>
> **The rules that keep the corpus honest:**
> - every page passes the validator (§V);
> - a PDF's picture and text layer are never edited, and a twin that
>   cannot pass is dropped;
> - the words a reader sees are text nodes, and figures carry no words;
> - nobody converts or opens a vault page.
>
> **At the end:**
> - write the outcome section;
> - update `docs/status.md`, `CLAUDE.md` and `level-up.md` §6;
> - close #43;
> - write a handover prompt for L2 (spec 0021) from the spec's "What
>   comes after".
