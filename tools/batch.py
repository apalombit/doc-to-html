"""Convert a pool of the corpus one page at a time, detached and resumable.

Spec 0021, step 3; `doc_to_html.batch` is the code. Start it detached and
read its log:

    nohup env PATH="$PWD/.venv/bin:$PATH" python tools/batch.py <label> \
        --pages dev --skip-known > debug/<label>.log 2>&1 & disown
    python tools/batch.py <label> --status

Run it again with the same arguments to resume: every page already in the
dump is skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.batch import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
