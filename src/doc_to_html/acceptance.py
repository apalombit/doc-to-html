"""What "structurally correct" means, in one place.

The regression signal. Without it, a prompt change or a model swap next month can
only be argued about; with it, the two can be compared. The acceptance harness in
the suite and the bake-off script both call `compare()`, so they cannot disagree
about what counts as right.

**Structure only.** Zone count, how the regions correspond, each Zone's Kind, Role
and Title, Band grouping and column order, Row Roles within each table, and Probe
outcomes. Cell-level text accuracy is deliberately not gated: there is no
measurement infrastructure for it yet, and a threshold picked before the first
measurement would be a number out of the air. Fidelity of the text is judged by
eye against the Source Image, per docs/adr/0002.

A finding names the Zone and the field. A whole-structure diff tells you something
is wrong and leaves you to find out what, which on a ten-Zone document is most of
the work.

**One fault, one finding.** Zones are paired with their references by geometry
rather than by list position, because position makes the count meaningless: an
extra Zone shifts every comparison after it, and a single mis-drawn region is then
reported as a dozen mismatches spread over Zones that are individually right. The
rectangles are not scored — they are only asked *which region is this* — so the
eyeballed slop in the fixtures still costs nothing. See `geometry_score.align`,
whose thresholds are the ones the contact sheet has always printed its verdicts
at, so a sheet and a report cannot disagree about what matched what.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import probes as probe_module
from .geometry_score import Correspondence, align
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
        """One line, always.

        Whitespace is collapsed because some of what lands in `actual` arrives from
        elsewhere — a Pydantic validation error runs to four lines — and a report
        that promises one finding per line has to keep that promise.
        """
        return " ".join(
            f"{self.where}: {self.field} expected {self.expected}, "
            f"got {self.actual}".split()
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


def _pairing(expected: Document, actual: Document) -> Correspondence | None:
    """Which produced Zone stands for which reference Zone, where geometry allows.

    `None` when either side leaves a Zone without a rectangle, which sends the
    caller back to comparing by position. That fallback is a real path and not a
    guard against the impossible: `Zone.bbox` is optional, and a reference IR that
    gives no rectangles can still say everything else this module checks.
    """
    want = [zone.bbox for zone in expected.zones]
    got = [zone.bbox for zone in actual.zones]
    if any(box is None for box in want) or any(box is None for box in got):
        return None
    return align([box for box in got if box is not None],
                 [box for box in want if box is not None])


def _region_finding(index: int, pairing: Correspondence) -> Mismatch | None:
    """How this reference Zone failed to be found, or None if it was.

    One finding per reference, naming the fault rather than its consequences.
    A Zone the layout cut in two is *one* mismatch here; compared by position it
    was one per field on every Zone after it.
    """
    parts = pairing.split().get(index)
    if parts is not None:
        return Mismatch(f"zone {index}", "region", "one region",
                        f"{len(parts)} regions: "
                        f"{', '.join(str(part) for part in parts)}")
    for produced, swallowed in sorted(pairing.merged.items()):
        if index == swallowed[0]:
            return Mismatch(
                f"zone {index}", "region",
                f"{len(swallowed)} regions, one per Zone "
                f"({', '.join(str(one) for one in swallowed)})",
                f"region {produced} covering all of them",
            )
        if index in swallowed:
            return None  # reported once, against the first Zone of the group
    if index in pairing.missing:
        return Mismatch(f"zone {index}", "region", "one region", "none")
    return None


def compare(expected: Document, actual: Document) -> list[Mismatch]:
    """Every structural difference between a hand-authored IR and a converted one.

    **Zones are paired by geometry, not by position**, and that is what keeps a
    count of findings proportional to the number of faults. Compared by position,
    one Zone too many shifts every later Zone against the wrong reference, so a
    single split heading reports as a Kind mismatch, a Role mismatch and a Band
    mismatch on Zones that are individually correct — and nothing in the report
    says they share one cause. Measured on `sample_css_0004`: 10 findings from one
    geometry fault, of which the classifier deserved none, agreeing with its
    reference on 6 of 6 regions once realigned.

    So geometry is compared first and reported in its own terms — `split across`,
    `merged into one`, `no produced region covers it` — and Kind, Role, Title and
    Row Roles are compared only where there is a pair to compare them on. A field
    is never scored against a reference the Zone was not shown.

    Band structure is compared only when every Zone pairs off, for the same
    reason: which Zones share a row is a statement about Zones both documents
    agree exist. Comparing it through a disagreement reports the geometry fault
    again in other words.

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

    pairing = _pairing(expected, actual)
    if pairing is None:
        pairs = list(enumerate(zip(expected.zones, actual.zones)))
    else:
        faulted = set()
        for index in range(len(expected.zones)):
            finding = _region_finding(index, pairing)
            if finding is not None:
                findings.append(finding)
                faulted.add(index)
        for first in pairing.spurious:
            findings.append(
                Mismatch("document", "extra region", "none",
                         f"region {first}, which no Zone accounts for")
            )
        # Fields are compared only where the region itself is right. A Zone that
        # was split or merged was never shown the picture its reference
        # describes, so its Kind is an answer to a different question and
        # scoring it says nothing about the classifier.
        pairs = [
            (second, (expected.zones[second], actual.zones[first]))
            for first, second in sorted(pairing.matched.items(),
                                        key=lambda item: item[1])
            if second not in faulted
        ]

    for index, (want, got) in pairs:
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
    if got_bands != want_bands and (pairing is None or pairing.exact):
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
