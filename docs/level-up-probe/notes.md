# Probe notes, by eye — 2026-10-24, commit 99110c2, shipped defaults

## payslip — 555 s, 9 Zones, vanished 0
- header: `PAYSLLIP` (misread title) printed above the real `PAYSLIP` — caption read wrong, then echoed (Zone read as pairs). Stage: classify/caption.
- employee details: dotted rules gone; values set beside labels instead of at the column's right edge. Stage: render (pairs layout).
- earnings table: `Gross pay 4,098.08` total row fell out of the table → a separate line under it; the detector's box ends one row early. Deductions kept its Total. Stage: layout.
- summary boxes (Gross / Deductions / Net) lost their frame and the Net pay fill; merged with the year-to-date table into one `table` Zone. Stage: layout.
- year-to-date table: header spread across the page, data row flattened into one line of text. Stage: layout → extract.
- `1.5×` → `1.5x`; email drawn as a blue link the page does not draw. Minor.

## labreport — 497 s, 6 Zones, vanished 3 (1 real)
- `NP-2291` → `NP-229 I` (Gill Sans 1 read as I). Stage: extract. Real loss.
- `109`, `73m2`: superscripts drawn as `sup` split the token; not a loss (scorer artefact).
- patient box: label-over-value fields became label-beside-value; the teal bar drawn twice. Stage: extract/render (pairs as label beside).
- results table: section rows kept (good). In four of the five rows with no flag (WCC, platelets, MCV, creatinine) the result moved one column right into Flag — an empty cell lost/misplaced → the table's meaning changes, invisible to `vanished`. Stage: extract.
- `L` flag drawn black where the page prints it red bold. Stage: looks.

## nutrition — 378 s, 4 Zones, vanished 0, precision 0.895
- the big `230` read as a picture: drawn as an inverted black block at the bottom of the label; `Calories 230` also printed small. Stage: layout/classify (display number as figure).
- the footnote's first line printed twice, the second copy corrupted — `The %s Daily Value (DV) told you…` — invented words. Stage: extract / unclaimed re-read.
- `% Daily Value*` moved from the table's head to under it. Stage: order.
- sub-rows (Saturated Fat, Trans Fat, Dietary Fiber, Total Sugars, Added Sugars) lose their indent. Stage: extract (indent not in the IR).
- the label's thick black bars (10px, 5px) drawn as thin rules; bold carried to whole lines. Stage: looks.
- render 28% taller than the source.

## recipe — 571 s, 14 Zones, vanished 0, tau 0.766, height +44%
- the two columns (ingredients 34% | method) cut into 14 Zones in 10 Bands, interleaving the columns: steps 1 and 5 drawn as bullets with their numbers inline, step 3 as a full-width bullet inside the ingredients list, steps 2 and 4 as plain paragraphs; the big step numbers lost. Stage: layout (no column region found) → classify.
- a truncated duplicate title `METH` beside `METHOD`. Stage: caption.
- chips: PREP / COOK / SERVES lose their chip, only VEGETARIAN keeps one; `SERVES 4` loses its `4` — invisible to `vanished`, a set, since `4` is printed elsewhere. Stage: looks / extract.
- ingredient lists spread down the page in Band rows with large gaps; the tip box's fill spans the page while its text starts at the method column. Stage: layout → render.
- the title bold where the page sets it regular.

## minutes — 449 s, 9 Zones, vanished 1
- the meta grid (two pairs per line: Date | Chair, Time | Minutes): `Chair  Margaret Ellison` lost; `Minutes Daniel Okoro` moved above Date as one bold line. Stage: extract (pairs). Real loss: `Margaret`.
- the action table's row numbers `1`, `2` drawn as superscripts — spec 0019 B2's raised-mark rule misfiring on small table numerals. Stage: raised (a hand-set rule).
- `Next meeting:` label loses its bold and is set over its value instead of inline. Stage: extract/render (pairs).
- numbered item bodies lose their hanging indent; the decision box keeps its border, loses its fill. Minor.

## flyer — 292 s, 8 Zones, vanished 0, precision 0.975
- the orange top band read as text: `The` printed twice in it — the ticket's halo-Zone fault (spec 0016 4a, dropped) on an unseen page. Stage: layout (a fill's edge as a Zone) → extract.
- the `Free entry · Family friendly` pill drawn as a full-width orange band. Stage: looks/render (a button is not a band).
- a stray bullet `•` before the URL — an invented list marker. Stage: classify/render.
- `wood-`, `Sri Lankan`, `4 pm` set in italics the page does not use. Stage: looks.
- the serif display headline drawn in a sans face, its two lines far apart; letter-spaced kicker and heads lose their tracking. Stage: looks.
- three columns, colours and reading order all kept.

