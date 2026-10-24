"""Tuned 21 (S14 re-derived today) against the ten unseen pages — same scorer, same day."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "docs" / "level-up-probe" / "src"
"""The ten probe pages: HTML and the screenshot each was converted from."""
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.corpus import NEW, Source  # noqa: E402
from doc_to_html.scoring import score_document  # noqa: E402

PROBE = REPO / "debug" / "probe" / "unseen-2026-10-24"


def probe_scores() -> list[dict]:
    path = PROBE / "scores.json"
    if path.exists():
        return json.loads(path.read_text())
    found = []
    for out in sorted((PROBE / "out").iterdir()):
        render = out / "render.html"
        if not render.exists():
            continue
        name = out.name
        source = Source(name, str(SRC / f"{name}.html"),
                        str(SRC / f"{name}.png"), "probe", "probe")
        found.append(score_document(source, render, work=out / "work").to_dict())
    path.write_text(json.dumps(found, indent=2, ensure_ascii=False))
    return found


def row(label: str, docs: list[dict]) -> str:
    c = [d["completeness"] for d in docs]
    lost = [len(x["vanished"]) for x in c]
    invented = [len(x["invented"]) for x in c]
    duplicated = [len(x["duplicated"]) for x in c]
    return (f"| {label} | {len(docs)} | {sum(1 for n in lost if n == 0)} | {sum(lost)} "
            f"| {sum(invented)} | {sum(duplicated)} "
            f"| {mean(x['vocabulary_recall'] for x in c):.3f} | {mean(x['precision'] for x in c):.3f} "
            f"| {mean(d['order']['tau'] for d in docs):.3f} "
            f"| {mean(abs(d['layout']['height_ratio'] - 1) for d in docs):.3f} |")


def main() -> int:
    tuned = json.loads((REPO / "debug/runs/G0-s14-rederived/scores.json").read_text())["documents"]
    if isinstance(tuned, dict):
        tuned = [dict(name=k, **v) for k, v in tuned.items()]
    fifteen = [d for d in tuned if d["name"] not in NEW]
    six = [d for d in tuned if d["name"] in NEW]
    unseen = probe_scores()
    print("| set | pages | pages losing no word | words lost | words invented | strings duplicated "
          "| vocab recall | precision | tau | mean height error |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for label, docs in (("the fifteen", fifteen), ("the six", six), ("all 21", tuned),
                        ("ten unseen", unseen)):
        print(row(label, docs))
    print()
    for d in unseen:
        c = d["completeness"]
        print(d["name"], "vanished", c["vanished"], "invented", c["invented"][:12],
              "duplicated", c["duplicated"][:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
