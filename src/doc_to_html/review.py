"""Look at what this project produced, beside what it was given.

**Why this exists.** The project's most expensive lesson is that a measure can
saturate and then invert while every number improves — `sample_table_0003`
scored a full match having deleted every column header of its only table, and
nobody had opened a render beside its source in eighty runs. `report.html`
answers *what do the numbers say*; this answers *what does it look like*, and
the two catch different things. `docs/agents/visual-review.md` carries the
evidence and the rationale; this module is the instrument.

**What it builds**, under `<run>/_review/`:

    00-invoice_0001.png       source | (previous render) | render, matched width
    00-invoice_0001-p2.png    ...part 2 of a tall document
    findings.json             the machine-readable form, filled in by looking
    review.md                 the same form for a person; regenerated on --check
    numbers.md                the scored axes, to quote in a note

**Three rules are built in and all three are load-bearing.**

*The reference is the PNG, never the re-rendered source HTML.* The screenshot
is what the model was shown and what a person compares against. Four of the
five original documents re-render 6.9-14.1% different from their own
screenshots on this machine and `invoice2.html` additionally wants a CDN, so
comparing against the HTML would show differences nobody introduced.

*Every panel is laid out at the source's width.* A page compared against itself
at two widths is two different pages. `projection.project()` already takes this
position for scoring; the review takes the same one so the two never disagree.

*Judgements are pairwise and in-session only.* CLAUDE.md is explicit that a
rubric reading from one session and one from another are not comparable, and
that this binds a model's visual judgements at least as strongly as numbers. So
every sheet and every form is stamped with its run label and date, the rubric
asks for *differences*, which are observations, rather than a score out of ten,
which is not — and `summarise()` refuses to merge findings from two stamps.

**The rubric is not frozen.** `RUBRIC` is a guess with two passes behind it.
`axis_tally()` exists so a later session can see which axes ever fire before
anyone freezes them, and an unknown axis in a findings file is accepted and
reported rather than rejected — trialling an axis must not require editing this
module.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent.parent

GUTTER = 24
"""Pixels between two pages, and the frame around the sheet.

Wide enough that a page's own right-hand edge is never mistaken for the seam,
which matters most on the documents that draw a border round the whole page.
"""

LABEL_BAR = 30
"""Height of the strip naming which panel is which.

It is **drawn**, not merely reserved. It used to be reserved and left blank,
which bought the sheet thirty pixels of grey and none of the protection its
docstring claimed: the one thing worse than no comparison is a confident
backwards one.
"""

SHEET_GROUND = (128, 128, 128)
"""Mid grey. Neither a light page nor a dark one can blend into it, and the
corpus holds both — `darkdeck_0009` and `cv_0013` are dark-grounded."""

LABEL_INK = (255, 255, 255)

MAX_SHEET_PX = 1600
"""Tallest a single sheet may be before it is cut into parts.

**Sized against the reader, not against taste.** An image arrives at the
reviewer downsampled to roughly 1568px on its long edge, so `statement_0006`'s
5166px sheet reached the one step of this workflow that finds anything at 30%
scale, with 10px type rendered at 3px. Cut into four parts it arrives at ~90%.

Only the height is cut. The width is set by how many panels are being compared
and no cutting helps it — comparing three renders instead of two is a
deliberate trade of scale for history.
"""

INK_DELTA = 40
"""How far a pixel must sit from the page's median grey to count as ink.

An absolute difference, so it reads light-on-dark pages as readily as
dark-on-light. It is a cutting aid, not a measurement: nothing scored depends
on it, and `style._ink_mask` remains the pipeline's own answer to this question.
"""

GUTTER_SEARCH = 0.10
"""How far from an ideal cut, as a share of page height, to hunt for a blank row.

A cut through the middle of a line of type is unreadable on both sheets it
lands on. Beyond this distance the ideal cut is better than a gutter, because a
cut that has wandered a tenth of the page no longer pairs with the other panel.
"""

BLEND = 0.5
"""How much of a cut's position comes from ink mass, the rest from height.

