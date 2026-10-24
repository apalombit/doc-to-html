"""One page for the probe: every document's source|render sheet, its numbers and the by-eye notes."""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBE = REPO / "debug" / "probe" / "unseen-2026-10-24"
NOTES = REPO / "docs" / "level-up-probe" / "notes.md"
ORDER = ["payslip", "labreport", "nutrition", "recipe", "minutes", "flyer",
         "quiz", "datasheet", "contract", "email"]


def notes_by_page() -> dict[str, str]:
    text = NOTES.read_text(encoding="utf-8").split("\n---\n")[0]
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    found = {}
    for part in parts:
        head, _, body = part.partition("\n")
        found[head.split(" ")[0]] = (head, body.strip())
    return found


def main() -> int:
    summary = json.loads((PROBE / "summary.json").read_text())
    glm = PROBE / "glm" / "summary.json"
    glm = json.loads(glm.read_text()) if glm.exists() else {}
    zones = PROBE / "glm-zones" / "summary.json"
    zones = json.loads(zones.read_text()) if zones.exists() else {}
    notes = notes_by_page()
    rows, sections = [], []
    for name in ORDER:
        entry = summary.get(name)
        if not entry:
            continue
        g, z = glm.get(name, {}), zones.get(name, {})
        rows.append(
            f"<tr><td><a href='#{name}'>{name}</a></td><td>{entry.get('seconds')}</td>"
            f"<td>{entry.get('zones')}</td><td>{len(entry.get('vanished', []))}</td>"
            f"<td>{entry.get('vocabulary_recall')}</td><td>{entry.get('precision')}</td>"
            f"<td>{len(g['vanished']) if g else '–'}</td><td>{g.get('seconds', '–')}</td>"
            f"<td>{len(z['vanished']) if z else '–'}</td><td>{z.get('seconds', '–')}</td></tr>")
        sheets = "".join(
            f"<img src='data:image/png;base64,{base64.b64encode(Path(p).read_bytes()).decode()}'>"
            for p in entry.get("sheets", []))
        head, body = notes.get(name, (name, ""))
        items = "".join(f"<li>{html.escape(line[2:])}</li>" for line in body.splitlines()
                        if line.startswith("- "))
        vanished = html.escape(", ".join(entry.get("vanished", [])) or "none")
        sections.append(
            f"<section id='{name}'><h2>{html.escape(head)}</h2>"
            f"<p class='v'>vanished: {vanished}</p><ul>{items}</ul>{sheets}</section>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Unseen probe</title>
<style>
 body {{ font:14px/1.45 -apple-system, Helvetica, Arial, sans-serif; margin:24px; color:#1d1d1f; background:#fff; }}
 table {{ border-collapse:collapse; margin:12px 0 24px; }}
 td, th {{ border:1px solid #ccc; padding:4px 8px; text-align:right; }}
 td:first-child, th:first-child {{ text-align:left; }}
 section {{ margin:28px 0; border-top:2px solid #333; padding-top:8px; }}
 img {{ max-width:100%; display:block; margin-top:8px; border:1px solid #ddd; }}
 .v {{ color:#8a1f11; }}
</style></head><body>
<h1>Ten pages the pipeline has never seen — 2026-10-24</h1>
<p>Commit {html.escape((PROBE / 'commit.txt').read_text().strip() if (PROBE / 'commit.txt').exists() else 'unknown')}, shipped defaults, one Conversion per page.
Source left, render right, at the source's width. Notes are by eye. GLM-OCR columns are the taste test
(whole page, and today's Zones re-read), not a conversion.</p>
<table><tr><th>page</th><th>s</th><th>Zones</th><th>vanished</th><th>vocab recall</th><th>precision</th>
<th>GLM page: vanished</th><th>GLM page: s</th><th>GLM Zones: vanished</th><th>GLM Zones: s</th></tr>
{''.join(rows)}</table>
{''.join(sections)}
</body></html>"""
    (PROBE / "report.html").write_text(page, encoding="utf-8")
    print(PROBE / "report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
