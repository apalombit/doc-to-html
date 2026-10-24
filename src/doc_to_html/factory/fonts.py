"""The faces a corpus page may name, each with its class — spec 0020, step 0.

**Why a page names only these.** The font class is a major criterion
(`docs/agents/review-criteria.md`: "the wrong font class (serif, sans,
mono, script)"). A page that names a face this machine lacks is drawn in a
fallback, so its HTML says one class and its picture shows another, and
the ground truth would mark the converter wrong for drawing what the
picture shows. Every face here is **measured as resolving** in the
corpus's own browser before it is listed.

**Which faces.** Two origins, both recorded per face in `corpus/fonts.json`:

- `apple` — shipped with macOS, in `/System/Library/Fonts` or its
  `Supplemental` folder. Any Mac on this macOS draws them.
- `open` — installed in `/Library/Fonts` and published under an open
  licence (SIL OFL 1.1, or the Ubuntu Font Licence). Another machine
  installs them to re-shoot a page.

Left out on purpose: faces for scripts the corpus does not use (CJK,
Arabic, Hebrew, Indic, Thai), symbol and dingbat faces, macOS's hidden
`.`-prefixed system faces (Chrome refuses them), and the commercial or
personal-use faces installed in `/Library/Fonts` on this machine. A page
in one of those cannot be re-shot on another machine, and some are
licensed for personal use only.

**What is measured** (`measure`), in Chrome, at 48px:

- *resolves*: a probe string is the same width whatever generic follows
  the face in the stack. A missing face falls through to `monospace` in
  one and `serif` in the other, and the two differ.
- *covers*: the same test, one glyph at a time, over `GLYPHS`: the
  accents of the five languages, `€ £ « » ’ “ ” – —`. A face that lacks
  one would draw that glyph from a fallback; it is not listed.
- *weights*: how many distinct widths the probe takes over weights
  100–900. Chrome snaps a weight to the nearest real face, so this counts
  the real faces. A face with three or more can carry `type.weights`.
  Measured, a synthesised bold keeps the regular's widths (Monaco has one
  face and counts 1), so a synthesised weight is never counted. A
  monospaced face keeps its widths at every weight too, so a mono face
  counts 1 however many it has (Menlo has a bold).
- *monospaced*: `iiiii` and `MMMMM` the same width. Checked against the
  class: a face classed `mono` must be monospaced and no other may be.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from doc_to_html.factory import browser

CLASSES = ("serif", "sans", "mono", "script", "display")
"""The five classes. The first three are a page's possible main face
(`type.serif`, `type.sans`, `type.mono`); script and display faces are
extras (`type.script`, `type.display`), never a page's body."""

GENERIC: dict[str, str] = {
    "serif": "serif", "sans-serif": "sans", "monospace": "mono",
    "cursive": "script", "ui-serif": "serif", "ui-sans-serif": "sans",
    "ui-monospace": "mono", "system-ui": "sans",
}
"""CSS's generic families and the class each draws on this machine. A page
may end a stack with one; it may not lead with one, so the face drawn is
always the face named. `fantasy` is not here: what it draws is a guess."""

