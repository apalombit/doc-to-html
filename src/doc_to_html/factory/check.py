"""The validator every corpus page passes before it counts — spec 0020 §V.

**Why it exists.** The corpus's ground truth is its HTML: the scorer reads
the words, lines and structure off it with `projection.project()`, which
walks text nodes. So a page is only honest if **every word in its DOM is a
word in its picture, and nothing in its picture is a word the DOM does not
hold**. `newsletter_0008` once clipped its own text, and nothing but a
picture showed it (`CLAUDE.md`'s lessons). The ten checks below are each a
way that promise has been seen to break, or would.

| # | check | name |
|---|---|---|
| 1 | it renders at the card's width, at most 2400 px tall | `renders` |
| 2 | a second shoot is the same picture, to the pixel | `own_picture` |
| 3 | nothing clipped, overflowing or off the page | `fits` |
| 4 | every text node's every line box has ink under it | `ink` |
| 5 | no external resource; every face on the allow-list | `self_contained` |
| 6 | no words inside a figure | `figures` |
| 7 | no generated text | `generated` |
| 8 | the card's auto-checkable features are on the page | `features` |
| 9 | the page is in the card's language | `language` |
| 10 | not a near-duplicate of an accepted page | `distinct` |

A PDF page's twin runs 5–10 (`check(..., twin=True)`); its picture is the
PDF's render, and §P's gate stands in for 1–4.

**Ink (4)** is measured per line box of each text node, on the page's own
screenshot: the box's most common colour is its ground, and a pixel more
than `INK_DIFF` from it in any channel is ink. A box needs
`max(INK_MIN_PX, INK_MIN_SHARE × area)` such pixels. Text the colour of its
ground, text under an opaque box, and text scaled to nothing all fail; a
lone full stop at 11px has about four.

**Faces (5).** The face drawn must be the face named, so a stack may lead
only with an allow-listed face or with `serif`, `sans-serif`, `monospace`
or `cursive`, which Chrome draws here as Times, Helvetica, Courier and
Apple Chancery, all on the list. Every other entry in the stack must be on
the list or generic too.

**Generated text (7)** is anything a reader sees that is not a text node:
`::before` or `::after` content with characters in it (a `<q>`'s quote
marks included), an `<ol>` that numbers itself, a list whose marker is a
counter or a string, automatic hyphenation (the hyphen is the renderer's,
CLAUDE.md's `con-` lesson), and form controls, whose values and ticks are
not text nodes. A plain `disc`, `circle` or `square` bullet is allowed, as
the brief says. Check 4 also refuses type under `MIN_TYPE_PX`.

**Features (8)** — the auto column of the spec's §F: a `<table>` for any
`table.*`; `colspan`/`rowspan` above 1; an empty `<td>`; 25 rows or more
in one table; `<ul>`, `<ol>`, a list inside a list; `text-align: justify`
on a block of two lines or more; `<sup>`/`<sub>`; `<blockquote>`; the main
face's class, taken over the characters each face sets; a dark ground,
taken as the screenshot's median luminance; an `<svg>` or `<img>` for any
`fig.*`; and a pattern in the text for each `fmt.*`. What a page shows of
these, whatever its card asked, is recorded as its `detected` features.
Check 8 also holds the card's density to a word floor: `WORD_FLOOR` words
per 1000 px of width, half that for the `COMPACT_KINDS` and for a
fragment (a part of a document at its own size), and none for a sparse
page. Set from the pilot's 50: the 17 pages written by Opus, which
read as their density, all clear it, and 14 of the 33 written by Sonnet,
about half as wordy at the same density, do not.

**Language (9)** counts each language's common words (`STOPWORDS`); a word
shared by two lists counts half to each. The card's language must score at
least `LANGUAGE_MIN` on a page of `LANGUAGE_SHORT` words or more (1 on a
shorter page in any language but English), and no other language may lead
it by `LANGUAGE_MARGIN` or more. Measured over the 31 pages already in the
corpus: `ticket_0020`, 55 words of labels, scores 0.5 in English and 0.5 in
French, and the numeric `sample_table_0003` 2.0 in 155 words. A page
written in the wrong language trails by many.

**Near-duplicates (10)**: four-word shingles, Jaccard under 0.5, against
every accepted page and the 31 already in the corpus; and a 64-bit
difference hash of the picture more than `HASH_NEAR` bits from each.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import numpy.typing as npt
from PIL import Image

from doc_to_html import projection
from doc_to_html.factory import browser, fonts
from doc_to_html.factory.cards import Card

MAX_HEIGHT = 2400
MIN_TYPE_PX = 7.0
INK_DIFF = 48
INK_MIN_PX = 2
INK_MIN_SHARE = 0.004
LANGUAGE_MIN = 2.0
LANGUAGE_MARGIN = 1.5
LANGUAGE_SHORT = 80
JACCARD_MAX = 0.5
HASH_NEAR = 3
SHINGLE = 4
DARK_GROUND = 0.40
LONG_TABLE = 25
WORD_FLOOR = {"medium": 220, "dense": 400}
COMPACT_KINDS = frozenset({"certificate", "ticket", "invitation", "membership card",
                           "slide", "flyer", "prescription", "calendar",
                           "nutrition label"})


def word_floor(card: Card) -> int:
    """The fewest words a page of `card`'s density holds at its width."""
    per_1000 = WORD_FLOOR.get(card.density or "", 0)
    share = 0.5 if card.kind in COMPACT_KINDS or card.family == "fragments" else 1.0
    return round(per_1000 * (card.width or 0) / 1000 * share)

