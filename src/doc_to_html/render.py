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
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from functools import lru_cache
from itertools import groupby
from statistics import median
from typing import Any, Sequence

from . import furnish
from .ir import (BBox, Block, Cell, CellState, Document, Flow, Furniture, Kind,
                 Pair, Region, Role, Row, RowRole, Style, Zone)
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
.lane > :last-child { margin-bottom:0; }
/* A rectangle the page draws round a run of Zones in one lane, drawn once
   round the run. Spec 0011, step 1a — see `rhythm.frames`. */
.frame { border:1px solid var(--rule); border-radius:4px; margin-bottom:1.75rem; }
/* One Zone of a Continuation, holding its own margins, so the gap drawn before it is
   the page's and not that gap collapsed into a paragraph's. Spec 0011, 1b. */
.cont { display:flow-root; }
/* A `grid` Region: its Zones by row and by lane, never wrapped. Spec 0010, B1. */
.grid { display:grid; column-gap:2rem; row-gap:1.75rem; align-items:start;
        margin-bottom:1.75rem; }
.grid > * { min-width:0; }
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
/* A pairs Zone whose lines the page sets centred or flush right: each pair a
   line, label beside value, so the line can sit where the page sets it. */
dl.pairs.lines { display:block; }
dl.pairs.lines dt, dl.pairs.lines dd { display:inline; }
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
"""


def render(document: Document, *, title: str | None = None) -> str:
    """Render the IR to a complete, self-contained HTML document."""
    body = _body(document)
    framed = _page_frame(document)

    heading = title or _infer_title(document) or "Document"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(heading)}</title>\n"
        f"<style>{STYLESHEET}</style>\n"
        f"{_style_css(document)}"
        "</head>\n<body>\n"
        f'<div class="doc"{framed}>\n{"".join(filter(None, body))}\n</div>\n'
        f"{_embedded_ir(document)}\n</body>\n</html>\n"
    )


@dataclass(frozen=True)
class _Page:
    """What a gap read off the page is measured in — spec 0011, step 1a.

    `y` and `x` are source pixels per unit of a normalised box, and `body` the
    size the body is drawn at. The render is laid out in the source's pixels
    — `Style.body_px` is scaled from the rectified image to the source's
    width — so a gap measured on the page is drawn at that many CSS pixels.
    """

    y: float
    x: float
    body: float


def _page(document: Document) -> _Page:
    source = document.source
    wide = source.rectified_width or source.width
    tall = source.rectified_height or source.height
    scale = source.width / wide if wide else 1.0
    body = (document.style.body_px if document.style is not None
            and document.style.body_px else 16.0)
    return _Page(y=tall * scale, x=float(source.width), body=body)


ABOVE_INK = {"p": 0.31, "h1": 0.39, "table": 0.75, "dl": 0.31, "title": 0.88,
             "li": 0.31}
BELOW_INK = {"p": 0.62, "h1": 0.53, "table": 0.72, "dl": 0.25, "li": 0.22}
"""How far the stylesheet's boxes reach past their ink, in ems — measured.

Spec 0011, step 1a draws the page's own gap between two rows: the gap
between their ink, less what CSS adds round the ink on each side. The spec
probed it as one figure, 1.3 body ems for a paragraph over a paragraph. It
was re-measured on 2026-10-12, each element alone in headless Chrome with this
stylesheet, at 13 and 16px, from the first inked row to the box above and
from the last to the box below, margins included: a paragraph 0.31 above and
0.62 below, so 0.93 rather than 1.3; a heading 0.39 and 0.53 of its own size
(0.62 and 0.85 at the house 1.6em); a table 0.75 and 0.72; a pairs list
0.31 and 0.25; a Zone Title 0.88 of its own size above; a list item, inside
a list, 0.31 and 0.22. So the figure is subtracted per side, by what each
row opens and closes with.
"""

FILLED_PAD = 0.9
"""`section.filled > .zone-body`'s padding, in ems: a titled Zone with a fill
of its own reaches this much further below its ink."""


def _opens(zone: Zone) -> float:
    """What the stylesheet draws above a Zone's first ink, in ems of the body."""
    if zone.title:
        return ABOVE_INK["title"] * (zone.title_size or 0.95)
    if zone.kind is Kind.TABLE:
        return ABOVE_INK["table"]
    if zone.kind is Kind.PAIRS:
        return ABOVE_INK["dl"]
    if zone.kind is Kind.FIGURE:
        return 0.0
    first = zone.blocks[0] if zone.blocks else None
    if first is not None and first.kind == "heading":
        return ABOVE_INK["h1"] * (first.size or 1.6)
    return ABOVE_INK["p"]


def _closes(zone: Zone, *, plain: bool = False) -> float:
    """What the stylesheet draws below a Zone's last ink, in ems of the body."""
    padded = FILLED_PAD if (zone.title and zone.fill is not None
                            and not zone.boxed and not plain) else 0.0
    if zone.kind is Kind.TABLE:
        return BELOW_INK["table"] + padded
    if zone.kind is Kind.PAIRS:
        # A Zone drawn as fields ends on its last box or rule, which is ink.
        drawn = any(pair.marks for pair in zone.pairs)
        return (0.0 if drawn else BELOW_INK["dl"]) + padded
    if zone.kind is Kind.FIGURE:
        return padded
    last = zone.blocks[-1] if zone.blocks else None
    if last is not None and last.kind == "heading":
        return BELOW_INK["h1"] * (last.size or 1.6) + padded
    return BELOW_INK["p"] + padded


def _own_frame(zone: Zone) -> bool:
    """Whether the Zone is drawn as its own card, so its edge is its frame's."""
    return zone.boxed and zone.frame is not None


def _top(zone: Zone, page: _Page) -> float | None:
    """Where the Zone's drawn box begins on the page, in source pixels."""
    if _own_frame(zone):
        assert zone.frame is not None
        return zone.frame.top * page.y
    if zone.bbox is None:
        return None
    return zone.bbox.top * page.y - _opens(zone) * page.body


def _bottom(zone: Zone, page: _Page, *, plain: bool = False) -> float | None:
    """Where the Zone's drawn box ends on the page, in source pixels."""
    if _own_frame(zone):
        assert zone.frame is not None
        return zone.frame.bottom * page.y
    if zone.bbox is None:
        return None
    return zone.bbox.bottom * page.y + _closes(zone, plain=plain) * page.body


def _px(value: float) -> str:
    return f"{max(0.0, value):.0f}px"


def _index(document: Document, zone: Zone) -> int:
    """The Zone's place in the Document, by identity."""
    return next((i for i, z in enumerate(document.zones) if z is zone), -1)


def _line(item: Furniture, page: _Page, side: str | None = "top") -> str:
    """A rule or frame the page draws, as the border on `side` of the
    element it belongs to — all four for None — at its own width, style and
    colour. Spec 0012, G3a; see `furnish`."""
    style = item.style if item.style in ("dashed", "dotted", "double") else "solid"
    width = max(3 if style == "double" else 1, round(item.thickness * page.x))
    edge = "border" if side is None else f"border-{side}"
    return f"{edge}:{width}px {style} {_rgb(item.color)}"


def _strip(item: Furniture, page: _Page) -> str:
    """One rule drawn on its own: its border, or a dashed one's dashes at the
    period the page draws them, which a CSS dashed border does not keep."""
    if item.style == "dashed" and item.period:
        width = max(1, round(item.thickness * page.x))
        period = item.period * page.x
        return (f"height:{width}px;background:repeating-linear-gradient(90deg,"
                f"{_rgb(item.color)} 0 {period / 2:.1f}px,transparent "
                f"{period / 2:.1f}px {period:.1f}px)")
    return _line(item, page)


def _hatching(item: Furniture, page: _Page, prop: str = "background") -> str:
    """A hatched fill's two colours in stripes, at its angle and period. The
    period is measured along a row of pixels; a gradient's runs across its
    stripes, at 45 degrees to the row."""
    period = (item.period or 0.0) * page.x / math.sqrt(2) or 12.0
    half = period / 2
    return (f"{prop}:repeating-linear-gradient({item.angle or 45}deg,"
            f"{_rgb(item.color)} 0 {half:.1f}px,"
            f"{_rgb(item.second or item.color)} {half:.1f}px {period:.1f}px)")


def _middle(item: Furniture) -> float:
    return (item.bbox.top + item.bbox.bottom) / 2


def _span(zones: Sequence[Zone]) -> tuple[float, float] | None:
    """How far across the page a stack's Zones reach — what a rule drawn
    between them is measured against."""
    boxes = [zone.bbox for zone in zones if zone.bbox is not None]
    if not boxes:
        return None
    return min(b.left for b in boxes), max(b.right for b in boxes)


FULL = 0.02
"""How near each end of its stack, as a share of the stack's width, a rule
reaches to be drawn the stack's full width."""


def _rule_lines(rules: Sequence[Furniture], page: _Page,
                span: tuple[float, float] | None, below: float | None,
                after: float | None = None) -> list[str]:
    """Rules between two rows of a stack, top to bottom, each line at the
    height the page draws it: the rules beside one another on one line —
    `certificate_0021`'s two signature lines — drawn as one. `below` is where
    the next row starts, in source pixels, and `after`, where given, where
    the row above ends."""
    lines: list[list[Furniture]] = []
    for rule in sorted(rules, key=lambda r: r.bbox.top):
        if lines and rule.bbox.top <= max(r.bbox.bottom for r in lines[-1]):
            lines[-1].append(rule)
        else:
            lines.append([rule])
    out = []
    for at, line in enumerate(lines):
        bottom = max(r.bbox.bottom for r in line) * page.y
        following = lines[at + 1] if at + 1 < len(lines) else None
        to = (min(r.bbox.top for r in following) * page.y
              if following is not None else below)
        above = (_px(min(r.bbox.top for r in line) * page.y - after)
                 if after is not None and not at else "0")
        margin = (f"margin:{above} 0 {_px(to - bottom)}" if to is not None
                  else f"margin-top:{above}" if above != "0" else "")
        out.append(_rule_line(line, page, span, margin))
    return out


