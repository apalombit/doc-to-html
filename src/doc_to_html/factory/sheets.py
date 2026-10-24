"""Contact sheets, for looking at the corpus's variety — spec 0020, step 2.

**Why pictures.** The validator can say a page is honest; it cannot say
the corpus looks like many hands wrote it, or that a receipt looks like a
receipt. `level-up.md` §6's stop rule — "a contact sheet of 50 looks like
one author" — is a judgement made by looking, and these are what is looked
at. The corpus has also shipped a page that hid its own text, and nothing
but a picture showed it.

Each sheet holds `PER_SHEET` thumbnails, four across. A thumbnail is the
page's own picture scaled to fit `THUMB` with its aspect kept, and is
labelled with its id, kind, style family and locale, then its card's
features in smaller type. Sheets are written to `debug/corpus-sheets/`,
which is gitignored and rebuilt on demand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from doc_to_html.factory.cards import Card

PER_SHEET = 12
ACROSS = 4
THUMB = (420, 560)
LABEL = 64
GAP = 16
FACE = "/System/Library/Fonts/Helvetica.ttc"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FACE, size)
    except OSError:
        return ImageFont.load_default()


def _fit(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int,
         draw: ImageDraw.ImageDraw) -> str:
    while text and draw.textlength(text, font=font) > width:
        text = text[:-2] + "…"
    return text


def sheet(cards: Sequence[Card], pictures: Sequence[Path], title: str,
          notes: Sequence[str] | None = None) -> Image.Image:
    """One sheet: the pages' pictures in a grid, each labelled."""
    rows = (len(cards) + ACROSS - 1) // ACROSS
    cell_w, cell_h = THUMB[0], THUMB[1] + LABEL
    width = GAP + ACROSS * (cell_w + GAP)
    height = 48 + rows * (cell_h + GAP) + GAP
    canvas = Image.new("RGB", (width, height), (232, 232, 228))
    draw = ImageDraw.Draw(canvas)
    draw.text((GAP, 14), title, fill=(30, 30, 30), font=_font(20))
    big, small = _font(14), _font(12)
    for index, (card, picture) in enumerate(zip(cards, pictures)):
        x = GAP + (index % ACROSS) * (cell_w + GAP)
        y = 48 + (index // ACROSS) * (cell_h + GAP)
        draw.rectangle((x, y, x + cell_w - 1, y + THUMB[1] - 1), fill=(250, 250, 250))
        if picture.exists():
            page = Image.open(picture).convert("RGB")
            page.thumbnail(THUMB, Image.Resampling.LANCZOS)
            px = x + (THUMB[0] - page.width) // 2
            canvas.paste(page, (px, y))
            draw.rectangle((px - 1, y - 1, px + page.width, y + page.height),
                           outline=(150, 150, 150))
        else:
            draw.text((x + 12, y + 12), "no picture", fill=(180, 0, 0), font=big)
        first = f"{card.id} · {card.kind} · {card.style} · {card.locale or card.language}"
        rest = " ".join(f.split(".", 1)[1] for f in card.all_features())
        if notes and notes[index]:
            rest = f"{notes[index]} · {rest}"
        draw.text((x, y + THUMB[1] + 6), _fit(first, big, cell_w, draw),
                  fill=(20, 20, 20), font=big)
        draw.text((x, y + THUMB[1] + 26), _fit(rest, small, cell_w, draw),
                  fill=(90, 90, 90), font=small)
        width_note = f"{card.width} px · {card.density} · {card.family}"
        draw.text((x, y + THUMB[1] + 42), _fit(width_note, small, cell_w, draw),
                  fill=(90, 90, 90), font=small)
    return canvas


def sheets(cards: Sequence[Card], pictures: Sequence[Path], out: Path, name: str,
           notes: Sequence[str] | None = None) -> list[Path]:
    """Every sheet for `cards`, `PER_SHEET` at a time, written under `out`."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    total = (len(cards) + PER_SHEET - 1) // PER_SHEET
    for number in range(total):
        part = slice(number * PER_SHEET, (number + 1) * PER_SHEET)
        image = sheet(cards[part], pictures[part],
                      f"{name} — sheet {number + 1} of {total}",
                      notes[part] if notes else None)
        target = out / f"{name}-{number + 1:02d}.png"
        image.save(target)
        written.append(target)
    return written
