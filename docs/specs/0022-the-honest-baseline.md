# The honest baseline: today's pipeline on panel pages nobody has tuned on

**Status: done 2026-11-09, issue #45 closed.** The outcome, and the prompt for P1, are after the steps; the decisions are at the end.
- **This is step L3** of the level-up plan
  ([`../level-up.md`](../level-up.md) §6, decision 1 of §8), on branch
  `level-up`. Its outline is spec 0020's "L3 — the honest baseline"; its
  prompt is spec 0021's last.
- **It is written to be run in a fresh chat.** Everything it needs is
  here or linked.
- **It measures; it builds nothing that converts.** Today's shipped
  pipeline over the L3 set, L2's checks over the result, Claude's review
  of every page by the agreed criteria, and the fault classes ranked by
  pages touched. That ranked table is **the reference P2 decides
  against**: the parser-first PoC (P1) is converted over the same pages
  and compared class by class.
- **It changes no conversion code** (`level-up.md` §6: L1–L3 change
  none). A check issue the review finds is fixed as in L2, in
  `checks.py`, and pinned on a dev page only.

**Why.** Every number before L3 was taken on pages someone had looked at
while tuning. The probe (`level-up.md` §3) found a structural fault on 9
of 10 unseen pages against 0 of 6 tuned ones, but ten pages is a taste,
not a rate. L3 is the first measurement on pages chosen in advance by
their variability and never opened while the converter was built.

## Read first, in order

1. `CLAUDE.md`'s READ THIS FIRST.
2. [`../status.md`](../status.md).
3. [`../level-up.md`](../level-up.md): the Gist, §6, §7 and §8.
4. [`../agents/review-criteria.md`](../agents/review-criteria.md): every
   call in the review is judged by it.
5. [`0021-measurement-and-the-judge.md`](0021-measurement-and-the-judge.md):
   "Where L2 stands" (what the checks still miss) and its decisions.
6. This spec, end to end.

---

## Facts, measured 2026-11-07

Each was measured in the session that wrote this spec. Re-check any of
them before relying on it.

**The code.**
- `level-up` at `7b00482`. Since `c7a9a17`, where L2's close proved
  `tools/replay_run.py` and `tools/rederive.py` 21 of 21 byte-identical
  over `s14-result/`, only docs changed (`CLAUDE.md`, `level-up.md`,
  spec 0021, `status.md`). The conversion answers as `a0d73c9`'s, plus
  L2's 3-minute limit on each model call.
- Ollama serves `qwen3-vl:4b`; nothing of ours is running.

**The L3 set**, `corpus/l3-subset.txt`, built by
`pools.l3_subset` (spec 0020, step 6) by greedy cover over the panel:
- **36 panel pages, four from each of the nine families**, nine of them
  parts of a document;
- density: 16 medium, 13 sparse, 7 dense; language: 33 English, one each
  Portuguese, Spanish, Italian;
