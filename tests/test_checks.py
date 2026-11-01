"""Spec 0021, step 2: the derived checks.

Three kinds of evidence, each on real corpus pages:

- **the known faults**: the three faults no scored number catches, found in
  the probe's committed outputs exactly as the probe's notes describe them;
- **mutations**: a fault injected into a real dev page — a value moved a
  column, a rule removed, a numbered list turned to bullets — is found by
  its own check, and by nothing that has no business firing;
- **identity**: a page against itself raises nothing.

A mutation runs in the page itself, at `DOMContentLoaded`, before the
reading; the source is read as it is, so the pair differ by exactly the
mutation.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
from PIL import Image

from doc_to_html import corpus, projection
from doc_to_html.checks import FACE_CLASS, PageCheck, check, check_page
from doc_to_html.projection import Projection, project

REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "docs" / "level-up-probe" / "out"

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

SEED = 20261030


# --- the known faults -------------------------------------------------------


@needs_chrome
class TestTheKnownFaults:
    """spec 0021's facts: what the probe's outputs do, and what the scorer
    could not see."""

    def test_the_lab_reports_results_drawn_under_flag(self) -> None:
        result = check_page("probe_labreport", PROBE / "labreport" / "render.html")
        moved = sorted(f.element for f in result.faults
                       if (f.check, f.fault) == ("cells", "wrong column"))
        assert moved == ["231", "6.4", "84", "92"]
        assert all("under 'Flag'" in f.note for f in result.faults if f.fault == "wrong column")

    def test_the_quizs_cells_merged_by_missing_rules(self) -> None:
        result = check_page("probe_quiz", PROBE / "quiz" / "render.html")
        (merged,) = [f for f in result.faults if f.fault == "cells merged as drawn"]
        assert merged.note.startswith("4 of the ")
        assert not [f for f in result.faults if f.check == "cells"]

    def test_the_recipes_method_interleaved_and_drawn_as_bullets(self) -> None:
        result = check_page("probe_recipe", PROBE / "recipe" / "render.html")
        kinds = {(f.check, f.fault) for f in result.faults}
        assert ("order", "interleaved") in kinds
        assert ("structure", "numbers as bullets") in kinds
        interleaved = [f.element for f in result.faults if f.fault == "interleaved"]
        assert any("Heat the oven" in element and "butternut" in element
                   for element in interleaved)


# --- mutations ----------------------------------------------------------------


def _read(page_id: str, script: str | None) -> tuple[Projection, Projection]:
    source = corpus.page(page_id)
    width = Image.open(source.png_path()).width
    html = source.html_path().read_text(encoding="utf-8")
    mine = project(html, width=width, flat=True, detail=True)
    if script is None:
        return mine, mine
    mutation = ("<script>document.addEventListener('DOMContentLoaded', () => {" + script
                + "});</script>")
    changed = html.replace("</body>", mutation + "</body>", 1) if "</body>" in html \
        else html + mutation
    return mine, project(changed, width=width, flat=True, detail=True)


def _pages(feature: str | None, wanted: int, fits: object = None) -> list[str]:
    """Dev pages carrying `feature` (any page when None), shuffled by seed;
    the test takes the first `wanted` its mutation can be applied to."""
    manifest = corpus.manifest()
    pages = sorted(page_id for page_id in corpus.names("dev")
                   if feature is None or feature in (manifest[page_id].get("features") or ())
                   or feature in (manifest[page_id].get("arrangement"), manifest[page_id].get("type")))
    random.Random(f"{SEED}:{feature}:{wanted}").shuffle(pages)
    return pages


def _assert_found(result: PageCheck, expected: tuple[str, str], allowed: set[str]) -> None:
    kinds = {(f.check, f.fault) for f in result.faults}
    assert expected in kinds, (result.page, sorted(kinds))
    stray = [(f.check, f.fault, f.element) for f in result.faults if f.check not in allowed]
    assert not stray, (result.page, stray)


def _applied(feature: str | None, count: int, target: object, expected: tuple[str, str],
             allowed: set[str]) -> None:
    done = 0
    for page_id in _pages(feature, count):
        source = corpus.page(page_id)
        width = Image.open(source.png_path()).width
        mine = project(source.html_path(), width=width, flat=True, detail=True)
        script = target(mine, source.html_path().read_text(encoding="utf-8"))  # type: ignore[operator]
        if script is None:
            continue
        mine, theirs = _read(page_id, script)
        assert mine.detail is not None and theirs.detail is not None
        if [(w.text, w.rect) for w in mine.detail.words] == \
                [(w.text, w.rect) for w in theirs.detail.words] and mine.height == theirs.height:
            continue  # a mutation the reader cannot see is not a test of anything
        _assert_found(check(mine, theirs, picture_height=mine.height, page=page_id),
                      expected, allowed)
        done += 1
        if done == count:
            return
    pytest.fail(f"fewer than {count} dev pages carrying {feature} could take the mutation")


def _dom_cell(table: projection.Table, index: int) -> int:
    cell = table.cells[index]
    return sorted(c.col for c in table.cells if c.row == cell.row).index(cell.col)


def _tokens(text: str) -> bool:
    return bool(re.search(r"[^\W_]", text))


def swap_two_cells(page: Projection, html: str) -> str | None:
    assert page.detail is not None
    for table in page.detail.tables:
        if table.rows < 3 or table.cols < 3:
            continue
        for row in range(1, table.rows):
            for col in range(table.cols - 1):
                a, b = table.slot(row, col), table.slot(row, col + 1)
                if a is None or b is None or a == b:
                    continue
                first, second = table.cells[a], table.cells[b]
                if first.row != row or second.row != row or 1 not in (first.colspan,) \
                        or second.colspan != 1 or first.rowspan != 1 or second.rowspan != 1:
                    continue
                if not (_tokens(first.text) and _tokens(second.text)) or \
                        first.text == second.text or first.header or second.header:
                    continue
                return (f"const r = document.querySelectorAll('table')[{table.index}].rows[{row}];"
                        f"const a = r.cells[{_dom_cell(table, a)}], b = r.cells[{_dom_cell(table, b)}];"
                        "const keep = a.innerHTML; a.innerHTML = b.innerHTML; b.innerHTML = keep;")
    return None


def remove_a_rule(page: Projection, html: str) -> str | None:
    assert page.detail is not None
    for table in page.detail.tables:
        if not table.collapse:
            continue
        for row in range(1, table.rows):
            for col in range(1, table.cols):
                a, b = table.slot(row, col - 1), table.slot(row, col)
                if a is None or b is None or a == b or not table.vertical_rule(row, col):
                    continue
                if table.cells[a].rowspan != 1 or table.cells[b].rowspan != 1:
                    continue
                if table.cells[a].row != row or table.cells[b].row != row:
                    continue
                return (f"const r = document.querySelectorAll('table')[{table.index}].rows[{row}];"
                        f"r.cells[{_dom_cell(table, a)}].style.setProperty('border-right', 'none', 'important');"
                        f"r.cells[{_dom_cell(table, b)}].style.setProperty('border-left', 'none', 'important');")
    return None


def bullets_for_numbers(page: Projection, html: str) -> str | None:
    """Bullets drawn on a numbered list. The corpus prints its numbers as
    text (only report_0011 and the recipe draw number markers, of dev's 231
    pages), so the list is one whose items open with a number either way,
    and the bullet is drawn beside it: the recipe's own fault."""
    assert page.detail is not None
    plain = [group for group in page.detail.lists if group.tag in ("ul", "ol")]
    for at, group in enumerate(plain):
        if len(group.items) >= 2 and all(item.marker == "number" or item.numbered_text
                                         for item in group.items):
            return ("const l = document.querySelectorAll('ul, ol')[" + str(at) + "];"
                    "for (const li of l.children) { li.style.setProperty('display', 'list-item', 'important');"
                    " li.style.setProperty('list-style', 'disc outside', 'important');"
                    " li.style.setProperty('margin-left', '1.5em', 'important'); }")
    return None


