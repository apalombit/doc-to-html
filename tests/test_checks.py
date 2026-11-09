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

    def test_the_recipes_step_drawn_across_the_ingredients_and_drawn_as_bullets(self) -> None:
        """The method's column is kept beside the ingredients', so their
        words alternating in the render's HTML is no fault (round 1's
        columns, 2026-11-07); step 3, drawn across both columns between the
        salad's ingredients and the dressing's, is. The steps drawn as
        bullets are the other fault."""
        result = check_page("probe_recipe", PROBE / "recipe" / "render.html")
        kinds = {(f.check, f.fault) for f in result.faults}
        assert ("structure", "numbers as bullets") in kinds
        (across,) = [f for f in result.faults if f.fault == "interleaved"]
        assert across.severity == "major" and across.element.startswith("Toast the hazelnuts")
        assert across.note.startswith("drawn across the column printed beside it")


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


LAYOUT = {"lines", "beside", "alignment", "height", "type"}
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
        _applied("type.serif", 3, serif_set_sans, ("type", "other face"), LAYOUT)

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

    def test_two_groups_drawn_side_by_side_as_printed_are_not_interleaved(self) -> None:
        """The education, in the left column on both: the render's HTML reads
        the columns row by row, and the eye reads them as printed. Once a
        minor; since 2026-11-07 no fault (Alessandro, round 1, c0221)."""
        result = check_page("cv_0013", S14 / "cv_0013.html")
        assert not [f for f in result.faults if f.fault == "interleaved" and "MEng" in f.element]

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

    def test_a_rule_drawn_by_a_separator_along_the_table_frames_it(self) -> None:
        """c0126's top rule is a separator above the table, not a border;
        its misread year stays."""
        result = check_page("c0126", DEV / "c0126.html")
        assert not [f for f in result.faults if f.check == "rules"]
        assert [f for f in result.faults if f.fault == "changed" and f.element == "2020 → 2028"]

    def test_rows_drawn_in_a_table_of_their_own_are_judged_there(self) -> None:
        """c0309's totals are drawn as a table apart; the rule under Repas is
        the main table's foot. Its steps drawn as bullets stay."""
        result = check_page("c0309", DEV / "c0309.html")
        assert not [f for f in result.faults if f.check == "rules" and "Total HT" in f.element]
        assert [f for f in result.faults if f.fault == "numbers as bullets"]

    def test_a_signature_in_a_script_face_has_no_italics_to_lose(self) -> None:
        """letter_0016's signature is a script face on both; the letterhead's
        serif drawn sans stays."""
        result = check_page("letter_0016", S14 / "letter_0016.html")
        assert not [f for f in result.faults if f.fault == "italics" and "Tomas Halden" in f.element]
        assert [f for f in result.faults if f.fault == "other face" and "Halden & Pryce" in f.element]

    def test_a_size_across_the_margin_by_less_than_it_is_not_out_of_proportion(self) -> None:
        """cv_0013's job titles, 1.04 of the body printed and 1.05 drawn; their
        bold drawn regular stays."""
        result = check_page("cv_0013", S14 / "cv_0013.html")
        sizes = [f for f in result.faults if f.fault == "sizes out of proportion"]
        assert not [f for f in sizes if "Structural Engineer" in f.element]
        assert [f for f in result.faults if f.fault == "bold lost" and "Senior Structural Engineer" in f.element]

    def test_a_word_of_several_tokens_is_spelled_as_a_whole(self) -> None:
        """probe_datasheet's order codes, three tokens each (issue B): the
        case changed is a misspelling; a hyphen drawn as an en dash alone is
        a mark changed, a minor (issue N)."""
        result = check_page("probe_datasheet", PROBE / "datasheet" / "render.html")
        spelt = {f.element: f for f in result.faults if f.fault in ("spelling", "mark changed")}
        assert spelt["AQ7-MB-W → AQ7–MB–w"].severity == "major"
        assert spelt["AQ7-POE-G → AQ7–POE–G"].severity == "minor"

    def test_a_cross_drawn_as_the_letter_x_is_a_mark_changed(self) -> None:
        """Issue N, Alessandro 2026-11-01: a look-alike mark is a minor.
        pricing_0017's one ✕ drawn as an X is that; its other two crosses
        and nine ticks, not drawn, stay lost. catalogue_0015's × read as an
        x is a word changed, not a mark."""
        result = check_page("pricing_0017", S14 / "pricing_0017.html")
        words = {(f.fault, f.element): f for f in result.faults if f.check == "words"}
        assert words[("mark changed", "✕ → X")].severity == "minor"
        assert ("invented", "x") not in words
        assert words[("mark lost", "✕")].note.startswith("2 ") and words[("mark lost", "✓")].note.startswith("9 ")
        result = check_page("catalogue_0015", S14 / "catalogue_0015.html")
        assert [f for f in result.faults if f.fault == "invented" and f.element == "x" and f.severity == "major"]


