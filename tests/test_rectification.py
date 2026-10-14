"""Seam 2 — `rectify()`, tested directly because its output is an image.

This seam carries the rectifier's correctness on its own. All five fixtures are
white documents filling a white frame, with no page quadrilateral to find, so the
end-to-end conversions exercise the *fallback* and essentially none of the
geometry. **Nobody should read a passing end-to-end test as evidence that
rectification works.** These tests are the evidence.

The method is to distort a fixture by known amounts, rectify, and check that
landmarks land where they sit in the undistorted rectification. Tolerances are in
normalised coordinates because that is what the IR stores — a bounding box means
the same thing at any output size.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from doc_to_html.ir import RECTIFIER_VERSION, BBox
from doc_to_html.preprocess import (
    PAD_X,
    PAD_Y,
    ImageArray,
    SHEET_BEYOND,
    RectifyError,
    crop,
    deskew,
    equalise,
    find_page_quad,
    paper_box,
    rectify,
    sheet_beyond,
    sheet_outline,
    skew_angle,
    surround_of,
    warp_to_quad,
)

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "example"
INVOICE = EXAMPLES / "invoice.png"

TOLERANCE = 8
"""Pixels, against the 862x563 reference. Roughly 1% of the page's long edge.

The distortions below land every landmark within 4px; this is that with a margin,
and it is well inside the precision of a bounding box a model draws.
"""

LANDMARKS = {
    "wordmark": (0.05, 0.07, 0.40, 0.16),
    "invoice number": (0.78, 0.06, 0.97, 0.13),
    "payment header": (0.03, 0.48, 0.30, 0.55),
    "total": (0.80, 0.86, 0.97, 0.94),
}
"""Distinctive patches spread over the page, as normalised boxes. Spread matters:
a perspective error is smallest at the centre and largest at the corners, so
landmarks clustered anywhere would understate it."""


def photograph(image: ImageArray, *, rotate: float = 0.0,
               perspective: float = 0.0) -> ImageArray:
    """Put a page on a dark background under a known distortion.

    A dark surround is what gives the rectifier a page quadrilateral to find,
    which is exactly what the project's own fixtures lack.
    """
    height, width = image.shape[:2]
    canvas_h, canvas_w = int(height * 1.6), int(width * 1.6)
    canvas = np.full((canvas_h, canvas_w, 3), 45, np.uint8)

    corners = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    )
    offset = np.float32([[(canvas_w - width) // 2, (canvas_h - height) // 2]] * 4)
    target = corners + offset
    # Pull the top edge inward and down: a page photographed from above its centre.
    target[0] += np.float32([perspective * width, perspective * height * 0.35])
    target[1] += np.float32([-perspective * width, perspective * height * 0.35])

    placed = cv2.warpPerspective(
        image,
        cv2.getPerspectiveTransform(corners, target),
        (canvas_w, canvas_h),
        borderMode=cv2.BORDER_TRANSPARENT,
        dst=canvas.copy(),
    )
    if not rotate:
        return placed
    spin = cv2.getRotationMatrix2D((canvas_w / 2, canvas_h / 2), rotate, 1.0)
    rotated: ImageArray = cv2.warpAffine(
        placed, spin, (canvas_w, canvas_h), borderValue=(45, 45, 45)
    )
    return rotated


def rectified_pixels(image: ImageArray, tmp_path: Path, name: str) -> ImageArray:
    path = tmp_path / f"{name}.png"
    cv2.imwrite(str(path), image)
    return rectify(path).image


def landmark_drift(reference: ImageArray, candidate: ImageArray) -> dict[str, int]:
    """How far each landmark moved, in pixels of the reference.

    The candidate is scaled to the reference's size first. That is not a fudge:
    the IR stores normalised coordinates, so correspondence up to scale is exactly
    the property that has to hold.
    """
    height, width = reference.shape[:2]
    scaled = cv2.resize(candidate, (width, height), interpolation=cv2.INTER_AREA)

    drift = {}
    for name, (left, top, right, bottom) in LANDMARKS.items():
        x0, y0 = int(left * width), int(top * height)
        patch = reference[y0:int(bottom * height), x0:int(right * width)]
        found = cv2.minMaxLoc(
            cv2.matchTemplate(scaled, patch, cv2.TM_CCOEFF_NORMED)
        )[3]
        drift[name] = max(abs(found[0] - x0), abs(found[1] - y0))
    return drift


@pytest.fixture
def invoice() -> ImageArray:
    return cv2.imread(str(INVOICE), cv2.IMREAD_COLOR)


@pytest.fixture
def reference(invoice: ImageArray, tmp_path: Path) -> ImageArray:
    """The undistorted page, rectified. Every landmark is measured against this."""
    return rectified_pixels(invoice, tmp_path, "reference")


class TestADistortedPhotographComesBack:
    @pytest.mark.parametrize(
        "rotate,perspective",
        [(0.0, 0.10), (5.0, 0.0), (5.0, 0.08), (-8.0, 0.12), (3.0, -0.06)],
        ids=["perspective", "rotation", "both", "against-the-other-way", "reversed"],
    )
    def test_landmarks_land_where_they_belong(
        self, invoice: ImageArray, reference: ImageArray, tmp_path: Path,
        rotate: float, perspective: float,
    ) -> None:
        distorted = photograph(invoice, rotate=rotate, perspective=perspective)
        candidate = rectified_pixels(distorted, tmp_path, "distorted")

        drift = landmark_drift(reference, candidate)
        assert all(moved <= TOLERANCE for moved in drift.values()), drift

    def test_the_page_comes_back_at_roughly_its_own_shape(
        self, invoice: ImageArray, tmp_path: Path
    ) -> None:
        """A warp that flattened the page to the wrong rectangle would move every
        coordinate in the IR while every landmark test still passed on a
        uniformly stretched page."""
        distorted = photograph(invoice, rotate=6.0, perspective=0.06)
        candidate = rectified_pixels(distorted, tmp_path, "distorted")

        original = invoice.shape[1] / invoice.shape[0]
        recovered = candidate.shape[1] / candidate.shape[0]
        assert recovered == pytest.approx(original, rel=0.06)

    def test_the_dark_surround_is_gone(
        self, invoice: ImageArray, tmp_path: Path
    ) -> None:
        distorted = photograph(invoice, rotate=4.0, perspective=0.05)
        assert distorted.mean() < 150
        assert rectified_pixels(distorted, tmp_path, "distorted").mean() > 180


class TestWhenTheQuadrilateralCannotBeFound:
    @pytest.mark.parametrize(
        "name",
        ["invoice.png", "invoice2.png", "sample-table.png", "sample-css.png",
         "sample-semantic.png"],
    )
    def test_every_fixture_takes_the_documented_fallback(self, name: str) -> None:
        """A white document filling a white frame has no page edge in it. The
        largest contour is the image border, and warping to that is a no-op with
        rounding error attached."""
        result = rectify(EXAMPLES / name)
        assert result.warped is False
        assert (result.source.rectified_width, result.source.rectified_height) == (
            result.source.width, result.source.height
        )

    def test_a_frame_filling_quadrilateral_is_rejected(
        self, invoice: ImageArray
    ) -> None:
        assert find_page_quad(invoice) is None

    def test_a_small_quadrilateral_is_rejected(self) -> None:
        """A panel, or a photograph within the page. Warping to it would crop the
        document to one of its own parts."""
        canvas = np.full((600, 800, 3), 45, np.uint8)
        canvas[250:350, 350:450] = 255
        assert find_page_quad(canvas) is None

    def test_a_frame_the_page_draws_is_not_warped_to(self, tmp_path: Path) -> None:
        """Spec 0012, G3b — `certificate_0021`'s double frame: cream inside
        and out, so a frame on the page, not the edge of a sheet."""
        page = np.full((600, 900, 3), (230, 244, 250), np.uint8)
        page[20:580, 20:24] = page[20:580, 876:880] = (60, 140, 180)
        page[20:24, 20:880] = page[576:580, 20:880] = (60, 140, 180)
        page[280:300, 300:600] = 30
        path = tmp_path / "framed.png"
        cv2.imwrite(str(path), page)
        assert find_page_quad(page) is not None, "the frame is a quadrilateral"
        result = rectify(path)
        assert result.warped is False and result.source.paper is None
        assert (result.source.rectified_width, result.source.rectified_height) == (900, 600)

    def test_an_unusable_image_is_refused_rather_than_guessed_at(
        self, tmp_path: Path
    ) -> None:
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not an image at all")
        with pytest.raises(RectifyError, match="could not decode"):
            rectify(broken)


DESK = (72, 65, 60)
TEAL = (138, 110, 11)
"""`ticket_0020`'s slate desk and teal header, BGR: 64 and 84 in grey."""


