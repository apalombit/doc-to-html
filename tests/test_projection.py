"""The browser mechanics the whole measure sits on.

Three of these pin faults that were found by *looking at a picture* after the
numbers said everything was fine, which is the habit spec 0007 exists to
install. Each one is silent, plausible, and corrupts both sides of a comparison
in a way no DOM-based measure can see:

- the colour scheme, which inverted every rendered page this project ever
  eyeballed;
- the 500px layout floor, which cropped a narrow document's right-hand column
  out of its own screenshot;
- the screenshot slack, which dropped the last row of a table from the PNG while
  leaving it in the DOM for `project()` to count as present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_to_html import corpus, projection
from doc_to_html.projection import MIN_WIDTH, Block, project, screenshot

REPO = Path(__file__).resolve().parent.parent
FROZEN = REPO / "tests" / "frozen" / "run84"

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

DARK_AND_LIGHT = """
<!doctype html><html><head><style>
body { background:#ffffff; color:#000000; margin:0 }
@media (prefers-color-scheme: dark) { body { background:#111111 } }
</style></head><body><p>ink</p></body></html>
"""


class TestTheBrowserIsPinnedWhereItMatters:
    @needs_chrome
    def test_the_page_is_measured_in_light_mode(self) -> None:
        """Headless Chrome here inherits the host's dark mode by default.

        Which means `render.py`'s `@media (prefers-color-scheme: dark)` fired
        on every rendered page this project produced, and every visual
        comparison before 2026-09-18 was an inverted page beside a light
        Source Image. Both sides now go through the same pinned flag.
        """
        page = project(DARK_AND_LIGHT, width=600)
        assert page.body_background == "rgb(255, 255, 255)"

    @needs_chrome
    def test_a_width_below_the_floor_is_reported_rather_than_obeyed(
        self, tmp_path: Path
    ) -> None:
        """Asked for 340, the browser lays out at 500 and crops the picture.

        Which put every price of `receipt_0010` off the right edge of a
        screenshot that still claimed to be the document. It cannot be
        prevented, so it is said out loud instead.
        """
        page = project(DARK_AND_LIGHT, width=340)
        assert page.width == MIN_WIDTH
        assert page.notes and "500" in page.notes[0]

    @needs_chrome
    def test_the_last_row_survives_a_screenshot_at_the_exact_page_height(
        self, tmp_path: Path
    ) -> None:
        """Chrome renders the final row blank when the window is exactly as
        tall as the page.

        Measured on `invoice_0001`: at `--window-size=862,640` against a page
        the browser itself reports as 640 tall, the `Total: $385.00` row came
        back with zero dark pixels; at 700 and at 900 it is there. `project()`
        reports that row at y 551-569 either way, so T1 counts its text as
        present while the picture does not contain it — two tiers disagreeing
        about whether content exists, arriving from the tooling.
        """
        import numpy as np
        from PIL import Image

        source = FROZEN / "invoice_0001.html"
        page = project(source, width=862)
        total = [run for run in page.runs if "385.00" in run.text]
        assert total, "the document should contain the total"
        top, bottom = int(total[0].rect[1]), int(total[0].rect[3])

        shot = tmp_path / "render.png"
        screenshot(source, shot, width=862, height=page.height)
        image = Image.open(shot)
        assert image.size == (862, page.height), "the PNG must still be the page"

        band = np.asarray(image.convert("L"))[top:bottom + 1, 600:862]
        assert int((band < 128).sum()) > 50, (
            "the last row is in the DOM but not in the pixels"
        )

    @needs_chrome
    def test_a_page_with_a_large_table_is_projected(self) -> None:
        """The payload is encoded in chunks: spreading every byte as one
        call's arguments failed at a table of 40 rows by 8 columns."""
        rows = "".join("<tr>" + "".join(f"<td>r{r}c{c} word</td>" for c in range(10))
                       + "</tr>" for r in range(60))
        page = project(f"<!doctype html><html><body><table>{rows}</table></body></html>",
                       width=900)
        assert len(page.runs) == 600


AUTHORED = [name for name in corpus.names("sweep")
            if name not in corpus.names("iterate")]
"""The ten documents `tools/shoot_corpus.py` shot, as against the five
originals, whose pictures are historical and re-render 6.9-14.1% different."""


class TestTheCorpusPictureIsItsOwnHTML:
    @needs_chrome
    @pytest.mark.parametrize("name", AUTHORED)
    def test_the_committed_picture_is_a_fresh_screenshot_of_the_html(
        self, name: str, tmp_path: Path
    ) -> None:
        """The slack fault, found a second time, in the ground truth itself.

        `SHOT_SLACK` landed in the same commit as these ten pictures, and they
        had been shot before it: each lost its bottom 60-90px. Found
        2026-09-29 by re-shooting and diffing — footers, `form_0007`'s
        signature line, `cv_0013`'s last publication, and `receipt_0010`'s
        last three lines were in the HTML and not in the PNG. The scorer reads
        the source's words from the HTML, so 266 tokens were counted against a
        model that was never shown them, and `shoot_corpus.py --check` could
        not see it: it scores the HTML against itself.

        Re-shot the same day. Two independent shoots agreed to the pixel, so
        this asks for equality, not similarity.
        """
        import numpy as np
        from PIL import Image

        source = corpus.SOURCES[name]
        committed = np.asarray(Image.open(source.png_path(REPO)).convert("RGB"))
        fresh = tmp_path / f"{name}.png"
        screenshot(source.html_path(REPO), fresh, width=committed.shape[1])
        shot = np.asarray(Image.open(fresh).convert("RGB"))

        assert shot.shape == committed.shape
        differs = (np.abs(shot.astype(int) - committed.astype(int)) > 8).any(axis=2)
        rows = np.flatnonzero(differs.any(axis=1))
        assert not rows.size, (
            f"{source.png} is not a screenshot of {source.html}: rows "
            f"{rows.min()}-{rows.max()} differ. Re-shoot it with "
            f"`tools/shoot_corpus.py --force {name}` if the HTML was edited; "
            f"if not, find out what moved before touching the picture."
        )


class TestTheProjectionIsPerceptionRatherThanMarkup:
    @needs_chrome
    def test_a_styled_div_is_a_heading_just_as_an_h2_is(self) -> None:
        """The clause that keeps the scorer from demanding our markup match.

        A source that reaches a heading with `div.panel-title` and an output
        that reaches it with `h2.zone-title` must project identically, or the
        measure is scoring how the page was typed.
        """
        typed = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<h2>Company Details</h2></body>", width=600)
        styled = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<div style='font-size:19px;font-weight:700'>Company Details</div>"
            "</body>", width=600)
        assert [block.role for block in typed.blocks] == ["heading"]
        assert [block.role for block in styled.blocks] == ["heading"]

    @needs_chrome
    def test_an_inline_run_is_recognised_by_appearance_as_well_as_by_tag(
        self,
    ) -> None:
        """Monospace is `code` whether it arrived as `<code>` or as a class."""
        tagged = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<p>run <code>npm ci</code> first</p></body>", width=600)
        styled = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<p>run <span style='font-family:monospace'>npm ci</span> first</p>"
            "</body>", width=600)
        assert [run.inline for run in tagged.runs] == ["text", "code", "text"]
        assert [run.inline for run in styled.runs] == ["text", "code", "text"]

    @needs_chrome
    def test_a_link_is_found_by_its_underline_and_colour_too(self) -> None:
        anchored = project(
            "<!doctype html><body><p>see <a href='#'>the notes</a></p></body>",
            width=600)
        assert "link" in [run.inline for run in anchored.runs]

    @needs_chrome
    def test_our_own_findings_panel_is_not_counted_as_document_content(
        self,
    ) -> None:
        """`render.py` puts its diagnostics at the top of a page that went
        badly. Counting them would report the system's own commentary as text
        the model invented, on exactly the runs that went worst."""
        page = project(
            "<!doctype html><body>"
            '<div class="findings"><strong>Unresolved</strong>'
            "<ul><li>Probe did not reconcile</li></ul></div>"
            "<p>real content</p></body>", width=600)
        assert [block.text for block in page.blocks] == ["real content"]


class TestLineBoxes:
    @needs_chrome
    def test_a_line_split_across_inline_elements_is_still_one_line(self) -> None:
        """A code span sits at a different rect top than the text around it.

        Merging line boxes on equal tops therefore counted one visual line as
        two, and every source page with an inline code span reported hard line
        breaks it does not have.
        """
        page = project(
            "<!doctype html><body style='font:16px sans-serif;width:900px'>"
            "<p>elements like <code>&lt;article&gt;</code>, "
            "<code>&lt;section&gt;</code> and <code>&lt;nav&gt;</code></p>"
            "</body>", width=900)
        paragraph = page.blocks[0]
        assert paragraph.lines == 1
        assert paragraph.forced_breaks == 0

    @needs_chrome
    def test_explicit_breaks_are_counted_and_wrapped_lines_are_not(self) -> None:
        """Counted as elements, because the geometry cannot tell a hard break
        from a line shortened by a float — `sample_semantic_0005`'s prose runs
        beside an aside and stops at 441 of a 760px container."""
        broken = project(
            "<!doctype html><body><p>one<br>two<br>three</p></body>", width=600)
        assert broken.break_elements == 2

        wrapped = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<p style='width:300px'>" + "word " * 40 + "</p></body>", width=600)
        assert wrapped.break_elements == 0

    @needs_chrome
    def test_a_block_of_short_equal_lines_reports_them_as_forced(self) -> None:
        """The geometric signal, on the case that defeated the first attempt.

        Three address lines of roughly equal length are all within a few
        percent of each other, so none looks early against the block's own
        widest line — while every one of them is a hard break. Measured
        against the container instead.
        """
        address = project(
            "<!doctype html><body style='font:16px sans-serif'>"
            "<p style='width:600px'>Sparksuite, Inc.<br>12345 Sunny Road<br>"
            "Sunnyville, CA 12345</p></body>", width=700)
        assert address.blocks[0].forced_breaks == 2


class TestABlocksAlignment:
    def test_ink_filling_its_container_is_neither_left_nor_right(self) -> None:
        """Computed from the ink against the box, never from `text-align`."""
        from doc_to_html.scoring import _alignment

        filling = Block(index=0, role="paragraph", tag="p", text="x",
                        ink=(0.0, 0.0, 100.0, 10.0), box=(0.0, 0.0, 100.0, 10.0),
                        lines=1, font_px=16, weight=400, italic=False, mono=False,
                        color="", background="")
        right = Block(index=1, role="paragraph", tag="p", text="x",
                      ink=(70.0, 0.0, 100.0, 10.0), box=(0.0, 0.0, 100.0, 10.0),
                      lines=1, font_px=16, weight=400, italic=False, mono=False,
                      color="", background="")
        assert _alignment(filling) == "fill"
        assert _alignment(right) == "right"


class TestAValueTooLongForItsColumnWraps:
    """`section.filled` and `section.boxed` set `overflow:hidden` to keep a
    fill inside its own rounded corner, so content wider than the Zone is cut
    off in the screenshot while `project()` still reports every word of it.
    That is T1 and the pixels disagreeing about whether content exists, which
    is the failure spec 0007 warns about, arriving from the stylesheet.

    `cv_0013`'s sidebar was the corpus's one case: the `dl`'s `auto` track
    sized itself to an email address with no break opportunity and gave the
    Zone a 368px content width inside a 256px box.
    """

    def a_sidebar(self) -> object:
        """A narrow Zone, narrow the way `cv_0013`'s is — by sharing its Band.

        A lone Zone is page-wide and nothing can overflow it, so a fixture with
        one Zone tests the stylesheet against no pressure at all. Four columns
        of `flex:1 1 12rem` at `MIN_WIDTH` is what squeezes the sidebar down to
        about a quarter of the page, which is the condition the rule exists for.
        """
        from doc_to_html.ir import (BBox, Document, Kind, Pair, Source, Zone,
                                    cell)

        doc = Document(source=Source(path="x.png", sha256="0" * 64,
                                     width=900, height=900))
        sidebar = Zone(kind=Kind.PAIRS, title="Contact", complete=True,
                       fill=(38, 51, 63), band=0, column=0,
                       bbox=BBox(0.0, 0.0, 0.24, 0.9),
                       pairs=[Pair(label=cell("Email"),
                                   value=cell("ines.halloran@fempost.example"))])
        doc.zones = [sidebar] + [
            Zone(kind=Kind.PAIRS, complete=True, band=0, column=index,
                 bbox=BBox(0.25 * index, 0.0, 0.25 * index + 0.24, 0.9),
                 pairs=[Pair(label=cell("Role"), value=cell("Engineer"))])
            for index in (1, 2, 3)
        ]
        return doc

    @needs_chrome
    def test_the_long_value_is_not_hidden(self) -> None:
        from doc_to_html.render import render

        page = project(render(self.a_sidebar()), width=MIN_WIDTH)

        assert page.clipped == 0

    @needs_chrome
    def test_and_every_word_of_it_is_still_printed(self) -> None:
        """Wrapping must not be bought by dropping characters: `anywhere`
        breaks the line, it does not shorten the string."""
        from doc_to_html.render import render

        page = project(render(self.a_sidebar()), width=MIN_WIDTH)

        assert "ines.halloran@fempost.example" in " ".join(
            block.text for block in page.blocks
        )


class TestALabelWithNoValueDoesNotSizeTheLabelColumn:
    """A pairs Zone is a grid of `auto 1fr`. A pair with no value used to put
    its label in the `auto` column all the same, so the longest such label
    sized it to the whole box and the `1fr` column was left a few pixels —
    where `anywhere`, above, broke the next value after every letter.
    `catalogue_0015`'s `each` was printed one letter to a line, twice. N4.
    """

    def a_card(self) -> object:
        """`catalogue_0015`'s IR-212 card as read, one of three in its Band."""
        from doc_to_html.ir import (BBox, Document, Kind, Pair, Source, Zone,
                                    cell)

        doc = Document(source=Source(path="x.png", sha256="0" * 64,
                                     width=900, height=900))
        lines = [("IR-212", ""), ("Iron thumb latch", ""),
                 ("Suffolk pattern, 265 mm, beeswax", ""),
                 ("£28.00", "each"), ("In stock", "")]
        doc.zones = [
            Zone(kind=Kind.PAIRS, complete=True, band=0, column=index,
                 bbox=BBox(0.33 * index, 0.0, 0.33 * index + 0.3, 0.3),
                 pairs=[Pair(label=cell(label), value=cell(value))
                        for label, value in lines])
            for index in (0, 1, 2)
        ]
        return doc

    @needs_chrome
    def test_the_value_keeps_its_word_whole(self) -> None:
        from doc_to_html.render import render

        page = project(render(self.a_card()), width=MIN_WIDTH)

        each = [block for block in page.blocks if block.text == "each"]
        assert len(each) == 3
        assert all(block.lines == 1 for block in each)

    @needs_chrome
    def test_and_the_label_with_no_value_is_still_printed_whole(self) -> None:
        from doc_to_html.render import render

        page = project(render(self.a_card()), width=MIN_WIDTH)

        assert page.clipped == 0
        assert sum(block.text == "Suffolk pattern, 265 mm, beeswax"
                   for block in page.blocks) == 3


class TestTheSourceInItsPapersFrame:
    """Spec 0018, 0b — `project(flat=True)` clears a turn the page sets on
    itself before measuring. `getClientRects` returns upright boxes round
    tilted lines, which stood `ticket_0020`'s `TRD` 15px above `OSL`."""

    PAGE = ("<!doctype html><html><body style='margin:0'>"
            "<div style='width:600px; transform:{transform}'>"
            "<span style='float:left'>LEFT</span>"
            "<span style='float:right'>RIGHT</span></div></body></html>")

    def tops(self, transform: str, *, flat: bool) -> dict[str, float]:
        page = project(self.PAGE.format(transform=transform), width=700, flat=flat)
        return {run.text: run.rect[1] for run in page.runs}

    def lefts(self, transform: str, *, flat: bool) -> dict[str, float]:
        page = project(self.PAGE.format(transform=transform), width=700, flat=flat)
        return {run.text: run.rect[0] for run in page.runs}

    @needs_chrome
    def test_a_turned_page_is_measured_level(self) -> None:
        turned = self.tops("rotate(-3deg)", flat=False)
        assert abs(turned["LEFT"] - turned["RIGHT"]) > 10
        level = self.tops("rotate(-3deg)", flat=True)
        assert level["LEFT"] == level["RIGHT"]

    @needs_chrome
    def test_a_translation_stays(self) -> None:
        moved = self.lefts("translateX(40px)", flat=True)
        assert moved == self.lefts("translateX(40px)", flat=False)
        assert moved["LEFT"] == 40

    @needs_chrome
    def test_the_corpus_ticket_is_the_only_turned_source(self) -> None:
        """Every other source measures alike flat or not: `menu_0012` and
        `pricing_0017` set only `translateX`."""
        for name in ("ticket_0020", "menu_0012", "pricing_0017"):
            source = corpus.SOURCES[name]
            text = source.html_path().read_text(encoding="utf-8")
            from PIL import Image
            width = Image.open(source.png_path()).width
            moved = project(text, width=width).runs != project(
                text, width=width, flat=True).runs
            assert moved == (name == "ticket_0020"), name
