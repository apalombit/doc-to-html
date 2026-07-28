"""The one place the process talks to Ollama.

Everything above this line — prompts, wire schemas, mapping, Extractors,
assembly, the renderer — is exercised by the suite against recorded responses.
That is only true because there is exactly one seam to replace, and it is this
one. If a second path to a model ever appears, the suite stops covering the
pipeline and starts covering half of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Response:
    """What came back, and whether the model ran out of room saying it."""

    content: str
    """The raw response text. Schema-valid by construction unless truncated."""

    truncated: bool
    """The generation stopped at the token limit rather than at the end of the
    answer. Constrained decoding cannot prevent this: it leaves a valid *prefix*
    of an incomplete array, which is exactly what a long table produces."""


class Transport(Protocol):
    """One call to a vision model."""

    def __call__(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes],
        schema: dict[str, Any],
        num_ctx: int,
    ) -> Response: ...


@dataclass
class OllamaTransport:
    """The real call. Constructed from an Engine's resolved configuration.

    `format=schema` is the load-bearing argument: it constrains generation during
    decoding, so the response cannot be syntactically invalid JSON or carry a
    field the schema does not describe. Parsing around malformed output is a code
    path this deliberately removes rather than defends.
    """

    client_kwargs: dict[str, Any]

    def __call__(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes],
        schema: dict[str, Any],
        num_ctx: int,
    ) -> Response:
        import ollama

        client = ollama.Client(**self.client_kwargs)
        reply = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt, "images": images}],
            format=schema,
            options={"num_ctx": num_ctx, "num_predict": num_ctx, "temperature": 0},
        )
        return Response(
            content=reply["message"]["content"],
            truncated=reply.get("done_reason") == "length",
        )
