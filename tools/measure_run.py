"""One command over a run: the checks, the report, the pages to open, their
sheets and the form.

Spec 0021, step 4; `doc_to_html.measure` is the code.

    python tools/measure_run.py debug/runs/<label>
    python tools/measure_run.py debug/runs/<label> --previous debug/runs/<older>
    python tools/measure_run.py debug/runs/<label> --all     # open every page

Then open `<run>/_review/review.md`'s sheets, answer `findings.json`, and
tally it with `python tools/visual_review.py <run> --check`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.measure import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
