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
#############################################
##############################################
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whirlwind.config import Config
from whirlwind.domain.filetree.run_tree import RunTree


@dataclass(frozen=True)
class CommandContext:
    config: Config

    @property
    def global_cfg(self) -> dict[str, Any]:
        value = self.config.merged.get("global", {})
        return value if isinstance(value, dict) else {}

    @property
    def io_cfg(self) -> dict[str, Any]:
        value = self.global_cfg.get("io", {})
        return value if isinstance(value, dict) else {}

    @property
    def in_dir(self) -> Path:
        return Path(self.io_cfg.get("in_dir", "./mnt")).expanduser().resolve()

    @property
    def dest_dir(self) -> Path:
        return Path(self.io_cfg.get("dest_dir", "./artifacts")).expanduser().resolve()

    @property
    def run_id(self) -> str:
        return str(self.global_cfg.get("run_id", "dev"))

    @property
    def run_tree(self) -> RunTree:
        return RunTree.plant(self.dest_dir / self.run_id)

    def section(self, *keys: str) -> dict[str, Any]:
        obj: Any = self.config.merged
        for key in keys:
            if not isinstance(obj, dict):
                return {}
            obj = obj.get(key, {})
        return obj if isinstance(obj, dict) else {}

    def value(self, *keys: str, default: Any = None) -> Any:
        obj: Any = self.config.merged
        for key in keys:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(key, default)
        return obj


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whirlwind.adapters.geo.window_planner_gdal import GDALWindowPlanner
from whirlwind.adapters.io.id_manifest_csv import IDManifestCSV
from whirlwind.adapters.io.tile_plan_csv import TilePlanCSV
from whirlwind.domain.filetree.file_ref import RasterFileRef
from whirlwind.specs.tiling import TSpec
from whirlwind.domain.filetree.run_tree import RunTree


@dataclass(frozen=True)
class PlanTilesRequest:
    run_tree: RunTree
    manifest_name: str
    spec: TSpec
    force: bool = False


@dataclass(frozen=True)
class PlanTilesResult:
    mosaics_seen: int
    plans_written: int
    plans_skipped: int
    errors: int
    code: int = 0


class PlanTilesBridge:
    def run(self, request: PlanTilesRequest) -> PlanTilesResult:
        manifest_path = request.run_tree.manifest_csv(request.manifest_name)
        manifest = IDManifestCSV(manifest_path)

        if not manifest.exists():
            raise FileNotFoundError(f"ID manifest does not exist: {manifest_path}")

        mosaics_seen = 0
        plans_written = 0
        plans_skipped = 0
        errors = 0

        for raster_path in manifest.paths():
            mosaics_seen += 1

            try:
                raster = RasterFileRef.from_path(raster_path)
                branch = request.run_tree.plant_mosaic_branch(raster.mid)

                plan_path = branch.manifest_dir / (
                    f"tile_plan_{request.spec.tile_size}_{request.spec.stride}.csv"
                )

                if plan_path.exists() and not request.force:
                    plans_skipped += 1
                    continue

                planner = GDALWindowPlanner(raster_path, request.spec)
                TilePlanCSV(plan_path).write(planner.rows())
                plans_written += 1

            except Exception:
                errors += 1

        return PlanTilesResult(
            mosaics_seen=mosaics_seen,
            plans_written=plans_written,
            plans_skipped=plans_skipped,
            errors=errors,
            code=0 if errors == 0 else 1,
        )


from __future__ import annotations

from whirlwind.commands.bridge import RequestBuilder, TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.config import Config
from whirlwind.bridges.tile.plan_tiles import PlanTilesRequest
from whirlwind.specs.tiling import TSpec


class PlanTilesRequestBuilder(RequestBuilder[PlanTilesRequest]):
    def from_tokens(self, tokens: list[str], config: Config) -> PlanTilesRequest:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("catalog", "manifest")

        return PlanTilesRequest(
            run_tree=ctx.run_tree,
            manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
            spec=TSpec.from_config(config),
            force=tv.has("-f", "--force"),
        )

