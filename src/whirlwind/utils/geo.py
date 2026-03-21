
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime 
from osgeo import gdal
from osgeo import osr  # SpatialReference + CoordinateTransformation
import argparse
from dataclasses import dataclass

from . import ids
from . import datahelp as dh
from . import readwrite as rwr
from ..ui.tui import TUI 

ui = TUI()

def _init() -> None:
    ui.info("initializing gdal: UseExceptions = True")
    gdal.UseExceptions()

def extract_metadata(uri: str, columns: List[str]) -> Dict[str, Any]:

    """
    Open raster at `uri` using GDAL and return a dict containing only the requested columns.

    Typical columns for mosaic_stage:
      mosaic_id,uri, uri_etag, byte_size, crs, srid, pixel_width, pixel_height,
      band_count, dtype, nodata, footprint, acquired_at, created_at
    """
    ds = gdal.Open(uri, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"GDAL failed to open: {uri}")

    out: Dict[str, Any] = {}
    
    if "mosaic_id" in columns:
        out["mosaic_id"]=ids.uuid_from_path(uri)
    # always allow uri
    if "uri" in columns:
        out["uri"] = uri

    if "byte_size" in columns:
        out["byte_size"] = dh.get_byte_size(uri)

    crs_wkt = ""
    if "crs" in columns or "srid" in columns or "footprint" in columns:
        crs_wkt = get_crs(ds)

    if "crs" in columns:
        out["crs"] = crs_wkt

    if "srid" in columns:
        out["srid"] = get_srid(crs_wkt)

    if any(c in columns for c in ("pixel_width", "pixel_height", "band_count")):
        w, h, b = get_raster_shape(ds)
        if "pixel_width" in columns:
            out["pixel_width"] = w
        if "pixel_height" in columns:
            out["pixel_height"] = h
        if "band_count" in columns:
            out["band_count"] = b

    if "dtype" in columns or "nodata" in columns:
        dtype, nodata = get_dtype_and_nodata(ds)
        if "dtype" in columns:
            out["dtype"] = dtype
        if "nodata" in columns:
            out["nodata"] = nodata

    if "footprint" in columns:
        out["footprint"] = get_footprint(ds, target_epsg=4326)

    if "acquired_at" in columns:
        out["acquired_at"] = parse_aquired_at(Path(uri), valid=True)

    if "uri_etag" in columns:
        out["uri_etag"] = ""
    if "created_at" in columns: 
        out["created_at"] = dh.created_at()

    return out

def num_tiles(ds: rasterio.DatasetReader, tile_size: int, stride: int) -> int:
    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    return tiles_x * tiles_y

def _quant_dtype(dtype: str) -> np.dtype:
    d = dtype.lower()
    if d == "float32":
        return np.float32 
    if d == "uint16":
        return np.uint16
    if d == "uint8":
        return np.uint8
    raise ValueError(f"unsuported dtype, see wind.log")

def _dst_range(dtype: str) -> Tuple[float, float]:
    d = dtype.lower()
    if d == "uint16":
        return 0.0, 65535.0
    if d == "uint8":
        return 0.0, 255.0
    if d == "float32":
        return 0.0, 1.0
    raise ValueError("unsuported dtype, see wind.log")

def get_dtype(gdal_type: int) -> str:
    """
    Convert a GDAL datatype enum (e.g., gdal.GDT_UInt16) to a readable string (e.g., "UInt16").
    """
    return gdal.GetDataTypeName(gdal_type) or ""

def get_byte_size(uri: str) -> str:
    """
    Best-effort file size in bytes for LOCAL files.

    If `uri` is not a local path (e.g., /vsis3/..., http://..., s3://...),
    Path(uri).exists() will usually fail; in that case this returns "".
    """
    try:
        p = Path(uri)
        if p.exists():
            return str(p.stat().st_size)
    except Exception:
        pass
    return ""

def get_crs(ds: gdal.Dataset) -> str:
    """Return CRS as WKT, or empty string if missing."""
    return ds.GetProjection() or ""

def get_srid(crs_wkt: str) -> str:
    """
    Try to extract an EPSG code (SRID) from a WKT projection.

    Returns:
      - "4326" etc if available
      - "" if no authority code can be found
    """
    if not crs_wkt:
        return ""

    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs_wkt)

    # Force lon/lat axis order for EPSG:4326 style CRS
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    epsg_code = srs.GetAuthorityCode(None)
    return epsg_code or ""

def get_raster_shape(ds: gdal.Dataset) -> Tuple[str, str, str]:
    """
    Return (pixel_width, pixel_height, band_count) as strings (staging-friendly).
    """
    return str(ds.RasterXSize), str(ds.RasterYSize), str(ds.RasterCount)

