"""Write each fixture's expected IR to JSON beside its builder.

    python tools/write_expected_ir.py

The Python builders are the authoritative hand-authored ground truth; these JSON
files are their serialised form, committed so `doc-to-html render` has something
to run against without importing the test suite. `tests/test_acceptance.py`
asserts the two agree, so a change to a builder that is not written out here is
caught rather than left to drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tests.fixtures import BUILDERS  # noqa: E402


def main() -> int:
    for name, build in BUILDERS.items():
        out = REPO / "tests" / "fixtures" / f"{name}.expected.json"
        out.write_text(build().to_json() + "\n")
        print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
