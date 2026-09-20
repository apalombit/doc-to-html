"""The Style Record — Thread 2/B, the palette and page-width increment.

Every test here runs offline with no model, which is the point of the thread:
ADR 0005 measures style from pixels precisely so that it is deterministic and
testable without Ollama.

**What this increment covers and what it does not.** Palette and page width.
The type scale is measured and deliberately unshipped — `style.py`'s module
docstring holds the numbers and the reason — and the border and card detector
is the next increment, so `section.titled` still cards unconditionally and no
test here pretends otherwise.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from doc_to_html.corpus import SOURCES
from doc_to_html.ir import Document, Kind, Source, Style, Zone
from doc_to_html.preprocess import rectify
from doc_to_html.render import render
from doc_to_html.style import MIN_ACCENT_SHARE, measure, modal

REPO = Path(__file__).resolve().parent.parent


def page(colour: tuple[int, int, int],
         marks: list[tuple[tuple[int, int, int], tuple[int, int, int, int]]],
         ) -> np.ndarray:
    """A flat BGR page with coloured rectangles drawn on it.

    BGR, because `measure` takes the Rectified Image as OpenCV holds it and the
    swap to RGB is one of the things being tested. A test written in RGB would
    pass against a `measure` that had forgotten the swap.
    """
    image = np.full((200, 200, 3), 0, dtype=np.uint8)
    image[:, :] = colour[::-1]
    for rgb, (left, top, right, bottom) in marks:
        image[top:bottom, left:right] = rgb[::-1]
    return image


def tokens(html: str) -> dict[str, str]:
    """The custom properties the render's override block declares."""
    block = re.search(r"<style>:root \{(.*?)\}", html, re.S)
    if block is None:
        return {}
    return dict(
        part.strip().split(":", 1) for part in block.group(1).split(";")
        if part.strip()
    )


def sum_of(colour: str) -> int:
    return sum(int(n) for n in re.findall(r"\d+", colour))


class TestTheModalColour:
    """`modal` is the one rounding rule, shared with `scoring`."""

    def test_it_finds_the_colour_most_of_the_page_is(self) -> None:
        pixels = np.full((10, 10, 3), 250, dtype=np.int64)
        pixels[0:2, 0:2] = 10
        assert modal(pixels) == (248, 248, 248)

    def test_it_survives_channel_values_that_overflow_a_small_int(self) -> None:
        # The bug the docstring records: `g * 256` overflowing an int16 array
        # silently, and every page coming back the same colour.
        pixels = np.full((8, 8, 3), (200, 240, 210), dtype=np.uint8)
        assert modal(pixels) == (200, 240, 208)

    def test_no_pixels_is_not_an_exception(self) -> None:
        assert modal(np.zeros((0, 3), dtype=np.int64)) == (0, 0, 0)