from whirlwind.commands.bridge import ResultPresenter
from whirlwind.bridges.tile.plan_tiles import PlanTilesResult
from whirlwind.ui import face


class PlanTilesPresenter(ResultPresenter[PlanTilesResult]):
    def show(self, result: PlanTilesResult) -> int:
        face.info("tile plans")
        face.prog_row("mosaics", result.mosaics_seen)
        face.prog_row("written", result.plans_written)
        face.prog_row("skipped", result.plans_skipped)
        face.prog_row("errors", result.errors)
        return result.code

from __future__ import annotations

from dataclasses import dataclass

from whirlwind.adapters.geo.damage_labeler import DamageLabeler
from whirlwind.adapters.geo.window_reader_rasterio import RasterioWindowReader
from whirlwind.adapters.io.id_manifest_csv import IDManifestCSV
from whirlwind.adapters.io.shard_tar import (
    ShardRequest,
    SplitTarShardWriter,
    TarShardWriter,
)
from whirlwind.adapters.io.tile_manifest_csv import TileManifestCSV
from whirlwind.adapters.io.tile_plan_csv import TilePlanCSV
from whirlwind.domain.filetree.file_ref import RasterFileRef
from whirlwind.domain.filetree.run_tree import RunTree
from whirlwind.domain.geometry.tile import TileEncoder
from whirlwind.specs.shard import ShardSpec
from whirlwind.specs.tiling import TSpec


@dataclass(frozen=True)
class TesselateRequest:
    run_tree: RunTree
    manifest_name: str
    tiling: TSpec
    shard: ShardSpec
    split_by_damage: bool = False
    use_damage_labels: bool = False
    force: bool = False


@dataclass(frozen=True)
class TesselateResult:
    mosaics_seen: int
    tiles_written: int
    errors: int
    code: int = 0


class TesselateBridge:
    def run(self, request: TesselateRequest) -> TesselateResult:
        manifest_path = request.run_tree.manifest_csv(request.manifest_name)
        manifest = IDManifestCSV(manifest_path)

        if not manifest.exists():
            raise FileNotFoundError(f"ID manifest does not exist: {manifest_path}")

        mosaics_seen = 0
        tiles_written = 0
        errors = 0

        for raster_path in manifest.paths():
            mosaics_seen += 1

            try:
                tiles_written += self._one_mosaic(raster_path, request)
            except Exception:
                errors += 1

        return TesselateResult(
            mosaics_seen=mosaics_seen,
            tiles_written=tiles_written,
            errors=errors,
            code=0 if errors == 0 else 1,
        )

    def _one_mosaic(self, raster_path, request: TesselateRequest) -> int:
        raster = RasterFileRef.from_path(raster_path)
        branch = request.run_tree.plant_mosaic_branch(raster.mid)

        plan_path = branch.manifest_dir / (
            f"tile_plan_{request.tiling.tile_size}_{request.tiling.stride}.csv"
        )

        if not plan_path.exists():
            raise FileNotFoundError(f"tile plan missing: {plan_path}")

        plan_reader = TilePlanCSV(plan_path)
        encoder = TileEncoder(src=raster)

        shard_request = ShardRequest(
            out_dir=branch.shards_dir,
            prefix=request.shard.prefix or raster.mid,
            shard_size=request.shard.shard_size,
        )

        manifest_writer = TileManifestCSV(branch.manifest_dir / "tile_manifest.csv")

        writer_cls = SplitTarShardWriter if request.split_by_damage else TarShardWriter

        written = 0

        with writer_cls(shard_request) as shard_writer:
            with RasterioWindowReader(raster_path) as reader:
                labeler = None

                if request.use_damage_labels:
                    labeler = DamageLabeler.from_gpkg(
                        gpkg_path=branch.browse_dir / "damaged_geometry.gpkg",
                        area_layer="damage_area",
                        line_layer="damage_path",
                        target_crs=reader.ds.crs,
                    )

                for tile in reader.tiles_from_rows(plan_reader.read()):
                    if labeler is not None:
                        tile = labeler.label(tile)

                    encoded = encoder.encode(tile)
                    placement = shard_writer.write(encoded)
                    manifest_writer.write_encoded(encoded, placement.shard_path)
                    written += 1

        manifest_writer.close()
        return written

