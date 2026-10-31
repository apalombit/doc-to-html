"""Spec 0021, step 1: the reading the checks are built on.

`project(..., detail=True)` adds every printed word with its box, each
table by slot with the borders that could draw a rule, each list with its
markers, and the boxes each block's lines can sit in. Two things are pinned
here: that the rest of the payload is the same with or without it, so no
score moves, and that each part reads what a reader sees — on small pages
written to isolate one thing, and on real dev pages carrying the feature.
"""

from __future__ import annotations

import dataclasses
import random
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

from doc_to_html import corpus, projection
from doc_to_html.projection import project
from doc_to_html.scoring import tokens

REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "docs" / "level-up-probe"

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)


def page(body: str, style: str = "") -> str:
    return ("<!doctype html><html><head><style>body{margin:20px;font:16px Georgia, serif}"
            f"{style}</style></head><body>{body}</body></html>")


def read(html: str, width: int = 700) -> projection.Detail:
    detail = project(html, width=width, detail=True).detail
    assert detail is not None
    return detail


def dev_pages(feature: str, count: int, seed: int = 20261030) -> list[str]:
    """`count` dev pages carrying `feature`, drawn by seed."""
    manifest = corpus.manifest()
    carrying = sorted(page_id for page_id in corpus.names("dev")
                      if feature in (manifest[page_id].get("features") or ()))
    return random.Random(f"{seed}:{feature}").sample(carrying, min(count, len(carrying)))


def read_page(page_id: str) -> projection.Projection:
    source = corpus.page(page_id)
    width = Image.open(source.png_path()).width
    return project(source.html_path(), width=width, flat=True, detail=True)


class TestTheScoredPayloadIsUnchanged:
    @needs_chrome
    @pytest.mark.parametrize("page_id", ["invoice_0001", "timetable_0019", "probe_quiz"])
    def test_detail_adds_and_moves_nothing(self, page_id: str) -> None:
        """Every field the scorer reads is the same with the reading as
        without it: the reading is computed after everything else, in the
        same pass."""
        source = corpus.page(page_id)
        width = Image.open(source.png_path()).width
        plain = project(source.html_path(), width=width, flat=True)
        rich = project(source.html_path(), width=width, flat=True, detail=True)
        assert plain.detail is None and rich.detail is not None
        assert dataclasses.replace(rich, detail=None) == plain


class TestWords:
    @needs_chrome
    def test_every_scored_token_is_a_word_with_a_box(self) -> None:
        detail = read(page("<p>Invoice #: 123 <b>paid</b> on 24/10/2026</p>"))
        assert [word.text for word in detail.words] == \
            ["Invoice", "#:", "123", "paid", "on", "24/10/2026"]
        assert all(word.rect[2] > word.rect[0] for word in detail.words)
        assert [word.weight for word in detail.words][3] >= 600

    @needs_chrome
    @pytest.mark.parametrize("page_id", ["c0008", "probe_labreport", "nonlatin_0014"])
    def test_words_hold_the_runs_tokens_exactly(self, page_id: str) -> None:
        """A word is cut on white space inside a text node, so its tokens are
        the scorer's tokens, one for one."""
        page_ = read_page(page_id)
        assert page_.detail is not None
        assert Counter(t for run in page_.runs for t in tokens(run.text)) == \
            Counter(t for word in page_.detail.words for t in tokens(word.text))


class TestTables:
    @needs_chrome
    def test_spans_fill_their_slots(self) -> None:
        detail = read(page(
            "<table><tr><td rowspan=2>a</td><td colspan=2>b</td></tr>"
            "<tr><td>c</td><td>d</td></tr></table>"))
        table = detail.tables[0]
        assert (table.rows, table.cols) == (2, 3)
        assert [table.cells[table.slot(1, c)].text for c in range(3)] == ["a", "c", "d"]
        assert table.slot(0, 2) == table.slot(0, 1)

    @needs_chrome
    def test_a_ruled_grid_draws_every_inner_rule(self) -> None:
        detail = read(page("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>",
                           "table{border-collapse:collapse} td{border:1px solid #111}"))
        table = detail.tables[0]
        assert all(table.vertical_rule(r, c) for r in range(2) for c in range(3))
        assert all(table.horizontal_rule(r, c) for r in range(3) for c in range(2))

    @needs_chrome
    def test_a_row_border_draws_only_when_borders_collapse(self) -> None:
        body = "<table><tr style='border-bottom:2px solid #000'><td>a</td></tr><tr><td>b</td></tr></table>"
        collapsed = read(page(body, "table{border-collapse:collapse}")).tables[0]
        separate = read(page(body, "table{border-collapse:separate}")).tables[0]
        assert collapsed.horizontal_rule(1, 0)
        assert not separate.horizontal_rule(1, 0)

    @needs_chrome
    def test_a_rule_the_ground_hides_is_not_drawn(self) -> None:
        table = read(page("<table><tr><td>a</td><td style='border-left:1px solid #fff'>b</td></tr></table>",
                          "table{border-collapse:collapse}")).tables[0]
        assert not table.vertical_rule(0, 1)

    @needs_chrome
    def test_a_box_hugging_the_table_draws_its_frame(self) -> None:
        """The quiz's render frames its table with the Zone's border, two
        wrappers up; a bordered box far from the table is not its frame."""
        body = "<section style='{0}'><div><table><tr><td>a</td><td>b</td></tr></table></div></section>"
        hugged = read(page(body.format("border:1px solid #111"), "table{width:100%}")).tables[0]
        assert hugged.vertical_rule(0, 0) and hugged.vertical_rule(0, 2)
        assert hugged.horizontal_rule(0, 0) and hugged.horizontal_rule(1, 1)
        assert not hugged.vertical_rule(0, 1)
        distant = read(page(body.format("border:1px solid #111;padding:30px"),
                            "table{width:100%}")).tables[0]
        assert not distant.vertical_rule(0, 0) and not distant.horizontal_rule(1, 1)

    @needs_chrome
    def test_a_spanning_cell_has_no_rule_inside_it(self) -> None:
        table = read(page("<table><tr><td colspan=2>wide</td></tr><tr><td>a</td><td>b</td></tr></table>",
                          "table{border-collapse:collapse} td{border:1px solid #000}")).tables[0]
        assert not table.vertical_rule(0, 1)
        assert table.vertical_rule(1, 1)

    @needs_chrome
    def test_the_quiz_output_loses_four_inner_rules(self) -> None:
        """The probe's quiz: the output keeps the source's grid and leaves
        out four of the six rules between body cells (spec 0021's facts)."""
        source = project(PROBE / "src" / "quiz.html", width=860, flat=True, detail=True)
        output = project(PROBE / "out" / "quiz" / "render.html", width=860, detail=True)
        assert source.detail is not None and output.detail is not None
        (mine,), (theirs,) = source.detail.tables, output.detail.tables
        assert (mine.rows, mine.cols) == (theirs.rows, theirs.cols) == (4, 3)
        inner = [(r, c) for r in range(1, 4) for c in (1, 2)]
        assert all(mine.vertical_rule(r, c) for r, c in inner)
        assert sorted((r, c) for r, c in inner if not theirs.vertical_rule(r, c)) == \
            [(1, 1), (2, 2), (3, 1), (3, 2)]


