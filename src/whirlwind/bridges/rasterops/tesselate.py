
from typing import Iterable, Any 
from dataclasses import dataclass, replace  
from pathlib import Path 

import numpy as np  

from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.adapters.io.windowplan_io import WindowPlanCSV
from whirlwind.adapters.io.shard_manifest import make_sink  
from whirlwind.adapters.io.write_shards import ShardWriter, WriteShardRequest, DamageSplitShardWriter
from whirlwind.adapters.geo.damage_labels import DamageLabeler 
from whirlwind.adapters.geo.window_read import RasterioWindowReader

from whirlwind.bridges.specs.tiling import TSpec 

from whirlwind.domain.tile import  TileEncoder
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.filesystem.files import RasterFile

from whirlwind.interface import face 

@dataclass(frozen=True)
class Request: 
    spec: TSpec 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path] 
    prefix: str 
    shard_size: int 
    overwrite: bool 
    label: bool 
    dry: bool 
    dpath_name: str 
    plan_name: str 
    manifest_name: str 
    manifest_kind: str 
    masked: bool = False 
    fill_value: float = 0.0 
    min_content_fraction: float = 0.02 
    zero_is_empty: bool = True 



@dataclass(frozen=True)
class Summary:
    error: int 
    code: int # 3 gpkg doesnt exist/empty, 5 no manifest, 7 no plan, 35 no man no plan, 
    gpkg_path: Path | None=None
    plan_path: Path | None=None
    n_tiles: int=0

@dataclass(frozen=True)
class Result: 
    n_tiles_written: int 
    n_rasters_seen: int 
    summaries: tuple[Summary,...]
    rasters_skipped: int 
    code: int 

@dataclass(frozen=True)
class TileContentStats:
    valid_fraction: float
    nonzero_fraction: float
    content_fraction: float
    mostly_empty: bool

    def record(self) -> dict[str, Any]:
        return {
            "valid_fraction": self.valid_fraction,
            "nonzero_fraction": self.nonzero_fraction,
            "content_fraction": self.content_fraction,
            "mostly_empty": self.mostly_empty,
        }


def tile_content_stats(
    tile,
    *,
    min_content_fraction: float,
    zero_is_empty: bool = True,
    eps: float = 0.0,
) -> TileContentStats:
    """
    Decide whether a tile has enough real image content to keep.

    For RGB orthos where nodata/background is 0, use zero_is_empty=True.
    """

    if tile.read is None:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            mostly_empty=True,
        )

    arr = tile.read.array

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected tile array shape (bands, height, width), got {arr.shape}")

    if np.ma.isMaskedArray(arr):
        mask = np.ma.getmaskarray(arr)
        valid_by_band = ~mask
        data = np.ma.filled(arr, 0)
    else:
        data = np.asarray(arr)
        valid_by_band = np.isfinite(data)

    # Pixel is valid if any band is valid.
    valid_pixel = np.any(valid_by_band, axis=0)

    if zero_is_empty:
        safe = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
        nonzero_pixel = np.any(np.abs(safe) > eps, axis=0)
    else:
        nonzero_pixel = valid_pixel

    content_pixel = valid_pixel & nonzero_pixel

    total_pixels = int(content_pixel.size)

    if total_pixels == 0:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            mostly_empty=True,
        )

    valid_fraction = float(valid_pixel.sum() / total_pixels)
    nonzero_fraction = float(nonzero_pixel.sum() / total_pixels)
    content_fraction = float(content_pixel.sum() / total_pixels)

    return TileContentStats(
        valid_fraction=valid_fraction,
        nonzero_fraction=nonzero_fraction,
        content_fraction=content_fraction,
        mostly_empty=content_fraction < min_content_fraction,
    )


def attach_content_stats(tile, stats: TileContentStats):
    """
    Store content stats in tile metadata.

    TileEncoder currently writes tile.label into metadata["labels"], so this
    merges content stats into that label dict without destroying damage labels.
    """
    label = dict(tile.label or {})
    label["content"] = stats.record()
    return replace(tile, label=label) 

