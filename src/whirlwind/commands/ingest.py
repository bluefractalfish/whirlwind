from __future__ import annotations

from typing import Any

from .base import Command
from ..utils import geo
from .tessera.tile import _tesselate_
from ..ui.tui import TUI


class IngestCommand(Command):
    name = "ingest"
    scmds = {"tiles", "shards"}

    def __init__(self, logger):
        self.log = logger.child(self.name)
        self.ui = TUI()

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:

        if not tokens:
            self.ui.print(tokens)
            self.ui.error("insufficient tokens for ingestion")
            return 2

        subcommand = tokens[0]
        
        if subcommand not in self.scmds:
            self.ui.error(f"command not found for ingest: {subcommand}")
            return 2
        
        if subcommand == "shards":
            self.ui.error("utility not yet built")
            return 2

        if subcommand == "tiles":
            self.ui.info("trying to tesselate")
            return _tesselate_(tokens[1:],config,self.log)


        self.ui.error(f"unknown ingest subcommand: {subcommand}")
        return 2

