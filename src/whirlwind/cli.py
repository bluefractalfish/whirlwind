from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

from .core.app import _build
from .utils import configure as conf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( "--config", type=str, default="config.yaml",
        help="path to yaml config, default config.yaml",)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = _build()
    config = conf.load_(args.config)

    while True:
        try:
            line = input("W: ").strip()
        except EOFError:
            return 0
        except KeyboardInterrupt:
            continue

        if not line:
            continue

        if line in {"quit", "exit"}:
            return 0

        if line == "reload":
            config = load_config(args.config)
            print("reloaded")
            continue

        if line == "help":
            print("commands: inspect, ingest tiles, reload, quit")
            continue

        try:
            tokens = shlex.split(line)
            app.run(tokens, config)
        except Exception as exc:
            print(f"error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
