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
from dataclasses import dataclass, field
from typing import Any

from ..config import (
    DEFAULT_EXTRACT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_S,
)
from ..ir import BBox, Kind, Reading, Zone
from ..preprocess import MODEL_INPUT_LONG_EDGE, ImageArray, resize_long_edge, to_png
from ..wire import (
    EXTRACTION_SCHEMAS,
    LayoutResponse,
    contents_into,
    schema_of,
    zones_from_layout,
)
from .transport import OllamaTransport, Response, Transport

PROMPT_VERSION = "1"
"""Recorded on every Reading. Without it an eval regression cannot be attributed."""

LAYOUT_PROMPT = """You are looking at one page of a document.

Divide the page into top-level regions and return them as a flat list, in
reading order. Report only where each region is and what it structurally is.
Do not read the text inside any region.

For each region give:

kind — one of:
  table   a grid of rows and columns
  pairs   label and value lines, such as "Invoice No: 12"
  prose   headings, paragraphs, addresses, free text
  list    bulleted or numbered items, or a row of navigation links
  figure  a logo, chart, stamp, signature or badge

role — one of:
  header   sits at the top of the page, above the main content
  summary  a totals or overview block
  footer   small print at the foot of the page
  body     anything else

band and column — number the horizontal stripes of the page from 0 at the top.
Regions that sit side by side belong to the same band and are numbered from 0
left to right in column. A region spanning the full width is alone in its band.

left, top, right, bottom — the region's bounding box as fractions of the page
width and height, between 0 and 1.

title — a short heading printed immediately above the region and belonging to
it, such as a panel caption or a card title. Use an empty string if there is
none. Do not invent one.

graphic — for a figure only: logo, chart, signature, stamp or badge. Use an
empty string for every other kind.

Ignore decoration. A horizontal rule, a panel border or a column divider is not
a region and must not appear in the list."""

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

Read only what is printed. Do not add a row that is not on the page, do not
merge two printed rows into one, and do not calculate anything — a total that is
printed is read like any other cell, and a total that is not printed does not
exist."""

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

    name: str = "ollama"
    calls: list[str] = field(default_factory=list)
    """Which pass ran, in order. The bake-off times these; nothing branches on it."""

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
            schema: dict[str, Any]) -> str:
        """One constrained-decoding call, retried once if it ran out of room.

        A truncated response is a valid prefix of an incomplete array, so it is
        indistinguishable from a short answer by shape alone — hence both signals
        are used: what the transport reports, and whether the text parses at all.
        The single retry raises the token budget; a second truncation is a real
        failure and says so rather than returning a plausible fragment.
        """
        transport = self.transport or OllamaTransport(self.client_kwargs())
        page = to_png(resize_long_edge(image, MODEL_INPUT_LONG_EDGE))

        budget = self.num_ctx
        for attempt in (1, 2):
            self.calls.append(pass_name)
            reply = transport(
                model=self.model,
                prompt=prompt,
                images=[page],
                schema=schema,
                num_ctx=budget,
            )
            if not _ran_out_of_room(reply):
                return reply.content
            budget *= 2

        raise TruncatedResponse(
            f"{pass_name}: {self.model} stopped at the token limit twice, "
            f"last budget {budget // 2}. The Zone is too dense to read whole."
        )

    def detect_zones(self, image: ImageArray, hint: str | None = None) -> list[Zone]:
        """Zones with Band, column, Kind, Role and bbox — no contents.

        Runs on a downscaled page: detecting regions is a coarse task that small
        models handle well, and the resolution given away here is bought back by
        cropping each Zone from the full-resolution image for extraction.
        """
        content = self.ask(
            "layout",
            with_hint(LAYOUT_PROMPT, hint),
            image,
            schema_of(LayoutResponse),
        )
        return zones_from_layout(LayoutResponse.model_validate_json(content))

    def extract_zone(self, image: ImageArray, zone: Zone,
                     hint: str | None = None) -> Zone:
        """Fill in a Zone's contents from the pixels it was handed.

        The pixels are already this Zone's crop — the Extractor owns
        decomposition. What is chosen here is the question: one prompt and one
        schema per Kind, and no branch anywhere on what the document is.
        """
        prompt = EXTRACTION_PROMPTS.get(zone.kind)
        schema = EXTRACTION_SCHEMAS.get(zone.kind)
        if prompt is None or schema is None:
            raise NotImplementedError(
                f"{zone.kind.value} extraction not yet wired"
            )
        content = self.ask(
            zone.kind.value, with_hint(prompt, hint), image, schema_of(schema)
        )
        return contents_into(zone, content, read=self.reading)

    def read_cell(self, image: ImageArray, bbox: BBox,
                  hint: str | None = None) -> Reading:
        raise NotImplementedError("cell re-read not yet wired")

    def audit_coverage(self, image: ImageArray, zones: list[Zone]) -> list[BBox]:
        raise NotImplementedError("coverage audit not yet wired")


def _ran_out_of_room(reply: Response) -> bool:
    """Whether the answer was cut short.

    Two signals because either alone is unreliable: a transport may not report
    `done_reason`, and a truncated array is still valid JSON if the cut happened
    to land after a closing brace.
    """
    if reply.truncated:
        return True
    try:
        json.loads(reply.content)
    except ValueError:
        return True
    return False


def with_hint(prompt: str, hint: str | None) -> str:
    """Append a Hint verbatim.

    Verbatim is the whole point: a Hint changes what a model is told and never
    what the code does. If anything here ever starts reading it — selecting a
    prompt, an Extractor or a template — ADR 0001 has been reversed by accident.
    """
    if not hint or not hint.strip():
        return prompt
    return f"{prompt}\n\nThe operator adds, verbatim:\n{hint.strip()}"
