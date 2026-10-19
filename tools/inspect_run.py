"""Turn a `--dump` directory into pictures you can look at.

    python tools/inspect_run.py /tmp/dth-dump/qwen3-vl_4b/invoice_0001 \
        --source example/invoice.png

Writes a folder of PNGs and an `index.html` contact sheet. Open that one file
and you see, in order: the Source Image, the page as the layout pass saw it
(`Rectified.image`, warped and equalised), the boxes it returned drawn on that
page, **the output HTML rasterised**, and the actual crop each extraction pass
was given beside the text it returned from that crop.

**This is the per-document view, and it answers one question: how was *this*
document converted, step by step.** The comparative question — how does every
document's render look beside its source — is
`debug/runs/<label>/report.html`, built by `doc_to_html.report`, and that is
the one to open first. Both come out of the same run.

`--expected` is still accepted and nothing passes it any more: the committed
`*.expected.json` were the serialised acceptance set and spec 0007 Thread 0
deleted them. The two panels it feeds are skipped when it is absent.

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
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html import geometry_score  # noqa: E402
from doc_to_html.ir import BBox, Kind, Role, Zone  # noqa: E402
from doc_to_html.preprocess import (  # noqa: E402
    PAD_X,
    PAD_Y,
    ImageArray,
    rectify,
)
from doc_to_html.trace import (  # noqa: E402
    TRACE_VERSION,
    Call,
    Disposition,
    Event,
    Stage,
    Trace,
)
from doc_to_html.wire import (  # noqa: E402
    CaptionResponse,
    MappingError,
    TableResponse,
    _join_split_header_row,
    _without_empty_rows,
    validate_bands,
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
    to the raw layout answer for a dump taken before that existed — read as
    plain JSON, now the vision layout pass and its wire schema are deleted.

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

    for path in sorted(dump.glob("*_layout.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
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
    """Reference rectangles out of an IR-shaped JSON, when one is supplied.

    Nothing supplies one any more. `tools/iterate.sh` stopped passing
    `--expected` when spec 0007 Thread 0 deleted the committed
    `*.expected.json` files, and the panels this feeds are skipped when the
    argument is absent. Kept because the shape is `Document.to_json()`'s, so
    anyone diagnosing a run against a saved IR still has a way to draw it.
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
    for path in sorted(dump.glob("*_layout.json"), reverse=True):
        try:
            zones = [
                Zone(kind=Kind.PROSE, role=Role.BODY,
                     band=z["band"], column=z["column"],
                     bbox=BBox(z["left"], z["top"], z["right"], z["bottom"]))
                for z in json.loads(path.read_text())["zones"]
            ]
        except Exception:  # noqa: BLE001 - unparseable is not "invalid Bands"
            continue
        try:
            validate_bands(zones)
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


def layout_input(page: Image.Image, long_edge: int | None) -> Image.Image:
    """The page at the size the layout stage is given.

    Whole, by default: the detector is handed the rectified page. `long_edge`
    draws it as the deleted vision layout pass was sent it, for an old dump.
    `resize_long_edge` never enlarges, so a downscale is a no-op on a source
    already smaller than the budget — which is what once hid a missing one.
    """
    longest = max(page.size)
    if long_edge is None or longest <= long_edge:
        return page.convert("RGB").copy()
    scale = long_edge / longest
    return page.convert("RGB").resize(
        (round(page.width * scale), round(page.height * scale)), Image.LANCZOS
    )


def crop_for(page: Image.Image, box: Box, *,
             pad_top: bool = True) -> Image.Image:
    """The pixels an Extractor really sent, padding included.

    Imports the pads from `preprocess` rather than restating them. A diagnostic
    that draws a different crop from the one the pipeline takes is worse than no
    diagnostic — it was reasoning from exactly that kind of mismatch that put
    "Zone 6 is invented" in the spec.

    `pad_top=False` for the one crop that is not an Extractor's: a Kind question
    whose caption band was withheld. Its recorded box already sits at the cut, so
    re-adding `PAD_Y` above it would draw back a sliver of the very band whose
    absence the panel exists to show.
    """
    width, height = page.size
    left = int(max(0.0, box.left - PAD_X) * width)
    right = int(min(1.0, box.right + PAD_X) * width)
    top = int(max(0.0, box.top - (PAD_Y if pad_top else 0.0)) * height)
    bottom = int(min(1.0, box.bottom + PAD_Y) * height)
    if right - left < 1 or bottom - top < 1:
        return Image.new("RGB", (10, 10), "black")
    return page.convert("RGB").crop((left, top, right, bottom))


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

