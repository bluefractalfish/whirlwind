"""whirlwind.domain.filesystem.files

PUBLIC
------
RasterFile(path: str | Path, georefs: bool = False)

    Metadata-only file reference for raster files.

    ID behavior:
        file_id = m-{date}-{variant}-{metamosaic hash}

    Example:
        20240119_denver_DSM.tif
            -> m-20240119-DSM-a31f

FileRef(path: str | Path)

    Generic file reference with extension-based hashed id.

FileID(uri: Path | str, ext: str = "")

    Generic deterministic file id.

RasterVariant

    Parsed product/spectrum/variant information from filename.

"""

from __future__ import annotations

import hashlib
import re
import datetime as dt 
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from osgeo import gdal


EXT2ID: Dict[str, Any] = {
    "m": (".tif", ".tiff"),
    "s": (".tar",),
    "d": (".gpkg",),
}

@dataclass
class FileID:
    """
    central authority for deterministic file ids.
 
    """
    

    uid: str
    ID_SCHEME = "file_name_scheme"
    ID_VERSION = "4"
    UUID_LEN: int = 4

    def __init__(self, uri: Path | str, ext: str = ""):
        self.uri = Path(uri) 
        self.uid = _short_hash(self.uri.name, size=6)
    
    @staticmethod 
    def _hash(value: str, size: int = 6) -> str: 
        return _short_hash(value, size=size)
    
    @staticmethod
    def mosaic (path: str | Path, use_uri: bool = False) -> str: 
        uri = _as_uri(path) 
        variant = _variant_from_path(path)
        date = _date_from_path(path) 
        if use_uri:
            h = _short_hash(uri, size=6) 
        else: 
            h = _short_hash(Path(path).name, size=6)
        return f"M{date}{variant.variant_id}{h}"
    
    @staticmethod 
    def metamosaic(
            member_ids: tuple[str, ...] | list [str], 
            stem: str = "locale",
            *,
            hash_len: int = 6
            ) -> str: 
        """ 
        construct a deterministic metamosaic ID from a group of mosaic IDs 
        
        metamosaic_id = MM<stem><hash_of_members> 
        
        """

        clean_stem = FileID.slug(stem).upper()
        canonical = "|".join(sorted(str(mid) for mid in member_ids if str(mid))) 
        h = _short_hash(canonical, size=hash_len)
        return f"MM_{clean_stem}_{h}" 

    @staticmethod 
    def branch(mosaic_id: str) -> str: 
        """ so future branch naming doesnt change bridge code """
        return str(mosaic_id)
    
    @staticmethod 
    def tile(mosaic_id: str, row_i: int, col_i: int, sigfig: int=4) -> str: 
        return f"T{mosaic_id[1:]}r{row_i:04d}c{col_i:04d}" 

    @staticmethod 
    def shard(branch_id: str, shard_index: int, prefix: str = "S") -> str:
        return f"{prefix}{branch_id}{shard_index:06d}.tar"

    @staticmethod 
    def slug(value: str) -> str: 
        slug = re.sub(r"[^A-Za-z0-9]+", "", value.strip()).strip("-").lower()
        return slug or "locale"

    def gen_uid(self, pref: str) -> str:
        u = uuid.uuid5(uuid.NAMESPACE_URL, str(self.uri))
        uid = hashlib.blake2b(
            u.bytes,
            digest_size=max(1, self.UUID_LEN // 2),
        ).hexdigest()
        return pref + uid

    def record(self) -> Dict[str, object]:
        return {
            "uri": str(self.uri),
            "uid": self.uid,
            "id_scheme": self.ID_SCHEME, 
            "id_version": self.ID_VERSION
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
    "ERIK": RasterVariant("ERIK", "custom"),
    "ERIK2": RasterVariant("ERIK2", "custom"),
}


def _variant_from_path(path: str | Path) -> RasterVariant:
    """
    Extract raster product/spectrum/variant from filename.

    Examples:
        site_20240119_DSM.tif      -> DSM
        site-20240119-rgb.tif      -> RGB
        SiteDSM2024.tif            -> DSM
        unknown_file.tif           -> NULL
    """
    stem = Path(path).stem.upper()

    tokens = [
        token
        for token in re.split(r"[^A-Z0-9]+", stem)
        if token
    ]

    # always prefer exact token match.
    for token in tokens:
        if token in VARIANT_ALIASES:
            return VARIANT_ALIASES[token]

    # fallback compact names like SiteDSM2024 or AreaNDVI.
    for key, variant in VARIANT_ALIASES.items():
        if key in stem:
            return variant

    return RasterVariant(
        variant_id="NLL",
        variant_type="unknown",
        spectral_id=None,
        source="unknown",
    )



def _date_from_path(path: str | Path) -> str:
    """
    Extract acquisition/date token from raster filename.

    Supports:
        YYYYMMDD
        YYYY-MM-DD
        YYYY_MM_DD
        YYMMDD

    Examples:
        20240119_denver_DSM.tif      -> 240119
        2024-01-19_denver_DSM.tif    -> 240119
        2024_01_19_denver_DSM.tif    -> 240119
        240119_denver_DSM.tif        -> 240119
    """

    stem = Path(path).stem

    patterns = (
        r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)",
        r"(?<!\d)(\d{2})([01]\d)([0-3]\d)(?!\d)",
    )

    for pattern in patterns:
        m = re.search(pattern, stem)
        if not m:
            continue

        y, mm, dd = m.groups()
        yyyy = y if len(y) == 4 else f"20{y}"

        try:
            parsed = dt.datetime.strptime(f"{yyyy}{mm}{dd}", "%Y%m%d")
        except ValueError:
            continue

        return parsed.strftime("%y%m%d")

    return "nulldate"