class TestMeasuringAPage:
    def test_a_light_page_reads_light(self) -> None:
        measured = measure(page((255, 255, 255), [((26, 26, 26), (10, 10, 190, 60))]))
        assert measured.page_bg == (248, 248, 248)
        assert sum(measured.ink) < 120

    def test_a_dark_page_read_through_rectification_stays_dark(self) -> None:
        """The reason `inverted` is a parameter rather than something inferred.

        `rectify` has already turned the page over by the time anything
        downstream sees it, so the image handed to `measure` is light — and
        measuring it as it stands reports white paper for a page printed on
        near-black.
        """
        turned_over = page((255, 255, 255), [((26, 26, 26), (10, 10, 190, 60))])

        as_it_stands = measure(turned_over)
        as_printed = measure(turned_over, inverted=True)

        assert sum(as_it_stands.page_bg) > sum(as_printed.page_bg)
        assert sum(as_printed.page_bg) < 120
        assert sum(as_printed.ink) > 600

    def test_an_accent_is_found_where_the_page_has_one(self) -> None:
        marked = page(
            (255, 255, 255),
            [((26, 26, 26), (20, 90, 180, 130)),
             ((11, 87, 208), (20, 20, 180, 60))],
        )
        measured = measure(marked)
        assert measured.accent is not None
        red, green, blue = measured.accent
        assert blue > red

    def test_an_accent_is_not_invented_on_a_page_without_one(self) -> None:
        """A fabricated accent is a T5 finding, not a harmless default.

        The scorer compares the most-saturated non-neutral on each side, so
        giving a grey page an accent turns a clean palette delta into a
        difference the render caused.
        """
        assert measure(page((255, 255, 255),
                            [((26, 26, 26), (10, 10, 190, 60))])).accent is None

    def test_a_hue_smaller_than_the_threshold_is_antialiasing(self) -> None:
        speck = page((255, 255, 255), [((26, 26, 26), (10, 10, 190, 60))])
        speck[0:1, 0:1] = (208, 87, 11)  # BGR; 1 of 40000 pixels
        assert 1 / 40000 < MIN_ACCENT_SHARE
        assert measure(speck).accent is None

    def test_a_shaded_band_is_the_pages_furniture(self) -> None:
        shaded = page(
            (255, 255, 255),
            [((26, 26, 26), (20, 90, 180, 130)),
             ((224, 224, 224), (20, 20, 180, 60))],
        )
        measured = measure(shaded)
        assert measured.shade is not None
        assert sum(measured.ink) < sum(measured.shade) < sum(measured.page_bg)

    def test_a_plain_page_has_no_furniture(self) -> None:
        assert measure(page((255, 255, 255),
                            [((26, 26, 26), (10, 10, 190, 60))])).shade is None

    def test_a_greyscale_image_gets_the_house_palette_rather_than_a_guess(
            self) -> None:
        """Not every caller holds three channels, and a wrong palette is worse
        than none: the default Style is what the renderer already draws."""
        assert measure(np.full((40, 40), 200, dtype=np.uint8)) == Style()


class TestMeasuringTheCorpus:
    """Two real documents, because a synthetic page cannot fail the way a
    photograph of a real one can."""

    def test_darkdeck_is_measured_as_the_dark_page_it_is(self) -> None:
        rectified = rectify(REPO / SOURCES["darkdeck_0009"].png)
        measured = measure(rectified.image, inverted=rectified.inverted)

        assert rectified.inverted, "rectify should have turned this page over"
        assert sum(measured.page_bg) < sum(measured.ink)
        assert sum(measured.page_bg) < 200

    def test_a_light_document_is_not_turned_over(self) -> None:
        rectified = rectify(REPO / SOURCES["invoice_0001"].png)
        measured = measure(rectified.image, inverted=rectified.inverted)

        assert not rectified.inverted
        assert sum(measured.page_bg) > sum(measured.ink)


def document(**fields: object) -> Document:
    doc = Document(source=Source(path="x.png", sha256="0" * 64,
                                 width=1164, height=900))
    for name, value in fields.items():
        setattr(doc, name, value)
    return doc


class TestTheRecordSurvivesTheIR:
    """A-1 shipped a decoder that dropped `Gap.ink_share` silently, so findings
    printed 0% while their own note said 3.2%. `_decode_document` builds each
    object field by field, so every new field is that bug waiting. One test per
    field, and they are cheap."""

    def test_the_page_width_round_trips(self) -> None:
        back = Document.from_json(document(page_px=1164).to_json())
        assert back.page_px == 1164

    def test_the_palette_round_trips_as_tuples_not_lists(self) -> None:
        style = Style(page_bg=(0, 0, 0), ink=(192, 200, 216),
                      accent=(64, 136, 208), shade=(16, 24, 32))
        back = Document.from_json(document(style=style).to_json())

        assert back.style == style
        assert isinstance(back.style.page_bg, tuple) if back.style else False

    def test_an_absent_record_round_trips_as_absent(self) -> None:
        back = Document.from_json(document().to_json())
        assert back.style is None
        assert back.page_px is None

    def test_an_ir_written_before_this_existed_still_decodes(self) -> None:
        raw = document().to_json()
        older = raw.replace('"style": null,', "").replace('"page_px": null,', "")
        back = Document.from_json(older)
        assert back.style is None and back.page_px is None


