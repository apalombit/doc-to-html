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
        --page-bg:#fff; --accent:inherit;
        --flag:#b45309; --flag-bg:#fff7ed; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --muted:#9a9a9a; --rule:#333; --shade:#1e1e1e;
          --page-bg:#111;
          --flag:#fbbf24; --flag-bg:#2a1f0a; }
}
body { font:16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       color:var(--ink); background:var(--page-bg); margin:0; padding:2rem 1rem; }
.doc { max-width:52rem; margin:0 auto; }
.band { display:flex; gap:2rem; align-items:flex-start;
        margin-bottom:1.75rem; flex-wrap:wrap; }
.band > * { flex:1 1 12rem; min-width:0; }
.zone-header { font-size:1.05em; }
.zone-footer { color:var(--muted); font-size:.875em; }
h1 { font-size:1.6em; margin:0 0 .35em; letter-spacing:.01em; }
section.boxed { border:1px solid var(--rule); border-radius:4px; overflow:hidden; }
section.filled { border-radius:4px; overflow:hidden; }
h2.zone-title { font-size:.95em; font-weight:600; margin:0; padding:.55em 0; }
h2.zone-title.barred { padding:.55em .9em; }
section.boxed > h2.zone-title, section.filled > h2.zone-title { padding:.55em .9em; }
.zone-body { padding:0; }
section.boxed > .zone-body, section.filled > .zone-body { padding:.9em; }
section.boxed > .zone-body > .table-wrap,
section.filled > .zone-body > .table-wrap { margin:-.9em; }
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
        f"<style>{STYLESHEET}</style>\n"
        f"{_style_css(document)}"
        "</head>\n<body>\n"
        f'<div class="doc">\n{"".join(filter(None, body))}\n</div>\n'
        f"{_embedded_ir(document)}\n</body>\n</html>\n"
    )


def _rgb(colour: tuple[int, int, int]) -> str:
    return f"rgb({colour[0]},{colour[1]},{colour[2]})"


def _mix(ink: tuple[int, int, int], ground: tuple[int, int, int], part: float) -> str:
    """Ink moved `part` of the way toward the ground.

    Muted text and rules are not measured — they are quieter versions of the
    ink, and the only thing that makes them quiet is how close to the ground
    they sit. Hard-coding them cannot work once the ground moves: `--muted:#666`
    is grey-on-white by design and near-invisible on `darkdeck_0009`'s black,
    while `--rule:#e0e0e0` stops being a hairline and becomes the brightest
    thing on that page.
    """
    return _rgb(
        tuple(  # type: ignore[arg-type]
            round(i + (g - i) * part) for i, g in zip(ink, ground)
        )
    )


def _style_css(document: Document) -> str:
    """The measured Style Record, as CSS that overrides the house defaults.

    **A second `<style>` after the first, and that is deliberate.** The base
    stylesheet carries a `prefers-color-scheme: dark` block, and a measured
    palette written into `:root` above it would lose to that block on any
    machine in dark mode — which is precisely the harness fault Thread 0 spent a
    day finding, arriving by a different route. Later rules win, so these do.

    Emitted only for what was actually measured. A `Document` with neither a
    Style nor a width — a hand-built one in a test, an IR written before this
    existed — gets nothing here and renders exactly as it always did.

    `accent` and `shade` are omitted when the page has neither, rather than
    given a fallback. Inventing an accent would put a saturated colour in our
    output that the source does not have, and the scorer would find it: T5
    compares the most-saturated non-neutral on each side, so a fabricated
    accent turns a clean 0.00 into a finding.
    """
    # `document.page_px` is measured, traced and carried in the IR, and the
    # renderer deliberately does **not** act on it yet. Run `89-style-record`
    # set `.doc` to the source's own width and `invoice_0002`'s
    # `beside_agreement` fell 0.640 -> 0.295 — a hard-tier regression, isolated
    # to the width by re-rendering that run's own IR four ways with the palette
    # held fixed. It bought `height_ratio` 1.63 -> 1.60 on that one document and
    # nothing on the other four, which do not wrap at either width.
    #
    # The cause is the band model rather than the number: at the wider column
    # our `dl` rows re-wrap and stop lining up row for row with the source's
    # panels, so pairs the source has beside each other — `Email` beside
    # `Phone`, and six more — stop overlapping vertically in ours. That is
    # column shares and `Zone.align`, which stayed in **A2**.
    #
    # **What would have to become true**, written down so this is re-tried
    # rather than forgotten: A2 gives a Band a real column model instead of
    # `flex:1 1 12rem`, and `invoice_0002`'s `beside_agreement` at the source's
    # width matches or beats its value at 52rem. The width is already in the IR
    # waiting for that.
    rules: list[str] = []

    style = document.style
    if style is None:
        return _wrap([], rules)

    root = [
        f"--page-bg:{_rgb(style.page_bg)}",
        f"--ink:{_rgb(style.ink)}",
        f"--muted:{_mix(style.ink, style.page_bg, 0.33)}",
        f"--rule:{_mix(style.ink, style.page_bg, 0.85)}",
    ]
    # **`--shade` is derived, never the measured `Style.shade`.** The renderer
    # shades table header rows whether or not the source does, so the token has
    # to exist — but filling it with a page-wide measurement puts a colour on
    # the page that nothing on the page is: `receipt_0010` got heavy beige bars
    # and `menu_0012` tan ones, on sources with no fill anywhere, and
    # `cv_0013`'s came out accent blue. Two discriminators were built to tell a
    # real shaded band from antialiasing and texture — coverage share, and the
    # longest run of rows that are mostly the colour — and **neither separated
    # them** on the corpus (`receipt_0010` 2.7% against `invoice_0002`'s real
    # 1.9%; runs of 0-2 across the board). A-1's rule applies: do not build a
    # third without a new kind of evidence.
    #
    # A whisper of ink into the ground is the least wrong answer — it lands
    # near the `#f4f4f4` it replaces on a light page and stays dark on a dark
    # one, and it can never introduce a hue. **The measured fills are not
    # discarded**: they are per-Zone, they were accurate on `invoice_0002`,
    # `nonlatin_0014`, `form_0007` and `darkdeck_0009`, and they are emitted as
    # inline styles by `_inline_style`. Region colour is a region measurement.
    root.append(f"--shade:{_mix(style.ink, style.page_bg, 0.94)}")
    if style.accent is not None:
        # Declared and deliberately **not spent**. Every rule tried so far
        # invented the colour somewhere the source does not put it: colouring
        # `h1` text turned all of `sample_css_0004`'s dark navy headings blue,
        # and underlining `h1` instead put three rules on `sample_semantic_0005`
        # that its source does not draw. The measurement is sound and is in the
        # IR; where a page *puts* its accent is a detection problem this thread
        # has not solved. The token stays so a later pass can spend it without
        # re-measuring, and so the IR and the CSS agree about what was found.
        root.append(f"--accent:{_rgb(style.accent)}")

    return _wrap(root, rules)


