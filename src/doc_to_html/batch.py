"""Convert a pool of the corpus one page at a time, detached and resumable.

Spec 0021, step 3. A sweep (`tools/iterate.sh`) converts 21 pages in one
process and writes its dump when the last page is done (`bakeoff.main`
calls `write_dump` after `run` returns), so a run that dies keeps nothing.
At about 8 minutes a page, dev's 200 unconverted pages take about 27
hours, and a run that long must survive a crash, a reboot and a lid
closed by mistake. So this runner:

- converts **one page at a time, through the bake-off's own path**
  (`bakeoff.run`, so the engines, the settings and the trace are a
  sweep's: the lesson of `DTH_HEADING_RULE`, which reached `Settings` and
  never the detector);
- writes **each page's dump the moment it converts**, first under
  `.partial/` and then moved into `dump/` in one rename, so a page is in
  the dump whole or not at all;
- on a restart, **skips every page already in the dump**, so no page is
  converted twice, and a page cut off mid-conversion is converted again;
- records **seconds per page** in `pages.jsonl`, and a page that raises
  keeps its trace and answers while the run goes on;
- refuses the **vault**: `corpus.names` raises `SealedError`, and nothing
  here passes `unseal`;
- refuses to **resume on other conversion code**: a run is one pipeline,
  and a page converted by yesterday's code beside one converted by
  today's measures neither;
- gives **each page a time limit** (`PAGE_MINUTES`): the page converts in a
  child process, which is stopped at the limit, and the page is recorded as
  timed out, with the reason in its dump, and not tried again;
- **stops between two pages** when `stop.txt` is in the run directory: the
  page in flight finishes and is recorded, the run ends without
  `done.txt`, and the next start removes the file and resumes. Killing a
  detached run instead would cut the page in flight, or leave its child
  converting with no parent.

It writes `debug/runs/<label>/` as a sweep does, so `report`, the replay,
the rederive and the visual review all read it.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .bakeoff import Attempt, write_dump
from .corpus import REPO, manifest, names, page

MEASUREMENT = (
    "projection.py", "scoring.py", "report.py", "review.py", "checks.py",
    "corpus.py", "batch.py", "measure.py", "geometry_score.py", "factory/",
)
"""The modules under `src/doc_to_html/` that measure rather than convert.

Everything else there is conversion code, the bake-off included, since it
builds the engines. A resume refuses when conversion code has changed since
the run started; measurement code may move under a running batch, which is
how spec 0021 builds its checks while dev converts."""

Converter = Callable[[str, Path], Attempt]
"""Converts one page: its id and its picture, to the bake-off's Attempt."""

PAGE_MINUTES = 20.0
"""How long one page may take before it is stopped and recorded as timed
out. Alessandro, 2026-10-31, after c0004 ran for 8 hours: one call on a
near-empty crop ran to the token limit, and its retry at twice the context
pushed the 8 GB machine into swap. On a quiet machine the S14 sweep took
130-1,036 s a page; at 20 minutes none of its 21 pages would have stopped,
at 10 minutes four would (darkdeck, newsletter, pricing, cv)."""


class PageTimeout(Exception):
    """A page did not convert within its run's limit."""

    def __init__(self, seconds: float) -> None:
        super().__init__(f"timeout: not converted within {seconds / 60:.0f} minutes; stopped")
        self.seconds = seconds


class BatchError(RuntimeError):
    """The run cannot start or resume as asked; the message says why."""


@dataclass(frozen=True)
class Status:
    """Where a run stands, read from its directory alone."""

    label: str
    total: int
    done: int
    errors: int
    mean_seconds: float | None
    running: bool
    timeouts: int = 0

    @property
    def left_hours(self) -> float | None:
        if self.mean_seconds is None:
            return None
        return (self.total - self.done) * self.mean_seconds / 3600

    def line(self) -> str:
        left = f", about {self.left_hours:.1f} h left" if self.left_hours is not None \
            and self.done < self.total else ""
        mean = f", mean {self.mean_seconds:.0f} s a page" if self.mean_seconds else ""
        state = "running" if self.running else "not running"
        stopped = f", {self.timeouts} timed out" if self.timeouts else ""
        return (f"{self.label}: {self.done} of {self.total} pages done, {self.errors} "
                f"raised{stopped}{mean}{left}; {state}")


def pages_for(spec: str, *, skip_known: bool = False) -> tuple[str, ...]:
    """The pages a run converts: a pool (`dev`, `l3`) or a comma list.

    `skip_known` drops the 31 pages already converted and committed (the
    21's `s14-result/` and the ten probe pages), which is dev's 200 left.
    """
    wanted = names(spec)
    if not skip_known:
        return wanted
    entries = manifest()
    return tuple(name for name in wanted
                 if entries.get(name, {}).get("origin") not in ("corpus", "probe"))


