"""The only layer that reads the environment.

Every model, host, key and timeout a Conversion uses resolves here, so changing
which model does extraction is an edit to `.env` rather than to Python. That is
what makes a bake-off across models a configuration exercise, and what makes
Ollama Cloud reachable without touching code.

Two properties are load-bearing:

*Everything has a default in code.* An empty environment produces a working
configuration, so the suite and a fresh clone behave identically.

*Every resolved value remembers where it came from.* An operator asking why a
run used the wrong model should not have to read source to find out — see
`describe()` and the `config` CLI command.

Nothing outside this module reads an environment variable. Two places that do is
two places to look when a setting does not take effect.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, TypeVar

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_LAYOUT_MODEL = "qwen3-vl:4b"
DEFAULT_EXTRACT_MODEL = "qwen3-vl:4b"
DEFAULT_AUDIT_MODEL = "qwen3-vl:4b"
"""A placeholder, and the one default that is knowingly wrong for its job.

Nothing loads this today: `_audit` is a no-op, `OllamaEngine.audit_coverage`
raises, and no code path reaches either. So the value names a model that is
never sent anywhere, and pointing it at the model already on disk keeps
`doc-to-html config` describing a machine that exists — an 8GB box has no room
for a second vision family it never calls.

**It must be re-pointed before the Coverage Audit is built.** The audit is the
only safeguard that catches *absent* content, and it is worth something only
from a different model family: asking the model that missed a block whether it
missed a block shares the blind spot that caused the miss. Left at this value it
would self-audit, pass, and report confidence it has not earned — worse than not
running, because a silent no-op is at least honest about being one.

`test_the_coverage_audit_is_still_unwired` fails the moment the audit is
implemented, which is the moment this needs deciding rather than inheriting."""

DEFAULT_CLASSIFY_MODEL = "qwen3-vl:4b"
"""The same model as layout and extraction, deliberately, for now.

**What this default costs, stated plainly.** Issue #13 asked two models the Kind
question about `invoice_0001`'s Zone 4 — a shaded heading row over a data row —
three times each at two resolutions. `qwen3-vl:4b` answered `pairs` six times
out of six, including at the full-resolution crop where the shading is plainly
legible. `qwen3.5:4b` answered `pairs` at layout scale and `table` at the crop.
So with this default, splitting the pass fixes Zone 1, whose problem is being
asked about as one of seven regions rather than on its own, and leaves Zone 4
wrong. Two mismatches becomes one, not zero.

**Why take that anyway.** `qwen3.5:4b` has never run the layout pass, never been
measured on the other four fixtures, and never converted a document end to end;
naming two Kinds correctly in a standalone probe is not evidence it can do the
job. Shipping it as a default on that basis would be generalising from one
measurement on one fixture, which is the mistake 0001 records twice. One model
in every role also costs one model load per document rather than two, since two
vision models will not stay resident in 8GB together.

What #15 actually bought is that this is a *setting*: `DTH_CLASSIFY_MODEL` picks
the classifier independently of the layout and extraction models, so evaluating
models per step — and combinations across steps — is configuration rather than
code. That evaluation is issue #19."""
DEFAULT_LAYOUT_LONG_EDGE = 512
DEFAULT_NUM_CTX = 8192
DEFAULT_TIMEOUT_S = 180.0
DEFAULT_LOG_LEVEL = "INFO"

DEFAULT_LENIENT_DECODING = False
"""Whether to repair a response that ignored the schema it was given.

Off, because every local Ollama model honours `format` and a repair path that is
never exercised is a place for bugs to hide. On, it is the only way to reach a
cloud vision model: none of them honour `format`. See `engines/lenient.py`."""

DOTENV = Path(".env")
"""Looked for in the working directory. Absent is the normal case, not an error."""

ENVIRONMENT = "environment"
DEFAULT = "default"


class ConfigError(ValueError):
    """A value was set but could not be used. Always names the variable."""


@dataclass(frozen=True)
class Setting:
    """One resolved value and its provenance."""

    name: str
    value: str
    source: str
    """`environment`, `default`, or the path of the dotenv file it came from."""

    secret: bool = False

    @property
    def shown(self) -> str:
        """The value as it is safe to print."""
        if not self.value:
            return "(unset)"
        return "(set, redacted)" if self.secret else self.value


