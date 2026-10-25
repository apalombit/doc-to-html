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


def gallery(cards: Sequence[Card], pictures: Sequence[Path], target: Path, title: str,
            writers: Sequence[str] | None = None) -> Path:
    """One local HTML page with every picture at its own size beside its
    card, for looking at pages closely rather than for variety. It points
    at the pictures where they are; nothing is copied."""
    import html
    import os

    rows = []
    for index, (card, picture) in enumerate(zip(cards, pictures)):
        source = os.path.relpath(picture, target.parent)
        page = os.path.relpath(picture.with_suffix(".html"), target.parent)
        writer = writers[index] if writers else ""
        features = ", ".join(card.all_features())
        rows.append(
            f'<section id="{card.id}"><h2>{card.id} · {html.escape(card.kind or "")} '
            f'<small>{html.escape(card.family)} · {card.style} · {card.locale} · '
            f'{card.width} px · {card.density}{" · " + writer if writer else ""}</small></h2>'
            f'<p class="f">{html.escape(features)} · <a href="{page}">HTML</a></p>'
            f'<img src="{source}" width="{card.width}" alt="{card.id}"></section>')
    index_links = " ".join(f'<a href="#{card.id}">{card.id}</a>' for card in cards)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>"
        "body{margin:0;padding:16px 24px;background:#e8e8e4;font:14px Helvetica,sans-serif;color:#222}"
        "section{margin:28px 0 40px}h2{font-size:17px;margin:0 0 4px}"
        "h2 small{font-weight:400;color:#555;margin-left:8px}.f{margin:0 0 8px;color:#555}"
        "img{display:block;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.25);max-width:100%;height:auto}"
        "nav{position:sticky;top:0;background:#e8e8e4;padding:6px 0;line-height:1.8}"
        "nav a{margin-right:6px}</style></head><body>"
        f"<h1>{html.escape(title)}</h1><nav>{index_links}</nav>{''.join(rows)}</body></html>",
        encoding="utf-8")
    return target
