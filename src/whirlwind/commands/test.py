
from dataclasses import dataclass
from whirlwind.ui import face 
from whirlwind.commands.base import Command 
from whirlwind.config import Config

from whirlwind.commands.catalog import BuildMetadataManifests, BuildIDManifest, BuildMosaicBranches 
from whirlwind.commands.filesystem import BuildTree, CutTree 
from whirlwind.commands.planners.plan_tiles import TesselationPlan
import os 

#from whirlwind.commands.mosaic import ShardMosaicCommand 
@dataclass
class Test(Command):
    name = "test"

    def run(self, tokens: list[str], config: Config) -> int:
        if len(tokens) == 0:
            return 1
        match tokens[0]:
            case "ids":
                return BuildIDManifest().run(tokens[1:], config)
            case "meta":
                return BuildMetadataManifests().run(tokens[1:], config)
            case "branch":
                return BuildMosaicBranches().run(tokens[1:], config)
            case "buildtree":
                return BuildTree().run(tokens[1:], config)
            case "deletetree":
                return CutTree().run(tokens[1:], config)
            case "tileplan":
                return TesselationPlan().run(tokens[1:], config)
            case _:
                print("nope?")
                pass
                return 3
    

class RestartShell:
    names = ["restart","r"]

    def run(self, tokens) -> int:
        """replace current instance of app with new instance """ 
        try:
            os.execvp("W", ["W"])
        except:
            return 1
    def help(self) -> dict[str,str]:
        return {"restart":"restart current instance by replacing with new one"} 

class QuitShell:
    names = ["quit","q"]

    def run(self, tokens,) -> int:
        ln = input("are you sure you want to quit? (y/n) ")
        if ln != "n":
            return 13 
        else:
            return 0

    def help(self) -> dict[str,str]:
        return {"quit":"safely quit shell"}
