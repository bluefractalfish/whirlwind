
from __future__ import annotations 

from pathlib import Path 
from typing import Any, Protocol, Tuple, runtime_checkable, Iterator 


@runtime_checkable 
class Searchable(Protocol):
    path: Path 

    def search_for(self, options: Any) -> Iterator[Any]: 
        ... 


from dataclasses import dataclass 
from typing import Dict, Any, List 
import csv 
import uuid 
import hashlib 


EXT2ID: Dict[str, Any] = {
        "m" : (".tif",".tiff"), 
        "s" : (".tar", ),
        "d" : (".gpkg")
    }

@dataclass  
class File: 
    path: Path 
    uri: str 
    ext: str 
    fid: FileID 

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.ext = self.path.suffix.lower()
        self.uri = self.path.as_uri()
        self.fid = FileID(self.uri, self.ext)

    @property  
    def record(self) -> dict[str,Any]:
        return {
                "id": self.fid.get_uid(),
                "uri": self.uri, 
                }
    @property  
    def get_path(self) -> Path:
        return self.path
        

@dataclass 
class FileID:
    uri: Path 
    uid: str 
    UUID_LEN: int=12
    
    def __init__(self, uri: Path | str, ext: str = ""):
        self.uri = Path(uri) 
        pref = next((k for k,v in EXT2ID.items() if ext in v), "")
        self.uid = self.gen_uid(pref)

    def gen_uid(self, pref: str) -> str:
        u = uuid.uuid5(uuid.NAMESPACE_URL, str(self.uri)) 
        uid = hashlib.blake2b(u.bytes, digest_size=self.UUID_LEN//2).hexdigest()
        return pref+uid

    def record(self) -> Dict[str,object]:
        return {
                "uri": str(self.uri),
                "uid": self.uid
                }
    def get_uid(self) -> str:
        return self.uid



