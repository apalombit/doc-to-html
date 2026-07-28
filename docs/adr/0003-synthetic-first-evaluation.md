# Evaluation is synthetic-first

Ground truth comes primarily from documents we generate: authored HTML, rendered to an image, then degraded on purpose — skew, blur, shadow, JPEG noise. Because we built the document, its expected IR is exact and costs nothing. A small set of real photographs exists alongside it to keep the synthetic set honest.

This explains why a document *reader* contains a document *generator*, which would otherwise look like scope creep.

## Considered options

Hand-labelling a corpus of real documents measures exactly the right thing with no synthetic-to-real gap, but it is roughly half an hour of transcription per document, it grows only as fast as someone is willing to type, and genuine invoices cannot be committed to a repository.

Tracking only internal signals — Probe pass rate, dispute rate, coverage — needs no fixtures at all, but it measures the system's confidence in itself, which is precisely the quantity that is wrong when the system is wrong.

## Consequences

The degradation parameters are the point, not a detail: they let us find the exact skew angle or blur radius at which a model starts dropping table rows, which no fixed corpus reveals.

The synthetic-to-real gap is real and unmeasured. The small real-photo set is the only guard against it, and human Corrections accumulate into a second real corpus over time — which is why Corrections are anchored to image geometry rather than to IR positions, so they survive the prompt changes they exist to evaluate.
