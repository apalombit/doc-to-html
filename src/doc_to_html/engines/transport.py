"""The one place the process talks to Ollama.

Everything above this line — prompts, wire schemas, mapping, Extractors,
assembly, the renderer — is exercised by the suite against recorded responses.
That is only true because there is exactly one seam to replace, and it is this
one. If a second path to a model ever appears, the suite stops covering the
pipeline and starts covering half of it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

PROGRESS_EVERY_S = 15.0
"""How often a pass in flight says it is still alive.

A vision pass on an 8 GB machine takes tens of seconds, and silence for that long
is indistinguishable from a hang — which is exactly how a runner dying mid-request
first presented. Set DTH_LOG_LEVEL=INFO to see these.
"""


@dataclass(frozen=True)
class Response:
    """What came back, and whether the model ran out of room saying it."""

    content: str
    """The raw response text. Schema-valid by construction unless truncated."""

    truncated: bool
    """The generation stopped at the token limit rather than at the end of the
    answer. Constrained decoding cannot prevent this: it leaves a valid *prefix*
    of an incomplete array, which is exactly what a long table produces."""

    thinking: str = ""
    """Whatever arrived on the reasoning channel.

    Kept separate rather than discarded because Ollama routes `qwen3-vl`'s
    structured output here and leaves `content` empty — the answer is correct and
    on the wrong channel. `answer` is what callers should read.

    When the model really did reason, this holds prose instead, and schema
    validation rejects it. That is the right outcome: the two cases are
    indistinguishable by shape, so let the schema decide rather than guessing.
    """

    @property
    def answer(self) -> str:
        """The response, from whichever channel carried it."""
        return self.content or self.thinking


class CallTooLong(RuntimeError):
    """A call stopped at its limit (`config.DEFAULT_CALL_LIMIT_S`) before it
    finished. Not retried: at `temperature: 0` it would run on again."""


class Transport(Protocol):
    """One call to a vision model."""

    def __call__(
        self,
        *,
        model: str,
        pass_name: str,
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

    `pass_name` is used only for logging here. It is what a measuring wrapper needs
    and cannot otherwise know: `prose` and `list` share one schema, so the schema's
    title cannot tell them apart, and per-pass latency that lumps them together is
    the wrong number.

    **Thinking is disabled.** `qwen3-vl` is a reasoning model, and with thinking on
    it spends its entire token budget in `message.thinking` and returns an empty
    `message.content` — which looks exactly like a truncation and cost a first
    bake-off run 180 seconds to produce nothing. There is nothing to reason about
    here: the answer is a transcription constrained by a schema.

    **The response is streamed.** Not for the tokens, which are assembled and
    handed back whole, but so a pass in flight can say it is still alive. A vision
    pass takes tens of seconds on an 8 GB machine and silence that long reads as a
    hang.
    """

    client_kwargs: dict[str, Any]
    limit_s: float = 0.0
    """How long the call may run, whole; 0 for no limit. The client's own
    timeout cannot be this: it is reset by every piece of the stream."""

    def __call__(
        self,
        *,
        model: str,
        pass_name: str,
        prompt: str,
        images: list[bytes],
        schema: dict[str, Any],
        num_ctx: int,
    ) -> Response:
        import ollama

        client = ollama.Client(**self.client_kwargs)
        request: dict[str, Any] = dict(
            model=model,
            messages=[{"role": "user", "content": prompt, "images": images}],
            format=schema,
            options={"num_ctx": num_ctx, "num_predict": num_ctx, "temperature": 0},
            stream=True,
        )

        started = time.perf_counter()
        log.info("%s: %s starting (num_ctx=%d, image=%dKB)",
                 pass_name, model, num_ctx, len(images[0]) // 1024 if images else 0)

        parts: list[str] = []
        thoughts: list[str] = []
        done_reason: str | None = None
        spoke_at = started

        stream = self._stream(client, request)
        try:
            for chunk in stream:
                message = chunk.get("message") or {}
                parts.append(message.get("content") or "")
                thoughts.append(message.get("thinking") or "")
                if chunk.get("done"):
                    done_reason = chunk.get("done_reason")

                now = time.perf_counter()
                if self.limit_s and now - started > self.limit_s and not chunk.get("done"):
                    written = sum(map(len, parts)) + sum(map(len, thoughts))
                    log.info("%s: %s stopped at its limit, %.0fs, %d chars",
                             pass_name, model, now - started, written)
                    raise CallTooLong(
                        f"{pass_name}: {model} had not finished after {self.limit_s:.0f} s "
                        f"({written} characters); stopped")
                if now - spoke_at >= PROGRESS_EVERY_S:
                    log.info("%s: %s still going, %.0fs, %d chars answered, %d reasoning",
                             pass_name, model, now - started,
                             sum(map(len, parts)), sum(map(len, thoughts)))
                    spoke_at = now
        finally:
            # Closing the stream closes the connection, and Ollama cancels
            # the generation when its client goes (spec 0021's limit proof).
            stream.close()

        content, thinking = "".join(parts), "".join(thoughts)
        log.info("%s: %s done in %.1fs, reason=%s, %d chars on %s",
                 pass_name, model, time.perf_counter() - started, done_reason,
                 len(content) or len(thinking),
                 "content" if content else "the reasoning channel")

        return Response(
            content=content,
            truncated=done_reason == "length",
            thinking=thinking,
        )

    @staticmethod
    def _stream(client: Any, request: dict[str, Any]) -> Any:
        """Stream the reply, asking for thinking to be off where the model has it.

        `think` is rejected outright by models that cannot reason, and which those
        are is not worth a lookup table — so ask, and fall back once if the server
        says no. Any other error is the caller's problem and is not swallowed here.
        """
        import ollama

        try:
            yield from client.chat(think=False, **request)
        except (ollama.ResponseError, TypeError) as error:
            if "think" not in str(error).lower():
                raise
            log.debug("%s does not take think=False; retrying without",
                      request.get("model"))
            yield from client.chat(**request)
