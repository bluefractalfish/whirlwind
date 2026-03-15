
from __future__ import annotations

import uuid
import hashlib
from pathlib import Path

def uuid_from_path(uri:str, length: int=8)->str:
    u = uuid.uuid5(uuid.NAMESPACE_URL,uri)
    return hashlib.blake2b(u.bytes, digest_size=length//2).hexdigest()

def gen_fingerprint(p: str | Path) -> str:
    "generate deterministic fingerprint from path, to use in metadata naming"
    return hashlib.blake2b(str(p).encode("utf-8"),digest_size=5).hexdigest()

def gen_tile_id(mosaic_id: str, row: int, col: int) -> str:
    return f"{mosaic_id}_r{row:05d}_c{col:05d}"

