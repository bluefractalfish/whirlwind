"""whirlwind.io.shards 


    PURPOSE:
        - write tile payloads into tar shards 
    BEHAVIOR:
        - create sequential tar files <prefix>-NNN.tar 
        - write two entries per tile <tile_id>.npy and <tile_id>.json 
        - rotate to next shard after shard_size samples 
    PUBLIC:
        - ShardWriter 
        
"""
from __future__ import annotations
import io
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ShardWriter:
    out_dir: Path
    prefix: str
    shard_size: int
    shard_index: int = 1
    samples_in_shard: int = 0
    tar: Optional[tarfile.TarFile] = None
    tar_path: Optional[Path] = None
    def _open_next(self) -> None:
        if self.tar is not None:
            self.tar.close()
        name = f"{self.prefix}-{self.shard_index:03d}.tar"
        self.tar_path = self.out_dir / name
        self.tar = tarfile.open(self.tar_path, "w")
        self.samples_in_shard = 0
        self.shard_index += 1

    def write_sample(self, key: str, npy: bytes, meta_json: bytes) -> Path:
        if self.tar is None or self.samples_in_shard >= self.shard_size:
            self._open_next()
        assert self.tar is not None
        assert self.tar_path is not None
        npy_name = f"<{key}>.npy"
        ti = tarfile.TarInfo(npy_name)
        ti.size = len(npy)
        ti.mtime = int(time.time())
        self.tar.addfile(ti, io.BytesIO(npy))
        js_name = f"<{key}>.json"
        tj = tarfile.TarInfo(js_name)
        tj.size = len(meta_json)
        tj.mtime = int(time.time())
        self.tar.addfile(tj, io.BytesIO(meta_json))
        self.samples_in_shard += 1
        return self.tar_path

    def close(self) -> None:
        if self.tar is not None:
            self.tar.close()
            self.tar = None
            self.tar_path = None