@dataclass(frozen=True)
class Settings:
    """Everything resolved, plus where each value came from."""

    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_api_key: str = ""
    layout_model: str = DEFAULT_LAYOUT_MODEL
    classify_model: str = DEFAULT_CLASSIFY_MODEL
    extract_model: str = DEFAULT_EXTRACT_MODEL
    audit_model: str = DEFAULT_AUDIT_MODEL
    layout_long_edge: int = DEFAULT_LAYOUT_LONG_EDGE
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_s: float = DEFAULT_TIMEOUT_S
    log_level: str = DEFAULT_LOG_LEVEL
    lenient_decoding: bool = DEFAULT_LENIENT_DECODING

    origins: dict[str, Setting] = field(default_factory=dict)
    """Variable name -> what resolved and from where. Declaration order."""


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse `KEY=value` lines. Missing file yields nothing.

    Deliberately not python-dotenv: this is the whole of the format the project
    documents, and a dependency for it would be larger than the parser.
    """
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, raw = line.partition("=")
        values[name.strip()] = raw.strip().strip("'\"")
    return values


T = TypeVar("T", int, float)


def _number(setting: Setting, cast: Callable[[str], T]) -> T:
    """Parse a numeric setting, naming the variable and its source if it will not.

    Generic in the target type so callers do not re-cast what was just cast —
    `int(_number(s, int))` reads as though the parse were untrustworthy.
    """
    try:
        return cast(setting.value)
    except ValueError as error:
        raise ConfigError(
            f"{setting.name}={setting.value!r} from {setting.source} "
            f"is not a {getattr(cast, '__name__', cast)}"
        ) from error


def _flag(setting: Setting) -> bool:
    """Parse a boolean setting, accepting what people actually type.

    Named values only: an unrecognised string is a mistake worth reporting rather
    than quietly falling back to false, which is how a run silently ignores the
    thing it was configured to do.
    """
    value = setting.value.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off", ""):
        return False
    raise ConfigError(
        f"{setting.name}={setting.value!r} from {setting.source} is not a boolean"
    )


def load(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | None = None,
) -> Settings:
    """Resolve settings. Environment wins, then the dotenv file, then the default.

    A dotenv file records what a workstation usually wants; an exported variable
    is a deliberate act for one run, so it takes precedence.

    An empty string counts as unset. `DTH_NUM_CTX=` in a dotenv file reads as
    "I left this alone", not as a value that then fails to parse.
    """
    environ = os.environ if env is None else env
    dotenv = DOTENV if dotenv_path is None else dotenv_path
    from_file = read_dotenv(dotenv)

    def resolve(name: str, default: object, *, secret: bool = False) -> Setting:
        if environ.get(name):
            return Setting(name, environ[name], ENVIRONMENT, secret)
        if from_file.get(name):
            return Setting(name, from_file[name], str(dotenv), secret)
        return Setting(name, str(default), DEFAULT, secret)

    origins = {
        setting.name: setting
        for setting in (
            resolve("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
            resolve("OLLAMA_API_KEY", "", secret=True),
            resolve("DTH_LAYOUT_MODEL", DEFAULT_LAYOUT_MODEL),
            resolve("DTH_CLASSIFY_MODEL", DEFAULT_CLASSIFY_MODEL),
            resolve("DTH_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL),
            resolve("DTH_AUDIT_MODEL", DEFAULT_AUDIT_MODEL),
            resolve("DTH_LAYOUT_LONG_EDGE", DEFAULT_LAYOUT_LONG_EDGE),
            resolve("DTH_NUM_CTX", DEFAULT_NUM_CTX),
            resolve("DTH_TIMEOUT_S", DEFAULT_TIMEOUT_S),
            resolve("DTH_LOG_LEVEL", DEFAULT_LOG_LEVEL),
            resolve("DTH_LENIENT_DECODING", DEFAULT_LENIENT_DECODING),
        )
    }

    return Settings(
        ollama_host=origins["OLLAMA_HOST"].value,
        ollama_api_key=origins["OLLAMA_API_KEY"].value,
        layout_model=origins["DTH_LAYOUT_MODEL"].value,
        classify_model=origins["DTH_CLASSIFY_MODEL"].value,
        extract_model=origins["DTH_EXTRACT_MODEL"].value,
        audit_model=origins["DTH_AUDIT_MODEL"].value,
        layout_long_edge=_number(origins["DTH_LAYOUT_LONG_EDGE"], int),
        num_ctx=_number(origins["DTH_NUM_CTX"], int),
        timeout_s=_number(origins["DTH_TIMEOUT_S"], float),
        log_level=origins["DTH_LOG_LEVEL"].value,
        lenient_decoding=_flag(origins["DTH_LENIENT_DECODING"]),
        origins=origins,
    )


def configure_logging(settings: Settings) -> None:
    """Apply DTH_LOG_LEVEL.

    Resolved since the configuration layer was built and read by nothing until a
    180-second vision pass produced no output at all and no way to tell a slow
    model from a dead one. INFO gets one line per pass, plus a heartbeat while one
    is in flight.
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def describe(settings: Settings) -> list[str]:
    """One aligned line per variable: name, value, where it came from."""
    width = max(len(name) for name in settings.origins)
    return [
        f"{setting.name:<{width}}  {setting.shown:<28}  {setting.source}"
        for setting in settings.origins.values()
    ]