GENERIC_FIRST = {"serif": "serif", "sans-serif": "sans", "monospace": "mono",
                 "cursive": "script"}
"""Generics a stack may lead with, and the class each draws here."""

PLAIN_MARKERS = {"disc", "circle", "square", "none"}

_PROBE = r"""
(() => {
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE']);
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName)) continue;
    if (parent.closest('script, style, noscript, template')) continue;
    const style = getComputedStyle(parent);
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()]
      .filter((r) => r.width > 0.5 && r.height > 0.5)
      .map((r) => [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY]);
    const inSvg = !!parent.closest('svg, canvas');
    const inFigure = !!parent.closest('figure') && !parent.closest('figcaption');
    texts.push({
      text: text, rects: rects, family: style.fontFamily,
      size: parseFloat(style.fontSize), in_figure: inSvg || inFigure,
      visible: parent.checkVisibility({opacityProperty: true, visibilityProperty: true}),
    });
  }

  const generated = [];
  const lists = [];
  const tables = [];
  let justified = 0;
  let hyphenated = 0;
  for (const element of document.querySelectorAll('body *')) {
    if (SKIP.has(element.tagName) || element.closest('svg')) continue;
    for (const pseudo of ['::before', '::after']) {
      const content = getComputedStyle(element, pseudo).content;
      if (!content || content === 'none' || content === 'normal') continue;
      const stripped = content.replace(/^["']|["']$/g, '').trim();
      if (stripped) generated.push({tag: element.tagName, pseudo, content});
    }
    const style = getComputedStyle(element);
    const isList = element.tagName === 'OL' || element.tagName === 'UL'
      || (style.display === 'list-item' && element.tagName !== 'LI');
    if (isList) {
      lists.push({tag: element.tagName, marker: style.listStyleType,
                  nested: !!element.parentElement && !!element.parentElement.closest('ol, ul'),
                  items: element.children.length});
    }
    if (element.tagName === 'LI' && element.parentElement
        && !['OL', 'UL'].includes(element.parentElement.tagName)) {
      lists.push({tag: 'LI-ALONE', marker: style.listStyleType, nested: false, items: 1});
    }
    if (element.tagName === 'TABLE') {
      let spans = false, empty = false;
      for (const cell of element.querySelectorAll('td, th')) {
        if (cell.colSpan > 1 || cell.rowSpan > 1) spans = true;
        if (cell.tagName === 'TD' && !cell.textContent.trim()) empty = true;
      }
      tables.push({rows: element.rows.length, spans: spans, empty: empty});
    }
    if ((style.hyphens === 'auto' || style.webkitHyphens === 'auto')
        && element.textContent.trim()) hyphenated += 1;
    if (style.textAlign === 'justify' && element.textContent.trim()) {
      const range = document.createRange();
      range.selectNodeContents(element);
      const tops = new Set([...range.getClientRects()].map((r) => Math.round(r.top / 4)));
      if (tops.size >= 2) justified += 1;
    }
  }
  const count = (selector) => [...document.querySelectorAll(selector)]
    .filter((e) => e.textContent.trim()).length;
  return {
    texts: texts, generated: generated, lists: lists, tables: tables,
    justified: justified, hyphenated: hyphenated,
    controls: document.querySelectorAll('input, select, textarea, progress, meter, details').length,
    sup: count('sup, sub'), blockquote: count('blockquote'),
    svg: document.querySelectorAll('body svg').length,
    img: [...document.querySelectorAll('img')].map((i) => (i.getAttribute('src') || '').slice(0, 16)),
    canvas: document.querySelectorAll('canvas').length,
    width: document.documentElement.scrollWidth,
  };
})()
"""

