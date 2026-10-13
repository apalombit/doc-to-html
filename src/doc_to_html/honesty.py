"""Did the document say what it lost — spec 0007 Phase A-1's gate.

**The rule.** Content that does not reach the output must produce a finding that
says so and says how much. Not "should"; the phase is not done while any
document in the corpus can lose content quietly.

**Why it is the gate and not a nicety.** Two documents in the Thread 0
checkpoint lost most of themselves and the render was serene about it.
`darkdeck_0009` came back as one Zone holding a fifth of its own text, with no
Failure, no Gap and no Caveat — nothing at all. `receipt_0010` kept its header,
dropped everything from the first line item to the barcode, and filed 77 of 103
tokens under *"found by ink coverage, so it may be a mark"*. A silent loss is
worse than a loud failure: a loud failure is a bug report, and a silent one is a
document somebody trusts.

**The two halves, and why they are separate.**

- The *pipeline* emits findings without ground truth. It knows a Zone raised, it
  knows ink lies outside every box, it can count printed lines against lines
  read. It cannot know it split `Invoice #: 123` at the wrong point, because
  that needs the source text, which it has never seen.
- The *scorer* has ground truth and knows exactly what was lost.

This module is the join: it asks whether, wherever the scorer sees loss, the
pipeline said something about it. It is not a second scorer, and it never
measures loss itself.

**What counts as loss here, decided 2026-09-19 and deliberately narrow.** Token
recall, and nothing else. Duplication is a precision fault and a mis-split is a
join fault, and neither is content that failed to arrive — `invoice_0001` at
recall 1.000 with a broken join is not a document that lost anything, and
requiring it to report one would require the pipeline to detect something it has
no way to see. Those two faults are Phase A0's to fix, and A0 fixes them rather
than announcing them.

**The rule's measured ceiling, found at A-1's checkpoint rather than assumed.**
What the pipeline can declare is loss that is *structural* — a Zone that
raised, a Zone read grossly short of its own crop, ink no Zone covered. It
cannot declare loss *within* a line, and on the checkpoint that is the larger
half: nine of fifteen documents lost between 2% and 43% of their tokens while
returning **as many lines as are printed, or more**. `catalogue_0015` read 28
lines where 20 are printed and lost 43% of its words; `menu_0012` read 31 for
18. A line count cannot see a line that came back with half its words in it.

Two pixel-side detectors were built and measured against the checkpoint's own
documents before this was written down, and both were rejected for firing on
correct documents while missing the worst real loss:

| signal | why it was rejected |
|---|---|
| ink per character, against the page's median | `sample_css_0004` lost nothing and peaks at 6.2x on a display heading; `catalogue_0015` lost 43% and peaks at 2.6x |
| characters expected from ink, normalised by the Zone's own measured type height | `invoice_0001` lost nothing and reads 3.4x; `newsletter_0008` reads 8.0x having lost 5.7% |

Both are dominated by type size, letter spacing and how much of a crop is
whitespace — all of which vary more between documents than the loss does.
**Do not build a third without a new kind of evidence.** A finding that fires
on a correct reading is worse than no finding, which is this project's own
recorded lesson about `CaptionResponse` read from the other end.

**What would actually reach it**, named so it is not re-invented: two readings
of the same crop, compared against each other. The IR already has the
vocabulary — `CellState.DISPUTED` and the Ladder — and
`orchestrator._climb_ladders` already records that it is waiting on a second
Engine. That is model time and a different thread's decision, not A-1's.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from .ir import Document
from .scoring import DocumentScore

LOSS_TOLERANCE = 0.999
"""Recall at or above this counts as having lost nothing.