CANDIDATES: dict[str, tuple[str, str]] = {
    # serif
    "Times New Roman": ("serif", "apple"), "Times": ("serif", "apple"),
    "Georgia": ("serif", "apple"), "Palatino": ("serif", "apple"),
    "Baskerville": ("serif", "apple"), "Hoefler Text": ("serif", "apple"),
    "Cochin": ("serif", "apple"), "Charter": ("serif", "apple"),
    "STIX Two Text": ("serif", "apple"), "PT Serif": ("serif", "apple"),
    "PT Serif Caption": ("serif", "apple"), "Bodoni 72": ("serif", "apple"),
    "Bodoni 72 Oldstyle": ("serif", "apple"), "Didot": ("serif", "apple"),
    "Big Caslon": ("serif", "apple"), "Rockwell": ("serif", "apple"),
    "American Typewriter": ("serif", "apple"),
    "Lora": ("serif", "open"), "Libre Baskerville": ("serif", "open"),
    "Source Serif Variable": ("serif", "open"),
    "Cormorant Garamond": ("serif", "open"), "Baskervville": ("serif", "open"),
    # sans
    "Helvetica": ("sans", "apple"), "Helvetica Neue": ("sans", "apple"),
    "Arial": ("sans", "apple"), "Arial Narrow": ("sans", "apple"),
    "Verdana": ("sans", "apple"), "Tahoma": ("sans", "apple"),
    "Trebuchet MS": ("sans", "apple"), "Gill Sans": ("sans", "apple"),
    "Futura": ("sans", "apple"), "Avenir": ("sans", "apple"),
    "Avenir Next": ("sans", "apple"),
    "Avenir Next Condensed": ("sans", "apple"), "Optima": ("sans", "apple"),
    "Lucida Grande": ("sans", "apple"), "Geneva": ("sans", "apple"),
    "Microsoft Sans Serif": ("sans", "apple"), "Galvji": ("sans", "apple"),
    "Skia": ("sans", "apple"), "PT Sans": ("sans", "apple"),
    "PT Sans Narrow": ("sans", "apple"), "PT Sans Caption": ("sans", "apple"),
    "Arial Rounded MT Bold": ("sans", "apple"),
    "DIN Alternate": ("sans", "apple"),
    "Open Sans": ("sans", "open"), "Source Sans Variable": ("sans", "open"),
    "Ubuntu": ("sans", "open"), "Comfortaa": ("sans", "open"),
    "Hind": ("sans", "open"),
    # mono
    "Menlo": ("mono", "apple"), "Monaco": ("mono", "apple"),
    "Courier": ("mono", "apple"), "Courier New": ("mono", "apple"),
    "Andale Mono": ("mono", "apple"), "PT Mono": ("mono", "apple"),
    "Source Code Variable": ("mono", "open"),
    # script: joined or handwritten
    "Snell Roundhand": ("script", "apple"), "Zapfino": ("script", "apple"),
    "Apple Chancery": ("script", "apple"), "Brush Script MT": ("script", "apple"),
    "Savoye LET": ("script", "apple"), "Bradley Hand": ("script", "apple"),
    "SignPainter": ("script", "apple"), "Noteworthy": ("script", "apple"),
    "Marker Felt": ("script", "apple"), "Chalkboard SE": ("script", "apple"),
    "Caveat": ("script", "open"),
    # display: for titles, never a body
    "Copperplate": ("display", "apple"), "Herculanum": ("display", "apple"),
    "Papyrus": ("display", "apple"), "Phosphate": ("display", "apple"),
    "Chalkduster": ("display", "apple"), "Impact": ("display", "apple"),
    "Arial Black": ("display", "apple"),
    "Bodoni 72 Smallcaps": ("display", "apple"),
    "Party LET": ("display", "apple"),
    "Academy Engraved LET": ("display", "apple"),
    "Trattatello": ("display", "apple"), "Luminari": ("display", "apple"),
    "DIN Condensed": ("display", "apple"),
    "Playfair Display": ("display", "open"), "Oswald": ("display", "open"),
    "Cinzel": ("display", "open"),
}
"""Every face considered, with its class and origin. Classed by hand —
a class is a judgement about how a face reads, which no measure gives —
and then measured: `measure` drops any that fails to resolve or to cover
`GLYPHS`, and `check_classes` holds `mono` to the monospaced test."""

GLYPHS = "àáâãäçèéêëìíîïñòóôõöùúûüœÀÁÂÃÇÈÉÊÍÑÓÔÕÚÜŒ€£«»’“”–—"
"""What a page in English, Italian, French, Spanish or Portuguese prints
beyond ASCII, often enough that a face missing one would be drawn in two
faces. Symbols such as ✓ are not here: a face rarely has them, a fallback
draws them, and that is the same on both sides."""

PROBE = "Hamburgefontsiv 0123456789 WMQ@&"