def item_into_another_list(page: Projection, html: str) -> str | None:
    assert page.detail is not None
    plain = [group for group in page.detail.lists if group.tag in ("ul", "ol")]
    for i, first in enumerate(plain):
        for j in range(i + 1, len(plain)):
            second = plain[j]
            if len(first.items) < 3 or len(second.items) < 3:
                continue
            a, b = first.items[0].box, second.items[0].box
            inside = any(item.box[1] <= b[1] <= item.box[3] for item in first.items)
            if inside or not _tokens(second.items[1].text):
                continue
            return ("const all = document.querySelectorAll('ul, ol');"
                    f"const a = all[{i}], b = all[{j}];"
                    "a.insertBefore(b.children[1], a.children[1]);")
    return None


def join_two_lines(page: Projection, html: str) -> str | None:
    """The first `<br>` between two runs of text whose removal moves a word:
    in a narrow column the joined line can wrap at the very same word, and
    then the reader sees no change and nothing should fire."""
    if not re.search(r"[^>\s]\s*<br\s*/?>\s*[^<\s]", html):
        return None
    return ("for (const br of document.querySelectorAll('br')) {"
            " const before = br.previousSibling, after = br.nextSibling;"
            " if (!before || before.nodeType !== 3 || !before.textContent.trim()) continue;"
            " if (!after || after.nodeType !== 3 || !after.textContent.trim()) continue;"
            " const r = document.createRange(); r.selectNodeContents(after);"
            " const top = r.getBoundingClientRect().top;"
            " const space = document.createTextNode(' '); br.replaceWith(space);"
            " r.selectNodeContents(after);"
            " if (Math.abs(r.getBoundingClientRect().top - top) > 1) break;"
            " space.replaceWith(br); }")