**Both pure measures were tried on `statement_0006` and both failed.** Cutting
by height pairs part 2 of the source with part 2 of nothing in particular,
because that document's render runs 5124px against a 1401px page. Cutting by
ink pairs the content and then produces a part **3316px tall**: 84% of that
render's ink is in its first 1900 rows — a dense table — and the remaining
3200 rows are the forty-one near-identical caveat lines, which are sparse. All
three cuts landed in the table and the tail arrived as one unreadable sheet.

Half and half keeps the pairing roughly honest and bounds the overrun, and
`_plan` then adds parts until the cap is actually met. Where the pairing slips
the reviewer sees the slip, because both panels stay whole, full width, and
labelled with the part they are.
"""

OVERRUN = 1.05
"""How far past the cap a part may run before another sheet is worth cutting.

A cut moved into a gutter lands a few rows from where it was asked to, and
spending a whole extra sheet on a five-row overshoot is worse than the
overshoot.
"""

MAX_PARTS = 12
"""Sheets one document may be cut into before the cap is abandoned.

A document needing more than this is telling you something — a render an order
of magnitude taller than its page — and twelve sheets is already past the point
where a reviewer reads them all.
"""

RUBRIC: tuple[tuple[str, str], ...] = (
    ("content", "Anything in the source missing from the render, or anything in "
                "the render that is not in the source"),
    ("order", "Reading order and grouping — same things, in the same sequence, "
              "bound to the same headings"),
    ("columns", "What sits beside what. A source column rendered as a stack is a "
                "major, not a minor"),
    ("chrome", "Borders, cards, rules, fills — drawn where the source draws them "
               "and nowhere else"),
    ("type", "Relative size and weight. Is the hierarchy the same shape, even if "
             "the absolute sizes differ"),
    ("colour", "Ground, ink, accent, shaded bands"),
    ("rhythm", "Spacing and density — how much taller or tighter the render is "
               "than the page"),
)
"""One entry per axis: the name, and the question it asks.

