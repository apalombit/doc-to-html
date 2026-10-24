"""Run a script in the corpus's browser and read back what it returns.

`projection.project()` injects one fixed script, `MEASURE`. The factory
asks other questions of a page — which faces resolve, what a text node's
computed face is, whether a list numbers itself — so it needs the same
browser with a different script. It reuses `projection`'s Chrome and its
flags exactly, so a page is asked its questions in the light scheme and
the hinting the corpus's pictures were shot in.

The payload comes back base64 in a `<pre>`, for the reason
`projection`'s docstring gives: `--dump-dom` HTML-escapes what it prints.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from doc_to_html import projection

_ID = "__factory"


def evaluate(html: str, script: str, *, width: int, height: int = 3000
             ) -> Any:
    """The JSON value `script` evaluates to, once the page has loaded.

    `script` is a JavaScript expression — usually an arrow function called
    in place, `(() => { ... return value; })()`. `width` is clamped to
    `projection.MIN_WIDTH`, as every entry point there is.
    """
    if not projection.available():
        raise projection.ProjectionError(f"no headless Chrome at {projection.CHROME}")
    width = max(width, projection.MIN_WIDTH)
    wrapper = (
        "<script>window.addEventListener('load', () => {"
        f"const value = {script};"
        "const pre = document.createElement('pre');"
        f"pre.id = '{_ID}';"
        "pre.textContent = btoa(String.fromCharCode("
        "...new TextEncoder().encode(JSON.stringify(value))));"
        "document.documentElement.appendChild(pre);"
        "});</script>"
    )
    page = (html.replace("</body>", wrapper + "</body>", 1)
            if "</body>" in html else html + wrapper)
    with tempfile.TemporaryDirectory() as work:
        target = Path(work) / "asked.html"
        target.write_text(page, encoding="utf-8")
        result = subprocess.run(
            [str(projection.CHROME), *projection._FLAGS,
             "--virtual-time-budget=5000", "--dump-dom",
             f"--window-size={width},{height}", target.resolve().as_uri()],
            capture_output=True, timeout=projection.TIMEOUT_S,
        )
    dom = result.stdout.decode("utf-8", "replace")
    opening = f'id="{_ID}">'
    start = dom.find(opening)
    if start < 0:
        raise projection.ProjectionError(
            "the browser returned nothing: "
            f"{result.stderr.decode('utf-8', 'replace')[:400]}"
        )
    start += len(opening)
    encoded = dom[start:dom.find("</pre>", start)].strip()
    return json.loads(base64.b64decode(encoded))
