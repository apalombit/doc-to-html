"""The Style Record — Thread 2/B, the palette and page-width increment.

Every test here runs offline with no model, which is the point of the thread:
ADR 0005 measures style from pixels precisely so that it is deterministic and
testable without Ollama.

**What this increment covers and what it does not.** Palette, page width and
the border finder. The type scale is measured and deliberately unshipped —
`style.py`'s module docstring holds the numbers and the reason.

The border finder's one end-to-end test, through a real Conversion, lives in
`tests/test_list_and_figure.py::TestCards` beside the render it has to reach.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from doc_to_html.corpus import SOURCES, SWEEP
from doc_to_html.ir import BBox, Document, Kind, Source, Style, Zone
from doc_to_html.preprocess import rectify
from doc_to_html.render import render
from doc_to_html.style import (
    MIN_ACCENT_SHARE,
    box_around,
    chrome,
    dominant,
    measure,
    modal,
    rectangles,
)

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


class TestTheDominantColour:
    """`dominant` is what gets emitted as CSS, and it must be the page's own
    colour rather than the bucket's floor."""

    def test_a_white_page_is_white_and_not_nearly_white(self) -> None:
        """Reported from looking at a render beside its source: every white
        document was being laid on `#f8f8f8`, because `255 // 8 * 8` is 248.
        Invisible in `background_delta`, obvious on the screen."""
        assert dominant(np.full((10, 10, 3), 255, dtype=np.uint8)) == (255, 255, 255)
        assert modal(np.full((10, 10, 3), 255, dtype=np.uint8)) == (248, 248, 248)

    def test_a_black_page_is_black(self) -> None:
        assert dominant(np.zeros((10, 10, 3), dtype=np.uint8)) == (0, 0, 0)

    def test_the_bucket_still_picks_the_winner(self) -> None:
        """The bucketing is not abandoned, only stopped from naming the colour:
        near-identical antialiased shades still count as one, and the winner's
        own pixels then say what it is."""
        pixels = np.full((10, 10, 3), 250, dtype=np.int64)
        pixels[0, 0] = 251
        pixels[0, 1] = 252   # same bucket as 250, so the ground is one thing
        pixels[1:4, :] = 10  # a smaller, darker region
        assert dominant(pixels) == (250, 250, 250)

    def test_no_pixels_is_not_an_exception(self) -> None:
        assert dominant(np.zeros((0, 3), dtype=np.int64)) == (0, 0, 0)


class TestMeasuringAPage:
    def test_a_white_page_renders_on_white(self) -> None:
        measured = measure(page((255, 255, 255), [((26, 26, 26), (10, 10, 190, 60))]))
        assert measured.page_bg == (255, 255, 255)

    def test_a_light_page_reads_light(self) -> None:
        measured = measure(page((255, 255, 255), [((26, 26, 26), (10, 10, 190, 60))]))
        assert measured.page_bg == (255, 255, 255)
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

    def test_an_accent_is_declared_and_deliberately_not_spent(self) -> None:
        """Measured, recorded, and applied to nothing — for now.

        Two spends were tried and both invented the colour somewhere the source
        does not put it: colouring `h1` text turned all of `sample_css_0004`'s
        dark navy headings blue, and underlining `h1` instead drew three rules
        on `sample_semantic_0005` that its source does not have. Where a page
        puts its accent is a detection problem, not a palette one. The token
        stays so a later pass can spend it without re-measuring.
        """
        html = render(document(style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26),
                                           accent=(11, 87, 208))))
        assert "--accent:rgb(11,87,208)" in html
        assert "var(--accent)" not in html.split("</style>")[-1]
        assert "h1 { color:var(--accent)" not in html
        assert "border-bottom:2px solid var(--accent)" not in html

    def test_a_page_with_no_accent_declares_none(self) -> None:
        html = render(document(style=Style(page_bg=(255, 255, 255),
                                           ink=(26, 26, 26))))
        assert "--accent:rgb" not in html
        assert "var(--accent)" not in html.split("</style>")[-1]
        assert "border-bottom:2px solid var(--accent)" not in html

    def test_the_shade_token_is_derived_and_never_the_measured_one(self) -> None:
        """A page-wide shade measurement is not evidence that the page has a
        fill, and using it as one put beige bars on `receipt_0010` and tan ones
        on `menu_0012`, whose sources draw no fill anywhere. The token is
        derived from the measured pair instead — it can never introduce a hue —
        and real fills travel per Zone, inline. See `render._style_css`."""
        measured = Style(page_bg=(255, 255, 255), ink=(26, 26, 26),
                         shade=(185, 166, 137))
        declared = tokens(render(document(style=measured)))
        assert declared["--shade"] != "rgb(185,166,137)"
        red, green, blue = (int(n) for n in re.findall(r"\d+", declared["--shade"]))
        assert red == green == blue, "a derived shade cannot carry a hue"

    def test_a_dark_page_gets_a_dark_shade(self) -> None:
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