def _rule_line(line: list[Furniture], page: _Page,
               span: tuple[float, float] | None, margin: str) -> str:
    left = span[0] if span else min(r.bbox.left for r in line)
    right = span[1] if span else max(r.bbox.right for r in line)
    wide = max(right - left, 1e-6)
    pieces = sorted(line, key=lambda r: r.bbox.left)
    if (len(pieces) == 1 and pieces[0].bbox.left <= left + FULL * wide
            and pieces[0].bbox.right >= right - FULL * wide):
        style = ";".join(part for part in (_strip(pieces[0], page), margin) if part)
        return f'<div class="separator" style="{style}"></div>'
    parts = []
    cursor = left
    for rule in pieces:
        start, end = max(rule.bbox.left, cursor), min(rule.bbox.right, right)
        if end <= start:
            continue
        parts.append(f'<div style="margin-left:{(start - cursor) / wide * 100:.2f}%;'
                     f'width:{(end - start) / wide * 100:.2f}%;{_strip(rule, page)}"></div>')
        cursor = end
    return f'<div class="separator rules"{_styled(margin)}>{"".join(parts)}</div>'


def _page_frame(document: Document) -> str:
    """The frame the page draws round everything, as `.doc`'s border, with
    the space the page leaves inside it — `certificate_0021`."""
    frame = furnish.anchor(document).page
    inside = _union([z.bbox for z in document.zones if z.bbox is not None]) \
        if any(z.bbox is not None for z in document.zones) else None
    if frame is None or inside is None:
        return ""
    page = _page(document)
    width = max(1, round(frame.thickness * page.x))
    box = frame.bbox
    padding = (f"padding:{_px((inside.top - box.top) * page.y - width)} "
               f"{_px((box.right - inside.right) * page.x - width)} "
               f"{_px((box.bottom - inside.bottom) * page.y - width)} "
               f"{_px((inside.left - box.left) * page.x - width)}")
    return f' style="{_line(frame, page, None)};{padding}"'


@dataclass
class _Row:
    """One row of a stack — a band, a region, a frame — with where the page
    draws it, so the stack can put the page's gap after it."""

    cls: str
    inner: str
    zones: list[Zone]
    top: float | None
    bottom: float | None
    style: list[str] = field(default_factory=list)

    def markup(self, margin: float | None = None) -> str:
        style = list(self.style)
        if margin is not None:
            style.append(f"margin-bottom:{_px(margin)}")
        attribute = f' style="{";".join(style)}"' if style else ""
        return f'<div class="{self.cls}"{attribute}>{self.inner}</div>'


def _shared(document: Document) -> set[BBox]:
    """The frames more than one Zone is drawn inside — see `rhythm.frames`."""
    counts = Counter(zone.frame for zone in document.zones
                     if zone.frame is not None)
    return {frame for frame, count in counts.items() if count > 1}


def _units(zones: list[Zone]) -> list[list[Zone]]:
    """`zones` with each Continuation gathered into one unit, at its first member's
    place, members top to bottom — see `rhythm.groups`."""
    runs: dict[int, list[Zone]] = {}
    out: list[list[Zone]] = []
    for zone in zones:
        if zone.group is None:
            out.append([zone])
            continue
        if zone.group not in runs:
            runs[zone.group] = []
            out.append(runs[zone.group])
        runs[zone.group].append(zone)
    for unit in out:
        unit.sort(key=lambda z: z.bbox.top if z.bbox is not None else 0.0)
    return out


def _unit_box(unit: list[Zone]) -> BBox | None:
    boxes = [zone.bbox for zone in unit if zone.bbox is not None]
    if not boxes:
        return None
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def _band(units: list[list[Zone]], document: Document, page: _Page,
          plain: set[int]) -> _Row:
    """One row of side-by-side units. **A unit set flush right with others
    beside it** shrinks to its content and is pushed to the row's end, so the
    unit before it takes the room the page gives it — `Q3 2026 · INTERNAL`
    beside `Platform review`, `Account` beside the statement's title. **Each
    unit starts as far below the row's top as the page starts it**, so
    `Q3 2026 · INTERNAL` stands level with the Title beside it and `2021 —
    present` with its job, not with the heading above it."""
    starts = [_top(unit[0], page) for unit in units]
    known = [t for t in starts if t is not None]
    first = min(known) if known else None
    parts = []
    for position, (unit, start) in enumerate(zip(units, starts)):
        extra = []
        if first is not None and start is not None and start - first >= 1:
            extra.append(f"margin-top:{_px(start - first)}")
        if (len(units) > 1 and position == len(units) - 1
                and len(unit) == 1 and unit[0].align == "right"):
            extra.append("flex:0 1 auto;margin-left:auto")
        parts.append(_unit(unit, document, page,
                           plain=id(unit[0]) in plain, extra=";".join(extra)))
    zones = [zone for unit in units for zone in unit]
    tops = known
    bottoms = [b for unit in units
               if (b := _bottom(unit[-1], page, plain=id(unit[0]) in plain))
               is not None]
    return _Row("band", "".join(parts), zones,
                min(tops) if tops else None, max(bottoms) if bottoms else None)


def _gap(above: _Row, below: _Row) -> float | None:
    if above.bottom is None or below.top is None:
        return None
    return below.top - above.bottom


def _stack(rows: list[_Row], page: _Page, rules: Sequence[Furniture] = (),
           span: tuple[float, float] | None = None) -> list[str]:
    """Rows one under another, each followed by the gap the page leaves
    before the next — spec 0011, step 1a.

    The gap is the page's ink gap less what the stylesheet draws round the
    ink on either side (`ABOVE_INK`, `BELOW_INK`), or measured from a drawn
    box's edge where the row is one. **The house 1.75rem is the fallback**,
    for a row with no box to measure.

    **A rule the page draws between two rows splits the gap where it lies**
    — spec 0009, step D, 4b: a bordered `div`, not an `<hr>`, because
    `projection` counts an `<hr>` as a forced line break. A rule is drawn
    after a row when it lies between the bottom of everything drawn so far
    and the top of the next row, so a rule at a height some Zone already
    spans is never drawn through it; above the first row, or below the last,
    when it lies there. **Since spec 0012, G3a, every rule is one of
    `furnish`'s**, drawn as the page draws it — width, style, colour, and how
    far across `span` it runs — where spec 0009 drew `Document.separators`
    as the house's thin grey line, full width.
    """
    out: list[str] = []
    pending = sorted(rules, key=lambda r: r.bbox.top)
    above: float | None = None
    for index, row in enumerate(rows):
        boxes = [z.bbox for z in row.zones if z.bbox is not None]
        if index == 0 and pending and boxes:
            lead = [r for r in pending if _middle(r) <= min(b.top for b in boxes)]
            if lead:
                out += _rule_lines(lead, page, span, row.top)
        following = rows[index + 1] if index + 1 < len(rows) else None
        reach = max([b.bottom for b in boxes] + ([above] if above is not None else []),
                    default=None)
        drawn: list[Furniture] = []
        if pending and reach is not None:
            if following is None:
                drawn = [r for r in pending if _middle(r) >= reach]
            else:
                nexts = [z.bbox.top for z in following.zones if z.bbox is not None]
                if nexts:
                    drawn = [r for r in pending if reach <= _middle(r) <= min(nexts)]
        if not drawn:
            out.append(row.markup(None if following is None else _gap(row, following)))
        elif row.bottom is not None:
            out.append(row.markup(min(r.bbox.top for r in drawn) * page.y - row.bottom))
            out += _rule_lines(drawn, page, span,
                               following.top if following is not None
                               else max(r.bbox.bottom for r in drawn) * page.y)
        else:
            out.append(row.markup(None if following is None else _gap(row, following)))
            out += _rule_lines(drawn, page, span, None)
        if boxes:
            bottom = max(box.bottom for box in boxes)
            above = bottom if above is None else max(above, bottom)
    return out


def _framed(rows: list[_Row], document: Document, page: _Page,
            shared: set[BBox]) -> list[_Row]:
    """Consecutive rows whose every Zone is drawn inside one shared frame,
    gathered into that frame, drawn once round them — the card
    `darkdeck_0009` draws round OPEN RISKS and DECISIONS WANTED.

    Its padding is the page's: from the frame's edge to the first row's top,
    to the Zones' left edge, and from the last row's bottom. Its fill is its
    Zones' common fill, which they then do not paint again. Its border is the
    one the page draws, where `furniture` found it — spec 0012, G3a — and
    the rules inside it are drawn between its rows.
    """
    anchors = furnish.anchor(document)
    def frame_of(row: _Row) -> BBox | None:
        frames = {zone.frame for zone in row.zones}
        if len(frames) == 1:
            (frame,) = frames
            if frame in shared:
                return frame
        return None

    out: list[_Row] = []
    index = 0
    while index < len(rows):
        frame = frame_of(rows[index])
        if frame is None:
            out.append(rows[index])
            index += 1
            continue
        run = [rows[index]]
        while index + len(run) < len(rows) and frame_of(rows[index + len(run)]) == frame:
            run.append(rows[index + len(run)])
        index += len(run)
        zones = [zone for row in run for zone in row.zones]
        style = []
        fills = {zone.fill for zone in zones}
        if len(fills) == 1 and None not in fills:
            (fill,) = fills
            assert fill is not None
            style.append(f"background:{_rgb(fill)}")
            ink = _readable_on(fill, document.style.ink if document.style else None)
            if ink is not None:
                style.append(f"color:{_rgb(ink)}")
        top = frame.top * page.y
        bottom = frame.bottom * page.y
        lefts = [z.bbox.left for z in zones if z.bbox is not None]
        side = (min(lefts) - frame.left) * page.x if lefts else 0.0
        head = run[0].top - top if run[0].top is not None else 0.0
        foot = bottom - run[-1].bottom if run[-1].bottom is not None else 0.0
        style.append(f"padding:{_px(head)} {_px(side)} {_px(foot)}")
        drawn = anchors.frames.get(frame)
        if drawn is not None:
            style.append(_line(drawn, page, None))
        inside = [r for r in anchors.between if _within(r.bbox, frame)]
        out.append(_Row("frame", "".join(_stack(run, page, inside, _span(zones))),
                        zones, top, bottom, style))
    return out


def _within(box: BBox, outer: BBox) -> bool:
    middle_x, middle_y = (box.left + box.right) / 2, (box.top + box.bottom) / 2
    return outer.left <= middle_x <= outer.right and outer.top <= middle_y <= outer.bottom


