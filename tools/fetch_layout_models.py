"""Download the layout detectors the bakeoff measures, into `models/`.

    python tools/fetch_layout_models.py            # both, skipping what is there
    python tools/fetch_layout_models.py --only heron
    python tools/fetch_layout_models.py --force    # re-download

Plain `urllib` against the Hugging Face `resolve/main/` URLs rather than
`huggingface_hub`, because a dependency that exists only to concatenate a URL is
a dependency the base install would carry for nothing. `models/` is gitignored:
these are weights, not source, and re-fetching is a minute.

**Two candidates, deliberately.** They disagree about what a region *is*, which
is the whole question:

`doclayout_yolo` was trained on DocStructBench and its ten classes are the ones
a paper has — title, plain text, figure, table and their captions. It has no
concept of a form. AGPL-3.0, via the YOLOv10 lineage.

`heron` is Docling's RT-DETRv2 and predicts seventeen, among them **`form`** and
**`key_value_region`** — which is exactly what `invoice_0002`'s boxed
label/value panels are, and exactly the structure that defeats both the VLM and
the XY-cut. Apache-2.0.

Whether that second list is a real advantage or only a more flattering
vocabulary is what `tools/detector_probe.py` measures. Nothing here decides it.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODELS = REPO / "models"

HF = "https://huggingface.co"


@dataclass(frozen=True)
class Candidate:
    """One detector: where its files live, and where they land."""

    name: str
    repo: str
    files: tuple[str, ...]
    license: str

    def url(self, filename: str) -> str:
        return f"{HF}/{self.repo}/resolve/main/{filename}"

    def target(self, filename: str) -> Path:
        return MODELS / self.name / filename


CANDIDATES = (
    Candidate(
        name="doclayout_yolo",
        repo="wybxc/DocLayout-YOLO-DocStructBench-onnx",
        files=("doclayout_yolo_docstructbench_imgsz1024.onnx",),
        license="AGPL-3.0",
    ),
    Candidate(
        name="heron",
        repo="docling-project/docling-layout-heron-onnx",
        # `config.json` carries `id2label` and `preprocessor_config.json` carries
        # the 640x640 resize — both are read at inference rather than hardcoded,
        # so a model whose export changes shape says so instead of quietly
        # decoding into the wrong class names.
        files=("model.onnx", "config.json", "preprocessor_config.json"),
        license="Apache-2.0",
    ),
)


def fetch(url: str, into: Path, *, force: bool) -> bool:
    """Download one file. Returns whether anything was transferred.

    Written to a `.part` beside the target and moved into place only on success,
    so an interrupted download cannot leave a truncated ONNX file that loads and
    then decodes garbage.
    """
    if into.exists() and not force:
        print(f"  have  {into.name} ({into.stat().st_size / 1e6:.1f} MB)")
        return False

    into.parent.mkdir(parents=True, exist_ok=True)
    partial = into.with_suffix(into.suffix + ".part")
    print(f"  fetch {into.name} <- {url}")
    try:
        with urllib.request.urlopen(url) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
    except urllib.error.URLError as error:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"could not fetch {url}: {error}") from error

    partial.replace(into)
    print(f"        {into.stat().st_size / 1e6:.1f} MB")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[c.name for c in CANDIDATES],
                        help="fetch one candidate rather than both")
    parser.add_argument("--force", action="store_true",
                        help="re-download files that are already present")
    args = parser.parse_args()

    wanted = [c for c in CANDIDATES if args.only in (None, c.name)]
    for candidate in wanted:
        print(f"{candidate.name}  ({candidate.repo}, {candidate.license})")
        for filename in candidate.files:
            fetch(candidate.url(filename), candidate.target(filename),
                  force=args.force)
        print()

    print(f"models in {MODELS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
