
from pathlib import Path 
from dataclasses import dataclass, replace 

from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.adapters.io.windowplan_io import WindowPlanCSV 
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.io.shard_manifest import make_sink  
from whirlwind.adapters.io.write_shards import ( 

                ShardWriter, WriteShardRequest, BinSplitShardWriter, RoutedShardWriter
            )
from whirlwind.adapters.io.label_metadata import (
        make_label_metadata_sink, 
        make_review_sink, 
        write_label_sidecar
        )
from whirlwind.adapters.label.label_protocol import Labeler
from whirlwind.adapters.label.binary_label_by_intersection import LabelByIntersection
from whirlwind.adapters.label.null_labeler import UnaryLabeler
from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.domain.tile import ( 
            TileEncoder, tile_content_stats
                    ) 
from whirlwind.bridges.specs.semclass import SCSpec
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
                 keep_empty: bool,  
                 min_content_fraction: float, 
                 zero_is_empty: bool, 
                 labeler: Labeler | None = None
                 ) -> None: 
        self.p = p 
        self.code = 0 
        self.labeler = labeler or UnaryLabeler()
        f = RasterFile(p)
        self.encoder = TileEncoder(src=f)
        
        branch = tree.branchlook(manifest,p)
        self.dry = dry 
        self.keep_empty=keep_empty
        self.min_content_fraction = min_content_fraction 
        self.zero_is_empty=zero_is_empty
        self.shard_dir = branch.shards_dir
        self.shard_prefix = shard_prefix 
        self.shard_size = shard_size 
        self.masked = masked 
        self.fill_value = fill_value

        self.manifest_path = branch.manifest_dir/manifest_name 
        self.label_metadata_path = branch.metadata_dir / "label_metadata.csv"
        self.review_path = branch.metadata_dir / "review.csv"

        self.manifest_kind = manifest_kind
        self.tile_plan_path = branch.staging_dir/plan_name

        self.branch = branch
        if not self.tile_plan_path.is_file() or not self.tile_plan_path.exists():
            raise FileNotFoundError

    def build_sinks(self) -> int:
        return_code = 1 
        try:  
            self.manifest_sink = make_sink(self.manifest_kind, self.manifest_path)
            self.label_metadata_sink = make_label_metadata_sink(self.label_metadata_path)
            self.review_sink = make_review_sink(self.review_path)

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


    
    def run(self, progress=None, task_id=None) -> TileSummary: 
        tiles_to_process = self.plan_sink.count()
        planned_windows = self.plan_sink.read()
        try:
            with RoutedShardWriter(self.req) as writer: 
                with RasterioWindowReader(
                        self.p, self.masked, self.fill_value
                        ) as reader:  

                    n_tiles = 0  
                    n_written = 0 
                    n_skipped = 0 

                    for tile in reader.tiles_from_rows(planned_windows):
                        n_tiles += 1 

                        if progress is not None and task_id is not None: 
                            progress.update(
                                    task_id, 
                                    description=(
                                        f"tiling {Path(self.p).name}\n"
                                        f"tile={n_tiles}/{tiles_to_process}\n"
                                        f"written={n_written}\n"
                                        f"skipped={n_skipped}\n"
                                        )
                                    )
                        if not self.keep_empty: 
                            stats = tile_content_stats(
                                    tile, 
                                    min_content_fraction=self.min_content_fraction, 
                                    zero_is_empty=self.zero_is_empty)
                            if stats.mostly_empty: 
                                n_skipped += 1 
                                if progress is not None and task_id is not None:
                                    progress.advance(task_id, 1)
                                continue 
                        label = self.labeler.label(tile)
                        encoded = self.encoder.encode(tile,label)
                        if self.dry:
                            shard_path = f"dry_{tile.tile_id}"
                        else:
                            placement = writer.write(encoded)
                            shard_path = placement.shard_path
                            n_written += 1 

                        row = encoded.as_manifest_row(shard_path)

                        # main tile manifest 
                        self.manifest_sink.write(row)
        
                        # label metadata: 
                        #   - real class tile -> label_metadata 
                        #   - review/unknown -> review.csv
                        write_label_sidecar(
                                encoded=encoded, 
                                shard=shard_path, 
                                label_sink=self.label_metadata_sink, 
                                review_sink=self.review_sink
                                )
                        if progress is not None and task_id is not None:
                            progress.advance(task_id, 1)

            return TileSummary(code=0, n_tiles=n_tiles)

        finally: 
            self.manifest_sink.close()
            self.label_metadata_sink.close()
            self.review_sink.close()



    def tile(self) -> TileSummary:
        planned_windows = self.plan_sink.read() 
        with ShardWriter(self.req) as writer:
            with RasterioWindowReader(
                    self.p, self.masked, self.fill_value
                    ) as reader:  

                labeler = UnaryLabeler()
                n_tiles = 0 

                for tile in reader.tiles_from_rows(planned_windows):
                    # get tile stats to determine content amounts 
                    stats = tile_content_stats(
                        tile,
                        min_content_fraction=self.min_content_fraction,
                        zero_is_empty=self.zero_is_empty,
                        )

                    if stats.mostly_empty and not self.keep_empty: 
                        continue
                    
                    label = labeler.label(tile)
                    encoded = self.encoder.encode(tile, label)

                    if self.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}") 
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.shard_path)

                    self.manifest_sink.write(row)
        
        return TileSummary(code=0,n_tiles=n_tiles)
    
    def tile_by_intersection(self, geometry_name, gpkg_path) -> TileSummary: 

        planned_windows = self.plan_sink.read() 
        #
        gpkg_path = self.branch.browse_dir / gpkg_path
        
        with BinSplitShardWriter(self.req, split_on=geometry_name) as writer:
            with RasterioWindowReader(
                    self.p, masked=self.masked, fill=self.fill_value
                    ) as reader: 
        
                if not gpkg_path.exists():
                    return TileSummary(code=3)

                labeler = LabelByIntersection.from_gpkg(
                            gpkg_path=gpkg_path, 
                            geometry_name=geometry_name,
                            area_layer=f"{geometry_name}_area",
                            line_layer=f"{geometry_name}_line",
                            target_crs=reader.ds.crs )
                n_tiles = 0  
                for tile in reader.tiles_from_rows(planned_windows): 
                    label = labeler.label(tile)
                    encoded = self.encoder.encode(tile, label)
                    if self.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}")
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.shard_path)
                    self.manifest_sink.write(row)

        return TileSummary(code=0,n_tiles=n_tiles)
    
    def tile_by_bucket(self, spec: SCSpec) -> TileSummary:
        ...
