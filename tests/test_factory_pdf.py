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
    return pdfpage.gate(pdfpage.pdf_words(printed, pdfpage.WIDTH),
                        pdfpage.twin_words(twin, pdfpage.WIDTH), pdfpage.WIDTH)


@needs_chrome
class TestTheGate:
    def test_the_page_is_one_page_rendered_at_the_width(self, printed: Path,
                                                        tmp_path: Path) -> None:
        assert pdfpage.page_size(printed) == (612.0, 792.0)
        width, height = pdfpage.render(printed, pdfpage.WIDTH, tmp_path / "page.png")
        assert (width, height) == (1000, 1294) or (width, height) == (1000, 1295)

    def test_the_text_layer_reads_as_rows(self, printed: Path) -> None:
        found = [row.shown for row in pdfpage.rows(pdfpage.pdf_words(printed, pdfpage.WIDTH))]
        assert "This statement lists the payments received" in found
        assert "between 1 July and 30 September 2026." in found
        assert ["Date", "Reference", "Amount"] == found[3:6]

    def test_a_true_twin_is_admitted(self, printed: Path) -> None:
        result = _gate(printed, SOURCE.replace("/*EXTRA*/", ZOOM))
        assert result.failures == {}
        assert result.matched == result.rows == 13

    def test_a_twin_missing_a_word(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM).replace("Office supplies", "Office")
        result = _gate(printed, twin)
        assert any(m.startswith("the twin lacks") for m in result.failures["words"])
        assert any("Office supplies" in m for m in result.failures["rows"])

    def test_a_twin_breaking_a_line_elsewhere(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM).replace(
            "payments received<br>between", "payments<br>received between")
        result = _gate(printed, twin)
        assert "words" not in result.failures
        assert any("payments received" in m for m in result.failures["rows"])

    def test_a_twin_with_a_line_moved_down(self, printed: Path) -> None:
        twin = SOURCE.replace("/*EXTRA*/", ZOOM + " h1 { margin-bottom: 40px; }")
        result = _gate(printed, twin)
        assert set(result.failures) == {"geometry"}


class TestNormalising:
    def test_ligatures_soft_hyphens_and_case(self) -> None:
        assert pdfpage.normalise("ﬁnal") == "final"
        assert pdfpage.normalise("con\xadfirmed") == "confirmed"
        assert pdfpage.normalise("TOTAL") == "total"

    def test_white_space_and_accents_as_text_layers_get_them_wrong(self) -> None:
        """The pilot's text layers, each beside what the picture shows."""
        for layer, picture in [("Whenyoumakeaclaim", "When you make a claim"),
                               ("1.IDENTIFICAÇÃO", "1. IDENTIFICAÇÃO"),
                               ("P esquisa", "Pesquisa"),
                               ("Brynjarsd´ottir", "Brynjarsdóttir"),
                               ("λˆ", "λ̂"), ("𝔼[L", "E[L"), ("zero\u200bwidth", "zerowidth")]:
            assert pdfpage.normalise(layer) == pdfpage.normalise(picture), layer

    def test_the_listing_marks_which_gaps_the_twin_must_keep(self) -> None:
        words = [pdfpage.Word("Name", 0, 0, 40, 12, 12), pdfpage.Word("Ada", 45, 0, 70, 12, 12),
                 pdfpage.Word("Lovelace", 100, 0, 150, 12, 12),
                 pdfpage.Word("Date", 200, 1, 240, 13, 12)]
        assert pdfpage.listing(words) == ["    0.0  12.0  0 Name Ada  | 100 Lovelace  ‖ 200 Date"]


def _row(*words: tuple[str, float]) -> list[pdfpage.Word]:
    """Words on one row at 12 px, each placed at its left edge, 7 px a letter."""
    return [pdfpage.Word(text, left, 0, left + 7 * len(text), 12, 12) for text, left in words]