# --- what Alessandro decided, review rounds 1 to 4, 2026-11-07 -----------------------


@needs_chrome
class TestWhatTheRoundsDecided:
    """docs/agents/review-issues.json: each rule pinned on the page it was
    decided on, with the page's true fault beside it."""

    def test_a_menu_drawn_as_its_items_on_one_row_keeps_its_place(self) -> None:
        """c0548's menu sits at the top right on both; read by its first
        item alone it was 'printed right, drawn left'."""
        result = check_page("c0548", DEV / "c0548.html")
        assert not [f for f in result.faults if f.check == "alignment" and "Produit" in f.element]

    def test_a_note_drawn_under_the_title_whose_line_it_shares_is_drawn_under(self) -> None:
        result = check_page("c0600", DEV / "c0600.html")
        (under,) = [f for f in result.faults if f.check == "beside"]
        assert under.severity == "major" and "Fill in and hand" in under.element
        assert not [f for f in result.faults if f.check == "alignment" and "Fill in" in f.element]

    def test_values_shifted_in_their_column_are_minor_and_drawn_under_their_questions_major(self) -> None:
        """c0029: answers drawn beside their questions, not at the right edge,
        a minor; the six drawn under all the questions, a major."""
        result = check_page("c0029", DEV / "c0029.html")
        assert all(f.severity == "minor" for f in result.faults if f.check == "alignment")
        (under,) = [f for f in result.faults if f.check == "beside"]
        assert under.severity == "major" and "about 16" in under.element

    def test_a_paragraph_rewrapped_by_its_column_is_minor(self) -> None:
        result = check_page("c0363", DEV / "c0363.html")
        assert not [f for f in result.faults if f.fault == "broken differently"]
        (wrapped,) = [f for f in result.faults if f.fault == "re-wrapped"]
        assert wrapped.severity == "minor" and "La tostatrice" in wrapped.element

    def test_fields_run_together_or_split_from_their_label_stay_major(self) -> None:
        """c0246: Forma, Posologia and Quantità drawn on one line; 'Diagnosi:'
        drawn in a block of its own over its text."""
        result = check_page("c0246", DEV / "c0246.html")
        (split,) = [f for f in result.faults if f.fault == "broken differently"]
        assert split.severity == "major" and "Diagnosi" in split.element
        (joined,) = [f for f in result.faults if f.fault == "rows joined"]
        assert joined.severity == "major" and "Amoxicillina" in joined.element

    def test_a_size_change_no_reader_sees_is_not_out_of_proportion(self) -> None:
        """form_0007's 'OFFICE USE', 11 px printed and 10.8 px drawn."""
        result = check_page("form_0007", S14 / "form_0007.html")
        assert not [f for f in result.faults if f.fault == "sizes out of proportion"
                    and "OFFICE USE" in f.element.upper()]

    def test_a_subscript_drawn_inline_after_a_mark_is_one_mark_changed(self) -> None:
        result = check_page("c0576", DEV / "c0576.html")
        (marks,) = [f for f in result.faults if f.fault == "mark changed"]
        assert marks.severity == "minor" and "H2015) → H_2015)" in marks.element
        assert not [f for f in result.faults if f.fault in ("lost", "invented")
                    and f.element in ("h2015", "v2015", "ht", "vt", "h", "v", "t")]

    def test_a_copy_is_compared_with_the_copy_drawn_where_it_is_printed(self) -> None:
        """c0345's 'Camila Park', a script signature and a bold name, each
        drawn as printed; its section numbers drawn regular stay."""
        result = check_page("c0345", DEV / "c0345.html")
        assert not [f for f in result.faults if f.check == "type" and "Camila Park" in f.element]
        assert [f for f in result.faults if f.fault == "bold lost" and "1 Parties" in f.element]

    def test_columns_kept_as_printed_name_only_the_items_drawn_in_another(self) -> None:
        """c0221's three sections, three columns on both: fifteen majors for
        two items. Item (a) drawn in section 3's column stays."""
        result = check_page("c0221", DEV / "c0221.html")
        assert not [f for f in result.faults if f.fault == "interleaved"]
        assert [f for f in result.faults if f.fault == "under another heading"
                and "quadri di distribuzione" in f.element and f.severity == "major"]

    def test_labels_drawn_over_their_values(self) -> None:
        result = check_page("c0166", DEV / "c0166.html")
        (over,) = [f for f in result.faults if f.check == "overprint"]
        assert over.severity == "major" and "Date: / 01/10/2021" in over.element

    def test_two_boxes_printed_side_by_side_drawn_stacked(self) -> None:
        """c0187's Year to date and Time off."""
        result = check_page("c0187", DEV / "c0187.html")
        (under,) = [f for f in result.faults if f.check == "beside"]
        assert under.severity == "major" and "Time off" in under.element

    def test_a_copy_matched_beside_a_word_printed_once_stays_with_it(self) -> None:
        """c0366's heading 'Comment fonctionne un panier', not swapped with
        the 'panier' of the answer under it. 'Foire aux questions' drawn
        regular stays."""
        result = check_page("c0366", DEV / "c0366.html")
        assert not [f for f in result.faults if f.check == "type" and "Comment fonctionne" in f.element]
        (bold,) = [f for f in result.faults if f.fault == "bold lost"]
        assert bold.element == "Foire aux questions"

    def test_a_group_mostly_lost_is_not_interleaved(self) -> None:
        """c0008's section 1, 3% to 8% of it drawn: eight interleavings, each
        rejected."""
        result = check_page("c0008", DEV / "c0008.html")
        assert not [f for f in result.faults if f.fault == "interleaved"
                    and ("SECTION 1" in f.element or "Surname" in f.element)]

    def test_type_drawn_too_faint_to_read(self) -> None:
        """c0063's patient total, dark on its tint, drawn white on white."""
        result = check_page("c0063", DEV / "c0063.html")
        (faint,) = [f for f in result.faults if f.fault == "too faint"]
        assert faint.severity == "major" and "$2,965.78" in faint.element

    def test_a_line_printed_on_the_page_drawn_in_a_dark_box(self) -> None:
        result = check_page("c0419", DEV / "c0419.html")
        (ground,) = [f for f in result.faults if f.fault == "ground changed"]
        assert ground.severity == "major" and "Le Sentier des Mousses" in ground.element
        assert "printed on light, drawn on dark" in ground.note

    def test_colour_printed_drawn_dark(self) -> None:
        """c0355's notice printed red."""
        result = check_page("c0355", DEV / "c0355.html")
        (lost,) = [f for f in result.faults if f.fault == "colour lost"]
        assert lost.severity == "major" and "printed red, drawn dark" in lost.note

    def test_a_headings_accent_colour_drawn_dark_is_minor(self) -> None:
        """c0548's 'Des tarifs simples', orange printed, dark drawn
        (Alessandro, round 5, 2026-11-07)."""
        result = check_page("c0548", DEV / "c0548.html")
        (lost,) = [f for f in result.faults if f.fault == "colour lost"]
        assert lost.severity == "minor" and lost.element == "Des tarifs simples"

    def test_an_accent_frame_drawn_light_a_chip_minor(self) -> None:
        """c0548's orange buttons: the plans' a major, the contact chip a
        minor."""
        result = check_page("c0548", DEV / "c0548.html")
        frames = {f.severity: f.element for f in result.faults if f.fault == "frame colour lost"}
        assert "Essayer 30 jours" in frames["major"] and "Parler à Yann Masson" in frames["minor"]

    def test_a_pill_drawn_across_the_page(self) -> None:
        result = check_page("probe_flyer", PROBE / "flyer" / "render.html")
        (shape,) = [f for f in result.faults if f.fault == "fill drawn another shape"]
        assert shape.severity == "major" and "31% of the page → 100%" in shape.element

    def test_a_framed_card_drawn_as_a_filled_box_is_minor(self) -> None:
        """c0567's cards, framed on the page, drawn white on the render's
        beige: boxes to the eye still."""
        result = check_page("c0567", DEV / "c0567.html")
        (frame,) = [f for f in result.faults if f.fault == "frame missing"]
        assert frame.severity == "minor" and "Ardnamurchan lodge" in frame.element
        assert frame.note.startswith("framed on the page, drawn as a filled box")

    def test_a_framed_box_drawn_with_no_frame(self) -> None:
        result = check_page("probe_payslip", PROBE / "payslip" / "render.html")
        (frame,) = [f for f in result.faults if f.fault == "frame missing"]
        assert frame.severity == "major" and "Gross pay" in frame.element


