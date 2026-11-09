"""GLM-OCR's whole pipeline over pictures: its regions, as it read them.

Spec 0023, arm D2. **Run by the parser's own Python**, never this
project's: the SDK needs PyMuPDF (AGPL-3.0), which this project keeps out,
so it lives in its own virtual environment (`~/.venvs/glmocr`, `glmocr[selfhosted]`
at `0288f96`) and this script is the only thing that imports it.

    ~/.venvs/glmocr/bin/python tools/glmocr_parse.py parser/glmocr.yaml \
        <out_dir> <picture> [<picture> ...]

writes, for each picture, `<out_dir>/<stem>.regions.json`: the reader's raw
regions for the page (`index`, `label`, `bbox_2d` on 0-1000, `polygon`,
`content`), before the SDK's markdown formatter, which adds `## ` to titles,
bullets to lines between bullets and blank lines between lines. Then one
line of JSON per picture on stdout: its seconds and region count. The
layout model is loaded once for all of them.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    config, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    from glmocr import GlmOcr

    started = time.perf_counter()
    with GlmOcr(config_path=config) as parser:
        loaded = time.perf_counter() - started
        for picture in map(Path, sys.argv[3:]):
            began = time.perf_counter()
            result = parser.parse(str(picture))
            raw = result.raw_json_result
            regions = raw[0] if raw else []
            (out / f"{picture.stem}.regions.json").write_text(
                json.dumps(regions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(json.dumps({"picture": str(picture), "regions": len(regions),
                              "seconds": round(time.perf_counter() - began, 2),
                              "load_seconds": round(loaded, 2)}), flush=True)
            loaded = 0.0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