def _body(document: Document) -> list[str]:
    """Every Band as a row, except where a `columns` Region reads down.

    **A page with no `columns` Region is drawn Band by Band.** Where there is
    one, its Zones leave the page's Bands and are drawn together, where the
    first of them would have been: each lane a stack of its own rows, read
    top to bottom, so `cv_0013`'s sidebar is no longer paired with whichever
    main-column item sits at its height. A `grid` Region is drawn the same
    way, as one grid — see `_grid`.

    **Spec 0011, step 1.** Every row is followed by the page's own gap (see
    `_stack`); a Continuation is drawn as one section (`_unit`); a frame a run of rows shares is drawn once round them
    (`_framed`).
    """
    page = _page(document)
    shared = _shared(document)
    plain = {id(zone) for zone in document.zones if zone.frame in shared}
    columns = [r for r in document.regions
               if r.flow in (Flow.COLUMNS, Flow.GRID)]
    home: dict[int, Region] = {}
    for zone in document.zones:
        for region in columns:
            if zone.bbox is not None and region.holds(zone.bbox):
                home[id(zone)] = region
                break

    later = {id(zone) for unit in _units(document.zones) for zone in unit[1:]}
    heads = {id(unit[0]): unit for unit in _units(document.zones)}
    rows: list[_Row] = []
    drawn: set[int] = set()
    for band in document.bands():
        outside = [heads[id(zone)] for zone in band
                   if id(zone) not in home and id(zone) not in later]
        if outside:
            rows.append(_band(outside, document, page, plain))
        for zone in band:
            held = home.get(id(zone))
            if held is None or id(held) in drawn:
                continue
            drawn.add(id(held))
            inside = [z for z in document.zones if home.get(id(z)) is held]
            if held.flow is Flow.GRID:
                rows.append(_grid(held, inside, document, page))
            else:
                rows.append(_columns(held, inside, document, page, shared, plain))
    # The rules drawn between the page's own rows: none a lane's, a grid's
    # or a shared frame's, which their own stacks draw or the page's never
    # reaches. Spec 0012, G3a.
    inner = [r for r in document.regions if r.flow in (Flow.COLUMNS, Flow.GRID)]
    rules = [rule for rule in furnish.anchor(document).between
             if not any(r.top <= _middle(rule) <= r.bottom for r in inner)
             and not any(_within(rule.bbox, frame) for frame in shared)]
    return _stack(_framed(rows, document, page, shared), page, rules,
                  _span(document.zones))


def _columns(region: Region, zones: list[Zone], document: Document,
             page: _Page, shared: set[BBox], plain: set[int]) -> _Row:
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
    sidebar is one strip and its aside one panel, not a stack of cards —
    unless a frame is drawn round them, which paints it. **Each lane starts
    as far down as the page starts it** (spec 0011, step 1a): `newsletter_0008`'s
    third column opens on a Title set below the first column's top line.
    """
    lanes: list[list[Zone]] = [[] for _ in range(region.lanes)]
    for zone in zones:
        assert zone.bbox is not None
        lanes[region.lane_of(zone.bbox)].append(zone)
    edges = [0.0, *region.splits, 1.0]

    stacks: list[list[_Row]] = []
    for lane in lanes:
        units = _units(lane)
        boxes = [_unit_box(unit) for unit in units]
        placed = bands_from_boxes([box for box in boxes if box is not None])
        rows: dict[int, list[tuple[int, list[Zone]]]] = {}
        for unit, (band, column) in zip([u for u, b in zip(units, boxes) if b],
                                        placed):
            rows.setdefault(band, []).append((column, unit))
        stacks.append(_framed(
            [_band([u for _, u in sorted(rows[b], key=lambda r: r[0])],
                   document, page, plain) for b in sorted(rows)],
            document, page, shared))

    # Spec 0012, G3a: each lane's own rules, and the rule down its left edge.
    anchors = furnish.anchor(document)
    number = next((i for i, r in enumerate(document.regions) if r is region), -1)
    held = [[r for r in anchors.between
             if furnish.container(r.bbox, document.regions) == (number, lane)]
            for lane in range(region.lanes)]
    dividers = {lane: rule for kept, lane, rule in anchors.lanes if kept is region}
    # Spec 0012, G4: a filled lane starts where its fill starts and keeps
    # the inset the page gives its type — `cv_0013`'s sidebar.
    painted = [_lane_fill(lane, document) for lane in lanes]
    heads: list[float | None] = []
    for stack, rules, ground in zip(stacks, held, painted):
        tops: list[float] = [stack[0].top] if stack and stack[0].top is not None else []
        if ground is not None:
            tops = [ground.top * page.y]
        first = [z.bbox.top for z in (stack[0].zones if stack else [])
                 if z.bbox is not None]
        if first:
            tops += [r.bbox.top * page.y for r in rules if _middle(r) <= min(first)]
        heads.append(min(tops) if tops else None)
    firsts = [head for head in heads if head is not None]
    start = min(firsts) if firsts else None
    parts = []
    for index, (lane, stack) in enumerate(zip(lanes, stacks)):
        style = f"flex:{(edges[index + 1] - edges[index]) * 100:.1f} 1 0"
        fills = {zone.fill for zone in lane}
        if (lane and len(fills) == 1 and None not in fills
                and not all(id(zone) in plain for zone in lane)):
            (fill,) = fills
            assert fill is not None
            style += f";background:{_rgb(fill)}"
        box = painted[index]
        if box is not None:
            entries = [b for z in lane for b in furnish._entries(z)
                       if box.left <= b.left]
            style += f";{_inset(box, entries, page, width=0)}"
        head = heads[index]
        if stack and start is not None and head is not None and head - start >= 1:
            style += (f";margin-top:{_px(head - start)}" if box is not None
                      else f";padding-top:{_px(head - start)}")
        divider = dividers.get(index)
        if divider is not None:
            inks = [z.bbox.left for z in lane if z.bbox is not None]
            gap = (min(inks) - divider.bbox.right) * page.x if inks else 0.0
            style += f";{_line(divider, page, 'left')};padding-left:{_px(gap)}"
        parts.append(f'<div class="lane" style="{style}">'
                     + "".join(_stack(stack, page, held[index], _span(lane)))
                     + "</div>")
    lasts = [stack[-1].bottom for stack in stacks
             if stack and stack[-1].bottom is not None]
    return _Row("columns", "".join(parts), list(zones), start,
                max(lasts) if lasts else None)


def _lane_fill(lane: list[Zone], document: Document) -> BBox | None:
    """The fill a lane's Zones all stand on, where the page draws one and
    `furniture` found it: its box. None for a lane on the page's ground."""
    fills = {zone.fill for zone in lane}
    if not lane or len(fills) != 1 or None in fills:
        return None
    (colour,) = fills
    assert colour is not None
    for item in document.furniture:
        if (item.kind == "fill" and item.style == "solid"
                and _apart(item.color, colour) <= COLOUR_APART
                and all(z.bbox is None or _within(z.bbox, item.bbox) for z in lane)):
            return item.bbox
    return None


def _grid(region: Region, zones: list[Zone], document: Document,
          page: _Page) -> _Row:
    """One `grid` Region: each Zone in the row and the lane the page puts it
    in, lanes as wide as the page draws them — spec 0010, step B1.

    **Drawn as a grid because a Band wraps.** `.band > *` asks 12rem of each
    Zone and wraps what does not fit, which is right for a row of unrelated
    blocks and wrong for a lattice the page draws: `darkdeck_0009`'s four
    metric tiles need more than the 52rem column and came out three and one.
    A grid's lanes are the page's own, so they cannot wrap, and a lane with
    no Zone in some row stays empty rather than letting the next one slide in.

    **Its rows are as far apart as the page sets them** (spec 0011, step 1a):
    the median of the gaps between its rows, a grid's gap being one figure.
    """
    edges = [0.0, *region.splits, 1.0]
    tracks = " ".join(f"minmax(0,{(edges[i + 1] - edges[i]) * 100:.1f}fr)"
                      for i in range(region.lanes))
    boxes = [zone.bbox for zone in zones if zone.bbox is not None]
    placed = bands_from_boxes(boxes)
    rows = sorted({band for band, _ in placed})
    copies = {band for band in rows
              if _copies([z for z, (b, _) in zip(zones, placed) if b == band])}
    cells = []
    for zone, (band, _) in zip(zones, placed):
        assert zone.bbox is not None
        row, lane = rows.index(band) + 1, region.lane_of(zone.bbox) + 1
        # Spec 0012, G4: copies in one row drawn one height, as the page
        # draws them — the cell stretches to the row, its card to the cell.
        stretched = ";align-self:stretch;display:grid" if band in copies else ""
        cells.append(((row, lane, zone.bbox.left),
                      f'<div style="grid-row:{row};grid-column:{lane}{stretched}">'
                      f'{_zone(zone, document)}</div>'))
    tops: dict[int, list[float]] = {}
    bottoms: dict[int, list[float]] = {}
    for zone, (band, _) in zip(zones, placed):
        if (top := _top(zone, page)) is not None:
            tops.setdefault(band, []).append(top)
        if (bottom := _bottom(zone, page)) is not None:
            bottoms.setdefault(band, []).append(bottom)
    gaps = [min(tops[b]) - max(bottoms[a]) for a, b in zip(rows, rows[1:])
            if tops.get(b) and bottoms.get(a)]
    style = [f"grid-template-columns:{tracks}"]
    if gaps:
        style.append(f"row-gap:{_px(float(median(gaps)))}")
    every_top = [t for ts in tops.values() for t in ts]
    every_bottom = [b for bs in bottoms.values() for b in bs]
    # In reading order in the markup too, not only on the screen: a reader
    # of the HTML — and `project()` — meets them row by row, left to right.
    return _Row("grid",
                "".join(markup for _, markup in sorted(cells, key=lambda c: c[0])),
                list(zones), min(every_top) if every_top else None,
                max(every_bottom) if every_bottom else None, style)


SAME_HEIGHT = 0.01
"""How far apart, as a share of the page's height, two cards' frames may
stand in height and still be copies drawn one height: `darkdeck_0009`'s
four tiles and `catalogue_0015`'s rows of cards are one height to the pixel."""


def _copies(row: list[Zone]) -> bool:
    """Whether a grid row is drawn cards of one height — spec 0012, G4."""
    frames = [z.frame for z in row if z.boxed and z.frame is not None]
    if len(row) < 2 or len(frames) != len(row):
        return False
    heights = [f.bottom - f.top for f in frames]
    return max(heights) - min(heights) <= SAME_HEIGHT


def _rgb(colour: tuple[int, int, int]) -> str:
    return f"rgb({colour[0]},{colour[1]},{colour[2]})"


def _toward(ink: tuple[int, int, int], ground: tuple[int, int, int],
            part: float) -> tuple[int, int, int]:
    """Ink moved `part` of the way toward the ground, as a colour."""
    near = [round(i + (g - i) * part) for i, g in zip(ink, ground)]
    return near[0], near[1], near[2]


