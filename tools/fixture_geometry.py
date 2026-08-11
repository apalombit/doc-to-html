"""Read a fixture's true Zone rectangles off the document that produced it.

    python tools/fixture_geometry.py            # print, and check the render
    python tools/fixture_geometry.py --write    # update the expected IR

Every geometry number this project has recorded is scored against rectangles
that were **typed by hand**. Both fixture builders say so, and #23 measured what
it costs: snapping the expected boxes to their own ink moves them by enough that
the mean IoU between typed and snapped is **0.701** across five fixtures, worst
single box 0.04. A ruler with that much slop cannot referee a change, which is
why spec 0004 pre-registered demoting `iou` and why the demotion fired.

`example/invoice.png` is a screenshot of `example/invoice.html`, so the true
rectangles are not a matter of opinion. The browser already computed them. This
asks it.

**What a Zone's rectangle is, here.** The union of the client rects of every
non-empty text node and every image inside the elements that make up the Zone —
not the element's own border box, which includes cell padding the ink does not
occupy. That is as close to "where the ink is" as the source can answer, and it
is exact rather than eyeballed.

**The one judgement.** Which elements make up which Zone is a mapping decision,
made once, written down below. Everything after it is arithmetic. Zones 4 and 5
are each a union of table rows, which is the only place this is interesting:
`invoice.html` is one table, and what a reader calls "the line-item table" is a
run of `tr`s inside it.

**It checks itself.** The same headless Chrome re-renders the page at the Source
Image's own size and the result is compared with `example/invoice.png` pixel by
pixel. If the render has drifted from the screenshot on disk — a font
substitution, a Chrome upgrade — the coordinates describe a page nobody has, and
this says so instead of quietly writing them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from doc_to_html.geometry_score import expected_zones, iou, score_geometry  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import rectify  # noqa: E402

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

SOURCE_HTML = REPO / "example" / "invoice.html"
SOURCE_PNG = REPO / "example" / "invoice.png"
EXPECTED = REPO / "tests" / "fixtures" / "invoice_0001.expected.json"

RENDERED_EXTENT_SLACK = 1
"""Pixels of slack around the browser's text bounds, and why it is not a fudge.

A range's client rect is the glyph *box*. The rasteriser antialiases a fraction
of a pixel outside it, so a rectangle sitting exactly on the glyph box clips the
mark as it was actually drawn — measured, that is 2 of the 6 Zones reporting a
split against their own ink. One pixel contains the rendered extent and takes
`splits` to 0 with `covered` unchanged at 1.00. Two pixels changes nothing
further, so this is the smallest slack that works rather than a tuned one.
"""

NO_BODY_MARGIN = "<style>body{margin:0}</style>"
"""How `example/invoice.png` was taken, recovered by measurement.

Rendering `invoice.html` as-is puts every mark 8px right and 8px down of where
the Source Image has it, and makes the content 16px narrower — the browser's
default `body { margin: 8px }`, which whatever produced the screenshot did not
apply. 13.1% of pixels differ with it and 0.7% without it.

It matters more than it sounds. 8px on a 563px page is 1.4%, which is the same
order as the differences between a good box and a bad one, so geometry read off
an unadjusted render would be wrong by about as much as the thing being measured.
"""

ZONE_ELEMENTS = """
  const outer = document.querySelector('.invoice-box > table');
  const top = outer.querySelector('tr.top');
  const info = outer.querySelector('tr.information');
  const headings = outer.querySelectorAll('tr.heading');
  const details = outer.querySelectorAll('tr.details');
  const items = outer.querySelectorAll('tr.item');
  const total = outer.querySelector('tr.total');

  // Scoped by walking, not by selector: `top.querySelectorAll('table td')`
  // also matches the outer `td colspan=2`, because a descendant selector's
  // ancestor part is resolved against the whole document rather than against
  // the element being queried.
  const topCells = top.querySelector('td > table').querySelectorAll('td');
  const infoCells = info.querySelector('td > table').querySelectorAll('td');

  const groups = [
    [topCells[0]],
    [topCells[1]],
    [infoCells[0]],
    [infoCells[1]],
    [headings[0], ...details],
    [headings[1], ...items, total],
  ];
"""
"""The mapping, and the only judgement in this file.

  0  the logo image
  1  the Invoice #/Created/Due block beside it
  2  the sender's address
  3  the recipient's address
  4  the Payment Method heading row and its data row
  5  the Item/Price heading row, the three line items, and the total

Zones 4 and 5 are runs of `tr`s in one table, because `invoice.html` is a single
table and "the line-item table" is a reader's word for part of it.
"""

MEASURE = """
function contentRect(nodes) {
  let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
  const push = (rect) => {
    if (rect.width <= 0 && rect.height <= 0) return;
    l = Math.min(l, rect.left); t = Math.min(t, rect.top);
    r = Math.max(r, rect.right); b = Math.max(b, rect.bottom);
  };
  for (const root of nodes) {
    if (root.tagName === 'IMG') push(root.getBoundingClientRect());
    for (const img of root.querySelectorAll('img')) {
      push(img.getBoundingClientRect());
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) push(rect);
    }
  }
  return [l, t, r, b];
}
%s
  const out = {
    width: document.documentElement.clientWidth,
    height: document.documentElement.clientHeight,
    zones: groups.map(contentRect),
    logo: (() => { const i = document.querySelector('img');
                   const r = i.getBoundingClientRect();
                   return [r.left, r.top, r.right, r.bottom, i.complete,
                           i.naturalWidth]; })(),
  };
  const pre = document.createElement('pre');
  pre.id = 'measured-geometry';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
