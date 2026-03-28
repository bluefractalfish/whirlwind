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

from whirlwind.geo.metadata import extract 
from whirlwind.tools import pathfinder as pf 
from whirlwind.tools.timer import timed 

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


def write_mosaic_metadata(input_dir_name: str, 
                         out_csv_name: str, 
                         columns: Optional[List[str]] = None
                         ) -> None: 
    input_path = Path(input_dir_name).expanduser().resolve()
    output_path = pf.find_home_() / "metadata"/ out_csv_name 
    output_path.parent.mkdir(parents=True,exist_ok=True) 

    if columns is None: 
        columns = list(DEFAULT_MOSAIC_COLUMNS) 

    rows: List[Dict[str, object]] = [] 
    
    for file in pf.search_for_extension(input_path):
        metadata = extract(str(file), columns)
        rows.append(metadata)

    with output_path.open("w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows: 
            w.writerow({k: r.get(k,"") for k in columns})

