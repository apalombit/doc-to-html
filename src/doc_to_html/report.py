"""One page, every document, source left and render right — the review surface.

**This is what gets reviewed.** Reviewing five documents used to mean opening
five folders, and in eighty runs nobody once put a rendered page beside the
image it came from — which is how `sample_table_0003` came to lose every column
header of its only table inside a score that called it a full match. A measure
that nobody checks against the artefact is a measure that can quietly invert.

Written to `debug/runs/<label>/report.html`, at the run root rather than in a
per-fixture folder. `tools/inspect_run.py`'s per-fixture `index.html` stays
exactly as it is and answers the other question — *how was this one document
converted, step by step* — and both are produced by the same run.

Four things it has to do, from spec 0007:

- **Every document in one scrollable page**, source left and render right, both
  at matched width, so proportions are directly comparable.
- **Scores above each pair**, with the delta against the previous run, and any
  T1, T2 or T3 regression flagged as a phase-gate failure.
- **The intermediate steps that matter, inline and collapsed** — the detected
  boxes over the source, and the crop behind any Zone a finding implicates.
  Expanded on click, so the default view is purely source against output.
- **Self-contained**, images inlined, so the file can be moved or sent.

It also writes `scores.json` beside itself. That is what the *next* run reads to
compute its deltas, and it is the only reason a delta here means anything: a
score from one session and a score from another are comparable only when both
came from the same scorer over the same corpus, and the file records which.
"""

from __future__ import annotations

import base64
import html
import io
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .corpus import SOURCES, Source, split_of
from .projection import available, screenshot
from .scoring import DocumentScore, normalise, score_document

PANEL_WIDTH = 470
"""How wide each half of a pair is drawn, in CSS pixels.

Both halves get the same number, which is the whole point: the source and the
render are scaled by the *same* factor from their own matched-width rendering,
so a page that comes out half again as tall looks half again as tall here. A
report that fitted each image to its own box would hide `height_ratio`, which
is the single best diagnostic the scorer produces.
"""

_IR = re.compile(
    r'<script type="application/json" id="doc-ir">(.*?)</script>', re.S
)


def _data_uri(image: Any, *, quality: int = 82) -> str:
    """A PIL image as an inline `data:` URI, so the page carries its pictures."""
    buffer = io.BytesIO()
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _scaled(path: Path, width: int) -> Any:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    if image.width > width:
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image


def _zones_of(document_html: str) -> list[dict[str, Any]]:
    """The Zones the Conversion produced, read back out of its own output.

    `render.py` embeds the IR in the document it writes, so the run's own
    artefact carries the rectangles and the text of every Zone and nothing has
    to be reconstructed from a dump directory that may have been cleared.
    """
    found = _IR.search(document_html)
    if not found:
        return []
    try:
        payload = json.loads(found.group(1).replace("<\\/", "</"))
    except json.JSONDecodeError:
        return []
    zones: list[dict[str, Any]] = payload.get("zones", [])
    return zones


def _zone_text(zone: dict[str, Any]) -> str:
    """Everything one Zone says, flattened, for matching a finding to a crop."""
    parts: list[str] = [str(zone.get("title") or "")]
    for block in zone.get("blocks", []):
        for line in block.get("lines", []):
            readings = line.get("readings") or []
            if readings:
                parts.append(str(readings[0].get("text", "")))
    for row in zone.get("rows", []):
        for cell in row.get("cells", []):
            readings = cell.get("readings") or []
            if readings:
                parts.append(str(readings[0].get("text", "")))
    for pair in zone.get("pairs", []):
        for side in ("label", "value"):
            readings = (pair.get(side) or {}).get("readings") or []
            if readings:
                parts.append(str(readings[0].get("text", "")))
    return normalise(" ".join(part for part in parts if part))


def _boxes_over(source_png: Path, zones: list[dict[str, Any]], width: int) -> Any:
    """The source image with the detected Zone rectangles drawn on it."""
    from PIL import Image, ImageDraw

    image = Image.open(source_png).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for index, zone in enumerate(zones):
        box = zone.get("bbox")
        if not box:
            continue
        rectangle = (
            box["left"] * image.width, box["top"] * image.height,
            box["right"] * image.width, box["bottom"] * image.height,
        )
        draw.rectangle(rectangle, outline=(214, 64, 40, 255), width=2)
        draw.rectangle(
            (rectangle[0], rectangle[1], rectangle[0] + 34, rectangle[1] + 15),
            fill=(214, 64, 40, 230),
        )
        draw.text((rectangle[0] + 5, rectangle[1] + 3),
                  f"{index} {zone.get('kind', '?')[:2]}", fill=(255, 255, 255))
    if image.width > width:
        image = image.resize(
            (width, round(image.height * width / image.width)),
            Image.Resampling.LANCZOS,
        )
    return image


