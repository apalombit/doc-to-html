# Review criteria — what matters in a conversion

**Agreed with Alessandro on 2026-10-24**, in five rounds of questions held
after the level-up review ([`../level-up.md`](../level-up.md) §4.9). These
are the criteria the review judges by. The visual-review skill
([`visual-review.md`](visual-review.md)) takes them up when it is evolved,
in L2, after the corpus is built (his order).

## The principle

1. **The render must look like the page.** That is the main point.
2. **Among HTML that looks the same, pick the simplest, most fitting
   structure**: a table for a table, a list for steps, headings for
   headings. A look-alike built the wrong way is a minor fault.
3. **Never guess.** Where two independent readers disagree, the disputed
   word becomes a gap: a hatched box tagged "unread" on the page, with the
   reason in the HTML and in the run report. The cause can then be found
   and fixed.
4. **The output is a fixed page**, like print, at the source's width.
   Every line breaks where the page breaks it, by explicit line ends, with
   type sized so each line fits its box.

## Severity

| | major | minor |
|---|---|---|
| **words and numbers** | a word or number lost, invented, changed or merged (`NP-229 I` for `NP-2291`, `METH`, `gsalt`) | a mark drawn as a look-alike, the letters and the meaning unchanged: ✕ as the letter X, ’ as ', – as -; a subscript or superscript drawn inline after a mark (`H_2015` for H₂₀₁₅) |
| **structure** | a cell in the wrong row or column; a label printed over its value flattened onto one line; numbered steps drawn as bullets, or a hanging number lost; content drawn under the wrong heading, in another column, or across the column set beside it (the recipe's step 3 drawn between the ingredients) | the right look built from the wrong HTML structure. Groups set side by side on the page and in the render are no fault, however the HTML orders them; a group mostly lost is a words fault, not an order one |
| **layout** | a block printed beside another drawn under it (a label torn from its amount, two boxes stacked, a note off its title's line); text drawn over text; a line joined or split where it had room; page height off by more than 10% | a paragraph re-wrapped by its column's width; alignment changed within the line's own column or cell (right-aligned numbers drawn left, a value further from its label, a centred line drawn flush left, justified drawn ragged, a first-line indent lost); page height off by up to 10% |
| **type** | the wrong font class where it changes the kind of text: a monospace or a script lost or added; sizes out of proportion, the line's own size changed by more than 10%; bold printed regular | serif drawn sans or sans drawn serif; italics; letterspacing; small caps |
| **looks** | the page drawn on the wrong ground (dark for light); text too faint to read on its ground; a colour that carries meaning lost (red H/L flags printed grey, an orange frame drawn grey); a fill or band missing, added or drawn another shape (a pill drawn as a band); a frame missing round a box that holds content (card, panel, field); a rule missing that merges cells | a colour in the right family but off; a heading's or a title's accent colour drawn neutral (a lone number's or letter's stays major); chips and buttons drawn as plain text; a framed box drawn as a filled box about as wide (a card still reads as a card); a legend's swatches missing |
| **figures** | — | any figure missing or imperfect, for now: logos, barcodes, icons, signatures, photos |

After words, numbers and the overall layout, **structure comes first**.

Three of these calls were Claude's inference, confirmed by Alessandro the
same day: a cell in the wrong row or column, merged or split words, and a
page drawn on the wrong ground are all major.

**A look-alike mark is minor — Alessandro, 2026-11-01** (spec 0021's
issue N). A cross drawn as the letter X in a box, a curly apostrophe drawn
straight, an en dash drawn as a hyphen: the same letters, the same
meaning. A mark whose meaning changes stays major: an empty box drawn
crossed, a tick lost.

**Rounds 1 to 4 — Alessandro, 2026-11-07** (spec 0021, step 6; 44
issues, one at a time, `review-issues.json`). Where the checks and the
eye disagreed, the eye's rule was taken:

- *Moved, not shifted.* An alignment change is minor while the line
  stays in its column or cell ("a spacing issue… all text is there");
  it is major only when the line is drawn in another place — off the
  row it shares with another block. That is its own fault, `beside`.
- *Columns as the eye reads them.* Two groups set side by side on the
  page and in the render are not interleaved, whatever the HTML's
  order; an item drawn in the other column is under another heading.
- *A break the column made is not a break the page set.* A paragraph
  re-wrapped by a wider column is minor; a line joined or split where it
  had room stays major.
- *A size is judged by the line's own size*: under 10% changed, no
  reader sees it.
- *Serif and sans read the same*; a monospace or a script does not.
- *A missing rule that merges cells is major* (c0208, against Claude's
  proposed minor): the table reads wrong.
- *A colour that marks something is meaning*: an order number printed
  red, a card framed orange.

**Round 7 — Alessandro, 2026-11-09** (spec 0022, L3's review; 15
issues, all agreed):

- *What is not drawn is not judged for its look.* A table or a block
  mostly lost is a words fault; its structure, size and weight are not
  judged from a few of its words matched elsewhere (c0300's PG7).
- *A drop cap and the rest of its word are one word*; the drop cap
  drawn in the line is a minor (c0334's 'N' + 'otice').
- *Printed beside a heading is not under it* (c0476's opening hours),
  and a line the page does not print as a heading heads nothing (c0431).
- *A line in its place is not moved*: what c0575's line lost is its bold
  and its colour.
- *Major, though no check raises them*: a block drawn unreadable (a
  column a pixel wide, a word at 0.30 of the body); an accent word drawn
  as a link (an address the page prints plain, drawn as a link, stays
  minor); a chart drawn as loose numbers; a card's fill split into one
  box per Zone.

**Round 9 — Alessandro, 2026-11-09** (spec 0023, D2's review; 11
issues on the calls and P2's question, all agreed):

- *A look-alike mark, checked as one*: √ ✓ ✔, × ✗ ✕ and □ ☐ ▢ are one
  mark each; drawn as another of its set it is a minor "mark changed",
  never a mark lost plus a mark invented (`checks.ALIKE`, pinned on
  c0068). A tick lost outright stays major.
- *A drawn box written as □ is not invented* when the page draws the
  box (c0074); a box lost stays major.
- *A heading on a band is on the band's ground*, not its parents'
  (c0082); *two blocks drawn side by side as printed are not
  interleaved* (c0243). Both rejected as called; the checks are not
  changed for one page.
- *Major, new kinds*: a label parted from its value (labels on one line,
  values on the next, c0515); a formula drawn as its LaTeX source
  (c0382); a full-width block drawn in a lane (c0523); a colour added (a
  black paragraph drawn red, c0387). Markup drawn as text (`4^{1}$`,
  c0405) is a mark invented, major.
- *Kept major on his spot checks*: a form read only to its first header
  rows (c0196); bold header cells drawn regular (c0300).

## Deciding

- **Net gain ships.** A change that makes more pages better than worse
  ships, and that holds for content too. Every worse page is named and
  goes next in line. This retires the T1 ratchet as a gate; it has been
  suspended since spec 0011. The `vanished` list stays a pointer to pages
  to open.
- **Ranking what to fix next**: majors first, then the biggest visible
  gain for the effort, judged by Claude with the reasoning shown.

## Process

- **Claude is the judge**, with the visual-review skill. No local model.
- **Alessandro spot-checks** every page called worse, plus two at random.
- **Each review is one private page**: the ranked fault classes on top,
  each with an example sheet, then every page with its calls. He ticks
  agree or disagree and adds a note. His calls are saved and read back to
  calibrate, and every disagreement changes the checklist, re-tested on
  all past calls.

## What the criteria change in the converter (queued, not yet done)

| criterion | what changes | today |
|---|---|---|
| every line as printed | explicit line ends in the render, type sized to fit | Phase A1 joined printed lines into flowing paragraphs |
| never guess | a disputed word drawn as a hatched "unread" box | spec 0019 D2 draws a disputed cell plain |
| net gain, content included | the report names a lost word; it does not block | the T1 ratchet, suspended as a gate since spec 0011 |

## What the skill must change (L2)

- the seven axes become faults tagged by feature (`level-up.md` §4.7,
  table 2) and by stage, with the severities above;
- the exact checks run first, from the source HTML;
- dense pages get zoomed tiles, and a highlight shows where two renders
  differ;
- the ranked roll-up and the page with agree buttons;
- `owner` and the rules about deferred faults are retired;
- `numbers.md`'s table header is fixed: an operator-precedence slip in
  `review._numbers_md`.
