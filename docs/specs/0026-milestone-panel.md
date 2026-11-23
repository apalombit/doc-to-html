# The milestone, its first half: D2 on the panel

**Status: closed 2026-11-22, issue #49, branch `milestone` (cut from
`skeleton`); `main` fast-forwarded to it.** Closed on Alessandro's
word (in chat, round 14's last issue: "Ok close here and move on").
The spec's end is "Outcome — the spec" and "The prompt for the next
session", below. `level-up.md` §6, row M1, its first half only
(Alessandro, 2026-11-22: the panel; **the vault is not for now**).
The spec first ran arm D2 as it stood at `94699c9` over the L3 set and
judged it. Then, on his word, part two mended three causes on dev
pages and the panel was run again.

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
| 7 | **part two, (c)**: a cut line's short piece at its line's size, likewise | likewise — done 2026-11-22: 3 of 15 better, 12 the same (outcome below) |
| 8 | **part two, (a)**: a card grid held by the skeleton, likewise | likewise — done 2026-11-22: 3 of 10 better, 7 the same; 1 of 5 more better, none worse (outcome below) |
| 9 | the panel run again, judged against `M1-D2-L3`; stop for his call | every moved page called — done 2026-11-22: 7 moved, 4 better, 1 mixed, 2 the same, none worse (outcome below); **decided 2026-11-22** (Alessandro, in chat: "Ok close here and move on"): close; next, a spec for the remaining causes, the undrawn card grid first |
| 10 | **the close**: `status.md`, `CLAUDE.md`, `level-up.md` §6, `main` fast-forwarded, issue #49 closed, the next prompt | done 2026-11-22 |

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

## Outcome — part two (c), a sentence going on in one size, 2026-11-22

**The pool**: dev pages drawn at random, seed 260007, each drawn at
today's code until 15 showed a line `linebreaks.restore` cut whose
parts measure `SIZE_STEP` or more apart: 64 drawn. First 10: c0085,
c0514, c0235, c0203, c0434, c0509, c0236, c0544, c0419, c0095; then
c0504, c0427, c0315, c0023, c0292.

**What the sample showed**: most such parts are the page's own other
size: a label over its value (c0236's `MRN` over `LHP-0092817`), a
heading over its subtitle (c0095's `Rental Application`). The fault is
a sentence the page wrapped, its parts set apart (`apart`) for a size
measured off few letters: c0434's footnote over its last word
`quarter.`, measured on its `t` at 0.75, drawn a speck on a line of its
own; c0419's standfirst, 1.08 over 0.92, broken in two Blocks. Neither
the render's wrap test (`_broken`'s room for the next word; a value's
first word fills its box) nor the letters' width (a label's are as wide
as its value's) tells them apart. The text does: every part that goes
on with a sentence opens in lower case after a part ending in a
lower-case letter, and every label, value and heading in the sample
opens in a capital or a figure, or follows one, as c0504's `E-MAIL`
over `d.lockhart@example.com`.

**What shipped** (`linebreaks._goes_on`): a part that opens in lower
case after a part that ends in a lower-case letter or a comma is not
set apart for its size; for bold it still is.

**By eye**, `tools/d2.py C-1 --previous C-0` and `C-2b --previous C-0b`:

| page | before | after | |
|---|---|---|---|
| c0434 | `quarter.` a speck on a line of its own | `previous quarter.` reflowed at the footnote's size | **better** |
| c0419 | the standfirst broken after `comment réserver` | one paragraph, as printed | **better** |
| c0023 | `entregue` small on a line of its own | at its item's size | **better** |
| the other 12 | label over value, heading over subtitle, set apart | the same | same |

D2's code only (`linebreaks` runs in D2 alone);
`tests/test_linebreaks.py` has two more tests (a sentence going on, a
label over a value in lower case). The first fails without the rule.

## Outcome — part two (a), a grid of cards, 2026-11-22

**The pool**: the 19 dev pages the corpus labels `arr.cards_grid` (3 of
the panel's 4 card pages are). Drawn at random, seed 260008: c0568,
c0384, c0394, darkdeck_0009, c0263, then c0464, c0439, c0587, c0595,
c0427, each against `L5-F13` (dev before the skeleton), its grids read
as a batch run reads them.

**What the sample showed**:
- **c0427** has the panel's worst fault (c0456's, c0129's): twelve
  product cards lose their frames, and each card's `CODE / SIZE /
  FINISH` and price fall to rows of their own, away from their card.
  Three causes, one under the other:
  1. **The cards stand 9 px apart**, under `GUTTER` (half a line), so
     no cut down was a candidate and each row of four was kept flat.
     The gutter keeps the words of one printed line together; two drawn
     boxes are parted by their edges.
  2. **A box that is the cards' outline**: the detector traced the
     twelve as one box round them all, edge for edge. The page draws no
     such box, and a box inside a box is not drawn, so no card was.
  3. **Each card drawn to its own height**: the page ends a row's cards
     at one height; the render ended each frame at its own text.
- **c0384** (a FAQ, its items under rules, no boxes): the parser reads
  the items column by column, so the cut down wins and the second row
  is staggered. Not mended: the order is the skeleton's signal, and a
  shared gap across is also what two columns of paragraphs can show.
- **c0568**: the second card inset in a pale fill and wrapped narrower.
  A drawing fault, not mended.
- c0394, darkdeck_0009, c0263, c0464, c0439: no card fault.

**What shipped**:
- `skeleton._between_drawn`: a gap down between drawn boxes is a cut
  whatever its width;
- `skeleton._outline`: a box holding only boxes inside it, its edges
  theirs within `OUTLINE` (0.002 of the page), is not a container;
- `render._card_row`: a banded Region whose every lane is one frame,
  the page drawing them from one top to one bottom within
  `ALIGN_SLACK`, draws each frame to the row's height (only D2 sets
  `banded`).

**By eye**, `tools/d2.py A-3 --previous A-0` (A-1 and A-2 the steps
between), then 5 random `arr.panels_side_by_side` dev pages (seed
260009) before and after, `A-3p --previous A-0p`:

| page | before | after | |
|---|---|---|---|
| c0427 | cards unframed in one outer frame; fields and prices in rows of their own below the cards; 1.57 of the height | twelve framed cards in three rows, each holding its fields and price, each row one height; 1.42 (the Secateurs picture is still set under its text) | **better** |
| c0595 | the six metric cards at six heights | each row's cards one height, as printed | **better** |
| c0587 | the Household and Library cards at two heights | one height, as printed | **better** |
| c0568, c0384, c0394, darkdeck_0009, c0263, c0464, c0439 | | the same | same |
| c0096 | panel B's frame shorter than panel A's | both one height, as printed | **better** |
| c0011, c0191, c0548, c0600 | | the same | same |

`render.py` is shared code: **the replay of `s14-result/` is 21 of 21
byte-identical, 0 asked differently.** `tests/test_skeleton.py` has two
more tests (cards closer than a gutter parted; their outline no box),
each failing without its rule; the render's rule is pinned by the
replay (today's) and by eye (D2's), as spec 0025's were.

## Outcome — the panel run again, 2026-11-22

`tools/batch.py M2-D2-L3 --arm d2 --pages l3` on `177c1d6`, nothing
beside it: **41 of 41 converted**, a mean 34 s a page. The parser's
regions are `M1-D2-L3`'s byte for byte on all 41, and the grids read
are its grids (their timings apart). **7 renders moved**; the other 34
are byte for byte M1's.

**By eye, against `M1-D2-L3`** (`tools/measure_run.py debug/runs/M2-D2-L3
--previous debug/runs/M1-D2-L3 --model glm-ocr:latest --all`):

| page | M1 | M2 | |
|---|---|---|---|
| c0115 | `TOTAL $110.28` at the rows' size | set large, as printed | **better** (M1 worse page) |
| c0405 | the four facts' values at their labels' size | `15 min`, `25 min`, `2 hours` set large, as printed | **better** (M1 worse page) |
| c0343 | `arrange a meeting.` drawn at 0.82 | at its paragraph's size | **better** (M1 mixed page) |
| c0382 | the second row's cards at two heights | each row's cards one height, as printed | **better** |
| c0196 | the privacy statement's first two lines at half size, the third at its size | one paragraph, as printed, but all of it at half size | mixed (M1 worse page) |
| c0575 | the feature cards spread, a code fence as a heading | the same; the guarantee card drawn to its row's height | same |
| c0555 | | the same; the first row's two cards one height | same |

**The M1 worse and mixed pages that did not move**, and why, read from
the IR (no panel page tuned on):
- **c0456, c0476** (cards): their cards have no drawn box, so (a)'s
  rules, which part drawn boxes, do not reach them. c0456 is c0384's
  fault: the parser reads the price cards column by column, the cut
  down wins, and its lanes hold cards and lifted blocks. c0476's dish
  cards are cut into a part the skeleton calls a grid, across three
  dishes, and the grid read joins them.
- **c0129**: its three boxes are found; its fault lies lower, not here.
- **c0334**: `Mondays.` is a block of its own (the parser's), not the
  tail of a cut line, so (c) does not reach it; it still measures 0.6.
- **c0128**: the reader returned the total row as one Cell,
  `TOTAL(33items)54.44`, so the row holds one measured Cell and (b)
  needs two.
- c0121, c0074, c0034, c0527, c0547: one-offs, not in part two.

**What part two did, on the panel**: of M1's 10 worse pages, 2 are
mended (c0115, c0405) and 1 mixed (c0196); of its 5 mixed, 1 mended
(c0343); 1 page more is better (c0382), and none is worse. Judged
against M1 only; no page was opened against L5 again.

---

## Outcome — the spec, 2026-11-22

**The milestone's first half: D2 on the 41 L3 panel pages**, which no
one has tuned on. The vault stays closed (his word).

**M1, D2 with spec 0024's part two and spec 0025, against `L5-D2-L3`**:
17 better, 9 the same, 5 mixed, 10 worse. Net gain, so kept
(Alessandro, "Go ahead keep this"). The parser's regions were the same
byte for byte, so every difference is our side's.

**Part two, the worse pages' causes, each reproduced and judged on dev
first** (no panel page drawn, read or tuned on):

| cause | what shipped | on dev, by eye |
|---|---|---|
| (b) a row printed larger, flattened in a table | `parser_first.table_sizes`: a row with two cells or more above their role's size keeps theirs | 2 of 10 better (c0177, c0175), none worse |
| (c) a cut line's short piece measured small | `linebreaks._goes_on`: a sentence going on keeps its line's size | 3 of 15 better (c0434, c0419, c0023), none worse |
| (a) a grid of drawn cards broken | `skeleton._between_drawn` (cards parted by their edges), `skeleton._outline` (their outline no box), `render._card_row` (a row of cards one height) | 3 of 10 better (c0427, c0595, c0587), 1 of 5 more (c0096), none worse |

**M2 against M1**: 7 pages moved; 4 better (c0115, c0405, c0343,
c0382), c0196 mixed, 2 the same, none worse. Of M1's 10 worse pages, 2
are mended and 1 is mixed. The checks' majors went 803 → 801.

**What is left on the panel**, by cause, the worst page first. None is
mended on a panel page; each is reproduced on dev first, or recorded as
not found:

| # | cause | stage | panel | on dev |
|---|---|---|---|---|
| 1 | a grid of cards the page draws no box round: the parser reads it column by column, the cut down wins, the lanes hold cards and lifted blocks | ③a, the order rule | c0456 (2.66 of its height) | c0384 |
| 2 | a grid part across several cards, its table read joining them | ③a, 3c | c0476 | not yet looked for |
| 3 | cards spread, one tall with a code fence as its heading | not read from the IR | c0575 | — |
| 4 | a payment card in three boxes, its labels parted from their values; its boxes are found, the fault is lower | not read from the IR | c0129 | — |
| 5 | sizes in prose: a parser block of its own measured small (`Mondays.` 0.6); a paragraph drawn at half size. **Minor**, his call on c0196 (round 14): its words all in, "just font size" | ④ | c0334, c0196 | spec 0025's left fault 2 (c0246, c0439, c0407) |
| 6 | a box regrouped, measured differently: the net pay at 0.9 where L5 measured 1.6 | ④ | c0121 | c0198 (spec 0025's fault 1) |
| 7 | the reader returns a table row as one cell (`TOTAL(33items)54.44`), so (b) has one cell to keep | the parser's reader | c0128 | — |
| 8 | one each: a footer's right part torn off (c0074); a one-line banner title broken (c0334); a heading at 2.9 times (c0034); a fill added behind a photo (c0527); a page 1.15 of its height (c0547) | ③, ④, ⑤ | five pages | — |

**What is not known**: the vault, by his word; and whether causes 1
and 2 are one fault. Both concern a grid of cards with no drawn box.

## Decisions — Alessandro

| # | asked | decided |
|---|---|---|
| 1 | the milestone's halves | **Decided** (2026-11-22, the prompt): the panel only; the vault is not for now, `unseal=True` never passed |
| 2 | round 13's last issue: keep the code, mend (b), (c), then (a) on dev first, run the panel again | **Decided** (2026-11-22, in chat): "Go ahead keep this" |
| 3 | round 14's last issue: close this spec; next, a spec for the remaining causes, the undrawn card grid first | **Decided** (2026-11-22, in chat): "Ok close here and move on"; agreed on the page 2026-11-23 |
| 4 | round 14's spot checks: c0196 mixed, c0405 better, c0555 the same | **Decided** (2026-11-23): c0405 and c0555 agreed; c0196 **disagreed**, "minor - if text is in this is just font size matter". A paragraph drawn smaller, its words all in, is minor (`review-criteria.md`, round 14) |

Round 13's 17 spot checks have no answer saved on the issue page.

## The prompt for the next session

> Start spec 0027 on arm D2: the panel's remaining causes, worst page
> first, each reproduced and mended on dev pages first. Spec 0026 is
> closed: issue #49, branch `milestone`, `main` fast-forwarded to it.
> Read `CLAUDE.md`'s READ THIS FIRST, `docs/status.md`,
> `docs/glm-ocr.md`, then spec 0026's "Outcome — the spec" and "Outcome
> — part two (a)", spec 0025's §3a (how the skeleton cuts) and
> `docs/agents/review-criteria.md`.
>
> 1. **Write spec 0027** and its GitHub issue
>    (`docs/agents/issue-tracker.md`), on a branch cut from `milestone`.
>    Its causes are spec 0026's "What is left on the panel", in that
>    order.
> 2. **Prove first**: the replay of `s14-result/` 21 of 21 and
>    `mypy src/`.
> 3. **Cause 1, a grid of cards the page draws no box round** (c0456 on
>    the panel; c0384 on dev). The parser reads it column by column, so
>    the skeleton's cut down wins over the gaps across that part its
>    rows. **Measure first**, offline over the dev pool's recorded
>    regions (`debug/runs/L5-D2-dev/`, no model). Count the parts
>    where a gap across runs through every column while the parser's
>    order goes down a column. Then count how many of those parts are
>    two columns of running text, which must stay columns. Write both
>    numbers into the spec, then decide whether the order may lose to
>    such a gap. Judge it as spec 0026's part two did:
>    - a pool of dev pages that show it, 5 drawn at random (seed
>      recorded), 5 more if unclear;
>    - drawn offline with `tools/d2.py --regions L5-D2-dev --grids`;
>    - harm drawn from the pages the rule touches;
>    - none worse.
> 4. **Then the others, one at a time**, in the spec's order. Each is
>    reproduced on a dev page first, or recorded as not found. A
>    direction that does not work is dropped. Sizes in prose (cause 5)
>    are **minor** by his call on c0196 (`review-criteria.md`, round
>    14): they go last, after structure and words.
> 5. **Stop for his call before any panel run.** When he names it, the
>    run is `tools/batch.py M3-D2-L3 --arm d2 --pages l3` (about 25
>    minutes), judged by eye against `M2-D2-L3`.
>
> Rules: local models only; the vault stays closed, never pass
> `unseal=True`. No panel page in a test or to tune anything, c0001
> and c0002 above all; a fault seen on a panel page is reproduced on a
> dev page first. Today's pipeline stays as it is: the replay of
> `s14-result/` stays 21 of 21. One conversion at a time, nothing
> beside it. Run nothing he has not asked for. Tests minimal: the
> changed files' tests, the replay when shared code moves, `mypy
> src/`; never the full suite. Judge by eye; a number is a pointer to a
> page. Replies concise: what worked or not and why, each change as
> page / before / after; no process lines (tests passing, seeds,
> commits) and nothing he already knows.
