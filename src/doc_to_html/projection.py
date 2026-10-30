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
  const detailNodes = [];
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
    if (window.__dthDetail) detailNodes.push([node, record.index]);
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

  // Spec 0021, step 1: what the checks need and the scorer does not. Each
  // printed word and its box, each table's cells with the rules drawn round
  // them, each list's markers, and the boxes each block's lines can sit in.
  // Computed only when asked (`project(..., detail=True)`), so the payload
  // every score is read from is the same with or without it.
  function detailOf(nodes, blockMap, skipped) {
    const shown = (element) => {
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden';
    };
    const box = (rect) => [rect.left, rect.top, rect.right, rect.bottom];
    const collapse = (text) => text.replace(/\s+/g, ' ').trim();
    const side = (style, name) => [px(style[`border${name}Width`]),
                                   style[`border${name}Style`],
                                   style[`border${name}Color`]];
    const sides = (element) => {
      const style = getComputedStyle(element);
      return ['Top', 'Right', 'Bottom', 'Left'].map((name) => side(style, name));
    };
    const groundOf = (element) => {
      for (let at = element; at; at = at.parentElement) {
        const colour = getComputedStyle(at).backgroundColor;
        if (colour && colour !== 'rgba(0, 0, 0, 0)' && colour !== 'transparent') return colour;
      }
      return 'rgb(255, 255, 255)';
    };
    const ordered = (elements) => [...elements].sort((a, b) =>
      (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);

    // The face a stack draws: its first family that resolves. A family this
    // machine lacks falls through to `monospace` in one probe and `serif` in
    // the other, and the two widths differ — `factory.fonts`' own test.
    const GENERICS = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy',
      'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded',
      '-apple-system', 'blinkmacsystemfont', 'math', 'emoji']);
    const canvas = document.createElement('canvas').getContext('2d');
    const faces = new Map();
    const named = (family) => (/^[-\w]+$/.test(family) ? family : `"${family}"`);
    const faceOf = (stack) => {
      if (faces.has(stack)) return faces.get(stack);
      const families = stack.split(',').map((f) => f.trim().replace(/^["']|["']$/g, ''))
                            .filter(Boolean);
      let drawn = families[families.length - 1] || 'serif';
      for (const family of families) {
        if (GENERICS.has(family.toLowerCase())) { drawn = family; break; }
        canvas.font = `48px ${named(family)}, monospace`;
        const one = canvas.measureText('Hamburgefonstiv 0123456789').width;
        canvas.font = `48px ${named(family)}, serif`;
        if (canvas.measureText('Hamburgefonstiv 0123456789').width === one) {
          drawn = family;
          break;
        }
      }
      canvas.font = `48px ${stack}`;
      const face = {family: drawn,
                    mono: Math.abs(canvas.measureText('iiiii').width
                                   - canvas.measureText('MMMMM').width) < 0.5};
      faces.set(stack, face);
      return face;
    };

    // Tables, by slot: a cell spanning two columns fills two slots. Each
    // cell's own four borders, its row's and its row group's, and the
    // table's, are kept raw; which of them draws a rule is `Table.drawn`'s
    // question, since `border-collapse` decides whose border shows.
    const cellIds = new Map();
    const tables = [];
    for (const table of document.querySelectorAll('table')) {
      if (skipped.has(table) || !shown(table)) continue;
      const index = tables.length;
      const rows = [...table.rows];
      const grid = [];
      const cells = [];
      const rowSides = [];
      rows.forEach((row, r) => {
        const style = getComputedStyle(row);
        rowSides.push([side(style, 'Top'), side(style, 'Bottom')]);
        grid[r] = grid[r] || [];
        let c = 0;
        for (const cell of row.cells) {
          while (grid[r][c] !== undefined) c += 1;
          const down = Math.min(cell.rowSpan > 0 ? cell.rowSpan : rows.length - r, rows.length - r);
          const across = Math.max(1, cell.colSpan || 1);
          for (let i = r; i < r + down; i += 1) {
            grid[i] = grid[i] || [];
            for (let j = c; j < c + across; j += 1) grid[i][j] = cells.length;
          }
          cellIds.set(cell, [index, cells.length]);
          cells.push({row: r, col: c, rowspan: down, colspan: across,
                      header: cell.tagName === 'TH', text: collapse(cell.textContent),
                      box: box(cell.getBoundingClientRect()), sides: sides(cell),
                      ground: groundOf(cell)});
          c += across;
        }
      });
      const groups = [];
      for (const group of table.querySelectorAll(':scope > thead, :scope > tbody, :scope > tfoot')) {
        const inside = [...group.rows].map((row) => rows.indexOf(row)).filter((at) => at >= 0);
        if (!inside.length) continue;
        const style = getComputedStyle(group);
        groups.push({first: Math.min(...inside), last: Math.max(...inside),
                     top: side(style, 'Top'), bottom: side(style, 'Bottom')});
      }
      const style = getComputedStyle(table);
      tables.push({index, rows: rows.length,
                   cols: Math.max(0, ...grid.map((row) => (row ? row.length : 0))),
                   collapse: style.borderCollapse === 'collapse',
                   box: box(table.getBoundingClientRect()), sides: sides(table),
                   ground: groundOf(table), row_sides: rowSides, groups, cells});
    }

    // Lists, and what each item is marked with: its list-style, a `::marker`
    // standing in for it, or a `::before` — the text node walk sees none of
    // them, which is how a numbered step drawn as a bullet stayed invisible.
    const NUMBERED = /decimal|roman|alpha|latin|greek|armenian|georgian|hebrew|cjk|hiragana|katakana/;
    const BULLETED = /disc|circle|square|disclosure/;
    const markOf = (text) => {
      if (/counter\(/.test(text)) return 'number';
      if (/[✓✔☑☒✗✘☐□✅❌]/.test(text)) return 'tick';
      if (/\d/.test(text)) return 'number';
      if (/[•·▪▫●○◦‣⁃–—\-*►▸»>]/.test(text)) {
        return 'bullet';
      }
      return text.trim() ? 'other' : 'none';
    };
    const markerOf = (item) => {
      const style = getComputedStyle(item);
      if (style.display === 'list-item') {
        if (style.listStyleImage && style.listStyleImage !== 'none') return 'bullet';
        const type = style.listStyleType;
        if (type && type !== 'none') {
          if (NUMBERED.test(type)) return 'number';
          if (BULLETED.test(type)) return 'bullet';
          if (/^["']/.test(type)) return markOf(type.slice(1, -1));
          return 'other';
        }
      }
      const before = getComputedStyle(item, '::before');
      const content = before.content;
      if (!content || content === 'none' || content === 'normal') return 'none';
      const text = content.replace(/^["']|["']$/g, '');
      if (text.trim()) return markOf(text);
      // An empty `::before` with a size and a fill or a border is a drawn dot.
      const drawn = px(before.width) > 0 && px(before.height) > 0
        && ((before.backgroundColor !== 'rgba(0, 0, 0, 0)') || px(before.borderTopWidth) > 0);
      return drawn ? 'bullet' : 'none';
    };
    const itemIds = new Map();
    const lists = [];
    const listy = new Set(document.querySelectorAll('ul, ol, menu'));
    for (const item of document.querySelectorAll('li')) {
      if (item.parentElement) listy.add(item.parentElement);
    }
    for (const list of ordered(listy)) {
      if (skipped.has(list) || !shown(list)) continue;
      const items = [...list.children].filter((child) =>
        child.tagName === 'LI' || getComputedStyle(child).display === 'list-item');
      if (!items.length) continue;
      const index = lists.length;
      lists.push({index, tag: list.tagName.toLowerCase(), items: items.map((item, k) => {
        itemIds.set(item, [index, k]);
        const text = collapse(item.textContent);
        // A number printed as the item's own text, as most of the corpus's
        // numbered lists do: `1.`, `2)`, `(a)`, or a number set in its own
        // span straight before a word (`1What is…`, c0011). A letter needs its
        // stop, or every item opening with `a` would be numbered.
        return {text, box: box(item.getBoundingClientRect()), marker: markerOf(item),
                numbered_text: /^\(?(\d{1,3}([.)]|(?=[^\W\d_]))|[a-z][.)]|[ivxlc]{1,4}[.)])/iu.test(text),
                ticked_text: /^[☐-☒✓-✘□■▢▣]/u.test(text)};
      })});
    }

    // Every printed word: a run of non-space in one text node, so a word the
    // markup cuts in two is two words here exactly as it is two runs to the
    // scorer.
    const range = document.createRange();
    const words = [];
    for (const [node, block] of nodes) {
      const parent = node.parentElement;
      const style = getComputedStyle(parent);
      const face = faceOf(style.fontFamily);
      const cell = parent.closest('td, th');
      let item = null;
      for (let at = parent; at && at !== document.body; at = at.parentElement) {
        if (itemIds.has(at)) { item = itemIds.get(at); break; }
      }
      for (const match of node.textContent.matchAll(/\S+/g)) {
        range.setStart(node, match.index);
        range.setEnd(node, match.index + match[0].length);
        const lines = linesFrom(range.getClientRects());
        if (!lines.length) continue;
        let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
        for (const [x0, y0, x1, y1] of lines) {
          l = Math.min(l, x0); t = Math.min(t, y0);
          r = Math.max(r, x1); b = Math.max(b, y1);
        }
        words.push({text: match[0], rect: [l, t, r, b], block, lines: lines.length,
                    weight: parseInt(style.fontWeight, 10) || 400,
                    italic: style.fontStyle === 'italic',
                    family: face.family, mono: face.mono, font_px: px(style.fontSize),
                    color: style.color, transform: style.textTransform,
                    small_caps: /small-caps/.test(style.fontVariantCaps || ''),
                    cell: cell && cellIds.has(cell) ? cellIds.get(cell) : null,
                    item});
      }
    }

    // The boxes a block's lines can be aligned in: its own content box and
    // each block ancestor's, innermost first. A box no wider than the line
    // cannot say where the line sits in it; `Detail.frame` picks the first
    // one that can.
    const frames = [];
    for (const [element, record] of blockMap) {
      const chain = [];
      for (let at = element; at && at !== document.documentElement; at = at.parentElement) {
        const style = getComputedStyle(at);
        if (isInline(style)) continue;
        const rect = at.getBoundingClientRect();
        chain.push([rect.left + px(style.borderLeftWidth) + px(style.paddingLeft),
                    rect.top + px(style.borderTopWidth) + px(style.paddingTop),
                    rect.right - px(style.borderRightWidth) - px(style.paddingRight),
                    rect.bottom - px(style.borderBottomWidth) - px(style.paddingBottom)]);
      }
      frames.push({block: record.index, chain, align: getComputedStyle(element).textAlign});
    }

    let unread = 0;
    for (const element of document.querySelectorAll('.disputed, .unread, [data-unread]')) {
      if (!skipped.has(element)) unread += 1;
    }
    return {words, tables, lists, frames, unread};
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
  if (window.__dthDetail) payload.detail = detailOf(detailNodes, blocks, chrome);

  // In chunks: spreading every byte as an argument fails on a payload
  // over about 100 KB, a table of 40 rows by 8 columns (spec 0020).
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  const pre = document.createElement('pre');
  pre.id = '__projection';
  pre.textContent = btoa(binary);
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


Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Word:
    """One printed word: a run of non-space inside one text node, and where it
    landed. Spec 0021, step 1.

    The word is the text node's, not the scorer's token: `NP-2291` is one
    word here and two tokens to `scoring.tokens`, which the checks take
    each word's tokens from. `cell` is (table, cell) and `item` is (list,
    item), indexes into `Detail.tables` and `Detail.lists`.
    """

    text: str
    rect: Rect
    block: int
    lines: int
    weight: int
    italic: bool
    family: str
    """The face the word's stack draws: its first family that resolves."""
    mono: bool
    """Whether that stack draws `iiiii` and `MMMMM` the same width."""
    font_px: float
    color: str
    transform: str
    """The computed `text-transform`: the page prints `PATIENT` where its
    text node holds `Patient`."""
    small_caps: bool
    cell: tuple[int, int] | None = None
    item: tuple[int, int] | None = None


@dataclass(frozen=True)
class Side:
    """One border as computed: width in pixels, style, colour."""

    width: float
    style: str
    color: str

    def drawn(self, ground: str) -> bool:
        """Whether a reader sees it: some width, a style that draws, and ink
        that differs from what it is drawn on."""
        if self.width <= 0 or self.style in ("none", "hidden"):
            return False
        ink, under = parse_rgba(self.color), parse_rgba(ground)
        if ink is None or ink[3] <= 0:
            return False
        if under is None:
            return True
        return max(abs(ink[i] - under[i]) for i in range(3)) > INK_FROM_GROUND


INK_FROM_GROUND = 8
"""How far a border's colour must sit from its ground to be seen, per channel.
A white rule on a white page is not a rule; anything darker by more than a
rounding step is."""


def parse_rgba(value: str) -> tuple[float, float, float, float] | None:
    """`rgb(1, 2, 3)` or `rgba(1, 2, 3, 0.5)` as four numbers, else None."""
    if not value or "(" not in value:
        return None
    try:
        numbers = [float(part) for part in
                   value[value.index("(") + 1:value.rindex(")")].replace("/", ",").split(",")
                   if part.strip()]
    except ValueError:
        return None
    if len(numbers) < 3:
        return None
    return (numbers[0], numbers[1], numbers[2], numbers[3] if len(numbers) > 3 else 1.0)


@dataclass(frozen=True)
class TableCell:
    """One cell of a table, by slot: `row`, `col` and its spans."""

    row: int
    col: int
    rowspan: int
    colspan: int
    header: bool
    text: str
    box: Rect
    sides: tuple[Side, Side, Side, Side]
    """Top, right, bottom, left — the cell's own borders, as computed."""
    ground: str


@dataclass(frozen=True)
class RowGroup:
    """A `thead`, `tbody` or `tfoot`: its first and last row and its borders."""

    first: int
    last: int
    top: Side
    bottom: Side


@dataclass(frozen=True)
class Table:
    """One `<table>` as drawn: its cells by slot, and every border that could
    draw a rule between them."""

    index: int
    rows: int
    cols: int
    collapse: bool
    box: Rect
    sides: tuple[Side, Side, Side, Side]
    ground: str
    row_sides: tuple[tuple[Side, Side], ...]
    """Each row's top and bottom border. Drawn only under `border-collapse`."""
    groups: tuple[RowGroup, ...]
    cells: tuple[TableCell, ...]

    def slot(self, row: int, col: int) -> int | None:
        """The index of the cell covering a slot, or None for a hole."""
        for index, cell in enumerate(self.cells):
            if cell.row <= row < cell.row + cell.rowspan and \
                    cell.col <= col < cell.col + cell.colspan:
                return index
        return None

    def vertical_rule(self, row: int, col: int) -> bool:
        """Whether a rule is drawn on row `row` between columns `col - 1` and
        `col` — `col` 0 is the left edge, `cols` the right.

        Inside one cell that spans the edge there is no edge. Otherwise the
        right side of the cell on the left or the left side of the one on the
        right draws it; at the table's edge, the table's own side too.
        """
        left = self.slot(row, col - 1) if col > 0 else None
        right = self.slot(row, col) if col < self.cols else None
        if left is not None and left == right:
            return False
        sides: list[tuple[Side, str]] = []
        if left is not None:
            sides.append((self.cells[left].sides[1], self.cells[left].ground))
        if right is not None:
            sides.append((self.cells[right].sides[3], self.cells[right].ground))
        if col in (0, self.cols):
            sides.append((self.sides[3 if col == 0 else 1], self.ground))
        return any(side.drawn(ground) for side, ground in sides)

    def horizontal_rule(self, row: int, col: int) -> bool:
        """Whether a rule is drawn in column `col` between rows `row - 1` and
        `row` — `row` 0 is the top edge, `rows` the bottom.

        Rows and row groups draw borders only when borders collapse.
        """
        above = self.slot(row - 1, col) if row > 0 else None
        below = self.slot(row, col) if row < self.rows else None
        if above is not None and above == below:
            return False
        sides: list[tuple[Side, str]] = []
        if above is not None:
            sides.append((self.cells[above].sides[2], self.cells[above].ground))
        if below is not None:
            sides.append((self.cells[below].sides[0], self.cells[below].ground))
        if self.collapse:
            if row > 0:
                sides.append((self.row_sides[row - 1][1], self.ground))
            if row < self.rows:
                sides.append((self.row_sides[row][0], self.ground))
            for group in self.groups:
                if group.last == row - 1:
                    sides.append((group.bottom, self.ground))
                if group.first == row:
                    sides.append((group.top, self.ground))
        if row in (0, self.rows):
            sides.append((self.sides[0 if row == 0 else 2], self.ground))
        return any(side.drawn(ground) for side, ground in sides)


@dataclass(frozen=True)
class ListItem:
    text: str
    box: Rect
    marker: str
    """`number`, `bullet`, `tick`, `other` or `none` — what is drawn before
    the item, read from its list-style, an image, or a `::before`."""
    numbered_text: bool
    """Whether the item's own text opens with a number: `1.`, `2)`, `(a)`, or
    a number straight before a word (`1What is…`, c0011). Measured on dev's
    33 pages carrying `list.numbers`, 2026-10-30: 13 draw a number marker;
    with numbers printed as text, 32 read as numbered. The 33rd, c0039,
    opens each item with a tick box."""
    ticked_text: bool = False
    """Whether the item's own text opens with a tick, a cross or a box:
    `☑ Full forum pass`. Measured on dev's 32 pages carrying `list.ticks`,
    2026-10-30: none draws a tick as a marker, and 24 open list items with
    one printed as text. Of the other eight, four set tick glyphs outside
    any list, three draw their boxes in CSS, and one prints its ticks
    inside the item's text."""


@dataclass(frozen=True)
class ListGroup:
    index: int
    tag: str
    items: tuple[ListItem, ...]


@dataclass(frozen=True)
class Frames:
    """The boxes a block's lines can be aligned in, innermost first: its own
    content box, then each block ancestor's."""

    block: int
    chain: tuple[Rect, ...]
    align: str
    """The block's computed `text-align`."""


@dataclass(frozen=True)
class Detail:
    """What `project(..., detail=True)` adds: spec 0021's reading."""

    words: tuple[Word, ...]
    tables: tuple[Table, ...]
    lists: tuple[ListGroup, ...]
    frames: tuple[Frames, ...]
    unread: int
    """Elements drawn as unread or disputed (`.disputed`, `.unread`,
    `[data-unread]`)."""


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
    detail: Detail | None = None
    """Spec 0021's reading, only when asked for: `project(..., detail=True)`."""

    @property
    def text(self) -> str:
        """Everything the page says, in reading order, one line per run."""
        return "\n".join(run.text for run in self.runs)

    @property
    def aspect(self) -> float:
        return self.height / self.width if self.width else 0.0


class ProjectionError(RuntimeError):
    """The browser did not answer, so there is nothing to compare."""


def _run_chrome(html: str, width: int, height: int, *, flat: bool = False,
                detail: bool = False) -> dict[str, Any]:
    injected = _inject(html, flat=flat, detail=detail)
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


def _inject(html: str, *, flat: bool = False, detail: bool = False) -> str:
    """Put the measuring script in, wherever the document lets us.

    Appended to `</body>` when there is one and to the end otherwise, because
    `render.py` always writes one and a hand-authored page might not. With
    `flat`, `FLATTEN` runs first; with `detail`, `MEASURE` adds spec 0021's
    reading to its payload.
    """
    script = (
        "<script>window.addEventListener('load', () => {"
        + ("window.__dthDetail = true;" if detail else "")
        + (FLATTEN if flat else "") + MEASURE + "});</script>"
    )
    if "</body>" in html:
        return html.replace("</body>", script + "</body>", 1)
    return html + script


def project(html: Path | str, *, width: int, height: int = 3000,
            label: str = "", flat: bool = False,
            detail: bool = False) -> Projection:
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

    `detail` adds spec 0021's reading (`Detail`): every word's box, the
    tables by slot with their borders, the lists and their markers, and
    each block's frames. It is computed in the same pass, after everything
    else, and the rest of the payload is the same with or without it.
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
    payload = _run_chrome(text, width, height, flat=flat, detail=detail)

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
        detail=_detail(payload["detail"]) if "detail" in payload else None,
    )


def _side(values: Any) -> Side:
    width, style, color = values
    return Side(float(width), str(style), str(color))


def _sides(values: Any) -> tuple[Side, Side, Side, Side]:
    top, right, bottom, left = (_side(value) for value in values)
    return top, right, bottom, left


def _rect(values: Any) -> Rect:
    left, top, right, bottom = (float(value) for value in values)
    return left, top, right, bottom


def _pair(values: Any) -> tuple[int, int] | None:
    if values is None:
        return None
    first, second = values
    return int(first), int(second)


def _detail(payload: dict[str, Any]) -> Detail:
    """`MEASURE`'s `detailOf`, as dataclasses."""
    words = tuple(
        Word(text=str(item["text"]), rect=_rect(item["rect"]), block=int(item["block"]),
             lines=int(item["lines"]), weight=int(item["weight"]),
             italic=bool(item["italic"]), family=str(item["family"]),
             mono=bool(item["mono"]), font_px=float(item["font_px"]),
             color=str(item["color"]), transform=str(item["transform"]),
             small_caps=bool(item["small_caps"]), cell=_pair(item["cell"]),
             item=_pair(item["item"]))
        for item in payload["words"]
    )
    tables = tuple(
        Table(index=int(table["index"]), rows=int(table["rows"]), cols=int(table["cols"]),
              collapse=bool(table["collapse"]), box=_rect(table["box"]),
              sides=_sides(table["sides"]), ground=str(table["ground"]),
              row_sides=tuple((_side(top), _side(bottom))
                              for top, bottom in table["row_sides"]),
              groups=tuple(RowGroup(int(group["first"]), int(group["last"]),
                                    _side(group["top"]), _side(group["bottom"]))
                           for group in table["groups"]),
              cells=tuple(TableCell(row=int(cell["row"]), col=int(cell["col"]),
                                    rowspan=int(cell["rowspan"]),
                                    colspan=int(cell["colspan"]),
                                    header=bool(cell["header"]), text=str(cell["text"]),
                                    box=_rect(cell["box"]), sides=_sides(cell["sides"]),
                                    ground=str(cell["ground"]))
                          for cell in table["cells"]))
        for table in payload["tables"]
    )
    lists = tuple(
        ListGroup(index=int(group["index"]), tag=str(group["tag"]),
                  items=tuple(ListItem(text=str(item["text"]), box=_rect(item["box"]),
                                       marker=str(item["marker"]),
                                       numbered_text=bool(item["numbered_text"]),
                                       ticked_text=bool(item["ticked_text"]))
                              for item in group["items"]))
        for group in payload["lists"]
    )
    frames = tuple(
        Frames(block=int(frame["block"]),
               chain=tuple(_rect(box) for box in frame["chain"]),
               align=str(frame["align"]))
        for frame in payload["frames"]
    )
    return Detail(words=words, tables=tables, lists=lists, frames=frames,
                  unread=int(payload["unread"]))


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
