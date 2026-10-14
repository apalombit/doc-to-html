"""The bake-off's own machinery, exercised without a model.

The bake-off itself is opt-in and takes minutes. Its *logic* is here, driven by the
same recorded responses everything else uses, so a formatting mistake or an
off-by-one in the timing is caught in a millisecond rather than after ten minutes
of real model calls.

What is deliberately not tested here is anything about a model. That is the whole
point of the script existing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_to_html.bakeoff import (
    CANDIDATES,
    Attempt,
    PassTiming,
    TimingTransport,
    engines_for,
    load_corpus,
    main,
    report,
    run,
)
from doc_to_html.config import Settings
from doc_to_html.engines.transport import Response, Transport
from doc_to_html.trace import Call, Trace

from .replay import ReplayTransport, break_zone, recorded_for

REPO = Path(__file__).resolve().parent.parent

REPLAYING = Settings(layout_detector="stub")
"""Settings for a replayed run, with geometry from a stub rather than a model.

The vision layout path is gone — spec 0007 Thread 0 retired it — so there is no
longer a configuration under which a recorded `layout` response is asked for.
Geometry now always comes from a detector, and a detector needs a 171MB ONNX
file this suite must not require, so `stub_detector` below stands in for one
and serves each document's recorded boxes.

The real detector has its own tests, against its own fake, in
`test_layout_detector.py`. The stub here exists so the *bake-off* can be
exercised end to end offline; it is not a second detector."""


@pytest.fixture(autouse=True)
def stub_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve each document's recorded Zone boxes in place of the ONNX detector.

    Patched at `orchestrator.from_name`, which is the single place both the
    Conversion path and the bake-off path now reach a detector through — so a
    stub here cannot accidentally cover only one of them, which is the whole
    point of `TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion` below.
    """
    from doc_to_html.engines import detector as detector_module
    from doc_to_html.ir import Zone

    from .documents import SAMPLE_DOCUMENTS

    def zones_of(fixture: str) -> list[Zone]:
        return [
            Zone(kind=zone.kind, role=zone.role, band=zone.band,
                 column=zone.column, bbox=zone.bbox)
            for zone in SAMPLE_DOCUMENTS[fixture]().zones
            if zone.bbox is not None
        ]

    from PIL import Image as PILImage

    from doc_to_html.corpus import SOURCES

    by_shape = {
        PILImage.open(SOURCES[name].png_path(REPO)).size[::-1]: name
        for name in SAMPLE_DOCUMENTS
    }

    class StubDetector:
        """Geometry without a 171MB download. Not a second detector.

        Which document it has been handed is decided by the image's shape,
        because `detect_zones` is given pixels and nothing else. Returning one
        document's Zones for every page would put the recorded answers against
        the wrong questions: the queues are keyed per pass, so a page that
        detects six Zones where nine were recorded leaves three unread.
        """

        name = "detector:stub"
        model = "stub"
        confidence = 0.0
        heading_rule = "absolute"
        prefer_container = False

        def detect_zones(self, image: object, hint: object = None) -> list[Zone]:
            shape = getattr(image, "shape", (0, 0))[:2]
            return zones_of(by_shape[shape])

    def stub_from_name(name: str, confidence: float | None = None,
                       **kwargs: object) -> StubDetector:
        return StubDetector()

    monkeypatch.setattr(detector_module, "from_name", stub_from_name)


def replaying(model: str, fixture: str) -> Transport:
    """A transport that answers correctly for whichever document is being read."""
    return ReplayTransport(recorded_for(fixture))


def failing(model: str, fixture: str) -> Transport:
    """A model that falls over on the first thing it is asked.

    It used to be an empty `{"zones": []}` layout answer, which made the
    Conversion raise "no Zones". There is no layout call any more — geometry
    comes from a detector — so falling over has to be expressed as the
    transport itself refusing, which is also what an unreachable Ollama
    actually looks like.
    """
    def refuse(**_: object) -> Response:
        raise RuntimeError("model is not loaded")

    return refuse  # type: ignore[return-value]


