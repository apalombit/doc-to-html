"""Spec 0025's yardsticks: the parser's order and the page's true box tree.

    # step 1(a): the parser's reading order against each dev page's DOM order
    python tools/skeleton_check.py order [--regions L5-D2-dev]

    # step 1(b): the source's box tree of some dev pages, read in Chrome
    python tools/skeleton_check.py trees c0511,c0274 [--out trees.json]

    # step 2: the skeleton and today's parts scored against the source trees,
    # each page's tree printed and an overlay sheet drawn (today | skeleton)
    python tools/skeleton_check.py score c0511,c0274 --label SK-2 [--regions L5-D2-dev]

Offline: `order` reads the HTML files' text and a run's recorded regions (no
Chrome, no model); `trees` runs headless Chrome over each page's HTML at its
picture's width. Dev pages only: a panel page is refused.

**The order.** Each text region is placed in its page's DOM word stream by
the n-grams of its words that occur once on the page (trigrams, else
bigrams, else words), at the median start they give. Then Kendall's tau
between DOM position and the parser's `index`, and between DOM position and
a top-to-bottom, left-to-right sort (what `adapter.groups_of` walks).

**The tree.** A node is an element that draws a frame on all four sides,
or a fill unlike the ground it sits on, or sets two block children side by
side (sharing half the lower one's height, apart across); and each block
child of the latter, a *lane*. A table is one leaf, a grid, unless its
cells hold such elements: then it is a layout table and each cell a node.
A node's region is on 0-1 of the page's picture; its parent is its nearest
ancestor that is a node.

**The score** (spec 0025 §4). A source node's blocks are the parser's
regions whose centres fall inside it; a node of two blocks or more is
*found* when one part of ours holds exactly those blocks. Nodes holding
the same blocks count once. Today's parts are its Zones, the Zones each
Band sets side by side, and the measured stretches and their lanes
(`parser_first.measure`); the skeleton's are every part of its tree.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from statistics import median
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.adapter import FIGURES, Region, plain, regions_of  # noqa: E402
from doc_to_html.corpus import manifest, names, page  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ARM = "glm-ocr_latest"


def regions_file(name: str, run: str) -> Path:
    return REPO / "debug" / "runs" / run / "dump" / ARM / name / "00_regions.json"


def dev_only(wanted: list[str]) -> list[str]:
    entries = manifest()
    refused = [n for n in wanted if entries[n]["pool"] != "dev"]
    if refused:
        raise SystemExit(f"refused: not dev pages: {', '.join(refused)}")
    return wanted


# ---- (a) the order --------------------------------------------------------------

class _Text(HTMLParser):
    SKIP = {"script", "style", "head", "title", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIP:
            self.depth += 1
        elif tag in ("br", "p", "div", "td", "th", "li", "tr"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth:
            self.parts.append(data)


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).lower())


def dom_words(html: str) -> list[str]:
    parser = _Text()
    parser.feed(html)
    return words(" ".join(parser.parts))


def dom_position(region: Region, grams: dict[int, dict[tuple[str, ...], list[int]]]
                 ) -> float | None:
    """Where a region starts in its page's DOM word stream, or None."""
    content = re.sub(r"<[^>]+>", " ", region.content) if region.label == "table" else region.content
    found = words(plain(content))
    for n in (3, 2, 1):
        hits = [grams[n][tuple(found[i:i + n])][0] - i for i in range(len(found) - n + 1)
                if len(grams[n].get(tuple(found[i:i + n]), ())) == 1]
        if hits:
            return float(median(hits))
    return None


def tau(values: list[float]) -> float:
    agree = disagree = 0
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            agree += b > a
            disagree += b < a
    return (agree - disagree) / max(agree + disagree, 1)


