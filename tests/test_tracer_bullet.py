"""The spine, end to end: a Source Image in, HTML with the IR embedded out.

Everything here goes through `convert()` — the same entry point the CLI and the
eval harness use — with only the Ollama transport replaced. Assertions are on
what a caller can observe: the Document that comes back and the HTML rendered
from it. Nothing asserts how many passes ran or which private method was called.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from doc_to_html.config import Settings
from doc_to_html.engines.ollama import OllamaEngine, TruncatedResponse, with_hint
from doc_to_html.ir import Document, Kind, Role
from doc_to_html.orchestrator import Conversion, EngineSet, convert
from doc_to_html.preprocess import RectifyError, rectify
from doc_to_html.render import render
from doc_to_html.wire import LayoutResponse, MappingError, schema_of, zones_from_layout

from .replay import Call, ReplayTransport, layout_only, text

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"


def engines_replaying(transport: ReplayTransport) -> EngineSet:
    """An EngineSet whose only difference from production is the transport."""
    settings = Settings()
    return EngineSet(
        layout=OllamaEngine(model=settings.layout_model, transport=transport),
        extract=OllamaEngine(model=settings.extract_model, transport=transport),
        audit=OllamaEngine(model=settings.audit_model, transport=transport),
    )


def convert_invoice(transport: ReplayTransport) -> Document:
    return convert(INVOICE, engines=engines_replaying(transport))


@pytest.fixture
def transport() -> ReplayTransport:
    """The layout pass and nothing else recorded.

    Every Zone therefore fails to extract, which is the spine at its thinnest:
    the run completes, the Zones are in the right Bands, and the render is
    skeletons. What makes each Zone fail is not the subject here.
    """
    return ReplayTransport(layout_only("invoice_0001"))


def layout_calls(transport: ReplayTransport) -> list[Call]:
    return [
        call for call in transport.calls
        if call.schema == schema_of(LayoutResponse)
    ]


class TestTheFirstConversion:
    def test_a_source_image_becomes_a_document(
        self, transport: ReplayTransport
    ) -> None:
        document = convert_invoice(transport)
        assert len(document.zones) == 6
        assert [z.kind for z in document.zones][:2] == [Kind.FIGURE, Kind.PAIRS]
        assert [z.role for z in document.zones][:2] == [Role.HEADER, Role.HEADER]

    def test_zones_carry_band_column_and_geometry(
        self, transport: ReplayTransport
    ) -> None:
        document = convert_invoice(transport)
        bands = document.bands()
        assert [len(band) for band in bands] == [2, 2, 1, 1]
        assert [z.column for z in bands[0]] == [0, 1]
        assert all(z.bbox is not None for z in document.zones)

    def test_a_zone_with_no_reading_renders_as_a_skeleton(
        self, transport: ReplayTransport
    ) -> None:
        """The point of the tracer bullet: the spine works before any Extractor
        does. A skeleton is an honest account of a detected, unread region."""
        document = convert_invoice(transport)
        assert not any(zone.complete for zone in document.zones)
        html = render(document)
        assert html.count('class="skeleton"') == 5  # the figure is a placeholder

    def test_the_output_is_self_contained_with_the_ir_embedded(
        self, transport: ReplayTransport
    ) -> None:
        html = render(convert_invoice(transport))
        assert html.startswith("<!doctype html>")
        assert "http://" not in html and "https://" not in html

        payload = html.split('id="doc-ir">')[1].split("</script>")[0]
        embedded = json.loads(payload.replace("<\\/", "</"))
        assert embedded["ir_version"] >= 1
        assert embedded["rectifier_version"] >= 1
        assert len(embedded["zones"]) == 6

    def test_provenance_of_the_pixels_is_recorded(
        self, transport: ReplayTransport
    ) -> None:
        source = convert_invoice(transport).source
        assert source.width == 862 and source.height == 563
        assert source.rectified_width == 862
        assert len(source.sha256) == 64

    def test_the_cli_writes_a_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`doc-to-html convert` is how an operator meets this, so it is what a
        test should drive."""
        from doc_to_html import cli

        replay = ReplayTransport(layout_only("invoice_0001"))
        monkeypatch.setattr(
            cli, "convert",
            lambda image, **kw: convert(image, engines=engines_replaying(replay)),
        )
        out = tmp_path / "out.html"
        assert cli.main(["convert", str(INVOICE), "-o", str(out)]) == 0
        assert "doc-ir" in out.read_text()


