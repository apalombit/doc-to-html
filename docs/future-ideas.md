# Future ideas — a judge-led loop for growing the converter

**Status: record, 2026-10-18; taken up by the level-up plan.** This is
the direction agreed in discussion on 2026-10-18. Its judge was built as
the level-up's L2 ([spec 0021](specs/0021-measurement-and-the-judge.md)):
checks from the HTML and an AI reviewer held to criteria the human
agreed. Nothing here is open work. This file records the ideas, the
choice, the evidence and the related records. It does not record
implementation.

---

## 1. The choice

**Build a judge.** It is a fixed, tested instrument that compares a
render with its source picture, check by check. Alessandro curates it
against his own pairwise calls (which of two renders is closer to the
page).

**Then let the judge's calls direct the converter in four ways:**
1. **Accept or reject** a change, over the whole corpus.
2. **Point** at where to work next: the differences left after a run,
   grouped by check, ranked by how many pages they touch.
3. **Remember.** A per-page fitting loop (idea B, offline actions only)
   tries the options the rules already have and keeps the one the judge
   prefers. Every choice is kept as a case, and the cases form a
   **memory** of how conversion went in which situations (§7). B is
   **the first loop the judge drives.**
4. **Promote.** Where the memory keeps choosing the same option across
   pages, that option becomes the converter's rule or threshold.

The memory is what lets the system's capacity grow as the corpus does.
Multi-proposal conversion (idea A) is deferred. A free agent is
rejected.

## 2. The problem it answers

The corpus will keep growing toward more general documents, and in time
real photographs. That is ADR 0003's synthetic-to-real gap. Today's loop
does not scale with it:
- **Review cost grows with the corpus.** Every sweep, every page is
  judged by eye.
- **Rules are fitted to the page that needed them.** Spec 0016 §1's
  table shows most recent rules proven on one page only, with guessed
  thresholds (`LEVEL`, `HABIT`, `WRAPS`).
- **Nothing checks a page without its source HTML.** The scorer needs
  the HTML; a real input is only a picture.
- **The one automated measure was demoted** because it did not track the
  eye (spec 0007; "scores recorded, never gating").

---

## 3. Today

```
picture ─► rectify ─► Zones ─► classify / extract ─► OCR ─► style ─► render ─► HTML
           one guess per stage; nothing looks back
           a person opens every sheet: the only check against the source
```

**ELI5.** An assembly line. Each worker makes one decision and passes the
piece on. If the first worker cuts the cloth wrong, everyone after sews
the wrong pieces perfectly.

**Key points:** deterministic; offline loops measure a change in
minutes; every decision is traced.
**Fail points:**
- an early wrong guess is final;
- each repair is a new rule, one fault and one spec at a time;
- only a person compares output with source.

## 4. The ideas weighed

```
A  proposals    picture ─► 3 cheap layout proposals ─► judge ─► top 2 ─► convert ×2 ─► judge ─► winner
B  fitting      convert ─► render ─► judge: where it differs ─► one action on that region ─► keep if better ─► repeat
C  free agent   a model plans, measures, edits the HTML, and re-renders, for a fixed time
D  judge-led    the judge accepts changes, points at the next fault class, remembers what won, promotes it to rules
```

How each one grows capability as the corpus grows:

| idea | how a new document gets handled better | person's role | scales with the corpus? | main risk | verdict |
|---|---|---|---|---|---|
| today | a new rule per fault, through a spec | judges every page of every sweep | no | rules fitted to one page | stays the base |
| A | a better early guess per page; nothing is learned | audits | no: every candidate is a full conversion, and a moved crop costs a sweep | which candidate wins can flip on a page far from the change | **deferred**: only if the leftover differences show cuts the render cannot undo |
| B | a per-page choice among known options; alone, nothing is learned | audits | partly: it covers known faults only | hides a bad rule; pages drift apart | **the first loop, inside D**: its choices feed the memory |
| C | per-page edits | none, or audits | no: 7.4× the time, and nothing carries over (§12) | games the judge; measures instead of fixing | **rejected** |
| **D** | rules the judge accepts, points at and promotes, and a memory of what won where | curates the judge, audits samples, approves promotions | **yes**: review cost grows with disagreements, not with pages | the judge's blind spots become the converter's | **chosen** |

---

## 5. The chosen shape: loops around one judge and its memory

```
            Alessandro ── pairwise calls, check fixes ──► JUDGE (named checks + call record)
                                                            ▲            │
 new document ─► converter ─► render ─► compared with its picture       │
                    ▲                                                    │
                    ├── (1) accept / reject a change over all pages ◄────┤
                    ├── (2) next spec ◄── differences left, by check ◄───┤
                    ├── (3) rules ◄── promote ◄─┐                        │
                    │                           CASE MEMORY ◄── B: per-page choices ◄┘
                    └── (4) similar situation ◄─┘ try its past winner first
```