def order(run: str) -> int:
    rows = []
    for name in names("dev"):
        path = regions_file(name, run)
        if not path.exists():
            continue
        dom = dom_words(page(name).html_path(REPO).read_text(encoding="utf-8"))
        grams: dict[int, dict[tuple[str, ...], list[int]]] = {}
        for n in (3, 2, 1):
            index: dict[tuple[str, ...], list[int]] = {}
            for i in range(len(dom) - n + 1):
                index.setdefault(tuple(dom[i:i + n]), []).append(i)
            grams[n] = index
        texts = [r for r in regions_of(json.loads(path.read_text())) if r.label not in FIGURES]
        placed = [(r, p) for r in texts if (p := dom_position(r, grams)) is not None]
        if len(placed) < 2:
            continue
        by_parser = [p for _, p in sorted(placed, key=lambda t: t[0].index)]
        by_sort = [p for _, p in sorted(placed, key=lambda t: (t[0].box.top, t[0].box.left))]
        rows.append({"page": name, "regions": len(texts), "placed": len(placed),
                     "tau_parser": tau(by_parser), "tau_sort": tau(by_sort),
                     "back_parser": sum(b < a for a, b in zip(by_parser, by_parser[1:])),
                     "back_sort": sum(b < a for a, b in zip(by_sort, by_sort[1:])),
                     "differ": by_parser != by_sort})
    regions, placed = sum(r["regions"] for r in rows), sum(r["placed"] for r in rows)
    print(f"{len(rows)} pages; {placed} of {regions} text regions placed ({placed / regions:.0%})")
    for key, label in (("parser", "parser's order"), ("sort", "position sort")):
        print(f"{label}: the DOM's exactly on {sum(r['back_' + key] == 0 for r in rows)}, "
              f"tau median {median(r['tau_' + key] for r in rows):.3f}, "
              f"under 0.7 on {sum(r['tau_' + key] < 0.7 for r in rows)}, "
              f"steps backward {sum(r['back_' + key] for r in rows)} "
              f"on {sum(r['back_' + key] > 0 for r in rows)} pages")
    differ = [r for r in rows if r["differ"]]
    nearer = sum(r["tau_parser"] > r["tau_sort"] for r in differ)
    farther = sum(r["tau_parser"] < r["tau_sort"] for r in differ)
    print(f"where they differ ({len(differ)} pages): parser nearer {nearer}, sort nearer "
          f"{farther} ({', '.join(r['page'] for r in differ if r['tau_parser'] < r['tau_sort'])}),"
          f" tied {len(differ) - nearer - farther}")
    return 0


# ---- (b) the source's tree ------------------------------------------------------

TREE = r"""
(() => {
  const alpha = c => { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return 0;
    const p = m[1].split(',').map(Number); return p.length > 3 ? p[3] : 1; };
  const shown = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'
      && parseFloat(s.opacity) > 0; };
  const ground = el => { for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e); if (alpha(s.backgroundColor) > 0.05) return s.backgroundColor; }
    return 'rgb(255, 255, 255)'; };
  const block = el => !/^inline$|^contents$|^none$/.test(getComputedStyle(el).display);
  const PART = /^(TABLE|THEAD|TBODY|TFOOT|TR|TD|TH|CAPTION|COLGROUP|COL)$/;
  const looks = el => { const s = getComputedStyle(el);
    const sides = ['Top', 'Right', 'Bottom', 'Left'].filter(k =>
      parseFloat(s['border' + k + 'Width']) > 0 && s['border' + k + 'Style'] !== 'none'
      && alpha(s['border' + k + 'Color']) > 0.05);
    const fill = (alpha(s.backgroundColor) > 0.05 && el.parentElement
                  && s.backgroundColor !== ground(el.parentElement)) || s.backgroundImage !== 'none';
    return {frame: sides.length === 4, fill: !!fill}; };
  const besideOf = el => { const kids = [...el.children].filter(c => shown(c) && block(c))
      .map(c => c.getBoundingClientRect());
    for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++) {
      const a = kids[i], b = kids[j];
      const shared = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      const apart = a.right <= b.left + 1 || b.right <= a.left + 1;
      if (apart && shared > 0.5 * Math.min(a.height, b.height)) return true; }
    return false; };
  const content = el => /^(IMG|SVG|CANVAS)$/i.test(el.tagName) || (el.innerText || '').trim()
    || el.querySelector('img,svg,canvas');
  const nodes = [];
  const push = (el, parent, kind) => { const r = el.getBoundingClientRect();
    nodes.push({id: nodes.length, parent, tag: el.tagName.toLowerCase(),
      cls: typeof el.className === 'string' ? el.className : '', kind,
      rect: [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY],
      text: (el.innerText || '').trim().slice(0, 40)});
    return nodes.length - 1; };
  const kinds = (...k) => k.filter(Boolean).join('+');
  const layoutTable = t => [...t.querySelectorAll('*')].some(d => !PART.test(d.tagName) && shown(d)
      && (looks(d).frame || looks(d).fill || besideOf(d)) && content(d));
  function visit(el, parent, lane) {
    if (!shown(el) && getComputedStyle(el).display !== 'contents') return;
    if (el === document.body || el === document.documentElement) {
      for (const c of el.children) visit(c, parent, false); return; }
    if (el.tagName === 'TABLE') {
      const lk = looks(el);
      if (!layoutTable(el)) {
        if (content(el)) push(el, parent, kinds('table', lk.frame && 'frame', lane && 'lane'));
        return; }
      const me = push(el, parent, kinds('layout-table', lk.frame && 'frame', lane && 'lane'));
      for (const row of el.rows) for (const cell of row.cells) {
        if (!shown(cell) || !content(cell)) continue;
        const c = looks(cell);
        const at = push(cell, me, kinds('cell', c.frame && 'frame', c.fill && 'fill'));
        for (const k of cell.children) visit(k, at, false);
      }
      return;
    }
    if (PART.test(el.tagName)) { for (const c of el.children) visit(c, parent, false); return; }
    const lk = looks(el), beside = besideOf(el);
    let me = parent;
    if ((lk.frame || lk.fill || beside || lane) && content(el))
      me = push(el, parent, kinds(lk.frame && 'frame', lk.fill && 'fill', beside && 'beside',
                                  lane && 'lane'));
    for (const c of el.children) visit(c, me, me !== parent && beside && block(c));
  }
  visit(document.body, -1);
  const pre = document.createElement('pre'); pre.id = '__tree';
  const bytes = new TextEncoder().encode(JSON.stringify({nodes}));
  let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000)
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  pre.textContent = btoa(bin); document.documentElement.appendChild(pre);
})();
"""