# --- the border finder ------------------------------------------------------


def sheet(width: int = 400, height: int = 400,
          ground: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    image = np.full((height, width, 3), 0, dtype=np.uint8)
    image[:, :] = ground[::-1]
    return image


def draw_box(image: np.ndarray, box: tuple[int, int, int, int],
             rule: tuple[int, int, int] = (225, 232, 237),
             fill: tuple[int, int, int] | None = None,
             thickness: int = 1) -> None:
    """A rule around a rectangle, optionally over a fill, in the real colours.

    `#e1e8ed` on `#f7f9fb` is `sample_css_0004`'s actual card: the rule's grey
    is 230, well above `preprocess.INK_LEVEL`, so it is not ink and never
    reaches the mask the Zone box is snapped against.
    """
    left, top, right, bottom = box
    if fill is not None:
        image[top:bottom, left:right] = fill[::-1]
    for t in range(thickness):
        image[top + t, left:right] = rule[::-1]
        image[bottom - 1 - t, left:right] = rule[::-1]
        image[top:bottom, left + t] = rule[::-1]
        image[top:bottom, right - 1 - t] = rule[::-1]


def write_text(image: np.ndarray, rows: list[tuple[int, int, int]]) -> None:
    """Dark bars standing in for lines of type."""
    for top, left, right in rows:
        image[top:top + 6, left:right] = (26, 26, 26)


class TestFindingTheDrawnBoxes:
    """A rule is a property of the page, not of a Zone's crop.

    The crop is snapped onto content ink and `preprocess.content_ink` deletes
    separators from that mask by name — "a horizontal rule, a panel border, a
    column divider" — so the rule is not merely outside the box, it is
    invisible to the thing that placed the box.
    """

    def test_a_drawn_card_is_found_where_it_is_drawn(self) -> None:
        image = sheet()
        draw_box(image, (40, 40, 360, 200), fill=(247, 249, 251))
        write_text(image, [(70, 60, 300), (90, 60, 250)])

        found = rectangles(image, ground=(255, 255, 255))

        assert len(found) == 1
        box = found[0]
        assert box.left * 400 == 40 and box.top * 400 == 40
        assert round(box.right * 400) == 360 and round(box.bottom * 400) == 200

    def test_a_rectangle_bigger_than_the_page_guard_is_the_page(self) -> None:
        """`invoice_0001`'s only drawn box is the frame round the whole
        invoice, at 0.981 of the page. Unguarded, every Zone on that page sits
        inside it and every Zone is a card."""
        image = sheet()
        draw_box(image, (4, 4, 396, 396))
        write_text(image, [(60, 40, 300)])

        assert rectangles(image, ground=(255, 255, 255)) == ()

    def test_a_tick_box_is_drawn_and_is_not_a_panel(self) -> None:
        """`form_0007` draws 30 full boxes and 16 are checkboxes and
        single-character cells. Reporting them would card every tick."""
        image = sheet()
        draw_box(image, (40, 40, 54, 54))

        assert rectangles(image, ground=(255, 255, 255)) == ()

    def test_prose_is_not_a_rectangle(self) -> None:
        """What separates a card from a block of text, with no second
        detector: a paragraph's bounding box has ink on a small fraction of
        each edge, and `_bordered` wants 80%."""
        image = sheet()
        write_text(image, [(60 + n * 20, 40, 340 - (n % 3) * 40) for n in range(8)])

        assert rectangles(image, ground=(255, 255, 255)) == ()

    def test_two_cards_do_not_weld_into_one(self) -> None:
        image = sheet(height=500)
        draw_box(image, (40, 40, 360, 200), fill=(247, 249, 251))
        draw_box(image, (40, 230, 360, 400), fill=(247, 249, 251))

        assert len(rectangles(image, ground=(255, 255, 255))) == 2

    def test_a_dark_page_is_measured_on_its_own_polarity(self) -> None:
        """`darkdeck_0009` and `cv_0013` are printed light on dark, and
        `rectify` turns them over before anything downstream sees them."""
        image = sheet(ground=(18, 22, 28))
        draw_box(image, (40, 40, 360, 200), rule=(70, 78, 90),
                 fill=(30, 36, 44))
        turned = 255 - image

        found = rectangles(turned, ground=(18, 22, 28), inverted=True)

        assert len(found) == 1


class TestGivingAZoneItsBox:
    def test_the_smallest_containing_rectangle_wins(self) -> None:
        """A card inside a panel inside a page is three containers and only
        the nearest one is this Zone's own chrome."""
        outer = BBox(0.0, 0.0, 1.0, 1.0)
        inner = BBox(0.1, 0.1, 0.5, 0.5)
        zone = BBox(0.2, 0.2, 0.3, 0.3)

        assert box_around(zone, (outer, inner)) == inner

    def test_a_zone_no_rectangle_holds_gets_none(self) -> None:
        assert box_around(BBox(0.6, 0.6, 0.9, 0.9),
                          (BBox(0.1, 0.1, 0.5, 0.5),)) is None

    def test_a_zone_straddling_two_cards_is_not_boxed(self) -> None:
        left = BBox(0.05, 0.1, 0.45, 0.9)
        right = BBox(0.55, 0.1, 0.95, 0.9)

        assert box_around(BBox(0.1, 0.2, 0.9, 0.8), (left, right)) is None

    def test_a_zone_snapped_a_pixel_outside_its_rounded_corner_keeps_it(self) -> None:
        card = BBox(0.10, 0.10, 0.50, 0.50)

        assert box_around(BBox(0.099, 0.10, 0.50, 0.50), (card,)) == card


class TestChromeNoLongerGuessesABorder:
    def test_a_tight_line_of_type_is_not_a_bordered_region(self) -> None:
        """Asking a crop directly was not merely blind, it was wrong: a crop
        cut tight around one line of type has ink on all four of its edges."""
        line = np.full((8, 120, 3), 255, dtype=np.uint8)
        line[1:7, 2:118] = 26

        assert chrome(line, ground=(255, 255, 255)).bordered is False

    def test_what_the_page_found_is_what_is_reported(self) -> None:
        plain = np.full((40, 200, 3), 255, dtype=np.uint8)

        assert chrome(plain, ground=(255, 255, 255), bordered=True).bordered
        assert not chrome(plain, ground=(255, 255, 255)).bordered


class TestFindingBoxesInTheCorpus:
    """Synthetic pages cannot fail the way a real one can, and the fault this
    increment replaces was a detector that answered zero on all fifteen."""

    def test_the_carded_documents_get_their_cards(self) -> None:
        for name, expected in (("sample_css_0004", 2), ("darkdeck_0009", 5),
                               ("nonlatin_0014", 2), ("catalogue_0015", 9)):
            rectified = rectify(REPO / SOURCES[name].png)
            plain = rectified.plain if rectified.plain is not None \
                else rectified.image
            ground = measure(plain, inverted=rectified.inverted).page_bg
            found = rectangles(plain, ground=ground,
                               inverted=rectified.inverted)
            assert len(found) == expected, f"{name}: {len(found)} rectangles"

    def test_documents_that_draw_no_box_get_none(self) -> None:
        """The failure mode this replaces went the other way — the old
        `section.titled` rule carded roughly ten of fifteen documents whose
        sources draw nothing of the kind."""
        for name in ("sample_table_0003", "statement_0006", "receipt_0010",
                     "menu_0012", "cv_0013", "report_0011",
                     "newsletter_0008", "sample_semantic_0005"):
            rectified = rectify(REPO / SOURCES[name].png)
            plain = rectified.plain if rectified.plain is not None \
                else rectified.image
            ground = measure(plain, inverted=rectified.inverted).page_bg
            found = rectangles(plain, ground=ground,
                               inverted=rectified.inverted)
            assert found == (), f"{name}: invented {len(found)} rectangles"

    def test_every_sweep_document_is_covered_by_one_of_those_lists(self) -> None:
        """So a document added to the corpus cannot quietly go unchecked."""
        carded = {"sample_css_0004", "darkdeck_0009", "nonlatin_0014",
                  "catalogue_0015"}
        plain_pages = {"sample_table_0003", "statement_0006", "receipt_0010",
                       "menu_0012", "cv_0013", "report_0011",
                       "newsletter_0008", "sample_semantic_0005"}
        # invoice_0001 is the page-guard case and invoice_0002 and form_0007
        # are counted in the run report rather than pinned here: form_0007
        # finds 13 of its 14 in-range boxes and that number is a measurement,
        # not a target.
        known = carded | plain_pages | {"invoice_0001", "invoice_0002",
                                        "form_0007"}
        assert set(SWEEP) - known == set()
