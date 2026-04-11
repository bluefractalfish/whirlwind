"""whirlwind.geo.metadata 

    PURPOSE:
        - extract metadata from raster mosaics using gdal 
    BEHAVIOR:
        - open raster via gdal and return selected metadata fields 
        - compute lightweight geospatial descriptors 
    PUBLIC:
        - Extracter(uri, mode = "code" | "extended" | "full")
        - extract(uri, columns) -> dict[str, Any]

"""
from __future__ import annotations 

import re 
from dataclasses import dataclass 
from pathlib import Path 
from typing import Any, Dict, List, Tuple 
from osgeo import gdal, osr 

from whirlwind.tools import datamonkeys as dm 
from whirlwind.tools import ids 
from whirlwind.filesystem.files import File

@dataclass 
class Extracter: 
    f: File
    uri: str 
    ds: gdal.Dataset
    mode: str 

    def __init__(self, f: File, mode: str = "core") -> None:
        self.ds = gdal.Open(f.uri, gdal.GA_ReadOnly)
        self.f = f 
        self.uri = f.uri 
        self.mode = mode 
        if self.ds is None:
            raise RuntimeError(f"GDAL failed to open: {self.uri}")

        self.extract()

    def extract(self) -> dict[str, Any]:

        try:
            match self.mode:
                case "core":
                    return self._extract_core() 
                case "extended" | "ext": 
                    return self._extract_extended()
                case "full":
                    return self._extract_full()
                case _:
                    raise ValueError(f"unsupported mode: {self.mode}")
        finally:
            self.ds.Close() 


    def _extract_core(self) -> dict[str, Any]:

        """ 
        core metadata relating to dataset shape, drivers, and structure 
        mainly determined by comparability, cost of retrieval, and generality among rasters 

        extracts and populates dictionary:
                mosaic_id, 
                uri, 
                driver, 
                driver_long_name, 
                width, 
                height, 
                count, 
                crs_wkt, 
                srid, 
                transform, 
                dtype, 
                dtypes, 
                nodata,
                block_shapes, 
                overview_counts, 
                dataset_tags, 
                image_structure, 
                subdatasets 
            """
        d = self.ds 
        wkt = d.GetProjection() or ""
        srs = osr.SpatialReference()
        srid = ""

        if wkt: 
            srs.ImportFromWkt(wkt)
            srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            srid = srs.GetAuthorityCode(None) or ""

        gt = d.GetGeoTransform(can_return_null=True)
        block_shapes = []
        dtypes = []
        nodata = []
        overviews = []

        for i in range(1, d.RasterCount + 1):
            band = d.GetRasterBand(i)
            dtypes.append(gdal.GetDataTypeName(band.DataType) or "")
            nodata.append(band.GetNoDataValue())
            block_shapes.append(list(band.GetBlockSize()))
            overviews.append(band.GetOverviewCount())

        return {
            "mosaic_id": self.f.fid,
            "uri": self.uri,
            "driver": d.GetDriver().ShortName if d.GetDriver() else "",
            "driver_long_name": d.GetDriver().LongName if d.GetDriver() else "",
            "width": d.RasterXSize,
            "height": d.RasterYSize,
            "count": d.RasterCount,
            "crs_wkt": wkt,
            "srid": srid,
            "transform": list(gt) if gt else [],
            "dtype": dtypes[0] if dtypes else "",
            "dtypes": dtypes,
            "nodata": nodata,
            "block_shapes": block_shapes,
            "overview_counts": overviews,
            "dataset_tags": d.GetMetadata() or {},
            "image_structure": d.GetMetadata("IMAGE_STRUCTURE") or {},
            "subdatasets": d.GetMetadata("SUBDATASETS") or {},
        }     

    def _extract_extended(self) -> dict[str, Any]:
        """     CORE plus: 
                metadata_domains, 
                bands, 
                gcps, 
                rpc, 
                geolocation,

        """
        row = self._extract_core()
        row["metadata_domains"] = self._dataset_domains()
        row["bands"] = [self._extract_band(self.ds.GetRasterBand(i), i) 
                        for i in range(1, self.ds.RasterCount + 1)]
        row["gcps"] = self._extract_gcps()
        row["rpc"] = self.ds.GetMetadata("RPC") or {} 
        row["geolocation"] = self.ds.GetMetadata("GEOLOCATION") or {} 
        return row

    def _extract_full(self) -> dict[str, Any]:
        """
            mimics gdal.info()
        """
        return {
            "mosaic_id": self.f.fid,
            "uri": self.uri,
            "dataset": self._extract_all_metadata(),
            "bands": [self._extract_band(self.ds.GetRasterBand(i), i) 
                            for i in range(1, self.ds.RasterCount + 1)],
        }
    
    def _extract_all_metadata(self) -> dict[str, Any]:
        ...

    def _dataset_domains(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for domain in self.ds.GetMetadataDomainList() or []:
            out[domain] = self.ds.GetMetadata(domain) or {}
        out["default"] = self.ds.GetMetadata() or {}
        return out 

    def _extract_band(self, band: gdal.Band, band_index: int) -> dict[str, Any]:
        color_name = gdal.GetColorInterpretationByName(band.GetColorInterpretation())
        unit = band.GetUnitType() or ""
        desc = band.GetDescription() or ""
        scale = band.GetScale()
        offset = band.GetOffset()
        nodata = band.GetNoDataValue()
        minmax = None 
        try: 
            minmax = band.ComputeRasterMinMax(False)
        except Exception:
            minmax = None   

        domains: dict[str, dict[str, str]] = {}
        for domain in band.GetMetadataDomainList() or []:
            domains[domain] = band.GetMetadata(domain) or {}
        domains["default"] = band.GetMetadata() or {}

        return {
            "band": band_index,
            "dtype": gdal.GetDataTypeName(band.DataType) or "",
            "block_size": list(band.GetBlockSize()),
            "nodata": nodata,
            "description": desc,
            "unit": unit,
            "scale": scale,
            "offset": offset,
            "color_interpretation": color_name,
            "overview_count": band.GetOverviewCount(),
            "mask_flags": band.GetMaskFlags(),
            "category_names": band.GetCategoryNames(),
            "minmax": minmax,
            "metadata_domains": domains,
        }
    
    def _extract_gcps(self) -> dict[str, Any]:
        gcps = self.ds.GetGCPs() or []
        gcp_proj = self.ds.GetGCPProjection() or ""
        return {
            "projection": gcp_proj,
            "count": len(gcps),
            "items": [
                {
                    "id": g.Id,
                    "info": g.Info,
                    "pixel": g.GCPPixel,
                    "line": g.GCPLine,
                    "x": g.GCPX,
                    "y": g.GCPY,
                    "z": g.GCPZ,
                }
                for g in gcps
            ],
        }

def _import_osgeo():
    try:
        from osgeo import gdal, osr 
    except Exception as exc:
        raise RuntimeError(
        "GDAL required") from exc 
    try: 
        gdal.UseExceptions()
    except Exception:
        pass 
    return gdal, osr 

def extract(uri: str, columns: List[str]) -> Dict[str, Any]:

    """
    Open raster at `uri` using GDAL and return a dict containing only the requested columns.

    Typical columns for mosaic_stage:
      mosaic_id,uri, uri_etag, byte_size, crs, srid, pixel_width, pixel_height,
      band_count, dtype, nodata, footprint, acquired_at, created_at
    """
    

    gdal, _osr = _import_osgeo()

    ds = gdal.Open(uri, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"GDAL failed to open: {uri}")

    out: Dict[str, Any] = {}
    
    if "mosaic_id" in columns:
        out["mosaic_id"]=ids.gen_uuid_from_str(uri)

    # always allow uri
    if "uri" in columns:
        out["uri"] = uri

    if "byte_size" in columns:
        out["byte_size"] = dm.get_byte_size(uri)

    crs_wkt = ""
    if "crs" in columns or "srid" in columns or "footprint" in columns:
        crs_wkt = get_crs(ds)

    if "crs" in columns:
        out["crs"] = crs_wkt

    if "srid" in columns:
        out["srid"] = get_srid(crs_wkt)

    if any(c in columns for c in ("pixel_width", "pixel_height", "band_count")):
        w, h, b = get_raster_shape(ds)
        if "pixel_width" in columns:
            out["pixel_width"] = w
        if "pixel_height" in columns:
            out["pixel_height"] = h
        if "band_count" in columns:
            out["band_count"] = b

    if "dtype" in columns or "nodata" in columns:
        dtype, nodata = get_dtype_and_nodata(ds)
        if "dtype" in columns:
            out["dtype"] = dtype
        if "nodata" in columns:
            out["nodata"] = nodata

    if "footprint" in columns:
        out["footprint"] = get_footprint(ds, target_epsg=4326)

    if "acquired_at" in columns:
        out["acquired_at"] = parse_aquired_at(Path(uri), valid=True)

    if "uri_etag" in columns:
        out["uri_etag"] = ""
    if "created_at" in columns: 
        out["created_at"] = dm.created_at()

    return out



def get_crs(ds: Any) -> str:
    """Return CRS as WKT, or empty string if missing."""
    return ds.GetProjection() or ""

def get_srid(crs_wkt: str) -> str:
    """
    Try to extract an EPSG code (SRID) from a WKT projection.

    Returns:
      - "4326" etc if available
      - "" if no authority code can be found
    """
    if not crs_wkt:
        return ""

    _gdal, osr = _import_osgeo()
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs_wkt)

    # Force lon/lat axis order for EPSG:4326 style CRS
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    return srs.GetAuthorityCode(None) or ""