def tree(name: str) -> list[dict[str, Any]]:
    """One page's box tree, each node's `box` on 0-1 of its picture and its `depth`."""
    from PIL import Image

    from doc_to_html.projection import _FLAGS, CHROME

    source = page(name)
    html = source.html_path(REPO).read_text(encoding="utf-8")
    width, height = Image.open(source.png_path(REPO)).size
    base = f'<base href="{source.html_path(REPO).parent.resolve().as_uri()}/">'
    html = html.replace("<head>", "<head>" + base, 1) if "<head>" in html else base + html
    script = "<script>window.addEventListener('load', () => {" + TREE + "});</script>"
    html = html.replace("</body>", script + "</body>", 1) if "</body>" in html else html + script
    with tempfile.TemporaryDirectory() as work:
        target = Path(work) / "tree.html"
        target.write_text(html, encoding="utf-8")
        done = subprocess.run([str(CHROME), *_FLAGS, "--virtual-time-budget=5000", "--dump-dom",
                               f"--window-size={width},{height + 200}", target.resolve().as_uri()],
                              capture_output=True, timeout=120)
    dom = done.stdout.decode("utf-8", "replace")
    start = dom.find('id="__tree">')
    if start < 0:
        raise RuntimeError(f"{name}: the browser returned no tree")
    start += len('id="__tree">')
    nodes: list[dict[str, Any]] = json.loads(
        base64.b64decode(dom[start:dom.find("</pre>", start)].strip()))["nodes"]
    for node in nodes:
        left, top, right, bottom = node["rect"]
        node["box"] = [left / width, top / height, right / width, bottom / height]
        node["depth"] = 1 + (nodes[node["parent"]]["depth"] if node["parent"] >= 0 else 0)
    return nodes


def depths(nodes: list[dict[str, Any]]) -> dict[str, int]:
    beside: dict[int, int] = {}
    boxes: dict[int, int] = {}
    for node in nodes:
        up = node["parent"]
        beside[node["id"]] = (beside[up] if up >= 0 else 0) + ("beside" in node["kind"]
                                                             or "layout" in node["kind"])
        boxes[node["id"]] = (boxes[up] if up >= 0 else 0) + any(
            k in node["kind"].split("+") for k in ("frame", "fill"))
    return {"nodes": len(nodes), "depth": max((n["depth"] for n in nodes), default=0),
            "beside": max(beside.values(), default=0), "boxes": max(boxes.values(), default=0)}