def _mix(ink: tuple[int, int, int], ground: tuple[int, int, int], part: float) -> str:
    """Ink moved `part` of the way toward the ground.

    Muted text and rules are not measured — they are quieter versions of the
    ink, and the only thing that makes them quiet is how close to the ground
    they sit. Hard-coding them cannot work once the ground moves: `--muted:#666`
    is grey-on-white by design and near-invisible on `darkdeck_0009`'s black,
    while `--rule:#e0e0e0` stops being a hairline and becomes the brightest
    thing on that page.
    """
    return _rgb(_toward(ink, ground, part))


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
    # Spec 0009, step D, 4b — emitted only where there is a rule to draw, so a
    # page without one renders as it did. Since spec 0012, G3a, each rule
    # carries its own border: this is the place it takes in a gap nobody
    # measured, and a line of several rules side by side.
    if furnish.anchor(document).between:
        rules.append(".separator { margin:-0.875rem 0 0.875rem; }")
        rules.append(".rules { display:flex; } .rules > div { flex:none; }")
    if _has_fields(document):
        rules.extend(FIELD_CSS)
    if any(zone.kind is Kind.PAIRS and zone.align not in TEXT_ALIGN
           and _printed_lines(zone) is not None for zone in document.zones):
        rules.extend(PLACED_CSS)
    if any(_rows_read(zone) for zone in document.zones if zone.kind is Kind.TABLE):
        rules.extend(ROWS_CSS)
    if any(row.gap is not None for zone in document.zones for row in zone.rows):
        rules.extend(SPACED_CSS)
    if any(row.leader is not None and row.leader.kind != "none"
           for zone in document.zones for row in zone.rows):
        rules.extend(LEADER_CSS)

    style = document.style
    if style is None:
        return _wrap([], rules)

    # Spec 0010, step D1 — the body at the page's own size. Only `body`: every
    # other size is in ems of it, and `.doc`'s width is in rems, which it
    # leaves alone.
    if style.body_px is not None:
        # `--body` is what a Cell's measured size is in ems of (4a): an
        # element's own `em` is its parent's, and a footer's is 0.875 of it.
        rules.append(f"body {{ font-size:{style.body_px:g}px;"
                     f" --body:{style.body_px:g}px; }}")
    if style.face in FACE_CSS:
        rules.append(f"body {{ font-family:{FACE_CSS[style.face]}; }}")
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
                  document_ink: tuple[int, int, int] | None = None, *,
                  plain: bool = False, extra: str = "") -> str:
    """A Zone's measured fill, as an inline style.

    Inline rather than a class, because the colour is per Zone: one document can
    hold a white card, a grey card and a tinted one, and there is no fixed set
    of classes that covers what a page might do. The palette-wide values stay in
    custom properties on `:root`; only what varies Zone by Zone lands here.

    Carries more per-Zone facts for the same reason. **The ink is chosen
    against the Zone's own fill, not the page's ground** — see `_readable_on`.
    A Zone reserves the width its content needs, so the band wraps around
    it instead of clipping it — see `COLUMN_REM`. And its lines are set where
    the page sets them — `Zone.align`, spec 0011, step 1c.

    `plain` leaves the fill to a frame drawn round the Zone — see `_framed`.
    """
    parts = []
    if zone.fill is not None and not plain:
        parts.append(f"background:{_rgb(zone.fill)}")
        ink = _readable_on(zone.fill, document_ink)
        if ink is not None:
            parts.append(f"color:{_rgb(ink)}")
    reserved = _reserved(zone)
    if reserved:
        parts.append(f"min-width:min({reserved:g}rem,100%)")
    if zone.align in TEXT_ALIGN:
        parts.append(f"text-align:{TEXT_ALIGN[zone.align]}")
    if extra:
        parts.append(extra)
    return f' style="{";".join(parts)}"' if parts else ""


TEXT_ALIGN = {"centre": "center", "right": "right"}
"""`Zone.align` and `Zone.title_align` as CSS. Left is the house default and
draws nothing."""


def _inline_title_style(zone: Zone, extra: str = "") -> str:
    """The Title bar's measured fill, when the source draws one, the Title's
    printed size — spec 0010, step D2 — where its line sits over the
    Zone — spec 0011, step 1c — and the rules the page draws beside or
    under it — spec 0012, G3a."""
    rules = [extra] if extra else []
    if zone.title_fill is not None:
        rules.append(f"background:{_rgb(zone.title_fill)}")
    if zone.title_size is not None:
        rules.append(f"font-size:{zone.title_size:.2f}em")
    if zone.title_align in TEXT_ALIGN:
        rules.append(f"text-align:{TEXT_ALIGN[zone.title_align]}")
    return f' style="{";".join(rules)}"' if rules else ""


