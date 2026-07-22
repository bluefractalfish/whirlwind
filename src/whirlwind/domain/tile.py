
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
from copy import deepcopy 

import io 
import json 
import numpy as np 
import re
import rasterio 
from rasterio import Affine 
from pathlib import Path 
from dataclasses import dataclass, replace
from typing import Any
import hashlib
import math
import os
import datetime as dt

from whirlwind.filesystem.files import RasterFile, FileID
from whirlwind.domain.plannedwindow import PlannedWindow
from whirlwind.adapters.label.label_protocol import Label 
from whirlwind.geography.bbox import BBox
from rasterio.crs import CRS


def _crs_unit_name(crs_text: str | None) -> str | None:
    if not crs_text:
        return None

    try:
        crs = CRS.from_string(crs_text)
    except Exception:
        return None

    if crs.is_projected:
        try:
            return crs.linear_units
        except Exception:
            return "projected_units"

    if crs.is_geographic:
        return "degrees"

    return "map_units" 

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
    
    @property 
    def bbox(self) -> "BBox": 
        return BBox.from_bounds(self.bounds)

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
    # member npy arrays: 
    # RGB.band01 
    # NIR.band01 
    # .... 
    npy_members: dict[str, bytes] 

    # each spatial bundle has one json 
    json_bytes: bytes 
    metadata: dict[str, Any]
    
    def merge(self, other: "EncodedTile") -> "EncodedTile":
        """ combine two encoded tiles belonging to the same space"""

        if self.tile_id != other.tile_id: 
            raise ValueError(
                    "cannot merge different spatial tiles: " 
                    f"{self.tile_id} != {other.tile_id}"
                )

        members = dict(self.npy_members) 
        layers = dict(self.metadata.get("layers") or {}) 
        other_layers = other.metadata.get("layers") or {}
                
        for suffix, payload in other.npy_members.items():
            # existing variant.band will win 
            if suffix in members: 
                continue 

            members[suffix] = payload  

            if suffix in other_layers:
                layers[suffix] = dict(other_layers[suffix])
        
        metadata = _bundle_metadata(
                self.metadata, 
                members=members, 
                layers=layers 
                ) 

        return replace(
                self, 
                npy_members=members, 
                metadata=metadata, 
                json_bytes=_metadata_json_bytes(metadata)
            )
    


    def as_manifest_row(self, 
                        shard: str,  
                        *,
                        shard_uri: str | None = None,
                        tile_uri: str | None = None,
                        tile_json_uri: str | None = None,
                        ) -> "ManifestRow":

        meta: dict[str, Any] = self.metadata

        window = meta["window"]
        bounds = meta["bounds"]

        bucket = meta.get("bucket","shards")
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

            pixel_size_x=float(meta.get("pixel_size_x", 0.0)),
            pixel_size_y=float(meta.get("pixel_size_y", 0.0)),
            pixel_size_units=meta.get("pixel_size_units"), 
            shard_uri=shard_uri or meta.get("shard_uri"), 
            tile_uri=tile_uri or meta.get("tile_uri"), 
            tile_json_uri=tile_json_uri or meta.get("tile_json_uri")
        )


@dataclass(frozen=True)
class ManifestRow:   
    """
    a more minimal metadata object for manifest. comprehensive tile 
    metadata is written to TileMetadataRow

    """ 
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

    pixel_size_x: float = 0.0
    pixel_size_y: float = 0.0
    pixel_size_units: str | None = None

    shard_uri: str | None = None
    tile_uri: str | None = None
    tile_json_uri: str | None = None

