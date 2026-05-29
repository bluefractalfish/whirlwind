
"""whirlwind.commands.tile.quantize 

    PURPOSE:
        - scaling/quantization routines for tile tensors 
    BEHAVIOR:
        - estemate per band bounds by sampling windows 
        - apply scaling and cast output to dtype 
        - takes in raster and emits metadata for quantizing 
    PUBLIC:
        - sample_bands(ds, tile_size, stride, qp) -> dict[int, (lo,hi)]
        - quantize_tiler(arr, qp, band_bounds) -> (array, meta) 

OR 

    operate on a per tile basis. takes in 1 tile and quantizes/samples bands? 
    
    this way i can have a command like: tile 45 65 quantize or sample? 

    tile command could work per tile.... so mosaic tile could call "TileQuantizeCommand(x,y,config)"
"""
from __future__ import annotations 

from pathlib import Path 
from typing import Any, Dict 
from rich.traceback import install 
from whirlwind.tools.pathfinder import build_path
from whirlwind.io.inputs import iter_uris
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from dataclasses import dataclass 
from whirlwind.ui import face


from typing import Optional, Tuple, Union, List, Any, Dict
from whirlwind.io.out import append_jsonl
from whirlwind.lab.ingest_experiment import list_configs 


import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from whirlwind.geo.windows import window_bounds
from whirlwind.tools import datamonkeys as dm

import math
from typing import Callable, Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window

from whirlwind.ui import face

########################
## COMMAND CLASS HEAD ##
########################

class TileQuantizeCommand(Command):
    name = "quantize"

    def run(self, tokens: List[str], config: Config) -> int:
        ...



######################
## PARAM CONTAINERS ##
######################

@dataclass(frozen=True)
class QParams:
    dtype: str
    scale: str
    p_low: float
    p_high: float
    per_band: bool
    stats: str
    num_samples: int
    

    def validate(self) -> None:
        if self.scale == "percentile":
            if not (0.0 <= self.p_low < self.p_high <= 100.0):
                face.error("param init error: percentile scaling requires 0 <= p_low <p_high <= 100")
        if self.num_samples <= 0:
                face.error("param init error: num_samples must be > 0")
    def print_table(self) -> None:
        cols = ["quant params", "value"]
        rows = [ 
                ["dtype",self.dtype],
                ["scaling", self.scale],
                ["low", self.p_low],
                ["high", self.p_high],
                ["per band", self.per_band],
                ["stats", self.stats],
                ["sampling", self.num_samples]
                ]

        face.table(cols,rows)




############################
## SPECIAL LITTLE HELPERS ##
############################

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

################
## CORE LOGIC ##
################

def sample_band(
    ds: rasterio.DatasetReader,
    tile_size: int,
    stride: int,
    qp: QParams,
    p: rich.Progress() ) -> Dict[int, Tuple[float, float]]:

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
    total_smpls = min(need, sparse_total)

    sampled = 0
    sample_task = p.add_task(description=f"sampling {nb} bands", total=total_smpls)
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
    qp: QParams,
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

