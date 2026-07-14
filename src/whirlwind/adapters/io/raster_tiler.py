
from pathlib import Path 
from dataclasses import dataclass, replace 

from rasterio.enums import Resampling

from whirlwind.adapters.io.windowplan_io import WindowPlanCSV 
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.io.shard_manifest import make_sink  
from whirlwind.adapters.io.write_shards import ( 
                ShardWriter, WriteShardRequest, BinSplitShardWriter, RoutedShardWriter
            )

from whirlwind.domain.mosaic import MosaicRecord
from whirlwind.adapters.io.label_metadata import (
    write_label_json_row,
    make_review_sink,
    make_label_json_sink,
    write_review_sidecar,
)
from whirlwind.adapters.label.label_protocol import Labeler
from whirlwind.adapters.label.null_labeler import UnaryLabeler
from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.domain.tile import TileEncoder, CanonicalTileEncoder
from whirlwind.adapters.display.filters import should_skip_tile
                
from whirlwind.filesystem.files import RasterFile 
from whirlwind.filesystem.runtree import RunTree

def _record_for_path(  manifest: IDManifest, path: str | Path) -> "MosaicRecord":
    target = Path(path).expanduser().resolve()

    for record in manifest.records():
        if record.path.expanduser().resolve() == target:
            return record

    raise ValueError(
        f"mosaic path not found in manifest: {target}"
    ) 

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
                 min_content_fraction: float, 
                 zero_is_empty: bool, 
                 route_shard_by_label: bool = False, 
                 labeler: Labeler | None = None, 
                 overwrite: bool = False, 
                 skip_empty: bool = False 
                 ) -> None: 
        self.p = Path(p).expanduser().resolve()

        source_file = RasterFile(self.p)
        record = _record_for_path(
            manifest,
            self.p,
        )

        if not record.branch_id:
            raise ValueError(
                f"{record.mosaic_id} has no spatial branch"
            )

        records_by_id = {
            current.mosaic_id: current
            for current in manifest.records()
        }

        canonical_id = (
            record.canonical_mosaic_id
            or record.mosaic_id
        )

        canonical_record = records_by_id.get(
            canonical_id
        )

        if canonical_record is None:
            raise ValueError(
                f"canonical mosaic is missing: {canonical_id}"
            )

        self.code = 0
        self.labeler = labeler or UnaryLabeler()

        self.encoder = CanonicalTileEncoder(
            src=source_file,
            branch_id=record.branch_id,
        )

        self.record = record
        self.canonical_path = canonical_record.path
        self.skip_empty = skip_empty

        categorical_variants = {
            "MASK",
            "LABEL",
            "CLASS",
            "CLASSES",
            "SEGMENTATION",
            "CATEGORICAL",
        }

        variant_name = (
            record.variant_type
            or record.variant_id
            or ""
        ).upper()

        self.resampling = (
            Resampling.nearest
            if variant_name in categorical_variants
            else Resampling.bilinear
        )

        branch = tree.branch_for(record).ensure()
        spatial_branch = (
            tree.spatial_branch_for(record).ensure()
        )

        self.dry = dry
        self.overwrite = overwrite
        self.min_content_fraction = min_content_fraction
        self.zero_is_empty = zero_is_empty
        self.shard_dir = branch.shards_dir
        self.shard_prefix = shard_prefix
        self.shard_size = shard_size
        self.masked = masked
        self.fill_value = fill_value
        self.route_shard_by_label = route_shard_by_label
        self.manifest_kind = manifest_kind
        self.manifest_path = (
            branch.manifest_dir / manifest_name
        )
        self.label_metadata_path = (
            branch.metadata_dir
            / "label_metadata.csv"
        ) 

        self.review_path = (
            branch.metadata_dir
            / "shard_metadata.csv"
        )

        self.tile_plan_path = (
            spatial_branch.tile_plan_path(
                plan_name
            )
        )

        self.branch = branch
        self.spatial_branch = spatial_branch

        if not self.tile_plan_path.is_file() or not self.tile_plan_path.exists():
            raise FileNotFoundError

    def build_sinks(self) -> int:
        return_code = 1

        if self.overwrite:
            for path in (
                self.manifest_path,
                self.label_metadata_path,
                self.review_path,
            ):
                if path is not None and path.exists():
                    path.unlink()

        try:
            self.manifest_sink = make_sink(self.manifest_kind, self.manifest_path)
            self.label_metadata_sink = make_label_json_sink(self.label_metadata_path)
            self.review_sink = make_review_sink(self.review_path)

        except ValueError:
            return_code = 5

        try:
            self.plan_sink = WindowPlanCSV(self.tile_plan_path)
        except FileNotFoundError:
            return_code = return_code * 7

        return return_code

    def make_shard_request(self) -> None: 
        # create shard request from request configuration and this mosaics shard_dir
        self.req = WriteShardRequest.from_path(
                        out_path=self.shard_dir, 
                        prefix=self.shard_prefix, 
                        size=self.shard_size,) 


    
    def run(self, tile_limit: int | None = None, progress=None, task_id=None) -> TileSummary: 
        tiles_to_process = self.plan_sink.count()
        planned_windows = self.plan_sink.read()
        try:
            # routes shards into <bucket> if route_shards_by label is true 
            writer_class = RoutedShardWriter if self.route_shard_by_label else ShardWriter

            with writer_class(self.req) as writer: 
                with RasterioWindowReader(
                        self.p, 
                        self.masked,
                        self.fill_value, 
                        canonical_path=self.canonical_path, 
                        resampling=self.resampling
                        ) as reader:  

                    n_tiles = 0  
                    n_written = 0 
                    n_skipped = 0 

                    for tile in reader.tiles_from_rows(planned_windows):

                        n_tiles += 1 

                        if tile_limit is not None and n_tiles >= tile_limit: 
                            break

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
                        if self.skip_empty:
                            skip = should_skip_tile(
                                tile,
                                min_content_fraction=(
                                    self.min_content_fraction
                                ),
                                zero_is_empty=self.zero_is_empty,
                            )

                            if skip.skip:
                                n_skipped += 1

                                if (
                                    progress is not None
                                    and task_id is not None
                                ):
                                    progress.advance(task_id, 1)

                                continue
                        

                        encoded = self.encoder.encode(tile)

                        placement = None 

                        if self.dry:
                            shard_path = f"dry_{tile.tile_id}"
                        else:
                            placement = writer.write(encoded)
                            shard_path = placement.shard_path
                            n_written += 1 

                        row = encoded.as_manifest_row(
                            shard_path,
                            shard_uri=placement.shard_uri if placement else None,
                            tile_uri=placement.tile_uri if placement else None,
                            tile_json_uri=placement.tile_json_uri if placement else None,
                        ) 

                        # main tile manifest 
                        self.manifest_sink.write(row)
        
                        # label metadata: 
                        #   - real class tile -> label_metadata 
                        #   - review/unknown -> review.csv
                        write_review_sidecar(
                                encoded=encoded, 
                                shard=shard_path, 
                                review_sink=self.review_sink
                                ) 
                        write_label_json_row(
                            encoded=encoded,
                            shard=shard_path,
                            sink=self.label_metadata_sink,
                        )
                        if progress is not None and task_id is not None:
                            progress.advance(task_id, 1)

            return TileSummary(code=0, n_tiles=n_tiles)

        finally: 
            self.manifest_sink.close()
            self.label_metadata_sink.close()
            self.review_sink.close()