## quiz — 838 s, 28 Zones, vanished 0, precision 0.979
- the fill-in table's empty cells merged into spans: Potassium spans Metal+Observation, `Fizzes steadily` spans Observation+Reactivity, Copper spans all three — spec 0019 B1's span rule misfiring where the page leaves cells empty on purpose. Stage: spans (a hand-set rule).
- the equation `___ H₂ + O₂ → ___ H₂O` drawn as `H2 H2 / O2 O2 / H2O`: blanks, `+` and `→` lost, molecules doubled, subscripts lost. Stage: extract (no formula reading).
- the answer circles: one read as the letter `O` (`O A Oxygen`), two drawn as bullets, one dropped. Stage: extract / marks (an option's tick circle is not a Mark).
- kept: the header rule, the Name/Class/Date fill-in lines, the instructions box, marks right-aligned, the ruled answer lines.
- 28 Zones — one per question line and option line — hence 14 minutes. Stage: layout granularity.

## datasheet — 531 s, 14 Zones, vanished 1 (0 real), tau 0.833, height +37%
- the Key features list beside the spec table cut into one Zone per line; only the first item stays beside the table, the other five are pushed under it, leaving a hole beside the table and breaking reading order — the recipe's fault again: a column of short lines beside a taller block. Stage: layout (no column region; a Zone per line).
- the green ticks drawn as bullets. Stage: looks (a symbol list marker).
- part numbers `AQ7-MB-W` → `AQ7–MB–w`: hyphens to en dashes, a capital to lower case (the scorer casefolds, so it does not count it). Stage: extract.
- `m3`: the superscript split by `sup` (scorer artefact, not a loss).
- kept well: the header band, the spec table with its three group rows and their fill, the ordering table.
- `VERIDIAN` clipped at the band's right edge; `PM2.5 range` bold where the page is regular. Minor.

## contract — 430 s, 10 Zones, vanished 0 (but a heading lost)
- the two signature columns (For the Client | For the Provider, three ruled lines each) collapsed into one: `For the Provider` and its column gone, every signature rule gone, `Date` and `Name and title` printed over each other. `vanished` sees none of it — each word is printed elsewhere on the page. Stage: layout (one pairs Zone over both columns) → extract → render.
- clause numbering: hanging indents lost; 1.2, 1.3, (a), (b) drawn as bullets while 1.1, 2.1, 3.1 are paragraphs. Stage: classify (list vs prose per Zone).
- bold defined terms and party names drawn plain; curly quotes straightened; `3.2 …` drawn at heading size. Stage: looks.
- the agreement number and date drawn as blue links the page does not draw. Stage: inline runs.
- the initials box loses its frame and its `/ ______`. Stage: looks/extract.

## email — 386 s, vanished 0
- the two attachment chips lose their borders and collide: the green `XLS` badge sits on `Door_`, the `PDF` badge shrinks to a red square. Stage: looks/render (chips).
- `RIBA` bold where the page sets it regular. Minor.
- kept: the header bar, subject, From/To/Cc grid with the date right, the list, the signature, the quoted reply with its rule.

---

# Calibration: six of the tuned 21, drawn at random (seed 20261024), judged the same way, same sitting
S14 re-derived today at 99110c2 (`debug/runs/G0-s14-rederived`); sheets in `tuned-sample/`.
- form_0007: no structural fault; one footer word misread (`Castletown`).
- invoice_0001: no fault.
- receipt_0010: no structural fault; the AID one zero short; bold where the page is regular.
- sample_table_0003: no fault.
- statement_0006: no fault.
- timetable_0019: no structural fault; tints by row, legend without swatches (looks).
**Structural faults: 0 of 6 tuned pages, 9 of 10 unseen pages** (all but the email).

# GLM-OCR taste test (glm-ocr:q8_0, Ollama, 100% GPU, 2.5 GB loaded)
- whole page, "Text Recognition:": 4.0–10.3 s a page (mean 7.5 s). Real losses: the quiz's `Total: ___ / 10` line and the email's top bar (`Inbox · 3 of 214`, the account address); one misread (`POE` → `P0E`). Plain lines, no structure.
- today's Zones re-read, "Table Recognition:" on table Zones: HTML tables with `thead` and `colspan` section rows; the quiz's equation as correct LaTeX. But where a Zone holds a table plus other content (the lab report's patient box sits in the table's Zone), the table prompt returns only the table: 22 words dropped. The lab report's Result/Flag columns confuse it too (`128 L` in the Flag column).