def _zone(zone: Zone, document: Document, *, plain: bool = False,
          extra: str = "") -> str:
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
    actually are. A Zone inside a frame it shares is drawn `plain`: the frame
    is its card.
    """
    return _section(zone, _zone_body(zone, document), document,
                    plain=plain, extra=extra)


def _section(zone: Zone, body: str, document: Document, *, plain: bool,
             extra: str) -> str:
    classes = f"zone zone-{zone.role.value}"
    if zone.boxed and not plain:
        classes += " boxed"
    elif zone.fill is not None and not plain:
        classes += " filled"

    own, titled, lead = _furnished(zone, document, plain=plain)
    # The Title's own ink, where it is not the one it would be drawn in.
    house = document.style.ink if document.style is not None else None
    if zone.fill is not None and not plain:
        house = _readable_on(zone.fill, house) or house
    if (zone.title_color is not None and house is not None
            and _apart(zone.title_color, house) > COLOUR_APART):
        titled = ";".join(part for part in (titled, f"color:{_rgb(zone.title_color)}")
                          if part)
    bar = ' class="zone-title barred"' if zone.title_fill else ' class="zone-title"'
    style_of = _inline_style(
        zone, document.style.ink if document.style else None,
        plain=plain, extra=";".join(part for part in (extra, own) if part))
    title = (
        f"<h2{bar}{_inline_title_style(zone, titled)}>{html.escape(zone.title)}</h2>"
        if zone.title else ""
    )
    if zone.title:
        body = f'<div class="zone-body">{body}</div>'
    return f'<section class="{classes}"{style_of}>{lead}{title}{body}</section>'


def _furnished(zone: Zone, document: Document, *,
               plain: bool) -> tuple[str, str, str]:
    """What the page draws on this Zone, from `furnish`: the section's own
    borders, its Title's, and a hatch drawn over its top — spec 0012, G3a.

    Each border keeps the space the page leaves between it and the type:
    a side bar's from the Zone's ink, a rule under the Zone from its last
    line, a frame from its entries — less what the stylesheet already draws
    round the ink. A Zone drawn as a card or a fill keeps the card's own
    padding inside its bar."""
    anchors = furnish.anchor(document)
    index = _index(document, zone)
    page = _page(document)
    own: list[str] = []
    titled: list[str] = []
    lead = ""
    box = zone.bbox
    entries = _union(furnish._entries(zone)) if furnish._entries(zone) else box
    padded = zone.boxed or (zone.fill is not None and not plain)

    if (zone.boxed and not plain and not zone.title and zone.frame is not None
            and index not in anchors.boxes):
        # Spec 0012, G4: a card keeps the inset the page gives it, from its
        # frame to its type — `catalogue_0015`'s cards, which a card with no
        # Title drew with its type against the border.
        own.append(_inset(zone.frame, furnish._entries(zone), page, zone))
    frame = anchors.boxes.get(index)
    if frame is not None and not plain:
        own.append(_line(frame, page, None))
        if not zone.boxed and entries is not None:
            width = max(1, round(frame.thickness * page.x))
            edge = frame.bbox
            own.append(
                f"padding:{_px((entries.top - edge.top) * page.y - width - _opens(zone) * page.body)} "
                f"{_px((edge.right - entries.right) * page.x - width)} "
                f"{_px((edge.bottom - entries.bottom) * page.y - width - _closes(zone) * page.body)} "
                f"{_px((entries.left - edge.left) * page.x - width)}")
    side = anchors.sides.get(index)
    if side is not None and box is not None:
        own.append(_line(side, page, "left"))
        if not padded:
            own.append(f"padding-left:{_px((box.left - side.bbox.right) * page.x)}")
    rule = anchors.tops.get(index)
    if rule is not None and entries is not None:
        own.append(_line(rule, page, "top"))
        own.append(f"padding-top:{_px((entries.top - rule.bbox.bottom) * page.y - _opens(zone) * page.body)}")
    rule = anchors.bottoms.get(index)
    if rule is not None and box is not None:
        own.append(_line(rule, page, "bottom"))
        own.append(f"padding-bottom:{_px((rule.bbox.top - box.bottom) * page.y - _closes(zone, plain=plain) * page.body)}")
    bar = anchors.title_sides.get(index)
    if bar is not None and box is not None:
        titled.append(_line(bar, page, "left"))
        if not zone.title_fill:
            titled.append(f"padding-left:{_px((box.left - bar.bbox.right) * page.x)}")
    rule = anchors.under_title.get(index)
    if rule is not None:
        titled.append(_line(rule, page, "bottom"))
    hatch = anchors.hatches.get(index)
    if hatch is not None:
        # A band across the top of the Zone's box, behind whatever the page
        # prints over it; the entries below it are pushed under it by the
        # Zone's own body — see `_below_hatch`.
        holder = zone.frame or box
        assert holder is not None
        own.append(_hatching(hatch, page, "background-image"))
        own.append(f"background-size:100% {_px((hatch.bbox.bottom - holder.top) * page.y)};"
                   "background-repeat:no-repeat")
    return ";".join(own), ";".join(titled), lead


def _inset(box: BBox, entries: list[BBox], page: _Page, zone: Zone | None = None,
           width: int = 1) -> str:
    """The padding that keeps a box's type where the page sets it inside
    it — spec 0012, G4: from the box's edge to its placed entries, less what
    the stylesheet draws round the ink and the box's own border. The right
    side is the left's: a line of type stops where it stops, not at the
    padding."""
    if not entries:
        return ""
    ink = _union(entries)
    above = _opens(zone) if zone is not None else 0.0
    below = _closes(zone) if zone is not None else 0.0
    side = _px((ink.left - box.left) * page.x - width)
    return (f"padding:{_px((ink.top - box.top) * page.y - width - above * page.body)} "
            f"{side} "
            f"{_px((box.bottom - ink.bottom) * page.y - width - below * page.body)} "
            f"{side}")


def _below_hatch(zone: Zone, document: Document,
                 tops: list[float | None]) -> tuple[int, str] | None:
    """The first of a Zone's entries, by their tops, that the page prints
    below a hatch across its top, with the margin that puts it there — spec
    0012, G3a. The entries above it are printed over the hatch."""
    if not document.furniture:
        return None
    hatch = furnish.anchor(document).hatches.get(_index(document, zone))
    if hatch is None:
        return None
    page = _page(document)
    holder = zone.frame or zone.bbox
    assert holder is not None
    last = holder.top
    for position, top in enumerate(tops):
        if top is None:
            continue
        if top >= hatch.bbox.bottom:
            return position, f"margin-top:{_px((top - last) * page.y - page.body)}"
        last = top + page.body / page.y
    return None


def _zone_body(zone: Zone, document: Document) -> str:
    if not zone.complete and zone.kind is not Kind.FIGURE:
        # A titled Zone keeps its caption even while its contents are pending,
        # so a Draft shows what is being worked on rather than an unlabelled box.
        return '<div class="skeleton"></div>'
    renderers = {
        Kind.TABLE: _table,
        Kind.PAIRS: _pairs,
        Kind.PROSE: _prose,
        Kind.LIST: _list,
        Kind.FIGURE: _figure,
    }
    return renderers[zone.kind](zone, document)


def _unit(unit: list[Zone], document: Document, page: _Page, *,
          plain: bool = False, extra: str = "") -> str:
    """One Zone, or a Continuation — Zones that continue one another —
    drawn as one section under the first one's Title — spec 0011, step 1b.
    See `rhythm.groups`.

    **The page's gap is kept between the members**, measured as between
    rows: a list Continuation is one `<ul>` whose item opening each member
    stands as far below the last as the page sets it, and a prose one is its members'
    blocks one after another, each in a `div` that holds its own margins.
    """
    if len(unit) == 1:
        return _zone(unit[0], document, plain=plain, extra=extra)
    head = unit[0]
    # Spec 0012, G3a: a rule the page draws between two members is drawn
    # between them — `cv_0013`'s rules under its sidebar's headings.
    rules = furnish.anchor(document).between if document.furniture else []
    box = _unit_box(unit)
    home = furnish.container(box, document.regions) if box is not None else None
    # Measured across the lane it is drawn in, as the lane's own rules are.
    span = _span([z for z in document.zones if z.bbox is not None
                  and furnish.container(z.bbox, document.regions) == home]
                 if home is not None else unit)

    def gap(upper: Zone, lower: Zone, ink: float) -> str:
        if upper.bbox is None or lower.bbox is None:
            return ""
        space = (lower.bbox.top - upper.bbox.bottom) * page.y - ink * page.body
        return f' style="margin-top:{_px(space)}"'

    def among(upper: Zone, lower: Zone) -> list[Furniture]:
        if upper.bbox is None or lower.bbox is None or span is None:
            return []
        return [r for r in rules
                if upper.bbox.bottom <= _middle(r) <= lower.bbox.top
                and r.bbox.left < span[1] and r.bbox.right > span[0]]

    if all(zone.kind is Kind.LIST and zone.complete for zone in unit):
        items = []
        for position, zone in enumerate(unit):
            listed = [b for b in zone.blocks if b.kind == "item"]
            within = _spacing(listed, page) if len(listed) == len(zone.blocks) else []
            for index, block in enumerate(listed):
                drawn = among(unit[position - 1], zone) if position and not index else []
                if drawn and zone.bbox is not None and unit[position - 1].bbox is not None:
                    rule, previous = drawn[0], unit[position - 1].bbox
                    assert previous is not None
                    spaced = _styled(
                        f"margin-top:{_px((rule.bbox.top - previous.bottom) * page.y - BELOW_INK['li'] * page.body)};"
                        f"{_line(rule, page)};"
                        f"padding-top:{_px((zone.bbox.top - rule.bbox.bottom) * page.y - ABOVE_INK['li'] * page.body)}")
                elif position and not index:
                    spaced = gap(unit[position - 1], zone,
                                 BELOW_INK["li"] + ABOVE_INK["li"])
                else:
                    spaced = _styled(within[index][0]) if within else ""
                items.append(f"<li{_li_style(block, document, spaced)}>"
                             f"{_lines(block, document)}</li>")
        body = f"<ul>{''.join(items)}</ul>"
    else:
        parts = [f'<div class="cont">{_zone_body(head, document)}</div>']
        for upper, lower in zip(unit, unit[1:]):
            drawn = among(upper, lower)
            if drawn and upper.bbox is not None and lower.bbox is not None:
                parts += _rule_lines(
                    drawn, page, span,
                    lower.bbox.top * page.y - _opens(lower) * page.body,
                    upper.bbox.bottom * page.y + _closes(upper, plain=True) * page.body)
                spaced = ' style="margin-top:0"'
            else:
                spaced = gap(upper, lower, _closes(upper, plain=True) + _opens(lower))
            parts.append(f'<div class="cont"{spaced}>'
                         f'{_zone_body(lower, document)}</div>')
        body = "".join(parts)
    return _section(head, body, document, plain=plain, extra=extra)


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
    ink = _house(document)
    read = _rows_read(zone)
    page = _page(document)
    places: list[bool] = []
    for position, row in enumerate(zone.rows):
        if row.role is RowRole.HEADER:
            between = bool(data_at) and data_at[0] < position < data_at[-1]
            places.append(position >= opening and (opening > 0 or between))
        else:
            places.append(row.role is RowRole.SUMMARY and position < closing)
    # The order rows are drawn in: what opens the table, its body, what closes it.
    drawn = [position for bucket in (RowRole.HEADER, RowRole.DATA, RowRole.SUMMARY)
             for position, row in enumerate(zone.rows)
             if (RowRole.DATA if places[position] else row.role) is bucket]
    spaced = any(row.gap is not None for row in zone.rows)
    # Spec 0012, G3a: the bars beside a cell, the rules over one that
    # `looks` did not draw, and a hatch behind a row.
    anchors = furnish.anchor(document) if document.furniture else None
    index_of = _index(document, zone)
    for position, row in enumerate(zone.rows):
        tag = "th" if row.role is RowRole.HEADER else "td"
        padding = ""
        if spaced:
            at = drawn.index(position)
            above = zone.rows[drawn[at - 1]] if at else None
            below = zone.rows[drawn[at + 1]] if at + 1 < len(drawn) else None
            padding = _row_padding(row, above, below, page)

        def styled(cell: Cell, number: int) -> str:
            looked = _look(cell, bold=row.role is not RowRole.DATA, house=ink)
            drawn = []
            if anchors is not None:
                bar = anchors.cell_lefts.get((index_of, position, number))
                if bar is not None:
                    drawn.append(_line(bar, page, "left"))
                rule = anchors.cell_tops.get((index_of, position, number))
                if rule is not None:
                    drawn.append(_line(rule, page, "top"))
            looked = ";".join(part for part in (looked, padding, *drawn) if part)
            return f' style="{looked}"' if looked else ""

        led = _leader(row, page)
        cells = "".join(
            f'<{tag}{" class=\"num\"" if index in numeric else ""}{styled(c, index)}>'
            + (f'<span class="leader" style="{led}">{_cell(c, document)}</span>'
               if led and c is row.cells[0] else _cell(c, document))
            + f"</{tag}>"
            for index, c in enumerate(row.cells)
        )
        in_place = places[position]
        hatch = anchors.rows.get((index_of, position)) if anchors else None
        styled_row = _row_style(row, page, opens=not in_place) if read else ""
        if hatch is not None:
            styled_row = _merged(styled_row, _hatching(hatch, page))
        groups[RowRole.DATA if in_place else row.role].append(
            f"<tr{styled_row}>{cells}</tr>")

    parts = []
    if groups[RowRole.HEADER]:
        parts.append(f"<thead{_header_style(zone, document)}>"
                     f"{''.join(groups[RowRole.HEADER])}</thead>")
    if groups[RowRole.DATA]:
        parts.append(f"<tbody>{''.join(groups[RowRole.DATA])}</tbody>")
    if groups[RowRole.SUMMARY]:
        parts.append(f"<tfoot>{''.join(groups[RowRole.SUMMARY])}</tfoot>")
    css = " ".join(name for name, on in (("read", read), ("spaced", spaced)) if on)
    table = f'<table class="{css}">' if css else "<table>"
    return f'<div class="table-wrap">{table}{"".join(parts)}</table></div>'


ROWS_CSS = (
    "table.read th, table.read td { border-bottom:none; }",
    "table.read thead th { background:none; }",
    "table.read tfoot td { border-top:none; }",
)
"""The stylesheet for a table whose lines and fills were read off the page
— spec 0011, step 4c: the house rule under every cell, shade on the header
and rule over the totals give way to each row's own. Emitted only for a page
that has one, so every other page keeps its bytes."""


LEADER_CSS = (
    ".leader { display:flex; align-items:baseline; }",
    '.leader::after { content:""; flex:1; min-width:0; margin-left:.3em;'
    " border-bottom:var(--leader); }",
)
"""A row's leader, run from its first entry to the end of its cell — spec
0011, step 4d. Emitted only for a page that has one. No minimum width: a
name that wraps leaves its leader no room rather than a stub, and the
column is sized as if it had none."""


FACE_CSS = {
    "serif": 'Georgia, "Times New Roman", serif',
    "mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
}
"""The family a page set in a serif or a mono face is drawn in — spec 0011,
step 4f; a sans page keeps the house's. Each stands its capitals near the
house's 0.7em, so the body's measured size holds: `style.EM_PER_GLYPH`."""


def _leader(row: Row, page: _Page) -> str:
    """The `--leader` a row's first cell draws, or empty. None where a cell
    with words stands between the first and the last: `menu_0012`'s notes,
    printed under each dish, are a column of the table beside it, and a
    leader would run into the note rather than to the price."""
    line = row.leader
    if line is None or line.kind == "none" or not row.cells:
        return ""
    if any(cell.text.strip() for cell in row.cells[1:-1]):
        return ""
    width = max(1, round(line.width * page.y))
    colour = _rgb(line.color) if line.color else "var(--muted)"
    return f"--leader:{width}px {line.kind} {colour}"


ROW_ABOVE, ROW_BELOW, ROW_BELOW_LOW = 0.35, 0.37, 0.20
"""How far a table row's line box reaches past its ink with no padding, in
ems — measured 2026-10-12 in headless Chrome with this stylesheet at 11, 13
and 16px: 0.31-0.38 above; below, 0.36-0.38, or 0.18-0.23 for a row whose
words reach below the baseline. Spec 0011, step 4e draws the page's gap
between rows less these."""

DESCENDERS = frozenset("gjpqy,;()")
"""Characters that reach below the baseline, so a row's ink ends lower."""

