"""The record a run keeps of itself.

Two properties carry everything else here. The Trace is **append-only and never
read back**, so a wrong Event cannot change a Document — that is what makes it
safe to put diagnostic code in the Orchestrator at all. And every Event has a
`disposition`, so no step can be recorded without saying what became of its
input, which is the gap the whole module exists to close: three separate
investigations in this project ended at "the model answered correctly and the
content vanished", each one a disposition nobody had written down.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from doc_to_html.ir import BBox, Document, Kind, Reading, Role, Source, Zone
from doc_to_html.orchestrator import Conversion, EngineSet
from doc_to_html.preprocess import Rectified
from doc_to_html.trace import (
    TRACE_VERSION,
    Call,
    Change,
    Disposition,
    Stage,
    Trace,
)
from doc_to_html.wire import contents_into

HEIGHT, WIDTH = 600, 800


def source() -> Source:
    return Source(path="unused.png", sha256="0" * 64, width=WIDTH, height=HEIGHT)


def page() -> np.ndarray:
    sheet = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)
    sheet[240:280, 100:500] = 20
    return sheet


def rectified() -> Rectified:
    return Rectified(image=page(), source=source())


def one_zone(kind: Kind = Kind.PAIRS) -> list[Zone]:
    return [Zone(kind=kind, role=Role.BODY, band=0, column=0,
                 bbox=BBox(0.1, 0.35, 0.7, 0.5))]


class Answers:
    """An Engine answering through the real mappers, so `wire` decides outcomes."""

    def __init__(self, **replies: str) -> None:
        self.replies = {Kind(kind): text for kind, text in replies.items()}
        self.asked: list[Kind] = []

    def extract_zone(self, image: object, zone: Zone,
                     hint: str | None = None) -> Zone:
        self.asked.append(zone.kind)
        return contents_into(zone, self.replies[zone.kind],
                             read=lambda t: Reading(engine="test", text=t))

    def classify_zone(self, image: object, zone: Zone,
                      hint: str | None = None) -> Zone:
        self.asked.append(zone.kind)
        return replace(zone, kind=Kind(self.replies["classify_as"]))  # type: ignore[index]


def conversion(engine: object, **kwargs: object) -> Conversion:
    return Conversion(
        source=Path("unused.png"),
        engines=EngineSet(layout=engine, classify=engine,  # type: ignore[arg-type]
                          extract=engine, audit=engine),
        **kwargs,  # type: ignore[arg-type]
    )


class TestTheShapeOfTheRecord:
    def test_a_step_cannot_be_recorded_without_saying_what_became_of_it(self) -> None:
        """`disposition` is positional and required, by design.

        An Event that cannot say what was done with its input is the thing this
        module exists to prevent, so the type should not permit constructing one.
        """
        with pytest.raises(TypeError):
            Trace().record(Stage.EXTRACT, "extract")  # type: ignore[call-arg]

    def test_sequence_numbers_come_from_the_trace_and_not_the_caller(self) -> None:
        """So a step added somewhere new cannot be filed out of order."""
        trace = Trace()
        for step in ("a", "b", "c"):
            trace.record(Stage.EXTRACT, step, Disposition.ACCEPTED)
        assert [event.seq for event in trace.events] == [0, 1, 2]

    def test_a_round_trip_through_json_changes_nothing(self) -> None:
        """The tool reads this back with the same code that wrote it, so a
        reader and a writer cannot drift into disagreeing about the shape."""
        trace = Trace()
        trace.record_call(Call(pass_name="table", model="m", prompt="p",
                               answer="{}", thinking="hm", truncated=True))
        trace.record(Stage.EXTRACT, "extract", Disposition.REPAIRED,
                     zone_index=2, call=0, seconds=1.5,
                     changed=[Change(path="zones[2].kind", before="pairs",
                                     after="prose")],
                     rows=5)

        assert Trace.from_json(trace.to_json()).to_json() == trace.to_json()

    def test_it_carries_a_version_so_an_old_run_is_recognised(self) -> None:
        assert Trace().version == TRACE_VERSION


class TestFindingTheCallAStepMade:
    """`calls_since`, and why a step cannot just assume it made one call."""

    def test_a_step_that_asked_nothing_points_at_no_call(self) -> None:
        """Not at call zero. The calls are recorded by the harness's transport,
        so a plain `convert()` leaves `calls` empty while the events are complete
        — and an Event naming a call that does not exist is worse than one
        admitting it has none."""
        trace = Trace()
        assert trace.calls_since(trace.next_call) == (None, 0)

    def test_a_retried_pass_reports_both_of_its_calls(self) -> None:
        """A truncated answer is retried at a doubled budget. Reported as two so
        the sheet can explain a Zone that cost two calls, rather than leaving a
        gap in the numbering for a reader to trip over."""
        trace = Trace()
        mark = trace.next_call
        trace.record_call(Call(pass_name="table", model="m", prompt="p"))
        trace.record_call(Call(pass_name="table", model="m", prompt="p"))

        assert trace.calls_since(mark) == (0, 2)


class TestTheOrchestratorRecordsWhatItDid:
    def test_the_snap_records_the_boxes_it_moved(self) -> None:
        engine = Answers(prose='{"blocks": [{"kind": "body", "lines": ["x"]}]}')
        run = conversion(engine, snap_zones=True)
        run.trace.record  # the Conversion owns it; nothing else writes here
        document = Document(source=source())

        class Layout:
            def detect_zones(self, image: object, hint: object) -> list[Zone]:
                return [Zone(kind=Kind.PROSE, role=Role.BODY, band=0, column=0,
                             bbox=BBox(0.05, 0.35, 0.9, 0.55))]

        run.engines = EngineSet(layout=Layout(), classify=engine,  # type: ignore[arg-type]
                                extract=engine, audit=engine)
        run._layout(rectified(), document)

        snap = next(e for e in run.trace.events if e.stage is Stage.SNAP)
        assert snap.disposition is Disposition.OVERRIDDEN
        assert snap.changed, "a box that moved must be recorded as a change"
        assert snap.data["before"] != snap.data["after"]

    def test_the_snap_being_off_is_itself_recorded(self) -> None:
        """A stage that did nothing still gets an entry. A gap in the timeline
        reads as a step that was forgotten, not one that was declined."""
        engine = Answers()
        run = conversion(engine, snap_zones=False)
        document = Document(source=source())

        class Layout:
            def detect_zones(self, image: object, hint: object) -> list[Zone]:
                return one_zone(Kind.PROSE)

        run.engines = EngineSet(layout=Layout(), classify=engine,  # type: ignore[arg-type]
                                extract=engine, audit=engine)
        run._layout(rectified(), document)

        snap = next(e for e in run.trace.events if e.stage is Stage.SNAP)
        assert snap.disposition is Disposition.SKIPPED
        assert snap.data["enabled"] is False

    def test_a_rejected_extraction_records_the_rule_that_rejected_it(self) -> None:
        """The message is the finding. A Zone that renders as a skeleton with
        "MappingError" and no rule is exactly the dead end this closes."""
        engine = Answers(table='{"rows": [{"role": "header", "cells": ["a", "b"]},'
                               ' {"role": "data", "cells": ["1"]}]}')
        run = conversion(engine)
        run.classification_ran = True
        document = Document(source=source())
        document.zones = one_zone(Kind.TABLE)

        run._extract(rectified(), document)

        event = next(e for e in run.trace.events if e.step == "extract")
        assert event.disposition is Disposition.REJECTED
        assert "header has 2" in event.data["error"]
        assert event.data["crop"]["width"] > 0, "which pixels it was given"

    def test_the_reroute_reads_as_two_steps_in_sequence(self) -> None:
        """Cause and effect, in the order they happened. One merged entry would
        hide that a second call was made and what provoked it."""
        engine = Answers(
            pairs='{"pairs": [{"label": "Acme", "value": "John"},'
                  ' {"label": "", "value": "a@b.c"}]}',
            prose='{"blocks": [{"kind": "address", "lines": ["Acme", "John",'
                  ' "a@b.c"]}]}',
        )
        run = conversion(engine)
        run.classification_ran = True
        document = Document(source=source())
        document.zones = one_zone(Kind.PAIRS)

        run._extract(rectified(), document)

        steps = [e.step for e in run.trace.events if e.stage is Stage.EXTRACT]
        assert steps == ["extract", "reroute"]

        first, second = run.trace.events[0], run.trace.events[1]
        assert first.disposition is Disposition.REROUTED
        assert "not Pairs" in first.data["error"]
        assert second.changed[0].before == "pairs"
        assert second.changed[0].after == "prose"
        assert second.data["lines"] == 3

    def test_a_blank_crop_is_recorded_with_the_threshold_it_failed(self) -> None:
        """"Skipped" without the number is an assertion; with it, a reader can
        tell a blank Zone from a threshold set too high."""
        engine = Answers()
        engine.replies["classify_as"] = "prose"  # type: ignore[index]
        run = conversion(engine)
        document = Document(source=source())
        document.zones = [Zone(kind=Kind.PROSE, role=Role.BODY, band=0, column=0,
                               bbox=BBox(0.05, 0.02, 0.4, 0.12))]

        run._classify(rectified(), document)

        empty = next(e for e in run.trace.events if e.step == "empty_zone")
        assert empty.disposition is Disposition.SKIPPED
        assert empty.data["ink_fraction"] == 0.0
        assert empty.data["threshold"] > 0


class TestTheTraceCannotSteerAConversion:
    def test_the_document_is_identical_with_the_trace_discarded(self) -> None:
        """The property that makes diagnostic code in the Orchestrator safe.

        Nothing reads the Trace back, so a Conversion whose Trace is thrown away
        at every step produces the same Document as one that keeps it.
        """
        def convert(trace: Trace) -> str:
            engine = Answers(table='{"rows": [{"role": "header", "cells": ["a", "b"]},'
                                   ' {"role": "data", "cells": ["1", "2"]}]}')
            run = conversion(engine, trace=trace)
            run.classification_ran = True
            document = Document(source=source())
            document.zones = one_zone(Kind.TABLE)
            run._extract(rectified(), document)
            return document.to_json()

        class Amnesiac(Trace):
            """Forgets every Event the instant it is recorded."""

            def record(self, *args: object, **kwargs: object):  # type: ignore[override]
                event = super().record(*args, **kwargs)  # type: ignore[arg-type]
                self.events.clear()
                return event

        assert convert(Trace()) == convert(Amnesiac())