Provisional — see the module docstring. Two passes is not enough evidence to
say an axis earns its context.
"""

VERDICTS = ("match", "minor", "major")
"""What an axis may be answered with. Deliberately not a number out of ten."""

CHANGED_VERDICTS = ("better", "same", "worse")
"""What the `changed` axis may be answered with, and it only exists when a
previous render is on the sheet. This is the ratchet's own question — *did any
content that converted before stop converting* — asked of the pixels."""

RUBRIC_VERSION = 1
"""Bumped whenever `RUBRIC` changes, so a findings file says which rubric it was
answered against. Two files at different versions are not one table."""


# --- cutting a tall page into readable parts -------------------------------


def ink_profile(image: Image.Image) -> npt.NDArray[np.int64]:
    """Ink pixels per row, read against the page's own median grey.

    The median is the page and the difference is the type, which reads a
    dark-grounded page — `darkdeck_0009`, `cv_0013` — exactly as readily as a
    light one. It assumes ink is a minority of the pixels, which every page in
    the corpus satisfies by a wide margin; a page that is more than half ink
    would be read inside out, and that page is not a document.
    """
    grey = np.asarray(image.convert("L"), dtype=np.int16)
    ground = int(np.median(grey))
    counted = np.count_nonzero(np.abs(grey - ground) >= INK_DELTA, axis=1)
    return np.asarray(counted, dtype=np.int64)


def parts_for(height: int, cap: int = MAX_SHEET_PX) -> int:
    """How many parts a page of this height must be cut into to stay readable."""
    return max(1, math.ceil(height / cap)) if height > 0 else 1


def _nearest_gutter(profile: npt.NDArray[np.int64], row: int, reach: int) -> int:
    """The blank row closest to `row`, or `row` itself if none is within reach."""
    blank = profile == 0
    for offset in range(reach + 1):
        for candidate in (row - offset, row + offset):
            if 0 < candidate < len(profile) and blank[candidate]:
                return candidate
    return row


def cut_rows(profile: npt.NDArray[np.int64], parts: int) -> tuple[int, ...]:
    """Rows at which to cut a page into `parts`, by `BLEND` of ink and height.

    The two panels of a sheet hold the same content at different heights — our
    renders run to 3.7x the source — so a cut has two jobs that pull apart:
    part k of each panel should hold the same *content*, and no part should be
    too tall to read. `BLEND` carries the measurement that set the trade.

    Each cut is then moved to the nearest blank row within `GUTTER_SEARCH`,
    because a cut through the middle of a line of type is unreadable on both
    sheets it lands on.
    """
    if parts <= 1 or len(profile) == 0:
        return ()
    rows = len(profile)
    total = int(profile.sum())
    reach = max(1, int(rows * GUTTER_SEARCH))
    position = np.arange(rows, dtype=np.float64) / rows
    if total == 0:
        measure = position
    else:
        above = np.concatenate(([0.0], np.cumsum(profile, dtype=np.float64)[:-1]))
        measure = BLEND * (above / total) + (1 - BLEND) * position
    cuts: list[int] = []
    for k in range(1, parts):
        row = int(np.searchsorted(measure, k / parts))
        cut = _nearest_gutter(profile, row, reach)
        cut = min(max(cut, len(cuts) + 1), rows - (parts - len(cuts) - 1))
        if cuts and cut <= cuts[-1]:
            cut = cuts[-1] + 1
        cuts.append(cut)
    return tuple(cuts)


def _slices(profile: npt.NDArray[np.int64], height: int,
            parts: int) -> list[tuple[int, int]]:
    edges = (0, *cut_rows(profile, parts), height)
    return [(edges[k], edges[k + 1]) for k in range(len(edges) - 1)]


def plan(images: Sequence[Image.Image], cap: int = MAX_SHEET_PX
         ) -> list[list[tuple[int, int]]]:
    """Slice every panel into the same number of parts, none taller than `cap`.

    The part count starts from the tallest panel and rises until the cap is
    actually met, because a blended cut only bounds the overrun — it does not
    remove it. `MAX_PARTS` stops the rise.
    """
    profiles = [ink_profile(image) for image in images]
    heights = [image.height for image in images]
    start = parts_for(max(heights), cap)
    cut: list[list[tuple[int, int]]] = []
    for parts in range(start, MAX_PARTS + 1):
        cut = [_slices(profile, height, parts)
               for profile, height in zip(profiles, heights)]
        tallest = max(bottom - top for slices in cut for top, bottom in slices)
        if tallest <= cap * OVERRUN:
            break
    return cut


# --- the sheet --------------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    """One page on a sheet: what to call it, and where its PNG is."""

    label: str
    image: Path


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=18)
    except TypeError:  # Pillow older than 10.1
        return ImageFont.load_default()


def contact_sheet(panels: Sequence[Panel], stem: Path, *,
                  stamp: str, cap: int = MAX_SHEET_PX) -> list[Path]:
    """Write one sheet per part, panels side by side, each labelled.

    Returns the files written, in reading order. A short document is one file
    at `stem.png`; a tall one is `stem-p1.png`, `stem-p2.png`, ...
    """
    if not panels:
        raise ValueError("a sheet needs at least one panel")
    images = [Image.open(panel.image).convert("RGB") for panel in panels]
    cut = plan(images, cap)
    parts = len(cut[0])

    width = sum(image.width for image in images) + GUTTER * (len(images) + 1)
    font = _font()
    written: list[Path] = []
    for part in range(parts):
        boxes = [slices[part] for slices in cut]
        tall = max(bottom - top for top, bottom in boxes)
        sheet = Image.new("RGB", (width, tall + LABEL_BAR + GUTTER), SHEET_GROUND)
        draw = ImageDraw.Draw(sheet)
        x = GUTTER
        for image, (top, bottom), panel in zip(images, boxes, panels):
            name = panel.label
            if parts > 1:
                name = f"{name} · part {part + 1} of {parts}"
            draw.text((x, 6), f"{name}   ·   {stamp}", fill=LABEL_INK, font=font)
            sheet.paste(image.crop((0, top, image.width, bottom)), (x, LABEL_BAR))
            x += image.width + GUTTER
        target = stem.with_name(f"{stem.name}-p{part + 1}.png") if parts > 1 \
            else stem.with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(target)
        written.append(target)
    return written


# --- findings ---------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One axis of one document, answered by looking."""

    document: str
    axis: str
    verdict: str
    note: str


