from dataclasses import dataclass 
from whirlwind.commands.base import Command
from whirlwind.interfaces.geo.windows import WindowReader
from whirlwind.config.schema import Config 
from whirlwind.specs import TSpec 
from whirlwind.filetrees import RunTree, MosaicBranch, mosaicbranch
from whirlwind.manifests import IDManifest 
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from whirlwind.ui import face 
from whirlwind.interfaces.geo.windows import WindowPlan 
from whirlwind.filetrees.files import RasterFile
from whirlwind.io.planio import TilePlanIO, PlanRow 

from whirlwind.geometry.tile import EncodedTile, TileEncoder
from whirlwind.io.shards import ShardWriter, ShardRequest 

@dataclass 
class TesselateRequest:
    def __init__(self, tokens: list[str], config: Config) -> None:
        self.spec = TSpec.from_config(config) 
        self.tree = RunTree.from_config(config)
        self.manifest = IDManifest.from_tree(self.tree)
        self.paths = self.manifest.get_paths()

@dataclass 
class Tesselate(Command):
    name = "tesselate"


    def run(self, tokens: list[str], config: Config) -> int: 
        request = TesselateRequest(tokens, config) 
        for p in request.paths: 
            print(str(p))
            f = RasterFile(p)
            mosaic_id = f.mid  
            branch = MosaicBranch.plant(request.tree.root, mosaic_id).ensure()
            planio = TilePlanIO(branch, request.spec)
            encoder = TileEncoder(src=f) 
            req = ShardRequest(branch, config) 
            with ShardWriter(req) as writer:
                with WindowReader(p) as reader: 
                    for tile in reader.tiles_from_rows(planio.read_csv()): 
                        encoded = encoder.encode(tile)
                        placement = writer.write(encoded)
                        print(placement.shard_path, placement.key)
        


        return 0


