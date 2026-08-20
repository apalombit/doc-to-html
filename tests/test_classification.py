"""The Kind question, asked about one Zone at a time against its own crop.

The layout pass decides every Kind at `LAYOUT_LONG_EDGE` while looking at the
whole page. Issue #13 measured what that costs and separated two causes: a Zone
asked about on its own is classified correctly at a resolution where the same
Zone, asked about as one of seven, is not; and a Zone whose distinction needs
glyphs — a shaded heading row over a data row, against two label/value lines —
needs both the crop *and* a model able to use it.

The first half of this module covers the Engine side of that split — one call,
one Zone, one enum answer. The second half covers the Orchestrator driving it as
a pass of its own between geometry and extraction, which is where the split
becomes visible to an operator.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from doc_to_html import orchestrator
from doc_to_html.checkpoints import Answer, ScriptedHandler
from doc_to_html.config import load
from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.ir import BBox, Document, Kind, Role, Zone
from doc_to_html.orchestrator import Conversion
from doc_to_html.preprocess import PAD_X, PAD_Y, NoGeometry
from doc_to_html.wire import (
    CaptionResponse,
    ClassifyResponse,
    LayoutResponse,
    MappingError,
    WireZone,
    classification_into,
    schema_of,
)

from .replay import Call, ReplayTransport, convert_recording, engines_replaying, text

PAGE_WIDTH, PAGE_HEIGHT = 800, 600

REPO = Path(__file__).resolve().parent.parent
INVOICE = REPO / "example" / "invoice.png"
NOWHERE = Path("/nonexistent/.env")
"""Settings resolved here must not depend on the developer's own `.env`."""


def page() -> np.ndarray:
    """A page of plausible size. The pixels do not matter; the geometry does."""
    return np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), 255, dtype=np.uint8)


def zone(kind: Kind = Kind.PROSE, bbox: BBox | None = None) -> Zone:
    return Zone(
        kind=kind,
        role=Role.BODY,
        bbox=bbox if bbox is not None else BBox(0.25, 0.25, 0.75, 0.5),
    )


def engine_with(*replies: str) -> tuple[OllamaEngine, ReplayTransport]:
    transport = ReplayTransport([text(reply) for reply in replies])
    return OllamaEngine(model="test-model", transport=transport), transport


def answer(kind: str = "pairs", graphic: str = "") -> str:
    return ClassifyResponse(
        kind=kind,  # type: ignore[arg-type]
        graphic=graphic,  # type: ignore[arg-type]
    ).model_dump_json()


def caption(first_line: str = "", line_is: str = "caption") -> str:
    return CaptionResponse(
        first_line=first_line,
        line_is=line_is,  # type: ignore[arg-type]
    ).model_dump_json()


def sent(call: Call) -> Image.Image:
    return Image.open(io.BytesIO(call.images[0]))


class TestTheClassifierSeesTheZone:
    def test_it_is_shown_the_crop_and_not_the_page(self) -> None:
        """The whole point of the split, and the one assertion that carries it.

        Derived from the box and the pads rather than written down: a literal
        here goes stale the moment either pad is retuned, and a stale literal in
        this assertion reads as a broken crop.
        """
        engine, transport = engine_with(answer())
        box = BBox(0.25, 0.25, 0.75, 0.5)

        engine.classify_zone(page(), zone(bbox=box))

        wide = min(1.0, box.right + PAD_X) - max(0.0, box.left - PAD_X)
        tall = min(1.0, box.bottom + PAD_Y) - max(0.0, box.top - PAD_Y)
        image = sent(transport.last)
        assert image.size == (round(wide * PAGE_WIDTH), round(tall * PAGE_HEIGHT))
        assert image.size[0] < PAGE_WIDTH and image.size[1] < PAGE_HEIGHT

    def test_it_is_one_call_per_zone(self) -> None:
        """The loop belongs to the Orchestrator, as it does for extraction.

        A method taking every Zone at once would put a loop of model calls where
        the Orchestrator cannot see it — which is the objection the spec raises
        against hiding these calls inside `detect_zones`, and it applies just as
        well to hiding them one level down.
        """
        engine, transport = engine_with(answer(), answer("table"))

        engine.classify_zone(page(), zone())
        engine.classify_zone(page(), zone())

        assert len(transport.calls) == 2

    def test_a_zone_with_no_box_cannot_be_classified(self) -> None:
        engine, _ = engine_with(answer())
        with pytest.raises(NoGeometry):
            engine.classify_zone(page(), Zone(kind=Kind.PROSE, bbox=None))


