"""whirlwind.tools.ids 

    PURPOSE:
        - generate ids 
        - fingerprints for mosaics, 
        - uuid from uri
        - tile ids 

"""
import uuid 
import hashlib 
from pathlib import Path 

UUID_LENGTH: int=8

RUN_ID_LENGTH: int=3

def gen_uuid_from_str(uri:str, length = UUID_LENGTH)->str:
    u = uuid.uuid5(uuid.NAMESPACE_URL,uri)
    return hashlib.blake2b(u.bytes, digest_size=length//2).hexdigest()

def gen_uuid_from_path(uri:Path)->str:
    return gen_uuid_from_str(str(uri))

def gen_fingerprint(p: str | Path) -> str:
    "generate deterministic fingerprint from path, to use in metadata naming"
    return hashlib.blake2b(str(p).encode("utf-8"),digest_size=5).hexdigest()

def gen_tile_id(mosaic_id: str, row: int, col: int) -> str:
    return f"{mosaic_id}_r{row:05d}_c{col:05d}"

def gen_run_id() -> str:
    return "ww" + str(uuid.uuid4())[:RUN_ID_LENGTH]
