# Structural fidelity, not pixel fidelity

> **Partly superseded by [ADR 0005](0005-style-is-measured-from-the-pixels.md)
> (2026-09-18).** The rejection of absolute-positioned facsimile below stands.
> The sentence *"No styling is ever extracted from the Source Image"* does not:
> style is now measured from pixels, because the IR had nowhere to put the
> visual weight this ADR promised and a stylesheet cannot react to a quantity
> nothing records. Read this for the facsimile decision; read 0005 for what
> replaced the rest.


The output reproduces a document's *structure* — semantic markup, Zone ordering, side-by-side arrangement via Bands — rendered through this project's own stylesheet. It does not reproduce the document's appearance. Fonts, spacing and colour are the browser's, so two invoices from different vendors render looking like siblings rather than like their originals.

The alternative was absolute-positioned text runs at detected coordinates, overlaying the original almost exactly. We rejected it on two grounds: it is extremely brittle on photographs, where a couple of degrees of skew smears the whole page; and it is semantically inert — a `<table>` becomes a cloud of positioned `<span>`s, so copy-paste, screen readers and any downstream consumer get nothing.

## What this does not mean

It does not mean appearance is irrelevant. The render is expected to be *recognisable* against its Source Image when opened in a browser: a shaded table header stays shaded, a captioned block stays a bordered panel, numeric columns stay right-aligned, headings stay visually dominant, and Zones sharing a Band stay side by side.

The distinction is where that appearance comes from. Every one of those effects is produced by this project's stylesheet reacting to the IR — to a Zone's Kind, Role and Title, and to whether a table column parses as numbers. **No styling is ever extracted from the Source Image.** The model is never asked what colour a header band was, what weight a font had, or how thick a border was; nothing in the IR can carry that, so nothing can hallucinate it.

So a render is held to matching the original's structure and visual *weight*, and to matching none of its actual styling. Fonts, colours and page dimensions differ, and the output is responsive rather than fixed-width.

## Consequences

Anyone comparing a render side by side with its Source Image should expect the arrangement and the emphasis to correspond, and the specific styling not to. A render that carries the right structure but uses different fonts and colours has passed.

Improving how closely renders resemble their originals is stylesheet work, not extraction work. If a proposal to close a visual gap requires the model to report something new about appearance, it is reversing this decision rather than refining it.
