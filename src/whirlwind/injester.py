"""
WHIRLWIND ingest pipeline (v1): ile whole mosaics into WebDataset shards + Parquet manifest.

Design goals:
- NEVER read full rasters into memory
- Windowed reads only 
- Deterministic, non-overlapping grid (stride == tile_size by default)
- Sharded output for ML scalability (tens/hundreds of thousands of tiles)
- Per-tile georeferencing metadata preserved (CRS + affine transform + bounds)
- Manifest written as Parquet (fallback to CSV if pyarrow unavailable)

Outputs (default):
out/
  shards/
    mosaic_id-000.tar
    mosaic_id-001.tar
    ...
  manifest.parquet   (or manifest.csv)
  ingest.json        (run config + summary)

Each tile sample in WebDataset tar contains:
  <tile_id>.npy      : array in (bands, H, W), dtype float32/uint16/uint8
  <tile_id>.json     : metadata (crs, transform, bounds, window, source_uri, etc.)

Dependencies:
- rasterio
- numpy
- pyarrow  (for parquet manifest; else CSV)

Install:
  pip install rasterio numpy rich pyarrow
"""
import argparse
import csv
import io
import json
import math
import os
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from . import toolbox
from . import paint

##########
##INGEST##
##########

def ingest(args):
    if args.ingest_cmd == "tiles":
        stride = args.stride if args.stride is not None else args.tile_size
        out_dir = Path(args.out).expanduser().resolve()
        uris = list(toolbox.iter_uris(args.input,args.input_csv)) # read paths only, not raster data
        try: 
            return ingest_tiles(    
                    uris=uris,
                    out_dir=out_dir,
                    tile_size=args.tile_size,
                    stride=stride,
                    drop_partial=args.drop_partial,
                    shard_size=args.shard_size,
                    shard_prefix=args.shard_prefix,
                    manifest_kind=args.manifest,
                    dtype=args.dtype,
                    scale=args.scale,
                    p_low=args.p_low,
                    p_high=args.p_high,
                    stats=args.stats,
                    num_samples=args.num_samples,
                    resume=args.resume,
                    )
        except KeyboardInterrupt:
            toolbox.log("130")
            return 130
          
    return 2


##################
## QUANTIZATION ##
##################

@dataclass(frozen=True)
class QuantizationParams:
    dtype: str # "float32" | "uint16" | "uint8"
    scale: str= "none" # "none" | "minmax" | "percentile"
    p_low: float = 0.5
    p_high: float = 99.5
    per_band: bool = True
    stats: str = "sample" # "sample"  | "compute" (compute = full pass; slower)
    num_samples: int = 2048 # number of sampled windows per band 

def sample_band(
        ds: rasterio.DatasetReader,
        tile_size: int,
        stride: int,
        qp: QuantizationParams,) -> Dict[int, Tuple[float,float]]:
    """
    approx per band bounds for scaling. avoid full read.
    runs whenever qp.scale != none
    strategy:
        1 sample windows as a deterministic grid stride
        2 stop after num_samples per band
        3 return {band index: (lo, hi)}
    """
    if qp.scale == "none":
        toolbox.log(f"sample_band called for qp with scale=none")
        return {}
    nb = ds.count
    lo_hi: Dict[int, List[float]] = {b: [] for b in range(1, nb+1)}
    need = max(1, qp.num_samples)

    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    n_tiles = tiles_x * tiles_y

    # Deterministic sparse sampling of tile origins
    step = max(1, int(math.sqrt(n_tiles / need)))
    sampled = 0

    for ty in range(0, tiles_y, step):
        y = ty * stride
        for tx in range(0, tiles_x, step):
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
        qp: QuantizationParams,
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
    out_dtype = toolbox._quant_dtype(qp.dtype)
    
    if qp.scale == "none":
        if qp.dtype.lower() == "float32":
            return arr.astype(np.float32, copy=False), {"scale": "none", "dtype": "float32"}
        dst_lo, dst_hi = toolbox._dst_range(qp.dtype)
        clipped = np.clip(arr, dst_lo, dst_hi)
        return clipped.astype(out_dtype), {"scale": "none", "dtype": qp.dtype.lower(), "clipped_to": [dst_lo, dst_hi]}
    # scale requested 
    dst_lo, dst_hi = toolbox._dst_range(qp.dtype)
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

#############################
## WEBDATASET SHARD WRITER ##
#############################