def trees(wanted: list[str], out: Path | None) -> int:
    found = {name: tree(name) for name in dev_only(wanted)}
    if out is not None:
        out.write_text(json.dumps(found, indent=1))
    for name, nodes in found.items():
        d = depths(nodes)
        print(f"{name}: {d['nodes']} nodes, depth {d['depth']}, side by side nested "
              f"{d['beside']}, box in box {d['boxes']}")
        for node in nodes:
            left, top, right, bottom = node["box"]
            print(f"   {'  ' * (node['depth'] - 1)}{node['tag']}.{node['cls'][:16]} "
                  f"[{node['kind']}] ({left:.2f},{top:.2f},{right:.2f},{bottom:.2f}) "
                  f"{node['text'][:28]!r}")
    return 0


# ---- step 2: the score ----------------------------------------------------------

def _today(raw: list[dict[str, Any]], png: Path) -> tuple[list[tuple[str, frozenset[int]]], Any]:
    """Today's parts on a page, each with the parser's indices it holds,
    and the measured Document: `adapter.document_of`'s steps, each Zone's
    regions tracked, then `parser_first.measure`."""
    from doc_to_html import adapter
    from doc_to_html.ir import Document, Flow
    from doc_to_html.parser_first import containers, flat, measure
    from doc_to_html.wire import bands_from_boxes

    rectified = flat(png)
    regions = regions_of(raw)
    line = adapter.line_height(regions)
    groups = adapter._unnested(adapter.groups_of(regions, containers(rectified)))
    zones = [adapter.zone_of(g) for g in groups]
    held = {id(z): frozenset(r.index for r in g) for z, g in zip(zones, groups)}
    kept = adapter._titled(list(zones), line)
    for zone in zones:
        if zone not in kept:
            box = zone.bbox
            table = next(z for z in kept if z.bbox is not None and box is not None
                         and z.title is not None and abs(z.bbox.top - box.top) < 1e-9)
            held[id(table)] = held[id(table)] | held[id(zone)]
    for zone, (band, column) in zip(kept, bands_from_boxes(adapter._stacked(
            [adapter._inset(z.bbox, line) for z in kept if z.bbox is not None]))):
        zone.band, zone.column = band, column
    document = Document(source=rectified.source, zones=kept)
    measure(document, rectified)
    parts: list[tuple[str, frozenset[int]]] = [("zone", held[id(z)]) for z in kept]
    for band in {z.band for z in kept}:
        members = [z for z in kept if z.band == band]
        if len(members) > 1:
            parts.append(("band", frozenset().union(*(held[id(z)] for z in members))))
    for region in document.regions:
        inside = [z for z in kept if z.bbox is not None and region.holds(z.bbox)]
        parts.append(("stretch", frozenset().union(*(held[id(z)] for z in inside))))
        if region.flow is not Flow.SINGLE:
            for lane in range(region.lanes):
                parts.append(("lane", frozenset().union(
                    *(held[id(z)] for z in inside if region.lane_of(z.bbox) == lane))))
    return parts, document


def _skeleton(raw: list[dict[str, Any]], png: Path) -> Any:
    from doc_to_html.parser_first import containers, flat, skeleton_of

    rectified = flat(png)
    return skeleton_of(raw, rectified, containers(rectified))


COLOURS = {"page": (120, 120, 120), "rows": (150, 150, 150), "columns": (30, 90, 220),
           "grid": (240, 140, 0), "box": (20, 160, 60), "flat": (220, 30, 30),
           "block": (190, 190, 190), "zone": (190, 190, 190), "band": (30, 90, 220),
           "stretch": (150, 150, 150), "lane": (20, 160, 60)}


def _overlay(png: Path, parts: list[tuple[str, Any, int]], title: str) -> Any:
    """The page with each part's box drawn, coloured by kind, the outer
    ones thicker."""
    from PIL import Image, ImageDraw

    image = Image.open(png).convert("RGB")
    image = Image.blend(image, Image.new("RGB", image.size, (255, 255, 255)), 0.45)
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for kind, box, depth in sorted(parts, key=lambda p: -p[2]):
        width = 1 if kind in ("block", "zone") else max(1, 4 - depth)
        draw.rectangle([box.left * w, box.top * h, box.right * w, box.bottom * h],
                       outline=COLOURS[kind], width=width)
        if kind not in ("block", "zone", "rows", "page"):
            draw.text((box.left * w + 2, box.top * h + 1), kind[0].upper(), fill=COLOURS[kind])
    draw.text((4, h - 14), title, fill=(0, 0, 0))
    return image


