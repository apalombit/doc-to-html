"""Nothing may lose content quietly — spec 0007 Phase A-1's gate, as a test.

**The assertion, in one line:** over the whole sweep set, a drop in token recall
must be accompanied by a finding naming the Zone and saying how much.

**Why it is written over all fifteen documents rather than a couple.** The rule
is a claim about every document the project is measured on, and the two
documents that broke it were both outside the original five —
`darkdeck_0009`, which lost 80% of itself and printed no finding at all, and
`receipt_0010`, which lost 75% and called it a possible mark. A gate tested on
the five that never had the fault is a gate that would not have caught it.

**How loss is produced without a model.** Each source document is rebuilt
carrying the first half of its own words — see `halved` — so the "output" is a
real page that really is missing content, scored by the real scorer. No model
runs, nothing is replayed, and the loss is arranged rather than hoped for. The
two arms are then the whole of the rule: the same lossy document with no
findings must fail, and with one finding must pass.

**What is deliberately not asserted.** That the finding is *correct* about which
Zone, or *accurate* about the share. Neither is knowable without ground truth
the pipeline does not have, and demanding it would make the rule unmeetable.
What is asserted is that something was said, that it names a Zone, and that it
carries a number — which is the difference between the render that lost
`receipt_0010` and one a reader can act on.
"""

from __future__ import annotations

import re
from html import escape, unescape
from pathlib import Path

import pytest

from doc_to_html import projection
from doc_to_html.corpus import SOURCES, SWEEP
from doc_to_html.honesty import (
    LOSS_TOLERANCE,
    account,
    document_in,
    loss_findings,
    quiet_losses,
)
from doc_to_html.ir import BBox, Document, Failure, Gap, Shortfall, Source
from doc_to_html.render import render
from doc_to_html.report import flagged
from doc_to_html.scoring import score_document

REPO = Path(__file__).resolve().parent.parent

needs_chrome = pytest.mark.skipif(
    not projection.available(), reason="no headless Chrome on this machine"
)

_HIDDEN = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def halved(html: str) -> str:
    """A page carrying the first half of this document's words and nothing else.

    **Rebuilt rather than truncated, and the first attempt says why.** Cutting
    the source's body at its midpoint by character count produced malformed
    markup on eight of the fifteen — a cut landing inside a `<style>` swallows
    everything after it, including the measuring script, and the browser
    returned no projection at all. A document that will not project is not a
    document that lost content; it is a broken arrangement that would have read
    as the rule firing.

    So the loss is arranged out of the source's own words, in the source's own
    order, in markup that cannot be malformed. It is a crude page and that is
    fine: the honesty rule is about recall, and nothing here asks a question
    about layout.
    """
    text = _TAG.sub(" ", _HIDDEN.sub(" ", html))
    words = unescape(text).split()
    keep = words[: len(words) // 2]
    if len(keep) < 4:  # pragma: no cover - no corpus document is this short
        raise AssertionError("too few words to halve meaningfully")
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>half</title></head><body>"
        + "".join(f"<p>{escape(word)}</p>" for word in keep)
        + "</body></html>\n"
    )


def source_of(name: str) -> Source:
    return Source(path=name, sha256="0" * 64, width=100, height=100)