SPACED_CSS = (
    "table.spaced td, table.spaced th { padding-top:0; padding-bottom:0; }",
)
"""A table whose rows stand as far apart as the page sets them — spec 0011,
step 4e. Emitted only for a page that has one."""


def _between(upper: Row, lower: Row, page: _Page) -> float | None:
    """The space the page leaves between two rows' line boxes, in pixels, or
    None where the lower row's gap was not read."""
    if lower.gap is None:
        return None
    low = any(set(c.text) & DESCENDERS for c in upper.cells)
    ink = ROW_ABOVE + (ROW_BELOW_LOW if low else ROW_BELOW)
    return max(0.0, lower.gap * page.y - ink * page.body)


def _drawn_size(block: Block) -> float:
    """The size a Block is drawn at, in ems of the body: a heading's own,
    an attribution's, or the one most of its lines are measured at (4a)."""
    if block.kind == "heading":
        return block.size or 1.6
    sizes = Counter(round(cell.look.size, 2) for cell in block.lines
                    if cell.look is not None and cell.look.size is not None
                    and abs(cell.look.size - 1.0) >= SIZE_STEP)
    if sizes:
        size, count = sizes.most_common(1)[0]
        if count * 5 >= len(block.lines) * 3:
            return size
    return 0.85 if block.kind == "attribution" else 1.0


def _spacing(blocks: list[Block], page: _Page) -> list[tuple[str, bool]]:
    """Each Block's space above, and whether its own margin below gives way,
    so it stands as far below the one before as the page sets it — spec
    0011, step 4e, as `_between` does for rows: the gap between their ink
    less what each line box reaches past it, all above the lower Block. A
    gap not read keeps the house's margins."""
    over: list[float | None] = [None]
    for upper, lower in zip(blocks, blocks[1:]):
        if lower.gap is None:
            over.append(None)
            continue
        last = upper.lines[-1].text if upper.lines else ""
        below = ROW_BELOW_LOW if set(last) & DESCENDERS else ROW_BELOW
        ink = below * _drawn_size(upper) + ROW_ABOVE * _drawn_size(lower)
        over.append(max(0.0, lower.gap * page.y - ink * page.body))
    return [("" if space is None else f"margin-top:{_px(space)}",
             following is not None)
            for space, following in zip(over, over[1:] + [None])]


def _row_padding(row: Row, above: Row | None, below: Row | None, page: _Page) -> str:
    """A row's cells' padding, so the rows stand the page's gap apart: the
    space between two rows split between them, so a line the page draws
    between them falls in its middle, as `receipt_0010`'s dashed rules do.
    The first and last rows keep the house padding outside them, which step
    1 measures the table's own gap by; a gap not read keeps the house's."""
    over = _between(above, row, page) if above is not None else None
    under = _between(row, below, page) if below is not None else None
    top = ".45em" if over is None else _px(over / 2)
    bottom = ".45em" if under is None else _px(under / 2)
    return f"padding-top:{top};padding-bottom:{bottom}"


def _rows_read(zone: Zone) -> bool:
    return any(row.under is not None for row in zone.rows)


def _row_style(row: Row, page: _Page, *, opens: bool) -> str:
    """A row's own line and ground, as the page draws them: spec 0011, step
    4c. A row not read keeps the house rule, and a header that opens the
    table the house shade — one inside it, `menu_0012`'s `PUDDINGS`, never
    had it."""
    parts = []
    if row.under is None:
        parts.append("border-bottom:1px solid var(--rule)")
        if row.role is RowRole.HEADER and opens:
            parts.append("background:var(--shade)")
    else:
        if row.under.kind != "none":
            least = 3 if row.under.kind == "double" else 1
            width = max(least, round(row.under.width * page.y))
            colour = _rgb(row.under.color) if row.under.color else "var(--ink)"
            parts.append(f"border-bottom:{width}px {row.under.kind} {colour}")
        if row.fill is not None:
            parts.append(f"background:{_rgb(row.fill)}")
    return f' style="{";".join(parts)}"' if parts else ""


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


FIELD_CSS = (
    ".fields { display:grid; align-items:start; }",
    ".fields > .field { min-width:0; }",
    ".field > .label { display:block; font-size:.85em; line-height:1.25;"
    " color:var(--muted); white-space:nowrap; }",
    ".field > .box { border:1px solid var(--muted); padding:0 .4em; display:flex;"
    " align-items:center; white-space:nowrap; overflow:hidden; box-sizing:border-box; }",
    ".field > .comb { display:flex; }",
    ".field > .comb > span { border:1px solid var(--muted); display:flex;"
    " align-items:center; justify-content:center; flex:none; box-sizing:border-box; }",
    ".field > .ruled { border-bottom:1px solid var(--ink); display:flex;"
    " align-items:flex-end; padding-left:.2em; white-space:nowrap; box-sizing:border-box; }",
    ".field.option { display:flex; align-items:center; white-space:nowrap; }",
    ".tick { border:1px solid var(--ink); display:inline-flex; align-items:center;"
    " justify-content:center; font-size:.85em; line-height:1; flex:none;"
    " box-sizing:border-box; }",
    '.tick.on:empty::after { content:"\\2715"; }',
)
"""The stylesheet for fields — spec 0011, step 3c. Emitted only for a page
that draws one (`_style_css`), so every other page keeps its bytes."""

LANE_TOLERANCE = 1.0
"""Field edges within this many body ems of each other are one grid line."""

LABEL_ABOVE, LABEL_BELOW = 0.21, 0.15
"""How far a field label's line box reaches past its ink, in body ems —
measured 2026-10-12 in headless Chrome with `FIELD_CSS`, at 13 and 16px:
0.19-0.23 above; below, 0.08-0.13 for a label with a descender and
0.23-0.25 without. A gap read off the page is between inks, so these come
off it, as `ABOVE_INK` and `BELOW_INK` do between Zones."""


def _has_fields(document: Document) -> bool:
    return any(pair.marks for zone in document.zones for pair in zone.pairs)


def _lane_span(zone: Zone, document: Document) -> tuple[float, float]:
    """The left and right edges, normalised, of the lane the Zone is read
    in: as far as any Zone in it reaches. The fields grid spans the lane,
    so its lines fall where the page's do."""
    assert zone.bbox is not None
    mates = [zone]
    for region in document.regions:
        if region.holds(zone.bbox) and region.flow is not Flow.GRID:
            lane = region.lane_of(zone.bbox)
            mates = [z for z in document.zones if z.bbox is not None
                     and region.holds(z.bbox) and region.lane_of(z.bbox) == lane]
            break
    return (min(z.bbox.left for z in mates if z.bbox is not None),
            max(z.bbox.right for z in mates if z.bbox is not None))


def _union(boxes: list[BBox]) -> BBox:
    return BBox(min(b.left for b in boxes), min(b.top for b in boxes),
                max(b.right for b in boxes), max(b.bottom for b in boxes))


def _field(pair: Pair, document: Document, page: _Page) -> str:
    """One field: its label over its box, comb or rule; a tick box beside
    its option; or a signature line over its caption — as the page draws
    it. The value is the model's words; the mark is only drawn."""
    label, value = _cell(pair.label, document), _cell(pair.value, document)
    tone = _look(pair.label, sized=False, bold=True, house=_house(document, muted=True))
    if tone:
        label = f'<span style="{tone}">{label}</span>'
    held = _look(pair.value, sized=False, house=_house(document))
    if held and value:
        value = f'<span style="{held}">{value}</span>'
    marks = pair.marks
    if not marks:
        return (f'<div class="field"><span class="label">{label}</span>'
                f"<div>{value}</div></div>")
    first = marks[0]
    tall = (first.bbox.bottom - first.bbox.top) * page.y
    wide = (first.bbox.right - first.bbox.left) * page.x
    caption = pair.label.bbox
    if first.kind == "tick":
        on = " on" if first.ticked or pair.value.text.strip() else ""
        gap = (caption.left - first.bbox.right) * page.x if caption is not None else 5.0
        return (f'<div class="field option" style="gap:{_px(gap)}">'
                f'<span class="tick{on}" style="width:{_px(tall)};height:{_px(tall)}">'
                f"{value}</span><span>{label}</span></div>")
    if first.kind == "line" and caption is not None and first.bbox.bottom <= caption.top:
        below = (caption.top - first.bbox.bottom) * page.y - LABEL_ABOVE * page.body
        return (f'<div class="field"><div class="ruled" style="height:1px"></div>'
                f'<span class="label" style="margin-top:{_px(below)}">{label}</span></div>')
    under = 0.0
    if caption is not None:
        under = (first.bbox.top - caption.bottom) * page.y - LABEL_BELOW * page.body
    head = f'<span class="label" style="margin-bottom:{_px(under)}">{label}</span>'
    if first.kind == "comb":
        characters = pair.value.text.split()
        if len(characters) != first.count:
            characters = list(pair.value.text.replace(" ", ""))
        if len(characters) == first.count:
            spacing = tall / 8
            each = (wide - spacing * (first.count - 1)) / first.count
            boxes = "".join(
                f'<span style="width:{_px(each)};height:{_px(tall)}">'
                f"{html.escape(c)}</span>" for c in characters)
            return (f'<div class="field">{head}<div class="comb" style="gap:{_px(spacing)}">'
                    f"{boxes}</div></div>")
    if first.kind == "line":
        # The value sits on the first rule: one box from under the label to
        # the rule, the value at its foot.
        reach = tall
        if caption is not None:
            reach = (first.bbox.bottom - caption.bottom) * page.y - LABEL_BELOW * page.body
        rules = [f'<div class="ruled" style="height:{_px(reach)}">{value}</div>']
        for upper, lower in zip(marks, marks[1:]):
            step = (lower.bbox.bottom - upper.bbox.bottom) * page.y
            rules.append(f'<div class="ruled" style="height:{_px(step)}"></div>')
        return (f'<div class="field"><span class="label">{label}</span>'
                f'{"".join(rules)}</div>')
    return (f'<div class="field">{head}<div class="box" style="height:{_px(tall)}">'
            f"{value}</div></div>")


