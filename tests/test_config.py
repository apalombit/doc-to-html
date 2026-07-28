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
        assert settings.layout_model == config.DEFAULT_LAYOUT_MODEL
        assert settings.extract_model == config.DEFAULT_EXTRACT_MODEL
        assert settings.audit_model == config.DEFAULT_AUDIT_MODEL
        assert settings.num_ctx == config.DEFAULT_NUM_CTX
        assert settings.timeout_s == config.DEFAULT_TIMEOUT_S
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
        dotenv.write_text("DTH_LAYOUT_MODEL=from-file\n")
        settings = load(env={"DTH_LAYOUT_MODEL": "from-env"}, dotenv_path=dotenv)
        assert settings.layout_model == "from-env"
        assert settings.origins["DTH_LAYOUT_MODEL"].source == "environment"

    def test_an_empty_string_is_not_a_value(self) -> None:
        """`DTH_NUM_CTX=` in a dotenv file means "I did not set this", not
        "the empty string", which would fail to parse as a number."""
        settings = resolve(DTH_NUM_CTX="")
        assert settings.num_ctx == config.DEFAULT_NUM_CTX


class TestNumbers:
    def test_numeric_variables_are_parsed(self) -> None:
        settings = resolve(DTH_NUM_CTX="4096", DTH_TIMEOUT_S="30")
        assert settings.num_ctx == 4096
        assert settings.timeout_s == 30.0

    def test_a_non_numeric_value_names_the_variable(self) -> None:
        with pytest.raises(config.ConfigError, match="DTH_NUM_CTX"):
            resolve(DTH_NUM_CTX="lots")


class TestReporting:
    def test_the_report_shows_where_each_value_came_from(self) -> None:
        lines = config.describe(resolve(DTH_LAYOUT_MODEL="qwen3-vl:2b"))
        assert any("DTH_LAYOUT_MODEL" in line and "qwen3-vl:2b" in line
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
        settings = resolve(
            DTH_LAYOUT_MODEL="layout-model",
            DTH_EXTRACT_MODEL="extract-model",
            DTH_AUDIT_MODEL="audit-model",
        )
        engines = default_engines(settings)
        assert isinstance(engines, EngineSet)
        assert engines.layout.model == "layout-model"
        assert engines.extract.model == "extract-model"
        assert engines.audit.model == "audit-model"

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
        engine = default_engines(resolve(DTH_NUM_CTX="2048", DTH_TIMEOUT_S="9")).layout
        assert isinstance(engine, OllamaEngine)
        assert engine.num_ctx == 2048
        assert engine.timeout_s == 9.0


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