def _crops_for(source_png: Path, zones: list[dict[str, Any]],
               wanted: Iterable[str]) -> list[tuple[int, Any]]:
    """The crop behind each Zone a finding implicates, by matching its text.

    Matched on content rather than on position, because the point of showing a
    crop is to answer *what was the model looking at when it produced this*,
    and the finding is a string.
    """
    from PIL import Image

    needles = [normalise(text) for text in wanted if normalise(text)]
    if not needles:
        return []
    image = Image.open(source_png).convert("RGB")
    found: list[tuple[int, Any]] = []
    for index, zone in enumerate(zones):
        box = zone.get("bbox")
        if not box:
            continue
        text = _zone_text(zone)
        if not any(needle in text or text in needle for needle in needles):
            continue
        crop = image.crop((
            max(0, int(box["left"] * image.width) - 6),
            max(0, int(box["top"] * image.height) - 6),
            min(image.width, int(box["right"] * image.width) + 6),
            min(image.height, int(box["bottom"] * image.height) + 6),
        ))
        if crop.width > 2 and crop.height > 2:
            found.append((index, crop))
    return found[:6]


# --------------------------------------------------------------------------


STYLESHEET = """
:root { --ink:#1b1f24; --muted:#6b757f; --rule:#dfe4e9; --page:#f4f6f8;
        --card:#fff; --bad:#b4231c; --good:#1c7a45; --warn:#9a6205; }
* { box-sizing:border-box; }
body { font:14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       color:var(--ink); background:var(--page); margin:0; padding:26px 22px 60px; }
.wrap { max-width:1320px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
.run-meta { color:var(--muted); font-size:12.5px; margin-bottom:20px; }
.run-meta code { background:#e7ebef; padding:1px 5px; border-radius:3px; }
.gate { border-radius:5px; padding:10px 14px; margin-bottom:22px;
        font-size:13.5px; }
.gate.pass { background:#e6f4ec; border-left:4px solid var(--good); }
.gate.fail { background:#fdeceb; border-left:4px solid var(--bad); }
.gate ul { margin:6px 0 0; padding-left:20px; }
table.summary { border-collapse:collapse; width:100%; font-size:12.5px;
                background:var(--card); margin-bottom:26px;
                box-shadow:0 1px 2px rgba(0,0,0,.06); }
table.summary th { text-align:left; background:#eef1f4; padding:6px 9px;
                   font-size:11px; letter-spacing:.06em; text-transform:uppercase;
                   color:var(--muted); border-bottom:1px solid var(--rule); }
table.summary td { padding:5px 9px; border-bottom:1px solid #eef1f4;
                   font-variant-numeric:tabular-nums; }
table.summary td.name { font-weight:600; }
table.summary tr.regressed td { background:#fdf1f0; }
.delta { font-size:11px; margin-left:4px; }
.delta.up { color:var(--good); } .delta.down { color:var(--bad); }
section.doc { background:var(--card); border-radius:6px; padding:16px 18px 18px;
              margin-bottom:22px; box-shadow:0 1px 2px rgba(0,0,0,.06); }
section.doc > h2 { font-size:16px; margin:0 0 2px;
                   display:flex; align-items:baseline; gap:10px; }
section.doc .archetype { font-size:12px; color:var(--muted); font-weight:400; }
section.doc .awkward { font-size:12px; color:var(--muted); margin:0 0 10px; }
.axes { display:flex; flex-wrap:wrap; gap:7px; margin-bottom:12px; }
.axis { border:1px solid var(--rule); border-radius:4px; padding:4px 9px;
        font-size:12px; background:#fbfcfd; }
.axis b { font-variant-numeric:tabular-nums; }
.axis.hard { border-color:#c9d3db; background:#f2f6f9; }
.axis.bad b { color:var(--bad); }
.axis.good b { color:var(--good); }
.pair { display:flex; gap:14px; align-items:flex-start; }
.pair figure { margin:0; flex:0 0 auto; }
.pair figcaption { font-size:11px; color:var(--muted); letter-spacing:.06em;
                   text-transform:uppercase; margin-bottom:5px; }
.pair img { display:block; border:1px solid var(--rule); background:#fff;
            max-width:100%; }
.findings { flex:1 1 220px; min-width:200px; font-size:12px; }
.findings h3 { font-size:11px; letter-spacing:.07em; text-transform:uppercase;
               color:var(--muted); margin:0 0 4px; }
.findings ul { margin:0 0 10px; padding-left:16px; }
.findings li { margin-bottom:2px; }
.findings .none { color:var(--good); }
details { margin-top:12px; border-top:1px solid var(--rule); padding-top:9px; }
details summary { cursor:pointer; font-size:12px; color:var(--muted);
                  letter-spacing:.04em; }
details .steps { display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; }
details .steps figure { margin:0; }
details .steps figcaption { font-size:11px; color:var(--muted);
                            margin-bottom:4px; }
details .steps img { border:1px solid var(--rule); display:block;
                     background:#fff; max-width:100%; }
.error { color:var(--bad); font-size:13px; }
@media (max-width:820px) { .pair { flex-wrap:wrap; } }
"""