STOPWORDS: dict[str, set[str]] = {
    "en": set("the and of to in for with on at by from is are was this that these "
              "your our we you it be will not or an as all any per each "
              "please thank total subtotal date time page amount name number address "
              "phone signature payment due paid balance price quantity description "
              "notes note day week month year first last next monday tuesday "
              "wednesday thursday friday saturday sunday january february march "
              "april june july august september october november december".split()),
    "it": set("il lo la gli le di del della dei delle degli che per con non una un "
              "uno sono è nel nella nei alla alle al dal dalla si ai come anche più "
              "totale data pagina importo nome cognome numero indirizzo telefono firma "
              "pagamento grazie iva prezzo quantità descrizione note giorno settimana "
              "mese anno lunedì martedì mercoledì giovedì venerdì sabato domenica "
              "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre "
              "ottobre novembre dicembre".split()),
    "fr": set("le la les des du de et est pour dans avec une un sur par au aux vous "
              "nous votre vos ne pas qui que être ce cette sont "
              "total date montant nom prénom numéro adresse téléphone signature "
              "paiement merci tva prix quantité désignation remarques jour semaine "
              "mois année lundi mardi mercredi jeudi vendredi samedi dimanche "
              "janvier février mars avril mai juin juillet août septembre octobre "
              "novembre décembre".split()),
    "es": set("el los las del y que para con una un por es en su sus al se usted "
              "no lo como más este esta "
              "total fecha importe nombre apellidos número dirección teléfono firma "
              "pago gracias iva precio cantidad descripción notas día semana mes año "
              "lunes martes miércoles jueves viernes sábado domingo enero febrero "
              "marzo abril mayo junio julio agosto septiembre octubre noviembre "
              "diciembre".split()),
    "pt": set("o os as do da dos das e que para com uma um por em no na nos nas não "
              "você seu sua ao à é são mais este esta "
              "total data valor nome número endereço telefone assinatura pagamento "
              "obrigado obrigada iva preço quantidade descrição notas dia semana mês "
              "ano segunda terça quarta quinta sexta sábado domingo janeiro "
              "fevereiro março abril maio junho julho agosto setembro outubro "
              "novembro dezembro".split()),
}
"""Each language's common words: function words, the labels documents
print, weekdays and months. A word on two lists counts half to each."""

_MONTHS = ("january february march april may june july august september october "
           "november december jan feb mar apr jun jul aug sep sept oct nov dec "
           "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre "
           "ottobre novembre dicembre janvier février mars avril mai juin juillet "
           "août septembre octobre novembre décembre enero febrero marzo abril mayo "
           "junio julio agosto septiembre octubre noviembre diciembre janeiro "
           "fevereiro março abril maio junho julho agosto setembro outubro "
           "novembro dezembro").split()

FORMATS: dict[str, re.Pattern[str]] = {
    "fmt.eu_numbers": re.compile(r"\b\d{1,3}(?:[.   ]\d{3})+,\d{1,2}\b|\b\d+,\d{2}\b"),
    "fmt.dates": re.compile(
        r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|"
        r"\b\d{1,2}(?:st|nd|rd|th|º|°)?\.?\s+(?:de\s+)?(?:" + "|".join(_MONTHS) + r")\b|"
        r"\b(?:" + "|".join(_MONTHS) + r")\.?\s+\d{1,2}\b", re.IGNORECASE),
    "fmt.currency": re.compile(r"[€$£]\s?\d|\d\s?[€$£]|\b(?:EUR|USD|GBP|BRL|CHF)\b|R\$"),
}

