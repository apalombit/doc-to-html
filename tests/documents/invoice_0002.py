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
relation to what a reader sees.

**Bounding boxes are snapped onto their own ink, not eyeballed.** They were
eyeballed once, and around the wrong thing: typed around what is *drawn* — a
panel's shaded caption bar, a card's border — where `invoice_0001`'s are the
ink. That cost more than it sounds. Zone 6, `Services / Products`, is a panel
whose table is empty, so its typed full-width bar scored **0.043** against the
text it actually contains, and `geometry_score.MATCH_IOU` is 0.50 — meaning no
correctly drawn detection could be paired with it at all, and the fixture rather
than the run decided the finding. Across this file the typed boxes cut through
ink in 25 places. `tools/fixture_geometry.py --snap` moved them onto it, which
takes those 25 to 0 and `covered` to 1.00.
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
            # Band 0 — document title over its own numbers, logo, issuer block.
            #
            # **The title and the NO/Date line are one Zone**, because the source
            # prints them as one block — `<div class="col-sm-8">` holding an
            # `<h1>` and the `<h4>` beneath it — and because every other titled
            # region in this corpus is read that way, panel captions here
            # included. They were two Zones in two Bands, which said the `<h1>`
            # names nothing and cost this fixture geometry findings the detector
            # did not deserve: it groups them, correctly, and had no way to be
            # right.
            Zone(
                kind=Kind.PAIRS,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.0146, 0.0627, 0.2560, 0.1504),
                title="Invoice With Credit",
                pairs=[
                    Pair(label=cell("NO"),
                         value=cell("554775/R1", bbox=BBox(0.048, 0.130, 0.115, 0.150))),
                    Pair(label=cell("Date"),
                         value=cell("01/01/2015", bbox=BBox(0.175, 0.130, 0.258, 0.150))),
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.FIGURE,
                role=Role.HEADER,
                band=0,
                column=1,
                bbox=BBox(0.6787, 0.0251, 0.7388, 0.1226),
                graphic_kind="logo",
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=2,
                bbox=BBox(0.7474, 0.0306, 0.8694, 0.1295),
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
            # Band 1 — the case Title exists for: a caption bound to its block.
            Zone(
                kind=Kind.PAIRS,
                role=Role.BODY,
                band=1,
                column=0,
                bbox=BBox(0.0284, 0.1811, 0.3050, 0.4276),
                title="Company Details",
                pairs=_pairs(_COMPANY, 0.183, 0.350),
                complete=True,
            ),
            Zone(
                kind=Kind.PAIRS,
                role=Role.BODY,
                band=1,
                column=1,
                bbox=BBox(0.4433, 0.1811, 0.9845, 0.4554),
                title="Customer Details",
                pairs=_pairs(_CUSTOMER, 0.590, 0.885),
                complete=True,
            ),
            # Band 2 — a heading with nothing under it. Empty, not failed.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.0284, 0.5028, 0.1521, 0.5223),
                title="Services / Products",
                complete=True,
            ),
            # Band 3 — free prose beside a payment block.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.0284, 0.6017, 0.5687, 0.7423),
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
                band=3,
                column=1,
                bbox=BBox(0.6091, 0.6003, 0.9820, 0.8217),
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
            # Band 4 — closing prose.
            Zone(
                kind=Kind.PROSE,
                role=Role.FOOTER,
                band=4,
                column=0,
                bbox=BBox(0.0137, 0.8997, 0.2113, 0.9694),
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
