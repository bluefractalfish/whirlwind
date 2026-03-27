""" whirlwind.commands.ingest 
    
    PURPOSE:
        - `ingest` command family: (mosaics (legacy tiles), shards)

    BEHAVIOR:
        - validate tokens and select subcommand 
        - delegate to ingest pipeline in whirlwind.ingest 
        - print conside human output for interactive use 
    PUBLIC:
        - IngestCommand 

"""

from __future__ import annotations 

from pathlib import Path 
from typing import Any, Dict 

from whirlwind.commands.base import Command 
from whirlwind.core.interfaces import LoggerProtocol, NullLogger 
from whirlwind.ingest.runner import IngestMosaicsRunner


class IngestCommand(Command):
    name = "ingest"
    subcmds = {"mosaics", "tiles", "shards", "experiment"}

    def __init__(self, logger: LoggerProtocol | None=None) -> None: 
        self.log = logger 

    def run(self, tokens: list[str], config: Dict[str,Any]) -> int: 

        if not tokens:
            return 2

        subcommand = tokens[0]
        
        if subcommand not in self.subcmds:
            return 2
        
        if subcommand == "shards":
            print("utility not yet built")
            #source = tokens[1] 
            #runner = IngestShardsRunner.from_config(source, config, log=self.log)
            #rows = runner.run()
            return 2

        if subcommand == "tiles":
            if len(tokens) != 2:
                print("usage: tiles expects input")
            source = tokens[1] 
            #runner = IngestTilesRunner.from_config(source, config, log=self.log)
            #rows = runner.run()
        if subcommand == "mosaics":
            if len(tokens) != 2:
                print("usage: mosaics expects input")
                return 2
            source = tokens[1] 
            runner = IngestMosaicsRunner.from_config(source, config, log=self.log)
            rows = runner.run() 

            for r in rows: 
                print(f"{r['mosaic_id']}")

        if subcommand == "experiment":
            in_ = tokens[1]
            #exp_dir = f"../artifacts/experiments/ingest-1"
            #exp = IngestTilesExperiment( files_in=in_,log=self.log,grid=INGEST_GRID,out_root=Path(exp_dir))
            #exp.run()
            return 1
        
        print("unknown command ")
        return 2
    
    def help(self) -> dict[str, str]:
        return { 
                "ingest": "Ingest "
                }
