"""The brief every writer is given — spec 0020 §B.

It quotes the font allow-list and the feature notes. These hold it to the
files it quotes, so a face added to `fonts.json` or a feature to
`taxonomy.json` cannot leave the writers' copy behind.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from doc_to_html.factory import cards, fonts

REPO = Path(__file__).resolve().parent.parent
BRIEF = (REPO / "corpus" / "brief.md").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    return BRIEF[BRIEF.index(start) + len(start):BRIEF.index(end)]


def test_the_brief_lists_exactly_the_allowed_faces_by_class() -> None:
    listed = fonts.load(REPO / "corpus" / "fonts.json")
    section = _between("<!-- faces:begin -->", "<!-- faces:end -->")
    for cls in fonts.CLASSES:
        line = re.search(rf"\*\*{cls}:\*\* (.+)", section)
        assert line, cls
        named = [name.strip() for name in line.group(1).split(",")]
        assert sorted(named) == sorted(f for f, face in listed.items() if face.cls == cls), cls


def test_the_brief_explains_every_feature_as_the_taxonomy_does() -> None:
    taxonomy = json.loads((REPO / "corpus" / "taxonomy.json").read_text(encoding="utf-8"))
    section = _between("<!-- features:begin -->", "<!-- features:end -->")
    rows = dict(re.findall(r"^\| `([a-z_.]+)` \| (.+) \|$", section, re.MULTILINE))
    assert list(rows) == cards.feature_ids(taxonomy)
    assert rows == taxonomy["feature_notes"]


def test_the_brief_names_every_style_family() -> None:
    taxonomy = json.loads((REPO / "corpus" / "taxonomy.json").read_text(encoding="utf-8"))
    for style in taxonomy["styles"]:
        assert f"| `{style}` |" in BRIEF, style
