"""IR -> one self-contained HTML file, with the IR embedded inside it.

The HTML is a derived artifact and is never hand-edited: a re-render overwrites
it. Corrections live in the IR and are applied here at render time, so the body
shows the corrected value while the IR retains what each Engine actually read.

This must tolerate an incomplete IR. Drafts are rendered partway through a
Conversion so a human can see the output converging on the Source Image, so a
Zone that has been detected but not yet extracted renders as a skeleton rather
than raising.
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from enum import Enum
from itertools import groupby
from typing import Any

from .ir import Block, Cell, CellState, Document, Kind, Pair, Role, RowRole, Zone
from .probes import is_numeric
from .wire import MARKS

STYLESHEET = """
:root { --ink:#1a1a1a; --muted:#666; --rule:#e0e0e0; --shade:#f4f4f4;
        --flag:#b45309; --flag-bg:#fff7ed; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --muted:#9a9a9a; --rule:#333; --shade:#1e1e1e;
          --flag:#fbbf24; --flag-bg:#2a1f0a; }
  body { background:#111; }
}
body { font:16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       color:var(--ink); margin:0; padding:2rem 1rem; }
.doc { max-width:52rem; margin:0 auto; }
.band { display:flex; gap:2rem; align-items:flex-start;
        margin-bottom:1.75rem; flex-wrap:wrap; }
.band > * { flex:1 1 12rem; min-width:0; }
.zone-header { font-size:1.05em; }
.zone-footer { color:var(--muted); font-size:.875em; }
h1 { font-size:1.6em; margin:0 0 .35em; letter-spacing:.01em; }
section.titled { border:1px solid var(--rule); border-radius:4px; overflow:hidden; }
h2.zone-title { font-size:.95em; font-weight:600; margin:0;
                padding:.55em .9em; background:var(--shade);
                border-bottom:1px solid var(--rule); }
.zone-body { padding:.9em; }
.zone-body > .table-wrap { margin:-.9em; }
blockquote { margin:.6em 0 .3em 1.5em; }
p.attribution { color:var(--muted); font-size:.85em; margin:0 0 .4em; }
ul { margin:0 0 .4em; padding-left:1.3em; }
.zone-header ul { display:flex; flex-wrap:wrap; gap:1.1rem;
                  list-style:none; padding:0; }
p { margin:0 0 .4em; }
dl.pairs { display:grid; grid-template-columns:auto 1fr; gap:.15em .75em; margin:0; }
dl.pairs dt { color:var(--muted); }
dl.pairs dd { margin:0; }
.zone-summary dl.pairs dd { font-weight:600; text-align:right; }
.table-wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th, td { padding:.45em .6em; text-align:left; border-bottom:1px solid var(--rule); }
thead th { background:var(--shade); font-weight:600; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
tfoot td:last-child { text-align:right; }
tfoot td { font-weight:600; border-top:2px solid var(--rule); border-bottom:none; }
figure.omitted { margin:0; border:1px dashed var(--rule); border-radius:3px;
                 min-height:3rem; display:flex; align-items:center;
                 justify-content:center; color:var(--muted); font-size:.8em; }
figure.omitted figcaption { padding:.5em; text-align:center; }
.mark { display:inline-block; border:2px solid var(--flag); color:var(--flag);
        padding:.15em .6em; border-radius:3px; font-weight:600; letter-spacing:.08em; }
.disputed { background:var(--flag-bg); border-bottom:2px solid var(--flag); cursor:help; }
.corrected { border-bottom:2px solid var(--rule); cursor:help; }
.skeleton { background:repeating-linear-gradient(135deg, var(--shade),
            var(--shade) 6px, transparent 6px, transparent 12px);
            border:1px dashed var(--rule); min-height:2.5rem; border-radius:3px; }
.findings { border-left:3px solid var(--flag); background:var(--flag-bg);
            padding:.6em 1em; margin:0 0 1.75rem; font-size:.875em; }
.findings ul { margin:.3em 0 0; padding-left:1.2em; }
.findings.caveats { border-left-color:var(--rule); background:var(--shade);
                    color:var(--muted); }
"""


def render(document: Document, *, title: str | None = None) -> str:
    """Render the IR to a complete, self-contained HTML document."""
    body = [_findings(document)]
    for band in document.bands():
        body.append(
            '<div class="band">'
            + "".join(_zone(zone, document) for zone in band)
            + "</div>"
        )

    heading = title or _infer_title(document) or "Document"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(heading)}</title>\n"
        f"<style>{STYLESHEET}</style>\n</head>\n<body>\n"
        f'<div class="doc">\n{"".join(filter(None, body))}\n</div>\n'
        f"{_embedded_ir(document)}\n</body>\n</html>\n"
    )


def _infer_title(document: Document) -> str | None:
    for zone in document.zones:
        for block in zone.blocks:
            if block.kind == "heading" and block.lines:
                return block.lines[0].text
    return None


def _findings(document: Document) -> str:
    """Surface failed Probes, Gaps, Failures, Shortfalls and Caveats at the top.

    A reader should not have to open the IR to learn the system was unsure.

    **Every finding about missing content says how much**, as a share of the
    page's printed ink. That is spec 0007 Phase A-1's honesty rule, and the
    reason it is a rule: `receipt_0010` lost 77 of its 103 tokens under "found
    by ink coverage, so it may be a mark", and `darkdeck_0009` lost most of its
    document and printed nothing here at all.

    The panel is excluded from `projection.project` by class name, so nothing
    written here is ever scored as content the model invented — see
    `projection.MEASURE`'s `CHROME_SELECTORS`. That is what makes it safe for a
    finding to be honest at length.

    Two blocks, not one, because the two say opposite things about whether the
    content below can be relied on. "Unresolved" means something is missing or
    does not add up. A Caveat means the Zone converted and there is a qualifier
    on *how* — read at reduced resolution, or a Kind overturned by the Extractor
    that was handed it. Filing the second under the first tells a reader their
    document failed while showing them a complete document, which is what a run
    on `invoice_0001` with a re-read Zone and no Failures at all looked like.
    """
    items = [
        f"Probe <code>{html.escape(p.kind)}</code> did not reconcile"
        + (f": computed {html.escape(p.computed)}" if p.computed else "")
        + (f" ({html.escape(p.detail)})" if p.detail else "")
        for p in document.probes
        if not p.ok
    ]
    items += [
        "Content found outside every detected region"
        + (f": {html.escape(g.note)}" if g.note else "")
        for g in document.gaps
        if not g.resolved
    ]
    items += [
        f"Zone {f.zone_index} (<code>{html.escape(f.kind)}</code>) could not "
        f"be read: {html.escape(f.reason)}"
        + (f" — this Zone holds {f.ink_share * 100:.0f}% of the page's printed "
           "ink, and none of it reached this document" if f.ink_share else "")
        for f in document.failures
    ]
    # Read, and read short. Under "Unresolved" rather than under the Caveats
    # below, because content that did not arrive is not a qualifier on content
    # that did — see `ir.Shortfall`.
    items += [
        f"Zone {s.zone_index} (<code>{html.escape(s.kind)}</code>) was read "
        f"short: {s.printed_lines} lines are printed in it and the reading "
        f"returned {s.read_lines}"
        + (f", over {s.ink_share * 100:.0f}% of the page's printed ink"
           if s.ink_share else "")
        for s in document.shortfalls
    ]
    caveats = [
        f"Zone {c.zone_index} (<code>{html.escape(c.kind)}</code>) "
        f"{html.escape(c.note)}"
        for c in document.caveats
    ]
    return _findings_block("Unresolved", "findings", items) + _findings_block(
        "Read with a caveat", "findings caveats", caveats
    )


def _findings_block(heading: str, css: str, items: list[str]) -> str:
    if not items:
        return ""
    return (
        f'<div class="{css}"><strong>{heading}</strong><ul>'
        + "".join(f"<li>{item}</li>" for item in items)
        + "</ul></div>"
    )


def _zone(zone: Zone, document: Document) -> str:
    """Render one Zone.

    A Title turns the Zone into a bordered panel with a shaded title bar. That
    is not decoration for its own sake: documents that caption a block that way
    read as panels, and the render is held to matching the original's visual
    weight even though it matches none of its actual styling.
    """
    classes = f"zone zone-{zone.role.value}" + (" titled" if zone.title else "")
    title = (
        f'<h2 class="zone-title">{html.escape(zone.title)}</h2>' if zone.title else ""
    )

    if not zone.complete and zone.kind is not Kind.FIGURE:
        # A titled Zone keeps its caption even while its contents are pending,
        # so a Draft shows what is being worked on rather than an unlabelled box.
        body = '<div class="skeleton"></div>'
    else:
        renderers = {
            Kind.TABLE: _table,
            Kind.PAIRS: _pairs,
            Kind.PROSE: _prose,
            Kind.LIST: _list,
            Kind.FIGURE: _figure,
        }
        body = renderers[zone.kind](zone, document)

    if zone.title:
        body = f'<div class="zone-body">{body}</div>'
    return f'<section class="{classes}">{title}{body}</section>'


def _numeric_columns(zone: Zone) -> set[int]:
    """Column indices whose data rows are predominantly numbers.

    Alignment follows content rather than position. Right-aligning everything
    but the first column looks right on an invoice and wrong on a table whose
    second and fifth columns are country codes and currencies.

    The test is whether a cell *is* a number, not whether it contains one: an
    item column reading "Hosting (3 months)" and "Domain name (1 year)" would
    otherwise be right-aligned on the strength of the digits inside its
    descriptions.
    """
    counts: dict[int, list[int]] = {}
    for row in zone.rows:
        if row.role is not RowRole.DATA:
            continue
        for index, cell in enumerate(row.cells):
            seen = counts.setdefault(index, [0, 0])
            seen[0] += 1
            if is_numeric(cell.text):
                seen[1] += 1
    return {index for index, (total, numeric) in counts.items()
            if total and numeric / total > 0.6}


def _table(zone: Zone, document: Document) -> str:
    numeric = _numeric_columns(zone)
    groups: dict[RowRole, list[str]] = {role: [] for role in RowRole}
    for row in zone.rows:
        tag = "th" if row.role is RowRole.HEADER else "td"
        cells = "".join(
            f'<{tag}{" class=\"num\"" if index in numeric else ""}>'
            f"{_cell(c, document)}</{tag}>"
            for index, c in enumerate(row.cells)
        )
        groups[row.role].append(f"<tr>{cells}</tr>")

    parts = []
    if groups[RowRole.HEADER]:
        parts.append(f"<thead>{''.join(groups[RowRole.HEADER])}</thead>")
    if groups[RowRole.DATA]:
        parts.append(f"<tbody>{''.join(groups[RowRole.DATA])}</tbody>")
    if groups[RowRole.SUMMARY]:
        parts.append(f"<tfoot>{''.join(groups[RowRole.SUMMARY])}</tfoot>")
    return f'<div class="table-wrap"><table>{"".join(parts)}</table></div>'


def _pairs(zone: Zone, document: Document) -> str:
    return (
        '<dl class="pairs">'
        + "".join(
            f"<dt>{_cell(p.label, document)}</dt><dd>{_cell(p.value, document)}</dd>"
            for p in zone.pairs
        )
        + "</dl>"
    )


def _prose(zone: Zone, document: Document) -> str:
    """Blocks in order, with runs of `item` gathered into lists.

    `prose` and `list` are not disjoint: `PROSE_PROMPT` offers `item` as a block
    kind, so a bulleted region read as prose comes back with exactly the blocks a
    LIST Zone would have. Rendering those as paragraphs made the classifier's
    choice change the HTML for identical content — silently, since a prose Zone
    full of items is complete, carries no Failure and no Caveat, and reads as a
    success. Gathering them here means the Kind decides which prompt is asked and
    stops deciding what the reader gets.

    Only *consecutive* items group, because a paragraph between two bullets ends
    the list on the page and should end it here.
    """
    parts = []
    for is_item, run in groupby(zone.blocks, key=lambda b: b.kind == "item"):
        if is_item:
            items = "".join(f"<li>{_lines(b, document)}</li>" for b in run)
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.extend(_block(b, document) for b in run)
    return "".join(parts)


def _list(zone: Zone, document: Document) -> str:
    """Items only, and deliberately nothing else.

    Kept separate from `_prose` rather than routed through it. Dropping a
    non-item block is the point: a LIST Zone that comes back as paragraphs
    renders an empty `<ul>`, which is visible as the mis-read it is. `_prose`
    keeps every block because there nothing has claimed the region is a list.
    """
    items = "".join(
        f"<li>{_lines(b, document)}</li>" for b in zone.blocks if b.kind == "item"
    )
    return f"<ul>{items}</ul>"


def _figure(zone: Zone, document: Document) -> str:
    """A Graphic is placeholdered; a Mark keeps its text.

    Chart data is never reconstructed from geometry, but a chart's title and
    axis labels are document text and are captured as a caption.
    """
    kind = zone.graphic_kind or "figure"
    if kind in MARKS:
        # A Mark with no text — an illegible signature — falls back to naming
        # itself. That it is there is the finding, and an empty box states it
        # less clearly than the word does.
        text = "".join(_lines(b, document) for b in zone.blocks)
        return (
            f'<div class="mark" data-kind="{html.escape(kind)}">'
            f"{text or html.escape(kind)}</div>"
        )

    caption = "".join(
        f"<figcaption>{_lines(b, document)}</figcaption>"
        for b in zone.blocks
        if b.lines
    )
    bbox = _bbox_attr(zone)
    return (
        f'<figure class="omitted" data-kind="{html.escape(kind)}"{bbox}>'
        f"{caption or f'<figcaption>{html.escape(kind)}</figcaption>'}</figure>"
    )


def _block(block: Block, document: Document) -> str:
    if block.kind == "heading":
        return f"<h1>{_lines(block, document)}</h1>"
    if block.kind == "quote":
        return f"<blockquote>{_lines(block, document)}</blockquote>"
    if block.kind == "attribution":
        return f'<p class="attribution">{_lines(block, document)}</p>'
    return f"<p>{_lines(block, document)}</p>"


def _lines(block: Block, document: Document) -> str:
    return "<br>".join(_cell(line, document) for line in block.lines)


def _cell(cell: Cell, document: Document) -> str:
    """Render one value, applying any Correction anchored to its pixels.

    A Correction wins over every Engine reading; the readings it displaced stay
    in the embedded IR, which is what makes each one a ground-truth label.
    """
    correction = (
        document.correction_for(cell.bbox) if cell.bbox is not None else None
    )
    if correction is not None:
        was = html.escape(correction.replaced or cell.text)
        return (
            f'<span class="corrected" title="read as: {was}">'
            f"{html.escape(correction.text)}</span>"
        )

    if cell.state is CellState.DISPUTED and len(cell.readings) > 1:
        alt = " / ".join(r.text for r in cell.readings[1:])
        return (
            f'<span class="disputed" data-alt="{html.escape(alt)}" '
            f'title="also read as: {html.escape(alt)}">{html.escape(cell.text)}</span>'
        )
    return html.escape(cell.text)


def _bbox_attr(zone: Zone) -> str:
    if zone.bbox is None:
        return ""
    b = zone.bbox
    return f' data-bbox="{b.left:.4f},{b.top:.4f},{b.right:.4f},{b.bottom:.4f}"'


def _embedded_ir(document: Document) -> str:
    """Embed the IR as JSON.

    `</` is escaped so a document containing the literal text `</script>` cannot
    terminate the block and break the page.
    """
    payload = json.dumps(asdict(document), default=_encode, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    return f'<script type="application/json" id="doc-ir">{payload}</script>'


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"not JSON-serialisable: {type(value).__name__}")