OWN_TEXT = ("const own = (e) => [...e.childNodes].some((n) => n.nodeType === 3 && "
            "/[A-Za-z0-9]/.test(n.textContent));")


def centred_set_left(page: Projection, html: str) -> str | None:
    assert page.detail is not None
    if not any(frames.align == "center" for frames in page.detail.frames):
        return None
    return (OWN_TEXT +
            "const e = [...document.body.querySelectorAll('*')].find((e) => own(e)"
            " && getComputedStyle(e).textAlign === 'center' && getComputedStyle(e).display === 'block'"
            " && (() => { const r = document.createRange(); r.selectNodeContents(e);"
            " return r.getBoundingClientRect().width < 0.6 * e.getBoundingClientRect().width; })());"
            "e.style.setProperty('text-align', 'left', 'important');")


SERIF = sorted(name for name, kind in FACE_CLASS.items() if kind == "serif")


def serif_set_sans(page: Projection, html: str) -> str | None:
    assert page.detail is not None
    if not any(FACE_CLASS.get(word.family) == "serif" for word in page.detail.words):
        return None
    return (OWN_TEXT + f"const serif = {SERIF!r};"
            "const e = [...document.body.querySelectorAll('*')].find((e) => own(e)"
            " && serif.some((f) => getComputedStyle(e).fontFamily.replace(/[\"']/g, '').startsWith(f))"
            " && e.textContent.trim().split(/\\s+/).length >= 3);"
            "e.style.setProperty('font-family', 'Arial, sans-serif', 'important');")


def bold_set_regular(page: Projection, html: str) -> str | None:
    return (OWN_TEXT +
            "const e = [...document.body.querySelectorAll('b, strong, span')].find((e) => own(e)"
            " && parseInt(getComputedStyle(e).fontWeight, 10) >= 600"
            " && getComputedStyle(e).display === 'inline'"
            " && parseInt(getComputedStyle(e.parentElement).fontWeight, 10) < 600"
            " && own(e.parentElement));"
            "if (!e) throw new Error('no bold run'); e.style.setProperty('font-weight', '400', 'important');")


def _word_edit(how: str) -> str:
    """Edit the second and third words of the first text node with five
    words or more whose second and third are plain words."""
    return ("const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);"
            "let n, w; while ((n = walk.nextNode())) {"
            " const p = n.parentElement; if (!p || /SCRIPT|STYLE/.test(p.tagName)) continue;"
            " w = n.textContent.trim().split(/\\s+/);"
            " if (w.length >= 5 && /^[A-Za-z]{3,}$/.test(w[1]) && /^[A-Za-z]{3,}$/.test(w[2])) break; }"
            + how + "n.textContent = w.join(' ');")


def drop_a_word(page: Projection, html: str) -> str:
    return _word_edit("w.splice(1, 1);")


def double_a_word(page: Projection, html: str) -> str:
    return _word_edit("w.splice(1, 0, w[1]);")


def merge_two_words(page: Projection, html: str) -> str:
    return _word_edit("w.splice(1, 2, (w[1] + w[2]).replace(/[,.;:]/g, ''));")


def make_it_taller(page: Projection, html: str) -> str:
    return ("const d = document.createElement('div');"
            "d.style.height = Math.round(document.body.scrollHeight * 0.2) + 'px';"
            "document.body.appendChild(d);")


LAYOUT = {"lines", "alignment", "height", "type"}
"""What a change in widths or wraps moves besides the thing changed."""


