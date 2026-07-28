"""Vision models via Ollama.

Local by default. Ollama Cloud is a configuration change rather than an
architectural one — same client, same prompts, same parser — but note it is a
different *host*, not a different trust boundary: images do leave the machine.

Model budget on 8GB unified memory is roughly 4GB, which puts qwen3-vl:2b,
qwen3-vl:4b and granite3.2-vision in range and rules out deepseek-ocr at 6.7GB.
Layout and audit deliberately default to different families so their blind spots
are not shared.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir import BBox, Reading, Zone

DEFAULT_LAYOUT_MODEL = "qwen3-vl:4b"
DEFAULT_EXTRACT_MODEL = "qwen3-vl:4b"
DEFAULT_AUDIT_MODEL = "granite3.2-vision:latest"

PROMPT_VERSION = "0"
"""Recorded on every Reading. Without it an eval regression cannot be attributed."""


@dataclass
class OllamaEngine:
    """One model, reached through the Ollama API."""

    model: str = DEFAULT_EXTRACT_MODEL
    host: str | None = None
    name: str = "ollama"

    def detect_zones(self, image: object, hint: str | None = None) -> list[Zone]:
        raise NotImplementedError("layout pass not yet wired")

    def extract_zone(self, image: object, zone: Zone, hint: str | None = None) -> Zone:
        raise NotImplementedError("zone extraction not yet wired")

    def read_cell(self, image: object, bbox: BBox, hint: str | None = None) -> Reading:
        raise NotImplementedError("cell re-read not yet wired")

    def audit_coverage(self, image: object, zones: list[Zone]) -> list[BBox]:
        raise NotImplementedError("coverage audit not yet wired")
