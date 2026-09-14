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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from doc_to_html.config import Settings
from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.engines.transport import Response
from doc_to_html.ir import Document
from doc_to_html.orchestrator import Conversion, EngineSet, convert

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
    deterministic and matching on the prompt would make the recordings depend on
    prompt wording, which is exactly the thing a bake-off changes.

    **One queue per pass, when given a dict — issue #16.** A flat list assumes
    every call belongs to the same sequence, and it stopped being true the moment
    #15 put a classify call in front of every Zone: classification asks about
    *every* Zone while only the Zones with a wired Extractor have a recorded
    answer, so each fixture's classify calls ate the answers meant for its
    extractions. 49 tests failed on that alone, and every future pass would have
    moved the offset again.

    Keyed on `pass_name` because that is what the pipeline already tells the
    transport, and because a queue that runs dry can then name which question
    went unanswered instead of reporting an arithmetic mismatch.

    A plain list is still accepted and still served in order. Tests that script a
    specific sequence — a truncation and its retry, a layout that returns no
    Zones — are asserting on the order itself, and routing those by pass would
    hide the thing they exist to check.
    """

    replies: list[Response] | dict[str, list[Response]]
    calls: list[Call] = field(default_factory=list)

    def __call__(self, *, model: str, pass_name: str, prompt: str,
                 images: list[bytes], schema: dict[str, Any],
                 num_ctx: int) -> Response:
        self.calls.append(Call(model, pass_name, prompt, images, schema, num_ctx))
        if isinstance(self.replies, dict):
            queue = self.replies.get(pass_name)
            if not queue:
                asked = sum(1 for call in self.calls if call.pass_name == pass_name)
                raise AssertionError(
                    f"the pipeline made {asked} {pass_name} call(s) but only "
                    f"{asked - 1} {pass_name} response(s) were recorded"
                )
            return queue.pop(0)
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


def reasoning_channel(content: str, *, truncated: bool = False) -> Response:
    """The same answer, arriving where the real model actually puts it.

    Ollama routes `qwen3-vl`'s schema-constrained output to `message.thinking`
    and leaves `message.content` empty on every call. `text` models the other
    case, and modelling only that case is what let a truncation on this channel
    be misread as a thinking setting for three runs. See
    `ollama._reasoned_instead_of_answering`.
    """
    return Response(content="", truncated=truncated, thinking=content)


def recorded(fixture: str, zones: list[int] | None = None
             ) -> dict[str, list[Response]]:
    """The recorded responses for one fixture, one queue per pass.

    `zones` names which Zones are expected to reach an *Extractor*, for while
    some Kinds are not yet wired. Spelling that out in the test is the point: if
    a pass appears or disappears, `ReplayTransport` says so rather than silently
    serving one Zone's answer for another's question.

    **Classification is answered for every Zone, not only the wired ones**, which
    is the whole of issue #16. `_classify` asks about each Zone in turn regardless
    of whether its Kind has an Extractor, so a recording that skipped the
    unwired ones would put every later answer against the wrong question. The
    answers are derived from the expected IR rather than from a file, for the
    same reason `tools/record_responses.py` derives everything else that way: a
    recording taken from a model captures that model's mistakes.
    """
    from .fixtures import BUILDERS

    directory = RESPONSES / fixture
    document = BUILDERS[fixture]()
    indices = (
        range(len(list(directory.glob("zone_*.json")))) if zones is None else zones
    )

    queues: dict[str, list[Response]] = {
        "layout": [text((directory / "layout.json").read_text())],
        "classify": [
            text(json.dumps({"kind": zone.kind.value,
                             "graphic": zone.graphic_kind or ""}))
            for zone in document.zones
        ],
    }
    # **One entry per Zone that is actually asked, not per Zone.** A crop holding
    # a single band of ink is never put to the model, so `caption.json` is
    # shorter than the Zone list and `tools/record_responses.py` derives which
    # ones by measuring the same crops the Orchestrator measures. The key is
    # omitted when the file is absent, so a fixture recorded before captions
    # existed fails at the transport naming the pass rather than serving one
    # Zone's answer to another Zone's question.
    captions = directory / "caption.json"
    if captions.is_file():
        queues["caption"] = [
            text(json.dumps(answer))
            for answer in json.loads(captions.read_text())
        ]
    for index in indices:
        queues.setdefault(document.zones[index].kind.value, []).append(
            text((directory / f"zone_{index:02d}.json").read_text())
        )
    return queues


def layout_only(fixture: str) -> list[Response]:
    """Just the layout answer, as a flat list.

    A list rather than a queue map because its callers splice it — a truncated
    prefix in front of the real answer — and what they are testing is the order.
    """
    return [text((RESPONSES / fixture / "layout.json").read_text())]


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


def recorded_for(fixture: str) -> dict[str, list[Response]]:
    """Layout, classification for every Zone, extraction for the wired ones."""
    return recorded(fixture, zones=wired_zones(fixture))


def break_zone(replies: dict[str, list[Response]], fixture: str,
               zone_index: int, payload: str) -> dict[str, list[Response]]:
    """Replace one Zone's extraction answer, addressing it by Zone.

    A test that wants "Zone 5 comes back broken" should say that. With one flat
    list it had to say `wired_zones(fixture).index(5) + 1` instead — an offset
    into a sequence, which is the arithmetic that made issue #16 possible in the
    first place. Queues per pass let the Zone be named, and the position within
    its own Kind's queue is derived here rather than at each call site.
    """
    from .fixtures import BUILDERS

    kinds = [zone.kind.value for zone in BUILDERS[fixture]().zones]
    wired = wired_zones(fixture)
    kind = kinds[zone_index]
    position = sum(1 for index in wired
                   if index < zone_index and kinds[index] == kind)
    replies[kind][position] = text(payload)
    return replies


def engines_replaying(transport: ReplayTransport) -> EngineSet:
    """An EngineSet whose only difference from production is the transport."""
    settings = Settings()
    return EngineSet(
        layout=OllamaEngine.from_settings(settings, settings.layout_model, transport),
        classify=OllamaEngine.from_settings(
            settings, settings.classify_model, transport
        ),
        extract=OllamaEngine.from_settings(settings, settings.extract_model, transport),
        audit=OllamaEngine.from_settings(settings, settings.audit_model, transport),
    )


def convert_recording(
    image: Path, replies: list[Response] | dict[str, list[Response]],
    *, caption_pass: bool | None = None,
) -> tuple[Document, ReplayTransport]:
    """Convert a Source Image against recorded responses, keeping the calls.

    Here rather than in each test module because four of them were repeating the
    same three lines, and a change to how the seam is faked should be one edit.

    `caption_pass` names the pass explicitly instead of letting it follow the
    shipped default. **A test that scripts a flat list of replies needs this**:
    `ReplayTransport` serves a flat list strictly in order, so switching a pass
    on inserts a call the list does not have and every later answer lands
    against the wrong question. Tests pinning the classify-then-extract sequence
    say `caption_pass=False` and go on measuring one thing.
    """
    transport = ReplayTransport(replies)
    if caption_pass is None:
        return convert(image, engines=engines_replaying(transport)), transport

    conversion = Conversion(source=Path(image),
                            engines=engines_replaying(transport),
                            caption_pass=caption_pass)
    return conversion.run(), transport


def convert_replaying(
    image: Path, replies: list[Response] | dict[str, list[Response]]
) -> Document:
    return convert_recording(image, replies)[0]


def convert_fixture(fixture: str, root: Path) -> Document:
    """Convert a fixture's own Source Image against its own recorded responses."""
    from .fixtures import IMAGES

    return convert_replaying(root / IMAGES[fixture], recorded_for(fixture))