_EXTERNAL = [
    (re.compile(r"""\b(?:src|href|srcset|poster|data|action|background)\s*=\s*["']?\s*(?:https?:)?//""",
                re.IGNORECASE), "a URL in an attribute"),
    (re.compile(r"@import", re.IGNORECASE), "@import"),
    (re.compile(r"@font-face", re.IGNORECASE), "@font-face"),
    (re.compile(r"""url\(\s*(?!["']?\s*(?:data:|#))""", re.IGNORECASE), "url() not data: or #"),
    (re.compile(r"<\s*(?:link|script|iframe|object|embed|base|video|audio)\b", re.IGNORECASE),
     "an element that loads or runs something"),
    (re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']?(?!data:)""", re.IGNORECASE), "an <img> not data:"),
]

_WINDOW = [
    (re.compile(r"\d(?:vh|vmin|vmax|dvh|svh|lvh)\b", re.IGNORECASE), "a viewport-height unit"),
    (re.compile(r"position\s*:\s*(?:fixed|sticky)", re.IGNORECASE), "fixed or sticky positioning"),
]
"""Layout that depends on the window. `project()` measures in a 3000 px
window and the screenshot is taken in one as tall as the page, so a page
using these is laid out differently in the two and its picture is not the
page that was measured."""


@dataclass
class Result:
    """What the validator found on one page."""

    id: str
    failures: dict[str, list[str]] = field(default_factory=dict)
    detected: list[str] = field(default_factory=list)
    height: int = 0
    words: int = 0
    dhash: str = ""
    seconds: float = 0.0
    picture: Path | None = None

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, check: str, message: str) -> None:
        self.failures.setdefault(check, []).append(message)


def _stack(family: str) -> list[str]:
    return [part.strip().strip("\"'") for part in family.split(",") if part.strip()]


def face_problems(stacks: Iterable[str], allowed: dict[str, fonts.Face]) -> list[str]:
    """Each font stack that leads with a face not on the list, or names one."""
    found = []
    for family in sorted(set(stacks)):
        names = _stack(family)
        if not names:
            continue
        if names[0] not in allowed and names[0] not in GENERIC_FIRST:
            found.append(f"leads with {names[0]!r}")
        for name in names[1:]:
            if name not in allowed and name not in fonts.GENERIC:
                found.append(f"names {name!r} in {family}")
    return sorted(set(found))


def main_class(texts: list[dict[str, Any]], allowed: dict[str, fonts.Face]) -> str | None:
    """The class of the face that sets the most characters."""
    weight: dict[str, int] = {}
    for item in texts:
        names = _stack(item["family"])
        if not names:
            continue
        head = names[0]
        cls = allowed[head].cls if head in allowed else GENERIC_FIRST.get(head)
        if cls:
            weight[cls] = weight.get(cls, 0) + len(item["text"])
    return max(weight, key=lambda k: weight[k]) if weight else None


def ink_failures(image: npt.NDArray[np.uint8], texts: list[dict[str, Any]]) -> list[str]:
    """Each text line box with too little ink under it, by its text."""
    found = []
    height, width = image.shape[:2]
    for item in texts:
        for left, top, right, bottom in item["rects"]:
            x0, y0 = max(0, int(np.floor(left))), max(0, int(np.floor(top)))
            x1, y1 = min(width, int(np.ceil(right))), min(height, int(np.ceil(bottom)))
            if x1 <= x0 or y1 <= y0:
                found.append(f"{item['text'][:40]!r} lies off the picture")
                continue
            crop = image[y0:y1, x0:x1].reshape(-1, 3).astype(int)
            colours, counts = np.unique(crop, axis=0, return_counts=True)
            ground = colours[int(np.argmax(counts))]
            ink = int((np.abs(crop - ground).max(axis=1) > INK_DIFF).sum())
            if ink < max(INK_MIN_PX, INK_MIN_SHARE * crop.shape[0]):
                found.append(f"{item['text'][:40]!r} has {ink} ink pixels at "
                             f"{x0},{y0}-{x1},{y1}")
    return found


