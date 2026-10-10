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
import re
from dataclasses import asdict
from enum import Enum
from functools import lru_cache
from itertools import groupby
from typing import Any

from .ir import (Block, Cell, CellState, Document, Flow, Kind, Pair, Region,
                 Role, RowRole, Zone)
from .probes import is_numeric
from .wire import MARKS, bands_from_boxes

STYLESHEET = """
:root { --ink:#1a1a1a; --muted:#666; --rule:#e0e0e0; --shade:#f4f4f4;
        --page-bg:#fff; --accent:inherit;
        --flag:#b45309; --flag-bg:#fff7ed;
        --link:#0645ad; --mark-bg:#fff2a8; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --muted:#9a9a9a; --rule:#333; --shade:#1e1e1e;
          --page-bg:#111;
          --flag:#fbbf24; --flag-bg:#2a1f0a;
          --link:#7aa7ff; --mark-bg:#5a4a12; }
}
body { font:16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       color:var(--ink); background:var(--page-bg); margin:0; padding:2rem 1rem; }
.doc { max-width:52rem; margin:0 auto; }
/* Inline runs. `<a>` carries no href — nothing read off the page says where a
   link goes — so it needs styling of its own to read as one. */
a { color:var(--link); text-decoration:underline; }
code { font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
       font-size:0.92em; }
mark { background:var(--mark-bg); color:inherit; padding:0 0.15em; }
.band { display:flex; gap:2rem; align-items:flex-start;
        margin-bottom:1.75rem; flex-wrap:wrap; }
.band > * { flex:1 1 12rem; min-width:0; }
/* A `columns` Region: its lanes side by side, each read top to bottom and as
   wide as the page draws it. Spec 0008, step 2. */
.columns { display:flex; gap:2rem; align-items:flex-start; margin-bottom:1.75rem; }
.lane { min-width:0; }
.lane > .band:last-child { margin-bottom:0; }
/* A label column in a lane takes at most half of it. A lane is narrower than
   the page, and `cv_0013`'s `Chartered Engineer, Engineers Ireland (2019)`
   sized the `auto` track to the whole sidebar, leaving `Reg. no. 11408` a
   sliver that `anywhere` broke after every letter — N4's fault, in a lane. */
.columns dl.pairs { grid-template-columns:fit-content(50%) 1fr; }
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
/* A long unbreakable value must wrap, not be hidden. `section.filled` and
   `section.boxed` both set `overflow:hidden` to keep a fill inside its own
   rounded corner, so anything wider than the Zone is silently cut off in the
   screenshot — recall says the text is present and the picture does not
   contain it. `cv_0013`'s sidebar was the corpus's one case: the `auto` track
   sized itself to `ines.halloran@fempost.example`, which has no break
   opportunity, giving the Zone a 368px content width inside a 256px box.
   `anywhere` rather than `break-word` because only `anywhere` lowers the
   min-content width the grid track is measured from. Measured 2026-09-25 over
   all fifteen: corpus `clipped` 1 -> 0, `beside_agreement` +0.0033,
   `alignment_agreement` +0.0019, ratchet clean, and `cv_0013`'s height_ratio
   1.77 -> 2.14, which is the wrapped address taking the lines it needs. */
dl.pairs dt, dl.pairs dd { overflow-wrap:anywhere; }
/* A label with no value is not in the label column. Left there, the `auto`
   track sizes itself to it as if a value stood beside it, and the `1fr` track
   gets what is left: `catalogue_0015`'s `Suffolk pattern, 265 mm, beeswax` took
   the whole card and `each`, the next line's value, was broken after every
   letter by the `anywhere` above. Across both columns it sizes neither, so the
   label column is as wide as the labels that have values. N4, 2026-10-10. */
dl.pairs dt.alone { grid-column:1 / -1; }
dl.pairs dt.alone + dd { display:none; }
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
    body = [_findings(document), *_body(document)]

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


def _band(zones: list[Zone], document: Document) -> str:
    return ('<div class="band">'
            + "".join(_zone(zone, document) for zone in zones) + "</div>")


def _body(document: Document) -> list[str]:
    """Every Band as a row, except where a `columns` Region reads down.

    **A page with no `columns` Region is drawn exactly as before**, Band by
    Band. Where there is one, its Zones leave the page's Bands and are drawn
    together, where the first of them would have been: each lane a stack of
    its own rows, read top to bottom, so `cv_0013`'s sidebar is no longer
    paired with whichever main-column item sits at its height.
    """
    columns = [r for r in document.regions if r.flow is Flow.COLUMNS]
    home: dict[int, Region] = {}
    for zone in document.zones:
        for region in columns:
            if zone.bbox is not None and region.holds(zone.bbox):
                home[id(zone)] = region
                break
    if not home:
        return [_band(band, document) for band in document.bands()]

    out: list[str] = []
    drawn: set[int] = set()
    for band in document.bands():
        outside = [zone for zone in band if id(zone) not in home]
        if outside:
            out.append(_band(outside, document))
        for zone in band:
            held = home.get(id(zone))
            if held is None or id(held) in drawn:
                continue
            drawn.add(id(held))
            out.append(_columns(
                held, [z for z in document.zones if home.get(id(z)) is held],
                document))
    return out


def _columns(region: Region, zones: list[Zone], document: Document) -> str:
    """One `columns` Region: its lanes side by side, each as wide as the page
    draws it and holding its own Zones in rows worked out among themselves —
    so `2021 — present` sits beside `Senior Structural Engineer` in its lane,
    as on the page.

    **Each lane is stacked on its own**, and it costs T3 `beside`, measured
    before choosing. A two-column page's side-by-side pairs are coincidences
    of height between independent columns, and the Band render reproduced them
    by construction — it is built from exactly those overlaps, which is also
    why it interleaved the columns. Two ways of keeping them were measured
    offline over F1-sweep's IRs, spec 0008 step 2: lanes sharing row lines
    taken from the page (`cv_0013` beside 0.36 -> 0.41, `darkdeck_0009`
    0.81 -> 0.85) open gaps in every lane wherever the other is taller, and
    rows proportional to the page's own (`darkdeck_0009` 0.93) make it
    3 to 6 times the source's height. Both look less like the page than this.

    A lane whose Zones all carry one fill is painted with it, so the source's
    sidebar is one strip and its aside one panel, not a stack of cards.
    """
    lanes: list[list[Zone]] = [[] for _ in range(region.lanes)]
    for zone in zones:
        assert zone.bbox is not None
        lanes[region.lane_of(zone.bbox)].append(zone)
    edges = [0.0, *region.splits, 1.0]

    parts = []
    for index, lane in enumerate(lanes):
        rows: dict[int, list[tuple[int, Zone]]] = {}
        placed = bands_from_boxes([zone.bbox for zone in lane if zone.bbox])
        for zone, (band, column) in zip(lane, placed):
            rows.setdefault(band, []).append((column, zone))
        style = f"flex:{(edges[index + 1] - edges[index]) * 100:.1f} 1 0"
        fills = {zone.fill for zone in lane}
        if lane and len(fills) == 1 and None not in fills:
            (fill,) = fills
            assert fill is not None
            style += f";background:{_rgb(fill)}"
        parts.append(
            f'<div class="lane" style="{style}">'
            + "".join(_band([z for _, z in sorted(rows[b], key=lambda r: r[0])],
                            document) for b in sorted(rows))
            + "</div>")
    return '<div class="columns">' + "".join(parts) + "</div>"


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

    **An empty cell votes neither way — measured 2026-09-25.** It used to vote
    against, and a sparse money column is mostly empty: `statement_0006`'s
    "Paid out" holds five amounts in forty rows, so it scored 5/40 and stayed
    left-aligned beside "Paid in" and "Balance", which are dense and did not.
    Counted over the cells that hold something it is **5 of 5**. Skipping the
    blanks right-aligns **42 cells** in that one document — 92 `.num` cells to
    134 — and clears all seven of its `right`-against-`left` disagreements with
    its source.

    **It moved `alignment_agreement` by exactly nothing, 0.935 to 0.935**, and
    that is a fact about the axis rather than about the change: a right-aligned
    cell in a cramped seven-column table has no slack between its ink and its
    box, so `scoring._alignment` reads it as `fill`. The ratio is a function of
    our own column widths as much as of our alignment. Gate this on a count of
    the named columns, in the DOM — see `docs/specs/0007-a2-measurements.md`.
    """
    counts: dict[int, list[int]] = {}
    for row in zone.rows:
        if row.role is not RowRole.DATA:
            continue
        for index, cell in enumerate(row.cells):
            seen = counts.setdefault(index, [0, 0, 0])
            seen[2] += 1
            if not cell.text.strip():
                continue
            seen[0] += 1
            if is_numeric(cell.text):
                seen[1] += 1
    return {index for index, (total, numeric, rows) in counts.items()
            if _speaks_for_its_column(total, rows) and numeric / total > 0.6}


