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

from dataclasses import dataclass
from typing import Any

from ..config import (
    DEFAULT_EXTRACT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_S,
)
from ..ir import BBox, Reading, Zone

PROMPT_VERSION = "0"
"""Recorded on every Reading. Without it an eval regression cannot be attributed."""


@dataclass
class OllamaEngine:
    """One model, reached through the Ollama API."""

    model: str = DEFAULT_EXTRACT_MODEL
    host: str = DEFAULT_OLLAMA_HOST
    api_key: str = ""
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_s: float = DEFAULT_TIMEOUT_S
    name: str = "ollama"

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

    def detect_zones(self, image: object, hint: str | None = None) -> list[Zone]:
        raise NotImplementedError("layout pass not yet wired")

    def extract_zone(self, image: object, zone: Zone, hint: str | None = None) -> Zone:
        raise NotImplementedError("zone extraction not yet wired")

    def read_cell(self, image: object, bbox: BBox, hint: str | None = None) -> Reading:
        raise NotImplementedError("cell re-read not yet wired")

    def audit_coverage(self, image: object, zones: list[Zone]) -> list[BBox]:
        raise NotImplementedError("coverage audit not yet wired")