def language_scores(text: str) -> dict[str, float]:
    words = re.findall(r"[^\W\d_]+", text.casefold())
    owners: dict[str, list[str]] = {}
    for lang, vocabulary in STOPWORDS.items():
        for word in vocabulary:
            owners.setdefault(word, []).append(lang)
    scores = {lang: 0.0 for lang in STOPWORDS}
    for word in words:
        for lang in owners.get(word, ()):
            scores[lang] += 1.0 / len(owners[word])
    return scores


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script", "head", "title"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head", "title") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_text(source: str) -> str:
    """The words of a page, read from its HTML without a browser."""
    parser = _Text()
    parser.feed(source)
    return html_lib.unescape(" ".join(parser.parts))


def shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[i:i + SHINGLE]) for i in range(max(0, len(words) - SHINGLE + 1))}


def jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def dhash(path: Path) -> str:
    """A 64-bit difference hash of a picture, as hex."""
    small = np.asarray(Image.open(path).convert("L").resize((9, 8), Image.Resampling.LANCZOS),
                       dtype=int)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hash_distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def detect(probe: dict[str, Any], text: str, main: str | None, dark: bool) -> list[str]:
    """The §F auto-checkable features the page shows, whatever its card."""
    found: set[str] = set()
    if probe["tables"]:
        found.add("table")
    if any(t["spans"] for t in probe["tables"]):
        found.add("table.spanning")
    if any(t["empty"] for t in probe["tables"]):
        found.add("table.empty_cells")
    if any(t["rows"] >= LONG_TABLE for t in probe["tables"]):
        found.add("table.long")
    tags = {item["tag"] for item in probe["lists"]}
    if "UL" in tags:
        found.add("list.bullets")
    if "OL" in tags:
        found.add("list.numbers")
    if any(item["nested"] for item in probe["lists"]):
        found.add("list.nested")
    if probe["justified"]:
        found.add("text.justified")
    if probe["sup"]:
        found.add("text.supsub")
    if probe["blockquote"]:
        found.add("text.quote")
    if main in ("serif", "sans", "mono"):
        found.add(f"type.{main}")
    if dark:
        found.add("look.dark_ground")
    if probe["svg"] or probe["img"] or probe["canvas"]:
        found.add("figure")
    for fid, pattern in FORMATS.items():
        if pattern.search(text):
            found.add(fid)
    return sorted(found)


def _wanted(fid: str, detected: set[str]) -> bool | None:
    """Whether the page shows `fid`, or None when no check can tell."""
    if fid in ("table.spanning", "table.empty_cells", "table.long"):
        return fid in detected
    if fid.startswith("table."):
        return "table" in detected
    if fid in ("list.bullets", "list.numbers", "list.nested", "text.justified",
               "text.supsub", "text.quote", "look.dark_ground") or fid.startswith("fmt."):
        return fid in detected
    if fid.startswith("fig."):
        return "figure" in detected
    return None


@dataclass(frozen=True)
class Known:
    """An accepted page the near-duplicate check compares against."""

    id: str
    shingles: frozenset[tuple[str, ...]]
    dhash: str


def known_pages(entries: Iterable[tuple[str, Path, Path]]) -> list[Known]:
    """`(id, html, png)` for every accepted page, read for check 10."""
    found = []
    for page_id, html_path, png_path in entries:
        if html_path.exists() and png_path.exists():
            found.append(Known(page_id, frozenset(shingles(html_text(
                html_path.read_text(encoding="utf-8", errors="replace")))), dhash(png_path)))
    return found


def _shoot(source: str, width: int, height: int, target: Path) -> npt.NDArray[np.uint8]:
    projection.screenshot(source, target, width=width, height=height)
    return np.asarray(Image.open(target).convert("RGB"))


