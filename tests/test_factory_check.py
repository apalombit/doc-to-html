"""The validator every corpus page passes — spec 0020 §V, step 2.

One sound page passes every check. Then each way a page can lie is
planted on a copy of it, and the check that exists for it must name it:
an external font, words inside an SVG, clipped text, a horizontal
overflow, a near-duplicate, and generated text (`::before` content and
`<ol>` auto-numbers) — the spec's list — and beside them text the colour
of its ground, a page in the wrong language, a feature the card asks for
and the page lacks, too few words for the card's density, and layout that
depends on the window.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from doc_to_html import projection
from doc_to_html.factory import check, fonts
from doc_to_html.factory.cards import Card

REPO = Path(__file__).resolve().parent.parent
ALLOWED = fonts.load(REPO / "corpus" / "fonts.json")

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

CARD = Card(id="t0001", origin="generated", family="transactional", language="en",
            kind="invoice", arrangement="arr.one_column", type="type.sans",
            features=("table.ruled", "table.totals", "kv.inline", "fig.logo",
                      "fmt.currency", "fmt.dates"),
            style="corporate-modern", width=820, density="medium", locale="en-GB")

SOUND = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><title>Invoice</title>
<style>
body { margin: 0; background: #ffffff; color: #1d2433;
       font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; }
.page { padding: 40px 48px; }
.head { display: flex; justify-content: space-between; align-items: center; }
.mark { display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; margin-top: 24px; }
th, td { border-bottom: 1px solid #c8ccd4; padding: 6px 8px; text-align: left; }
td.n { text-align: right; }
p { line-height: 1.5; }
/*EXTRA*/
</style></head>
<body><div class="page">
<div class="head">
  <div class="mark"><svg width="28" height="28" viewBox="0 0 28 28">
    <rect x="2" y="2" width="24" height="24" rx="6" fill="#2b6cb0"/></svg>
    <span>Harbourside Joinery Ltd</span></div>
  <div>Invoice no. HJ-2291<br>Date: 14/10/2026</div>
</div>
<p>Billed to: Mrs Eleanor Whitcombe, 18 Quarry Lane, Bristol BS3 4QT.
Thank you for your order. Please find below the work we carried out at the
property during the first week of October, with the materials used.</p>
<table>
<tr><th>Description</th><th>Qty</th><th>Price</th><th>Amount</th></tr>
<tr><td>Oak skirting board, fitted</td><td>12</td><td class="n">£8.50</td><td class="n">£102.00</td></tr>
<tr><td>Sash window repair, two panes</td><td>2</td><td class="n">£65.00</td><td class="n">£130.00</td></tr>
<tr><td>Labour, carpenter, per hour</td><td>6</td><td class="n">£32.00</td><td class="n">£192.00</td></tr>
<tr><td>Subtotal</td><td></td><td></td><td class="n">£424.00</td></tr>
<tr><td>VAT at 20%</td><td></td><td></td><td class="n">£84.80</td></tr>
<tr><td><b>Total due</b></td><td></td><td></td><td class="n"><b>£508.80</b></td></tr>
</table>
<p>Payment is due within 30 days of the invoice date. Our bank details are on
the back of this page. If you have any questions about this invoice, please
call the workshop on the number above and ask for the accounts office.</p>
<p>All timber is sourced from certified suppliers in the south west, and the
offcuts from your job have been taken back to the workshop for reuse. Any
fitted joinery is guaranteed against defects in workmanship for two years
from the date of fitting. Small marks and movement in the wood as it settles
over its first winter are normal, and we are happy to return and adjust any
door or window that sticks during that time at no extra charge.</p>
<!--BODY-->
</div></body></html>
"""


def _page(tmp_path: Path, html: str, name: str = "page") -> Path:
    path = tmp_path / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _with(extra_css: str = "", extra_body: str = "", base: str = SOUND) -> str:
    return base.replace("/*EXTRA*/", extra_css).replace("<!--BODY-->", extra_body)


@pytest.fixture(scope="module")
def sound(tmp_path_factory: pytest.TempPathFactory) -> check.Result:
    if not projection.available():
        pytest.skip("no headless Chrome on this machine")
    path = _page(tmp_path_factory.mktemp("sound"), SOUND)
    return check.check(CARD, path, ALLOWED, [])


def _twin(tmp_path: Path, html: str, picture: Path, card: Card = CARD) -> check.Result:
    """Checks 5-10 only, against the sound page's picture: what a planted
    fault in the HTML alone needs, at half the browser calls."""
    return check.check(card, _page(tmp_path, html), ALLOWED, [], twin=True, picture=picture)