class TestRows:
    def _gate(self, pdf: list[pdfpage.Word], twin: list[pdfpage.Word]) -> pdfpage.Gate:
        return pdfpage.gate(pdf, twin, pdfpage.WIDTH)

    def test_spaces_the_text_layer_lacks_are_allowed(self) -> None:
        result = self._gate(_row(("Whenyoumakeaclaim", 40)),
                            _row(("When", 40), ("you", 75), ("make", 100), ("a", 133), ("claim", 145)))
        assert result.failures == {}

    def test_a_justified_line_may_be_one_piece(self) -> None:
        """Word spaces of 2 em cut the PDF's row into pieces; the twin's
        paragraph keeps the line whole, and that is allowed."""
        result = self._gate(_row(("Solicito", 0), ("a", 80), ("Pesquisa", 111)),
                            _row(("Solicito", 0), ("a", 60), ("Pesquisa", 71)))
        assert result.failures == {}

    def test_heads_the_text_layer_runs_together_may_be_cells(self) -> None:
        result = self._gate(_row(("CONSUNTIVO", 0), ("AL", 80)),
                            _row(("CONSUNTIVO", 0), ("AL", 95)))
        assert result.failures == {}

    def test_a_column_the_pdf_sets_apart_must_stay_apart(self) -> None:
        result = self._gate(_row(("Name", 0), ("Ada", 200)),
                            _row(("Name", 0), ("Ada", 35)))
        assert any("sets it apart" in m for m in result.failures["rows"])

    def test_a_piece_out_of_place_is_refused(self) -> None:
        result = self._gate(_row(("Name", 0), ("Ada", 200)),
                            _row(("Name", 0), ("Ada", 240)))
        assert any("'ada' begins 40 px across" in m for m in result.failures["geometry"])


def _block(text: str, left: float, top: float, right: float, *, tag: str = "div",
           cell: int = -1, rows: int = 1) -> pdfpage.TwinBlock:
    return pdfpage.TwinBlock(tag, cell, 16.0, 400, "Arial", left, top, right, rows, text)


class TestSplitParagraphs:
    def test_a_paragraph_cut_into_one_block_a_line_is_reported(self) -> None:
        lines = [_block("Table 2 reports empirical miscoverage", 150, 517, 850),
                 _block("observed weekly cases, and average", 150, 541, 850),
                 _block("and the MCMC baseline.", 150, 565, 400)]
        assert len(pdfpage.split_paragraphs(lines)) == 1

    def test_a_stack_of_short_items_is_not(self) -> None:
        stack = [_block("12 Mill Lane", 40, 100, 160), _block("Leeds", 40, 120, 90),
                 _block("LS2 7DT", 40, 140, 110)]
        assert pdfpage.split_paragraphs(stack) == []

    def test_a_paragraph_that_is_one_block_is_not(self) -> None:
        whole = [_block("Table 2 reports ... the MCMC baseline.", 150, 517, 850, tag="p", rows=3)]
        assert pdfpage.split_paragraphs(whole) == []

    def test_cells_are_blocks_on_purpose(self) -> None:
        column = [_block("Radius-based", 267, 200, 380, tag="td", cell=0),
                  _block("Posterior-based", 267, 220, 390, tag="td", cell=4)]
        assert pdfpage.split_paragraphs(column) == []

    def test_lines_inside_one_cell_are_reported(self) -> None:
        cell = [_block("Stato di", 722, 164, 790, cell=3), _block("avanzamento %", 699, 187, 810, cell=3)]
        assert len(pdfpage.split_paragraphs(cell)) == 1

    def test_a_line_cut_into_words_is_reported(self) -> None:
        words = [_block("Solicito", 82, 640, 140), _block("a", 150, 640, 158),
                 _block("Pesquisa", 180, 640, 245)]
        assert any("words of one line" in m for m in pdfpage.split_paragraphs(words))

    def test_cells_set_apart_on_one_row_are_not(self) -> None:
        row = [_block("Name", 0, 100, 40, tag="td", cell=0),
               _block("Ada", 45, 100, 70, tag="td", cell=1)]
        assert pdfpage.split_paragraphs(row) == []


def _at(text: str, left: float, middle: float, size: float = 12.0) -> pdfpage.Word:
    """A word of `size` px type centred on `middle`, 0.6 of its size a letter."""
    return pdfpage.Word(text, left, middle - size / 2, left + 0.6 * size * len(text),
                        middle + size / 2, size)


