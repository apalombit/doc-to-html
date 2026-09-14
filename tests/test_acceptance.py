"""The regression signal: every fixture, converted and compared.

Five documents, each covering something the others cannot. A change to a prompt or
a model next month is judged better or worse here rather than argued about.

Runs entirely offline against recorded responses, so what it measures is the
pipeline below the model and not the model. That division is the point: the
bake-off measures the model, and neither can stand in for the other.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_to_html.acceptance import Mismatch, compare, report
from doc_to_html.ir import Document, Kind, Role, RowRole

from .fixtures import BUILDERS, IMAGES
from .replay import convert_fixture

REPO = Path(__file__).resolve().parent.parent

PROBE_EXPECTATIONS = {
    "invoice_0001": [("column-sum", True, "385.00")],
    "invoice_0002": [],
    "sample_table_0003": [],
    "sample_css_0004": [],
    "sample_semantic_0005": [],
}
"""Written out rather than derived, because the numbers are the claim.

`compare()` derives its expectation by running the Probes over the ground truth,
which is right for a regression check but circular as a statement of intent. This
table says what the acceptance set is *for*: one document reconciles at 385.00 and
four attract no check at all — a document with nothing to reconcile must not
attract one that fails.
"""


def converted(fixture: str) -> Document:
    return convert_fixture(fixture, REPO)


@pytest.mark.parametrize("fixture", list(BUILDERS))
class TestEveryFixtureConvertsToItsExpectedStructure:
    def test_structure_matches(self, fixture: str) -> None:
        findings = compare(BUILDERS[fixture](), converted(fixture))
        assert findings == [], "\n" + report(fixture, findings)

    def test_nothing_failed_to_extract(self, fixture: str) -> None:
        document = converted(fixture)
        assert document.failures == []
        assert all(zone.complete for zone in document.zones)

    def test_probes_are_what_the_acceptance_set_promises(self, fixture: str) -> None:
        document = converted(fixture)
        assert [
            (p.kind, p.ok, p.stated) for p in document.probes
        ] == PROBE_EXPECTATIONS[fixture]

    def test_the_output_is_one_self_contained_file(self, fixture: str) -> None:
        from doc_to_html.render import render

        html = render(converted(fixture))
        assert html.startswith("<!doctype html>")
        assert '"ir_version"' in html
        assert "http://" not in html and "https://" not in html


class TestTheInvoiceReconciles:
    def test_the_column_sum_lands_on_385(self) -> None:
        """The one arithmetic claim in the whole acceptance set. Three line items
        of 300, 75 and 10 against a printed total of 385, with the total inside
        the table where Row Roles keep it out of the sum."""
        document = converted("invoice_0001")
        (probe,) = document.probes
        assert (probe.kind, probe.ok) == ("column-sum", True)
        assert probe.computed == probe.stated == "385.00"


class TestTheComparisonCatchesWhatItClaimsTo:
    """A harness that passes on a broken conversion is worse than none."""

    def expected(self) -> Document:
        return BUILDERS["invoice_0001"]()

    def findings_for(self, mutate: object) -> list[Mismatch]:
        """Mutate a copy of the ground truth into a plausible bad conversion.

        Probes are run over the result, because that is what a real Conversion
        does — and it is what makes the row-role test show two findings rather
        than one.
        """
        from doc_to_html import probes

        actual = self.expected()
        mutate(actual)  # type: ignore[operator]
        actual.probes = probes.run(actual)
        return compare(self.expected(), actual)

    def test_a_wrong_kind_is_named_with_its_zone(self) -> None:
        findings = self.findings_for(
            lambda doc: setattr(doc.zones[4], "kind", Kind.PAIRS)
        )
        assert [(f.where, f.field) for f in findings] == [("zone 4", "kind")]
        assert str(findings[0]) == "zone 4: kind expected table, got pairs"

    def test_a_wrong_role_is_caught(self) -> None:
        findings = self.findings_for(
            lambda doc: setattr(doc.zones[0], "role", Role.FOOTER)
        )
        assert [f.field for f in findings] == ["role"]

    def test_a_lost_title_is_caught(self) -> None:
        findings = self.findings_for(
            lambda doc: setattr(doc.zones[4], "title", "Invented")
        )
        assert [(f.where, f.field) for f in findings] == [("zone 4", "title")]

    def test_a_missing_zone_is_caught(self) -> None:
        findings = self.findings_for(lambda doc: doc.zones.pop())
        assert ("document", "Zone count") in [(f.where, f.field) for f in findings]

    def test_a_swapped_column_order_is_caught(self) -> None:
        """Two Zones side by side in the wrong order render as a document whose
        header has the logo on the right."""
        def swap(doc: Document) -> None:
            doc.zones[0].column, doc.zones[1].column = 1, 0

        findings = self.findings_for(swap)
        assert [f.where for f in findings if f.field.startswith("Zones")] == ["band 0"]

    def test_a_collapsed_band_is_caught(self) -> None:
        """Two Zones merged into one Band stop being columns and start being a
        stack, which is a different document."""
        findings = self.findings_for(
            lambda doc: setattr(doc.zones[2], "band", 0)
        )
        assert any(f.field == "Zones, left to right" for f in findings)

    def test_a_lost_row_role_is_caught(self) -> None:
        """The totals row demoted to data would put 385 into the column sum and
        make a correct invoice fail its Probe."""
        def demote(doc: Document) -> None:
            doc.zones[5].rows[-1].role = RowRole.DATA

        findings = self.findings_for(demote)
        fields = [f.field for f in findings]
        assert "Row Roles" in fields
        assert "Probe results" in fields

    def test_a_dropped_row_is_caught(self) -> None:
        findings = self.findings_for(lambda doc: doc.zones[5].rows.pop(1))
        assert "Row Roles" in [f.field for f in findings]

    def test_an_invented_probe_is_caught(self) -> None:
        """A check the ground truth does not attract. A failing Probe on a
        document with nothing to reconcile is a false alarm an operator would
        chase."""
        from doc_to_html.ir import ProbeResult

        actual = self.expected()
        actual.probes = [ProbeResult(kind="column-sum", zone_index=0, ok=False)]
        assert [f.field for f in compare(self.expected(), actual)] == [
            "Probe results"
        ]


class TestOneGeometryFaultIsOneFinding:
    """The whole point of pairing by geometry rather than by list position.

    Compared by position, one extra Zone shifts every later Zone against the
    wrong reference, and a single mis-drawn region reports as a Kind mismatch, a
    Role mismatch and a Band mismatch on Zones that are individually correct.
    Measured on `sample_css_0004`: 10 findings from one fault, of which the
    classifier deserved none.
    """

    def expected(self) -> Document:
        return BUILDERS["invoice_0001"]()

    def findings(self, actual: Document) -> list[Mismatch]:
        """Compare, with the Probes run over the result as a Conversion does."""
        from doc_to_html import probes

        actual.probes = probes.run(actual)
        return compare(self.expected(), actual)

    def split_in_two(self, doc: Document) -> None:
        """Cut Zone 2 into the two halves a heading-and-body split produces."""
        from dataclasses import replace

        from doc_to_html.ir import BBox

        zone = doc.zones[2]
        assert zone.bbox is not None
        middle = (zone.bbox.top + zone.bbox.bottom) / 2
        top = replace(zone, bbox=BBox(zone.bbox.left, zone.bbox.top,
                                      zone.bbox.right, middle))
        bottom = replace(zone, bbox=BBox(zone.bbox.left, middle,
                                         zone.bbox.right, zone.bbox.bottom))
        doc.zones[2:3] = [top, bottom]
        for index, other in enumerate(doc.zones):
            other.band = index

    def test_a_split_region_is_named_once(self) -> None:
        actual = self.expected()
        self.split_in_two(actual)
        regions = [f for f in self.findings(actual) if f.field == "region"]
        assert [f.where for f in regions] == ["zone 2"]
        assert regions[0].actual.startswith("2 regions:")

    def test_a_split_does_not_report_the_zones_after_it_as_wrong(self) -> None:
        """The cascade this pairing exists to stop. Every Zone below the split is
        untouched, and a positional comparison calls all of them wrong."""
        actual = self.expected()
        self.split_in_two(actual)
        fields = {f.field for f in self.findings(actual)}
        assert fields == {"Zone count", "region"}

    def test_a_merged_region_is_named_once(self) -> None:
        """Two references under one produced box — `invoice_0002`'s panels."""
        from doc_to_html.ir import BBox

        actual = self.expected()
        first, second = actual.zones[2].bbox, actual.zones[3].bbox
        assert first is not None and second is not None
        actual.zones[2].bbox = BBox(min(first.left, second.left),
                                    min(first.top, second.top),
                                    max(first.right, second.right),
                                    max(first.bottom, second.bottom))
        del actual.zones[3]
        regions = [f for f in self.findings(actual) if f.field == "region"]
        assert [f.where for f in regions] == ["zone 2"]
        assert regions[0].actual.startswith("region 2 covering")

    def test_a_region_nothing_accounts_for_is_caught(self) -> None:
        """The case the old positional comparison could not see at all: a box
        drawn where no reference is, which under `zip` merely shifted the
        comparison and was reported as somebody else's wrong Kind."""
        from doc_to_html.ir import BBox

        actual = self.expected()
        actual.zones[0].bbox = BBox(0.45, 0.45, 0.55, 0.55)
        findings = self.findings(actual)
        assert ("zone 0", "region") in [(f.where, f.field) for f in findings]
        assert ("document", "extra region") in [(f.where, f.field)
                                                for f in findings]

    def test_bands_are_not_compared_through_a_geometry_fault(self) -> None:
        """Which Zones share a row is a statement about Zones both documents
        agree exist. Comparing it across a split reports the split again."""
        actual = self.expected()
        self.split_in_two(actual)
        assert not any(f.field.startswith("Zones")
                       for f in self.findings(actual))