def score(wanted: list[str], run: str, label: str) -> int:
    from PIL import Image

    from doc_to_html.adapter import _union

    out = REPO / "debug" / "runs" / label / "skeleton"
    out.mkdir(parents=True, exist_ok=True)
    totals = {"source": 0, "skeleton": 0, "today": 0}
    for name in dev_only(wanted):
        raw = json.loads(regions_file(name, run).read_text())
        png = page(name).png_path(REPO)
        regions = regions_of(raw)
        sk = _skeleton(raw, png)
        today, document = _today(raw, png)
        mine = {frozenset(p.blocks) for p in sk.walk()}
        theirs = {blocks for _, blocks in today}
        nodes = tree(name)
        seen: dict[frozenset[int], dict[str, Any]] = {}
        for node in nodes:
            l, t, r, b = node["box"]
            held = frozenset(x.index for x in regions if l <= (x.box.left + x.box.right) / 2 <= r
                             and t <= (x.box.top + x.box.bottom) / 2 <= b)
            if len(held) >= 2 and held not in seen:
                seen[held] = node
        found_sk = [s for s in seen if s in mine]
        found_today = [s for s in seen if s in theirs]
        totals["source"] += len(seen)
        totals["skeleton"] += len(found_sk)
        totals["today"] += len(found_today)
        report = [f"{name}: {len(seen)} source parts; skeleton finds {len(found_sk)}, "
                  f"today {len(found_today)}", sk.describe()]
        for held, node in seen.items():
            mark = ("S" if held in mine else "-") + ("T" if held in theirs else "-")
            report.append(f"  {mark} {node['tag']}.{node['cls'][:14]} [{node['kind']}] "
                          f"{sorted(held)} {node['text'][:30]!r}")
        (out / f"{name}.txt").write_text("\n".join(report) + "\n")
        print(report[0])
        def depth_of(part: Any, depth: int = 0) -> list[tuple[str, Any, int]]:
            got = [(part.kind, part.box, depth)]
            for child in part.children:
                got += depth_of(child, depth + 1)
            return got
        boxes = {x.index: x.box for x in regions}
        old = [(kind, _union([boxes[i] for i in blocks]), {"stretch": 0, "lane": 1, "band": 2,
                                                            "zone": 3}[kind])
               for kind, blocks in today if blocks]
        left = _overlay(png, old, f"today: {len(found_today)} of {len(seen)}")
        right = _overlay(png, depth_of(sk), f"skeleton: {len(found_sk)} of {len(seen)}")
        sheet = Image.new("RGB", (left.width * 2 + 20, left.height), (136, 136, 136))
        sheet.paste(left, (0, 0))
        sheet.paste(right, (left.width + 20, 0))
        sheet.save(out / f"{name}.png")
        del document
    print(f"all: {totals['source']} source parts; skeleton finds {totals['skeleton']}, "
          f"today {totals['today']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    o = sub.add_parser("order", help="step 1(a): the parser's order against the DOM's")
    o.add_argument("--regions", default="L5-D2-dev", metavar="RUN")
    t = sub.add_parser("trees", help="step 1(b): the source's box tree of some dev pages")
    t.add_argument("pages", help="comma list of dev page ids")
    t.add_argument("--out", type=Path)
    c = sub.add_parser("score", help="step 2: the skeleton and today's parts against the trees")
    c.add_argument("pages", help="comma list of dev page ids")
    c.add_argument("--regions", default="L5-D2-dev", metavar="RUN")
    c.add_argument("--label", required=True, help="writes debug/runs/<label>/skeleton/")
    args = parser.parse_args()
    if args.command == "order":
        return order(args.regions)
    if args.command == "score":
        return score([n for n in args.pages.split(",") if n], args.regions, args.label)
    return trees([n for n in args.pages.split(",") if n], args.out)


if __name__ == "__main__":
    raise SystemExit(main())
