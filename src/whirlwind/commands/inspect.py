"""
owns all scan logic
"""
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
# for painting to terminal
from ..ui import paint
# for directory utilities
from ..utils import durs as du 
# for generating, searching file/path ids
from ..utils import ids
from ..utils import geo
from ..utils import rwriters as rwr
from .base import Command 



# SCAN ###############################################
@dataclass
class InspectCommand(Command):
    name: str = "inspect"

    def configure(self, subparser: argparse._SubParsersAction) -> None:
        parser = subparser.add_parser(
                self.name,
                help="Scan a directory and sumarize files",
            )
        parser.add_argument(
                "root", type=str,
                help=" ROOT to be scanned"
            )
        parser.add_argument(
                "--top-n", type=int, default=500,
                help="show top N largest files, default 500"
            )

    def run(self, args: argparse.Namespace) -> int:
        geo._init()
        root = du._get_root_(args.root)
        out = f"{ids.gen_fingerprint(root)}.csv"
        if not root.exists() or not root.is_dir():
            # HANDLE ERROR
            return 2
        csv_path = Path(du._find_home_() / "metadata" / out )
        #return toolbox.dispatch_scan(args)
        if not csv_path.exists():
            # if there is no csv already, write one
            rwr.write_metadata(args.root,out)
        else:
            print(f"csv found")
        stats = inspect_metadata(csv_path)

        return 0
@dataclass
class ScanStats:
    # how many directories, files, and bytes in root
    num_dirs: int = 0
    num_files: int = 0
    total_bytes: int = 0
    largest: List[Tuple[int, str, str, str]] = field(default_factory=list)
    # (size_bytes, uri, dtype, band_count)
    def add_file(self, path: Path, size: int, dtype: str, band_count: str, top_n: int) -> None:
        self.num_files += 1
        self.total_bytes += size
        if top_n > 0:
            item = (size, str(path), dtype, band_count)
            # heap order still driven by size
            if len(self.largest) < top_n:
                heapq.heappush(self.largest, item)
            else:
                if size > self.largest[0][0]:
                    heapq.heapreplace(self.largest, item)

def inspect_metadata(csv_path: Path, top_n: int = 500) -> ScanStats:
    """
    build ScanStats from existing metadata CSV:
    
    currently uses columns:
        uri
        byte_size
        dtype
        band_count
    populates:
        num_files
        total_btyes
        largest()
    with paint.progress("running scan on",root) as progress:
        task = paint.new_task(progress, "scan", total=None) 
        for dirpath, dirnames, filenames in os.walk(root):
            paint.advance(progress,task,1)
    paint.completed_msg("scan")
    paint.terminal(f"[[bold yellow]{stats.num_dirs}[/bold yellow]] directories scanned from {root}","center")
    paint.divider()

    """
    stats = ScanStats()
    parent_dirs = set()

    if not csv_path.exists():
        paint.error_msg(f"no csv to load at: {csv_path}")
        return stats
    with open(csv_path) as f:
        r = csv.reader(f)
        n_rows = sum(1 for _ in r) - 1
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        with paint.progress("scanning: ", csv_path.name) as progress:
            task = paint.new_task(progress, "scan", total=n_rows)
            for row in r:
                paint.advance(progress, task, 1)
                uri = (row.get("uri") or "").strip()
                uri = Path(uri).name
                if not uri:
                    continue
                size_s = (row.get("byte_size") or "").strip()
                try:
                    size=int(size_s) if size_s else 0
                except ValueError:
                    size = 0 
                dtype = (row.get("dtype") or "").strip()
                band_count = (row.get("band_count") or "").strip()
                stats.num_files += 1 
                stats.total_bytes += size 

                try:
                    parent_dirs.add(str(Path(uri).parent))
                except Exception:
                    pass

                # maintain top-N largest
                if top_n > 0:
                    item = (size, uri, dtype, band_count)
                    if len(stats.largest) < top_n:
                        heapq.heappush(stats.largest, item)
                    else:
                        if size > stats.largest[0][0]:
                            heapq.heapreplace(stats.largest, item)

    paint.completed_msg("scan")
    paint.divider()

    stats.num_dirs = len(parent_dirs)
    return stats

