from __future__ import annotations

import argparse
import io
import json
import math
import sys
import tarfile
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds
import csv
import re
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime 
from osgeo import gdal
from osgeo import osr  # SpatialReference + CoordinateTransformation
import argparse
import heapq
import os
from dataclasses import dataclass, field


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

def affine_to_list(a: rasterio.Affine) -> List[float]:
    """Store affine as 6 params [a,b,c,d,e,f]."""
    return [a.a, a.b, a.c, a.d, a.e, a.f]

def list_to_affine(v: Sequence[float]) -> rasterio.Affine:
    return rasterio.Affine(v[0], v[1], v[2], v[3], v[4], v[5])

def npy_bytes(arr: np.ndarray) -> bytes:
    bio = io.BytesIO()
    np.save(bio, arr, allow_pickle=False)
    return bio.getvalue()

def json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def created_at() -> str:
    now = datetime.now()
    return now.isoformat()

