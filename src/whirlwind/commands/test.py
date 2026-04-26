
from dataclasses import dataclass
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.ui import face 
from pathlib import Path 


from whirlwind.commands.base import Command 
#from whirlwind.commands.filesystem import BuildTree, CutTree 
#from whirlwind.commands.planners.plan_tiles import TesselationPlan
#from whirlwind.commands.planners.plan_dpaths import BuildPathPlan
#from whirlwind.commands.tiles.test_tesselate import Tesselate 

from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.domain.config import Config
from whirlwind.bridges.specs.downsample import DSSpec
from whirlwind.bridges.rasterops.downsample import DownsampleBridge, Request
from whirlwind.bridges.catalogs.writeidmanifest import IDManifestBridge
from whirlwind.bridges.catalogs.discovermetadata import DiscoverMetadataBridge
from whirlwind.commands.bridge import ABridgeCommand
from whirlwind.commands.catalog.write_id_manifest import IDManifestRequestBuilder, IDManifestReporter
from whirlwind.commands.catalog.write_metadata import BuildMetadataRequest, BuildMetadataReporter 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile 
import os 

BuildIDManifestCommand = ABridgeCommand(
    name="ids",
    builder=IDManifestRequestBuilder(),
    bridge=IDManifestBridge(),
    reporter=IDManifestReporter(),
)

BuildMetadataCommand = ABridgeCommand(
    name="meta",
    builder=BuildMetadataRequest(),
    bridge=DiscoverMetadataBridge(),
    reporter=BuildMetadataReporter(),
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
                return BuildIDManifestCommand.run(tokens[1:], config)
            case "meta":
                return BuildMetadataCommand.run(tokens[1:], config)
            case "tileplan":
                ...
                #return TesselationPlan().run(tokens[1:], config)
            case "tile":
                ...
                #return Tesselate().run(tokens[1:], config)
            case "downsample":
                spec = DSSpec.from_config(config)
                request = Request(run_tree=RunTree.plant(config.out_path() / config.run_id()), 
                                            spec = spec, 
                                            overwrite = "-f" in tokens,
                                            display_range= "-d" in tokens) 

                manifest = IDManifest.from_tree(request.run_tree) 
                for p in manifest.paths():
                    f = RasterFile(p)
                    mosaic_id = f.mid 
                    branch = MosaicBranch.plant(request.run_tree.root, mosaic_id).ensure()
                    out = branch.browse_dir / f"br-{mosaic_id}.tif"
                    source = p 
                    written_out= DownsampleBridge().run(source, out, request )
                    print(f"{written_out} written") 
                return 1
            case "pathplan":
                ...
                #return BuildPathPlan().run(tokens[1:], config)
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
