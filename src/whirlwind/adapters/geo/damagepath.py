
import json 
from dataclasses import dataclass, field, asdict 
from pathlib import Path
from typing import Optional, Sequence
from osgeo import gdal, ogr, osr 
from datetime import datetime, timezone 
from whirlwind.bridges.specs.path import PathSpec 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch

@dataclass(frozen=True)
class PathPlan: 
    branch: MosaicBranch 
    gpkg_path: Path 
    metadata_path: Path 
    crs_wkt: str 
    spec: PathSpec 

    @classmethod 
    def from_browse(
            cls, 
            branch: MosaicBranch, 
            crs_wkt: str, 
            spec: Optional[PathSpec] = None 
            ) -> "PathPlan":

        # create empty gpkg 
        gpkg_path = branch.browse_dir / "staged_path.gpkg"
        meta_path = branch.manifest_dir / "path_plan.json"
        
        return cls(
                branch=branch, 
                gpkg_path=gpkg_path,
                metadata_path=meta_path, 
                crs_wkt = crs_wkt,
                spec = spec or PathSpec.default()
                )

    def record(self) -> dict[str, object]:
        out = asdict(self)
        out["browse_uri"] = str(self.branch.browse_dir)
        out["gpkg_path"] = str(self.gpkg_path)
        out["metadata_path"] = str(self.metadata_path)
        return out

    def meta(self) -> dict[str, object]:
        file_id = self.branch.file_id
        browse_uri = self.branch.browse_dir

        return {
                "file_id": str(file_id),
                "browse_uri": str(browse_uri),
                "gpkg_path": str(self.gpkg_path),
                "crs_wkt": self.crs_wkt,
                "layers": [
                    {
                        "name": lyr.name,
                        "geometry_type": lyr.geometry,
                        "fields": [f.__dict__ for f in lyr.fields],
                    }
                    for lyr in self.spec.layers
                ],
            }

    def dump_meta(self) -> Path:  
        meta = self.meta() 
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return self.metadata_path


    def field_defaults(self, layer_name: str) -> dict[str, object]:
            """
            default attribute values to attach to newly created GPKG fields.

            These become schema-level defaults in the GeoPackage, so QGIS can
            auto-populate them when drawing new features.
            """

            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            return {
                "path_id": f"{self.branch.file_id}-{layer_name}",
                "file_id": str(self.branch.file_id),
                "browse_uri": str(self.branch.browse_dir),
                "gpkg_path": str(self.gpkg_path),
                "metadata_path": str(self.metadata_path),
                "label_type": str(layer_name),
                "created_at": str(now),
                "updated_at": str(now),
            
                "event_date": "",

                "source_uri": "",
                "notes": "",
            }

class DamagePathPlanner: 
    """ 
        sets up empty gpkg files for damage path and polygon to be added from QGIS, etc 
        
        uses ogr.CreateField to instantiate field containers from PathPlan 
        
        Input 
        ---------- 
        PathPlan 

        Output 
        ---------
        creates empty gpkg files with PathPlan layers and fields 

        Usage 
        ---------- 
        plan = PathPlan.from_browse(
            branch = mosaic_branch, 
            out_root=labels_root,
            crs_wkt=crs_wkt,
        )

        DamagePathPlanner.stage(plan)
    """

    @staticmethod 
    def _geometry_type(name: str) -> int: 
        kinds = {
                "LineString": ogr.wkbLineString, 
                "Polygon": ogr.wkbPolygon, 
                }
        if name not in kinds:
            raise ValueError(f"unsupported geometr: {name}")
        return kinds[name] 

    @staticmethod 
    def _field_type(kind: str) -> int: 
        kinds = {
                "str": ogr.OFTString, 
                "int": ogr.OFTInteger,
                "float": ogr.OFTReal,
                "date": ogr.OFTDate 
                }
        if kind not in kinds:
            raise ValueError(f"unsupported field type: {kind}")
        return kinds[kind]

    @staticmethod
    def _ogr_default_string(value: object) -> str | None:
        """
        Convert a Python value into an OGR field default expression.
        only handles strings 
        OGR defaults are stored as expressions. String/date literals need quotes.
        """

        if value is None:
            return None

        text = str(value)

        if not text: 
            return None 
        
        return "'" + text.replace("'","''") + "'"

    @classmethod 
    def stage(cls, plan: PathPlan, overwrite: bool = False, set_defaults: bool = True) -> int:
        # make sure this mosaic branch exists  
        plan.branch.ensure()
        driver = ogr.GetDriverByName("GPKG") 
        if driver is None:
            raise RuntimeError("GPKG driver not available")
        if plan.gpkg_path.exists():
            if overwrite:
                driver.DeleteDataSource(str(plan.gpkg_path))
            else:
                return 2
        try:  
            cls._stage_layers(driver, plan, set_defaults)
        except RuntimeError as err:
            return 1
        plan.dump_meta() 
        return 0 
    
    @classmethod 
    def _stage_layers(cls, driver, plan, set_defaults) -> None: 
        ds = driver.CreateDataSource(str(plan.gpkg_path))
        if ds is None:
            raise RuntimeError(f"failed to create geopackage: {plan.gpkg_path}") 
        try:
            srs = osr.SpatialReference()
            if plan.crs_wkt:
                srs.ImportFromWkt(plan.crs_wkt)
            else:
                srs = None  
            # damage_path, damage_area, etc
            for layer_spec in plan.spec.layers: 
                layer = ds.CreateLayer(
                        layer_spec.name, 
                        srs=srs, 
                        geom_type=cls._geometry_type(layer_spec.geometry),
                        )
                if layer is None:
                    raise RuntimeError(f"failed to create layer: {layer_spec.name}") 

                # apply default values to fld from pathplan 
                defaults = plan.field_defaults(layer_spec.name)
                # path_id, file_id, source_uri, etc...
                for fld in layer_spec.fields: 
                    def_n = ogr.FieldDefn(fld.name, cls._field_type(fld.kind))
                    if fld.kind == "str":
                        def_n.SetWidth(254)
                    if set_defaults:
                        #default value 
                        def_v = defaults.get(fld.name)
                        #default, assumes can be stringified 
                        def_s = cls._ogr_default_string(def_v)
                        if def_s is not None: 
                            def_n.SetDefault(def_s) 
            
                    # create layer from field definition (and defaults) 
                    rc = layer.CreateField(def_n)
                    if rc != 0:
                        raise RuntimeError(
                        f"failed to create field: {fld.name} on {layer_spec.name}")
        finally:
            ds = None
