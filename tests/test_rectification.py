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
    ImageArray,
    RectifyError,
    crop,
    deskew,
    equalise,
    find_page_quad,
    rectify,
    skew_angle,
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

    def test_an_unusable_image_is_refused_rather_than_guessed_at(
        self, tmp_path: Path
    ) -> None:
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not an image at all")
        with pytest.raises(RectifyError, match="could not decode"):
            rectify(broken)


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
