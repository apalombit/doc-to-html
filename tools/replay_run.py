"""Replay a run's recorded answers through a real Conversion. No model call.

**Why this exists.** `tools/rederive.py` re-applies the steps that work on the
IR; it cannot re-run what sits between a model's answer and the IR — the wire
schemas, the mapper, the wire-level row nets — nor say what a *different*
answer to one call would do to the whole page. This does both. Every answer a
run recorded for a document is served back, pass by pass in the order it was
asked, to a Conversion the bake-off builds exactly as `tools/iterate.sh` does
— the real detector, every CV stage, every pass — and the result is written
as a run the report and the visual review read like any other.

    python tools/replay_run.py <run or frozen dir> --label <label>
    python tools/replay_run.py <run or frozen dir> --label <label> \\
        --documents invoice_0001 --swap invoice_0001:07=answer.json
    python -m doc_to_html.report debug/runs/<label> --model qwen3-vl:4b \\
        --documents sweep --previous tests/frozen/s6-result/scores.json

The source is a run directory, read from each document's `trace.json`, or a
frozen directory carrying `answers/<document>.json` — the same calls with
their prompts dropped, written by `--save-answers` when the directory was
frozen. `debug/` is cleared; a frozen directory's answers are committed, so
this loop needs no sweep first.

`--swap <document>:<NN>=<file>` serves `<file>` where the run recorded
`NN_<pass>.json` — the NN-th call, counted from 00: a prompt change probed on
one crop, measured on its whole document and against the ratchet, for no
sweep. Q5 measured the withheld one-column grid hint this way.

**A replay answers only the questions the run asked.** When today's code asks
one the run did not — a box moved, a Zone split, a swapped Kind routed to
another Extractor — the queue for that pass runs dry, and the Conversion
records a Failure for that Zone and carries on, as it would for any pass that
raised — or, for a pass that swallows its own error, records nothing. The
tool counts each pass's calls against the run's (`asked_more`), marks that
document **ASKED MORE THAN THE RUN** and names the pass, and nothing
it produced there is a measurement: answers are served in order, so once the
questions change, the answers that were served may belong to other questions.
That is a finding about the change, not a fault in the tool — the change
moved a crop, and a crop costs a sweep. Answers left unserved are named too:
the code asked fewer questions than the run did.

**A replay also says when a call was asked differently** — spec 0012 §4b,
2026-10-13. Serving by pass and order, a change that asks the same number
of calls *differently* — a grid hint of 8 rows where the run asked 4, a
crop moved a few pixels — is served the old answers and comes back looking
like a change that did nothing. So every call records a hash of its prompt,
its picture and its schema (`trace.asked_of`), the frozen answers keep it,
and the replay compares today's call with the one whose answer it was
served. A document with any call that moved is marked **ASKED DIFFERENTLY —
not a measurement**, naming each call as `NN_<pass>` and the parts that
moved, byte-identical or not. That list is what a sweep's prediction names
before the sweep is taken. Answers frozen before that day carry no hash,
and the replay counts them rather than passing them.

**Proved 2026-09-30**, before it was relied on: over sweep `Q5-40-sweep`, taken
at the commit this tool was written against, it reproduced **15 of 15**
documents byte for byte, and again from `tests/frozen/q5-result/`'s answers.
Over `Q5-10-reshot-sweep`, taken before Q5's three changes, 14 of 15 came back
byte-identical and `receipt_0010` asked two classify questions the run never
did — Q5's `prefer_container` rule gives it two more Zones — which is the
behaviour described above.

**This is not a substitute for a run.** It cannot say what the model would
answer to a question it was not asked. Say which of the two produced any
number you report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from doc_to_html import bakeoff  # noqa: E402
from doc_to_html.config import load  # noqa: E402
from doc_to_html.corpus import page  # noqa: E402
from doc_to_html.engines.transport import Response  # noqa: E402
from replay import ReplayTransport, reasoning_channel  # noqa: E402

KEPT = ("pass_name", "answer", "truncated", "error", "asked")
"""What a replay needs of a call. The prompt is not among it: it is what
today's code sends, and serving by pass and order never reads it. Its hash
is — `asked`, with the picture's and the schema's — so a replay can say
when today's code put a call differently from the run."""


class Source:
    """A run directory or a frozen one, read the same way."""

    def __init__(self, root: Path, model: str) -> None:
        self.root = root
        self.dump = root / "dump" / model.replace(":", "_")
        self.frozen = (root / "answers").is_dir()

    def names(self) -> list[str]:
        if self.frozen:
            return sorted(f.stem for f in (self.root / "answers").glob("*.json"))
        return sorted(t.parent.name for t in self.dump.glob("*/trace.json"))

    def calls(self, name: str) -> list[dict[str, Any]]:
        path = (self.root / "answers" / f"{name}.json" if self.frozen
                else self.dump / name / "trace.json")
        calls: list[dict[str, Any]] = json.loads(
            path.read_text(encoding="utf-8"))["calls"]
        return calls

    def document(self, name: str) -> Path:
        return (self.root / "documents" / f"{name}.html" if self.frozen
                else self.dump / name / "document.html")


