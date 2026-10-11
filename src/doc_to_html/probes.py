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
_CURRENCY = re.compile(r"[$€£¥₹]")
_JUST_A_NUMBER = re.compile(r"[-+(]?\d[\d.,\s']*\)?%?")


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


def is_numeric(text: str) -> bool:
    """Whether a cell *is* a number, rather than merely containing one.

    `parse_number` is deliberately lenient: it has to find 385.00 inside
    "Total: $385.00". Column alignment needs the opposite question asked.
    "Hosting (3 months)" and "Domain name (1 year)" are descriptions, and two of
    them in a three-row column are enough to right-align an invoice's item
    column if containing a digit is the test.
    """
    stripped = _CURRENCY.sub("", text).strip()
    if not stripped or not _JUST_A_NUMBER.fullmatch(stripped):
        return False
    return parse_number(stripped) is not None


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

    **Only the DATA rows above the first SUMMARY row are summed** — what a
    total totals. `receipt_0010`, read whole in Q5, prints `Card ****4417
    29.10` and `Change 0.00` after its `Subtotal 26.45`; counting them made the
    price column 55.55, which matches nothing printed, and the finding then
    named the quantity column summed with `4417` and `084417` out of the
    payment lines — 88843. Its eight items sum to 26.45. Every other table in
    the corpus closes with its summaries, so on those this is every DATA row,
    as before.
    """
    summary_rows = [r for r in zone.rows if r.role is RowRole.SUMMARY]
    if not summary_rows:
        return []
    first_summary = next(index for index, row in enumerate(zone.rows)
                         if row.role is RowRole.SUMMARY)

    stated: list[Decimal] = [
        value
        for row in summary_rows
        for cell in row.cells
        if (value := parse_number(cell.text)) is not None
    ]
    if not stated:
        return []

    results = []
    for index, values in _numeric_columns(zone.rows[:first_summary]).items():
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
    # when no column reconciles with any stated figure — or when a column
    # *nearly* does, which is a misread, not a column nobody totalled.
    if any(r.ok for r in results):
        return [r for r in results if r.ok] + _near_misses(
            zone, zone_index, first_summary, stated)
    return results[:1]


NEAR_MISS = Decimal("0.01")
"""How close, as a share of a stated total, a column must sum to be a misread
rather than a column nobody totalled.

**Spec 0010, step B2.** `statement_0006`'s paid-out column sums to 5,766.36
against the printed 5,772.36 — 0.1% short, exactly the 6.00 between 216.08
and the 210.08 the model read. The Probe matched the paid-in column, and
returned only that, so the miss was never shown. Columns that total nothing
miss every stated figure by far more: on the corpus the next-nearest column
to any stated total is not within 1%."""


def _near_misses(zone: Zone, zone_index: int, first_summary: int,
                 stated: list[Decimal]) -> list[ProbeResult]:
    """Columns within `NEAR_MISS` of a stated total without reaching it."""
    found = []
    for index, values in _numeric_columns(zone.rows[:first_summary]).items():
        if len(values) < 2:
            continue
        computed = sum(values, Decimal(0))
        for total in stated:
            gap = abs(total - computed)
            if total and TOLERANCE < gap <= NEAR_MISS * abs(total):
                found.append(ProbeResult(
                    kind="column-sum", zone_index=zone_index, ok=False,
                    computed=str(computed), stated=str(total),
                    detail=f"column {index}, {len(values)} data rows, "
                           f"{gap} short of the stated {total}",
                ))
                break
    return found


def _running_balance_probes(zone: Zone, zone_index: int) -> list[ProbeResult]:
    """Does a column carry a running balance, and where does it break?

    **Spec 0010, step B2.** A statement's balance column is the row above's
    balance plus what came in less what went out, row by row. Which column is
    the balance and which columns move it are inferred from the table, as
    `_row_product_probes` infers its triple: each column is tried as the
    balance, each other numeric column as adding, subtracting or neither, and
    the relation is believed only when it holds across at least
    `BALANCE_HOLDS` of the consecutive data rows, four at the least.

    Where it breaks, the rows are named — by their first cell that is not a
    number, which on a statement is the date or the payee. When two
    consecutive rows both break and the row above the first reconciles with
    the row below the second, the balance printed between them is the reading
    at fault, and that cell is named. Detection only: no value is changed, and
    none reaches a prompt (docs/adr/0004).
    """
    data = [row for row in zone.rows if row.role is RowRole.DATA]
    if len(data) < 5:
        return []
    parsed = [{i: v for i, c in enumerate(row.cells)
               if (v := parse_number(c.text)) is not None} for row in data]
    columns = sorted(set().union(*(p.keys() for p in parsed)))
    best: tuple[int, int, dict[int, int], list[int]] | None = None
    for balance in columns:
        others = [c for c in columns if c != balance][:3]
        for signs in _sign_choices(len(others)):
            if not any(signs):
                continue
            weights = dict(zip(others, signs))
            checked, broken = 0, []
            for k in range(1, len(parsed)):
                if balance not in parsed[k] or balance not in parsed[k - 1]:
                    continue
                checked += 1
                moved = sum((weights[c] * parsed[k].get(c, Decimal(0))
                             for c in others), Decimal(0))
                if abs(parsed[k - 1][balance] + moved - parsed[k][balance]) > TOLERANCE:
                    broken.append(k)
            held = checked - len(broken)
            if checked >= 4 and held >= BALANCE_HOLDS * checked and (
                    best is None or held > best[0]):
                best = (held, balance, weights, broken)
    if best is None:
        return []
    held, balance, weights, broken = best
    if not broken:
        return [ProbeResult(kind="running-balance", zone_index=zone_index, ok=True,
                            detail=f"column {balance}, {held} rows")]

    def name(k: int) -> str:
        words = [c.text for i, c in enumerate(data[k].cells)
                 if c.text.strip() and i not in parsed[k]]
        return " ".join(words) or f"row {k + 1}"

    def movement(k: int) -> Decimal:
        return sum((w * parsed[k].get(c, Decimal(0)) for c, w in weights.items()),
                   Decimal(0))

    named: list[str] = []
    skip: set[int] = set()
    for k in broken:
        if k in skip:
            continue
        after = k + 1
        if (after in broken and balance in parsed[after]
                and abs(parsed[k - 1][balance] + movement(k) + movement(after)
                        - parsed[after][balance]) <= TOLERANCE):
            named.append(f"the balance of {name(k)} ({data[k].cells[balance].text})")
            skip.add(after)
        else:
            named.append(name(k))
    return [ProbeResult(
        kind="running-balance", zone_index=zone_index, ok=False,
        detail=f"column {balance} breaks at {'; '.join(named)}",
    )]


BALANCE_HOLDS = 0.8
"""The share of consecutive rows a running balance must hold across to be
believed. A balance with a misread or two still holds on the rest; a column
that merely happens to rise and fall with another does not hold on four."""


def _sign_choices(count: int) -> list[tuple[int, ...]]:
    choices: list[tuple[int, ...]] = [()]
    for _ in range(count):
        choices = [c + (s,) for c in choices for s in (1, -1, 0)]
    return choices


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
        results.extend(_running_balance_probes(zone, index))
    return results


def implicated_zones(results: list[ProbeResult]) -> set[int]:
    """Zones a failed Probe points at — the input to a targeted re-read.

    Note what this returns and what it does not: locations, never expected
    values. See docs/adr/0004.
    """
    return {r.zone_index for r in results if not r.ok}