from whirlwind.commands.bridge import RequestBuilder, TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.config import Config
from whirlwind.bridges.tile.tesselate import TesselateRequest
from whirlwind.specs.tiling import TSpec
from whirlwind.specs.shard import ShardSpec


class TesselateRequestBuilder(RequestBuilder[TesselateRequest]):
    def from_tokens(self, tokens: list[str], config: Config) -> TesselateRequest:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("catalog", "manifest")
        tess_cfg = ctx.section("tile", "tesselate")

        shard = ShardSpec(
            shard_size=int(tess_cfg.get("shard_size", 2048)),
            prefix=str(tess_cfg.get("shard_prefix", "tiles")),
            manifest_kind=str(tess_cfg.get("manifest", "csv")),
        )

        return TesselateRequest(
            run_tree=ctx.run_tree,
            manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
            tiling=TSpec.from_config(config),
            shard=shard,
            split_by_damage=tv.has("--split", "-s")
            or bool(tess_cfg.get("split_by_damage", False)),
            use_damage_labels=tv.has("--labels", "-l")
            or bool(tess_cfg.get("use_damage_labels", False)),
            force=tv.has("-f", "--force"),
        )


from whirlwind.commands.bridge import ResultPresenter
from whirlwind.bridges.tile.tesselate import TesselateResult
from whirlwind.ui import face


class TesselatePresenter(ResultPresenter[TesselateResult]):
    def show(self, result: TesselateResult) -> int:
        face.info("tesselate")
        face.prog_row("mosaics", result.mosaics_seen)
        face.prog_row("tiles written", result.tiles_written)
        face.prog_row("errors", result.errors)
        return result.code

from __future__ import annotations

from dataclasses import dataclass

from whirlwind.adapters.geo.damage_gpkg import DamagePathPlanner, PathPlan
from whirlwind.adapters.io.id_manifest_csv import IDManifestCSV
from whirlwind.domain.filetree.file_ref import RasterFileRef
from whirlwind.domain.filetree.run_tree import RunTree
from whirlwind.specs.path import PathSpec


@dataclass(frozen=True)
class PlanPathsRequest:
    run_tree: RunTree
    manifest_name: str
    path_spec: PathSpec
    overwrite: bool = False


@dataclass(frozen=True)
class PlanPathsResult:
    mosaics_seen: int
    plans_written: int
    errors: int
    code: int = 0


class PlanPathsBridge:
    def run(self, request: PlanPathsRequest) -> PlanPathsResult:
        manifest_path = request.run_tree.manifest_csv(request.manifest_name)
        manifest = IDManifestCSV(manifest_path)

        if not manifest.exists():
            raise FileNotFoundError(f"ID manifest does not exist: {manifest_path}")

        mosaics_seen = 0
        plans_written = 0
        errors = 0

        for raster_path in manifest.paths():
            mosaics_seen += 1

            try:
                raster = RasterFileRef.from_path(raster_path, georefs=True)
                branch = request.run_tree.plant_mosaic_branch(raster.mid)

                plan = PathPlan.from_browse(
                    branch=branch,
                    crs_wkt=raster.crs_wkt,
                    spec=request.path_spec,
                )

                DamagePathPlanner.make_plan(plan, overwrite=request.overwrite)
                plans_written += 1

            except Exception:
                errors += 1

        return PlanPathsResult(
            mosaics_seen=mosaics_seen,
            plans_written=plans_written,
            errors=errors,
            code=0 if errors == 0 else 1,
        )

