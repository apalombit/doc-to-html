"""One-off probe: convert documents the pipeline has never seen, shipped defaults.

Shoots each HTML at its width, converts the PNG with `Conversion` (default
engines, the same calls a sweep makes), renders, scores against the source HTML
and builds a source|render sheet. Nothing here touches the corpus.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "docs" / "level-up-probe" / "src"
"""The ten probe pages: HTML and the screenshot each was converted from."""
sys.path.insert(0, str(REPO / "src"))

from doc_to_html import projection  # noqa: E402
from doc_to_html.corpus import Source  # noqa: E402
from doc_to_html.orchestrator import Conversion  # noqa: E402
from doc_to_html.render import render  # noqa: E402
from doc_to_html.review import pair  # noqa: E402
from doc_to_html.scoring import score_document  # noqa: E402

PROBE = REPO / "debug" / "probe" / "unseen-2026-10-24"
WIDTHS = {
    "payslip": 900, "labreport": 860, "nutrition": 500, "recipe": 900,
    "minutes": 820, "flyer": 800, "quiz": 860, "datasheet": 940,
    "contract": 820, "email": 820,
}


def main() -> int:
    only = sys.argv[1:] or list(WIDTHS)
    src = SRC
    for name in only:
        png = src / f"{name}.png"
        if not png.exists():
            projection.screenshot(src / f"{name}.html", png, width=WIDTHS[name])
            print(f"shot {name}", flush=True)
    if shoot_only:
        return 0
    import subprocess
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "commit.txt").write_text(subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
        text=True).stdout)
    summary_path = PROBE / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in only:
        out = PROBE / "out" / name
        out.mkdir(parents=True, exist_ok=True)
        png = src / f"{name}.png"
        entry: dict = {"name": name}
        started = time.perf_counter()
        try:
            conversion = Conversion(source=png)
            document = conversion.run()
            entry["seconds"] = round(time.perf_counter() - started, 1)
            entry["calls"] = len(conversion.trace.calls)
            entry["zones"] = len(document.zones)
            entry["failures"] = len(document.failures)
            (out / "render.html").write_text(render(document), encoding="utf-8")
            (out / "ir.json").write_text(document.to_json(), encoding="utf-8")
            (out / "trace.json").write_text(conversion.trace.to_json(), encoding="utf-8")
        except Exception as error:  # keep going: one page must not stop the rest
            entry["error"] = f"{type(error).__name__}: {error}"
            entry["traceback"] = traceback.format_exc()
            entry["seconds"] = round(time.perf_counter() - started, 1)
            summary[name] = entry
            summary_path.write_text(json.dumps(summary, indent=2))
            print(f"FAILED {name}: {entry['error']}", flush=True)
            continue
        try:
            source = Source(name, str(src / f"{name}.html"), str(png), "probe", "probe")
            score = score_document(source, out / "render.html", work=out / "work")
            done = score.completeness
            entry.update({
                "vocabulary_recall": round(done.vocabulary_recall, 3),
                "precision": round(done.precision, 3),
                "join_recall": round(done.join_recall, 3),
                "tau": round(score.order.tau, 3),
                "beside": round(score.layout.beside_agreement, 3),
                "height_ratio": round(score.layout.height_ratio, 3),
                "vanished": list(done.vanished),
            })
        except Exception as error:
            entry["score_error"] = f"{type(error).__name__}: {error}"
        try:
            sheets = pair(png, out / "render.html", out / "sheet", label=name)
            entry["sheets"] = [str(p) for p in sheets]
        except Exception as error:
            entry["sheet_error"] = f"{type(error).__name__}: {error}"
        summary[name] = entry
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"done {name}: {entry.get('seconds')}s, {entry.get('calls')} calls, "
              f"vanished {len(entry.get('vanished', []))}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
