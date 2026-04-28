
import os 
from dataclasses import dataclass


from whirlwind.commands.base import Command 
from whirlwind.domain.config import Config


## commands 
from whirlwind.commands.builders.downsample_cmd import DownsampleCommand 
from whirlwind.commands.builders.write_id_manifest_cmd import WriteIDManifestCommand
from whirlwind.commands.builders.discover_metadata_cmd import DiscoverMetadataCommand
from whirlwind.commands.builders.stage_damagepaths_cmd import StagePathsCommand 
from whirlwind.commands.builders.stage_tesselation_cmd import StageTesselationCommand

#from whirlwind.commands.mosaic import ShardMosaicCommand 
@dataclass
class Test(Command):
    name = "test"

    def run(self, tokens: list[str], config: Config) -> int:
        if len(tokens) == 0:
            return 1
        match tokens[0]:
            case "ids":
                return WriteIDManifestCommand.run(tokens[1:], config)
            case "meta":
                return DiscoverMetadataCommand.run(tokens[1:], config)
            case "tileplan":
                return StageTesselationCommand.run(tokens[1:], config)
            case "tile":
                ...
                #return Tesselate().run(tokens[1:], config)
            case "downsample":
                return DownsampleCommand.run(tokens[1:], config)
            case "pathplan":
                return StagePathsCommand.run(tokens[1:], config)
            case _:
                print("nope?")
                pass
                return 3
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