class TestPieces:
    """Small things set between two rows decide nothing, either side."""

    def test_a_label_after_a_line_may_sit_in_a_row_of_its_own(self) -> None:
        """The W-9's `or`, 2.7 em after a line in the PDF, a few px lower in
        the twin: the PDF's row runs on into it and the twin's does not."""
        line = [_at("see", 0, 100), _at("How", 25, 100), _at("to", 55, 100)]
        pdf = line + [_at("or", 101, 100)]
        twin = line + [_at("or", 101, 107)]
        assert pdfpage.gate(pdf, twin, pdfpage.WIDTH).failures == {}

    def test_a_cells_second_line_half_a_line_up_is_its_own_piece(self) -> None:
        pdf = [_at("number", 0, 327), _at("household", 60, 321)]
        twin = [_at("number", 0, 327), _at("household", 60, 314)]
        assert pdfpage.gate(pdf, twin, pdfpage.WIDTH).failures == {}

    def test_a_column_run_on_is_still_refused(self) -> None:
        pdf = [_at("Name", 0, 100), _at("Ada", 200, 100)]
        twin = [_at("Name", 0, 100), _at("Ada", 40, 100)]
        assert "rows" in pdfpage.gate(pdf, twin, pdfpage.WIDTH).failures

    def test_type_set_smaller_than_the_page_is_pointed_at(self) -> None:
        pdf = [_at("Total", 0, 100, 12.0)]
        twin = [_at("Total", 0, 100, 10.0)]
        result = pdfpage.gate(pdf, twin, pdfpage.WIDTH)
        assert result.failures == {} and len(result.type_off) == 1


class TestTurned:
    """Text set at an angle: compared by its characters, never by rows."""

    MARGIN = [pdfpage.Word(char, 950, 900 - 8 * i, 958, 908 - 8 * i, 8, upright=False)
              for i, char in enumerate("cve: BOE-A-2025-6771")]

    def test_a_turned_margin_is_in_the_words_test_only(self) -> None:
        row = _row(("Núm.", 0), ("81", 40))
        twin = row + [pdfpage.Word(w, 940, 700, 948, 760, 8, upright=False)
                      for w in ("cve:", "BOE-A-2025-6771")]
        assert pdfpage.gate(row + self.MARGIN, twin, pdfpage.WIDTH).failures == {}

    def test_a_twin_without_it_lacks_its_characters(self) -> None:
        row = _row(("Núm.", 0), ("81", 40))
        result = pdfpage.gate(row + self.MARGIN, row, pdfpage.WIDTH)
        assert set(result.failures) == {"words"}

    def test_the_twin_reads_a_rotated_element_as_turned(self) -> None:
        html = ("<!doctype html><html><body style='margin:0'><p>Núm. 81</p>"
                "<div style='position:absolute;left:900px;top:600px;"
                "transform:rotate(-90deg)'>cve: BOE-A-2025-6771</div></body></html>")
        words = pdfpage.twin_words(html, pdfpage.WIDTH)
        assert [w.text for w in words if w.upright] == ["Núm.", "81"]
        assert pdfpage.turned(words) == "cve:BOE-A-2025-6771"



class TestBands:
    def test_a_browsers_taller_boxes_band_as_the_pdfs_do(self) -> None:
        """Two lines of 10 px type set 6 px apart, as a form's stacked
        label is: the PDF's boxes are 10 px tall and the browser's 12.2.
        Banded by its boxes, the twin's second line fell inside the first's
        band and the PDF's did not."""
        pdf = [pdfpage.Word("Codigo", 0, 100, 40, 110, 10), pdfpage.Word("NIF", 0, 106, 20, 116, 10)]
        twin = [pdfpage.Word("Codigo", 0, 98.9, 40, 111.1, 10),
                pdfpage.Word("NIF", 0, 104.9, 20, 117.1, 10)]
        assert len(pdfpage.rows(pdf)) == len(pdfpage.rows(twin)) == 2
        assert pdfpage.gate(pdf, twin, pdfpage.WIDTH).failures == {}

    def test_a_two_line_label_beside_a_heading_is_three_rows(self) -> None:
        """The W-9's corner: two lines of small type in one column, one line
        of larger type in the next, set between them. Banded alone, the
        heading's band took both label lines and their words interleaved."""
        words = [pdfpage.Word("Department", 0, 100, 60, 107, 7),
                 pdfpage.Word("Internal", 0, 108, 40, 115, 7),
                 pdfpage.Word("Go", 200, 102, 215, 113, 11)]
        assert sorted(r.text for r in pdfpage.rows(words)) == ["department", "go", "internal"]
