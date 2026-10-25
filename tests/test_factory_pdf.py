"""Real PDF pages and their twins — spec 0020 §P.

A PDF printed here from an HTML page is the one real PDF a test can make
without a download, and its HTML is a twin known to be right. The gate
must admit it, and must refuse a twin with a word missing, a line broken
somewhere else, or a line moved down the page.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from doc_to_html import projection
from doc_to_html.factory import pdfpage

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

SOURCE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
@page { size: 816px 1056px; margin: 0; }
html, body { margin: 0; }
body { padding: 48px 56px; font-family: Georgia, serif; font-size: 14px; color: #111; }
h1 { font-size: 22px; margin: 0 0 12px; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #999; padding: 4px 6px; text-align: left; }
/*EXTRA*/
</style></head><body>
<h1>Form 77-B Statement of Account</h1>
<p>This statement lists the payments received<br>between 1 July and 30 September 2026.</p>
<table><tr><th>Date</th><th>Reference</th><th>Amount</th></tr>
<tr><td>07/04/2026</td><td>Payment received, thank you</td><td>120.00</td></tr>
<tr><td>08/11/2026</td><td>Office supplies</td><td>48.15</td></tr></table>
<p>Questions? Call 555-0100 between 9 a.m. and 5 p.m.</p>
</body></html>
"""

ZOOM = f"html {{ zoom: {pdfpage.WIDTH / 816} }}"
"""The twin is laid out at the render's width; the page was printed at 816."""


@pytest.fixture(scope="module")
def printed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not projection.available():
        pytest.skip("no headless Chrome on this machine")
    work = tmp_path_factory.mktemp("pdf")
    page = work / "source.html"
    page.write_text(SOURCE, encoding="utf-8")
    whole = work / "printed.pdf"
    subprocess.run([str(projection.CHROME), "--headless", "--disable-gpu",
                    "--no-pdf-header-footer", f"--print-to-pdf={whole}",
                    page.resolve().as_uri()], capture_output=True, timeout=120)
    single = work / "one.pdf"
    pdfpage.one_page(whole, 1, single)
    return single


def _gate(printed: Path, twin: str) -> pdfpage.Gate:
    pdf_lines = pdfpage.lines(pdfpage.pdf_words(printed, pdfpage.WIDTH))
    twin_lines = pdfpage.lines(pdfpage.twin_words(twin, pdfpage.WIDTH))
    return pdfpage.gate(pdf_lines, twin_lines, pdfpage.WIDTH)


@needs_chrome
class TestTheGate:
    def test_the_page_is_one_page_rendered_at_the_width(self, printed: Path,
                                                        tmp_path: Path) -> None:
        assert pdfpage.page_size(printed) == (612.0, 792.0)
        width, height = pdfpage.render(printed, pdfpage.WIDTH, tmp_path / "page.png")
        assert (width, height) == (1000, 1294) or (width, height) == (1000, 1295)

    def test_the_text_layer_reads_as_lines(self, printed: Path) -> None:
        found = [" ".join(line.words)
                 for line in pdfpage.lines(pdfpage.pdf_words(printed, pdfpage.WIDTH))]
        assert "This statement lists the payments received" in found
        assert "between 1 July and 30 September 2026." in found
        assert "Reference" in found and "Amount" in found

    def test_a_true_twin_is_admitted(self, printed: Path) -> None:
        result = _gate(printed, SOURCE.replace("/*EXTRA*/", ZOOM))
        assert result.failures == {}
        assert result.matched == result.lines == 13

    def test_a_twin_missing_a_word(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM).replace("Office supplies", "Office")
        result = _gate(printed, twin)
        assert "the twin lacks 'supplies'" in result.failures["words"]

    def test_a_twin_breaking_a_line_elsewhere(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM).replace(
            "payments received<br>between", "payments<br>received between")
        result = _gate(printed, twin)
        assert "words" not in result.failures
        assert any("payments received" in m for m in result.failures["lines"])

    def test_a_twin_with_a_line_moved_down(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM + " h1 { margin-bottom: 40px; }")
        result = _gate(printed, twin)
        assert set(result.failures) == {"geometry"}


class TestNormalising:
    def test_ligatures_soft_hyphens_and_case(self) -> None:
        assert pdfpage.normalise("ﬁnal") == "final"
        assert pdfpage.normalise("con­firmed") == "confirmed"
        assert pdfpage.normalise("TOTAL") == "total"

    def test_a_wide_gap_cuts_a_row_into_two_lines(self) -> None:
        words = [pdfpage.Word("Name", 0, 0, 40, 12, 12), pdfpage.Word("Ada", 45, 0, 70, 12, 12),
                 pdfpage.Word("Date", 200, 1, 240, 13, 12)]
        assert [line.words for line in pdfpage.lines(words)] == [("Name", "Ada"), ("Date",)]
