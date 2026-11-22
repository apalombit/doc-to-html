# The milestone, its first half: D2 on the panel

**Status: open, 2026-11-22, issue #49, branch `milestone` (cut from
`skeleton`).** `level-up.md` §6, row M1, its first half only
(Alessandro, 2026-11-22: the panel; **the vault is not for now**).
Nothing in the conversion changes in this spec: it runs arm D2 as it
stands at `94699c9` over the L3 set and judges it.

**Read first**, in order: `CLAUDE.md`'s READ THIS FIRST;
[`../status.md`](../status.md); [`0025-page-skeleton.md`](0025-page-skeleton.md)'s
"Outcome — the spec"; [`../agents/review-criteria.md`](../agents/review-criteria.md);
then this spec.

---

## 1. What is measured

D2 over the 41 L3 panel pages, against `L5-D2-L3`, the same set on
D2 as it stood on 2026-11-10 (`7de8497`).

**What lies between the two runs**: 22 commits, each change in them
D2's own:
spec 0024's two causes (a line cut by the row below it, a Cell sized
from a box that does not hold its text) and its part two (tick boxes,
line cuts, table rules, nested and held boxes, leaders, units, a
line's own colour), then the whole of spec 0025 (the skeleton, its
grouping and drawing, grids read as tables, one size per role in a
table). Every one of them was judged on dev pages only. **This run is
the first time any of them meets the panel**, so a page moved here
cannot be credited to one change by this run alone.

**What is not measured**: the vault (never opened here; `unseal=True`
is never passed), and today's pipeline, which stays as it is.

## 2. Steps

| step | what | done when |
|---|---|---|
| 0 | this spec, issue #49, branch `milestone` | done 2026-11-22 |
| 1 | **prove first**: `tools/replay_run.py tests/frozen/s14-result` 21 of 21, `mypy src/` | both hold — done 2026-11-22: 21 of 21 byte-identical, 0 asked differently; `mypy src/` clean |
| 2 | **the run**: every Chrome job finished first; `tools/batch.py M1-D2-L3 --arm d2 --pages l3`, detached; its regions checked against `L5-D2-L3`'s | 41 pages converted, the regions byte for byte — done 2026-11-22 (outcome below) |
| 3 | **judge**: `tools/measure_run.py debug/runs/M1-D2-L3 --previous debug/runs/L5-D2-L3 --model glm-ocr:latest --all`; every moved page's sheet opened against `L5-D2-L3`: better, same or worse, a sentence each naming the element | every moved page called — done 2026-11-22: 41 of 41 (outcome below) |
| 4 | **his spot checks** on the issue page: every page called worse, two at random; no decided issue re-shown (`../agents/review-issues.json`) | the round published — done 2026-11-22: round 13, 18 issues |
| 5 | the outcome here; stop for his call | written 2026-11-22; **decided 2026-11-22** (Alessandro, in chat: "Go ahead keep this"): the code kept; part two below |
| 6 | **part two, (b)**: a row or cell printed larger keeps its size in a table, reproduced on 5 random dev pages first | the 5 drawn nearer the source by eye, none worse — done 2026-11-22: 2 of 10 better, 8 the same (outcome below) |
| 7 | **part two, (c)**: a cut line's short piece at its line's size, likewise | likewise |
| 8 | **part two, (a)**: a card grid held by the skeleton, likewise | likewise |
| 9 | the panel run again, judged against `M1-D2-L3`; stop for his call | every moved page called |

## 3. Rules

- **Local models only.** Never pass `unseal=True`.
- **No panel page is used in a test or to tune anything**, c0001 and
  c0002 above all. A fault seen on a panel page is reproduced on a dev
  page first, and only when he names it.
- **Today's pipeline stays as it is**: the replay of `s14-result/`
  stays 21 of 21.
- **One conversion at a time, nothing beside it**; every Chrome job
  finished before the run starts. Never edit `src/` while it runs.
- **Run nothing he has not asked for.** Tests minimal: the changed
  files' tests, the replay when shared code moves, `mypy src/`.
- **Judge by eye** (`review-criteria.md`); the checks' counts are
  pointers to pages.

---

## Outcome — the run, 2026-11-22

`tools/batch.py M1-D2-L3 --arm d2 --pages l3` on `94699c9`, after the
replay and `mypy src/`, with no Chrome job and no other model running:
**41 of 41 converted in 23 minutes** (11:11 to 11:34), a mean 33 s a
page. **The parser's regions are `L5-D2-L3`'s byte for byte on all
41**, so every difference is our side's. Five grids were read as tables
on four pages (c0121, c0456, c0476, c0555 twice), 15.5 s in all. All 41
renders moved.

## Outcome — by eye, against `L5-D2-L3`, 2026-11-22