class TestWhatIsDeliberatelyNotGated:
    def test_cell_text_is_not_compared(self) -> None:
        """There is no measurement infrastructure for text accuracy yet, and a
        threshold chosen before the first measurement would be invented. Text is
        judged by eye against the Source Image — docs/adr/0002."""
        expected = BUILDERS["invoice_0001"]()
        actual = converted("invoice_0001")
        actual.zones[5].rows[1].cells[0].readings[0].text = "Wcbsite dcsign"
        assert compare(expected, actual) == []

    def test_how_well_a_box_fits_is_not_compared_only_which_region_it_is(
        self,
    ) -> None:
        """A fixture's rectangles are derived rather than measured — off the
        browser for this one, by snapping onto the ink for the other four — so
        scoring how closely a box fits would be measuring the derivation.
        Geometry is asked one question, *which region is this*, and a box that
        is tighter or looser than its reference still answers it."""
        from doc_to_html.ir import BBox

        expected = BUILDERS["invoice_0001"]()
        actual = converted("invoice_0001")
        for zone in actual.zones:
            assert zone.bbox is not None
            zone.bbox = BBox(
                zone.bbox.left + 0.01, zone.bbox.top + 0.005,
                zone.bbox.right - 0.01, zone.bbox.bottom - 0.005,
            )
        assert compare(expected, actual) == []

    def test_band_and_column_numbering_are_not_compared_only_grouping(self) -> None:
        """Bands 0, 1, 2 and bands 0, 5, 9 render identically, and so do columns
        0, 1 and columns 3, 7. A Conversion that numbered them differently while
        grouping them the same has not made a mistake a reader would see."""
        expected = BUILDERS["invoice_0001"]()
        actual = converted("invoice_0001")
        for zone in actual.zones:
            zone.band *= 10
            zone.column = zone.column * 3 + 1
        assert compare(expected, actual) == []