def _short_hash(value: str, size: int = 6) -> str:
    digest_size = max(1, (size + 1) // 2)
    return hashlib.blake2b(
        value.encode("utf-8"),
        digest_size=digest_size,
    ).hexdigest()[:size]

def _as_uri(value: str | Path) -> str: 
    """
        normalize path-like input into stable string for deterministic hash

    """
    if isinstance(value, Path):
        return value.expanduser().resolve().as_uri()

    raw = str(value) 

    if "://" in raw or raw.startswith("/vsi"):
        return raw 

    return Path(raw).expanduser().resolve().as_uri()



@dataclass
class RasterFile:
    """
    File reference created for .tif/.tiff rasters.

    Contains:
        path: Path
        uri: str
        ext: str
        fid: FileID
        raster_id: semantic raster id

    If georefs=True, also loads GDAL metadata:
        crs_wkt: str
        width: int
        height: int
        count: int
        transform: tuple | None

    Memory behavior:
        georefs=False:
            metadata-only path parsing; no raster open.

        georefs=True:
            opens raster with GDAL but does not read pixel arrays.
    """

    def __init__(self, path: str | Path, georefs: bool = False):
        self.path = Path(path).expanduser().resolve()
        self.ext = self.path.suffix.lower()
        self.uri = self.path.as_uri()

        # Generic hashed file id retained for compatibility.
        self.fid = FileID(self.uri, self.ext)
            
        # semantic raster ID for mosaics 
        self.raster_id = FileID.mosaic(self.path)

        if georefs:
            ds = gdal.Open(str(self.path), gdal.GA_ReadOnly)
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
    def variant_id(self) -> str:
        return _variant_from_path(self.path).variant_id

    @property
    def date(self) -> str:
        return _date_from_path(self.path)

    @property
    def mosaic_id(self) -> str:
        return self.raster_id

    def record(self) -> Dict[str, Any]:
        """ 
            manifest row for source mosaic 

            new canonical fields: 
                mosaic_id 
                source_uri 

        """

        variant = _variant_from_path(self.path)
        date = _date_from_path(self.path)

        return {
            
            # canonical identity fields 

            "alias": self.fid.uid,
            "mosaic_id": self.mosaic_id,
            "source_uri": self.uri, 
            "path": str(self.path),

            # semantic fields 
            "date": date,
            "variant_id": variant.variant_id,
            "variant_type": variant.variant_type,
            "spectral_id": variant.spectral_id or "",
            
            # id policy fields 
            "id_scheme": FileID.ID_SCHEME, 
            "id_version": FileID.ID_VERSION
        }

    def col_row(self) -> tuple[list[str], list[Any]]:
        record = self.record()
        cols = list(record.keys())
        row = list(record.values())
        return cols, row

    def get_path(self) -> Path:
        return self.path



@dataclass
class FileRef:
    """
    Generic file reference.

    Contains:
        path: Path
        uri: str
        ext: str
        fid: FileID
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.ext = self.path.suffix.lower()
        self.uri = self.path.as_uri()
        self.fid = FileID(self.uri, self.ext)

    def record(self) -> dict[str, Any]:
        return {
            "id": self.fid.get_uid(),
            "uri": self.uri,
            "path": self.path,
            "id_scheme": FileID.ID_SCHEME, 
            "id_version": FileID.ID_VERSION
        }

    def get_path(self) -> Path:
        return self.path


