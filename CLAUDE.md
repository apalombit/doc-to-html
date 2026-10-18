# doc-to-html

## Agent skills

### Issue tracker

Issues live as GitHub issues in `apalombit/doc-to-html`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Visual review

**Look at the output, not only at the numbers.** The `visual-review` skill
(`.claude/skills/visual-review/`) builds one sheet per document — source,
optionally the previous run's render, and this run's render, all at the source's
width — and a rubric to answer by opening them. Run over all fifteen documents
on 2026-09-21 it found nine cross-cutting faults that **no scored axis had
reported**.

`doc_to_html.review` is the code and `tests/test_review.py` pins it;
`tools/visual_review.py` is the command line. `--previous <run>` is the
render-against-render comparison the T1 ratchet is built on; `--check` tallies
the answered `findings.json` and names every `major` that sits beside scored
ratios all at 1.000. `docs/agents/visual-review.md` is the record: the evidence
behind the rules, what the rubric must never become, and the remaining gaps.
**The rubric is not frozen** — seven axes with two passes behind them, and a
trial axis is kept rather than rejected.

### Specs

Each piece of work gets a spec in `docs/specs/`, one file per piece of work, each
tracked as a GitHub issue. **Read the spec before the code** — it carries the
measured numbers and what has already been tried and rejected. **0017 is
open** — issue #40, two render steps built 2026-10-18, Alessandro's
decision pending. 0016 (issue #39) is done and decided, swept as
`S12-sweep`, the baseline. 0008 to 0015 (issues #31–#38) are done and
decided. 0007 still defines the target.

---

## READ THIS FIRST — the target changed on 2026-09-17

**`docs/specs/0007-look-like-the-document.md` is authoritative. Where this file
disagrees with it, the spec wins.** Its tracking issue, **#30**, closed on
2026-10-10 when its work plan finished; the target stands.

The project no longer optimises agreement between the IR and a hand-typed
reference IR. **It optimises whether the rendered output looks and reads like the
source document.** `acceptance.compare()`, `tests/fixtures/*.py` and every
mismatch total this file used to carry are deleted.

**Why, in one paragraph.** Someone finally opened
`debug/runs/84-rule-not-a-line/<fixture>/05_rendered.png` beside
`01_layout_input.png`. `sample_table_0003` scored a **full match** while having
deleted all five of its table's column headers — the harness compares `RowRole`
sequences and never compares cell *content*. And runs 81→84 improved the total
23→10 while *introducing* duplicated titles in three of five documents. The
measure had saturated, and past that point it was steering the wrong way. Spec
0007 carries the full evidence, including the exact JSON and the exact prompt
line that caused the deletion.

**Where the project is — 2026-10-18: the baseline is `tests/frozen/s12-result/`, spec 0016's sweep; spec 0017's two render steps are built, his decision pending. Work is judged by eye.**

```
Thread 0    Scorer, corpus, report                  DONE 2026-09-18
Phase A-1   Nothing loses content quietly           DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, zero model calls  DONE 2026-09-22
Phase A0    Stop the bleeding                       DONE 2026-09-22, gate MET
Phase A1    Inline runs, hard line breaks           DONE 2026-09-25, gate NOT met
Phase A2    Geometry, re-scoped                     DONE 2026-09-25, gate MET
Phase A3    Figure pixels                           DONE 2026-09-26, gate MET
Queue       Open issues 1-3, Q1-Q5, N1-N4           DONE 2026-09-26 to 2026-10-10
RESET       2026-10-10, Alessandro: every open task and idea cleared —
              Q6, Q7, N5, the live-fault list, Threads 3/C and 4/D.
              Fresh sweep F1-sweep on 12fa2d1
Spec 0008   Page structure — opened 2026-10-10 from his review of
              F1-sweep, issue #31. Three steps, in order:
              1 structure from pixels, offline              DONE, gate MET
              2 carry it in the IR and draw it, offline     DONE, gate NOT met
              3 let it shape the boxes, one sweep           DONE, gate NOT met
              sweep S3-sweep on 9c42d81 — DECIDED 2026-10-11: the new floor
Spec 0009   Four repairs after the structure step, one sweep — planned
              2026-10-11 from his review of S3-sweep, issue #32:
              0 freeze S3-sweep as tests/frozen/s3-result/  DONE, gate MET
              A wire row nets  DONE    B cut at a grid's inner splits DONE
              C the detector's own sections DONE   D separators DONE (width dropped)
              E sweep S4-sweep on b80b7f0                DONE, gate NOT met
              its floor decision folded into spec 0010's
Spec 0010   Five repairs, the beside score, type at the page's size —
              2026-10-11 from his review of the S4-sweep analysis, issue #33:
              A vetoed caption kept, title echo keeps a value  DONE
              B grid drawn as a grid, two Probes, polarity   DONE
              C beside by row groups                         REVERTED
              D type at the page's size                      DONE
              E sweep S5-sweep on 4a5fe3f, prediction held, ratchet
              falls on five documents, each named
              DECIDED 2026-10-12: S5-sweep is the baseline, the five legs accepted
Spec 0011   Place every entry where the page puts it — planned 2026-10-12
              from his review of S5-sweep, issue #34:
              0 freeze S5-sweep as tests/frozen/s5-result/   DONE
              1 rhythm DONE  2 locate DONE  3 fields DONE
              4 lines: 4a size, weight, italic DONE  4b colour DONE  4c rules DONE
                       4d leaders DONE  4e spacing DONE  4f typeface DONE
              5 sweep S6-sweep on 7c12935, prediction held, 14 pages better
              DECIDED 2026-10-13: S6-sweep is the baseline, frozen as s6-result/
Corpus      six held-out documents added 2026-10-13, the fifteen kept;
              sweep S7-sweep over all 21, prediction held on the fifteen,
              pricing's crash fixed downstream (9cd4ae2)
              DECIDED 2026-10-13: S7-sweep is the baseline, frozen as s7-result/
Spec 0012   Draw what the page draws — planned 2026-10-13, issue #35:
              the report notebook from S7-sweep, faults grouped G1-G9,
              workflow changes; groups G1-G9 in order, the upstream halves
              in step U, then ONE sweep S8-sweep over all 21
              0 ASKED DIFFERENTLY  G1-G9 DONE, each judged by eye
              U  DONE, the sweep's prediction registered
              S  S8-sweep on ba0c110, 2026-10-14: prediction held,
                 18 pages better, 3 worse — receipt and statement from
                 step U's column count, certificate from its unwarped layout
              DECIDED 2026-10-14: S8-sweep is the baseline, frozen as s8-result/
RESET       2026-10-14, Alessandro: everything not in spec 0013 cleared —
              spec 0012 §7's list, the faults on S8-sweep's sheets 0013
              does not name, every earlier queue and idea
Spec 0013   Four pages first — planned 2026-10-14, issue #36:
              1 receipt: the column count only where the table draws them
              2 certificate: its width inside two frames
              3 pricing: three cards, not scattered sections
              4 certificate: its groups on the unwarped page
              5 ticket: the paper's whole outline in rectify
              6, 7 lower priority: paper's caption row; type on a fill
              each DONE, judged by eye
              S  S9-sweep on a3969f3, 2026-10-14: prediction held to the
                 byte, 7 pages better, 13 same, 1 worse (ticket)
              DECIDED 2026-10-14: S9-sweep is the baseline, frozen as s9-result/
Spec 0014   Every printed line has a place — planned 2026-10-14 from his
              ask for general, principled repairs, issue #37:
              1 Zone.extra: lines a Zone's Kind has no place for, drawn
              2 read what nobody read: locate's unclaimed lines, each
                read on its own crop, a separate pass
              3 copies take the Kind that keeps the most of a line
              1, 2 DONE, each judged by eye; 3 built, the catalogue
                worse — DROPPED, Alessandro 2026-10-14
              S  S10-sweep on a53f11b, 2026-10-15: prediction held to
                 the byte, 3 pages better, 18 same, none worse
              DECIDED 2026-10-15: S10-sweep is the baseline, frozen as s10-result/
RESET       2026-10-15, Alessandro: everything not in spec 0015 cleared —
              the recap's other groups, spec 0014's directions, the
              wordmark question
Spec 0015   Every line read, and drawn where the page puts it — planned
              2026-10-15, issue #38; ticket and certificate the focus:
              1 read the lines nobody reads (locate.unclaimed widened)
              2 pairs drawn as the page prints them
              3 side by side where the page puts it: band lanes, dividers
              1-3 DONE, each judged by eye
              S  S11-sweep on 6b1caf4, 2026-10-16: prediction held to
                 the byte, 6 pages better, 15 same, none worse
              DECIDED 2026-10-17: S11-sweep is the baseline, frozen as s11-result/
RESET       2026-10-18, Alessandro: everything not in spec 0016 cleared —
              spec 0015's ranked directions, the other pages' left
              faults, display type, borrowed looks, marks, bold
Spec 0016   Structure first — one grid where the page sets one, one strip
              where it draws one — planned 2026-10-18, issue #39; the
              ticket's layout the focus, structure not words:
              1 one column grid per line-drawn Zone (render._placed)
              2 one grid across side-by-side Zones (render._band)
              3 a drawn strip is one container (fills, top bands)
              4 two locate guards; 4a, no Zone from a drawn fill's
                edge, DROPPED with the crop fix it called for
              1-4 DONE, each judged by eye
              S  S12-sweep on 3abb55d, 2026-10-18: prediction held to
                 the byte, 1 page better (ticket), 20 same, none worse
              DECIDED 2026-10-18: S12-sweep is the baseline, frozen as s12-result/
Spec 0017   Margins from the type, one size per role — planned 2026-10-18
              from his review of S12-sweep's ticket, issue #40; render only:
              1 margins from the type    2 one size per role    each DONE
              rederived over s12-result/: ticket better, catalogue same,
              nineteen byte-identical. DECISION PENDING; directions 3 and
              4 (photographed pages, Zones from drawn containers) next
```

What each step shipped and measured is in `docs/status.md` and the handover's
outcome sections; spec 0007 keeps the design record and what was rejected.

**How work is judged now — Alessandro, 2026-10-12, for spec 0011, carried
over by 0012 and 0013: by eye.**
Every step's sheets are opened against the previous step's, and each page is
judged better / same / worse with a sentence naming the element. Scores and
`report.html` are still produced and recorded. They **never gate a step and
never carry an argument**, and the ratchet described below is suspended as a
gate for the spec. The one number still read is the report's `vanished`
list, because content must match absolutely — it is a pointer to a page to
open, not a gate. He checks every run himself too. Spec 0011's "How to
work" is the full statement.

**The baseline is `tests/frozen/s12-result/` since 2026-10-18** — sweep
`S12-sweep` on `3abb55d`, spec 0016's, all **twenty-one documents**,
Alessandro's decision, frozen with its 749 answers, byte-identical to
`s11-result/`'s. Against `s11-result/` it drew one page better, the
ticket, twenty the same and none worse; no ratchet leg fell. The six added 2026-10-13
(`corpus.NEW`) stay **held out** — authored after every measure was tuned,
and reported in their own lines. Each earlier floor, and why it moved, is
in its README and in `docs/status.md`.

**Spec 0015, `docs/specs/0015-drawn-where-the-page-puts-it.md`, is
done and decided** — issue #38, `ticket_0020` and `certificate_0021` the
focus. Its "Outcome — the sweep" checks §1's tables row by row, lists
the faults left by stage and ranks the directions — record only; the
directions were cleared on 2026-10-18.

**Spec 0016, `docs/specs/0016-one-grid-one-strip.md`, is done** —
issue #39, the ticket's layout, structure first. Steps 1–3 and two
`locate` guards shipped; step 4a and the crop fix it called for were
measured and dropped (its §5). Its "Outcome — the sweep" checks §1's
table row by row. **Alessandro took `S12-sweep` as the baseline** on
2026-10-18, frozen as `tests/frozen/s12-result/`.
**Everything else was cleared by
Alessandro on 2026-10-18** — spec 0015's ranked directions, the faults
left on `S11-sweep`'s other pages, display type, borrowed looks, marks,
the stub strip's text, bold, the wordmark question and every earlier
queue; do not pick anything up unless he names it.
`docs/specs/0007-handover.md` holds spec 0007's prompts, as record.

**[`docs/status.md`](docs/status.md) is the live status — read it second, after
this section.** It says what is done, where the floor is, what is closed with
evidence, and what is queued. It is maintained, not archived: when it goes
stale, rewrite it rather than banner it.

### What Thread 0 built, and where it lives

| module | what it is |
|---|---|
| `corpus.py` | what the corpus is: twenty-one documents, an HTML file and a screenshot each, split *iterate* / *sweep*, and *new* for the six held out |
| `projection.py` | `project()` — one page as a reader perceives it, read off headless Chrome. **One function, both sides.** |
| `scoring.py` | `score_document()` — six axes between two projections. T1/T2/T3 hard tier, T1 a ratchet. |
| `report.py` | `debug/runs/<label>/report.html` — the review surface |

**`report.html` is what gets reviewed.** One page, every document, source left
and render right at matched width, scores above each pair with the delta
against the previous run, intermediate steps collapsed.
`tools/inspect_run.py`'s per-fixture `index.html` stays as it is and answers a
different question: how one document was converted, step by step.

**The scorer is developable with no model running.** `tests/frozen/run84/`
holds run 84's five output documents, copied in before `debug/runs/` was
cleared, and `tests/test_scoring.py` is Thread 0's exit gate: asked only
general questions, the scorer finds the deleted table header, the repeated Zone
Titles and the hard line breaks.

**Adding a document is writing an HTML file and running
`tools/shoot_corpus.py`.** No Python, no transcription. That is what let the
corpus leave five.

### The new criteria, in brief

Six axes scored source-image against rendered-output: **1 Completeness,
2 Order & grouping, 3 Layout skeleton, 4 Typographic weight, 5 Palette & texture,
6 Inline detail.** Axes 1–3 are a hard tier — a regression on any of them fails a
phase regardless of what improved elsewhere.

**The T1 ratchet: completeness may never decrease between phases, for any
reason.** Not a target to optimise; a floor never to cross. It is the rule that
would have caught all three faults that shipped as improvements. **Its recall
leg is `vocabulary_recall` as of 2026-09-22** — see below, and spec 0007's
"Why the ratchet's recall leg is now distinct tokens" for what moved it.

**T1 reports four numbers, and none of them is decoration.** Recall and
precision are token multisets, so they cannot see text that is all present, in
the right order, and *cut in the wrong place*: `Invoice #: 123` read as label
`Invoice` and value `#: 123` scores 1.000, 1.000 and tau 1.000.
`join_recall` — the adjacent-word pairs — is the only one that catches it, and
`Completeness.broken_joins` names the join that was cut.

**`vocabulary_recall` is the fourth, and as of Phase A0 it is the one the
ratchet is on.** Distinct source words the output still prints *somewhere*,
against the multiset's how many times. The change was forced by measurement:
removing a doubled Zone Title lowers multiset recall on six of the fifteen
documents while nothing leaves the page, because the echo had been standing in
numerically for a genuine occurrence elsewhere that the output never read.
`newsletter_0008` prints "Castleton Chronicle" in its masthead and its footer;
the output printed it twice in the masthead. Both are reported and a multiset
fall is worth reading — the **floor** is *no word the page shows stops being
shown*, and `Completeness.vanished` names what a failure caught.

Ground truth is **derived, not typed**: `example/foo.png` is a screenshot of
`example/foo.html`, so the expected answer is already on disk. One `project()`
function runs over source and output alike and the projections are diffed. Adding
a document is writing an HTML file — which is what lets the corpus leave five.

**The source and its screenshot agree exactly for the ten authored documents
— since 2026-09-29, and pinned by `TestTheCorpusPictureIsItsOwnHTML` — and
approximately for four of the original five.** Until that day this sentence
was false and nothing checked it: the ten had been shot before
`projection.SHOT_SLACK` and each was missing its bottom 60-90px, found by
re-shooting and diffing. Only `invoice.html` still
re-renders to its screenshot (0.74% of pixels differing); the other four differ
by 6.9–14.1%, in content *height* rather than position, because of fonts on
this machine — and `invoice2.html` additionally wants a CDN. So `height_ratio`
is measured against the **PNG's** own height, which is what the model was
shown, while T3's relations and column shares come from the re-rendered source.

### The review surface

**Every run produces `debug/runs/<label>/report.html`** — one page, every
document, source left and render right at matched width, intermediate steps
collapsed. This is what Alessandro reviews; he will not navigate per-fixture
folders. `tools/inspect_run.py`'s per-fixture `index.html` stays as it is and
answers a different question: how one document was converted, step by step.

---

## How runs are used here — read this before quoting any number

**A run number is not evidence. Take a measurement or say you do not have one.**

This file, `docs/specs/*` and many docstrings are full of run numbers and mismatch
totals. They are kept as a record of how decisions were reached. **They are not
citable**, and no conclusion may rest on them:

- `debug/runs/` is cleared regularly, so most of those runs cannot be re-opened.
- Historical runs differed on several flags at once, so their totals describe
  configurations that are neither the shipped one nor each other.
- Historical totals are not comparable *even where the pipeline is*, for the
  reasons above and below. **On the determinism question specifically, the old
  claim here was wrong and has been measured:** `transport.py` asks Ollama for
  `temperature: 0`, and on 2026-09-18 the five original documents came back
  **byte-identical** to the copies frozen in `tests/frozen/run84/` — all five,
  md5 for md5, on a later commit and with the model partly on the CPU. So on
  one machine, one model and one pipeline, *the conversion is reproducible*,
  and a byte-identical arm means **the change did nothing** rather than "noise
  swamped it". That is a legitimate comparison rather than a cited run: the
  frozen files are committed inputs, and the run was taken in the same sitting.
  It also confirms from the other side that the CPU/GPU split moves timings
  only. **This licenses nothing across machines, Ollama versions or models**,
  and says nothing about the other ten documents, which have no prior run.
- **Every total recorded before 2026-09-17 also measures a quantity this project
  no longer optimises.** Three separate breaks — the comparison changed
  (2026-09-11), the reference rectangles changed (2026-09-14), and the target
  changed (2026-09-17). Together they make every older number dead.

Compare only runs taken against each other, one change apart, in one sitting.
**This applies to Claude's visual judgements at least as strongly as to numbers:**
a rubric score from one session and a rubric score from another are not
comparable and must never be tabulated together. Judge pairwise — previous render
against new render, both against the source, side by side, now.

**The one exception, and it is narrow.** Scores over `tests/frozen/run84/` *are*
citable: the inputs are committed files, the scorer runs offline over them with
no model, and `tests/frozen/run84/README.md` tabulates them. They are the fixed
point every later measurement can be described against. Nothing from a *run* —
including `scores.json` — joins that exception, because a run involves the
model. A run's `report.html` computes its delta against the previous run's
`scores.json`, which is the pairwise comparison this section asks for, taken
automatically and in one sitting.

**The other exceptions are the frozen directories, and each exists because
`debug/` is gitignored and gets cleared.** Every one is a committed file whose
README states its provenance exactly. Quote them only for what their README
says they are.

| directory | what it is | role now |
|---|---|---|
| `run84/` | run 84's five output documents | the scorer's offline test input |
| `a1-checkpoint/` | Phase A-1's checkpoint scores, the ratchet's first notch | record |
| `a0-checkpoint/` | A0's starting notch | record |
| `a0-result/` | the scores A0 reached, sweep `100-a0-gate` | record — the floor 2026-09-24 to 2026-09-25 |
| `a1-result/` | A1's fifteen documents beside their scores | record — A2's control |
| `a2-result/` | A2's fifteen documents beside their scores, sweep `A2-10-enclosed-sweep` | record — the floor and A3's control 2026-09-25 to 2026-09-26 |
| `a3-result/` | A3's fifteen documents beside their scores, sweep `A3-10-figure-pixels-sweep` | record — the floor 2026-09-26 to 2026-09-29, measured on pictures missing their last lines |
| `reshot/` | the first sweep on whole pictures, `Q5-10-reshot-sweep` | record — the floor and the control 2026-09-29 to 2026-09-30 |
| `q5-result/` | Q5's fifteen documents beside their scores and the answers that made them, sweep `Q5-40-sweep` | record — the floor and the control 2026-09-30 to 2026-10-11 |
| `s3-result/` | spec 0008's fifteen documents beside their scores and the answers that made them, sweep `S3-sweep` | record — the floor and the control 2026-10-11 to 2026-10-12 |
| `s5-result/` | spec 0010's fifteen documents, scores and answers, sweep `S5-sweep` — frozen at spec 0011's step 0 | record — the baseline 2026-10-12 to 2026-10-13 |
| `s6-result/` | spec 0011's fifteen documents, scores and answers, sweep `S6-sweep` | record — the baseline for 2026-10-13, its fifteen held byte for byte in `s7-result/` |
| `s7-result/` | all twenty-one documents, scores and 751 answers, sweep `S7-sweep` | record — the baseline 2026-10-13 to 2026-10-14; four of its table answers are spec 0013 step 1's target |
| `s8-result/` | all twenty-one documents, scores and 725 answers, sweep `S8-sweep` | record — the baseline for 2026-10-14, until spec 0013's sweep |
| `s9-result/` | all twenty-one documents, scores and 732 answers, sweep `S9-sweep` | record — the baseline 2026-10-14 to 2026-10-15 |
| `s10-result/` | all twenty-one documents, scores and 735 answers, sweep `S10-sweep` | record — the baseline 2026-10-15 to 2026-10-17 |
| `s11-result/` | all twenty-one documents, scores and 749 answers, sweep `S11-sweep` | record — the baseline 2026-10-17 to 2026-10-18 |
| **`s12-result/`** | **all twenty-one documents, scores and 749 answers, sweep `S12-sweep`** | **the baseline, from 2026-10-18** |

**Score against the baseline by path**, and always with `--documents sweep` —
without a `fixtures.txt` the report silently scores the iterate five:

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --documents sweep --previous tests/frozen/s12-result/scores.json
```

**Each floor move was measured, not argued:** the new floor was no lower than
the old on any ratcheted leg of any of the fifteen documents, and Alessandro
took the decision each time — `q5-result/` over `reshot/` included: fourteen
documents byte-identical, the receipt's tau and beside up. **`reshot/` is the
one exception, decided in advance:** it corrects the pictures rather than the
pipeline, and its README names every leg on which it falls below
`a3-result` and why — four words and `cv_0013`'s reading order among them.
**`s3-result/` is the second, decided after review:** spec 0008 read
`cv_0013`'s and `darkdeck_0009`'s columns as columns, which costs the Band
render's cross-column T3 beside agreements, and `catalogue_0015` printed a
spec line for the first time with one `×` read as `x`. Its README names the
three legs. **`s5-result/` is the third**, five legs below `s3-result/`,
accepted 2026-10-12; its README names them. **`s6-result/` is the fourth**,
four beside legs below `s5-result/`, accepted 2026-10-13. **`s7-result/`
moves no leg**: it adds six documents, and its fifteen are `s6-result/`'s
byte for byte. **`s8-result/` was judged by eye**, the first floor taken
that way: three pages worse, each traced and accepted 2026-10-14, its
README names them. **`s9-result/` likewise**: one page worse, the ticket,
accepted the same day. **`s10-result/`**: no page worse, the ticket's tau
the one leg below `s9-result/`, accepted 2026-10-15. **`s11-result/`**:
no page worse, the timetable's tau and beside the legs below
`s10-result/`, accepted 2026-10-17. **`s12-result/`**: no page worse and
no leg below `s11-result/`, taken 2026-10-18.

**A directory holding documents beside scores buys a loop, not a number.**
Scored straight out of `s12-result/`, **21 documents, 0 differing fields**, and **`tools/rederive.py`
over it reproduces every page** at the commit it was taken on — 21 of 21
files byte for byte. When code downstream of the model moves, `rederive.py` brings
the IRs up to it — re-applying every step downstream of the model — and that,
not a plain re-render, is the baseline a change is measured one apart from. So a
change downstream of the model is measured pairwise, in about a minute, with
no model. Phases A2 and A3 measured every prototype they tried that way before
spending a sweep. **Any new downstream step that writes the IR must be added
to `rederive.py`**, or the loop measures yesterday's code. It is not a target
to match.

**A directory that also holds the answers buys a second loop.** `q5-result/`
was the first to carry `answers/`, and `s3-result/`, `s5-result/`, `s6-result/`, `s7-result/`, `s8-result/`, `s9-result/`, `s10-result/`, `s11-result/` and `s12-result/` carry them too — each document's model answers, in the
order they were asked — and **`tools/replay_run.py` serves them to today's
code through a real Conversion**: wire, mapper and every pass, which
`rederive.py` cannot re-run. With `--swap` it serves one new answer, so a
prompt change probed on one crop is measured on its whole document, ratchet
included, with no sweep. It reproduces `s12-result/` **21 of 21 byte for byte** from its answers. A
document it marks **ASKED MORE THAN THE RUN** is not a measurement: the
change moved a crop, and a crop costs a sweep. **It serves by pass and
order**, so a change that asks the same number of calls *differently* — a
grid hint of 9 rows where it was 4 — is served the old answers. **Since spec
0012's step 0 it says so:** every call's prompt, picture and schema are
hashed beside its answer, and a document whose calls moved is marked
**ASKED DIFFERENTLY — not a measurement**, naming each call. That list is
what a sweep's prediction is registered from (spec 0012 §6).

**A floor is not a result to quote in an argument** — the distinction the rest
of this section is about.

---

## Knowledge that survives the target change

### The Zone convention

**A heading and the content it names are one Zone, with the heading as
`Zone.title`.** `ir.Zone` never nests, so a Zone carrying a Title and its Blocks
is the IR's only vocabulary for containment — this is the model used as designed,
not DOM nesting smuggled in.

It was applied inconsistently until 2026-09-14: a card and every Bootstrap panel
were one Zone with a Title, while `<header><h1>+<nav></header>` was two Zones in
two Bands. Same shape, opposite readings. **The proof it was a definitional
disagreement rather than a page-reading failure is that fixing the code and
fixing the references landed on exactly the same total.** The detector groups
these regions; insisting they were two meant it could not be right.

**Author the next document to it.** Spec 0007's Phase A0 added a second rule on
top: a Zone carrying a Title must **not** also carry a Block repeating it.
`wire._without_title_echo` enforces it, and the corpus went **34 echoes to 0**
on 2026-09-22.

**That rule is about one Zone, and no across-Zone echo is measured on the
floor.** Both examples once filed as across-Zone turned out not to be.
`menu_0012`'s `To begin` was a Zone lying wholly inside another: **A2 closed
it in the detector**, with `without_enclosed`. `darkdeck_0009`'s
`AVAILABILITY` was one Zone all along — the caption pass lifted the first cell
of Zone 2's own header row into its Title — and
`wire._title_is_its_header_cell` drops that Title and keeps the row,
2026-09-26. Over `a3-result`'s 47 titled Zones, the only Title spelled
anywhere in another Zone is `AVAILABILITY` in Zone 9's column header, which
the source prints too.

### What must not be deleted

Four shipped defaults, each documented where it lives: `DTH_SNAP_ZONES` (boxes
onto their ink, 0.56 → 0.91 IoU, fixes no Kind), `DTH_TABLE_GRID_HINT` (state the
measured grid in the table prompt), `CLASSIFY_PROMPT` making typesetting decisive
rather than an aside, and `_reread_as_prose` acting on the Pairs Extractor's
`NotPairs` diagnosis. See each constant's docstring in `config.py`.

**Two dormant safety nets, and do not delete them on one run** — four runs
established the behaviour each guards. `wire._without_empty_rows` drops a
zero-cell row before the table width check (two runs lost a whole table and the
385.00 Probe to one such row). `_reread_as_prose` recovers a Zone the Pairs mapper
rejects wholesale.

**`_without_empty_rows` filtered on cell count rather than cell content, and
Phase A0 fixed the condition — 2026-09-22.** `if row.cells` is truthy for
`['', '', '', '', '']`, so a row of empty strings passed the net that exists to
drop it and rendered as a blank line inside the table. The net itself stayed:
the finding was that it tested the wrong thing, not that it should not exist.

**There are six wire-level row nets as of 2026-10-14, not one.** Each invents
nothing and discards nothing, and each exists because a measured run lost
content without it: `_without_empty_rows` (above), `_join_split_header_row`,
and `_without_repeated_header` — which drops a second `role == "header"` row
that spells the same as the first, the padding the model produces when the
grid hint asks for more rows than the table has. Spec 0009 added two for
`nonlatin_0014`'s totals, which were misplaced and doubled rather than lost:
`_trimmed_to_header` takes the leading empty cells off a row wider than the
header, and `_without_repeated_total` drops a summary row repeating the
summary above it. Spec 0013 added `without_title_rows`: a row whose printed
cells spell the Zone's Title goes, `paper_0018`'s caption returned as a
row after its data.

### The rectangle finder — `style.rectangles`, built in 2/B on 2026-09-21

It finds every box the page draws — cards, panels, bordered fields — for the
style record's borders and card treatment. **It is found on the page, never
grown from a Zone**: a snapped Zone sits on its *content* ink, and
`preprocess.content_ink` deletes rules by name, so the rule is invisible to
the thing that placed the box. Its docstring carries the measurement over
all fifteen documents, and its guard — a rectangle covering more than 0.80 of
the page is the page.

**Do not use it for *grouping*.** Wired into grouping, morphology produced
byte-identical boxes on all five original documents; Zones come from the
detector.

**The lesson it left, which generalises:** for a year three documents told
each session to *reuse* a finder that had never been committed — spec 0006
Change 3 measured it in a scratch script. **A claim in the docs that nothing
verifies is the project's recurring fault applied to itself.** Before relying
on something, prove it is there.

### Runs explain themselves

`trace.py` records every step of a Conversion — model calls *and* decisions — each
with a required `disposition` saying what became of its answer.
`tools/inspect_run.py` renders it in execution order:
GIVEN / ASKED / ANSWERED / HANDLED / RESULT per step, crop inline, prompts
collapsed. **Open `debug/runs/<label>/<fixture>/index.html` and read top to
bottom** when diagnosing one document; open `report.html` when comparing them all.
`trace.json` is in the dump for programmatic use.

### Standing knowledge about the model and the prompts

- **The `invoice_0002` panel question is answered.** Each panel opens with a
  **shaded caption bar**, which satisfies `CLASSIFY_PROMPT`'s own "top row set
  apart" test for a table. Withholding the bar fixes it; a prompt clause
  explaining the difference moved 0 of 6.
- **`DTH_CAPTION_PASS` ships on.** It reads each Zone's Title in its own call,
  then withholds the caption band from the Kind question. It withholds the band
  from the *Kind* question only — **not from the Extractor's crop**, and that is
  correct. **Phase A0 built the withholding, measured it, and reverted it on
  2026-09-22**: cutting the top band off `darkdeck_0009` z2, a row of four
  metric cards with no caption at all, deletes `P95 LATENCY`, `INGEST VOLUME`
  and `COST PER MILLION` — confirmed by opening the crop, not inferred — and it
  moves the measured column count on three other tables. Widening
  `CaptionBand.aligns_to_grid` to a ratio instead strips four real captions.
  **What shipped is only the removal of `with_grid`'s row subtraction**, so the
  arithmetic now matches the picture it is taken from, and
  `sample_table_0003` returns all five headers and sixteen rows. Do not rebuild
  the cut; the docstrings in `engines/ollama.py` carry the numbers.
- **`preprocess._without_vertical_rules`** clears full-height columns before
  banding. Without it, a 3px `border-left` inked in every row makes a crop read as
  one unbroken band, and `TL;DR` and `Introduction` were never asked for a Title.

---

## Retired in Thread 0 — gone, and why

- **`acceptance.compare()`, `tests/test_acceptance.py`, `tests/test_fixture_0002.py`
  and every `*.expected.json`.** The typed-reference harness and its serialised
  reference. `geometry_score.align()` survives as a component of T3.
  `tests/frozen/run84/` holds run 84's five output documents, copied in before
  anything was deleted; spec 0007's problem statement is the rest of the record.
- **`tests/fixtures/` is now `tests/documents/`, and `BUILDERS` is
  `SAMPLE_DOCUMENTS`.** The hand-built `Document` objects survive **only as
  input** to render, probe and replay tests. With the comparison function and
  every serialised reference deleted, nothing can score against them. **Never
  score against them** — doing so rebuilds the harness spec 0007 deleted. They
  no longer have to be *true* IR, only plausible IR.
- **The vision layout path.** Geometry comes from a detector in every
  Conversion. `DTH_LAYOUT_DETECTOR=none` now **refuses by name** rather than
  being handed to `from_name` as if it were a detector, so a stale value in
  somebody's shell says so instead of failing somewhere obscure.
  `DTH_LAYOUT_LONG_EDGE`, which served only that pass, is gone, and Q4 took
  `preprocess.LAYOUT_LONG_EDGE` with the rest of the pass.
- **The probes bound to the retired reference**: `layout_probe.py` (measured
  the vision pass), `snap_probe.py`, `classify_truth_probe.py`,
  `fixture_geometry.py` (derived rectangles *for* the expected IR) and
  `write_expected_ir.py`. `cv_layout_probe.py` and `detector_probe.py` are
  **kept** and repointed — see the OpenCV rectangle finder note above, which
  Thread 2/B needs.

**The one thing Thread 0 did not finish was finished by Q4, 2026-09-29.**
`OllamaEngine.detect_zones`, `LAYOUT_PROMPT`, the layout wire schema, the
region-ceiling rescue and `DTH_LAYOUT_MODEL` / `DTH_DERIVE_BANDS` /
`DTH_LAYOUT_REGION_HINT` are gone. The recorded-response suite now hands the
layout stage fixed Zones — `tests/replay.py`'s `FixedLayout`, serving each
fixture's `tests/responses/<fixture>/geometry.json` — so a replayed Conversion
takes its Zones the way a real one does, from something that is not a model.
**The production layout front can be run with no model at all:** give a
Conversion engines whose transport refuses every call, and the real detector
and every model-free layout stage run, each Zone renders a skeleton, and all
fifteen take 11 seconds: `python tools/layout_front.py <out>`. It reproduces
`a3-result`'s Zone band, column and bbox on 15 of 15 and is byte-identical run
to run, and it is how Q4 proved it changed nothing. It sees no model answer —
`tools/rederive.py` is that loop — so it measures geometry changes only.

### What Phase A-1 settled, including what it could not do

Its three causes are fixed — a table reconciled against its header instead of
discarded, a light-on-dark page turned over before `equalise`, and ink no box
covers given a Zone. **Its honesty gate is not met**, and the reason bounds what
any later thread should attempt.

**The pipeline can declare structural loss and cannot declare loss inside a
line.** Nine of fifteen documents lost 2–43% of their tokens while returning *as
many printed lines as the crop holds, or more* — `catalogue_0015` read 28 lines
where 20 are printed and lost 43% of its words. Two pixel-side detectors were
built and measured against the checkpoint's own documents and both were
rejected for firing on clean documents while missing the worst real loss;
`src/doc_to_html/honesty.py` carries the table and the numbers. **Do not build a
third without a new kind of evidence.**

**What that means for any repair loop** (spec 0007's Thread 3/C, cleared
unbuilt on 2026-10-10). Classify each residual error as (a) the IR cannot
express it, (b) a pass read it wrong and would again, or (c) it needs a second
look at the whole page — a loop only pays if (c) is a material share. This
residue is **(b)**: the conversion is deterministic at `temperature: 0`, so a
loop that re-examines the same crop gets the identical wrong answer back.
**Do not expect a repair loop to recover recall**, and do not let that
expectation justify deferring reading quality.

What *would* reach intra-line loss is two readings of one crop compared against
each other — `CellState.DISPUTED` and the Ladder are already the vocabulary for
it, and `_climb_ladders` already records that it waits on a second Engine. That
is model time and Alessandro's decision, not a detector.

**Tracker state, 2026-10-18: one open issue — #40, spec 0017, built, his decision pending.** #31–#39 (specs 0008–0016) are closed, each done and decided. #30 (spec 0007) closed when its
work plan finished; #29 records spec 0006 retrospectively; #28 (spec 0005) and
#17 (the vision layout prompt) were closed by Thread 0. Every other spec is closed
history; 0007 still defines the target.

---

## Lessons that generalise

- **The tool between you and the artefact is part of the measurement, and it
  lies quietly.** Thread 0 found three faults in the *rendering harness*, none
  visible in any number, each found by looking at a picture after the numbers
  said everything was fine. (1) Headless Chrome inherits the host's dark mode,
  so `render.py`'s `@media (prefers-color-scheme: dark)` fired and **every
  visual comparison eyeballed in this project before 2026-09-18 was an inverted
  page beside a light source**. (2) Chrome lays out no page narrower than 500px
  but crops the screenshot to the width you asked for, so a 340px document
  became a 500px layout with its right-hand column cut off. (3) A screenshot
  taken at *exactly* the page height renders the last row blank —
  `invoice_0001`'s `Total: $385.00` had zero dark pixels while `project()`
  reported it present at y 551-569. The third is the dangerous shape: **T1 and
  the pixels disagreeing about whether content exists**, which is the failure
  spec 0007 warns about, arriving from the tooling rather than from the IR. All
  three are pinned in `tests/test_projection.py`.
- **A corpus document that hides its own text is not ground truth.**
  `newsletter_0008`'s CSS multicol balanced its content into a box shorter than
  the content and cut a line in half. The text stays in the DOM, so the
  projection reports it and T1 demands the model read it, while the picture
  does not contain it. Invisible in the page height, obvious in the PNG. It now
  uses three explicit columns, which cannot do that.
- **A metric can saturate and then invert, and nothing inside it will say so.**
  Runs 81→84 moved the total 23→10. Over those same runs, duplicated titles
  appeared in three of five documents and `sample_table_0003` lost every column
  header of its only table — scored as a **full match**, because the harness
  compared `RowRole` sequences and never compared cell content. **When a measure
  cannot see a class of fault, improving it is unconstrained in that direction.**
  Nobody had opened the rendered output beside its source in eighty runs. **Look
  at the artefact, not only at the number.**
- **A change can be blocked by a fault somewhere else, and nothing will tell you
  when it stops being blocked.** `DTH_CAPTION_PASS` was built, tested and correct,
  and sat switched off for ten runs. The gate it failed was real, but the cause
  was *grouping*: the reference split those boxes, so neither half could carry a
  Title. Spec 0006 merged them and the pass then went 23 findings to 12 **with no
  change to the pass at all**. The note on the shelf said "the pass is right about
  the pixels it is shown and the pixels are wrong" — the correct diagnosis, and it
  still did not schedule the retry. **When you shelve a change, write down what
  would have to become true — and re-read that list when a neighbouring pass
  moves.**
- **`dth_env.txt` proves what was exported, not what was read — and a flag that
  does not arrive looks exactly like a flag that does nothing.** `DTH_HEADING_RULE`
  reached `Settings`, was recorded in the run directory, and never reached the
  detector: `bakeoff.engines_for` builds its own `EngineSet` rather than calling
  `orchestrator._layout_engine`. The arm came back **byte-identical to its
  baseline**, which is the signature of a change that did nothing — so the correct
  reading of that run was very nearly the opposite of the truth. `tools/iterate.sh`
  runs the bake-off, so *every measured run in this project takes that path.*
  **Before believing a null result, prove the arm was actually armed.**
  `TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion` compares the two paths
  attribute by attribute. **It happened again, found 2026-09-21:**
  `Zone.title_fill` shipped, was verified offline and had never once been set
  in a conversion, because `_measure_chrome` ran *before* the `_classify` pass
  that sets `Zone.title` and `title_rows` was therefore always zero — 0 of 119
  Zones across the corpus. A stage's *position* is as much a way for a feature
  not to arrive as an unread flag.
- **An instruction is reachable only if it asks the model to decide differently,
  not to perceive differently.** Two prompt attempts to stop the model splitting a
  wide table row failed, and one run's answers were **byte-identical** to the run
  before it. The model does not read the two ends of an 800px row as one line, so
  the instruction had nothing to act on. A *count* worked. **It complies with how
  many, and ignores which line.** This is also why Thread 2/B measures colour from
  pixels rather than asking a model for it: colour is perception, and the pixels
  are already in hand.
- **When a model answers a closed question the same way every time, check whether
  the schema can express the true answer before rewording the question.**
  `CaptionResponse` first asked a boolean — is this line a heading? — and got
  `true` on 8 of 8 crops, because its test for a heading was word for word
  `CLASSIFY_PROMPT`'s test for a table's top row and no other answer was
  available. A third value — `caption` / `header` / `content` — took the same model
  from 4/11 to 8/11 with no change to the reasoning asked of it. **Do not collapse
  it to a boolean.**
- **A prompt rule that bundles two tests will be credited with the wrong one.**
  `pairs` required the label "on the same line as the value it names" — a
  geometric test and a semantic one in one sentence. Spec 0003 credits the whole
  clause with fixing a Zone, so it read as untouchable; in fact only the semantic
  half did that, and the geometric half was the sole cause of the `invoice_0002`
  panel regression. Dropping it left all 13 answers byte-identical. **Check whether
  a clause is one rule or two wearing one sentence before defending it.**
- **Do not gate a change on the fields it was designed to move.** Spec 0004's
  Gate 1 was pre-registered, passed every field it named, and shipped a regression
  that cost a Zone and a Probe, because it gated a geometry change on geometry
  fields alone. Spec 0007's T1 ratchet is the general form of the fix: *no content
  that previously converted stops converting*, checked on every phase.
- **A reference that cannot be matched reads as a detector failure, and may be
  the reference.** `invoice_0002`'s `Services / Products` sat at **0.043** IoU
  against its own ink, under `MATCH_IOU` 0.50, so nothing the detector drew could
  ever pair with it — and the harness reported that as three references the run had
  missed. Before believing a `missing`, score the references against their own
  Source Image.
- **A Zone's Title is a band of ink that is not a row.** `table_grid` counts
  printed lines, so a titled table measures one row too many —
  `sample_table_0003` gives 17 against a true 16, and `with_grid` subtracts. Both
  numbers were right; they counted different things. **But the subtraction is only
  safe if the caption is also removed from the crop**, and it is not — which is
  exactly how the header row gets deleted. Arithmetic and picture must agree with
  the page, not merely with each other. **Phase A0 resolved it the other way
  round, 2026-09-22**: the cut was built and measured and it deletes real
  content on a Zone with no caption, so *the subtraction went* and the crop
  stayed whole. When a count and a picture disagree, changing the picture to
  match the count is the more expensive of the two repairs — it can only
  destroy, where dropping the count can only be wrong.

- **Where you ask is a bigger lever than how you ask.** A1 asked for inline
  runs twice with almost the same words. **Inside** the four Extractor prompts
  it cost `invoice_0002` a whole pairs answer — five pairs to one, a
  neighbouring answer in the same document byte-identical — and crossed the T1
  ratchet on seven documents. Moved into a **separate pass** over the same crop,
  changing no Extractor prompt, it holds the ratchet on all fifteen and costs
  nothing, because at `temperature: 0` every extraction answer is then the one
  the floor already has. Same model, same question, opposite result. When an
  extra ask damages the primary task, **move the ask before you reword it.**

- **The check that reports a fault is not where the fault is.** For a whole
  phase `DTH_SNAP_ZONES` was "not applying to 3 of 15", and A2 was scoped
  around repairing it. Run offline one stage at a time, the snap had returned
  every box on those pages **unchanged**; the enclosure came from two union
  steps in the detector, and the snap was named only because it was the one
  place `validate_bands` ran. A gate clause reading "the snap applies to 15 of
  15" would have passed without moving a box. **Before fixing the component a
  finding names, find the stage that introduces the fault** — and suspect a
  docstring that says a check "cannot fire": `validate_bands`' did, and was
  false.

- **Set a threshold from the distribution, and look for the empty band.**
  `keep_runs` drops marking that covers a whole line. The first cut was a
  tidy-looking 0.5 and it threw away `editor@example.com` — a genuine link that
  is three of its line's four words. Measured across every marked Cell of the
  trial sweep, the marked share is **bimodal with nothing in the middle**:
  genuine marks 0.077–0.333 plus that one at 0.750, junk at **exactly 1.000**.
  The threshold belongs in the gap, and "every word" needs no constant at all.
  **A round number chosen before the histogram is a guess wearing a decimal
  point.**

- **When two things look identical in the picture, the information is not in
  the picture, and neither a prompt nor a pixel will put it there.** A line
  ending `con-` and a line ending `nine-` are the same shape: one hyphen is the
  renderer's, inserted because the line wrapped, and the other belongs to the
  word. `newsletter_0008` has both. Telling them apart is knowing English, so
  the repair is a word list — and the default when there is none is to **keep**
  the hyphen, because keeping one that should have gone costs nothing (`con`
  and `firmed` score exactly as they already did) while dropping one that
  should have stayed costs two source words (`nine-month` becomes
  `ninemonth`). Same asymmetry that put `_without_repeated_header` at the wire:
  put the repair on the side where being wrong is free.

- **The ratchet earns its keep on the first replay, not at the gate.** A1's
  reflow was measured offline before a single model call. Everything improved —
  `hard_breaks` 57 to 8, `join_recall` 0.8128 to 0.8258, five documents better
  on four axes — and the ratchet failed it on **one word**, `nine`. A mean
  would have called that a clean win. **Measure downstream-of-the-model changes
  by replay before spending a sweep**; `tools/remeasure_style.py` does it, and
  it proved itself first by reproducing `a0-result` to the last digit.

- **A prompt clause is not additive just because the schema is.** A1's
  `marked` field was designed so that an empty answer left everything exactly
  as before — and it did, at the schema. The *clause asking for it* still cost
  `invoice_0002` a whole pairs answer: 5 pairs at the floor, **1** with the
  clause, a neighbouring answer in the same document byte-identical, and all
  five back the moment the clause was removed. **Asking a model for one more
  thing is a change to everything it was already doing.** Where the extra ask
  paid nothing at all — tables and pairs returned 0 usable runs — it was pure
  loss. Budget a revert, and verify it on the document that was hurt.

- **A fault can be invisible in the picture and loud in the measurement, and
  that direction is as real as the reverse.** Joining a word across two marked
  lines produced `<strong>...con</strong><strong>firmed...</strong>`. The page
  reads `confirmed` — correct to any eye — while `project()` walks **text
  nodes** and scored `con` and `firmed`, reporting a printed word as missing.
  The usual warning here is the other way round (`Total: $385.00` present in
  T1 and blank in the pixels). **Both directions mean the same thing: the tool
  between you and the artefact is part of the measurement.** `render._SEAM`.

- **A count that ignores location cannot guard a claim about location.** A1
  pre-registered "no document's `hard_breaks` may fall below its
  `source_hard_breaks`" to stop `join_recall` being gamed by joining
  everything — `join_recall` counts source bigrams *found*, so a wrong join can
  never lower it. The guard fired on `nonlatin_0014` and the fault had not
  happened: `hard_breaks` counts `<br>` **elements wherever they sit**, the
  source's four are in an address block and a date block, and the two the
  output lost were in Greek paragraphs that genuinely wrap. Same blindness that
  let a full match hide five deleted table headers. The positive form holds and
  is what should have been written: **every `<br>` still drawn is in a block
  whose kind keeps its lines, and none was lost.**

- **A clause about bytes has to say which bytes.** A3 pre-registered "every
  document with no figure renders byte-identical", and it could not hold for
  a reason that had nothing to do with figures: a new `Zone` field puts
  `"pixels": null` into every embedded IR, and a rule added to `STYLESHEET`
  lands in every render. It was restated before the sweep — identical outside
  the embedded IR, and inside it differing by that key alone — and met 12 of
  12. The same trap sprang on the comparison: reading the floor's IR back
  through today's `Document` adds the field to the floor too, so strip it
  from both sides or compare the raw JSON.

- **A fault's description is a claim, and the IR can refute it.** Open issue
  3 was filed, briefed and handed over as an *across-Zone* echo — two Zones
  reading one printed line — and scoped around a rule `_without_title_echo`
  could not reach. One print of the floor's IR showed a single Zone whose
  Title was its own header row's first cell. **Read the IR before scoping a
  fix to the description.** The same session's gate clause said only
  `height_ratio` would move when a findings panel shrank, and three palette
  fields moved too: the projection excludes the panel, and T5 samples the
  whole screenshot. **Before predicting which fields move, know what each
  axis samples.**

- **A guard can be right and still create the fault it looks like.** A0's
  heading guard stopped `attach_trailing_rows` swallowing headings, which
  recovered `What Q4 commits to` — and shortened `darkdeck_0009`'s table crop
  to 8 ink bands, so the prompt asked for 8 rows where the table has 7 and
  **the model padded by repeating the header**. The tempting fix was to restore
  `with_grid`'s subtraction, which is what deleted `sample_table_0003`'s
  headers in the first place. It went to the wire instead
  (`_without_repeated_header`), because **a dropped row is a recall fault and a
  surplus row is only a precision one** — put the repair on the side where
  being wrong costs less.

- **A fixed tool does not fix what it already made.** `projection.SHOT_SLACK`
  fixed the shooter in the commit that added it, and the ten authored pictures
  had been shot by the unfixed one: each was missing its bottom 60–90px —
  footers, a signature line, a footnote, a receipt's last three lines. Every
  score on those documents since was taken against text the model was never
  shown, and `shoot_corpus.py --check` could not see it, because it compares
  the HTML with itself. **When a tool is fixed, remake what it made and diff
  the remake against the original**; `TestTheCorpusPictureIsItsOwnHTML` now
  keeps that diff.

- **When the evidence under a queue changes, re-take each item's premise
  before building its fix.** Q5 and Q6 were scoped on the cut-short pictures.
  On the whole ones `receipt_0010` read every row with no resize — Q5's lead
  was answered before it was built — and the full-width Zone Q6 was to repair
  no longer exists. The same change *uncovered* a fault the cut had hidden:
  `cv_0013`'s sidebar now ran the page's full height, deskew read it as a 15°
  tilt, and the detector saw the straightened page as one photograph. A
  truncated input can mask faults as well as cause them.

- **A semantic element can carry a layout decision.** `<thead>` is drawn at
  the top of its table and `<tfoot>` at the bottom, wherever their rows sit in
  the IR. `render._table` grouped every `header` row there, and Q1 exempted
  only a header with data on both sides — so a row the model *called* a
  header still moved: the receipt's `AID` and `Auth` lines, printed last,
  were drawn first. **A role is not a position.** Q5: a header stays in place
  once the table has opened with one, and only the summaries nothing follows
  go to `<tfoot>`.

---

## The loop

```
tools/iterate.sh <label>                  # one document, shipped defaults
FIXTURE=iterate tools/iterate.sh <label>  # the five, ~20 min
FIXTURE=sweep   tools/iterate.sh <label>  # all twenty-one, at a phase gate
FIXTURE=invoice_0001,cv_0013 tools/iterate.sh <label>
```

Set a `DTH_*` only to change **one** axis against that baseline, and say which
one when reporting the result.

**Open `debug/runs/<label>/report.html`.** It is built by the run, it holds
every document, and it carries the delta against the previous run's
`scores.json` plus a pass/fail on the hard tier. A run's numbers are in
`scores.json` beside it.

**Any run whose output will be reviewed is a `sweep`.** Decided 2026-09-21,
after reviewing the five found four real faults in one pass and the five turned
out to be the least representative sample in the corpus — all light-grounded,
all similar, none of the ten documents authored after the target changed. The
~2¼ hours is budgeted for. `iterate` is for a throwaway check nobody will draw
a conclusion from. **A renderer-only change needs no new run at all:** every
pixel-derived field can be re-measured and the IRs re-rendered offline, so one
sweep serves many render iterations.

**Corpus split.** *iterate* = the original five. *sweep* =
all twenty-one, run at phase gates. *new* = the six added 2026-10-13, held
out. `doc_to_html.corpus` is the one place that says which is which. **A
sweep takes about 2¼ hours** — `S7-sweep`, 2026-10-13: 2h16m wall clock,
751 model calls, the model 54%/46% CPU/GPU; `S8-sweep`, 2026-10-14: 2h12m,
725 calls, 40%/60%. Budget for it before starting one. **It outlasts a
two-hour background task**, so start it detached (`nohup … & disown`) and
wait on its log; `docs/status.md`'s loop has the line. **Never edit
`tools/iterate.sh` while a sweep runs it**: bash reads a script as it
goes, and `S8-sweep`'s died after its bake-off on a line the edit had
shifted — the dump was whole, and the rest was run by hand. `pricing_0017` alone took about 15 minutes; the iterate five take
about 20 minutes together.

**The five original documents are the ones every prompt was tuned on.** That is
why *sweep* exists and why a phase gate is not allowed to be decided on
*iterate*.

Runs live in `debug/runs/<label>/`, which is **gitignored** and gets cleared —
regenerate rather than hunt, and never quote a run you cannot open. Nothing in the
suite reads a run directory.

Ollama reports the CPU/GPU split into `ollama_ps_after.txt` and the script warns
when the model was partly on CPU. **That affects timings only** — the answers are
unchanged — so a run with the warning is still valid.