class TestADropInRecallMustBeDeclared:
    """The gate, over the sweep set, both arms.

    One score per document and both arms asserted against it, rather than two
    tests scoring the same page twice: `score_document` launches the browser
    three times, and fifteen documents is already the slowest thing in the
    suite.
    """

    @needs_chrome
    @pytest.mark.parametrize("name", SWEEP)
    def test_a_loss_fails_unless_a_finding_names_the_zone(
        self, name: str, tmp_path: Path
    ) -> None:
        document = SOURCES[name]
        lossy = tmp_path / f"{name}.html"
        lossy.write_text(
            halved(document.html_path(REPO).read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        score = score_document(document, lossy, work=tmp_path, root=REPO)

        assert score.completeness.recall < LOSS_TOLERANCE, (
            f"the arrangement itself failed: half of {name}'s words scored "
            "recall 1.0, so this document proves nothing either way"
        )

        # Arm one: the loss, undeclared. This is `darkdeck_0009` exactly.
        quiet = account(score, [])
        assert not quiet.ok
        assert quiet_losses([quiet]) == [quiet]
        assert f"{score.completeness.recall:.3f}" in quiet.reason, (
            "a gate that fails without naming the number is a gate that gets "
            "argued with"
        )

        # Arm two: the same loss, declared.
        declared = Document(source=source_of(name))
        declared.failures = [
            Failure(zone_index=3, kind="table",
                    reason="MappingError: the crop could not be read",
                    ink_share=0.41)
        ]
        spoken = account(score, loss_findings(declared))

        assert spoken.ok
        assert quiet_losses([spoken]) == []
        assert "Zone 3" in spoken.findings[0], "the finding names the Zone"
        assert "41%" in spoken.findings[0], "and says how much"


class TestWhatCountsAsDeclaringALoss:
    """Which findings discharge the rule, and which deliberately do not."""

    def test_a_failure_a_shortfall_and_a_gap_all_count(self) -> None:
        document = Document(source=source_of("x"))
        document.failures = [Failure(zone_index=0, kind="prose", reason="boom",
                                     ink_share=0.2)]
        document.shortfalls = [Shortfall(zone_index=1, kind="table",
                                         printed_lines=36, read_lines=2,
                                         ink_share=0.5)]
        document.gaps = [Gap(bbox=BBox(0.0, 0.0, 0.5, 0.5), ink_share=0.3,
                             note="content nothing read")]

        found = loss_findings(document)

        assert len(found) == 3
        assert all("%" in item for item in found), "each one says how much"
        assert "was read short — 36 printed lines, 2 returned" in found[1]

    def test_a_caveat_does_not_count(self) -> None:
        """A Caveat says content arrived with a qualifier on *how*. Letting
        "read at reduced resolution" discharge the honesty rule would let a
        document that lost half its text pass on a note about the other half."""
        from doc_to_html.ir import Caveat

        document = Document(source=source_of("x"))
        document.caveats = [Caveat(zone_index=0, kind="table",
                                   note="read at reduced resolution")]

        assert loss_findings(document) == ()

    def test_a_resolved_gap_does_not_count(self) -> None:
        document = Document(source=source_of("x"))
        document.gaps = [Gap(bbox=BBox(0.0, 0.0, 0.5, 0.5), ink_share=0.3,
                             resolved=True)]

        assert loss_findings(document) == ()


class TestTheFindingsSurviveTheRoundTrip:
    """The report reads findings off the IR the render embeds, not off its prose.

    So the two have to agree, and the join has to survive `render()` — which is
    where a finding could be dropped without any test noticing, because the
    render is scored on its *content* and the findings panel is excluded from
    that scoring by design.
    """

    def test_findings_come_back_out_of_a_rendered_document(self) -> None:
        document = Document(source=source_of("x"))
        document.failures = [Failure(zone_index=2, kind="table", reason="boom",
                                     ink_share=0.37)]
        document.shortfalls = [Shortfall(zone_index=4, kind="prose",
                                         printed_lines=20, read_lines=3,
                                         ink_share=0.12)]

        recovered = document_in(render(document))

        assert recovered is not None
        assert loss_findings(recovered) == loss_findings(document)

    def test_the_render_prints_the_share_a_failure_lost(self) -> None:
        document = Document(source=source_of("x"))
        document.failures = [Failure(zone_index=2, kind="table", reason="boom",
                                     ink_share=0.37)]

        html = flagged(document)

        assert "37% of the page&#x27;s printed ink" in html or \
               "37% of the page's printed ink" in html

    def test_a_shortfall_is_unresolved_rather_than_a_caveat(self) -> None:
        """Content that did not arrive is not a qualifier on content that did.
        Filing it under "Read with a caveat" is the understatement this phase
        exists to remove."""
        document = Document(source=source_of("x"))
        document.shortfalls = [Shortfall(zone_index=4, kind="prose",
                                         printed_lines=20, read_lines=3)]

        html = flagged(document)
        unresolved = html.index("Unresolved")
        assert "was read short" in html
        assert html.index("was read short") > unresolved
        if "Read with a caveat" in html:  # pragma: no cover - none here
            assert html.index("was read short") < html.index("Read with a caveat")
