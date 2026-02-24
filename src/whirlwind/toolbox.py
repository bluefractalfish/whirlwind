
"""
toolbox.py
"""

from __future__ import annotations

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
from . import paint

def dispatch(args: argparse.Namespace) -> int:
    gdal.DontUseExceptions()
    if args.cmd == "scan":
        log("--scan--------------------------------------------------------")
        with paint.status("SCANNING"):
            return scan(args)

#============# 
#    SCAN    # 
#============#
def scan(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    out = f"scan_metadata_{gen_fingerprint(root)}.csv"
    if not root.exists() or not root.is_dir():
        error = f"not a directory you can scan: {root}"
        paint.error_msg(error)
        log(error+"returned error code 2")
        return 2 
    log(f"directory {root} scanned as root")  
    write_metadata(args.root,out)
    csv_path = Path(find_root()/ "metadata" / out)
    stats = scan_from_metadata(csv_path)
    # for walking system directly
    #stats = scan_directory(root,top_n=args.top_n)

    render_scan_report(root,stats)
    paint.info(f"csv written to: {out}")
    log(f"{out} written")
    log("0")
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

def load_metadata_csv(csv_path: Path, key: str = "uri") -> Dict[str, Dict[str,str]]:
    """
    load scan metadata csv into index: key ---> full row ductionary 
    """
    idx: Dict[str, Dict[str, str]] = {}
    if not csv_path.exists():
        paint.error(f"no csv to load at: {csv_path}")
        return idx
       
    with open(csv_path,newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            k = row.get(key, "")
            if not k:
                continue
            idx[k] = row
            # store full row
    return idx
            
#===#
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
    """
    stats = ScanStats()
    parent_dirs = set()

    if not csv_path.exists():
        paint.error_msg(f"no csv to load at: {csv_path}")
        return stats
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
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

    stats.num_dirs = len(parent_dirs)
    return stats

#===#
def scan_directory(root: Path, top_n: int = 500) -> ScanStats:
    """ only use this when no csv has been generated or isnt present
        for better efficiency and architectural coherence, load scanned metadata
        first then read from the csv"""
    stats = ScanStats()

    with paint.progress("running scan on",root) as progress:
        task = paint.new_task(progress, "scan", total=None) 
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
    inv.add_row("total size", format_bytes(stats.total_bytes))

    if stats.largest:
        largest_tbl = paint.set_table()
        largest_tbl.add_column("uri", justify="left")
        largest_tbl.add_column("size", justify="right")
        largest_tbl.add_column("dtype", justify="center")
        largest_tbl.add_column("bands", justify="center")
        for size, uri, dtype, bands in sorted(stats.largest, key=lambda x: x[0], reverse=True):
            largest_tbl.add_row(
                    paint.text(
                        uri,
                        style_by_size(size)
                        ),
                    paint.text(
                        format_bytes(size),
                        style_by_size(size)
                        ),
                        dtype, 
                        bands,
                    )

    content = paint.group([inv,largest_tbl], f"summary of scan on {root}")
    paint.divider() 
# ----------------------------
# helpful tools
# ----------------------------
def style_by_size(nbytes:int) -> str:
    gb = 1024 ** 3 
    mb = 1024 ** 2 
    if nbytes >= 50 * gb:
        return "bold purple"
    elif nbytes >= 5 * gb:
        return "red"
    elif nbytes >= 2 * gb:
        return "orange1"
    elif nbytes >= 1 * gb:
        return "yellow"
    elif nbytes >= 50 * mb:
        return "green3"
    return "white"
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

def gen_fingerprint(path: str | Path) -> str:
    "generate deterministic fingerprint from path, to use in metadata naming"
    p = Path(path)
    st = p.stat()
    pl = f"{st.st_size}-{st.st_mtime_ns}"
    return hashlib.blake2b(pl.encode(),digest_size=6).hexdigest()


def iter_tifs(root: Path) -> Iterable[Path]:
    """
    Recursively yield .tif/.tiff file paths under `root`.
    """
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".tif", ".tiff"):
            yield p


def write_metadata(input_dir: str, out_csv: str, columns: Optional[List[str]] = None) -> None:
    """
    Walk `input_dir` consisting of mosaics, extract metadata for each tif/tiff, write CSV to `out_csv`.

    If `columns` is None, a default mosaic_stage-compatible column list is used.
    """
    input_path = Path(input_dir)
    root = find_root()
    output_path = Path(root/"metadata"/out_csv)
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

    log(f"columns extracted: {columns}")
    for tif in iter_tifs(input_path):
        rows.append(extract_metadata(str(tif), columns))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            # Ensure all requested columns exist; fill missing with ""
            w.writerow({k: r.get(k, "") for k in columns})

def log(msg: str, log_path: Path | None = None) -> None:
    root = find_root()
    default_log_path = root / "logs" / "wind.log"
    path = (log_path or default_log_path).resolve()
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    ln = f"{timestamp} | {msg} \n"
    with path.open("a", encoding="utf-8") as f:
        f.write(ln)

def find_root(start: Path | None = None, markers: Iterable[str] = (".git", "pyproject.toml")) -> Path:
    """
    Walk upward from `start` (default: this file's directory) until a marker is found.
    Markers can be files or directories.
    """
    here = (start or Path(__file__).resolve()).resolve()
    if here.is_file():
        here = here.parent

    for p in (here, *here.parents):
        for m in markers:
            if (p / m).exists():
                return p
    # Fallback: last resort, anchor to this file's directory
    return here
