from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import Command
from ..utils import pathfinder as pf
from ..utils import geo
from ..utils import readwrite as rwr
from .tessera.tile import _tesselate_


class IngestCommand(Command):
    name = "ingest"
    scmds = {"tiles", "shards"}

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:
        if not tokens:
            raise ValueError("ingest requires a subcommand")

        subcommand = tokens[0]
        
        if subcommand not in self.scmds:
            print(f"command not found for ingest: {subcommand}")
        
        if subcommand == "tiles":
            return _tesselate_(tokens[1:],config)

        if subcommand == "shards":
            raise ValueError("not yet built")
            return 0

        raise ValueError(f"unknown ingest subcommand: {subcommand}")