- every table, key–value, list and arrangement feature at least twice
  (the cover's four groups). Outside those groups, three panel features
  are absent (`text.justified`, `fmt.eu_numbers`, `look.dark_ground`)
  and five appear once (`look.buttons`, `look.chips`, `text.formula`,
  `text.drop_cap`, `fig.photo`);
- **no real PDF page.** The panel holds nine; the cover, which takes
  whatever page adds most, took none:

  | page | family | kind | density | language |
  |---|---|---|---|---|
  | c0074 | forms | application form | medium | en |
  | c0082 | forms | application form | sparse | en |
  | c0083 | forms | numbered-box tax form | dense | es |
  | c0196 | transactional | invoice | medium | en |
  | c0272 | reports | minutes | medium | en |
  | c0300 | reports | status report | medium | it |
  | c0411 | publishing | paper page | dense | en |
  | c0412 | publishing | paper page | dense | en |
  | c0472 | reference | timetable | dense | en |

- **No real PDF page has been converted under today's limits.** Dev's
  one attempt, c0072 (a dense form), timed out at 20 minutes in
  `L2-dev-mixed`, before the call limit existed.

**Time**, from `L2-dev-90` (90 dev pages, the 20-minute page limit and
the 3-minute call limit, `debug/runs/L2-dev-90/pages.jsonl`):

| density | pages | median | mean | timed out |
|---|---|---|---|---|
| sparse | 24 | 434 s | 484 s | 1 |
| medium | 36 | 452 s | 600 s | 2 |
| dense | 30 | 765 s | 800 s | 3 |

The 36 take **5.1 h at these medians, 6.0 h at the means, 5.9 h if
every dense page reaches its limit.** A medium page adds about 8 minutes,
20 at its limit.

---

## Two questions for Alessandro

Asked on the one-issue-at-a-time page (round 6,
https://claude.ai/artifact/RpUd3a7ioGjdNWBLyqM6JD); neither was asked in
rounds 1–5 (`../agents/review-issues.json`).

**Q1 — should the L3 set carry real PDF pages?**
- **Claude proposes yes: add every PDF page of the panel that is not
  dense, five** — c0074 and c0082 (application forms), c0196 (invoice),
  c0272 (minutes), c0300 (Italian status report). 41 pages.
- Why: P2 decides on this set, and a parser trained on millions of real
  pages may do better or worse on real pages than on pages Claude wrote.
  With none, P2 cannot see either. Five pages in three families give a
  look, not a rate, and they are reported in their own line, as the six
  held-out pages were.
- Why by a rule and not by eye: "not dense" picks them without anyone
  choosing pages by how they look. The four dense ones (a tax form, two
  two-column papers, a timetable) most likely reach the 20-minute limit,
  as dev's one dense PDF page did, and a timeout tells P2 only what dense
  generated pages already tell it.
- Cost: about 37 minutes at the medians, 100 if each reaches its limit:
  **41 pages, 5.7 h at the medians, 6.8 h at the means, about 7.6 h at
  worst** (every dense page and every PDF page at its limit).
- How: `pools.l3_subset` gains the rule, `corpus/l3-subset.txt` is
  rewritten by `tools/corpus_manifest.py`, and
  `tests/test_corpus_manifest.py`'s L3 test reads 41. No conversion code
  moves.
- Shown on the page beside dev's PDF pages of the same kinds (c0071,
  c0197, c0287), not the panel's own, which stay unopened until the run.

**Q2 — is every page opened?**
- **Claude proposes yes**: `measure_run.py --all`, and Claude reviews
  every page's sheet by the criteria, confirming or rejecting each
  check's fault and adding what the checks miss.
- Why: this is the reference P2 decides against. The sampling rule
  (spec 0021, step 5) opens only pages with a structural major, two per
  family, and moved pages; the rest would be judged by the checks alone,
  and the checks still miss faults (a group drawn below the one beside
  it, a list torn by a gap) and still raise false ones (over L2's 114
  called pages, 23 majors and 32 minors the review had rejected).
- What it costs: Claude's time only, no model. Opened pages are looked
  at, so the vault stays the exam: **no fix is pinned on an L3 page**,
  and nothing in the converter changes in L3.
- Your spot-check stays spec 0021's decision 2: every page where
  Claude's call overturns a check, and two at random.

---

## Steps

### Step 0 — the spec, the issue, his two calls

This spec; its issue; round 6 of the issue page with Q1 and Q2. His calls
go under "Decisions" below and into `review-issues.json`.

### Step 1 — everything with Chrome, then the time, then his go

- If Q1 changes the set: the rule in `pools.l3_subset`,
  `corpus/l3-subset.txt` rewritten by `tools/corpus_manifest.py`, and
  `tests/test_corpus_manifest.py` run (it re-shoots 60 pictures).
- No Chrome job is left running (`pgrep`), and nothing else beside the
  conversion.
- **Give Alessandro the time and the expected end, and wait for his go.**

### Step 2 — the conversion

One page at a time, the 20-minute page limit and 3-minute call limit,
detached, with nothing beside it:

```
nohup env PATH="$PWD/.venv/bin:$PATH" python tools/batch.py \
    L3-baseline --pages l3 > debug/L3-baseline.log 2>&1 & disown
python tools/batch.py L3-baseline --status
```

A timeout is recorded with its reason and not retried (spec 0021,
decision 9). If it stops, the same command resumes it.

### Step 3 — the measurement and the review

- `python tools/measure_run.py debug/runs/L3-baseline --all`: the
  checks over every page, the report, every page's sheet.
- **Claude reviews every page** by the criteria (Q2), with the
  visual-review skill: each check's fault confirmed or rejected by
  looking, its stage named from the IR and the trace, and the faults no
  check raises added by eye — spec 0021's "Where L2 stands" lists the
  known ones. Calls in `docs/agents/review-calls/L3-baseline.json`.
- A timed-out page has no render; it is counted as a timeout, by
  density and family, not reviewed.

### Step 4 — the result, and his calls

- **Fault classes ranked by pages touched**, majors first (criteria,
  "Deciding"), with the pages named; per family and per feature; the
  PDF pages, if any, in their own line.
- His calls through the issue page, round 7: every page where Claude's
  call overturns a check, and two at random. **Where his calls disagree
  with the checks, stop and ask.**
- A check issue the review finds is fixed as in L2, in `checks.py`,
  and pinned in `tests/test_checks.py` **on a dev page only**; the
  checks re-run over L3 after the fix.

### Step 5 — close

This spec's outcome; `docs/status.md`; `CLAUDE.md`; `level-up.md` §6;
the issue closed; a handover prompt for P1, with its facts re-measured.

---

## Rules

- **Never pass `unseal=True`.** The vault stays sealed.
- **No panel page is used in a test**, c0001 and c0002 above all.
- **L3 changes no conversion code.**
- One conversion at a time, nothing beside it; every Chrome job finished
  before a conversion starts.
- Stop and ask before any conversion longer than two hours, and wherever
  his calls disagree with the checks.
- Judge by eye (`review-criteria.md`); a number is a pointer to a page.

## Outcome — 2026-11-09: the reference P2 decides against

### The run

- **`L3-baseline`**, today's shipped pipeline (conversion code as at
  `7b00482`), over the 41 pages of `corpus/l3-subset.txt`, one page at a
  time, 2026-11-08 17:52 to 2026-11-09 00:26: **6.6 hours**, 577 s a page
  on average. Medians by density: sparse 405 s (14 pages), medium 520 s
  (20), dense 725 s (7).
