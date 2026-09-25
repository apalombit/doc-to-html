"""Phase A1: inline runs, and lines that flow instead of breaking.

Two migrations of the same structures, pinned here because both are easy to
regress invisibly. Marking may never change the words, and reflowing may never
delete the per-line Cells a Correction anchors to — neither of which any scored
axis would report if it broke.
"""

from __future__ import annotations

import pytest

from doc_to_html.ir import (Block, Cell, Document, Kind, Reading, Run, Source,
                            Zone)
from doc_to_html.render import (
    DEHYPHENATE, SPACE, TIGHT, _how_to_join, _lines, _runs, render,
)
from doc_to_html.wire import WireRun, _runs_for

import re


def cell(text: str, runs: list[Run] | None = None) -> Cell:
    return Cell(readings=[Reading(engine="test", text=text, runs=runs or [])])


def block(kind: str, *lines: str) -> Block:
    return Block(kind=kind, lines=[cell(line) for line in lines])


def document(*blocks: Block) -> Document:
    return Document(
        source=Source(path="test.png", sha256="0" * 64, width=800, height=600),
        zones=[Zone(kind=Kind.PROSE, blocks=list(blocks))],
    )


# --------------------------------------------------------------------------
# Marking may never change the words
# --------------------------------------------------------------------------


class TestMarkingCannotChangeTheWords:
    """The one invariant the whole feature rests on.

    A model asked only to *annotate* a reading must not be able to edit it. The
    check is made twice — in `_runs_for`, which cuts the string it was given,
    and again in `Cell.runs`, which refuses Runs that do not spell the text.
    """

    def test_runs_always_rejoin_to_the_text(self) -> None:
        text = "Use <article> for standards, or email editor@example.com"
        runs = _runs_for(text, [
            WireRun(text="<article>", kind="code"),
            WireRun(text="standards", kind="link"),
            WireRun(text="editor@example.com", kind="link"),
        ])
        assert "".join(run.text for run in runs) == text
        assert [r.kind for r in runs if r.kind != "text"] == [
            "code", "link", "link",
        ]

    def test_a_span_that_is_not_there_is_skipped(self) -> None:
        runs = _runs_for("plain text", [WireRun(text="absent", kind="link")])
        assert runs == []

    def test_the_longer_span_wins_over_one_inside_it(self) -> None:
        text = "write to editor@example.com today"
        runs = _runs_for(text, [
            WireRun(text="example.com", kind="code"),
            WireRun(text="editor@example.com", kind="link"),
        ])
        assert "".join(run.text for run in runs) == text
        assert [(r.kind, r.text) for r in runs if r.kind != "text"] == [
            ("link", "editor@example.com"),
        ]

    def test_a_cell_discards_runs_that_do_not_spell_its_text(self) -> None:
        bad = cell("the real reading", [Run("something else", "link")])
        assert [(r.text, r.kind) for r in bad.runs] == [
            ("the real reading", "text"),
        ]

    def test_an_unmarked_cell_renders_exactly_as_before(self) -> None:
        assert _runs(cell("plain & simple")) == "plain &amp; simple"


class TestRunsRenderAsTheTagsTheProjectionReads:
    """`render.TAG_FOR_RUN` must stay `projection.INLINE_BY_TAG`'s tags.

    T6 compares the source's runs against the output's, both read by the same
    `project()`. A kind the output spelled with some other element would score
    as lost however the page looked.
    """

    @pytest.mark.parametrize("kind,tag", [
        ("link", "a"), ("code", "code"), ("strong", "strong"),
        ("em", "em"), ("mark", "mark"),
    ])
    def test_each_kind_gets_its_element(self, kind: str, tag: str) -> None:
        marked = cell("before after", [Run("before", kind), Run(" after")])
        assert f"<{tag}>before</{tag}>" in _runs(marked)

    def test_the_text_is_still_escaped_inside_a_run(self) -> None:
        marked = cell("<article>", [Run("<article>", "code")])
        assert _runs(marked) == "<code>&lt;article&gt;</code>"


# --------------------------------------------------------------------------
# Reflow
# --------------------------------------------------------------------------


class TestWrappedLinesFlowAndRealLinesDoNot:
    def test_a_paragraph_reflows_into_one_run_of_text(self) -> None:
        out = _lines(block("paragraph", "the stretch of towpath", "will reopen"),
                     document())
        assert out == "the stretch of towpath will reopen"
        assert "<br>" not in out

    def test_an_address_keeps_every_line(self) -> None:
        out = _lines(block("address", "Acme Corporation", "123 Main Street",
                           "Anytown"), document())
        assert out == "Acme Corporation<br>123 Main Street<br>Anytown"

    def test_reflowing_does_not_delete_the_per_line_cells(self) -> None:
        """What Correction anchors to, and what makes each reading a label.

        The rendered body flows; the IR behind it still has one Cell per
        printed line. This is the clause of Phase A1's brief that no scored
        axis would have reported.
        """
        paragraph = block("paragraph", "first line", "second line")
        doc = document(paragraph)
        render(doc)
        assert [c.text for c in doc.zones[0].blocks[0].lines] == [
            "first line", "second line",
        ]


