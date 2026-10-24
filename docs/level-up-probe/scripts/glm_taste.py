"""Taste test: GLM-OCR reads each probe page whole. Not a pipeline, not a measurement to decide on.

For each page: one call, prompt "Text Recognition:", temperature 0. The answer's
words are compared with the source HTML's words using the project's own
tokenizer, so `vanished` means exactly what it means in a report.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "docs" / "level-up-probe" / "src"
"""The ten probe pages: HTML and the screenshot each was converted from."""
sys.path.insert(0, str(REPO / "src"))

from PIL import Image  # noqa: E402

from doc_to_html.projection import project  # noqa: E402
from doc_to_html.scoring import tokens  # noqa: E402

PROBE = REPO / "debug" / "probe" / "unseen-2026-10-24"
MODEL = "glm-ocr:q8_0"
PAGES = ["payslip", "labreport", "nutrition", "recipe", "minutes", "flyer",
         "quiz", "datasheet", "contract", "email"]


def ask(png: Path, prompt: str) -> tuple[str, float]:
    body = json.dumps({
        "model": MODEL, "stream": False,
        "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 6000},
        "messages": [{"role": "user", "content": prompt,
                      "images": [base64.b64encode(png.read_bytes()).decode()]}],
    }).encode()
    request = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:
        answer = json.loads(response.read())
    return answer["message"]["content"], time.perf_counter() - started


def words(text: str) -> list[str]:
    # Only real markup is stripped: `< 42 ... >` and `<s.lindqvist@...>` are printed text.
    text = re.sub(r"</?(table|thead|tbody|tfoot|tr|td|th|caption|colgroup|col|br|b|i|u|sup|sub|span|div|p)\b[^<>]*>",
                  " ", text, flags=re.I)
    return tokens(text)


def per_zone(pages: list[str]) -> int:
    """D1: today's Zones, each read by GLM-OCR instead of qwen3-vl:4b."""
    out = PROBE / "glm-zones"
    out.mkdir(exist_ok=True)
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in pages:
        png = SRC / f"{name}.png"
        html = (SRC / f"{name}.html").read_text(encoding="utf-8")
        ir = json.loads((PROBE / "out" / name / "ir.json").read_text())
        page = Image.open(png).convert("RGB")
        width, height = page.size
        assert (ir["source"]["rectified_width"], ir["source"]["rectified_height"]) == (width, height)
        source = set(tokens(project(html, width=width, flat=True).text))
        texts, seconds = [], 0.0
        for index, zone in enumerate(ir["zones"]):
            box = zone["bbox"]
            crop = page.crop((max(0, int(box["left"] * width) - 4), max(0, int(box["top"] * height) - 4),
                              min(width, int(box["right"] * width) + 4), min(height, int(box["bottom"] * height) + 4)))
            path = out / f"{name}-z{index:02d}.png"
            crop.save(path)
            prompt = "Table Recognition:" if zone["kind"] == "table" else "Text Recognition:"
            text, took = ask(path, prompt)
            seconds += took
            texts.append(f"<!-- z{index} {zone['kind']} {prompt} -->\n{text}")
        joined = "\n\n".join(texts)
        (out / f"{name}.md").write_text(joined, encoding="utf-8")
        got = set(words(re.sub(r"<!--.*?-->", " ", joined)))
        summary[name] = {
            "seconds": round(seconds, 1), "zones": len(ir["zones"]),
            "source_words": len(source),
            "vanished": sorted(source - got), "invented": sorted(got - source),
            "vocabulary_recall": round(len(source & got) / len(source), 3),
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"{name} (zones): {seconds:.1f}s, vanished {len(source - got)}, "
              f"invented {len(got - source)}", flush=True)
    return 0


def rescore(folder: str) -> int:
    """Re-score saved answers without asking the model again."""
    out = PROBE / folder
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text())
    for name, entry in summary.items():
        png = SRC / f"{name}.png"
        html = (SRC / f"{name}.html").read_text(encoding="utf-8")
        source = set(tokens(project(html, width=Image.open(png).width, flat=True).text))
        text = re.sub(r"<!--.*?-->", " ", (out / f"{name}.md").read_text(encoding="utf-8"))
        got = set(words(text))
        entry.update(vanished=sorted(source - got), invented=sorted(got - source),
                     vocabulary_recall=round(len(source & got) / len(source), 3))
        print(f"{name}: vanished {entry['vanished']} invented {entry['invented'][:8]}")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    if sys.argv[1:2] == ["--rescore"]:
        return rescore(sys.argv[2])
    if sys.argv[1:2] == ["--zones"]:
        return per_zone(sys.argv[2:] or PAGES)
    pages = sys.argv[1:] or PAGES
    out = PROBE / "glm"
    out.mkdir(exist_ok=True)
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in pages:
        png = SRC / f"{name}.png"
        html = (SRC / f"{name}.html").read_text(encoding="utf-8")
        width = Image.open(png).width
        source = set(tokens(project(html, width=width, flat=True).text))
        text, seconds = ask(png, "Text Recognition:")
        (out / f"{name}.md").write_text(text, encoding="utf-8")
        got = set(words(text))
        summary[name] = {
            "seconds": round(seconds, 1),
            "source_words": len(source),
            "vanished": sorted(source - got),
            "invented": sorted(got - source),
            "vocabulary_recall": round(len(source & got) / len(source), 3),
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"{name}: {seconds:.1f}s, vanished {len(source - got)}, "
              f"invented {len(got - source)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