def get_raster_shape(ds: Any )-> Tuple[str, str, str]:
    """
    Return (pixel_width, pixel_height, band_count) as strings (staging-friendly).
    """
    return str(ds.RasterXSize), str(ds.RasterYSize), str(ds.RasterCount)

def get_dtype(ds_type: int) -> str:
    gdal, _osr = _import_osgeo()
    return gdal.GetDataTypeName(ds_type) or ""

def get_dtype_and_nodata(ds: Any) -> Tuple[str, str]:
    """
    Use band 1 as representative for dtype + nodata.

    Returns:
      (dtype_str, nodata_str)
    """
    if ds.RasterCount < 1:
        return "", ""

    b1 = ds.GetRasterBand(1)
    dtype = get_dtype(b1.DataType)

    nd = b1.GetNoDataValue()
    nodata = "" if nd is None else str(nd)
    return dtype, nodata

def parse_aquired_at(path: Path, valid: bool = True) -> str:
    """
    Parse acquisition date from filename prefix.

    Convention:
      YYMMDD_loc_...  (example: 240119_denver_ortho.tif)

    Returns:
      "20YY-MM-DD"  (example: "2024-01-19")

    If no match is found, returns "".

    NOTE: function name kept as `parse_aquired_at` to match your existing calls
    (spelling preserved).
    """
    name = path.name

    if valid:
        # Strict-ish month/day ranges
        m = re.match(r"^(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", name)
    else:
        m = re.match(r"^(\d{2})(\d{2})(\d{2})", name)

    if not m:
        return ""

    yy, mm, dd = m.group(1), m.group(2), m.group(3)
    return f"20{yy}-{mm}-{dd}"

