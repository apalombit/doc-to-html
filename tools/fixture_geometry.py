"""Read a fixture's true Zone rectangles off the document that produced it.

    python tools/fixture_geometry.py            # invoice_0001, off the browser
    python tools/fixture_geometry.py --write    # update the expected IR

    python tools/fixture_geometry.py --snap                    # the other four
    python tools/fixture_geometry.py --snap --write
    python tools/fixture_geometry.py --snap --fixtures sample_css_0004

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

## Two derivations, one convention

That convention — **ink, not container** — is the whole of it, and for a long
time only `invoice_0001` followed it. The other four fixtures were typed around
what is *drawn*: a card's border, a panel's shaded caption bar, an `<aside>`'s
padding. Measured, mean typed-vs-ink IoU per fixture:

    invoice_0001          exact        read off the browser
    sample_table_0003     0.854
    sample_semantic_0005  0.758        worst box 0.445, the TL;DR aside
    invoice_0002          0.659        worst box 0.043, Services / Products
    sample_css_0004       0.605        worst box 0.260, the second card

`geometry_score.MATCH_IOU` is 0.50, so a reference at 0.043 against its own ink
cannot be matched by a correctly drawn detection at all — the fixture, not the
run, decides the finding. `Services / Products` is the clearest case: its panel
is empty, so the typed box is a full-width shaded bar over a heading's worth of
text.

**`--snap` is the second derivation**, for the four whose HTML cannot be
re-rendered. `preprocess.snap_to_ink` moves each typed rectangle onto the ink it
encloses, from the Source Image — the artefact that actually exists — using the
same operation every detection goes through in `LayoutEngine.detect_zones`. It
corrects edges, so it cannot fix a box drawn around the wrong *content*; the one
such case in the corpus, `sample_semantic_0005` Zone 2 stopping short of the
byline its own Block claims, is fixed in the builder and that fix has to land
first or snapping shrinks the box further.

**Why the browser is not used for those four.** Measured, not assumed: only
`invoice.html` still re-renders to its screenshot, at 0.74% of pixels differing.
The other four differ by 6.9-14.1%, and in **content height** rather than
position — different fonts on this machine, and `invoice2.html` additionally
wants the Bootstrap CDN. `render_matches_source` refuses all four, correctly.

**`--snap` refuses `invoice_0001`**, because snapping is an approximation of the
convention and that fixture already has the thing itself. Snapped, its
browser-exact rectangles score 0.916 against themselves — so applying this to it
would trade the corpus's only ground truth for an estimate of it.

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
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from doc_to_html.geometry_score import expected_zones, iou, score_geometry  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import rectify, snap_to_ink  # noqa: E402

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

SOURCE_HTML = REPO / "example" / "invoice.html"
SOURCE_PNG = REPO / "example" / "invoice.png"
EXPECTED = REPO / "tests" / "fixtures" / "invoice_0001.expected.json"

BROWSER_EXACT = "invoice_0001"
"""The one fixture `--snap` refuses, and the reason it exists to refuse it.

Its rectangles are already the thing `--snap` approximates. Snapped, they score
0.916 against themselves — so running this over it would trade the corpus's only
ground truth for an estimate of it, and every later comparison would be against
a ruler nobody could re-derive.
"""

ZONE_BBOX = re.compile(r"^ {16}bbox=BBox\([^)]*\),$", re.M)
"""A Zone's own rectangle in a builder, and nothing else.

