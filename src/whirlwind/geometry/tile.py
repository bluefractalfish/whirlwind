
""" whirlwind.geometry.tile
"""
from dataclasses import dataclass, asdict 
from typing import ClassVar, Mapping, Any 
from whirlwind.geometry.footprint import Bounds 


@dataclass(frozen=True)
class Tile:
    """
    metadata representation of mosaic subwindow 

    does not store raster payload or decoded arrays 
    """
    id: str 
    parent_id: str 
    source_uri: str 
    crs: str 
    footprint: Bounds  

    x_off: int 
    y_off: int 
    width: int 
    height: int 

    transform: tuple[float, float, float, float, float, float]

    band_count: int | None = None 
    dtype: str | None = None 

    shard_ref: str | None = None 
    label: str | None = None 

    def record(self) -> TileRow:
        return TileRow( 
                       tile_id=self.id, 
                       )
    @property 
    def window(self) -> tuple[int, int, int, int]
        """
        pixel window as (x_off, y_off, width, height)

        """
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
