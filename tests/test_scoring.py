"""The scorer, measured against faults that were established by eye.

**This module is spec 0007 Thread 0's exit gate.** The old harness scored
`sample_table_0003` a full match while that document had deleted every column
header of its only table, and scored runs 81 to 84 as a 23-to-10 improvement
while duplicated titles appeared in three of five documents. Nothing inside a
measure will tell you it has stopped seeing a class of fault, so the only test
that means anything is whether a new measure finds faults that are already known
to be there — **without being told where to look.**

So every test here asks the scorer a question it could answer for any document,
and checks the answer against what somebody saw in run 84's pictures. None of
them names a Zone index, a row number or a prompt.

`tests/frozen/run84/` is the input: five `document.html` files copied out of
`debug/runs/84-rule-not-a-line/` before that directory was cleared, which is why
these run with no model, no Ollama and no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_to_html import projection
from doc_to_html.corpus import ITERATE, SOURCES
from doc_to_html.scoring import (
    DocumentScore,
    kendall_tau,
    normalise,
    score_document,
    tokens,
)

REPO = Path(__file__).resolve().parent.parent
FROZEN = REPO / "tests" / "frozen" / "run84"

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)


@pytest.fixture(scope="module")
def scored(tmp_path_factory: pytest.TempPathFactory) -> dict[str, DocumentScore]:
    """Every frozen document, scored once and shared.

    Module-scoped because each document costs three browser launches and the
    assertions below are all about the same five results. A per-test fixture
    turned a four-second module into a ninety-second one.
    """
    work = tmp_path_factory.mktemp("render")
    return {
        name: score_document(SOURCES[name], FROZEN / f"{name}.html", work=work,
                             root=REPO)
        for name in ITERATE
    }


class TestTheScorerFindsRun84sFaultsUnaided:
    """The three faults spec 0007 was opened over, found by asking generally.

    Each test states the fault in the language of the rubric rather than in the
    language of the bug, because the scorer has to keep finding these after the
    code that caused them is gone and something else causes them again.
    """

    @needs_chrome
    def test_a_document_that_lost_a_table_header_fails_completeness(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """`sample_table_0003` scored a full match under the old harness.

        Its table's header row reads `Country | ISO | Population | GDP (USD M)
        | Currency` in the source and is absent from the output, replaced by
        the caption. The old harness compared `RowRole` sequences and never
        compared cell content, so five column names — the entire semantic key
        of the table — went missing inside a perfect score.
        """
        score = scored["sample_table_0003"]
        assert score.completeness.recall < 1.0
        assert not score.completeness.ok

        lost = {word for word, _ in score.completeness.lost}
        assert {"country", "iso", "currency"} <= lost, (
            f"the column headers should be reported missing; lost={sorted(lost)}"
        )

    @needs_chrome
    def test_the_same_document_reports_the_caption_printed_twice(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """The caption took the header row's place as well as keeping its own.

        Which makes it a precision fault as well as a recall one, and the two
        together are what say *what happened* rather than only that something
        did.
        """
        score = scored["sample_table_0003"]
        assert score.completeness.precision < 1.0
        repeated = [text for text, _, _ in score.completeness.duplicated]
        assert any("population and gdp" in text for text in repeated)

    @needs_chrome
    def test_a_zone_title_is_repeated_inside_its_own_body_in_four_documents(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """`DTH_CAPTION_PASS` sets `Zone.title` and nothing removes the Block.

        Run 81's render showed `Card heading` once and run 84's showed it
        twice, and the score improved 23 to 10 across that change because
        `Zone.title` was compared for equality and the body was never compared
        against it.

        **Four documents, where spec 0007 says three, and the scorer is
        right.** The spec counted the ones where a *heading* is visibly
        printed twice and filed `sample_table_0003` separately under the lost
        table header. But the table's caption is repeated by the same
        mechanism — lifted into `Zone.title`, left in the crop, printed again
        as the header row — so a measure asked the general question finds four.
        This is the difference between cataloguing what was noticed and
        measuring what is there, which is the whole reason for the rebuild.
        """
        affected = {
            name: score.completeness.duplicated
            for name, score in scored.items()
            if score.completeness.duplicated
        }
        assert len(affected) == 4, f"expected four documents, got {sorted(affected)}"
        assert "invoice_0001" not in affected

        repeated = [
            text for duplicated in affected.values() for text, _, _ in duplicated
        ]
        assert "card heading" in repeated
        assert "another card" in repeated
        assert "tl;dr" in repeated
        assert "payment method" in repeated

    @needs_chrome
    def test_a_paragraph_carries_hard_breaks_the_source_does_not_have(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """`Block.lines: list[Cell]` joined by `<br>` cannot reflow.

        `sample_semantic_0005`'s source prints no forced break anywhere; its
        output prints four. The surplus is what matters, not the count —
        `invoice.html` breaks six lines on purpose and an output that keeps
        them is right to.
        """
        score = scored["sample_semantic_0005"]
        assert score.completeness.source_hard_breaks == 0
        assert score.completeness.surplus_breaks > 0

        kept = scored["invoice_0001"].completeness
        assert kept.source_hard_breaks > 0
        assert kept.surplus_breaks == 0, (
            "a document whose source breaks its own lines must not be "
            "penalised for keeping them"
        )


class TestTheAxesSayWhatTheyClaimTo:
    """Each axis, checked against something visible in run 84's pictures."""

    @needs_chrome
    def test_every_inline_run_is_lost(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """T6 is a 100% loss, which is what makes it the cheapest axis to move.

        `Cell.text` is a flat string, so no link, code span or badge can
        survive the IR. Two documents carry them and neither keeps one.
        """
        for name in ("sample_css_0004", "sample_semantic_0005"):
            score = scored[name]
            assert sum(score.inline.of.values()) > 0
            assert sum(score.inline.found.values()) == 0
            assert score.inline.rate == 0.0

    @needs_chrome
    def test_the_worst_height_inflation_is_the_bootstrap_invoice(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """`invoice_0002` is half again as tall as its source at matched width.

        `render.py`'s `.band > * { flex: 1 1 12rem }` makes every column equal
        and no width exists in the IR to be wrong about, so a page of panels
        unpacks downward. This is Thread B's primary target and the single
        best diagnostic the scorer produces.
        """
        ratios = {
            name: score.layout.height_ratio for name, score in scored.items()
        }
        assert max(ratios, key=lambda name: ratios[name]) == "invoice_0002"
        assert ratios["invoice_0002"] > 1.4
        for name, ratio in ratios.items():
            assert ratio > 1.0, f"{name} is not taller than its source: {ratio}"

    @needs_chrome
    def test_side_by_side_relations_break_where_the_panels_are(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """T3 is relational, so it fires on stacking and not on a few pixels.

        The two documents with genuine multi-column bands are the two that
        lose them; the three single-column documents agree exactly, which is
        what says the measure is not just noise.
        """
        assert scored["invoice_0002"].layout.beside_agreement < 0.9
        assert scored["sample_table_0003"].layout.beside_agreement == 1.0

    @needs_chrome
    def test_an_accent_colour_present_in_the_source_is_absent_from_the_render(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """T5 is sampled from pixels, never asked of a model.

        `sample_css_0004`'s blue badge and `sample_semantic_0005`'s link colour
        are the only saturated ink in the corpus, and the render has neither.
        """
        score = scored["sample_css_0004"]
        assert score.palette is not None
        assert score.palette.source_accent is not None
        assert score.palette.accent_delta > 0.5

    @needs_chrome
    def test_a_mis_split_label_shows_up_as_a_broken_join(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """`Invoice #: 123` read as label `Invoice`, value `#: 123`.

        Every word is present, exactly once, in the right order, so recall,
        precision and tau are all perfect and the fault is invisible to them.
        The join between two adjacent words is the only thing that can see it,
        which is why T1 reports three numbers rather than two.
        """
        score = scored["invoice_0001"]
        assert score.completeness.recall == 1.0
        assert score.order.tau == 1.0
        assert score.completeness.join_recall < 1.0
        assert ("invoice", "123") in score.completeness.broken_joins


class TestTheHardTier:
    """T1, T2 and T3 gate a phase; T4, T5 and T6 do not."""

    @needs_chrome
    def test_no_document_of_run_84_passes_the_hard_tier(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        """Which is the baseline Thread 1/A starts from, stated once."""
        assert not any(score.hard_tier_ok for score in scored.values())

    @needs_chrome
    def test_completeness_is_the_axis_that_fails_most_of_them(
        self, scored: dict[str, DocumentScore]
    ) -> None:
        failing = [name for name, score in scored.items()
                   if not score.completeness.ok]
        assert len(failing) == len(ITERATE)


class TestTheNormalisationRules:
    """The small decisions the rest of the measure rests on, pinned."""

    def test_two_spellings_of_one_string_compare_equal(self) -> None:
        assert normalise("  Card   Heading\n") == normalise("card heading")

    def test_punctuation_survives_normalisation_and_leaves_the_token_stream(
        self,
    ) -> None:
        """Both halves matter, and they pull in opposite directions.

        `normalise` keeps punctuation so a duplicated *string* is still
        recognisable as the same string; `tokens` drops it so a comma read as a
        full stop is not a content loss. Collapsing them into one rule loses
        one of the two.
        """
        assert normalise("Invoice #: 123") == "invoice #: 123"
        assert tokens("Invoice #: 123") == ["invoice", "123"]

    def test_accents_are_kept_because_a_document_depends_on_them(self) -> None:
        """`nonlatin_0014` is in the corpus to be scored in its own script."""
        assert normalise("Τιμολόγιο") == "τιμολόγιο"
        assert tokens("Αθήνα 2026") == ["αθήνα", "2026"]

    def test_tau_is_one_for_the_same_sequence_and_minus_one_reversed(self) -> None:
        assert kendall_tau([(0, 0), (1, 1), (2, 2), (3, 3)]) == 1.0
        assert kendall_tau([(0, 3), (1, 2), (2, 1), (3, 0)]) == -1.0

    def test_tau_of_a_single_pair_is_one_rather_than_undefined(self) -> None:
        """A document with one block is in order, trivially. Returning 0.0 for
        it would make an empty conversion look like a scrambled one."""
        assert kendall_tau([(0, 0)]) == 1.0
        assert kendall_tau([]) == 1.0
