"""Thin wrapper over the library. Argument parsing and file IO, nothing else."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config
from .ir import Document
from .orchestrator import convert
from .render import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doc-to-html")
    sub = parser.add_subparsers(dest="command", required=True)

    convert_cmd = sub.add_parser("convert", help="convert one image to HTML")
    convert_cmd.add_argument("image", type=Path)
    convert_cmd.add_argument("-o", "--out", type=Path, required=True)
    convert_cmd.add_argument(
        "--review",
        action="store_true",
        help="stop at Checkpoints to ask; without it the run is unattended",
    )

    render_cmd = sub.add_parser(
        "render", help="render an IR JSON file to HTML, without reading any image"
    )
    render_cmd.add_argument("ir", type=Path)
    render_cmd.add_argument("-o", "--out", type=Path, required=True)

    sub.add_parser(
        "config", help="print the resolved settings and where each came from"
    )

    args = parser.parse_args(argv)
    config.configure_logging(config.load())

    if args.command == "config":
        for line in config.describe(config.load()):
            print(line)
        return 0

    if args.command == "render":
        document = Document.from_json(args.ir.read_text())
        args.out.write_text(render(document))
        print(f"wrote {args.out}", file=sys.stderr)
        return 0

    if args.review:
        print("interactive review is not yet wired", file=sys.stderr)
        return 2

    started = time.perf_counter()
    document = convert(args.image)
    args.out.write_text(render(document))

    # How long it took is part of the answer: an operator with a stack of
    # documents needs to know whether this is practical before starting.
    elapsed = time.perf_counter() - started
    zones = len(document.zones)
    unread = len(document.failures)
    print(
        f"wrote {args.out} — {zones} Zones in {elapsed:.1f}s"
        + (f", {unread} could not be read" if unread else ""),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