@needs_chrome
class TestEachMutationIsFoundByItsCheck:
    def test_two_cells_swapped(self) -> None:
        _applied("table.ruled", 3, swap_two_cells, ("cells", "wrong column"),
                 {"cells", "rules"} | LAYOUT)

    def test_a_rule_between_two_cells_removed(self) -> None:
        _applied("table.ruled", 3, remove_a_rule, ("rules", "cells merged as drawn"), {"rules"})

    def test_a_numbered_list_drawn_as_bullets(self) -> None:
        _applied("list.numbers", 3, bullets_for_numbers, ("structure", "numbers as bullets"),
                 {"structure", "words"} | LAYOUT)

    def test_an_item_moved_into_another_list(self) -> None:
        _applied("list.bullets", 3, item_into_another_list, ("order", "interleaved"),
                 {"order", "structure"} | LAYOUT)

    def test_two_printed_lines_joined(self) -> None:
        _applied(None, 3, join_two_lines, ("lines", "broken differently"),
                 {"lines", "alignment", "height"})

    def test_a_centred_line_set_flush_left(self) -> None:
        _applied("arr.centred", 3, centred_set_left, ("alignment", "alignment"), {"alignment"})

    def test_a_serif_block_set_sans(self) -> None:
        _applied("type.serif", 3, serif_set_sans, ("type", "wrong face"), LAYOUT)

    def test_a_bold_word_set_regular(self) -> None:
        _applied("type.weights", 3, bold_set_regular, ("type", "bold lost"), LAYOUT)

    @pytest.mark.parametrize("edit, expected", [
        (drop_a_word, ("words", "lost")),
        (double_a_word, ("words", "invented")),
        (merge_two_words, ("words", "merged")),
    ])
    def test_a_word_dropped_doubled_or_merged(self, edit: object, expected: tuple[str, str]) -> None:
        _applied("text.justified", 3, edit, expected, {"words"} | LAYOUT)

    def test_the_page_drawn_taller(self) -> None:
        _applied(None, 2, make_it_taller, ("height", "height"), {"height"})


# --- what the review rejected, 2026-10-31 ----------------------------------------


S14 = REPO / "tests" / "frozen" / "s14-result" / "documents"


@needs_chrome
class TestWhatTheReviewOfTheThirtyOneRejected:
    """False alarms found by opening every sheet of the 31 known pages
    (spec 0021, the review of K0-known31), each pinned on its page, with the
    true fault beside it kept."""

    def test_the_body_is_what_the_render_does_with_the_pages_body(self) -> None:
        """form_0007: labels the page's body, values the render's commonest
        size; every block of both was reported."""
        result = check_page("form_0007", S14 / "form_0007.html")
        sizes = [f for f in result.faults if f.fault == "sizes out of proportion"]
        assert not [f for f in sizes if "Whitlock" in f.element or "Family name" in f.element]

    def test_a_generated_step_number_is_not_its_steps_weight(self) -> None:
        result = check_page("probe_recipe", PROBE / "recipe" / "render.html")
        assert not [f for f in result.faults if f.fault == "bold lost" and "Heat the oven" in f.element]
        assert [f for f in result.faults if f.fault == "numbers as bullets"], "the true fault stays"

    def test_a_pair_drawn_side_by_side_is_not_a_broken_line(self) -> None:
        result = check_page("probe_minutes", PROBE / "minutes" / "render.html")
        (lines,) = [f for f in result.faults if f.fault == "broken differently"]
        assert "Present" not in lines.element and "Next meeting" in lines.element

    def test_two_groups_drawn_side_by_side_as_printed_interleave_only_in_the_html(self) -> None:
        result = check_page("cv_0013", S14 / "cv_0013.html")
        education = [f for f in result.faults if f.fault == "interleaved" and "MEng" in f.element]
        assert education and all(f.severity == "minor" for f in education)

    def test_a_page_that_does_not_register_keeps_its_words_not_its_layout(self) -> None:
        result = check_page("invoice_0002", S14 / "invoice_0002.html")
        assert result.registered < 0.8
        assert not [f for f in result.faults if f.check in ("lines", "alignment", "type")]
        assert [f for f in result.faults if f.fault == "changed"], "its misread words stay"
        assert any("withheld" in note for note in result.notes)

    def test_a_justified_paragraph_drawn_ragged_is_found(self) -> None:
        result = check_page("letter_0016", S14 / "letter_0016.html")
        assert [f for f in result.faults if f.check == "alignment"
                and "printed justified, drawn left" in f.note and "Thank you" in f.element]

    def test_a_paragraphs_last_line_drawn_mid_paragraph_is_not_an_alignment_fault(self) -> None:
        """All three print justified and draw justified; the page's last line
        is ragged, and the output's paragraph goes on past it. Where a
        paragraph ends is not alignment. paper_0018's 'This paper reports',
        kept line for line and drawn ragged, is."""
        for page, html in (("newsletter_0008", S14 / "newsletter_0008.html"),
                           ("paper_0018", S14 / "paper_0018.html"),
                           ("probe_contract", PROBE / "contract" / "render.html")):
            result = check_page(page, html)
            assert not [f for f in result.faults if "printed left, drawn justified" in f.note], page
        result = check_page("paper_0018", S14 / "paper_0018.html")
        assert [f for f in result.faults if "printed justified, drawn left" in f.note
                and "This paper reports" in f.element]

    def test_a_cell_printed_as_a_dash_and_drawn_blank_is_a_word_lost(self) -> None:
        """Found by eye, missed by every check: tokens drop punctuation."""
        result = check_page("nonlatin_0014", S14 / "nonlatin_0014.html")
        (dash,) = [f for f in result.faults if f.fault == "lost" and f.element == "—"]
        assert dash.note.startswith("2 cells")

    def test_an_inverted_size_names_the_heading_it_is_inverted_against(self) -> None:
        result = check_page("probe_flyer", PROBE / "flyer" / "render.html")
        (inverted,) = [f for f in result.faults if "drawn smaller" in f.note and "Free entry" in f.element]
        assert "'Ferry Wharf" in inverted.note