class TestWhatComesBack:
    def test_the_answer_replaces_the_kind_the_zone_arrived_with(self) -> None:
        """Geometry's guess is not consulted. After #17 there will not be one."""
        engine, _ = engine_with(answer("table"))

        classified = engine.classify_zone(page(), zone(kind=Kind.PROSE))

        assert classified.kind is Kind.TABLE

    def test_a_title_belonging_to_the_zone_comes_back_with_it(self) -> None:
        """From the caption pass, not the Kind question. Asked alongside the
        Kind it came back empty 36 times out of 36 — see `CAPTION_PROMPT`."""
        engine, _ = engine_with(caption("Company Details", line_is="caption"))
        assert engine.read_caption(page(), zone()).title == "Company Details"

    def test_a_first_line_that_is_content_is_not_a_title(self) -> None:
        """The model read the line and said it is the content\'s own first row.
        Storing it anyway would duplicate it: the Extractor reads it next."""
        engine, _ = engine_with(caption("Name", line_is="content"))
        assert engine.read_caption(page(), zone()).title is None

    def test_a_grid_heading_row_is_not_a_title_either(self) -> None:
        """The answer the two-value schema could not express, and the whole
        reason for the third. `"Item"` over a price table is a heading — it is
        just not the *region's* heading — and with only true/false available the
        model said true, cutting the row off `invoice_0001`'s table in run 71."""
        engine, _ = engine_with(caption("Item", line_is="header"))
        assert engine.read_caption(page(), zone()).title is None

    def test_a_verdict_outside_the_three_is_refused(self) -> None:
        """Constrained decoding prevents this locally; the lenient path for cloud
        models does not honour `format`, so the mapper is the guard. Refusing
        costs the Title and nothing else — see `Conversion._read_caption`."""
        engine, _ = engine_with('{"first_line": "Item", "line_is": "maybe"}')
        with pytest.raises(MappingError):
            engine.read_caption(page(), zone())

    def test_no_title_is_None_rather_than_empty(self) -> None:
        """`None` and `""` render differently, and the wire can only say `""`."""
        engine, _ = engine_with(caption("   ", line_is="caption"))
        assert engine.read_caption(page(), zone()).title is None

    def test_a_figure_says_which_graphic_it_is(self) -> None:
        engine, _ = engine_with(answer("figure", graphic="logo"))

        classified = engine.classify_zone(page(), zone())

        assert classified.kind is Kind.FIGURE
        assert classified.graphic_kind == "logo"

    def test_classifying_does_not_make_a_zone_complete(self) -> None:
        """A Kind is not contents. The Zone still renders as a skeleton until an
        Extractor fills it, and a Zone marked complete here would never be."""
        engine, _ = engine_with(answer("pairs"))
        assert not engine.classify_zone(page(), zone()).complete


class TestTheAnswerIsConstrained:
    def test_the_schema_closes_the_kind(self) -> None:
        """Constrained decoding is what makes a wrong Kind impossible rather
        than merely unlikely — the reason this pass is one small enum."""
        schema = schema_of(ClassifyResponse)
        assert set(schema["properties"]["kind"]["enum"]) == {
            kind.value for kind in Kind
        }

    def test_the_schema_closes_the_graphic(self) -> None:
        """Described as a free string, this model once answered `"SPARKSUITE"` —
        the text it had read off the wordmark. See `WireZone.graphic`."""
        enum = schema_of(ClassifyResponse)["properties"]["graphic"]["enum"]
        assert "" in enum and "logo" in enum and "SPARKSUITE" not in enum

    def test_the_schema_is_flat(self) -> None:
        """One record of scalars, per this repo's rule: a 4B model asked for
        something flat reads a page better than one asked for something nested."""
        properties = schema_of(ClassifyResponse)["properties"]
        assert set(properties) == {"kind", "graphic"}
        assert all(field.get("type") != "array" for field in properties.values())

    def test_a_kind_outside_the_closed_set_is_refused(self) -> None:
        with pytest.raises(MappingError, match="stripe"):
            classification_into(zone(), '{"kind": "stripe", "title": "", '
                                        '"graphic": ""}')

    def test_a_graphic_outside_the_closed_set_is_refused(self) -> None:
        """Belt and braces for an Engine that cannot constrain — the same
        runtime check `zones_from_layout` keeps for the same reason."""
        with pytest.raises(MappingError, match="SPARKSUITE"):
            classification_into(zone(), '{"kind": "figure", "title": "", '
                                        '"graphic": "SPARKSUITE"}')