class TestLists:
    @needs_chrome
    def test_markers(self) -> None:
        detail = read(page(
            "<ol><li>one</li></ol><ul><li>dot</li></ul>"
            "<ul class=t><li>ticked</li></ul><ol class=c><li>counted</li></ol>"
            "<ul class=d><li>drawn dot</li></ul><ul class=n><li>1. typed</li></ul>",
            "ul.t,ol.c,ul.d,ul.n{list-style:none}"
            "ul.t li::before{content:'\\2713  '}"
            "ol.c{counter-reset:s} ol.c li::before{counter-increment:s;content:counter(s) '. '}"
            "ul.d li::before{content:'';display:inline-block;width:6px;height:6px;background:#000}"))
        markers = [(group.items[0].marker, group.items[0].numbered_text) for group in detail.lists]
        assert markers == [("number", False), ("bullet", False), ("tick", False),
                           ("number", False), ("bullet", False), ("none", True)]

    @needs_chrome
    def test_numbers_and_ticks_printed_as_text(self) -> None:
        """Most of the corpus prints a list's numbers and ticks as text: a
        number in its own span straight before the item's first word, a
        tick box glyph before it. A letter opening a word is not a number."""
        detail = read(page(
            "<ol style='list-style:none'><li><span>1</span>What is your main activity?</li></ol>"
            "<ul style='list-style:none'><li>\u2611 Full forum pass</li></ul>"
            "<ul style='list-style:none'><li>about the venue</li></ul>"))
        assert [(group.items[0].numbered_text, group.items[0].ticked_text)
                for group in detail.lists] == [(True, False), (False, True), (False, False)]

    @needs_chrome
    @pytest.mark.parametrize("feature, numbered", [("list.numbers", True), ("list.ticks", False)])
    def test_dev_pages_read_their_numbers_and_ticks(self, feature: str, numbered: bool) -> None:
        """Measured over every dev page carrying the feature, 2026-10-30:
        numbers on 32 of 33, ticks on 24 of 32 (`ListItem`'s docstrings).
        Five drawn by seed must each read some."""
        for page_id in dev_pages(feature, 5):
            if page_id in ("c0039", "c0068", "c0075", "c0105", "c0191",
                           "c0197", "c0198", "c0202", "c0429"):
                continue
            detail = read_page(page_id).detail
            assert detail is not None
            items = [item for group in detail.lists for item in group.items]
            if numbered:
                assert any(item.marker == "number" or item.numbered_text for item in items), page_id
            else:
                assert any(item.marker == "tick" or item.ticked_text for item in items), page_id

    @needs_chrome
    def test_a_word_knows_its_item(self) -> None:
        detail = read(page("<ul><li>alpha</li><li>beta <b>gamma</b></li></ul>"))
        assert [(word.text, word.item) for word in detail.words] == \
            [("alpha", (0, 0)), ("beta", (0, 1)), ("gamma", (0, 1))]


class TestFacesFramesUnread:
    @needs_chrome
    def test_the_face_drawn_is_the_first_that_resolves(self) -> None:
        detail = read(page("<p style=\"font-family:'No Such Face 0021', Menlo, monospace\">code</p>"
                           "<p>serif</p>"))
        assert [(word.family, word.mono) for word in detail.words] == \
            [("Menlo", True), ("Georgia", False)]

    @needs_chrome
    def test_a_cells_frame_is_wider_than_its_number(self) -> None:
        detail = read(page("<table style='width:400px'><tr><td style='text-align:right'>12.50</td></tr></table>"))
        (word,) = detail.words
        frames = detail.frames[word.block]
        assert frames.align == "right"
        assert frames.chain[0][2] - frames.chain[0][0] > word.rect[2] - word.rect[0] + 100

    @needs_chrome
    def test_unread_marks_are_counted(self) -> None:
        assert read(page("<p><span class=disputed data-alt='x'>NP-2291</span> ok</p>")).unread == 1