def _speaks_for_its_column(filled: int, rows: int) -> bool:
    """Whether this many non-empty cells can decide a whole column.

    **One cell decides a column only when it *is* the column.** Skipping blanks
    lets a single value speak for a column it is a quarter of: `cv_0013`'s
    education table holds `2015` above three empty cells, and right-aligning
    the years on that evidence put ink where the source does not — eight cells
    across the corpus, on the one document whose table nobody had a reading
    for.

    A minimum of two would also have thrown away `invoice_0001`'s payment
    table, which has exactly one data row and belongs right-aligned. So the
    test is two cells **or** a column with nothing skipped, and measured over
    every table in the corpus it changes exactly the one case it is written
    for: eighteen table Zones, twenty-one right-aligned columns between them,
    and only `cv_0013`'s two years move.
    """
    return filled >= 2 or filled == rows


def _table(zone: Zone, document: Document) -> str:
    """Header rows into `<thead>`, data into `<tbody>`, summaries into `<tfoot>`.

    **Except a header row with data rows on both sides**, which is a section
    heading and stays where it is, inside `<tbody>`: `menu_0012`'s `From the
    grill`, `Main courses` and `Puddings` came back as rows 7, 12 and 19, each
    above its own dishes, and gathering them stacked all three above the first
    dish. A header with nothing after it still goes on top — that is
    `sample_table_0003`'s column header, which the model returned as its last
    row — **unless the table already opens with its header**, when a later one
    is a line of the table like any other: `receipt_0010`, read whole in Q5,
    opens with `Till 02` / `Order 00418` and ends with `THANK YOU — PLEASE
    CALL AGAIN`, and lifting that to the top put the farewell above the order.

    **Summaries go to `<tfoot>` only when nothing follows them.** The same
    receipt's `Subtotal` to `TOTAL` are followed by `Card`, `Change` and the
    payment lines, and gathering them at the foot drew the total below the
    change. Every other summary row in the corpus closes its table, so this
    moves no other document.
    """
    numeric = _numeric_columns(zone)
    roles = [row.role for row in zone.rows]
    data_at = [i for i, role in enumerate(roles) if role is RowRole.DATA]
    opening = next((i for i, role in enumerate(roles)
                    if role is not RowRole.HEADER), len(roles))
    closing = len(roles)
    while closing and roles[closing - 1] is RowRole.SUMMARY:
        closing -= 1

    groups: dict[RowRole, list[str]] = {role: [] for role in RowRole}
    for position, row in enumerate(zone.rows):
        tag = "th" if row.role is RowRole.HEADER else "td"
        cells = "".join(
            f'<{tag}{" class=\"num\"" if index in numeric else ""}>'
            f"{_cell(c, document)}</{tag}>"
            for index, c in enumerate(row.cells)
        )
        if row.role is RowRole.HEADER:
            between = bool(data_at) and data_at[0] < position < data_at[-1]
            in_place = position >= opening and (opening > 0 or between)
        else:
            in_place = row.role is RowRole.SUMMARY and position < closing
        groups[RowRole.DATA if in_place else row.role].append(
            f"<tr>{cells}</tr>")

    parts = []
    if groups[RowRole.HEADER]:
        parts.append(f"<thead{_header_style(zone, document)}>"
                     f"{''.join(groups[RowRole.HEADER])}</thead>")
    if groups[RowRole.DATA]:
        parts.append(f"<tbody>{''.join(groups[RowRole.DATA])}</tbody>")
    if groups[RowRole.SUMMARY]:
        parts.append(f"<tfoot>{''.join(groups[RowRole.SUMMARY])}</tfoot>")
    return f'<div class="table-wrap"><table>{"".join(parts)}</table></div>'


