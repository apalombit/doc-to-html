# `l2-dev/` — seventeen of dev's renders, the input to the check tests

Spec 0021's review of dev (2026-11-01) overturned the exact checks on
some pages. Each fix to a check is pinned on the page that showed the
fault, and the page's true faults are pinned beside it. These are the
renders those tests read: `tests/test_checks.py`, classes
`TestWhatTheReviewOfDevRejected` and, from Alessandro's review rounds of
2026-11-07 (`docs/agents/review-issues.json`), `TestWhatTheRoundsDecided`.

| file | what it pins |
|---|---|
| `c0550.html` | T: the exploded drawing's callouts 1, 2, 4 and 5 and the Cinder logo are drawn in a figure's pixels, a minor. The nomenclature's 1 and 4, read as bullets, stay lost |
| `c0208.html` | I: the header's right block and the patient box's right half are drawn side by side as printed, interleaved only in the render's HTML, a minor. Nothing is under another heading |
| `c0236.html` | I: the copies of the medication list drawn in the Plan column stay under another heading, a major. 'Wt 214 lb' and 'SpO2 97%', drawn in the Vitals column as printed, do not |
| `c0486.html` | A: 'Margaret Ellison', a short line ended by a break in a justified block, is set left as printed. The job title drawn right stays |
| `c0492.html` | A: the two names, centred in their halves on both, are not read as set left. 'ST-22-0417', drawn left of where the page sets it flush right, stays |
| `c0126.html` | P: the top rule, drawn by a separator above the table, frames it. '2020' read '2028' stays |
| `c0309.html` | P: the totals drawn as a table of their own; the rule under Repas is the main table's foot. The steps drawn as bullets stay |
| `c0548.html` | B1: the menu, drawn as four items on its row at the top right, keeps its place |
| `c0600.html` | D2: the note printed on 'Booking slip''s line, drawn under it, a major; the dates' alignment a minor |
| `c0029.html` | B1, D2: answers drawn beside their questions, a minor; the six drawn under all the questions, a major |
| `c0363.html` | B3: a paragraph re-wrapped by its wider column, a minor |
| `c0246.html` | B3: 'Diagnosi:' drawn over its text and the fields run onto one line stay major |
| `c0576.html` | B5: H₂₀₁₅ drawn `H_2015`, one minor mark changed |
| `c0345.html` | C1: 'Camila Park', signature and name, each compared with its own copy; the section numbers drawn regular stay |
| `c0221.html` | C2: three columns kept, no interleaving; item (a) drawn in section 3's column stays |
| `c0166.html` | D1: the receipt's labels drawn over their values |
| `c0187.html` | D2: Year to date and Time off, side by side, drawn stacked |

## Provenance

- Copied byte for byte from `debug/runs/<run>/dump/qwen3-vl_4b/<page>/document.html`,
  qwen3-vl:4b: run `L2-dev-90` on commit `8bb13b8`, 2026-11-01, for all but
  `c0126`, which is run `L2-dev-mixed` on commit `618750c`, 2026-10-31.
- md5: `c0126` `27594bb44075c0ad5a960ae02d0e9329`, `c0208` `75f0d0b85ee0cf309a74e2053ef9d368`, `c0236`
  `db644e80ef6958e61b13ce672e2fba48`, `c0486` `866e35419e3fe1543d3eaee47dfe7aaa`,
  `c0309` `c2812e9b34d5dac9ba134064fe9862eb`, `c0492` `ec636dea3a48fcb1188a44a020356ad4`,
  `c0550` `5f9e1da507e17ed5f2bd2861dedad251`.
- Added 2026-11-07, the same way: `c0363` and `c0246` from run
  `L2-dev-mixed` on `618750c`, the other eight from `L2-dev-90` on
  `8bb13b8`. md5: `c0029` `1492666822299512d3c37af76e099c31`, `c0166` `0cd372f9d88c12ff3c95c00f940f18aa`, `c0187` `6ef037cdefbf8685c13e30b09de8000c`, `c0221` `6b9b20ee92644c5b89fa10fe2ed88d83`, `c0246` `c7ab7e246b0cd2cfa17d422d233215c6`, `c0345` `f0fd6d49903e17c405367cb47890e4fb`, `c0363` `c58615a3181db96c902f9290ac2617c6`, `c0548` `b1097ecbd763345246a4f52bb8e2d0d2`, `c0576` `b0383d01520f2288f39349209d266608`, `c0600` `19b4daff5e718243eefaf17bba9e5c26`.
- Each source is `corpus/` (`doc_to_html.corpus.page`), which `check_page`
  finds by the page's name.

These are inputs, not a baseline. Nothing scores against them, and no run
is measured from them.