Anchored on exactly sixteen spaces, which is the indentation of a keyword
argument to a `Zone(` inside the `zones=[` list. Cell rectangles are written at
thirty-three or more — `value=cell(..., bbox=BBox(...))` — so they cannot match.
`rewrite_builder` checks the count against the Zone count anyway and refuses on
a mismatch, because an indentation convention is a weaker guarantee than a
count.
"""

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


def rewrite_builder(fixture: str, boxes: list[BBox]) -> None:
    """Put the derived rectangles back into the builder, which is the truth.

    The builders are the authoritative hand-authored ground truth and the JSON
    beside them is their serialised form — `tools/write_expected_ir.py` says so,
    and `tests/test_acceptance.py` asserts the two agree. So writing the JSON
    alone, the way the browser path does for `invoice_0001`, would land this
    fixture's numbers in the file nobody edits and leave the file everybody
    reads disagreeing with it. The assertion would catch that, but only after
    the numbers had been quoted.
    """
    path = REPO / "tests" / "fixtures" / f"{fixture}.py"
    source = path.read_text()
    found = ZONE_BBOX.findall(source)
    if len(found) != len(boxes):
        raise SystemExit(
            f"{path.name}: {len(found)} Zone rectangles in the source against "
            f"{len(boxes)} in the IR — refusing to guess which is which"
        )

    replacements = iter(
        f"                bbox=BBox({box.left:.4f}, {box.top:.4f}, "
        f"{box.right:.4f}, {box.bottom:.4f}),"
        for box in boxes
    )
    path.write_text(ZONE_BBOX.sub(lambda _: next(replacements), source))
    print(f"  wrote {len(boxes)} rectangles into {path.relative_to(REPO)}")


def snap_fixture(fixture: str, write: bool) -> int:
    """Move one fixture's typed rectangles onto the ink they enclose."""
    from tests.fixtures import IMAGES

    if fixture == BROWSER_EXACT:
        print(f"{fixture}: refusing — its rectangles are read off the browser, "
              f"and snapping them scores 0.916 against themselves")
        return 1

    image = rectify(REPO / IMAGES[fixture]).image
    zones = expected_zones(REPO / "tests" / "fixtures" / f"{fixture}.expected.json")
    typed = [zone.box for zone in zones if zone.box is not None]
    if len(typed) != len(zones):
        raise SystemExit(f"{fixture}: a Zone has no rectangle to snap")
    snapped = snap_to_ink(image, typed)

    print(f"\n{fixture}")
    print(f"{'zone':6}{'typed by hand':>34}{'snapped to its ink':>34}{'IoU':>7}")
    for index, (was, now) in enumerate(zip(typed, snapped)):
        print(f"{index:<6}"
              f"{f'{was.left:.3f} {was.top:.3f} {was.right:.3f} {was.bottom:.3f}':>34}"
              f"{f'{now.left:.3f} {now.top:.3f} {now.right:.3f} {now.bottom:.3f}':>34}"
              f"{iou(was, now):7.3f}")

    before = score_geometry(typed, typed, image)
    after = score_geometry(snapped, snapped, image)
    print(f"{'':11}{'covered':>10}{'splits':>8}{'doubles':>9}")
    print(f"{'typed':11}{before.covered:10.2f}{before.splits:8d}{before.doubles:9d}")
    print(f"{'snapped':11}{after.covered:10.2f}{after.splits:8d}{after.doubles:9d}")

    if write:
        rewrite_builder(fixture, snapped)
    return 0


def snap_main(args: argparse.Namespace) -> int:
    """`--snap` over every fixture but the one with real ground truth.

    Run it twice: the second run should report IoU 1.000 on every Zone, which is
    the check that the rewrite landed and that snapping is idempotent. A box
    that still moves on the second pass is a box `snap_to_ink` disagrees with
    itself about.
    """
    from tests.fixtures import IMAGES

    wanted = ([f.strip() for f in args.fixtures.split(",") if f.strip()]
              if args.fixtures else
              [name for name in IMAGES if name != BROWSER_EXACT])
    for fixture in wanted:
        if fixture not in IMAGES:
            raise SystemExit(f"unknown fixture {fixture!r}; "
                             f"known: {', '.join(IMAGES)}")
        snap_fixture(fixture, args.write)

    if args.write:
        print("\nnow run: python tools/write_expected_ir.py")
    else:
        print("\n--write to update the builders")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="update the expected IR in place")
    parser.add_argument("--snap", action="store_true",
                        help="derive the four non-browser fixtures' rectangles "
                             "by snapping the typed ones onto their own ink")
    parser.add_argument("--fixtures", default=None,
                        help="comma-separated, with --snap; default is every "
                             "fixture but invoice_0001")
    args = parser.parse_args()

    if args.snap:
        return snap_main(args)

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
