"""One command over a run: the checks, the report, the pages to open, their
sheets and the form (spec 0021, step 4).

    python tools/measure_run.py debug/runs/<label> [--previous debug/runs/<older>]

writes, under the run:

    checks/<page>.json   every check on one page (`checks.check_page`)
    checks/checks.json   all of them, with the code version that made them
    checks/report.md     faults by check and class, per family and per
                         feature, the words lost and invented, the pages
                         opened and why
    _review/             the opened pages' sheets, each fault boxed and
                         numbered, tiles for a dense page, and with a previous
                         run where the renders differ; the form, filled in
                         with the checks' faults (`review.build`)

**Which pages are opened** (`sample`), spec 0021 step 5: every page where a
check finds a major in cells, rules, structure or order, which a reader must
confirm; every page a change moved; and two more per family, drawn by seed.
A page flagged only by the words, lines, height, alignment or type checks is
counted in the report, not opened: those read the HTML exactly. Step 7
measures the rule: all 31 known pages opened, and whether the sample would
have found what the full review found.

**A page's checks are kept** while its output and the checks' code are
unchanged, so a 231-page run is checked once, and `--fresh` checks again.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from . import review
from .corpus import REPO, manifest

CHECKS_CODE = ("src/doc_to_html/checks.py", "src/doc_to_html/projection.py",
               "corpus/twin-spellings.json")
"""What a page's checks depend on besides its output: a change here checks
every page again."""

OPEN_CHECKS = frozenset({"cells", "rules", "structure", "order"})
"""A major from one of these opens its page: each judges where content sits
from boxes and rules a reader must confirm, where markup can mislead."""

PER_FAMILY = 2
"""Pages drawn per family on top of the rule's own, so every family is seen."""


def checks_version(root: Path = REPO) -> str:
    """A short hash of `CHECKS_CODE`: which code a page's checks were made by."""
    digest = hashlib.sha256()
    for name in CHECKS_CODE:
        path = root / name
        digest.update(name.encode())
        digest.update(path.read_bytes() if path.exists() else b"")
    return digest.hexdigest()[:12]


def _output(run: Path, model: str, name: str) -> Path:
    return review._dump(run, model) / name / "document.html"


def run_checks(run: Path, *, model: str, fresh: bool = False,
               check: Callable[[str, Path], Any] | None = None,
               say: Callable[[str], None] = print) -> dict[str, dict[str, Any]]:
    """Every page of the run checked, or its checks kept. A page with no
    output, or whose checks raise, is recorded with the reason."""
    if check is None:
        from .checks import check_page
        check = check_page
    version = checks_version()
    folder = run / "checks"
    folder.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    names = review.documents_in(run, model)
    for count, name in enumerate(names, start=1):
        html = _output(run, model, name)
        target = folder / f"{name}.json"
        if not html.exists():
            stopped = html.parent / "timeout.txt"
            reason = stopped.read_text().strip() if stopped.exists() else "no document.html"
            results[name] = {"page": name, "error": reason, "faults": []}
            continue
        if not fresh and target.exists() and target.stat().st_mtime >= html.stat().st_mtime:
            kept: dict[str, Any] = json.loads(target.read_text())
            if kept.get("version") == version:
                results[name] = kept
                continue
        try:
            result = check(name, html).to_dict()
        except Exception as error:  # noqa: BLE001 — one page must not stop the run
            result = {"page": name, "error": f"{type(error).__name__}: {error}", "faults": []}
        result["version"] = version
        target.write_text(json.dumps(result, indent=1, default=list) + "\n")
        results[name] = result
        if count % 20 == 0:
            say(f"checked {count} of {len(names)}")
    (folder / "checks.json").write_text(json.dumps(
        {"run": run.name, "version": version, "taken": date.today().isoformat(),
         "pages": results}, indent=1, default=list) + "\n")
    return results