class TestAWordCutInTwoIsPutBackTogether:
    """Measured cases from `newsletter_0008`, not invented ones."""

    @pytest.mark.parametrize("previous,following,expected", [
        ("the borough council con-", "firmed on Tuesday", DEHYPHENATE),
        ("nor the naviga-", "tion authority", DEHYPHENATE),
        ("The two slip-", "ways follow", DEHYPHENATE),
        ("culvert has been re-", "lined rather than", DEHYPHENATE),
        ("paid for by public sub-", "scription, will be", DEHYPHENATE),
        ("scheduled as a nine-", "month job", TIGHT),
        ("T", "he stretch of towpath", TIGHT),
        ("between Bridge Street", "and the old lock", SPACE),
        ("end.", "The mayor will attend", SPACE),
    ])
    def test_how_two_lines_are_joined(
        self, previous: str, following: str, expected: str,
    ) -> None:
        assert _how_to_join(previous, following) == expected

    def test_a_soft_hyphen_is_dropped(self) -> None:
        out = _lines(block("paragraph", "the borough council con-",
                           "firmed on Tuesday"), document())
        assert out == "the borough council confirmed on Tuesday"

    def test_a_compound_keeps_its_hyphen(self) -> None:
        """`nine-month`, not `ninemonth`.

        The T1 ratchet caught this on Phase A1's first replay: stripping every
        trailing hyphen stopped `newsletter_0008` printing `nine`.
        """
        out = _lines(block("paragraph", "scheduled as a nine-",
                           "month job ran on"), document())
        assert out == "scheduled as a nine-month job ran on"

    def test_a_drop_cap_joins_tight(self) -> None:
        out = _lines(block("heading", "T", "he stretch of towpath"), document())
        assert out == "The stretch of towpath"


class TestRunsSurviveTheEmbeddedIR:
    """Everything that re-renders reads the IR back out of a rendered file.

    `tools/remeasure_style.py`, `honesty.document_in`, `tools/inspect_run.py`
    and `cli --ir` all go through `Document.from_json`. Rebuilding a Reading
    with `Reading(**data)` leaves `runs` a list of plain dicts, which a
    dataclass accepts without complaint and which fails much later, on the
    first `run.text`.
    """

    def test_a_marked_cell_round_trips_and_re_renders(self) -> None:
        doc = document(Block(kind="paragraph", lines=[
            cell("see standards now",
                 [Run("see "), Run("standards", "link"), Run(" now")]),
        ]))
        doc.zones[0].complete = True
        html = render(doc)
        assert "<a>standards</a>" in html

        raw = re.search(r'id="doc-ir">(.*?)</script>', html, re.S)
        assert raw is not None
        back = Document.from_json(raw.group(1).replace("<\\/", "</"))
        runs = back.zones[0].blocks[0].lines[0].runs
        assert all(isinstance(run, Run) for run in runs)
        assert [(r.text, r.kind) for r in runs] == [
            ("see ", "text"), ("standards", "link"), (" now", "text"),
        ]
        assert "<a>standards</a>" in render(back)


class TestATightJoinLeavesNoSeam:
    """The seam is invisible in the picture and loud in the scorer.

    A word cut across two marked lines renders correctly either way — the page
    reads `confirmed`. But two adjacent `<strong>` elements are two DOM text
    nodes, and `project()` walks text nodes, so T1 scores `con` and `firmed`
    and reports a plainly printed word as missing. Found in Phase A1's sweep,
    on `newsletter_0008`, where the model marked five whole lines `strong`.
    """

    def marked(self, text: str) -> Cell:
        return cell(text, [Run(text, "strong")])

    def test_a_dehyphenated_join_merges_the_elements(self) -> None:
        out = _lines(Block(kind="heading", lines=[
            self.marked("the borough council con-"),
            self.marked("firmed on Tuesday"),
        ]), document())
        assert out == "<strong>the borough council confirmed on Tuesday</strong>"

    def test_a_space_join_keeps_them_apart(self) -> None:
        out = _lines(Block(kind="paragraph", lines=[
            self.marked("one line here"), self.marked("next line here"),
        ]), document())
        assert out == "<strong>one line here</strong> <strong>next line here</strong>"

    def test_different_kinds_are_never_merged(self) -> None:
        out = _lines(Block(kind="paragraph", lines=[
            cell("con-", [Run("con-", "strong")]),
            cell("firmed", [Run("firmed", "em")]),
        ]), document())
        assert out == "<strong>con</strong><em>firmed</em>"


