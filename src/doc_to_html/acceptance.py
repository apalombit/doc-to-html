"""What "structurally correct" means, in one place.

The regression signal. Without it, a prompt change or a model swap next month can
only be argued about; with it, the two can be compared. The acceptance harness in
the suite and the bake-off script both call `compare()`, so they cannot disagree
about what counts as right.

**Structure only.** Zone count, each Zone's Kind, Role and Title, Band grouping
and column order, Row Roles within each table, and Probe outcomes. Cell-level text
accuracy is deliberately not gated: there is no measurement infrastructure for it
yet, and a threshold picked before the first measurement would be a number out of
the air. Fidelity of the text is judged by eye against the Source Image, per
docs/adr/0002.

A finding names the Zone and the field. A whole-structure diff tells you something
is wrong and leaves you to find out what, which on a ten-Zone document is most of
the work.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import probes as probe_module
from .ir import Document, Kind, Zone


@dataclass(frozen=True)
class Mismatch:
    """One specific difference, in terms a reader can act on."""

    where: str
    """`document`, `zone 3`, `band 2` — whatever the difference is about."""

    field: str
    expected: str
    actual: str

    def __str__(self) -> str:
        return (
            f"{self.where}: {self.field} expected {self.expected}, "
            f"got {self.actual}"
        )


def _zone_summary(zone: Zone) -> dict[str, str]:
    return {
        "kind": zone.kind.value,
        "role": zone.role.value,
        "title": repr(zone.title),
    }


def _band_shape(document: Document) -> list[list[int]]:
    """Which Zones share a Band, in the order they render, left to right.

    Zones are identified by their position in the document rather than by their
    Band and column numbers. Those numbers are not what a reader sees: bands 0, 1,
    2 and bands 0, 5, 9 render identically, and so do columns 0, 1 and columns 3,
    7. What matters is the grouping and the order, and comparing the raw numbers
    would report a harmless renumbering as a regression.

    It also keeps a Kind mismatch to one finding. Identifying Zones by Kind here
    would report a single wrong Kind twice — once as itself and once as a Band that
    no longer matches.
    """
    position = {id(zone): index for index, zone in enumerate(document.zones)}
    return [[position[id(zone)] for zone in band] for band in document.bands()]


def _row_roles(zone: Zone) -> list[str]:
    return [row.role.value for row in zone.rows]


def _probe_summary(document: Document) -> list[tuple[str, bool, str | None]]:
    return [(p.kind, p.ok, p.stated) for p in document.probes]


def compare(expected: Document, actual: Document) -> list[Mismatch]:
    """Every structural difference between a hand-authored IR and a converted one.

    Probe expectations are derived by running the Probes over the *expected*
    document rather than written down separately. That keeps this comparison about
    extraction: a document with nothing to reconcile attracts no check on both
    sides, and the Probes' own correctness is somebody else's test.
    """
    findings: list[Mismatch] = []

    if len(actual.zones) != len(expected.zones):
        findings.append(
            Mismatch("document", "Zone count",
                     str(len(expected.zones)), str(len(actual.zones)))
        )

    for index, (want, got) in enumerate(zip(expected.zones, actual.zones)):
        want_summary, got_summary = _zone_summary(want), _zone_summary(got)
        for field, value in want_summary.items():
            if got_summary[field] != value:
                findings.append(
                    Mismatch(f"zone {index}", field, value, got_summary[field])
                )

        if want.kind is Kind.TABLE and got.kind is Kind.TABLE:
            if _row_roles(got) != _row_roles(want):
                findings.append(
                    Mismatch(f"zone {index}", "Row Roles",
                             str(_row_roles(want)), str(_row_roles(got)))
                )

    want_bands, got_bands = _band_shape(expected), _band_shape(actual)
    if got_bands != want_bands:
        for band, (want_row, got_row) in enumerate(zip(want_bands, got_bands)):
            if want_row != got_row:
                findings.append(
                    Mismatch(f"band {band}", "Zones, left to right",
                             str(want_row), str(got_row))
                )
        if len(want_bands) != len(got_bands):
            findings.append(
                Mismatch("document", "Band count",
                         str(len(want_bands)), str(len(got_bands)))
            )

    want_probes = _probe_summary(
        Document(source=expected.source, zones=expected.zones,
                 probes=probe_module.run(expected))
    )
    got_probes = _probe_summary(actual)
    if got_probes != want_probes:
        findings.append(
            Mismatch("document", "Probe results",
                     str(want_probes) or "none", str(got_probes) or "none")
        )

    return findings


def report(name: str, findings: list[Mismatch]) -> str:
    """One line per finding, or a line saying there were none."""
    if not findings:
        return f"{name}: structure matches"
    lines = [f"{name}: {len(findings)} mismatch(es)"]
    lines += [f"  - {finding}" for finding in findings]
    return "\n".join(lines)
