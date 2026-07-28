"""Replaying recorded model responses — the suite's only fake.

Seam 1 is `convert()`, faked at the Ollama transport and nowhere else. A test
runs the real rectification, the real Engine, the real Extractors, the real
assembly and the real renderer; only the call to a model is replaced. That is
what makes the response parser exercised by the same tests that exercise the
pipeline, rather than verified separately and hoped about.

The recorded responses live in `tests/responses/` and are derived from the
hand-authored expected IR by `tools/record_responses.py`. See that file for what
replaying them does and does not prove.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from doc_to_html.engines.transport import Response

RESPONSES = Path(__file__).resolve().parent / "responses"


@dataclass
class Call:
    """One request the pipeline made, kept so a test can assert on it."""

    model: str
    prompt: str
    images: list[bytes]
    schema: dict[str, Any]
    num_ctx: int


@dataclass
class ReplayTransport:
    """Serves recorded responses in the order the pipeline asks for them.

    Order rather than content-matching, because the pipeline's call sequence is
    deterministic — layout once, then each Zone in order — and matching on the
    prompt would make the recordings depend on prompt wording, which is exactly
    the thing a bake-off changes.
    """

    replies: list[Response]
    calls: list[Call] = field(default_factory=list)

    def __call__(self, *, model: str, prompt: str, images: list[bytes],
                 schema: dict[str, Any], num_ctx: int) -> Response:
        self.calls.append(Call(model, prompt, images, schema, num_ctx))
        if not self.replies:
            raise AssertionError(
                f"the pipeline made {len(self.calls)} calls but only "
                f"{len(self.calls) - 1} responses were recorded"
            )
        return self.replies.pop(0)

    @property
    def last(self) -> Call:
        return self.calls[-1]


def text(content: str, *, truncated: bool = False) -> Response:
    return Response(content=content, truncated=truncated)


def recorded(fixture: str, zones: list[int] | None = None) -> list[Response]:
    """The recorded responses for one fixture, in pipeline order.

    `zones` names which Zones are expected to reach a model, for while some
    Kinds are not yet wired. Spelling that out in the test is the point: if a
    pass appears or disappears, `ReplayTransport` says so rather than silently
    serving one Zone's answer for another's question.
    """
    directory = RESPONSES / fixture
    indices = (
        range(len(list(directory.glob("zone_*.json")))) if zones is None else zones
    )
    paths = [directory / "layout.json"] + [
        directory / f"zone_{index:02d}.json" for index in indices
    ]
    return [text(path.read_text()) for path in paths]


def layout_only(fixture: str) -> list[Response]:
    return recorded(fixture, zones=[])
