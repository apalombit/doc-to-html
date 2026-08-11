"""Ask the classifier about perfect crops, and find out whose fault the Kinds are.

    python tools/classify_truth_probe.py [--label 42-classify-truth]

`example/invoice.png` converts with three mismatches and **all three are wrong
Kinds** — Zone 3 read as `pairs` where the reference says `prose`, Zone 4 read as
`pairs` where it says `table`, and Zone 3's extraction then failing because the
Pairs Extractor was handed prose.

Specs 0003 and 0004 both assume the crops are why. 0004 goes further and spends
four tickets improving geometry on the strength of it. Two measurements have
since undercut the assumption:

- Zone 4's crop is **not** crowded. Its ink is its own two lines with blank
  margin above and below; the nearest neighbour ink stops 8px clear of the box.
- Wiring the snap made the document **worse**, 3 mismatches to 6, while the
  geometry it produced scores 0.91 IoU against the true rectangles.

So this asks the question directly, and it is cheap: hand the classifier the
crop taken from the **true** Zone rectangle — read off `example/invoice.html` by
`tools/fixture_geometry.py`, not eyeballed — and see which Kinds come back.

    every Kind correct    the crops were the problem, and geometry work pays
    same Kinds wrong      the crops were never the problem, and four tickets of
                          geometry were aimed at the wrong thing

Six calls. The same Engine, the same prompt, the same padding and the same
`classify_zone` the Conversion uses, so the only thing changed is the rectangle.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doc_to_html.config import load  # noqa: E402
from doc_to_html.engines.ollama import OllamaEngine  # noqa: E402
from doc_to_html.geometry_score import expected_zones  # noqa: E402
from doc_to_html.ir import Kind, Role, Zone  # noqa: E402
from doc_to_html.preprocess import crop, rectify, to_png  # noqa: E402

EXPECTED = REPO / "tests" / "fixtures" / "invoice_0001.expected.json"
SOURCE = REPO / "example" / "invoice.png"

SHIPPED_KINDS = ["figure", "pairs", "prose", "pairs", "pairs", "table"]
"""What the Conversion answered from the model's own boxes, run 40.

Zones 3 and 4 are the mismatches: `prose` and `table` are what the reference
says. Written out so this probe's rows can be read against them without opening
another run.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="42-classify-truth")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    out = REPO / "debug" / "runs" / args.label
    out.mkdir(parents=True, exist_ok=True)

    settings = load()
    engine = OllamaEngine.from_settings(settings, settings.classify_model)
    rectified = rectify(SOURCE)
    truth = expected_zones(EXPECTED)

    lines = [
        f"classification from the TRUE crop — {settings.classify_model}",
        "",
        "The rectangles are read off example/invoice.html, not eyeballed, so a",
        "wrong Kind here cannot be blamed on the crop.",
        "",
        f"{'zone':6}{'expected':>10}{'from true crop':>18}{'from model box':>18}"
        f"{'seconds':>9}",
    ]
    right = 0
    for zone in truth:
        if zone.box is None:
            continue
        asked = Zone(kind=Kind.PROSE, role=Role(zone.role), bbox=zone.box,
                     band=zone.band, column=zone.column)
        (out / f"zone_{zone.index:02d}_true_crop.png").write_bytes(
            to_png(crop(rectified.image, zone.box)))

        answers = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            try:
                answered = engine.classify_zone(rectified.image, asked)
                answers.append((answered.kind.value, time.perf_counter() - started))
            except Exception as exc:  # noqa: BLE001
                answers.append((f"{type(exc).__name__}", 0.0))

        got = answers[0][0] if len(set(a for a, _ in answers)) == 1 else "/".join(
            a for a, _ in answers)
        took = sum(t for _, t in answers) / len(answers)
        mark = "" if got == zone.kind else "   <- WRONG"
        if got == zone.kind:
            right += 1
        lines.append(
            f"{zone.index:<6}{zone.kind:>10}{got:>18}"
            f"{SHIPPED_KINDS[zone.index]:>18}{took:9.1f}{mark}"
        )
        print(lines[-1], file=sys.stderr)

    lines += [
        "",
        f"{right} of {len(truth)} correct from perfect crops.",
        "",
    ]
    if right == len(truth):
        lines += [
            "READING: the crops were the problem. Every Kind is right once the",
            "rectangle is right, so geometry is worth the work — but note that",
            "wiring the snap still cost the document (run 39), so a better crop",
            "helps classification and hurts extraction, and both have to be",
            "carried together.",
        ]
    else:
        lines += [
            "READING: the crops were NOT the problem. The classifier gets these",
            "Kinds wrong when handed the exact rectangle from the source HTML, so",
            "no amount of geometry repair reaches them. Spec 0004's premise does",
            "not hold for this document, and the work belongs in classification —",
            "the prompt, the model, or the question being asked.",
        ]

    report = "\n".join(lines)
    (out / "summary.txt").write_text(report + "\n")
    print()
    print(report)
    print(f"\ncrops and summary in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