- **37 converted, 4 timed out** at the 20-minute limit, not retried:

  | page | family | kind | density | arrangement | origin |
  |---|---|---|---|---|---|
  | c0034 | forms | numbered-box tax form | dense | three columns | generated |
  | c0196 | transactional | invoice | medium | one column | **PDF** |
  | c0291 | reports | status report | medium | cards grid | generated |
  | c0456 | reference | price list | medium | cards grid | generated |

  Six converted pages had a Zone read short: c0074, c0129, c0272,
  c0388, c0431, c0555.

### The review

- `python tools/measure_run.py debug/runs/L3-baseline --all`, then
  Claude's review of all 37 converted pages by the criteria, every sheet
  opened. Calls: `docs/agents/review-calls/L3-baseline.json`.
- **848 check faults called**: 822 confirmed (605 major, 217 minor) and
  26 rejected, on 10 pages. **65 faults added** that no check raises
  (46 major, 19 minor). Every major carries its stage, read from the IR
  and the trace.
- **Every one of the 37 pages has at least one major fault.** The probe
  found a structural fault on 9 of 10 unseen pages; L3 finds one on 37
  of 37.

**Majors per page**, the faults standing after the review:

| by | majors per page |
|---|---|
| origin | **PDF 43.5** (c0074, c0082, c0272, c0300); generated 14.5 (33 pages) |
| density | dense 27.3 (6); medium 19.9 (17); sparse 10.6 (14) |
| family | forms 33.8 (5); reports 25.8 (5); reference 22.3 (3); transactional 16.2 (4); fragments 13.5 (4); presentation 12.2 (4); publishing 10.0 (4); correspondence and legal 9.8 (4); credentials 9.8 (4) |

