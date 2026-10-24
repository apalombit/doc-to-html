"""Measure the candidate faces and write the corpus's font allow-list.

    python tools/corpus_fonts.py            # write corpus/fonts.json
    python tools/corpus_fonts.py --check    # say what changed, write nothing

Every decision is in `doc_to_html.factory.fonts`; this is the command line.
Re-run it when this machine's fonts change, and re-shoot nothing until the
list has been read: a page whose face left the list draws in a fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import fonts  # noqa: E402

TARGET = REPO / "corpus" / "fonts.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare with corpus/fonts.json; write nothing")
    args = parser.parse_args()

    measured = fonts.measure(list(fonts.CANDIDATES))
    wrong = fonts.check_classes(measured)
    for line in wrong:
        print(f"class does not hold: {line}")
    faces = fonts.allow_list(measured)
    by_class: dict[str, list[str]] = {}
    for face in faces:
        by_class.setdefault(face.cls, []).append(face.family)
    for cls in fonts.CLASSES:
        print(f"{cls:8} {len(by_class.get(cls, [])):3}  "
              f"{', '.join(by_class.get(cls, []))}")
    print(f"{len(faces)} of {len(fonts.CANDIDATES)} candidates kept")

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} does not exist")
            return 1
        written = json.loads(TARGET.read_text(encoding="utf-8"))["faces"]
        now = {face.family for face in faces}
        gone, new = sorted(set(written) - now), sorted(now - set(written))
        for family in gone:
            print(f"left the list: {family}")
        for family in new:
            print(f"joined the list: {family}")
        return 1 if gone or new or wrong else 0
    if wrong:
        return 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    fonts.write(TARGET, faces, measured)
    print(f"wrote {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
