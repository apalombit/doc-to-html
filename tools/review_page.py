"""tools/review_page.py <out_dir>: build step 6's review page (spec 0021).

Reads the calls in docs/agents/review-calls/ and the sheets in
debug/runs/<run>/_review/, and writes <out_dir>/l2-dev-review.html (the
template tools/review_page.html with the data inlined) and
<out_dir>/sheets/<run>/*.webp beside it, ready to publish as an Artifact
with capabilities {db: {}, user: {}}. The pages chosen are decision 2's:
every dev page where Claude's call overturns a check, the three known-fault
pages, and two at random (seed 0). Alessandro's calls land in the page's
`calls` collection, one document per fault group, `<run>~<page>~g<n>` or
`~a<n>` for a fault the review added, with the fault numbers it covers.
"""
import json, random, glob, os, sys
from pathlib import Path
from PIL import Image
OUT = Path(sys.argv[1])
runs = {r: json.load(open(f"docs/agents/review-calls/{r}.json")) for r in ("L2-dev-90", "L2-dev-mixed", "K0-known31")}
chosen = []  # (run, page, reason)
for r in ("L2-dev-90", "L2-dev-mixed"):
    for p in runs[r]["pages"]:
        if p["opened"] and any(f.get("call") == "rejected" for f in p["faults"]):
            chosen.append((r, p["name"], "my call overturns a check"))
for name in ("probe_labreport", "probe_recipe", "probe_quiz"):
    chosen.append(("K0-known31", name, "a known fault"))
taken = {(r, n) for r, n, _ in chosen}
rest = sorted((r, p["name"]) for r in ("L2-dev-90", "L2-dev-mixed") for p in runs[r]["pages"]
              if p["opened"] and (r, p["name"]) not in taken)
for r, n in random.Random(0).sample(rest, 2):
    chosen.append((r, n, "drawn at random (seed 0)"))
manifest = json.load(open("corpus/manifest.json"))["pages"]
def sheets(run, name):
    found = sorted(glob.glob(f"debug/runs/{run}/_review/*-{name}.png") + glob.glob(f"debug/runs/{run}/_review/*-{name}-p*.png"))
    out = []
    for f in found:
        dest = OUT / "sheets" / run / (Path(f).stem + ".webp")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            Image.open(f).convert("RGB").save(dest, "WEBP", quality=82, method=6)
        out.append(f"sheets/{run}/{dest.name}")
    return out
def slim(f):
    return {k: f.get(k) for k in ("n", "from", "check", "fault", "severity", "element", "note", "stage", "call", "why")}
pages = []
for run, name, reason in chosen:
    p = next(x for x in runs[run]["pages"] if x["name"] == name)
    pages.append({"run": run, "name": name, "family": p.get("family"), "kind": p.get("kind"),
                  "reason": reason, "worst": p.get("worst"), "sheets": sheets(run, name),
                  "faults": [slim(f) for f in p["faults"]]})
ranked = []
for i, c in enumerate(runs["L2-dev-90"]["ranked"]):
    ex = None
    for p in runs["L2-dev-90"]["pages"]:
        w = next((f for f in p["faults"] if f["n"] == p.get("worst")), None)
        if p["opened"] and w and w["check"] == c["check"] and w["fault"] == c["fault"]:
            ex = {"run": "L2-dev-90", "name": p["name"], "sheet": sheets("L2-dev-90", p["name"])[0],
                  "worst": slim(w)}
            break
    if ex is None:
        for p in runs["L2-dev-90"]["pages"]:
            w = next((f for f in p["faults"] if f["check"] == c["check"] and f["fault"] == c["fault"]
                      and f.get("call") != "rejected"), None)
            if p["opened"] and w:
                ex = {"run": "L2-dev-90", "name": p["name"], "sheet": sheets("L2-dev-90", p["name"])[0],
                      "worst": slim(w)}
                break
    ranked.append({"rank": i + 1, "check": c["check"], "fault": c["fault"], "why": c["why"], "example": ex})
data = {"stamp": "spec 0021 · step 6 · 2026-11-01", "runs": ["L2-dev-90", "L2-dev-mixed", "K0-known31"],
        "ranked": ranked, "pages": pages}
(OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False))
template = (Path(__file__).parent / "review_page.html").read_text(encoding="utf-8")
(OUT / "l2-dev-review.html").write_text(
    template.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
print(len(pages), "pages;", sum(len(p["faults"]) for p in pages), "faults;", sum(len(p["sheets"]) for p in pages), "sheets")
print("ranked examples:", [(r["check"], r["fault"], r["example"] and r["example"]["name"]) for r in ranked])
print("random:", [(r, n) for r, n, why in chosen if "random" in why])
tot = sum(os.path.getsize(f) for f in glob.glob(str(OUT / "sheets" / "*" / "*.webp")))
print("sheets", tot // 1024, "KB; data", os.path.getsize(OUT / "data.json") // 1024, "KB")
