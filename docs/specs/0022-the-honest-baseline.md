# The honest baseline: today's pipeline on panel pages nobody has tuned on

**Status: decided 2026-11-08, issue #45; the conversion running.** The decisions are at the end.
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
