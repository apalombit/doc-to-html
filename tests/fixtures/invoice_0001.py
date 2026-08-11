"""Fixture 0001 — expected IR for example/invoice.png.

Hand-authored against the *rendered image*, deliberately not derived from
example/invoice.html. That source is layout-table soup: the header is a table,
the address block is a table, nested three deep. A tree derived from that markup
would have nothing to do with what a reader sees, which is what the IR describes.

Bounding boxes are eyeballed to roughly the right place. They matter for
Correction anchoring and Zone geometry, not for text comparison, so approximate
is fine here and exact would be false precision.
"""

from __future__ import annotations

from doc_to_html.ir import (
    BBox,
    Block,
    Document,
    Kind,
    Pair,
    Role,
    Row,
    RowRole,
    Source,
    Zone,
    cell,
)

SOURCE = Source(
    path="example/invoice.png",
    sha256="d48cde2b98ecb74a8ac195aa56b87297bfe6f6f4d81fafc1f785be46717e5afc",
    width=862,
    height=563,
)


def _pair(label: str, value: str, bbox: BBox) -> Pair:
    return Pair(label=cell(label), value=cell(value, bbox=bbox))


def build() -> Document:
    """The IR a correct Conversion of example/invoice.png should produce."""
    return Document(
        source=SOURCE,
        zones=[
            # Band 0 — logo on the left, invoice metadata on the right.
            Zone(
                kind=Kind.FIGURE,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.0487, 0.081, 0.3991, 0.1474),
                graphic_kind="logo",
                blocks=[Block(kind="caption", lines=[cell("SPARKSUITE")])],
                complete=True,
            ),
            Zone(
                kind=Kind.PAIRS,
                role=Role.HEADER,
                band=0,
                column=1,
                bbox=BBox(0.7399, 0.0799, 0.9513, 0.2007),
                pairs=[
                    _pair("Invoice #", "123", BBox(0.92, 0.085, 0.96, 0.105)),
                    _pair("Created", "January 1, 2023",
                          BBox(0.80, 0.140, 0.96, 0.160)),
                    _pair("Due", "February 1, 2023",
                          BBox(0.80, 0.170, 0.96, 0.190)),
                ],
                complete=True,
            ),
            # Band 1 — issuer on the left, recipient on the right. The system
            # does not label them as such: no document types, so they are simply
            # two prose Zones sharing a Band.
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=1,
                column=0,
                bbox=BBox(0.0487, 0.2771, 0.2275, 0.3979),
                blocks=[
                    Block(
                        kind="address",
                        lines=[
                            cell("Sparksuite, Inc."),
                            cell("12345 Sunny Road"),
                            cell("Sunnyville, CA 12345"),
                        ],
                    )
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=1,
                column=1,
                bbox=BBox(0.7866, 0.2771, 0.9513, 0.3979),
                blocks=[
                    Block(
                        kind="address",
                        lines=[
                            cell("Acme Corp."),
                            cell("John Doe"),
                            cell("john@example.com"),
                        ],
                    )
                ],
                complete=True,
            ),
            # Band 2 — payment method. A two-row table, no summary row, so no
            # column-sum Probe applies to it.
            Zone(
                kind=Kind.TABLE,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.0406, 0.4956, 0.9594, 0.595),
                rows=[
                    Row(
                        role=RowRole.HEADER,
                        cells=[cell("Payment Method"), cell("Check #")],
                    ),
                    Row(
                        role=RowRole.DATA,
                        cells=[cell("Check"), cell("1000",
                                                   bbox=BBox(0.91, 0.565, 0.96, 0.585))],
                    ),
                ],
                complete=True,
            ),
            # Band 3 — line items. The total sits inside this table as its last
            # row, which is why Row Roles exist: without them a column-sum Probe
            # would compute 300 + 75 + 10 + 385 and fail on a correct invoice.
            Zone(
                kind=Kind.TABLE,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.0406, 0.6448, 0.9594, 0.9325),
                rows=[
                    Row(role=RowRole.HEADER, cells=[cell("Item"), cell("Price")]),
                    Row(
                        role=RowRole.DATA,
                        cells=[
                            cell("Website design"),
                            cell("$300.00", bbox=BBox(0.89, 0.715, 0.96, 0.735)),
                        ],
                    ),
                    Row(
                        role=RowRole.DATA,
                        cells=[
                            cell("Hosting (3 months)"),
                            cell("$75.00", bbox=BBox(0.90, 0.777, 0.96, 0.797)),
                        ],
                    ),
                    Row(
                        role=RowRole.DATA,
                        cells=[
                            cell("Domain name (1 year)"),
                            cell("$10.00", bbox=BBox(0.90, 0.840, 0.96, 0.860)),
                        ],
                    ),
                    Row(
                        role=RowRole.SUMMARY,
                        cells=[
                            cell(""),
                            cell("Total: $385.00",
                                 bbox=BBox(0.84, 0.898, 0.96, 0.920)),
                        ],
                    ),
                ],
                complete=True,
            ),
        ],
    )