def recorded(name: str, calls: list[dict[str, Any]],
             swaps: dict[int, Path]) -> dict[str, list[Response]]:
    """One document's answers, one queue per pass, in call order.

    Read from the Trace rather than the `NN_<pass>.json` files because the
    Trace carries what the files do not: whether a call came back truncated,
    and whether it raised. A truncated answer served as a whole one would take
    the retry path the run did not take.
    """
    if failed := [f"{i:02d}_{c['pass_name']}" for i, c in enumerate(calls)
                  if c["error"]]:
        raise SystemExit(f"{name}: calls {', '.join(failed)} raised in the "
                         f"run, and a raise cannot be replayed")
    if unknown := sorted(set(swaps) - set(range(len(calls)))):
        raise SystemExit(f"{name}: the run made {len(calls)} calls, so there "
                         f"is no call {unknown[0]:02d} to swap")
    queues: dict[str, list[Response]] = {}
    for index, call in enumerate(calls):
        answer = (swaps[index].read_text(encoding="utf-8") if index in swaps
                  else call["answer"])
        queues.setdefault(call["pass_name"], []).append(
            reasoning_channel(answer, truncated=call["truncated"]))
    return queues


def asked_differently(recorded_calls: list[dict[str, Any]],
                      today: list[Any]) -> tuple[list[str], int]:
    """Each call today's code put differently from the run, and how many of
    the run's calls carry no hash to compare against.

    Paired the way the answers are served — by pass, in order — so the call
    named is the one whose answer was served to it. Named as `NN_<pass>` by
    the run's numbering, which is what `--swap` takes, with the parts that
    moved: `07_table picture`. A call the run never asked is not here;
    `asked_more` counts it, and the document is ASKED MORE THAN THE RUN.
    """
    served: dict[str, list[tuple[int, dict[str, str]]]] = {}
    for index, call in enumerate(recorded_calls):
        served.setdefault(call["pass_name"], []).append(
            (index, call.get("asked") or {}))
    moved: list[str] = []
    unhashed = 0
    for call in today:
        queue = served.get(call.pass_name)
        if not queue:
            continue
        index, then = queue.pop(0)
        if not then:
            unhashed += 1
            continue
        parts = [part for part in ("prompt", "picture", "schema")
                 if then.get(part) != call.asked.get(part)]
        if parts:
            moved.append(f"{index:02d}_{call.pass_name} {'+'.join(parts)}")
    return moved, unhashed


def not_asked_alike(recorded_calls: list[dict[str, Any]],
                    today: list[Any]) -> list[str]:
    """Each call the run asked that today's code asked nowhere alike — the
    same pass, prompt, picture and schema, wherever it falls in the order.
    Spec 0015, step 1.

    `asked_differently` pairs calls the way answers are served, by pass and
    order, so a new call asked *before* an old one of the same pass shifts
    every old one after it: spec 0015's new re-reads of unclaimed lines sort
    among spec 0014's, and the ticket's `OSLO GARDERMOEN` crop, asked again
    byte for byte, was named as moved because a new crop took its turn. A
    call named there and not here was only asked in another turn. Matched
    as a multiset, each of today's calls standing for one of the run's."""
    left = [(call.pass_name, call.asked.get("prompt"), call.asked.get("picture"),
             call.asked.get("schema")) for call in today]
    missing: list[str] = []
    for index, call in enumerate(recorded_calls):
        then = call.get("asked") or {}
        key = (call["pass_name"], then.get("prompt"), then.get("picture"),
               then.get("schema"))
        if then and key in left:
            left.remove(key)
        elif then:
            missing.append(f"{index:02d}_{call['pass_name']}")
    return missing


def asked_more(recorded_calls: list[dict[str, Any]],
               today: list[Any]) -> dict[str, int]:
    """How many calls more than the run today's code made, by pass.

    Counted off the transport rather than read off the Conversion's
    Failures, because a pass that swallows its own error — the inline runs,
    spec 0014's re-read of an unclaimed line — leaves no Failure when its
    queue runs dry, and the document would come back looking like one that
    asked nothing new."""
    then: dict[str, int] = {}
    for call in recorded_calls:
        then[call["pass_name"]] = then.get(call["pass_name"], 0) + 1
    now: dict[str, int] = {}
    for call in today:
        now[call.pass_name] = now.get(call.pass_name, 0) + 1
    return {name: count - then.get(name, 0) for name, count in now.items()
            if count > then.get(name, 0)}


def exported(root: Path) -> dict[str, str]:
    """The `DTH_*` a run was taken under, as `tools/iterate.sh` recorded them."""
    listing = root / "dth_env.txt"
    lines = listing.read_text().splitlines() if listing.is_file() else []
    return {key: value for key, _, value in
            (line.partition("=") for line in lines if "=" in line)
            if key != "DTH_LOG_LEVEL"}


