"""The ratchet, and the round trip it depends on.

**The ratchet is the one rule spec 0007 allows no exception to**: completeness
may never decrease between phases, for any reason. It is not a target to
optimise; it is a floor never to cross, and it is what would have caught all
three of the faults that shipped as improvements in runs 81 to 84.

It only works if a run's `scores.json` comes back the way it went out, so both
halves are tested here. Neither needs a browser: the gate is arithmetic over
two sets of scores, and the round trip is JSON.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from doc_to_html.report import _gate_html, _previous, _summary_table, _write_scores
from doc_to_html.scoring import (
    Completeness,
    DocumentScore,
    Inline,
    Layout,
    Order,
    Palette,
    Typography,
)


def a_score(name: str = "invoice_0001", **overrides: Any) -> DocumentScore:
    """A plausible, clean score, so a test can spoil exactly one field."""
    base = DocumentScore(
        name=name, split="iterate", width=862, source_height=563,
        output_height=580,
        completeness=Completeness(
            recall=1.0, precision=1.0, join_recall=1.0,
            vocabulary_recall=1.0, vanished=(),
            source_tokens=120,
            output_tokens=120, lost=(), duplicated=(), invented=(),
            broken_joins=(), figures_lost=0, hard_breaks=6,
            source_hard_breaks=6, short_lines=6, source_short_lines=6,
        ),
        order=Order(tau=1.0, matched=16, of=16),
        layout=Layout(
            beside_agreement=1.0, beside_pairs=7, column_error=0.0,
            columns_within_tolerance=1.0, height_ratio=1.0, matched_blocks=16,
            of_blocks=16, split_regions=0, merged_regions=0,
            clipped=0, source_clipped=0,
        ),
        typography=Typography(
            source_scale=1.0, output_scale=1.0, scale_error=0.0,
            heading_levels_source=1, heading_levels_output=1,
            alignment_agreement=1.0, aligned_blocks=16,
        ),
        palette=Palette(
            source_background=(248, 248, 248), output_background=(248, 248, 248),
            source_ink=(16, 16, 16), output_ink=(16, 16, 16),
            source_accent=None, output_accent=None, background_delta=0.0,
            ink_delta=0.0, accent_delta=0.0, source_texture=0.02,
            output_texture=0.02,
        ),
        inline=Inline(found={"link": 1}, of={"link": 1}, missing=()),
    )
    return replace(base, **overrides)


class TestTheT1Ratchet:
    """Completeness may never decrease between phases, for any reason."""

    def test_a_word_lost_fails_it_even_when_more_words_are_gained(self) -> None:
        """Word by word, not ratio against ratio — and this is a live case.

        On Phase A0's own checkpoint run `darkdeck_0009` stopped printing the
        heading "What Q4 commits to" and gained the five figures of its delta
        row, so its `vocabulary_recall` *rose* from 0.910 to 0.928 while the
        page had stopped printing something it printed before. A ratio
        comparison passes that; the ratchet is a floor, not a budget to trade
        against.
        """
        before = {"invoice_0001": a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.910,
                                 vanished=("alpha", "beta", "gamma")))}
        traded = a_score(completeness=replace(
            a_score().completeness, vocabulary_recall=0.928,
            vanished=("commits", "what")))

        gate = _gate_html([traded], before)
        assert "FAILED" in gate
        assert "stopped printing commits, what" in gate

    def test_a_word_no_longer_printed_fails_the_phase_whatever_else_improved(
        self,
    ) -> None:
        """This is the whole rule, and the case that makes it worth having.

        Runs 81 to 84 moved the total 23 to 10 *while* deleting a table's
        column headers and duplicating titles in three documents. A gate that
        traded one axis off against another would have passed that change, as
        the old one did.
        """
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.95, vanished=("total",)),
            layout=replace(a_score().layout, beside_agreement=1.0,
                           height_ratio=1.0),
            typography=replace(a_score().typography, alignment_agreement=1.0),
        )

        gate = _gate_html([worse], before)
        assert "FAILED" in gate
        assert "stopped printing total" in gate

    def test_the_failure_names_the_words_that_stopped_being_printed(
        self,
    ) -> None:
        """A ratio that moved is not a finding. The words are.

        `Completeness.vanished` is what the clause is short by, so the message
        built from it says what was caught rather than only that a number fell.
        """
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.9,
                                 vanished=("currency", "iso")))

        gate = _gate_html([worse], before)
        assert "currency" in gate and "iso" in gate

    def test_a_fall_in_multiset_recall_alone_does_not_fail_it(self) -> None:
        """Spec 0007 Phase A0, 2026-09-22 — and it is the change, not a relaxation.

        Removing a doubled Zone Title lowers multiset recall on six of the
        fifteen documents while nothing leaves the page: the echo had been
        standing in, numerically, for a genuine occurrence elsewhere that the
        output never read. `newsletter_0008` prints "Castleton Chronicle" twice
        and printed both copies in its masthead Zone. The floor is what the page
        still shows, so a multiset fall with no word vanishing is not a
        regression — it is the count finally reporting the truth.
        """
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness, recall=0.95))

        gate = _gate_html([worse], before)
        assert "holds" in gate
        assert "FAILED" not in gate

    def test_a_previous_run_predating_the_field_is_reported_not_compared(
        self,
    ) -> None:
        """`nan` means unmeasured, and must never read as a previous score.

        `tests/frozen/a1-checkpoint/` was written before `vocabulary_recall`
        existed. Treating its absence as 0.0 would make every later run pass
        this clause for the wrong reason, on exactly the notch it defends.
        """
        import math
        before = {"invoice_0001": a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=math.nan))}

        gate = _gate_html([a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.4))], before)
        assert "FAILED" not in gate
        assert "unmeasured" in gate

    def test_a_fall_in_precision_fails_it_too(self) -> None:
        """Precision below 1.00 means content duplicated or invented, which is
        how eight repeated Titles arrived scoring zero findings."""
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness, precision=0.9))

        assert "FAILED" in _gate_html([worse], before)

    @pytest.mark.parametrize("field,value", [
        ("tau", 0.9),
    ])
    def test_the_rest_of_the_hard_tier_fails_it(self, field: str,
                                                value: float) -> None:
        before = {"invoice_0001": a_score()}
        worse = a_score(order=replace(a_score().order, **{field: value}))

        assert "FAILED" in _gate_html([worse], before)

    def test_losing_side_by_side_structure_fails_it(self) -> None:
        before = {"invoice_0001": a_score()}
        worse = a_score(
            layout=replace(a_score().layout, beside_agreement=0.8))

        assert "FAILED" in _gate_html([worse], before)

    def test_a_soft_tier_axis_going_backwards_does_not_fail_it(self) -> None:
        """T4, T5 and T6 are traded off against each other and judged on net
        movement. Only 1, 2 and 3 are absolute."""
        before = {"invoice_0001": a_score()}
        worse = a_score(
            typography=replace(a_score().typography, alignment_agreement=0.3),
            inline=Inline(found={"link": 0}, of={"link": 1}, missing=("link: x",)),
        )

        assert "holds" in _gate_html([worse], before)

    def test_holding_steady_passes(self) -> None:
        before = {"invoice_0001": a_score()}

        assert "holds" in _gate_html([a_score()], before)

    def test_the_first_run_has_nothing_to_ratchet_against_and_says_so(
        self,
    ) -> None:
        """Rather than passing silently, which would read the same as a pass
        on a real comparison."""
        gate = _gate_html([a_score()], {})

        assert "No previous run" in gate
        assert "the notch the next one may not fall below" in gate

    def test_a_regressed_document_is_marked_in_the_summary_row(self) -> None:
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.95, vanished=("total",)))

        assert 'class="regressed"' in _summary_table([worse], before)

    def test_the_summary_marks_a_row_on_the_same_rule_the_gate_fails_on(
        self,
    ) -> None:
        """Or a reader sees a clean table above a failed gate, and vice versa."""
        before = {"invoice_0001": a_score()}
        worse = a_score(
            completeness=replace(a_score().completeness, recall=0.95))

        assert 'class="regressed"' not in _summary_table([worse], before)
        assert "holds" in _gate_html([worse], before)

    def test_the_summary_marks_the_row_a_traded_word_loss_fails_the_gate_on(
        self,
    ) -> None:
        """The case the two came apart on: `darkdeck_0009` lost two words and
        gained five, so the ratio rose. Flagging the row on the ratio left a
        green table above a failed gate."""
        before = {"invoice_0001": a_score(
            completeness=replace(a_score().completeness,
                                 vocabulary_recall=0.910,
                                 vanished=("alpha", "beta", "gamma")))}
        traded = a_score(completeness=replace(
            a_score().completeness, vocabulary_recall=0.928,
            vanished=("commits", "what")))

        assert "FAILED" in _gate_html([traded], before)
        assert 'class="regressed"' in _summary_table([traded], before)


class TestScoresRoundTrip:
    """A delta means nothing if the previous run comes back wrong."""

    def test_every_axis_survives_being_written_and_read(
        self, tmp_path: Path
    ) -> None:
        _write_scores(tmp_path, [a_score()], label="x", model="m", taken="now")
        restored = _previous(tmp_path / "scores.json")

        assert restored["invoice_0001"] == a_score()

    def test_nested_tuples_come_back_as_tuples(self, tmp_path: Path) -> None:
        """JSON has only lists, and `duplicated` is a tuple of triples. A
        round trip that returned lists would compare unequal and read as a
        change nobody made."""
        score = a_score(completeness=replace(
            a_score().completeness,
            duplicated=(("card heading", 1, 2),),
            lost=(("country", 1),),
            broken_joins=(("invoice", "123"),),
        ))
        _write_scores(tmp_path, [score], label="x", model="m", taken="now")
        restored = _previous(tmp_path / "scores.json")["invoice_0001"]

        assert restored.completeness.duplicated == (("card heading", 1, 2),)
        assert restored.completeness.lost == (("country", 1),)
        assert restored.completeness.broken_joins == (("invoice", "123"),)

    def test_a_missing_or_unreadable_previous_run_is_not_fatal(
        self, tmp_path: Path
    ) -> None:
        """A run that cannot find its predecessor should still produce a
        report — with no deltas, and saying so."""
        assert _previous(None) == {}
        assert _previous(tmp_path / "nothing.json") == {}

        broken = tmp_path / "broken.json"
        broken.write_text("{not json")
        assert _previous(broken) == {}

    def test_a_document_with_no_palette_round_trips_as_none(
        self, tmp_path: Path
    ) -> None:
        """T5 is skipped when the render could not be screenshotted, and the
        other five axes still have to survive the journey."""
        _write_scores(tmp_path, [a_score(palette=None)], label="x", model="m",
                      taken="now")
        restored = _previous(tmp_path / "scores.json")["invoice_0001"]

        assert restored.palette is None
        assert restored.completeness.recall == 1.0

    def test_the_file_records_which_scorer_and_which_model_produced_it(
        self, tmp_path: Path
    ) -> None:
        """A score from one session and a score from another are comparable
        only when both came from the same scorer over the same corpus, and the
        file is what says so."""
        _write_scores(tmp_path, [a_score()], label="85-x", model="qwen3-vl:4b",
                      taken="2026-09-18 06:00 UTC")
        written = json.loads((tmp_path / "scores.json").read_text())

        assert written["label"] == "85-x"
        assert written["model"] == "qwen3-vl:4b"
        assert written["taken"] == "2026-09-18 06:00 UTC"
