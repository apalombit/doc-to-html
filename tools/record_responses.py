"""Derive recorded model responses from the hand-authored expected IR.

    python tools/record_responses.py

Writes `tests/responses/<fixture>/layout.json` and one file per Zone: the
responses a model that read each fixture correctly would have returned. The
output is committed, so the suite runs with no Ollama process, no model
installed and no network.

**What this does and does not buy.** Replaying these exercises the whole path
below the model — the wire schemas, the parser, the mapping and its validation,
every Extractor, Probes, assembly and the renderer — against known-correct
input. It says nothing whatever about whether a real model reads a page
correctly. That is the bake-off's job (`python -m doc_to_html.bakeoff`), and the reason the
acceptance harness and the bake-off both exist.

Deriving these from the ground truth rather than from a live model is deliberate:
a recording taken from a model captures that model's mistakes, and the suite
would then assert that the pipeline reproduces them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from doc_to_html.ir import Document, Kind, RowRole, Zone  # noqa: E402
from doc_to_html.preprocess import (  # noqa: E402
    caption_band,
    rectify,
    zone_pixels,
)
from doc_to_html.wire import (  # noqa: E402
    BlocksResponse,
    CaptionResponse,
    FigureResponse,
    LayoutResponse,
    PairsResponse,
    TableResponse,
    WireBlock,
    WirePair,
    WireRow,
    WireZone,
)

from tests.fixtures import BUILDERS, IMAGES  # noqa: E402

# `tests.fixtures.BUILDERS` is the single list of what the acceptance set is.
# A second copy here is how a sixth fixture ends up recorded by one tool and not
# the other.


def layout_of(document: Document) -> LayoutResponse:
    return LayoutResponse(
        zones=[
            WireZone(
                kind=zone.kind.value,  # type: ignore[arg-type]
                role=zone.role.value,  # type: ignore[arg-type]
                band=zone.band,
                column=zone.column,
                left=zone.bbox.left if zone.bbox else 0.0,
                top=zone.bbox.top if zone.bbox else 0.0,
                right=zone.bbox.right if zone.bbox else 1.0,
                bottom=zone.bbox.bottom if zone.bbox else 1.0,
                title=zone.title or "",
                graphic=zone.graphic_kind or "",
            )
            for zone in document.zones
        ]
    )


def contents_of(zone: Zone) -> object:
    """The extraction response for one Zone, in the schema its Kind is read with."""
    if zone.kind is Kind.TABLE:
        return TableResponse(
            rows=[
                WireRow(
                    role=row.role.value,  # type: ignore[arg-type]
                    cells=[c.text for c in row.cells],
                )
                for row in zone.rows
            ]
        )
    if zone.kind is Kind.PAIRS:
        return PairsResponse(
            pairs=[
                WirePair(label=pair.label.text, value=pair.value.text)
                for pair in zone.pairs
            ]
        )
    if zone.kind is Kind.FIGURE:
        return FigureResponse(
            graphic=zone.graphic_kind or "chart",  # type: ignore[arg-type]
            text=[line.text for block in zone.blocks for line in block.lines],
        )
    return BlocksResponse(
        blocks=[
            WireBlock(
                kind=block.kind,  # type: ignore[arg-type]
                lines=[line.text for line in block.lines],
            )
            for block in zone.blocks
        ]
    )


def first_printed_line(zone: Zone) -> str:
    """The line a reader's eye lands on first, whatever the Zone's Kind."""
    if zone.rows:
        return " ".join(c.text for c in zone.rows[0].cells).strip()
    if zone.pairs:
        return f"{zone.pairs[0].label.text} {zone.pairs[0].value.text}".strip()
    for block in zone.blocks:
        for line in block.lines:
            if line.text.strip():
                return line.text.strip()
    return ""


def caption_of(zone: Zone) -> CaptionResponse:
    """What a model that read this Zone correctly would answer about its first
    line — all three verdicts, not just the one that writes a Title.

    `header` and `content` do the same thing in the pipeline and are still kept
    apart here, for the reason `wire.CaptionResponse` gives: collapsing them is
    what made run 71 answer `true` on 8 of 8 crops. A recording that flattened
    them would stop the suite noticing if the distinction were ever lost.
    """
    if zone.title:
        return CaptionResponse(first_line=zone.title, line_is="caption")
    if zone.rows and zone.rows[0].role is RowRole.HEADER:
        return CaptionResponse(first_line=first_printed_line(zone),
                               line_is="header")
    return CaptionResponse(first_line=first_printed_line(zone),
                           line_is="content")


def captions_of(name: str, document: Document) -> list[CaptionResponse]:
    """One answer per Zone the Orchestrator will actually ask about.

    **The gate is re-derived here rather than assumed**, because it is not the
    Zone count: `preprocess.caption_band` returns `None` for a crop holding a
    single band of ink, and the Orchestrator then never makes the call. A queue
    with one entry per Zone would serve every answer to the wrong question from
    the first skipped Zone onward — the same off-by-one `recorded`'s per-pass
    queues were introduced to make impossible.

    Measured against the Source Image, so it is the same arithmetic
    `_read_caption` runs, not a second copy of the rule.
    """
    image = rectify(REPO / IMAGES[name]).image
    return [
        caption_of(zone)
        for zone in document.zones
        if zone.bbox is not None
        and caption_band(zone_pixels(image, zone)) is not None
    ]


def record(name: str, out: Path) -> None:
    document: Document = BUILDERS[name]()

    directory = out / name
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.json"):
        stale.unlink()

    (directory / "layout.json").write_text(
        layout_of(document).model_dump_json(indent=2) + "\n"
    )
    for index, zone in enumerate(document.zones):
        payload = contents_of(zone)
        (directory / f"zone_{index:02d}.json").write_text(
            payload.model_dump_json(indent=2) + "\n"  # type: ignore[attr-defined]
        )

    captions = captions_of(name, document)
    (directory / "caption.json").write_text(
        json.dumps([c.model_dump() for c in captions], indent=2) + "\n"
    )
    print(f"{name}: layout + {len(document.zones)} zones "
          f"+ {len(captions)} captions")


def main() -> int:
    out = REPO / "tests" / "responses"
    for name in BUILDERS:
        record(name, out)

    summary = {
        name: sorted(p.name for p in (out / name).glob("*.json"))
        for name in BUILDERS
    }
    (out / "index.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
