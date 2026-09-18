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

from doc_to_html import projection
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
