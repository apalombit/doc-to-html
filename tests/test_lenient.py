"""Repairing a model that ignored its schema, without weakening the mapper.

The inputs here are real answers taken from Ollama Cloud on 2026-07-28, not
invented ones: `minimax-m3` wraps a bare array in a markdown fence, and
`gemma4:31b` answers in its own detection format regardless of the schema given.
"""

from __future__ import annotations

import json

import pytest

from doc_to_html.engines.lenient import LenientTransport, canonicalise
from doc_to_html.engines.transport import Response
from doc_to_html.wire import LayoutResponse, TableResponse, schema_of

LAYOUT = schema_of(LayoutResponse)

MINIMAX_LAYOUT = """```json
[
  {"kind": "figure", "role": "header", "band": 0, "column": 0,
   "left": 0.05, "top": 0.055, "right": 0.405, "bottom": 0.115,
   "title": "", "graphic": "logo"}
]
```"""

GEMMA_LAYOUT = """```json
[
  {"box_2d": [93, 48, 162, 396], "label": "company_logo"}
]
```"""


class TestWhatItRepairs:
    def test_a_fenced_bare_array_becomes_the_object_the_schema_wants(self) -> None:
        repaired = canonicalise(MINIMAX_LAYOUT, LAYOUT)
        assert LayoutResponse.model_validate_json(repaired).zones[0].kind == "figure"

    def test_an_unfenced_bare_array_is_wrapped_too(self) -> None:
        rows = '[{"role": "header", "cells": ["Item", "Price"]}]'
        repaired = canonicalise(rows, schema_of(TableResponse))
        assert len(TableResponse.model_validate_json(repaired).rows) == 1

    def test_a_fenced_object_is_unwrapped(self) -> None:
        fenced = '```json\n{"zones": []}\n```'
        assert json.loads(canonicalise(fenced, LAYOUT)) == {"zones": []}

    def test_the_right_key_is_chosen_per_schema(self) -> None:
        """`zones` and `rows` are both the sole array of their own schema.

        Wrapping is only safe because there is exactly one candidate; this pins
        that the candidate is read from the schema rather than hardcoded.
        """
        array = "[]"
        assert json.loads(canonicalise(array, LAYOUT)) == {"zones": []}
        assert json.loads(canonicalise(array, schema_of(TableResponse))) == {"rows": []}


class TestWhatItLeavesAlone:
    """Everything a repair cannot recover losslessly fails as it would have."""

    def test_canonical_json_is_returned_untouched(self) -> None:
        already = '{"zones": []}'
        assert canonicalise(already, LAYOUT) is already

    def test_gemma_detection_format_is_not_translated(self) -> None:
        """`box_2d` plus a free-text `label` is not our vocabulary.

        Mapping `company_logo` onto a closed Kind enum would be guessing dressed
        as parsing. The repair declines, and the model stays unsupported rather
        than silently mis-served.
        """
        repaired = canonicalise(GEMMA_LAYOUT, LAYOUT)
        with pytest.raises(Exception):
            LayoutResponse.model_validate_json(repaired)

    def test_prose_is_left_for_the_schema_to_reject(self) -> None:
        prose = "Looking at this invoice page, I can identify the following regions:"
        assert canonicalise(prose, LAYOUT) == prose

    def test_an_empty_answer_is_left_alone(self) -> None:
        assert canonicalise("   ", LAYOUT) == "   "

    def test_a_schema_with_two_arrays_declines_to_guess(self) -> None:
        ambiguous = {"properties": {"a": {"type": "array"}, "b": {"type": "array"}}}
        assert canonicalise("[]", ambiguous) == "[]"


class TestTheWrapper:
    def transport(self, answer: str, **kwargs: object):
        def fake(**_: object) -> Response:
            return Response(content=answer, truncated=False)
        return LenientTransport(inner=fake)  # type: ignore[arg-type]

    def call(self, transport: LenientTransport) -> Response:
        return transport(model="m", pass_name="layout", prompt="p", images=[],
                         schema=LAYOUT, num_ctx=8192)

    def test_it_repairs_on_the_way_through(self) -> None:
        reply = self.call(self.transport(MINIMAX_LAYOUT))
        assert LayoutResponse.model_validate_json(reply.answer).zones[0].graphic == "logo"

    def test_an_answer_needing_no_repair_is_passed_through_identically(self) -> None:
        reply = self.call(self.transport('{"zones": []}'))
        assert reply.answer == '{"zones": []}'

    def test_truncation_survives_a_repair(self) -> None:
        """The retry in `ask` reads this flag; losing it would turn a truncated
        answer into a silently short one."""
        def fake(**_: object) -> Response:
            return Response(content=MINIMAX_LAYOUT, truncated=True)
        reply = self.call(LenientTransport(inner=fake))  # type: ignore[arg-type]
        assert reply.truncated

    def test_an_answer_on_the_reasoning_channel_is_still_repaired(self) -> None:
        """`qwen3-vl` puts structured output on `thinking`. A lenient run must
        not lose that, or enabling leniency would break the local models."""
        def fake(**_: object) -> Response:
            return Response(content="", thinking=MINIMAX_LAYOUT, truncated=False)
        reply = self.call(LenientTransport(inner=fake))  # type: ignore[arg-type]
        assert LayoutResponse.model_validate_json(reply.answer).zones


class TestEnumCoercion:
    """The one inference in the module, and the limits placed on it.

    `minimax-m3` answered `graphic: "SPARKSUITE logo"` where the schema allows
    five words. A model honouring `format` could not have.
    """

    def zone(self, **overrides: object) -> str:
        base = {
            "kind": "figure", "role": "header", "band": 0, "column": 0,
            "left": 0.0, "top": 0.0, "right": 0.4, "bottom": 0.2,
            "title": "", "graphic": "logo",
        }
        return json.dumps([base | overrides])

    def graphic_of(self, raw: str) -> str:
        return json.loads(canonicalise(raw, LAYOUT))["zones"][0]["graphic"]

    def test_a_phrase_containing_one_allowed_word_is_pulled_out(self) -> None:
        assert self.graphic_of(self.zone(graphic="SPARKSUITE logo")) == "logo"

    def test_matching_is_case_insensitive(self) -> None:
        assert self.graphic_of(self.zone(graphic="Company LOGO")) == "logo"

    def test_a_phrase_with_two_allowed_words_declines(self) -> None:
        """Ambiguity is left for the schema to reject rather than resolved by
        picking whichever came first."""
        assert self.graphic_of(self.zone(graphic="logo and badge")) == "logo and badge"

    def test_a_phrase_with_no_allowed_word_is_left_to_fail(self) -> None:
        assert self.graphic_of(self.zone(graphic="photograph")) == "photograph"

    def test_a_substring_inside_another_word_does_not_match(self) -> None:
        """Whole words only: `badger` is not `badge`."""
        assert self.graphic_of(self.zone(graphic="badger")) == "badger"

    def test_kind_and_role_are_coerced_by_the_same_rule(self) -> None:
        """Nothing about this is specific to `graphic`; it reads the schema."""
        assert json.loads(
            canonicalise(self.zone(kind="a table of items"), LAYOUT)
        )["zones"][0]["kind"] == "table"

    def test_an_already_valid_value_is_untouched(self) -> None:
        assert self.graphic_of(self.zone(graphic="stamp")) == "stamp"
