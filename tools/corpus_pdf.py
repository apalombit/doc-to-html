"""Take a real PDF page into the corpus, and gate its twin (spec 0020 §P).

    # one page out of a downloaded source, its provenance, its picture, and
    # its text layer laid out for the twin's writer
    python tools/corpus_pdf.py take c0461 downloads/fw9.pdf --page 1 \
        --url https://www.irs.gov/pub/irs-pdf/fw9.pdf \
        --licence "public domain, 17 U.S.C. 105" --kind "application form" \
        --language en --locale en-US --type type.sans --arrangement arr.one_column \
        --features kv.boxed,list.ticks,table.ruled

    # the gate, then checks 5-10 on the twin corpus/pages/c0461.html
    python tools/corpus_pdf.py gate c0461

    # the rows listing again, for a page taken before the listing changed
    python tools/corpus_pdf.py list c0461

    # corpus/pdf/ATTRIBUTION.md, from every page's source record
    python tools/corpus_pdf.py attribution

`take` writes `corpus/pdf/<id>.pdf` (the page, never edited),
`corpus/pdf/<id>.source.json`, `corpus/pages/<id>.png` (the PDF's render)
and `debug/corpus-pdf/<id>.lines.txt`, and fills the PDF slot's card in
`corpus/cards.json`. `gate` writes `corpus/checks/<id>.json` when the twin
passes. Every decision is in `doc_to_html.factory.pdfpage`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.factory import cards, check, fonts, pdfpage  # noqa: E402

CORPUS = REPO / "corpus"
DEBUG = REPO / "debug" / "corpus-pdf"


def _listing(page_id: str, single: Path, width: int, height: int) -> int:
    """Write the text layer's rows for the twin's writer; return how many."""
    words = pdfpage.pdf_words(single, width)
    found = pdfpage.listing(words)
    DEBUG.mkdir(parents=True, exist_ok=True)
    faces = pdfpage.pdf_faces(single)
    header = [f"# {page_id}: {width}x{height} px; faces by characters: "
              + ", ".join(f"{face} {n}" for face, n in faces.most_common()),
              "# top height  left piece  ‖ left piece (set apart)  | left piece (either)"]
    angled = pdfpage.turned(words)
    footer = [f"# set at an angle, compared by its characters only: {angled}"] if angled else []
    (DEBUG / f"{page_id}.lines.txt").write_text("\n".join(header + found + footer) + "\n",
                                                encoding="utf-8")
    return len(found)


def _take(args: argparse.Namespace) -> int:
    seed, drawn = cards.load(CORPUS / "cards.json")
    by_id = {card.id: card for card in drawn}
    card = by_id.get(args.id)
    if card is None or card.origin != "pdf":
        print(f"{args.id} is not a PDF slot")
        return 2
    single = CORPUS / "pdf" / f"{args.id}.pdf"
    pdfpage.one_page(Path(args.source), args.page, single)
    width, height = pdfpage.render(single, args.width, CORPUS / "pages" / f"{args.id}.png")
    pdfpage.write_json(CORPUS / "pdf" / f"{args.id}.source.json", pdfpage.source_record(
        args.id, args.url, args.licence, args.page, Path(args.source), single, args.note))
    found = _listing(args.id, single, width, height)
    filled = replace(card, kind=args.kind, language=args.language, locale=args.locale,
                     type=args.type, arrangement=args.arrangement,
                     features=tuple(sorted(f for f in args.features.split(",") if f)),
                     style="real-pdf", width=width, density=args.density)
    taxonomy = cards.load_taxonomy(CORPUS / "taxonomy.json")
    problems = cards.problems(taxonomy, filled)
    if problems:
        print(f"the card would not be sound: {problems}")
        return 1
    data = json.loads((CORPUS / "cards.json").read_text(encoding="utf-8"))
    data["cards"] = [filled.to_json() if c["id"] == args.id else c for c in data["cards"]]
    data.setdefault("history", []).append({"step": "pdf page", "changed": [args.id]})
    (CORPUS / "cards.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    print(f"took {args.id}: {width}x{height} px, {found} rows; "
          f"{(DEBUG / f'{args.id}.lines.txt').relative_to(REPO)}")
    return 0


def _gate(args: argparse.Namespace) -> int:
    _, drawn = cards.load(CORPUS / "cards.json")
    card = {c.id: c for c in drawn}[args.id]
    single = CORPUS / "pdf" / f"{args.id}.pdf"
    twin = CORPUS / "pages" / f"{args.id}.html"
    picture = CORPUS / "pages" / f"{args.id}.png"
    assert card.width
    gated = pdfpage.gate(pdfpage.pdf_words(single, card.width),
                         pdfpage.twin_words(twin.read_text(encoding="utf-8"), card.width),
                         card.width)
    result = check.check(card, twin, fonts.load(CORPUS / "fonts.json"),
                         check.known_in(REPO), twin=True, picture=picture)
    for name, messages in gated.failures.items():
        for message in messages:
            result.fail(f"gate_{name}", message)
    print(f"{args.id}: {gated.matched} of {gated.rows} rows matched; worst offsets "
          f"{gated.worst_left:.1f} px across, {gated.worst_top:.1f} px down "
          f"(tolerance {pdfpage.GEOMETRY * card.width:.1f})")
    runs = pdfpage.split_paragraphs(pdfpage.twin_blocks(twin.read_text(encoding="utf-8"),
                                                        card.width))
    for run in runs:
        print(f"  structure, to read: {run}")
    if result.passed:
        check.keep_twin(result, card, twin, picture, CORPUS / "checks" / f"{args.id}.json",
                        {"rows": gated.rows, "worst_left": round(gated.worst_left, 1),
                         "worst_top": round(gated.worst_top, 1), "one_line_runs": len(runs)})
        print(f"PASS {args.id}")
        return 0
    (CORPUS / "checks" / f"{args.id}.json").unlink(missing_ok=True)
    print(f"FAIL {args.id}")
    for name, messages in result.failures.items():
        for message in messages[:10]:
            print(f"  {name}: {message}")
        if len(messages) > 10:
            print(f"  {name}: ... and {len(messages) - 10} more")
    return 1


ATTRIBUTION_HEAD = """# Where the PDF pages come from