def get_dtype_and_nodata(ds: gdal.Dataset) -> Tuple[str, str]:
    """
    Use band 1 as representative for dtype + nodata.

    Returns:
      (dtype_str, nodata_str)
    """
    if ds.RasterCount < 1:
        return "", ""

    b1 = ds.GetRasterBand(1)
    dtype = get_dtype(b1.DataType)

    nd = b1.GetNoDataValue()
    nodata = "" if nd is None else str(nd)
    return dtype, nodata

def parse_aquired_at(path: Path, valid: bool = True) -> str:
    """
    Parse acquisition date from filename prefix.

    Convention:
      YYMMDD_loc_...  (example: 240119_denver_ortho.tif)

    Returns:
      "20YY-MM-DD"  (example: "2024-01-19")

    If no match is found, returns "".

    NOTE: function name kept as `parse_aquired_at` to match your existing calls
    (spelling preserved).
    """
    name = path.name

    if valid:
        # Strict-ish month/day ranges
        m = re.match(r"^(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", name)
    else:
        m = re.match(r"^(\d{2})(\d{2})(\d{2})", name)

    if not m:
        return ""

    yy, mm, dd = m.group(1), m.group(2), m.group(3)
    return f"20{yy}-{mm}-{dd}"

def get_footprint(ds: gdal.Dataset, target_epsg: int = 4326) -> str:
    """
    Compute raster bbox footprint as EWKT in target_epsg (default 4326).

    Returns:
      "SRID=4326;POLYGON((lon lat, lon lat, ...))"

    Requirements:
      - dataset must have a geotransform and projection
    """
    gt = ds.GetGeoTransform(can_return_null=True)
    if gt is None:
        return ""

    src_wkt = ds.GetProjection() or ""
    if not src_wkt:
        return ""

    width = ds.RasterXSize
    height = ds.RasterYSize

    def pix_to_geo(px: float, py: float) -> Tuple[float, float]:
        x = gt[0] + px * gt[1] + py * gt[2]
        y = gt[3] + px * gt[4] + py * gt[5]
        return x, y

    # corners in source CRS (closed ring)
    corners = [
        pix_to_geo(0, 0),
        pix_to_geo(width, 0),
        pix_to_geo(width, height),
        pix_to_geo(0, height),
        pix_to_geo(0, 0),
    ]

    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(target_epsg)

    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    tx = osr.CoordinateTransformation(src, dst)

    corners_out = []
    for x, y in corners:
        lon, lat, _ = tx.TransformPoint(x, y)
        corners_out.append((lon, lat))

    coords = ",".join(f"{lon:.8f} {lat:.8f}" for lon, lat in corners_out)
    return f"SRID={target_epsg};POLYGON(({coords}))"

def window_bounds(ds: rasterio.DatasetReader, win: Window) -> tuple[float, float, float, float]:
    """Bounds in dataset CRS."""
    return rasterio.windows.bounds(win, ds.transform)

def iter_windows(ds: rasterio.DatasetReader, 
                 tp: TParams) -> Iterator[Tuple[int, int, Window]]:
    """
    deterministic row major iteration of windows. 
    returns (row_indx, col_indx, window)
    """
    max_x = ds.width
    max_y = ds.height
    tile_size = tp.tile_size
    stride = tp.stride
    
    if tp.drop_partial:
        x_stops = range(0, max_x - tile_size + 1, stride)
        y_stops = range(0, max_y - tile_size + 1, stride)
    else:
        x_stops = range(0, max_x, stride)
        y_stops = range(0, max_y, stride)

    for ry, y in enumerate(y_stops):
        for cx, x in enumerate(x_stops):
            w = tile_size if (x + tile_size <= max_x) else (max_x-x)
            h = tile_size if (y + tile_size <= max_y) else (max_y-y)
            if tp.drop_partial and (w != tile_size or h != tile_size):
                continue
            yield ry, cx, Window(x, y, w, h)