class TestTheInlinePassCannotChangeWhatWasRead:
    """The reason A1's second attempt is a separate pass.

    Asking for marking inside the Extractor prompts cost `invoice_0002` a whole
    pairs answer. This route can only mark text that is already there, and two
    independent guards say so.
    """

    def zone(self, *lines: str) -> Zone:
        return Zone(kind=Kind.PROSE, complete=True, blocks=[
            Block(kind="paragraph", lines=[cell(line) for line in lines]),
        ])

    def test_a_span_that_was_not_read_marks_nothing(self) -> None:
        from doc_to_html.wire import RunsResponse, runs_into
        z = self.zone("plain text here")
        runs_into(z, RunsResponse(marked=[WireRun(text="absent", kind="link")]))
        assert [(r.text, r.kind) for r in z.blocks[0].lines[0].runs] == [
            ("plain text here", "text"),
        ]

    def test_the_words_are_never_changed(self) -> None:
        from doc_to_html.wire import RunsResponse, runs_into
        z = self.zone("see the standards page")
        runs_into(z, RunsResponse(
            marked=[WireRun(text="standards", kind="link")]))
        runs = z.blocks[0].lines[0].runs
        assert "".join(r.text for r in runs) == "see the standards page"
        assert [(r.text, r.kind) for r in runs if r.kind != "text"] == [
            ("standards", "link"),
        ]

    def test_a_span_covering_a_whole_line_is_dropped(self) -> None:
        """`newsletter_0008`: the model marked five whole lines `strong`.

        `projection.inlineOf` judges a run against the block it sits in, so a
        wholly bold paragraph yields no `strong` runs and a span like this
        could never score. Dropping it also stops the renderer wrapping a whole
        paragraph in `<strong>`.
        """
        from doc_to_html.wire import RunsResponse, runs_into
        line = "the borough council confirmed on Tuesday"
        z = self.zone(line)
        runs_into(z, RunsResponse(marked=[WireRun(text=line, kind="strong")]))
        assert [(r.text, r.kind) for r in z.blocks[0].lines[0].runs] == [
            (line, "text"),
        ]

    def test_an_empty_answer_leaves_the_zone_exactly_as_it_was(self) -> None:
        from doc_to_html.wire import RunsResponse, runs_into
        z = self.zone("first line", "second line")
        runs_into(z, RunsResponse(marked=[]))
        assert [c.text for c in z.blocks[0].lines] == ["first line", "second line"]
        assert all(len(c.runs) == 1 and c.runs[0].kind == "text"
                   for c in z.blocks[0].lines)


class TestMarkingThatIsReallyTheTypeface:
    """Junk marks are not merely useless — each one costs a join.

    Every mark is a text-node boundary, and `project()` walks text nodes, so a
    line shredded into one mark per word loses every adjacent-word pair in it.
    `join_recall` is the only T1 leg that sees it.
    """

    def marks(self, text: str, *spans: tuple[str, str]) -> list[Run]:
        return [r for r in _runs_for(
            text, [WireRun(text=t, kind=k) for t, k in spans])
            if r.kind != "text"]

    def test_every_word_marked_is_the_lines_typeface(self) -> None:
        """`newsletter_0008`'s pull quote came back as 22 one-word marks."""
        quote = "We found three problems the survey could not have seen"
        assert self.marks(quote, *[(w, "strong") for w in quote.split()]) == []

    def test_two_kinds_splitting_one_line_are_counted_together(self) -> None:
        """`Country statistics` sat at exactly 50% per kind and slipped a
        per-kind test twice over. `cv_0013`'s `2021 — present` is the same."""
        assert self.marks("Country statistics",
                          ("Country", "strong"), ("statistics", "em")) == []
        assert self.marks("2021 — present",
                          ("2021", "code"), ("present", "em")) == []

    def test_a_genuine_email_link_survives(self) -> None:
        """The measured reason the threshold is "all of them" and not a half.

        `editor@example.com` is three of the four words in its line — a marked
        share of 0.750, the highest genuine mark in the corpus, and far above
        every other. Every junk case sits at exactly 1.000.
        """
        assert self.marks("Contact: editor@example.com",
                          ("editor@example.com", "link")) == [
            Run("editor@example.com", "link")]

    def test_a_mark_never_splits_a_word(self) -> None:
        """`newsletter_0008`: `T` was marked, and the first `T` in the block
        belonged to `Tuesday`. It rendered `<strong>T</strong>uesday`, the page
        read correctly, and T1 reported `tuesday` as no longer printed."""
        assert self.marks("the council confirmed on Tuesday, bringing an end",
                          ("T", "strong")) == []
