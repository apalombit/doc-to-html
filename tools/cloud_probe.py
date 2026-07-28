"""Ask a cloud model the two questions the local runs cannot settle alone.

    python tools/cloud_probe.py

Deliberately **not** wired into the pipeline. Ollama Cloud's vision models do not
honour `format`, so a Conversion driven by one would fail to map on every pass and
say nothing about layout quality. That is a finding, not an obstacle to route
around: constrained decoding is what this project relies on to make malformed JSON
impossible, and weakening the shared mapper to accommodate a model that ignores it
would trade the guarantee for a data point.

So this asks directly, normalises the answer here, and writes what came back to
`debug/cloud/`. Two questions:

1. **Is the trailing-character truncation ours or the model's?** `qwen3-vl:4b`
   returns `$300.00` as `$300.0` and `1000` as `100` — always the last character.
   A different family reading the same crop settles where that comes from.
2. **Are the two `kind` confusions our prompt or the 4B's capacity?** If a much
   larger model also calls the payment table `pairs` and the invoice details
   `prose`, the prompt is ambiguous and fixing it helps the local path too.

Requires `OLLAMA_API_KEY` in `.env`. Costs nothing on the 8 GB M1 — no local model
is loaded — so it does not disturb the latency baseline the local runs measure.
"""

from __future__ import annotations

import base64
import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doc_to_html.engines.ollama import LAYOUT_PROMPT, TABLE_PROMPT  # noqa: E402

CLOUD = "https://ollama.com/api/chat"
MODELS = ("gemma4:31b", "minimax-m3")
"""The vision models this account can reach.

`qwen3.5:397b` and `kimi-k3` both answer 403 "requires a subscription". The first
is the one actually worth having — same family as the local `qwen3-vl:4b` at about
a hundred times the parameters, which would separate capacity from prompt within
one lineage instead of across two."""


def key() -> str:
    found = re.search(r"^OLLAMA_API_KEY=(.*)$", Path(".env").read_text(), re.M)
    if not found or not found.group(1).strip():
        raise SystemExit("no OLLAMA_API_KEY in .env")
    return found.group(1).strip()


def encode(image: Image.Image, long_edge: int | None = None) -> str:
    page = image.convert("RGB")
    if long_edge:
        page.thumbnail((long_edge, long_edge))
    buffer = io.BytesIO()
    page.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def ask(model: str, prompt: str, image: str, token: str) -> str:
    """One call. No `format`: these models ignore it, and asking invites a 500."""
    body = json.dumps({
        "model": model, "stream": False, "think": False,
        "options": {"num_ctx": 8192},
        "messages": [{"role": "user", "content": prompt, "images": [image]}],
    }).encode()
    request = urllib.request.Request(
        CLOUD, data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    try:
        reply = json.load(urllib.request.urlopen(request, timeout=600))
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}: {error.read().decode()[:200]}"
    message = reply.get("message", {})
    return message.get("content") or message.get("thinking") or ""


def unfence(text: str) -> str:
    """Strip a markdown code fence, which is all these models wrap JSON in.

    Lossless and local to this script. The shared mapper does not learn this
    tolerance — the point of the exercise is to keep that guarantee intact.
    """
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return (fenced.group(1) if fenced else text).strip()


def zones_of(text: str) -> list[dict[str, object]] | None:
    """Accept either `{"zones": [...]}` or a bare top-level array."""
    try:
        parsed = json.loads(unfence(text))
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        found = parsed.get("zones")
        return found if isinstance(found, list) else None
    return parsed if isinstance(parsed, list) else None


def main() -> int:
    token = key()
    out = Path("debug/cloud")
    out.mkdir(parents=True, exist_ok=True)

    page = Image.open("example/invoice.png")
    # The line-items table as run 06 at 384 finally cropped it correctly.
    items = page.convert("RGB").crop(
        (int(0.04 * page.width), int(0.63 * page.height),
         int(0.95 * page.width), int(0.93 * page.height))
    )

    for model in MODELS:
        slug = model.replace(":", "_").replace(".", "_")
        print(f"\n{'=' * 62}\n{model}\n{'=' * 62}")

        answer = ask(model, LAYOUT_PROMPT, encode(page, 384), token)
        (out / f"{slug}_layout.txt").write_text(answer)
        zones = zones_of(answer)
        if zones is None:
            print(f"  layout: unparseable -> {answer[:160]}")
        else:
            print(f"  layout: {len(zones)} regions")
            for index, zone in enumerate(zones):
                box = [zone.get(k) for k in ("left", "top", "right", "bottom")]
                print(f"    {index} {str(zone.get('kind')):7} "
                      f"{str(zone.get('role')):7} {box}")

        answer = ask(model, TABLE_PROMPT, encode(items), token)
        (out / f"{slug}_table.txt").write_text(answer)
        print("  line-items table, as read:")
        try:
            rows = json.loads(unfence(answer))
            rows = rows.get("rows", rows) if isinstance(rows, dict) else rows
            for row in rows:
                print(f"    {str(row.get('role')):8} {row.get('cells')}")
        except (json.JSONDecodeError, AttributeError):
            print(f"    unparseable -> {answer[:200]}")

    print(f"\nraw answers in {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
