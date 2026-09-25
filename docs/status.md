# Status — 2026-09-22 (Phase A0 closed, gate met; A1 is next)

**Live document.** This is where the project actually is. When it goes stale,
rewrite it; do not add a banner and leave it.

Reading order for a fresh session: `CLAUDE.md`'s **READ THIS FIRST**, then
[`specs/0007-look-like-the-document.md`](specs/0007-look-like-the-document.md)
(authoritative), then this file. If you are going to look at output — and you
should — use the **`visual-review` skill**
(`.claude/skills/visual-review/SKILL.md`).

Branch `scaffold`, head `98c0665` plus A0's uncommitted work.
**731 tests pass, `mypy src/` clean.**

---

## Where we are

```
Thread 0    Scorer, corpus, report              DONE 2026-09-18
Phase A-1   Nothing loses content quietly       DONE 2026-09-19, gate NOT met
Thread 2/B  Style record, all CV, no model      DONE 2026-09-22 bar the type scale
Phase A0    Stop the bleeding                   DONE 2026-09-22, gate MET
  |- the doubled Title                          0 echoes, from 34
  |- _without_empty_rows filtered on count      fixed; 0 all-blank rows
  |- the caption band and the Extractor's crop  measured, withholding REJECTED
  \- _without_repeated_header                   new net, for a fault A0 created
Phase A1    Inline runs, and hard line breaks   NEXT   <- you are here
Phase A2/A3, Thread 3/C, Thread 4/D             unchanged
```

---

## The notch — DECIDED 2026-09-24

**The floor is `tests/frozen/a0-result/scores.json`.** Decided by Alessandro at
the start of Phase A1. It was open until then; it is not open now.

```
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-result/scores.json
```

### The mechanism

1. Every run writes `debug/runs/<label>/scores.json`.
2. `report.py --previous <path>` compares this run's scores against that file
   and **fails the gate if any document stopped printing a source word the
   previous file says it printed.**
3. That `--previous` file *is* the notch. It is the floor, and the only thing
   that makes "completeness may never decrease" enforceable rather than a
   slogan.
4. **`debug/runs/` is gitignored and gets cleared**, so a floor left in a run
   directory disappears. That is why floors are copied into `tests/frozen/` and
   committed.

### What the ratchet actually enforces, per document

Not four ratios compared loosely. `_ratchet_html` fails the phase on any of:

| leg | test |
|---|---|
| T1 recall | `_stopped_printing` — a **set difference** on `Completeness.vanished`, not a ratio |
| T1 precision | strict decrease, any amount |
| T2 tau | strict decrease, any amount |
| T3 beside | strict decrease, any amount |

`vocabulary_recall` is reported beside the failure to say how far it fell; it
is not itself the comparison.

### The state after the decision

| directory | what it holds | is it the floor? |
|---|---|---|
| `tests/frozen/a1-checkpoint/` | where the ratchet started, Phase A-1 | no, historical |
| `tests/frozen/a0-checkpoint/` | scores from **before A0 ran** | no, superseded 2026-09-24 |
| `tests/frozen/a0-result/` | scores from **after A0 ran** (`100-a0-gate`) | **yes** |

### Why it moved, measured rather than argued

The two candidates were compared per document on all four ratcheted legs, since
the gate is per document and strict. **`a0-result` dominates `a0-checkpoint`
everywhere — no document is lower on any ratcheted axis.**

| axis | floor rises on | floor falls on | largest rise |
|---|---|---|---|
| T1 vocabulary | 3 of 15 | **0** | `darkdeck_0009` +0.030 |
| T1 precision | 12 of 15 | **0** | `receipt_0010` 0.692 → 0.947 |
| T2 tau | 1 of 15 | **0** | `darkdeck_0009` 0.799 → 0.836 |
| T3 beside | 3 of 15 | **0** | `form_0007` 0.029 → 0.059 |

So moving the floor surrenders nothing. It removes one freedom only: A1's
freedom to hand back A0's gains, which is the freedom the ratchet exists to
remove.

### The known risk of the tighter floor, recorded before A1 ran

A1 reflows `<br>`-joined lines, which shortens blocks and therefore moves
geometry. The three `beside` values and the one `tau` value that rose
incidentally during A0 could wobble back down without a word being lost, and
that would fail the hard tier on an axis A1 never aimed at. **If that happens
it is reported as a gate failure and brought back as a decision — the floor is
not quietly re-cut to make a run pass.**

---

## What A0 did, and what it cost

Three faults were named in the brief. All three were diagnosed; **two were
fixed and the third was measured and its planned fix rejected.**

### 1. The doubled Title — fixed

