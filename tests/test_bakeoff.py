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

from doc_to_html.acceptance import Mismatch
from doc_to_html.bakeoff import (
    CANDIDATES,
    Attempt,
    PassTiming,
    TimingTransport,
    load_acceptance_set,
    main,
    report,
    run,
)
from doc_to_html.config import Settings
from doc_to_html.engines.transport import Response, Transport

from .replay import ReplayTransport, break_zone, recorded_for

REPO = Path(__file__).resolve().parent.parent


def replaying(model: str, fixture: str) -> Transport:
    """A transport that answers correctly for whichever document is being read."""
    return ReplayTransport(recorded_for(fixture))


def failing(model: str, fixture: str) -> Transport:
    return ReplayTransport([Response(content='{"zones": []}', truncated=False)])


SIZES = {"model-a": 3300.0, "model-b": 1900.0}


def sized(model: str) -> float | None:
    """Stands in for asking Ollama what it has loaded.

    Injected rather than left to the real probe so the suite makes no network
    call — `test_the_ollama_package_is_never_imported` is what keeps that honest.
    """
    return SIZES.get(model)


@pytest.fixture
def acceptance() -> dict[str, object]:
    return load_acceptance_set(REPO)  # type: ignore[return-value]


class TestTheAcceptanceSetLoadsFromDisk:
    def test_all_five_documents_are_found_with_their_images(
        self, acceptance: dict[str, object]
    ) -> None:
        """Read from the committed JSON rather than the Python builders, so nothing
        in the package imports the test suite."""
        assert len(acceptance) == 5
        for image, expected in acceptance.values():  # type: ignore[misc]
            assert image.is_file()
            assert expected.zones

    def test_a_root_with_no_fixtures_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="no expected IR"):
            load_acceptance_set(tmp_path)


class TestWhatARunProduces:
    def test_every_model_meets_every_document(
        self, acceptance: dict[str, object]
    ) -> None:
        attempts = run(
            ["model-a", "model-b"], acceptance, Settings(),  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        assert len(attempts) == 10
        assert [a.model for a in attempts[:5]] == ["model-a"] * 5

    def test_models_are_batched_rather_than_alternated(
        self, acceptance: dict[str, object]
    ) -> None:
        """Two vision models cannot stay resident in 8 GB, so alternating costs a
        reload each time — and that reload would be timed as if it belonged to the
        document."""
        attempts = run(
            ["model-a", "model-b"], acceptance, Settings(),  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        order = [a.model for a in attempts]
        assert order == sorted(order, key=["model-a", "model-b"].index)

    def test_a_correct_reading_matches_the_expected_structure(
        self, acceptance: dict[str, object]
    ) -> None:
        attempts = run(
            ["model-a"], acceptance, Settings(),  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        assert [a.verdict for a in attempts] == ["match"] * 5
        assert all(a.error is None for a in attempts)

    def test_each_pass_is_timed_and_named(
        self, acceptance: dict[str, object]
    ) -> None:
        attempts = run(
            ["model-a"], acceptance, Settings(),  # type: ignore[arg-type]
            transport_for=replaying, resident_for=sized,
        )
        invoice = next(a for a in attempts if a.fixture == "invoice_0001")
        assert [t.pass_name for t in invoice.timings] == [
            "layout",
            *["classify"] * 6,
            "figure", "pairs", "prose", "prose", "table", "table",
        ]
        assert all(t.seconds >= 0 for t in invoice.timings)
        assert invoice.seconds == pytest.approx(
            sum(t.seconds for t in invoice.timings)
        )

    def test_a_caveat_does_not_count_against_the_model(
        self, acceptance: dict[str, object]
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
                ["model-a"], {"invoice_0001": acceptance["invoice_0001"]},  # type: ignore[arg-type,dict-item]
                Settings(), transport_for=replaying, resident_for=sized,
            )
        finally:
            orchestrator.resolution_caveat = real  # type: ignore[assignment]

        assert attempts[0].verdict == "match"
        assert attempts[0].caveats
        assert Caveat  # the concept exists in the IR, distinct from Failure

    def test_a_failed_extraction_counts_against_the_model(
        self, acceptance: dict[str, object]
    ) -> None:
        """A Zone left as a skeleton is not a match, however well the rest read."""
        def one_bad_zone(model: str, fixture: str) -> Transport:
            replies = break_zone(recorded_for(fixture), fixture, 4,
                                 '{"rows": []}')
            return ReplayTransport(replies)

        attempts = run(
            ["model-a"], {"invoice_0001": acceptance["invoice_0001"]},  # type: ignore[arg-type,dict-item]
            Settings(), transport_for=one_bad_zone, resident_for=sized,
        )
        assert attempts[0].verdict != "match"
        assert any(m.field == "extraction" for m in attempts[0].mismatches)

    def test_one_model_falling_over_does_not_end_the_run(
        self, acceptance: dict[str, object]
    ) -> None:
        """Ten minutes of measurement thrown away because the last document
        errored would be a bad trade."""
        attempts = run(
            ["broken"], acceptance, Settings(),  # type: ignore[arg-type]
            transport_for=failing, resident_for=sized,
        )
        assert len(attempts) == 5
        assert all(a.verdict == "error" for a in attempts)
        assert all("no Zones" in (a.error or "") for a in attempts)


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
                mismatches=[Mismatch("zone 4", "kind", "table", "pairs")],
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

    def test_it_says_what_did_not_match_and_where(self) -> None:
        text = report(self.attempts())
        assert "What did not match" in text
        assert "zone 4: kind expected table, got pairs" in text

    def test_a_clean_sweep_omits_the_details_section(self) -> None:
        clean = [a for a in self.attempts() if not a.mismatches]
        assert "What did not match" not in report(clean)

    def test_unknown_resident_memory_is_labelled_not_blank(self) -> None:
        text = report([Attempt(fixture="f", model="m",
                               timings=[PassTiming("layout", 1.0)])])
        assert "unknown" in text

    def test_an_empty_run_says_so_rather_than_printing_a_bare_table(self) -> None:
        assert report([]) == "no attempts"


class TestTheCommandLine:
    def test_an_unknown_fixture_is_refused_before_any_model_runs(self) -> None:
        """Discovering a typo after loading a 3 GB model is a poor trade."""
        with pytest.raises(SystemExit, match="unknown fixture"):
            main(["--fixtures", "invoice_0003", "--root", str(REPO)])

    def test_the_configured_models_are_measured_too(self) -> None:
        """"Runs each configured vision model" — a configuration naming a model
        the candidates omit must still get measured."""
        from doc_to_html.bakeoff import models_to_measure

        settings = Settings(layout_model="house-model", extract_model="house-model",
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


class TestItIsNotPartOfTheDefaultSuite:
    def test_pytest_only_collects_the_tests_directory(self) -> None:
        """Otherwise the bake-off would run on every `pytest` invocation and need a
        model installed to do it."""
        import tomllib

        config = tomllib.loads((REPO / "pyproject.toml").read_text())
        assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]

    def test_the_bakeoff_module_is_not_named_like_a_test(self) -> None:
        assert not Path("src/doc_to_html/bakeoff.py").name.startswith("test_")
