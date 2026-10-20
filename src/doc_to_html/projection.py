"""What a reader perceives on a page, read off the browser — one view, both sides.

`project()` is applied to `example/foo.html` and to the `document.html` a
Conversion produced, and the two results are diffed. It is deliberately **one
function**: a source-side reader and an output-side reader would drift, and the
first thing they would disagree about is whatever the current change is trying to
move.

**It must never compare raw markup, and this is the rule the whole measure rests
on.** Demanding that the output reproduce the source's `div` nesting or its
Bootstrap class names would be a worse overfit than the typed-reference harness
spec 0007 exists to escape — it would make "look like the document" mean "be
typed like the document". So what comes back here is *perception*:

- the text, in reading order, whitespace collapsed;
- a **role** per block, taken from what it looks like as much as from its tag —
  a `div` set in bold at 1.4x the body size is a `heading` here, exactly as an
  `h2` is, because a reader cannot tell them apart and neither should this;
- an **inline kind** per run, taken the same way — monospace is `code` whether
  it arrived as `<code>` or as a class on a `span`;
- **rectangles from the browser's own client rects**, which are where the ink
  actually landed rather than where a stylesheet said to put it.

Nothing here reads a tag name without also accepting the appearance that tag
usually produces, and nothing reads a class name at all.

## Two things that are measured rather than assumed

**The colour scheme is pinned to light.** Headless Chrome on this machine
inherits the host's dark mode — measured: `prefers-color-scheme: dark` matches
by default — so `render.py`'s dark block fired and every rendered page this
project has eyeballed was inverted. `--blink-settings=preferredColorScheme=1`
turns that off, and both sides of every comparison go through it.

**The payload comes back base64.** `--dump-dom` HTML-escapes the text content it
prints, so a JSON payload containing `<style>` — which several of these
documents do, as a code span — comes back with `&lt;` in it and parses as
different text than the page holds. Encoding sidesteps the question rather than
unescaping and hoping the escaping was the escaping we thought.
"""

from __future__ import annotations

import base64
import json

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
"""The one renderer already on this machine. See `available()` before using it."""

LIGHT = "--blink-settings=preferredColorScheme=1"
"""Pin `prefers-color-scheme` to light, on both sides of every comparison.

Not a preference. `tools/inspect_run.py` shelled out with no colour-scheme flag,
so it inherited the host's dark mode and `render.py`'s
`@media (prefers-color-scheme: dark)` fired — which means every visual
comparison eyeballed in this project before 2026-09-18 was against an inverted
page, while the Source Image beside it was light. Measured on this machine:
without the flag `matchMedia('(prefers-color-scheme: dark)').matches` is `true`.
"""

_FLAGS = ["--headless", "--disable-gpu", "--hide-scrollbars", LIGHT,
          "--no-sandbox", "--disable-lcd-text", "--font-render-hinting=none"]

TIMEOUT_S = 120

MIN_WIDTH = 500
"""The narrowest window headless Chrome will actually honour, measured.

Asked for 200, 300, 340, 400, 450 or 480, it lays the page out at **500** and
says so through `clientWidth`; only 520 and above come back as asked. The
screenshot, meanwhile, is cropped to the width that *was* asked for — so a
narrow document silently becomes a 500px layout with its right-hand side cut
off, and a projection of the same page reports rectangles the picture does not
contain. `receipt_0010` was authored at 340 and lost every price in its right
column to exactly this before the guard existed.

Every entry point clamps to it and records a note rather than failing, because
the honest answer is that the page was measured wider than requested and both
sides of the comparison need to know.
"""

FILLS_THE_COLUMN = 0.80
"""How much of its column a line must occupy before it counts as wrapped.

Calibrated against the `<br>` counts of the corpus itself, which is the one
place the true answer is known by construction: `example/invoice.html` prints
six explicit breaks and `example/sample-semantic.html` prints none, so a
threshold is right when it reports six and zero. A wrapped line gives up at
most one word's width to the edge of its column; a line broken on purpose
typically stops less than half way across.
"""


def available() -> bool:
    """Whether the browser this module needs is on this machine."""
    return CHROME.is_file()


