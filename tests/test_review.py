"""The instrument that checks the instrument.

`tools/visual_review.py` found nine cross-cutting faults that no scored axis
reported, and until now it had no tests of its own — which is the shape of
fault this project has been bitten by twice: *the tool between you and the
artefact is part of the measurement, and it lies quietly.* Headless Chrome
inherited the host's dark mode for eighty runs and every eyeballed comparison
in the project was an inverted page beside a light source.

None of these need a browser. The screenshot function is injected, so what is
tested is the pairing, the cutting and the tally — everything except Chrome,
which `tests/test_projection.py` pins separately.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from doc_to_html import review

REPO = Path(__file__).resolve().parent.parent


# --- cutting ----------------------------------------------------------------


def a_page(height: int, bands: list[tuple[int, int]], width: int = 200) -> Image.Image:
    """A white page with black bands at the given row ranges — ink where the
    bands are, a clean gutter everywhere else.

    Keep the bands a minority of the page, as type is on a real one: the ground
    is read as the page's median grey, so a fixture that is more than half ink
    is a fixture of a page turned inside out.
    """
    pixels = np.full((height, width, 3), 255, dtype=np.uint8)
    for top, bottom in bands:
        pixels[top:bottom] = 0
    return Image.fromarray(pixels)


def test_parts_for_splits_only_what_is_too_tall() -> None:
    assert review.parts_for(500, cap=1600) == 1
    assert review.parts_for(1600, cap=1600) == 1
    assert review.parts_for(1601, cap=1600) == 2
    assert review.parts_for(5166, cap=1600) == 4


def test_a_cut_lands_in_a_gutter_not_through_a_line() -> None:
    """A cut through the middle of a line of type is unreadable on both sheets
    it lands on."""
    page = a_page(600, [(20, 50), (120, 150), (400, 430), (500, 530)])
    profile = review.ink_profile(page)
    for cut in review.cut_rows(profile, 3):
        assert profile[cut] == 0, f"row {cut} has ink on it"


def test_cuts_follow_the_ink_not_the_pixels() -> None:
    """The whole reason a sheet needs cutting is that two panels hold the same
    content at different heights, so an equal-pixel cut pairs part 2 of the
    source with part 2 of nothing in particular."""
    top_heavy = a_page(900, [(20, 70), (100, 150), (180, 230), (260, 300)])
    cuts = review.cut_rows(review.ink_profile(top_heavy), 2)
    assert len(cuts) == 1
    assert cuts[0] < 400, "an equal-pixel cut would have landed at 450"


def test_a_blank_page_still_cuts() -> None:
    cuts = review.cut_rows(review.ink_profile(a_page(400, [])), 2)
    assert cuts == (200,)


def test_cuts_stay_ordered_and_inside_the_page() -> None:
    page = a_page(300, [(10, 30), (60, 80), (140, 160), (220, 240)])
    cuts = review.cut_rows(review.ink_profile(page), 4)
    assert len(cuts) == 3
    assert list(cuts) == sorted(set(cuts))
    assert 0 < cuts[0] and cuts[-1] < 300


def test_ink_is_read_on_a_dark_page_too() -> None:
    """`darkdeck_0009` and `cv_0013` are dark-grounded; a threshold that only
    knows dark-on-light reads a dark page as solid ink and cuts it anywhere."""
    pixels = np.full((200, 50, 3), 20, dtype=np.uint8)
    pixels[80:120] = 240
    profile = review.ink_profile(Image.fromarray(pixels))
    assert profile[0] == 0 and profile[100] == 50


# --- the sheet --------------------------------------------------------------


def test_a_short_document_is_one_sheet_with_both_panels(tmp_path: Path) -> None:
    left, right = tmp_path / "l.png", tmp_path / "r.png"
    a_page(300, [(50, 100)], width=400).save(left)
    a_page(340, [(60, 120)], width=400).save(right)

    parts = review.contact_sheet(
        [review.Panel("SOURCE", left), review.Panel("RENDER", right)],
        tmp_path / "sheet", stamp="run-x · today")

    assert [p.name for p in parts] == ["sheet.png"]
    sheet = Image.open(parts[0])
    assert sheet.width == 400 + 400 + review.GUTTER * 3
    assert sheet.height == 340 + review.LABEL_BAR + review.GUTTER


def test_the_label_bar_is_drawn_not_merely_reserved(tmp_path: Path) -> None:
    """It used to be reserved and left blank: thirty pixels of grey and none of
    the protection, and a confident backwards comparison is worse than none."""
    page = tmp_path / "p.png"
    a_page(200, [(10, 40)], width=400).save(page)
    parts = review.contact_sheet([review.Panel("SOURCE", page)],
                                 tmp_path / "s", stamp="run-x · today")
    bar = np.asarray(Image.open(parts[0]))[: review.LABEL_BAR]
    assert (bar == review.LABEL_INK).all(axis=2).any(), "nothing was written"


def test_a_tall_document_becomes_several_readable_sheets(tmp_path: Path) -> None:
    """`statement_0006`'s sheet was 5166px and arrived at the one step of this
    workflow that finds anything at 30% scale."""
    left, right = tmp_path / "l.png", tmp_path / "r.png"
    a_page(600, [(i, i + 10) for i in range(0, 580, 40)], width=300).save(left)
    a_page(2400, [(i, i + 40) for i in range(0, 2320, 160)], width=300).save(right)

    parts = review.contact_sheet(
        [review.Panel("SOURCE", left), review.Panel("RENDER", right)],
        tmp_path / "sheet", stamp="run-x · today", cap=800)

    assert [p.name for p in parts] == [f"sheet-p{k}.png" for k in (1, 2, 3)]
    assert all(Image.open(p).height
               <= 800 * review.OVERRUN + review.LABEL_BAR + review.GUTTER
               for p in parts)
    assert sum(Image.open(p).height - review.LABEL_BAR - review.GUTTER
               for p in parts) == 2400


def test_a_sheet_needs_a_panel(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        review.contact_sheet([], tmp_path / "s", stamp="x")


# --- building off a run -----------------------------------------------------


class FakeChrome:
    """Records what width it was asked for, and writes a page of that width."""

    def __init__(self, height: int = 700) -> None:
        self.calls: list[tuple[Path, int]] = []
        self.height = height

    def __call__(self, html: Path, destination: Path, *, width: int,
                 height: int | None = None) -> Path:
        self.calls.append((html, width))
        destination.parent.mkdir(parents=True, exist_ok=True)
        a_page(self.height, [(20, 60)], width=width).save(destination)
        return destination


def a_run(root: Path, label: str, documents: dict[str, str | None],
          scores: dict[str, Any] | None = None) -> Path:
    run = root / label
    for name, html in documents.items():
        folder = run / "dump" / "qwen3-vl_4b" / name
        folder.mkdir(parents=True, exist_ok=True)
        if html is not None:
            (folder / "document.html").write_text(html)
    if scores is not None:
        (run / "scores.json").write_text(json.dumps(scores))
    return run


def test_both_panels_are_laid_out_at_the_source_width(tmp_path: Path) -> None:
    """A page compared against itself at two widths is two different pages."""
    run = a_run(tmp_path, "99-test", {"invoice_0001": "<p>hi</p>"})
    chrome = FakeChrome()
    sheets, out = review.build(run, render=chrome)

    assert [width for _, width in chrome.calls] == [862]
    assert sheets[0].width == 862
    sheet = Image.open(sheets[0].parts[0])
    assert sheet.width == 862 * 2 + review.GUTTER * 3


def test_a_document_with_no_render_is_skipped_and_said_so(tmp_path: Path) -> None:
    run = a_run(tmp_path, "99-test",
                {"invoice_0001": "<p>hi</p>", "statement_0006": None})
    sheets, out = review.build(run, render=FakeChrome())

    assert [sheet.document for sheet in sheets] == ["invoice_0001"]
    assert "statement_0006: no document.html" in (out / "review.md").read_text()


def test_the_run_label_and_the_date_reach_every_output(tmp_path: Path) -> None:
    """A reading from one session and one from another are not comparable, so
    nothing this produces may travel without saying which sitting it came
    from."""
    run = a_run(tmp_path, "99-test", {"invoice_0001": "<p>hi</p>"})
    _, out = review.build(run, render=FakeChrome())
    stamp = f"99-test · {date.today().isoformat()}"
    for name in ("review.md", "numbers.md"):
        assert stamp in (out / name).read_text()
    assert json.loads((out / "findings.json").read_text())["stamp"] == stamp


def test_a_previous_run_becomes_a_third_panel_and_the_changed_axis(
        tmp_path: Path) -> None:
    """The comparison the ratchet is built on, and the one this workflow could
    not make: whether the render *moved*, not how far it sits from its source."""
    older = a_run(tmp_path, "98-older", {"invoice_0001": "<p>old</p>"})
    run = a_run(tmp_path, "99-test", {"invoice_0001": "<p>new</p>"})
    chrome = FakeChrome()
    sheets, out = review.build(run, previous=older, render=chrome)

    assert [html.parent.parent.parent.parent.name for html, _ in chrome.calls] \
        == ["98-older", "99-test"]
    assert Image.open(sheets[0].parts[0]).width == 862 * 3 + review.GUTTER * 4
    record = json.loads((out / "findings.json").read_text())
    assert record["previous"] == "98-older"
    assert "changed" in record["rubric"]
    assert "changed" in record["documents"][0]["axes"]


def test_without_a_previous_run_there_is_no_changed_axis(tmp_path: Path) -> None:
    run = a_run(tmp_path, "99-test", {"invoice_0001": "<p>hi</p>"})
    _, out = review.build(run, render=FakeChrome())
    record = json.loads((out / "findings.json").read_text())
    assert "changed" not in record["rubric"]


def test_a_filled_findings_file_is_never_overwritten(tmp_path: Path) -> None:
    """Rebuilding the sheets after answering half of them must not throw the
    answers away."""
    run = a_run(tmp_path, "99-test", {"invoice_0001": "<p>hi</p>"})
    _, out = review.build(run, render=FakeChrome())
    (out / "findings.json").write_text('{"mine": true}')
    review.build(run, render=FakeChrome())
    assert json.loads((out / "findings.json").read_text()) == {"mine": True}
    assert (out / "findings.blank.json").exists()


# --- the tally --------------------------------------------------------------


def a_scores(name: str = "invoice_0001", **ratios: float) -> dict[str, Any]:
    values = {"recall": 1.0, "precision": 1.0, "join_recall": 1.0, "tau": 1.0}
    values.update(ratios)
    return {"label": "99-test", "documents": [{
        "name": name,
        "completeness": {"recall": values["recall"],
                         "precision": values["precision"],
                         "join_recall": values["join_recall"]},
        "order": {"tau": values["tau"]},
        "layout": {"beside_agreement": 1.0, "height_ratio": 1.0},
        "palette": {"ink_delta": 0.0},
    }]}


def answered(**axes: tuple[str, str]) -> dict[str, Any]:
    record = review.blank_findings(["invoice_0001"], stamp="99-test · today",
                                   run="99-test", previous=None,
                                   model="qwen3-vl:4b")
    for axis, (verdict, note) in axes.items():
        record["documents"][0]["axes"][axis] = {"verdict": verdict, "note": note}
    record["documents"][0]["owner"] = "A0"
    return record


def test_a_major_beside_perfect_ratios_is_named_unreported() -> None:
    """`sample_table_0003` scored a full match having deleted every column
    header of its only table. One is not a threshold somebody chose; it is the
    ceiling."""
    summary = review.summarise(
        answered(content=("major", "the table has no header row")),
        scores=a_scores())
    assert [(f.document, f.axis) for f in summary.unreported] \
        == [("invoice_0001", "content")]


def test_a_major_the_numbers_did_notice_is_not_unreported() -> None:
    summary = review.summarise(
        answered(content=("major", "the sidebar is gone")),
        scores=a_scores(recall=0.57))
    assert summary.unreported == ()


def test_a_minor_is_not_unreported() -> None:
    summary = review.summarise(answered(chrome=("minor", "bar is pale")),
                               scores=a_scores())
    assert summary.unreported == ()


def test_the_tally_says_which_axes_fired_and_which_never_did() -> None:
    """The rubric is a guess with two passes behind it. This is the evidence a
    later session needs before anyone freezes seven axes."""
    summary = review.summarise(
        answered(content=("major", "x"), colour=("match", "y")))
    assert summary.axis_tally["content"]["major"] == 1
    assert summary.axis_tally["colour"]["match"] == 1
    assert "rhythm" in summary.missing_axes
    assert summary.owner_tally["A0"] == 1


def test_a_trial_axis_is_kept_not_rejected() -> None:
    """Trialling an eighth axis must not require editing the module that
    declares the seven."""
    record = answered(content=("major", "x"))
    record["documents"][0]["axes"]["figures"] = {"verdict": "major",
                                                 "note": "placeholder"}
    summary = review.summarise(record)
    assert summary.unknown_axes == ("figures",)
    assert summary.axis_tally["figures"]["major"] == 1


def test_deltas_are_only_reported_against_a_previous_run() -> None:
    summary = review.summarise(answered(), scores=a_scores(recall=0.8),
                               previous_scores=a_scores(recall=0.6))
    assert summary.deltas["invoice_0001"]["recall"] == pytest.approx(0.2)
    assert review.summarise(answered(), scores=a_scores()).deltas \
        == {"invoice_0001": {}}


def test_the_written_report_names_the_unreported_fault() -> None:
    record = answered(content=("major", "the table has no header row"))
    summary = review.summarise(record, scores=a_scores())
    text = review.report_md(record, summary)
    assert "the table has no header row" in text
    assert "99-test · today" in text


# --- the general case -------------------------------------------------------


def test_an_arbitrary_pair_needs_no_run(tmp_path: Path) -> None:
    """A hand-written page against a photograph, outside any run directory."""
    source, render_png = tmp_path / "s.png", tmp_path / "r.png"
    a_page(300, [(10, 40)], width=400).save(source)
    a_page(300, [(10, 40)], width=400).save(render_png)
    parts = review.pair(source, render_png, tmp_path / "out", label="mine")
    assert [p.name for p in parts] == ["mine.png"]
    assert render_png.exists(), "an input must not be consumed"


def test_parts_rise_until_the_cap_is_actually_met() -> None:
    """`statement_0006` is 84% ink in its first 1900 rows — a dense table — and
    3200 sparse rows of repeated caveats after it. An ink-mass cut put all
    three cuts in the table and delivered the tail as one 3316px sheet."""
    front_heavy = a_page(
        4000, [(i, i + 30) for i in range(0, 1800, 45)]
        + [(i, i + 10) for i in range(1900, 3960, 240)], width=200)
    even = a_page(1000, [(i, i + 10) for i in range(0, 980, 40)], width=200)

    cut = review.plan([even, front_heavy], cap=900)

    assert len({len(slices) for slices in cut}) == 1, "panels must pair"
    assert max(bottom - top for slices in cut
               for top, bottom in slices) <= 900 * review.OVERRUN


def test_no_scores_is_not_reported_as_the_numbers_having_noticed() -> None:
    """An empty `unreported` means two very different things, and a summary
    that cannot tell them apart is the same quiet lie this workflow exists to
    catch."""
    record = answered(content=("major", "the table has no header row"))
    summary = review.summarise(record)
    assert summary.unreported == () and summary.cross_checked == ()
    assert "Not checked" in review.report_md(record, summary)

    checked = review.summarise(record, scores=a_scores(recall=0.5))
    assert checked.cross_checked == ("invoice_0001",)
    assert "Not checked" not in review.report_md(record, checked)


# --- the render re-photographed, spec 0018, 0a ------------------------------


class Outline:
    """What `preprocess.page_outline` hands over, built by hand."""

    def __init__(self, quad: list[list[float]], surround: tuple[int, int, int]) -> None:
        self.quad = np.array(quad, dtype=np.float32)
        self.surround = surround


def test_the_render_lands_on_the_outline() -> None:
    """The render draws its paper at `paper_box` of the outline, and that
    rectangle is carried onto the outline: a mark in each of the paper's
    corners lands in the turned outline's corner."""
    from doc_to_html.preprocess import paper_box

    centre, turn = np.array([200.0, 150.0]), np.radians(4.0)
    spin = np.array([[np.cos(turn), -np.sin(turn)], [np.sin(turn), np.cos(turn)]])
    corners = [centre + spin @ np.array(corner) for corner in
               ((-150, -100), (150, -100), (150, 100), (-150, 100))]
    outline = Outline([list(corner) for corner in corners], (60, 65, 72))
    paper = paper_box(outline.quad, 400, 300)
    render = np.full((300, 400, 3), 255, dtype=np.uint8)
    left, top = round(paper.left * 400), round(paper.top * 300)
    right, bottom = round(paper.right * 400), round(paper.bottom * 300)
    for x, y in ((left, top), (right - 6, top), (right - 6, bottom - 6), (left, bottom - 6)):
        render[y:y + 6, x:x + 6] = 0
    photo, offset = review.rephotograph(Image.fromarray(render), outline, (400, 300))
    dark = np.asarray(photo.convert("L")) < 128
    for corner in corners:
        x, y = (int(v) for v in corner + np.array(offset))
        near = dark[max(0, y - 8):y + 8, max(0, x - 8):x + 8]
        assert near.sum() > 10, f"no mark near {corner}"


