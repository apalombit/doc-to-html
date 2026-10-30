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
measured on. `SWEEP` is every document — twenty-one since 2026-10-13 — and is
what a phase gate is measured on. `NEW` names the six added that day, a
held-out set. A single number taken on `ITERATE` and compared with one
taken on `SWEEP` is two different quantities, so the split each result came from
is recorded beside it everywhere it is reported.

The five original names are kept exactly as they were — `invoice_0001` and the
rest — because every run directory, spec and docstring in this repository refers
to documents by those names, and renaming them would orphan the lot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    # Six added 2026-10-13, after spec 0011, each meaningfully different in
    # its formatting from the fifteen and none of them ever tuned on: the
    # held-out set `NEW` names.
    Source("letter_0016", "example/letter.html", "example/letter.png",
           "business letter",
           "a ruled letterhead, address and date blocks set apart, justified "
           "prose, a signature in a script face"),
    Source("pricing_0017", "example/pricing.html", "example/pricing.png",
           "pricing tiers",
           "three equal-height cards, a ribbon across one card's edge, tick and "
           "cross lists, button-like boxes"),
    Source("paper_0018", "example/paper.html", "example/paper.png",
           "conference paper page",
           "superscript affiliations, a ruled abstract, two columns divided by "
           "a vertical rule, an equation, a three-rule table"),
    Source("timetable_0019", "example/timetable.html", "example/timetable.png",
           "weekly timetable",
           "a grid ruled both ways, cells spanning rows and columns, tinted "
           "blocks with coloured edges, a hatched band"),
    Source("ticket_0020", "example/ticket.html", "example/ticket.png",
           "boarding pass, photographed",
           "a card turned 1.5 degrees on a dark desk, huge codes, small-capital "
           "labels over values, a dashed perforation"),
    Source("certificate_0021", "example/certificate.html",
           "example/certificate.png",
           "certificate",
           "a double-ruled frame, everything centred, small capitals, a script "
           "name, signature lines beside a round seal"),
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
"""Every document, twenty-one since 2026-10-13. Run at phase gates."""

NEW = (
    "letter_0016", "pricing_0017", "paper_0018", "timetable_0019",
    "ticket_0020", "certificate_0021",
)
"""The six added 2026-10-13 — a held-out set: no threshold, prompt or step
was set on them. Their first sweep was taken on the code `s6-result/` was
made with, so what it shows is how that code meets pages it has never seen."""

SPLITS: dict[str, tuple[str, ...]] = {"iterate": ITERATE, "sweep": SWEEP,
                                      "new": NEW}


def names(split: str, *, unseal: bool = False) -> tuple[str, ...]:
    """The documents in a split, or a single document named directly.

    Accepts a split name, `all` as a spelling of `sweep`, or a comma-separated
    list of document names — so `FIXTURE=iterate`, `FIXTURE=all` and
    `FIXTURE=invoice_0001,cv_0013` all mean something, and a typo names itself
    rather than silently measuring a smaller corpus than was asked for. A
    pool of spec 0020's corpus (`dev`, `panel`, `l3`, and the sealed
    `vault`) is `pool`'s. A list may name the manifest's pages too
    (`c0001,probe_quiz`); one in the vault raises `SealedError` unless
    `unseal`, as the vault itself does (spec 0021, step 3).
    """
    wanted = split.strip()
    if wanted in (*POOLS, "vault"):
        return pool(wanted, unseal=unseal)
    if wanted == "all":
        return SWEEP
    if wanted in SPLITS:
        return SPLITS[wanted]
    asked = tuple(part.strip() for part in wanted.split(",") if part.strip())
    pages = manifest() if any(name not in SOURCES for name in asked) else {}
    unknown = [name for name in asked if name not in SOURCES and name not in pages]
    if unknown:
        raise KeyError(
            f"unknown document(s): {', '.join(unknown)}. "
            f"Known: {', '.join(SOURCES)}, and the manifest's pages"
        )
    sealed = [name for name in asked
              if name not in SOURCES and pages[name]["pool"] == "vault"]
    if sealed and not unseal:
        raise SealedError(f"{', '.join(sealed)}: in the vault, sealed until a milestone; "
                          "pass unseal=True only when Alessandro has opened it")
    return asked


def split_of(name: str) -> str:
    """Which split a document belongs to, for a report that says so."""
    return "iterate" if name in ITERATE else "sweep"


MANIFEST = REPO / "corpus" / "manifest.json"
"""Every page of spec 0020's corpus, by id: its pool, card, files and hashes."""

L3_SUBSET = REPO / "corpus" / "l3-subset.txt"
"""The limited baseline set: 36 panel pages (spec 0020, step 6)."""

POOLS = ("dev", "panel", "l3")
"""What `pool` returns without asking: the vault is not among them."""


class SealedError(PermissionError):
    """The vault was asked for without `unseal=True`."""


def manifest() -> dict[str, dict[str, Any]]:
    """The corpus manifest's pages, by id, read afresh each call."""
    data: dict[str, dict[str, Any]] = json.loads(MANIFEST.read_text(encoding="utf-8"))["pages"]
    return data


def pool(name: str, *, unseal: bool = False) -> tuple[str, ...]:
    """The pages of one pool of spec 0020's corpus: `dev`, `panel`, or `l3`.

    **The vault refuses unless asked with `unseal=True`** (`level-up.md`
    §4.3): it is opened by nobody until a milestone, and a page looked at
    is no longer held out. The 21 and the ten probe pages are in dev.
    `SOURCES` and the splits above are untouched by the pools; a pool's
    page is found by `page`.
    """
    if name == "vault":
        if not unseal:
            raise SealedError("the vault is sealed until a milestone; pass unseal=True "
                              "only when Alessandro has opened it")
    elif name == "l3":
        return tuple(line.strip() for line in L3_SUBSET.read_text(encoding="utf-8").splitlines()
                     if line.strip())
    elif name not in POOLS:
        raise KeyError(f"unknown pool {name!r}: known {', '.join(POOLS)} and the vault")
    return tuple(page_id for page_id, entry in manifest().items() if entry["pool"] == name)


def page(name: str) -> Source:
    """A corpus page as a `Source`, from `SOURCES` or else from the manifest."""
    if name in SOURCES:
        return SOURCES[name]
    entry = manifest()[name]
    return Source(name, entry["files"]["html"], entry["files"]["png"],
                  f"{entry['kind']}{' (part)' if entry.get('scope') == 'part' else ''}",
                  f"{entry['origin']}, {entry['family']}")