class TestTheRendererReacts:
    def test_an_unmeasured_document_renders_exactly_as_it_always_did(
            self) -> None:
        html = render(document())
        assert html.count("<style>") == 1
        assert "max-width:52rem" in html.replace(" ", "")

    def test_the_measured_palette_wins_over_the_house_one(self) -> None:
        """The override block must come *after* the base stylesheet.

        The base carries a `prefers-color-scheme: dark` block, and a measured
        palette declared above it loses to that block on any machine in dark
        mode — the same harness fault Thread 0 spent a day finding, arriving by
        a different route.
        """
        html = render(document(style=Style(page_bg=(0, 0, 0),
                                           ink=(192, 200, 216))))
        assert html.index("prefers-color-scheme") < html.index("<style>:root")

    def test_the_measured_width_is_carried_but_not_yet_drawn(self) -> None:
        """Measured, traced, round-tripped — and deliberately not rendered.

        Run `89-style-record` set `.doc` to the source's width and
        `invoice_0002`'s `beside_agreement` fell 0.640 -> 0.295, isolated to the
        width by re-rendering that run's own IR with the palette held fixed. It
        is a hard-tier regression and its cause is the band model, which is
        A2's. `render.py` records what would have to become true for this to be
        re-tried; this test is what stops it being switched on by accident in
        the meantime.
        """
        html = render(document(page_px=1164))
        assert "width:1164px" not in html
        assert "max-width:52rem" in html.replace(" ", "")
        assert Document.from_json(document(page_px=1164).to_json()).page_px == 1164

    def test_a_measured_page_declares_its_ground_and_ink(self) -> None:
        html = render(document(style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26))))
        declared = tokens(html)
        assert declared["--page-bg"] == "rgb(255,255,255)"
        assert declared["--ink"] == "rgb(26,26,26)"

    def test_rules_and_muted_text_follow_the_ground_rather_than_staying_light(
            self) -> None:
        """`--muted:#666` and `--rule:#e0e0e0` are grey-on-white by design.

        On `darkdeck_0009`'s near-black they stop meaning what they are named:
        the muted text goes near-invisible and the hairline rule becomes the
        brightest thing on the page. Both are derived from the measured pair
        instead, and the test is the ordering, not the exact value.
        """
        declared = tokens(render(document(style=Style(page_bg=(0, 0, 0),
                                                      ink=(192, 200, 216)))))
        ink, ground = sum_of(declared["--ink"]), sum_of(declared["--page-bg"])
        assert ground < sum_of(declared["--rule"]) < sum_of(declared["--muted"])
        assert sum_of(declared["--muted"]) < ink

    def test_a_light_page_keeps_the_values_those_constants_had(self) -> None:
        """The derivation may not be a change of behaviour on a white page.

        Fourteen of fifteen corpus documents are light, so a derivation that
        drifted from the shipped constants would move every one of them for no
        reason and muddy whatever the checkpoint measures.
        """
        declared = tokens(render(document(style=Style(page_bg=(255, 255, 255),
                                                      ink=(26, 26, 26)))))
        assert abs(sum_of(declared["--rule"]) - 0xE0 * 3) < 12   # was #e0e0e0
        assert abs(sum_of(declared["--shade"]) - 0xF4 * 3) < 12  # was #f4f4f4
        assert abs(sum_of(declared["--muted"]) - 0x66 * 3) < 12  # was #666

    def test_an_accent_is_spent_on_the_heading(self) -> None:
        html = render(document(style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26),
                                           accent=(11, 87, 208))))
        assert "--accent:rgb(11,87,208)" in html
        assert "h1 { color:var(--accent); }" in html

    def test_a_page_with_no_accent_declares_none(self) -> None:
        html = render(document(style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26))))
        assert "--accent:rgb" not in html
        assert "h1 { color:var(--accent); }" not in html

    def test_an_unshaded_page_still_gets_a_shade_to_draw_header_rows_with(
            self) -> None:
        """The renderer shades table header rows whether or not the source
        does, so the token has to exist; what it must not be is the fixed light
        grey on a dark page."""
        declared = tokens(render(document(style=Style(page_bg=(0, 0, 0),
                                                      ink=(192, 200, 216)))))
        assert sum_of(declared["--shade"]) < 120

    def test_the_document_still_renders_its_content(self) -> None:
        """A palette change that broke the body would show here before it showed
        in `project()`."""
        zone = Zone(kind=Kind.PROSE, bbox=(0, 0, 100, 100))
        html = render(document(zones=[zone], page_px=800,
                               style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26))))
        assert '<div class="doc">' in html
        assert "<section" in html
