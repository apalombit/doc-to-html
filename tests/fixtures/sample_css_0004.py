"""Fixture 0004 — expected IR for example/sample-css.png.

The simplest document in the set, and the one that pins down three small rules.

**Card headings are Titles.** Two bordered cards, each a caption over a
paragraph — the same shape as invoice2's panels, arriving from a completely
different source document. If Title were the wrong abstraction, two unrelated
documents would not both need it.

**A badge is a Mark, not a Graphic.** The blue `CSS` pill beside the heading
carries text a reader reads, so its text is captured. That distinguishes it from
the ACME logo in fixture 0002, whose wordmark is part of the artwork.

**Separators are not recorded.** The rule under the heading is decorative and
produces no Zone. A placeholder for it would add a box to the render carrying no
information.

The document also contains inline code spans — `<style>` and `<head>` — which
appear in the text as literal angle brackets. They are content, not markup, and
must survive escaping intact.
"""

from __future__ import annotations

from doc_to_html.ir import (
    BBox,
    Block,
    Document,
    Kind,
    Role,
    Source,
    Zone,
    cell,
)

SOURCE = Source(
    path="example/sample-css.png",
    sha256="c8e749f5758437c7a7c2ce3335cf9fb7ba5697ac81bf0c3886f165eeafb8dfd5",
    width=789,
    height=534,
)


def build() -> Document:
    """The IR a correct Conversion of example/sample-css.png should produce."""
    return Document(
        source=SOURCE,
        zones=[
            Zone(
                kind=Kind.PROSE,
                role=Role.HEADER,
                band=0,
                column=0,
                bbox=BBox(0.0456, 0.0730, 0.3118, 0.1311),
                blocks=[Block(kind="heading", lines=[cell("Sample HTML")])],
                complete=True,
            ),
            Zone(
                kind=Kind.FIGURE,
                role=Role.HEADER,
                band=0,
                column=1,
                bbox=BBox(0.3219, 0.0861, 0.3777, 0.1348),
                graphic_kind="badge",
                blocks=[Block(kind="caption", lines=[cell("CSS")])],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=1,
                column=0,
                bbox=BBox(0.0431, 0.2097, 0.9024, 0.2416),
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "This document demonstrates inline <style> blocks "
                                "with typography, layout, and components."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=2,
                column=0,
                bbox=BBox(0.0710, 0.3895, 0.7997, 0.5225),
                title="Card heading",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "Cards are reusable layout containers. Edit the CSS "
                                "in the <head> to customize."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
            Zone(
                kind=Kind.PROSE,
                role=Role.BODY,
                band=3,
                column=0,
                bbox=BBox(0.0710, 0.7322, 0.6324, 0.8633),
                title="Another card",
                blocks=[
                    Block(
                        kind="paragraph",
                        lines=[
                            cell(
                                "You can add as many as you need. Anchor links are "
                                "styled too."
                            )
                        ],
                    )
                ],
                complete=True,
            ),
        ],
    )
