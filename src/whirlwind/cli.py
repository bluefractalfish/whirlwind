from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

from .core.app import _build


def normalize_keys(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            str(key).replace("-", "_"): normalize_keys(value)
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
        raise ValueError("config file must contain a top level map")
    return normalize_keys(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="path to yaml config, default config.yaml",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = _build()
    config = load_config(args.config)

    while True:
        try:
            line = input("W: ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
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
