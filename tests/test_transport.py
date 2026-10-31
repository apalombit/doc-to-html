"""The limit on one model call's whole time (spec 0021, decision 11).

The client's own timeout is reset by every piece of a streamed answer, so a
call that streams on and never finishes ran ten minutes under it. Pinned
here with a stand-in for the Ollama client: a stream that never ends is
stopped at the limit and its connection closed, one that ends is returned
whole, and a stopped call is not retried.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

from doc_to_html.engines.ollama import OllamaEngine
from doc_to_html.engines.transport import CallTooLong, OllamaTransport, Response


class Stream:
    """`ollama.Client` stood in for: `chat` streams `pieces` pieces, or
    without end, and records whether the stream was closed."""

    def __init__(self, pieces: int | None, every_s: float = 0.01) -> None:
        self.pieces, self.every_s, self.closed = pieces, every_s, False

    def __call__(self, **kwargs: Any) -> Stream:
        return self

    def chat(self, **request: Any) -> Iterator[dict[str, Any]]:
        sent = 0
        try:
            while self.pieces is None or sent < self.pieces:
                time.sleep(self.every_s)
                sent += 1
                yield {"message": {"thinking": "x"}}
            yield {"message": {"thinking": "}"}, "done": True, "done_reason": "stop"}
        finally:
            self.closed = True


def call(stream: Stream, monkeypatch: pytest.MonkeyPatch, limit_s: float) -> Response:
    import ollama

    monkeypatch.setattr(ollama, "Client", stream)
    transport = OllamaTransport({"host": "http://localhost:11434"}, limit_s=limit_s)
    return transport(model="m", pass_name="table", prompt="p", images=[b"png"],
                     schema={}, num_ctx=8192)


def test_a_call_that_never_finishes_is_stopped_at_its_limit_and_its_stream_closed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    stream = Stream(pieces=None)
    started = time.perf_counter()
    with pytest.raises(CallTooLong, match="table: m had not finished after 0 s"):
        call(stream, monkeypatch, limit_s=0.2)
    assert time.perf_counter() - started < 2.0
    assert stream.closed, "the connection is what tells Ollama to stop generating"


def test_a_call_that_finishes_within_its_limit_is_returned_whole(
        monkeypatch: pytest.MonkeyPatch) -> None:
    stream = Stream(pieces=5)
    reply = call(stream, monkeypatch, limit_s=5.0)
    assert reply.answer == "xxxxx}" and not reply.truncated
    assert stream.closed


def test_no_limit_lets_a_long_call_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = call(Stream(pieces=30), monkeypatch, limit_s=0.0)
    assert reply.answer == "x" * 30 + "}"


def test_a_stopped_call_is_not_retried() -> None:
    """A truncation is retried at twice the budget; a call stopped at its
    limit would run on again at `temperature: 0`, so its Zone fails."""
    asked: list[int] = []

    def transport(**kwargs: Any) -> Response:
        asked.append(kwargs["num_ctx"])
        raise CallTooLong("table: m had not finished after 180 s")

    engine = OllamaEngine(model="m", transport=transport)
    with pytest.raises(CallTooLong):
        engine.ask("table", "p", np.zeros((8, 8, 3), dtype=np.uint8), {})
    assert asked == [engine.num_ctx]
