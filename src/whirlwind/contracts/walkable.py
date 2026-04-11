"""whirlwind.contracts.discoverable 

PURPOSE: 
    - protocol contract for classes that can be used to generate manifests
    - used for generic operation: catalog(Discoverable, destination)
    - example: catalog(Directory(mnt/, tif, tiff),path/to/manifest) -> prints catalog.csv

"""
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
class Directory: 
    path: Path 
    uri: str 

    def   __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.uri = self.path.as_uri()
    
    def search_for(self, options: Tuple[str,...]) -> Iterator[File]:
        if self.path.is_dir():
            for f in self.path.rglob("*"):
                if f.is_file() and f.suffix.lower() in options:
                    yield File(f)

    def is_empty(self, options: Tuple[str, ...]) -> bool:
        if not self.path.is_dir():
            return True
        for f in self.path.rglob("*"):
            if f.is_file() and f.suffix.lower() in options:
                return False 
        return True 

@dataclass 
class MosaicCatalog:
    """ class for writing catalog of mosaics to be used as alternative for walking through directory """
    # where file will be written
    path: Path 
    # what file will be called 
    name: str 
    # what file types will be catalogged 
    file_types: Tuple[str,...] = (".tiff",".tif")

    def __init__(self,path: str|Path, extension: str = "csv") -> None:
        self.path = Path(path).expanduser().resolve()
        #type of file, usually csv 
        self.extension = extension 

    def get_mosaic_ids(self) -> Iterator[str]:
        """returns ids """
        p = self.path 
        if p.is_file() and p.suffix.lower() == ".csv":
            with p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                if "id" not in (r.fieldnames or []):
                    raise ValueError(f"MosaicCatalog missing uri column: {p}")
                for row in r:
                    uri = (row.get("id") or "").strip()
                    if uri:
                        yield uri
            return 

    def write_from(self, src: Path ) -> int:
        """constructs a Directory from path and builds csv of .tif/f uris"""

        # directory containing tiffs 
        mosaic_dir = Directory(src)
        
        if mosaic_dir.is_empty(self.file_types):
            print(f"there are no files like: {self.file_types}")
            return 1
        # list of File objects corresponding to Rasters 
        mosaic_files = mosaic_dir.search_for(self.file_types)

        rows: List[Dict[str,object]] = []
        
        for file in mosaic_files:
            rows.append(file.record)

        cols = rows[0].keys()

        try: 
            with self.path.open("w", newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in rows:
                    w.writerow({k: r.get(k,"") for k in cols })
            return 0
        except: 
            return 1