class TestTheModelIsGivenASchema:
    def test_the_wire_schema_is_passed_as_format(
        self, transport: ReplayTransport
    ) -> None:
        """Constrained decoding is what makes malformed JSON impossible. If the
        schema stops travelling with the request, that guarantee is gone and the
        absence of a JSON-repair code path becomes a bug."""
        convert_invoice(transport)
        first = transport.calls[0]
        assert first.schema == schema_of(LayoutResponse)
        assert first.images and first.images[0][:4] == b"\x89PNG"

    def test_the_wire_schema_is_not_the_ir(self) -> None:
        """A flat schema reads the page better than a nested one, and the IR's
        readings, provenance and Disputed states are not things a model produces."""
        zone = schema_of(LayoutResponse)["$defs"]["WireZone"]["properties"]
        assert "readings" not in zone and "complete" not in zone
        assert all(
            "$ref" not in spec and spec.get("type") != "array"
            for spec in zone.values()
        )

    def test_a_hint_is_appended_verbatim(self) -> None:
        """A Hint changes what a model is told, never what the code does."""
        assert with_hint("PROMPT", "the totals column is smudged").endswith(
            "the totals column is smudged"
        )
        assert with_hint("PROMPT", None) == "PROMPT"
        assert with_hint("PROMPT", "   ") == "PROMPT"

    def test_the_layout_pass_sees_a_downscaled_page(
        self, transport: ReplayTransport
    ) -> None:
        """Detecting regions is coarse work; the resolution given away here is
        bought back by cropping each Zone from the full-resolution image."""
        convert_invoice(transport)
        assert len(layout_calls(transport)[0].images[0]) < INVOICE.stat().st_size * 4


class TestMappingValidatesWhatASchemaCannot:
    def wire(self, **overrides: object) -> dict[str, object]:
        base = {
            "kind": "prose", "role": "body", "band": 0, "column": 0,
            "left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.3,
            "title": "", "graphic": "",
        }
        return base | overrides

    def parse(self, *zones: dict[str, object]) -> list[object]:
        return list(
            zones_from_layout(LayoutResponse.model_validate({"zones": list(zones)}))
        )

    def test_a_box_off_the_page_names_the_zone(self) -> None:
        with pytest.raises(MappingError, match=r"zone 0 \(prose.*right=1\.4"):
            self.parse(self.wire(right=1.4))

    def test_a_box_enclosing_no_area_names_the_zone(self) -> None:
        with pytest.raises(MappingError, match="zone 0 .*encloses no area"):
            self.parse(self.wire(top=0.5, bottom=0.5))

    def test_bands_that_do_not_descend_the_page_are_rejected(self) -> None:
        """A model that numbered Bands by reading order rather than by position
        produces geometry that is schema-valid and describes no page."""
        with pytest.raises(MappingError, match="Bands do not descend"):
            self.parse(
                self.wire(band=0, top=0.6, bottom=0.8),
                self.wire(band=1, top=0.1, bottom=0.3),
            )

    def test_zones_that_do_not_sit_side_by_side_are_not_a_band(self) -> None:
        with pytest.raises(MappingError, match="do not overlap vertically"):
            self.parse(
                self.wire(band=0, column=0, left=0.1, right=0.4,
                          top=0.1, bottom=0.2),
                self.wire(band=0, column=1, left=0.6, right=0.9,
                          top=0.5, bottom=0.7),
            )

    def test_columns_must_run_left_to_right(self) -> None:
        with pytest.raises(MappingError, match="does not run left to right"):
            self.parse(
                self.wire(band=0, column=0, left=0.6, right=0.9),
                self.wire(band=0, column=1, left=0.1, right=0.4),
            )

    def test_a_repeated_column_is_rejected(self) -> None:
        with pytest.raises(MappingError, match="share column"):
            self.parse(
                self.wire(band=0, column=0, left=0.1, right=0.4),
                self.wire(band=0, column=0, left=0.6, right=0.9),
            )

    def test_an_unknown_graphic_is_rejected(self) -> None:
        with pytest.raises(MappingError, match="graphic 'photograph'"):
            self.parse(self.wire(kind="figure", graphic="photograph"))

    def test_a_title_of_whitespace_is_no_title(self) -> None:
        assert self.parse(self.wire(title="  "))[0].title is None  # type: ignore[attr-defined]

    @pytest.mark.parametrize("fixture", [
        "invoice_0001", "invoice_0002", "sample_table_0003",
        "sample_css_0004", "sample_semantic_0005",
    ])
    def test_every_hand_authored_layout_is_accepted(self, fixture: str) -> None:
        """The plausibility rules have to admit the documents the project holds
        itself to. A rule that rejects the ground truth is a wrong rule."""
        raw = (REPO / "tests" / "responses" / fixture / "layout.json").read_text()
        assert zones_from_layout(LayoutResponse.model_validate_json(raw))