@needs_chrome
class TestASoundPage:
    def test_it_passes_every_check(self, sound: check.Result) -> None:
        assert sound.failures == {}
        assert sound.passed

    def test_what_it_shows_is_detected(self, sound: check.Result) -> None:
        for fid in ("table", "table.empty_cells", "type.sans", "figure",
                    "fmt.currency", "fmt.dates"):
            assert fid in sound.detected, fid
        assert "look.dark_ground" not in sound.detected


@needs_chrome
class TestThePlantedFaults:
    def test_an_external_font(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with("body { font-family: Inter, sans-serif; }")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert "leads with 'Inter'" in result.failures["self_contained"]

    def test_a_font_face_rule(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with("@font-face { font-family: X; src: local(Arial); }")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert "@font-face" in result.failures["self_contained"]

    def test_a_url_in_an_attribute(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(extra_body='<a href="https://example.com/terms">Terms</a>')
        result = _twin(tmp_path, html, sound.picture or Path())
        assert "a URL in an attribute" in result.failures["self_contained"]

    def test_words_inside_an_svg(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(extra_body='<svg width="120" height="30"><text x="4" y="20">'
                     'HARBOURSIDE</text></svg>')
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("HARBOURSIDE" in m for m in result.failures["figures"])

    def test_generated_text_before(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with('td.n::before { content: "✓ "; }')
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("::before" in m for m in result.failures["generated"])

    def test_an_ol_that_numbers_itself(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(extra_body="<ol><li>Measure the frames</li><li>Fit the boards</li></ol>")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("numbers itself" in m for m in result.failures["generated"])

    def test_an_ol_with_its_numbers_written_passes(self, tmp_path: Path,
                                                   sound: check.Result) -> None:
        html = _with("ol { list-style: none; padding: 0; }",
                     "<ol><li>1. Measure the frames</li><li>2. Fit the boards</li></ol>")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert "generated" not in result.failures

    def test_automatic_hyphens(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with("p { hyphens: auto; }")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("hyphenate" in m for m in result.failures["generated"])

    def test_a_form_control(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(extra_body='<input type="text" value="Eleanor Whitcombe">')
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("form controls" in m for m in result.failures["generated"])

    def test_a_q_draws_its_quote_marks(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(extra_body="<p>She said <q>by Friday</q>.</p>")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert any("q::before" in m for m in result.failures["generated"])

    def test_a_near_duplicate(self, tmp_path: Path, sound: check.Result) -> None:
        assert sound.picture
        twin_of_sound = check.Known("c9999", frozenset(check.shingles(check.html_text(SOUND))),
                                    sound.dhash)
        result = check.check(CARD, _page(tmp_path, SOUND), ALLOWED, [twin_of_sound],
                             twin=True, picture=sound.picture)
        messages = result.failures["distinct"]
        assert any("shingles with c9999" in m for m in messages)
        assert any("bits from c9999" in m for m in messages)

    def test_the_wrong_language(self, tmp_path: Path, sound: check.Result) -> None:
        italian = replace(CARD, language="it", locale="it-IT")
        html = SOUND.replace('lang="en-GB"', 'lang="it"')
        result = _twin(tmp_path, html, sound.picture or Path(), italian)
        assert any("reads as en, not it" in m for m in result.failures["language"])

    def test_a_feature_the_card_asks_for_and_the_page_lacks(
            self, tmp_path: Path, sound: check.Result) -> None:
        card = replace(CARD, features=CARD.features + ("table.spanning",))
        result = _twin(tmp_path, SOUND, sound.picture or Path(), card)
        assert any(m.startswith("table.spanning") for m in result.failures["features"])

    def test_the_wrong_main_face(self, tmp_path: Path, sound: check.Result) -> None:
        result = _twin(tmp_path, SOUND, sound.picture or Path(), replace(CARD, type="type.serif"))
        assert any("the main face is sans" in m for m in result.failures["features"])

    def test_too_few_words_for_its_density(self, tmp_path: Path, sound: check.Result) -> None:
        result = check.check(replace(CARD, density="dense"), _page(tmp_path, SOUND), ALLOWED, [])
        assert f"{sound.words} words; a dense page 820 px wide holds at least 328" in (
            result.failures["features"])

    def test_a_viewport_height_unit(self, tmp_path: Path, sound: check.Result) -> None:
        html = _with(".page { min-height: 90vh; }")
        result = _twin(tmp_path, html, sound.picture or Path())
        assert "a viewport-height unit" in result.failures["fits"]


@needs_chrome
class TestThePlantedFaultsThatNeedThePicture:
    def test_clipped_text(self, tmp_path: Path) -> None:
        html = _with(".note { height: 18px; overflow: hidden; width: 200px; }",
                     '<div class="note">Deliveries are made between eight and six on '
                     'weekdays, and on Saturday mornings by arrangement.</div>')
        result = check.check(CARD, _page(tmp_path, html), ALLOWED, [])
        assert any("clip" in m for m in result.failures["fits"])

    def test_a_horizontal_overflow(self, tmp_path: Path) -> None:
        html = _with(".wide { width: 1300px; }",
                     '<div class="wide">Account 0042 7781 2290, sort code 20-45-77.</div>')
        result = check.check(CARD, _page(tmp_path, html), ALLOWED, [])
        assert any("wide" in m or "outside" in m for m in result.failures["fits"])

    def test_text_the_colour_of_its_ground(self, tmp_path: Path) -> None:
        html = _with(".ghost { color: #fefefe; }",
                     '<p class="ghost">Registered in England no. 08812291.</p>')
        result = check.check(CARD, _page(tmp_path, html), ALLOWED, [])
        assert any("Registered in England" in m for m in result.failures["ink"])

    def test_type_too_small_to_read(self, tmp_path: Path) -> None:
        html = _with(".fine { font-size: 5px; }",
                     '<p class="fine">Terms and conditions apply to every order.</p>')
        result = check.check(CARD, _page(tmp_path, html), ALLOWED, [])
        assert any("5.0 px" in m for m in result.failures["ink"])

    def test_a_page_taller_than_one_page(self, tmp_path: Path) -> None:
        html = _with(".tall { height: 2600px; }", '<div class="tall"></div>')
        result = check.check(CARD, _page(tmp_path, html), ALLOWED, [])
        assert any("over 2400" in m for m in result.failures["renders"])


class TestThePieces:
    def test_a_stack_may_lead_with_a_generic_that_draws_a_listed_face(self) -> None:
        assert check.face_problems(["monospace", "serif", '"Menlo", monospace'], ALLOWED) == []

    def test_a_stack_may_not_lead_with_the_system_face(self) -> None:
        assert check.face_problems(["system-ui, sans-serif"], ALLOWED) == ["leads with 'system-ui'"]

    def test_the_word_floor_by_density_width_and_kind(self) -> None:
        wide = replace(CARD, width=1000)
        assert check.word_floor(replace(wide, density="dense")) == 400
        assert check.word_floor(replace(wide, density="medium")) == 220
        assert check.word_floor(replace(wide, density="sparse")) == 0
        assert check.word_floor(replace(wide, density="dense", kind="ticket")) == 200
        assert check.word_floor(replace(wide, density="medium", width=500)) == 110
        assert check.word_floor(replace(wide, density="dense", family="fragments",
                                        kind="standalone table")) == 200

    def test_formats_by_language(self) -> None:
        assert check.FORMATS["fmt.eu_numbers"].search("Totale 1.234,56 €")
        assert check.FORMATS["fmt.eu_numbers"].search("Total : 1 234,56 €")
        assert not check.FORMATS["fmt.eu_numbers"].search("Total £1,250.00")
        assert check.FORMATS["fmt.dates"].search("24 ottobre 2026")
        assert check.FORMATS["fmt.dates"].search("October 24, 2026")
        assert check.FORMATS["fmt.dates"].search("24/10/2026")
        assert check.FORMATS["fmt.currency"].search("R$ 89,90")

    def test_each_language_reads_as_itself(self) -> None:
        samples = {
            "en": "Please find attached the invoice for the work carried out in October.",
            "it": "Le inviamo in allegato la fattura per i lavori eseguiti nel mese di ottobre.",
            "fr": "Veuillez trouver ci-joint la facture pour les travaux réalisés en octobre.",
            "es": "Le enviamos adjunta la factura por los trabajos realizados en el mes de octubre.",
            "pt": "Enviamos em anexo a fatura dos trabalhos realizados no mês de outubro.",
        }
        for lang, text in samples.items():
            scores = check.language_scores(text)
            assert max(scores, key=lambda k: scores[k]) == lang, (lang, scores)


class TestContactSheets:
    def test_twelve_to_a_sheet_each_labelled(self, tmp_path: Path) -> None:
        from PIL import Image

        from doc_to_html.factory import sheets

        pictures = []
        for index in range(14):
            path = tmp_path / f"p{index}.png"
            Image.new("RGB", (820, 400 + 40 * index), (255, 255, 255)).save(path)
            pictures.append(path)
        cards = [replace(CARD, id=f"t{index:04d}") for index in range(14)]
        written = sheets.sheets(cards, pictures, tmp_path / "out", "test")
        assert [p.name for p in written] == ["test-01.png", "test-02.png"]
        first = Image.open(written[0])
        assert first.width == sheets.GAP + sheets.ACROSS * (sheets.THUMB[0] + sheets.GAP)