class TesselationBridge:

    def run(self, request: Request) -> Result:
        with face.phase(1,5,"locating manifest...", delay=0.5):
            if not request.manifest.exists():
                face.error(f"no manifest found for request")
                face.div()
                face.info("run `discover manifest` or ? for help")
                face.div()
                raise FileNotFoundError 

        with face.phase(2,5,"constructing tesselation request..."): pass
        summaries: list[Summary] = []
        n_tiles = 0 
        n_rasters = 0 
        with face.phase(3,5,"building tesselation spec, referencing plan..."): pass 
        with face.progress() as pr:
            t1 = pr.add_task("walking manifest",total=request.manifest.length)
            t2 = pr.add_task("",total=request.manifest.length)
            for p in request.paths: 
                pr.advance(t1,1)
                pr.update(t2, description=f"tiling {p}")
                
                # confirm tile plan exists 
                try: 
                    tiler = RasterTiler(p,request)
                except FileNotFoundError:
                    with face.phase(4,5,"no tiling plan found"): pass 
                    summaries.append(Summary(error=1,code=3))
                    continue
                # get sink code (sc): 1 -> ok, else error 
                sc = tiler.build_sinks()
                if sc != 1: 
                    print(sc)
                    summaries.append(Summary(error=1,code=sc))
                    continue 

                tiler.make_shard_request()
                # only run labeling if --label or -l flag present. 
                # uses SplitShardWriter to write to damage/nodamage bins 
                if request.label: 
                    summary = tiler.tile_with_damage_labels()

                # if no labeling request present, shard normally without referencing labeler 
                # or this tiles label metadata 
                else:
                    summary = tiler.tile()

                n_rasters += 1
                n_tiles += summary.n_tiles
                summaries.append(summary)
                pr.advance(t2,1)
        
        face.phase(4,4,"assessing summaries...")
        skipped = sum(1 for s in summaries if s.code==7)
        
        face.phase(5,5,"building report",delay=1)
        return Result(
                n_rasters_seen=n_rasters, 
                n_tiles_written=n_tiles,
                rasters_skipped= skipped, 
                summaries=tuple(summaries), 
                code = 0 if all(s.error==0 for s in summaries) else 1
                )


class RasterTiler:
    def __init__(self, p: Path | str, request: Request) -> None: 
        self.p = p 
        self.request = request 
        self.code = 0 
        f = RasterFile(p)
        self.encoder = TileEncoder(src=f)

        branch = request.tree.branchlook(request.manifest,p)
        self.shard_dir = branch.shards_dir

        #find the path for the gpkg and tile_plan if they exist 
        #can only label with gpkg present and manually configured 
        self.gpkg_path = branch.browse_dir/ request.dpath_name    
        self.manifest_path = branch.manifest_dir/request.manifest_name 

        self.tile_plan_path = branch.staging_dir/request.plan_name
        if not self.tile_plan_path.is_file() or not self.tile_plan_path.exists():
            raise FileNotFoundError

    def build_sinks(self) -> int:
        return_code = 1 
        try:  
            self.manifest_sink=make_sink(self.request.manifest_kind, self.manifest_path)
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
                        prefix=self.request.prefix, 
                        size=self.request.shard_size,) 

    def tile(self) -> Summary:
        planned_windows = self.plan_sink.read() 
        with ShardWriter(self.req) as writer:
            with RasterioWindowReader(
                    self.p, self.request.masked, self.request.fill_value
                    ) as reader: 
                n_tiles = 0 

                for tile in reader.tiles_from_rows(planned_windows):
                    stats = tile_content_stats(
                        tile,
                        min_content_fraction=self.request.min_content_fraction,
                        zero_is_empty=self.request.zero_is_empty,
                    )

                    tile = attach_content_stats(tile, stats)
                    encoded = self.encoder.encode(tile)

                    if self.request.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}") 
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)

                    self.manifest_sink.write(row)
        
        return Summary(error=0, 
                       code=0, 
                       gpkg_path=self.gpkg_path, 
                       plan_path=self.tile_plan_path, 
                       n_tiles=n_tiles)

    def tile_with_damage_labels(self) -> Summary: 
        planned_windows = self.plan_sink.read() 
        with DamageSplitShardWriter(self.req) as writer:
            with RasterioWindowReader(
                    self.p, masked=self.request.masked, fill=self.request.fill_value
                    ) as reader: 
                if not self.gpkg_path.exists():
                    return Summary(plan_path=self.tile_plan_path, 
                                             code=3, 
                                             error=1)
                labeler = DamageLabeler.from_gpkg(
                            gpkg_path=self.gpkg_path,
                            area_layer="damage_area",
                            line_layer="center_line",
                            target_crs=reader.ds.crs )
                n_tiles = 0  
                for tile in reader.tiles_from_rows(planned_windows): 
                    tile = labeler.label(tile)
                    encoded = self.encoder.encode(tile)
                    if self.request.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}")
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)
                    self.manifest_sink.write(row)

        return Summary(error=0, 
                       code=0, 
                       gpkg_path=self.gpkg_path, 
                       plan_path=self.tile_plan_path, 
                       n_tiles=n_tiles)


