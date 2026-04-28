
import os 
from dataclasses import dataclass

from whirlwind.bridges.rasterops.downsample import DownsampleBridge
from whirlwind.bridges.catalogs.writeidmanifest import IDManifestBridge
from whirlwind.bridges.catalogs.discovermetadata import DiscoverMetadataBridge
from whirlwind.bridges.rasterops.downsample import DownsampleBridge
from whirlwind.bridges.staging.stage_damagepaths import DamagepathStagingBridge
from whirlwind.commands.base import Command 
from whirlwind.commands.bridge import Bridge 
from whirlwind.commands.builders.catalog.write_id_manifest_builders import IDManifestRequestBuilder, IDManifestReporter
from whirlwind.commands.builders.catalog.write_metadata_builders import BuildMetadataRequest, BuildMetadataReporter 
from whirlwind.commands.builders.rasters.downsample_raster import BuildDownsampleReporter, BuildDownsampleRequest
from whirlwind.commands.builders.staging.stage_damagepaths import BuildDamagePathStageReporter, BuildDamagePathStageRequest
from whirlwind.domain.config import Config

WriteIDManifestCommand = Bridge(
    name="ids",
    builder=IDManifestRequestBuilder(),
    bridge=IDManifestBridge(),
    reporter=IDManifestReporter(),
)

WriteMetadataCommand = Bridge(
    name="meta",
    builder=BuildMetadataRequest(),
    bridge=DiscoverMetadataBridge(),
    reporter=BuildMetadataReporter(),
)

DownsampleCommand = Bridge(
    name = "downsample", 
    builder = BuildDownsampleRequest(), 
    bridge= DownsampleBridge(), 
    reporter = BuildDownsampleReporter()
        )

StagePathsCommand = Bridge(
    name = "stage", 
    builder = BuildDamagePathStageRequest(), 
    bridge = DamagepathStagingBridge(), 
    reporter = BuildDamagePathStageReporter()
)

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
                return WriteMetadataCommand.run(tokens[1:], config)
            case "tileplan":
                ...
                #return TesselationPlan().run(tokens[1:], config)
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
