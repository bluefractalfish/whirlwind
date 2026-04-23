
""" whirlwind.geometry.tile

    PURPOSE: store all tile related functionality, including writing, reading, abstract ref
    

    PlanRow: the planned cut for a tile 
    TileRead: the tile as pixel data that has been read from a rasterio dataset 
    GeoData: the geo referenced spatial aspects of a tile 
    

"""
from dataclasses import dataclass, asdict 
from typing import ClassVar, Mapping, Any 

import io 
import json 
import numpy as np 
from rasterio import Affine 
from rasterio.windows import Window 

from whirlwind.filetrees.files import RasterFile
from whirlwind.io.planio import PlanRow

@dataclass(frozen=True)
class TileRead: 
    """ stores the result of reading one PlanRow, planned tile window """

    row: PlanRow 
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
class GeoData: 
    transform: Affine 
    bounds: tuple[float, float, float, float]
    crs: str 


@dataclass(frozen=True)
class Tile:
    """
    feature rich composed object 
    """

    plan: PlanRow 
    tile_id: str | None = None 
    source: RasterFile  | None = None 
    read: TileRead | None = None 
    geo: GeoData | None = None 
    label: str | None=None

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
            meta["labels"] = list(tile.label)

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

@dataclass(frozen=True)
class BinLabel: 
    """ label object which holds label features for binary class labeling"""
    # semantic label, i.e. damage, no_damage 
    semlabel: str | None = None 
    # int label, i.e. 0 -> no damage, 1 -> damage 
    intlabel: int | None = None 
    # confidence measure, float between 0-1 
    confidence: float | None = None 
    # annotations, e.g. damage ammount 
    annotation: str | None = None 

""" 
    @property   
    def window(self) -> tuple[int, int, int, int]
        return (self.x_off, self.y_off, self.width, self.height)
    
    def with_label(self, label: str | None) -> "TILE":
        return TILE(
            id=self.id,
            parent_id=self.parent_id,
            source_uri=self.source_uri,
            crs=self.crs,
            footprint=self.footprint,
            x_off=self.x_off,
            y_off=self.y_off,
            width=self.width,
            height=self.height,
            transform=self.transform,
            band_count=self.band_count,
            dtype=self.dtype,
            shard_ref=self.shard_ref,
            label=label,
        )

    def with_shard_ref(self, shard_ref: str | None) -> "TILE":
        return TILE(
            id=self.id,
            parent_id=self.parent_id,
            source_uri=self.source_uri,
            crs=self.crs,
            footprint=self.footprint,
            x_off=self.x_off,
            y_off=self.y_off,
            width=self.width,
            height=self.height,
            transform=self.transform,
            band_count=self.band_count,
            dtype=self.dtype,
            shard_ref=shard_ref,
            label=self.label,
        )

@dataclass(frozen=True)
class TileRow:
    FIELDNAMES: ClassVar[tuple[str, ...]] = (
        "tile_id",
        "shard",
        "key",
        "source_uri",
        "mosaic_id",
        "x_off",
        "y_off",
        "w",
        "h",
        "crs",
        "minx",
        "miny",
        "maxx",
        "maxy",
        "bands",
        "dtype",
    )

    tile_id: str
    shard: str
    key: str
    source_uri: str
    mosaic_id: str
    x_off: int
    y_off: int
    w: int
    h: int
    crs: str
    minx: float
    miny: float
    maxx: float
    maxy: float
    bands: int
    dtype: str

    def to_record(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.FIELDNAMES}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "TileRow":
        return cls(
            tile_id=str(record.get("tile_id", "")),
            shard=str(record.get("shard", "")),
            key=str(record.get("key", "")),
            source_uri=str(record.get("source_uri", "")),
            mosaic_id=str(record.get("mosaic_id", "")),
            x_off=int(record.get("x_off", 0)),
            y_off=int(record.get("y_off", 0)),
            w=int(record.get("w", 0)),
            h=int(record.get("h", 0)),
            crs=str(record.get("crs", "")),
            minx=float(record.get("minx", 0.0)),
            miny=float(record.get("miny", 0.0)),
            maxx=float(record.get("maxx", 0.0)),
            maxy=float(record.get("maxy", 0.0)),
            bands=int(record.get("bands", 0)),
            dtype=str(record.get("dtype", "")),
        )
"""
