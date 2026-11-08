"""The corpus manifest, its pools and the sealed vault — spec 0020, step 6.

Every page's files are where the manifest says and unchanged since it
was written; the pools are the seeded deal of `cards.json`, with the 31
known pages in dev; the vault refuses unless unsealed; and a fixed
sample of the generated pages' pictures are fresh screenshots of their
HTML. The whole corpus's pictures are checked by
`tools/corpus_check.py --all --dry`, too slow for the suite.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import pytest

from doc_to_html import corpus, projection
from doc_to_html.factory import cards, pools

REPO = Path(__file__).resolve().parent.parent
TAXONOMY = cards.load_taxonomy(REPO / "corpus" / "taxonomy.json")

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

PAGES = corpus.manifest()
KNOWN = [card["id"] for card in
         json.loads((REPO / "corpus" / "known.json").read_text(encoding="utf-8"))["cards"]]
SAMPLE = sorted(random.Random(20261029).sample(
    sorted(i for i, e in PAGES.items() if e["origin"] == "generated"), 60))
"""Sixty generated pages, fixed: their pictures are re-shot in the suite."""


def test_every_page_s_files_are_there_and_unchanged() -> None:
    assert len(PAGES) == 631
    for page_id, entry in PAGES.items():
        for kind, path in entry["files"].items():
            digest = hashlib.sha256((REPO / path).read_bytes()).hexdigest()
            assert digest == entry["sha256"][kind], f"{page_id}: {path} changed"


def test_every_page_passed_the_validator_as_it_now_is() -> None:
    """A page edited after its last validator run has a record about
    another file. Two writers stopped mid-loop left one each (c0042,
    c0268), found by the re-shoot below; both were re-run and passed."""
    for page_id, entry in PAGES.items():
        if entry["origin"] not in ("generated", "pdf"):
            continue
        record = json.loads((REPO / "corpus" / "checks" / f"{page_id}.json").read_text())
        assert record["passed"], page_id
        assert record["html_sha256"] == entry["sha256"]["html"], page_id
        assert record["png_sha256"] == entry["sha256"]["png"], page_id


def test_the_pools_are_the_seeded_deal_with_the_known_pages_in_dev() -> None:
    seed, drawn = cards.load(REPO / "corpus" / "cards.json")
    dealt = pools.deal(TAXONOMY, drawn, seed)
    assert {i: PAGES[i]["pool"] for i in dealt} == dealt
    assert all(PAGES[i]["pool"] == "dev" for i in KNOWN) and len(KNOWN) == 31
    assert Counter(e["pool"] for e in PAGES.values()) == {"dev": 231, "panel": 200,
                                                          "vault": 200}
    assert corpus.names("dev") == corpus.pool("dev")
    assert len(corpus.names("panel")) == 200


def test_the_vault_refuses_unless_unsealed() -> None:
    with pytest.raises(corpus.SealedError):
        corpus.names("vault")
    with pytest.raises(corpus.SealedError):
        corpus.pool("vault")
    assert len(corpus.pool("vault", unseal=True)) == 200


def test_the_l3_set_is_forty_one_panel_pages() -> None:
    # the cover's 36, then the panel's five PDF pages that are not dense (spec 0022)
    l3 = corpus.names("l3")
    assert len(l3) == 41 and all(PAGES[i]["pool"] == "panel" for i in l3)
    assert sum(PAGES[i]["origin"] == "pdf" for i in l3) == 5
    seed, drawn = cards.load(REPO / "corpus" / "cards.json")
    assert list(l3) == pools.l3_subset(TAXONOMY, drawn, pools.deal(TAXONOMY, drawn, seed), seed)


def test_a_page_is_found_by_its_name() -> None:
    assert corpus.page("invoice_0001") is corpus.SOURCES["invoice_0001"]
    found = corpus.page(SAMPLE[0])
    assert found.html_path().exists() and found.png_path().exists()
    assert corpus.names("sweep") == corpus.SWEEP


@needs_chrome
@pytest.mark.parametrize("page_id", SAMPLE)
def test_the_picture_is_a_fresh_screenshot_of_the_html(page_id: str, tmp_path: Path) -> None:
    """`TestTheCorpusPictureIsItsOwnHTML`'s check, on a fixed sample of
    the generated pages: equality, not similarity."""
    import numpy as np
    from PIL import Image

    source = corpus.page(page_id)
    committed = np.asarray(Image.open(source.png_path()).convert("RGB"))
    fresh = tmp_path / f"{page_id}.png"
    projection.screenshot(source.html_path().read_text(encoding="utf-8"), fresh,
                          width=committed.shape[1], height=committed.shape[0])
    shot = np.asarray(Image.open(fresh).convert("RGB"))
    assert shot.shape == committed.shape
    differs = (np.abs(shot.astype(int) - committed.astype(int)) > 8).any(axis=2)
    rows = np.flatnonzero(differs.any(axis=1))
    assert not rows.size, f"{page_id}: rows {rows.min()}-{rows.max()} differ"
