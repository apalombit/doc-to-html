"""tools/review_issues.py <out_dir>: build step 6's issue page (spec 0021).

One issue at a time, for Alessandro's decisions: the review's
disagreements with the checks, ranked by consequence, each shown on one
page as two marked crops, the page beside our render. The issues and
their crops are `docs/agents/review-issues.json`; this shoots each
example's render, crops and marks both sides, and writes
<out_dir>/l2-issues.html (the template tools/review_issues.html with the
data inlined) and <out_dir>/crops/*.webp beside it, ready to publish as
an Artifact with capabilities {db: {}, user: {}}. Decisions land in the
page's `issues` collection, one document per issue key.
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from doc_to_html.corpus import page  # noqa: E402
from doc_to_html.projection import screenshot  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1])
MARK = (214, 40, 40)
data = json.loads((REPO / "docs/agents/review-issues.json").read_text(encoding="utf-8"))
(OUT / "crops").mkdir(parents=True, exist_ok=True)
shots = OUT / "shots"
shots.mkdir(exist_ok=True)


def cropped(image: Image.Image, box, marks, labels, dest: Path) -> str:
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    for i, mark in enumerate(marks):
        draw.rectangle(mark, outline=MARK, width=3)
        if labels:
            draw.rectangle([mark[2] + 2, mark[1], mark[2] + 18, mark[1] + 18], fill=MARK)
            draw.text((mark[2] + 6, mark[1] + 3), labels[i], fill="white")
    box = [max(0, box[0]), max(0, box[1]), min(image.width, box[2]), min(image.height, box[3])]
    crop = image.crop(box)
    scale = 2 if crop.width < 400 else 1.5 if crop.width < 600 else 1
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    crop.save(dest, "WEBP", quality=88, method=6)
    return f"crops/{dest.name}"


for issue in data["issues"]:
    name, run = issue["page"], issue["run"]
    source = page(name).png_path(REPO)
    width = Image.open(source).width
    render = shots / f"{name}-render.png"
    screenshot(REPO / f"debug/runs/{run}/dump/qwen3-vl_4b/{name}/document.html", render, width=width)
    labels = issue.get("labels")
    issue["source_img"] = cropped(Image.open(source), issue["source_crop"], issue["source_marks"], labels,
                                  OUT / "crops" / f"{issue['key']}-source.webp")
    issue["render_img"] = cropped(Image.open(render), issue["render_crop"], issue["render_marks"], labels,
                                  OUT / "crops" / f"{issue['key']}-render.webp")
    print(issue["key"], name, run)

template = (Path(__file__).parent / "review_issues.html").read_text(encoding="utf-8")
(OUT / "l2-issues.html").write_text(
    template.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
print(len(data["issues"]), "issues ->", OUT / "l2-issues.html")