class TestFailuresThatASchemaCannotPrevent:
    def test_a_truncated_response_is_retried_with_a_raised_budget(self) -> None:
        cut = '{"zones": [{"kind": "prose", "role": "body", "band": 0, "col'
        replay = ReplayTransport([
            text(cut, truncated=True),
            *layout_only("invoice_0001"),
        ])
        document = convert_invoice(replay)
        assert len(document.zones) == 6
        assert [call.num_ctx for call in layout_calls(replay)] == [8192, 16384]

    def test_truncation_is_detected_even_when_the_transport_is_silent(self) -> None:
        """A transport may not report why it stopped. An unparseable prefix says
        the same thing."""
        replay = ReplayTransport([
            text('{"zones": [{"kind": "tab'),
            *layout_only("invoice_0001"),
        ])
        assert len(convert_invoice(replay).zones) == 6

    def test_truncating_twice_fails_clearly(self) -> None:
        """A plausible fragment returned as an answer is worse than an error: it
        looks like a sparse document."""
        replay = ReplayTransport([text("{", truncated=True)] * 2)
        with pytest.raises(TruncatedResponse, match="token limit twice"):
            convert_invoice(replay)

    def test_a_layout_returning_no_zones_aborts(self) -> None:
        """One of only two things that abort a Conversion: with no Zones there is
        nothing to show."""
        replay = ReplayTransport([text('{"zones": []}')])
        with pytest.raises(MappingError, match="no Zones"):
            convert_invoice(replay)

    def test_geometry_corresponding_to_nothing_aborts_rather_than_coercing(
        self,
    ) -> None:
        """Schema-valid nonsense. Coercing it to an empty result would put a
        sparse Document in front of an operator with nothing to explain it."""
        nonsense = {
            "zones": [
                {"kind": "table", "role": "body", "band": 0, "column": 0,
                 "left": 0.9, "top": 0.9, "right": 0.1, "bottom": 0.1,
                 "title": "", "graphic": ""}
            ]
        }
        replay = ReplayTransport([text(json.dumps(nonsense))])
        with pytest.raises(MappingError, match="zone 0"):
            convert_invoice(replay)

    def test_an_unreadable_source_image_aborts(self, tmp_path: Path) -> None:
        with pytest.raises(RectifyError, match="no such Source Image"):
            rectify(tmp_path / "absent.png")

        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not an image")
        with pytest.raises(RectifyError, match="could not decode"):
            rectify(broken)


class TestTheFailureContract:
    def test_a_zone_that_cannot_be_read_is_reported_and_does_not_abort(
        self, transport: ReplayTransport
    ) -> None:
        """With no extraction responses recorded, every Zone fails — which is
        the shape of the contract at its clearest: the run completes, each Zone
        is named with a reason, and the render shows skeletons rather than
        nothing."""
        document = convert_invoice(transport)
        assert [f.zone_index for f in document.failures] == list(range(6))
        assert {f.kind for f in document.failures} == {
            "figure", "pairs", "prose", "table"
        }
        assert all(f.reason for f in document.failures)

    def test_a_failure_is_traceable_from_the_render(
        self, transport: ReplayTransport
    ) -> None:
        html = render(convert_invoice(transport))
        assert "Unresolved" in html
        assert "could not be read" in html


class TestProvenanceOfReadings:
    def test_a_reading_records_its_engine_model_and_prompt_version(self) -> None:
        """Without these an accuracy regression cannot be attributed to a model
        change, a prompt change or a code change."""
        engine = OllamaEngine(model="qwen3-vl:2b")
        reading = engine.reading("385.00")
        assert (reading.engine, reading.model) == ("ollama", "qwen3-vl:2b")
        assert reading.prompt_version


class TestTheSuiteNeedsNoModel:
    def test_the_ollama_package_is_never_imported(
        self, transport: ReplayTransport
    ) -> None:
        """Not a proxy for "no network": it is the check that the transport seam
        is the only route to a model. A second route would leave half the
        pipeline uncovered."""
        convert_invoice(transport)
        assert "ollama" not in sys.modules

    def test_a_conversion_runs_exactly_one_round_unattended(
        self, transport: ReplayTransport
    ) -> None:
        """NullHandler answers nothing, so nothing new enters the system and a
        second round would re-run identical passes over identical pixels."""
        conversion = Conversion(
            source=INVOICE, engines=engines_replaying(transport)
        )
        conversion.run()
        assert len(layout_calls(transport)) == 1
