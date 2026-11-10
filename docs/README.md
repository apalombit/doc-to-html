# docs — a map

**Start here:** the [README](../README.md), then [`CONTEXT.md`](../CONTEXT.md)
(the vocabulary), then [`status.md`](status.md) (where the project is), then
the latest spec.

| where | what |
|---|---|
| [`status.md`](status.md) | **The live state**: what is done, what is decided, what comes next. Rewritten when it goes stale. |
| [`level-up.md`](level-up.md) | The plan since 2026-10-24: conversion that holds on pages nobody has tuned on. Its "Gist" is the short version. |
| [`specs/`](specs/) | One spec per piece of work: its question, its measurements, what was tried and rejected, and the decision. Listed below. |
| [`adr/`](adr/) | Five architecture decisions, each with the reason it looks the way it does. |
| [`agents/`](agents/) | How the AI agent works here: the [review criteria](agents/review-criteria.md) agreed with the human, the calls of each review (`review-calls/`), the decisions taken on the issue page (`review-issues.json`), and the issue-tracker and labelling conventions. |
| [`level-up-probe/`](level-up-probe/README.md) | The probe on ten never-seen pages that showed the pipeline was overfit, 2026-10-24. |
| [`future-ideas.md`](future-ideas.md) | A judge-led loop, discussed 2026-10-18; its judge was built as the level-up's L2 (spec 0021). Record only. |
| [`img/`](img/) | Pictures for the README. |

## The specs

| # | month | spec |
|---|---|---|
| 0001 | Jul | [Make one image work](specs/0001-one-image-at-a-time.md) |
| 0002 | Jul | [Structure, not geometry](specs/0002-structure-not-geometry.md) |
| 0003 | Jul | [Classify from the crop, not from the downscaled page](specs/0003-classify-from-the-crop.md) |
| 0004 | Aug | [Check the box against the ink](specs/0004-check-the-box-against-the-ink.md) |
| 0005 | Aug | [Nothing is missing](specs/0005-nothing-is-missing.md) |
| 0006 | Sep | [Group at the right level](specs/0006-group-at-the-right-level.md) |
| **0007** | Sep | [**Look like the document**](specs/0007-look-like-the-document.md): the target since 2026-09-17, still authoritative ([measurements](specs/0007-a2-measurements.md), [handover](specs/0007-handover.md)) |
| 0008 | Oct | [Read the page's structure before its boxes](specs/0008-page-structure.md) |
| 0009 | Oct | [Four repairs after the structure step, one sweep](specs/0009-four-repairs-one-sweep.md) |
| 0010 | Oct | [Five repairs, the beside score, and type at the page's size](specs/0010-repairs-beside-and-type.md) |
| 0011 | Oct | [Place every entry where the page puts it](specs/0011-place-every-entry.md) |
| 0012 | Oct | [Draw what the page draws](specs/0012-draw-what-the-page-draws.md) |
| 0013 | Oct | [Four pages first](specs/0013-four-pages-first.md) |
| 0014 | Oct | [Every printed line has a place](specs/0014-every-line-a-place.md) |
| 0015 | Oct | [Every line read, and drawn where the page puts it](specs/0015-drawn-where-the-page-puts-it.md) |
| 0016 | Oct | [Structure first: one grid, one strip](specs/0016-one-grid-one-strip.md) |
| 0017 | Oct | [Margins from the type, one size per role](specs/0017-margins-and-roles.md) |
| 0018 | Oct | [The strip, photographed pages, and the straightening step](specs/0018-strip-twins-rectify.md) |
| 0019 | Oct | [One grouping however the page is pictured; structure, looks, readings checked](specs/0019-steady-checked-structured-styled.md) |
| 0020 | Oct | [The corpus: 600 pages, chosen by their variability](specs/0020-the-corpus.md) |
| 0021 | Nov | [Measurement and the judge](specs/0021-measurement-and-the-judge.md) |
| 0022 | Nov | [The honest baseline](specs/0022-the-honest-baseline.md) |
| **0023** | Nov | [**Parser first**: GLM-OCR's pipeline, an adapter, our looks](specs/0023-parser-first.md): adopted 2026-11-09 |

## The decisions

| # | decision |
|---|---|
| [0001](adr/0001-no-document-types.md) | No document types: an invoice and a menu are the same kind of input |
| [0002](adr/0002-structural-over-pixel-fidelity.md) | Structural fidelity, not pixel fidelity |
| [0003](adr/0003-synthetic-first-evaluation.md) | Evaluation is synthetic-first |
| [0004](adr/0004-probes-never-supply-expected-values.md) | Probes may target a re-read, but never supply the expected value |
| [0005](adr/0005-style-is-measured-from-the-pixels.md) | Style is measured from the pixels |
