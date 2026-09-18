"""Which documents this project is measured on, and where each one lives.

**A document is an HTML file and a screenshot of it.** That is the whole
registry. `example/sample-table.png` is a screenshot of `example/sample-table.html`,
so the expected answer for that document is already on disk and nothing has to be
transcribed — `projection.project()` reads it off the browser. Adding a document
is writing an HTML file and screenshotting it, which is what let the corpus leave
five; the previous registry was five hand-typed `Document` builders at roughly
half an hour each, rewritten in full every time the IR widened.

**Two splits, because the two questions cost differently.** `ITERATE` is the
original five, about seventeen minutes of model time, and is what a change is
measured on. `SWEEP` is all fifteen, about fifty minutes, and is what a phase
gate is measured on. A single number taken on `ITERATE` and compared with one
taken on `SWEEP` is two different quantities, so the split each result came from
is recorded beside it everywhere it is reported.

The five original names are kept exactly as they were — `invoice_0001` and the
rest — because every run directory, spec and docstring in this repository refers
to documents by those names, and renaming them would orphan the lot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
"""The repository root, found by walking up from `src/doc_to_html/`."""


@dataclass(frozen=True)
class Source:
    """One document of the corpus: the page, the picture of it, and its notes.

    `html` and `png` are repository-relative so that a run directory recording a
    corpus can be read on another machine. `archetype` and `awkward` are the
    reason the document is in the set at all — spec 0007 names a real-world shape
    for each and the one feature it carries that the others do not, and a
    document whose awkward feature nothing exercises is a document that only
    makes the suite slower.
    """

    name: str
    html: str
    png: str
    archetype: str
    awkward: str

    def html_path(self, root: Path | None = None) -> Path:
        return (root or REPO) / self.html

    def png_path(self, root: Path | None = None) -> Path:
        return (root or REPO) / self.png


_SOURCES = (
    Source("invoice_0001", "example/invoice.html", "example/invoice.png",
           "single-table invoice",
           "a logo image, right-aligned totals, label/value pairs on one line"),
    Source("invoice_0002", "example/invoice2.html", "example/invoice2.png",
           "Bootstrap invoice",
           "shaded caption bars over four panels, a two-column band, an ACME mark"),
    Source("sample_table_0003", "example/sample-table.html",
           "example/sample-table.png",
           "statistical table",
           "a table caption above a real header row, sixteen printed lines"),
    Source("sample_css_0004", "example/sample-css.html", "example/sample-css.png",
           "styled article",
           "an inline badge beside the h1, code spans, a link, two bordered cards"),
    Source("sample_semantic_0005", "example/sample-semantic.html",
           "example/sample-semantic.png",
           "semantic article",
           "a narrow aside beside wide prose, a nav bar of links, a blockquote"),
    Source("statement_0006", "example/statement.html", "example/statement.png",
           "bank statement",
           "40+ rows, zebra striping, right-aligned currency, a running balance"),
    Source("form_0007", "example/form.html", "example/form.png",
           "application form",
           "labelled input boxes, checkboxes, ruled fill-in lines, empty values"),
    Source("newsletter_0008", "example/newsletter.html", "example/newsletter.png",
           "newspaper page",
           "three columns, serif body, a drop cap, a pull quote, hairline rules"),
    Source("darkdeck_0009", "example/darkdeck.html", "example/darkdeck.png",
           "dark report page",
           "light ink on a dark ground, which inverts every binarisation default"),
    Source("receipt_0010", "example/receipt.html", "example/receipt.png",
           "thermal receipt",
           "narrow portrait aspect, monospace, centred header, dotted separators"),
    Source("report_0011", "example/report.html", "example/report.png",
           "corporate report",
           "h1-h4 hierarchy, numbered sections, footnotes, a table inside prose"),
    Source("menu_0012", "example/menu.html", "example/menu.png",
           "restaurant menu",
           "leader dots between item and price, two columns, mixed type sizes"),
    Source("cv_0013", "example/cv.html", "example/cv.png",
           "curriculum vitae",
           "an asymmetric 30/70 sidebar split — the direct test of column width"),
    Source("nonlatin_0014", "example/nonlatin.html", "example/nonlatin.png",
           "Greek invoice",
           "non-Latin script, different text metrics, different OCR assumptions"),
    Source("catalogue_0015", "example/catalogue.html", "example/catalogue.png",
           "product grid",
           "a 3x3 grid of repeated sibling cards with shaded backgrounds"),
)

SOURCES: dict[str, Source] = {source.name: source for source in _SOURCES}
"""Every document, by name, in the order the corpus grew."""

ITERATE = (
    "invoice_0001", "invoice_0002", "sample_table_0003",
    "sample_css_0004", "sample_semantic_0005",
)
"""The five the system was built against. Run on every change.

About seventeen minutes of model time on `qwen3-vl:4b`, measured from run 84's
`trace.json`: `invoice_0002` 301s, `sample_semantic_0005` 300s, `invoice_0001`
174s, `sample_table_0003` 132s, `sample_css_0004` 128s.

They are also, precisely, the documents every prompt in this project was tuned
on — which is the reason `SWEEP` exists and the reason a phase gate is not
allowed to be decided here.
"""

SWEEP = tuple(source.name for source in _SOURCES)
"""All fifteen. Run at phase gates. About fifty minutes of model time."""

SPLITS: dict[str, tuple[str, ...]] = {"iterate": ITERATE, "sweep": SWEEP}


def names(split: str) -> tuple[str, ...]:
    """The documents in a split, or a single document named directly.

    Accepts a split name, `all` as a spelling of `sweep`, or a comma-separated
    list of document names — so `FIXTURE=iterate`, `FIXTURE=all` and
    `FIXTURE=invoice_0001,cv_0013` all mean something, and a typo names itself
    rather than silently measuring a smaller corpus than was asked for.
    """
    wanted = split.strip()
    if wanted == "all":
        return SWEEP
    if wanted in SPLITS:
        return SPLITS[wanted]
    asked = tuple(part.strip() for part in wanted.split(",") if part.strip())
    unknown = [name for name in asked if name not in SOURCES]
    if unknown:
        raise KeyError(
            f"unknown document(s): {', '.join(unknown)}. "
            f"Known: {', '.join(SOURCES)}"
        )
    return asked


def split_of(name: str) -> str:
    """Which split a document belongs to, for a report that says so."""
    return "iterate" if name in ITERATE else "sweep"
