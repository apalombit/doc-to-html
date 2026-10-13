"""Vision models via Ollama.

Local by default. Ollama Cloud is a configuration change rather than an
architectural one — same client, same prompts, same parser — but note it is a
different *host*, not a different trust boundary: images do leave the machine.

Model budget on 8GB unified memory is roughly 4GB, which puts qwen3-vl:2b,
qwen3-vl:4b and granite3.2-vision in range and rules out deepseek-ocr at 6.7GB.
Layout and audit deliberately default to different families so their blind spots
are not shared.

Nothing here reads the environment: an Engine is handed its host, key and limits
by `config`, so there is one place to look when a setting does not take effect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..config import (
    DEFAULT_EXTRACT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_S,
    Settings,
)
from ..ir import BBox, Kind, Reading, Zone
from ..preprocess import (
    MODEL_INPUT_LONG_EDGE,
    ImageArray,
    TableGrid,
    resize_long_edge,
    table_grid,
    to_png,
    zone_pixels,
)
from ..wire import (
    EXTRACTION_SCHEMAS,
    CaptionResponse,
    ClassifyResponse,
    RunsResponse,
    caption_into,
    classification_into,
    contents_into,
    runs_into,
    schema_of,
)
from .lenient import LenientTransport
from .transport import OllamaTransport, Response, Transport

PROMPT_VERSION = "2"
"""Recorded on every Reading. Without it an eval regression cannot be attributed.

Bumped to 2 when `CLASSIFY_PROMPT`'s `pairs` entry dropped its same-line
constraint. Readings either side of that are not comparable at one version, which
is the whole reason the field exists."""

CLASSIFY_PROMPT = """You are looking at one region, cropped from a page of a
document.

Say what it structurally is.

kind — one of:
  table   a grid of rows and columns under a heading row. Decide this on the
          typesetting rather than the wording: if the top row is set apart from
          what follows — shaded, ruled off, or in bold — and its cells line up in
          the same columns as the values under it, the region is a table. That
          holds even when each heading word would read naturally as a label for
          the value beneath it, and even when only one row of values follows
  pairs   a block of labelled values, such as "Invoice No: 12". Every entry
          names its value: a line with nothing naming it is not a pair. The
          label may sit beside its value or directly above it. What makes this
          pairs rather than a table is that the labels are not set apart from
          the values as a row — not shaded, ruled off, or in bold
  prose   headings, paragraphs, addresses, free text
  list    bulleted or numbered items, or a row of navigation links
  figure  a logo, chart, stamp, signature or badge

graphic — for a figure only: logo, chart, signature, stamp or badge. Use an empty
string for every other kind.

Answer for this region only. Do not describe anything outside the crop, and do
not read the text out."""
"""The Kind question, asked about one crop rather than about a whole page.

Split out of the vision layout prompt on measured evidence, not for tidiness —
that pass is deleted, and geometry comes from a detector. Issue #13
put both of `example/invoice.png`'s wrong Kinds to a real model twice each, once
at the resolution the layout pass sees and once at the Zone's own crop, and
separated two causes the layout prompt had conflated:

- **Isolation.** Zone 1 answers `pairs` correctly at 96x38px when it is the only
  region in the question, and `prose` when it is one of seven — in runs 13, 14
  and 15. Its evidence always survived the downscale; the question was crowded.
- **Resolution, for a model that can use it.** Zone 4 — a shaded heading row over
  one data row — is `pairs` at 365x60px and `table` at 819x135px to `qwen3.5:4b`,
  and `pairs` at both to `qwen3-vl:4b`, six times out of six.

**The `table`/`pairs` wording says the typesetting decides, and that ordering was
measured rather than guessed.** The earlier version put the semantic test first —
"the heading row names the columns rather than labelling the values beside it" —
and mentioned shading as an aside, "often shaded or ruled off". One reads as a
rule and the other as a hint, so `qwen3-vl:4b` applied the rule and called
`invoice_0001`'s Zone 4 `pairs` in every run ever recorded, 8 for 8. It was not
wrong to: `Payment Method` genuinely does label the `Check` beneath it, while
`Item` names a column.

Three experiments separated the cause, all with this prompt's predecessor:

- **Not row count.** Zone 5 truncated to a heading plus one data row — Zone 4's
  exact shape — still answers `table`, 3/3. So the old "even if only one row of
  values follows it" clause was never the clause being tested.
- **Not blindness to the shading.** Asked a typesetting question alone — "is the
  top row set apart by shade, rule or bold?" — Zone 4 answers yes, 3/3. The cue
  was seen and outweighed.
- **The heading's words decide, and nothing else does.** Crossing the two heading
  bands over the two data rows, so the layout is pixel-identical and only the
  text differs, gives `table` wherever `Item | Price` is the heading and `pairs`
  wherever `Payment Method | Check #` is — 12 for 12, the data row contributing
  nothing.

