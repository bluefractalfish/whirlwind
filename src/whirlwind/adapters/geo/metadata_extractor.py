"""whirlwind.geo.metadata_extractor

    PURPOSE:
        - extract metadata from raster using gdal. allow several different resolutions of metadata to be extracted  


    BEHAVIOR:
        - open raster via gdal and return selected metadata fields 
        - compute lightweight geospatial descriptors 
    PUBLIC:
        - Extracter(uri, mode = "code" | "extended" | "full")
        - extract(uri, columns) -> dict[str, Any]

"""
from __future__ import annotations 

from dataclasses import dataclass 
from pathlib import Path 
from typing import Any 
from osgeo import gdal, osr 

from whirlwind.filesystem.files import RasterFile

@dataclass 
class GeoMetadataExtractor: 
    """ 
        dataclass created from uri as string, modulated by `mode` 
        calling it returns a dictionary whose length/metadata resolution is 
        determined by mode: core -> minimum identifyable information, extended = core + extended informtaion 
        and full = all gdal information. these are also in order of costs 

    """

    f: RasterFile
    path: Path 
    uri: str 
    ds: gdal.Dataset
    mode: str 

    def __init__(self, path: str|Path, mode: str = "core") -> None:
        _import_osgeo()
        self.path = Path(path).expanduser().resolve()
        self.f = RasterFile(path)  
        self.ds = gdal.Open(str(self.path), gdal.GA_ReadOnly)
        self.mode = mode 
        if self.ds is None:
            raise RuntimeError(f"GDAL failed to open: {self.f.uri}")

    def discover(self) -> dict[str, Any]:
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

        footprint = self._footprint_wgs84()

        return {
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
            "uri": self.f.uri,
            "mosaic_id": self.f.mosaic_id,
            "footprint_wgs84": footprint["footprint_wgs84"],
            "minx_wgs84": footprint["minx_wgs84"],
            "miny_wgs84": footprint["miny_wgs84"],
            "maxx_wgs84": footprint["maxx_wgs84"],
            "maxy_wgs84": footprint["maxy_wgs84"],
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
            "dataset": self._extract_all_metadata(),
            "bands": [self._extract_band(self.ds.GetRasterBand(i), i) 
                            for i in range(1, self.ds.RasterCount + 1)],
            "uri": self.f.uri,
            "mosaic_id": self.f.mosaic_id,
        }
    
    def _extract_all_metadata(self) -> dict[str, Any]:
        d = self.ds 
        gt = d.GetGeoTransform(can_return_null=True)
        return {
            "description": d.GetDescription(),
            "driver": {
                "short_name": d.GetDriver().ShortName if d.GetDriver() else "",
                "long_name": d.GetDriver().LongName if d.GetDriver() else "",
            },
            "size": {
                "width": d.RasterXSize,
                "height": d.RasterYSize,
                "count": d.RasterCount,
            },
            "projection_wkt": d.GetProjection() or "",
            "transform": list(gt) if gt else [],
            "metadata_domains": self._dataset_domains(),
            "subdatasets": d.GetMetadata("SUBDATASETS") or {},
            "image_structure": d.GetMetadata("IMAGE_STRUCTURE") or {},
            "rpc": d.GetMetadata("RPC") or {},
            "geolocation": d.GetMetadata("GEOLOCATION") or {},
            "gcps": self._extract_gcps(),
        }
        
    def _dataset_domains(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for domain in self.ds.GetMetadataDomainList() or []:
            out[domain] = self.ds.GetMetadata(domain) or {}
        out["default"] = self.ds.GetMetadata() or {}
        return out 

    def _extract_band(self, band: gdal.Band, band_index: int) -> dict[str, Any]:
        color_name = gdal.GetColorInterpretationName(int(band.GetColorInterpretation()))
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

    def _footprint_wgs84(self) -> dict[str, object]:
        gt = self.ds.GetGeoTransform(can_return_null=True)
        src_wkt = self.ds.GetProjection() or ""

        if gt is None or not src_wkt:
            return {
                "footprint_wgs84": "",
                "minx_wgs84": "",
                "miny_wgs84": "",
                "maxx_wgs84": "",
                "maxy_wgs84": "",
            }

        width = self.ds.RasterXSize
        height = self.ds.RasterYSize

        def pix_to_geo(px: float, py: float) -> tuple[float, float]:
            x = gt[0] + px * gt[1] + py * gt[2]
            y = gt[3] + px * gt[4] + py * gt[5]
            return x, y

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
        dst.ImportFromEPSG(4326)

        src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        tx = osr.CoordinateTransformation(src, dst)

        points: list[tuple[float, float]] = []
        for x, y in corners:
            lon, lat, _ = tx.TransformPoint(x, y)
            points.append((float(lon), float(lat)))

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        coords = ",".join(f"{x:.8f} {y:.8f}" for x, y in points)

        return {
            "footprint_wgs84": f"SRID=4326;POLYGON(({coords}))",
            "minx_wgs84": min(xs),
            "miny_wgs84": min(ys),
            "maxx_wgs84": max(xs),
            "maxy_wgs84": max(ys),
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

