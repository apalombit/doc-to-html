# The brief — how to write a corpus page

Every page of the corpus is written from a **card** and this brief, which
every writer is given word for word (spec 0020 §B). Read it to the end
before writing anything.

## What a page is for

The page's **picture** is shown to a document converter that sees nothing
else. The page's **HTML** is the ground truth the converter is marked
against: every word, every line break and every structure (table, list,
heading, label and value) is read off the HTML by a browser. So two
things must both hold:

1. **It looks like a real document of its kind**, from the hand of its
   style family: a receipt that looks printed by a till, a tax form that
   looks issued by an office, a menu that looks set by a restaurant.
2. **The HTML is honest about the picture.** Every word a reader sees is
   a text node in the HTML, and every text node is a word a reader sees.

A validator (§ The loop) checks the second. You check the first by
looking at your page's screenshot.

## The file

- One self-contained file: `corpus/pages/<id>.html`, `<id>` being the
  card's id.
- It starts `<!doctype html>`. It has `<meta charset="utf-8">`, and
  `<html lang="…">` set to the card's locale (`en-GB`, `it-IT`, …).
- Inline `<style>` only, in the head or in `style` attributes. **No
  JavaScript.**
- **No external resources of any kind.** No `http(s)` URL in any
  attribute (`src`, `href`, …). No `<link>`, `@import`, `@font-face` or
  web font. No `url()` except a `data:` URI. A URL printed as text on the
  page is fine.
- Laid out for **exactly the card's width**: nothing wider, no horizontal
  overflow. A document may sit on a plain ground narrower than the page:
  a till slip, a ticket, a card. The page itself is the card's width.
- **At most 2400 px tall** at that width: one page. Most pages land
  between 700 and 1800 px; a sparse one can be shorter.
- **The picture ends where `<body>` ends.** A last child's bottom margin
  collapses out of the body and is cut off, so put the space round the
  document in the body's `padding`.
- **The layout must not depend on the window**: no `vh`, `vmin`, `vmax`
  (or `dvh`, `svh`, `lvh`) and no `position: fixed` or `sticky`.

## Words a reader sees are text nodes

- **Never generate visible text with CSS**: no `::before` or `::after`
  with `content`, no counters, no `<ol>` that numbers itself, no
  `list-style-type` other than `disc`, `circle`, `square` or `none`.
- **Write numbers and marks yourself.** Step numbers, clause numbers
  (`1.1`, `(a)`), footnote marks (`¹`, `*`), ticks and crosses (`✓` `✗`),
  tick boxes (`☐` `☑` `☒`), stars, arrows, bullets that are not a plain
  disc: all of them are characters in the HTML.
- An `<ol>` is fine, with `list-style: none` and its numbers written in
  each `<li>`. A `<ul>` may keep its browser-drawn plain bullets.
- **No `<q>`**: it draws its quote marks with CSS. Type the quote marks.
- **No `hyphens: auto`**: the browser's hyphen is not in the text.
- **No form controls**: no `<input>`, `<select>`, `<textarea>`,
  `<progress>`, `<meter>`, `<details>`. Draw a field as a bordered box
  and write what is in it as text. Draw a tick box as `☐` or `☑`.
- **Every word in the DOM is visible**: nothing clipped, hidden, scrolled
  away, off the page, behind something else, or the colour of its ground.
  Nothing smaller than 8 px; fine print is 8–10 px.
- `text-transform`, `letter-spacing` and `font-variant: small-caps` are
  fine: the words stay the same.
- **A line a reader reads as one is one block.** A numbered heading
  (`1.2 Les prestations`), a numbered clause or list item, or an entry in
  a table of contents keeps its number and its text in one element: give
  the number an inline `<span>` (`display: inline-block; width: …` for a
  hanging column). Making them two flex or grid items, or placing either
  with `position: absolute`, turns them into two blocks, and the scorer
  groups text by its block. A label and its value set as two cells of a
  table or grid are two blocks on purpose, and that is fine.

## Figures

- A figure is an inline `<svg>` with **no `<text>` in it**, or an
  `<img>` whose `src` is a `data:` URI.
- **Words never go inside a figure.** A chart's title, axis labels and
  legend are HTML text beside or around the `<svg>`, positioned over it
  if need be. A logo is shapes; its wordmark, if it has one, is HTML text
  beside it.
- Inside a `<figure>`, text may only be in its `<figcaption>`.
- Real brand logos never; draw an invented mark.
- A barcode is a row of `<rect>`s; a QR code a grid of them; a signature
  one or two `<path>`s with a stroke; a photo-like picture shapes and
  gradients (a landscape, a product silhouette, a portrait outline).
  Figures are minor for now: plausible, not perfect.