Hence the inversion, plus a `pairs` clause that took Zone 3 out of `pairs`. On
`invoice_0001`, six Zones, three repeats: **6/6, against 4/6 for the wording it
replaces.** Zone 4 `pairs`→`table` and Zone 3 `pairs`→`prose`, with Zones 0, 1,
2 and 5 unmoved.

**That clause bundled two constraints, and only one of them was doing the work.**
It read "each label sits on the same line as the value it names, with nothing
below it" — a geometric test (*beside*) and a semantic one (*names*) in one
sentence. The geometric half is what turned `invoice_0002`'s two panel Zones from
`pairs` to `table`: those panels put each label above its value, and the
same-line rule read them out of `pairs` on their arrangement alone. So it is
gone, and the semantic half is now stated on its own — "every entry names its
value; a line with nothing naming it is not a pair".

**What carries Zone 3 is the half that stayed.** Zone 3 is `Acme Corp.` /
`John Doe` / `john@example.com`: three stacked lines, none of which names
another. It was never excluded from `pairs` for being stacked — plenty of pairs
are — but for being unlabelled, and that test is unchanged and now explicit. If
Zone 3 ever comes back `pairs` again, this paragraph is the thing that was
wrong, and restoring the same-line wording is the revert.

The closing sentence defers to the `table` entry rather than competing with it,
which keeps the ordering the 12/12 crossover bought: typesetting decides, and a
set-apart row of labels is a table however its words read.

Unlike the four attempts 0002 records, none of this can cost Band numbering:
Bands come from the layout stage and this prompt runs after geometry.

**The `title` paragraph is gone, and its absence is the point.** It asked for "a
short heading printed at the top of this region and naming the whole of it" and
returned `""` in all 36 of run 69's classify calls — on crops where the caption
is legible enough that the same model, asked about it alone, answered correctly
4 times out of 4. Two mechanisms are consistent with that and this change does
not need to separate them: the field may simply be a low-attention slot in a
three-part answer, or the prompt may be contradicting itself, since `kind` is
decoded first and a panel's shaded caption bar satisfies the `table` entry's own
"top row set apart" test — after which the title clause's "do not use the first
cell of a table heading row" correctly forbids reporting it. Either way the ask
is unreachable from here. It now has its own call; see `CAPTION_PROMPT`."""

CAPTION_PROMPT = """You are looking at one region, cropped from a page of a
document.

Copy out the first printed line of this region, exactly as printed.

Then say which of these three it is:

  caption   a short heading that names the whole region and is not itself part
            of the content, such as a panel caption or a card title
  header    the heading row of a grid: it has one cell per column of the values
            below it, and its words sit over the columns they name
  content   the first line of the region's own content — a paragraph's opening
            line, an address's first line, or the first labelled value

Answer for this region only, and do not read out any line but the first."""
"""What a region's first printed line is. One question, one call.

Asked because the same question inside `CLASSIFY_PROMPT` was answered `""` 36
times out of 36, and asked *this* way — alone, against the identical crops from
run 69 — was answered correctly 4 times out of 4: `sample_table_0003`'s
"Population and GDP (millions of USD)" and `invoice_0002`'s "Company Details",
"Customer Details" and "Payment Method".

**Three answers, because two were not enough, and that was the whole defect.**
The first version asked a yes/no — is this line a heading? — and got `true` on
**8 of 8** crops in run 71. It was not being ignored; it was being answered
correctly, because that prompt's test for a heading ("set apart by being bold,
larger, shaded, or alone above the rest") is word for word `CLASSIFY_PROMPT`'s
test for a table's top row. A heading row satisfies both, and with no third
answer available the model had nowhere else to put it. Two of `invoice_0001`'s
Zones lost their heading rows to that, taking a Kind, a summary row and the
385.00 Probe with them.

Measured over the 11 crops from run 71 that the two shapes were compared on —
the five `invoice_0001` false positives, three true captions and three
`sample_semantic_0005` cases:

| | correct |
|---|---|
| `is_heading: true/false` | **4 / 11** |
| `caption` / `header` / `content` | **8 / 11** |

A fourth shape was tried and rejected: asking the question semantically with
typesetting explicitly discounted ("ignore how the line is typeset") answers
`content` for `sample_table_0003`'s caption, losing the fixture the whole change
is gated on.

**One residual miss, and no further wording is proposed for it.**
`invoice_0001`'s Zone 1 opens "Invoice # : 123" and comes back `caption`, even
though the `content` entry already names "the first labelled value". It costs one
title mismatch and nothing structural.