@dataclass(frozen=True)
class Summary:
    """What a filled findings file adds up to.

    `unreported` is the reason the whole workflow exists, and it is computed
    **without inventing a quality threshold**: a document is unreported when a
    human-visible `major` sits beside scored ratios that are all at 1.000. One
    is not a bar somebody chose; it is the ceiling, and `sample_table_0003`
    stood there having deleted every column header of its only table.

    `cross_checked` names the documents that actually had scores to check
    against. An empty `unreported` means two very different things — the
    numbers noticed, or there were no numbers — and a summary that could not
    tell them apart would be the same quiet lie this workflow exists to catch.
    """

    stamp: str
    documents: int
    answered: int
    axis_tally: dict[str, Counter[str]]
    owner_tally: Counter[str]
    unreported: tuple[Finding, ...]
    cross_checked: tuple[str, ...]
    unknown_axes: tuple[str, ...]
    missing_axes: tuple[str, ...]
    deltas: dict[str, dict[str, float]] = field(default_factory=dict)


PERFECT = ("recall", "precision", "join_recall", "tau")
"""The scored ratios whose ceiling is exactly 1.000, so "did not notice" can be
stated as a fact rather than as a threshold somebody picked."""


def blank_findings(names: Sequence[str], *, stamp: str, run: str,
                   previous: str | None, model: str) -> dict[str, Any]:
    """The form, unanswered. One block per document, one entry per axis."""
    axes = [axis for axis, _ in RUBRIC]
    if previous:
        axes = [*axes, "changed"]
    return {
        "run": run,
        "previous": previous,
        "model": model,
        "stamp": stamp,
        "taken": date.today().isoformat(),
        "rubric_version": RUBRIC_VERSION,
        "rubric": axes,
        "documents": [
            {
                "name": name,
                "axes": {axis: {"verdict": None, "note": ""} for axis in axes},
                "worst": None,
                "owner": None,
            }
            for name in names
        ],
    }


def findings_of(record: dict[str, Any]) -> tuple[Finding, ...]:
    """Every answered axis in a findings file, as flat records."""
    out: list[Finding] = []
    for document in record.get("documents", ()):
        name = str(document.get("name", ""))
        for axis, answer in (document.get("axes") or {}).items():
            verdict = (answer or {}).get("verdict")
            if verdict:
                out.append(Finding(name, str(axis), str(verdict),
                                   str((answer or {}).get("note", ""))))
    return tuple(out)


