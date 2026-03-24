from whirlwind.imps import *
from .base import Command
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
            return _tesselate_(tokens[1:],config,self.log)


        self.ui.error(f"unknown ingest subcommand: {subcommand}")
        return 2

    def help(self) -> dict[str,str]:
        tr = {
                "ingest" : "this command is for the ingesting of geodata packaged in a directory or referenced by a manifest. it is used alongside the following subcommands: ",
                "tiles" : "using ingest tiles <input csv/directory> a shardwriter tesselates the given uris into tiles of --tile-size",
                "shards": "not yet constructed",
                "mosaics": "not yet constructed",
        }
        
        return tr