**No measured numbers in this prompt, against the standing pattern.**
`DTH_TABLE_GRID_HINT` established that this model honours a counted fact where it
ignores a behavioural instruction, so stating the caption band's measurements
here was the obvious next move. The measurements say the opposite of the truth on
the fixture that matters most: `sample_table_0003`'s caption sits 19 rows above
its table against a median line gap of 20, so a prompt reporting that gap would
argue the model out of the answer it gets right unaided. `invoice_0002`'s panels
do show the expected signal — 30, 33 and 29 against medians of 10, 7 and 10 —
which is exactly why one number cannot be trusted to carry both. The band is
measured, but only to decide whether to ask at all, and to explain the step in
the contact sheet. See `preprocess.caption_band`.

**Reading before judging** is deliberate: `first_line` is decoded before
`line_is`, so the verdict is given against a line the model has already copied
out rather than against an impression of the crop."""

RUNS_PROMPT = """You are looking at one block of text, cropped from a page.
It has already been read. You are not being asked to read it again.

Return only the spans inside it that are **set apart from the type around
them**, each copied exactly as it is printed, with its kind:

  link    underlined, or in a colour the text around it does not use — a web
          address, an email address, or an entry in a row of navigation links
  code    set in a monospaced typeface, as a tag, a filename or a command is
  strong  noticeably bolder than the text beside it
  em      italic where the text beside it is not
  mark    printed on a band of colour, as a badge or a highlighter is

Judge every span against the text beside it, not against the page. If the whole
block is bold, nothing in it is `strong` — that is the block's own typeface. If
the whole block is one colour, there is no link in it.

Copy the span and nothing else: not the words around it, and not a whole line
unless a whole line is genuinely set apart from the lines above and below it.

Most blocks have nothing set apart in them. **Return an empty list for those.**
An empty list is the right answer far more often than not, and a span that is
not really there is worse than no answer at all."""
"""Ask one Zone which of its spans are marked — and ask nothing else.

**The separate pass, and the point is what it does not touch.** The first
attempt at inline runs appended `MARKED_CLAUSE` to the four Extractor prompts
and crossed the T1 ratchet; that constant carries the numbers. Asking here
changes no Extractor prompt, so at `temperature: 0` every extraction answer is
the one the floor already has, and content loss is off the table by
construction rather than by hope.

"It has already been read. You are not being asked to read it again." is
load-bearing: the failure mode of the first attempt was the model re-doing the
transcription differently — it returned `The two slip-ways follow...` as one
line with the hyphen inside it, where the floor had split the line and
`render._how_to_join` repairs the split. Here the transcription is not in
play, because nothing this pass returns can change a Cell's text.

The whole-block clauses mirror `projection.inlineOf`, which is what scores the
answer: it compares a run against *the block it sits in*, so a wholly bold
paragraph yields no `strong` runs. The model ignored that clause once already
and marked five whole lines of `newsletter_0008` `strong`, so it is enforced in
code as well, by `wire._covers_everything`.
"""

MARKED_CLAUSE = """
marked — the spans inside the text above that are set apart from the type
around them. Copy each one exactly as it is printed, and give its kind:
  link    underlined, or in a colour the text around it does not use — a web
          address, an email address, or an entry in a row of navigation links
  code    set in a monospaced typeface, as a tag, a filename or a command is
  strong  noticeably bolder than the text beside it
  em      italic where the text beside it is not
  mark    printed on a band of colour, as a badge or a highlighter is

Judge each span against the text beside it, not against the page: a heading set
entirely in bold is a heading, not a strong span, and a block printed wholly in
one colour has no link in it. Copy the span and nothing else — not the words
around it, and not a whole line unless the whole line is what is set apart.

Return an empty list when nothing in it is set apart. That is the usual answer,
and it is a better one than a span that is not really there."""
"""What the Extractors ask about inline runs — **BUILT, MEASURED, REVERTED.**

**Nothing sends this. Do not wire it back in without reading why.** Phase A1,
2026-09-24: it was appended to all four Extractor prompts, swept over all
fifteen documents, and **removed again because it crossed the T1 ratchet** —
which is a floor never to cross for any reason, whatever else improves.

**What it bought.** T6 went 0 of 42 to **8 of 42**, and every one of the eight
came from a `prose` or `list` Zone. `table` and `pairs` returned **zero**
usable runs.

**What it cost, read off the dumps rather than off a total.**

    invoice_0002 / 20_pairs.json   floor 5 pairs -> with this clause, 1
    invoice_0002 / 18_pairs.json   floor 6 pairs -> 6, byte-identical

The lost answer is exactly the fourteen words the document stopped printing —
`alpha`, `beta`, `gamma`, `bank`, `banks`, `deposit`, `convenience`, `final`,
`amount` and the rest of *"For your convenience, you may deposit the final
amount at one of our banks"*. Seven documents lost words, order or side-by-side
structure in all, including `sample_semantic_0005` losing `editor`, `example`
and `com` — **the email address, one of the very links this clause exists to
recover.**

