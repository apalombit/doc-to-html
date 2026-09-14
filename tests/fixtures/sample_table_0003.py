"""Fixture 0003 — expected IR for example/sample-table.png.

The large-table case, and the closest thing in the set to the inventory sheet
that motivated slicing. Fifteen data rows, five columns, thousands separators
throughout, and — importantly — **no summary row**.

That last point is the reason this fixture earns its place. A table with nothing
to reconcile against must attract no column-sum Probe at all, rather than
attracting one that fails. It also has only two numeric columns, so the
row-product Probe has no triple to infer and must stay silent: three numeric
columns are its minimum, and inventing a relationship between population and GDP
would be a false finding on correct data.

It is also the first fixture to put a Title on a `table` Zone rather than a
`pairs` or `prose` one.

Row geometry is generated rather than typed: the rows are evenly spaced in the
original, so a loop is both less error-prone and more honest than fifteen
hand-copied bounding boxes suggesting precision that was never measured.
"""

from __future__ import annotations

from doc_to_html.ir import (
    BBox,
    Block,
    Document,
    Kind,
    Role,
    Row,
    RowRole,
    Source,
    Zone,
    cell,
)

SOURCE = Source(
    path="example/sample-table.png",
    sha256="94aac4057c9f65b887e44431600a6f291876f0877c378b0db9cb2e193a1525cc",
    width=960,
    height=690,
)

HEADER = ["Country", "ISO", "Population", "GDP (USD M)", "Currency"]

ROWS = [
    ("United States", "USA", "331,900,000", "19,485,394", "USD"),
    ("China", "CHN", "1,412,000,000", "14,722,801", "CNY"),
    ("Japan", "JPN", "125,700,000", "4,937,422", "JPY"),
    ("Germany", "DEU", "83,240,000", "4,223,116", "EUR"),
    ("India", "IND", "1,408,000,000", "3,173,398", "INR"),
    ("United Kingdom", "GBR", "67,330,000", "3,070,667", "GBP"),
    ("France", "FRA", "67,750,000", "2,937,473", "EUR"),
    ("Italy", "ITA", "59,110,000", "2,099,880", "EUR"),
    ("Canada", "CAN", "38,250,000", "1,988,336", "CAD"),
    ("South Korea", "KOR", "51,740,000", "1,810,966", "KRW"),
    ("Russia", "RUS", "143,400,000", "1,775,800", "RUB"),
    ("Brazil", "BRA", "214,300,000", "1,608,981", "BRL"),
    ("Australia", "AUS", "25,690,000", "1,542,660", "AUD"),
    ("Spain", "ESP", "47,420,000", "1,425,865", "EUR"),
    ("Mexico", "MEX", "130,300,000", "1,293,490", "MXN"),
]

_FIRST_ROW_TOP = 0.220
_ROW_PITCH = 0.0507
_COLUMN_SPANS = [
    (0.038, 0.270),  # Country
    (0.278, 0.360),  # ISO
    (0.370, 0.580),  # Population
    (0.600, 0.805),  # GDP
    (0.818, 0.900),  # Currency
]


def _row(values: tuple[str, ...], index: int) -> Row:
    top = _FIRST_ROW_TOP + index * _ROW_PITCH
    return Row(
        role=RowRole.DATA,
        cells=[
            cell(text, bbox=BBox(left, top, right, top + 0.026))
            for text, (left, right) in zip(values, _COLUMN_SPANS)
        ],
    )


def build() -> Document:
    """The IR a correct Conversion of example/sample-table.png should produce."""
    return Document(
        source=SOURCE,
        zones=[
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.0292, 0.0290, 0.3052, 0.0725),
                blocks=[Block(kind="heading", lines=[cell("Country statistics")])],
                complete=True,
            ),
            Zone(
                kind=Kind.TABLE,
                role=Role.BODY,
                band=1,
                column=0,
                bbox=BBox(0.0375, 0.1188, 0.8917, 0.9522),
                title="Population and GDP (millions of USD)",
                rows=[
                    Row(role=RowRole.HEADER, cells=[cell(text) for text in HEADER]),
                    *(_row(values, index) for index, values in enumerate(ROWS)),
                ],
                complete=True,
            ),
        ],
    )