def _slug(model: str) -> str:
    return model.replace(":", "_")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def conversion_changed(since: str) -> list[str]:
    """Conversion files that differ between commit `since` and the working
    tree, measurement modules excepted."""
    changed = _git("diff", "--name-only", since, "--", "src/doc_to_html").splitlines()
    return [path for path in changed
            if not any(path.removeprefix("src/doc_to_html/").startswith(module)
                       for module in MEASUREMENT)]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def status(run: Path) -> Status:
    listing = run / "fixtures.txt"
    total = len(listing.read_text().split()) if listing.exists() else 0
    done = errors = timeouts = 0
    seconds: list[float] = []
    log = run / "pages.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            entry = json.loads(line)
            done += 1
            timeouts += entry.get("verdict") == "timeout"
            errors += bool(entry.get("error")) and entry.get("verdict") != "timeout"
            seconds.append(float(entry["seconds"]))
    pid_file = run / "batch.pid"
    running = pid_file.exists() and _alive(int(pid_file.read_text().strip() or 0))
    return Status(run.name, total, done, errors,
                  sum(seconds) / len(seconds) if seconds else None, running, timeouts)


def done_pages(run: Path, model: str) -> set[str]:
    """Pages whose dump is whole: moved into `dump/` by the last rename."""
    dump = run / "dump" / _slug(model)
    return {path.name for path in dump.iterdir() if path.is_dir()} if dump.is_dir() else set()


def _record_start(run: Path, wanted: Sequence[str], model: str) -> None:
    """What a sweep records, written once, on the run's first start."""
    (run / "fixtures.txt").write_text("\n".join(wanted) + "\n")
    (run / "commit.txt").write_text(_git("rev-parse", "HEAD") + "\n")
    (run / "model.txt").write_text(model + "\n")
    from .config import ENVIRONMENT, load
    (run / "dth_env.txt").write_text("".join(
        f"{name}={setting.value}\n" for name, setting in sorted(load().origins.items())
        if name.startswith("DTH_") and setting.source == ENVIRONMENT))
    from .engines.ollama import CLASSIFY_PROMPT
    (run / "classify_prompt_sent.txt").write_text(CLASSIFY_PROMPT)
    (run / "started.txt").write_text(datetime.now().isoformat(timespec="seconds") + "\n")