Written by `tools/corpus_pdf.py attribution` from each page's
`<id>.source.json`; do not edit by hand.

Each page below is one page copied out of its source document, unedited:
`<id>.pdf` holds that page alone, and `corpus/pages/<id>.png` is its render.
`corpus/pages/<id>.html` is not the source's: it is a redrawing of the page
in HTML, written for this corpus as the ground truth a converter is marked
against, with the page's words as its picture shows them. Those are the
only changes made. Licences are as each source states them; where a
licence asks for its source to be named, it is named here.

| page | source | page of source | licence and attribution |
|---|---|---|---|
"""


def _attribution() -> int:
    rows = []
    for record in sorted((CORPUS / "pdf").glob("*.source.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        licence = data["licence"].replace("|", "\\|")
        rows.append(f"| {data['id']} | <{data['url']}> | {data['page']} | {licence} |")
    target = CORPUS / "pdf" / "ATTRIBUTION.md"
    target.write_text(ATTRIBUTION_HEAD + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"{target.relative_to(REPO)}: {len(rows)} pages")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    take = sub.add_parser("take", help="take one page of a source PDF into a PDF slot")
    take.add_argument("id")
    take.add_argument("source")
    take.add_argument("--page", type=int, required=True)
    take.add_argument("--url", required=True)
    take.add_argument("--licence", required=True)
    take.add_argument("--note", default="")
    take.add_argument("--kind", required=True)
    take.add_argument("--language", required=True)
    take.add_argument("--locale", required=True)
    take.add_argument("--type", required=True)
    take.add_argument("--arrangement", required=True)
    take.add_argument("--features", required=True)
    take.add_argument("--density", default="medium")
    take.add_argument("--width", type=int, default=pdfpage.WIDTH)
    sub.add_parser("attribution", help="write corpus/pdf/ATTRIBUTION.md from the records")
    listed = sub.add_parser("list", help="write a taken page's rows for the twin's writer again")
    listed.add_argument("id")
    gate = sub.add_parser("gate", help="gate a PDF page's twin")
    gate.add_argument("id")
    args = parser.parse_args()
    if args.command == "attribution":
        return _attribution()
    if args.command == "list":
        from PIL import Image

        single = CORPUS / "pdf" / f"{args.id}.pdf"
        with Image.open(CORPUS / "pages" / f"{args.id}.png") as picture:
            width, height = picture.size
        print(f"{args.id}: {_listing(args.id, single, width, height)} rows")
        return 0
    return _take(args) if args.command == "take" else _gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
