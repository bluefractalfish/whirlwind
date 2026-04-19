"""whirlwind.ingest.tesselate 

    PURPOSE:
        - cur one raster window into a tile tensor + JSON metadata paylow 
        
    BEHAVIOR:
        - read a rasterio window as float32 (always?)
        - apply quantization/scaling if requested 
        - produce metadata 

    PUBLIC:
        - Tile (dataclass)
        - tesselate(tile, ds, qp, tp, band_bounds) -> (npy_btyes, json_bytes, meta_dict)


"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from whirlwind.geo.windows import window_bounds
from whirlwind.ingest.params import QParams, TParams
from whirlwind.ingest.quantize import quantize_tile
from whirlwind.tools import datamonkeys as dm

from rich.traceback import install


install(show_locals=True)

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


def tesselate(
    tile: Tile,
    ds: rasterio.DatasetReader,
    qp: QParams,
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