@dataclass(frozen=True)
class TileMetadataRow: 
    """ 
        comprehensive immutable tile metadata 
        
        contains 
        ---------- 
        - tile identity 
        - source providence 
        - window/plan 

    """ 
    # identity
    tile_id: str
    key: str
    schema_name: str
    schema_version: str
    mosaic_id: str
    source_uri: str

    # source provenance
    source_name: str
    source_size_bytes: int | None
    source_mtime_ns: int | None
    source_fingerprint: str | None
    source_driver: str | None
    source_width: int | None
    source_height: int | None
    source_count: int | None
    source_dtypes: list[str]
    source_colorinterp: list[str]
    source_nodata: list[float | int | None]

    # plan/window
    row_i: int | None
    col_i: int | None
    x_off: int
    y_off: int
    w: int
    h: int
    stride_x: int | None
    stride_y: int | None
    is_partial: bool

    # raster payload
    bands: int
    dtype: str
    array_shape: list[int]
    npy_sha256: str | None

    # geospatial
    crs: str | None
    pixel_size_x: float
    pixel_size_y: float
    pixel_size_units: str | None
    transform: list[float]
    minx: float
    miny: float
    maxx: float
    maxy: float
    centroid_x: float
    centroid_y: float
    footprint: dict[str, Any]

    # quality/content
    content: dict[str, Any]
    image_stats: dict[str, Any]
    
    # where it will be written 
    bucket: str

    def record(self) -> dict[str, Any]:
        """
         JSON-ready nested representation.
         its written to <id>.json in the tar shard.
        """
        return {
            "schema": {
                "name": self.schema_name,
                "version": self.schema_version,
            },
            "identity": {
                "tile_id": self.tile_id,
                "key": self.key,
                "mosaic_id": self.mosaic_id,
            }, 

            # top-level fields for compatibility with ManifestRow.
            "tile_id": self.tile_id,
            "key": self.key,
            "mosaic_id": self.mosaic_id,
            "source_uri": self.source_uri,
            "row_i": self.row_i,
            "col_i": self.col_i,
            "window": {
                "x_off": self.x_off,
                "y_off": self.y_off,
                "w": self.w,
                "h": self.h,
                "stride_x": self.stride_x,
                "stride_y": self.stride_y,
                "is_partial": self.is_partial,
            },
            "bands": self.bands,
            "dtype": self.dtype,
            "crs": self.crs,
            "pixel_size_x": self.pixel_size_x,
            "pixel_size_y": self.pixel_size_y,
            "pixel_size_units": self.pixel_size_units,
            "bounds": {
                "minx": self.minx,
                "miny": self.miny,
                "maxx": self.maxx,
                "maxy": self.maxy,
            },
            "transform": self.transform,

            "source": {
                "source_uri": self.source_uri,
                "source_name": self.source_name,
                "source_size_bytes": self.source_size_bytes,
                "source_mtime_ns": self.source_mtime_ns,
                "source_fingerprint": self.source_fingerprint,
                "source_driver": self.source_driver,
                "source_width": self.source_width,
                "source_height": self.source_height,
                "source_count": self.source_count,
                "source_dtypes": self.source_dtypes,
                "source_colorinterp": self.source_colorinterp,
                "source_nodata": self.source_nodata,
            },
            "raster": {
                "array_shape": self.array_shape,
                "bands": self.bands,
                "dtype": self.dtype,
                "npy_sha256": self.npy_sha256,
            },
            "geo": {
                "crs": self.crs,
                "pixel_size_x": self.pixel_size_x,
                "pixel_size_y": self.pixel_size_y,
                "pixel_size_units": self.pixel_size_units,
                "transform": self.transform,
                "bounds": {
                    "minx": self.minx,
                    "miny": self.miny,
                    "maxx": self.maxx,
                    "maxy": self.maxy,
                },
                "centroid": {
                    "x": self.centroid_x,
                    "y": self.centroid_y,
                },
                "footprint": self.footprint,
            },
            "content": self.content,
            "image_stats": self.image_stats,
            "hashes": {
                "npy_sha256": self.npy_sha256,
            },
            "bucket": self.bucket,
        }

def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
    except Exception:
        return None
    if not math.isfinite(f):
        return None
    return f


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def _metadata_json_bytes(metadata: dict[str, Any]) -> bytes: 
    return json.dumps(
            metadata, 
            ensure_ascii=False, 
            separators=(",",":"),
            ).encode("utf-8")
