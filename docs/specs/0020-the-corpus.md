# The corpus: 600 pages, chosen by their variability

**Status: in progress, issue #43. Steps 0–2 done 2026-10-24 ("Outcome —
the steps").**
- **This is step L1b** of the level-up plan
  ([`../level-up.md`](../level-up.md) §6), on branch `level-up`.
- **It is written to be run in a fresh chat.** Everything it needs is here
  or linked.
- **It builds** 600 new pages, each an HTML file and the picture converted
  from it, in three pools of 200: dev, panel and vault. About 100 of them
  are real PDF pages. It also writes cards for the 31 pages we already
  have, which join dev.
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
6. **The gate.** A page is admitted only if all three hold:
   - **words:** the twin's projected words equal the text layer's, as a
     multiset, after normalising ligatures, soft hyphens and white space;
   - **lines:** every PDF line's word sequence is one line of the twin's
     projection;
   - **geometry:** each line's top and left lie within 1.5% of the page's
     width of the PDF's, scaled. Measure the spread on the pilot of 10
     and state the threshold before admitting more.
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

## Outcome — the corpus

*To be written at step 7.*

---

## Handover prompt

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
