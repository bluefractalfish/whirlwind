from __future__ import annotations

import argparse
import shlex
import sys

from .core.app import _build
from .utils import configure as confio
from .utils.logger import Logger
from .utils.pathfinder import _find_home_
from .ui.tui import TUI
from .core.shell import WShell


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( "--config", type=str, default="config.yaml",
        help="path to yaml config, default config.yaml",)
    return parser

def main(argv: list[str] | None = None) -> int:
    ui = TUI()
    args = build_parser().parse_args(argv)
    ui.info(f"sourcing configuration from {args.config}...")
    config = confio.load_(args.config) 
    ui.success(f"configuration loaded")
    log = Logger(_find_home_()/"logs"/"wind.jsonl")
    app = _build(log)  
    shell = WShell(app,config,log) 
    return shell._run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