**ELI5.** The converter is an apprentice and the judge is an inspector
with a checklist. Alessandro trains the inspector. When the two of them
disagree about which of two results is better, either the checklist is
missing something and gets fixed, or the call was a close one and is
recorded. The inspector then:
- signs off the apprentice's new habits;
- says which kind of mistake is most common;
- notices which tricks keep working, so they become standard practice.

## 6. How the judge's calls direct the converter

- **Accept.** A change ships when no check gets worse on any page: a
  ratchet per check, never a sum. A person also opens every page the
  judge calls better or worse. In the article (§12), one check rewarding
  markup carried the whole average.
- **Point.** Take what still differs after the best option, group it by
  check and by kind of region, and rank the groups by how many pages
  they touch. A group across many pages is the next spec. A group on one
  page waits. This is the "general, not per-page" rule (Alessandro,
  2026-10-14) made measurable.
- **Promote.** Where one option wins on most pages of a kind, it becomes
  the default. Where the pages split, the measured quantity behind the
  choice gives a threshold, placed in the gap of its distribution (the
  `keep_runs` lesson). Measured thresholds replace guessed ones.
- **Never supply the answer** (ADR 0004). The judge may say where to look
  and which option to try. Its own reading of the source never becomes
  content. Otherwise the converter copies the judge, every check passes,
  and the signal is gone.

## 7. A case memory: how the judge's information counts dynamically

Every choice B makes is kept as a **case**:
- the situation, described by measured features of the region (for
  example: two side-by-side field Zones, sharing three printed lines, no
  frame);
- the option that won;
- the judge's checks before and after;
- its provenance, and whether a person's audit confirmed it.

The memory is used in two ways:
- **offline:** where many cases agree, the option is promoted to a rule
  (§6);
- **at conversion time:** a new region that resembles past cases tries
  their winning option first. The search gets shorter, and similar
  situations get treated alike.

**ELI5.** A cookbook of fixes. Each time the inspector likes a fix in some
situation, a card goes in the box: "in this situation, this worked."
When a similar situation turns up, the card's fix is tried first. When
many cards agree, the fix becomes a house rule.

| fail point | guard |
|---|---|
| **document types by the back door** (ADR 0001): cases keyed on "ticket" or "invoice" | the situation is measured features of a region, never a document's identity or type |
| **poisoning:** a judge mistake stored as a case gets reused on other pages | only cases no audit has overturned are reusable; an overturned call deletes its case; every case keeps its provenance |
| **non-reproducible runs:** output depends on the memory's state, and adding a document changes other pages | the memory is frozen per sweep and versioned with the baseline, like the frozen directories; a change is measured with the memory held fixed |
| **opacity:** "why did it do that?" | every choice made from the memory is traced to the cases behind it; stable patterns leave the memory as reviewed rules |
| **memorising, not transferring:** cases help only the pages they came from | the transfer test (§11, stage 4): build the memory on some documents and apply it to held-out ones. Capacity grows only if the held-out pages improve |

## 8. Alessandro's role

- **Labeller:** pairwise calls on a sample each sweep. That means every
  page the judge calls better or worse, plus a few it calls the same.
- **Keeper of the call record:** his pairwise calls, each kept with both
  renders, are what the judge is calibrated against. It is distinct from
  the case memory, which holds B's choices.
- **Judge editor:** every disagreement is triaged as a missing check, a
  wrong check, or a close call. A change to a check must hold over the
  whole call record, never only on the page that raised it.
- **Approver:** of promotions and new options. Specs stay his.
- **Corpus extender:** new documents are held out from the judge's tuning
  first, as `corpus.NEW` is held out from the converter's.

## 9. Why this judge should not go the way of the scorer

| the scorer | the judge |
|---|---|
| absolute scores per page, designed from axes | pairwise: which of two renders is closer to the page, which is what the eye does |
| never checked against the person | calibrated against his recorded calls, and re-checked as the call record grows |
| needs the source HTML | needs only the picture, so it works on real inputs |
| a bundle of axes, read as numbers | named checks, each one a fault class, each pointing at a region |
| one kind of error | the costly error is counted on its own: calling a worse page better |

## 10. Fail points and guards

| fail point | guard |
|---|---|
| the judge's blind spots become the converter's | a person audits every page the judge moves; each miss joins the call record; a ratchet per check |
| the judge is tuned to the corpus it judges | hold-out documents for the judge too |
| the two sides are read differently: the render exactly (from its HTML), the source by OCR | read both pictures the same way; a difference smaller than the OCR's noise is not a difference |
| converter and judge share an instrument, and agree while both are wrong | the judge reads independently (another engine or settings); ADR 0004 |
| per-page choices hide a bad rule; pages drift apart | trace which option won where, and why; promotion pulls choices back into shared rules |
| the options grow into a search problem | toggles on existing rules only; a new option needs approval |
| a cross-session table of judgements, which CLAUDE.md forbids | the call record keeps pairs with both renders, so any call can be re-judged; the judge is deterministic, so its outputs compare like the frozen scores |
| drift toward copying pixels (ADR 0002) | options are flow layout only; checks measure arrangement and content, not pixel identity |
| document-type checks creeping in (ADR 0001) | checks are about words, lines, columns, fills and order, never about invoices or tickets |

