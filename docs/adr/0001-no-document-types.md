# No document types

An invoice, an inventory sheet and a doctor's note are the same kind of input to this system: a page of Zones, tables and Pairs. There is no classifier, no per-type schema, no per-type template and no per-type prompt — one Extractor per structural Kind, one renderer, for everything.

This is surprising, because the obvious design for an invoice reader is an `Invoice` model whose fields can be validated against each other. We gave that up deliberately: a typed model is only as general as the types someone has written, and the first unanticipated document either fails or gets mangled into the nearest schema.

## Consequences

The arithmetic self-checking a typed model would have given us is recovered generically instead, by [Probes](0004-probes-never-supply-expected-values.md) that test structural relationships between numbers — a column summing to a value beneath it — without knowing what an invoice is. A Probe works identically on an invoice's totals and an inventory's stock counts.

Where per-document context genuinely helps, it enters as a **Hint**: free prose from the operator that is appended to prompts and changes no code path. A Hint is not a Type. If a Hint ever starts selecting an Extractor or a template, this decision has been reversed by accident.