def moved_pages(run: Path, previous: Path, *, model: str, names: Sequence[str],
                render: Any = None) -> dict[str, float | None]:
    """The share of pixels each page's render moved by against the previous
    run's, at the source's width: 0.0 where the HTML is byte-identical, None
    where the previous run has no output for it."""
    from PIL import Image

    from .corpus import page

    if render is None:
        from .projection import screenshot as render
    scratch = run / "checks" / "_moved"
    scratch.mkdir(parents=True, exist_ok=True)
    moved: dict[str, float | None] = {}
    for name in names:
        mine, theirs = _output(run, model, name), _output(previous, model, name)
        if not theirs.exists() or not mine.exists():
            moved[name] = None
            continue
        if mine.read_bytes() == theirs.read_bytes():
            moved[name] = 0.0
            continue
        width = Image.open(page(name).png_path(REPO)).width
        before, after = scratch / f"{name}-before.png", scratch / f"{name}-after.png"
        render(theirs, before, width=width)
        render(mine, after, width=width)
        _, moved[name] = review.difference(Image.open(before), Image.open(after))
        before.unlink()
        after.unlink()
    scratch.rmdir()
    return moved


def sample(checks: Mapping[str, Mapping[str, Any]], *, families: Mapping[str, str],
           moved: Mapping[str, float | None] | None = None, seed: int = 0,
           per_family: int = PER_FAMILY) -> dict[str, list[str]]:
    """The pages to open, each with why (step 5's rule)."""
    why: dict[str, list[str]] = defaultdict(list)
    for name in sorted(checks):
        result = checks[name]
        majors = sorted({f"{fault['check']}: {fault['fault']}"
                         for fault in result.get("faults", ())
                         if fault["severity"] == "major" and fault["check"] in OPEN_CHECKS})
        if majors:
            why[name].append("a major to confirm: " + ", ".join(majors))
        if (moved or {}).get(name):
            why[name].append(f"moved against the previous run, "
                             f"{100 * float((moved or {})[name] or 0):.2f}% of pixels")
    draw = random.Random(seed)
    by_family: dict[str, list[str]] = defaultdict(list)
    for name in sorted(checks):
        if not checks[name].get("error"):
            by_family[families.get(name, "") or "no family"].append(name)
    for family, names in sorted(by_family.items()):
        left = [name for name in names if name not in why]
        for name in draw.sample(left, min(per_family, len(left))):
            why[name].append(f"drawn for {family}, seed {seed}")
    return {name: why[name] for name in sorted(why)}


def marks_of(result: Mapping[str, Any]) -> list[review.Mark]:
    """A page's faults as numbered boxes, in the order the form numbers them.
    On a page whose HTML no longer lays out as its picture does
    (`checks.REGISTERED`), the source boxes are left off: they would mark
    blank paper."""
    drawn = _registered(result)
    out = []
    for n, fault in enumerate(result.get("faults", ()), start=1):
        source = [_box(box) for box in (fault.get("source_box"), *fault.get("places", ()))
                  if box and drawn]
        output = [_box(fault["output_box"])] if fault.get("output_box") else []
        out.append(review.Mark(n, tuple(dict.fromkeys(source)), tuple(output)))
    return out


def _registered(result: Mapping[str, Any]) -> bool:
    from .checks import REGISTERED

    return float(result.get("registered", 1.0)) >= REGISTERED


def _box(values: Sequence[float]) -> review.Box:
    left, top, right, bottom = (float(value) for value in values)
    return (left, top, right, bottom)


def _occurrences(fault: Mapping[str, Any]) -> int:
    return max(1, len(fault.get("places") or ()))


