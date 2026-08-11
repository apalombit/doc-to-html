"""Turn a `--dump` directory into pictures you can look at.

    python tools/inspect_run.py /tmp/dth-dump/qwen3-vl_4b/invoice_0001 \
        --source example/invoice.png \
        --expected tests/fixtures/invoice_0001.expected.json

Writes a folder of PNGs and an `index.html` contact sheet. Open that one file
and you see, in order: the page as the layout model saw it, the boxes it
returned drawn on the page, the boxes the fixture says are right, the two
superimposed, **the output HTML rasterised**, and the actual crop each
extraction pass was given beside the text it returned from that crop.

The rendered panel is the only one showing the artefact a reader would be handed
rather than an intermediate stage, and docs/adr/0002 asks for structural
fidelity to be judged by eye against the Source Image — which needs both in one
place. It appears when the Conversion finished; a run that aborted has no
document to show.

**Why this exists.** A bake-off run costs about five minutes on the 8 GB M1, and
`--dump` preserves its answers as JSON. Reasoning about a page from seven
normalised rectangles is how `docs/specs/0001` came to record that Zone 6 was
"invented" over "nothing is printed here", when in fact it holds the last line
item and the total. Nobody looking at a picture would have written that down.
This reads the dump rather than the model, so the expensive part is paid once
and every question after it is free.

Deliberately not wired into the pipeline. It is a darkroom for a run that has
already happened, and it never calls Ollama.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html import geometry_score  # noqa: E402
from doc_to_html.engines.lenient import canonicalise  # noqa: E402
from doc_to_html.ir import BBox  # noqa: E402
from doc_to_html.preprocess import (  # noqa: E402
    LAYOUT_LONG_EDGE,
    PAD_X,
    PAD_Y,
    ImageArray,
    rectify,
)
from doc_to_html.wire import (  # noqa: E402
    LayoutResponse,
    MappingError,
    schema_of,
    zones_from_layout,
)

MODEL_COLOUR = (220, 50, 50)
EXPECTED_COLOUR = (30, 150, 70)


@dataclass(frozen=True)
class Box:
    """One rectangle in normalised page coordinates, with what it claims to be."""

    left: float
    top: float
    right: float
    bottom: float
    kind: str
    role: str
    band: int | None = None
    column: int | None = None

    @property
    def label(self) -> str:
        where = "" if self.band is None else f" b{self.band}c{self.column}"
        return f"{self.kind}/{self.role}{where}"

    def pixels(self, size: tuple[int, int]) -> tuple[int, int, int, int]:
        width, height = size
        return (
            int(self.left * width), int(self.top * height),
            int(self.right * width), int(self.bottom * height),
        )

    @property
    def bbox(self) -> BBox:
        """The rectangle alone, as the domain type the shared ruler measures.

        A `Box` is a rectangle plus what a run claimed about it — kind, role,
        Band, column — which the scorer has no business knowing. This is the
        seam between the two.
        """
        return BBox(self.left, self.top, self.right, self.bottom)

    def area(self) -> float:
        return geometry_score.area(self.bbox)

    def iou(self, other: Box) -> float:
        return geometry_score.iou(self.bbox, other.bbox)

    def covered_by(self, other: Box) -> float:
        """How much of *this* box sits inside `other`, as a fraction of this one.

        Asymmetric on purpose. IoU cannot tell "the model split one Zone in two"
        from "the model invented a Zone", because both score low. This can: each
        half of a split is almost entirely covered by the reference Zone it came
        from, while a genuinely spurious box is not covered by anything.
        """
        return geometry_score.covered_by(self.bbox, other.bbox)


def boxes_from_layout(dump: Path) -> list[Box]:
    """The geometry the Conversion ran on, in wire form.

    Prefers `zones_used.json` — what the Document actually held — and falls back
    to the raw layout answer for a dump taken before that existed.

    Takes the **last** `*_layout.json` that parses, not the first. `ask` retries
    a truncated pass with a doubled budget and the dump records every call, so a
    retried run has `00_layout.json` holding the discarded attempt — which on
    `minimax-m3` was a YAML bullet list, and made this tool die on a run that had
    in fact succeeded.

    The dump holds the **raw** answer: the bake-off's recorder sits inside the
    lenient wrapper, so what a model really said is what lands on disk. That is
    the right thing to keep, and it means the same repair has to be applied here
    to read it back.
    """
    used = dump / "zones_used.json"
    if used.exists():
        # What the Conversion ran on, which is not always what the model said.
        # Run 39 converted on boxes the Orchestrator had snapped onto the ink
        # while this tool drew and scored the raw layout answer, so its contact
        # sheet described a document that was never produced. Prefer the record
        # of what happened over the record of what was proposed.
        return [
            Box(
                left=z["left"], top=z["top"], right=z["right"], bottom=z["bottom"],
                kind=z.get("kind", "?"), role=z.get("role", "?"),
                band=z.get("band"), column=z.get("column"),
            )
            for z in json.loads(used.read_text())
        ]

    schema = schema_of(LayoutResponse)
    for path in sorted(dump.glob("*_layout.json"), reverse=True):
        try:
            data = json.loads(canonicalise(path.read_text(), schema))
        except json.JSONDecodeError:
            continue
        zones = data.get("zones") if isinstance(data, dict) else None
        if not zones:
            continue
        return [
            Box(
                left=z["left"], top=z["top"], right=z["right"], bottom=z["bottom"],
                kind=z.get("kind", "?"), role=z.get("role", "?"),
                band=z.get("band"), column=z.get("column"),
            )
            for z in zones
        ]
    raise SystemExit(f"no parseable layout answer in {dump}")


def boxes_from_expected(path: Path) -> list[Box]:
    """The hand-authored reference IR, which stores a `bbox` object per Zone.

    Read through the shared loader, so the rectangles this draws are the same
    rectangles the probes score against — a picture that disagreed with the
    number under it would be worse than no picture.
    """
    found = []
    for zone in geometry_score.expected_zones(path):
        if zone.box is None:
            print(f"  expected zone {zone.index} has no bbox, skipped",
                  file=sys.stderr)
            continue
        found.append(
            Box(
                left=zone.box.left, top=zone.box.top,
                right=zone.box.right, bottom=zone.box.bottom,
                kind=zone.kind, role=zone.role,
                band=zone.band, column=zone.column,
            )
        )
    return found


def bands_validate(dump: Path) -> bool | None:
    """Whether this run's Bands and columns would survive mapping into the IR.

    Reported beside the ink because run 25 taught that the two move
    independently: that answer passed Band validation and scored 0.21 IoU,
    describing a page it had not been shown. A summary carrying only one of them
    would have called it a success.
    """
    schema = schema_of(LayoutResponse)
    for path in sorted(dump.glob("*_layout.json"), reverse=True):
        try:
            parsed = LayoutResponse.model_validate_json(
                canonicalise(path.read_text(), schema))
        except Exception:  # noqa: BLE001 - unparseable is not "invalid Bands"
            continue
        try:
            zones_from_layout(parsed)
        except MappingError:
            return False
        return True
    return None


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                      "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw(page: Image.Image, boxes: list[Box], colour: tuple[int, int, int],
         *, prefix: str, width: int = 3, dash: bool = False) -> Image.Image:
    """Outline each box on a copy of the page and number it in a filled tag."""
    canvas = page.convert("RGB").copy()
    pen = ImageDraw.Draw(canvas)
    font = _font(13)

    for index, box in enumerate(boxes):
        left, top, right, bottom = box.pixels(canvas.size)
        if dash:
            _dashed(pen, (left, top, right, bottom), colour, width)
        else:
            pen.rectangle((left, top, right, bottom), outline=colour, width=width)

        tag = f"{prefix}{index} {box.label}"
        text_box = pen.textbbox((0, 0), tag, font=font)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        # Tags on boxes that reach the top edge would be clipped; drop them inside.
        tag_top = top if top > text_height + 6 else top + 2
        pen.rectangle(
            (left, tag_top - text_height - 6, left + text_width + 8, tag_top),
            fill=colour,
        )
        pen.text((left + 4, tag_top - text_height - 4), tag, fill="white", font=font)

    return canvas


def _dashed(pen: ImageDraw.ImageDraw, rect: tuple[int, int, int, int],
            colour: tuple[int, int, int], width: int, step: int = 9) -> None:
    left, top, right, bottom = rect
    for x in range(left, right, step * 2):
        pen.line((x, top, min(x + step, right), top), fill=colour, width=width)
        pen.line((x, bottom, min(x + step, right), bottom), fill=colour, width=width)
    for y in range(top, bottom, step * 2):
        pen.line((left, y, left, min(y + step, bottom)), fill=colour, width=width)
        pen.line((right, y, right, min(y + step, bottom)), fill=colour, width=width)


def both(page: Image.Image, model: list[Box], expected: list[Box]) -> Image.Image:
    """Expected in green, dashed; model in red, solid. The one picture that matters."""
    canvas = draw(page, expected, EXPECTED_COLOUR, prefix="want ", dash=True)
    return draw(canvas, model, MODEL_COLOUR, prefix="got ")


def layout_input(page: Image.Image, long_edge: int) -> Image.Image:
    """The page at the size the layout pass is actually given.

    `resize_long_edge` never enlarges, so this is a no-op on a source already
    smaller than the budget — which is itself worth seeing, because that no-op
    is what hid the missing downscale until `LAYOUT_LONG_EDGE` was split out.
    """
    longest = max(page.size)
    if longest <= long_edge:
        return page.convert("RGB").copy()
    scale = long_edge / longest
    return page.convert("RGB").resize(
        (round(page.width * scale), round(page.height * scale)), Image.LANCZOS
    )


def crop_for(page: Image.Image, box: Box) -> Image.Image:
    """The pixels an Extractor really sent, padding included.

    Imports the pads from `preprocess` rather than restating them. A diagnostic
    that draws a different crop from the one the pipeline takes is worse than no
    diagnostic — it was reasoning from exactly that kind of mismatch that put
    "Zone 6 is invented" in the spec.
    """
    width, height = page.size
    left = int(max(0.0, box.left - PAD_X) * width)
    right = int(min(1.0, box.right + PAD_X) * width)
    top = int(max(0.0, box.top - PAD_Y) * height)
    bottom = int(min(1.0, box.bottom + PAD_Y) * height)
    if right - left < 1 or bottom - top < 1:
        return Image.new("RGB", (10, 10), "black")
    return page.convert("RGB").crop((left, top, right, bottom))


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def rasterise(html: Path, out: Path, width: int) -> Image.Image | None:
    """Screenshot the rendered document, so it can be seen beside its source.

    Every other picture here shows an intermediate stage. This is the artefact a
    reader would actually be handed, and docs/adr/0002 asks for fidelity to be
    judged by eye against the Source Image — which needs the two side by side.

    Headless Chrome because it is the one renderer already on this machine.
    Returns None rather than raising if it is missing: a contact sheet without
    this panel is still worth having, and a diagnostic tool that dies on a
    machine with no browser is worse than one that quietly omits a panel.
    """
    if not CHROME.exists():
        print("no headless Chrome, skipping the rendered-document panel",
              file=sys.stderr)
        return None

    shot = out / "05_rendered.png"
    result = subprocess.run(
        [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--screenshot={shot}", f"--window-size={width},2400",
         html.resolve().as_uri()],
        capture_output=True, timeout=90,
    )
    if not shot.exists():
        print(f"Chrome wrote no screenshot: {result.stderr.decode()[:300]}",
              file=sys.stderr)
        return None

    page = Image.open(shot).convert("RGB")
    return _trim(page)


def _trim(page: Image.Image) -> Image.Image:
    """Cut the empty tail off a fixed-height screenshot.

    The window height is a guess large enough for any document, so most shots end
    in a tall band of blank page. Trimming keeps the panel readable beside a
    source image that has no such band.

    The background colour is sampled from the bottom-right pixel rather than
    assumed. An earlier version tested for "lighter than 250" and did nothing at
    all, because this project's stylesheet renders dark and every row was already
    below the threshold.
    """
    background = page.getpixel((page.width - 1, page.height - 1))
    used = ImageChops.difference(
        page, Image.new("RGB", page.size, background)  # type: ignore[arg-type]
    ).getbbox()
    if used is None:
        return page
    return page.crop((0, 0, page.width, min(page.height, used[3] + 24)))


def pass_answers(dump: Path) -> list[tuple[str, str]]:
    """(file stem, answer) for every extraction pass, one per Zone, in order.

    Retries are collapsed. `ask` retries a truncated pass with a doubled budget
    and the dump records both calls, so a naive listing has more answers than
    Zones and pairs every Zone after the first with the wrong text.

    A discarded attempt is recognised as *unparseable, and followed by another
    call to the same pass*. That is a heuristic, and it has to be: two adjacent
    Zones of the same Kind produce two `pairs` files that look exactly like one
    retried `pairs`, so the name alone cannot separate them. Parseability is the
    signal that can, because a retry only ever follows an answer that failed.
    """
    entries: list[tuple[str, str, bool]] = []
    for path in sorted(dump.glob("*.json")):
        if path.name.endswith("_layout.json"):
            continue
        raw = path.read_text()
        try:
            entries.append((path.stem, json.dumps(json.loads(raw), indent=2), True))
        except json.JSONDecodeError:
            entries.append((path.stem, f"(did not parse, retried)\n\n{raw}", False))

    kept = []
    for index, (stem, text, parsed) in enumerate(entries):
        following = entries[index + 1] if index + 1 < len(entries) else None
        retried = (
            not parsed
            and following is not None
            and following[0].split("_", 1)[-1] == stem.split("_", 1)[-1]
        )
        if not retried:
            kept.append((stem, text))
    return kept


def _embed(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def layout_prompt(dump: Path) -> str:
    """The exact prompt the layout pass was given, as `--dump` recorded it.

    Shown at the top of the sheet rather than referred to. Comparing two runs is
    the whole activity, and a sheet that does not carry its own prompt makes the
    reader reconstruct it from a git log that may have moved on since.
    """
    path = dump / "00_layout.prompt.txt"
    if not path.exists():
        return ("(no prompt recorded — this dump predates prompt capture, so "
                "which wording produced it is not on disk)")
    return path.read_text()


def contact_sheet(title: str, panels: list[tuple[str, str, str, Image.Image]],
                  zones: list[tuple[str, Image.Image, str]],
                  geometry: str, prompt: str, paths: str) -> str:
    """One self-contained page: every image inline, so it survives being moved."""
    parts = [
        "<style>",
        "body{font:14px -apple-system,system-ui,sans-serif;margin:0;padding:32px;",
        "background:#1a1a1a;color:#e8e8e8;max-width:1100px}",
        "h1{font-size:20px} h2{font-size:16px;margin-top:36px;border-bottom:1px solid #444;",
        "padding-bottom:6px} img{max-width:100%;border:1px solid #444;background:#fff}",
        ".note{color:#aaa;margin:4px 0 12px} pre{background:#242424;padding:12px;",
        "border-radius:4px;overflow-x:auto;font-size:12px;line-height:1.45}",
        ".zone{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;",
        "align-items:start;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #333}",
        "@media(max-width:760px){.zone{grid-template-columns:1fr}}",
        "</style>",
        f"<h1>{html.escape(title)}</h1>",
        "<h2>Where this came from</h2>",
        f"<pre>{html.escape(paths)}</pre>",
        "<h2>The layout prompt that produced it</h2>",
        f"<pre>{html.escape(prompt)}</pre>",
    ]

    for _slug, heading, note, image in panels:
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        parts.append(f"<p class=note>{html.escape(note)}</p>")
        parts.append(f'<img src="data:image/png;base64,{_embed(image)}">')

    parts.append("<h2>Geometry</h2>")
    parts.append(f"<pre>{html.escape(geometry)}</pre>")

    parts.append("<h2>What each crop returned</h2>")
    parts.append("<p class=note>Left: the pixels sent. Right: the answer that came back."
                 " A wrong answer beside a wrong crop is an extraction problem that is"
                 " really a layout problem.</p>")
    for heading, crop, answer in zones:
        parts.append("<div class=zone>")
        parts.append(f'<div><b>{html.escape(heading)}</b><br>'
                     f'<img src="data:image/png;base64,{_embed(crop)}"></div>')
        parts.append(f"<div><pre>{html.escape(answer)}</pre></div>")
        parts.append("</div>")

    return "\n".join(parts)


def _ink_report(model: list[Box], expected: list[Box], page: ImageArray,
                valid: bool | None = None) -> str:
    """The same boxes, scored against the pixels instead of against the fixture.

    Reported beside the IoU and never instead of it, and **nothing here rejects a
    layout**. `splits` and `doubles` are new enough that their thresholds have
    been measured on exactly one page, and spec 0002 records four prompt changes
    that were obviously right and cost Band numbering. A guard tuned against a
    ruler this young would reject good geometry.

    The reference row is the floor. The fixture's own rectangles were typed by
    hand, so what they score is how well the ruler can possibly be satisfied on
    this page — a model row is only readable against it.
    """
    got = [box.bbox for box in model]
    want = [box.bbox for box in expected]
    scored = geometry_score.score_geometry(got, want, page, valid=valid)
    floor = geometry_score.score_geometry(want, want, page, valid=True)

    def row(label: str, score: geometry_score.GeometryScore) -> str:
        says = {True: "yes", False: "NO", None: "?"}[score.valid]
        return (f"{label:11}{score.zones:7d}{score.iou:8.2f}{score.covered:10.2f}"
                f"{score.splits:8d}{score.doubles:9d}{says:>7}")

    lines = [
        "against the ink  (reported, never enforced — nothing here rejects a layout)",
        f"{'':11}{'zones':>7}{'iou':>8}{'covered':>10}{'splits':>8}"
        f"{'doubles':>9}{'valid':>7}",
        row("model", scored),
        row("reference", floor),
        "",
    ]
    for index, box in enumerate(model):
        one = geometry_score.score_geometry([box.bbox], want, page)
        note = ""
        if one.splits:
            note = f"cuts {one.splits} mass{'es' if one.splits > 1 else ''} of ink"
        if one.doubles:
            note = (note + "; " if note else "") + "holds two separated masses"
        if note:
            lines.append(f"got {index}  {box.label:22} {note}")
    return "\n".join(lines)


def geometry_report(model: list[Box], expected: list[Box],
                    page: ImageArray | None = None,
                    valid: bool | None = None) -> str:
    """Per-box IoU, and the coverage that tells a split from an invention.

    Both numbers are printed because they disagree in the interesting case, and
    the disagreement is the finding. A box with low IoU and high coverage is half
    of a Zone the model cut in two. A box with low IoU and low coverage is one it
    made up. Ranking by IoU alone calls both of them the same thing.
    """
    lines = []
    if not expected:
        lines.append("no expected IR given, so nothing to compare against")
        for index, box in enumerate(model):
            lines.append(f"got {index}  {box.label:22} "
                         f"({box.left:.2f},{box.top:.2f},{box.right:.2f},{box.bottom:.2f})")
        return "\n".join(lines)

    lines.append(f"{'':4} {'model box':38} {'best IoU':>10}  {'covered by':>10}  verdict")
    reference = [want.bbox for want in expected]
    for index, box in enumerate(model):
        best, best_iou = geometry_score.best_match(box.bbox, reference)
        covers = [(box.covered_by(want), i) for i, want in enumerate(expected)]
        cover, cover_index = max(covers)

        if best_iou >= 0.5:
            verdict = f"matches want {best}"
        elif cover >= 0.8:
            verdict = f"inside want {cover_index} - a SPLIT, not spurious"
        else:
            verdict = "no reference accounts for it"
        lines.append(
            f"got {index}  {box.label:22} "
            f"({box.left:.2f},{box.top:.2f},{box.right:.2f},{box.bottom:.2f}) "
            f"{best_iou:>10.2f}  {cover:>10.2f}  {verdict}"
        )

    mean = geometry_score.mean_best_iou([box.bbox for box in model], reference)
    lines.append("")
    lines.append(f"mean best IoU over {len(model)} model boxes: {mean:.2f}")

    claimed = [max(want.covered_by(box) for box in model) for want in expected]
    for index, (want, share) in enumerate(zip(expected, claimed)):
        if share < 0.9:
            lines.append(f"want {index} ({want.label}) is only {share:.0%} covered by "
                         f"any single model box")

    if page is not None:
        lines.append("")
        lines.append(_ink_report(model, expected, page, valid))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dump", type=Path,
                        help="a --dump directory, e.g. /tmp/dth-dump/qwen3-vl_4b/invoice_0001")
    parser.add_argument("--source", type=Path, required=True, help="the Source Image")
    parser.add_argument("--expected", type=Path, default=None,
                        help="hand-authored expected IR, to draw alongside")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory (default: ./debug/<dump name>)")
    parser.add_argument("--long-edge", type=int, default=LAYOUT_LONG_EDGE)
    args = parser.parse_args(argv)

    if not (args.dump / "00_layout.json").exists():
        print(f"no 00_layout.json in {args.dump}", file=sys.stderr)
        return 1

    out = args.out or Path("debug") / args.dump.name
    out.mkdir(parents=True, exist_ok=True)

    page = Image.open(args.source)
    model = boxes_from_layout(args.dump)
    expected = boxes_from_expected(args.expected) if args.expected else []

    seen = layout_input(page, args.long_edge)
    panels = [
        ("01_layout_input", "The page as the layout pass saw it",
         f"{page.width}x{page.height} source, sent at {seen.width}x{seen.height} "
         f"(budget {args.long_edge}).", seen),
        ("02_model_boxes", "Boxes the model returned",
         f"{len(model)} Zones.", draw(page, model, MODEL_COLOUR, prefix="got ")),
    ]
    if expected:
        panels.append(("03_expected_boxes", "Boxes the fixture says are right",
                       f"{len(expected)} Zones.",
                       draw(page, expected, EXPECTED_COLOUR, prefix="want ", dash=True)))
        panels.append(("04_superimposed", "Both, superimposed",
                       "Green dashed is the reference; red solid is the model.",
                       both(page, model, expected)))

    document = args.dump / "document.html"
    if document.exists():
        rendered = rasterise(document, out, width=page.width)
        if rendered is not None:
            panels.append((
                "05_rendered", "What we actually produced",
                "The output HTML, rasterised. Judge it against the Source Image at "
                "the top — structural fidelity is an eye judgement, per "
                "docs/adr/0002, and this is the only panel showing the artefact a "
                "reader would be handed.",
                rendered,
            ))
    else:
        print(f"no document.html in {args.dump} — the Conversion did not finish, "
              "so there is nothing rendered to show", file=sys.stderr)

    answers = pass_answers(args.dump)
    zones = []
    for index, box in enumerate(model):
        crop = crop_for(page, box)
        answer = answers[index][1] if index < len(answers) else "(no answer dumped)"
        name = answers[index][0] if index < len(answers) else f"{index:02d}_?"
        zones.append((f"got {index}  {box.label}  -> {name}", crop, answer))
        crop.save(out / f"zone_{index:02d}_{box.kind}.png")

    # The ruler measures the Rectified Image, because that is the page the
    # Orchestrator put the boxes on. The panels above draw on the Source Image,
    # which is the page a reader recognises; on a photograph the two differ by a
    # deskew and a warp, and scoring the wrong one would quietly measure the
    # rectifier instead of the layout pass.
    report = geometry_report(model, expected, rectify(args.source).image,
                             bands_validate(args.dump))
    print(report)

    for slug, _heading, _note, image in panels:
        image.save(out / f"{slug}.png")

    prompt = layout_prompt(args.dump)
    paths = "\n".join([
        f"source image  {args.source}",
        f"expected IR   {args.expected}",
        f"raw dump      {args.dump.resolve()}",
        f"this report   {out.resolve()}",
    ])
    (out / "layout_prompt.txt").write_text(prompt)

    sheet = out / "index.html"
    sheet.write_text(contact_sheet(f"{args.dump.parent.name} / {args.dump.name}",
                                   panels, zones, report, prompt, paths))
    print(f"\n{paths}\n\nwrote {sheet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