## 11. Order, with a stop at each stage

1. **The judge as an instrument, with its call record.** Calibrate it on the
   recorded by-eye calls: the frozen baselines `s8-result/` to
   `s11-result/` and their specs' outcomes.
   - **Stop if** it calls worse pages better too often.
   - Useful on its own: it pre-screens a sweep's sheets, and it fills
     visual-review's gap that "nothing points at *where* two renders
     differ".
2. **Judge-led development:** the judge accepts and points; a person
   audits samples. **Stop if** the audits keep overturning it.
3. **Per-page fitting, offline** (B, no model calls), every choice kept
   as a case. **Stop if** it does not beat the plain rules by eye.
4. **The transfer test:** build the memory on the fifteen, apply it to
   the six held out. **Stop if** the held-out pages do not improve: the
   memory would then only be per-page fitting, not capacity.
5. **Promotion** of consistent choices into rules and thresholds.
6. **The memory at conversion time**, frozen per sweep.
7. **Only if the leftover differences demand it:** options that ask the
   model something different (B with model calls), or layout proposals
   (A).

---

## 12. Evidence: one published agent experiment

Pasquale Molinaro, "I had a free Qwen3.8-27B agent copy 10 web pages. It
spent 64% of its time measuring pixels" (aiadvances.org, 2026). The
setup:
- Design2Code pages rebuilt from screenshots;
- one shot, against one revision, against an OpenCode agent with a
  renderer, its eyes and 20 minutes;
- 10 pages, one sample each, temperature 1.0, no blind control.

The evidence is thin, but it points the same way as this project's own
lessons.

| finding | the same lesson here | what it asks of the judge-led loop |
|---|---|---|
| one revision, with the render shown beside the target, gained nothing: −0.0005 on average; the Design2Code paper found the same for GPT-4V, GPT-4o and Claude 3 Opus | the same question gets the same answer (Phase A-1; temperature 0) | every option must change the question asked |
| the agent's lead, 0.942 against 0.922, was mostly one page; 0.150 of that page's +0.160 came from the metric rewarding markup, the visible fix was worth 0.009, and an edit that made the page worse raised the score | runs 81→84; "the tool between you and the artefact is part of the measurement" | calibrate the judge against a person; a person checks every gain; a ratchet per check, never an average |
| 64% of its time went to ad-hoc pixel measuring and 2.5% to looking; a broken measurement led to a wrong conclusion | an untested instrument lies quietly | measuring is a fixed, tested tool; nothing improvises its own ruler |
| it edited without re-rendering; the scored file held an edit nobody had seen | — | judge after every change; keep the best version, not the last |
| the gains came in the first few edits; the run cost 7.4× the one-shot time | — | small budgets; stop at the first round without a gain |
| an image read "succeeded" while the model actually got an error text; a permission prompt killed another run silently | "prove the arm was armed" | a canary check before every run |

## 13. Related records

- **Spec 0007:** the target, and why the scorer stopped gating. CLAUDE.md
  "How runs are used here"; spec 0011's "How to work" (judge by eye).
- **ADR 0001** no document types; **ADR 0002** structure over pixel
  fidelity, facsimile rejected; **ADR 0003** synthetic-first evaluation
  and the synthetic-to-real gap; **ADR 0004** a check may direct where to
  look, never supply the value; **ADR 0005** style measured from pixels.
- **Phase A-1** (`honesty.py`, CLAUDE.md): two pixel-side detectors were
  measured and rejected; the repair-loop classes (a), (b) and (c); the
  same crop gets the same answer.
- **`docs/agents/visual-review.md`:** pairwise and in-session only; "What
  the tool cannot do", items 2 and 3.
- **Lessons in CLAUDE.md:** a metric saturates and then inverts; the tool
  between you and the artefact; set a threshold from the distribution;
  prove the arm was armed; put the repair where being wrong is free.
- **Spec 0016 §1, "Do these rules generalise?":** the gates and
  thresholds that promotion would replace.
- **The frozen baselines, `s8-result/` to `s11-result/`,** with their
  by-eye calls: the first call record.
- **The article** in §12.

## 14. Open questions

- Which checks make the first judge? Candidates: words present, words
  sharing a line, column edges, fills present, reading order, relative
  size.
- How many recorded calls are enough to trust it, and what counts as
  "too often" for calling a worse page better?
- Can the judge read the source independently of the converter's own OCR?
- Is a sampled audit per sweep enough, or must every moved page still be
  opened?
- When the corpus gains real photographs, does the judge's agreement with
  the person hold?
- Which region features describe a situation well enough for cases to
  transfer, without naming a document type?
- How many agreeing cases make a rule, and who reviews the promotion?
