""" whirlwind.ingest.planner 

    PURPOSE:
        - determine output directory layour for ingested mosaics 

    BEHAVIOR:
        - given output root and mosaic_id compute,create:
            - <out-root>/mosaic_id/shards
            - <out_root>/mosaic_id/manifest 
            - etc 
    PUBLIC:
        - mosaic_dirs(out_root, mosaic_id) -> (shards_dir, manifst_dir)

"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple

def mosaic_dirs(out_root: Path, mosaic_id: str) -> Tuple[Path, Path]:
    shards_dir = out_root / str(mosaic_id) / "shards"
    manifest_dir = out_root / str(mosaic_id) / "manifest"
    shards_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return shards_dir, manifest_dir