Not 1.0, because token recall over a whole document is a ratio of integers and a
single token of ordinary noise — a ligature, a soft hyphen, a currency symbol
normalised differently on two sides of the same comparison — should not put a
document into breach of a gate about *losing content*. One token in a thousand
is the width of that noise and nothing in the corpus loses content that slowly:
the losses this rule exists for are 0.097, 0.201, 0.25.
"""


@dataclass(frozen=True)
class Accounting:
    """Whether one document's loss was declared, and what it declared.

    `ok` is the gate. Everything else is there so a report can say *why*
    without re-deriving it, because a gate that fails without naming the
    document and the number is a gate somebody will start ignoring.
    """

    name: str
    recall: float
    lost_tokens: int
    findings: tuple[str, ...]
    """The loss-class findings the output document carries, as sentences."""

    ok: bool
    reason: str

    @property
    def lost(self) -> bool:
        return self.recall < LOSS_TOLERANCE


def loss_findings(document: Document) -> tuple[str, ...]:
    """The findings in this document that declare missing content.

    Three kinds, and only three. A Failure is a Zone that could not be read at
    all; a Shortfall is a Zone read short of its own crop; an unresolved Gap is
    ink no Zone covered. A Caveat is deliberately **not** one of them — it says
    content arrived with a qualifier on how, and counting it would let "read at
    reduced resolution" discharge the honesty rule for a document that lost half
    its text.

    Each sentence carries its magnitude, because the rule is that a finding says
    how much. `report.flagged` prints these same three lists beside the
    document in `report.html`, and `tools/inspect_run.py` shows them per Zone;
    this is the machine
    reading of the same facts, taken from the IR rather than from the prose.
    """
    found = [
        f"Zone {failure.zone_index} ({failure.kind}) could not be read "
        f"[{failure.ink_share * 100:.0f}% of the page's ink]: {failure.reason}"
        for failure in document.failures
    ]
    found += [
        f"Zone {short.zone_index} ({short.kind}) was read short — "
        f"{short.printed_lines} printed lines, {short.read_lines} returned "
        f"[{short.ink_share * 100:.0f}% of the page's ink]"
        for short in document.shortfalls
    ]
    found += [
        f"ink outside every Zone [{gap.ink_share * 100:.0f}% of the page's ink]"
        + (f": {gap.note}" if gap.note else "")
        for gap in document.gaps
        if not gap.resolved
    ]
    return tuple(found)


_IR = re.compile(
    r'<script type="application/json" id="doc-ir">(.*?)</script>', re.DOTALL
)


def document_in(output_html: str) -> Document | None:
    """The IR embedded in a rendered document, or None if there is none.

    `render._embedded_ir` writes it, escaping `</` so a document containing the
    literal text `</script>` cannot terminate the block; that is undone here.
    Reading the IR back rather than scraping the findings panel is what keeps
    this from breaking the first time somebody rewords a finding.
    """
    match = _IR.search(output_html)
    if match is None:
        return None
    try:
        return Document.from_json(match.group(1).replace("<\\/", "</"))
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def account(score: DocumentScore, findings: Sequence[str]) -> Accounting:
    """Whether this document's loss was declared. The honesty rule, applied.

    Takes the findings as sentences rather than a Document, so the same rule can
    be applied to a run's output, to a frozen document, and to a case a test
    constructs — the rule is about whether something was said, not about which
    object said it.
    """
    lost = max(0, round(score.completeness.source_tokens
                        * (1.0 - score.completeness.recall)))
    declared = tuple(findings)

    if score.completeness.recall >= LOSS_TOLERANCE:
        return Accounting(
            name=score.name, recall=score.completeness.recall, lost_tokens=lost,
            findings=declared, ok=True,
            reason="nothing was lost, so there is nothing to declare",
        )
    if not declared:
        return Accounting(
            name=score.name, recall=score.completeness.recall, lost_tokens=lost,
            findings=declared, ok=False,
            reason=(
                f"recall {score.completeness.recall:.3f} — about {lost} of "
                f"{score.completeness.source_tokens} tokens did not reach the "
                "output, and the document says nothing about any of it"
            ),
        )
    return Accounting(
        name=score.name, recall=score.completeness.recall, lost_tokens=lost,
        findings=declared, ok=True,
        reason=(
            f"recall {score.completeness.recall:.3f} — about {lost} tokens "
            f"lost, declared by {len(declared)} finding(s)"
        ),
    )


def account_all(pairs: Iterable[tuple[DocumentScore, Sequence[str]]]
                ) -> list[Accounting]:
    """One `Accounting` per document, in the order given."""
    return [account(score, findings) for score, findings in pairs]


def quiet_losses(accounts: Iterable[Accounting]) -> list[Accounting]:
    """The documents that lost content and did not say so. Empty is the gate."""
    return [entry for entry in accounts if not entry.ok]
