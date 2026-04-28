""" whirlwind.domain.filesystem.files 

PUBLIC 
-------- 
RasterFile(path: str | Path, georefs: bool)

    contains 
    -------- 
    path: Path 
    uri: str 
    ext: str (extension) 
    fid: FileID 
    IF GEOREFS 
    crs_wkt : str 
    width: int 
    height: int 
    count: int 
    transform: Transform 

    methods 
    --------- 
    - record() -> dict 
    - get_path() -> Path 
    - mid -> str (fid.uid)

FileRef(path: str | Path)
    contains 
    --------- 
    path: Path 
    uri: str | Path 
    ext: str 
    fid: FileID 
    
    methods 
    --------- 
    - record() -> dict 
    - get_path() -> Path 


FileID(uri: Path | str, ext: str="")
    contains 
    ---------- 
    uid: str 
    UUID_LEN: int=12 

    methods 
    --------- 
    - gen_uid(pref: str) -> str 
    - record() -> dict 
    - get_uid() -> str 
"""
from __future__ import annotations 

import re 
from pathlib import Path 
from typing import Any 
from osgeo import gdal 


from dataclasses import dataclass 
from typing import Dict, Any
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
    FileRef created with extensions .tif/tiff 
    
    PUBLIC 
    -------- 
    RasterFile(path: str | Path, georefs: bool)

        contains 
        -------- 
        path: Path 
        uri: str 
        ext: str (extension) 
        fid: FileID 
        IF GEOREFS 
        crs_wkt : str 
        width: int 
        height: int 
        count: int 
        transform: Transform 
    
        - record() -> dict 
        - get_path() -> Path 
        - mid -> str (fid.uid)
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

    def record(self) -> Dict[str, Any]:
        return { 
                "mosaic_id": self.mosaic_id,
                "id": self.fid.get_uid(), 
                "uri": self.uri, 
                "path": self.path
                }
    def get_path(self) -> Path: 
        return self.path 
    
    @property
    def file_id(self) -> str: 
        return self.fid.uid 

    @property
    def variant_id(self) -> str: 
        return variant_from_path(self.path).variant_id 

    @property
    def mosaic_id(self) -> str: 
        return f"{self.file_id}-{self.variant_id}"

    @property 
    def mid(self) -> str: 
        "return mosaic_id or FileID.uid for self"
        return self.fid.uid 
 

@dataclass  
class FileRef: 
    """ creates a file reference 
    
        PUBLIC 
        --------- 
        FileRef(path: str | Path)
            contains 
            --------- 
            path: Path 
            uri: str | Path 
            ext: str 
            fid: FileID 
            
            - record() -> dict 
            - get_path() -> Path 
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.ext = self.path.suffix.lower()
        self.uri = self.path.as_uri()
        self.fid = FileID(self.uri, self.ext)

    def record(self) -> dict[str,Any]:
        return {
                "id": self.fid.get_uid(),
                "uri": self.uri, 
                "path": self.path
                }
    def get_path(self) -> Path:
        return self.path
        

@dataclass 
class FileID:
    """container for file id 
        
        FileID(uri: Path | str, ext: str="")
            contains 
            ---------- 
            uid: str 
            UUID_LEN: int=12 

            - gen_uid(pref: str) -> str 
            - record() -> dict 
            - get_uid() -> str 


    """
    uid: str 
    UUID_LEN: int=4
    
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



@dataclass(frozen=True)
class RasterVariant:
    variant_id: str
    variant_type: str
    spectral_id: str | None = None
    source: str = "filename"


VARIANT_ALIASES: dict[str, RasterVariant] = {
    "DSM": RasterVariant("DSM", "elevation_surface"),
    "DEM": RasterVariant("DEM", "elevation_ground"),
    "DTM": RasterVariant("DTM", "elevation_ground"),
    "CHM": RasterVariant("CHM", "canopy_height"),
    "NDVI": RasterVariant("NDVI", "vegetation_index", "ndvi"),
    "BGR": RasterVariant("BGR", "color_composite", "bgr"),
    "RGB": RasterVariant("RGB", "color_composite", "rgb"),
    "NIR": RasterVariant("NIR", "spectral_band", "nir"),
    "RED": RasterVariant("RED", "spectral_band", "red"),
    "GREEN": RasterVariant("GREEN", "spectral_band", "green"),
    "BLUE": RasterVariant("BLUE", "spectral_band", "blue"),
    "SWIR1": RasterVariant("SWIR1", "spectral_band", "swir1"),
    "SWIR2": RasterVariant("SWIR2", "spectral_band", "swir2"),
    "ERIC": RasterVariant("ERIC", "custom"),
}


def variant_from_path(path: str | Path) -> RasterVariant:
    stem = Path(path).stem.upper()

    tokens = [
        token
        for token in re.split(r"[^A-Z0-9]+", stem)
        if token
    ]

    # Prefer exact token match.
    for token in tokens:
        if token in VARIANT_ALIASES:
            return VARIANT_ALIASES[token]

    # Fallback for compact names like SiteDSM2024 or AreaNDVI.
    for key, variant in VARIANT_ALIASES.items():
        if key in stem:
            return variant

    return RasterVariant(
        variant_id="NULL",
        variant_type="unknown",
        spectral_id=None,
        source="unknown",
    )


def make_mosaic_id(file_id: str, variant_id: str) -> str:
    return f"{file_id}-{variant_id}"