def check(card: Card, html_path: Path, allowed: dict[str, fonts.Face],
          known: list[Known], *, twin: bool = False, picture: Path | None = None
          ) -> Result:
    """Run §V on one page. Its screenshot is left in `Result.picture`, in a
    temporary directory the caller moves or discards. A twin's `picture`
    is the PDF's render, and checks 1–4 are §P's gate's."""
    started = time.monotonic()
    result = Result(id=card.id)
    source = html_path.read_text(encoding="utf-8")
    assert card.width
    width = card.width

    # 5: self-contained, read from the source before any browser runs it.
    scanned = re.sub(r"""\sxmlns(?::\w+)?\s*=\s*["'][^"']*["']""", " ", source)
    for pattern, what in _EXTERNAL:
        if pattern.search(scanned):
            result.fail("self_contained", what)
    for pattern, what in _WINDOW:
        if pattern.search(scanned):
            result.fail("fits", what)
    if not re.search(r"<!doctype html>", source, re.IGNORECASE):
        result.fail("self_contained", "no <!doctype html>")
    if not re.search(r"<meta\s+charset=[\"']?utf-8", source, re.IGNORECASE):
        result.fail("self_contained", "no <meta charset=utf-8>")
    lang = re.search(r"<html[^>]*\blang=[\"']?([a-zA-Z-]+)", source)
    if not lang or lang.group(1).split("-")[0].lower() != card.language:
        result.fail("self_contained", f"<html lang> is not {card.language}")

    page = projection.project(source, width=width)
    result.height = page.height
    probe: dict[str, Any] = browser.evaluate(source, _PROBE, width=width)
    texts = probe["texts"]
    text = " ".join(run.text for run in page.runs)
    result.words = len(re.findall(r"\w+", text))

    for problem in face_problems((item["family"] for item in texts), allowed):
        result.fail("self_contained", problem)

    work = Path(tempfile.mkdtemp(prefix=f"corpus-{card.id}-"))
    if not twin:
        # 1: it renders, one page tall.
        if page.height > MAX_HEIGHT:
            result.fail("renders", f"{page.height} px tall, over {MAX_HEIGHT}")
        if not page.runs:
            result.fail("renders", "no text at all")
        first = _shoot(source, width, page.height, work / "page.png")
        result.picture = work / "page.png"
        # 2: the picture is its own HTML.
        second = _shoot(source, width, page.height, work / "again.png")
        if first.shape != second.shape:
            result.fail("own_picture", f"two shoots {first.shape} and {second.shape}")
        else:
            rows = np.flatnonzero((np.abs(first.astype(int) - second.astype(int)) > 8)
                                  .any(axis=2).any(axis=1))
            if rows.size:
                result.fail("own_picture", f"two shoots differ on rows {rows.min()}-{rows.max()}")
        # 3: nothing clipped, nothing overflowing, nothing off the page.
        if page.clipped:
            result.fail("fits", f"{page.clipped} elements clip their content")
        if probe["width"] != width or page.width != width:
            result.fail("fits", f"the page is {probe['width']} px wide, not {width}")
        for item in texts:
            for left, top, right, bottom in item["rects"]:
                if left < -0.5 or top < -0.5 or right > width + 0.5 or bottom > page.height + 0.5:
                    result.fail("fits", f"{item['text'][:40]!r} lies outside the page")
                    break
        # 4: every word has ink under it, at a size a reader can read.
        for item in texts:
            if item["size"] < MIN_TYPE_PX and item["rects"]:
                result.fail("ink", f"{item['text'][:40]!r} is set at {item['size']:.1f} px")
        for item in texts:
            if not item["rects"] or not item["visible"]:
                result.fail("ink", f"{item['text'][:40]!r} is in the DOM and not drawn")
        for problem in ink_failures(first, [t for t in texts if t["rects"]]):
            result.fail("ink", problem)
        image = first
    else:
        assert picture is not None
        result.picture = picture
        image = np.asarray(Image.open(picture).convert("RGB"))

    # 6: no words inside figures.
    for item in texts:
        if item["in_figure"]:
            result.fail("figures", f"{item['text'][:40]!r} is inside a figure")
    for src in probe["img"]:
        if not src.startswith("data:"):
            result.fail("figures", f"an <img> whose source is {src!r}")

    # 7: no generated text.
    if probe["hyphenated"]:
        result.fail("generated", f"{probe['hyphenated']} elements hyphenate automatically")
    if probe["controls"]:
        result.fail("generated", f"{probe['controls']} form controls or disclosure widgets")
    for item in probe["generated"]:
        result.fail("generated", f"{item['tag'].lower()}{item['pseudo']} draws {item['content'][:30]}")
    for item in probe["lists"]:
        if item["tag"] == "OL" and item["marker"] != "none":
            result.fail("generated", f"an <ol> numbers itself ({item['marker']})")
        elif item["marker"] not in PLAIN_MARKERS:
            result.fail("generated", f"a {item['tag'].lower()} marked {item['marker']}")

    # 8: the card's features.
    luminance = (image[..., :3] @ np.array([0.2126, 0.7152, 0.0722])) / 255.0
    main = main_class(texts, allowed)
    result.detected = detect(probe, text, main, float(np.median(luminance)) < DARK_GROUND)
    detected = set(result.detected)
    for fid in card.all_features():
        if _wanted(fid, detected) is False:
            result.fail("features", f"{fid} is on the card and not on the page")
    if card.type and main and f"type.{main}" != card.type:
        result.fail("features", f"the main face is {main}, the card asks {card.type}")
    if not twin and result.words < word_floor(card):
        result.fail("features", f"{result.words} words; a {card.density} page "
                                f"{card.width} px wide holds at least {word_floor(card)}")

    # 9: the language.
    scores = language_scores(text)
    leader = max(scores, key=lambda lang: scores[lang])
    floor = (LANGUAGE_MIN if result.words >= LANGUAGE_SHORT
             else 1.0 if card.language != "en" else 0.0)
    if (scores[card.language] < floor
            or scores[leader] - scores[card.language] >= LANGUAGE_MARGIN):
        shown = ", ".join(f"{lang} {score:.1f}" for lang, score in sorted(scores.items()))
        result.fail("language", f"reads as {leader}, not {card.language} ({shown})")

    # 10: not a near-duplicate.
    own = shingles(html_text(source))
    result.dhash = dhash(result.picture)
    for other in known:
        if other.id == card.id:
            continue
        overlap = jaccard(own, set(other.shingles))
        if overlap >= JACCARD_MAX:
            result.fail("distinct", f"shares {overlap:.2f} of its shingles with {other.id}")
        distance = hash_distance(result.dhash, other.dhash)
        if distance <= HASH_NEAR:
            result.fail("distinct", f"its picture is {distance} bits from {other.id}'s")

    result.seconds = round(time.monotonic() - started, 1)
    return result


