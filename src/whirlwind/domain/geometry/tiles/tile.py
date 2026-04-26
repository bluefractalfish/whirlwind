
""" whirlwind.domain.geometry.tiles.tile 

    PURPOSE: 
    --------
    store all tile related functionality, including writing, reading, abstract ref

    TileRead: the tile as pixel data that has been read from a rasterio dataset 
    TileGeoData: the geo referenced spatial aspects of a tile 
    



    Tile: entity tying all other above together 

    PUBLIC 
    --------  

    TileRead(row: PlannedWindow, 
             array: npy.ndarray, 
             masked: bool, 
             band_count: int, 
             dtype: str 
             ) 


    TileGeoData(transform: Affine, 
                bounds: Tuple[float, float, float, float], 
                crs: str) 
    

"""
from dataclasses import dataclass
from typing import Any 

import io 
import json 
import numpy as np 
from rasterio import Affine 

from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.domain.geometry.tiles.plannedwindow import PlannedWindow

@dataclass(frozen=True)
class TileRead: 
 
    """ stores the result of reading one PlannedWindow, planned tile window """

    row: PlannedWindow 
    array: np.ndarray # shape: (bands, h, w)
    masked: bool 
    band_count: int 
    dtype: str 

    def filled(self, fill_value: float = 0.0) -> np.ndarray:
        if np.ma.isMaskedArray(self.array):
            return np.ma.filled(self.array, fill_value)
        return self.array

    def as_float32(self, fill_value: float = 0.0) -> np.ndarray:
        return self.filled(fill_value=fill_value).astype(np.float32, copy=False)


@dataclass(frozen=True)
class TileGeoData: 
    transform: Affine 
    bounds: tuple[float, float, float, float]
    crs: str 


@dataclass(frozen=True)
class Tile:
    """
    feature rich composed object 
    """
    plan: PlannedWindow 
    tile_id: str | None = None 
    source: RasterFile  | None = None 
    read: TileRead | None = None 
    geo: TileGeoData | None = None 
    label: dict[str, Any] | None=None

@dataclass(frozen=True)
class EncodedTile: 
    """ class representation of an encoded Tile object """
    tile_id: str 
    key: str 
    npy_bytes: bytes 
    json_bytes: bytes 
    metadata: dict[str, Any]

class TileEncoder: 
    """
    init 
    -------- 
     src=RasterFile

    purpose 
    -------- 
    turns Tile object into writable tile artifacts npybytes, jsonbytes for shard writer, using src mosaic file 
    
    Owns
    ------ 
     - Tile.tile_id creation,
     - converting tile.read.array into .npy bytes 
     - building tile metadata dict/json bytes 
     - quantization hook for downsampling etc 

    """

    def __init__(self, src: RasterFile) -> None:
        parent_id = src.fid 
        self.mosaic_id = parent_id.uid 
        self.source_uri = parent_id.uri 

    def gen_tile_id(self, tile: Tile) -> str: 
        row = tile.plan
        return f"{self.mosaic_id}_r{row.row_i:03d}_c{row.col_i:03d}"

    def gen_key(self, tile: Tile) -> str: 
        return self.gen_tile_id(tile) 
    
    def to_npy_bytes(self, tile: Tile) -> bytes: 
        arr = tile.read.array 
        bio = io.BytesIO()
        np.save(bio, arr, allow_pickle=False)
        return bio.getvalue()
    
    def to_metadata(self, tile: Tile, tile_id: str) -> dict[str, Any]:
        if tile.read is None or tile.geo is None:
            return {}

        minx, miny, maxx, maxy = tile.geo.bounds

        meta: dict[str, Any] = {
            "tile_id": tile_id,
            "mosaic_id": self.mosaic_id,
            "source_uri": str(self.source_uri),
            "row_i": tile.plan.row_i,
            "col_i": tile.plan.col_i,
            "window": {
                "x_off": int(tile.plan.x),
                "y_off": int(tile.plan.y),
                "w": int(tile.plan.w),
                "h": int(tile.plan.h),
            },
            "bands": int(tile.read.band_count),
            "dtype": str(tile.read.dtype),
            "crs": tile.geo.crs,
            "bounds": {
                "minx": float(minx),
                "miny": float(miny),
                "maxx": float(maxx),
                "maxy": float(maxy),
            },
            "transform": [
                tile.geo.transform.a,
                tile.geo.transform.b,
                tile.geo.transform.c,
                tile.geo.transform.d,
                tile.geo.transform.e,
                tile.geo.transform.f,
            ],
        }

        if tile.label is not None:
            meta["labels"] = dict(tile.label)

        if tile.tile_id is not None:
            meta["tile_ref_id"] = tile.tile_id

        return meta

    def to_json_bytes(self, metadata: dict[str, Any]) -> bytes:
        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def encode(self, tile: Tile) -> EncodedTile: 
        tile_id = self.gen_tile_id(tile)
        key = self.gen_key(tile)
        metadata = self.to_metadata(tile, tile_id)
        npy = self.to_npy_bytes(tile)
        js = self.to_json_bytes(metadata)

        return EncodedTile(
                tile_id=tile_id, 
                key=key, 
                npy_bytes=npy, 
                json_bytes=js, 
                metadata=metadata
            )

