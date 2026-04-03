"""whirlwind.io.inputs 
    
    PURPOSE:
        - resolve an input selector (csv, directory, glob)
        - iterate raster uris 
    BEHAVIOR:
        - csv: read a uri column from metadata file 
        - directory: recursively yield files with ext = DEFAULT (.tif,.tiff)
        - glob: yield matching files 
    PUBLIC:
        - iterate_uris(source, extensions)

"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterator, Tuple
from whirlwind.ui import face

def iter_uris(source: str, extensions: Tuple[str, ...] = (".tif", ".tiff")) -> Iterator[str]:
    s = (source or "").strip()
    if not s:
        raise ValueError("input source is required")
    p = Path(s).expanduser()
    if p.is_file() and p.suffix.lower() == ".csv":
        with p.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if "uri" not in (r.fieldnames or []):
                raise ValueError(f"input CSV missing uri column: {p}")
            for row in r:
                uri = (row.get("uri") or "").strip()
                if uri:
                    yield uri
        return

    if p.is_dir():
        for tif in p.rglob("*"):
            if tif.is_file() and tif.suffix.lower() in extensions:
                yield str(tif)
        return
        
    matches = False
    for tif in Path().glob(s):
        if tif.is_file() and tif.suffix.lower() in extensions:
            matches = True
            yield str(tif)
        if matches:
            return
    face.error(f"could not resolve input as csv, directory, or glob: {source}")
    return 