def record(result: Result, card: Card, html_path: Path, png_path: Path) -> dict[str, Any]:
    """What `corpus/checks/<id>.json` keeps of a passed page."""
    return {
        "id": result.id, "passed": result.passed, "failures": result.failures,
        "checked": date.today().isoformat(), "seconds": result.seconds,
        "width": card.width, "height": result.height, "words": result.words,
        "card_features": list(card.all_features()), "detected": result.detected,
        "dhash": result.dhash,
        "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
        "png_sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
    }


def keep(result: Result, card: Card, html_path: Path, png_path: Path, record_path: Path
         ) -> None:
    """Move a passed page's picture into place and write its record."""
    assert result.passed and result.picture
    png_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result.picture, png_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    partial = record_path.with_suffix(".partial")
    partial.write_text(json.dumps(record(result, card, html_path, png_path),
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    partial.replace(record_path)


PROBE_PAGES = ("contract", "datasheet", "email", "flyer", "labreport", "minutes",
               "nutrition", "payslip", "quiz", "recipe")
"""The ten probe pages of 2026-10-24, in `docs/level-up-probe/src/`."""


def known_in(repo: Path) -> list[Known]:
    """Every page check 10 compares against: the 21, the ten probe pages,
    and every corpus page with a passed record. A record's hash is read
    from it rather than from the picture again."""
    from doc_to_html import corpus

    entries = [(name, source.html_path(repo), source.png_path(repo))
               for name, source in corpus.SOURCES.items()]
    entries += [(f"probe_{name}", repo / "docs/level-up-probe/src" / f"{name}.html",
                 repo / "docs/level-up-probe/src" / f"{name}.png") for name in PROBE_PAGES]
    found = known_pages(entries)
    for path in sorted((repo / "corpus" / "checks").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # another writer's record, half written
        page = repo / "corpus" / "pages" / f"{data['id']}.html"
        if data.get("passed") and page.exists():
            found.append(Known(data["id"], frozenset(shingles(html_text(
                page.read_text(encoding="utf-8")))), data["dhash"]))
    return found


def keep_twin(result: Result, card: Card, html_path: Path, png_path: Path,
              record_path: Path, gate: dict[str, Any]) -> None:
    """Write a gated twin's record. Its picture is the PDF's render, already
    in place, and is not touched."""
    assert result.passed
    data = record(result, card, html_path, png_path)
    data["gate"] = gate
    record_path.parent.mkdir(parents=True, exist_ok=True)
    partial = record_path.with_suffix(".partial")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    partial.replace(record_path)