MEASURE = r"""
(() => {
  // Our own commentary, never part of the document. `render.py` put a
  // findings panel at the top of a page until spec 0012 moved it into
  // `report.html`, and every frozen document before that still carries one;
  // counting it as content would report the system's own diagnostics as text
  // the model invented, on exactly the runs that went worst.
  const CHROME_SELECTORS = ['.findings'];

  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD']);

  // Tag to role, for the tags whose meaning a reader can actually see. The map
  // is a shortcut, not the definition: anything not in it is decided by
  // appearance below, so an output that reaches the same look by other markup
  // scores the same.
  const ROLE_BY_TAG = {
    H1: 'heading', H2: 'heading', H3: 'heading', H4: 'heading',
    H5: 'heading', H6: 'heading',
    TH: 'header-cell', TD: 'cell', LI: 'item', DT: 'term', DD: 'definition',
    CAPTION: 'caption', FIGCAPTION: 'caption', BLOCKQUOTE: 'quote',
    PRE: 'code-block', ADDRESS: 'paragraph', P: 'paragraph',
  };

  const INLINE_BY_TAG = {
    A: 'link', CODE: 'code', KBD: 'code', SAMP: 'code', TT: 'code',
    EM: 'em', I: 'em', STRONG: 'strong', B: 'strong', MARK: 'mark',
    SUP: 'sup',
  };

  const chrome = new Set();
  for (const selector of CHROME_SELECTORS) {
    for (const node of document.querySelectorAll(selector)) {
      chrome.add(node);
      for (const inner of node.querySelectorAll('*')) chrome.add(inner);
    }
  }

  const px = (value) => parseFloat(value) || 0;
  const isInline = (style) => style.display.startsWith('inline');
  const mono = (family) => /mono|courier|menlo|consolas|monaco/i.test(family);

  const bodyStyle = getComputedStyle(document.body);
  const bodyPx = px(bodyStyle.fontSize) || 16;

  function blockOf(node) {
    let element = node.parentElement;
    while (element && element !== document.body) {
      const style = getComputedStyle(element);
      if (!isInline(style)) return element;
      element = element.parentElement;
    }
    return element || document.body;
  }

  function roleOf(element) {
    const named = ROLE_BY_TAG[element.tagName];
    if (named) return named;
    const style = getComputedStyle(element);
    // Appearance, for everything the tag map does not name. A container set
    // bolder and larger than the body is a heading to a reader whatever it was
    // typed as, and this is the clause that lets a `div.panel-title` in the
    // source and an `h2.zone-title` in the output be the same thing.
    const size = px(style.fontSize);
    const weight = parseInt(style.fontWeight, 10) || 400;
    if (size >= bodyPx * 1.12 && weight >= 600) return 'heading';
    if (weight >= 600 && size >= bodyPx * 1.02) return 'heading';
    if (mono(style.fontFamily)) return 'code-block';
    return 'paragraph';
  }

  function inlineOf(node, block) {
    const blockStyle = getComputedStyle(block);
    let element = node.parentElement;
    let found = 'text';
    while (element && element !== block) {
      const tagged = INLINE_BY_TAG[element.tagName];
      if (tagged) { found = tagged; break; }
      element = element.parentElement;
    }
    if (found !== 'text') return found;

    // Appearance again, so a run styled rather than tagged still counts. The
    // comparison is always against the block the run sits in, never against an
    // absolute: a whole heading being bold does not make its words `strong`.
    const inner = node.parentElement;
    if (!inner || inner === block) return 'text';
    const style = getComputedStyle(inner);
    if (!isInline(style)) return 'text';
    if (mono(style.fontFamily) && !mono(blockStyle.fontFamily)) return 'code';
    if (style.textDecorationLine.includes('underline')
        && style.color !== blockStyle.color) return 'link';
    if (style.color !== blockStyle.color
        && /pointer/.test(style.cursor)) return 'link';
    const weight = parseInt(style.fontWeight, 10) || 400;
    const blockWeight = parseInt(blockStyle.fontWeight, 10) || 400;
    if (weight >= blockWeight + 200) return 'strong';
    if (style.fontStyle === 'italic' && blockStyle.fontStyle !== 'italic') {
      return 'em';
    }
    const ground = style.backgroundColor;
    if (ground && ground !== 'rgba(0, 0, 0, 0)'
        && ground !== blockStyle.backgroundColor) return 'mark';
    return 'text';
  }

  // Rectangles gathered into the lines a reader sees.
  //
  // `getClientRects()` returns one rect per line box *per inline element*, so
  // a sentence with a code span in it comes back as three rects on one line —
  // and the code span's rect does not share a top with the text around it,
  // because it is set at a different size. Merging on equal tops therefore
  // counted one line as two, which made every source page with an inline
  // code span report hard line breaks it does not have.
  //
  // Merged on vertical overlap instead: two rects are the same line when they
  // share more than half the height of the shorter one.
  function linesFrom(rects) {
    const kept = [...rects].filter((r) => r.width > 0 || r.height > 0)
                           .sort((a, b) => a.top - b.top);
    const lines = [];
    for (const rect of kept) {
      const last = lines[lines.length - 1];
      if (last) {
        const overlap = Math.min(last[3], rect.bottom) - Math.max(last[1], rect.top);
        const shorter = Math.min(last[3] - last[1], rect.height);
        if (shorter > 0 && overlap > 0.5 * shorter) {
          last[0] = Math.min(last[0], rect.left);
          last[1] = Math.min(last[1], rect.top);
          last[2] = Math.max(last[2], rect.right);
          last[3] = Math.max(last[3], rect.bottom);
          continue;
        }
      }
      lines.push([rect.left, rect.top, rect.right, rect.bottom]);
    }
    return lines;
  }

  function unionOf(rects) {
    const lines = linesFrom(rects);
    if (!lines.length) return null;
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    for (const [x0, y0, x1, y1] of lines) {
      l = Math.min(l, x0); t = Math.min(t, y0);
      r = Math.max(r, x1); b = Math.max(b, y1);
    }
    return {rect: [l, t, r, b], lines: lines.length,
            tops: lines.map((line) => Math.round(line[1])), boxes: lines};
  }

  const runs = [];
  const blocks = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  let order = 0;
  while ((node = walker.nextNode())) {
    const text = node.textContent.replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName) || chrome.has(parent)) continue;
    if (parent.closest('script, style, noscript, template')) continue;
    const style = getComputedStyle(parent);
    if (style.display === 'none' || style.visibility === 'hidden') continue;

    const range = document.createRange();
    range.selectNodeContents(node);
    const measured = unionOf(range.getClientRects());
    if (!measured) continue;

    const block = blockOf(node);
    if (!blocks.has(block)) {
      const box = block.getBoundingClientRect();
      const blockStyle = getComputedStyle(block);
      blocks.set(block, {
        index: blocks.size,
        role: roleOf(block),
        tag: block.tagName.toLowerCase(),
        font_px: px(blockStyle.fontSize),
        weight: parseInt(blockStyle.fontWeight, 10) || 400,
        italic: blockStyle.fontStyle === 'italic',
        mono: mono(blockStyle.fontFamily),
        box: [box.left, box.top, box.right, box.bottom],
        color: blockStyle.color,
        background: blockStyle.backgroundColor,
        texts: [],
        rects: [],
        lineRects: [],
      });
    }
    const record = blocks.get(block);
    record.texts.push(text);
    record.rects.push(measured.rect);
    // Kept per block as well as per run, because a forced line break is a
    // property of the block: it is one of its lines ending early with more
    // lines below it, and a run that is only part of a line cannot see that.
    // Merged across the block's runs at the end, for the same reason
    // `linesFrom` merges within one: a line is a line however many text nodes
    // it took to write it.
    for (const box of measured.boxes) {
      record.lineRects.push({left: box[0], top: box[1], right: box[2],
                             bottom: box[3], width: box[2] - box[0],
                             height: box[3] - box[1]});
    }

    runs.push({
      order: order++,
      text: text,
      role: record.role,
      inline: inlineOf(node, block),
      block: record.index,
      rect: measured.rect,
      lines: measured.lines,
      font_px: px(style.fontSize),
    });
  }

  const blockList = [...blocks.values()].map((record) => {
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    for (const [x0, y0, x1, y1] of record.rects) {
      l = Math.min(l, x0); t = Math.min(t, y0);
      r = Math.max(r, x1); b = Math.max(b, y1);
    }
    const lines = linesFrom(record.lineRects);
    return {
      index: record.index, role: record.role, tag: record.tag,
      text: record.texts.join(' '), ink: [l, t, r, b], box: record.box,
      lines: lines.length, font_px: record.font_px, weight: record.weight,
      italic: record.italic, mono: record.mono,
      color: record.color, background: record.background,
      line_boxes: lines,
    };
  });

  // Break elements the page actually draws.
  //
  // A `br` and an `hr` are the page saying "end this line here whatever the
  // column does", which is the exact thing `Block.lines` joined by `<br>`
  // makes unavoidable. Counted as elements because the geometry cannot tell
  // them apart from a line shortened by a float: `sample_semantic_0005`'s
  // prose runs beside an aside, so its lines stop at 441 of a 760px container
  // and read as broken when they are merely narrow. This is not the markup
  // comparison the scorer is forbidden — no nesting and no class name is
  // being demanded — it is a typographic instruction a reader can see.
  let breakElements = 0;
  for (const element of document.querySelectorAll('br, hr')) {
    if (chrome.has(element)) continue;
    const style = getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    breakElements += 1;
  }

  const figures = [];
  for (const element of document.querySelectorAll('img, svg, canvas, figure')) {
    if (chrome.has(element)) continue;
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const drawn = element.tagName === 'IMG'
      ? (element.complete && element.naturalWidth > 0)
      : element.tagName !== 'FIGURE';
    figures.push({
      tag: element.tagName.toLowerCase(),
      rect: [rect.left, rect.top, rect.right, rect.bottom],
      drawn: drawn,
    });
  }

  // The page's own height, not the viewport's. `scrollHeight` is
  // `max(viewport, content)`, so a short page measured in a tall window comes
  // back as the window — which would make every height ratio a statement about
  // the flag we passed. The body's border box plus its bottom margin is what
  // the browser would actually paint, and the ink's own bottom is the floor
  // under it for a page whose body collapses.
  const bodyBox = document.body.getBoundingClientRect();
  const bodyBottom = bodyBox.bottom + px(bodyStyle.marginBottom);
  let inkBottom = 0;
  for (const block of blockList) inkBottom = Math.max(inkBottom, block.ink[3]);
  for (const figure of figures) inkBottom = Math.max(inkBottom, figure.rect[3]);

  // Content the page draws but does not show.
  //
  // A corpus document that clips its own text is unusable as ground truth:
  // the words are in the DOM, so the projection reports them and T1 demands
  // the model read them, but they are not in the picture the model is shown.
  // `newsletter_0008` did exactly this — its three balanced columns overflowed
  // by one line, which is invisible in the page height and obvious in the PNG.
  let clipped = 0;
  for (const element of document.querySelectorAll('*')) {
    if (chrome.has(element)) continue;
    const style = getComputedStyle(element);
    if (style.overflow === 'visible' && style.overflowY === 'visible'
        && style.overflowX === 'visible') continue;
    if (style.display === 'none') continue;
    // Only content counts. `menu_0012`'s decorative rule is a zero-height
    // `hr` whose ornament is drawn by a `::after`, so its scrollHeight is 11
    // against a clientHeight of 0 — overflowing, and hiding nothing a reader
    // or the scorer will ever ask for.
    if (!element.textContent.trim()
        && !element.querySelector('img, svg, canvas')) continue;
    if (element.scrollHeight > element.clientHeight + 2
        || element.scrollWidth > element.clientWidth + 2) clipped += 1;
  }

  const payload = {
    clipped: clipped,
    width: document.documentElement.scrollWidth,
    height: Math.ceil(Math.max(bodyBottom, inkBottom)),
    body_font_px: bodyPx,
    body_color: bodyStyle.color,
    body_background: bodyStyle.backgroundColor,
    break_elements: breakElements,
    runs: runs,
    blocks: blockList,
    figures: figures,
  };

  const pre = document.createElement('pre');
  pre.id = '__projection';
  pre.textContent = btoa(
    String.fromCharCode(...new TextEncoder().encode(JSON.stringify(payload)))
  );
  document.documentElement.appendChild(pre);
})();
"""


