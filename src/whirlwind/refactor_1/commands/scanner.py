"""
WHIRLWIND scanner (v1): scan unorganized directory and retrieve metadata

Design goals: 
    - separate shared utilities into paint and toolbox 
    - generate metadata as csv and read file size, path, dtype, etc from csv
    - render scan report to terminal
    - save metadata as source manifest
Outputs (default):
    - csv containing source mosaic metadata 
    - scan report of top-n largest files before compression,
        number of directories, tif files, etc.  

"""
from . import toolbox
from .import paint
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


#============# 
#    SCAN    # 
#============#
def scan(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    out = f"scan_{toolbox.gen_fingerprint(root)}.csv"
    if not root.exists() or not root.is_dir():
        error = f"not a directory you can scan: {root}"
        paint.error_msg(error)
        toolbox.log(error+"returned error code 2")
        return 2 
    toolbox.log(f"directory {root} scanned as root")  
    csv_path = Path(toolbox.find_root()/ "metadata" / out)
    if not csv_path.exists():
        toolbox.write_metadata(args.root,out)
        paint.info(f"csv written to: {csv_path}")
        toolbox.log(f"{out} written")
    else:
        paint.ok(f"CSV FOUND AT: \n  {csv_path} ")
    stats = scan_from_metadata(csv_path)
    # for walking system directly
    #stats = scan_directory(root,top_n=args.top_n)

    render_scan_report(csv_path.name,stats)
    toolbox.log("0")
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

def scan_from_metadata(csv_path: Path, top_n: int = 500) -> ScanStats:
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

#===#
def scan_directory(root: Path, top_n: int = 500) -> ScanStats:
    """ only use this when no csv has been generated or isnt present
        for better efficiency and architectural coherence, load scanned metadata
        first then read from the csv"""
    stats = ScanStats()
    n_files = sum(1 for p in root.iterdir() if p.is_file())
    with paint.progress("scanning: ",root) as progress:
        task = paint.new_task(progress, "scan", total=n_files) 
        for dirpath, dirnames, filenames in os.walk(root):
            stats.num_dirs += 1
            paint.advance(progress,task,1)

            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() not in ('.tif','.tiff'):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                stats.add_file(p, st.st_size, top_n=top_n)
    paint.completed_msg("scan")
    paint.terminal(f"[[bold yellow]{stats.num_dirs}[/bold yellow]] directories scanned from {root}","center")
    paint.divider()

    return stats
#===#
def render_scan_report(root: Path, stats: ScanStats, largest: bool=True, tree: bool=False) -> None:
    if tree:
        paint.print_dir_tree_panel(
            root,
            title="scanned path",
            max_depth=5,
            max_entries_per_dir=100,
            show_files=True,
        )

    inv = paint.set_table()
    inv.add_column("metric")
    inv.add_column("value")
    inv.add_row("directories", str(stats.num_dirs))
    inv.add_row("files", str(stats.num_files))
    inv.add_row("total size", toolbox.format_bytes(stats.total_bytes))

    largest_tbl = paint.set_table()
    if stats.largest and largest:
        largest_tbl = paint.set_table()
        largest_tbl.add_column("uri", justify="left")
        largest_tbl.add_column("size", justify="right")
        largest_tbl.add_column("dtype", justify="center")
        largest_tbl.add_column("bands", justify="center")
        for size, uri, dtype, bands in sorted(stats.largest, key=lambda x: x[0], reverse=True):
            largest_tbl.add_row(
                    paint.text(
                        uri,
                        toolbox.style_by_size(size)
                        ),
                    paint.text(
                        toolbox.format_bytes(size),
                        toolbox.style_by_size(size)
                        ),
                        dtype, 
                        bands,
                    )
    
    content = paint.group([inv,largest_tbl], f"summary of scan on {root}")
    paint.divider() 