def _delta_html(now: float, before: float | None, *, higher_is_better: bool,
                places: int = 3) -> str:
    if before is None:
        return ""
    change = now - before
    if abs(change) < 10 ** -(places + 1):
        return ""
    better = change > 0 if higher_is_better else change < 0
    return (
        f'<span class="delta {"up" if better else "down"}">'
        f'{change:+.{places}f}</span>'
    )


def _axis(label: str, value: str, *, hard: bool = False,
          ok: bool | None = None, delta: str = "") -> str:
    tone = "" if ok is None else (" good" if ok else " bad")
    return (
        f'<span class="axis{" hard" if hard else ""}{tone}">{html.escape(label)} '
        f"<b>{value}</b>{delta}</span>"
    )


def _findings_html(score: DocumentScore) -> str:
    done = score.completeness
    parts: list[str] = ["<h3>What the scorer found</h3><ul>"]
    if done.lost:
        words = ", ".join(
            f"{html.escape(word)}" + (f" ×{count}" if count > 1 else "")
            for word, count in done.lost[:8]
        )
        parts.append(f"<li><b>Lost:</b> {words}</li>")
    if done.duplicated:
        strings = "; ".join(
            f"“{html.escape(text[:44])}” ×{got}"
            for text, _, got in done.duplicated[:5]
        )
        parts.append(f"<li><b>Printed twice:</b> {strings}</li>")
    if done.invented:
        words = ", ".join(html.escape(word) for word, _ in done.invented[:6])
        parts.append(f"<li><b>Invented:</b> {words}</li>")
    if done.broken_joins:
        joins = "; ".join(
            f"{html.escape(a)} | {html.escape(b)}" for a, b in done.broken_joins[:5]
        )
        parts.append(f"<li><b>Split apart:</b> {joins}</li>")
    if done.surplus_breaks:
        parts.append(
            f"<li><b>Hard line breaks:</b> {done.hard_breaks} against "
            f"{done.source_hard_breaks} in the source</li>"
        )
    if done.figures_lost:
        parts.append(f"<li><b>Figures lost:</b> {done.figures_lost}</li>")
    if score.layout.split_regions or score.layout.merged_regions:
        parts.append(
            f"<li><b>Regions:</b> {score.layout.split_regions} split, "
            f"{score.layout.merged_regions} merged</li>"
        )
    if score.inline.missing:
        parts.append(
            f"<li><b>Inline lost:</b> "
            + "; ".join(html.escape(item[:40]) for item in score.inline.missing[:5])
            + "</li>"
        )
    if len(parts) == 1:
        parts.append('<li class="none">Nothing. Every axis is clean.</li>')
    parts.append("</ul>")
    return f'<div class="findings">{"".join(parts)}</div>'


