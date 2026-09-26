# doc-to-html

Turns a photograph or scan of a text-bearing document into an HTML file that, when rendered, carries the same content and the same structure as the original. Document type is not modelled: an invoice and an inventory sheet are the same kind of input.

## Language

**Source Image**:
The photograph or scan given to the system. One Source Image is the unit of input.
_Avoid_: Scan, photo, input file

**Document**:
The thing depicted in a Source Image, understood as content rather than pixels. Has no type — the system never classifies it as "an invoice" or "an inventory sheet".
_Avoid_: Page, file, record

**Zone**:
A top-level region of a Document, and the coarse layout skeleton the rendered HTML preserves. Every Zone carries two independent classifications, a Kind and a Role.
_Avoid_: Section, region, area

**Band**:
A horizontal stripe of the Document holding one or more Zones side by side. Bands are the only expression of horizontal arrangement — Zones are a flat list, never nested, and two Zones sharing a Band render as columns.
_Avoid_: Row, group, container, section

**Title**:
A heading that belongs to a Zone rather than standing beside it — "Company Details" captioning the Pairs beneath it. A Title binds the caption to the block it names, so the grouping holds even when a neighbouring Zone in the same Band is a different height.
_Avoid_: Heading, caption, label, panel header

**Kind**:
What a Zone's content structurally is, drawn from a closed set: `table`, `pairs`, `prose`, `list`, `figure`. Kind determines which Extractor reads the Zone — one Extractor per Kind, no more.
_Avoid_: Type, class, category

**Role**:
What a Zone plays in the Document, drawn from a closed set: `header`, `summary`, `footer`, `body` (the default). Role is orthogonal to Kind — a totals block is Kind `pairs` with Role `summary` — and it is what Probes navigate by.
_Avoid_: Position, function, purpose, section type

**Row Role**:
The same distinction one level down, existing only inside a `table` Zone: `header`, `data`, `summary`. Probes sum `data` rows and check the result against `summary` rows. Zones of other Kinds have no rows and never carry this.
_Avoid_: Row type, total row, footer row

**Block**:
A unit of content inside a Zone — a heading, a paragraph, an address, a table. The leaf level of the structural model.
_Avoid_: Element, node, chunk

**Pair**:
A label bound to a value, as in "Invoice No: INV-2026-0184". The characteristic content of a key-value Zone.
_Avoid_: Field, key-value, attribute

**Graphic**:
A non-text region carrying no document-bearing text of its own — a logo, a chart's plotted area. A Graphic carries its own pixels, cropped from the Rectified Image, and is drawn from them; its data is never reconstructed from geometry. A logo's wordmark counts as part of the Graphic and is not printed as content, unlike a Mark's text: anything read off a Graphic is kept as the image's alternative text.
_Avoid_: Image, figure, illustration

**Separator**:
A purely decorative division — a horizontal rule, a panel border, a column divider. Separators are not Zones and are not recorded: they carry no content, and a placeholder for one would add noise to the render without adding information.
_Avoid_: Rule, divider, line, border

**Mark**:
A graphically rendered element that nonetheless carries document meaning — a PAID stamp, a signature, a handwritten annotation. A Mark's text is captured; where it has none, its presence alone is recorded.
_Avoid_: Annotation, overlay, stamp

**Structural Fidelity**:
The standard the output is held to: semantic markup and correct Zone ordering, rendered through the project's own stylesheet, **now driven by the Style Record measured off the Source Image**. Still explicitly not a pixel-level reproduction — a `<table>` stays a `<table>` and absolute-positioned facsimile stays rejected — but "fonts, spacing and colour are the browser's" no longer holds. See ADR 0005, which supersedes that half of ADR 0002.
_Avoid_: Accuracy, faithfulness, visual fidelity

**Style Record**:
What a page looks like, measured from its own pixels and never asked of a model: ground, ink and accent colour, shaded bands, borders and card treatment, type scale, and the page's width. It is part of the IR, so the renderer reacts to it exactly as it reacts to Kind, Role and Title. Measuring rather than asking is the decision, not an implementation detail — colour is perception, and this project has established that a model complies with instructions to decide differently and ignores instructions to perceive differently.
_Avoid_: Theme, stylesheet, CSS, design tokens, styling

**Probe**:
A type-agnostic arithmetic check run over an extracted table — a column that should sum to a stated value, a row whose factors should give its product. Probes know nothing about invoices; they test structural relationships between numbers.
_Avoid_: Validation, check, rule, assertion

**IR**:
The engine-agnostic structured record of everything the system learned from one Source Image — Zones, Blocks, text, geometry, rival readings, Disputed states and Probe results. Extractors write it, Probes test it, the renderer reads it; nothing else touches pixels or HTML.
_Avoid_: Model, AST, document tree, extraction result

