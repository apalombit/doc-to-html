"""Make a model that ignores `format` answerable anyway.

Ollama's local models honour `format`, so generation is constrained during
decoding and the response cannot be syntactically invalid JSON. **No vision model
on Ollama Cloud does.** `minimax-m3` returns the right fields wrapped in a
markdown fence as a bare array; `gemma4:31b` returns its own `box_2d` detection
format and ignores the schema entirely.

That leaves a choice, and the shape of the choice matters more than the answer:

- Loosen `wire.py`'s mapper. Rejected. "Malformed JSON is impossible" is a
  property the whole project leans on, and trading it away everywhere to reach
  one model is a bad exchange.
- Put the tolerance **behind the Transport seam**, which `transport.py` already
  names as the one seam to replace. The mapper still only ever sees canonical
  JSON; it cannot tell whether a model produced it or this module did.

The second, which is this file. Off by default — set `DTH_LENIENT_DECODING=1`.

**Only lossless repairs live here.** Unwrapping a fence and wrapping a bare array
both recover exactly what the model meant. Translating `gemma4`'s `box_2d` into
our vocabulary would mean mapping free-text labels like `company_logo` onto a
closed Kind enum, which is guessing dressed as parsing — so it is deliberately
not done, and `gemma4:31b` stays unsupported rather than silently mis-served.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .transport import Response, Transport

log = logging.getLogger(__name__)

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _sole_array_property(schema: dict[str, Any]) -> str | None:
    """The one array-valued property a wire schema has, if it has exactly one.

    Every wire response in this project is an object wrapping a single list —
    `zones`, `rows`, `pairs`, `blocks`. That regularity is what makes wrapping a
    bare array safe: there is exactly one key it could belong under, so no choice
    is being made. If a schema ever grows a second array, this returns None and
    the leniency correctly declines to guess.
    """
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    arrays = [
        name for name, spec in properties.items()
        if isinstance(spec, dict) and spec.get("type") == "array"
    ]
    return arrays[0] if len(arrays) == 1 else None


def _item_properties(schema: dict[str, Any], key: str) -> dict[str, Any]:
    """The property schemas of the objects inside the sole array, following $ref."""
    array = schema.get("properties", {}).get(key, {})
    item = array.get("items", {})
    ref = item.get("$ref")
    if ref and ref.startswith("#/$defs/"):
        item = schema.get("$defs", {}).get(ref.split("/")[-1], {})
    properties = item.get("properties")
    return properties if isinstance(properties, dict) else {}


def _coerce_enum(value: str, allowed: list[Any]) -> str | None:
    """Pull a closed-vocabulary value out of a phrase, or decline.

    **This is an inference, not a lossless repair, and it is the one exception in
    this module.** `minimax-m3` answered `graphic: "SPARKSUITE logo"` where the
    schema allows five words; a model honouring `format` could not have. Rather
    than lose the whole Conversion to it, the phrase is matched against the
    schema's own enum — case-insensitively, on whole words only, and *only* when
    exactly one candidate appears. Two candidates, or none, declines and lets the
    schema reject it.

    Known limitation, stated rather than hidden: a negation like "no logo here"
    would match `logo`. The field asks what a graphic *is*, so a negation is not
    an answer the prompt invites, and the alternative — dropping to the default —
    would silently assert something the model never said.
    """
    lowered = value.strip().lower()
    words = [w for w in allowed if isinstance(w, str) and w]
    exact = [w for w in words if w.lower() == lowered]
    if exact:
        return exact[0]
    found = [w for w in words if re.search(rf"\b{re.escape(w)}\b", lowered)]
    return found[0] if len(found) == 1 else None


def _coerce_enums(rows: list[Any], properties: dict[str, Any]) -> int:
    """Repair enum-valued fields in place. Returns how many were changed."""
    repaired = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name, spec in properties.items():
            allowed = spec.get("enum") if isinstance(spec, dict) else None
            value = row.get(name)
            if not allowed or not isinstance(value, str) or value in allowed:
                continue
            better = _coerce_enum(value, allowed)
            if better is not None:
                log.debug("lenient: %s %r -> %r", name, value, better)
                row[name] = better
                repaired += 1
    return repaired


def canonicalise(text: str, schema: dict[str, Any]) -> str:
    """Return `text` as the JSON object the schema describes, if that is lossless.

    Returns the input unchanged when it is already canonical, when no repair
    applies, or when the repair would require inventing something. Callers hand
    the result to Pydantic either way, so a failed repair fails exactly as it
    would have without this.
    """
    stripped = text.strip()
    if not stripped:
        return text

    fenced = FENCE.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return text

    key = _sole_array_property(schema)
    if key is None:
        return text

    wrapped = False
    if isinstance(parsed, list):
        log.debug("lenient: wrapped a bare array under %r", key)
        parsed, wrapped = {key: parsed}, True
    elif not isinstance(parsed, dict):
        return text

    rows = parsed.get(key)
    coerced = (
        _coerce_enums(rows, _item_properties(schema, key))
        if isinstance(rows, list) else 0
    )

    if wrapped or coerced or fenced:
        return json.dumps(parsed)
    return text


@dataclass
class LenientTransport:
    """Wraps a Transport and canonicalises whatever came back.

    A decorator rather than a subclass so it composes with the bake-off's timing
    wrapper and the suite's fake in any order, and so the real transport keeps
    knowing nothing about this.
    """

    inner: Transport

    def __call__(self, *, model: str, pass_name: str, prompt: str,
                 images: list[bytes], schema: dict[str, Any],
                 num_ctx: int) -> Response:
        reply = self.inner(
            model=model, pass_name=pass_name, prompt=prompt, images=images,
            schema=schema, num_ctx=num_ctx,
        )
        repaired = canonicalise(reply.answer, schema)
        if repaired == reply.answer:
            return reply

        log.info("%s: %s answered outside its schema; canonicalised %d -> %d chars",
                 pass_name, model, len(reply.answer), len(repaired))
        # Onto `content` whichever channel carried it: `answer` prefers content,
        # and a repaired answer is no longer the raw text of either channel.
        return Response(content=repaired, truncated=reply.truncated)
