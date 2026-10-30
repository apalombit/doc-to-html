"""Spec 0021, step 4: one command over a run.

What is pinned: which pages the sampling rule opens and why, that a page's
checks are kept until its output or the checks' code changes, that a moved
render is told from an identical one, and, over the three probe pages
whose faults are known, that the command opens each for the class that
names its fault and arrives with the form filled in.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from doc_to_html import measure, review
from doc_to_html.projection import available

REPO = Path(__file__).resolve().parent.parent
needs_chrome = pytest.mark.skipif(not available(), reason="headless Chrome not found")


def fault(check: str, name: str, severity: str = "major", **more: Any) -> dict[str, Any]:
    return {"check": check, "fault": name, "severity": severity, "element": "x",
            "note": "", "features": [], "source_box": None, "output_box": None,
            "places": [], **more}


def a_run(root: Path, label: str, pages: dict[str, str]) -> Path:
    run = root / label
    for name, html in pages.items():
        folder = run / "dump" / "qwen3-vl_4b" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "document.html").write_text(html)
    return run


class TestTheSamplingRule:
    CHECKS = {
        "a": {"faults": [fault("cells", "wrong column")]},
        "b": {"faults": [fault("words", "lost"), fault("lines", "broken differently"),
                         fault("height", "height")]},
        "c": {"faults": [fault("structure", "marker changed", "minor")]},
        "d": {"faults": [fault("order", "interleaved"), fault("rules", "frame missing")]},
        "e": {"faults": []},
        "f": {"faults": [], "error": "no document.html"},
    }
    FAMILIES = {"a": "forms", "b": "forms", "c": "forms", "d": "reports", "e": "reports",
                "f": "reports"}

    def test_a_major_a_reader_must_confirm_opens_its_page(self) -> None:
        opened = measure.sample(self.CHECKS, families=self.FAMILIES, per_family=0)
        assert sorted(opened) == ["a", "d"]
        assert opened["d"] == ["a major to confirm: order: interleaved, rules: frame missing"]

    def test_words_lines_and_height_are_counted_not_opened(self) -> None:
        assert "b" not in measure.sample(self.CHECKS, families=self.FAMILIES, per_family=0)

    def test_a_moved_page_opens_and_an_unmoved_one_does_not(self) -> None:
        opened = measure.sample(self.CHECKS, families=self.FAMILIES, per_family=0,
                                moved={"b": 0.012, "c": 0.0, "e": None})
        assert sorted(opened) == ["a", "b", "d"]
        assert opened["b"] == ["moved against the previous run, 1.20% of pixels"]

    def test_two_more_per_family_by_seed_never_a_page_with_no_checks(self) -> None:
        opened = measure.sample(self.CHECKS, families=self.FAMILIES, seed=7)
        drawn = {name for name, why in opened.items() if any("drawn for" in w for w in why)}
        assert drawn == {"b", "c", "e"}, "two of forms' three, all reports' one left"
        assert opened == measure.sample(self.CHECKS, families=self.FAMILIES, seed=7)


def test_a_faults_boxes_become_its_numbered_mark() -> None:
    result = {"faults": [fault("type", "bold lost", source_box=[1, 2, 3, 4],
                               places=[[1, 2, 3, 4], [5, 6, 7, 8]], output_box=[9, 9, 10, 10]),
                         fault("height", "height", "minor")]}
    first, second = measure.marks_of(result)
    assert first == review.Mark(1, ((1, 2, 3, 4), (5, 6, 7, 8)), ((9, 9, 10, 10),))
    assert second == review.Mark(2)


class Result:
    def __init__(self, page: str) -> None:
        self.page = page

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "faults": [fault("cells", "wrong column")]}


def test_a_pages_checks_are_kept_until_its_output_or_the_code_changes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = a_run(tmp_path, "99-test", {"c0008": "<p>one</p>", "c0009": "<p>two</p>"})
    (run / "dump" / "qwen3-vl_4b" / "c0010").mkdir()
    asked: list[str] = []

    def check(name: str, html: Path) -> Result:
        asked.append(name)
        return Result(name)

    first = measure.run_checks(run, model="qwen3-vl:4b", check=check, say=lambda line: None)
    assert asked == ["c0008", "c0009"]
    assert first["c0010"]["error"] == "no document.html"
    measure.run_checks(run, model="qwen3-vl:4b", check=check, say=lambda line: None)
    assert asked == ["c0008", "c0009"], "nothing changed, nothing checked"
    monkeypatch.setattr(measure, "checks_version", lambda root=REPO: "another")
    measure.run_checks(run, model="qwen3-vl:4b", check=check, say=lambda line: None)
    assert asked == ["c0008", "c0009"] * 2
    saved = json.loads((run / "checks" / "checks.json").read_text())
    assert saved["version"] == "another" and sorted(saved["pages"]) == ["c0008", "c0009", "c0010"]


def test_a_page_whose_checks_raise_is_recorded_and_the_rest_go_on(tmp_path: Path) -> None:
    run = a_run(tmp_path, "99-test", {"c0008": "<p>one</p>", "c0009": "<p>two</p>"})

    def check(name: str, html: Path) -> Result:
        if name == "c0008":
            raise RuntimeError("Chrome went away")
        return Result(name)

    results = measure.run_checks(run, model="qwen3-vl:4b", check=check, say=lambda line: None)
    assert results["c0008"]["error"] == "RuntimeError: Chrome went away"
    assert results["c0009"]["faults"]


def drawn_by_length(html: Path, destination: Path, *, width: int,
                    height: int | None = None) -> Path:
    """A screenshot whose ink depends on the page's text, so two pages
    differ when their HTML does."""
    pixels = np.full((200, width, 3), 255, dtype=np.uint8)
    pixels[10:10 + len(html.read_text()), :20] = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(destination)
    return destination


def test_moved_is_told_from_identical_and_from_new(tmp_path: Path) -> None:
    older = a_run(tmp_path, "98-older", {"c0008": "<p>same</p>", "c0009": "<p>short</p>"})
    run = a_run(tmp_path, "99-test", {"c0008": "<p>same</p>", "c0009": "<p>much longer</p>",
                                      "c0010": "<p>new</p>"})
    moved = measure.moved_pages(run, older, model="qwen3-vl:4b",
                                names=["c0008", "c0009", "c0010"], render=drawn_by_length)
    assert moved["c0008"] == 0.0 and moved["c0010"] is None
    assert moved["c0009"] is not None and moved["c0009"] > 0


KNOWN = {"probe_labreport": "labreport", "probe_quiz": "quiz", "probe_recipe": "recipe"}


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The three probe pages whose faults are known, from their committed
    renders, through the one command."""
    run = tmp_path_factory.mktemp("runs") / "K0-known"
    for page, folder in KNOWN.items():
        target = run / "dump" / "qwen3-vl_4b" / page
        target.mkdir(parents=True)
        shutil.copy(REPO / "docs" / "level-up-probe" / "out" / folder / "render.html",
                    target / "document.html")
    measure.measure(run, say=lambda line: None)
    return run


