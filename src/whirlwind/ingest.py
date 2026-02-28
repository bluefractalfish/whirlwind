"""
WHIRLWIND ingest pipeline (v1): tile whole mosaics into WebDataset shards + Parquet manifest.

Design goals:
- NEVER read full rasters into memory
- Windowed reads only (tile-by-tile)
- Deterministic, non-overlapping grid (stride == tile_size by default)
- Sharded output for ML scalability (tens/hundreds of thousands of tiles)
- Per-tile georeferencing metadata preserved (CRS + affine transform + bounds)
- Manifest written as Parquet (fallback to CSV if pyarrow unavailable)

Outputs (default):
out/
  shards/
    tiles-000000.tar
    tiles-000001.tar
    ...
  manifest.parquet   (or manifest.csv)
  ingest.json        (run config + summary)

Each tile sample in WebDataset tar contains:
  <tile_id>.npy      : array in (bands, H, W), dtype float32/uint16/uint8
  <tile_id>.json     : metadata (crs, transform, bounds, window, source_uri, etc.)

Dependencies:
- rasterio
- numpy
- (optional) pyarrow  (for parquet manifest; else CSV)

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