class TestTheReportIsReadable:
    def test_a_pass_says_so(self) -> None:
        assert report("invoice_0001", []) == "invoice_0001: structure matches"

    def test_a_failure_lists_each_mismatch_rather_than_a_diff(self) -> None:
        text = report("x", [Mismatch("zone 4", "kind", "table", "pairs")])
        assert text.splitlines() == [
            "x: 1 mismatch(es)",
            "  - zone 4: kind expected table, got pairs",
        ]


class TestTheGroundTruthOnDisk:
    @pytest.mark.parametrize("fixture", list(BUILDERS))
    def test_the_expected_json_agrees_with_its_builder(self, fixture: str) -> None:
        """The builders are authoritative; the JSON files exist so
        `doc-to-html render` has something to run against. Drift between them
        would make the committed artifacts quietly wrong — regenerate with
        `python tools/write_expected_ir.py`."""
        on_disk = (REPO / "tests" / "fixtures" / f"{fixture}.expected.json").read_text()
        assert on_disk.strip() == BUILDERS[fixture]().to_json().strip()

    @pytest.mark.parametrize("fixture", list(BUILDERS))
    def test_every_fixture_names_an_image_that_exists(self, fixture: str) -> None:
        assert (REPO / IMAGES[fixture]).is_file()
        assert BUILDERS[fixture]().source.path == IMAGES[fixture]