_MEASURE = r"""
(() => {
  const families = %FAMILIES%;
  const glyphs = %GLYPHS%;
  const probe = %PROBE%;
  const span = document.createElement('span');
  span.style.cssText = 'position:absolute;top:0;left:0;font-size:48px;white-space:pre';
  document.body.appendChild(span);
  const width = (text, family, weight, style) => {
    span.style.fontFamily = family;
    span.style.fontWeight = String(weight);
    span.style.fontStyle = style;
    span.textContent = text;
    return span.getBoundingClientRect().width;
  };
  const same = (a, b) => Math.abs(a - b) < 0.01;
  const out = {};
  for (const family of families) {
    const named = '"' + family + '"';
    const resolves = same(width(probe, named + ', monospace', 400, 'normal'),
                          width(probe, named + ', serif', 400, 'normal'));
    const missing = [];
    for (const glyph of glyphs) {
      const text = glyph.repeat(8);
      if (!same(width(text, named + ', monospace', 400, 'normal'),
                width(text, named + ', serif', 400, 'normal'))) missing.push(glyph);
    }
    const widths = new Set();
    for (let weight = 100; weight <= 900; weight += 100) {
      widths.add(width(probe, named + ', monospace', weight, 'normal').toFixed(2));
    }
    out[family] = {
      resolves: resolves,
      missing: missing.join(''),
      weights: widths.size,
      monospaced: same(width('iiiii', named + ', serif', 400, 'normal'),
                       width('MMMMM', named + ', serif', 400, 'normal')),
    };
  }
  return out;
})()
"""


@dataclass(frozen=True)
class Face:
    """One face a page may name."""

    family: str
    cls: str
    origin: str
    weights: int


def measure(families: list[str]) -> dict[str, dict[str, Any]]:
    """What the browser says about each family: resolves, missing glyphs,
    real weights, monospaced. One browser call for the lot."""
    script = (_MEASURE.replace("%FAMILIES%", json.dumps(families))
              .replace("%GLYPHS%", json.dumps(GLYPHS))
              .replace("%PROBE%", json.dumps(PROBE)))
    result: dict[str, dict[str, Any]] = browser.evaluate(
        "<!doctype html><html><body></body></html>", script, width=800)
    return result


def allow_list(measured: dict[str, dict[str, Any]]) -> list[Face]:
    """The candidates that resolve and cover every glyph, in class order."""
    faces = []
    for family, (cls, origin) in CANDIDATES.items():
        found = measured.get(family, {})
        if found.get("resolves") and not found.get("missing"):
            faces.append(Face(family, cls, origin, int(found["weights"])))
    order = {cls: index for index, cls in enumerate(CLASSES)}
    return sorted(faces, key=lambda face: (order[face.cls], face.family))


def check_classes(measured: dict[str, dict[str, Any]]) -> list[str]:
    """Each face classed `mono` that is not monospaced, and each face that
    is monospaced and classed otherwise. Empty when the classes hold."""
    wrong = []
    for family, (cls, _) in CANDIDATES.items():
        found = measured.get(family)
        if not found or not found.get("resolves"):
            continue
        if (cls == "mono") != bool(found["monospaced"]):
            wrong.append(f"{family}: classed {cls}, monospaced {found['monospaced']}")
    return wrong


def write(path: Path, faces: list[Face], measured: dict[str, dict[str, Any]]
          ) -> None:
    """`corpus/fonts.json`: the allow-list, and why each candidate left out
    was left out."""
    kept = {face.family for face in faces}
    payload = {
        "about": ("The faces a corpus page may name (spec 0020, step 0). "
                  "Written by tools/corpus_fonts.py; see "
                  "doc_to_html.factory.fonts for how each was measured."),
        "glyphs": GLYPHS,
        "generic": GENERIC,
        "faces": {face.family: {"class": face.cls, "origin": face.origin,
                                "weights": face.weights} for face in faces},
        "left_out": {
            family: ("does not resolve" if not measured.get(family, {}).get("resolves")
                     else f"lacks {measured[family]['missing']}")
            for family in CANDIDATES if family not in kept
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")


def load(path: Path) -> dict[str, Face]:
    """The allow-list as written, by family."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {family: Face(family, entry["class"], entry["origin"], entry["weights"])
            for family, entry in data["faces"].items()}