**The revert was measured, not assumed.** Run `A1-04-pairs-reverted`,
`invoice_0002`, this clause dropped from `PAIRS_PROMPT` alone: **all four pairs
answers byte-identical to the floor's**, `20_pairs` back to 5.

**It also made a repairable fault unrepairable.** With the clause in, the model
returned `The two slip-ways follow a fortnight later...` as **one line with the
hyphen inside it**. At the floor it split the line, which `render._how_to_join`
repairs. Nothing at the wire or the renderer can reach a hyphen in the middle
of a single returned string.

**What would have to become true before trying again.** Not the schema — the
schema works, and `ir.Run` through `render.TAG_FOR_RUN` is proven end to end,
with `project()` reading a rendered `<code>`/`<a>` back as `code`/`link`. It is
the *asking* that failed, and it failed hardest where it paid nothing. The
obvious next attempt is a **separate pass over the same crop**, the way
`DTH_CAPTION_PASS` asks its own question without touching the Extractor's, and
on `prose` and `list` only. That is a thread's decision and a sweep's cost, not
a clause to re-append.

Two clauses below were load-bearing and should survive into any retry, because
both mirror `projection.inlineOf`, which is what scores the answer: *"against
the text beside it, not against the page"* is that function's own rule, and
*"return an empty list ... better than a span that is not really there"* exists
because `CaptionResponse` answered `true` on 8 of 8 crops when its schema
offered no way to say "neither". **Neither saved it**: the model marked five
whole lines of `newsletter_0008` `strong` regardless.
"""


TABLE_PROMPT = """You are looking at one table, cropped from a page.

Return every row of it, in order from top to bottom.

For each row give:

role — one of:
  header   a row of column headings, usually at the top and often shaded
  data     an ordinary row of the table's contents
  summary  a row of totals or subtotals, usually ruled off from the rows above it

cells — the text of each cell, left to right, exactly as printed. Keep currency
symbols, thousands separators and decimal marks as they appear on the page. Use
an empty string for a cell that is blank, and keep it in the list: a blank cell
still holds a column position.

Give every data row the same number of cells as the header row.

A row is one horizontal line of the page. Its cells can sit far apart — a wide
table puts the first column against the left edge and the last against the right,
with blank paper between them — and that is still one row. Text printed at the
same height belongs to the same row however far apart it sits, so read across the
whole width of the region before starting a new row.

Ignore decoration. A horizontal rule between two rows is not itself a row, and
neither is a shaded band behind one. Every row you return must have printed text
in at least one of its cells; a row with no text in any cell is not a row.

Read only what is printed. Do not add a row that is not on the page, do not merge
two printed rows into one, do not split one printed row across two rows, and do
not calculate anything — a total that is printed is read like any other cell, and
a total that is not printed does not exist."""
"""Read a grid, one row per printed line.