""" % ZONE_ELEMENTS


def measure(width: int, height: int) -> dict[str, object]:
    """Render the source document and ask the browser where everything is."""
    page = SOURCE_HTML.read_text().replace("</head>", NO_BODY_MARGIN + "</head>")
    injected = page.replace(
        "</body>", f"<script>window.addEventListener('load', () => {{{MEASURE}}});"
                   "</script></body>")
    if "measured-geometry" not in injected:
        raise SystemExit("could not inject the measuring script — no </body>?")

    with tempfile.TemporaryDirectory() as work:
        target = Path(work) / "measured.html"
        target.write_text(injected)
        result = subprocess.run(
            [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars",
             "--virtual-time-budget=4000", "--dump-dom",
             f"--window-size={width},{height}", target.resolve().as_uri()],
            capture_output=True, timeout=90,
        )
    dom = result.stdout.decode("utf-8", "replace")
    start = dom.find('id="measured-geometry">')
    if start < 0:
        raise SystemExit(f"no geometry in the DOM: {result.stderr.decode()[:400]}")
    start += len('id="measured-geometry">')
    payload: dict[str, object] = json.loads(dom[start:dom.find("</pre>", start)])
    return payload


def render_matches_source(width: int, height: int) -> tuple[bool, float]:
    """Whether re-rendering the HTML still produces the Source Image on disk.

    The coordinates are only true of the page this machine renders today. A font
    substitution or a browser upgrade would move the ink without moving the
    numbers, and every geometry result after that would be measured against a
    page nobody has.
    """
    with tempfile.TemporaryDirectory() as work:
        shot = Path(work) / "render.png"
        target = Path(work) / "render.html"
        target.write_text(
            SOURCE_HTML.read_text().replace("</head>", NO_BODY_MARGIN + "</head>"))
        subprocess.run(
            [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={shot}", f"--window-size={width},{height}",
             target.resolve().as_uri()],
            capture_output=True, timeout=90,
        )
        if not shot.exists():
            return False, 1.0
        fresh = np.asarray(Image.open(shot).convert("L"), dtype=np.int16)
    original = np.asarray(Image.open(SOURCE_PNG).convert("L"), dtype=np.int16)
    if fresh.shape != original.shape:
        return False, 1.0
    differing = float((np.abs(fresh - original) > 16).mean())
    return differing < 0.01, differing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="update the expected IR in place")
    args = parser.parse_args()

    if not CHROME.exists():
        print(f"no headless Chrome at {CHROME}", file=sys.stderr)
        return 1

    width, height = Image.open(SOURCE_PNG).size
    print(f"Source Image is {width}x{height}; rendering the HTML at that size")

    same, differing = render_matches_source(width, height)
    print(f"re-render differs from the Source Image on "
          f"{differing:.2%} of pixels — {'OK' if same else 'TOO MUCH'}")
    if not same:
        print("The page this machine renders is not the page in example/. The "
              "coordinates below would describe a document nobody has.",
              file=sys.stderr)
        return 1

    measured = measure(width, height)
    # Normalised against the Source Image, not against the browser's reported
    # viewport. Under `--dump-dom` the document element's clientHeight comes back
    # as the content height (476) rather than the window height, and dividing by
    # it puts the last Zone's bottom edge at 1.10 — off the page it is meant to
    # describe. The rects themselves are in CSS pixels from the viewport origin,
    # which is exactly the screenshot's own coordinate space.
    slack = RENDERED_EXTENT_SLACK
    exact = [
        BBox((l - slack) / width, (t - slack) / height,
             (r + slack) / width, (b + slack) / height)
        for l, t, r, b in measured["zones"]  # type: ignore[union-attr]
    ]

    typed = [zone.box for zone in expected_zones(EXPECTED) if zone.box]
    image = rectify(SOURCE_PNG).image
    print(f"\n{'zone':6}{'typed by hand':>34}{'read off the render':>34}{'IoU':>7}")
    for index, (was, now) in enumerate(zip(typed, exact)):
        print(f"{index:<6}"
              f"{f'{was.left:.3f} {was.top:.3f} {was.right:.3f} {was.bottom:.3f}':>34}"
              f"{f'{now.left:.3f} {now.top:.3f} {now.right:.3f} {now.bottom:.3f}':>34}"
              f"{iou(was, now):7.2f}")

    before = score_geometry(typed, typed, image)
    after = score_geometry(exact, exact, image)
    print(f"\n{'':11}{'covered':>10}{'splits':>8}{'doubles':>9}")
    print(f"{'typed':11}{before.covered:10.2f}{before.splits:8d}{before.doubles:9d}")
    print(f"{'exact':11}{after.covered:10.2f}{after.splits:8d}{after.doubles:9d}")

    if args.write:
        data = json.loads(EXPECTED.read_text())
        for zone, box in zip(data["zones"], exact):
            zone["bbox"] = {
                "left": round(box.left, 4), "top": round(box.top, 4),
                "right": round(box.right, 4), "bottom": round(box.bottom, 4),
            }
        EXPECTED.write_text(json.dumps(data, indent=2) + "\n")
        print(f"\nwrote {EXPECTED}")
    else:
        print("\n--write to update the expected IR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