def _document_section(source: Source, score: DocumentScore, *,
                      source_png: Path, render_png: Path | None,
                      document_html: str, before: DocumentScore | None) -> str:
    done = score.completeness
    axes = [
        _axis("T1 recall", f"{done.recall:.3f}", hard=True, ok=done.recall >= 1.0,
              delta=_delta_html(done.recall,
                                before.completeness.recall if before else None,
                                higher_is_better=True)),
        _axis("T1 precision", f"{done.precision:.3f}", hard=True,
              ok=done.precision >= 1.0,
              delta=_delta_html(done.precision,
                                before.completeness.precision if before else None,
                                higher_is_better=True)),
        _axis("T1 joins", f"{done.join_recall:.3f}", hard=True,
              ok=done.join_recall >= 1.0),
        _axis("T2 tau", f"{score.order.tau:.3f}", hard=True,
              ok=score.order.tau >= 0.99,
              delta=_delta_html(score.order.tau,
                                before.order.tau if before else None,
                                higher_is_better=True)),
        _axis("T3 beside", f"{score.layout.beside_agreement:.2f}", hard=True,
              ok=score.layout.beside_agreement >= 0.99),
        _axis("T3 height", f"{score.layout.height_ratio:.2f}", hard=True,
              ok=abs(score.layout.height_ratio - 1.0) <= 0.05,
              delta=_delta_html(score.layout.height_ratio,
                                before.layout.height_ratio if before else None,
                                higher_is_better=False, places=2)),
        _axis("T4 scale", f"{score.typography.output_scale:.2f}"
                          f" / {score.typography.source_scale:.2f}"),
        _axis("T4 align", f"{score.typography.alignment_agreement:.2f}"),
    ]
    if score.palette is not None:
        axes.append(_axis("T5 ink Δ", f"{score.palette.ink_delta:.2f}"))
        axes.append(_axis("T5 accent Δ", f"{score.palette.accent_delta:.2f}"))
        axes.append(_axis(
            "T5 texture",
            f"{score.palette.output_texture:.3f}"
            f" / {score.palette.source_texture:.3f}"))
    axes.append(_axis(
        "T6 inline",
        f"{sum(score.inline.found.values())}/{sum(score.inline.of.values())}",
        ok=score.inline.rate >= 1.0 if sum(score.inline.of.values()) else None))

    left = _data_uri(_scaled(source_png, PANEL_WIDTH))
    right = (
        _data_uri(_scaled(render_png, PANEL_WIDTH))
        if render_png is not None and render_png.is_file() else ""
    )

    zones = _zones_of(document_html)
    steps = [
        f'<figure><figcaption>{len(zones)} detected region(s) over the source'
        f'</figcaption><img src="{_data_uri(_boxes_over(source_png, zones, 460))}"'
        f' alt="detected boxes"></figure>'
    ] if zones else []
    implicated = [text for text, _, _ in done.duplicated]
    implicated += [word for word, _ in done.lost[:6]]
    for index, crop in _crops_for(source_png, zones, implicated):
        steps.append(
            f'<figure><figcaption>Zone {index} — behind a finding</figcaption>'
            f'<img src="{_data_uri(crop)}" alt="zone {index} crop"></figure>'
        )

    collapsed = (
        "<details><summary>Intermediate steps — detected regions, and the crops "
        "behind the findings</summary>"
        f'<div class="steps">{"".join(steps)}</div></details>'
        if steps else ""
    )

    return (
        f'<section class="doc" id="{html.escape(source.name)}">'
        f"<h2>{html.escape(source.name)}"
        f'<span class="archetype">{html.escape(source.archetype)} · '
        f"{score.split} · {score.width}×{score.source_height}px</span></h2>"
        f'<p class="awkward">{html.escape(source.awkward)}</p>'
        f'<div class="axes">{"".join(axes)}</div>'
        '<div class="pair">'
        f'<figure><figcaption>Source</figcaption>'
        f'<img src="{left}" alt="source"></figure>'
        + (f'<figure><figcaption>Rendered output</figcaption>'
           f'<img src="{right}" alt="render"></figure>'
           if right else '<div class="error">no render</div>')
        + _findings_html(score)
        + "</div>" + collapsed + "</section>"
    )