def _bundle_metadata(
        original: dict[str, Any], 
        *, 
        members: dict[str, bytes], 
        layers: dict[str, dict[str, Any]],
        ) -> dict[str, Any]: 
    metadata = dict(original)
    metadata["layers"] = layers 
    metadata["bands"] = len(members)  

    dtypes = {
            str(layer["dtype"]) 
            for layer in layers.values() 
            if layer.get("dtype") is not None
        }  
    
    if len(dtypes) == 1: 
        bundle_dtypes = next(iter(dtypes))
    elif len(dtypes) > 1: 
        bundle_dtypes = "mixed"
    else: 
        bundle_dtypes = str(metadata.get("dtype") or "")

    metadata["dtype"] = bundle_dtypes
    
    shapes = {
            tuple(layer["shape"])
            for layer in layers.values()
            if layer.get("shape")
        }

    array_shape: list[int] | None = None 

    if len(shapes) == 1: 
        height, width = next(iter(shapes))
        array_shape = [len(members),int(height),int(width)]
    
    member_hashes = {
            suffix: str(layer["npy_sha256"])
            for suffix, layer in layers.items()
            if layer.get("npy_sha256")
            }

    raster = dict(metadata.get("raster") or {})

    raster.update( 
            {
                "array_shape": array_shape, 
                "bands": len(members), 
                "dtype": bundle_dtypes, 
                "npy_sha256": None, 
                "members": [
                    layers[suffix]["member"]
                    for suffix in members
                    if suffix in layers
                    ], 
                "member_sha256": member_hashes
            }
        )
    metadata["raster"] = raster
    hashes = dict(metadata.get("hashes") or {})
    hashes["npy_sha256"] = None 
    hashes["npy_members"] = member_hashes 
    metadata["hashes"] = hashes 

    schema = dict(metadata.get("schema") or {}) 
    schema["version"] = "6.1"
    metadata["schema"] = schema 

    metadata["mosaic_ids"] = sorted(
            {
                str(layer["mosaic_id"])
                for layer in layers.values()
                if layer.get("mosaic_id") 
                }
            )
    return metadata 

   
def _file_fingerprint(path: Path) -> tuple[int | None, int | None, str | None]:
    """
        returns the size, time_ns, and hashed filename for cheap source id
    """
    try:
        st = path.stat()
    except OSError:
        return None, None, None

    size = int(st.st_size)
    mtime_ns = int(st.st_mtime_ns)
    fp = hashlib.sha256(f"{path.name}".encode("utf-8")).hexdigest()
    return size, mtime_ns, fp


def _source_record(path: Path) -> dict[str, Any]:
    """
    Metadata-only raster open. No pixel reads.
    Called once per tile for now, but can be cached in TileEncoder.
    """
    size, mtime_ns, fingerprint = _file_fingerprint(path)

    rec: dict[str, Any] = {
        "source_name": path.name,
        "source_size_bytes": size,
        "source_mtime_ns": mtime_ns,
        "source_fingerprint": fingerprint,
        "source_driver": None,
        "source_width": None,
        "source_height": None,
        "source_count": None,
        "source_dtypes": [],
        "source_colorinterp": [],
        "source_nodata": [],
    }

    try:
        with rasterio.open(path) as ds:
            rec["source_driver"] = ds.driver
            rec["source_width"] = int(ds.width)
            rec["source_height"] = int(ds.height)
            rec["source_count"] = int(ds.count)
            rec["source_dtypes"] = [str(d) for d in ds.dtypes]
            rec["source_colorinterp"] = [str(c).split(".")[-1].lower() for c in ds.colorinterp]
            rec["source_nodata"] = [
                _safe_float(v) if v is not None else None
                for v in ds.nodatavals
            ]
    except Exception:
        # dont make this fatel if it fails 
        pass

    return rec


def _footprint_from_transform(
    transform: Affine,
    width: int,
    height: int,
) -> dict[str, Any]:
    """
    GeoJSON footprint from exact transformed pixel corners.
    Better than bounds if the raster ever has rotation/skew.
    """
    ul = transform * (0, 0)
    ur = transform * (width, 0)
    lr = transform * (width, height)
    ll = transform * (0, height)

    return {
        "type": "Polygon",
        "coordinates": [[
            [float(ul[0]), float(ul[1])],
            [float(ur[0]), float(ur[1])],
            [float(lr[0]), float(lr[1])],
            [float(ll[0]), float(ll[1])],
            [float(ul[0]), float(ul[1])],
        ]],
    }


