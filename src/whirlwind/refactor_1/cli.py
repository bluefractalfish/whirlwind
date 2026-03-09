from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

from .app import _build_

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")

def normalize_keys(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            str(key).replace("-","_"): normalize_keys(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [normalize_keys(item) for item in data]
    return data

def load_config(path_str: str | None) -> dict[str, Any]:
    if not path_str:
        return {}
    path = Path(path_str).expanduser().resolve()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a top level map")
    return normalize_keys(data)

def extract_command_path(args: argparse.Namespace) -> list[str]:
    path: list[str] = []
    cmd = getattr(args, "cmd", None)
    if cmd:
        path.append(cmd)
    # sub commands for ingestion
    ingest_cmd = getattr(args, "ingest_cmd",None)
    if ingest_cmd:
        path.append(ingest_cmd)
    return path

def merge_config(config: dict[str, Any], path: list[str]) -> dict[str, Any]:
    merged = dict[str, Any] = {}

    global_conf = config.get("global", {})
    if isinstance(global_conf, dict):
        merged.update(global_conf)
    current: Any = config 
    for index, part in enumerate(path):
        if not isinstance(current, dict):
            break
        current = current.get(part, {})
        if not isinstance(current, dict):
            break
        is_last = index == len(path) -1
        if is_last:
            for key, value in current.items():
                if key != "global":
                    merged[key] = value
        else:
            nested_global = current.get("global", {})
            if isinstance(nested_global, dict):
                merged.update(nested_global)
        return merged

def build_parser() -> argparse.ArgumentParser:
    app = _build_()

    parser = argparse.ArgumentParser(prog="whirlwind")
    parse.add_argument(
            "--config", type=str, default="config.yaml",
            help="path to yaml config, default config.yaml"
            )
    subparser = parser.add_subparser(des="cmd", required = True)

    for command in app.commands:
        command.configure(subparser)
    return parser

def parser_args(argv: Optional[Sequence[str]]==None) -> argparse.Namespace:
    parser = build_parser()
    # parse first pass: discover --config and command path
    primal_args, _ = parser.parse_known_args(argv)
    config = load_config(getattr(primal_args, "config",None))
    command_path = extract_command_path(primal_args)
    defaults = merge_config(config, command_path)
    if defaults:
        parser.set_defaults(**defaults)
    # parse second pass: apply config defaults, then cli flags win
    return parser.parse_args(argv)

def main(argv: Optional[Sequence[str]]=None) -> int:
    args = parse_args(argv)
    app = _build_()
    return app.run(args)

if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))

