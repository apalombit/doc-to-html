"""The acceptance set: five documents with hand-authored expected IR.

Each earns its place by covering something the others cannot. Every one is
authored against the *rendered image* rather than derived from the source HTML,
whose markup tree bears no relation to what a reader sees.

`BUILDERS` is the single list of them, so a harness, a bake-off and the
expected-IR writer cannot disagree about what the acceptance set is.
"""

from __future__ import annotations

from typing import Callable

from doc_to_html.ir import Document

from .invoice_0001 import build as invoice_0001
from .invoice_0002 import build as invoice_0002
from .sample_css_0004 import build as sample_css_0004
from .sample_semantic_0005 import build as sample_semantic_0005
from .sample_table_0003 import build as sample_table_0003

BUILDERS: dict[str, Callable[[], Document]] = {
    "invoice_0001": invoice_0001,
    "invoice_0002": invoice_0002,
    "sample_table_0003": sample_table_0003,
    "sample_css_0004": sample_css_0004,
    "sample_semantic_0005": sample_semantic_0005,
}

IMAGES: dict[str, str] = {
    "invoice_0001": "example/invoice.png",
    "invoice_0002": "example/invoice2.png",
    "sample_table_0003": "example/sample-table.png",
    "sample_css_0004": "example/sample-css.png",
    "sample_semantic_0005": "example/sample-semantic.png",
}