# --- The Orchestrator side --------------------------------------------------
#
# These build their own responses rather than replaying `tests/responses/`. The
# recordings say what five particular documents look like; what is under test
# here is the shape of the pass sequence, and tying that to a fixture would mean
# re-recording five documents to change one assertion about call order.

PROSE_CONTENT = '{"blocks": [{"kind": "paragraph", "lines": ["a line"]}]}'
PAIRS_CONTENT = '{"pairs": [{"label": "Due", "value": "today"}]}'
CONTENT_FOR = {"prose": PROSE_CONTENT, "pairs": PAIRS_CONTENT}


def geometry(*kinds: str) -> str:
    """A geometry answer stacking one Zone per Band down the page.

    The Kinds passed here are what geometry *guessed*. Every test below then
    hands classification a different answer, because a Kind that survived from
    geometry would make the whole pass unobservable.
    """
    height = 0.9 / len(kinds)
    return LayoutResponse(
        zones=[
            WireZone(
                kind=kind,  # type: ignore[arg-type]
                role="body", band=index, column=0,
                left=0.05, top=0.05 + index * height,
                right=0.95, bottom=0.05 + (index + 1) * height,
                title="", graphic="",
            )
            for index, kind in enumerate(kinds)
        ]
    ).model_dump_json()


UNCLASSIFIABLE = '{"kind": "stripe"}'
"""A Kind outside the closed set, which `classification_into` refuses. How a
failing classification is provoked without a model that fails."""


def convert_classifying(guessed: list[str], classified: list[str],
                        broken: int | None = None,
                        ) -> tuple[Document, ReplayTransport]:
    """Convert `example/invoice.png` against a scripted geometry/classify/extract.

    `broken` is the index of the one Zone whose classification comes back
    unusable.
    """
    replies = [text(geometry(*guessed))]
    for index, kind in enumerate(classified):
        replies.append(text(UNCLASSIFIABLE if index == broken else answer(kind)))
    # Only the Zones that survive classification are extracted, so only they get
    # a content reply — `ReplayTransport` serves by order, and a spare reply here
    # would be handed to the next Zone's question.
    replies.extend(
        text(CONTENT_FOR[kind])
        for index, kind in enumerate(classified) if index != broken
    )
    return convert_recording(INVOICE, replies)


class TestTheOrchestratorClassifiesBetweenGeometryAndExtraction:
    def test_the_three_passes_run_in_order(self) -> None:
        """Geometry once, then every Zone classified, then every Zone extracted.

        The batching is not incidental: classification defaults to a different
        model from geometry and extraction, and two vision models resident at
        once does not fit in 8GB. Interleaving classify and extract per Zone
        would cost a model reload per Zone rather than two for the document.
        """
        _, transport = convert_classifying(["prose", "prose"], ["prose", "pairs"])

        assert [call.pass_name for call in transport.calls] == [
            "layout", "classify", "classify", "prose", "pairs",
        ]

    def test_the_kind_that_routes_a_zone_comes_from_classification(self) -> None:
        """The whole spec, as one assertion: geometry said prose, the crop said
        pairs, and it is the crop's answer that reached an Extractor."""
        document, transport = convert_classifying(["prose"], ["pairs"])

        assert document.zones[0].kind is Kind.PAIRS
        assert transport.calls[-1].pass_name == "pairs"

    def test_classification_is_routable_to_its_own_model(self) -> None:
        """A model that locates blocks well and one that reads them well need
        not be the same one. They are the same one today; what #15 bought is
        that changing it is a setting rather than an edit here."""
        settings = load(env={"DTH_CLASSIFY_MODEL": "a-classifier"}, dotenv_path=NOWHERE)
        engines = orchestrator.default_engines(settings)

        assert engines.classify.model == "a-classifier"
        assert engines.layout.model == settings.layout_model
        assert engines.classify.model != engines.layout.model

    def test_classification_runs_once_per_conversion_not_once_per_round(
        self,
    ) -> None:
        """Same reason geometry does. A second round refines what is *in* the
        Zones; re-classifying would spend a call per Zone to be told again what
        the same pixels are."""
        transport = ReplayTransport(
            [text(geometry("prose")), text(answer("prose")), text(PROSE_CONTENT)]
        )
        # A note is what makes a round non-empty, so this runs two of them.
        handler = ScriptedHandler([Answer(), Answer(note="try again"), Answer()])
        Conversion(
            source=INVOICE, engines=engines_replaying(transport), handler=handler
        ).run()

        rounds = [q for q in handler.asked if q.kind == "convergence"]
        assert len(rounds) == 2
        assert [c.pass_name for c in transport.calls].count("classify") == 1
        assert [c.pass_name for c in transport.calls].count("layout") == 1