A Zone carrying a Title also carried a Block, a row or a pair repeating it, in
12 of 15 documents. `wire._without_title_echo` drops a first Block / first row
/ first pair whose normalised text equals `zone.title`. The bound was measured
before the rule was written: **all 27 Block echoes were `blocks[0]`, and there
were zero near-misses** — nothing in the corpus sits just outside the rule.

**34 title echoes before, 0 after.**

### 2. `_without_empty_rows` filtered on cell count — fixed

`if row.cells` is truthy for `['', '', '', '', '']`, so the net let an
all-blank row through. It now tests content:
`any(cell.strip() for cell in row.cells)`. The net itself stays; four runs
established what it guards.

**The brief named `sample_table_0003` as the document returning a 17th blank
row. It was not.** `sample_table_0003` has 16 rows and none blank. The live
all-blank row was `report_0011` z6 row 5, `['', '', '', '']`. The bug was real
and the named document had moved.

### 3. The caption band and the Extractor's crop — REJECTED after measurement

`DTH_CAPTION_PASS` withholds the caption band from the *Kind* question and not
from the Extractor's crop, and `with_grid` subtracted one row for the caption
anyway. The agreed fix was to withhold the band from the crop too. **It was
built, measured, and reverted**, because cutting the band deletes real content:

- `darkdeck_0009` z2 is a row of four metric cards with no caption. Cutting the
  top band removed `P95 LATENCY`, `INGEST VOLUME` and `COST PER MILLION` —
  confirmed by opening the crop image, not inferred.
- The cut moved the *measured* column count on three tables.
- Widening `CaptionBand.aligns_to_grid` to a ratio instead was also rejected:
  it strips four real captions corpus-wide.

**What shipped is only the removal of `with_grid`'s subtraction.** The
arithmetic now matches the picture it is taken from. Both docstrings record
why the cut was tried and why it is not there.

### 4. `_without_repeated_header` — a net for a fault A0 itself created

A heading guard in `detector._trailing_row` (headings are no longer absorbed
as trailing rows, which recovered `What Q4 commits to`) shortened
`darkdeck_0009`'s table crop to 8 ink bands. The prompt then asked for 8 rows
where the table has 7 — a caption band is counted and is not a row — and the
model **padded by repeating the header**. Same on `report_0011`.

Restoring `with_grid`'s subtraction is what deleted `sample_table_0003`'s
headers in the first place, so the repair is at the wire instead: a second
`role == "header"` row whose cells spell the same as the first is dropped.
**A dropped row is a recall fault; a surplus row is only a precision one**, and
that asymmetry is why the net sits on this side.

### The measurement that forced the gate to change

Removing a title echo **lowers multiset recall without losing anything**: the
echo was numerically covering for a genuine occurrence elsewhere that was never
read. So the ratchet's recall leg is now **distinct tokens**, not the multiset.
`Completeness.vocabulary_recall` and `Completeness.vanished` are the two new
fields, and `report._stopped_printing()` is the one place that decides — both
`_gate_html` and `_summary_table` call it, because a green summary row above a
failed gate is how a ratchet stops being believed.

**`Completeness.duplicated` is not the gate and cannot be.** It totals 29 over
twelve documents and is **empty for `report_0011`**, which visibly prints all
eight of its numbered headings twice. Three independent mechanisms make it
blind; it saw 30 echoes and missed 18. The gate counts echoes structurally, off
the IR.

---

## A1's gate — PRE-REGISTERED 2026-09-24, before any code changed

Agreed with Alessandro at the start of the phase, from measurements taken
offline against `tests/frozen/a0-result/` — the floor — and no model running.
**Written down before the first line of A1 was written**, which is the whole
point: spec 0004 pre-registered a gate on exactly the fields its change moved,
passed every one, and shipped a regression.

### What A1 starts from, measured

| what | at the floor |
|---|---|
| T6 inline runs recovered | **0 of 42**, across 8 documents |
| — by kind | link 13, code 8, strong 17, em 3, mark 1 |
| output `hard_breaks` | 57, against 28 in the sources |
| — the excess, by document | `newsletter_0008` +31, `darkdeck_0009` +6, `report_0011` +5, `sample_semantic_0005` +4, `cv_0013` +1 |
| `join_recall` | 0.8128 — the weakest of the four T1 legs |
| word-level splits | 5 real, all in `newsletter_0008` |

The five split words, named, because a ratio cannot say which came back:
`confirmed`, `navigation`, `relined`, `slipways`, `subscription`. Each is
today one lost word plus two invented fragments (`con`+`firmed`,
`naviga`+`tion`, `re`+`lined`, `slip`+`ways`, `sub`+`scription`).

