""" whirlwind.cli 


    PURPOSE: 
        - entrypoint for whirlwind cli 

    BEHAVIOR:
        - parse cli arguments 
        - load yaml config from disk 
        - bootstrap app + shell 

    PUBLIC:
        - main(argv=None) -> int 
"""

from __future__ import annotations

import argparse 
import sys 
from pathlib import Path 
from typing import Any, Dict, Optional

import yaml 
from rich.traceback import install 

from whirlwind.config import build_config 
from whirlwind.core.app import build_app 
from whirlwind.core.shell import WShell 
from whirlwind.core.state import STATE 
from whirlwind.tools.logger import Logger 
from whirlwind.tools.pathfinder import find_home_ 
from whirlwind.ui import face 

install(show_locals=True)

def load_yaml(path_str: str) -> Dict[str,Any]: 
    path = Path(path_str).expanduser().resolve()
    with path.open("r",encoding="utf-8") as f: 
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("config file must contain top level mapping")
    return data 

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( 
                        "--config",
                        type=str,
                        default="config.yaml",
                        help="path to yaml config. defaults to config.yaml"
                    )
    return parser 


def main(argv: Optional[list[str]] = None) -> int:
    config_path = find_home_()/build_parser().parse_args(argv).config
    raw = load_yaml(config_path)
    config = build_config(raw)

    lp = config.get("global",{}).get("log")
    log = Logger(lp) 

    app = build_app(log) 
    shell = WShell(app, config) 
    return shell.run() 

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


