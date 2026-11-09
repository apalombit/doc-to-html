"""tools/review_issues.py <out_dir>: build step 6's issue page (spec 0021).

One issue at a time, for Alessandro's decisions, in rounds: each issue
shown on one screen as two marked crops, the page beside our render, with
what the checks say, what Claude says and what Claude proposes. The
rounds, their issues and crops are `docs/agents/review-issues.json`
(each decided issue carries his decision under `decided`); this shoots each
example's render, crops and marks both sides, and writes
<out_dir>/l2-issues.html (the template tools/review_issues.html with the
data inlined) and <out_dir>/crops/*.webp beside it, ready to publish as
an Artifact with capabilities {db: {}, user: {}}. Decisions land in the
page's `issues` collection, one document per issue key.

An issue whose two crops are already in <out_dir> is not shot again, so
copying the last build's crops in first rebuilds only a new round. A
question for the plan (spec 0022) has no `run`: no render is shot, and its
one picture, if any, is `montage`, the tops of the named pages side by side,
or `picture`, one page cropped and marked by `source_crop` and `source_marks`
(spec 0023).
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


def cropped(image: Image.Image, box: list[float], marks: list[list[float]],
            labels: list[str] | None, dest: Path) -> str:
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    for i, mark in enumerate(marks):
        draw.rectangle(mark, outline=MARK, width=3)
        if labels:
            draw.rectangle([mark[2] + 2, mark[1], mark[2] + 18, mark[1] + 18], fill=MARK)
            draw.text((mark[2] + 6, mark[1] + 3), labels[i], fill="white")
    crop = image.crop((max(0, box[0]), max(0, box[1]), min(image.width, box[2]), min(image.height, box[3])))
    scale = 2 if crop.width < 400 else 1.5 if crop.width < 600 else 1
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    crop.save(dest, "WEBP", quality=88, method=6)
    return f"crops/{dest.name}"


def montage(names: list[str], top: int, dest: Path) -> list[int]:
    """The top `top` px of each page, side by side at one width; the crop box."""
    tiles = [Image.open(page(n).png_path(REPO)).convert("RGB") for n in names]
    tiles = [t.crop((0, 0, t.width, min(t.height, top))) for t in tiles]
    width = 420
    tiles = [t.resize((width, round(t.height * width / t.width)), Image.Resampling.LANCZOS) for t in tiles]
    gap, height = 12, max(t.height for t in tiles)
    sheet = Image.new("RGB", (len(tiles) * width + (len(tiles) - 1) * gap, height), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * (width + gap), 0))
    sheet.save(dest, "WEBP", quality=88, method=6)
    return [0, 0, sheet.width, sheet.height]


shot: set[str] = set()
for issue in (issue for round_ in data["rounds"] for issue in round_["issues"]):
    if "run" not in issue:
        if issue.get("montage"):
            dest = OUT / "crops" / f"{issue['key']}-source.webp"
            issue["source_crop"] = montage(issue["montage"], issue.get("montage_top", 700), dest)
            issue["source_img"] = f"crops/{dest.name}"
        elif issue.get("picture"):
            dest = OUT / "crops" / f"{issue['key']}-source.webp"
            issue["source_img"] = cropped(Image.open(page(issue["picture"]).png_path(REPO)), issue["source_crop"],
                                          issue.get("source_marks", []), issue.get("labels"), dest)
        print(issue["key"], "a question for the plan")
        continue
    done = [OUT / "crops" / f"{issue['key']}-{side}.webp" for side in ("source", "render")]
    if all(d.exists() for d in done):
        issue["source_img"], issue["render_img"] = (f"crops/{d.name}" for d in done)
        continue
    name, run = issue["page"], issue["run"]
    source = page(name).png_path(REPO)
    width = Image.open(source).width
    render = shots / f"{run}~{name}-render.png"
    if render.name not in shot:
        # Any arm's dump: today's under qwen3-vl_4b/, D2's under glm-ocr_latest/ (spec 0023).
        (html,) = (REPO / f"debug/runs/{run}/dump").glob(f"*/{name}/document.html")
        screenshot(html, render, width=width)
        shot.add(render.name)
    labels = issue.get("labels")
    issue["source_img"] = cropped(Image.open(source), issue["source_crop"], issue["source_marks"], labels,
                                  OUT / "crops" / f"{issue['key']}-source.webp")
    issue["render_img"] = cropped(Image.open(render), issue["render_crop"], issue["render_marks"], labels,
                                  OUT / "crops" / f"{issue['key']}-render.webp")
    print(issue["key"], name, run)

template = (Path(__file__).parent / "review_issues.html").read_text(encoding="utf-8")
(OUT / "l2-issues.html").write_text(
    template.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
print(", ".join(f"{r['name']}: {len(r['issues'])} issues" for r in data["rounds"]), "->", OUT / "l2-issues.html")
