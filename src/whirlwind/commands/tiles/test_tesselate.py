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
from whirlwind.io.shards import ShardWriter, ShardRequest, SplitShardWriter
from whirlwind.io.manifests import CSVSink, make_sink, ManifestRow, manifest_row_from_encoded
from whirlwind.interfaces.label.damage_labels import DamageLabeler 
manifest_fieldnames = list(ManifestRow.__dataclass_fields__.keys())


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
            man_path = branch.manifest_dir/"tile_manifest"
            sink = make_sink( "csv", man_path, fieldnames=manifest_fieldnames)
            req = ShardRequest(branch, config) 
            with SplitShardWriter(req) as writer:
                with WindowReader(p) as reader: 
                    labeler = DamageLabeler.from_gpkg(
                                gpkg_path=branch.browse_dir/"damaged_geometry.gpkg",
                                area_layer="damage_area",
                                line_layer="damage_path",
                                target_crs=reader.ds.crs )
                    
                    for tile in reader.tiles_from_rows(planio.read_csv()): 
                        tile = labeler.label(tile)
                        encoded = encoder.encode(tile)
                        placement = writer.write(encoded)
                        row = manifest_row_from_encoded(encoded, placement.key)
                        sink.write(row)
                        print(placement.shard_path, placement.key)
        

        return 0


