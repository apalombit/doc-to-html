"""Vision models via Ollama.

Local by default. Ollama Cloud is a configuration change rather than an
architectural one — same client, same prompts, same parser — but note it is a
different *host*, not a different trust boundary: images do leave the machine.

Model budget on 8GB unified memory is roughly 4GB, which puts qwen3-vl:2b,
qwen3-vl:4b and granite3.2-vision in range and rules out deepseek-ocr at 6.7GB.
Layout and audit deliberately default to different families so their blind spots
are not shared.

Nothing here reads the environment: an Engine is handed its host, key and limits
by `config`, so there is one place to look when a setting does not take effect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..config import (
    DEFAULT_EXTRACT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_S,
)
from ..ir import BBox, Reading, Zone
from ..preprocess import MODEL_INPUT_LONG_EDGE, ImageArray, resize_long_edge, to_png
from ..wire import LayoutResponse, schema_of, zones_from_layout
from .transport import OllamaTransport, Response, Transport

PROMPT_VERSION = "1"
"""Recorded on every Reading. Without it an eval regression cannot be attributed."""

LAYOUT_PROMPT = """You are looking at one page of a document.

Divide the page into top-level regions and return them as a flat list, in
reading order. Report only where each region is and what it structurally is.
Do not read the text inside any region.

For each region give:

kind — one of:
  table   a grid of rows and columns
  pairs   label and value lines, such as "Invoice No: 12"
  prose   headings, paragraphs, addresses, free text
  list    bulleted or numbered items, or a row of navigation links
  figure  a logo, chart, stamp, signature or badge

role — one of:
  header   sits at the top of the page, above the main content
  summary  a totals or overview block
  footer   small print at the foot of the page
  body     anything else

band and column — number the horizontal stripes of the page from 0 at the top.
Regions that sit side by side belong to the same band and are numbered from 0
left to right in column. A region spanning the full width is alone in its band.

left, top, right, bottom — the region's bounding box as fractions of the page
width and height, between 0 and 1.

title — a short heading printed immediately above the region and belonging to
it, such as a panel caption or a card title. Use an empty string if there is
none. Do not invent one.

graphic — for a figure only: logo, chart, signature, stamp or badge. Use an
empty string for every other kind.

Ignore decoration. A horizontal rule, a panel border or a column divider is not
a region and must not appear in the list."""


class TruncatedResponse(RuntimeError):
    """The model ran out of room and stopped mid-answer, twice.

    Not a Ladder Rung. The Ladder resolves *disagreement* between readings;
    this is a transport failure, and handling it here is what keeps retry policy
    from leaking outside the Orchestrator.
    """


@dataclass
class OllamaEngine:
    """One model, reached through the Ollama API."""

    model: str = DEFAULT_EXTRACT_MODEL
    host: str = DEFAULT_OLLAMA_HOST
    api_key: str = ""
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_s: float = DEFAULT_TIMEOUT_S
    transport: Transport | None = None
    """Injected by the suite. `None` means talk to a real Ollama."""

    name: str = "ollama"
    calls: list[str] = field(default_factory=list)
    """Which pass ran, in order. The bake-off times these; nothing branches on it."""

    def client_kwargs(self) -> dict[str, Any]:
        """What the Ollama client is constructed with.

        Separated from the client itself so the cloud path is assertable without
        a network: pointing at Ollama Cloud is a host plus a bearer token, and
        this is where that claim can be checked.
        """
        kwargs: dict[str, Any] = {"host": self.host, "timeout": self.timeout_s}
        if self.api_key:
            kwargs["headers"] = {"Authorization": f"Bearer {self.api_key}"}
        return kwargs

    def reading(self, text: str) -> Reading:
        """One account of a value, carrying what produced it.

        Engine, model and prompt version travel with every reading so a change in
        accuracy next month can be attributed to a specific change rather than
        argued about.
        """
        return Reading(
            engine=self.name,
            text=text,
            model=self.model,
            prompt_version=PROMPT_VERSION,
        )

    def ask(self, pass_name: str, prompt: str, image: ImageArray,
            schema: dict[str, Any]) -> str:
        """One constrained-decoding call, retried once if it ran out of room.

        A truncated response is a valid prefix of an incomplete array, so it is
        indistinguishable from a short answer by shape alone — hence both signals
        are used: what the transport reports, and whether the text parses at all.
        The single retry raises the token budget; a second truncation is a real
        failure and says so rather than returning a plausible fragment.
        """
        transport = self.transport or OllamaTransport(self.client_kwargs())
        page = to_png(resize_long_edge(image, MODEL_INPUT_LONG_EDGE))

        budget = self.num_ctx
        for attempt in (1, 2):
            self.calls.append(pass_name)
            reply = transport(
                model=self.model,
                prompt=prompt,
                images=[page],
                schema=schema,
                num_ctx=budget,
            )
            if not _ran_out_of_room(reply):
                return reply.content
            budget *= 2

        raise TruncatedResponse(
            f"{pass_name}: {self.model} stopped at the token limit twice, "
            f"last budget {budget // 2}. The Zone is too dense to read whole."
        )

    def detect_zones(self, image: ImageArray, hint: str | None = None) -> list[Zone]:
        """Zones with Band, column, Kind, Role and bbox — no contents.

        Runs on a downscaled page: detecting regions is a coarse task that small
        models handle well, and the resolution given away here is bought back by
        cropping each Zone from the full-resolution image for extraction.
        """
        content = self.ask(
            "layout",
            with_hint(LAYOUT_PROMPT, hint),
            image,
            schema_of(LayoutResponse),
        )
        return zones_from_layout(LayoutResponse.model_validate_json(content))

    def extract_zone(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        raise NotImplementedError("zone extraction not yet wired")

    def read_cell(self, image: ImageArray, bbox: BBox,
                  hint: str | None = None) -> Reading:
        raise NotImplementedError("cell re-read not yet wired")

    def audit_coverage(self, image: ImageArray, zones: list[Zone]) -> list[BBox]:
        raise NotImplementedError("coverage audit not yet wired")


def _ran_out_of_room(reply: Response) -> bool:
    """Whether the answer was cut short.

    Two signals because either alone is unreliable: a transport may not report
    `done_reason`, and a truncated array is still valid JSON if the cut happened
    to land after a closing brace.
    """
    if reply.truncated:
        return True
    try:
        json.loads(reply.content)
    except ValueError:
        return True
    return False


def with_hint(prompt: str, hint: str | None) -> str:
    """Append a Hint verbatim.

    Verbatim is the whole point: a Hint changes what a model is told and never
    what the code does. If anything here ever starts reading it — selecting a
    prompt, an Extractor or a template — ADR 0001 has been reversed by accident.
    """
    if not hint or not hint.strip():
        return prompt
    return f"{prompt}\n\nThe operator adds, verbatim:\n{hint.strip()}"