def sample_band(
        ds: rasterio.DatasetReader,
        tile_size: int,
        stride: int,
        qp: QParams,
        p: Progress()) -> Dict[int, Tuple[float,float]]:
    """
    approx per band bounds for scaling. avoid full read.
    runs whenever qp.scale != none
    strategy:
        1 sample windows as a deterministic grid stride
        2 stop after num_samples per band
        3 return {band index: (lo, hi)}
    """
    if qp.scale == "none":
        return {}
    # number of bands
    nb = ds.count
    lo_hi: Dict[int, List[float]] = {b: [] for b in range(1, nb+1)}
    need = max(1, qp.num_samples)


    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    n_tiles = tiles_x * tiles_y
    

    # Deterministic sparse sampling of tile origins
    step = max(1, int(math.sqrt(n_tiles / need)))
    sparse = math.ceil(tiles_y/step)*math.ceil(tiles_x/step)
    sampled = 0
    
    t2 = p.add_task(description="sampling bands", total=min(need,sparse))
    for ty in range(0, tiles_y, step):
        y = ty * stride
        for tx in range(0, tiles_x, step):
            p.update(t2, advance=1)
            x = tx * stride
            win = Window(x, y, tile_size, tile_size)

            # masked read avoids nodata bias
            data = ds.read(window=win, out_dtype=np.float32, masked=True)  # (bands, H, W)

            for bi in range(nb):
                band = data[bi]
                if getattr(band, "mask", None) is not None and band.mask.all():
                    continue
                vals = band.compressed() if hasattr(band, "compressed") else band.ravel()
                if vals.size == 0:
                    continue

                if qp.scale == "minmax":
                    lo_hi[bi + 1].append(float(np.min(vals)))
                    lo_hi[bi + 1].append(float(np.max(vals)))
                elif qp.scale == "percentile":
                    lo = float(np.percentile(vals, qp.p_low))
                    hi = float(np.percentile(vals, qp.p_high))
                    lo_hi[bi + 1].append(lo)
                    lo_hi[bi + 1].append(hi)
                else:
                    # unknown -> no bounds
                    pass

            sampled += 1
            if sampled >= need:
                break
        if sampled >= need:
            break

    out: Dict[int, Tuple[float, float]] = {}
    for b in range(1, nb + 1):
        xs = lo_hi[b]
        if not xs:
            out[b] = (0.0, 1.0)
        else:
            out[b] = (min(xs), max(xs))
    return out

def quantize_tile(
        arr: np.ndarray, # (band, H, W) float32
        qp: QParams,
        band_bounds: Dict[int, Tuple[float, float]],
        ) -> Tuple[np.ndarray, Dict[str, object]]:
    """
    apply scaling (if qp.scale != none) using minmax/percentile then
        cast to output dtype

    if scale == none:
        returns arr cast to requested dtype with no scaling 
        (uint cast will clip to valid range)
    scale in {minmax, percentile}
        compute per-band linear mapping from [src_lo, src_hi] -> dst_range(dtype)
            -> float32 dst_range is [0,1] (normalize float tiles)
            -> uint16/uin8: quantized integer tiles 
    """
    out_dtype = _quant_dtype(qp.dtype)
    if qp.scale == "none":
        if qp.dtype.lower() == "float32":
            return arr.astype(np.float32, copy=False), {"scale": "none", "dtype": "float32"}
        dst_lo, dst_hi = _dst_range(qp.dtype)
        clipped = np.clip(arr, dst_lo, dst_hi)
        return clipped.astype(out_dtype), {"scale": "none", "dtype": qp.dtype.lower(), "clipped_to": [dst_lo, dst_hi]}
    # scale requested 
    dst_lo, dst_hi = _dst_range(qp.dtype)
    nb = arr.shape[0]
    
    scaled = np.empty_like(arr, dtype=np.float32)
    meta: Dict[str, object] = {
            "scale": qp.scale,
            "dtype": qp.dtype.lower(),
            "per_band": True,
            "dst_range": [dst_lo, dst_hi],
            "bands": [],
            }
    for bi in range(nb):
        b = bi + 1
        src_lo, src_hi = band_bounds.get(b, (0.0,1.0))
        if not np.isfinite(src_lo) or not np.isfinite(src_hi) or src_hi <= src_lo:
            src_lo, src_hi = 0.0, 1.0

        band = arr[bi]
        # linear map
        s = (band - src_lo) * (dst_hi - dst_lo) / (src_hi - src_lo) + dst_lo
        scaled[bi] = s

        meta["bands"].append({"band": b, "src_lo": float(src_lo), "src_hi": float(src_hi)})

    scaled = np.clip(scaled, dst_lo, dst_hi)

    if qp.dtype.lower() == "float32":
        # normalized float tiles
        return scaled.astype(np.float32, copy=False), meta

    # quantized integer tiles
    return scaled.astype(out_dtype), meta