def run_batch(run: Path, wanted: Sequence[str], *, model: str, convert: Converter,
              after_page: Callable[[str], None] | None = None,
              say: Callable[[str], None] = print,
              page_minutes: float | None = None) -> Status:
    """Convert every page of `wanted` not yet in the run's dump.

    A fresh directory records the run (`_record_start`); an existing one is
    resumed, after checking it is the same list, the same page limit, and
    that no conversion code has changed since it started. `convert` is
    injected so the resuming can be tested without a model; `after_page` is
    called after each page is recorded, and a test raises from it to stop
    the run. A `convert` that raises `PageTimeout` records the page as timed
    out: a `timeout.txt` in its dump says why, and a resume skips it.
    """
    run.mkdir(parents=True, exist_ok=True)
    pid_file = run / "batch.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip() or 0)
        if pid != os.getpid() and _alive(pid):
            raise BatchError(f"{run.name} is already being converted by process {pid}")
    listing = run / "fixtures.txt"
    if listing.exists():
        recorded = listing.read_text().split()
        if recorded != list(wanted):
            raise BatchError(f"{run.name} was started on another list of pages; "
                             "pick a new label")
        commit = (run / "commit.txt").read_text().strip()
        changed = conversion_changed(commit)
        if changed:
            raise BatchError(f"conversion code changed since {run.name} started at "
                             f"{commit[:7]}: {', '.join(changed)}. A run is one "
                             "pipeline; pick a new label")
        limit = run / "page_limit.txt"
        recorded_limit = limit.read_text().strip() if limit.exists() else "none"
        if recorded_limit != _limit_text(page_minutes):
            raise BatchError(f"{run.name} was started with a page limit of {recorded_limit} "
                             f"minutes, not {_limit_text(page_minutes)}; the limit decides "
                             "which pages are dropped, so pick a new label")
        with (run / "resumes.txt").open("a") as resumes:
            resumes.write(f"{datetime.now().isoformat(timespec='seconds')} "
                          f"{_git('rev-parse', 'HEAD')}\n")
    else:
        _record_start(run, wanted, model)
        (run / "page_limit.txt").write_text(_limit_text(page_minutes) + "\n")
    pid_file.write_text(f"{os.getpid()}\n")
    stop = run / "stop.txt"
    stop.unlink(missing_ok=True)

    partial = run / ".partial"
    if partial.exists():
        shutil.rmtree(partial)
    dump = run / "dump" / _slug(model)
    dump.mkdir(parents=True, exist_ok=True)
    try:
        finished = done_pages(run, model)
        todo = [name for name in wanted if name not in finished]
        say(f"{run.name}: {len(wanted) - len(todo)} of {len(wanted)} already done, "
            f"{len(todo)} to convert")
        stopped_early = False
        for name in todo:
            if stop.exists():
                stopped_early = True
                say(f"{run.name}: stopped by stop.txt with {status(run).done} of "
                    f"{len(wanted)} done; start it again to go on")
                break
            started = time.perf_counter()
            entry: dict[str, Any]
            try:
                attempt = convert(name, page(name).png_path())
            except PageTimeout as stopped:
                seconds = time.perf_counter() - started
                folder = partial / _slug(model) / name
                folder.mkdir(parents=True)
                (folder / "timeout.txt").write_text(f"{stopped}\n")
                folder.rename(dump / name)
                entry = {"page": name, "seconds": round(seconds, 1), "model_seconds": None,
                         "calls": None, "verdict": "timeout", "error": str(stopped),
                         "finished": datetime.now().isoformat(timespec="seconds")}
                with (run / "pages.jsonl").open("a") as log:
                    log.write(json.dumps(entry) + "\n")
                say(f"{name}: {seconds:.0f} s, {stopped}")
                if after_page is not None:
                    after_page(name)
                continue
            seconds = time.perf_counter() - started
            write_dump([attempt], partial)
            (partial / _slug(model) / name).rename(dump / name)
            entry = {
                "page": name, "seconds": round(seconds, 1),
                "model_seconds": round(attempt.seconds, 1),
                "calls": len(attempt.answers), "verdict": attempt.verdict,
                "error": attempt.error,
                "finished": datetime.now().isoformat(timespec="seconds"),
            }
            with (run / "pages.jsonl").open("a") as log:
                log.write(json.dumps(entry) + "\n")
            say(f"{name}: {seconds:.0f} s, {entry['calls']} calls, {attempt.verdict}")
            if after_page is not None:
                after_page(name)
        if not stopped_early:
            (run / "done.txt").write_text(datetime.now().isoformat(timespec="seconds") + "\n")
    finally:
        pid_file.unlink(missing_ok=True)
        if partial.exists():
            shutil.rmtree(partial)
    return status(run)


def _limit_text(page_minutes: float | None) -> str:
    return "none" if not page_minutes else f"{page_minutes:g}"


def bounded(target: Callable[..., Any], args: tuple[Any, ...], seconds: float) -> Any:
    """`target(*args)` in a child process, stopped after `seconds`.

    A child, not a thread, so a call blocked in the model's stream can be
    stopped at all; stopping it closes its connection, and Ollama drops a
    request whose client has gone. Raises `PageTimeout` at the limit, and
    re-raises what the child raised.
    """
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    child = context.Process(target=_relay, args=(send, target, args), daemon=True)
    child.start()
    send.close()
    try:
        if not receive.poll(seconds):
            raise PageTimeout(seconds)
        try:
            ok, value = receive.recv()
        except EOFError:
            raise RuntimeError(f"the conversion process died (exit {child.exitcode})") from None
    finally:
        if child.is_alive():
            child.terminate()
            child.join(10)
        if child.is_alive():
            child.kill()
        child.join()
    if not ok:
        raise value
    return value