def _fields(zone: Zone, document: Document) -> str | None:
    """A pairs Zone the page draws as fields — spec 0011, step 3c: a grid
    whose lines are the page's, each field where the page puts it.

    The grid's lines are every field's left and right edge on the page,
    those within `LANE_TOLERANCE` of each other taken as one, and the
    lane's own edges; each track is as wide, in `fr`, as the page has it, so
    `form_0007`'s two half-width columns and its full-width fields fall
    where the page's do at any width. Fields stand in rows by where they
    sit, each row as far below the last as the page sets it, and a row of
    tick options flows as the page's does. A pair with nothing placed
    leaves the Zone to `_pairs`."""
    page = _page(document)
    anchors: list[BBox] = []
    for pair in zone.pairs:
        boxes = [b for b in (pair.label.bbox, pair.value.bbox) if b is not None]
        boxes += [mark.bbox for mark in pair.marks]
        if not boxes:
            return None
        anchors.append(_union(boxes))
    left, right = _lane_span(zone, document)
    left = min([left] + [a.left for a in anchors])
    right = max([right] + [a.right for a in anchors])
    tolerance = LANE_TOLERANCE * page.body / page.x
    lines: list[float] = []
    for edge in sorted([left, right] + [a.left for a in anchors]
                       + [a.right for a in anchors]):
        if not lines or edge - lines[-1] > tolerance:
            lines.append(edge)
    if len(lines) < 2:
        return None

    def line(edge: float) -> int:
        return min(range(len(lines)), key=lambda i: abs(lines[i] - edge)) + 1

    def opens_with_label(i: int) -> bool:
        pair = zone.pairs[i]
        if pair.label.bbox is None:
            return False
        if not pair.marks:
            return True
        return (pair.marks[0].kind != "tick"
                and pair.marks[0].bbox.top >= pair.label.bbox.bottom)

    order = sorted(range(len(anchors)), key=lambda i: (anchors[i].top, anchors[i].left))
    rows: list[list[int]] = []
    for i in order:
        if rows and anchors[i].top < min(anchors[j].bottom for j in rows[-1]):
            rows[-1].append(i)
        else:
            rows.append([i])
    parts = []
    for number, members in enumerate(rows, start=1):
        gap = 0.0
        if number > 1:
            gap = (min(anchors[i].top for i in members)
                   - max(anchors[j].bottom for j in rows[number - 2])) * page.y
            if any(opens_with_label(i) for i in members):
                gap -= LABEL_ABOVE * page.body
        members = sorted(members, key=lambda i: anchors[i].left)
        if all(zone.pairs[i].marks and zone.pairs[i].marks[0].kind == "tick"
               for i in members):
            # A row of tick options flows like the page's, each the page's
            # distance after the last: a track as wide as the page's text
            # overflows when ours sets it wider.
            spot = f"grid-row:{number};grid-column:1 / -1;display:flex"
            if gap:
                spot += f";margin-top:{_px(gap)}"
            edge = lines[0]
            options = []
            for i in members:
                after = (anchors[i].left - edge) * page.x
                options.append(f'<div style="margin-left:{_px(after)};flex:none">'
                               f"{_field(zone.pairs[i], document, page)}</div>")
                edge = anchors[i].right
            parts.append(f'<div style="{spot}">' + "".join(options) + "</div>")
            continue
        for i in members:
            start, end = line(anchors[i].left), line(anchors[i].right)
            end = max(end, start + 1)
            spot = f"grid-row:{number};grid-column:{start} / {end}"
            if gap:
                spot += f";margin-top:{_px(gap)}"
            parts.append(f'<div style="{spot}">{_field(zone.pairs[i], document, page)}</div>')
    tracks = " ".join(f"minmax(0,{(b - a) * page.x:.0f}fr)"
                      for a, b in zip(lines, lines[1:]))
    return (f'<div class="fields" style="grid-template-columns:{tracks}">'
            + "".join(parts) + "</div>")


def _pairs(zone: Zone, document: Document) -> str:
    """One `dt` and one `dd` per pair; a pair with no value marks its label
    `alone`, which the stylesheet draws across both columns, and a value
    whose label was its Zone's Title is drawn the same way — see
    `wire._without_title_echo`.

    **A pairs Zone the page sets centred or flush right is drawn as lines**
    — spec 0011, step 1c: each pair a line, its label beside its value, so
    `text-align` can put the line where the page does. `statement_0006`'s
    `Account 40-21-88 / 60114427` and `invoice_0001`'s `Invoice #: 123` are
    lines set flush right, not a two-column list."""
    if any(pair.marks for pair in zone.pairs) and zone.bbox is not None:
        drawn = _fields(zone, document)
        if drawn is not None:
            return drawn
    lines = zone.align in TEXT_ALIGN
    if not lines and (printed := _printed_lines(zone)) is not None:
        return _placed(zone, document, printed)
    summary = zone.role is Role.SUMMARY
    anchors = furnish.anchor(document) if document.furniture else None
    index, page = _index(document, zone), _page(document)
    pushed = _below_hatch(zone, document, [
        min((c.bbox.top for c in (pair.label, pair.value) if c.bbox is not None),
            default=None) for pair in zone.pairs])
    parts = []
    for position, pair in enumerate(zone.pairs):
        label, value = _cell(pair.label, document), _cell(pair.value, document)
        named: Cell | None = pair.label
        held: Cell | None = pair.value
        if not label.strip() and value.strip():
            label, value = value, ""
            named, held = pair.value, None

        def styled(cell: Cell | None, bold: bool = False, muted: bool = False) -> str:
            looked = _look(cell, bold=bold, house=_house(document, muted=muted))
            return f' style="{looked}"' if looked else ""

        dt, dd = styled(named, muted=True), styled(held, bold=summary)
        rule = anchors.pairs.get((index, position)) if anchors else None
        if rule is not None and not lines:
            # Spec 0012, G3a: a rule the page draws over this pair, across
            # both columns — `catalogue_0015`'s rule over each card's foot.
            drawn = f"{_line(rule, page)};padding-top:.4em;margin-top:.4em"
            dt = _merged(dt, drawn)
            dd = _merged(dd, drawn)
        if pushed is not None and pushed[0] == position:
            dt, dd = _merged(dt, pushed[1]), _merged(dd, pushed[1])
        if lines:
            parts.append(f"<div><dt{dt}>{label}</dt>"
                         + (f" <dd{dd}>{value}</dd>" if value.strip() else "")
                         + "</div>")
            continue
        tag = f"<dt{dt}>" if value.strip() else f'<dt class="alone"{dt}>'
        parts.append(f"{tag}{label}</dt><dd{dd}>{value}</dd>")
    css = "pairs lines" if lines else "pairs"
    return f'<dl class="{css}">' + "".join(parts) + "</dl>"


def _printed_lines(zone: Zone) -> list[list[tuple[Cell, bool]]] | None:
    """A pairs Zone's entries by the lines the page prints them on, each
    with whether it is a label — or None where a label and its value per
    line is what the page prints, and the `dl` draws it.

    Spec 0012, G4: `catalogue_0015`'s card prints price, unit and stock on
    one line, two pairs; its last card, and `cv_0013`'s registration, print
    a value under its label. Only where every entry is placed."""
    entries = [(c, c is pair.label, number) for number, pair in enumerate(zone.pairs)
               for c in (pair.label, pair.value) if c.text.strip()]
    if not entries or any(c.bbox is None for c, _, _ in entries):
        return None
    printed: list[list[tuple[Cell, bool, int]]] = []
    for entry in entries:
        box = entry[0].bbox
        assert box is not None
        if printed:
            band = printed[-1][0][0].bbox
            assert band is not None
            shared = min(box.bottom, band.bottom) - max(box.top, band.top)
            if shared >= 0.5 * min(box.bottom - box.top, band.bottom - band.top):
                printed[-1].append(entry)
                continue
        printed.append([entry])
    lines_of = {number: {index for index, line in enumerate(printed)
                         for _, _, n in line if n == number}
                for _, _, number in entries}
    if not (any(len({n for _, _, n in line}) > 1 for line in printed)
            or any(len(found) > 1 for found in lines_of.values())):
        return None
    return [[(c, label) for c, label, _ in line] for line in printed]


def _placed(zone: Zone, document: Document,
            printed: list[list[tuple[Cell, bool]]]) -> str:
    """A pairs Zone drawn line by line as the page prints it — spec 0012,
    G4: each entry starting where its box starts across the Zone's type,
    the last flush right where the page sets it there, and each line as
    far below the one before as the page sets it."""
    page = _page(document)
    boxes = [c.bbox for line in printed for c, _ in line if c.bbox is not None]
    left, right = min(b.left for b in boxes), max(b.right for b in boxes)
    wide = max(right - left, 1e-6)
    reach = page.body / page.x
    parts = []
    above: tuple[float, float] | None = None
    for line in printed:
        line = sorted(line, key=lambda entry: entry[0].bbox.left if entry[0].bbox else 0.0)
        shown = [c.bbox for c, _ in line if c.bbox is not None]
        starts = [b.left for b in shown]
        # Each entry's share of the line up to the next one's start; the
        # last as wide as it prints, so a face wider than the page's
        # squeezes the shares rather than breaking `In stock` in two.
        tracks = [f"{(b - a) / wide * 100:.2f}fr" for a, b in zip(starts, starts[1:])] + ["auto"]
        size = max((c.look.size or 1.0) if c.look else 1.0 for c, _ in line)
        style = [f"grid-template-columns:{' '.join(tracks)}"]
        if starts[0] - left > reach:
            style.append(f"margin-left:{(starts[0] - left) / wide * 100:.2f}%")
        top, bottom = min(b.top for b in shown), max(b.bottom for b in shown)
        if above is not None:
            gap = ((top - above[0]) * page.y
                   - (ROW_BELOW * above[1] + ROW_ABOVE * size) * page.body)
            style.append(f"margin-top:{_px(gap)}")
        spans = []
        for position, (c, label) in enumerate(line):
            looked = _look(c, house=_house(document, muted=label))
            box = c.bbox
            assert box is not None
            if position and position == len(line) - 1 and box.right >= right - reach:
                looked = ";".join(part for part in (looked, "justify-self:end") if part)
            css = ' class="label"' if label else ""
            spans.append(f"<span{css}{_styled(looked)}>{_cell(c, document)}</span>")
        parts.append(f'<div class="line" style="{";".join(style)}">{"".join(spans)}</div>')
        above = (bottom, size)
    return f'<div class="placed">{"".join(parts)}</div>'


