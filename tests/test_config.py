"""Configuration resolution — the one layer allowed to read the environment.

These tests never touch the repo's own `.env`. A suite whose expectations depend
on an untracked file passes or fails according to what the developer happens to
have on disk, which is the opposite of a regression signal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from doc_to_html import config
from doc_to_html.config import Settings, load
from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.orchestrator import EngineSet, default_engines

REPO = Path(__file__).resolve().parent.parent
NOWHERE = Path("/nonexistent/.env")


def resolve(**env: str) -> Settings:
    """Resolve settings from an explicit environment and no dotenv file."""
    return load(env=env, dotenv_path=NOWHERE)


class TestDefaults:
    def test_an_empty_environment_still_works(self) -> None:
        """Every variable has a default in code, so nothing has to be set."""
        settings = resolve()
        assert settings.ollama_host == "http://localhost:11434"
        assert settings.classify_model == config.DEFAULT_CLASSIFY_MODEL
        assert settings.extract_model == config.DEFAULT_EXTRACT_MODEL
        assert settings.audit_model == config.DEFAULT_AUDIT_MODEL
        assert settings.num_ctx == config.DEFAULT_NUM_CTX
        assert settings.timeout_s == config.DEFAULT_TIMEOUT_S
        assert settings.call_limit_s == config.DEFAULT_CALL_LIMIT_S == 180.0
        assert settings.log_level == config.DEFAULT_LOG_LEVEL
        assert settings.ollama_api_key == ""

    def test_every_variable_documented_in_env_example_is_read(self) -> None:
        """`.env.example` is the operator-facing contract. A variable documented
        there and ignored by the code is a lie in the documentation."""
        declared = set(
            re.findall(
                r"^([A-Z][A-Z0-9_]*)=", (REPO / ".env.example").read_text(), re.M
            )
        )
        assert declared, "no variables found in .env.example"
        assert declared <= set(resolve().origins)

    def test_defaults_are_reported_as_defaults(self) -> None:
        assert resolve().origins["DTH_NUM_CTX"].source == "default"


class TestPrecedence:
    def test_the_environment_overrides_a_default(self) -> None:
        settings = resolve(DTH_EXTRACT_MODEL="qwen3-vl:2b")
        assert settings.extract_model == "qwen3-vl:2b"
        assert settings.origins["DTH_EXTRACT_MODEL"].source == "environment"

    def test_a_dotenv_file_overrides_a_default(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "# a comment\n"
            "\n"
            "OLLAMA_HOST=https://ollama.com\n"
            'DTH_AUDIT_MODEL="granite3.2-vision:2b"\n'
        )
        settings = load(env={}, dotenv_path=dotenv)
        assert settings.ollama_host == "https://ollama.com"
        assert settings.audit_model == "granite3.2-vision:2b"
        assert settings.origins["OLLAMA_HOST"].source == str(dotenv)

    def test_the_environment_beats_a_dotenv_file(self, tmp_path: Path) -> None:
        """A dotenv file is a convenience for a workstation; an exported
        variable is a deliberate act for one run and must win."""
        dotenv = tmp_path / ".env"
        dotenv.write_text("DTH_EXTRACT_MODEL=from-file\n")
        settings = load(env={"DTH_EXTRACT_MODEL": "from-env"}, dotenv_path=dotenv)
        assert settings.extract_model == "from-env"
        assert settings.origins["DTH_EXTRACT_MODEL"].source == "environment"

    def test_an_empty_string_is_not_a_value(self) -> None:
        """`DTH_NUM_CTX=` in a dotenv file means "I did not set this", not
        "the empty string", which would fail to parse as a number."""
        settings = resolve(DTH_NUM_CTX="")
        assert settings.num_ctx == config.DEFAULT_NUM_CTX


class TestNumbers:
    def test_numeric_variables_are_parsed(self) -> None:
        settings = resolve(DTH_NUM_CTX="4096", DTH_TIMEOUT_S="30", DTH_CALL_LIMIT_S="0")
        assert settings.num_ctx == 4096
        assert settings.timeout_s == 30.0
        assert settings.call_limit_s == 0.0

    def test_a_non_numeric_value_names_the_variable(self) -> None:
        with pytest.raises(config.ConfigError, match="DTH_NUM_CTX"):
            resolve(DTH_NUM_CTX="lots")


class TestTheHeadingRule:
    """`DTH_HEADING_RULE` chooses between two segmentations of a page, so an
    unrecognised value has to be an error rather than a fallback: a run launched
    as one arm and silently measuring the other is the exact failure
    `debug/runs/<label>/dth_env.txt` exists to make impossible."""

    def test_it_ships_relative(self) -> None:
        assert resolve().heading_rule == config.DEFAULT_HEADING_RULE == "relative"

    def test_the_absolute_rule_is_still_reachable(self) -> None:
        """The rule it replaced stays selectable, so the pair can be measured
        against each other again without reverting a default."""
        assert resolve(DTH_HEADING_RULE="absolute").heading_rule == "absolute"

    def test_case_and_spacing_do_not_matter(self) -> None:
        assert resolve(DTH_HEADING_RULE=" Absolute ").heading_rule == "absolute"

    def test_an_unknown_rule_names_the_variable_and_the_alternatives(self) -> None:
        with pytest.raises(config.ConfigError, match="DTH_HEADING_RULE"):
            resolve(DTH_HEADING_RULE="ratio")

    def test_the_rule_reaches_the_layout_engine(self) -> None:
        """The setting is worth nothing if it stops at `Settings`."""
        from doc_to_html.orchestrator import _layout_engine

        assert _layout_engine(resolve()).heading_rule == "relative"
        assert _layout_engine(
            resolve(DTH_HEADING_RULE="absolute")).heading_rule == "absolute"


class TestPreferringAContainer:
    """Adopting a sub-threshold container over the stack of boxes it holds.
    Shipped since run 81, alongside the relative heading rule — the two tie on
    the finding count and differ in the documents, which only reading them
    showed."""

    def test_it_ships_on(self) -> None:
        assert resolve().prefer_container is config.DEFAULT_PREFER_CONTAINER is True

    def test_it_reaches_the_layout_engine(self) -> None:
        from doc_to_html.orchestrator import _layout_engine

        assert _layout_engine(resolve()).prefer_container is True
        assert _layout_engine(
            resolve(DTH_PREFER_CONTAINER="0")).prefer_container is False


class TestReadingEachZonesTitle:
    """`DTH_CAPTION_PASS`, on since run 82 — 23 findings to 12, and the only
    pass that writes `zone.title` on the shipped path."""

    def test_it_ships_on(self) -> None:
        assert resolve().caption_pass is config.DEFAULT_CAPTION_PASS is True

    def test_it_can_be_switched_off(self) -> None:
        """It costs a second call per Zone that has a body, so the way back to
        one call per Zone stays reachable."""
        assert resolve(DTH_CAPTION_PASS="0").caption_pass is False


class TestReporting:
    def test_the_report_shows_where_each_value_came_from(self) -> None:
        lines = config.describe(resolve(DTH_EXTRACT_MODEL="qwen3-vl:2b"))
        assert any("DTH_EXTRACT_MODEL" in line and "qwen3-vl:2b" in line
                   and "environment" in line for line in lines)
        assert any("DTH_AUDIT_MODEL" in line and "default" in line for line in lines)

    def test_the_api_key_is_redacted_in_the_report(self) -> None:
        """An operator asking what resolved should be able to paste the answer
        into a bug report."""
        settings = resolve(OLLAMA_API_KEY="sk-secret-value")
        assert settings.ollama_api_key == "sk-secret-value"
        assert "sk-secret-value" not in "\n".join(config.describe(settings))
        assert any("OLLAMA_API_KEY" in line for line in config.describe(settings))

    def test_an_unset_key_reads_as_unset_rather_than_redacted(self) -> None:
        report = "\n".join(config.describe(resolve()))
        assert re.search(r"OLLAMA_API_KEY\s+\(unset\)", report)


class TestEngineSet:
    def test_engines_are_built_from_resolved_configuration(self) -> None:
        """Model routing per role.

        The layout role reaches no model at all — geometry comes from a
        detector — and its model setting went with the vision layout pass in
        spec 0007's queue, Q4.
        """
        settings = resolve(
            DTH_CLASSIFY_MODEL="classify-model",
            DTH_EXTRACT_MODEL="extract-model",
            DTH_AUDIT_MODEL="audit-model",
        )

        engines = default_engines(settings)
        assert isinstance(engines, EngineSet)
        assert engines.classify.model == "classify-model"
        assert engines.extract.model == "extract-model"
        assert engines.audit.model == "audit-model"

    def test_one_model_does_classification_and_extraction(self) -> None:
        """Separable roles, one model in both of them for now.

        Not an accident of copying a default around: two vision models will not
        stay resident in 8GB, and the rival classifier has never run the layout
        pass or touched four of the five fixtures. See
        `config.DEFAULT_CLASSIFY_MODEL` for what this costs, and #19 for the
        evaluation that would change it."""
        assert config.DEFAULT_CLASSIFY_MODEL == config.DEFAULT_EXTRACT_MODEL

    def test_the_classifier_can_still_be_pointed_somewhere_else(self) -> None:
        """The point of the role existing. Sharing a default must not quietly
        become sharing a value."""
        settings = resolve(DTH_CLASSIFY_MODEL="a-classifier")
        engines = default_engines(settings)
        assert engines.classify.model == "a-classifier"
        assert engines.extract.model == config.DEFAULT_EXTRACT_MODEL

    def test_a_cloud_host_and_key_reach_the_client(self) -> None:
        """The promise is that Ollama Cloud is a configuration change. If the
        key stops at the settings object, that promise is false."""
        settings = resolve(
            OLLAMA_HOST="https://ollama.com", OLLAMA_API_KEY="sk-test"
        )
        engine = default_engines(settings).extract
        assert isinstance(engine, OllamaEngine)
        assert engine.host == "https://ollama.com"
        assert engine.api_key == "sk-test"
        assert engine.client_kwargs()["host"] == "https://ollama.com"
        assert "sk-test" in engine.client_kwargs()["headers"]["Authorization"]

    def test_no_key_sends_no_authorization_header(self) -> None:
        engine = default_engines(resolve()).extract
        assert isinstance(engine, OllamaEngine)
        assert "headers" not in engine.client_kwargs()

    def test_inference_settings_reach_the_engine(self) -> None:
        """Asked of extraction, which is where a model still is.

        Layout used to be the natural place to ask and no longer has a model
        at all: geometry comes from a detector, which makes no inference call
        and has no context window or timeout to set.
        """
        engine = default_engines(resolve(
            DTH_NUM_CTX="2048", DTH_TIMEOUT_S="9", DTH_CALL_LIMIT_S="60",
        )).extract
        assert isinstance(engine, OllamaEngine)
        assert engine.num_ctx == 2048
        assert engine.timeout_s == 9.0
        assert engine.call_limit_s == 60.0


class TestNothingElseReadsTheEnvironment:
    def test_environment_access_is_confined_to_the_config_layer(self) -> None:
        """Two places that read the environment is two places to look when a
        setting does not take effect."""
        offenders = [
            path.relative_to(REPO)
            for path in (REPO / "src").rglob("*.py")
            if path.name != "config.py"
            and re.search(r"os\.environ|os\.getenv|getenv\(", path.read_text())
        ]
        assert offenders == []


class TestTheAuditModelIsAPlaceholder:
    """`DTH_AUDIT_MODEL` names the same model as extraction, which is precisely
    the arrangement the Coverage Audit is documented as worthless under.

    Safe only because nothing calls it. These two tests are the tripwire: the
    first records the debt, the second fails the moment the debt comes due.
    """

    def test_the_audit_shares_the_extraction_model_for_now(self) -> None:
        assert config.DEFAULT_AUDIT_MODEL == config.DEFAULT_EXTRACT_MODEL

    def test_the_coverage_audit_is_still_unwired(self) -> None:
        """**When this fails, read `config.DEFAULT_AUDIT_MODEL` before fixing it.**

        Implementing `audit_coverage` is what makes the model above start
        mattering. An auditor sharing the layout model's blind spot cannot see
        what that blind spot missed, so it would pass every document and report
        confidence it has not earned — on the one check that catches *absent*
        content, where a false pass is the whole failure mode. Point
        `DTH_AUDIT_MODEL` at a second family as part of that work; do not simply
        delete this test.
        """
        import numpy as np

        from doc_to_html.engines.ollama import OllamaEngine

        with pytest.raises(NotImplementedError):
            OllamaEngine(model="test-model").audit_coverage(
                np.zeros((10, 10, 3), dtype=np.uint8), []
            )


class TestCli:
    def test_the_config_command_prints_what_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from doc_to_html.cli import main

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("DTH_EXTRACT_MODEL=from-dotenv\n")
        monkeypatch.setenv("OLLAMA_API_KEY", "sk-should-not-appear")

        assert main(["config"]) == 0
        out = capsys.readouterr().out
        assert "from-dotenv" in out
        assert ".env" in out
        assert "sk-should-not-appear" not in out