**The two paragraphs about what a row is are measured, and they changed nothing.
Do not try this again.** They close an asymmetry worth closing — this prompt
forbade *merging* two printed rows and said nothing about *splitting* one, while
`LIST_PROMPT` has forbidden both directions all along ("do not merge two entries
into one, do not split one across two") — but closing it did not move the model.
Run 48 returned answers **byte-identical** to run 47's for both tables on
`invoice_0001`. Not similar: identical. Kept because the instruction is correct
and the asymmetry was a latent trap, not because it earns its tokens.

The defect they are aimed at, from run 47's Zone 4 — a shaded heading over one
line of values, 841x59px, its two columns roughly 800px apart:

    {"role": "header", "cells": ["Payment Method", ""]},
    {"role": "header", "cells": ["", "Check #"]},
    {"role": "data",   "cells": ["Check", ""]},
    {"role": "data",   "cells": ["", "1000"]}

Four rows where the page has two. Note what is *not* wrong: every row carries two
cells, so the width check passes, and every string is correct and in the column it
belongs to. It is a well-formed table making a false claim about the document —
two records where there is one — which is why no structural rule catches it.
`_join_split_header_row` repairs the header half of this and deliberately leaves
data rows alone; see its docstring for why guessing there is dangerous.

**That makes two independent prompt attempts, and the route is closed.** Run 13
forbade the header split in as many words and failed, which is what moved the
repair into `wire.py` in the first place. Run 48 argued the general case instead
— what a row *is* on the page, rather than what a header is — on the theory that
run 13 had argued too narrowly. It produced identical output. The model's reading
of a wide, short table is not reachable from the prompt, and the remedy is the
one thing that can see what the prompt cannot: the page. A horizontal ink
projection over the crop counts the printed lines, and on both tables it is
right — 2 bands for Zone 4's two printed lines, 5 for Zone 5's five rows. That
licenses generalising `_join_split_header_row` to data rows without the guesswork
its docstring is careful about.

Every fixture's tables share this prompt, and `invoice_0001`'s Zone 5 carries the
only arithmetic Probe in the suite. A change here that fixes Zone 4 and costs
Zone 5 is a failure, not a trade — run 48 at least cost nothing, holding Zone 5
at 5 rows with the Probe reconciling."""

PAIRS_PROMPT = """You are looking at one block of label and value lines, cropped
from a page.

Return every pair in it, in order from top to bottom.

label — the text naming the value, without its trailing colon.

value — the value itself, exactly as printed. Use an empty string if a label has
nothing printed against it.

Two pairs printed side by side on one line, separated by a gap or a divider, are
two pairs and not one.

A heading printed above this block is not a pair and must not appear in the list.

Read only what is printed. Do not expand an abbreviation, do not reformat a date
or a number, do not correct what looks like a mistake, and do not add a pair that
is not on the page."""

PROSE_PROMPT = """You are looking at one block of text, cropped from a page.

Return it as a list of blocks, in order from top to bottom.

For each block give:

kind — one of:
  heading      a title for what follows
  paragraph    ordinary running text
  address      a postal address or a block of contact details
  item         one entry of a bulleted or numbered list, or one link in a row of
               navigation links
  caption      a short label belonging to a picture or a figure
  quote        text quoted from elsewhere, usually indented or in quotation marks
  attribution  the line naming the source of a quote
  mark         a stamp, a signature or a badge

lines — the text of the block, one entry per line the document breaks. A line
that runs to the right-hand edge and continues below it has merely wrapped, and
is one line. A line that stops short and continues below it was broken on
purpose, and is two — which is how a three-line address stays three lines.

Read what is printed, in full. Do not shorten a paragraph, do not summarise it,
do not correct its spelling, and do not add text that is not on the page. Leave
out a heading printed above this block that names the block rather than being
part of it.

If the region genuinely contains no text, return an empty list."""

LIST_PROMPT = """You are looking at a list, cropped from a page. It may be
bulleted, numbered, or a row of links across the top of the page.

Return one block per entry, in order, each with kind "item".

lines — the text of the entry. Leave out the bullet character or the number
itself: that a thing is a list entry is already recorded by its kind, and keeping
the marker would print it twice.

A heading printed above the list is not an entry and must not appear.

Read only what is printed. Do not merge two entries into one, do not split one
across two, and do not add an entry that is not on the page."""

FIGURE_PROMPT = """You are looking at a picture, cropped from a page — a logo, a
chart, a stamp, a signature or a badge.

graphic — which of those it is.

text — the words written on the picture that a reader reads, one entry each. For
a chart, that is its title and its axis labels. For a stamp or a badge, the words
on it. For a logo, return text only where it is set as ordinary type beside the
mark; lettering drawn as part of the artwork is part of the picture and is not
text. Return an empty list where there are no such words, which is the usual
answer for a logo and for a handwritten signature.

Never describe the picture, and never report what a chart's bars or lines are
worth. A number read off the shape of a bar is a guess, and there is nowhere for
it to go."""

EXTRACTION_PROMPTS: dict[Kind, str] = {
    Kind.TABLE: TABLE_PROMPT,
    Kind.PAIRS: PAIRS_PROMPT,
    Kind.PROSE: PROSE_PROMPT,
    Kind.LIST: LIST_PROMPT,
    Kind.FIGURE: FIGURE_PROMPT,
}
"""One prompt per Kind, and never one per document type. An invoice's line items
and an inventory's stock list are the same question. See docs/adr/0001."""


class ThinkingNotDisabled(RuntimeError):
    """The model reasoned instead of answering, and returned nothing.

    Its own failure mode, because it is indistinguishable from a truncation by
    shape — an empty `content` either way — and the two want opposite responses. A
    truncation wants a bigger budget; this wants thinking turned off.
    """


class TruncatedResponse(RuntimeError):
    """The model ran out of room and stopped mid-answer, twice.

    Not a Ladder Rung. The Ladder resolves *disagreement* between readings;
    this is a transport failure, and handling it here is what keeps retry policy
    from leaking outside the Orchestrator.
    """


@dataclass
class OllamaEngine:
    """One model, reached through the Ollama API."""

    model: str = DEFAULT_EXTRACT_MODEL
    host: str = DEFAULT_OLLAMA_HOST
    api_key: str = ""
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_s: float = DEFAULT_TIMEOUT_S
    transport: Transport | None = None
    """Injected by the suite. `None` means talk to a real Ollama."""

    lenient: bool = False
    """Repair a response that ignored the schema it was given.

    Needed only for models that do not honour `format` — which is every vision
    model on Ollama Cloud, and none of the local ones. See `engines/lenient.py`
    for why the tolerance lives behind this seam rather than in the mapper."""

    table_grid_hint: bool = False
    """State a table's measured row and column counts in its prompt.

    Off by default; see `config.DEFAULT_TABLE_GRID_HINT` for what it is aimed at
    and why a counted fact is a different lever from the two behavioural
    instructions that already failed."""

    name: str = "ollama"

    @classmethod
    def from_settings(cls, settings: Settings, model: str,
                      transport: Transport | None = None) -> OllamaEngine:
        """Build an Engine from resolved configuration.

        One constructor for every caller — the Orchestrator, the bake-off and any
        future one — because host, key, context and timeout travelling together
        from `Settings` into an Engine is one decision, and three copies of it is
        three places for a new setting to be forgotten.
        """
        return cls(
            model=model,
            host=settings.ollama_host,
            api_key=settings.ollama_api_key,
            num_ctx=settings.num_ctx,
            timeout_s=settings.timeout_s,
            transport=transport,
            lenient=settings.lenient_decoding,
            table_grid_hint=settings.table_grid_hint,
        )

    def client_kwargs(self) -> dict[str, Any]:
        """What the Ollama client is constructed with.

        Separated from the client itself so the cloud path is assertable without
        a network: pointing at Ollama Cloud is a host plus a bearer token, and
        this is where that claim can be checked.
        """
        kwargs: dict[str, Any] = {"host": self.host, "timeout": self.timeout_s}
        if self.api_key:
            kwargs["headers"] = {"Authorization": f"Bearer {self.api_key}"}
        return kwargs

    def reading(self, text: str) -> Reading:
        """One account of a value, carrying what produced it.

        Engine, model and prompt version travel with every reading so a change in
        accuracy next month can be attributed to a specific change rather than
        argued about.
        """
        return Reading(
            engine=self.name,
            text=text,
            model=self.model,
            prompt_version=PROMPT_VERSION,
        )

    def ask(self, pass_name: str, prompt: str, image: ImageArray,
            schema: dict[str, Any], long_edge: int = MODEL_INPUT_LONG_EDGE) -> str:
        """One constrained-decoding call, retried once if it ran out of room.

        A truncated response is a valid prefix of an incomplete array, so it is
        indistinguishable from a short answer by shape alone — hence both signals
        are used: what the transport reports, and whether the text parses at all.
        The single retry raises the token budget; a second truncation is a real
        failure and says so rather than returning a plausible fragment.
        """
        transport = self.transport or OllamaTransport(self.client_kwargs())
        if self.lenient:
            transport = LenientTransport(transport)
        page = to_png(resize_long_edge(image, long_edge))

        budget = self.num_ctx
        for attempt in (1, 2):
            reply = transport(
                model=self.model,
                pass_name=pass_name,
                prompt=prompt,
                images=[page],
                schema=schema,
                num_ctx=budget,
            )
            if _reasoned_instead_of_answering(reply):
                # Not a truncation to retry, however much it looks like one: the
                # model filled its budget with reasoning and never answered. A
                # bigger budget buys more reasoning, so say what it is instead.
                raise ThinkingNotDisabled(
                    f"{pass_name}: {self.model} spent its whole budget reasoning "
                    f"({len(reply.thinking)} characters) and never answered. "
                    "Thinking is not disabled for this model, and there is nothing "
                    "here to reason about."
                )
            if not _ran_out_of_room(reply):
                return reply.answer
            budget *= 2

        raise TruncatedResponse(
            f"{pass_name}: {self.model} stopped at the token limit twice, "
            f"last budget {budget // 2}. The Zone is too dense to read whole."
        )

    def read_caption(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        """Read this Zone's first printed line and say whether it is its Title.

        Cut with `zone_pixels`, the same helper `classify_zone` and every
        Extractor use, because this question needs the caption *in* frame — it is
        the one pass that must see the band the Kind question is about to be
        spared. See `CAPTION_PROMPT` for what was measured.

        Only worth asking when `preprocess.caption_band` finds a band with
        something under it; the Orchestrator owns that test, so this method makes
        no judgement about whether it should have been called.
        """
        return caption_into(
            zone,
            self.ask(
                "caption",
                with_hint(CAPTION_PROMPT, hint),
                zone_pixels(image, zone),
                schema_of(CaptionResponse),
            ),
        )

    def read_runs(self, image: ImageArray, zone: Zone,
                  hint: str | None = None) -> Zone:
        """Ask which spans of this Zone are set apart, and mark them.

        Cut with `zone_pixels`, the same helper every Extractor uses, so the
        pass judges the picture the text was read from.

        Called only for `prose` and `list` Zones that already have content —
        the Orchestrator owns that test. This method makes no judgement about
        whether it should have been called, and none about what the Zone says:
        `wire.runs_into` can only mark text that is already there.
        """
        return runs_into(
            zone,
            RunsResponse.model_validate_json(self.ask(
                "runs",
                with_hint(RUNS_PROMPT, hint),
                zone_pixels(image, zone),
                schema_of(RunsResponse),
            )),
        )

    def classify_zone(self, image: ImageArray, zone: Zone,
                      hint: str | None = None, *, skip_rows: int = 0) -> Zone:
        """Decide one Zone's Kind from that Zone's own crop.

        Takes the whole Rectified Image and cuts the Zone out itself, with the
        same helper and the same padding an Extractor uses — a classifier judging
        a differently-padded image could name a Kind for one picture while the
        Extractor reads another, and nothing in the IR would say why they
        disagreed.

        **`skip_rows` breaks that on purpose, and only downward.** It drops the
        leading crop rows holding a caption the caption pass has already taken as
        the Title, because while a shaded caption bar is visible this model reads
        it as a table's heading row — `CLASSIFY_PROMPT`'s own "top row set apart"
        test, which the bar satisfies. Cropping it off moved 2 of 3
        `invoice_0002` panels from `table` to the correct `pairs`, where a prompt
        clause spelling out the difference moved 0 of 6.

        **The Extractor still keeps the whole crop, and the arithmetic stopped
        compensating for it instead — spec 0007 Phase A0, 2026-09-22.** The
        caption used to be subtracted from the Extractor's stated row budget by
        `with_grid(titled=True)` while staying in its picture. Both halves were
        individually right and together they deleted content: the crop showed 17
        lines, the prompt said "return exactly 16", and the model dropped the
        real header row and kept the caption. `sample_table_0003` lost all five
        of its column headers that way and the harness scored it a full match.

        **Cutting the band off the Extractor's crop as well was tried first and
        rejected on measurement**, although spec 0007 named it the correct
        remedy. It costs real content wherever the caption pass took a Title
        from something that was not a caption, and the pass has no reliable test
        for that: `darkdeck_0009`'s Zone 2 is a row of four metric cards whose
        first band is the labels `AVAILABILITY / P95 LATENCY / INGEST VOLUME /
        COST PER MILLION`, and cutting it deletes three of the four. Widening
        `CaptionBand.aligns_to_grid` to catch that does not work either — over
        all fifteen documents a ratio test in place of its equality strips
        `The Castleton Chronicle`, `ELDER STREET CAFE`, `NORTHGATE MUTUAL` and
        `Why semantic HTML matters`, every one of them a real caption. Cutting
        also moved the measured *column* count on three tables, because a
        full-width caption bridges gaps that are not column boundaries.

        Removing the subtraction reaches the same property by the safer route:
        the prompt's count and the picture are now the same pixels, measured
        once. The caption comes back as a row, and `wire._without_title_echo`
        drops it — a row deleted after it was read, rather than a row the model
        was pressured into not reading.

        One Zone per call, like `extract_zone` and for the same reason: the loop
        is the Orchestrator's, so a Zone whose classification fails is a Failure
        on that Zone rather than on the document.
        """
        return classification_into(
            zone,
            self.ask(
                "classify",
                with_hint(CLASSIFY_PROMPT, hint),
                zone_pixels(image, zone)[skip_rows:],
                schema_of(ClassifyResponse),
            ),
        )

    def extract_zone(self, image: ImageArray, zone: Zone,
                     hint: str | None = None, grid: TableGrid | None = None) -> Zone:
        """Fill in a Zone's contents from the pixels it was handed.

        The pixels are already this Zone's crop — the Extractor owns
        decomposition. What is chosen here is the question: one prompt and one
        schema per Kind, and no branch anywhere on what the document is.

        **Every measurement the prompt quotes is taken from the pixels actually
        sent**, which is the property `with_grid`'s row subtraction used to
        break. See `classify_zone` for why the Kind question, and only the Kind
        question, is shown a different picture.
        """
        prompt = EXTRACTION_PROMPTS.get(zone.kind)
        schema = EXTRACTION_SCHEMAS.get(zone.kind)
        if prompt is None or schema is None:
            raise NotImplementedError(
                f"{zone.kind.value} extraction not yet wired"
            )
        if zone.kind is Kind.TABLE and self.table_grid_hint:
            # Spec 0012, G3b: the caller's grid, measured with what the page
            # draws known, when it has one.
            prompt = with_grid(prompt, grid if grid is not None else table_grid(image))
        content = self.ask(
            zone.kind.value, with_hint(prompt, hint), image, schema_of(schema)
        )
        return contents_into(zone, content, read=self.reading)

    def read_cell(self, image: ImageArray, bbox: BBox,
                  hint: str | None = None) -> Reading:
        raise NotImplementedError("cell re-read not yet wired")

    def audit_coverage(self, image: ImageArray, zones: list[Zone]) -> list[BBox]:
        raise NotImplementedError("coverage audit not yet wired")


def _reasoned_instead_of_answering(reply: Response) -> bool:
    """Whether the reasoning channel holds reasoning rather than the answer.

    The distinction is not academic: it decides between a retry at twice the
    budget and an error, and getting it backwards costs a document.

    **An empty `content` proves nothing about this model.** Ollama routes
    `qwen3-vl`'s schema-constrained output to `message.thinking` and leaves
    `message.content` empty on *every* call — checked across all 13 calls of run
    50, layout through both tables, each of which logged "chars on the reasoning
    channel" and each of which was a correct answer. So the old test here —
    truncated, no content, some thinking — was true of every genuine truncation
    this model can produce, which made the doubling retry in `ask` unreachable
    and reported a budget the page had outgrown as a thinking setting that was
    never wrong. `invoice_0002` died this way in three runs (36 twice, 51).

    What actually separates the two is the *shape* of the text. The answer is
    constrained by `format`, so it opens with a brace or a bracket however early
    it was cut off; reasoning is prose. That test costs one character.

    The budget test is kept, so the error it gates stays literally true when it
    says the model spent the whole of one. Prose that stops of its own accord is
    a different failure and still falls through to the retry.
    """
    if not reply.truncated or reply.content or not reply.thinking:
        return False
    return reply.thinking.lstrip()[:1] not in ("{", "[")


def _ran_out_of_room(reply: Response) -> bool:
    """Whether the answer was cut short.

    Two signals because either alone is unreliable: a transport may not report
    `done_reason`, and a truncated array is still valid JSON if the cut happened
    to land after a closing brace.
    """
    if reply.truncated:
        return True
    try:
        json.loads(reply.answer)
    except ValueError:
        return True
    return False


def with_grid(prompt: str, grid: TableGrid) -> str:
    """State the grid a table Extractor is filling in, measured from its crop.

    The one prompt in this project assembled from the page rather than written
    down, which is the whole idea: two attempts to talk the model out of cutting a
    wide row in half failed — run 48's answers were byte-identical to the run
    before it — and a measurement is not an instruction. The counts come from
    `preprocess.table_grid`, an ink projection over the very pixels about to be
    sent, so the prompt and the picture cannot disagree. Since spec 0012's
    G3b the Conversion measures it with the page's rules and fills known
    (`preprocess.Drawn`), so decoration is not counted as rows or columns.

    **A Title is a printed line and not a row, and the grid is now measured on
    a crop that no longer holds one.** `table_grid` counts bands of ink and
    cannot tell a caption from a heading row, so a crop carrying a caption
    measures one row too many: `sample_table_0003` prints "Population and GDP
    (millions of USD)" above its grid and came out at 17 against a true 16.

    This used to be corrected here, by a `titled=` flag subtracting one from the
    stated count while the caption stayed in the Extractor's picture. **That
    correction is removed — spec 0007 Phase A0, 2026-09-22 — because it made the
    prompt and the crop describe different pages**, and the model resolved the
    disagreement by dropping the real header row and keeping the caption. Every
    one of `sample_table_0003`'s five column headers went that way, and the
    harness scored it a full match. `extract_zone` now cuts the caption band off
    the crop, exactly as `classify_zone` does, so the count needs no correction:
    the ruler and the picture measure the same pixels by construction, which is
    a stronger property than agreeing arithmetically about pixels only one of
    them has seen.

    Stated, not enforced. The schema is untouched, so the model can return a
    different shape and every check behind it still runs. That tolerance is the
    reason the fault above cost only one document rather than every table: the
    ruler is right on three real tables and unproven on every other page in the
    world, and a sentence survives a wrong number where a schema would force
    content to be dropped or invented to satisfy one. It is worth keeping.
    """
    rows = grid.rows
    return (
        f"{prompt}\n\n"
        f"This region has been measured from the page: it holds {rows} "
        f"rows and {grid.columns} columns. Return exactly {rows} rows, each "
        f"with {grid.columns} cells. Two pieces of text at the same height are "
        f"two cells of one row, even when they sit at opposite edges with blank "
        f"paper between them — they are not two rows."
    )


def with_hint(prompt: str, hint: str | None) -> str:
    """Append a Hint verbatim.

    Verbatim is the whole point: a Hint changes what a model is told and never
    what the code does. If anything here ever starts reading it — selecting a
    prompt, an Extractor or a template — ADR 0001 has been reversed by accident.
    """
    if not hint or not hint.strip():
        return prompt
    return f"{prompt}\n\nThe operator adds, verbatim:\n{hint.strip()}"