def save_answers(source: Source, into: Path) -> int:
    """Write each document's calls, prompts dropped, as `into/answers/`."""
    (into / "answers").mkdir(parents=True, exist_ok=True)
    for name in source.names():
        calls = [{key: call[key] for key in KEPT} for call in source.calls(name)]
        (into / "answers" / f"{name}.json").write_text(
            json.dumps({"calls": calls}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
    print(f"{len(source.names())} documents' answers -> {into / 'answers'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="a run or a frozen directory")
    parser.add_argument("--label", help="the new run's label")
    parser.add_argument("--model", default="qwen3-vl:4b")
    parser.add_argument("--documents", default="",
                        help="comma-separated names; default is every document "
                             "the source recorded")
    parser.add_argument("--swap", action="append", default=[],
                        metavar="DOCUMENT:NN=FILE",
                        help="serve FILE where the run recorded NN_<pass>.json")
    parser.add_argument("--save-answers", type=Path, metavar="DIR",
                        help="write the source's answers into DIR/answers/ for "
                             "freezing, and replay nothing")
    args = parser.parse_args()

    source = Source(args.source.resolve(), args.model)
    if args.save_answers:
        return save_answers(source, args.save_answers)
    if not args.label:
        parser.error("--label is required to replay")
    target = REPO / "debug" / "runs" / args.label
    if target.exists():
        print(f"{target} already exists — pick another label")
        return 1

    # A replay converts on this process's Settings, so they must be the run's.
    # The trap `DTH_HEADING_RULE` set: a flag that does not arrive looks
    # exactly like a flag that does nothing.
    here = {key: value for key, value in os.environ.items()
            if key.startswith("DTH_") and key != "DTH_LOG_LEVEL"}
    there = exported(source.root)
    if here != there:
        print(f"the run was taken under {there or 'no DTH_* at all'} and this "
              f"shell exports {here or 'none'} — export the run's, then replay")
        return 1

    names = ([name.strip() for name in args.documents.split(",") if name.strip()]
             or source.names())
    swaps: dict[str, dict[int, Path]] = {}
    for swap in args.swap:
        where, _, file = swap.partition("=")
        name, _, index = where.partition(":")
        if name not in names or not index.isdigit() or not Path(file).is_file():
            print(f"--swap {swap}: want DOCUMENT:NN=FILE, with DOCUMENT among "
                  f"those replayed and FILE on disk")
            return 1
        swaps.setdefault(name, {})[int(index)] = Path(file).resolve()

    transports = {
        name: ReplayTransport(recorded(name, source.calls(name),
                                       swaps.get(name, {})))
        for name in names
    }
    corpus = {name: page(name).png_path(REPO) for name in names}
    attempts = bakeoff.run(
        [args.model], corpus, load(),
        transport_for=lambda model, name: transports[name],
        resident_for=lambda model: None,
    )

    target.mkdir(parents=True)
    bakeoff.write_dump(attempts, target / "dump")
    (target / "fixtures.txt").write_text("".join(f"{n}\n" for n in names))
    (target / "replayed_from.txt").write_text(
        f"{source.root}\nits recorded answers served to today's code by "
        f"tools/replay_run.py; no model call\n"
        + "".join(f"swap {s}\n" for s in args.swap))

    identical = differently = unhashed = 0
    for attempt in attempts:
        name = attempt.fixture
        replies = transports[name].replies
        left = ({pass_name: len(queue) for pass_name, queue in replies.items()
                 if queue} if isinstance(replies, dict) else {})
        before = source.document(name)
        same = (attempt.html is not None and before.is_file()
                and before.read_text(encoding="utf-8") == attempt.html)
        identical += same
        unanswered = [f for f in attempt.failures if "were recorded" in f]
        more = asked_more(source.calls(name), transports[name].calls)
        moved, blind = asked_differently(
            source.calls(name),
            attempt.trace.calls if attempt.trace is not None else [])
        differently += bool(moved)
        unhashed += blind
        # A call asked differently was served the answer to another
        # question, so nothing after it is a measurement — however the page
        # came out, byte-identical included.
        outcome = ("ASKED MORE THAN THE RUN — not a measurement"
                   if unanswered or more else "ASKED DIFFERENTLY — not a measurement" if moved
                   else "byte-identical" if same
                   else attempt.error or "differs from the run")
        print(f"{name:<22} {len(transports[name].calls):>3} calls  {outcome}"
              + (f"  unserved: {left}" if left else ""))
        for failure in unanswered:
            print(f"{'':<28}{failure}")
        if more:
            print(f"{'':<28}asked more: "
                  + ", ".join(f"{count} {pass_name}" for pass_name, count in more.items()))
        if moved:
            print(f"{'':<28}asked differently: {', '.join(moved)}")
        if moved or more:
            missing = not_asked_alike(
                source.calls(name),
                attempt.trace.calls if attempt.trace is not None else [])
            print(f"{'':<28}" + (f"not asked alike anywhere: {', '.join(missing)}"
                                 if missing else
                                 "every call the run asked was asked again alike"))
    print(f"\n{identical} of {len(attempts)} byte-identical to "
          f"{source.root.name}; {differently} asked differently"
          + (f"; {unhashed} calls recorded no hash, so whether they were "
             f"asked differently is unknown" if unhashed else "")
          + f"\n-> {target.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
