
from __future__ import annotations 

from pathlib import Path 
from typing import Any, Protocol, Tuple, runtime_checkable, Iterator 
from osgeo import gdal 

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
class RasterFile:
    """ 
    of procotol File, created with extensions .tif/tiff 
    
    contains 
    -------- 
    path: Path 
    uri: str 
    ext: str (extension) 
    fid: FileID 
    

    """

    def __init__(self, path: str | Path, georefs: bool = False):
        self.path = Path(path).expanduser().resolve()
        self.ext = self.path.suffix.lower() 
        self.uri = self.path.as_uri() 
        self.fid = FileID(self.uri, self.ext)
        
        if georefs:
            ds = gdal.Open(self.path, gdal.GA_ReadOnly)
            if ds is None:
                raise RuntimeError(f"failed to open raster: {self.uri}")

            try:
                self.crs_wkt: str = ds.GetProjection() or ""
                self.width: int = ds.RasterXSize
                self.height: int = ds.RasterYSize
                self.count: int = ds.RasterCount
                self.transform = ds.GetGeoTransform(can_return_null=True)
            finally:
                ds = None
    @property 
    def record(self) -> Dict[str, Any]:
        return { 
                "id": self.fid.get_uid(), 
                "uri": self.uri, 
                "path": self.path
                }
    @property 
    def get_path(self) -> Path: 
        return self.path 

    @property 
    def mid(self) -> str: 
        "return mosaic_id or FileID.uid for self"
        return self.fid.uid 
 

@dataclass  
class File: 
    """ creates a file reference File(path: str | Path) 
        with properties: 
        path: Path, uri: str, extention=ext: str, fid: FileID 
        and medthod property self.record -> {"id":fid.uid, "uri": uri}
        and get_path -> Path
    """
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
                "path": self.path
                }
    @property  
    def get_path(self) -> Path:
        return self.path

@dataclass  
class FileRef(Protocol): 
    """ creates a file reference File(path: str | Path) 
        with properties: 
        path: Path, uri: str, extention=ext: str, fid: FileID 
        and medthod property self.record -> {"id":fid.uid, "uri": uri}
        and get_path -> Path
    """
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
                "path": self.path
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



