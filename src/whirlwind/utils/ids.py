
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

def uuid_from_path(uri:str)->str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL,uri))
def gen_fingerprint(path: str | Path) -> str:
    "generate deterministic fingerprint from path, to use in metadata naming"
    p = Path(path)
    st = p.stat()
    pl = f"{st.st_size}-{st.st_mtime_ns}"
    return hashlib.blake2b(pl.encode(),digest_size=6).hexdigest()
def gen_tile_id(mosaic_id: str, row: int, col: int) -> str:
    return f"{mosaic_id}_r{row:07d}_c{col:07d}"