FLATTEN = r"""
(() => {
  // Spec 0018, 0b: the source measured in its paper's frame. A transform
  // moves no layout, so a page turned, skewed or set in perspective by its
  // own CSS is measured as it lies before the turn; a pure translation (and a
  // scale) stays. `getClientRects` returns upright boxes round tilted lines,
  // which stood `ticket_0020`'s `TRD` 15px above `OSL`.
  const turned = (value) => {
    if (!value || value === 'none') return false;
    const numbers = value.slice(value.indexOf('(') + 1, -1).split(',').map(parseFloat);
    const at = value.startsWith('matrix3d') ? [1, 2, 3, 4, 6, 7, 8, 9, 11] : [1, 2];
    return at.some((index) => Math.abs(numbers[index] || 0) > 1e-9);
  };
  for (const element of document.querySelectorAll('*')) {
    const style = getComputedStyle(element);
    if (turned(style.transform)) element.style.setProperty('transform', 'none', 'important');
    if (style.rotate && style.rotate !== 'none') element.style.setProperty('rotate', 'none', 'important');
    if (style.perspective && style.perspective !== 'none') {
      element.style.setProperty('perspective', 'none', 'important');
    }
  }
})();
"""
"""Run before `MEASURE` on a source page — `project(..., flat=True)`.

Which matrix entries turn a page: in `matrix(a, b, c, d, e, f)` the
off-diagonal `b` and `c`; in `matrix3d`, column-major, every off-diagonal
entry of the linear part and the three perspective terms. `rotate` and
`perspective` are their own properties and are cleared outright.
"""


