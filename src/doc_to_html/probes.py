"""Type-agnostic arithmetic checks over extracted tables.

A Probe knows nothing about invoices. It tests structural relationships between
numbers — a column of figures summing to a value in a summary row, a pair of
columns multiplying into a third — which hold just as well for an inventory
sheet's stock counts as for an invoice's totals.

Probes may direct *where* to look again. They must never put their expected
value into a prompt: see docs/adr/0004.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .ir import Document, Kind, ProbeResult, Row, RowRole, Zone

TOLERANCE = Decimal("0.01")
"""Absolute tolerance, to absorb rounding in the document itself."""

_NUMBER = re.compile(r"-?\d[\d., \s']*\d|-?\d")


def parse_number(text: str) -> Decimal | None:
    """Pull a number out of cell text, or None if there isn't one.

    Handles the shapes real documents use: currency symbols, thousands
    separators, a label packed into the same cell as its value
    ("Total: $385.00"), and both decimal conventions.
    """
    if not text:
        return None
    match = _NUMBER.search(text.replace("−", "-"))
    if not match:
        return None

    raw = re.sub(r"[\s ']", "", match.group())
    has_dot, has_comma = "." in raw, "," in raw

    if has_dot and has_comma:
        # Whichever appears last is the decimal separator; the other groups.
        decimal_sep = "." if raw.rfind(".") > raw.rfind(",") else ","
        group_sep = "," if decimal_sep == "." else "."
        raw = raw.replace(group_sep, "").replace(decimal_sep, ".")
    elif has_comma:
        # A lone comma is decimal ("1,50") unless it groups thousands ("1,234").
        tail = raw.rsplit(",", 1)[1]
        raw = raw.replace(",", "" if len(tail) == 3 else ".")
    elif has_dot:
        tail = raw.rsplit(".", 1)[1]
        if len(tail) == 3 and raw.count(".") >= 1 and len(raw.split(".")[0]) <= 3:
            # Ambiguous: "1.234" is 1234 in European usage, 1.234 elsewhere.
            # Treat as a decimal — under-grouping is the safer misread, since it
            # produces a visible probe failure rather than a plausible total.
            pass

    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _numeric_columns(rows: list[Row]) -> dict[int, list[Decimal]]:
    """Column index -> the numbers found in DATA rows of that column."""
    columns: dict[int, list[Decimal]] = {}
    for row in rows:
        if row.role is not RowRole.DATA:
            continue
        for index, cell in enumerate(row.cells):
            value = parse_number(cell.text)
            if value is not None:
                columns.setdefault(index, []).append(value)
    return columns


def _column_sum_probes(zone: Zone, zone_index: int) -> list[ProbeResult]:
    """Does a column of DATA rows sum to a figure stated in a SUMMARY row?

    The stated total is matched by *value* across the summary row's cells rather
    than by column position, because documents routinely place it in a merged or
    offset cell, packed together with its label.
    """
    summary_rows = [r for r in zone.rows if r.role is RowRole.SUMMARY]
    if not summary_rows:
        return []

    stated: list[Decimal] = [
        value
        for row in summary_rows
        for cell in row.cells
        if (value := parse_number(cell.text)) is not None
    ]
    if not stated:
        return []

    results = []
    for index, values in _numeric_columns(zone.rows).items():
        if len(values) < 2:
            continue
        computed = sum(values, Decimal(0))
        match = next((s for s in stated if abs(s - computed) <= TOLERANCE), None)
        results.append(
            ProbeResult(
                kind="column-sum",
                zone_index=zone_index,
                ok=match is not None,
                computed=str(computed),
                stated=str(match) if match is not None else None,
                detail=f"column {index}, {len(values)} data rows",
            )
        )

    # A column that matches nothing is not itself a failure — a table may hold
    # several numeric columns of which only one is totalled. Only report failure
    # when no column reconciles with any stated figure.
    if any(r.ok for r in results):
        return [r for r in results if r.ok]
    return results[:1]


def _row_product_probes(zone: Zone, zone_index: int) -> list[ProbeResult]:
    """Do two columns multiply into a third, consistently across the table?

    The triple is inferred from the table as a whole rather than assumed, so this
    works on any document where it happens to hold — quantity x unit price, or
    units x weight — without knowing what the columns mean.
    """
    data_rows = [r for r in zone.rows if r.role is RowRole.DATA]
    if len(data_rows) < 2:
        return []

    parsed = [
        {i: v for i, c in enumerate(row.cells) if (v := parse_number(c.text)) is not None}
        for row in data_rows
    ]
    indices = sorted(set().union(*(p.keys() for p in parsed)) if parsed else set())
    if len(indices) < 3:
        return []

    for i in indices:
        for j in indices:
            if j <= i:
                continue
            for k in indices:
                if k in (i, j):
                    continue
                applicable = [p for p in parsed if {i, j, k} <= p.keys()]
                if len(applicable) < 2:
                    continue
                bad = [p for p in applicable if abs(p[i] * p[j] - p[k]) > TOLERANCE]
                if not bad:
                    return [
                        ProbeResult(
                            kind="row-product",
                            zone_index=zone_index,
                            ok=True,
                            detail=f"columns {i} x {j} = {k}, {len(applicable)} rows",
                        )
                    ]
                if len(bad) <= max(1, len(applicable) // 5):
                    # The relationship holds broadly; the exceptions are the finding.
                    return [
                        ProbeResult(
                            kind="row-product",
                            zone_index=zone_index,
                            ok=False,
                            detail=(
                                f"columns {i} x {j} = {k} holds for "
                                f"{len(applicable) - len(bad)}/{len(applicable)} rows"
                            ),
                        )
                    ]
    return []


def run(document: Document) -> list[ProbeResult]:
    """Run every Probe over every table in the Document."""
    results: list[ProbeResult] = []
    for index, zone in enumerate(document.zones):
        if zone.kind is not Kind.TABLE or not zone.complete:
            continue
        results.extend(_column_sum_probes(zone, index))
        results.extend(_row_product_probes(zone, index))
    return results


def implicated_zones(results: list[ProbeResult]) -> set[int]:
    """Zones a failed Probe points at — the input to a targeted re-read.

    Note what this returns and what it does not: locations, never expected
    values. See docs/adr/0004.
    """
    return {r.zone_index for r in results if not r.ok}