### Why the ratchet alone cannot gate this phase

**The larger half of A1's target is invisible to every ratcheted axis.** A break
at a space — `Invoice #: 123` cut into `Invoice` and `#: 123` — leaves recall,
precision and tau all at 1.000. Only `join_recall` sees it, and `join_recall`
is not a ratchet leg. Of the excess hard breaks, **6 are word-level splits and
the other 29 are not**. So clauses 2–4 below exist because the hard tier is
blind here, not as decoration on top of it.

### The six clauses

**Three that say A1 did its job — named counts, not ratios, which is A0's model:**

1. **Inline runs recovered: T6 `found` ≥ 21 of 42**, non-zero on all eight
   documents that have runs, and **the recovered strings reported by name**.
   The bar is half because 21 of the 42 (`strong`, `em`, `mark`) are derived
   from *appearance*, and this project's own evidence is that a model complies
   with *how many* and ignores *which*. The tag-driven kinds — link 13 and
   code 8 — are 21 on their own, so the clause is clearable by the half that
   is reachable by deciding rather than perceiving.
2. **The five split words print whole**, checked as strings one at a time:
   `confirmed`, `navigation`, `relined`, `slipways`, `subscription`.
3. **Spurious hard breaks fall** on the four documents that carry them, from
   their named starting counts: `newsletter_0008` 31, `darkdeck_0009` 6,
   `report_0011` 5, `sample_semantic_0005` 4.

**One that says A1 did not cheat — the clause spec 0004 lacked:**

4. **No over-joining.** `join_recall` counts source bigrams *found*, so a join
   the source does not have can never lower it: **joining every line into one
   maximises the axis A1 is optimising.** Without this clause, clause 3 is
   gameable by deleting every break in the corpus.

   **RESTATED 2026-09-24, after it fired on a document where the fault had not
   happened.** As first written it read *"no document's `hard_breaks` may fall
   below its `source_hard_breaks`, nor below today's value where already
   under"*. That failed `nonlatin_0014` — and `hard_breaks` counts `<br>`
   **elements wherever they sit**: the source's four are all in an address
   block and a date block (`example/nonlatin.html`, lines 47–48 and 53–54),
   while the two the output lost were in Greek paragraphs that genuinely wrap,
   the first ending mid-clause on `με`. **The two counts were never comparing
   the same breaks.** A count that ignores location cannot guard a claim about
   location — the same blindness that let a full match hide five deleted table
   headers.

   The clause now reads: **every `<br>` the output still draws sits in a block
   whose kind keeps its lines, and no such block lost one.** That is the
   over-joining fault stated directly rather than through a proxy, and it is
   checkable per document. It was verified before being adopted: after reflow
   the corpus draws **8** `<br>`, and the `address` blocks account for exactly
   8 — `invoice_0001` 4, `invoice_0002` 3, `receipt_0010` 1.

   **Restating a clause after seeing the result is a real hazard**, so it is
   recorded here rather than quietly swapped, it was put to Alessandro with the
   evidence before anything changed, and the original wording is kept above.

**Two general guards:**

5. **The ratchet holds** against `tests/frozen/a0-result/`, per document: no
   document stops printing a source word, and no fall in precision, tau or
   beside agreement.
6. **The structure survives the migration.** Per-line Cells stay reachable and
   a test pins it — they are what Correction anchors to and what makes each
   reading a ground-truth label, so reflowing must not delete them. 731+ tests
   pass, `mypy src/` clean, and a **full-sweep** visual review against this
   session's own baseline shows no `worse` on any document and no `major`
   sitting beside scored ratios all at 1.000.

### Where the two halves get their evidence, and what each costs

A1 is two migrations of the same structures, and they are **not** the same
kind of change:

| half | where it lives | needs a sweep? |
|---|---|---|
| reflow — `Block.lines` joined by `<br>` becomes flowing text | `render._lines`, one function | **no** — entirely downstream of the model |
| inline runs — `Cell.text` becomes typed runs | `wire` schema, the prompt, `ir`, `render` | **yes** — the schema cannot express a link today |

So reflow is built and measured first by replaying a recorded sweep's own
answers through the shipping mapper, which A0 validated to four decimal places
on every mean, and only the inline half spends the ninety minutes. **The
replay's own check comes first**: replaying the recorded answers through
*unmodified* code must reproduce `a0-result`'s committed numbers exactly, which
is what proves the dump still matches the floor it is named after.