**Where the majors are made**:

| side | stages | majors | pages |
|---|---|---|---|
| **reading the page** | extract 177, layout 124, locate 83, rectify 69 (one page), inline runs 15, caption 13, classify 11, third reading 3 | **495** | 37 |
| **drawing it** | render 96, cv:looks 42, cv:furniture 8, cv:heading_sizes 7, cv:zone_chrome 2, cv:figure_pixels 1 | **156** | 36 |

Three majors in four are made on the reading side, the side a
parser-first front (P1, `level-up.md` §5.3) takes over. The drawing side
stays ours either way.

### The fault classes, ranked

Majors first, then the visible gain for the effort; pages touched counts
every page where the class stands after the review. The `why` of each
is in the calls file's `ranked`.

| # | class | pages | times | made at |
|---|---|---|---|---|
| 1 | words: lost | 24 | 182 | extract 98 (ticks, list numbers, a table's last rows), rectify 69 (c0300, a flat PDF cropped to one table), layout 8 |
| 2 | words: invented | 24 | 178 | locate 74 (fragments and copies of lines already read), layout 73 (overlapping Zones drawn twice), caption 13 (a Title repeated as its first line) |
| 3 | beside: drawn under (with layout: beside) | 13 | 13 | layout: card grids and side-by-side blocks drawn as a stack |
| 4 | looks: fill drawn another shape | 12 | 14 | layout 8, render 5: a band or card split into one box per Zone |
| 5 | height | 37 (24 major) | 37 | render 18, layout 17: mostly the consequence of 3 and 4 |
| 6 | structure: numbers as bullets | 10 | 12 | extract |
| 7 | words: mark lost (✓ ✗ ☐) | 8 | 15 | extract |
| 8 | words: changed | 10 | 15 | extract: misreads |
| 9 | type: bold lost | 26 | 26 | inline runs 10 (a bold value under a regular label in one cell), cv:looks 10 |
| 10 | type: sizes out of proportion | 33 | 67 | render 37, cv:looks 20 (sizes measured 0.25, 0.30, 0.41 of the body) |
| 11 | looks: ground changed | 4 | 7 | cv:looks: white type on a dark band measured as dark on a white chip |
| 12 | looks: too faint | 3 | 3 | cv:looks |
| 13 | words: drawn unreadable (added) | 2 | 2 | a Zone given a column a pixel wide; a word drawn at 0.30 of the body |
| 14 | rules: cells merged as drawn | 9 | 13 | render: row rules not drawn |
| 15 | lines: broken differently | 13 | 13 | extract, render |
| 16 | cells: wrong column | 5 | 17 | extract: a table's last row read as loose lines |
| 17 | rules and looks: frame missing | 11 | 17 | render, cv:furniture |

**The PDF pages, in their own line.** Four of the five converted; c0196
timed out. They carry three times the majors of a generated page:
c0300, a flat page, was taken for a photograph and cropped to its PG8
table, losing PG7 and the running header (69 words); c0074 and c0082
lose content to the unclaimed-lines pass's fragments; c0272 read a Zone
short.

### Round 7 — his calls on the review

Fifteen issues on the one-issue page, 2026-11-09 (decision 4): every
check fault Claude rejected (27 on 10 pages, issues 1–9), one example of
each new kind of fault Claude added (10–13), and two of Claude's
confirmed majors drawn at random (14–15). **All fifteen agreed.** His
notes: c0575's line is in place, what it lost is its bold and colour;
c0431's worst fault is its first section's title drawn twice in the
wrong format (confirmed, #52); c0476's fault is the layout, the 2×3 card
grid drawn as one column (confirmed, #24).

### The checks fixed — round 7's issues

Each in `checks.py`, pinned in `tests/test_checks.py`'s
`TestWhatRoundSevenDecided` on a dev page, failing on the old code and
passing on the new:

| issue | the fix | pinned on |
|---|---|---|
| l3-ligature (c0082) | the strict spelling check maps the source word through the page's `TWIN_SPELLINGS` before comparing | c0421, its twin made to drop the fi of 'soil-specific' |
| l3-moot (c0300) | a table or a block mostly not drawn is not judged for structure or type (`JUDGED_KEPT`, `_judged`): half its words drawn, or a run of its own | c0029's '5. Safety and staff', c0309's 'Note de service' |
| l3-hours (c0476) | a block printed on a heading's row, right of it, is not in its section | c0366's themes box beside 'Foire aux questions' |
| l3-dropcap (c0334) | a single letter set twice its word's size or more, with no space before the rest of the word in the HTML, is glued to it (`Word.joined`, a new projection field); its loss is one minor, `drop cap lost`, and it is not a heading | c0399's 'E' + 'very', the drop cap drawn in the line |
| l3-copies (c0476) | a copy of a repeated word is re-paired only where it lands nearer its neighbours than its copy in order | no dev page shows the fault; c0345's and c0366's pins keep the re-pairing working |
| l3-columns (c0431) | only a heading the page prints as one can stand over a block in the drawing | no dev page shows the fault; the round-1 to round-5 heading pins hold |

l3-ground (c0074) and l3-rules (c0523) are left as recorded: two cases
of a line on two grounds, and one rule count Claude could not trace.

**Re-checked over L3 and the 23 frozen dev renders**: every fault that
goes is one round 7 rejected, or sits on a block not drawn at all; c0342
and c0382 keep their type faults with a lost block left out; c0334 gains
the drop cap's minor, which the review had added by hand. On dev, the
faults that go are on blocks not drawn (c0008, c0029, c0063, c0309), two
minors L2 rejected (c0246), and three of c0366's five interleavings,
whose fault, the first answer drawn as a narrow column, is still raised
twice. The re-measure with the fixed checks (`measure_run.py --all`, 2026-11-09)
takes L3's check faults from **848 to 828** (majors 635 to 617): c0082's
three spellings, c0300's five on PG7, c0334's merge and heading (one
drop cap minor gained), c0431's two, c0476's nine. It is under
`debug/runs/L3-baseline/checks/`; what the review answered is kept
beside it in `checks.reviewed/` and `_review.reviewed/`, and the calls
file's `after_round_7` names the faults the fixed checks no longer
raise.

### What L3 hands on, and the prompt for P1

**The reference.** `L3-baseline`'s ranked table above, its majors by
stage, and the calls in `docs/agents/review-calls/L3-baseline.json`. P2
compares P1's arm against it **class by class, on the same 41 pages**,
by the same judge and criteria. The run itself is in
`debug/runs/L3-baseline/` (gitignored): `pages.jsonl` holds each page's
time and verdict.

**What the checks still miss**, for P1's review to look for by eye
(each added by this review, none raised by a check):
- a block drawn unreadable: a Zone given a column a pixel wide
  (c0555), a word drawn at 0.30 of the body (c0596);
- an accent word drawn as a link, blue and underlined (c0547);
- a chart drawn as loose numbers and table rows (c0467);
- a card's fill split into one box per Zone while its text stays on the
  same ground (c0575, and 10 more pages);
- a frame found only as loose rules, and decorative rules not drawn
  (c0097, c0243, c0441, c0515);
- side by side drawn as a stack where the beside check is silent (four
  pages, among them c0485's notes and c0527's details).

**Open check issues:** l3-ground (a line on two grounds, c0074) and
l3-rules (c0523's rule count) stay as recorded; the copies and columns
fixes have no dev page that shows their fault.

**Proved on this code, 2026-11-09**:
- `tools/replay_run.py tests/frozen/s14-result --label L3-close-replay`:
  21 of 21 byte-identical, 0 asked differently;
- `tools/rederive.py` over it: 21 of 21 byte-identical files;
- every dev page checked against itself: 231 pages, 0 faults, every
  token matched (214 s);
- 1702 tests pass (1 skipped), 4 of them round 7's pins; `mypy src/`
  clean.

**The prompt for P1:**

> Start P1 of the level-up plan, the GLM-OCR parser-first PoC:
> `docs/level-up.md` §5.3, §6 and decision 2 of §8. Read
> `docs/level-up.md`'s Gist, §5.3 and §8 (GLM-OCR as of 2026-10-24),
> spec 0022's "Outcome" (the reference: the ranked fault classes, the
> majors by stage, what the checks still miss),
> `docs/agents/review-criteria.md`, then `docs/status.md`.
>
> 1. **Re-check GLM-OCR** before anything is built: the `glmocr` SDK's
>    latest version, its layout model (PP-DocLayoutV3) and its reader,
>    `glm-ocr:latest` on Ollama, the licences. Record what changed since
>    2026-10-24.
> 2. **Write spec 0023** and its GitHub issue
>    (`docs/agents/issue-tracker.md`). Questions for Alessandro on the
>    one-issue-at-a-time page (round 8; load the `artifact-capabilities`
>    skill first; never re-show an issue he has decided,
>    `docs/agents/review-issues.json`): the branch's base (§5.3 says
>    `develop`, but the corpus, the checks and the batch runner live on
>    `level-up`; Claude's recommendation: branch from `level-up`); the
>    first pages (a handful of dev pages to build the adapter on, then
>    the L3 set); and the time budget for a 41-page run.
> 3. **Build arm D2**, on branch `poc-parser-first`: GLM-OCR's own
>    entire pipeline, nothing of today's layout fed into it; an adapter
>    from its blocks (box, category, order, content) to the IR's Zones,
>    Blocks and Cells, each with its box; then today's looks, style
>    record, furniture and renderer. Iterate on the adapter and the
>    looks side on dev pages only, never the parser's weights.
> 4. **Convert the L3 set** with D2 (`corpus/l3-subset.txt`, 41 pages),
>    one page at a time, the 20-minute page limit. **Over two hours: give
>    him the time and wait for his go.** Then `python
>    tools/measure_run.py debug/runs/<label> --all`, and Claude's review
>    of every page by the criteria, calls in
>    `docs/agents/review-calls/<label>.json`.
> 5. **The comparison**: D2 against `L3-baseline` class by class, pages
>    touched and majors by stage, the PDF pages and the timeouts in
>    their own lines; his spot checks on the issue page. Then P2's
>    question, for him: keep today's, take D2, or a mix.
>
> Rules: local models only. Never pass `unseal=True`. No panel page is
> used in a test or to tune the adapter, c0001 and c0002 above all.
> Today's pipeline on `level-up` stays as it is: the replay of
> `s14-result/` stays 21 of 21. One conversion at a time, nothing beside
> it; every Chrome job finished before a conversion starts. Stop and ask
> before any conversion longer than two hours, and wherever his calls
> disagree with the checks. Judge by eye; a number is a pointer to a
> page. Keep replies short: bullets, facts, no filler.

## What L3 does not do

- No converter change, and no fix pinned on an L3 page.
- No panel conversion beyond the L3 set, and no vault.
- No comparison with an earlier run: there is none on these pages, so
  every call is the render against its source.

---

## Decisions — Alessandro

| # | asked | decided |
|---|---|---|
| 1 | Q1: real PDF pages in the L3 set? | **Yes, the five not dense** (round 6, 2026-11-08): c0074, c0082, c0196, c0272, c0300; 41 pages |
| 2 | Q2: every page opened? | **Yes** (round 6, 2026-11-08): Claude reviews all 41; he checks every page where Claude's call overturns a check, and two at random |
| 3 | the conversion's time, and the go | **Go**, 2026-11-08, given about 5.7 h (7.6 h at worst) |
| 4 | round 7's scope: counted literally, 33 of 37 pages overturn a check, any added major counting | **Fifteen issues** (2026-11-09): every rejection, one of each new kind added, two at random |
| 5 | round 7, the fifteen | **All agreed** (2026-11-09), with three notes, in the outcome above |