def _header_style(zone: Zone, document: Document) -> str:
    """The header row's measured fill, when the source draws one.

    Set as the `thead`'s own `--shade`, which `thead th` already paints, so
    `STYLESHEET` is untouched and no other document's bytes move. The ink is
    chosen against the fill the way a filled Zone's is — see `_readable_on` —
    which is what puts `nonlatin_0014`'s white-on-blue header back.
    """
    if zone.header_fill is None:
        return ""
    parts = [f"--shade:{_rgb(zone.header_fill)}"]
    ink = _readable_on(zone.header_fill,
                       document.style.ink if document.style else None)
    if ink is not None:
        parts.append(f"color:{_rgb(ink)}")
    return f' style="{";".join(parts)}"'


def _pairs(zone: Zone, document: Document) -> str:
    """One `dt` and one `dd` per pair; a pair with no value marks its label
    `alone`, which the stylesheet draws across both columns."""
    parts = []
    for pair in zone.pairs:
        label, value = _cell(pair.label, document), _cell(pair.value, document)
        tag = "<dt>" if value.strip() else '<dt class="alone">'
        parts.append(f"{tag}{label}</dt><dd>{value}</dd>")
    return '<dl class="pairs">' + "".join(parts) + "</dl>"


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
    """A Graphic is drawn from its own pixels; a Mark keeps its text.

    **Drawn since spec 0007 Phase A3, 2026-09-26.** A Graphic with pixels is an
    `<img>` of them, and whatever was read off it goes to `alt` — reachable,
    and not printed. Printed, it was invented text: `sparksuite` was
    `invoice_0001`'s only invented word and `logo` one of `receipt_0010`'s,
    because the page shows both only as pixels. Decided on entry with the
    measurement: both words leave, precision reaches 1.000 on both documents,
    and nothing else scored moves.

    The styling is on the elements rather than in `STYLESHEET`, because the
    stylesheet is inside every render and a rule added there changed the bytes
    of all fifteen documents to draw two of them.

    A Graphic with no pixels — a hand-built Zone, an IR read back from before
    A3 — keeps the placeholder, and a chart's title and axis labels there are
    still captured as a caption. Chart data is never reconstructed from
    geometry either way.
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

    if zone.pixels:
        read = " ".join(cell.text for block in zone.blocks for cell in block.lines)
        return (
            f'<figure style="margin:0" data-kind="{html.escape(kind)}"'
            f'{_bbox_attr(zone)}>'
            f'<img src="data:image/png;base64,{zone.pixels}"'
            f' alt="{html.escape(read or kind)}"'
            ' style="display:block;max-width:100%;height:auto"></figure>'
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
        # A size is only ever set smaller than `h1`'s own 1.6em — see
        # `style.heading_sizes` — so the stylesheet keeps the heading's weight
        # and margins and this changes only how large it is.
        size = f' style="font-size:{block.size:.2f}em"' if block.size else ""
        return f"<h1{size}>{_lines(block, document)}</h1>"
    if block.kind == "quote":
        return f"<blockquote>{_lines(block, document)}</blockquote>"
    if block.kind == "attribution":
        return f'<p class="attribution">{_lines(block, document)}</p>'
    return f"<p>{_lines(block, document)}</p>"


KEEPS_ITS_LINES = frozenset({"address"})
"""Block kinds whose line structure is content rather than an artefact of wrapping.