# --- what the review of dev rejected, 2026-11-01 ------------------------------------


DEV = REPO / "tests" / "frozen" / "l2-dev"


@needs_chrome
class TestWhatTheReviewOfDevRejected:
    """False alarms found by opening dev's sheets (spec 0021, the review of
    L2-dev-90), each pinned on its page, with the true fault beside it kept."""

    def test_words_drawn_in_a_figures_pixels_are_a_figures_minor(self) -> None:
        """c0550's callouts are drawn in the exploded drawing's pixels; the
        nomenclature's 1 and 4, read as bullets, are lost."""
        result = check_page("c0550", DEV / "c0550.html")
        (pictured,) = [f for f in result.faults if f.fault == "drawn as a picture"]
        assert pictured.severity == "minor" and pictured.element.split() == ["1", "2", "4", "5", "cinder"]
        lost = {f.element for f in result.faults if f.fault == "lost"}
        assert {"1", "4"} <= lost and not {"2", "5", "cinder"} & lost, "the true faults stay"

    def test_columns_drawn_side_by_side_as_printed_are_minor_and_under_their_own_heading(self) -> None:
        """c0208's header and patient box: the render's HTML reads its bands
        row by row, the eye reads the columns as printed."""
        result = check_page("c0208", DEV / "c0208.html")
        order = [f for f in result.faults if f.check == "order"]
        assert order and all(f.fault == "interleaved" and f.severity == "minor" for f in order)

    def test_copies_drawn_in_another_column_stay_under_another_heading(self) -> None:
        """c0236: the medication list's copies drawn in the Plan column are
        the true fault; the vitals drawn in their own column are not."""
        result = check_page("c0236", DEV / "c0236.html")
        under = [f for f in result.faults if f.fault == "under another heading"]
        assert [f for f in under if "Metformin" in f.element and f.severity == "major"]
        assert not [f for f in under if "Wt 214" in f.element or "SpO2" in f.element]

    def test_a_short_line_in_a_justified_block_is_set_left(self) -> None:
        """c0486's name, ended by a break in a justified block, is drawn
        left as printed; the job title drawn right is the true fault."""
        result = check_page("c0486", DEV / "c0486.html")
        aligned = [f for f in result.faults if f.check == "alignment"]
        assert not [f for f in aligned if "Margaret Ellison" in f.element]
        assert [f for f in aligned if "Senior Landscape Architect" in f.element
                and "printed left, drawn right" in f.note]

    def test_a_line_drawn_where_it_is_printed_keeps_its_alignment(self) -> None:
        """c0492's names sit centred in their halves on both; the render's box
        starts at the ink and reads them as set left. The value set left of
        where the page sets it flush right is the true fault."""
        result = check_page("c0492", DEV / "c0492.html")
        aligned = [f for f in result.faults if f.check == "alignment"]
        assert not [f for f in aligned if "Grant Nguyen" in f.element or "Hiro Ramirez" in f.element]
        assert [f for f in aligned if "ST-22-0417" in f.element and "printed right, drawn left" in f.note]


# --- identity -----------------------------------------------------------------


@needs_chrome
@pytest.mark.parametrize("page_id", sorted(random.Random(SEED).sample(
    sorted(corpus.names("dev")), 8)))
def test_a_page_against_itself_raises_nothing(page_id: str) -> None:
    mine, _ = _read(page_id, None)
    result = check(mine, mine, picture_height=mine.height, page=page_id)
    assert result.faults == ()
    assert result.matched_tokens == result.source_tokens