def report_md(run: Path, checks: Mapping[str, Mapping[str, Any]],
              opened: Mapping[str, Sequence[str]], *, entries: Mapping[str, Mapping[str, Any]],
              moved: Mapping[str, float | None] | None = None) -> str:
    """`checks/report.md`: what the checks found across the run."""
    stamp = f"{run.name} · {date.today().isoformat()}"
    pages = {name: result for name, result in checks.items() if not result.get("error")}
    failed = {name: result["error"] for name, result in checks.items() if result.get("error")}

    classes: dict[tuple[str, str], dict[str, Any]] = {}
    for name, result in pages.items():
        for fault in result["faults"]:
            entry = classes.setdefault((fault["check"], fault["fault"]),
                                       {"severity": Counter(), "pages": set(), "times": 0})
            entry["severity"][fault["severity"]] += 1
            entry["pages"].add(name)
            entry["times"] += _occurrences(fault)

    def worst(counter: Counter[str]) -> str:
        return min(counter, key=lambda value: review.SEVERITY_RANK.get(value, 2))

    lines = [
        f"# Checks — {stamp}",
        "",
        f"{len(pages)} page(s) checked"
        + (f", {len(failed)} with no checks" if failed else "")
        + f"; {sum(1 for r in pages.values() if any(f['severity'] == 'major' for f in r['faults']))}"
        " with a major. Exact, from the source HTML; severities from "
        "`docs/agents/review-criteria.md`. **A count, not a review**: the "
        "opened pages are reviewed in `_review/`.",
        "",
        "## Faults by class",
        "",
        "| check | class | severity | pages | times |",
        "|---|---|---|---|---|",
    ]
    ordered = sorted(classes.items(), key=lambda item: (
        review.SEVERITY_RANK.get(worst(item[1]["severity"]), 2), -len(item[1]["pages"]), item[0]))
    for (check, fault), entry in ordered:
        severity = " / ".join(f"{value} {count}" for value, count in entry["severity"].items()) \
            if len(entry["severity"]) > 1 else worst(entry["severity"])
        lines.append(f"| {check} | {fault} | {severity} | {len(entry['pages'])} | {entry['times']} |")

    lines += ["", "## By family", "",
              "| family | pages | with a major | majors | most pages touched |",
              "|---|---|---|---|---|"]
    by_family: dict[str, list[str]] = defaultdict(list)
    for name in pages:
        by_family[str(entries.get(name, {}).get("family") or "no family")].append(name)
    for family, names in sorted(by_family.items()):
        touched: Counter[str] = Counter()
        majors = 0
        for name in names:
            seen = {f"{f['check']}: {f['fault']}" for f in pages[name]["faults"]
                    if f["severity"] == "major"}
            touched.update(seen)
            majors += sum(1 for f in pages[name]["faults"] if f["severity"] == "major")
        with_major = sum(1 for name in names
                         if any(f["severity"] == "major" for f in pages[name]["faults"]))
        top = ", ".join(f"{label} {count}" for label, count in touched.most_common(3))
        lines.append(f"| {family} | {len(names)} | {with_major} | {majors} | {top or '—'} |")

    lines += ["", "## By feature", "",
              "A feature counts a fault when the fault's check bears on it "
              "(`checks.CHECK_FEATURES`): a cell for `table.*`, a list for "
              "`list.*`.", "",
              "| feature | pages carrying it | pages with a fault on it | times | classes |",
              "|---|---|---|---|---|"]
    carrying: Counter[str] = Counter()
    for name in pages:
        card = entries.get(name, {})
        found = [*(card.get("features") or ()), card.get("arrangement"), card.get("type")]
        carrying.update({str(feature) for feature in found if feature})
    faulted: dict[str, dict[str, Any]] = defaultdict(lambda: {"pages": set(), "times": 0,
                                                              "classes": Counter()})
    for name, result in pages.items():
        for fault in result["faults"]:
            for feature in fault.get("features") or ():
                faulted[feature]["pages"].add(name)
                faulted[feature]["times"] += _occurrences(fault)
                faulted[feature]["classes"][f"{fault['check']}: {fault['fault']}"] += 1
    for feature in sorted(carrying, key=lambda f: (-len(faulted[f]["pages"]), f)):
        info = faulted[feature]
        top = ", ".join(f"{label} {count}" for label, count in info["classes"].most_common(2))
        lines.append(f"| {feature} | {carrying[feature]} | {len(info['pages'])} | "
                     f"{info['times']} | {top or '—'} |")

    lines += ["", "## Words lost and invented", "",
              "Every word fault, by page: the `vanished` list's successor, a "
              "pointer to a page to open.", ""]
    for name, result in sorted(pages.items()):
        words = [f for f in result["faults"] if f["check"] == "words"]
        if words:
            lines.append(f"- **{name}** — " + "; ".join(
                f"{f['fault']}: {f['element']}" for f in words))
    if not any(f["check"] == "words" for r in pages.values() for f in r["faults"]):
        lines.append("None.")

    lines += ["", f"## Opened — {len(opened)} page(s)", ""]
    lines += [f"- **{name}** — {'; '.join(why)}" for name, why in opened.items()] or ["None."]
    counted = [name for name in pages if name not in opened]
    lines += ["", f"## Counted, not opened — {len(counted)} page(s)", "",
              "Flagged only by checks that read the HTML exactly, or by nothing.", ""]
    flagged = Counter(f"{f['check']}: {f['fault']}" for name in counted
                      for f in pages[name]["faults"] if f["severity"] == "major")
    lines += [f"- {label}: {count}" for label, count in flagged.most_common()] or ["No major."]
    if moved:
        lines += ["", "## Against the previous run", "",
                  f"{sum(1 for v in moved.values() if v)} page(s) moved, "
                  f"{sum(1 for v in moved.values() if v == 0.0)} identical, "
                  f"{sum(1 for v in moved.values() if v is None)} with no previous output."]
    if failed:
        lines += ["", "## Not checked", ""]
        lines += [f"- {name}: {error}" for name, error in sorted(failed.items())]
    return "\n".join(lines) + "\n"


