"""Bring recorded IRs up to today's code downstream of the model. No model call.

**Why this exists.** A frozen directory records two things at once: what the
model answered, and what the code *of its day* made of those answers. The floor
stays put while that code moves, so `tests/frozen/a3-result/`'s IRs still carry
43 caveats on `statement_0006`, no header-row fills and `darkdeck_0009`'s
lifted `AVAILABILITY` Title — none of which today's pipeline would produce from
the same answers. Re-rendering them as they are measures yesterday's code; a
change compared against that is not one change apart from today's.

This re-applies every step downstream of the model whose result lives in the IR
and can be recomputed from it, in the order a Conversion runs them:

    1. a table Title that is its own header row's first cell is dropped
                                    wire._title_is_its_header_cell  (in _extract)
       and every table's rows padded to the header that is left, not to a
       caption row the echo rule dropped    wire.repadded  (in _extract)
    2. table-repair Caveats re-derived from each table's rows
                                    wire.table_repairs              (in _extract)
    3. palette and chrome re-measured — fill, title bar, header bar, border
                                    remeasure_style.remeasure  (_measure_chrome)
       and each leading heading's size      (_measure_type)
    4. Shortfalls re-measured, since step 1 changes a read-line count
                                    orchestrator.shortfall  (_measure_shortfalls)
    5. Probes re-run over the tables as they now stand
                                    probes.run         (after _measure_type)

then re-renders into a run-shaped directory that `doc_to_html.report` and
`tools/visual_review.py` read without knowing the difference.

    python tools/rederive.py tests/frozen/a3-result --label <label>
    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \\
        --documents sweep --previous tests/frozen/a3-result/scores.json

**Add a step here whenever a change downstream of the model puts something in
the IR** — a new wire rule, a new measured field, a new finding. Otherwise this
loop quietly measures the code as it was, which is the fault it exists to fix.
A renderer-only change needs no step: rendering is always today's.

**Proved 2026-09-27**, before it was relied on: over `a3-result` it reproduces,
byte for byte on all fifteen, the offline arm open issues 1–3 were gated on —
`statement_0006` 43 caveats to 3, `header_fill` on exactly four Zones,
`darkdeck_0009` Zone 2 untitled, and every Shortfall exactly as the floor
recorded it. A sweep would produce the same, because nothing model-facing
after extraction reads what these steps change: the inline pass asks only
prose and list Zones, and the caption pass runs before any of them.

**This is not a substitute for a run.** It cannot move anything the model
decided. Say which of the two produced any number you report.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent / "src"))
sys.path.insert(0, str(TOOLS))

from doc_to_html import probes  # noqa: E402
from doc_to_html.corpus import SOURCES  # noqa: E402
from doc_to_html.ir import Caveat, Document, Kind  # noqa: E402
from doc_to_html.orchestrator import shortfall  # noqa: E402
from doc_to_html.preprocess import rectify  # noqa: E402
from doc_to_html.render import render  # noqa: E402
from doc_to_html.wire import (  # noqa: E402
    _title_is_its_header_cell, repadded, table_repairs)
from remeasure_style import ir_of, remeasure  # noqa: E402

REPO = TOOLS.parent

_REPAIR = re.compile(
    r"^rows? .* (was|were) (padded rather than discarded|kept whole)")
"""A table-repair Caveat, in either wording `table_repairs` has ever used."""


def rederive(document: Document, png: Path) -> None:
    """Steps 1-5 of this module's docstring, in place."""
    for zone in document.zones:
        if _title_is_its_header_cell(zone):
            zone.title = None
        if zone.kind is Kind.TABLE:
            zone.rows = repadded(zone.rows)

    caveats: list[Caveat] = []
    redone: set[int] = set()
    for caveat in document.caveats:
        if not _REPAIR.match(caveat.note):
            caveats.append(caveat)
            continue
        # Replaced where the first of them stood, so each Zone's resolution
        # Caveats still come before its repairs, as `_extract` writes them.
        if caveat.zone_index in redone:
            continue
        redone.add(caveat.zone_index)
        zone = document.zones[caveat.zone_index]
        caveats += [
            Caveat(zone_index=caveat.zone_index, kind=caveat.kind, note=note)
            for note in (table_repairs(zone) if zone.kind is Kind.TABLE else [])
        ]
    document.caveats = caveats

    remeasure(document, png)

    image = rectify(png).image
    document.shortfalls = [
        found for index, zone in enumerate(document.zones)
        if (found := shortfall(image, zone, index)) is not None
    ]
    # Q5, 2026-09-29: a column-sum totals the rows above its summary only.
    document.probes = probes.run(document)


def documents_in(source: Path, model: str) -> list[tuple[str, Path]]:
    """A frozen directory's `documents/*.html`, or a run's dump."""
    if (source / "documents").is_dir():
        return [(f.stem, f) for f in sorted((source / "documents").glob("*.html"))]
    dump = source / "dump" / model.replace(":", "_")
    return [(f.parent.name, f) for f in sorted(dump.glob("*/document.html"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path,
                        help="a frozen directory or a run directory")
    parser.add_argument("--label", required=True, help="the new run's label")
    parser.add_argument("--model", default="qwen3-vl:4b")
    args = parser.parse_args()

    target = REPO / "debug" / "runs" / args.label
    if target.exists():
        print(f"{target} already exists — pick another label")
        return 1
    found = documents_in(args.source.resolve(), args.model)
    if not found:
        print(f"no documents under {args.source}")
        return 1

    slug = args.model.replace(":", "_")
    target.mkdir(parents=True)
    (target / "rederived_from.txt").write_text(
        f"{args.source}\nmodel answers reused; everything downstream of the "
        f"model re-derived by tools/rederive.py\n")

    for name, html in found:
        if name not in SOURCES:
            print(f"{name:<22} skipped (not in the corpus)")
            continue
        document = ir_of(html.read_text(encoding="utf-8"))
        if document is None:
            print(f"{name:<22} skipped (no embedded IR)")
            continue
        rederive(document, REPO / SOURCES[name].png)
        out = target / "dump" / slug / name / "document.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(document), encoding="utf-8")
        print(f"{name:<22} caveats={len(document.caveats):<3} "
              f"header_fills={sum(1 for z in document.zones if z.header_fill)} "
              f"shortfalls={len(document.shortfalls)}")

    print(f"\n-> {target.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
