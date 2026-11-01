# `l2-dev/` — seven of dev's renders, the input to the check tests

Spec 0021's review of dev (2026-11-01) overturned the exact checks on
some pages. Each fix to a check is pinned on the page that showed the
fault, and the page's true faults are pinned beside it. These are the
renders those tests read: `tests/test_checks.py`, class
`TestWhatTheReviewOfDevRejected`.

| file | what it pins |
|---|---|
| `c0550.html` | T: the exploded drawing's callouts 1, 2, 4 and 5 and the Cinder logo are drawn in a figure's pixels, a minor. The nomenclature's 1 and 4, read as bullets, stay lost |
| `c0208.html` | I: the header's right block and the patient box's right half are drawn side by side as printed, interleaved only in the render's HTML, a minor. Nothing is under another heading |
| `c0236.html` | I: the copies of the medication list drawn in the Plan column stay under another heading, a major. 'Wt 214 lb' and 'SpO2 97%', drawn in the Vitals column as printed, do not |
| `c0486.html` | A: 'Margaret Ellison', a short line ended by a break in a justified block, is set left as printed. The job title drawn right stays |
| `c0492.html` | A: the two names, centred in their halves on both, are not read as set left. 'ST-22-0417', drawn left of where the page sets it flush right, stays |
| `c0126.html` | P: the top rule, drawn by a separator above the table, frames it. '2020' read '2028' stays |
| `c0309.html` | P: the totals drawn as a table of their own; the rule under Repas is the main table's foot. The steps drawn as bullets stay |

## Provenance

- Copied byte for byte from `debug/runs/<run>/dump/qwen3-vl_4b/<page>/document.html`,
  qwen3-vl:4b: run `L2-dev-90` on commit `8bb13b8`, 2026-11-01, for all but
  `c0126`, which is run `L2-dev-mixed` on commit `618750c`, 2026-10-31.
- md5: `c0126` `27594bb44075c0ad5a960ae02d0e9329`, `c0208` `75f0d0b85ee0cf309a74e2053ef9d368`, `c0236`
  `db644e80ef6958e61b13ce672e2fba48`, `c0486` `866e35419e3fe1543d3eaee47dfe7aaa`,
  `c0309` `c2812e9b34d5dac9ba134064fe9862eb`, `c0492` `ec636dea3a48fcb1188a44a020356ad4`,
  `c0550` `5f9e1da507e17ed5f2bd2861dedad251`.
- Each source is `corpus/` (`doc_to_html.corpus.page`), which `check_page`
  finds by the page's name.

These are inputs, not a baseline. Nothing scores against them, and no run
is measured from them.
