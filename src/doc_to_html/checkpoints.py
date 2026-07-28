"""Where the Orchestrator stops and asks a human.

Answers are structured, so the Orchestrator applies them deterministically with
nothing in between that could misunderstand them. An optional free-text note
rides along and is appended verbatim to the next pass's prompt — never parsed,
never interpreted.

Free-text feedback interpreted by an LLM is a later milestone. When it arrives,
its job is to map prose onto the structured answers defined here, which is a far
narrower and more testable task than editing the IR from prose.

Unattended runs (including the eval harness) pass NullHandler, so the same code
path serves the CLI, the library and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Question:
    """Something the Orchestrator cannot settle on its own."""

    kind: str
    """opening | convergence | arbitration"""

    text: str
    options: list[str] = field(default_factory=list)
    """Empty for an opening question, which takes free prose."""

    crop_png: bytes | None = None
    """The pixels in question, for arbitration."""

    draft_html: str | None = None
    """The Draft so far, for a convergence question."""


@dataclass
class Answer:
    """A human's response. `choice` is acted on; `note` only reaches prompts."""

    choice: str | None = None
    note: str | None = None

    @property
    def is_empty(self) -> bool:
        """True when nothing new entered the system.

        A refinement round is only worth running if something changed — the
        models are near-deterministic, so re-running identical passes over
        identical pixels reproduces the Draft already on screen.
        """
        return not self.choice and not self.note


@runtime_checkable
class CheckpointHandler(Protocol):
    def ask(self, question: Question) -> Answer: ...


class NullHandler:
    """Declines everything. The unattended and eval path."""

    def ask(self, question: Question) -> Answer:
        return Answer()


class ScriptedHandler:
    """Replays canned answers. For testing the loop without a human."""

    def __init__(self, answers: list[Answer]) -> None:
        self._answers = list(answers)
        self.asked: list[Question] = []

    def ask(self, question: Question) -> Answer:
        self.asked.append(question)
        return self._answers.pop(0) if self._answers else Answer()