def measure(run: Path, *, model: str = "qwen3-vl:4b", previous: Path | None = None,
            seed: int = 0, everything: bool = False, fresh: bool = False,
            render: Any = None, check: Callable[[str, Path], Any] | None = None,
            say: Callable[[str], None] = print) -> Path:
    """The one command. Returns the review folder."""
    checks = run_checks(run, model=model, fresh=fresh, check=check, say=say)
    moved = moved_pages(run, previous, model=model, names=sorted(checks), render=render) \
        if previous else None
    entries = manifest()
    families = {name: str(entries.get(name, {}).get("family") or "") for name in checks}
    opened = {name: ["every page asked for"] for name in sorted(checks)
              if not checks[name].get("error")} if everything else \
        sample(checks, families=families, moved=moved, seed=seed)

    pages = []
    for name in sorted(checks):
        entry = entries.get(name, {})
        result = checks[name]
        why = opened.get(name, [])
        if result.get("error"):
            why = [*why, f"not checked: {result['error']}"]
        pages.append(review.page_entry(
            name, family=str(entry.get("family") or ""), kind=str(entry.get("kind") or ""),
            opened=name in opened, why=why, faults=result.get("faults", ())))
    (run / "checks" / "report.md").write_text(
        report_md(run, checks, opened, entries=entries, moved=moved))
    sheets, out = review.build(
        run, model=model, documents=list(opened), previous=previous, render=render,
        marks={name: marks_of(checks[name]) for name in opened},
        body_px={name: float(checks[name].get("body_px") or 0) for name in opened},
        anchors={name: [(float(a[0]), float(a[1])) for a in checks[name].get("anchors") or ()]
                 for name in opened},
        source_notes={name: "no boxes: its HTML does not lay out as this picture"
                      for name in opened if not _registered(checks[name])},
        pages=pages)
    say(f"{len(checks)} page(s) checked, {len(sheets)} opened: "
        f"{run.name}/checks/report.md, {out.relative_to(run.parent)}/review.md")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="tools/measure_run.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="debug/runs/<label>")
    parser.add_argument("--previous", type=Path, default=None,
                        help="another run: its render on each sheet, and moved pages opened")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--seed", type=int, default=0, help="which two pages per family")
    parser.add_argument("--all", action="store_true", dest="everything",
                        help="open every page, not the sample (step 7's proof)")
    parser.add_argument("--fresh", action="store_true", help="check every page again")
    args = parser.parse_args(argv)
    measure(args.run.resolve(), model=args.model,
            previous=args.previous.resolve() if args.previous else None,
            seed=args.seed, everything=args.everything, fresh=args.fresh)
    return 0