@dataclass(frozen=True)
class Run:
    """One text node as it was actually drawn: what it says and where it landed."""

    order: int
    text: str
    role: str
    inline: str
    block: int
    rect: tuple[float, float, float, float]
    lines: int
    font_px: float


@dataclass(frozen=True)
class Block:
    """One block of the page — the thing a reader would call a paragraph.

    `ink` is the union of its runs' client rects and `box` is its border box.
    Both are kept because alignment is the difference between them: text sitting
    at the right-hand end of a full-width container is right-aligned, and no
    single rectangle can say so.
    """

    index: int
    role: str
    tag: str
    text: str
    ink: tuple[float, float, float, float]
    box: tuple[float, float, float, float]
    lines: int
    font_px: float
    weight: int
    italic: bool
    mono: bool
    color: str
    background: str
    line_boxes: tuple[tuple[float, float, float, float], ...] = ()
    """One rectangle per line of the block, top to bottom.

    This is what makes a forced break visible. A wrapped line fills its measure
    and the next one starts under it; a line that stops a third of the way
    across with more text below was broken by something in the markup rather
    than by the edge of the column.
    """

    @property
    def forced_breaks(self) -> int:
        """Lines that end well short of the column with more text beneath them.

        Measured against the **container's** width, not against the block's own
        widest line. The block's own widest line was the first thing tried and
        it cannot see the case that matters: three address lines of roughly
        equal length are all within a few percent of each other, so none of
        them looks early, while every one of them is a hard break. The column
        is the thing a wrapped line fills and a broken line does not.

        Width rather than right edge, so centred and right-aligned text are
        judged the same way as left-aligned text.

        The last line is never counted. Every paragraph's last line ends early;
        that is what a paragraph is.
        """
        if len(self.line_boxes) < 2:
            return 0
        column = self.box[2] - self.box[0]
        if column <= 0:
            return 0
        return sum(
            1 for box in self.line_boxes[:-1]
            if (box[2] - box[0]) < FILLS_THE_COLUMN * column
        )