**Conversion**:
One run of the Orchestrator over one Source Image, producing one self-contained HTML file with the IR embedded in it.
_Avoid_: Job, run, transform, processing

## Pipeline

**Extractor**:
A narrow, single-purpose step that turns one Zone into part of the IR. An Extractor owns one Zone kind and has no autonomy — it does not decide whether its own output is good enough.
_Avoid_: Agent, worker, parser, handler

**Orchestrator**:
The single component that sequences Extractors, routes each Zone to an engine, and owns all retry and Escalation policy. Retry logic lives here and nowhere else.
_Avoid_: Pipeline, controller, manager, coordinator

**Engine**:
A source of readings from pixels — tesseract, or a vision model reached through Ollama. Engines are interchangeable behind an Extractor; which one runs on a given Zone is the Orchestrator's routing decision.
_Avoid_: Backend, provider, model, OCR

**Rectified Image**:
The Source Image after geometric and photometric normalisation — page quadrilateral detected, perspective corrected, orientation fixed, intensity equalised. Everything downstream reads this and never the raw photo; Bands and bounding boxes are only meaningful against it.
_Avoid_: Processed image, normalised image, cleaned image

**Ladder**:
The ordered set of increasingly expensive re-looks available for one unresolved item: read normally, re-crop and upscale, try another Engine, ask the human. Each Rung is tried at most once, so a Conversion terminates by exhausting Ladders rather than by counting rounds.
_Avoid_: Retry loop, pipeline, strategy, chain

**Slice**:
A horizontal band of a Zone too dense to read whole, cropped with a deliberate row overlap onto its neighbours. Slices are extracted independently and stitched by matching the repeated rows in the overlap, which doubles as a consistency check on the seam.
_Avoid_: Chunk, tile, segment, split

**Coverage Audit**:
An independent check that every part of the Rectified Image bearing content falls inside some Zone, performed by a different model family from the one that produced the layout. It exists to catch content that was never detected — the one failure mode that leaves the IR internally consistent and every Probe passing.
_Avoid_: Completeness check, validation, sanity check

**Gap**:
A region of the Rectified Image carrying content that no Zone covers. A Gap is a finding of the Coverage Audit and enters the Ladder like any other unresolved item.
_Avoid_: Missing region, hole, uncovered area

**Failure**:
A Zone an Extractor could not fill, recorded in the IR rather than raised. The Zone stays incomplete and renders as a skeleton, the Conversion continues, and the reason is kept — which is what makes a skeleton traceable to what went wrong rather than merely visible. Distinct from a Gap: a Gap is content no Zone covers, a Failure is a Zone whose content could not be read.
_Avoid_: Error, exception, incomplete zone

**Caveat**:
Something an operator should know about *how* a Zone was read, on a Zone that was read. The Zone is complete and keeps its content, because degraded content beats none; the Caveat exists so nobody mistakes it for an ordinary reading. A table too tall to fit the model's input, read whole at reduced resolution instead of in stitched Slices, carries one. The opposite of a Failure rather than a milder version of it: a Failure has no content and a skeleton, a Caveat has content and a note.
_Avoid_: Warning, degraded failure, partial failure

**Hint**:
Free prose supplied by the human at the opening Checkpoint, stored in the IR and appended verbatim to every prompt. A Hint changes what a model is told and never what the code does — it is not a document type, and nothing branches on it.
_Avoid_: Type, class, category, document kind

**Escalation**:
The targeted re-reading of a single disputed cell — re-cropped from the Rectified Image at full resolution, upscaled, and put to an Engine again. Escalation is triggered by disagreement, never run wholesale.
_Avoid_: Retry, fallback, second pass

**Draft**:
A render produced from an incomplete IR partway through a Conversion. Drafts exist so a human can see the output converging on the Source Image; the renderer must never assume the IR is finished.
_Avoid_: Preview, intermediate output, partial render

**Checkpoint**:
A point at which the Orchestrator stops and asks the human a question — to establish what a Document is at the outset, to confirm a Draft is converging, or to arbitrate readings it could not reconcile. Answers are structured; an optional free-text note rides along and is appended verbatim to the next pass's prompt, never interpreted.
_Avoid_: Prompt, review, approval, gate

**Correction**:
A human ruling on a cell, appended to the IR rather than overwriting the readings that prompted it, and anchored to a bounding box on the Rectified Image rather than to a position in the IR. Both what the Engines read and what the human ruled stay on record, and the anchor survives any later change to prompts, models or Zone structure — which is what makes a Correction a durable ground-truth label.
_Avoid_: Fix, edit, override, amendment

**Disputed**:
The state of a cell whose readings still disagree after Escalation. A Disputed value is emitted with its rival reading retained alongside it, never silently resolved.
_Avoid_: Uncertain, low-confidence, ambiguous