Every page's sheet opened, the source beside both renders:
**17 better, 9 the same, 5 mixed, 10 worse.**

- **Better, 17**
  - c0032: the subtitle under the title, `FIGURE 3 / TRADING` on its
    two lines, the table's `Aug` row at its size.
  - c0064: the frame round the whole form; the CPF and name fields at
    the body's size.
  - c0069: sections A and B side by side; the job title at its size
    (spec 0024's worse page).
  - c0082: the green band's heading at its size, not a speck.
  - c0097: the marks table one framed table with its column rules.
  - c0243: the teal header one band; the tick boxes back; the page's
    frame.
  - c0252: `Outpatient Prescription` back at the top right; the `Rx`
    tile; the tick boxes.
  - c0300: the second table's descriptions readable, at one size.
  - c0342: the trip details' labels over their values.
  - c0356: the sidebar's labels over their values; the address on two
    lines.
  - c0382: the four cards whole at their width; L5 set `Try it` one
    word a line.
  - c0387: the headline across both columns; the pull quote and the
    last paragraph in the left column; a paragraph black, not red.
  - c0388: `BEFORE YOU GO` at the sidebar's width; the page's height.
  - c0441: the two small timetable rows at the table's size (spec
    0024's worse page).
  - c0523: `Lancaster → Derby` side by side; `Have a pleasant
    journey…` whole (spec 0024's worse page).
  - c0555: `Set the new tiers` readable and `STANDARD £29.00` back;
    the height nearer.
  - c0596: `Meet at` and `Booking line` on their own lines; the
    standfirst regular; the section title centred.
- **The same, 9**: c0070, c0234, c0272, c0291, c0316, c0431, c0467,
  c0485, c0515.
- **Mixed, 5**
  - c0034: the form's title shows again and the `FILER INFORMATION`
    band is drawn, but `INSTRUCTIONS BY LINE` is at about 3 times the
    body.
  - c0128: the two cut lines whole again, but `TOTAL (33 items)
    54.44` is at the rows' size.
  - c0343: the wordmark over its small subtitle, but `arrange a
    meeting.` is drawn at 0.82.
  - c0527: the pill reads on one line, but a dark fill is added behind
    the photo.
  - c0547: the quote's attribution on its own line, but the slide is
    1.15 of its height.
- **Worse, 10**
  - c0456: the eight price cards collapse into narrow lanes, one word
    a line, cut at the right edge; 2603 px for 978.
  - c0575: the feature cards spread, one tall with ```` ```markdown ````
    as a heading; 1.76 of the height.
  - c0476: the dish cards staggered out of their rows; `Sous chef`
    under the credits; 1.21 of the height.
  - c0129: the payment card in three boxes, its labels parted from
    their values; 1.37 of the height.
  - c0115: the receipt's `TOTAL $110.28` at its rows' size.
  - c0405: the recipe's four facts at their labels' size, the rules
    between them lost.
  - c0334: the banner's one-line title broken in two; `Mondays.` a
    speck.
  - c0196: the privacy statement's first two lines at half size.
  - c0121: the net pay `$1,783.31` at about the body's size;
    `64.5 hours` slid right.
  - c0074: `Form 8822 (Rev. 2-2021)` torn off the footer line and
    split.

**The worse and mixed pages, by cause.** Read from the IR, on panel
pages only: by the rules each is reproduced on a dev page before
anything is changed.

| # | cause | stage | worse | mixed |
|---|---|---|---|---|
| a | cards broken, spread or staggered: the skeleton's lanes do not hold a card grid, and a grid read across cards joins them (c0476's table holds the first dish's text and the fourth and fifth dishes) | ③a, 3c | c0456, c0575, c0476, c0129 | |
| b | a row or cell printed larger, flattened in a table: one size per role takes the total's or the value's own size (c0115 and c0405 are tables in both runs) | 3e | c0115, c0405 | c0128 |
| c | a cut line's short piece measured on its own: the reader's line cut where the page breaks it (spec 0024 §8), the tail measured small: `Mondays.` 0.6, `arrange a meeting.` 0.82, c0196's lines 0.5; each at full size in L5 | ④ | c0334, c0196 | c0343 |
| d | a box regrouped and measured differently (spec 0025's first named fault): c0121's net pay measured 0.9 where L5 measured 1.6 | ④ | c0121 | |
| e | one each: a footer's right part drawn under its line (c0074); a one-line banner title broken (c0334); a heading at 2.9 times (c0034); a fill added behind a photo (c0527); a page 1.15 of its height (c0547) | ③, ④, ⑤ | c0074 | c0034, c0527, c0547 |

**The grids, on the panel**: of the five read, two are right (c0121's
earnings table, c0555's `GO LIVE / BUDGET`). c0476's joins three dish
cards. c0555's puts `TRIAL ENDS` a row below its label. c0456's is
drawn among the broken cards.

**The checks, as pointers** (the same check code, `4505689d305a`, on
both runs): **803 majors against 851**. They count fewer on 23 pages,
more on 4 (c0115, c0128, c0405, c0456) and the same on 14. All four
pages with more are pages the eye calls worse or mixed; on two worse
pages they count fewer (c0074, c0575). They miss the specks (c0334,
c0343), the torn footer (c0074), the labels parted from their values
(c0129) and the title come back (c0034).

| check | L5 | M1 |
|---|---|---|
| words | 608 | 598 |
| type | 118 | 104 |
| lines | 35 | 25 |
| rules | 33 | 20 |
| height | 19 | 22 |
| looks | 18 | 17 |
| cells | 8 | 8 |
| beside | 6 | 4 |
| order | 5 | 5 |
| overprint | 1 | 0 |

**What this run cannot say**: which change moved which page. Between
the two runs lie spec 0024's two causes, its part two and the whole of
spec 0025. Three of spec 0024's worse pages (c0069, c0441, c0523) and
c0128's cut lines are mended, as its dev work predicted.

**Round 13** puts these to Alessandro on the issue page, 18 issues:
- the 10 worse pages and the 5 mixed ones;
- c0485 and c0596, drawn at random (seed 20261122) from the 9 of the
  26 better or same pages he has not seen in any round;
- what comes next. Claude proposes keeping the code (a net gain, 17
  better against 10 worse), mending (b) and (c), then (a), each on a
  dev page first, then this panel run again. The vault stays closed.

Round 12's three answers (all agreed, 2026-11-20 and 21) are copied
into `review-issues.json`.

---

## Part two — the worse pages' causes, on dev first

**Decided 2026-11-22** (Alessandro, in chat, on round 13's last issue):
"Go ahead keep this". The code stays; (b), (c), then (a), each in
order and each judged as spec 0025 §5 judged its steps:

- the fault reproduced on dev pages before anything changes; a pool of
  dev pages that show it, **5 drawn at random** (seed recorded), 5 more
  if unclear, then decide, and a direction that does not work is
  dropped;
- drawn offline from the recorded regions (`tools/d2.py --regions
  L5-D2-dev`), no conversion; the panel pages are never drawn, read or
  used to tune;
- tests minimal: the changed files' tests, the replay of `s14-result/`
  when shared code moves, `mypy src/`;
- one commit a step, its outcome written here;
- then the panel run again (`tools/batch.py M2-D2-L3 --arm d2 --pages
  l3`, about 25 minutes), judged against `M1-D2-L3`, and his call.

## Outcome — part two (b), a row printed larger, 2026-11-22

**The pool**: the 37 dev pages whose table holds a Cell measured 1.2
times its role's median or more, and 0.15 above it, at `L5-F13` (before
3e), most of them receipts and invoices with a total set large. Drawn
at random, seed 260006: c0177, c0008, c0112, c0489, c0004, then c0179,
c0521, c0175, c0186, c0423. Each first five was checked at today's code:
3e draws the Cell 0.15 or more smaller than measured on every one.

**What the sample showed**: two kinds of Cell above its peers.
- **A whole row set large, the page's**: c0177's `Totale` and
  `3.295,22 €` at 1.67 among rows at 1.00; c0175's `Charged $26.87`
  at 1.33. 3e drew both at the rows' size.
- **One Cell, the measure's**: c0112's `Type` header at 1.38, c0489's
  bold `2,382` at 1.22, c0008's `16` at 1.25, c0004's `1. DELEGATE`.
  The page prints each at its row's size, and 3e is right to draw it
  there.

**What shipped** (`parser_first.table_sizes`): where two Cells of a row
or more measure `render.SIZE_STEP` (0.15) or more above their group's
size, each keeps its own. The row's other Cells keep their group's: the
first build drew c0177's whole row at its median and set the
`PAGAMENTO` note, which the parser's table puts in the total's row, at
1.67 too.

**By eye**, `tools/d2.py B-2 --previous B-0` and `B-2b --previous B-0b`:

| page | before | after | |
|---|---|---|---|
| c0177 | `Totale 3.295,22 €` at the rows' size | set large, as printed; the note beside it at the body's size | **better** |
| c0175 | `Charged $26.87` at the rows' size | set large, as printed | **better** |
| c0008, c0112, c0489, c0004, c0179, c0521, c0186, c0423 | one Cell above its peers, drawn at theirs | the same | same |

D2's code only; `tests/test_skeleton.py` has two more tests (a row set
large, and one Cell above its peers drawn at theirs). The first fails
without the rule.