LIGHT = "--blink-settings=preferredColorScheme=1"
"""Pin `prefers-color-scheme` to light. Spec 0007 Thread 0, step 4.

This call shelled out with no colour-scheme flag, so it inherited the host's
dark mode and `render.py`'s `@media (prefers-color-scheme: dark)` fired. The
Source Image beside it is light, which means **every visual comparison
eyeballed in this project before 2026-09-18 was against an inverted page**.
Measured on this machine: without the flag,
`matchMedia('(prefers-color-scheme: dark)').matches` is `true`.

`doc_to_html.projection.LIGHT` is the same flag, and both sides of every
comparison go through one or the other.
"""


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
        [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars", LIGHT,
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


NOT_EXTRACTION = ("_layout.json", "_classify.json", "_caption.json")
"""Dump files that are not one Zone's contents, and must not be paired with one.

Every pass added in front of extraction has to be listed here, and `_classify`
never was: since #15 put a classify call before every Zone, this paired Zone 0
with `00_classify.json` and every later Zone with another classify verdict —
run 69's `invoice_0001` dump has six of them sorting ahead of the first
extraction answer.

**Scope, stated honestly.** Only the fallback path reads this, for a dump written
before `trace.json` existed, and that path already prints a warning that it is
reconstructing from call order. So this was a wrong answer with a caveat attached
rather than a silent one. It is fixed because a caveat is not a reason to leave
a reconstruction wrong when the correction is a filename filter.

That the list is a constant rather than a rule is the remaining weakness: a dump
is filenames, and only the Orchestrator knows which passes read a Zone. The Trace
knows too, which is why `zone_lives` and the timeline read that instead — and why
a dump that has one never reaches this function.
"""


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
        # `bakeoff --dump` writes one `NN_<pass>.json` per call. Anything else in
        # the directory — `trace.json`, `zones_used.json` — is the run describing
        # itself, not a model answering.
        if not re.match(r"\d+_", path.name) or path.name.endswith(NOT_EXTRACTION):
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


def layout_prompt(dump: Path, trace: Trace | None = None) -> str:
    """The exact prompt the layout pass was given, as `--dump` recorded it.

    Shown at the top of the sheet rather than referred to. Comparing two runs is
    the whole activity, and a sheet that does not carry its own prompt makes the
    reader reconstruct it from a git log that may have moved on since.

    **Two different reasons there may be no prompt, and they must not read the
    same.** A dump from before prompt capture is missing a record. A dump from a
    `DTH_LAYOUT_DETECTOR` run is not missing anything — the geometry came from a
    trained detector, and there was no wording involved to record. A reader who
    saw "predates prompt capture" on a detector run would go looking for a
    recording bug that is not there.
    """
    path = dump / "00_layout.prompt.txt"
    if path.exists():
        return path.read_text()

    if trace is not None and any(
            event.stage is Stage.LAYOUT and event.data.get("calls") == 0
            for event in trace.events):
        return ("(no prompt — this run's geometry came from a layout detector, "
                "not from a model, so there was no wording to record. See "
                "dth_env.txt for which detector.)")
    return ("(no prompt recorded — this dump predates prompt capture, so "
            "which wording produced it is not on disk)")


def read_trace(dump: Path) -> Trace | None:
    """The Conversion's own account of itself, when the run recorded one.

    None for every run taken before `trace.json` existed, and for any
    `trace_version` this tool does not know — a half-understood shape rendered
    confidently is the failure this file keeps relearning, so an unfamiliar
    version goes to the same fallback as no trace at all.
    """
    path = dump / "trace.json"
    if not path.exists():
        return None
    trace = Trace.from_json(path.read_text())
    if trace.version != TRACE_VERSION:
        print(f"trace.json is version {trace.version}, this tool reads "
              f"{TRACE_VERSION} — falling back", file=sys.stderr)
        return None
    return trace


def run_settings(dump: Path) -> list[tuple[str, str]]:
    """How the run was configured, from the files `iterate.sh` already writes.

    `dump` is `<run>/dump/<model>/<fixture>`, so the run directory is three up.
    Everything here is optional: a dump inspected on its own, away from the run
    that produced it, still builds a sheet — it just cannot say what commit it
    was taken at.
    """
    run = dump.parents[2]
    files = [
        ("commit", "commit.txt"), ("host", "host.txt"),
        ("layout long edge", "layout_long_edge.txt"),
        ("fixtures", "fixtures.txt"),
    ]
    rows = []
    for label, name in files:
        path = run / name
        if path.exists():
            rows.append((label, path.read_text().strip()))

    env = run / "dth_env.txt"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                rows.append((key, value))

    resident = run / "ollama_ps_after.txt"
    if resident.exists():
        lines = resident.read_text().splitlines()
        if len(lines) > 1 and lines[1].strip():
            rows.append(("resident during the run", " ".join(lines[1].split())))
    return rows


STAGE_TITLES = {
    Stage.RECTIFY: "RECTIFY",
    Stage.LAYOUT: "LAYOUT",
    Stage.SNAP: "SNAP",
    Stage.CLASSIFY: "CLASSIFY",
    Stage.EXTRACT: "EXTRACT",
    Stage.PROBE: "PROBE",
    Stage.AUDIT: "AUDIT",
    Stage.RENDER: "RENDER",
}


def stage_numbers(trace: Trace) -> dict[int, str]:
    """`seq` -> "4.3", the stage's position and the step's position within it.

    Numbered from the stages that actually ran rather than from the `Stage` enum,
    so a run that never reached extraction does not leave a gap where a reader
    would look for one.
    """
    order: list[Stage] = []
    for event in trace.events:
        if event.stage not in order:
            order.append(event.stage)

    numbers, counts = {}, {stage: 0 for stage in order}
    for event in trace.events:
        counts[event.stage] += 1
        numbers[event.seq] = f"{order.index(event.stage) + 1}.{counts[event.stage]}"
    return numbers


def handled(event: Event, trace: Trace) -> str:
    """The one line saying what became of this step's input. Never empty.

    Composed here rather than in the Orchestrator on purpose. `trace.py` records
    primitives so that building a sentence can never raise inside a Conversion;
    the sentence is this tool's job, where the worst a mistake can do is misword a
    report. The vocabulary is fixed by `Disposition` so the sheet reads the same
    way at every step.
    """
    data = event.data
    if event.step == "empty_zone":
        return (f"skipped — the crop carries {data.get('ink_fraction', 0):.1%} "
                f"ink, under the {data.get('threshold', 0):.1%} floor, so there "
                "is nothing here to classify")
    if event.step == "snap_to_ink":
        if not data.get("enabled"):
            return f"skipped — {data.get('reason', 'the snap is off')}"
        if data.get("reverted"):
            return f"kept — {data.get('reason', 'the snap was refused')}"
        moved = len(event.changed)
        return (f"overridden — {moved} of {len(data.get('before', []))} boxes "
                "moved onto their ink; the Engine's own coordinates were "
                "replaced")
    if event.step == "read_caption":
        if event.disposition is Disposition.SKIPPED:
            return f"skipped — {data.get('reason', 'the caption pass is off')}"
        if event.disposition is Disposition.REJECTED:
            return (f"rejected — {data.get('error', 'the call failed')}. "
                    f"{data.get('consequence', '')}")
        read = caption_verdict(
            trace.calls[event.call] if event.call is not None else None
        )
        if event.disposition is Disposition.KEPT:
            if data.get("vetoed"):
                return (f"kept — the model called {data['vetoed']!r} a caption "
                        f"and the ink refused it: that line holds "
                        f"{data.get('head_columns')} columns and so does what is "
                        "below it, which makes it a grid's heading row. No Title "
                        "is taken and the Kind question keeps the whole crop")
            if read and read[1] == "header":
                return (f"kept — {read[0]!r} is the heading row of a grid, "
                        "not a caption naming the region, so the Zone takes no "
                        "Title and the Kind question keeps the whole crop")
            said = f"{read[0]!r} is" if read else "the first line is"
            return (f"kept — {said} the region's own content, not a caption, so "
                    "the Zone takes no Title and the Kind question keeps the "
                    "whole crop")
        return (f"accepted — {data.get('title')!r} is a caption naming the "
                f"region; it becomes the Zone's Title, and the "
                f"{data.get('cut_row', 0)} rows it occupies are cut from the "
                "crop the Kind question sees")
    if event.step == "classify_zone":
        if event.disposition is Disposition.REJECTED:
            return (f"rejected — {data.get('error', 'the call failed')}. "
                    f"{data.get('consequence', '')}")
        before, after = data.get("kind_before"), data.get("kind_after")
        withheld = (
            "" if not data.get("skip_rows") else
            f", asked without the {data['skip_rows']} caption rows above it"
        )
        if before == after:
            return f"accepted — Kind confirmed as {after}{withheld}"
        return f"accepted — Kind overturned, {before} -> {after}{withheld}"
    if event.step == "classify_caveat" or event.step == "resolution_caveat":
        return f"accepted with a caveat — {data.get('note', '')}"
    if event.step == "extract":
        if event.disposition is Disposition.REROUTED:
            return (f"re-routed — the {data.get('kind_asked')} Extractor reports "
                    f"the region is not {data.get('kind_asked')}: "
                    f"{data.get('error', '')}")
        if event.disposition is Disposition.REJECTED:
            return (f"rejected — {data.get('error', '')} "
                    "The Zone keeps no content and renders as a skeleton.")
        counts = ", ".join(
            f"{data[key]} {key}" for key in ("rows", "pairs", "blocks")
            if data.get(key)
        )
        return f"accepted — {counts or 'no items'} into the Zone"
    if event.step == "reroute":
        return (f"re-routed — read again as prose, Kind corrected "
                f"{data.get('kind_before')} -> {data.get('kind_after')}, "
                f"{data.get('lines', 0)} lines recovered")
    if event.step == "wire_repair":
        return f"repaired — {data.get('what', '')}"
    if event.stage is Stage.PROBE:
        verdict = "reconciles" if data.get("ok") else "DOES NOT reconcile"
        return (f"{'accepted' if data.get('ok') else 'rejected'} — computed "
                f"{data.get('computed')} against a stated {data.get('stated')}, "
                f"{verdict}")
    if event.step == "rectify":
        warped = data.get("warped")
        return ("accepted — a page quadrilateral was found and flattened to"
                if warped else
                "accepted — no page quadrilateral, so the image is used as-is")
    if event.step == "converged":
        return (f"accepted — nothing new entered the system on round "
                f"{data.get('round', 0) + 1}, so the Draft stands")
    return f"{event.disposition.value} — {event.step}"


def result_line(event: Event) -> str:
    """What changed in the Document because of this step, or that nothing did."""
    if event.changed:
        return "; ".join(
            f"{change.path}: {_short(change.before)} -> {_short(change.after)}"
            for change in event.changed
        )
    if event.step == "extract" and event.disposition is Disposition.REJECTED:
        return "the Zone stays incomplete and a Failure is recorded against it"
    if event.step == "classify_zone" and event.disposition is Disposition.REJECTED:
        return "the Zone is left out of extraction entirely"
    return "nothing in the Document changed"


def _short(value: object) -> str:
    if isinstance(value, dict) and "left" in value:
        return (f"({value['left']:.3f},{value['top']:.3f},"
                f"{value['right']:.3f},{value['bottom']:.3f})")
    return str(value)


def caption_verdict(call: Call | None) -> tuple[str, str] | None:
    """(first line, verdict) from a recorded caption answer, or None.

    Read back off the answer rather than carried in the Event, the same way
    `wire_repairs` below re-runs `wire.py` on a recorded response: the real
    schema is imported, so this cannot drift from what the Conversion mapped.

    Worth the trouble because `header` and `content` are indistinguishable by
    effect — both take no Title and cut nothing — so without the verdict the
    sheet can only report that nothing happened, not *why*. "That line is a
    grid's heading row" is the whole reason the third value exists, and a
    diagnostic that cannot show it cannot explain the next regression either.

    `None` for a dump whose calls were not recorded, which is any plain
    `convert()`; the caller falls back to naming no line.
    """
    if call is None or call.pass_name != "caption" or not call.answer:
        return None
    try:
        answer = CaptionResponse.model_validate_json(call.answer)
    except Exception:
        return None
    return answer.first_line.strip(), answer.line_is


def wire_repairs(call: Call) -> list[str]:
    """The repairs `wire.py` applied to this answer, recovered by replaying them.

    The two mappers that quietly change an answer — the split-header join and the
    empty-row drop — run inside `wire.py`, which maps a response without knowing
    which Zone it belongs to. Rather than thread a collector through the shipping
    path for a diagnostic, this re-runs those same functions on the same recorded
    input and reports the difference. Pure functions, the real ones imported
    rather than reimplemented, so this cannot drift from what the Conversion did.

    Silent on anything that does not parse: a truncated answer has its own
    reporting and does not need a second, confusing account here.
    """
    if call.pass_name != "table" or not call.answer:
        return []
    try:
        rows = TableResponse.model_validate_json(call.answer).rows
    except Exception:
        return []

    notes = []
    without_empty = _without_empty_rows(rows)
    dropped = len(rows) - len(without_empty)
    if dropped:
        notes.append(
            f"{dropped} row(s) carrying no cells at all were dropped before the "
            "width check — a row with nothing in it has no value to put in the "
            "wrong column, and rejecting the table over one would have cost "
            "every row beside it"
        )
    joined = _join_split_header_row(without_empty)
    if len(joined) < len(without_empty):
        notes.append(
            f"a header row split across {len(without_empty) - len(joined) + 1} "
            "rows was joined back into one — this model puts `Item` and `Price` "
            "on separate rows when they sit at opposite edges of a wide table"
        )
    return notes


def pipeline_map(trace: Trace) -> str:
    """The shape of the run before any of the detail, one line per stage.

    Read first and read fast: how many calls each stage made, how long it took,
    and what it produced. A reader who only wants "where did the time go" or
    "which stage lost the Zone" should not have to scroll the timeline to find
    out which stage to scroll to.
    """
    order: list[Stage] = []
    for event in trace.events:
        if event.stage not in order:
            order.append(event.stage)

    rows = []
    for position, stage in enumerate(order, start=1):
        events = trace.in_stage(stage)
        calls = sum(event.data.get("calls", 0) or 0 for event in events)
        seconds = sum(event.seconds for event in events)
        dispositions: dict[str, int] = {}
        for event in events:
            dispositions[event.disposition.value] = (
                dispositions.get(event.disposition.value, 0) + 1
            )
        summary = ", ".join(f"{count} {name}" for name, count in dispositions.items())
        rows.append(
            f"{position} {STAGE_TITLES[stage]:<9}"
            f"{f'{calls} call(s)' if calls else 'no calls':<12}"
            f"{summary:<44}{seconds:>7.1f}s"
        )
    return "\n".join(rows)


def zone_lives(trace: Trace, model: list[Box], expected: list[Box]) -> str:
    """One row per Zone: the whole causal chain, stage by stage.

    The at-a-glance answer to "where did this Zone go wrong", which is the
    question every session with this tool has actually been asking. Each cell is
    what one stage decided, so a wrong Kind and a lost extraction are visibly two
    columns apart rather than one undifferentiated failure.
    """
    reference = [box.bbox for box in expected]
    header = (f"{'Zone':<6}{'geometry':<16}{'layout said':<14}"
              f"{'classify said':<16}{'title':<22}{'extracted as':<15}outcome")
    rows = [header, "-" * len(header)]

    for index in range(len(model)):
        events = trace.for_zone(index)
        classify = next((e for e in events if e.step == "classify_zone"), None)
        caption = next((e for e in events if e.step == "read_caption"), None)
        extract = [e for e in events if e.step in ("extract", "reroute")]

        if reference:
            _, best = geometry_score.best_match(model[index].bbox, reference)
            geometry = f"{best:.2f} IoU {'ok' if best >= 0.5 else 'POOR'}"
        else:
            geometry = "no reference"

        said = (classify.data.get("kind_before") if classify else None) or "?"
        got = (classify.data.get("kind_after") if classify else None) or "?"
        if classify and classify.disposition is Disposition.REJECTED:
            got = "FAILED"

        last = extract[-1] if extract else None
        if last is None:
            kind, outcome = "-", "never reached extraction"
        else:
            kind = last.data.get("kind_after") or last.data.get("kind_asked") or "-"
            counts = ", ".join(
                f"{last.data[key]} {key}" for key in ("rows", "pairs", "blocks",
                                                      "lines")
                if last.data.get(key)
            )
            if last.disposition is Disposition.REJECTED:
                outcome = "LOST — renders as a skeleton"
            elif last.step == "reroute":
                outcome = f"re-routed, {counts}"
            else:
                outcome = counts or "empty"

        # Blank when the pass never ran, "—" when it ran and took nothing. The
        # difference is the whole question `DTH_CAPTION_PASS` is being measured
        # on, and one symbol for both would hide it.
        if caption is None:
            title = ""
        else:
            title = _short(caption.data.get("title") or "—")[:20]

        rows.append(f"{index:<6}{geometry:<16}{said:<14}{got:<16}{title:<22}"
                    f"{kind:<15}{outcome}")
    return "\n".join(rows)


def timeline(trace: Trace, page: Image.Image) -> list[str]:
    """Every step of the Conversion, in the order it ran.

    The spine of the sheet. One entry per Event — a model call and a decision get
    the same five lines in the same order, so a reader never has to work out
    which they are looking at. The steps that lose content in this project are
    mostly decisions, and a sheet that showed only the calls would show only the
    half that was working.
    """
    numbers = stage_numbers(trace)
    parts = []

    for event in trace.events:
        call = trace.calls[event.call] if event.call is not None else None
        zone = "" if event.zone_index is None else f" · Zone {event.zone_index}"
        meta = []
        if call is not None:
            meta.append(html.escape(call.model))
        if event.seconds:
            meta.append(f"{event.seconds:.1f}s")
        if call is not None:
            meta.append(f"call {event.call + 1} of {len(trace.calls)}")
            if call.retried:
                meta.append("a retry of the call above, at a doubled budget")

        parts.append(f'<div class=step id="step-{event.seq}">')
        parts.append(
            f'<h3><span class=num>{numbers[event.seq]}</span> '
            f'{STAGE_TITLES[event.stage]}{html.escape(zone)} '
            f'<span class=stepname>{html.escape(event.step)}</span>'
            f'<span class=meta>{" · ".join(meta)}</span></h3>'
        )

        given = _given(event, page)
        if given:
            parts.append(_row("GIVEN", given))
        if call is not None:
            parts.append(_row("ASKED", _details(
                f"the {html.escape(call.pass_name)} prompt, "
                f"{len(call.prompt)} characters",
                html.escape(call.prompt),
            )))
            answered = _details(
                f"{len(call.answer)} characters"
                + (", TRUNCATED" if call.truncated else ""),
                html.escape(call.answer or "(nothing on the content channel)"),
            )
            if call.thinking:
                answered += _details(
                    f"reasoning channel, {len(call.thinking)} characters",
                    html.escape(call.thinking),
                )
            if call.error:
                answered += f'<div class=bad>{html.escape(call.error)}</div>'
            parts.append(_row("ANSWERED", answered))
            for note in wire_repairs(call):
                parts.append(_row("REPAIRED", html.escape(note)))

        parts.append(_row("HANDLED",
                          f'<b>{html.escape(handled(event, trace))}</b>',
                          css="handled"))
        parts.append(_row("RESULT", html.escape(result_line(event))))
        parts.append("</div>")
    return parts


def _row(label: str, body: str, css: str = "") -> str:
    return (f'<div class="line {css}"><span class=label>{label}</span>'
            f'<span class=body>{body}</span></div>')


def _details(summary: str, body: str) -> str:
    return (f"<details><summary>{summary}</summary>"
            f"<pre>{body}</pre></details>")


def _given(event: Event, page: Image.Image) -> str:
    """What this step was handed, described — and shown, when it was pixels.

    The crop is rendered inline rather than linked because "the model misread
    this" and "the model was shown the wrong thing" are the two explanations a
    reader is choosing between, and only one of them survives seeing the picture.
    """
    data = event.data
    crop = data.get("crop")
    if crop and crop.get("box"):
        box = crop["box"]
        cut = crop.get("skip_rows") or 0
        image = crop_for(page, Box(left=box["left"], top=box["top"],
                                   right=box["right"], bottom=box["bottom"],
                                   kind="", role=""),
                         pad_top=not cut)
        described = (
            f"the Zone's own crop, {crop['width']}x{crop['height']}px, cut from "
            f"the rectified page with PAD_X {crop['pad_x']:.0%} / "
            f"PAD_Y {crop['pad_y']:.0%}, {crop['ink_fraction']:.1%} ink"
        )
        if cut:
            described = (
                f"the Zone's crop <b>with its top {cut} rows withheld</b> — the "
                f"caption band, already read as the Title — {crop['width']}x"
                f"{crop['height']}px, {crop['ink_fraction']:.1%} ink. The "
                "Extractor still gets the whole crop; only this question does not"
            )
        if event.step == "read_caption":
            median = data.get("median_gap")
            against = (f"against a median line gap of {median}px"
                       if median is not None else
                       "and only two bands, so no median to compare it against")
            described += (
                f". The first printed line spans rows {data.get('band_top')}"
                f"-{data.get('band_bottom')} of {data.get('lines')} bands, with "
                f"{data.get('gap_below')}px blank below it, {against} — reported "
                "only; no rule keys off that ratio. It holds "
                f"{data.get('head_columns')} column(s) of ink against "
                f"{data.get('body_columns')} below the cut, and *that* pair does "
                "decide: equal counts mean a grid's heading row, which the ink "
                "may refuse a caption for. See CAPTION_PROMPT"
            )
        return (
            described
            + f'<br><img class=crop src="data:image/png;base64,{_embed(image)}">'
        )
    if event.step == "read_caption":
        return (f"the Zone's crop, measured for a caption band before anything "
                f"is asked of it — {data.get('lines', 1)} band(s) of ink")
    if event.step == "detect_zones":
        if data.get("long_edge"):
            return (f"the whole page, downscaled to a {data.get('long_edge')}px "
                    "long edge — finding regions is coarse work and needs no "
                    "glyphs")
        return "the whole rectified page, given to the layout detector"
    if event.step == "rectify":
        return (f"{data.get('source_width')}x{data.get('source_height')} source, "
                f"rectified to {data.get('rectified_width')}x"
                f"{data.get('rectified_height')}")
    if event.step == "snap_to_ink":
        return f"the {len(data.get('before', []))} boxes the layout pass returned"
    if event.step == "empty_zone":
        return f"the Zone's crop, tested for ink before anything is asked of it"
    return ""


STYLE = """
body{font:14px/1.55 -apple-system,system-ui,sans-serif;margin:0;padding:32px;
background:#1a1a1a;color:#e8e8e8;max-width:1180px}
h1{font-size:21px;margin:0 0 4px}
h2{font-size:16px;margin-top:40px;border-bottom:1px solid #444;padding-bottom:6px}
h3{font-size:14px;margin:0 0 10px;font-weight:600}
img{max-width:100%;border:1px solid #444;background:#fff}
img.crop{margin-top:6px;max-height:280px;width:auto}
.note{color:#aaa;margin:4px 0 14px}
pre{background:#111;padding:12px;border-radius:4px;overflow-x:auto;
font-size:12px;line-height:1.45;white-space:pre-wrap;word-break:break-word}
details{margin:2px 0}
summary{cursor:pointer;color:#8ab4f8;font-size:13px}
.step{border-left:3px solid #3a3a3a;padding:14px 0 14px 16px;margin:0 0 6px}
.step:hover{border-left-color:#666}
.num{display:inline-block;min-width:34px;color:#f0a04b;font-variant-numeric:tabular-nums}
.stepname{color:#888;font-weight:400;margin-left:8px;font-family:ui-monospace,monospace;
font-size:12px}
.meta{float:right;color:#777;font-weight:400;font-size:12px}
.line{display:grid;grid-template-columns:92px minmax(0,1fr);gap:12px;margin:3px 0}
.label{color:#777;font-size:11px;letter-spacing:.08em;padding-top:2px}
.body{min-width:0}
.handled .label{color:#f0a04b}
.handled .body{color:#fff}
.bad{color:#ff8a8a}
.zone{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;
align-items:start;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #333}
@media(max-width:760px){.zone{grid-template-columns:1fr}.line{grid-template-columns:1fr}}
table.cfg{border-collapse:collapse;font-size:13px}
table.cfg td{padding:3px 18px 3px 0;vertical-align:top}
table.cfg td:first-child{color:#888}
"""


def contact_sheet(title: str, panels: list[tuple[str, str, str, Image.Image]],
                  zones: list[tuple[str, Image.Image, str]],
                  geometry: str, prompt: str, paths: str,
                  trace: Trace | None = None,
                  settings: list[tuple[str, str]] | None = None,
                  page: Image.Image | None = None,
                  model: list[Box] | None = None,
                  expected: list[Box] | None = None,
                  outcome: str = "") -> str:
    """One self-contained page: every image inline, so it survives being moved.

    With a Trace, the spine of the page is the pipeline in execution order and
    the panels are orientation for it. Without one — every run taken before
    `trace.json` existed — it falls back to the old shape and says so, rather
    than presenting a reconstruction as a record.
    """
    parts = [f"<style>{STYLE}</style>", f"<h1>{html.escape(title)}</h1>"]

    if settings:
        parts.append('<table class=cfg>')
        for label, value in settings:
            parts.append(f"<tr><td>{html.escape(label)}</td>"
                         f"<td>{html.escape(value)}</td></tr>")
        parts.append("</table>")

    parts.append("<h2>Where this came from</h2>")
    parts.append(f"<pre>{html.escape(paths)}</pre>")

    if trace is not None:
        parts.append("<h2>The shape of this run</h2>")
        parts.append("<p class=note>Every stage the Conversion ran, in order, "
                     "with what each decided. Read this first, then scroll to "
                     "whichever stage the question is about.</p>")
        parts.append(f"<pre>{html.escape(pipeline_map(trace))}</pre>")

        if model is not None and expected is not None:
            parts.append("<h2>The life of each Zone</h2>")
            parts.append("<p class=note>One row per Zone, across every stage. A "
                         "wrong Kind and a lost extraction are two different "
                         "columns here, which is the distinction a single "
                         "'6 off' hides.</p>")
            parts.append(f"<pre>{html.escape(zone_lives(trace, model, expected))}</pre>")

    for _slug, heading, note, image in panels:
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        parts.append(f"<p class=note>{html.escape(note)}</p>")
        parts.append(f'<img src="data:image/png;base64,{_embed(image)}">')

    parts.append("<h2>Geometry</h2>")
    parts.append(f"<pre>{html.escape(geometry)}</pre>")

    if trace is not None and page is not None:
        parts.append("<h2>What happened, step by step</h2>")
        parts.append(
            "<p class=note>Every step the Conversion took, in the order it took "
            "them — model calls and decisions alike, in the same shape, because "
            "the steps that lose content here are mostly decisions. "
            "<b>HANDLED</b> is what was done with the answer; <b>RESULT</b> is "
            "what changed in the Document because of it.</p>"
        )
        parts.extend(timeline(trace, page))
    else:
        parts.append("<h2>What each crop returned</h2>")
        parts.append(
            "<p class=note><b>Inferred, not recorded.</b> This dump predates "
            "<code>trace.json</code>, so which answer belongs to which Zone is "
            "reconstructed from call order rather than read from the run. The "
            "passes that run <i>before</i> extraction — layout, classify, "
            "caption — are skipped here so the pairing lands on contents rather "
            "than on verdicts, but two adjacent Zones of the same Kind still "
            "cannot be told from one retried call. Re-run the conversion to get "
            "the real account.</p>"
        )
        for heading, crop, answer in zones:
            parts.append("<div class=zone>")
            parts.append(f'<div><b>{html.escape(heading)}</b><br>'
                         f'<img src="data:image/png;base64,{_embed(crop)}"></div>')
            parts.append(f"<div><pre>{html.escape(answer)}</pre></div>")
            parts.append("</div>")

    if outcome:
        parts.append("<h2>What came out</h2>")
        parts.append(f"<pre>{html.escape(outcome)}</pre>")

    parts.append("<h2>The layout prompt that produced it</h2>")
    parts.append("<p class=note>Kept whole at the foot of the sheet. Every other "
                 "prompt this run sent is on its own step above.</p>")
    parts.append(f"<pre>{html.escape(prompt)}</pre>")

    return "\n".join(parts)


def outcome_report(dump: Path, trace: Trace | None) -> str:
    """The artefact and its findings: Probes, Failures, Caveats, final Kinds.

    Read off `document.html`'s embedded IR rather than recomputed, so this is
    what the reader was actually handed and not a second opinion about it.
    """
    document = dump / "document.html"
    if not document.exists():
        return "the Conversion did not finish, so there is no Document to report"

    match = re.search(r'id="doc-ir">(.*?)</script>', document.read_text(), re.S)
    if match is None:
        return "document.html carries no embedded IR"
    ir = json.loads(match.group(1))

    lines = [f"{'Zone':<6}{'kind':<9}{'complete':<10}items"]
    for index, zone in enumerate(ir["zones"]):
        items = len(zone["rows"]) or len(zone["pairs"]) or len(zone["blocks"])
        lines.append(f"{index:<6}{zone['kind']:<9}"
                     f"{str(zone['complete']):<10}{items}")

    lines.append("")
    for probe in ir.get("probes", []):
        verdict = "ok" if probe["ok"] else "DID NOT RECONCILE"
        lines.append(f"probe {probe['kind']}: computed {probe['computed']} "
                     f"against a stated {probe['stated']} — {verdict}")
    for failure in ir.get("failures", []):
        lines.append(f"FAILURE on zone {failure['zone_index']}: {failure['reason']}")
    for caveat in ir.get("caveats", []):
        lines.append(f"caveat on zone {caveat['zone_index']}: {caveat['note']}")
    if not any((ir.get("probes"), ir.get("failures"), ir.get("caveats"))):
        lines.append("no Probes, Failures or Caveats")
    return "\n".join(lines)


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
    parser.add_argument("--long-edge", type=int, default=None,
                        help="draw the page downscaled to this long edge, as the "
                             "deleted vision layout pass was sent it; default: "
                             "whole, as the detector sees it")
    args = parser.parse_args(argv)

    # Either a recorded layout *call* or a record of the geometry the Conversion
    # ran on. Requiring the first assumed the layout pass is always a model, and
    # `DTH_LAYOUT_DETECTOR` makes it sometimes an ONNX detector that issues no
    # call and writes no `00_layout.json`. Run 69 converted all five fixtures
    # that way and produced no contact sheet at all — `boxes_from_layout` had
    # everything it needed in `zones_used.json` and never got asked.
    if not ((args.dump / "00_layout.json").exists()
            or (args.dump / "zones_used.json").exists()):
        print(f"no layout answer and no zones_used.json in {args.dump}",
              file=sys.stderr)
        return 1

    out = args.out or Path("debug") / args.dump.name
    out.mkdir(parents=True, exist_ok=True)

    # Spec 0018, 0c: the layout pass is given `Rectified.image` — warped,
    # turned over, deskewed and equalised — and every box and crop is taken in
    # its frame. Drawing them on the Source Image stood the ticket's boxes on
    # its desk. The Source Image keeps a panel of its own.
    source = Image.open(args.source)
    rectified = rectify(args.source)
    page = Image.fromarray(rectified.image[:, :, ::-1].copy())
    model = boxes_from_layout(args.dump)
    expected = boxes_from_expected(args.expected) if args.expected else []

    seen = layout_input(page, args.long_edge)
    made = ", ".join(step for step, done in (("warped", rectified.warped),
                                             ("turned over", rectified.inverted)) if done)
    panels = [
        ("00_source", "The Source Image", f"{source.width}x{source.height}, as given.",
         source.convert("RGB")),
        ("01_layout_input", "The page as the layout pass saw it",
         f"Rectified.image, {page.width}x{page.height}: "
         f"{made + ', ' if made else ''}deskewed and equalised; "
         f"sent at {seen.width}x{seen.height} (budget {args.long_edge or 'none'}).",
         seen),
        ("02_model_boxes", "Boxes the model returned",
         f"{len(model)} Zones, on the rectified page.",
         draw(page, model, MODEL_COLOUR, prefix="got ")),
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
        rendered = rasterise(document, out, width=source.width)
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
    # Orchestrator put the boxes on — and so, since spec 0018's 0c, do the
    # panels above; on a photograph the Source Image differs from it by a
    # deskew and a warp.
    report = geometry_report(model, expected, rectified.image,
                             bands_validate(args.dump))
    print(report)

    for slug, _heading, _note, image in panels:
        image.save(out / f"{slug}.png")

    trace = read_trace(args.dump)
    prompt = layout_prompt(args.dump, trace)
    paths = "\n".join([
        f"source image  {args.source}",
        f"expected IR   {args.expected}",
        f"raw dump      {args.dump.resolve()}",
        f"this report   {out.resolve()}",
        f"trace         {'trace.json, ' + str(len(trace.events)) + ' steps and '
                         + str(len(trace.calls)) + ' calls'
                        if trace else 'none — this dump predates it'}",
    ])
    (out / "layout_prompt.txt").write_text(prompt)

    sheet = out / "index.html"
    sheet.write_text(contact_sheet(
        f"{args.dump.parent.name} / {args.dump.name}",
        panels, zones, report, prompt, paths,
        trace=trace, settings=run_settings(args.dump), page=page,
        model=model, expected=expected,
        outcome=outcome_report(args.dump, trace),
    ))
    print(f"\n{paths}\n\nwrote {sheet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