def _summary_table(scores: list[DocumentScore],
                   before: dict[str, DocumentScore]) -> str:
    rows = []
    for score in scores:
        was = before.get(score.name)
        regressed = bool(
            was
            and (score.completeness.recall < was.completeness.recall - 1e-9
                 or score.completeness.precision < was.completeness.precision - 1e-9
                 or score.order.tau < was.order.tau - 1e-9
                 or score.layout.beside_agreement
                 < was.layout.beside_agreement - 1e-9)
        )
        rows.append(
            f'<tr class="{"regressed" if regressed else ""}">'
            f'<td class="name"><a href="#{html.escape(score.name)}">'
            f"{html.escape(score.name)}</a></td>"
            f"<td>{score.split}</td>"
            f"<td>{score.completeness.recall:.3f}"
            f"{_delta_html(score.completeness.recall, was.completeness.recall if was else None, higher_is_better=True)}</td>"
            f"<td>{score.completeness.precision:.3f}"
            f"{_delta_html(score.completeness.precision, was.completeness.precision if was else None, higher_is_better=True)}</td>"
            f"<td>{score.completeness.join_recall:.3f}</td>"
            f"<td>{score.order.tau:.3f}</td>"
            f"<td>{score.layout.beside_agreement:.2f}</td>"
            f"<td>{score.layout.height_ratio:.2f}</td>"
            f"<td>{score.typography.alignment_agreement:.2f}</td>"
            f"<td>{sum(score.inline.found.values())}/"
            f"{sum(score.inline.of.values())}</td>"
            f"<td>{len(score.completeness.duplicated)}</td>"
            f"<td>{score.completeness.surplus_breaks}</td>"
            "</tr>"
        )
    return (
        '<table class="summary"><thead><tr>'
        "<th>document</th><th>split</th><th>T1 recall</th><th>T1 prec</th>"
        "<th>T1 joins</th><th>T2 tau</th><th>T3 beside</th><th>T3 height</th>"
        "<th>T4 align</th><th>T6 inline</th><th>dupes</th><th>breaks</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _gate_html(scores: list[DocumentScore],
               before: dict[str, DocumentScore]) -> str:
    """The T1 ratchet, stated at the top where it cannot be scrolled past.

    Completeness may never decrease between phases, for any reason. Not a
    target to optimise — a floor never to cross, and the rule that would have
    caught all three of the faults that shipped as improvements in runs 81 to
    84.
    """
    if not before:
        return (
            '<div class="gate pass"><b>No previous run to ratchet against.</b> '
            "This run becomes the notch the next one may not fall below.</div>"
        )
    broken = []
    for score in scores:
        was = before.get(score.name)
        if not was:
            continue
        if score.completeness.recall < was.completeness.recall - 1e-9:
            broken.append(
                f"{score.name}: T1 recall {was.completeness.recall:.3f} → "
                f"{score.completeness.recall:.3f}"
            )
        if score.completeness.precision < was.completeness.precision - 1e-9:
            broken.append(
                f"{score.name}: T1 precision {was.completeness.precision:.3f} "
                f"→ {score.completeness.precision:.3f}"
            )
        if score.order.tau < was.order.tau - 1e-9:
            broken.append(
                f"{score.name}: T2 tau {was.order.tau:.3f} → "
                f"{score.order.tau:.3f}"
            )
        if score.layout.beside_agreement < was.layout.beside_agreement - 1e-9:
            broken.append(
                f"{score.name}: T3 beside {was.layout.beside_agreement:.2f} "
                f"→ {score.layout.beside_agreement:.2f}"
            )
    if not broken:
        return (
            '<div class="gate pass"><b>Hard tier holds.</b> No document lost '
            "completeness, reading order or side-by-side structure against the "
            "previous run.</div>"
        )
    return (
        '<div class="gate fail"><b>Phase gate FAILED.</b> The hard tier '
        "regressed, which fails the phase whatever improved elsewhere:<ul>"
        + "".join(f"<li>{item}</li>" for item in broken)
        + "</ul></div>"
    )


def _previous(path: Path | None) -> dict[str, DocumentScore]:
    """Last run's scores, for the deltas. Missing or unreadable is not fatal."""
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    found = {}
    for entry in payload.get("documents", []):
        try:
            found[entry["name"]] = _score_from(entry)
        except (KeyError, TypeError):
            continue
    return found


def _score_from(entry: dict[str, Any]) -> DocumentScore:
    """Rebuild a score from JSON, for comparing against a previous run."""
    from .scoring import Completeness, Inline, Layout, Order, Palette, Typography

    def build(kind: Any, data: Any) -> Any:
        if data is None:
            return None
        fields = {field.name for field in kind.__dataclass_fields__.values()}
        return kind(**{
            key: (tuple(tuple(item) if isinstance(item, list) else item
                        for item in value)
                  if isinstance(value, list) else value)
            for key, value in data.items() if key in fields
        })

    return DocumentScore(
        name=entry["name"], split=entry.get("split", "iterate"),
        width=entry.get("width", 0), source_height=entry.get("source_height", 0),
        output_height=entry.get("output_height", 0),
        completeness=build(Completeness, entry["completeness"]),
        order=build(Order, entry["order"]),
        layout=build(Layout, entry["layout"]),
        typography=build(Typography, entry["typography"]),
        palette=build(Palette, entry.get("palette")),
        inline=build(Inline, entry["inline"]),
    )