# --- what Alessandro decided, review round 7, 2026-11-09 (spec 0022) ------------


@needs_chrome
class TestWhatRoundSevenDecided:
    """docs/agents/review-issues.json, round 7: false alarms found on L3's
    panel pages, each pinned on a dev page the same way (panel pages are
    never used in a test)."""

    def test_a_word_its_twin_spells_otherwise_is_spelled_as_the_map_says(self) -> None:
        """l3-ligature (c0082): a PDF's text layer drops the fi ligature of
        'specific'; the spelling check compared that raw text. c0421's
        'soil-specific', its twin made to drop the fi, mapped back."""
        source = corpus.page("c0421")
        width = Image.open(source.png_path()).width
        html = source.html_path().read_text(encoding="utf-8")
        twin = project(html.replace("specific", "specifc"), width=width, flat=True, detail=True)
        page = project(html, width=width, flat=True, detail=True)
        result = check(twin, page, picture_height=twin.height, page="c0421",
                       spellings={"specifc": "specific"})
        assert not [f for f in result.faults if f.check == "words"]

    def test_a_drop_cap_and_the_rest_of_its_word_are_one_word(self) -> None:
        """l3-dropcap (c0334's 'N' + 'otice'): c0399's drop cap 'E' + 'very'
        drawn in the line is one word kept and one drop cap lost, a minor;
        not a merge, and not a heading."""
        mine, theirs = _read("c0399", "for (const e of document.querySelectorAll('.dc')) "
                             "Object.assign(e.style, {float: 'none', fontSize: 'inherit', "
                             "lineHeight: 'inherit', fontWeight: 'inherit', padding: '0', "
                             "color: 'inherit'});")
        result = check(mine, theirs, picture_height=mine.height, page="c0399")
        kinds = {(f.check, f.fault, f.severity) for f in result.faults}
        assert ("type", "drop cap lost", "minor") in kinds
        assert not [f for f in result.faults if f.fault in ("merged", "heading not kept")
                    or f.check in ("type", "looks") and f.element in ("E", "Every")
                    and f.fault != "drop cap lost"]

    def test_a_block_not_drawn_is_not_judged_for_its_look(self) -> None:
        """l3-moot (c0300's PG7.2026, cropped away whole): c0029's '5. Safety
        and staff' and c0309's 'Note de service' are not drawn; their loss
        is the words check's, and no heading or type fault is raised on the
        few words matched elsewhere."""
        for page_id, heading, word in (("c0029", "5. Safety and staff", "safety"),
                                       ("c0309", "Note de service", "service")):
            result = check_page(page_id, DEV / f"{page_id}.html")
            assert [f for f in result.faults if f.fault == "lost" and f.element == word]
            assert not [f for f in result.faults if f.check in ("structure", "type")
                        and heading in f.element]

    def test_a_line_printed_beside_a_heading_is_not_under_it(self) -> None:
        """l3-hours (c0476's opening hours, top right of 'Small plates'):
        c0366's themes box, beside 'Foire aux questions', is not its
        section; the first answer drawn as a narrow column stays major."""
        result = check_page("c0366", DEV / "c0366.html")
        order = [f for f in result.faults if f.fault == "interleaved"]
        assert not [f for f in order if "Foire aux questions" in f.element]
        assert [f for f in order if f.severity == "major" and "Comment fonctionne" in f.element]