@dataclass
class ShardWriter:
    out_dir: Path
    prefix: str
    shard_size: int
    shard_index: int = 1 
    sample_in_shard: int = 0 
    tar: Optional[tarfile.TarFile] = None
    tar_path: Optional[Path] = None

    def _open_next(self) -> None:
        if self.tar is not None:
            self.tar.close()
        name = f"{self.prefix}-{self.shard_index:03d}.tar"
        self.tar_path = self.out_dir / name
        self.tar = tarfile.open(self.tar_path, "w")  # uncompressed tar for faster IO
        self.sample_in_shard = 0
        self.shard_index += 1

    def write_sample(self, key: str, npy: bytes, meta_json: bytes) -> Tuple[str, str]:
        """
        Write <key>.npy and <key>.json into current shard tar.
        Returns: (shard_filename, key)
        """
        if self.tar is None or self.sample_in_shard >= self.shard_size:
            self._open_next()

        assert self.tar is not None
        assert self.tar_path is not None

        npy_name = f"{key}.npy"
        ti = tarfile.TarInfo(npy_name)
        ti.size = len(npy)
        ti.mtime = int(time.time())
        self.tar.addfile(ti, io.BytesIO(npy))

        js_name = f"{key}.json"
        tj = tarfile.TarInfo(js_name)
        tj.size = len(meta_json)
        tj.mtime = int(time.time())
        self.tar.addfile(tj, io.BytesIO(meta_json))

        self.sample_in_shard += 1
        return (self.tar_path.name, key)

    def close(self) -> None:
        if self.tar is not None:
            self.tar.close()
            self.tar = None

#####################
## MANIFEST WRITER ##
#####################

@dataclass
class ManifestRow:
    tile_id: str
    shard: str
    key: str 
    source_uri: str
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

class ManifestSink:
    def write(self, row: ManifestRow) -> None:
        raise NotImplentedError
    def close(self) -> None:
        raise NotImplentedError

class CSVManifestSink(ManifestSink):
    def __init__(self, path: Path):
        self.path = path
        toolbox.makedir(path.parent)
        self.f = open(path, "w", newline="", encoding="utf-8")
        self.w = csv.DictWriter(
            self.f,
            fieldnames=[
                "tile_id", "shard", "key", "source_uri", "x_off", "y_off", "w", "h", "crs",
                "minx", "miny", "maxx", "maxy", "bands", "dtype",
            ],
        )
        self.w.writeheader()

    def write(self, row: ManifestRow) -> None:
        self.w.writerow(row.__dict__)

    def close(self) -> None:
        self.f.close()


class ParquetManifestSink(ManifestSink):
    def __init__(self, path: Path):
        self.path = path
        toolbox.makedir(path.parent)
        self.rows: List[dict] = []
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception as e:
            raise RuntimeError(f"pyarrow required for parquet manifest: {e}") from e
        self.pa = pa
        self.pq = pq

    def write(self, row: ManifestRow) -> None:
        self.rows.append(row.__dict__)

    def close(self) -> None:
        table = self.pa.Table.from_pylist(self.rows)
        self.pq.write_table(table, str(self.path))


def make_manifest_sink(kind: str, path: Path) -> ManifestSink:
    k = kind.lower()
    if k == "csv":
        return CSVManifestSink(path)
    if k == "parquet":
        return ParquetManifestSink(path)
    if k == "none":
        class _Null(ManifestSink):
            def write(self, row: ManifestRow) -> None:
                return

            def close(self) -> None:
                return
        return _Null()
    raise ValueError(f"unknown manifest kind: {kind}")

#########################
## CORE INGESTION LOGIC##
#########################

def iter_windows(ds: rasterio.DatasetReader, 
                 tile_size: int, stride: int, 
                 drop_partial: bool) -> Iterator[Tuple[int, int, Window]]:
    """
    deterministic row major iteration of windows. 
    returns (row_indx, col_indx, window)
    """
    max_x = ds.width
    max_y = ds.height
    
    if drop_partial:
        x_stops = range(0, max_x - tile_size + 1, stride)
        y_stops = range(0, max_y - tile_size + 1, stride)
    else:
        x_stops = range(0, max_x, stride)
        y_stops = range(0, max_y, stride)

    for ry, y in enumerate(y_stops):
        for cx, x in enumerate(x_stops):
            w = tile_size if (x + tile_size <= max_x) else (max_x-x)
            h = tile_size if (y + tile_size <= max_y) else (max_y-y)
            if drop_partial and (w != tile_size or h != tile_size):
                continue
            yield ry, cx, Window(x, y, w, h)

