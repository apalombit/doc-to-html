"""Fixture 0002 — expected IR for example/invoice2.png.

Complementary to fixture 0001 rather than more of the same. This document has no
table and no arithmetic anywhere, so it attracts zero Probes — a case the system
must handle, and one 0001 cannot exercise. What it does carry is dense Pairs,
real prose, panel Titles, and a second Graphic.

Two details worth knowing before comparing against a real extraction:

- The bank account is `MO123456789456123` — letter O, not zero. In the rendered
  image the glyphs are near-identical. This is precisely the ambiguity Escalation
  and Disputed exist for, and a model reading `M0` here is wrong in a way no
  Probe can catch, because there is no arithmetic to check it against.
- `Services / Products` is a section heading with nothing beneath it. An empty
  Zone is not a failed extraction and must not be reported as one.

As with 0001, this is authored against the *rendered image*, not derived from
example/invoice2.html — that file is Bootstrap markup whose tree bears no
relation to what a reader sees. Bounding boxes are eyeballed; they matter for
Correction anchoring, not for text comparison.
"""

from __future__ import annotations

from doc_to_html.ir import (
    BBox,
    Block,
    Document,
    Kind,
    Pair,
    Role,
    Source,
    Zone,
    cell,
)

SOURCE = Source(
    path="example/invoice2.png",
    sha256="6f602a7612b19e448d974deea1b6f1685a644bb6a6edf26f349154381c3381d8",
    width=1164,
    height=718,
)

_COMPANY = [
    ("Name", "Acme Corporation", 0.246),
    ("Industry", "Software Development", 0.274),
    ("Address", "Field 3, Moon", 0.302),
    ("Phone", "123.4456.4567", 0.330),
    ("Email", "mainl@acme.com", 0.358),
    ("Tax NO", "123456789", 0.386),
    ("Tax Office", "A' Moon", 0.414),
]

_CUSTOMER = [
    ("Name", "Microsoft Corporation", 0.246),
    ("Industry", "Software Development", 0.274),
    ("Address", "One Microsoft Way Redmond, WA 98052-7329, USA", 0.302),
    ("Phone", "(425) 882-8080", 0.330),
    ("Email", "contact@microsoft.com", 0.358),
    ("Tax NO", "123456789", 0.386),
]


def _pairs(rows: list[tuple[str, str, float]], value_left: float,
           value_right: float) -> list[Pair]:
    return [
        Pair(
            label=cell(label),
            value=cell(value, bbox=BBox(value_left, top, value_right, top + 0.018)),
        )
        for label, value, top in rows
    ]


def build() -> Document:
    """The IR a correct Conversion of example/invoice2.png should produce."""
    return Document(
        source=SOURCE,
        zones=[
            # Band 0 — document title, logo, issuer block.
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.014, 0.045, 0.230, 0.110),
                blocks=[Block(kind="heading", lines=[cell("Invoice With Credit")])],
                complete=True,
            ),
            Zone(
                kind=Kind.FIGURE,
                role=Role.HEADER,
                band=0,
                column=1,
                bbox=BBox(0.676, 0.024, 0.742, 0.122),
                graphic_kind="logo",
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=2,
                bbox=BBox(0.750, 0.028, 0.900, 0.135),
                blocks=[
                    Block(
                        kind="address",
                        lines=[
                            cell("Acme Corporation"),
                            cell("Software Development"),
                            cell("Field 3, Moon"),
                            cell("info@acme.com"),
                        ],
                    )
                ],
                complete=True,
            ),
            # Band 1 — two Pairs packed onto one pipe-separated line.
            Zone(
                kind=Kind.PAIRS,
                role=Role.HEADER,
                band=1,
                column=0,
                bbox=BBox(0.014, 0.128, 0.300, 0.155),
                pairs=[
                    Pair(label=cell("NO"),
                         value=cell("554775/R1", bbox=BBox(0.048, 0.130, 0.115, 0.150))),
                    Pair(label=cell("Date"),
                         value=cell("01/01/2015", bbox=BBox(0.175, 0.130, 0.258, 0.150))),
                ],
                complete=True,
            ),
            # Band 2 — the case Title exists for: a caption bound to its block.
            Zone(
                kind=Kind.PAIRS,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.015, 0.168, 0.405, 0.455),
                title="Company Details",
                pairs=_pairs(_COMPANY, 0.183, 0.350),
                complete=True,
            ),
            Zone(
                kind=Kind.PAIRS,
                role=Role.BODY,
                band=2,
                column=1,
                bbox=BBox(0.430, 0.168, 0.985, 0.455),
                title="Customer Details",
                pairs=_pairs(_CUSTOMER, 0.590, 0.885),
                complete=True,
            ),
            # Band 3 — a heading with nothing under it. Empty, not failed.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.015, 0.487, 0.985, 0.545),
                title="Services / Products",
                complete=True,
            ),
            # Band 4 — free prose beside a payment block.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=4,
                column=0,
                bbox=BBox(0.015, 0.600, 0.573, 0.770),
                title="Comments / Notes",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "Lorem ipsum dolor sit amet, consectetur adipisicing "
                                "elit. Odit repudiandae numquam sit facere blanditiis, "
                                "quasi distinctio ipsam? Libero odit ex expedita, "
                                "facere sunt, possimus consectetur dolore, nobis iure "
                                "amet vero."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=4,
                column=1,
                bbox=BBox(0.598, 0.600, 0.985, 0.865),
                title="Payment Method",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "For your convenience, you may deposit the final "
                                "amount at one of our banks"
                            )
                        ],
                    ),
                    Block(
                        kind="paragraph",
                        lines=[
                            cell("Alpha Bank - MO123456789456123",
                                 bbox=BBox(0.607, 0.750, 0.807, 0.772)),
                            cell("Beta Bank - MO123456789456123",
                                 bbox=BBox(0.607, 0.778, 0.800, 0.800)),
                            cell("Gamma Bank - MO123456789456123",
                                 bbox=BBox(0.607, 0.806, 0.812, 0.828)),
                        ],
                    ),
                ],
                complete=True,
            ),
            # Band 5 — closing prose.
            Zone(
                kind=Kind.PROSE,
                role=Role.FOOTER,
                band=5,
                column=0,
                bbox=BBox(0.015, 0.895, 0.300, 0.975),
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell("Thank you for choosing our services."),
                            cell("We hope to see you again soon"),
                            cell("~ACME~"),
                        ],
                    )
                ],
                complete=True,
            ),
        ],
    )
