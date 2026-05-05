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


def date_from_path(path: str | Path) -> str:
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

    # YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD
    m = re.search(
        r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)",
        stem,
    )
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy[-2:]}{mm}{dd}"

    # YYMMDD
    m = re.search(
        r"(?<!\d)(\d{2})([01]\d)([0-3]\d)(?!\d)",
        stem,
    )
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy[-2:]}{mm}{dd}"

    return "nulldate"


def short_hash(value: str, size: int = 6) -> str:
    digest_size = max(1, (size + 1) // 2)
    return hashlib.blake2b(
        value.encode("utf-8"),
        digest_size=digest_size,
    ).hexdigest()[:size]


def raster_file_id(path: str | Path, date: bool=False) -> str:
    p = Path(path).expanduser().resolve()
    variant = variant_from_path(p)
    h = short_hash(p.parent.as_uri(), size=4)

    return f"m{h}{variant.variant_id}"


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

        self.raster_id = raster_file_id(self.path)

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

    def record(self) -> Dict[str, Any]:
        variant = variant_from_path(self.path)
        date = date_from_path(self.path)

        return {
            "file_id": self.file_id,
            "date": date,
            "variant_id": variant.variant_id,
            "variant_type": variant.variant_type,
            "spectral_id": variant.spectral_id or "",
            "uri": self.uri,
            "path": self.path,
        }

    def col_row(self) -> tuple[list[str], list[Any]]:
        record = self.record()
        cols = list(record.keys())
        row = list(record.values())
        return cols, row

    def get_path(self) -> Path:
        return self.path

    @property
    def file_id(self) -> str:
        return self.raster_id


    @property
    def variant_id(self) -> str:
        return variant_from_path(self.path).variant_id

    @property
    def date(self) -> str:
        return date_from_path(self.path)

    @property
    def mosaic_id(self) -> str:
        return self.file_id

    @property
    def mid(self) -> str:
        return self.file_id


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
        }

    def get_path(self) -> Path:
        return self.path


@dataclass
class FileID:
    """
    Generic deterministic file id.

    For RasterFile, prefer RasterFile.file_id.
    This class remains useful for generic files such as shards,
    gpkg files, and non-raster file references.
    """

    uid: str
    UUID_LEN: int = 4

    def __init__(self, uri: Path | str, ext: str = ""):
        self.uri = str(uri)
        pref = next((k for k, v in EXT2ID.items() if ext in v), "")
        self.uid = self.gen_uid(pref)

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
        }

    def get_uid(self) -> str:
        return self.uid

