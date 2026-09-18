"""Hand-built `Document` objects, used as **input** to tests. Not a reference.

These were `tests/fixtures/` — the acceptance set — and they were the thing the
project was measured against: `acceptance.compare()` scored a converted IR
against them field by field, and a mismatch total was the steering signal.

**That is over.** Spec 0007 retired it, and Thread 0 deleted `acceptance.py`,
`tests/test_acceptance.py` and every `*.expected.json`. There is no longer any
function in this repository that scores anything against these objects, and
there is no file on disk that serialises them. Ground truth now comes from
`example/*.html` by way of `projection.project()`, and the measure is
`scoring.score_document()`.

What survives is their other job, which was never the problem: **they are a
realistic `Document` to hand to something.** The renderer, the Probes and the
recorded-response replay all need one, and building a plausible five-Zone
invoice inline in every test that wants one is worse than keeping five here.

Two rules follow from that, and they are the whole reason this file says so at
length:

- **Never score against these.** If you find yourself comparing a converted
  Document to one of them, you have rebuilt the harness spec 0007 deleted, and
  you are measuring agreement with a transcription rather than resemblance to a
  page.
- **They may drift from the pages, and that is tolerable now.** Under the old
  harness a builder that disagreed with its Source Image was a bug in the
  ruler. Here they are fixtures in the ordinary sense: they only have to be
  *plausible* IR, not *true* IR.

`example/*.png` is reached through `doc_to_html.corpus`, which is now the one
place that says what the corpus is.
"""

from __future__ import annotations

from typing import Callable

from doc_to_html.ir import Document

from .invoice_0001 import build as invoice_0001
from .invoice_0002 import build as invoice_0002
from .sample_css_0004 import build as sample_css_0004
from .sample_semantic_0005 import build as sample_semantic_0005
from .sample_table_0003 import build as sample_table_0003

SAMPLE_DOCUMENTS: dict[str, Callable[[], Document]] = {
    "invoice_0001": invoice_0001,
    "invoice_0002": invoice_0002,
    "sample_table_0003": sample_table_0003,
    "sample_css_0004": sample_css_0004,
    "sample_semantic_0005": sample_semantic_0005,
}
"""Deliberately not called `BUILDERS`, and deliberately not called an
acceptance set. The name is the reminder: these are sample documents."""
