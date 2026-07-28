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
            # Band 0 — masthead.
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.096, 0.062, 0.430, 0.096),
                blocks=[Block(kind="heading", lines=[cell("The Weekly Digest")])],
                complete=True,
            ),
            # Band 1 — navigation. A list by structure, a row by presentation.
            Zone(
                kind=Kind.LIST,
                role=Role.HEADER,
                band=1,
                column=0,
                bbox=BBox(0.096, 0.125, 0.365, 0.146),
                blocks=[
                    Block(kind="item", lines=[cell(label)]) for label in NAV
                ],
                complete=True,
            ),
            # Band 2 — article title and byline.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.096, 0.235, 0.495, 0.262),
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
            # Band 3 — opening section beside the callout.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.096, 0.355, 0.580, 0.465),
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
                band=3,
                column=1,
                bbox=BBox(0.598, 0.335, 0.927, 0.487),
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
            # Band 4 — the bulleted list.
            Zone(
                kind=Kind.LIST,
                role=Role.BODY,
                band=4,
                column=0,
                bbox=BBox(0.096, 0.485, 0.560, 0.595),
                title="Benefits",
                blocks=[
                    Block(kind="item", lines=[cell(text)]) for text in BENEFITS
                ],
                complete=True,
            ),
            # Band 5 — quotation and its attribution.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=5,
                column=0,
                bbox=BBox(0.096, 0.620, 0.840, 0.700),
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
            # Band 6 — tag row.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=6,
                column=0,
                bbox=BBox(0.096, 0.755, 0.285, 0.775),
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[cell("Tags: html, web, standards")],
                    )
                ],
                complete=True,
            ),
            # Band 7 — colophon.
            Zone(
                kind=Kind.PROSE,
                role=Role.FOOTER,
                band=7,
                column=0,
                bbox=BBox(0.096, 0.860, 0.425, 0.910),
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