def test_a_render_taller_than_its_paper_overhangs() -> None:
    """The overhang is information, so the picture grows to hold it."""
    outline = Outline([[20, 10], [180, 10], [180, 110], [20, 110]], (60, 65, 72))
    render = Image.new("RGB", (200, 300), (255, 255, 255))
    photo, offset = review.rephotograph(render, outline, (200, 120))
    assert photo.width == 200 and photo.height >= 300 - 1
    assert offset == (0, 0)


def test_the_overlay_shows_each_sides_ink_in_its_own_colour() -> None:
    """Cyan is the source's alone, red the render's alone, dark both."""
    source = np.full((10, 30, 3), 255, dtype=np.uint8)
    render = np.full((10, 30, 3), 255, dtype=np.uint8)
    source[:, 0:10] = 0
    source[:, 20:30] = 0
    render[:, 10:30] = 0
    laid = np.asarray(review.overlay(Image.fromarray(source), Image.fromarray(render),
                                     (0, 0), (60, 65, 72)))
    assert tuple(laid[5, 5]) == (0, 255, 255)
    assert tuple(laid[5, 15]) == (255, 0, 0)
    assert tuple(laid[5, 25]) == (0, 0, 0)


def test_a_photographed_page_gains_a_second_row(tmp_path: Path) -> None:
    """`ticket_0020` is warped by `rectify`, so its sheet carries each
    render re-photographed and its overlay under the first row."""
    older = a_run(tmp_path, "98-older", {"ticket_0020": "<p>old</p>"})
    run = a_run(tmp_path, "99-test", {"ticket_0020": "<p>new</p>",
                                      "invoice_0001": "<p>hi</p>"})
    sheets, out = review.build(run, previous=older, render=FakeChrome(height=400))
    by_name = {sheet.document: sheet for sheet in sheets}

    ticket = Image.open(by_name["ticket_0020"].parts[0])
    assert ticket.width >= 900 * 4 + review.GUTTER * 5
    assert ticket.height > 2 * (400 + review.LABEL_BAR)
    invoice = Image.open(by_name["invoice_0001"].parts[0])
    assert invoice.height == 563 + review.LABEL_BAR + review.GUTTER, "one row"
    assert sorted(p.name for p in out.iterdir() if p.suffix == ".png") == [
        "00-invoice_0001.png", "01-ticket_0020.png"], "scratch panels are removed"