**Measured, not assumed — Phase A1, 2026-09-24.** Over the corpus, the extra
lines carried by every other kind sum *exactly* to the excess hard breaks the
scorer reports per document: `newsletter_0008` 30 paragraph + 1 heading = its
+31, `darkdeck_0009` 5 + 1 item = +6, `report_0011` 5 = +5,
`sample_semantic_0005` 3 + 1 quote = +4, `cv_0013` 1 = +1. All eight multi-line
`address` blocks sit in `invoice_0001`, `invoice_0002` and `receipt_0010` —
the three documents whose sources genuinely print 6, 3 and 9 hard breaks.

So reflowing everything but an address removes precisely the breaks the output
invented and leaves every break the page really has. A postal address, a set of
metric lines and a signature block read as lines; a paragraph does not.
"""


WORDLISTS = ("/usr/share/dict/words", "/usr/dict/words")
"""Where to look for a list of English words, in order. First one wins.

**A hyphen at a line end is ambiguous and the picture cannot resolve it.**
`newsletter_0008` breaks `con-` / `firmed`, where the hyphen exists only
because the line wrapped — the source DOM says `confirmed` — and in the same
document breaks `nine-` / `month`, where the hyphen is part of the compound and
the source says `nine-month`. Both look identical in the crop the model reads,
so nothing in the pixels tells them apart. Knowing which is which is knowing
the language, and that is what a word list is.