def ingest_tiles(
    uris: Iterable[str],
    out_dir: Path,
    tile_size: int,
    stride: int,
    drop_partial: bool,
    shard_size: int,
    shard_prefix: str,
    manifest_kind: str,
    dtype: str,
    scale: str,
    p_low: float,
    p_high: float,
    stats: str,
    num_samples: int,
    resume: bool,
) -> int:
    toolbox.makedir(out_dir)
    shards_dir = out_dir/ "shards"
    toolbox.makedir(shards_dir)

    manifest_path = out_dir / ("manifest.parquet" if manifest_kind.lower() == "parquet" else "manifest.csv")
    sink = make_manifest_sink(manifest_kind, manifest_path)

    qp = QuantizationParams(dtype=dtype, scale=scale,
                            p_low=p_low, p_high=p_high,
                            per_band=True,stats=stats,
                            num_samples=num_samples)
    # resume support for csv
    seen: set[str] = set()
    if resume and manifest_path.exists() and manifest_kind.lower() == "csv":
        with open(manifest_path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                tid = (row.get("tile_id") or "").strip()
                if tid:
                    seen.add(tid)
    n_tiles = 0 
    n_written = 0 
    n_skipped = 0 
    n_errors = 0
    paint.ok("ingesting tiles")
    toolbox.log("ingesting tiles started")
    
    with paint.progress("tiling mosaics to", out_dir) as progress:
        task = paint.new_task(progress, "ingesting mosaics...", total=len(uris))
        for uri in uris:
            paint.advance(progress, task, 1)

            uri = uri.strip()
            if not uri: 
                continue
            mosaic_id = toolbox.uuid_from_path(uri)
            writer = ShardWriter(out_dir=shards_dir, prefix=mosaic_id, shard_size=shard_size)
            try:
                with rasterio.open(uri) as ds:
                    crs_str = ds.crs.to_string() if ds.crs else ""
                    bands = ds.count


                    # Bounds for scaling computed once per mosaic when scaling requested
                    band_bounds: Dict[int, Tuple[float, float]] = {}
                    if qp.scale != "none":
                        band_bounds = sample_band(ds, tile_size, stride, qp)

                    for r_i, c_i, win in iter_windows(ds, tile_size, stride, drop_partial):
                        tid = toolbox.gen_tile_id(mosaic_id, r_i, c_i)
                        n_tiles += 1

                        if resume and tid in seen:
                            n_skipped += 1
                            continue

                        try:
                            # Read window only; masked to handle nodata robustly
                            arr = ds.read(window=win, masked=True, out_dtype=np.float32)  # (bands, h, w)

                            # Fill masked values with 0 for ML tensors; retain mask info optionally
                            if np.ma.isMaskedArray(arr):
                                arr = np.ma.filled(arr, 0.0).astype(np.float32, copy=False)
                            else:
                                arr = arr.astype(np.float32, copy=False)

                            # Apply scaling/quantization (can output float32 normalized or uint*)
                            out_arr, q_meta = quantize_tile(arr, qp, band_bounds)

                            # Build per-tile georef metadata
                            t_transform = rasterio.windows.transform(win, ds.transform)
                            minx, miny, maxx, maxy = toolbox.window_bounds(ds, win)

                            meta = {
                                "tile_id": tid,
                                "source_uri": uri,
                                "mosaic_id": mosaic_id,
                                "tile_size": tile_size,
                                "stride": stride,
                                "window": {"x_off": int(win.col_off), "y_off": int(win.row_off), "w": int(win.width), "h": int(win.height)},
                                "crs": crs_str,
                                "transform": toolbox.affine_to_list(t_transform),
                                "bounds": {"minx": float(minx), "miny": float(miny), "maxx": float(maxx), "maxy": float(maxy)},
                                "bands": int(bands),
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
                            except Exception:
                                pass

                            # Serialize and write to shard
                            npy = toolbox.npy_bytes(out_arr)
                            js = toolbox.json_bytes(meta)
                            shard_name, key = writer.write_sample(tid, npy, js)

                            # Manifest row
                            sink.write(
                                ManifestRow(
                                    tile_id=tid,
                                    shard=shard_name,
                                    key=key,
                                    source_uri=uri,
                                    x_off=int(win.col_off),
                                    y_off=int(win.row_off),
                                    w=int(win.width),
                                    h=int(win.height),
                                    crs=crs_str,
                                    minx=float(minx),
                                    miny=float(miny),
                                    maxx=float(maxx),
                                    maxy=float(maxy),
                                    bands=int(bands),
                                    dtype=str(out_arr.dtype),
                                )
                            )

                            n_written += 1

                        except KeyboardInterrupt:
                            writer.close()
                            sink.close()
                            toolbox.log("-1 | keyboard interrupt")
                            raise
                        except Exception as e:
                            n_errors += 1
                            toolbox.log(f"ERROR | tile failed | uri={uri} | tile_id={tid} | {type(e).__name__}: {e}")
                            continue

            except KeyboardInterrupt:
                writer.close()
                sink.close()
                raise
            except Exception as e:
                n_errors += 1
                toolbox.log(f"ERROR | raster failed | uri={uri} | {type(e).__name__}: {e}")
                continue
            finally:
                writer.close()
                sink.close()

        summary = {
            "finished_at": toolbox.utc_now(),
            "out_dir": str(out_dir),
            "tile_size": tile_size,
            "stride": stride,
            "drop_partial": drop_partial,
            "dtype": dtype,
            "scale": scale,
            "p_low": p_low,
            "p_high": p_high,
            "manifest": str(manifest_path),
            "shard_size": shard_size,
            "shard_prefix": shard_prefix,
            "tiles_total_seen": n_tiles,
            "tiles_written": n_written,
            "tiles_skipped": n_skipped,
            "errors": n_errors,
        }

        (out_dir / "ingest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        toolbox.log(f"ingestion tiles done | written={n_written} skipped={n_skipped} errors={n_errors}")
        return 0

