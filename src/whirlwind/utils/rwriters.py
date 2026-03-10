
from __future__ import annotations

import argparse
import io
import json
import math
import sys
import tarfile
import time
from dataclasses import dataclass, field
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
from ..ui import paint
from . import durs as du 
from . import geo

def write_metadata(input_dir: str, out_csv: str, columns: Optional[List[str]] = None) -> None:
    """
    Walk `input_dir` consisting of mosaics, extract metadata for each tif/tiff, write CSV to `out_csv`.

    If `columns` is None, a default mosaic_stage-compatible column list is used.
    """
    input_path = Path(input_dir)
    output_path = Path(du._find_home()/"metadata"/out_csv)
    rows: List[Dict[str, Any]] = []

    if columns is None:
        columns = [
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
            "created_at"
        ]

    n_files = sum(1 for p in input_path.rglob("*") if p.is_file())
    with paint.progress("extracting metadata from", input_dir) as progress:
        task = paint.new_task(progress, "extracting...", total=n_files)
        for tif in _search_ext(input_path):
            paint.advance(progress,task,1)
            rows.append(geo.extract_metadata(str(tif), columns))
    paint.completed_msg("extraction",)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            # Ensure all requested columns exist; fill missing with ""
            w.writerow({k: r.get(k, "") for k in columns})



def _search_ext(root: Path, extensions: List[str]=(".tif", ".tiff")) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            yield p
