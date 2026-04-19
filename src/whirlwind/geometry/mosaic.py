""" whirlwind.geometry.mosaic 
"""
from dataclasses import dataclass, asdict 
from typing import ClassVar, Any, Mapping 
from whirlwind.filesystem.files import RasterFile
from whirlwind.contracts import Raster 



@dataclass(frozen=True)
class Mosaic:
    """ 
    metadata-first representation of source raster 

    does not hold decoded raster arrays. 
    only stores enough metadata for other layers to retreive 
    """
    mosaic_id: str 
    uri: str 
    f: RasterFile 
    raster: Raster 

    def to_record(self) -> dict[str,object]:
        return { 
            "mosaic_id": self.mosaic_id,
            "uri": self.uri,
            }

    @property 
    def shape(self) -> tuple[int, int, int]:
        """ returns (bands, height, width) """
        return (self.raster.count, self.raster.height, self.raster.width)



@dataclass(frozen=True)
class MosaicRow:
    FIELDNAMES: ClassVar[tuple[str, ...]] = (
        "mosaic_id",
        "uri",
        "uri_etag",
        "byte_size",
        "crs",
        "srid",
        "pixel_width",
        "pixel_height",
        "band_count",
        "dtype",
        "nodata",
        "footprint",
        "acquired_at",
        "created_at",
    )

    mosaic_id: str
    uri: str
    uri_etag: str
    byte_size: str
    crs: str
    srid: str
    pixel_width: str
    pixel_height: str
    band_count: str
    dtype: str
    nodata: str
    footprint: str
    acquired_at: str
    created_at: str

    def to_record(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.FIELDNAMES}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "MosaicRow":
        return cls(
            mosaic_id=str(record.get("mosaic_id", "")),
            uri=str(record.get("uri", "")),
            uri_etag=str(record.get("uri_etag", "")),
            byte_size=str(record.get("byte_size", "")),
            crs=str(record.get("crs", "")),
            srid=str(record.get("srid", "")),
            pixel_width=str(record.get("pixel_width", "")),
            pixel_height=str(record.get("pixel_height", "")),
            band_count=str(record.get("band_count", "")),
            dtype=str(record.get("dtype", "")),
            nodata=str(record.get("nodata", "")),
            footprint=str(record.get("footprint", "")),
            acquired_at=str(record.get("acquired_at", "")),
            created_at=str(record.get("created_at", "")),
        )