def cut_tile(
             t: Tile,
             ds: rasterio.DatasetReader,
             qp: QParams,
             tp: TParams,
             band_bounds: Iterator[Tuple[int, int, Window]],
             writer: rwr.ShardWriter) -> tuple[bytes, bytes, Any]:
    """ 
        given an id generated from row + column, a window and a raster being windowed, 
        generate the numpy array and json metadata for that tile 
    """
    
    arr = ds.read(window=t.window, masked=True, out_dtype=np.float32)
    # Fill masked values with 0 for ML tensors; retain mask info optionally
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, 0.0).astype(np.float32, copy=False)
    else:
        arr = arr.astype(np.float32, copy=False)
    # Apply scaling/quantization (can output float32 normalized or uint*)
    out_arr, q_meta = quantize_tile(arr, qp, band_bounds)
    # Build per-tile georef metadata
    t_transform = rasterio.windows.transform(t.window, ds.transform)
    minx, miny, maxx, maxy = window_bounds(ds, t.window)
    meta = {
                        "tile_id": t.tid,
                        "source_uri": t.source_uri,
                        "mosaic_id": t.mid,
                        "tile_size": t.height,
                        "stride": tp.stride,
                        "window": {"x_off": int(t.window.col_off), "y_off": int(t.window.row_off), "w": int(t.width), "h": int(t.height)},
                        "crs": t.crs,
                        "transform": dh.affine_to_list(t_transform),
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
            meta["bounds_wgs84"]={
                            "minx": float(0),
                            "miny": float(0),
                            "maxx": float(0),
                            "maxy": float(0),
                                  }
    except Exception:
        pass

                    

    npy = dh.npy_bytes(out_arr)
    js = dh.json_bytes(meta)
    return npy, js, meta


def cut_mosaic(uri: str,
               man_dir: Path,
               shard_dir: Path, 
               qp: QParams, 
               tp: TParams) -> tuple[str,int,int,int,int]:
    n_seen = 0 
    n_skipped = 0 
    n_errors = 0 
    n_written = 0 
    mosaic_id = ids.uuid_from_path(uri)
    ui.div(f"cutting: {mosaic_id}")
    writer = rwr.ShardWriter(
            out_dir=shard_dir,prefix=mosaic_id,shard_size=tp.shard_size)
    ui.info(f"shardwriter opened for {shard_dir}")
    k = tp.manifest_kind.lower()
    mosaic_man_path = man_dir/(f"{mosaic_id}.parquet" if k == "parquet" else f"{mosaic_id}.csv")
    ui.print(f"tring to write {k} manifest to {mosaic_man_path}...")
    sink = rwr.make_sink(k,mosaic_man_path)
    try:
        ui.print(f"trying to open mosaic at {uri}...")
        with rasterio.open(uri) as ds:
            tile_size = tp.tile_size
            stride = tp.stride
            total_tiles = num_tiles(ds, tile_size, stride) 
            band_bounds = {}
            with ui.progress() as p:
                if qp.scale != "none":
                    band_bounds = sample_band(ds, tile_size, stride, qp, p) 
                t = p.add_task(description="tiling",total=total_tiles)
                for r_i, c_i, win in iter_windows(ds,tp):
                    p.update(t, advance=1)
                    # one tile per iteration
                    n_seen += 1
                    try:
                        tid = ids.gen_tile_id(mosaic_id, r_i, c_i)
                        #cut_tile returns Tile object
                        tile = Tile(
                                tid = tid,
                                mid = mosaic_id,
                                source_uri = uri,
                                row_id = r_i,
                                col_id = c_i,
                                window = win,
                                transform = ds.transform,
                                crs=ds.crs.to_string() if ds.crs else None,
                                )
                        npy, js, meta = cut_tile( tile, ds, qp, tp, band_bounds, writer)
                        writer._write_sample(tid,npy,js)
                        bounds = meta["bounds_wgs84"]
                        manifest_row = rwr.ManifestRow(
                            tile_id=tid,
                            shard=writer.tar_path,
                            key=tid,
                            source_uri=uri,
                            x_off=int(win.col_off),
                            y_off=int(win.row_off),
                            w=int(win.width),
                            h=int(win.height),
                            crs=tile.crs,
                            minx=bounds["minx"],
                            miny=bounds["miny"],
                            maxx=bounds["maxx"],
                            maxy=bounds["maxy"],
                            bands=int(ds.count),
                            dtype=meta["dtype"],
                            )
                        sink._write(manifest_row)
                        n_written += 1 
                    except KeyboardInterrupt:
                        ui.warn("closing shard writer")
                        writer._close()
                        ui.warn("closing manifest")
                        sink._close()
                        raise
                    except Exception as e:
                        ui.error(f"{e}")
                        n_errors += 1
                        continue
    except KeyboardInterrupt:
        ui.warn("closing shard writer")
        ui.warn("closing manifest")
        writer._close()
        sink._close()
        raise
    except Exception as e:
        ui.error(f"{e}")
        n_errors += 1
    finally:
        ui.print("closing shard and manifest writers")
        writer._close()
        sink._close()
    return mosaic_id, n_seen, n_written, n_errors, n_skipped


@dataclass
class Tile:
    tid: str
    mid: str
    source_uri: str
    row_id: int 
    col_id: int
    window: Window
    transform: Affine
    crs: str | None

    @property
    def width(self) -> int:
        return int(self.window.width)

    @property
    def height(self) -> int:
        return int(self.window.height)