## Faces

Name only these faces. The face your HTML declares must be the face the
picture shows, and the validator refuses any other.

<!-- faces:begin -->
- **serif:** American Typewriter, Baskerville, Baskervville, Big Caslon, Bodoni 72, Charter, Cochin, Cormorant Garamond, Didot, Georgia, Hoefler Text, Libre Baskerville, Lora, PT Serif, PT Serif Caption, Palatino, Rockwell, STIX Two Text, Source Serif Variable, Times, Times New Roman
- **sans:** Arial, Arial Narrow, Arial Rounded MT Bold, Avenir, Avenir Next, Avenir Next Condensed, Comfortaa, Galvji, Geneva, Gill Sans, Helvetica, Helvetica Neue, Hind, Lucida Grande, Microsoft Sans Serif, Open Sans, Optima, PT Sans, PT Sans Caption, PT Sans Narrow, Skia, Source Sans Variable, Tahoma, Trebuchet MS, Ubuntu, Verdana
- **mono:** Andale Mono, Courier, Courier New, Menlo, Monaco, PT Mono, Source Code Variable
- **script:** Apple Chancery, Bradley Hand, Brush Script MT, Caveat, Chalkboard SE, Marker Felt, Noteworthy, Savoye LET, SignPainter, Snell Roundhand, Zapfino
- **display:** Arial Black, Chalkduster, Cinzel, Copperplate, DIN Condensed, Herculanum, Impact, Luminari, Oswald, Papyrus, Phosphate, Playfair Display, Trattatello
<!-- faces:end -->

- A font stack **leads with a face on this list**, or with `serif`,
  `sans-serif`, `monospace` or `cursive`. It may end with a generic. It
  never names a face that is not on the list, not even as a fallback:
  no Inter, Roboto, Segoe UI, Calibri, Cambria, Consolas, system-ui or
  -apple-system.
- **The card's main type class sets most of the page's words**: `type.sans`
  means most characters are in a sans face. Script and display faces are
  for titles, names and signatures, never a body.
- **`type.weights`** (three weights or more) needs a face with three real
  weights or more: American Typewriter, Avenir, Avenir Next, Avenir Next
  Condensed, Baskerville, Charter, Comfortaa, Gill Sans, Helvetica,
  Helvetica Neue, Hind, Open Sans, Optima, STIX Two Text, Skia, Source
  Sans Variable, Source Serif Variable, Ubuntu. Use `font-weight` values
  such as 300, 400, 600, 700 and 800.
- Use the faces' variety. Two serif pages need not both be Georgia.

## The card

A card looks like this:

```json
{"id": "c0137", "family": "reports", "kind": "clinical visit note",
 "arrangement": "arr.two_columns", "type": "type.sans",
 "features": ["kv.over", "table.ruled", "table.empty_cells", "text.supsub"],
 "style": "clinical-plain", "language": "it", "locale": "it-IT",
 "width": 820, "density": "dense",
 "particulars": {"date": "2021-03-11",
                 "people": ["Giulia Ricci", "Stefano Fontana", "Anna Gatti"],
                 "places": ["Lecce", "Matera"], "name_words": ["Garnet", "Linnet"]}}
```

- **kind**: what document it is. Make it unmistakably one.
- **arrangement**: how the page is laid out. Exactly one.
- **type**: the class of the face that sets most of the words.
- **features**: each must be **visibly present**. Add others only where
  they come naturally to the kind; most documents have dates, and an
  invoice has totals.
- **style**: whose hand it is (below). It decides the look and the HTML
  habits.
- **width**: the page's width in CSS pixels.
- **density**: sparse, medium or dense (below).
- **locale**: the language and its conventions (below).
- **particulars**: what to fill the page with, so that no two pages
  share their names and dates (below, under Content).

### Features