@dataclass(frozen=True)
class Figure:
    """An image-shaped thing, and whether it actually has pixels in it.

    `drawn` is false for `render.py`'s dashed `figure.omitted` placeholder and
    for an `img` that failed to load, which are the two ways a logo goes missing.
    """

    tag: str
    rect: tuple[float, float, float, float]
    drawn: bool


@dataclass(frozen=True)
class Projection:
    """One page as a reader perceives it. The only thing the scorer compares."""

    width: int
    height: int
    body_font_px: float
    body_color: str
    body_background: str
    break_elements: int
    """Rendered `br` and `hr` elements — line breaks the column did not cause."""

    clipped: int
    """Elements hiding some of their own content behind a non-visible overflow.

    Nonzero on a *source* document means it is not usable as ground truth: the
    text is in the DOM and not in the picture, so the scorer would demand the
    model read something it was never shown."""

    runs: tuple[Run, ...]
    blocks: tuple[Block, ...]
    figures: tuple[Figure, ...]
    label: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        """Everything the page says, in reading order, one line per run."""
        return "\n".join(run.text for run in self.runs)

    @property
    def aspect(self) -> float:
        return self.height / self.width if self.width else 0.0


class ProjectionError(RuntimeError):
    """The browser did not answer, so there is nothing to compare."""