**Absent, every hyphen is kept**, which is the side where being wrong is free:
keeping one that should have gone leaves `con` and `firmed` exactly as they
score today, while dropping one that should have stayed turns `nine-month` into
`ninemonth` and costs two source words. Phase A1 measured that failure rather
than predicting it — the T1 ratchet caught `nine` on the first replay.
"""

_PREFIXES = ("re", "un", "pre", "sub", "non", "over", "under", "mis", "dis",
             "co", "inter", "anti")


@lru_cache(maxsize=1)
def _vocabulary() -> frozenset[str]:
    for path in WORDLISTS:
        try:
            with open(path, encoding="utf-8", errors="ignore") as handle:
                return frozenset(line.strip().lower() for line in handle
                                 if line.strip())
        except OSError:
            continue
    return frozenset()


def _is_a_word(candidate: str, vocabulary: frozenset[str] | None = None) -> bool:
    """Whether joining the two fragments spells something English.

    Light morphology on top of the list, because `web2` carries lemmas: it has
    `slipway` but not `slipways`, and `line` but not `relined`. Without the
    suffix and prefix steps the rule strips 3 of the corpus's 5 soft hyphens
    instead of 5, and with them it is right on all 15 cases measured — every
    soft hyphen dropped, every compound kept.
    """
    words = _vocabulary() if vocabulary is None else vocabulary
    if not words:
        return False
    word = candidate.lower()
    if word in words:
        return True
    for suffix in ("s", "es", "d", "ed", "ing", "ly"):
        if word.endswith(suffix) and word[: -len(suffix)] in words:
            return True
    for suffix in ("ed", "ing"):
        if word.endswith(suffix) and word[: -len(suffix)] + "e" in words:
            return True
    for prefix in _PREFIXES:
        if not word.startswith(prefix) or len(word) <= len(prefix) + 2:
            continue
        rest = word[len(prefix):]
        if rest in words:
            return True
        for suffix in ("d", "ed", "s"):
            if rest.endswith(suffix) and rest[: -len(suffix)] in words:
                return True
        for suffix in ("ed", "d"):
            if rest.endswith(suffix) and rest[: -len(suffix)] + "e" in words:
                return True
    return False


_LAST_WORD = re.compile(r"[^\W_]+\Z")
_FIRST_WORD = re.compile(r"\A[^\W_]+")

SPACE, TIGHT, DEHYPHENATE = "space", "tight", "dehyphenate"


def _how_to_join(previous: str, following: str) -> str:
    """How two wrapped lines are put back together.

    `SPACE` is the ordinary case — one line wrapped into the next and the words
    either side are whole. The other two are the cases where a word itself was
    cut, both measured in the corpus rather than imagined:

    - `TIGHT` for a **drop cap**. `newsletter_0008`'s masthead sets `T` in its
      own box, so the model reads a line of one letter and then `he stretch of
      towpath`. Joined with a space that scores as `t` and `he`; joined tight
      it is `the`. `TIGHT` also covers a **compound** whose own hyphen fell at
      the line end, where the hyphen is kept.
    - `DEHYPHENATE` for a **soft hyphen**, which is dropped.
    """
    if not previous or not following or not following[:1].islower():
        return SPACE
    if len(previous) == 1 and previous.isalpha():
        return TIGHT
    if not previous.endswith("-"):
        return SPACE
    tail = _LAST_WORD.search(previous[:-1])
    head = _FIRST_WORD.search(following)
    if tail and head and _is_a_word(tail.group() + head.group()):
        return DEHYPHENATE
    return TIGHT


_TRAILING_HYPHEN = re.compile(r"-(?=(?:</[a-z]+>)*\Z)")
"""The soft hyphen at the very end of a rendered line, past any closing tags.

