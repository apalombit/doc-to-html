"""Fixture 0005 — expected IR for example/sample-semantic.png.

The document that does not fit the model as originally scoped, which is why it
is worth having. It brings in three things the invoice-shaped fixtures never
touch:

- **A real bulleted list**, forcing `Kind.LIST` back into scope.
- **A blockquote with an attribution line**, forcing `quote` and `attribution`
  Block kinds.
- **A navigation bar** — Home / Archive / About / Contact. Structurally a list,
  visually a row. It is modelled as `Kind.LIST` with `Role.HEADER`, and the
  stylesheet renders lists inside a header Zone inline. Structure decides the
  IR; presentation follows from Role, never from anything read off the image.

It also carries the callout box (`TL;DR`) beside the article's opening section —
a two-column Band where both columns are titled prose, which is the arrangement
Bands exist for.

**Hyperlinks are deliberately absent from the IR.** `Jane Author`, the tag links
and `editor@example.com` are anchors in the source HTML, but a photograph does
not contain an href — only blue underlined text. Recording link text without its
target would be recording that something *looked* like a link, which is styling,
not structure. Links therefore render as plain text: a limit of the input, not a
shortcut.
"""

from __future__ import annotations

from doc_to_html.ir import (
    BBox,
    Block,
    Document,
    Kind,
    Role,
    Source,
    Zone,
    cell,
)

SOURCE = Source(
    path="example/sample-semantic.png",
    sha256="902f72417c0a60b00e674d36200bd10f946cbf08c91fe8f53c63b0f734594ea0",
    width=915,
    height=1122,
)

NAV = ["Home", "Archive", "About", "Contact"]

BENEFITS = [
    "Screen readers can navigate the document structure",
    "Search engines understand content hierarchy",
    "CSS and JavaScript can target meaningful regions",
]


def build() -> Document:
    """The IR a correct Conversion of example/sample-semantic.png should produce."""
    return Document(
        source=SOURCE,
        zones=[
            # Band 0 — the masthead: `<header>` holding an `<h1>` and a `<nav>`.
            #
            # **One Zone, because the heading names what follows it.** This was
            # two — the `<h1>` alone, then the nav — which read the same shape
            # the opposite way from every other fixture: a card's `<h2>` over its
            # paragraph, a Bootstrap panel's `<h3>` over its body. `ir.Zone` never
            # nests, so a Zone carrying a Title and its Blocks is the IR's only
            # vocabulary for containment, and splitting the two here was not a
            # finer reading of the page but an inconsistent one. Measured: the
            # detector already groups them, and it cost 5 geometry findings
            # across the corpus to insist otherwise.
            Zone(
                kind=Kind.LIST,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.0951, 0.0660, 0.4284, 0.1390),
                title="The Weekly Digest",
                blocks=[
                    Block(kind="item", lines=[cell(label)]) for label in NAV
                ],
                complete=True,
            ),
            # Band 1 — article title and byline.
            #
            # The rectangle has to reach the byline, and for a long time it did
            # not. It was typed as (0.096, 0.235, 0.495, 0.262), which stops at
            # the `<h2>` — while the byline this Zone's own second Block claims
            # is printed at y 0.285-0.300. That left 910px of ink no reference
            # in this fixture claimed, and it was the only such hole in the
            # corpus: the box contradicted its own contents.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=1,
                column=0,
                bbox=BBox(0.0951, 0.2362, 0.4918, 0.3004),
                blocks=[
                    Block(
                        kind="heading",
                        lines=[cell("Why semantic HTML matters")],
                    ),
                    Block(
                        kind="paragraph",
                        lines=[cell("May 9, 2026 · by Jane Author")],
                    ),
                ],
                complete=True,
            ),
            # Band 2 — opening section beside the callout.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.0962, 0.3565, 0.5770, 0.4617),
                title="Introduction",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "Modern HTML5 introduced semantic elements like "
                                "<article>, <section>, and <nav> that describe the "
                                "meaning of content rather than its appearance."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=2,
                column=1,
                bbox=BBox(0.6175, 0.3725, 0.8951, 0.4528),
                title="TL;DR",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "Semantic tags improve accessibility, SEO, and code "
                                "clarity."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
            # Band 3 — the bulleted list.
            Zone(
                kind=Kind.LIST,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.0962, 0.4875, 0.5399, 0.5927),
                title="Benefits",
                blocks=[
                    Block(kind="item", lines=[cell(text)]) for text in BENEFITS
                ],
                complete=True,
            ),
            # Band 4 — quotation and its attribution.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=4,
                column=0,
                bbox=BBox(0.1115, 0.6230, 0.8306, 0.6961),
                blocks=[
                    Block(
                        kind="quote",
                        lines=[
                            cell(
                                "HTML provides for a number of elements that allow "
                                "for finer-grained semantics in HTML documents."
                            )
                        ],
                    ),
                    Block(
                        kind="attribution",
                        lines=[cell("— W3C HTML5.2 specification")],
                    ),
                ],
                complete=True,
            ),
            # Band 5 — tag row.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=5,
                column=0,
                bbox=BBox(0.0951, 0.7602, 0.2820, 0.7727),
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[cell("Tags: html, web, standards")],
                    )
                ],
                complete=True,
            ),
            # Band 6 — colophon.
            Zone(
                kind=Kind.PROSE,
                role=Role.FOOTER,
                band=6,
                column=0,
                bbox=BBox(0.0962, 0.8654, 0.4219, 0.9118),
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell("© 2026 The Weekly Digest. All rights reserved."),
                            cell("Contact: editor@example.com"),
                        ],
                    )
                ],
                complete=True,
            ),
        ],
    )
