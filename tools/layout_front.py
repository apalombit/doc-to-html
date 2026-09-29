"""Run every corpus document through a real Conversion with no model at all.

    python tools/layout_front.py <out-dir> [--documents sweep]

Every model call is refused. What remains is the production layout front:
rectification, the trained detector, the recovery of unread ink, the snap and
every other model-free stage, under the shipped defaults. Each Zone then fails
to classify and renders as a skeleton, so `<out>/<document>/document.html`
shows exactly the Zones a Conversion would have read, and `trace.json` beside
it records every step that ran. All fifteen take about eleven seconds.

**Built for spec 0007's queue, Q4, and proved before it was used.** Run twice
it comes back byte-identical, and its Zones match `tests/frozen/a3-result/`'s
band, column and bbox on 15 of 15 — so it is the layout path a sweep takes,
not an approximation of it. Q4's gate used the same run with a repo-relative
source path; this writes the absolute one a sweep records, and the two differ
by that string alone. A change that should not move any Zone is measured by
running this before and after and comparing the files; one that should move
Zones is measured by which files differ.

What it cannot see: anything a model answer decides — Kinds, Titles, contents,
and every wire rule downstream of them. `tools/rederive.py` is that loop.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.corpus import SOURCES, names  # noqa: E402
from doc_to_html.engines.transport import Response  # noqa: E402
from doc_to_html.orchestrator import Conversion, EngineSet, default_engines  # noqa: E402
from doc_to_html.render import render  # noqa: E402


class Refused(RuntimeError):
    """What every model call gets. A `RuntimeError`, which is what a Zone that
    fails to classify is recorded under and carried past."""


def refuse(*, model: str, pass_name: str, prompt: str, images: list[bytes],
           schema: dict[str, object], num_ctx: int) -> Response:
    raise Refused(f"no model: {pass_name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--documents", default="all",
                        help="a corpus split, 'all', or a comma-separated list")
    args = parser.parse_args(argv)

    live = default_engines(load())
    engines = EngineSet(
        layout=live.layout,
        classify=replace(live.classify, transport=refuse),
        extract=replace(live.extract, transport=refuse),
        audit=replace(live.audit, transport=refuse),
    )
    for name in names(args.documents):
        conversion = Conversion(source=REPO / SOURCES[name].png, engines=engines)
        document = conversion.run()
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "document.html").write_text(render(document))
        (out / "trace.json").write_text(conversion.trace.to_json())
        print(f"{name:22} {len(document.zones):3} Zones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