@needs_chrome
class TestTheKnownFaults:
    def test_each_page_opens_for_the_class_that_names_its_fault(self, measured: Path) -> None:
        record = json.loads((measured / "_review" / "findings.json").read_text())
        why = {page["name"]: " ".join(page["why"]) for page in record["pages"]}
        assert "cells: wrong column" in why["probe_labreport"]
        assert "rules: cells merged as drawn" in why["probe_quiz"]
        assert "order: interleaved" in why["probe_recipe"]
        assert "structure: numbers as bullets" in why["probe_recipe"]

    def test_the_form_arrives_with_the_checks_faults_waiting_for_a_call(
            self, measured: Path) -> None:
        record = json.loads((measured / "_review" / "findings.json").read_text())
        assert record["rubric_version"] == review.RUBRIC_VERSION
        lab = next(page for page in record["pages"] if page["name"] == "probe_labreport")
        wrong = sorted(f["element"] for f in lab["faults"] if f["fault"] == "wrong column")
        assert wrong == ["231", "6.4", "84", "92"]
        assert all(f["call"] is None and f["stage"] is None and f["from"] == "check"
                   for f in lab["faults"])
        assert [f["n"] for f in lab["faults"]] == list(range(1, len(lab["faults"]) + 1))

    def test_each_opened_page_has_its_sheet_and_the_report_counts_them(
            self, measured: Path) -> None:
        sheets = sorted(path.name for path in (measured / "_review").glob("*.png"))
        assert [name for name in sheets if "tile" not in name] == [
            "00-probe_labreport.png", "01-probe_quiz.png", "02-probe_recipe.png"]
        report = (measured / "checks" / "report.md").read_text()
        assert "| cells | wrong column | major | 1 | 4 |" in report
        assert "## Opened — 3 page(s)" in report