<!-- features:begin -->
| id | what it means on the page |
|---|---|
| `arr.one_column` | one column of content from top to bottom |
| `arr.two_columns` | two columns of running content side by side |
| `arr.three_columns` | three columns of running content side by side |
| `arr.sidebar` | a narrow side column beside a wide main column |
| `arr.cards_grid` | a grid of repeated cards or tiles, at least two by two |
| `arr.panels_side_by_side` | two or three framed panels side by side, each its own block |
| `arr.centred` | everything centred on a vertical axis |
| `type.serif` | the body is set in a serif face |
| `type.sans` | the body is set in a sans face |
| `type.mono` | the body is set in a monospaced face |
| `table.ruled` | a table ruled between its rows and columns |
| `table.spanning` | a cell that spans two or more columns or rows (colspan or rowspan) |
| `table.section_rows` | a full-width row inside a table that names the rows below it |
| `table.totals` | summary rows (subtotal, tax, total) at a table's foot |
| `table.empty_cells` | cells left empty on purpose (a blank result, an unfilled box) |
| `table.zebra` | alternate rows shaded |
| `table.subrows` | indented sub-rows under a parent row |
| `table.long` | a table of 25 rows or more |
| `kv.inline` | label and value on one line (Date: 07/03/2024) |
| `kv.over` | a small label printed over its value |
| `kv.two_per_line` | two label-value pairs on one line |
| `kv.leaders` | leader dots between a label and its value |
| `kv.boxed` | values in drawn boxes or fields |
| `list.bullets` | a bulleted list |
| `list.numbers` | a numbered list, numbers written in the HTML |
| `list.nested` | a list inside a list |
| `list.ticks` | ticks and crosses (✓ ✗) or tick boxes (☐ ☑) beside items |
| `list.clauses` | hanging clause numbers (1.1, 1.2, (a), (b)) with the text indented past them |
| `list.big_steps` | large step numbers beside each step |
| `text.justified` | justified paragraphs |
| `text.footnotes` | footnote marks in the text and the notes at the foot |
| `text.supsub` | superscripts or subscripts (m², CO₂, 1st, a reference mark) |
| `text.formula` | a formula or equation set on its own line |
| `text.quote` | a quotation set apart (a pull quote or a block quote) |
| `text.drop_cap` | a drop cap at a paragraph's start |
| `type.display` | a display face for a title or masthead |
| `type.script` | a script or handwritten face somewhere on the page |
| `type.small_caps` | small capitals for labels or headings |
| `type.weights` | three or more weights of one family on the page |
| `look.accent` | one accent colour carrying meaning (headings, flags, totals) |
| `look.dark_ground` | the page, or most of it, light type on a dark ground |
| `look.bands` | full-width bands of fill (a header bar, shaded section strips) |
| `look.chips` | small rounded chips or badges with a fill |
| `look.buttons` | button-like boxes |
| `look.rules` | dashed, dotted or double rules |
| `fig.logo` | a logo drawn as shapes, its wordmark if any as HTML text beside it |
| `fig.chart` | a chart, its title and labels as HTML text outside the figure |
| `fig.code` | a barcode or QR code |
| `fig.signature` | a handwritten signature drawn as a path |
| `fig.photo` | a photo-like picture |
| `fig.icons` | small icons beside text |
| `fmt.eu_numbers` | numbers in the language's own format (1.234,56 or 1 234,56) |
| `fmt.dates` | dates in the language's format (07/03/2024, 7 marzo 2024) |
| `fmt.currency` | amounts with a currency sign or code |
<!-- features:end -->

**Some features need the real element**, because the ground truth is
derived from it:
- any `table.*` feature: a real `<table>`, and for `table.spanning` a real
  `colspan` or `rowspan`. An empty cell is a `<td>` with nothing in it;
- `list.bullets`: a `<ul>`. `list.numbers`: an `<ol>`, numbers written.
  `list.nested`: a list inside a list's `<li>`;
- `text.justified`: `text-align: justify` on a paragraph of two lines or
  more. `text.supsub`: `<sup>` or `<sub>`. `text.quote`: a `<blockquote>`;
- `text.drop_cap`: a large first letter, floated and enlarged, by a
  `<span>` round it or by `::first-letter`. The letter stays in the text;
- `look.dark_ground`: most of the picture dark;
- any `fig.*`: an `<svg>` or a `data:` `<img>`.

### Style families — whose hand it is

| style | looks | HTML habits |
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

What the three loose families mean in practice:
- **`legacy-table`**: the layout is built from nested `<table>`s with
  `border`, `cellpadding`, `cellspacing`, `bgcolor` and `width`
  attributes, perhaps `<font face="Verdana" size="2">`. It looks like an
  intranet page from 2003.
- **`utility-classes`**: a `<style>` block defines short utility classes
  (`.p-4 .px-2 .text-sm .font-semibold .grid .grid-cols-3 .gap-2
  .text-right .border-b .bg-slate-50 .rounded`). The markup is mostly
  `<div>`s carrying several of them each, as a framework page looks with
  its CSS inlined.
- **`print-export`**: it looks exported from a word processor. Paragraphs
  carry classes such as `MsoNormal`, spans carry inline `style` with
  sizes in `pt`, and spacing is made with margins and `&nbsp;` runs.

Even these three use a real `<table>` and a real list where the card has a
`table.*` or list feature. Their looseness is everywhere else.

### Density