**Run source for inline runs: the model, via a schema that can express runs.**
Agreed 2026-09-24. `CaptionResponse` went 4/11 to 8/11 by letting the schema
express the true answer with no change to the reasoning asked for, and the
schema today cannot express a link at all. Deriving runs from pixels the way
Thread 2/B derived style was considered and not taken: attaching a run to a
*span of text* needs word-level ink segmentation the project has no machinery
for.

---

## A1's gate — THE RESULT: **NOT MET**, 2026-09-24

Sweep `A1-03-sweep`, all fifteen, `qwen3-vl:4b`, against the floor
`tests/frozen/a0-result/`. **Four of the six clauses failed.** The phase split
cleanly in two: **the reflow migration works and the inline-run migration does
not**, and the evidence separating them is below.

**The gate was attempted twice.** The first attempt asked for inline runs
*inside* the Extractor prompts and failed four clauses; the second asked in a
**separate pass** and failed one. What shipped is the second.

| clause | attempt 1, in-prompt | attempt 2, **shipped** |
|---|---|---|
| 1 inline runs ≥ 21 of 42, all 8 documents | FAILED — 8 of 42, on 3 of 8 | **FAILED — 8 of 42, on 2 of 8** |
| 2 the five split words print whole | FAILED — 3 of 5 | **MET** |
| 3 spurious hard breaks fall | MET | **MET** — all four to 0 |
| 4 no over-joining | FAILED *(false positive; clause restated)* | **MET** |
| 5 the ratchet holds | FAILED — 7 documents | **MET** |
| 6 structure, tests, mypy | MET | **MET** — 769 tests, `mypy src/` clean |

**Clause 1 fails in both, and that is the phase's real result.** The model finds
very few of the marks that are there: **8 of 42**, all of them `link` or `code`
and all in two documents. It returned **no `strong`, `em` or `mark` anywhere**,
and nothing at all in `pairs` or `table` Zones. Widening the ask is what broke
attempt 1; the ceiling is the model, not the plumbing.

### Attempt 1, and why it was abandoned

### The cause, confirmed at the level of the model's own answers

**`MARKED_CLAUSE` — the prompt clause asking for inline runs — degraded
extraction.** Not inferred from totals; read off the two runs' dumps:

```
invoice_0002 / 20_pairs.json     floor 5 pairs -> sweep 1 pair
invoice_0002 / 18_pairs.json     floor 6 pairs -> sweep 6 pairs, byte-identical
```

The single lost answer is exactly the fourteen words `invoice_0002` stopped
printing — `alpha`, `beta`, `gamma`, `bank`, `banks`, `deposit`,
`convenience`, `final`, `amount`, and the rest of *"For your convenience, you
may deposit the final amount at one of our banks"*. A neighbouring pairs answer
in the same document was unchanged, so this is not drift.

**The revert was then run and it restores the floor exactly.** Run
`A1-04-pairs-reverted`, `invoice_0002`, clause removed from `PAIRS_PROMPT`
only: **all four pairs answers byte-identical to the floor's**, `20_pairs`
back to 5. That is both the proof of cause and a fresh confirmation that the
conversion is deterministic at `temperature: 0` on this machine.

### What the clause bought, against what it cost

**8 runs of 42, and every one of them from a `prose` or `list` Zone.** Tables
and pairs returned **zero** usable runs while taking the worst damage.

| | floor | A1-03-sweep |
|---|---|---|
| T6 inline rate | 0.0000 | 0.1905 |
| T1 vocabulary (mean) | 0.8653 | 0.8969 |
| T1 precision (mean) | 0.9765 | 0.9706 |
| T2 tau (mean) | 0.9381 | 0.9144 |
| T3 beside (mean) | 0.7233 | 0.6685 |

The means flatter it — `receipt_0010` alone moved vocabulary +0.679 — and the
ratchet is not a mean. Seven documents lost words, order or side-by-side
structure, including `sample_semantic_0005` losing `editor`, `example`, `com`:
**the email address, which is one of the links the clause exists to recover.**

**Decided by the standing rule, not by the trade.** The T1 ratchet is a floor
never to cross *for any reason*. `MARKED_CLAUSE` crosses it, so it cannot ship
whatever T6 gains. It is reverted from all four Extractor prompts.

### Two faults the sweep exposed, both real, one of them ours

**1. A rendering seam the picture cannot show and the scorer can — FIXED.**
The model marked five whole lines of `newsletter_0008` `strong`. Joining the
*rendered strings* then produced
`<strong>...council con</strong><strong>firmed on Tuesday...</strong>`: the
page reads **`confirmed`, correctly**, and `project()` walks **text nodes**, so
T1 scored `con` and `firmed` and called a plainly printed word missing. It
could not show up before, because unmarked text has no elements to leave a seam
between. `render._SEAM` closes it and `TestATightJoinLeavesNoSeam` pins it.

