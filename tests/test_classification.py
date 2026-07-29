"""The Kind question, asked about one Zone at a time against its own crop.

The layout pass decides every Kind at `LAYOUT_LONG_EDGE` while looking at the
whole page. Issue #13 measured what that costs and separated two causes: a Zone
asked about on its own is classified correctly at a resolution where the same
Zone, asked about as one of seven, is not; and a Zone whose distinction needs
glyphs — a shaded heading row over a data row, against two label/value lines —
needs both the crop *and* a model able to use it.

This module covers the Engine side of that split. Nothing here converts a
document: the Orchestrator does not call any of it yet.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.ir import BBox, Kind, Role, Zone
from doc_to_html.preprocess import PAD_X, PAD_Y, NoGeometry
from doc_to_html.wire import (
    ClassifyResponse,
    MappingError,
    classification_into,
    schema_of,
)

from .replay import Call, ReplayTransport, text

PAGE_WIDTH, PAGE_HEIGHT = 800, 600


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


def answer(kind: str = "pairs", title: str = "", graphic: str = "") -> str:
    return ClassifyResponse(
        kind=kind,  # type: ignore[arg-type]
        title=title,
        graphic=graphic,  # type: ignore[arg-type]
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
        engine, _ = engine_with(answer("pairs", title="Company Details"))
        assert engine.classify_zone(page(), zone()).title == "Company Details"

    def test_no_title_is_None_rather_than_empty(self) -> None:
        """`None` and `""` render differently, and the wire can only say `""`."""
        engine, _ = engine_with(answer("pairs", title="   "))
        assert engine.classify_zone(page(), zone()).title is None

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
        assert set(properties) == {"kind", "title", "graphic"}
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