SIZES = {"model-a": 3300.0, "model-b": 1900.0}


def sized(model: str) -> float | None:
    """Stands in for asking Ollama what it has loaded.

    Injected rather than left to the real probe so the suite makes no network
    call — `test_the_ollama_package_is_never_imported` is what keeps that honest.
    """
    return SIZES.get(model)


@pytest.fixture
def corpus() -> dict[str, object]:
    from doc_to_html.corpus import ITERATE

    return load_corpus(REPO, ITERATE)  # type: ignore[return-value]


class TestTheCorpusLoadsFromDisk:
    def test_the_iterate_split_is_five_documents_with_their_images(
        self, corpus: dict[str, object]
    ) -> None:
        """A name and a picture, and nothing else.

        There used to be an expected `Document` beside each one and a
        comparison at the end. `doc_to_html.corpus` now says what the corpus
        is and `doc_to_html.scoring` says how it is judged.
        """
        assert len(corpus) == 5
        for image in corpus.values():
            assert image.is_file()  # type: ignore[attr-defined]

    def test_the_whole_sweep_is_twenty_one(self) -> None:
        from doc_to_html.corpus import NEW, SWEEP

        assert len(load_corpus(REPO, SWEEP)) == 21
        assert set(NEW) <= set(SWEEP) and len(NEW) == 6

    def test_a_root_with_no_images_says_which_document_is_missing(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(SystemExit, match="invoice_0001"):
            load_corpus(tmp_path, ["invoice_0001"])


class TestWhatARunProduces:
    def test_every_model_meets_every_document(
        self, corpus: dict[str, object]
    ) -> None:
        attempts = run(
            ["model-a", "model-b"], corpus, REPLAYING,  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        assert len(attempts) == 10
        assert [a.model for a in attempts[:5]] == ["model-a"] * 5

    def test_models_are_batched_rather_than_alternated(
        self, corpus: dict[str, object]
    ) -> None:
        """Two vision models cannot stay resident in 8 GB, so alternating costs a
        reload each time — and that reload would be timed as if it belonged to the
        document."""
        attempts = run(
            ["model-a", "model-b"], corpus, REPLAYING,  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        order = [a.model for a in attempts]
        assert order == sorted(order, key=["model-a", "model-b"].index)

    def test_every_document_converts_without_the_run_falling_over(
        self, corpus: dict[str, object]
    ) -> None:
        """The bake-off's whole job now: convert, time, and write it out.

        It used to assert five matches, which was a claim about
        `acceptance.compare()`. There is no verdict here any more — quality is
        `scoring.score_document()`'s answer and it appears in `report.html` —
        so what is left to pin is that every document reaches the end.
        """
        attempts = run(
            ["model-a"], corpus, REPLAYING,  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        assert len(attempts) == 5
        assert all(a.error is None for a in attempts)
        assert all(a.html for a in attempts)

    def test_each_pass_is_timed_and_named(
        self, corpus: dict[str, object]
    ) -> None:
        attempts = run(
            ["model-a"], corpus, REPLAYING,  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        invoice = next(a for a in attempts if a.fixture == "invoice_0001")
        # Geometry once, then every Zone read for its Title and classified, then
        # every Zone extracted. Zone 0 is a single band of ink, so the ink
        # refuses to ask about it and there are five captions against six
        # classifications — the asymmetry is the guard in `preprocess`
        # doing its job, and a flat `["caption"] * 6` would assert it away.
        # No `layout` call any more: geometry comes from a detector, which
        # makes no model call at all. That is the whole of what spec 0007
        # Thread 0's deletion of the vision layout path changes here.
        # `runs` follows each `prose` Zone and nothing else: the inline pass
        # asks `prose` and `list` only, so the figure, the pairs and both
        # tables are never asked. See `config.DEFAULT_INLINE_PASS`.
        assert [t.pass_name for t in invoice.timings] == [
            "classify",
            *["caption", "classify"] * 5,
            "figure", "pairs", "prose", "runs", "prose", "runs",
            "table", "table",
        ]
        assert all(t.seconds >= 0 for t in invoice.timings)
        assert invoice.seconds == pytest.approx(
            sum(t.seconds for t in invoice.timings)
        )

    def test_a_caveat_does_not_count_against_the_model(
        self, corpus: dict[str, object]
    ) -> None:
        """A table read at reduced resolution is this project's limitation — slice
        stitching is not built — and charging the model for it would make a model
        look worse for a document nobody could read whole."""
        from doc_to_html.ir import Caveat

        import doc_to_html.orchestrator as orchestrator

        real = orchestrator.resolution_caveat
        try:
            orchestrator.resolution_caveat = lambda image, zone: "read at reduced resolution: test"  # type: ignore[assignment]
            attempts = run(
                ["model-a"], {"invoice_0001": corpus["invoice_0001"]},  # type: ignore[arg-type,dict-item]
                REPLAYING, transport_for=replaying, resident_for=sized,
            )
        finally:
            orchestrator.resolution_caveat = real  # type: ignore[assignment]

        assert attempts[0].verdict == "converted"
        assert attempts[0].caveats
        assert Caveat  # the concept exists in the IR, distinct from Failure

    def test_a_zone_that_could_not_be_read_is_named_in_the_run(
        self, corpus: dict[str, object]
    ) -> None:
        """A Zone left as a skeleton is a fact about the run, not a score.

        It is reported so a reader knows the output is incomplete before they
        judge it — `report.html` would otherwise show a page with a hole in it
        and no explanation of where the hole came from.
        """
        def one_bad_zone(model: str, fixture: str) -> Transport:
            replies = break_zone(recorded_for(fixture), fixture, 4,
                                 '{"rows": []}')
            return ReplayTransport(replies)

        attempts = run(
            ["model-a"], {"invoice_0001": corpus["invoice_0001"]},  # type: ignore[arg-type,dict-item]
            REPLAYING, transport_for=one_bad_zone, resident_for=sized,
        )
        assert attempts[0].failures
        assert "zone 4" in attempts[0].failures[0]

    def test_one_model_falling_over_does_not_end_the_run(
        self, corpus: dict[str, object]
    ) -> None:
        """Ten minutes of measurement thrown away because the last document
        errored would be a bad trade."""
        attempts = run(
            ["broken"], corpus, REPLAYING,  # type: ignore[arg-type]
            transport_for=failing, resident_for=sized,
        )
        assert len(attempts) == 5
        # Every Zone unread rather than the Conversion dying: the Orchestrator
        # catches a refused extraction per Zone and records a Failure, so a
        # model that is simply not there produces five complete Attempts, each
        # one saying exactly how much of its document went unread.
        assert all("unread" in a.verdict for a in attempts)
        assert all(a.failures for a in attempts)


class TestTiming:
    def test_a_pass_is_timed_even_when_it_raises(self) -> None:
        """A model that times out is exactly the measurement worth keeping."""
        def explode(**kwargs: object) -> Response:
            raise RuntimeError("timed out")

        timing = TimingTransport(inner=explode)  # type: ignore[arg-type]
        with pytest.raises(RuntimeError):
            timing(model="m", pass_name="table", prompt="p", images=[],
                   schema={}, num_ctx=1)
        assert [t.pass_name for t in timing.timings] == ["table"]

    def test_prose_and_list_are_timed_apart(self) -> None:
        """They share one wire schema, so reading the schema's title reports both
        as "Blocks" and averages two different jobs together."""
        timing = TimingTransport(
            inner=lambda **kwargs: Response(content="{}", truncated=False)  # type: ignore[arg-type]
        )
        for name in ("prose", "list"):
            timing(model="m", pass_name=name, prompt="p", images=[],
                   schema={"title": "BlocksResponse"}, num_ctx=1)
        assert [t.pass_name for t in timing.timings] == ["prose", "list"]


class TestEachCallRecordsWhatItAsked:
    """Spec 0012 §4b. A replay serves answers by pass and order, so it needs
    a record of what each answer was the answer *to*."""

    @staticmethod
    def asked(prompt: str = "p", images: list[bytes] | None = None,
              schema: dict[str, object] | None = None) -> dict[str, str]:
        trace = Trace()
        timing = TimingTransport(
            inner=lambda **kwargs: Response(content="{}", truncated=False),  # type: ignore[arg-type]
            trace=trace)
        timing(model="m", pass_name="table", prompt=prompt,
               images=[b"crop"] if images is None else images,
               schema={"title": "T"} if schema is None else schema, num_ctx=1)
        return trace.calls[0].asked

    def test_the_same_question_hashes_the_same(self) -> None:
        assert self.asked() == self.asked()
        assert set(self.asked()) == {"prompt", "picture", "schema"}

    def test_each_part_moves_only_its_own_hash(self) -> None:
        base = self.asked()
        for changed, part in ((self.asked(prompt="8 rows"), "prompt"),
                              (self.asked(images=[b"other crop"]), "picture"),
                              (self.asked(schema={"title": "U"}), "schema")):
            assert [k for k in base if base[k] != changed[k]] == [part]

    def test_a_trace_written_before_the_hash_still_reads(self) -> None:
        old = '{"calls": [{"pass_name": "table", "model": "m", "prompt": "p"}]}'
        assert Trace.from_json(old).calls[0].asked == {}


class TestTheReplaySaysWhenACallWasAskedDifferently:
    """`tools/replay_run.asked_differently`, paired the way answers are served."""

    @staticmethod
    def replay_tool() -> object:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "replay_run", REPO / "tools" / "replay_run.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_a_call_asked_alike_is_not_named(self) -> None:
        asked = {"prompt": "a", "picture": "b", "schema": "c"}
        run = [{"pass_name": "table", "asked": asked}]
        today = [Call(pass_name="table", model="m", prompt="p", asked=asked)]
        assert self.replay_tool().asked_differently(run, today) == ([], 0)  # type: ignore[attr-defined]

    def test_the_moved_call_is_named_by_the_runs_numbering(self) -> None:
        """Pass by pass, so a classify call in between does not shift which
        table answer is compared with which table question."""
        one = {"prompt": "a", "picture": "b", "schema": "c"}
        run = [{"pass_name": "table", "asked": one},
               {"pass_name": "classify", "asked": one},
               {"pass_name": "table", "asked": one}]
        today = [Call(pass_name="classify", model="m", prompt="", asked=one),
                 Call(pass_name="table", model="m", prompt="", asked=one),
                 Call(pass_name="table", model="m", prompt="",
                      asked={**one, "prompt": "8 rows", "picture": "x"})]
        moved, unhashed = self.replay_tool().asked_differently(run, today)  # type: ignore[attr-defined]
        assert moved == ["02_table prompt+picture"] and unhashed == 0

    def test_an_answer_frozen_with_no_hash_is_counted_not_passed(self) -> None:
        run = [{"pass_name": "table"}]
        today = [Call(pass_name="table", model="m", prompt="",
                      asked={"prompt": "a", "picture": "b", "schema": "c"})]
        assert self.replay_tool().asked_differently(run, today) == ([], 1)  # type: ignore[attr-defined]

    def test_a_call_more_than_the_run_is_counted_by_its_pass(self) -> None:
        """Spec 0014, step 2: a pass that swallows its own error leaves no
        Failure when its queue runs dry, so the calls are counted."""
        run = [{"pass_name": "prose"}, {"pass_name": "table"}]
        today = [Call(pass_name="prose", model="m", prompt=""),
                 Call(pass_name="table", model="m", prompt=""),
                 Call(pass_name="prose", model="m", prompt="")]
        assert self.replay_tool().asked_more(run, today) == {"prose": 1}  # type: ignore[attr-defined]
        assert self.replay_tool().asked_more(run, today[:2]) == {}  # type: ignore[attr-defined]


class TestTheReportIsSomethingToActOn:
    def attempts(self) -> list[Attempt]:
        return [
            Attempt(
                fixture="invoice_0001", model="qwen3-vl:4b",
                timings=[PassTiming("layout", 12.0), PassTiming("table", 31.0)],
                resident_mb=3300.0,
            ),
            Attempt(
                fixture="invoice_0001", model="qwen3-vl:2b",
                timings=[PassTiming("layout", 5.0), PassTiming("table", 9.0)],
                failures=["zone 4 (table): MappingError: no rows"],
                resident_mb=1900.0,
            ),
        ]

    def test_it_shows_latency_per_pass_as_well_as_per_document(self) -> None:
        """"Reports per-pass latency" means in the table a human reads, not only
        behind --json."""
        text = report(self.attempts())
        assert "Per pass" in text
        assert "layout" in text and "table" in text

    def test_it_shows_latency_per_document_and_per_model(self) -> None:
        text = report(self.attempts())
        assert "Per document" in text and "Per model" in text
        assert "43.0" in text  # the 4B model's total on this document
        assert "table 31.0s" in text  # its slowest pass, named

    def test_it_shows_resident_memory_because_the_ceiling_is_8gb(self) -> None:
        text = report(self.attempts())
        assert "resident MB" in text
        assert "3300" in text and "1900" in text

    def test_it_says_what_did_not_convert_and_where(self) -> None:
        text = report(self.attempts())
        assert "What did not convert" in text
        assert "zone 4 (table): MappingError: no rows" in text

    def test_a_clean_sweep_omits_the_details_section(self) -> None:
        clean = [a for a in self.attempts() if not a.failures]
        assert "What did not convert" not in report(clean)

    def test_unknown_resident_memory_is_labelled_not_blank(self) -> None:
        text = report([Attempt(fixture="f", model="m",
                               timings=[PassTiming("layout", 1.0)])])
        assert "unknown" in text

    def test_an_empty_run_says_so_rather_than_printing_a_bare_table(self) -> None:
        assert report([]) == "no attempts"


class TestTheCommandLine:
    def test_an_unknown_fixture_is_refused_before_any_model_runs(self) -> None:
        """Discovering a typo after loading a 3 GB model is a poor trade."""
        with pytest.raises(SystemExit, match="unknown document"):
            main(["--fixtures", "invoice_0003", "--root", str(REPO)])

    def test_the_configured_models_are_measured_too(self) -> None:
        """"Runs each configured vision model" — a configuration naming a model
        the candidates omit must still get measured."""
        from doc_to_html.bakeoff import models_to_measure

        settings = Settings(extract_model="house-model",
                            audit_model="granite3.2-vision:latest")
        models = models_to_measure(settings)
        assert models[0] == "house-model"
        assert set(CANDIDATES) <= set(models)
        assert len(models) == len(set(models))

    def test_the_candidates_cover_the_open_questions(self) -> None:
        """Both extraction candidates and the audit model, which is measured as a
        reader because the Coverage Audit does not exist — its resident size is the
        number that decides whether it can share 8 GB."""
        assert "qwen3-vl:4b" in CANDIDATES
        assert "qwen3-vl:2b" in CANDIDATES
        assert any("granite" in model for model in CANDIDATES)


class TestTheBakeOffBuildsTheSameLayoutEngineAsAConversion:
    """`tools/iterate.sh` runs the bake-off, so this is the path every measured
    run takes — and it assembles its own `EngineSet` rather than calling
    `orchestrator._layout_engine`.

    **This is not hypothetical.** `DTH_HEADING_RULE` was added, reached
    `Settings`, was recorded into the run directory's `dth_env.txt`, and never
    reached the detector, because `engines_for` passed `from_name` the two
    arguments it knew about. The run announced itself as the arm it was not and
    came back byte-identical to its baseline — which reads as a change that does
    nothing rather than a change that did not run, and is the most expensive kind
    of wrong answer this project can produce.
    """

    @staticmethod
    def _both(settings: Settings) -> tuple[object, object]:
        from doc_to_html.orchestrator import _layout_engine

        transport = ReplayTransport(recorded_for("invoice_0001"))
        return (engines_for("qwen3-vl:4b", settings, transport).layout,
                _layout_engine(settings))

    @pytest.mark.parametrize("settings", [
        Settings(layout_detector="stub"),
        Settings(layout_detector="stub", heading_rule="relative"),
        Settings(layout_detector="stub", detector_confidence=0.25),
    ])
    def test_every_detector_setting_reaches_both_paths(
        self, settings: Settings
    ) -> None:
        mine, theirs = self._both(settings)

        for field in ("confidence", "heading_rule", "model"):
            assert getattr(mine, field) == getattr(theirs, field), field

    def test_a_new_detector_setting_cannot_be_forwarded_by_only_one_path(
        self,
    ) -> None:
        """The general form, so the next setting is covered before it is added.

        Compares every public attribute of the two engines rather than a list
        somebody has to remember to extend — which is exactly what failed.
        """
        mine, theirs = self._both(
            Settings(layout_detector="stub", heading_rule="relative"))

        assert {name: value for name, value in vars(mine).items()
                if not name.startswith("_")} == {
            name: value for name, value in vars(theirs).items()
            if not name.startswith("_")}


class TestASettingThatBypassesTheEngineSetStillReachesTheBakeOff:
    """`DTH_CAPTION_PASS` arrives by a **different route** from the detector
    settings above, and that is the reason to pin it separately.

    `bakeoff` builds `Conversion(source=, engines=, trace=)` and never mentions
    `caption_pass`; the value arrives because the field's default factory calls
    `config.load()` itself. So the two paths agree today by coincidence of
    reading the same environment, not because anything forwards it — and the
    failure mode is identical to `DTH_HEADING_RULE`'s: a run that announces
    itself as an arm, records the variable in `dth_env.txt`, and measures the
    other arm. The moment any caller passes `caption_pass=` explicitly, this
    test is what says the bake-off was left behind.
    """

    @staticmethod
    def _captions_asked(settings: Settings,
                        corpus: dict[str, object]) -> int:
        """Caption calls made by a real `bakeoff.run`, not by a copy of it.

        Asserted on the calls rather than on an attribute, because the question
        is whether the pass *ran* — which is the thing a byte-identical arm
        cannot tell you.
        """
        seen: list[ReplayTransport] = []

        def counting(model: str, fixture: str) -> Transport:
            replies = recorded_for(fixture)
            replies["caption"] = [
                Response(content='{"first_line": "x", "line_is": "content"}',
                         truncated=False)
                for _ in range(40)
            ]
            transport = ReplayTransport(replies)
            seen.append(transport)
            return transport

        run(["model-a"], {"invoice_0001": corpus["invoice_0001"]},
            settings, transport_for=counting, resident_for=sized)
        return sum(1 for t in seen for c in t.calls if c.pass_name == "caption")

    def test_the_flag_reaches_the_conversion_the_bakeoff_runs(
        self, corpus: dict[str, object]
    ) -> None:
        asked = self._captions_asked(
            Settings(layout_detector="stub", caption_pass=True), corpus)

        assert asked > 0

    def test_and_switching_it_off_reaches_it_too(
        self, corpus: dict[str, object]
    ) -> None:
        """The other direction, so a rule that always asks cannot pass this."""
        asked = self._captions_asked(
            Settings(layout_detector="stub", caption_pass=False), corpus)

        assert asked == 0


class TestItIsNotPartOfTheDefaultSuite:
    def test_pytest_only_collects_the_tests_directory(self) -> None:
        """Otherwise the bake-off would run on every `pytest` invocation and need a
        model installed to do it."""
        import tomllib

        config = tomllib.loads((REPO / "pyproject.toml").read_text())
        assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]

    def test_the_bakeoff_module_is_not_named_like_a_test(self) -> None:
        assert not Path("src/doc_to_html/bakeoff.py").name.startswith("test_")
