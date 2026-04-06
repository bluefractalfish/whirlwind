
""" whirlwind.commands.mosaic.shard  
    
    PURPOSE:
        - ` command logic for cutting tiles from mosaic and emitting as shards
        - can accept a quantization plan if requested with `-q` 
        
    BEHAVIOR:
        - read windows from source mosaic(s)
        - emits tiles with or without quantization 
        - optionally uses existing label scheme metadata to label
        - optionally quantizes 
    PUBLIC:
        - ShardMosaicCommand



GOAL: pipe together: mosaic label, mosaic quantize, mosaic tile 
        - read raster with window reads 
        - for each read generate tile_id 
        - attach label row if label build has been run 
        - quantize if plan available 
        - write npy json 
"""

from __future__ import annotations 

from pathlib import Path 
from typing import Any, Dict 
from rich.traceback import install 
from whirlwind.tools.pathfinder import build_path
from whirlwind.io.inputs import iter_uris
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from dataclasses import dataclass 
from whirlwind.ui import face 

from typing import Optional, Tuple, Union, List, Any, Dict
from whirlwind.io.out import append_jsonl
from whirlwind.lab.ingest_experiment import list_configs 


import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from whirlwind.tools.geo.windows import window_bounds
from whirlwind.tools import datamonkeys as dm


########################
## COMMAND CLASS HEAD ##
########################


class TesselateMosaicCommand(Command):
    name = "tesselate"

    def run(self, tokens: List[str], config: Config ) -> int:
        face.info("TILING")
        face.prog_row("1/?","parsing config")
        face.print_dictionary(config.parse("mosaic","tile"))
        
        face.prog_row("2/?","building tiling params from config...")
        tp = self.build_params(tokens, config)

        # 

    def build_params(self, tokens: List[str], config: Config) -> TParams | None:
        return None
        
        
######################
## PARAM CONTAINERS ##
######################


@dataclass(frozen=True)
class TParams:

    uris: list[str]
    out_dir: Path
    tile_size: int
    stride: int
    drop_partial: bool
    shard_size: int
    shard_prefix: str
    manifest_kind: str

    def validate(self) -> None:
        if self.tile_size <= 0:
            face.error("param init error: tile_size must be > 0")
        if self.stride <= 0:
            face.error("param init error: stride must be > 0")
        if self.shard_size <= 0:
            face.error("param init error: shard_size must be > 0")
    def print_table(self) -> None:
        cols = ["tiling params","value"]
        rows = [
                ["uris",len(self.uris)],
                ["destination",str(self.out_dir)],
                ["tile size",self.tile_size],
                ["stride",self.stride],
                ["drop partials", self.drop_partial],
                ["shard size", self.shard_size],
                ["manifest", self.manifest_kind]
                ]
        face.table(cols,rows)

@dataclass(frozen=True)
class Tile:
    tile_id: str
    mosaic_id: str
    source_uri: str
    row_id: int
    col_id: int
    transform: Affine
    window: Window
    crs: str | None

    @property
    def width(self) -> int:
        return int(self.window.width)

    @property
    def height(self) -> int:
        return int(self.window.height)

################
## CORE LOGIC ##
################

def tesselate(
    tile: Tile,
    ds: rasterio.DatasetReader,
    #qp: QParams,
    tp: TParams,
    band_bounds: Dict[int, Tuple[float, float]],
    ) -> Tuple[bytes, bytes, Dict[str, Any]]:

    arr = ds.read(window=tile.window, masked=True, out_dtype=np.float32)
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, 0.0).astype(np.float32, copy=False)
    else:
        arr = arr.astype(np.float32, copy=False)

    out_arr, q_meta = quantize_tile(arr, qp, band_bounds)

    t_transform = rasterio.windows.transform(tile.window, ds.transform)
    minx, miny, maxx, maxy = window_bounds(ds, tile.window)

    meta: Dict[str, Any] = {
        "tile_id": tile.tile_id,
        "source_uri": tile.source_uri,
        "mosaic_id": tile.mosaic_id,
        "tile_size": tile.height,
        "stride": tp.stride,
        "window": {
            "x_off": int(tile.window.col_off),
            "y_off": int(tile.window.row_off),
            "w": int(tile.width),
            "h": int(tile.height),
        },
        "crs": tile.crs,
        "transform": dm.affine_to_list(t_transform),
        "bounds": {"minx": float(minx), "miny": float(miny), "maxx": float(maxx), "maxy": float(maxy)},
        "bands": int(ds.count),
        "dtype": str(out_arr.dtype),
    }
    if q_meta:
        meta["scaling"] = q_meta

    try:
        if ds.crs:
            wgs84 = transform_bounds(ds.crs, "EPSG:4326", minx, miny, maxx, maxy, densify_pts=0)
            meta["bounds_wgs84"] = {
                "minx": float(wgs84[0]),
                "miny": float(wgs84[1]),
                "maxx": float(wgs84[2]),
                "maxy": float(wgs84[3]),
            }
        else:
            meta["bounds_wgs84"] = {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0}
    except Exception:
        meta["bounds_wgs84"] = {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0}

    return dm.npy_bytes(out_arr), dm.json_bytes(meta), meta