def _wrap(root: list[str], rules: list[str]) -> str:
    """Custom properties and rules as one `<style>`, or nothing at all."""
    if not root and not rules:
        return ""
    declared = f":root {{ {'; '.join(root)}; }}\n" if root else ""
    return f"<style>{declared}" + "\n".join(rules) + "</style>\n"


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


MIN_ON_FILL = 0.35
"""How far a Zone's ink must sit from its own fill before it is legible.

The same figure as `style.MIN_INK_CONTRAST`, and the same reasoning: below it
the two colours are not telling a reader anything apart. Measured on
`cv_0013`, whose page ground reads white, whose ink reads **(38,51,63)**, and
whose sidebar Zone's measured fill is **(38,51,63) — the same colour**. The
renderer painted the panel and then set the type on it in the panel's own
colour, so the whole sidebar arrived invisible.

An ink measured against the *page* says nothing about a region the page does
not share a colour with. A filled Zone chooses its own.
"""

INK_ON_DARK = (232, 232, 232)
INK_ON_LIGHT = (26, 26, 26)
"""The two safe defaults, used only when the document's own ink is unreadable
on a Zone's fill. Not a palette: a legibility floor."""


def _readable_on(fill: tuple[int, int, int],
                 ink: tuple[int, int, int] | None = None) -> tuple[int, int, int] | None:
    """An ink for this fill, or None to leave the document's own ink alone.

    Returns a colour only when the document's ink would be illegible on this
    fill — the common case is a Zone whose fill is close to the page's, where
    the page's ink is exactly right and overriding it would invent a colour.
    """
    from .style import _contrast  # local import: render owns no CV of its own

    if ink is not None and _contrast(ink, fill) >= MIN_ON_FILL:
        return None
    lighter = sum(fill) > 382
    return INK_ON_LIGHT if lighter else INK_ON_DARK


COLUMN_REM = 6.0
"""Width a table column is assumed to want, when a Zone reserves room.

**Measured on 2026-09-22, and it sits in a narrow window rather than on a
plateau — say so before moving it.** `.band > * { flex:1 1 12rem; min-width:0 }`
lets a flex child shrink below its own content and `.table-wrap`'s
`overflow-x:auto` then clips the overflow, which in a screenshot is silent.
Three of fifteen renders clipped and none of the fifteen sources did:
`statement_0006`'s transactions table had 256px for the 569px it needed,
`darkdeck_0009`'s service table 400 for 467, and `cv_0013`'s sidebar pairs 256
for 368. Recall said the text was present; the picture did not contain it.

Reserving `columns x COLUMN_REM` lets `.band`'s existing `flex-wrap` put a wide
Zone on its own line instead of crushing it. Swept over the corpus with
everything else held fixed, counting clips against `beside_agreement`:

| rem | clips left | beside | what it costs |
|---|---|---|---|
| 0 | 3 | 0.717 | — |
| 5 | 3 | 0.717 | nothing, and fixes nothing |
| **6** | **1** | **0.719** | **nothing** |
| 7 | 1 | 0.715 | `catalogue_0015` 0.227 -> 0.200 |
| 8 | 1 | 0.708 | and `darkdeck_0009` 0.867 -> 0.856 |
| 10 | 1 | 0.706 | `catalogue_0015` down to 0.085 |

Six clears `statement_0006` and `darkdeck_0009` and **improves** the hard tier.
Seven begins prising `catalogue_0015`'s nine-card grid apart. Five does
nothing. There is no plateau here, so re-measure rather than nudge.
"""

