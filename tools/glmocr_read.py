"""GLM-OCR's reader on crops we choose, in the mode we choose — spec 0025, 3c.

Run by the parser's own Python, as `tools/glmocr_parse.py` is (the SDK
lives in `~/.venvs/glmocr`). Each request is a picture, a box on 0-1000
and a task (`table`, `text`, `formula`): the crop is the SDK's own
(`crop_image_region`), the request its own (`PageLoader.build_request_from_image`,
its prompt for the task and its settings from our config, untouched), and
the call its own (`OCRClient.process`). No layout model runs.

    ~/.venvs/glmocr/bin/python tools/glmocr_read.py parser/glmocr.yaml requests.json

`requests.json` is a list of `{"picture", "bbox_2d", "task"}`; one line of
JSON per request goes to stdout, in order: its `content` and seconds.
"""
from __future__ import annotations

import json
import sys
import time


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    from glmocr.config import GlmOcrConfig
    from glmocr.dataloader.page_loader import PageLoader
    from glmocr.ocr_client import OCRClient
    from glmocr.utils.image_utils import crop_image_region

    config = GlmOcrConfig.from_yaml(sys.argv[1]).pipeline
    requests = json.loads(open(sys.argv[2], encoding="utf-8").read())
    loader = PageLoader(config.page_loader)
    client = OCRClient(config.ocr_api)
    client.start()
    try:
        pages: dict[str, object] = {}
        for request in requests:
            began = time.perf_counter()
            picture = request["picture"]
            if picture not in pages:
                pages[picture] = loader._load_image(picture)
            crop = crop_image_region(pages[picture], request["bbox_2d"])
            response, status = client.process(
                loader.build_request_from_image(crop, request["task"]))
            content = (response["choices"][0]["message"]["content"] or "").strip() \
                if status == 200 else ""
            print(json.dumps({"content": content, "status": status,
                              "seconds": round(time.perf_counter() - began, 2)}), flush=True)
    finally:
        client.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