def _relay(send: Any, target: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        send.send((True, target(*args)))
    except BaseException as error:  # noqa: BLE001 — carried to the parent
        try:
            send.send((False, error))
        except Exception:  # noqa: BLE001 — an exception that will not pickle
            send.send((False, RuntimeError(f"{type(error).__name__}: {error}")))


def convert_page(model: str, name: str, png: Path) -> Attempt:
    """One page through `bakeoff.run`, in whichever process calls it."""
    return ollama_converter(model)(name, png)


def d2_page(name: str, png: Path) -> Attempt:
    """One page through arm D2 (spec 0023), in whichever process calls it."""
    from .parser_first import attempt
    result: Attempt = attempt(name, png)
    return result


def bounded_d2(page_minutes: float | None) -> Converter:
    """Arm D2's converter, each page in a child process stopped at the limit."""
    if not page_minutes:
        return d2_page

    def convert(name: str, png: Path) -> Attempt:
        result: Attempt = bounded(d2_page, (name, png), page_minutes * 60)
        return result

    return convert


def bounded_converter(model: str, page_minutes: float | None) -> Converter:
    """The real converter, each page in a child process stopped at the limit
    (`PAGE_MINUTES`); with no limit, in this process."""
    if not page_minutes:
        return ollama_converter(model)

    def convert(name: str, png: Path) -> Attempt:
        attempt: Attempt = bounded(convert_page, (model, name, png), page_minutes * 60)
        return attempt

    return convert


def resident_models(host: str) -> list[str]:
    """Models Ollama has loaded at `host`, by name."""
    import ollama

    return [str(loaded.model) for loaded in ollama.Client(host=host).ps().models]


def resident_split(host: str) -> str:
    """What `ollama ps` shows of each loaded model: its size, its context and
    how much of it sits on the GPU, which is what moves a run's timings."""
    import ollama

    lines = []
    for loaded in ollama.Client(host=host).ps().models:
        size, vram = int(loaded.size or 0), int(loaded.size_vram or 0)
        gpu = round(100 * vram / size) if size else 0
        lines.append(f"{loaded.model}  {size / 1e9:.1f} GB  {100 - gpu}%/{gpu}% CPU/GPU  "
                     f"context {loaded.context_length}")
    return "\n".join(lines) + "\n"


def guard_residency(model: str, host: str, *, fresh: bool,
                    resident: Callable[[str], list[str]] = resident_models,
                    stop: Callable[[str], None] | None = None) -> None:
    """`tools/iterate.sh`'s guard: no other model may be resident, because
    memory presents as latency on the 8 GB M1 (an unrelated model once made
    a 4.5 s pass take 180 s). Our own model left over is unloaded on a
    fresh start, for a cold start like a sweep's; a resume keeps it."""
    if not any(local in host for local in ("localhost", "127.0.0.1", "0.0.0.0")):
        return
    loaded = resident(host)
    ours = [name for name in loaded if name == model]
    others = [name for name in loaded if name != model]
    if others:
        raise BatchError(f"another model is resident in Ollama ({', '.join(others)}); "
                         "run 'ollama stop <model>' first")
    if ours and fresh:
        (stop or (lambda name: subprocess.run(["ollama", "stop", name],
                                              capture_output=True)))(model)
        time.sleep(3)


def ollama_converter(model: str) -> Converter:
    """The real converter: `bakeoff.run` over one page, a sweep's settings."""
    from .bakeoff import run as bakeoff_run
    from .config import configure_logging, load

    settings = load()
    configure_logging(settings)

    def convert(name: str, png: Path) -> Attempt:
        (attempt,) = bakeoff_run([model], {name: png}, settings)
        return attempt

    return convert


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="tools/batch.py",
        description="Convert a pool of the corpus, one page at a time, resumable. "
                    "Start it detached: nohup … & disown; --status says where it is; "
                    "touch debug/runs/<label>/stop.txt to stop it after the page in flight.")
    parser.add_argument("label", help="debug/runs/<label>")
    parser.add_argument("--pages", default="dev",
                        help="a pool (dev, l3) or a comma list of page ids; never the vault")
    parser.add_argument("--skip-known", action="store_true",
                        help="leave out the 31 pages already converted (dev's 200 left)")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--page-minutes", type=float, default=PAGE_MINUTES,
                        help="stop a page after this long and record it as timed out; 0 for no limit")
    parser.add_argument("--status", action="store_true", help="say where the run is and stop")
    parser.add_argument("--arm", choices=("today", "d2"), default="today",
                        help="today's pipeline, or D2: GLM-OCR's pipeline, the adapter, our "
                             "looks (spec 0023); D2 reads with glm-ocr:latest")
    args = parser.parse_args(argv)
    if args.arm == "d2":
        from .parser_first import MODEL
        args.model = MODEL

    run = REPO / "debug" / "runs" / args.label
    if args.status:
        print(status(run).line())
        return 0
    try:
        wanted = pages_for(args.pages, skip_known=args.skip_known)
        from .config import load
        host = load().ollama_host
        guard_residency(args.model, host, fresh=not (run / "fixtures.txt").exists())
        fresh = not (run / "ollama_ps_before.txt").exists()
        run.mkdir(parents=True, exist_ok=True)
        if fresh:
            (run / "host.txt").write_text(host + "\n")
            (run / "arm.txt").write_text(args.arm + "\n")
            (run / "ollama_ps_before.txt").write_text(resident_split(host))
        result = run_batch(run, wanted, model=args.model,
                           convert=(bounded_d2(args.page_minutes) if args.arm == "d2"
                                    else bounded_converter(args.model, args.page_minutes)),
                           say=lambda line: print(line, flush=True),
                           page_minutes=args.page_minutes)
        (run / "ollama_ps_after.txt").write_text(resident_split(host))
    except (BatchError, KeyError, PermissionError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(result.line())
    return 1 if result.errors else 0