PAIRS_REM = 0.0
"""The same reservation for a label/value list — **measured, and not shipped.**

`cv_0013`'s sidebar is the corpus's only clipped pairs list, 256px for the
368px it wants, and every reservation large enough to fix it costs the hard
tier. Swept with `COLUMN_REM` held at 0:

| rem | cv_0013 clip | beside | what it costs |
|---|---|---|---|
| 18, 20 | still clipped | 0.717 | nothing, and fixes nothing |
| 22 | still clipped | 0.715 | `cv_0013` 0.450 -> 0.429 |
| 24 | **fixed** | 0.712 | `cv_0013` 0.450 -> 0.409, `catalogue_0015` 0.227 -> 0.194 |
| 28 | fixed | 0.678 | `invoice_0002` 0.640 -> 0.250, `nonlatin_0014` 0.912 -> 0.662 |

Buying the clip by breaking `beside_agreement` is a T3 regression, and spec
0007 fails a phase on the hard tier regardless of what improved. A pairs list
has no column count to reserve against, so the fix is not a bigger number — it
is knowing how wide the list actually is, which is A2's question. Left at zero
and **reported** instead: `Layout.clipped` now carries it, so it is a number on
the report rather than something only a picture shows.
"""


def _reserved(zone: Zone) -> float:
    """How many rem this Zone's content needs before it starts being clipped."""
    if zone.kind is Kind.TABLE:
        columns = max((len(row.cells) for row in zone.rows), default=0)
        return columns * COLUMN_REM
    if zone.kind is Kind.PAIRS:
        return PAIRS_REM
    return 0.0


def _inline_style(zone: Zone,
                  document_ink: tuple[int, int, int] | None = None) -> str:
    """A Zone's measured fill, as an inline style.

    Inline rather than a class, because the colour is per Zone: one document can
    hold a white card, a grey card and a tinted one, and there is no fixed set
    of classes that covers what a page might do. The palette-wide values stay in
    custom properties on `:root`; only what varies Zone by Zone lands here.

    Carries two more per-Zone facts for the same reason. **The ink is chosen
    against the Zone's own fill, not the page's ground** — see `_readable_on`.
    And a Zone reserves the width its content needs, so the band wraps around
    it instead of clipping it — see `COLUMN_REM`.
    """
    parts = []
    if zone.fill is not None:
        parts.append(f"background:{_rgb(zone.fill)}")
        ink = _readable_on(zone.fill, document_ink)
        if ink is not None:
            parts.append(f"color:{_rgb(ink)}")
    reserved = _reserved(zone)
    if reserved:
        parts.append(f"min-width:min({reserved:g}rem,100%)")
    return f' style="{";".join(parts)}"' if parts else ""


def _inline_title_style(zone: Zone) -> str:
    """The Title bar's measured fill, when the source draws one."""
    if zone.title_fill is None:
        return ""
    return f' style="background:{_rgb(zone.title_fill)}"'


def _zone(zone: Zone, document: Document) -> str:
    """Render one Zone, with the chrome the **source** draws and no other.

    **This used to key off the Title, and that was the fault.** Having a caption
    turned a Zone into a bordered panel with a shaded title bar, on the
    reasoning that documents which caption a block that way read as panels.
    Some do. Most of this corpus does not, and the rule drew a card round every
    titled Zone on roughly ten documents — a full-width blue banner across
    `sample_css_0004`'s cards, and heavy grey bars over `receipt_0010`, which
    draws no fill anywhere on the page. It was invisible in every scored axis
    and obvious the moment a render was opened beside its source.

    So the border comes from `Zone.boxed`, the panel fill from `Zone.fill` and
    the bar from `Zone.title_fill` — all three measured off the Source Image by
    `style.chrome`, all three defaulting to nothing. A Zone nobody measured
    renders as plain text on the page, which is what the majority of real Zones
    actually are.
    """
    classes = f"zone zone-{zone.role.value}"
    if zone.boxed:
        classes += " boxed"
    elif zone.fill is not None:
        classes += " filled"

    bar = ' class="zone-title barred"' if zone.title_fill else ' class="zone-title"'
    style_of = _inline_style(
        zone, document.style.ink if document.style else None)
    title = (
        f"<h2{bar}{_inline_title_style(zone)}>{html.escape(zone.title)}</h2>"
        if zone.title else ""
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
    return f'<section class="{classes}"{style_of}>{title}{body}</section>'


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