class TestAFailedClassificationDoesNotSpread:
    def test_the_other_zones_still_classify_and_extract(self) -> None:
        """One bad crop does not cost the document, following the contract
        extraction already keeps."""
        document, transport = convert_classifying(
            ["prose", "prose"], ["prose", "pairs"], broken=0
        )

        assert [f.zone_index for f in document.failures] == [0]
        assert document.zones[1].kind is Kind.PAIRS
        assert document.zones[1].complete

    def test_the_failure_names_the_zone_and_why(self) -> None:
        document, _ = convert_classifying(
            ["prose"], ["prose"], broken=0
        )

        failure = document.failures[0]
        assert failure.zone_index == 0
        assert "stripe" in failure.reason

    def test_an_unclassified_zone_is_not_then_extracted(self) -> None:
        """Its Kind is unknown, so there is no question to ask about it. Asking
        anyway would route it on geometry's guess — the guess this pass exists
        to stop trusting."""
        _, transport = convert_classifying(
            ["prose"], ["prose"], broken=0
        )

        assert [c.pass_name for c in transport.calls] == ["layout", "classify"]


class TestAZoneClassifiedAtReducedResolution:
    def caveat_over(self, height: int, width: int) -> str | None:
        page = np.zeros((height, width, 3), dtype=np.uint8)
        return orchestrator.classification_caveat(
            page, Zone(kind=Kind.TABLE, bbox=BBox(0.0, 0.0, 1.0, 1.0))
        )

    def test_an_over_tall_crop_says_so(self) -> None:
        """A degraded reading beats none, so the Kind stands — the Caveat is
        there so nobody mistakes it for an ordinary one."""
        caveat = self.caveat_over(4000, 800) or ""
        assert "classified at reduced resolution" in caveat

    def test_a_crop_within_the_budget_says_nothing(self) -> None:
        assert self.caveat_over(200, 800) is None

    def test_a_crop_merely_wider_than_the_budget_is_flagged_too(self) -> None:
        """The one place this must *not* copy `resolution_caveat`, which ignores
        width because slices are horizontal bands and a wide Zone loses no rows.

        Classification loses something else. `resize_long_edge` scales on
        `max(height, width)`, so a wide crop is shrunk on both axes — and what
        goes with it is the shading under a heading row and the colon after a
        label, which is the entire evidence this pass decides on. A full-width
        Zone of a 3508px page is 2-3x over the budget and nowhere near over the
        height one, so testing height here would leave the commonest crop in the
        project silently degraded.
        """
        caveat = self.caveat_over(200, 4000) or ""
        assert "classified at reduced resolution" in caveat
        assert "4000px" in caveat

    def test_it_reaches_the_document_and_keeps_its_kind(self,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       ) -> None:
        monkeypatch.setattr(
            orchestrator, "classification_caveat",
            lambda image, zone: "classified at reduced resolution: test",
        )
        document, _ = convert_classifying(["prose"], ["pairs"])

        assert [(c.zone_index, c.note) for c in document.caveats] == [
            (0, "classified at reduced resolution: test")
        ]
        assert document.zones[0].kind is Kind.PAIRS
        assert not document.failures