PLACED_CSS = (
    ".placed .line { display:grid; align-items:baseline; column-gap:.3em; }",
    ".placed .label { color:var(--muted); }",
)
"""A pairs Zone drawn by its printed lines — spec 0012, G4. Emitted only
for a page that has one."""


def _merged(attribute: str, css: str) -> str:
    """A ` style="..."` attribute with `css` added to it."""
    if not attribute:
        return f' style="{css}"'
    return attribute[:-1] + f';{css}"'


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
    spacing = dict(zip(map(id, zone.blocks), _spacing(zone.blocks, _page(document))))
    for key, ruled in _ruled(zone, document).items():
        spacing[key] = (ruled, spacing[key][1])
    parts = []
    for is_item, run in groupby(zone.blocks, key=lambda b: b.kind == "item"):
        if is_item:
            listed = list(run)
            items = "".join(f"<li{_li_style(b, document, _styled(spacing[id(b)][0]))}>"
                            f"{_lines(b, document)}</li>" for b in listed)
            # The list's own margin below gives way, as a paragraph's does.
            closed = spacing[id(listed[-1])][1]
            parts.append(f"<ul{_styled('margin-bottom:0' if closed else '')}>"
                         f"{items}</ul>")
        else:
            for b in run:
                above, closed = spacing[id(b)]
                parts.append(_block(b, document, ";".join(
                    part for part in (above, "margin-bottom:0" if closed else "")
                    if part)))
    return "".join(parts)


def _styled(css: str) -> str:
    return f' style="{css}"' if css else ""


def _ruled(zone: Zone, document: Document) -> dict[int, str]:
    """The Blocks a rule the page draws stands over, by id, each with the
    style that draws it — spec 0012, G3a: the space from the Block above
    to the rule, the rule, and the space from it to the Block's own ink,
    each less what the line boxes reach past the ink, as `_spacing` takes
    it. `certificate_0021`'s signature lines, `cv_0013`'s sidebar rules."""
    if not document.furniture:
        return {}
    anchors = furnish.anchor(document)
    index = _index(document, zone)
    page = _page(document)
    out: dict[int, str] = {}
    for position, block in enumerate(zone.blocks):
        rule = anchors.blocks.get((index, position))
        if rule is None or not position:
            continue
        uppers = [c.bbox for c in zone.blocks[position - 1].lines if c.bbox is not None]
        lowers = [c.bbox for c in block.lines if c.bbox is not None]
        if not uppers or not lowers:
            continue
        upper, lower = _union(uppers), _union(lowers)
        above = (rule.bbox.top - upper.bottom) * page.y \
            - ROW_BELOW * _drawn_size(zone.blocks[position - 1]) * page.body
        below = (lower.top - rule.bbox.bottom) * page.y \
            - ROW_ABOVE * _drawn_size(block) * page.body
        out[id(block)] = (f"margin-top:{_px(above)};{_line(rule, page)};"
                          f"padding-top:{_px(below)}")
    return out


def _list(zone: Zone, document: Document) -> str:
    """Items only, and deliberately nothing else.

    Kept separate from `_prose` rather than routed through it. Dropping a
    non-item block is the point: a LIST Zone that comes back as paragraphs
    renders an empty `<ul>`, which is visible as the mis-read it is. `_prose`
    keeps every block because there nothing has claimed the region is a list.
    """
    listed = [b for b in zone.blocks if b.kind == "item"]
    # Spaced only where every Block is drawn: a gap is from the Block before.
    spacing = ([above for above, _ in _spacing(listed, _page(document))]
               if len(listed) == len(zone.blocks) else [""] * len(listed))
    ruled = _ruled(zone, document) if len(listed) == len(zone.blocks) else {}
    spacing = [ruled.get(id(b), above) for b, above in zip(listed, spacing)]
    items = "".join(
        f"<li{_li_style(b, document, _styled(above))}>{_lines(b, document)}</li>"
        for b, above in zip(listed, spacing)
    )
    return f"<ul>{items}</ul>"


FIGURE_PLACE = {"centre": ";margin:0 auto", "right": ";margin-left:auto"}
"""A picture is a block, which `text-align` does not move: it is set centred
or flush right by its margins — `receipt_0010`'s barcode, `invoice_0002`'s
logo. Spec 0011, step 1c."""


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
            ' style="display:block;max-width:100%;height:auto'
            f'{FIGURE_PLACE.get(zone.align or "", "")}"></figure>'
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


SIZE_STEP = 0.15
"""A Cell's measured size is drawn only this far from the body or more —
spec 0011, step 4a. Over the labelled Cells the measure is within 0.12 of
the source's size nine times in ten; inside that it is noise."""


COLOUR_APART = 60
"""Channel-sum by which an entry's measured ink must differ from the colour
its element is drawn in for the render to draw it — spec 0011, step 4b.
Over the 649 labelled Cells of the ten screenshots the measured ink is
within 2 of the colour Chrome drew nine times in ten and within 18 nineteen
in twenty; the nearest true difference from a page's ink is
`statement_0006`'s green credit figures, 69."""


def _apart(one: tuple[int, int, int], other: tuple[int, int, int]) -> int:
    return sum(abs(a - b) for a, b in zip(one, other))


def _house(document: Document, *, muted: bool = False) -> tuple[int, int, int]:
    """The colour an element is drawn in when no entry says otherwise: the
    page's ink, or for a muted element — a `dt`, an attribution, a field's
    label — the ink a third of the way to the ground, as `--muted` is."""
    style = document.style or Style()
    return _toward(style.ink, style.page_bg, 0.33) if muted else style.ink


def _look(cell: Cell | None, *, sized: bool = True, bold: bool = False,
          house: tuple[int, int, int] | None = None) -> str:
    """The inline style for how the page prints one entry — spec 0011,
    step 4: its size against the page's body, and bold or italic **where
    the page sets it and the stylesheet does not**. Never removes a weight
    or a slant the house style draws: the measure misses less than it
    invents in that direction. `sized` is False where the element already
    has its own size (a heading); `bold` is True where it is already bold.
    `house` is the colour the element is drawn in otherwise: the entry's
    own is drawn where it differs by more than `COLOUR_APART` (4b). A chip
    carries its own colour — see `_chip`."""
    look = cell.look if cell is not None else None
    if look is None:
        return ""
    parts = []
    if sized and look.size is not None and abs(look.size - 1.0) >= SIZE_STEP:
        parts.append(f"font-size:calc({look.size:.2f} * var(--body, 1em))")
    if look.bold and not bold:
        parts.append("font-weight:700")
    if look.italic:
        parts.append("font-style:italic")
    if (house is not None and look.color is not None and look.fill is None
            and _apart(look.color, house) > COLOUR_APART):
        parts.append(f"color:{_rgb(look.color)}")
    return ";".join(parts)


def _common_colour(cells: list[Cell], house: tuple[int, int, int] | None) -> str:
    """One colour for a block of lines: the middle of theirs, where most of
    its lines are within `COLOUR_APART` of it and it is that far from the
    house colour."""
    if house is None or not cells:
        return ""
    inks = [cell.look.color for cell in cells
            if cell.look is not None and cell.look.color is not None
            and cell.look.fill is None]
    if not inks:
        return ""
    middle = (int(median(i[0] for i in inks)), int(median(i[1] for i in inks)),
              int(median(i[2] for i in inks)))
    near = sum(1 for ink in inks if _apart(ink, middle) <= COLOUR_APART)
    if near * 5 < len(cells) * 3 or _apart(middle, house) <= COLOUR_APART:
        return ""
    return f"color:{_rgb(middle)}"


def _common_look(cells: list[Cell], *, sized: bool = True,
                 house: tuple[int, int, int] | None = None) -> str:
    """One style for a block of lines: the one most of its lines have, or
    none — a paragraph is set in one face, and a line measured otherwise is
    more likely noise than a change of face mid-paragraph."""
    if not cells:
        return ""
    styles = Counter(_look(cell, sized=sized) for cell in cells)
    style, count = styles.most_common(1)[0]
    shape = style if count * 5 >= len(cells) * 3 else ""
    return ";".join(part for part in (shape, _common_colour(cells, house)) if part)


def _li_style(block: Block, document: Document, spaced: str = "") -> str:
    """A list item's `style`, its own look added to any it already has."""
    looked = _common_look(block.lines, house=_house(document))
    if not looked:
        return spaced
    if spaced:
        return spaced[:-1] + ";" + looked + '"'
    return f' style="{looked}"'


def _block(block: Block, document: Document, spacing: str = "") -> str:
    if block.kind == "heading":
        # A size is only ever set smaller than `h1`'s own 1.6em — see
        # `style.heading_sizes` — so the stylesheet keeps the heading's weight
        # and margins and this changes only how large it is.
        looked = _common_look(block.lines, sized=False, house=_house(document))
        size = f"font-size:{block.size:.2f}em" if block.size else ""
        both = ";".join(part for part in (size, looked, spacing) if part)
        return f"<h1{_styled(both)}>{_lines(block, document)}</h1>"
    looked = _common_look(block.lines, house=_house(
        document, muted=block.kind == "attribution"))
    style = _styled(";".join(part for part in (looked, spacing) if part))
    if block.kind == "quote":
        return f"<blockquote{style}>{_lines(block, document)}</blockquote>"
    if block.kind == "attribution":
        return f'<p class="attribution"{style}>{_lines(block, document)}</p>'
    return f"<p{style}>{_lines(block, document)}</p>"


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
    return _chip(cell, _runs(cell), document)


def _chip(cell: Cell, inner: str, document: Document) -> str:
    """The chip a Cell is printed on, when the page prints it on one — a
    badge, a pill, a code tag: spec 0011, step 4b. Its fill, its ink, and
    the padding and corner the page gives it, round the Cell's words."""
    look = cell.look
    if look is None or look.fill is None or look.chip is None or cell.bbox is None:
        return inner
    page, chip, box = _page(document), look.chip, cell.bbox
    across = ((box.left - chip.left) + (chip.right - box.right)) / 2 * page.x
    down = ((box.top - chip.top) + (chip.bottom - box.bottom)) / 2 * page.y
    corner = (look.radius or 0.0) * (chip.bottom - chip.top) * page.y
    parts = [f"background:{_rgb(look.fill)}", f"padding:{_px(down)} {_px(across)}",
             f"border-radius:{_px(corner)}"]
    if look.color is not None:
        parts.append(f"color:{_rgb(look.color)}")
    return f'<span class="chip" style="{";".join(parts)}">{inner}</span>'



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