def _image_stats(tile: Tile) -> dict[str, Any]:
    """
    Cheap stats from the tile array while it is already in memory.
    No extra raster reads.
    """
    if tile.read is None:
        return {}

    arr = tile.read.array

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        return {}

    if np.ma.isMaskedArray(arr):
        data = np.ma.filled(arr, np.nan).astype("float32", copy=False)
    else:
        data = np.asarray(arr).astype("float32", copy=False)

    per_band: list[dict[str, Any]] = []

    for i in range(data.shape[0]):
        b = data[i]
        finite = b[np.isfinite(b)]

        if finite.size == 0:
            per_band.append({
                "band": i + 1,
                "min": None,
                "max": None,
                "mean": None,
                "std": None,
                "p01": None,
                "p02": None,
                "p05": None,
                "p50": None,
                "p95": None,
                "p98": None,
                "p99": None,
            })
            continue

        qs = np.percentile(finite, [1, 2, 5, 50, 95, 98, 99])

        per_band.append({
            "band": i + 1,
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
            "p01": float(qs[0]),
            "p02": float(qs[1]),
            "p05": float(qs[2]),
            "p50": float(qs[3]),
            "p95": float(qs[4]),
            "p98": float(qs[5]),
            "p99": float(qs[6]),
        })

    rgb_stats: dict[str, Any] = {}

    if data.shape[0] >= 3:
        rgb = data[:3]
        brightness = np.nanmean(rgb, axis=0)
        finite_brightness = brightness[np.isfinite(brightness)]

        if finite_brightness.size:
            rgb_stats["brightness_mean"] = float(np.mean(finite_brightness))
            rgb_stats["brightness_std"] = float(np.std(finite_brightness))
            rgb_stats["dark_fraction"] = float(np.mean(finite_brightness <= 5.0))
            rgb_stats["bright_fraction"] = float(np.mean(finite_brightness >= 250.0))

    return {
        "per_band": per_band,
        "rgb": rgb_stats,
    }