def get_footprint(ds: Any, target_epsg: int = 4326) -> str:
    """
    Compute raster bbox footprint as EWKT in target_epsg (default 4326).

    Returns:
      "SRID=4326;POLYGON((lon lat, lon lat, ...))"

    Requirements:
      - dataset must have a geotransform and projection
    """
    _gdal, osr = _import_osgeo()

    gt = ds.GetGeoTransform(can_return_null=True)
    if gt is None:
        return ""

    src_wkt = ds.GetProjection() or ""
    if not src_wkt:
        return ""

    width = ds.RasterXSize
    height = ds.RasterYSize

    def pix_to_geo(px: float, py: float) -> Tuple[float, float]:
        x = gt[0] + px * gt[1] + py * gt[2]
        y = gt[3] + px * gt[4] + py * gt[5]
        return x, y

    # corners in source CRS (closed ring)
    corners = [
        pix_to_geo(0, 0),
        pix_to_geo(width, 0),
        pix_to_geo(width, height),
        pix_to_geo(0, height),
        pix_to_geo(0, 0),
    ]

    src = osr.SpatialReference()
    src.ImportFromWkt(src_wkt)
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(target_epsg)

    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    tx = osr.CoordinateTransformation(src, dst)

    corners_out = []
    for x, y in corners:
        lon, lat, _ = tx.TransformPoint(x, y)
        corners_out.append((lon, lat))

    coords = ",".join(f"{lon:.8f} {lat:.8f}" for lon, lat in corners_out)
    return f"SRID={target_epsg};POLYGON(({coords}))"


#def gdalinfo(input_file: str) -> Dict[str,Any]:

