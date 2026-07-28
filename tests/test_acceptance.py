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
from doc_to_html.orchestrator import convert

from .fixtures import BUILDERS, IMAGES
from .replay import ReplayTransport, recorded_for
from .test_tracer_bullet import engines_replaying

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
    transport = ReplayTransport(recorded_for(fixture))
    return convert(REPO / IMAGES[fixture], engines=engines_replaying(transport))


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


class TestWhatIsDeliberatelyNotGated:
    def test_cell_text_is_not_compared(self) -> None:
        """There is no measurement infrastructure for text accuracy yet, and a
        threshold chosen before the first measurement would be invented. Text is
        judged by eye against the Source Image — docs/adr/0002."""
        expected = BUILDERS["invoice_0001"]()
        actual = converted("invoice_0001")
        actual.zones[5].rows[1].cells[0].readings[0].text = "Wcbsite dcsign"
        assert compare(expected, actual) == []

    def test_bounding_boxes_are_not_compared(self) -> None:
        """They are eyeballed in the fixtures, and exact would be false precision.
        What they are for is Correction anchoring, not text comparison."""
        from doc_to_html.ir import BBox

        expected = BUILDERS["invoice_0001"]()
        actual = converted("invoice_0001")
        actual.zones[0].bbox = BBox(0.5, 0.5, 0.6, 0.6)
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