def _content_record(tile: Tile) -> dict[str, Any]:
    """
    Reuse existing content stats. Use conservative defaults.
    """
    stats = tile_content_stats(
        tile,
        min_content_fraction=0.60,
        zero_is_empty=True,
        max_black_fraction=0.40,
        max_white_fraction=0.40,
    )
    return stats.record()


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
     - stores multiple spatial patches a bundle 

    """

    def __init__(self, 
                 src: RasterFile, 
                 *, 
                 variant_id: str | None=None, 
                 fill_value: float | int | None=None
    ) -> None:
        self.src = src 
        self.source_path = src.path
        # whole mosaic id 
        self.file_id = src.raster_id 
        # mosaic alias 
        self.uid = src.fid.uid
        # location in user system 
        self.source_uri = src.uri 
        self.variant_token = (
                self._safe_member_token(variant_id)
                if variant_id 
                else None )
        self._source_record: dict[str, Any] | None = None 
        self.fill_value = fill_value 

    @staticmethod
    def _safe_member_token(value: str) -> str: 
        safe = re.sub(
                r"[^A-Za-z0-9_-]+",
                "_",
                value.strip(),
                ).strip("_")
        if not safe: 
            raise ValueError(
                    f"invalid measurement variant: {value!r}"
                    ) 
        return safe 
    
    def materialize(
            self, 
            array: np.ndarray, 
            ) -> np.ndarray: 
        """ convers masked array into normal ndarray before serializing"""

        if not np.ma.isMaskedArray(array):
            return np.asarray(array) 

        mask = np.ma.getmaskarray(array)

        if not bool(mask.any()):
            return np.asarray(array.data)
        
        if self.fill_value is None: 
            raise ValueError(
                    "cannot serialize partial mask without fill value"
                    )

        return np.asarray(
                np.ma.filled(array, self.fill_value)
                )

    def source_record(self) -> dict[str, Any]: 
        """ 
        cache source metadata once per mosaic 
        """

        if self._source_record is None: 
            self._source_record = _source_record(self.source_path) 
        return self._source_record

    def gen_tile_id(self, tile: Tile) -> str: 
        row = tile.plan
        return FileID.tile(self.file_id, row.row_i, row.col_i )

    def gen_key(self, tile: Tile) -> str: 
        row = tile.plan 
        return FileID.tile_key(self.uid, row.row_i, row.col_i)
    
    def to_npy_bytes(self, array: np.ndarray) -> bytes: 
        if np.ma.isMaskedArray(array):
            raise TypeError(
                    "to_npy_bytes requires ordinary, nonmasked array."
                    "call materialize() first to apply mask"
                    )
        bio = io.BytesIO()
        np.save(
                bio, 
                np.asarray(array),
                allow_pickle=False,
            )
        return bio.getvalue()
    
    def split_bands(
            self, 
            array: np.ndarray,
        ) -> dict[str, bytes]:
        """
        splits a (C,H,W) array into one, two dimensional NPY per measured band 

        if ther is no variant id, preserve legacy one-npy behavior 
        """
        if array.ndim == 2: 
            array = array[np.newaxis, :,:]

        if array.ndim != 3:
            raise ValueError(
                    "expected array with shape (bands, height, width)"
                    f"but i got {array.shape} "
                )
        if self.variant_token is None: 
            return {"": self.to_npy_bytes(array)} 

        return {
                f"{self.variant_token}.b{band_index:02d}": self.to_npy_bytes(
                    array[band_index - 1]
                )
                for band_index in range(1, array.shape[0] + 1)
            }



    def to_metadata(self, 
                    tile: Tile, 
                    tile_id: str, 
                    key: str, 
                    *, 
                    npy_sha256: str | None=None, 
                    ) -> dict[str, Any]:
        """ 
        generates the comprehensive metadata row package given a tile 
        """

        if tile.read is None or tile.geo is None: 
            return {}
        
        minx, miny, maxx, maxy = tile.geo.bounds 
        pixel_size_x = abs(float(tile.geo.transform.a))
        pixel_size_y = abs(float(tile.geo.transform.e))
        pixel_size_units = _crs_unit_name(tile.geo.crs)

        src = self.source_record()

        arr = tile.read.array 
        if arr.ndim == 2: 
            array_shape = [1, int(arr.shape[0]), int(arr.shape[1])]
        else:
            array_shape = [int(v) for v in arr.shape]

        bucket = "shards"

        transform = [
                float(tile.geo.transform.a),
                float(tile.geo.transform.b),
                float(tile.geo.transform.c),
                float(tile.geo.transform.d), 
                float(tile.geo.transform.e),
                float(tile.geo.transform.f)
                ]

        centroid_x = float((minx + maxx) / 2.0)
        centroid_y = float((miny + maxy) / 2.0)

        row = TileMetadataRow(
                tile_id=tile_id,
                key=key,
                schema_name="whirlwind.tile",
                schema_version="6.0",
                mosaic_id=self.file_id,
                source_uri=str(self.source_uri),

                source_name=str(src.get("source_name") or self.source_path.name),
                source_size_bytes=src.get("source_size_bytes"),
                source_mtime_ns=src.get("source_mtime_ns"),
                source_fingerprint=src.get("source_fingerprint"),
                source_driver=src.get("source_driver"),
                source_width=src.get("source_width"),
                source_height=src.get("source_height"),
                source_count=src.get("source_count"),
                source_dtypes=list(src.get("source_dtypes") or []),
                source_colorinterp=list(src.get("source_colorinterp") or []),
                source_nodata=list(src.get("source_nodata") or []),

                row_i=tile.plan.row_i,
                col_i=tile.plan.col_i,
                x_off=int(tile.plan.x),
                y_off=int(tile.plan.y),
                w=int(tile.plan.w),
                h=int(tile.plan.h),
                stride_x=None,
                stride_y=None,
                is_partial=False,

                bands=int(tile.read.band_count),
                dtype=str(tile.read.dtype),
                array_shape=array_shape,
                npy_sha256=npy_sha256,

                crs=tile.geo.crs,
                pixel_size_x=pixel_size_x,
                pixel_size_y=pixel_size_y,
                pixel_size_units=pixel_size_units,
                transform=transform,
                minx=float(minx),
                miny=float(miny),
                maxx=float(maxx),
                maxy=float(maxy),
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                footprint=_footprint_from_transform(
                    tile.geo.transform,
                    int(tile.plan.w),
                    int(tile.plan.h),
                ),

                content=_content_record(tile),
                image_stats=_image_stats(tile),

                bucket=bucket,
            )

        meta = row.record()

        if tile.tile_id is not None:
            meta["tile_ref_id"] = tile.tile_id
        return meta



    def to_json_bytes(self, metadata: dict[str, Any]) -> bytes:
        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def encode(self, tile: Tile) -> "EncodedTile": 
        if tile.read is None: 
            raise ValueError("i cant encode a tile without pixel data!")

        tile_id = self.gen_tile_id(tile)
        key = self.gen_key(tile)

        original = tile.read.array 
        array = self.materialize(original)
        members = self.split_bands(array) 
        
        legacy_hash = None 
        if self.variant_token is None: 
            legacy_hash = _sha256_bytes(members[""])

        metadata = self.to_metadata(
                tile, 
                tile_id, 
                key, 
                npy_sha256=legacy_hash
            )

        if self.variant_token is not None: 
            if original.ndim == 2:
                original = original[np.newaxis, :, :]

            layers: dict[str, dict[str, Any]] = {}

            for bi, (suffix, payload) in enumerate(
                    members.items(), 
                    start=1
                    ):
                n_masked_pixels = 0 
                
                if np.ma.isMaskedArray(original):
                    n_masked_pixels = int(
                        np.ma.getmaskarray(
                            original[bi - 1]
                        ).sum()
                    )

                layers[suffix] = {
                    "member": f"{tile_id}.{suffix}.npy",
                    "suffix": suffix,
                    "mosaic_id": self.file_id,
                    "variant_token": self.variant_token,
                    "source_uri": str(self.source_uri),
                    "source_band": bi,
                    "dtype": str(array[bi - 1].dtype),
                    "shape": [
                        int(array.shape[1]),
                        int(array.shape[2]),
                    ],
                    "masked_pixel_count": n_masked_pixels,
                    "fill_value": (
                        self.fill_value
                        if n_masked_pixels > 0
                        else None
                    ),
                    "npy_sha256": _sha256_bytes(payload),
                }

            metadata["variant_token"] = self.variant_token
            metadata = _bundle_metadata(
                metadata,
                members=members,
                layers=layers,
            )

        json_bytes = _metadata_json_bytes(metadata)

        return EncodedTile(
            tile_id=tile_id,
            key=key,
            npy_members=members,
            json_bytes=json_bytes,
            metadata=metadata,
        )

class CanonicalTileEncoder(TileEncoder):
    """
    Generate the same tile identity for every source mosaic using one
    spatial branch plan.
    """

    def __init__( self,
                 *, 
                 src: RasterFile, 
                 bundle_id: str,
                 variant_id: str | None=None,
                 fill_value: float | int | None=None 
        ) -> None:
        super().__init__(
                src, 
                variant_id=variant_id, 
                fill_value=fill_value, 
            )
        self.bundle_id = bundle_id

    def gen_tile_id(self, tile: Tile) -> str:
        row = tile.plan

        return FileID.tile(
            self.bundle_id,
            row.row_i,
            row.col_i,
        )

    def gen_key(self, tile: Tile) -> str:
        return self.gen_tile_id(tile)

    def to_metadata(
        self,
        tile: Tile,
        tile_id: str,
        key: str,
        *,
        npy_sha256: str | None = None,
    ) -> dict[str, Any]:
        metadata = super().to_metadata(
            tile,
            tile_id,
            key,
            npy_sha256=npy_sha256,
        )

        metadata["bundle_id"] = self.bundle_id

        identity = dict(metadata.get("identity") or {})
        identity["bundle_id"] = self.bundle_id
        metadata["identity"] = identity

        return metadata

@dataclass(frozen=True)
class EncodedBundle: 
    key: str 
    npy: bytes | dict[str, bytes]
    metadata: dict[str, Any]

    def load_npy_bundle(self) -> dict[str,np.ndarray]: 
        """ 
        loads every named npy array independenyl as 
        a tile tensor, with keys such as RGB.b01, etc  
        
        expects shaped bundle of : (height, width) 

        can also take legacy tiles : (count, height, width)
                returns these with empty dictionary key: ""
        
        with this, usage: 
        ------------------ 
        members = bundle.load_npy_bundle 
        rgb_band1 = members["RGB.b01"][pixel_y, pixel_x]
        nir_band1 = members["NIR.b01"][pixel_y,pixel_x]
        """
        # check if contains dictionary of layers 
        payloads = (
                self.npy 
                if isinstance(self.npy, dict)
                else {"": self.npy}
                ) 

        return {
                suffix: np.load(
                    io.BytesIO(payload),
                    allow_pickle=False,
                    )
                for suffix, payload in payloads.items()
            } 

    def load_npy_tile(self) -> np.ndarray:
        """ preserves olf stacked-array interface for display/export """
        arrays = self.load_npy_bundle()
        if set(arrays) == {""}:
            array = arrays[""]

            if array.ndim == 2:
                 array = array[np.newaxis, :, :] 

            if array.ndim != 3: 
                raise ValueError(
                        "expected array with shape: (bands, height, width)"
                        f"instead got shape: {array.shape}"
                        ) 
            return array 

        bands: list[np.ndarray] = [] 

        for suffix, array in arrays.items():
            if array.ndim == 3 and array.shape[0] == 1: 
                array = array[0] 
            if array.ndim != 2: 
                raise ValueError(
                        f"expected two-dimensional member {suffix}" 
                        f"but instead i got {array.shape}"
                    )
            bands.append(array)

        return np.stack(bands, axis=0)

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
    black_fraction: float
    white_fraction: float
    mostly_empty: bool

    def record(self) -> dict[str, Any]:
        return {
            "valid_fraction": self.valid_fraction,
            "nonzero_fraction": self.nonzero_fraction,
            "content_fraction": self.content_fraction,
            "black_fraction": self.black_fraction,
            "white_fraction": self.white_fraction,
            "mostly_empty": self.mostly_empty,
        }


def tile_content_stats(
    tile,
    *,
    min_content_fraction: float,
    zero_is_empty: bool = True,
    eps: float = 2.0,
    white_eps: float = 2.0,
    max_black_fraction: float = 0.40,
    max_white_fraction: float = 0.40,
) -> TileContentStats:
    """
    Decide whether a tile has enough real RGB image content.

    - Only checks RGB-like bands, not alpha/NIR.
    - Treats near-black and near-white padding as empty.
    - Prevents black collars / white collars from being classified as water.
    """

    if tile.read is None:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            black_fraction=1.0,
            white_fraction=0.0,
            mostly_empty=True,
        )

    arr = tile.read.array

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(
            f"expected tile array shape (bands, height, width), got {arr.shape}"
        )

    # Use only first three image bands for content detection.
    # This avoids alpha=255 or NIR values making black RGB pixels look valid.
    rgb = arr[: min(3, arr.shape[0])]

    if np.ma.isMaskedArray(rgb):
        mask = np.ma.getmaskarray(rgb)
        data = np.ma.filled(rgb, 0)
        valid_by_band = ~mask
    else:
        data = np.asarray(rgb)
        valid_by_band = np.isfinite(data)

    # Require all RGB bands to be valid, not just one band.
    valid_pixel = np.all(valid_by_band, axis=0)

    safe = np.nan_to_num(data.astype("float32"), nan=0.0, posinf=0.0, neginf=0.0)

    # Near-black means all RGB bands are close to zero.
    black_pixel = np.all(np.abs(safe) <= eps, axis=0)

    # Infer likely max value.
    # uint8 -> 255, uint16 -> 65535, float normalized -> 1.0
    if np.issubdtype(data.dtype, np.integer):
        dtype_max = float(np.iinfo(data.dtype).max)
    else:
        observed_max = float(np.nanmax(safe)) if safe.size else 1.0
        dtype_max = 1.0 if observed_max <= 1.5 else 255.0

    white_threshold = dtype_max - white_eps

    # Near-white means all RGB bands are close to dtype max.
    white_pixel = np.all(safe >= white_threshold, axis=0)

    if zero_is_empty:
        nonzero_pixel = ~black_pixel
    else:
        nonzero_pixel = valid_pixel

    # Real content excludes black padding and white padding.
    content_pixel = valid_pixel & nonzero_pixel & ~white_pixel

    total_pixels = int(content_pixel.size)

    if total_pixels == 0:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            black_fraction=1.0,
            white_fraction=0.0,
            mostly_empty=True,
        )

    valid_fraction = float(valid_pixel.sum() / total_pixels)
    nonzero_fraction = float(nonzero_pixel.sum() / total_pixels)
    content_fraction = float(content_pixel.sum() / total_pixels)
    black_fraction = float(black_pixel.sum() / total_pixels)
    white_fraction = float(white_pixel.sum() / total_pixels)

    mostly_empty = (
        content_fraction < min_content_fraction
        or black_fraction > max_black_fraction
        or white_fraction > max_white_fraction
    )

    return TileContentStats(
        valid_fraction=valid_fraction,
        nonzero_fraction=nonzero_fraction,
        content_fraction=content_fraction,
        black_fraction=black_fraction,
        white_fraction=white_fraction,
        mostly_empty=mostly_empty,
    )