**2. The model stopped breaking the line at all.** With the clause in, it
returned `The two slip-ways follow a fortnight later...` as **one line with the
hyphen inside it**. At the floor it split across two lines, which the reflow
repairs. Nothing at the wire or the renderer can reach a hyphen in the middle
of a single returned string — so the clause converted a repairable fault into
an unrepairable one.

### Clause 4 failed on a false positive, and the clause is the thing at fault

`nonlatin_0014`: `hard_breaks` 2 → 0 against a source that has 4.

**`hard_breaks` counts `<br>` elements wherever they sit.** The source's four
are all in an address block and a date block
(`example/nonlatin.html` lines 47–48 and 53–54). The two the output lost were
in **Greek paragraphs that genuinely wrap** — the first ends mid-clause on
`με`. The counts were never comparing the same breaks, and the over-joining the
clause exists to catch did not happen.

**The positive form is checkable and it holds.** After reflow, corpus
`hard_breaks` is **8**, and the `address` blocks account for exactly 8 —
`invoice_0001` 4, `invoice_0002` 3, `receipt_0010` 1. Every `<br>` the output
still draws is in a block whose kind keeps its lines, and none was lost.
**Restating a pre-registered clause is not the implementer's call**, so it is
left failed and put to Alessandro.

### Attempt 2 — the separate pass, and what makes it safe

**`DTH_INLINE_PASS`, shipped on.** A per-Zone `runs` call asking one question —
which spans are set apart — over `prose` and `list` Zones only.

**It cannot repeat attempt 1's failure, structurally.** It changes no Extractor
prompt, so at `temperature: 0` every extraction answer is the one the floor
already has. That was verified twice before the pass was written, by reverting
attempt 1 and re-running: `invoice_0002`, all four pairs answers byte-identical
to the floor; `sample_semantic_0005`, **all 27 byte-identical**. A bad answer
here can cost marking and nothing else.

**Three guards, each written against a fault the trial sweep actually
produced**, not against an imagined one:

| guard | the fault it was written for |
|---|---|
| `_covers_everything` | a span covering a whole line |
| `_splits_a_word` | `T` marked, matching **`Tuesday`**'s `T`, rendering `<strong>T</strong>uesday` — the page read correctly and T1 reported `tuesday` gone. **One word, and it failed the ratchet.** |
| `keep_runs` | `newsletter_0008`'s pull quote returned as **22 one-word `strong` marks** — every mark is a text-node boundary, so a shredded line loses every join in it |
| one span, one Cell | `invoice_0001`'s `12345` stamped on both `12345 Sunny Road` and `Sunnyville, CA 12345` |

**`keep_runs`'s threshold is "every word", and the corpus put it there.** Over
every marked Cell of the trial sweep the marked share is bimodal with an empty
band in the middle: genuine marks run **0.077 to 0.333**, with one genuine
outlier at **0.750** — `editor@example.com`, three of its four words — and
**every junk case sits at exactly 1.000**. A tidier-looking 0.5 was tried first
and it threw that email away, which is precisely the span this phase exists to
keep.

Ten marks survive corpus-wide, **nine of them genuine** — `<article>`,
`<section>`, `<nav>`, `<style>`, `<head>`, `Anchor links`, `Jane Author`,
`editor@example.com` — and one false, `12345` in an address, which is the whole
of the 0.0029 that `join_recall` gives back.

| | floor | reflow only | **shipped: + inline pass** |
|---|---|---|---|
| T6 inline runs | 0 of 42 | 0 of 42 | **8 of 42** |
| join recall | 0.8128 | 0.8258 | 0.8229 |
| `hard_breaks` | 57 | 8 | 8 |
| vocabulary recall | 0.8653 | 0.8667 | 0.8667 |
| precision | 0.9765 | 0.9787 | 0.9787 |
| **the ratchet** | — | holds | **holds** |

**Read the last column as a replay, not as a run — this matters.** The trial
sweep `A1-08-inline-sweep` is a real run of all fifteen, and it is what every
guard above was measured on. The **guarded** numbers come from replaying that
run's own recorded marks through the fixed mapper, which is sound because every
guard is downstream of the model — but the replay rebuilt **41** spans where
the model returned **43**, so the shipped figure could differ slightly. It was
shipped without a confirming sweep, deliberately and with that known. **Anyone
quoting 8 of 42 as a measured run is quoting it wrong.**

---

## What Phase A1 leaves in the tree

**Shipped, and measured clean:**