def _run_chrome(html: str, width: int, height: int, *, flat: bool = False
                ) -> dict[str, Any]:
    injected = _inject(html, flat=flat)
    with tempfile.TemporaryDirectory() as work:
        target = Path(work) / "measured.html"
        target.write_text(injected, encoding="utf-8")
        result = subprocess.run(
            [str(CHROME), *_FLAGS, "--virtual-time-budget=5000", "--dump-dom",
             f"--window-size={width},{height}", target.resolve().as_uri()],
            capture_output=True, timeout=TIMEOUT_S,
        )
    dom = result.stdout.decode("utf-8", "replace")
    opening = 'id="__projection">'
    start = dom.find(opening)
    if start < 0:
        raise ProjectionError(
            "the browser returned no projection: "
            f"{result.stderr.decode('utf-8', 'replace')[:400]}"
        )
    start += len(opening)
    encoded = dom[start:dom.find("</pre>", start)].strip()
    payload: dict[str, Any] = json.loads(base64.b64decode(encoded))
    return payload


def _inject(html: str, *, flat: bool = False) -> str:
    """Put the measuring script in, wherever the document lets us.

    Appended to `</body>` when there is one and to the end otherwise, because
    `render.py` always writes one and a hand-authored page might not. With
    `flat`, `FLATTEN` runs first.
    """
    script = (
        "<script>window.addEventListener('load', () => {"
        + (FLATTEN if flat else "") + MEASURE + "});</script>"
    )
    if "</body>" in html:
        return html.replace("</body>", script + "</body>", 1)
    return html + script


