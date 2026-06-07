
import numpy as np 
from pathlib import Path 
from dataclasses import dataclass, replace 
from typing import Any 

from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.adapters.io.windowplan_io import WindowPlanCSV 
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.io.shard_manifest import make_sink  
from whirlwind.adapters.io.write_shards import ( 
                ShardWriter, WriteShardRequest, BinSplitShardWriter
            )
from whirlwind.adapters.label.binary_label_by_intersection import BinaryLabelByIntersection
from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.domain.tile import ( 
            TileEncoder, tile_content_stats, attach_content_stats
                    )
from whirlwind.filesystem.files import RasterFile 
from whirlwind.filesystem.runtree import RunTree



@dataclass(frozen=True)
class TileSummary: 
    code: int # 3 gpkg doesnt exist/empty, 5 no manifest, 7 no plan, 35 no man no plan, 
    n_tiles: int=0


class TileRasterFromPlan:
    def __init__(self, 
                 p: Path | str, 
                 tree: RunTree, 
                 manifest_name: str, 
                 manifest: IDManifest,
                 manifest_kind: str, 
                 plan_name: str, 
                 shard_prefix: str, 
                 shard_size: int, 
                 masked: bool, 
                 fill_value: float, 
                 dry: bool, 
                 keep_empty: bool
                 ) -> None: 
        self.p = p 
        self.code = 0 
        f = RasterFile(p)
        self.encoder = TileEncoder(src=f)

        branch = tree.branchlook(manifest,p)
        self.dry = dry 
        self.keep_empty=keep_empty
        self.shard_dir = branch.shards_dir
        self.shard_prefix = shard_prefix 
        self.shard_size = shard_size 
        self.masked = masked 
        self.fill_value = fill_value
        self.manifest_path = branch.manifest_dir/manifest_name 
        self.manifest_kind = manifest_kind
        self.tile_plan_path = branch.staging_dir/plan_name

        self.branch = branch
        if not self.tile_plan_path.is_file() or not self.tile_plan_path.exists():
            raise FileNotFoundError

    def build_sinks(self) -> int:
        return_code = 1 
        try:  
            self.manifest_sink=make_sink(self.manifest_kind, self.manifest_path)
        except ValueError:
            return_code =  5 # cannot make manifest  
        try: 
            self.plan_sink = WindowPlanCSV(self.tile_plan_path)
        except FileNotFoundError: 
            return_code = return_code*7 # tile plan cannot be found or isnt written 
        # return_code == 1 -> no errors, sinks exist 
        # return_code == 5 -> manifest_sink couldnt be made, plan_sink could 
        # return_code == 35 -> neither could be made, skip raster 

        return return_code  

    def make_shard_request(self) -> None: 
        # create shard request from request configuration and this mosaics shard_dir
        self.req = WriteShardRequest.from_path(
                        out_path=self.shard_dir, 
                        prefix=self.shard_prefix, 
                        size=self.shard_size,) 

    def tile(self, min_content_fraction: float, zero_is_empty: bool) -> TileSummary:
        planned_windows = self.plan_sink.read() 
        with ShardWriter(self.req) as writer:
            with RasterioWindowReader(
                    self.p, self.masked, self.fill_value
                    ) as reader: 
                n_tiles = 0 

                for tile in reader.tiles_from_rows(planned_windows):
                    # get tile stats to determine content amounts 
                    stats = tile_content_stats(
                        tile,
                        min_content_fraction=min_content_fraction,
                        zero_is_empty=zero_is_empty,
                        )

                    if stats.mostly_empty and not self.keep_empty: 
                        continue
                     
                    tile = attach_content_stats(tile, stats)
                    encoded = self.encoder.encode(tile)

                    if self.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}") 
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)

                    self.manifest_sink.write(row)
        
        return TileSummary(code=0,n_tiles=n_tiles)
    
    def tile_by_intersection(self, geometry_name, gpkg_path) -> TileSummary: 
        planned_windows = self.plan_sink.read() 
        gpkg_path = self.branch.browse_dir / gpkg_path
        with BinSplitShardWriter(self.req, split_on=geometry_name) as writer:
            with RasterioWindowReader(
                    self.p, masked=self.masked, fill=self.fill_value
                    ) as reader: 
                if not gpkg_path.exists():
                    return TileSummary(code=3)
                labeler = BinaryLabelByIntersection.from_gpkg(
                            gpkg_path=gpkg_path,
                            area_layer=f"{geometry_name}_area",
                            line_layer=f"{geometry_name}_center_line",
                            target_crs=reader.ds.crs )
                n_tiles = 0  
                for tile in reader.tiles_from_rows(planned_windows): 
                    tile = labeler.label(tile)
                    encoded = self.encoder.encode(tile)
                    if self.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}")
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)
                    self.manifest_sink.write(row)

        return TileSummary(code=0,n_tiles=n_tiles)

