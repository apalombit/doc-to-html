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
from doc_to_html.wire import (  # noqa: E402
    BlocksResponse,
    FigureResponse,
    LayoutResponse,
    PairsResponse,
    TableResponse,
    WireBlock,
    WirePair,
    WireRow,
    WireZone,
)

from tests.fixtures import BUILDERS  # noqa: E402

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
    print(f"{name}: layout + {len(document.zones)} zones")


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
