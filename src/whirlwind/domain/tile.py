
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
from dataclasses import dataclass, replace 
from typing import Any 

import io 
import json 
import numpy as np 
from rasterio import Affine 
from pathlib import Path 

from whirlwind.adapters.label.simple_label import SimpleLabel
from whirlwind.filesystem.files import RasterFile, FileID
from whirlwind.domain.plannedwindow import PlannedWindow
from whirlwind.adapters.label.label_protocol import Label 

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

@dataclass(frozen=True)
class EncodedTile: 
    """ class representation of an encoded Tile object """
    tile_id: str 
    key: str 
    npy_bytes: bytes 
    json_bytes: bytes 
    metadata: dict[str, Any]

    def as_manifest_row(self, shard: str) -> ManifestRow:
        meta: dict[str, Any] = self.metadata

        window = meta["window"]
        bounds = meta["bounds"]

        label_meta = meta.get("label", {})
        bucket = meta.get("bucket", label_meta.get("bucket", "shards"))

        return ManifestRow(
            tile_id=self.tile_id,
            shard=str(shard),
            key=self.key,
            source_uri=str(meta["source_uri"]),
            x_off=int(window["x_off"]),
            y_off=int(window["y_off"]),
            w=int(window["w"]),
            h=int(window["h"]),
            crs=meta.get("crs"),
            minx=float(bounds["minx"]),
            miny=float(bounds["miny"]),
            maxx=float(bounds["maxx"]),
            maxy=float(bounds["maxy"]),
            bands=int(meta["bands"]),
            dtype=str(meta["dtype"]),

            row_i=meta.get("row_i"),
            col_i=meta.get("col_i"),
            bucket=str(bucket),
            branch_id=meta.get("branch_id"),
            mosaic_id=meta.get("mosaic_id"),

            label_json=json.dumps(
                label_meta,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

@dataclass(frozen=True)
class ManifestRow:
    tile_id: str
    shard: str
    key: str
    source_uri: str
    x_off: int
    y_off: int
    w: int
    h: int
    crs: str | None
    minx: float
    miny: float
    maxx: float
    maxy: float
    bands: int
    dtype: str

    row_i: int | None = None
    col_i: int | None = None
    bucket: str = "tiles"
    branch_id: str | None = None
    mosaic_id: str | None = None

    label_json: str = "{}"

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
        self.file_id = src.raster_id 
        self.source_uri = parent_id.uri 

    def gen_tile_id(self, tile: Tile) -> str: 
        row = tile.plan
        return FileID.tile(self.file_id, row.row_i, row.col_i )

        return f"{self.file_id}_r{row.row_i:03d}_c{row.col_i:03d}"

    def gen_key(self, tile: Tile) -> str: 
        return self.gen_tile_id(tile) 
    
    def to_npy_bytes(self, tile: Tile) -> bytes: 
        arr = tile.read.array 
        bio = io.BytesIO()
        np.save(bio, arr, allow_pickle=False)
        return bio.getvalue()
    
    def to_metadata(self, tile: Tile, tile_id: str, label: Label | None=None) -> dict[str, Any]:
        if tile.read is None or tile.geo is None:
            return {}

        minx, miny, maxx, maxy = tile.geo.bounds

        meta: dict[str, Any] = {
            "tile_id": tile_id,
            "mosaic_id": self.file_id,
            "branch_id": FileID.branch(self.file_id),
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

        if label is not None:
            meta["bucket"] = label.bucket
            meta["label"] = dict(label.metadata())
        else:
            meta["bucket"] = "shards"

        if tile.tile_id is not None:
            meta["tile_ref_id"] = tile.tile_id

        return meta

    def to_json_bytes(self, metadata: dict[str, Any]) -> bytes:
        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def encode(self, tile: Tile, label: Label | None=None) -> EncodedTile: 
        tile_id = self.gen_tile_id(tile)
        key = self.gen_key(tile)
        metadata = self.to_metadata(tile, tile_id, label)
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
class EncodedPair: 
    key: str 
    npy: bytes 
    metadata: dict[str, Any]

    def load_npy_tile(self) -> np.ndarray: 
        """ 
        loads one tile tensor from npy bytes 
        
        expects shape: (bands, height, width) 
        can also take: (height, width)

        returns array with shape (bands, height, width)
        """
        arr = np.load(io.BytesIO(self.npy)) 

        if arr.ndim == 2: 
            arr = arr[np.newaxis, :, :]

        if arr.ndim != 3: 
            raise ValueError(f"expected array shape: (bands, height, width), got {arr.shape}")

        return arr 
    
    def tile_out_path(self, out_dir: Path) -> Path: 
        """ build output path for one tile """
        tile_id = self.metadata.get("tile_id") or self.key 
        return out_dir / f"{tile_id}.tif"


    def profile(
        self, 
        arr: np.ndarray, 
        *,
        compress: str | None = None,
    ) -> dict[str, Any]:
        """
        Build a rasterio GeoTIFF profile from tile array and metadata.

        Important:
            No nodata is set here. Display TIFFs should not use nodata,
            especially when writing RGB/RGBA for QGIS inspection.
        """ 

        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :] 

        if arr.ndim != 3:
            raise ValueError(
                f"expected array shape: (bands, height, width), got {arr.shape}"
            )

        metadata = self.metadata
        count, height, width = arr.shape

        transform_values = metadata.get("transform")
        if transform_values is None:
            tile_id = metadata.get("tile_id", "<unknown>")
            raise ValueError(f"tile metadata missing transform: {tile_id}")

        profile: dict[str, Any] = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": count,
            "dtype": arr.dtype,
            "crs": metadata.get("crs") or None,
            "transform": self.to_affine(transform_values),
        }

        if compress is not None:
            profile["compress"] = compress

        # internal tiling helps QGIS/GDAL for normal 256/512 tiles.
        # avoid invalid block sizes for very small edge tiles.
        if width >= 16 and height >= 16:
            profile["tiled"] = True
            profile["blockxsize"] = min(256, width)
            profile["blockysize"] = min(256, height)

        # defensive: never propagate nodata into display outputs.
        profile.pop("nodata", None)

        return profile

    def to_affine(self, v: list[float] | tuple[float, ...]) -> Affine:
        """
        Rebuild rasterio Affine from metadata transform list.

        Expected:
            [a, b, c, d, e, f]
        """
        if len(v) != 6:
            raise ValueError(f"expected transform with 6 values, got {len(v)}")

        return Affine(v[0], v[1], v[2], v[3], v[4], v[5])

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
    ...

