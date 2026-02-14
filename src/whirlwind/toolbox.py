
"""
toolbox.py

helper library for 
    - building staging-table CSVs from GeoTIFF/COG fieldnames

"""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime 
from osgeo import gdal
from osgeo import osr  # SpatialReference + CoordinateTransformation
import argparse
import heapq
import os
from dataclasses import dataclass, field
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn
)
from rich.table import Table
from rich.text import Text

console = Console()


#============# 
#    SCAN    # 
#============#

@dataclass
class ScanStats:
    # how many directories, files, and bytes in root
    num_dirs: int = 0
    num_files: int = 0
    total_bytes: int = 0
    largest: List[Tuple[int, str]] = field(default_factory=list)

    def add_file(self, path: Path, size: int, top_n: int) -> None:
        self.num_files += 1
        self.total_bytes += size
        if top_n > 0:
            item = (size, str(path))
            if len(self.largest) < top_n:
                heapq.heappush(self.largest, item)
            else:
                if size > self.largest[0][0]:
                    heapq.heapreplace(self.largest, item)
#===#
def scan_directory(root: Path, top_n: int = 100) -> ScanStats:
    stats = ScanStats()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]running scan[/bold]"),
        TextColumn("{task.completed} dirs"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("scan", total=None)

        for dirpath, dirnames, filenames in os.walk(root):
            stats.num_dirs += 1
            progress.update(task, advance=1)

            for name in filenames:
                p = Path(dirpath) / name
                try:
                    st = p.stat()
                except OSError:
                    continue
                stats.add_file(p, st.st_size, top_n=top_n)

    return stats
#===#
def render_scan_report(root: Path, stats: ScanStats) -> None:

    inv = Table(title="inventory", header_style="bold magenta")
    inv.add_column("metric", style="bold")
    inv.add_column("value", justify="right")
    inv.add_row("directories", str(stats.num_dirs))
    inv.add_row("files", str(stats.num_files))
    inv.add_row("total size", format_bytes(stats.total_bytes))

    if stats.largest:
        largest = Table(title="largest files", header_style="bold yellow")
        largest.add_column("size", justify="right")
        largest.add_column("path", overflow="fold")
        for size, path in sorted(stats.largest, key=lambda x: x[0], reverse=True):
            largest.add_row(format_bytes(size), path)
        
    content = Group(largest,inv)
    console.print(Panel.fit(content, title=f"summary of scan on {root}"))
        
# ----------------------------
# helpful tools
# ----------------------------
def format_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    v = float(n)
    for u in units:
        if v < 1024.0 or u == units[-1]:
            return f"{v:.2f} {u}" if u != "B" else f"{int(v)} {u}"
        v /= 1024.0
    return f"{n} B"
def uuid_from_path(uri:str)->str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL,uri))
def get_dtype(gdal_type: int) -> str:
    """
    Convert a GDAL datatype enum (e.g., gdal.GDT_UInt16) to a readable string (e.g., "UInt16").
    """
    return gdal.GetDataTypeName(gdal_type) or ""
#---#
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
#---#
def get_crs(ds: gdal.Dataset) -> str:
    """Return CRS as WKT, or empty string if missing."""
    return ds.GetProjection() or ""
#---#
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
#---#
def get_raster_shape(ds: gdal.Dataset) -> Tuple[str, str, str]:
    """
    Return (pixel_width, pixel_height, band_count) as strings (staging-friendly).
    """
    return str(ds.RasterXSize), str(ds.RasterYSize), str(ds.RasterCount)
#---#
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
#---#
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


# ----------------------------
# Footprint computation
# ----------------------------

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


# ----------------------------
# Main extraction
# ----------------------------

def parse_columns(path):
    """
    NEEDS WORK
    parse column names from file, returning dict
    expects:
    ---
    table1
    ---
    a 
    b 
    ---
    table2
    ---
    c 
    ---
    returns: {"table1": 'a','b'
              "table2": 'c'}
    """
    out = {}
    _key = None
    collect = False
    i = 0
    with open(path,"r") as f:
        lines = [ln.strip() for ln in f]
    return lines

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
        out["mosaic_id"]=uuid_from_path(uri)
    # always allow uri
    if "uri" in columns:
        out["uri"] = uri

    if "byte_size" in columns:
        out["byte_size"] = get_byte_size(uri)

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
        out["created_at"] = created_at()

    return out

def created_at() -> str:
    now = datetime.now()
    return now.isoformat()

def iter_tifs(root: Path) -> Iterable[Path]:
    """
    Recursively yield .tif/.tiff file paths under `root`.
    """
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".tif", ".tiff"):
            yield p


def write_csv_mosaics(input_dir: str, out_csv: str, columns: Optional[List[str]] = None) -> None:
    """
    Walk `input_dir` consisting of mosaics, extract metadata for each tif/tiff, write CSV to `out_csv`.

    If `columns` is None, a default mosaic_stage-compatible column list is used.
    """
    input_path = Path(input_dir)
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

    for tif in iter_tifs(input_path):
        rows.append(extract_metadata(str(tif), columns))

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            # Ensure all requested columns exist; fill missing with ""
            w.writerow({k: r.get(k, "") for k in columns})

def run(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="whirlwind")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan a directory and summarize files")
    scan.add_argument("root", type=str, help="Root directory to scan")
    scan.add_argument("--top-n", type=int, default=10, help="Show top N largest files (0 disables)")

    args = p.parse_args(argv)

    if args.cmd == "scan":
        root = Path(args.root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            console.print(f"[bold red]error:[/bold red] not a directory: {root}")
            return 2

        stats = scan_directory(root, top_n=args.top_n)
        render_scan_report(root, stats)
        return 0

    return 1