class TestWhatRoundNineDecided:
    """docs/agents/review-issues.json, round 9: a false alarm found on
    P1-D2-L3's panel pages, pinned on a dev page."""

    LOOKALIKES = ("for (const n of (function* w(e) { for (const c of e.childNodes) "
                  "{ if (c.nodeType === 3) yield c; else yield* w(c); } })(document.body)) "
                  "n.textContent = n.textContent.replace(/✓/g, '√').replace(/✗/g, '×')"
                  ".replace(/☐/g, '□');")

    def test_a_tick_drawn_as_its_look_alike_is_a_minor(self) -> None:
        """p1-lookalike (c0291's ✓ ✗ ☐ written √ × □): c0068's three of each,
        drawn as the look-alikes, are one minor 'mark changed', never a mark
        lost and a mark invented."""
        mine, theirs = _read("c0068", self.LOOKALIKES)
        result = check(mine, theirs, picture_height=mine.height, page="c0068")
        words = [f for f in result.faults if f.check == "words"]
        assert not [f for f in words if f.fault in ("mark lost", "mark invented")]
        assert [f for f in words if f.fault == "mark changed" and f.severity == "minor"]

    def test_a_tick_lost_outright_stays_major(self) -> None:
        """A ✓ dropped, not drawn as √, is still a mark lost."""
        mine, theirs = _read("c0068", self.LOOKALIKES.replace("'√'", "''"))
        result = check(mine, theirs, picture_height=mine.height, page="c0068")
        assert [f for f in result.faults if f.fault == "mark lost" and f.element == "✓"
                and f.severity == "major"]


# --- identity -----------------------------------------------------------------


@needs_chrome
@pytest.mark.parametrize("page_id", sorted(random.Random(SEED).sample(
    sorted(corpus.names("dev")), 8)))
def test_a_page_against_itself_raises_nothing(page_id: str) -> None:
    mine, _ = _read(page_id, None)
    result = check(mine, mine, picture_height=mine.height, page=page_id)
    assert result.faults == ()
    assert result.matched_tokens == result.source_tokens
