"""whirlwind.ingest.quantize 

    PURPOSE:
        - scaling/quantization routines for tile tensors 
    BEHAVIOR:
        - estemate per band bounds by sampling windows 
        - apply scaling and cast output to dtype 
    PUBLIC:
        - sample_bands(ds, tile_size, stride, qp) -> dict[int, (lo,hi)]
        - quantize_tiler(arr, qp, band_bounds) -> (array, meta) 

"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window

from whirlwind.ingest.params import QParams as QuantizationParams 
from whirlwind.ui.pantalla import PANT



def _quant_dtype(dtype: str) -> np.dtype:
    d = dtype.lower()
    if d == "float32":
        return np.float32
    if d == "uint16":
        return np.uint16
    if d == "uint8":
        return np.uint8
    raise ValueError(f"unsupported dtype: {dtype}")


def _dst_range(dtype: str) -> Tuple[float, float]:
    d = dtype.lower()
    if d == "uint16":
        return 0.0, 65535.0
    if d == "uint8":
        return 0.0, 255.0
    if d == "float32":
        return 0.0, 1.0
    raise ValueError(f"unsupported dtype: {dtype}")


def sample_band(
    ds: rasterio.DatasetReader,
    tile_size: int,
    stride: int,
    qp: QuantizationParams,
    p: Progress()
) -> Dict[int, Tuple[float, float]]:
    if qp.scale == "none":
        return {}

    nb = ds.count
    lo_hi: Dict[int, List[float]] = {b: [] for b in range(1, nb + 1)}
    need = max(1, int(qp.num_samples))

    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    n_tiles = tiles_x * tiles_y

    step = max(1, int(math.sqrt(n_tiles / need)))
    sparse_total = math.ceil(tiles_y / step) * math.ceil(tiles_x / step)
    total = min(need, sparse_total)

    sampled = 0
    sample_task = p.add_task(description="sampling bands", total=min(need,sparse_total))
    for ty in range(0, tiles_y, step):
        y = ty * stride
        for tx in range(0, tiles_x, step):
            p.update(sample_task, advance=1)
            x = tx * stride
            win = Window(x, y, tile_size, tile_size)
            data = ds.read(window=win, out_dtype=np.float32, masked=True)

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

            sampled += 1
            if sampled >= need:
                break
        if sampled >= need:
            break

    out: Dict[int, Tuple[float, float]] = {}
    for b in range(1, nb + 1):
        xs = lo_hi[b]
        out[b] = (0.0, 1.0) if not xs else (min(xs), max(xs))
    return out


def quantize_tile(
    arr: np.ndarray,
    qp: QuantizationParams,
    band_bounds: Dict[int, Tuple[float, float]],
) -> Tuple[np.ndarray, Dict[str, object]]:
    out_dtype = _quant_dtype(qp.dtype)

    if qp.scale == "none":
        if qp.dtype.lower() == "float32":
            return arr.astype(np.float32, copy=False), {"scale": "none", "dtype": "float32"}
        dst_lo, dst_hi = _dst_range(qp.dtype)
        clipped = np.clip(arr, dst_lo, dst_hi)
        return clipped.astype(out_dtype), {"scale": "none", "dtype": qp.dtype.lower(), "clipped_to": [dst_lo, dst_hi]}

    dst_lo, dst_hi = _dst_range(qp.dtype)
    nb = int(arr.shape[0])
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
        src_lo, src_hi = band_bounds.get(b, (0.0, 1.0))
        if not np.isfinite(src_lo) or not np.isfinite(src_hi) or src_hi <= src_lo:
            src_lo, src_hi = 0.0, 1.0

        band = arr[bi]
        s = (band - src_lo) * (dst_hi - dst_lo) / (src_hi - src_lo) + dst_lo
        scaled[bi] = s
        meta["bands"].append({"band": b, "src_lo": float(src_lo), "src_hi": float(src_hi)})

    scaled = np.clip(scaled, dst_lo, dst_hi)

    if qp.dtype.lower() == "float32":
        return scaled.astype(np.float32, copy=False), meta

    return scaled.astype(out_dtype), meta