def project(html: Path | str, *, width: int, height: int = 3000,
            label: str = "", flat: bool = False) -> Projection:
    """Read one page the way a reader sees it, at a stated width.

    `width` is always the **source document's** width, on both sides. A page
    compared against itself at two different widths is comparing two different
    pages: line wrapping, column stacking and total height all move. This is the
    "matched width" the comparison report is built on.

    `height` is the viewport the browser is given, not a constraint on the page —
    it is returned to 3000 so nothing short is clipped mid-measurement, and the
    page's own `scrollHeight` is what comes back as `Projection.height`.

    `flat` measures the page in its paper's frame, every turning transform
    cleared first (`FLATTEN`) — spec 0018, 0b. The scorer sets it on the
    source side only: the corpus's ground truth is its HTML, and a render is
    drawn level, so a turn the source sets on itself would otherwise be
    scored as the conversion's fault.
    """
    if not available():
        raise ProjectionError(f"no headless Chrome at {CHROME}")
    text = html.read_text(encoding="utf-8") if isinstance(html, Path) else html
    notes: list[str] = []
    if width < MIN_WIDTH:
        notes.append(
            f"asked for {width}px but the browser lays out no narrower than "
            f"{MIN_WIDTH}px; measured at {MIN_WIDTH}px"
        )
        width = MIN_WIDTH
    payload = _run_chrome(text, width, height, flat=flat)

    def rect(values: Any) -> tuple[float, float, float, float]:
        left, top, right, bottom = (float(value) for value in values)
        return left, top, right, bottom

    runs = tuple(
        Run(order=int(item["order"]), text=str(item["text"]),
            role=str(item["role"]), inline=str(item["inline"]),
            block=int(item["block"]), rect=rect(item["rect"]),
            lines=int(item["lines"]), font_px=float(item["font_px"]))
        for item in payload["runs"]
    )
    blocks = tuple(
        Block(index=int(item["index"]), role=str(item["role"]),
              tag=str(item["tag"]), text=str(item["text"]),
              ink=rect(item["ink"]), box=rect(item["box"]),
              lines=int(item["lines"]), font_px=float(item["font_px"]),
              weight=int(item["weight"]), italic=bool(item["italic"]),
              mono=bool(item["mono"]), color=str(item["color"]),
              background=str(item["background"]),
              line_boxes=tuple(rect(box) for box in item.get("line_boxes", ())))
        for item in payload["blocks"]
    )
    figures = tuple(
        Figure(tag=str(item["tag"]), rect=rect(item["rect"]),
               drawn=bool(item["drawn"]))
        for item in payload["figures"]
    )
    return Projection(
        width=int(payload["width"]),
        height=int(payload["height"]),
        body_font_px=float(payload["body_font_px"]),
        body_color=str(payload["body_color"]),
        body_background=str(payload["body_background"]),
        break_elements=int(payload.get("break_elements", 0)),
        clipped=int(payload.get("clipped", 0)),
        runs=runs, blocks=blocks, figures=figures, label=label,
        notes=tuple(notes),
    )


SHOT_SLACK = 120
"""Extra window height to shoot with, before cropping back to the true height.

**Measured, and it is not a cosmetic margin.** Given `--window-size=862,640`
for a page the browser itself reports as 640 tall, Chrome renders the last row
of the last table as blank — the `Total: $385.00` row of `invoice_0001` came
back with zero dark pixels. The same page at 700 and at 900 has it. So a
screenshot taken at exactly the page height loses its final line, silently, in
the one artefact a human reviews.

Nothing in a DOM-based measure can see this: `project()` reports the row at
y 551-569 with a client rect, so T1 counts its text as present while the
picture does not contain it. That is the two-tiers-disagreeing failure spec
0007 warns about, arriving from the tooling rather than from the IR.

Shot with slack and cropped back, so the PNG is still exactly the page.
"""


def screenshot(html: Path | str, destination: Path, *, width: int,
               height: int | None = None) -> Path:
    """Render a page to PNG at a stated width, full height, light scheme.

    The height is measured first rather than guessed, because Chrome's
    `--screenshot` captures exactly the window it is given: too short clips the
    page and too tall pads it with blank, and both make an aspect ratio a
    statement about the flag rather than about the document. It is then shot
    with `SHOT_SLACK` to spare and cropped back — see that constant for the
    measurement that makes the slack necessary.
    """
    if not available():
        raise ProjectionError(f"no headless Chrome at {CHROME}")
    text = html.read_text(encoding="utf-8") if isinstance(html, Path) else html
    width = max(width, MIN_WIDTH)
    tall = height
    if tall is None:
        tall = max(1, project(text, width=width).height)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        target = Path(work) / "page.html"
        target.write_text(text, encoding="utf-8")
        shot = Path(work) / "page.png"
        subprocess.run(
            [str(CHROME), *_FLAGS, "--virtual-time-budget=5000",
             f"--screenshot={shot}", f"--window-size={width},{tall + SHOT_SLACK}",
             target.resolve().as_uri()],
            capture_output=True, timeout=TIMEOUT_S,
        )
        if not shot.exists():
            raise ProjectionError(f"the browser wrote no screenshot for {target}")
        from PIL import Image

        image = Image.open(shot)
        image.crop((0, 0, image.width, min(tall, image.height))).save(destination)
    return destination