def _scored(scores: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    if not scores:
        return {}
    flat: dict[str, dict[str, float]] = {}
    for document in scores.get("documents", ()):
        flat[str(document["name"])] = {
            "recall": float(document["completeness"]["recall"]),
            "precision": float(document["completeness"]["precision"]),
            "join_recall": float(document["completeness"]["join_recall"]),
            "tau": float(document["order"]["tau"]),
            "beside": float(document["layout"]["beside_agreement"]),
            "height_ratio": float(document["layout"]["height_ratio"]),
            "ink_delta": float(document["palette"]["ink_delta"]),
        }
    return flat


def summarise(record: dict[str, Any], *, scores: dict[str, Any] | None = None,
              previous_scores: dict[str, Any] | None = None) -> Summary:
    """Count a filled findings file, and name the faults no number reported."""
    findings = findings_of(record)
    declared = list(record.get("rubric") or [axis for axis, _ in RUBRIC])
    seen = {finding.axis for finding in findings}

    tally: dict[str, Counter[str]] = {axis: Counter() for axis in declared}
    for finding in findings:
        tally.setdefault(finding.axis, Counter())[finding.verdict] += 1

    owners: Counter[str] = Counter(
        str(document.get("owner")) for document in record.get("documents", ())
        if document.get("owner")
    )

    now, before = _scored(scores), _scored(previous_scores)
    deltas = {
        name: {key: value - before[name][key] for key, value in axes.items()
               if key in before.get(name, {})}
        for name, axes in now.items()
    }

    unreported = tuple(
        finding for finding in findings
        if finding.verdict == "major" and finding.axis != "changed"
        and finding.document in now
        and all(now[finding.document][key] == 1.0 for key in PERFECT)
    )

    answered = len({(f.document, f.axis) for f in findings})
    checked = tuple(str(document.get("name"))
                    for document in record.get("documents", ())
                    if str(document.get("name")) in now)
    return Summary(
        stamp=str(record.get("stamp", "")),
        documents=len(record.get("documents", ())),
        answered=answered,
        axis_tally=tally,
        owner_tally=owners,
        unreported=unreported,
        cross_checked=checked,
        unknown_axes=tuple(sorted(seen - set(declared))),
        missing_axes=tuple(axis for axis in declared if axis not in seen),
        deltas=deltas,
    )


# --- building a review off a run -------------------------------------------


@dataclass(frozen=True)
class Sheet:
    """One document's comparison: the panels that went in, the files that came
    out, and the width they were all laid out at."""

    document: str
    width: int
    parts: tuple[Path, ...]


def _dump(run: Path, model: str) -> Path:
    return run / "dump" / model.replace(":", "_")


def documents_in(run: Path, model: str) -> list[str]:
    """Every document the run converted, in name order."""
    dump = _dump(run, model)
    if not dump.is_dir():
        return []
    return sorted(d.name for d in dump.iterdir() if d.is_dir())


def _scores_file(run: Path) -> dict[str, Any] | None:
    path = run / "scores.json"
    if not path.exists():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


def build(run: Path, *, model: str = "qwen3-vl:4b",
          documents: Sequence[str] | None = None,
          previous: Path | None = None,
          out: Path | None = None,
          cap: int = MAX_SHEET_PX,
          render: Any = None) -> tuple[list[Sheet], Path]:
    """Build every sheet and the two forms for one run.

    `previous` is another run directory; when given, each sheet carries three
    panels — source, that run's render, this run's render — and the form gains
    the `changed` axis. **That is the comparison the ratchet is built on**, and
    the one this workflow could not make until now: it could say how far a
    render sits from its source, never whether it moved.

    `render` is the screenshot function, injected so the sheet builder can be
    tested without a browser; it defaults to `projection.screenshot`.
    """
    from doc_to_html.corpus import SOURCES

    if render is None:
        from doc_to_html.projection import screenshot as render
    out = out or (run / "_review")
    out.mkdir(parents=True, exist_ok=True)
    stamp = f"{run.name} · {date.today().isoformat()}"
    if previous:
        stamp = f"{run.name} vs {previous.name} · {date.today().isoformat()}"

    names = [name for name in documents_in(run, model)
             if documents is None or name in documents]
    sheets: list[Sheet] = []
    skipped: list[str] = []
    for index, name in enumerate(names):
        source = REPO / SOURCES[name].png
        width = Image.open(source).width
        html = _dump(run, model) / name / "document.html"
        if not html.exists():
            skipped.append(f"{name}: no document.html in {run.name}")
            continue

        panels = [Panel("SOURCE (the page)", source)]
        scratch: list[Path] = []
        if previous:
            older = _dump(previous, model) / name / "document.html"
            if older.exists():
                shot = out / f"{index:02d}-{name}-previous.png"
                render(older, shot, width=width)
                scratch.append(shot)
                panels.append(Panel(f"RENDER {previous.name}", shot))
            else:
                skipped.append(f"{name}: no document.html in {previous.name}, "
                               "compared against the source only")
        shot = out / f"{index:02d}-{name}-render.png"
        render(html, shot, width=width)
        scratch.append(shot)
        panels.append(Panel(f"RENDER {run.name}", shot))

        parts = contact_sheet(panels, out / f"{index:02d}-{name}", stamp=stamp,
                              cap=cap)
        for path in scratch:
            path.unlink()
        sheets.append(Sheet(name, width, tuple(parts)))

    record = blank_findings([sheet.document for sheet in sheets], stamp=stamp,
                            run=run.name,
                            previous=previous.name if previous else None,
                            model=model)
    findings = out / "findings.json"
    if findings.exists():
        record["note"] = (f"{findings.name} already existed and was left alone; "
                          "the blank form is at findings.blank.json")
        (out / "findings.blank.json").write_text(json.dumps(record, indent=2) + "\n")
    else:
        findings.write_text(json.dumps(record, indent=2) + "\n")

    (out / "numbers.md").write_text(_numbers_md(stamp, sheets, _scores_file(run)))
    (out / "review.md").write_text(_form_md(stamp, sheets, record, skipped))
    return sheets, out


def _numbers_md(stamp: str, sheets: Sequence[Sheet],
                scores: dict[str, Any] | None) -> str:
    flat = _scored(scores)
    keys = ("recall", "precision", "join_recall", "tau", "beside",
            "height_ratio", "ink_delta")
    rows = []
    for sheet in sheets:
        values = flat.get(sheet.document, {})
        rows.append(f"| `{sheet.document}` | {sheet.width}px | " + " | ".join(
            f"{values[key]:.3f}" if key in values else "—" for key in keys) + " |")
    return (f"# Scored axes — {stamp}\n\n"
            "Here to be quoted in a note, not to be reviewed. The images are "
            "the review, and a finding that could have been written from this "
            "table has not done the job.\n\n"
            "| document | width | " + " | ".join(keys) + " |\n"
            "|---" * (len(keys) + 2) + "|\n" + "\n".join(rows) + "\n")


def _form_md(stamp: str, sheets: Sequence[Sheet], record: dict[str, Any],
             skipped: Sequence[str]) -> str:
    axes = dict(RUBRIC)
    axes["changed"] = ("Against the PREVIOUS render on the same sheet: "
                       f"{' / '.join(CHANGED_VERDICTS)}, and what moved")
    lines = [
        f"# Visual review — {stamp}",
        "",
        "**Filled in by opening each PNG**, one at a time. A note that could "
        "have been written from `numbers.md` alone has not done the job this "
        "file exists for.",
        "",
        "**Answers go in `findings.json`**, which is the form this file "
        "mirrors; `--check` rewrites this file from it, with the tally and the "
        "faults no scored axis reported.",
        "",
        "**Pairwise and in-session only.** These readings are not comparable "
        "with a review from another session — see CLAUDE.md, *How runs are "
        "used here*. Every sheet carries this stamp for that reason.",
        "",
        f"Each axis: `{' / '.join(VERDICTS)}`, and one concrete sentence "
        "naming the element, not the impression.",
        "",
    ]
    if skipped:
        lines += ["**Skipped:**", *(f"- {line}" for line in skipped), ""]
    for sheet in sheets:
        lines += [f"## {sheet.document}  ({sheet.width}px)", ""]
        lines += [f"![{sheet.document}]({part.name})" for part in sheet.parts]
        lines += [""]
        for axis in record["rubric"]:
            lines.append(f"- **{axis}** — _{axes.get(axis, '')}_")
        lines += ["- **worst fault** —",
                  "- **owner** — (which thread or phase this belongs to, or "
                  "`new`)", ""]
    return "\n".join(lines) + "\n"


def report_md(record: dict[str, Any], summary: Summary) -> str:
    """The filled form, rendered back out with its tally. Written by `--check`."""
    lines = [
        f"# Visual review — {summary.stamp}",
        "",
        f"{summary.answered} axes answered across {summary.documents} "
        f"document(s), rubric version {record.get('rubric_version')}.",
        "",
        "**Pairwise and in-session only.** Not comparable with any other "
        "session's reading.",
        "",
        "## Faults no scored axis reported",
        "",
    ]
    if not summary.cross_checked:
        lines += ["**Not checked.** No `scores.json` was found for these "
                  "documents, so nothing could be cross-checked — which is not "
                  "the same as nothing being found."]
    elif summary.unreported:
        lines += ["Every scored ratio at 1.000, and a `major` visible in the "
                  "picture:", ""]
        lines += [f"- **{f.document}** · `{f.axis}` — {f.note}"
                  for f in summary.unreported]
    else:
        lines += [f"None across {len(summary.cross_checked)} scored "
                  "document(s): every `major` sits beside at least one scored "
                  "ratio below 1.000."]
    lines += ["", "## Which axes fired", "",
              "Evidence for whether the rubric earns its seven axes. **Not to "
              "be added to another session's table.**", "",
              "| axis | " + " | ".join(VERDICTS) + " | changed |", "|---|---|---|---|---|"]
    for axis, counts in summary.axis_tally.items():
        lines.append(f"| `{axis}` | " + " | ".join(
            str(counts.get(verdict, 0)) for verdict in VERDICTS) + " | "
            + str(sum(counts.get(v, 0) for v in CHANGED_VERDICTS)) + " |")
    if summary.unknown_axes:
        lines += ["", f"Axes answered that the rubric does not declare: "
                  f"{', '.join('`' + a + '`' for a in summary.unknown_axes)} — "
                  "a trial axis, kept."]
    if summary.missing_axes:
        lines += ["", f"Axes that never fired: "
                  f"{', '.join('`' + a + '`' for a in summary.missing_axes)}."]
    if summary.owner_tally:
        lines += ["", "## Owners", ""]
        lines += [f"- {owner}: {count}"
                  for owner, count in summary.owner_tally.most_common()]
    lines += ["", "## Every finding", ""]
    for document in record.get("documents", ()):
        name = document.get("name")
        lines += [f"### {name}", ""]
        for axis, answer in (document.get("axes") or {}).items():
            verdict = (answer or {}).get("verdict") or "—"
            lines.append(f"- **{axis}** · `{verdict}` — "
                         f"{(answer or {}).get('note', '')}")
        lines += [f"- **worst fault** — {document.get('worst') or '—'}",
                  f"- **owner** — {document.get('owner') or '—'}", ""]
    return "\n".join(lines) + "\n"


def pair(source: Path, render_html: Path, out: Path, *, label: str = "pair",
         render: Any = None, cap: int = MAX_SHEET_PX) -> list[Path]:
    """Compare one arbitrary PNG against one arbitrary page, outside any run.

    The general case the run-shaped entry point could not reach: a hand-written
    HTML file against a photograph, a render saved from anywhere against the
    page it claims to be.
    """
    if render is None:
        from doc_to_html.projection import screenshot as render
    out.mkdir(parents=True, exist_ok=True)
    width = Image.open(source).width
    shot = out / f"{label}-render.png"
    if render_html.suffix.lower() == ".png":
        shot = render_html
    else:
        render(render_html, shot, width=width)
    parts = contact_sheet(
        [Panel(f"SOURCE {source.name}", source),
         Panel(f"RENDER {render_html.name}", shot)],
        out / label, stamp=f"{label} · {date.today().isoformat()}", cap=cap)
    if shot != render_html and shot.exists():
        shot.unlink()
    return parts
