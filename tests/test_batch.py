"""Spec 0021, step 3: the batch runner, without a model.

A 27-hour run must survive being stopped. What is pinned here is that a
stopped run resumes where it stopped and converts no page twice, that a
page cut off mid-write is converted again, that a page which raises is
recorded and the run goes on, and that a run refuses to resume on another
list or on other conversion code. The converter is injected; the real one
is `bakeoff.run`, proved on one page by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_to_html import batch, corpus
from doc_to_html.bakeoff import Attempt
from doc_to_html.batch import BatchError, guard_residency, pages_for, run_batch, status

REAL_CHANGED = batch.conversion_changed

PAGES = ("c0008", "c0009", "probe_quiz", "invoice_0001")
"""Four dev pages of the manifest, two generated, one probe, one of the 21."""


class Stop(Exception):
    """Stands in for the process being killed between two pages."""


def converter(calls: list[str], *, error_on: str | None = None):  # type: ignore[no-untyped-def]
    def convert(name: str, png: Path) -> Attempt:
        assert png.is_file()
        calls.append(name)
        attempt = Attempt(fixture=name, model="m:1")
        attempt.answers = [("classify", '{"kind":"prose"}', "prompt")]
        attempt.html = f"<html><body><p>{name}</p></body></html>"
        if name == error_on:
            attempt.error = "MappingError: no Zones"
            attempt.html = None
        return attempt
    return convert


@pytest.fixture(autouse=True)
def no_git_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The working tree may hold uncommitted measurement code; a resume in
    these tests is about the run's own record, not this checkout's."""
    monkeypatch.setattr(batch, "conversion_changed", lambda since: [])


class TestWhichPages:
    def test_dev_is_231_and_200_without_the_known(self) -> None:
        assert len(pages_for("dev")) == 231
        assert len(pages_for("dev", skip_known=True)) == 200

    def test_the_vault_is_refused_as_a_pool_and_by_id(self) -> None:
        sealed = next(page_id for page_id, entry in corpus.manifest().items()
                      if entry["pool"] == "vault")
        with pytest.raises(corpus.SealedError):
            pages_for("vault")
        with pytest.raises(corpus.SealedError):
            pages_for(f"c0008,{sealed}")

    def test_a_list_of_manifest_ids(self) -> None:
        assert pages_for(",".join(PAGES)) == PAGES


class TestResuming:
    def test_a_stopped_run_converts_each_page_exactly_once(self, tmp_path: Path) -> None:
        calls: list[str] = []

        def stop_after_second(name: str) -> None:
            if name == PAGES[1]:
                raise Stop

        run = tmp_path / "L2-batch"
        with pytest.raises(Stop):
            run_batch(run, PAGES, model="m:1", convert=converter(calls),
                      after_page=stop_after_second, say=lambda line: None)
        assert status(run).done == 2 and not status(run).running
        result = run_batch(run, PAGES, model="m:1", convert=converter(calls),
                           say=lambda line: None)
        assert calls == list(PAGES)
        assert (result.done, result.total, result.errors) == (4, 4, 0)
        logged = [json.loads(line)["page"] for line in (run / "pages.jsonl").read_text().splitlines()]
        assert logged == list(PAGES)
        assert sorted(path.name for path in (run / "dump" / "m_1").iterdir()) == sorted(PAGES)
        assert (run / "dump" / "m_1" / "probe_quiz" / "document.html").read_text().count("probe_quiz")
        assert len((run / "resumes.txt").read_text().splitlines()) == 1
        assert (run / "done.txt").exists() and not (run / "batch.pid").exists()

    def test_a_page_cut_off_mid_write_is_converted_again(self, tmp_path: Path) -> None:
        calls: list[str] = []
        run = tmp_path / "L2-batch"
        with pytest.raises(Stop):
            run_batch(run, PAGES, model="m:1", convert=converter(calls),
                      after_page=lambda name: (_ for _ in ()).throw(Stop),
                      say=lambda line: None)
        half = run / ".partial" / "m_1" / PAGES[1]
        half.mkdir(parents=True)
        (half / "00_classify.json").write_text("{")
        run_batch(run, PAGES, model="m:1", convert=converter(calls), say=lambda line: None)
        assert calls == list(PAGES)
        assert not (run / ".partial").exists()

    def test_a_page_that_raises_is_recorded_and_the_run_goes_on(self, tmp_path: Path) -> None:
        calls: list[str] = []
        run = tmp_path / "L2-batch"
        result = run_batch(run, PAGES, model="m:1", convert=converter(calls, error_on="c0009"),
                           say=lambda line: None)
        assert (result.done, result.errors) == (4, 1)
        assert (run / "dump" / "m_1" / "c0009" / "00_classify.json").exists()
        assert not (run / "dump" / "m_1" / "c0009" / "document.html").exists()

    def test_another_list_is_refused(self, tmp_path: Path) -> None:
        run = tmp_path / "L2-batch"
        run_batch(run, PAGES[:2], model="m:1", convert=converter([]), say=lambda line: None)
        with pytest.raises(BatchError, match="another list"):
            run_batch(run, PAGES, model="m:1", convert=converter([]), say=lambda line: None)

    def test_other_conversion_code_is_refused(self, tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
        run = tmp_path / "L2-batch"
        run_batch(run, PAGES[:2], model="m:1", convert=converter([]), say=lambda line: None)
        monkeypatch.setattr(batch, "conversion_changed",
                            lambda since: ["src/doc_to_html/orchestrator.py"])
        with pytest.raises(BatchError, match="orchestrator.py"):
            run_batch(run, PAGES[:2], model="m:1", convert=converter([]), say=lambda line: None)


def test_only_conversion_files_count_as_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Measurement code may move under a running batch, which is how this
    spec builds its checks while dev converts; conversion code may not."""
    monkeypatch.setattr(batch, "_git", lambda *args: "\n".join([
        "src/doc_to_html/checks.py", "src/doc_to_html/review.py",
        "src/doc_to_html/factory/cards.py", "src/doc_to_html/render.py",
        "src/doc_to_html/engines/ollama.py"]))
    assert REAL_CHANGED("abc") == ["src/doc_to_html/render.py",
                                   "src/doc_to_html/engines/ollama.py"]


class TestResidency:
    def test_another_model_resident_is_refused(self) -> None:
        with pytest.raises(BatchError, match="llama3.2:3b"):
            guard_residency("qwen3-vl:4b", "http://localhost:11434", fresh=True,
                            resident=lambda host: ["llama3.2:3b"])

    def test_our_own_model_is_unloaded_on_a_fresh_start_only(self,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(batch.time, "sleep", lambda seconds: None)
        stopped: list[str] = []
        for fresh in (True, False):
            guard_residency("qwen3-vl:4b", "http://localhost:11434", fresh=fresh,
                            resident=lambda host: ["qwen3-vl:4b"], stop=stopped.append)
        assert stopped == ["qwen3-vl:4b"]

    def test_a_remote_host_is_not_guarded(self) -> None:
        guard_residency("qwen3-vl:4b", "https://ollama.example", fresh=True,
                        resident=lambda host: ["other"])
