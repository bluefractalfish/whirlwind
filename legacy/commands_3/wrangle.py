
from .base import Command
from typing import Dict, Any, Optional 
from whirlwind.wrangler.runner import WrangleDownsampleRunner 
from whirlwind.core.interfaces import LoggerProtocol, NullLogger 
from whirlwind.io.metadata import source_inspection_metadata 
from whirlwind.ui import face

class WrangleCommand(Command):
    name = "wrangle"
    subcmds = {"downsample","ds", "mosaics","m", "tiles","t", "shards","s", "experimental","e"}

    def __init__(self, logger: LoggerProtocol | None=None) -> None: 
        self.log = logger 

    def run(self, tokens: list[str], config: Dict[str,Any]) -> int: 

        if not tokens:
            return 2

        subcommand = tokens[0]
        
        if subcommand not in self.subcmds:
            face.error(f"wrangle usage: {subcommand} not a valid command for wrangler")
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
            if subcommand == "downsample" or subcommand == "ds":
                # if no source is given default to run_id/metadata/*.csv
                if len(tokens)==1:
                    src = source_inspection_metadata(config)
                    if src == "":
                        print("usage: wrangle ds expects input. run ingest first if you want to default to manifest")
                        return 3
                    tokens.append(src)
                source = tokens[1] 
                runner = WrangleDownsampleRunner.from_config(source, config, log=self.log)
                a = runner.run(make_gpkg=True) 
                return 2


            if subcommand == "experimental":
                """
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
                    """
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
