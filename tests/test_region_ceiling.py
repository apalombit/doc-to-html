"""Telling the layout pass how many regions the page holds, at most.

`LAYOUT_PROMPT` already forbids reporting a panel's inner rows as regions of
their own, in as many words, and `qwen3-vl:4b` returns 72 regions for
`invoice_0002`'s 10 anyway — the third instruction this model has been measured
ignoring, after the two about splitting a table row. So the page is measured and
the number is stated, which is the one lever that has worked on this model.

Two properties carry the whole design and each has a test here: the ruler
overcounts, so the prompt must state a **ceiling** rather than a count; and the
flag off must mean the prompt is untouched, because `invoice_0001` at zero
mismatches is what this must not move.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from doc_to_html.config import DEFAULT_LAYOUT_REGION_HINT, load
from doc_to_html.engines.ollama import LAYOUT_PROMPT, with_regions
from doc_to_html.ir import BBox, Document, Kind, Role, Source, Zone
from doc_to_html.orchestrator import Conversion, EngineSet
from doc_to_html.preprocess import REGION_GAP, Rectified, count_regions, rectify
from doc_to_html.trace import Disposition, Stage
from doc_to_html.wire import MappingError

REPO = Path(__file__).resolve().parent.parent


class TestTheRulerOnRealPages:
    """The two fixtures `REGION_GAP` is calibrated against.

    Characterization, deliberately: these numbers are the entire basis for
    stating a bound rather than a count, and the functions behind them were
    moved out of `tools/cv_layout_probe.py` where nothing in the suite ran them.
    If the promotion ever changes behaviour, it changes here first.
    """

    def test_it_overcounts_the_flat_page(self) -> None:
        """`invoice_0001` has 6 regions and measures 8.

        The overcount is the point. 6 is comfortably under the bound, so a page
        the model already reads correctly feels no pressure to split — which is
        what makes this safe to switch on.
        """
        assert count_regions(rectify(REPO / "example" / "invoice.png").image) == 8

    def test_it_overcounts_the_nested_page_too(self) -> None:
        """`invoice_0002` has 10 regions and measures 11.

        Nearly exact, and far below the 72 the model returns unprompted. This is
        the number that has to bind.
        """
        assert count_regions(rectify(REPO / "example" / "invoice2.png").image) == 11

    def test_a_wider_gap_welds_the_nested_page_into_one(self) -> None:
        """Why `REGION_GAP` is not tuned to whichever fixture is in front of you.

        At 0.08 `invoice_0001` measures a correct 6 — and `invoice_0002`
        collapses to a single region, which as a ceiling would be catastrophic.
        The joint value is the only honest one, and this is the trap it avoids.
        """
        page = rectify(REPO / "example" / "invoice2.png").image
        assert count_regions(page, gap=0.08) == 1
        assert count_regions(page, gap=REGION_GAP) == 11


class TestWhatThePromptSays:
    def test_the_number_is_stated_as_a_bound_and_not_as_a_target(self) -> None:
        """The distinction the whole design rests on.

        `with_grid` says "Return exactly N rows" because its ruler is exact on
        the tables it was measured against. This ruler is not — 8 against a true
        6 — so the same wording would ask the model to invent two regions on the
        one document that currently converts perfectly.
        """
        asked = with_regions(LAYOUT_PROMPT, 8)
        assert "no more than 8" in asked
        assert "exactly 8" not in asked

    def test_something_in_it_pushes_the_count_down(self) -> None:
        """Run 55 is why this test exists.

        The first wording said only "it holds at most N" and "do not return more
        than N" — every imperative in it pointing one way, and all of them
        satisfied by returning exactly N. Both fixtures then returned exactly
        their ceiling: 8 for `invoice_0001`'s true 6, 11 for `invoice_0002`'s
        true 10, splitting real regions to get there. `invoice_0001` went from
        zero mismatches to a `MappingError`.

        So the bound needs a counterweight — a sentence saying that under is
        right — or it reads as a target. Asserting the *presence* of downward
        pressure rather than the exact words, since the wording will be retuned
        and the property is what must survive.
        """
        asked = with_regions(LAYOUT_PROMPT, 8)
        assert "not a quantity to produce" in asked
        assert "returning fewer is the usual and correct answer" in asked
        assert "Never split a region in order to reach the number" in asked

    def test_it_names_the_confusion_it_is_correcting(self) -> None:
        """A bound alone says how many but not which, and the model's error is
        which: it reports a panel's rows as regions. The count binds and the
        sentence beside it says where to spend the budget."""
        assert "count the panel, not its rows" in with_regions(LAYOUT_PROMPT, 11)

    def test_the_original_prompt_survives_intact(self) -> None:
        """Appended, never rewritten — the Kind and Band definitions below it are
        what four runs of prompt work paid for."""
        assert with_regions(LAYOUT_PROMPT, 8).startswith(LAYOUT_PROMPT)


class OneAnswer:
    """A layout Engine returning a set number of Zones, recording each ceiling.

    `raises` makes the first call fail, which is the other way into the retry.
    """

    def __init__(self, zones: int = 1, raises: Exception | None = None) -> None:
        self.zones = zones
        self.raises = raises
        self.ceilings: list[int | None] = []

    def detect_zones(self, image: np.ndarray, hint: str | None = None,
                     region_ceiling: int | None = None) -> list[Zone]:
        self.ceilings.append(region_ceiling)
        if self.raises is not None and len(self.ceilings) == 1:
            raise self.raises
        return [Zone(kind=Kind.PROSE, role=Role.BODY, band=0, column=index,
                     bbox=BBox(0.05, 0.35, 0.9, 0.55))
                for index in range(self.zones)]


def source() -> Source:
    return Source(path="unused.png", sha256="0" * 64, width=800, height=600)


def page() -> Rectified:
    """A page with one block of ink, so the ruler has something to measure."""
    image = np.full((600, 800, 3), 245, dtype=np.uint8)
    image[200:340, 50:600] = 20
    return Rectified(image=image, source=source())


def run(engine: OneAnswer, *, hint: bool) -> Conversion:
    engines = EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                        extract=engine, audit=engine)
    return Conversion(source=Path("unused.png"), engines=engines,
                      snap_zones=False, layout_region_hint=hint)


class TestTheHintIsARescueAndNotAPolicy:
    """Runs 55 and 56 are why this class exists.

    Both stated the ceiling on the *first* call, and both cost `invoice_0001` its
    zero-mismatch Conversion: the model read the bound as a target, split real
    regions to reach it, and returned quantised boxes where the unhinted call had
    returned measured ones. Asked only after an answer has already failed, it
    cannot do that — which protects the baseline by construction rather than by
    an argument about wording, twice proved wrong.
    """

    def test_the_first_call_never_carries_a_ceiling(self) -> None:
        """Even with the flag on. A document whose layout is fine must be asked
        exactly what it was asked before this existed."""
        engine = OneAnswer(zones=1)
        run(engine, hint=True)._layout(page(), Document(source=source()))
        assert engine.ceilings == [None], "the first ask must be unhinted"

    def test_an_answer_within_the_measurement_is_taken_as_it_is(self) -> None:
        engine = OneAnswer(zones=1)
        run(engine, hint=True)._layout(page(), Document(source=source()))
        assert len(engine.ceilings) == 1, "no reason to ask twice"

    def test_an_answer_over_the_measurement_is_asked_again_with_it(self) -> None:
        """`invoice_0002` in miniature: 72 regions on a page that measures 11."""
        measured = count_regions(page().image)
        engine = OneAnswer(zones=measured + 5)
        run(engine, hint=True)._layout(page(), Document(source=source()))
        assert engine.ceilings == [None, measured]

    def test_a_layout_that_failed_outright_is_asked_again_too(self) -> None:
        """The other way in. A `MappingError` means the answer described no page,
        and a stated count is the one lever measured to change that."""
        engine = OneAnswer(zones=1, raises=MappingError("describes no page"))
        run(engine, hint=True)._layout(page(), Document(source=source()))
        assert engine.ceilings == [None, count_regions(page().image)]

    def test_with_the_flag_off_a_failure_is_still_a_failure(self) -> None:
        """Off must not quietly acquire a retry. The exception is the caller's,
        unchanged."""
        engine = OneAnswer(zones=1, raises=MappingError("describes no page"))
        with pytest.raises(MappingError, match="describes no page"):
            run(engine, hint=False)._layout(page(), Document(source=source()))

    def test_off_sends_no_ceiling_at_all(self) -> None:
        """Off must mean the Engine is asked exactly what it was asked before.

        `None` rather than a large number: the Engine leaves the prompt untouched
        for `None`, so this is what guarantees a run with the flag unset is
        byte-identical to one from before this change existed.
        """
        engine = OneAnswer(zones=1)
        run(engine, hint=False)._layout(page(), Document(source=source()))
        assert engine.ceilings == [None]

    def test_the_default_is_off(self) -> None:
        """A default is a claim about every document, and this is measured on
        two. `DTH_TABLE_GRID_HINT` shipped off and was flipped only after a run
        passed a gate written before it."""
        assert DEFAULT_LAYOUT_REGION_HINT is False
        assert load(env={}).layout_region_hint is False

    def test_the_environment_turns_it_on(self) -> None:
        assert load(env={"DTH_LAYOUT_REGION_HINT": "1"}).layout_region_hint is True


class TestTheRunSaysWhatItMeasured:
    """A number that reached the model and appears nowhere in the run directory
    is a number nobody can check the answer against."""

    def test_the_measurement_is_recorded_with_its_gap(self) -> None:
        conversion = run(OneAnswer(zones=1), hint=True)
        conversion._layout(page(), Document(source=source()))

        event = next(e for e in conversion.trace.events
                     if e.step == "measure_regions")
        assert event.stage is Stage.LAYOUT
        assert event.disposition is Disposition.ACCEPTED
        assert event.data["regions"] == count_regions(page().image)
        assert event.data["gap"] == REGION_GAP

    def test_a_rejected_layout_and_its_retry_are_both_recorded(self) -> None:
        """Two calls where one was expected is exactly the kind of thing a
        reader has to be able to see, along with why the first was thrown away."""
        measured = count_regions(page().image)
        conversion = run(OneAnswer(zones=measured + 5), hint=True)
        conversion._layout(page(), Document(source=source()))

        first = next(e for e in conversion.trace.events
                     if e.step == "detect_zones")
        assert first.disposition is Disposition.REJECTED
        assert f"more than the {measured}" in first.data["reason"]

        again = next(e for e in conversion.trace.events
                     if e.step == "detect_zones_with_ceiling")
        assert again.disposition is Disposition.ACCEPTED
        assert again.data["ceiling"] == measured

    def test_being_switched_off_is_itself_recorded(self) -> None:
        """A gap in the timeline reads as a step that was forgotten rather than
        one that was declined — so "never measured" and "measured, and this is
        the number" stay distinguishable."""
        conversion = run(OneAnswer(), hint=False)
        conversion._layout(page(), Document(source=source()))

        event = next(e for e in conversion.trace.events
                     if e.step == "measure_regions")
        assert event.disposition is Disposition.SKIPPED
        assert "DTH_LAYOUT_REGION_HINT is off" in event.data["reason"]
