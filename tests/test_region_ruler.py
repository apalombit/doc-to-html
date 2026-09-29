"""`preprocess.count_regions`, the ruler that counts regions of ink. No model.

It used to be stated as a ceiling in the vision layout prompt, which spec
0007's queue deleted in Q4 along with the prompt. The ruler stays: it is how
`test_content_loss` shows a turned-over dark page gives grouping something to
work with, and `tools/cv_layout_probe.py` re-calibrates it.
"""

from __future__ import annotations

from pathlib import Path

from doc_to_html.preprocess import REGION_GAP, count_regions, rectify

REPO = Path(__file__).resolve().parent.parent


class TestTheRulerOnRealPages:
    """The two fixtures `REGION_GAP` is calibrated against.

    Characterization, deliberately: these numbers are the entire basis for
    stating a bound rather than a count, and the functions behind them were
    moved out of `tools/cv_layout_probe.py` where nothing in the suite ran them.
    If the promotion ever changes behaviour, it changes here first.
    """

    def test_it_overcounts_the_flat_page(self) -> None:
        """`invoice_0001` has 6 regions and measures 8.

        The overcount is the point. 6 is comfortably under the bound, so a page
        the model already reads correctly feels no pressure to split — which is
        what makes this safe to switch on.
        """
        assert count_regions(rectify(REPO / "example" / "invoice.png").image) == 8

    def test_it_overcounts_the_nested_page_too(self) -> None:
        """`invoice_0002` has 10 regions and measures 11.

        Nearly exact, and far below the 72 the model returns unprompted. This is
        the number that has to bind.
        """
        assert count_regions(rectify(REPO / "example" / "invoice2.png").image) == 11

    def test_a_wider_gap_welds_the_nested_page_into_one(self) -> None:
        """Why `REGION_GAP` is not tuned to whichever fixture is in front of you.

        At 0.08 `invoice_0001` measures a correct 6 — and `invoice_0002`
        collapses to a single region, which as a ceiling would be catastrophic.
        The joint value is the only honest one, and this is the trap it avoids.
        """
        page = rectify(REPO / "example" / "invoice2.png").image
        assert count_regions(page, gap=0.08) == 1
        assert count_regions(page, gap=REGION_GAP) == 11