def banded_card(tilt: float = 1.5) -> tuple[ImageArray, ImageArray]:
    """A white card with a teal band along its top, on a slate desk, tilted —
    and its four true corners. In grey the band is nearly the desk."""
    canvas = np.full((420, 900, 3), DESK, np.uint8)
    card = np.full_like(canvas, 255)
    card[60:100] = TEAL
    for top in range(140, 330, 30):
        card[top:top + 10, 100:600] = 30
    shape = np.zeros(canvas.shape[:2], np.uint8)
    cv2.rectangle(shape, (60, 60), (840, 350), 255, -1)
    spin = cv2.getRotationMatrix2D((450, 210), tilt, 1.0)
    shape = cv2.warpAffine(shape, spin, (900, 420))
    card = cv2.warpAffine(card, spin, (900, 420))
    canvas[shape > 127] = card[shape > 127]
    corners = np.array([[[60, 60], [840, 60], [840, 350], [60, 350]]], np.float32)
    return canvas, cv2.transform(corners, spin)[0]


class TestThePapersWholeOutline:
    """Spec 0013, step 5 — `find_page_quad` reads edges in grey, so a sheet
    whose border is the desk's shade there loses it, and the warp cuts the
    border off. An edge with the sheet beyond it is not the paper's edge."""

    def test_an_edge_with_the_sheet_beyond_it_is_not_the_papers(self) -> None:
        image, _ = banded_card()
        found = find_page_quad(image)
        assert found is not None
        surround = surround_of(image, found)
        assert surround is not None
        assert sheet_beyond(image, found, surround) > SHEET_BEYOND

    def test_the_outline_is_read_off_the_sheets_colour(self) -> None:
        image, true = banded_card()
        outline = sheet_outline(image, (60, 65, 72))
        assert outline is not None
        assert float(np.abs(outline - true).max()) < 1.5
        assert sheet_beyond(image, outline, (60, 65, 72)) == 0.0

    def test_the_band_is_kept_in_the_warp(self, tmp_path: Path) -> None:
        image, _ = banded_card()
        path = tmp_path / "card.png"
        cv2.imwrite(str(path), image)
        top = rectify(path).plain[6:12, 100:-100].reshape(-1, 3).mean(axis=0)
        assert np.abs(top - np.array(TEAL)).max() < 30

    def test_the_tickets_stub_keeps_its_header(self) -> None:
        """Warped to the grey quadrilateral, the stub's top eighth was the
        foot of its teal band over white card, `NORDLYS AIR` cut off."""
        result = rectify(EXAMPLES / "ticket.png")
        assert result.warped
        height, width = result.plain.shape[:2]
        stub = result.plain[:height // 8, int(0.78 * width):int(0.97 * width)]
        teal = np.abs(stub.astype(int) - np.array(TEAL)).max(axis=2) < 30
        assert teal.mean() > 0.8
        assert (stub.min(axis=2) > 200).sum() > 30, "its name, in white"

    def test_a_sheet_with_the_desk_beyond_every_edge_keeps_its_quadrilateral(
        self,
    ) -> None:
        """`receipt_0010`: the receipt's pixels must not move."""
        image = cv2.imread(str(EXAMPLES / "receipt.png"), cv2.IMREAD_COLOR)
        found = find_page_quad(image)
        assert found is not None
        surround = surround_of(image, found)
        assert surround is not None
        assert sheet_beyond(image, found, surround) == 0.0
        height, width = image.shape[:2]
        assert rectify(EXAMPLES / "receipt.png").source.paper == paper_box(
            found, width, height)


class TestDeskewCorrectsATiltAndNotAnOrientation:
    def straightened(self, invoice: ImageArray, tilt: float) -> float:
        height, width = invoice.shape[:2]
        spin = cv2.getRotationMatrix2D((width / 2, height / 2), tilt, 1.0)
        tilted = cv2.warpAffine(
            invoice, spin, (width, height), borderMode=cv2.BORDER_REPLICATE
        )
        return skew_angle(deskew(tilted))

    @pytest.mark.parametrize("tilt", [-4.0, -1.5, 1.5, 4.0])
    def test_a_tilt_is_taken_out(self, invoice: ImageArray, tilt: float) -> None:
        assert abs(self.straightened(invoice, tilt)) <= 1.0

    def test_a_straight_page_is_left_alone(self, invoice: ImageArray) -> None:
        """Rotating costs a resampling blur and moves every coordinate, so a page
        that is already level must be recognised as level."""
        assert skew_angle(invoice) == 0.0
        assert deskew(invoice) is invoice

    def test_a_full_height_panel_is_not_read_as_a_tilt(self) -> None:
        """`cv_0013`'s sidebar, once its picture was re-shot whole, 2026-09-29.

        A solid panel running the height of the page adds the same ink to
        every row at level, and a wedge of it once tilted — so the line
        profile scored every step of tilt higher than the last and a straight
        page was turned a full 15 degrees. See `_without_panels`.
        """
        page = cv2.imread(str(EXAMPLES / "cv.png"), cv2.IMREAD_COLOR)
        assert skew_angle(page) == 0.0
        assert deskew(page) is page

    @pytest.mark.parametrize("tilt", [-4.0, 4.0])
    def test_a_tilt_is_still_taken_out_beside_a_panel(
        self, invoice: ImageArray, tilt: float
    ) -> None:
        """Taking the panel out of the vote must not take the type with it."""
        panelled = invoice.copy()
        panelled[:, : invoice.shape[1] // 5] = (40, 50, 60)
        assert abs(self.straightened(panelled, tilt)) <= 1.0

    def test_a_page_on_its_side_is_not_guessed_at(
        self, invoice: ImageArray
    ) -> None:
        """Telling 90 degrees from 270 means reading the text, which is an
        Engine's job. A rectifier that guesses wrong ruins every coordinate in the
        IR, so this stays out of scope rather than being half-done."""
        sideways = cv2.rotate(invoice, cv2.ROTATE_90_CLOCKWISE)
        assert skew_angle(sideways) == 0.0


class TestPhotometry:
    def paper_level(self, image: ImageArray) -> ImageArray:
        """How bright the paper is in each column of the page.

        The 90th percentile down each column, which on a page of text is the paper
        rather than the ink. This is what a shadow shifts, and measuring the plain
        column mean instead conflates it with how much text a column happens to
        contain.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return np.percentile(gray, 90, axis=0)

    def test_uneven_lighting_is_flattened(self, invoice: ImageArray) -> None:
        """A shadow across the page costs the rows underneath it: the text there
        falls below whatever threshold anything downstream applies."""
        width = invoice.shape[1]
        gradient = np.linspace(0.35, 1.0, width, dtype=np.float32)
        shadowed = (invoice * gradient[None, :, None]).astype(np.uint8)

        before = self.paper_level(shadowed)
        after = self.paper_level(equalise(shadowed))
        assert before.max() - before.min() > 150  # the shadow, as introduced
        assert after.max() - after.min() < 50
        assert after.min() > 200  # paper is paper again, even in the shadow

    def test_a_local_contrast_stretch_alone_would_not_do_it(
        self, invoice: ImageArray
    ) -> None:
        """Recorded because CLAHE is the obvious thing to reach for and does not
        work here: it stretches contrast within each tile and leaves the gradient
        between tiles almost exactly where it was."""
        width = invoice.shape[1]
        gradient = np.linspace(0.35, 1.0, width, dtype=np.float32)
        shadowed = (invoice * gradient[None, :, None]).astype(np.uint8)

        lab = cv2.cvtColor(shadowed, cv2.COLOR_BGR2LAB)
        lightness, a_channel, b_channel = cv2.split(lab)
        clahe_only = cv2.cvtColor(
            cv2.merge((
                cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness),
                a_channel, b_channel,
            )),
            cv2.COLOR_LAB2BGR,
        )
        levels = self.paper_level(clahe_only)
        assert levels.max() - levels.min() > 150

    def test_colour_is_not_equalised(self, invoice: ImageArray) -> None:
        """Nothing downstream may read colour (ADR 0002), but shifting the hues a
        Mark is recognised by would still be a change made for no reason."""
        before = cv2.cvtColor(invoice, cv2.COLOR_BGR2LAB)
        after = cv2.cvtColor(equalise(invoice), cv2.COLOR_BGR2LAB)
        assert np.abs(before[:, :, 1:].astype(int)
                      - after[:, :, 1:].astype(int)).max() <= 2


class TestDeterminismAndVersioning:
    def test_the_same_image_always_rectifies_to_the_same_pixels(
        self, invoice: ImageArray, tmp_path: Path
    ) -> None:
        """Corrections are anchored in this coordinate space. If the same Source
        Image produced different pixels between runs, every stored Correction
        would point somewhere slightly different each time."""
        distorted = photograph(invoice, rotate=5.0, perspective=0.07)
        once = rectified_pixels(distorted, tmp_path, "a")
        twice = rectified_pixels(distorted, tmp_path, "b")
        assert np.array_equal(once, twice)

    def test_the_rectifier_version_is_recorded_in_the_ir(self) -> None:
        """Geometry changed, so previously stored Corrections point elsewhere and
        must be treated as orphaned rather than silently re-attached."""
        from doc_to_html.ir import Document, Source

        assert RECTIFIER_VERSION >= 2
        document = Document(source=Source(path="x", sha256="0" * 64,
                                         width=1, height=1))
        assert document.rectifier_version == RECTIFIER_VERSION


class TestCropsComeFromTheRectifiedImage:
    """The line-items table of `invoice.png`, as an Extractor would crop it."""

    BOX = BBox(0.03, 0.63, 0.97, 0.95)

    def test_a_skewed_source_yields_a_straight_crop(
        self, invoice: ImageArray, tmp_path: Path
    ) -> None:
        """Otherwise an Escalation crop is just a bigger skewed crop, and a Band
        is not a horizontal stripe of anything."""
        distorted = photograph(invoice, rotate=7.0, perspective=0.05)
        candidate = rectified_pixels(distorted, tmp_path, "distorted")
        assert skew_angle(crop(candidate, self.BOX)) == 0.0

    def test_the_same_crop_taken_without_rectifying_is_not_straight(
        self, invoice: ImageArray
    ) -> None:
        """The contrast that makes the previous test mean something: cropping a
        tilted page at the same normalised box gives a tilted crop."""
        height, width = invoice.shape[:2]
        spin = cv2.getRotationMatrix2D((width / 2, height / 2), 7.0, 1.0)
        tilted = cv2.warpAffine(
            invoice, spin, (width, height), borderMode=cv2.BORDER_REPLICATE
        )
        assert skew_angle(crop(tilted, self.BOX)) != 0.0

    def test_the_crop_holds_the_rows_it_should(
        self, invoice: ImageArray, reference: ImageArray, tmp_path: Path
    ) -> None:
        """Straight but of the wrong region would pass the test above."""
        distorted = photograph(invoice, rotate=7.0, perspective=0.05)
        candidate = rectified_pixels(distorted, tmp_path, "distorted")
        drift = landmark_drift(reference, candidate)
        assert drift["total"] <= TOLERANCE
        assert drift["payment header"] <= TOLERANCE


class TestTheWorkingResolution:
    def test_a_large_photograph_is_brought_down_to_the_ceiling(
        self, tmp_path: Path
    ) -> None:
        big = np.full((5000, 3000, 3), 240, np.uint8)
        big[1000:4000, 500:2500] = 255
        result = rectify(
            tmp_path / "big.png"
            if cv2.imwrite(str(tmp_path / "big.png"), big) else tmp_path / "big.png"
        )
        assert max(result.image.shape[:2]) <= 3508

    def test_a_small_screenshot_is_not_enlarged(self) -> None:
        """Enlarging adds no detail while multiplying the cost of every crop taken
        from it. TARGET_LONG_EDGE is a ceiling, not a target."""
        result = rectify(INVOICE)
        assert (result.image.shape[1], result.image.shape[0]) == (862, 563)


class TestCropPaddingIsAsymmetric:
    """The pads differ per axis, and the reason is measured rather than chosen.

    A real `qwen3-vl:4b` returns Zone boxes ending at `right=0.94` on
    `example/invoice.png` while the right-aligned prices run to about 0.97. With
    the old symmetric 0.01 pad every crop clipped the final glyph, and three
    unrelated model families all read `$300.00` as `$300.0` — they were reading
    the same short image, not making the same mistake.
    """

    def page(self) -> ImageArray:
        return np.full((1000, 1000, 3), 255, dtype=np.uint8)

    def test_the_horizontal_pad_is_wider_than_the_vertical(self) -> None:
        assert PAD_X > PAD_Y

    def test_a_crop_reaches_further_sideways_than_up_and_down(self) -> None:
        box = BBox(left=0.4, top=0.4, right=0.6, bottom=0.6)
        cropped = crop(self.page(), box)
        height, width = cropped.shape[:2]
        assert width == 1000 * (0.6 + PAD_X) - 1000 * (0.4 - PAD_X)
        assert height == 1000 * (0.6 + PAD_Y) - 1000 * (0.4 - PAD_Y)
        assert width > height

    def test_the_pad_recovers_the_last_character(self) -> None:
        """0.03 on an 862px page is 26px — wide enough for the glyph that a
        0.01 pad (8.6px) left outside the crop."""
        assert PAD_X * 862 > 20

    def test_padding_stays_inside_the_page(self) -> None:
        """A Zone against an edge must not produce a negative or oversized crop."""
        cropped = crop(self.page(), BBox(left=0.0, top=0.0, right=1.0, bottom=1.0))
        assert cropped.shape[:2] == (1000, 1000)

    def test_stacked_zones_do_not_swallow_each_other(self) -> None:
        """The vertical pad stays small on purpose.

        Run 06 put the two tables 0.01 apart, at 0.63 and 0.64. A vertical pad of
        0.03 would overlap them and re-create the split-table failure that took
        five runs to remove.
        """
        assert PAD_Y * 2 <= 0.02
