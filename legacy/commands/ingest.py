from whirlwind.imps import *
from .base import Command
from .tessera.tile import tesselate
from ..ui.tui import PANT
from ..experiments.config_grid import INGEST_GRID 
from ..experiments.ingest_experiment import IngestTilesExperiment 


class IngestCommand(Command):
    name = "ingest"
    scmds = {"tiles", "shards","experiment"}

    def __init__(self, logger):
        self.log = logger.child(self.name)

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:

        if not tokens:
            PANT.error("insufficient tokens for ingestion")
            return 2

        subcommand = tokens[0]
        
        if subcommand not in self.scmds:
            PANT.error(f"command not found for ingest: {subcommand}")
            return 2
        
        if subcommand == "shards":
            PANT.error("utility not yet built")
            return 2

        if subcommand == "tiles":
            return tesselate(tokens[1:],config,self.log)
        
        if subcommand == "experiment":
            in_ = tokens[1]
            exp_dir = f"../artifacts/experiments/ingest-1"
            exp = IngestTilesExperiment( files_in=in_,log=self.log,grid=INGEST_GRID,out_root=Path(exp_dir))
            exp.run()
            return 1
        

        PANT.error(f"unknown ingest subcommand: {subcommand}")
        return 2

    def help(self) -> dict[str,str]:
        tr = {
                "ingest" : "this command is for the ingesting of geodata packaged in a directory or referenced by a manifest. it is used alongside the following subcommands: ",
                "tiles" : "using ingest tiles <input csv/directory> a shardwriter tesselates the given uris into tiles of --tile-size",
                "shards": "not yet constructed",
                "mosaics": "not yet constructed",
        }
        
        return tr


