# Style is measured from the pixels

**Supersedes part of ADR 0002.** That decision's rejection of positioned
facsimile stands and is not reopened. What this reverses is one sentence of it:
*"No styling is ever extracted from the Source Image."*

Style now **is** extracted — background, ink, accent, shaded bands, borders,
card treatment, type scale, alignment and column proportion — and it is
extracted by **measuring pixels**, never by asking a model. The output stays
semantic: the IR gains fields for these quantities and the renderer reacts to
them, exactly as it already reacts to Kind, Role and Title. A `<table>` is
still a `<table>`.

## Why the original sentence could not survive

ADR 0002 said a render is held to matching its original's structure and visual
*weight*. Spec 0007 measured that claim and it does not hold, because the IR
has nowhere to put the weight:

| the page has | the IR has |
|---|---|
| inline runs (link, code, em, badge) | `Cell.text: str` — a flat string |
| colour, background, borders, rules | nothing |
| font family, size, weight | `Block.kind`, an 8-value enum |
| alignment | nothing |
| column proportions | `band: int`, `column: int` |
| reflowable paragraphs | `lines: list[Cell]` joined by `<br>` |
| a logo | `graphic_kind: str` — a label, no pixels |

"Improving how closely renders resemble their originals is stylesheet work, not
extraction work" was the load-bearing claim, and it is false for every row of
that table. A stylesheet cannot react to a quantity nothing records. `render.py`'s
`.band > * { flex: 1 1 12rem }` makes every column equal because **no width
exists in the IR to be wrong about** — which is why `sample_semantic_0005`'s
aside is 35% of the width in the source and 50% in the output.

## Why pixels, and not a model

Because this project already learned that *an instruction is reachable only if
it asks the model to decide differently, not to perceive differently.* Colour is
perception, and the pixels are already in hand.

Sampling a pixel is exact, free, deterministic and cannot hallucinate. Asking a
4B model what colour a band was is worse on every one of those four. So Thread
2/B adds **zero model calls**: modal background, modal ink, most-saturated
non-neutral, ink-band heights for the type scale, an OpenCV rectangle finder for
borders and cards, ink centroid for alignment.

**Correction, 2026-09-20 — the rectangle finder has to be built.** This decision
was written as though it were in hand. It is not in the tree and never was:
`git log -S findContours` across all history returns only `find_page_quad`,
which is page-edge detection for rectification.
`tools/cv_layout_probe.py`'s `zones_from_morphology` dilates ink into blocks and
cannot see a drawn border. Spec 0006 Change 3's measurement lived in a scratch
script that was never committed.

**Nothing above changes** — measuring borders from pixels is still right, and is
still cheaper and more reliable than asking a model. Only the cost changes, and
only for the one quantity. The guard recorded with it (*a rectangle covering
more than 0.80 of the page is the page*) is knowledge worth keeping and worth
**re-measuring** rather than citing.

That also makes the style record fully deterministic and unit-testable against
`tests/frozen/run84/` with nothing running.

## What is still rejected

**Absolute-positioned facsimile.** ADR 0002's two grounds are unchanged: it is
brittle under skew, and it is semantically inert — a `<table>` becomes a cloud
of `<span>`s and screen readers get nothing.

**Fixed output height.** The output carries the source's *width* and lets height
fall out. A fixed height makes every vertical dimension a constraint that must
be simultaneously exact, which it cannot be when our text differs from the
source by one OCR slip; the result is clipping, which means content T1 can see
in the DOM and T5 cannot see in the pixels — two tiers disagreeing about
whether content exists. With width pinned and height free, `height_ratio`
becomes the single best diagnostic available.

## Consequences

Comparing a render with its Source Image, expect palette, type scale, card
treatment and column proportion to correspond, not only arrangement. A render
that carries the right structure in the wrong colours has **not** passed.

The judgement is `doc_to_html.scoring`'s six axes and the evidence is
`debug/runs/<label>/report.html`. Font *family* is explicitly de-prioritised:
a cheap stroke-terminal guess with a sans fallback, and being wrong about serif
costs far less than being wrong about content.