Applied to rendered HTML rather than to `Cell.text`, because a corrected or
disputed cell renders wrapped in a `<span>` and the hyphen is then inside it.
"""


def _lines(block: Block, document: Document) -> str:
    """The block's lines, reflowed unless its kind keeps them.

    **Reflowing must not delete the per-line Cells** — they are what a
    Correction anchors to and what makes each reading a ground-truth label, so
    this joins `block.lines` for display only and leaves the IR alone. The IR
    embedded in the rendered file still carries one Cell per printed line.
    """
    rendered = [_cell(line, document) for line in block.lines]
    if block.kind in KEEPS_ITS_LINES or len(rendered) < 2:
        return "<br>".join(rendered)

    out = [rendered[0]]
    for previous, cell, piece in zip(block.lines, block.lines[1:], rendered[1:]):
        how = _how_to_join(previous.text.rstrip(), cell.text.lstrip())
        if how == DEHYPHENATE:
            out[-1] = _TRAILING_HYPHEN.sub("", out[-1])
            out.append(piece)
        elif how == TIGHT:
            out.append(piece)
        else:
            out.append(" " + piece)
    return _SEAM.sub("", "".join(out))


_SEAM = re.compile(r"</([a-z]+)><\1>")
"""Two adjacent elements of the same kind, left by a tight join.

**A rendering seam the picture cannot show you and the scorer can.** When a
word is cut across two marked lines — `...council con-` and `firmed on
Tuesday`, both marked `strong` — joining the rendered strings gives
`<strong>...con</strong><strong>firmed...</strong>`. The page reads
`confirmed` correctly, and `project()` still sees **two text nodes**, so T1
scores `con` and `firmed` and reports a word that is plainly printed as
missing.

Closing the seam merges them into one element and one text node. It can only
fire where two runs of one kind are directly adjacent with nothing between,
which a space join never produces — `</strong> <strong>` does not match.
"""


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
            f'title="also read as: {html.escape(alt)}">{_runs(cell)}</span>'
        )
    return _runs(cell)


TAG_FOR_RUN = {
    "link": "a", "code": "code", "strong": "strong", "em": "em", "mark": "mark",
}
"""Which element carries each Run kind.

These are `projection.INLINE_BY_TAG`'s own tags, so a Run rendered here is read
back as the same kind the source is read as. T6 compares the two projections
run for run, and a kind that only one side can express would score as a loss
however the page actually looks.
"""


def _runs(cell: Cell) -> str:
    """One Cell's text, with its marked spans wrapped in their elements.

    An unmarked Cell renders exactly as it did before Runs existed: `Cell.runs`
    returns a single `text` Run and this emits the escaped string and nothing
    else.

    The `<a>` carries no `href`. The output is a picture of a document, not a
    working hypertext — a link's *destination* was never read off the page and
    inventing one would put a guess in the output. What is being recorded is
    that the span is set apart as a link, which is what T6 asks.
    """
    runs = cell.runs
    if len(runs) == 1 and runs[0].kind == "text":
        return html.escape(runs[0].text)
    out = []
    for run in runs:
        text = html.escape(run.text)
        tag = TAG_FOR_RUN.get(run.kind)
        out.append(f"<{tag}>{text}</{tag}>" if tag else text)
    return "".join(out)


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
