# Evaluation is synthetic-first

> **Amended 2026-09-18 by spec 0007 Thread 0.** Two changes, both in the
> paragraph below. Ground truth is no longer a *typed expected IR*: it is
> **derived** from the source HTML by `projection.project()`, which runs over
> the source page and the rendered output alike and diffs the two. "Its
> expected IR is exact and costs nothing" was not true in practice — it was
> roughly half an hour of transcription per document and a rewrite of all five
> every time the IR widened, which is the reason the corpus never left five.
> Adding a document is now writing an HTML file and screenshotting it, and the
> corpus is fifteen.
>
> **The degradation generator still does not exist**, and the synthetic-to-real
> gap is now wider than this ADR describes: derived ground truth is
> **synthetic-only by construction**, because a photograph has no source HTML
> and cannot be scored on T1-T4 or T6 at all. `preprocess.*` — deskew,
> illumination correction, rectification, page-edge detection — is therefore
> unexercised by anything spec 0007 builds and may rot silently. **Revisit
> trigger:** when T1 holds at 1.00 across a full phase on the sweep set, build
> the generator this ADR describes, applied to the rendered source with ground
> truth unchanged.


Ground truth comes primarily from documents we generate: authored HTML, rendered to an image, then degraded on purpose — skew, blur, shadow, JPEG noise. Because we built the document, its expected IR is exact and costs nothing. A small set of real photographs exists alongside it to keep the synthetic set honest.

This explains why a document *reader* contains a document *generator*, which would otherwise look like scope creep.

## Considered options

Hand-labelling a corpus of real documents measures exactly the right thing with no synthetic-to-real gap, but it is roughly half an hour of transcription per document, it grows only as fast as someone is willing to type, and genuine invoices cannot be committed to a repository.

Tracking only internal signals — Probe pass rate, dispute rate, coverage — needs no fixtures at all, but it measures the system's confidence in itself, which is precisely the quantity that is wrong when the system is wrong.

## Consequences

The degradation parameters are the point, not a detail: they let us find the exact skew angle or blur radius at which a model starts dropping table rows, which no fixed corpus reveals.

The synthetic-to-real gap is real and unmeasured. The small real-photo set is the only guard against it, and human Corrections accumulate into a second real corpus over time — which is why Corrections are anchored to image geometry rather than to IR positions, so they survive the prompt changes they exist to evaluate.