- **sparse**: a few blocks with generous space: a flyer, an invitation.
- **medium**: a typical page of its kind.
- **dense**: packed: small type (10–12 px), many rows or fields, little
  space.

**The words a density asks for.** The validator counts the page's words
(numbers count, each run of letters or digits is one) and fails a page
below its floor: **400 words per 1000 px of width for dense, 220 for
medium**, none for sparse. A certificate, ticket, invitation, membership
card, slide, flyer, prescription, calendar or nutrition label needs half
that. So a dense page 820 px wide holds at least 328 words, and a medium
receipt 500 px wide at least 110. That is a floor, not the aim: a real
dense statement or form is often twice it. Reach it with what a real
document of the kind carries (more rows, more fields, the small print,
the terms, the second address, the reference numbers), never with
filler or repetition.

### Kinds that need a word

**A fragment** (family `fragments`) is not a whole page. It is one part
of a document at its own size, as if cut from a larger one or exported
on its own: a table with its title and notes, a chart with its caption,
a map with its labels, one section of a form, a diagram with its
callouts. The picture is the fragment and little else: a few pixels of
margin, no page header, footer or letterhead unless the part itself
carries one. Its height is what it needs, often 200–700 px.

- **standalone table**: a table with its title, column heads, units and
  a source or note line; pasted from a report, a spreadsheet or a
  website.
- **chart with caption**: a chart drawn in an `<svg>` (bars, lines,
  pie), with its title, axis labels, legend, caption and source as HTML
  text around it.
- **annotated map**: a simple map drawn in an `<svg>` (streets, a
  river, a park, numbered markers) with its labels, a legend, a scale and
  a north arrow written as HTML text.
- **form section**: one panel of a form, such as applicant details, a
  declaration, an office-use box or a payment block.
- **diagram with callouts**: a technical drawing in an `<svg>` (a
  device, a part, a wiring layout) with numbered callouts and a parts or
  key list beside or below it.

**Labels over a drawing.** A map's street names or a diagram's callout
numbers sit **over** the drawing, so they cannot be inside the `<svg>`
(§ Figures). Put the `<svg>` in a `position: relative` box and each
label in a positioned `<span>` beside it in the same box, outside the
`<svg>` and outside any `<figure>`. Give each label a ground it reads
on: a halo of `text-shadow` or a small white box.

Two kinds are whole pages and new:
- **book page** (`publishing`): a page from a non-fiction book, with a
  running head, a folio (the page number), body text set as a book sets
  it, and a chart or figure with its numbered caption.
- **technical printout** (`reference`): pages printed from a technical
  manual or a system's documentation, such as parameter tables, wiring or
  pin tables, numbered procedures, warnings, a revision line and
  "page x of y". Plain and functional.

### Locales

| locale | dates | numbers | money |
|---|---|---|---|
| `en-GB` | 07/03/2024, 7 March 2024 | 1,234.56 | £1,234.56 (or € where it fits) |
| `en-US` | 03/07/2024, March 7, 2024 | 1,234.56 | $1,234.56 |
| `it-IT` | 07/03/2024, 7 marzo 2024 | 1.234,56 | 1.234,56 € or € 1.234,56 |
| `fr-FR` | 07/03/2024, 7 mars 2024 | 1 234,56 | 1 234,56 € |
| `es-ES` | 07/03/2024, 7 de marzo de 2024 | 1.234,56 | 1.234,56 € |
| `pt-PT` | 07/03/2024, 7 de março de 2024 | 1 234,56 | 1 234,56 € |
| `pt-BR` | 07/03/2024, 7 de março de 2024 | 1.234,56 | R$ 1.234,56 |

The dates in this table show the **format** only. A page's own date is
its card's `particulars.date`.

- **Write the whole page in its language**, the way a native document of
  that kind is written: its labels, its legal lines, its abbreviations
  (`IVA`, `TVA`, `NIF`, `CPF`, `P.IVA`, `SIRET`). Not a translation of an
  English page.
- Its typography too: French `« guillemets »` with a space before `: ; ?
  !`; Spanish `¿` and `¡`; Italian and Portuguese `«»` or `“”`.
- English pages are British or American as the locale says, in spelling
  and in conventions.

## Content

- **Realistic for the kind and the language**: what a real one says, in
  the order and density a real one says it. Fictional but plausible:
  people, companies, addresses, products, numbers.
- **Totals add up, dates agree, ages match birth dates**, and a tax rate
  is the rate the totals were computed with.