- **The reflow.** `render._lines` flows wrapped lines; `KEEPS_ITS_LINES`
  excludes `address` only. The split was measured, not assumed: the multi-line
  counts of every other kind sum *exactly* to each document's excess
  (`newsletter_0008` 30 paragraph + 1 heading = its +31, `darkdeck_0009` 5 + 1
  item = +6, `report_0011` 5, `sample_semantic_0005` 3 + 1 quote = +4,
  `cv_0013` 1), and all eight multi-line `address` blocks sit in the three
  documents whose sources really do print 6, 3 and 9 breaks.
- **The hyphen rule.** `render._how_to_join` — soft hyphen dropped, compound
  kept, drop cap joined tight. `WORDLISTS`, with light morphology, is right on
  all 15 cases measured; **absent, every hyphen is kept**, which is the side
  where being wrong is free.
- **The Run machinery**, sound end to end and **fed by the inline pass**:
  `ir.Run`, `Cell.runs` with its content-preserving guard, `wire.WireRun`,
  `_runs_for`, `keep_runs` and `runs_into`, `render.TAG_FOR_RUN` matching
  `projection.INLINE_BY_TAG`, round-tripping through `Document.from_json`. A
  rendered `<code>`/`<a>` is read back by `project()` as `code`/`link`.
- **`DTH_INLINE_PASS`, on.** The separate pass above — `engines.ollama`'s
  `RUNS_PROMPT` and `read_runs`, `orchestrator._read_runs`. It asks only
  `prose` and `list` Zones, and only ones that came back with blocks.
- **`engines.ollama.MARKED_CLAUSE`, wired to nothing**, kept with attempt 1's
  numbers in its docstring so the route is not re-tried blind.

**Measured offline, with no model, against the floor** (`A1-02-reflow`,
replaying `100-a0-gate`'s own answers, itself first proved to reproduce
`a0-result` to the last digit):

| | floor | reflow only |
|---|---|---|
| `hard_breaks` (corpus) | 57 | **8** |
| join recall | 0.8128 | **0.8258** |
| vocabulary recall | 0.8653 | 0.8667 |
| precision | 0.9765 | 0.9787 |
| **the ratchet** | — | **holds** |

**The shipped tree was then re-measured end to end** (`A1-06-shipped`, the
working tree with the clause reverted, replayed over `100-a0-gate`): identical
to the table above, **ratchet holds**. And the revert restores the model's own
answers, checked on the two documents that matter most — `invoice_0002`, all
four pairs answers byte-identical to the floor, and `sample_semantic_0005`,
**all 27 answers byte-identical**. So the state in the tree is the floor's
answers plus the new renderer, and that is what the numbers above measure.

`newsletter_0008` gains on four axes at once, and the reflow-only render was
reviewed beside the source: the paragraphs flow, `confirmed`, `navigation`,
`relined`, `slipways` and `subscription` are whole, `nine-month` keeps its
hyphen, and `invoice_0001` is untouched with both address blocks intact.

**Also fixed on the way.** `Document.from_json` rebuilt `Reading.runs` as plain
dicts — which a dataclass accepts silently and which fails much later on the
first `run.text`. It would have broken `tools/remeasure_style.py`,
`honesty.document_in`, `tools/inspect_run.py` and `cli --ir` on any run
carrying runs.

### Open, and not the implementer's to close

1. **Clause 4's wording**, above. Left failed rather than restated.
2. **Clause 1's real ceiling.** The separate pass was built and it works, and
   it still reaches only **8 of 42**. Every one is a `link` or a `code` span in
   a `prose` Zone; the model returned **no `strong`, `em` or `mark` at all**,
   and nothing in `pairs` or `table`. Since `strong` and `em` are 20 of the 42
   and are derived from *appearance*, this is the shape CLAUDE.md's own lesson
   predicts — a model complies with *how many* and ignores *which*. **Raising
   it is a thread's question**, and the cheapest untried lever is the one
   Thread 2/B used for colour: measure weight and monospace off the pixels
   rather than asking. That needs word-level ink segmentation the project does
   not have.
3. **A confirming sweep for the shipped number.** 8 of 42 is a replay of a real
   run's marks, not a run. One sweep pins it.
4. **`invoice_0001`'s `12345`**, the one false mark left. It costs 0.0029 of
   `join_recall` and nothing else, and no guard written so far reaches it
   without also dropping genuine spans.
5. **`invoice_0001`'s `Invoice` / `#: 123`**, which the brief cites as A1
   evidence. It is a **Pair label/value boundary**, not a `<br>` between
   `Block.lines` — its broken joins are `invoice|123`, `created|january`,
   `due|february`, all label/value splits. Neither migration A1 names can reach
   it; it needs the Pairs Extractor to choose a different split point.

