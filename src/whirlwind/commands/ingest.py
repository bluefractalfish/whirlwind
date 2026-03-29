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
from rich.traceback import install 

from whirlwind.commands.base import Command 
from whirlwind.core.interfaces import LoggerProtocol, NullLogger 
from whirlwind.io.out import append_jsonl
from whirlwind.ingest.config import experiment_overrides
from whirlwind.ingest.runner import IngestMosaicsRunner
from whirlwind.lab.ingest_experiment import list_configs 

install(show_locals=True)

class IngestCommand(Command):
    name = "ingest"
    subcmds = {"mosaics", "tiles", "shards", "experimental"}

    def __init__(self, logger: LoggerProtocol | None=None) -> None: 
        self.log = logger 

    def run(self, tokens: list[str], config: Dict[str,Any]) -> int: 

        if not tokens:
            return 2

        subcommand = tokens[0]
        
        if subcommand not in self.subcmds:
            return 2

        try: 
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
                summary, overview = runner.run() 
                print(summary)
                print(overview)
                return 2


            if subcommand == "experimental":
                source = tokens[1]
                summaries = []
                overviews = []
                configs = list_configs()
                print(f"iterating through {len(configs)}")
                
                for cfg in configs:
                    permuted_cfg = experiment_overrides(cfg)
                    runner = IngestMosaicsRunner.from_config(source, permuted_cfg, log=self.log)
                    summary, overview = runner.run()
                    summaries.append(summary)
                    overviews.append(overview)
                    append_jsonl(overview, "experiment-overviews")
                    append_jsonl(summary, "experiment-summaries")
                return 1
            else:
                print("whstt")

        except Exception as e:
            
            raise e
        print("unknown command ")
        return 2
    
    def help(self) -> dict[str, str]:
        return { 
                "ingest": "Ingest "
                }
