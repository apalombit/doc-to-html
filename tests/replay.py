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

from doc_to_html.config import Settings
from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.engines.transport import Response
from doc_to_html.ir import Document
from doc_to_html.orchestrator import EngineSet, convert

RESPONSES = Path(__file__).resolve().parent / "responses"


@dataclass
class Call:
    """One request the pipeline made, kept so a test can assert on it."""

    model: str
    pass_name: str
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

    def __call__(self, *, model: str, pass_name: str, prompt: str,
                 images: list[bytes], schema: dict[str, Any],
                 num_ctx: int) -> Response:
        self.calls.append(Call(model, pass_name, prompt, images, schema, num_ctx))
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


def wired_zones(fixture: str) -> list[int]:
    """The Zones of a fixture whose Kind has an Extractor wired.

    Derived rather than written down, because a Kind gaining an Extractor changes
    which Zones reach a model and every test that replays this document would
    otherwise need editing to keep its responses in step.
    """
    from doc_to_html.wire import EXTRACTION_SCHEMAS

    from .fixtures import BUILDERS

    return [
        index
        for index, zone in enumerate(BUILDERS[fixture]().zones)
        if zone.kind in EXTRACTION_SCHEMAS
    ]


def recorded_for(fixture: str) -> list[Response]:
    """Layout, plus a response for every Zone that will actually be asked about."""
    return recorded(fixture, zones=wired_zones(fixture))


def engines_replaying(transport: ReplayTransport) -> EngineSet:
    """An EngineSet whose only difference from production is the transport."""
    settings = Settings()
    return EngineSet(
        layout=OllamaEngine.from_settings(settings, settings.layout_model, transport),
        extract=OllamaEngine.from_settings(settings, settings.extract_model, transport),
        audit=OllamaEngine.from_settings(settings, settings.audit_model, transport),
    )


def convert_recording(image: Path,
                      replies: list[Response]) -> tuple[Document, ReplayTransport]:
    """Convert a Source Image against recorded responses, keeping the calls.

    Here rather than in each test module because four of them were repeating the
    same three lines, and a change to how the seam is faked should be one edit.
    """
    transport = ReplayTransport(replies)
    return convert(image, engines=engines_replaying(transport)), transport


def convert_replaying(image: Path, replies: list[Response]) -> Document:
    return convert_recording(image, replies)[0]


def convert_fixture(fixture: str, root: Path) -> Document:
    """Convert a fixture's own Source Image against its own recorded responses."""
    from .fixtures import IMAGES

    return convert_replaying(root / IMAGES[fixture], recorded_for(fixture))
