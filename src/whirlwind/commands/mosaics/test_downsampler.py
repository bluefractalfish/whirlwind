
from dataclasses import dataclass 
from whirlwind.commands.base import Command
from whirlwind.interfaces.geo.windows import WindowReader
from whirlwind.config.schema import Config 
from whirlwind.specs import DSSpec 
from whirlwind.filetrees import RunTree, MosaicBranch, mosaicbranch
from whirlwind.manifests import IDManifest 
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from whirlwind.ui import face 
from whirlwind.interfaces.geo.downsample import Downsampler
from whirlwind.filetrees.files import RasterFile
from whirlwind.io.planio import TilePlanIO, PlanRow 

from whirlwind.geometry.tile import EncodedTile, TileEncoder
from whirlwind.io.shards import ShardWriter, ShardRequest 

@dataclass
class DownsampleRequest:
    def __init__(self, tokens: list[str], config: Config) -> None: 
        self.spec = DSSpec.from_config(config)
        self.tree = RunTree.from_config(config)
        self.manifest = IDManifest.from_tree(self.tree)
        self.paths  = self.manifest.get_paths()

class Downsample(Command):
    name = "downsample "

    def run(self, tokens: list[str], config: Config) -> int:
        request = DownsampleRequest(tokens, config) 
        for p in request.paths: 
            f = RasterFile(p) 
            mosaic_id = f.mid 
            branch = MosaicBranch.plant(request.tree.root, mosaic_id).ensure() 
            source = p 
            out_uri = branch.browse_dir / f"Br-{mosaic_id}"

            downsampler = Downsampler(p, out_uri, request.spec) 
            downsampler.run()
            print(mosaic_id)