from whirlwind.commands.bridge import RequestBuilder, TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.config import Config
from whirlwind.bridges.label.plan_paths import PlanPathsRequest
from whirlwind.specs.path import PathSpec


class PlanPathsRequestBuilder(RequestBuilder[PlanPathsRequest]):
    def from_tokens(self, tokens: list[str], config: Config) -> PlanPathsRequest:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("catalog", "manifest")

        return PlanPathsRequest(
            run_tree=ctx.run_tree,
            manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
            path_spec=PathSpec.default(),
            overwrite=tv.has("-f", "--force", "--overwrite"),
        )
    from whirlwind.commands.bridge import ResultPresenter
from whirlwind.bridges.label.plan_paths import PlanPathsResult
from whirlwind.ui import face


class PlanPathsPresenter(ResultPresenter[PlanPathsResult]):
    def show(self, result: PlanPathsResult) -> int:
        face.info("path plans")
        face.prog_row("mosaics", result.mosaics_seen)
        face.prog_row("plans written", result.plans_written)
        face.prog_row("errors", result.errors)
        return result.code

from __future__ import annotations

from dataclasses import dataclass

from whirlwind.adapters.geo.downsampler import GDALDownsampler
from whirlwind.adapters.geo.display_stretch import estimate_display_range
from whirlwind.adapters.io.id_manifest_csv import IDManifestCSV
from whirlwind.domain.filetree.file_ref import RasterFileRef
from whirlwind.domain.filetree.run_tree import RunTree
from whirlwind.specs.downsample import DSSpec


@dataclass(frozen=True)
class DownsampleRequest:
    run_tree: RunTree
    manifest_name: str
    spec: DSSpec
    overwrite: bool = False


@dataclass(frozen=True)
class DownsampleResult:
    mosaics_seen: int
    rasters_written: int
    errors: int
    code: int = 0


class DownsampleBridge:
    def run(self, request: DownsampleRequest) -> DownsampleResult:
        manifest_path = request.run_tree.manifest_csv(request.manifest_name)
        manifest = IDManifestCSV(manifest_path)

        if not manifest.exists():
            raise FileNotFoundError(f"ID manifest does not exist: {manifest_path}")

        mosaics_seen = 0
        rasters_written = 0
        errors = 0

        for raster_path in manifest.paths():
            mosaics_seen += 1

            try:
                raster = RasterFileRef.from_path(raster_path)
                branch = request.run_tree.plant_mosaic_branch(raster.mid)

                out_path = branch.browse_dir / f"browse-{raster.mid}.tif"

                display_range = None
                if request.spec.display.enabled:
                    display_range = estimate_display_range(
                        raster_path,
                        request.spec.display,
                    )

                downsampler = GDALDownsampler.from_paths(
                    src_path=raster_path,
                    out_path=out_path,
                    spec=request.spec,
                )

                downsampler.run(
                    overwrite=request.overwrite,
                    disp_range=display_range,
                )

                rasters_written += 1

            except Exception:
                errors += 1

        return DownsampleResult(
            mosaics_seen=mosaics_seen,
            rasters_written=rasters_written,
            errors=errors,
            code=0 if errors == 0 else 1,
        )

from whirlwind.commands.bridge import RequestBuilder, TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.config import Config
from whirlwind.bridges.mosaic.downsample import DownsampleRequest
from whirlwind.specs.downsample import DSSpec


class DownsampleRequestBuilder(RequestBuilder[DownsampleRequest]):
    def from_tokens(self, tokens: list[str], config: Config) -> DownsampleRequest:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("catalog", "manifest")

        return DownsampleRequest(
            run_tree=ctx.run_tree,
            manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
            spec=DSSpec.from_config(config),
            overwrite=tv.has("-f", "--force", "--overwrite"),
        )

