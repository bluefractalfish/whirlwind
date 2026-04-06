""" whirlwind.io.metadata 

    PURPOSE: 
        - write directory level mosaic metadata CSVs 
    BEHAVIOR:
        - recursively find files under input directroy 
        - extract metadata for each file via geo.metadata.extract_metadata 
        - write CSV under output 
    PUBLIC:
        # for mosaics
        - write_mosaic_metadata(input_dir, out_csv, columns)

"""


from __future__ import annotations 

import csv 
from pathlib import Path 
from typing import Dict, Iterable, List, Optional 

from whirlwind.interfaces.geo.metadata import extract 
from whirlwind.tools import pathfinder as pf 
from whirlwind.tools.timer import timed 
from whirlwind.io.out import write_csv 
from whirlwind.ui import face 

DEFAULT_MOSAIC_COLUMNS: List[str] = [ 
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
             "created_at",
             ]

DEFAULT_CATALOG_COLUMNS: List[str] = [
        "uri", 
        "mosaic_id",
        "pixel_width",
        "pixel_height",
        "band_count",
        "dtype",
        "crs"
    ]


def write_mosaic_metadata(input_dir_name: str, 
                         out_csv_path: Path, 
                         columns: Optional[List[str]] = None
                         ) -> int: 
    input_path = Path(input_dir_name).expanduser().resolve()
    output_path = out_csv_path 
    output_path.parent.mkdir(parents=True,exist_ok=True) 

    if columns is None: 
        columns = list(DEFAULT_MOSAIC_COLUMNS) 

    rows: List[Dict[str, object]] = [] 
    
    for file in pf.search_for_extension(input_path):
        metadata = extract(str(file), columns)
        rows.append(metadata)
    
    return write_csv(output_path, rows, columns)

def write_catalog(input_path: Path,
                  out_csv_path: Path,
                  columns: Optional[List[str]]=None ) -> int:

    if columns is None:
        columns = list(DEFAULT_CATALOG_COLUMNS)

    rows:  List[Dict[str,object]] = []

    for file in pf.search_for_extension(input_path):
        metadata = extract(str(file), columns)
        rows.append(metadata)

    return write_csv(out_csv_path, rows, columns)

def source_inspection_metadata(global_cfg) -> str: 
    run_out = Path(global_cfg.get("global").get("out"))
    meta_out = run_out/"metadata"
    if not meta_out.exists(): 
        face.error(f"path: {run_out} does not exist, run inspect")
        return "NULL PATH" 
    else:
        for p in meta_out.iterdir():
            if p.is_file() and p.name.startswith("scan-") and p.suffix.lower() == ".csv":
                return str(p)
    return "NULL PATH"


