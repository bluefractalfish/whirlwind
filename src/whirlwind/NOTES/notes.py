from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import json
import uuid

from osgeo import gdal, osr


def uuid_from_path(uri: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, uri))


def safe_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [safe_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): safe_jsonable(v) for k, v in value.items()}
    return str(value)


@dataclass(frozen=True)
class MosaicMetadata:
    uris: list[str]
    out_path: Path
    format: str = "csv"     # "csv" | "json"
    mode: str = "core"      # "core" | "extended" | "full"

    def write(self) -> Path:
        rows = [self.extract(uri) for uri in self.uris]
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

        if self.format == "json":
            with self.out_path.open("w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2, sort_keys=True)
            return self.out_path

        if self.format == "csv":
            flat_rows = [self._flatten_for_csv(row) for row in rows]
            fieldnames = self._fieldnames(flat_rows)
            with self.out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for row in flat_rows:
                    w.writerow({k: row.get(k, "") for k in fieldnames})
            return self.out_path

        raise ValueError(f"unsupported format: {self.format}")

    def extract(self, uri: str) -> dict[str, Any]:
        ds = gdal.Open(uri, gdal.GA_ReadOnly)
        gdal.UseExceptions()

        if ds is None:
            raise RuntimeError(f"GDAL failed to open: {uri}")

        try:
            if self.mode == "core":
                return self._extract_core(ds, uri)
            if self.mode == "extended":
                return self._extract_extended(ds, uri)
            if self.mode == "full":
                return self._extract_full(ds, uri)
            raise ValueError(f"unsupported mode: {self.mode}")
        finally:
            ds = None

    def _extract_core(self, ds: gdal.Dataset, uri: str) -> dict[str, Any]:
        wkt = ds.GetProjection() or ""
        srs = osr.SpatialReference()
        srid = ""
        if wkt:
            srs.ImportFromWkt(wkt)
            srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            srid = srs.GetAuthorityCode(None) or ""

        gt = ds.GetGeoTransform(can_return_null=True)
        block_shapes = []
        dtypes = []
        nodata = []
        overviews = []

        for i in range(1, ds.RasterCount + 1):
            band = ds.GetRasterBand(i)
            dtypes.append(gdal.GetDataTypeName(band.DataType) or "")
            nodata.append(band.GetNoDataValue())
            block_shapes.append(list(band.GetBlockSize()))
            overviews.append(band.GetOverviewCount())

        return {
            "mosaic_id": uuid_from_path(uri),
            "uri": uri,
            "driver": ds.GetDriver().ShortName if ds.GetDriver() else "",
            "driver_long_name": ds.GetDriver().LongName if ds.GetDriver() else "",
            "width": ds.RasterXSize,
            "height": ds.RasterYSize,
            "count": ds.RasterCount,
            "crs_wkt": wkt,
            "srid": srid,
            "transform": list(gt) if gt else [],
            "dtype": dtypes[0] if dtypes else "",
            "dtypes": dtypes,
            "nodata": nodata,
            "block_shapes": block_shapes,
            "overview_counts": overviews,
            "dataset_tags": ds.GetMetadata() or {},
            "image_structure": ds.GetMetadata("IMAGE_STRUCTURE") or {},
            "subdatasets": ds.GetMetadata("SUBDATASETS") or {},
        }

    def _extract_extended(self, ds: gdal.Dataset, uri: str) -> dict[str, Any]:
        row = self._extract_core(ds, uri)
        row["metadata_domains"] = self._dataset_domains(ds)
        row["bands"] = [self._extract_band(ds.GetRasterBand(i), i) for i in range(1, ds.RasterCount + 1)]
        row["gcps"] = self._extract_gcps(ds)
        row["rpc"] = ds.GetMetadata("RPC") or {}
        row["geolocation"] = ds.GetMetadata("GEOLOCATION") or {}
        return row

    def _extract_full(self, ds: gdal.Dataset, uri: str) -> dict[str, Any]:
        return {
            "mosaic_id": uuid_from_path(uri),
            "uri": uri,
            "dataset": self._extract_dataset_full(ds),
            "bands": [self._extract_band(ds.GetRasterBand(i), i) for i in range(1, ds.RasterCount + 1)],
        }

    def _extract_dataset_full(self, ds: gdal.Dataset) -> dict[str, Any]:
        gt = ds.GetGeoTransform(can_return_null=True)
        return {
            "description": ds.GetDescription(),
            "driver": {
                "short_name": ds.GetDriver().ShortName if ds.GetDriver() else "",
                "long_name": ds.GetDriver().LongName if ds.GetDriver() else "",
            },
            "size": {
                "width": ds.RasterXSize,
                "height": ds.RasterYSize,
                "count": ds.RasterCount,
            },
            "projection_wkt": ds.GetProjection() or "",
            "transform": list(gt) if gt else [],
            "metadata_domains": self._dataset_domains(ds),
            "subdatasets": ds.GetMetadata("SUBDATASETS") or {},
            "image_structure": ds.GetMetadata("IMAGE_STRUCTURE") or {},
            "rpc": ds.GetMetadata("RPC") or {},
            "geolocation": ds.GetMetadata("GEOLOCATION") or {},
            "gcps": self._extract_gcps(ds),
        }

    def _dataset_domains(self, ds: gdal.Dataset) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for domain in ds.GetMetadataDomainList() or []:
            out[domain] = ds.GetMetadata(domain) or {}
        out["default"] = ds.GetMetadata() or {}
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

    def _extract_gcps(self, ds: gdal.Dataset) -> dict[str, Any]:
        gcps = ds.GetGCPs() or []
        gcp_proj = ds.GetGCPProjection() or ""
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

    def _flatten_for_csv(self, row: dict[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in row.items():
            if isinstance(v, (dict, list, tuple)):
                out[k] = json.dumps(safe_jsonable(v), ensure_ascii=False, sort_keys=True)
            elif v is None:
                out[k] = ""
            else:
                out[k] = str(v)
        return out

    def _fieldnames(self, rows: list[dict[str, str]]) -> list[str]:
        names: set[str] = set()
        for row in rows:
            names.update(row.keys())
        return sorted(names)


############################################# 



from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

@dataclass(frozen=True)
class LabelField:
    name: str
    kind: str   # "str", "int", "float", "date"

@dataclass(frozen=True)
class LabelLayerSpec:
    name: str
    geometry_type: str   # "LineString" or "Polygon"
    fields: Sequence[LabelField]

@dataclass(frozen=True)
class LabelSpec:
    layers: Sequence[LabelLayerSpec]

    @classmethod
    def default(cls) -> "LabelSpec":
        common = [
            LabelField("label_id", "str"),
            LabelField("mosaic_id", "str"),
            LabelField("source_uri", "str"),
            LabelField("browse_uri", "str"),
            LabelField("label_type", "str"),
            LabelField("event_date", "str"),
            LabelField("notes", "str"),
            LabelField("created_at", "str"),
            LabelField("updated_at", "str"),
        ]
        return cls(
            layers=[
                LabelLayerSpec("damage_path", "LineString", common),
                LabelLayerSpec("damage_area", "Polygon", common),
            ]
        )

@dataclass(frozen=True)
class LabelPlan:
    mosaic_id: str
    source_uri: str
    browse_uri: Path
    out_dir: Path
    gpkg_path: Path
    metadata_path: Path
    crs_wkt: str
    spec: LabelSpec

    @classmethod
    def from_browse(
        cls,
        mosaic_id: str,
        source_uri: str,
        browse_uri: str | Path,
        out_root: str | Path,
        crs_wkt: str,
        spec: Optional[LabelSpec] = None,
    ) -> "LabelPlan":
        browse_path = Path(browse_uri).expanduser().resolve()
        root = Path(out_root).expanduser().resolve()
        out_dir = root / mosaic_id
        return cls(
            mosaic_id=mosaic_id,
            source_uri=source_uri,
            browse_uri=browse_path,
            out_dir=out_dir,
            gpkg_path=out_dir / "labels.gpkg",
            metadata_path=out_dir / "label_plan.json",
            crs_wkt=crs_wkt,
            spec=spec or LabelSpec.default(),
        )

    def to_record(self) -> dict[str, object]:
        out = asdict(self)
        out["browse_uri"] = str(self.browse_uri)
        out["out_dir"] = str(self.out_dir)
        out["gpkg_path"] = str(self.gpkg_path)
        out["metadata_path"] = str(self.metadata_path)
        return out

class LabelBackend:
    @staticmethod
    def _ogr_geom_type(name: str) -> int:
        lut = {
            "LineString": ogr.wkbLineString,
            "Polygon": ogr.wkbPolygon,
        }
        if name not in lut:
            raise ValueError(f"unsupported geometry type: {name}")
        return lut[name]

    @staticmethod
    def _ogr_field_type(kind: str) -> int:
        lut = {
            "str": ogr.OFTString,
            "int": ogr.OFTInteger,
            "float": ogr.OFTReal,
            "date": ogr.OFTDate,
        }
        if kind not in lut:
            raise ValueError(f"unsupported field type: {kind}")
        return lut[kind]

    @classmethod
    def create_plan(cls, plan: LabelPlan, overwrite: bool = False) -> None:
        plan.out_dir.mkdir(parents=True, exist_ok=True)

        driver = ogr.GetDriverByName("GPKG")
        if driver is None:
            raise RuntimeError("GPKG driver not available")

        if plan.gpkg_path.exists():
            if overwrite:
                driver.DeleteDataSource(str(plan.gpkg_path))
            else:
                raise FileExistsError(f"GeoPackage already exists: {plan.gpkg_path}")

        ds = driver.CreateDataSource(str(plan.gpkg_path))
        if ds is None:
            raise RuntimeError(f"failed to create geopackage: {plan.gpkg_path}")

        try:
            srs = osr.SpatialReference()
            if plan.crs_wkt:
                srs.ImportFromWkt(plan.crs_wkt)
            else:
                srs = None

            for layer_spec in plan.spec.layers:
                layer = ds.CreateLayer(
                    layer_spec.name,
                    srs=srs,
                    geom_type=cls._ogr_geom_type(layer_spec.geometry_type),
                )
                if layer is None:
                    raise RuntimeError(f"failed to create layer: {layer_spec.name}")

                for fld in layer_spec.fields:
                    defn = ogr.FieldDefn(fld.name, cls._ogr_field_type(fld.kind))
                    if fld.kind == "str":
                        defn.SetWidth(254)
                    rc = layer.CreateField(defn)
                    if rc != 0:
                        raise RuntimeError(
                            f"failed to create field {fld.name} on {layer_spec.name}"
                        )
        finally:
            ds = None

        meta = {
            "mosaic_id": plan.mosaic_id,
            "source_uri": plan.source_uri,
            "browse_uri": str(plan.browse_uri),
            "gpkg_path": str(plan.gpkg_path),
            "crs_wkt": plan.crs_wkt,
            "layers": [
                {
                    "name": lyr.name,
                    "geometry_type": lyr.geometry_type,
                    "fields": [f.__dict__ for f in lyr.fields],
                }
                for lyr in plan.spec.layers
            ],
        }

        with plan.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
