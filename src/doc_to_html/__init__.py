"""doc-to-html: a photograph of a document in, structural HTML out.

Start with CONTEXT.md for the vocabulary and docs/adr/ for the decisions that
would otherwise look arbitrary.
"""

from .ir import IR_VERSION, Document, Kind, Role, RowRole
from .orchestrator import Conversion, EngineSet, convert
from .render import render

__all__ = [
    "IR_VERSION",
    "Conversion",
    "Document",
    "EngineSet",
    "Kind",
    "Role",
    "RowRole",
    "convert",
    "render",
]