- **Use the card's particulars.**
  - `date` is the document's own date: issued, printed, the visit, the
    statement. Every other date on the page agrees with it: a due date
    after it, a birth date and a career before it, a schedule around it.
  - `people` are the people the document names: the customer, the
    patient, the signatory, the author. Add more only if the kind needs
    them, invented in the same locale.
  - `places` are the towns it is set in.
  - `name_words` are seeds for the names the page needs: the
    organisation's, a brand's, a product's, a building's. Use one, both
    or neither, in the form a real one of this kind and locale takes: a
    word and what it does (*Linnet Dental*, *Verdigris Analytics*), a
    surname or a family (*Hendricks Plumbing*, *Rossi & Figli*), a town
    (*Ipswich Joinery*), initials (*KBV Logistik*), a product line (*the
    Cinder 40 kettle*). **Do not join the two words into one name with
    "&"**: a third of the first 150 pages did, and it reads as one
    author. Translate or adapt them for a page not in English.
  - Never use Okafor, Whitcombe, Harbour, Harbor, Fenwick, Calloway,
    Marchetti or Marrowfield: earlier pages wore them out.
- **No lorem ipsum.** No real person, company, brand, product or logo.
  Real cities and real generic things are fine (Bristol, Lyon, paracetamol
  500 mg, an oak table).
- **No real organisation issues the document.** A tax form is issued by
  an invented revenue office, not the IRS or HMRC; a hospital, a bank, a
  school, a ministry or a council is invented too. Do not reuse a real
  form's number or title (`1040`, `P60`, `Cerfa 12345`). Generic systems
  and the fields they give a document are fine: an NHS number, a VAT or
  P.IVA number, an IBAN.
- Phone numbers, account numbers, IBANs and tax or ID numbers are invented
  and need not validate. Web and e-mail addresses use invented names, or
  `example.com`, `example.org` and `example.net`.
- **Clinical pages** read as a clinician would write them: structured
  fields, abbreviations, doses and units, generic drug names, reference
  ranges. Plausible, invented patients.
- **Structure**: use the HTML that fits what is drawn. A table for a
  table, lists for lists, headings for headings, a `<dl>` or a two-cell
  row for label–value pairs, in the semantic style families. The loose
  ones build as their habits say.

## Look

- Make it look like a document of its kind **from its style family's
  hand**. Two invoices from two style families must not look alike.
- Choose layout, sizes, colours and faces afresh for every card. **Never
  reuse your own previous page as a template**, and do not open other
  corpus pages or `example/` for ideas. Write from the card and this
  brief.
- Colour: most documents are mostly black on white, with one or two
  colours. `look.accent` makes one colour carry meaning.
  `look.dark_ground` makes most of the page dark.
- Leave the space a real document leaves. A dense page is packed, and a
  sparse one is not stretched to look full.

## The loop

For each card:

1. Write `corpus/pages/<id>.html`.
2. Run the validator from the repository root:
   `.venv/bin/python tools/corpus_check.py <id>`
3. **Look at the screenshot** with your image reader. It is at
   `corpus/pages/<id>.png` when the page passes, and at
   `debug/corpus-check/<id>.png` when it fails. Ask:
   - does it look like a real document of its kind?
   - is every feature on the card visible?
   - does any text overlap other text, or run out of its box?
   - is anything accidentally empty or crowded?
4. Fix what the validator names and what you saw, and run it again.
   **A page counts only once it passes and looks right.**

What the validator's failures mean:

| check | what it caught | usual fix |
|---|---|---|
| `renders` | taller than 2400 px, or no text | tighten, or drop content |
| `own_picture` | two shoots differ | something animates or depends on timing; remove it |
| `fits` | clipped or overflowing content, text off the page, the wrong width, window-dependent layout | give boxes room, `overflow: visible`, fix widths |
| `ink` | a word with no ink under it, or type under 7 px | contrast, z-order, size |
| `self_contained` | an external resource, a face not on the list, a missing doctype, charset or `lang` | |
| `figures` | words inside an `<svg>`, `<canvas>` or `<figure>` | move the words out into HTML |
| `generated` | text drawn by CSS, a self-numbering list, a form control, automatic hyphens | write the text in the HTML |
| `features` | a card feature the page does not show, or the wrong main face | add it with the element the feature needs |
| `language` | the page does not read as the card's language | write it in that language |
| `distinct` | too like a page already in the corpus | write a different page |

**Edit only your cards' HTML files.** Do not touch other pages, the
cards, the tools or anything else in the repository.

## What to report

One line per card:

```
c0137  PASS  3 runs  clinical visit note, Italian, two columns of fields
c0142  FAIL  5 runs  language: reads as en (explain what blocked it)
```

Then anything the card asked for that you could not make look right, and
why. Five validator runs per card at most; a card that still fails is
reported as FAIL with its HTML left in place.