---

## A0's gate — the result

Sweep `100-a0-gate`, all fifteen, against `tests/frozen/a0-checkpoint/`.

| | floor | 100-a0-gate |
|---|---|---|
| **vocabulary recall** (the ratchet's leg) | 0.8599 | **0.8653** |
| recall (multiset) | 0.8513 | 0.8542 |
| **precision** | 0.9342 | **0.9765** |
| join recall | 0.8088 | 0.8128 |
| tau | 0.9356 | 0.9381 |

Five clauses, all met:

1. **0 title echoes**, from 34.
2. `sample_table_0003` returns `Country | ISO | Population | GDP (USD M) | Currency` and 16 rows.
3. **0 all-blank rows** corpus-wide.
4. **0 repeated header rows** corpus-wide.
5. **The ratchet holds**: no document stopped printing a source word it printed at the floor, and precision ≥ 0.975.

**Offline replay was validated as a technique on the way.** Post-model changes
were predicted by replaying a run's recorded answers through the shipping
mapper, and sweep 100 confirmed the prediction to four decimal places on every
mean. The conversion is deterministic at `temperature: 0`, so this is sound for
anything downstream of the model — and for nothing upstream of it.

---

## What the corpus looks like as A1 begins

Reviewed document by document on 2026-09-22 against the sources, all fifteen,
`--previous debug/runs/99-a0-heading-guard`. Findings in
`debug/runs/100-a0-gate/_review/` — **that directory is under `debug/` and will
be cleared**; the tables below are what survives.

| | mean over fifteen |
|---|---|
| `vocabulary_recall` | 0.865 |
| `recall` | 0.854 |
| `precision` | 0.977 |
| `join_recall` | 0.813 |
| `tau` | 0.938 |

Worst fault per document, from the rubric:

| document | worst axis | what it is | owner |
|---|---|---|---|
| `receipt_0010` | content | everything below `Order 00418` — all eight items, all totals, the barcode. **Declared** by the render | open, see below |
| `catalogue_0015` | content | the page title `Hardwood fittings`, and eight of twelve cards lose price, unit and stock line | open, see below |
| `cv_0013` | content | `Ines Halloran` and `STRUCTURAL ENGINEER` absent; every sidebar value clipped mid-word | A2 |
| `menu_0012` | content | `To begin` printed **twice**, across two Zones; three section headings hoisted out of the menu | **new — see below** |
| `nonlatin_0014` | colour | the table's dark-blue header row renders on white | open, unscheduled |
| `statement_0006` | rhythm | 41 near-identical caveat lines fill two screens | A-1 residue |
| `darkdeck_0009`, `form_0007` | columns | cards and paired fields collapse to one stack | A2 |
| `report_0011`, `sample_semantic_0005`, `newsletter_0008`, `catalogue_0015` | type | three heading levels render at one size | 2/B |
| `invoice_0001`, `invoice_0002` | content | the logo blocks render as placeholders | A3 |
| `sample_css_0004`, `sample_table_0003` | chrome | a blue rule, a badge chip, zebra striping not drawn | 2/B |

Owner tally over fifteen: **2/B 5, new 4, A2 3, A3 2, A-1 1.**

**Two `better`s on the `changed` axis, no `worse`:**

- `darkdeck_0009` — 99 printed `COMPONENT | OWNER | AVAILABILITY | P95 | STATUS` twice; 100 prints it once.
- `report_0011` — 99 printed `Berth | Movements | Revenue £000 | Change` twice; 100 prints it once.

**No fault sat beside all-1.000 scored ratios.** Every `major` in the review has
at least one scored ratio below 1.000 next to it, which is the first time that
has been true.

**`sample_table_0003` is a full match** — five column headers, sixteen rows, no
blank row. That is the document spec 0007 was opened on.

---

## Next, in order

### 1. Phase A1 — inline runs, and hard line breaks  <- next

The prompt is in [`specs/0007-handover.md`](specs/0007-handover.md).
**Hard line breaks moved into A1 from A0** during A0's scoping, and the review
above is full of them: `newsletter_0008` reads `the borough council con-` /
`firmed on Tuesday`, `report_0011` reads `prepared under the terms` / `of the
1987 order`. `join_recall` at 0.813 is the axis that sees this, and it is the
weakest of the four.

`invoice_0001` shows the other half: `Invoice #: 123` is cut into a label
`Invoice` and a value `#: 123`, scoring 1.000 recall, 1.000 precision and
1.000 tau. Only `join_recall` and `Completeness.broken_joins` see it.

### 2. Found in A0's review, nothing owns it

- **`menu_0012` prints `To begin` twice, in two different Zones.**
  `_without_title_echo` cannot see this: it compares a Block against *its own*
  Zone's Title, and these are two Zones that each read the same printed line.
  The same shape appears on `darkdeck_0009`, where a caption line
  `AVAILABILITY` is printed above a table whose first column header is
  `AVAILABILITY`. **A0 closed the within-Zone echo; the across-Zone one is
  open and was not visible until the within-Zone one was gone.**

### 3. Open, unscheduled, and cheap — unchanged from before A0

- **`statement_0006`'s 41 near-identical caveat lines** should aggregate to
  one. Ours, from A-1, no model time, and it fills two of that document's three
  review sheets.
- **`receipt_0010`, the corpus's worst document, has one untested lead.**
  `preprocess.resize_long_edge` never enlarges — its docstring argues enlarging
  "adds no detail" — and `receipt_0010` rectifies to **335x547**, by far the
  smallest page, so the extractor sees ~300px across 19 lines of monospace.
  True of information, possibly false of legibility. One document, ~6 minutes
  to probe.
- **`nonlatin_0014`'s table header row.** Do not build a third detector; point
  `chrome()`'s existing title-band measurement at the row `RowRole.header`
  already names.
- **`catalogue_0015` at 0.571 recall.** Eight of twelve cards lose their price
  line and the loss is **not declared**. Nothing owns it. A-1 established that
  the pipeline cannot declare loss *inside a line* and that two pixel-side
  detectors were built and rejected — do not build a third without a new kind
  of evidence.

### 4. Then A2 / A3, Thread 3/C, Thread 4/D — unchanged

---

## Standing note: a detector change shipped inside A0

The heading guard in `detector._trailing_row` is detector-level work, which is
A2 territory, and it shipped inside A0 because it was the cause of a named A0
fault (`What Q4 commits to` was being absorbed as a trailing row). **Its blast
radius was measured before it shipped**: 2 headings wrongly absorbed and 4
non-headings correctly absorbed, including `invoice_0001`'s `$385.00` total,
which still attaches in `100-a0-gate`. Sweep 100 showed no movement beyond
those two headings. Had it shown more, the right call was to hand it to A2.

---

## Invariants — do not break these

- **Never cite or analyse a past run.** Only a run taken in this session
  counts. Three exceptions, all committed files: `tests/frozen/run84/`,
  `tests/frozen/a1-checkpoint/` and `tests/frozen/a0-checkpoint/`.
- **Leave `debug/runs/84-rule-not-a-line/` intact.**
- **Never score against `tests/documents/SAMPLE_DOCUMENTS`.**
- **Do not delete the two dormant safety nets or the four shipped defaults** —
  and there are now **three** wire-level nets: `_without_empty_rows`,
  `_join_split_header_row` and `_without_repeated_header`. Each invents nothing
  and discards nothing.
- **`project()` compares a normalised view, never raw markup.**
- **Every run must produce `debug/runs/<label>/report.html`.**
- **Any reviewed run is a full sweep**, all fifteen documents.
- **Rubric judgements are pairwise and in-session only.**

## Deferred deliberately — not new faults

- **Column collapse** waits for A2. Content complete and reading order correct,
  in one column, is the accepted interim state.
- **The type scale** waits for its own increment, gated on `height_ratio`
  directly rather than on agreement with the CSS size.
- **`Zone.align`** stays in A2.
- **Figures as placeholders** stay in A3.
- **`cv_0013`'s clipped sidebar values** stay in A2.

---

## The loop

```
FIXTURE=sweep tools/iterate.sh <label>        # all fifteen, ~90 min — anything reviewed
FIXTURE=iterate tools/iterate.sh <label>      # the five, ~17 min — throwaway checks only
python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \
    --previous tests/frozen/a0-checkpoint/scores.json
python tools/visual_review.py debug/runs/<label> --previous debug/runs/<older>
python tools/visual_review.py debug/runs/<label> --check
```

**A renderer-only or pixel-only change needs no new run.**
`tools/remeasure_style.py <sweep> --label <new>` re-measures the Style Record
and re-renders from a sweep's own embedded IRs with zero model calls. It cannot
move anything the model decided — a prompt, an extractor or the layout still
costs a sweep — and it says so. **It does not serve A0 or A1**, both of which
change prompts and extraction.

**A post-model change can be verified without a sweep by offline replay** —
feed a run's recorded answers back through the shipping mapper. Validated on
2026-09-22 to four decimal places on every mean. Upstream of the model it
proves nothing.