def build(run: Path, *, model: str, documents: Iterable[str],
          previous: Path | None = None, label: str = "") -> Path:
    """Score every document of a run and write the comparison report.

    Reads each `document.html` out of the run's own dump, so this works on a
    finished run directory and needs nothing that is not in it.
    """
    if not available():
        raise RuntimeError("no headless Chrome; the report needs it for both sides")

    dump = run / "dump" / model.replace(":", "_")
    work = run / "_renders"
    work.mkdir(parents=True, exist_ok=True)
    was = _previous(previous)

    scores: list[DocumentScore] = []
    sections: list[str] = []
    for name in documents:
        source = SOURCES.get(name)
        if source is None:
            continue
        output = dump / name / "document.html"
        if not output.is_file():
            sections.append(
                f'<section class="doc" id="{html.escape(name)}">'
                f"<h2>{html.escape(name)}</h2>"
                f'<p class="error">no document.html in the dump — the '
                f"Conversion did not get that far.</p></section>"
            )
            continue
        score = score_document(source, output, work=work)
        scores.append(score)
        render = work / f"{name}_render.png"
        if not render.is_file():
            try:
                screenshot(output.read_text(encoding="utf-8"), render,
                           width=score.width, height=max(1, score.output_height))
            except Exception:
                render = work / "missing.png"
        sections.append(_document_section(
            source, score, source_png=source.png_path(),
            render_png=render if render.is_file() else None,
            document_html=output.read_text(encoding="utf-8"),
            before=was.get(name),
        ))

    taken = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    splits = sorted({split_of(score.name) for score in scores})
    page = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(label or run.name)} — comparison report</title>\n"
        f"<style>{STYLESHEET}</style>\n</head>\n<body>\n<div class=\"wrap\">"
        f"<h1>{html.escape(label or run.name)}</h1>"
        f'<p class="run-meta">{len(scores)} document(s) · '
        f"split {', '.join(splits) or 'none'} · model <code>{html.escape(model)}</code> · "
        f"{taken}"
        + (f" · previous <code>{html.escape(previous.parent.name)}</code>"
           if previous and previous.is_file() else " · no previous run")
        + "</p>"
        + _gate_html(scores, was)
        + _summary_table(scores, was)
        + "".join(sections)
        + "</div>\n</body>\n</html>\n"
    )

    destination = run / "report.html"
    destination.write_text(page, encoding="utf-8")
    _write_scores(run, scores, label=label or run.name, model=model, taken=taken)
    return destination


def _write_scores(run: Path, scores: list[DocumentScore], *, label: str,
                  model: str, taken: str) -> None:
    (run / "scores.json").write_text(
        json.dumps(
            {
                "label": label,
                "model": model,
                "taken": taken,
                "documents": [asdict(score) for score in scores],
            },
            indent=2, default=str,
        ),
        encoding="utf-8",
    )


def latest_scores(runs: Path, *, before: str) -> Path | None:
    """The newest `scores.json` under `runs/` that is not this run's own.

    Newest by modification time rather than by the number a label starts with,
    because labels are chosen by hand and `84-rule-not-a-line` sorts after
    `100-something`. A missing or unreadable file just means no deltas.
    """
    found = [
        path for path in runs.glob("*/scores.json")
        if path.parent.name != before
    ]
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .corpus import names

    parser = argparse.ArgumentParser(
        prog="python -m doc_to_html.report",
        description="Build the comparison report for a finished run.",
    )
    parser.add_argument("run", type=Path, help="debug/runs/<label>")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--documents", default="",
                        help="split name, 'all', or a comma-separated list; "
                             "default is whatever the run's fixtures.txt says")
    parser.add_argument("--previous", type=Path, default=None,
                        help="a previous run's scores.json; default is the "
                             "newest one under the same runs directory")
    args = parser.parse_args(argv)

    run: Path = args.run
    if args.documents:
        wanted = names(args.documents)
    else:
        listing = run / "fixtures.txt"
        wanted = tuple(
            line.strip() for line in listing.read_text().splitlines()
            if line.strip()
        ) if listing.is_file() else names("iterate")

    previous = args.previous
    if previous is None:
        previous = latest_scores(run.parent, before=run.name)

    written = build(run, model=args.model, documents=wanted,
                    previous=previous, label=run.name)
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