from whirlwind.commands.bridge import ResultPresenter
from whirlwind.bridges.mosaic.downsample import DownsampleResult
from whirlwind.ui import face


class DownsamplePresenter(ResultPresenter[DownsampleResult]):
    def show(self, result: DownsampleResult) -> int:
        face.info("downsample")
        face.prog_row("mosaics", result.mosaics_seen)
        face.prog_row("written", result.rasters_written)
        face.prog_row("errors", result.errors)
        return result.code

from dataclasses import dataclass

from whirlwind.commands.base import Command
from whirlwind.commands.bridge import BridgeCommand
from whirlwind.config import Config

from whirlwind.commands.catalog_requests import (
    BuildIDManifestRequestBuilder,
    BuildMetadataRequestBuilder,
)
from whirlwind.commands.catalog_presenters import (
    BuildIDManifestPresenter,
    BuildMetadataPresenter,
)
from whirlwind.bridges.catalog.build_id_manifest import BuildIDManifestBridge
from whirlwind.bridges.catalog.build_metadata import BuildMetadataBridge

from whirlwind.commands.tile_requests import (
    PlanTilesRequestBuilder,
    TesselateRequestBuilder,
)
from whirlwind.commands.tile_presenters import (
    PlanTilesPresenter,
    TesselatePresenter,
)
from whirlwind.bridges.tile.plan_tiles import PlanTilesBridge
from whirlwind.bridges.tile.tesselate import TesselateBridge

from whirlwind.commands.label_requests import PlanPathsRequestBuilder
from whirlwind.commands.label_presenters import PlanPathsPresenter
from whirlwind.bridges.label.plan_paths import PlanPathsBridge

from whirlwind.commands.mosaic_requests import DownsampleRequestBuilder
from whirlwind.commands.mosaic_presenters import DownsamplePresenter
from whirlwind.bridges.mosaic.downsample import DownsampleBridge


BuildIDManifestCommand = BridgeCommand(
    name="ids",
    builder=BuildIDManifestRequestBuilder(),
    bridge=BuildIDManifestBridge(),
    presenter=BuildIDManifestPresenter(),
)

BuildMetadataCommand = BridgeCommand(
    name="meta",
    builder=BuildMetadataRequestBuilder(),
    bridge=BuildMetadataBridge(),
    presenter=BuildMetadataPresenter(),
)

PlanTilesCommand = BridgeCommand(
    name="tileplan",
    builder=PlanTilesRequestBuilder(),
    bridge=PlanTilesBridge(),
    presenter=PlanTilesPresenter(),
)

TesselateCommand = BridgeCommand(
    name="tile",
    builder=TesselateRequestBuilder(),
    bridge=TesselateBridge(),
    presenter=TesselatePresenter(),
)

PlanPathsCommand = BridgeCommand(
    name="pathplan",
    builder=PlanPathsRequestBuilder(),
    bridge=PlanPathsBridge(),
    presenter=PlanPathsPresenter(),
)

DownsampleCommand = BridgeCommand(
    name="downsample",
    builder=DownsampleRequestBuilder(),
    bridge=DownsampleBridge(),
    presenter=DownsamplePresenter(),
)


@dataclass
class Test(Command):
    name = "test"

    def run(self, tokens: list[str], config: Config) -> int:
        if not tokens:
            return 1

        match tokens[0]:
            case "ids":
                return BuildIDManifestCommand.run(tokens[1:], config)

            case "meta":
                return BuildMetadataCommand.run(tokens[1:], config)

            case "tileplan":
                return PlanTilesCommand.run(tokens[1:], config)

            case "tile":
                return TesselateCommand.run(tokens[1:], config)

            case "pathplan":
                return PlanPathsCommand.run(tokens[1:], config)

            case "downsample":
                return DownsampleCommand.run(tokens[1:], config)

            case _:
                return 3





