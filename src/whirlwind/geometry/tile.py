
""" whirlwind.geometry.tile

    PURPOSE: store all tile related functionality, including writing, reading, abstract ref
    

    PlanRow: the planned cut for a tile 
    TileRead: the tile as pixel data that has been read from a rasterio dataset 
    GeoData: the geo referenced spatial aspects of a tile 
    

"""
from dataclasses import dataclass, asdict 
from typing import ClassVar, Mapping, Any 

import numpy as np 
import rasterio 
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
    band_cound: int 
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
