
import json 
from dataclasses import dataclass, field, asdict 
from pathlib import Path
from typing import Optional, Sequence
from osgeo import gdal, ogr, osr 
from whirlwind.specs.path import PathSpec 
from whirlwind.filetrees.mosaicbranch import MosaicBranch

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
        mosaic_id = self.branch.mosaic_id
        browse_uri = self.branch.browse_dir

        return {
                "mosaic_id": str(mosaic_id),
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

        DamagePathPlanner.make_plan(plan)
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

    @classmethod 
    def make_plan(cls, plan: PathPlan, overwrite: bool = False) -> None:
        # make sure this mosaic branch exists 
        plan.branch.ensure()
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
            # damage_path, damage_area, etc
            for layer_spec in plan.spec.layers: 
                layer = ds.CreateLayer(
                        layer_spec.name, 
                        srs=srs, 
                        geom_type=cls._geometry_type(layer_spec.geometry),
                        )
                if layer is None:
                    raise RuntimeError(f"failed to create layer: {layer_spec.name}") 
                # path_id, mosaic_id, source_uri, etc...
                for fld in layer_spec.fields: 
                    defn = ogr.FieldDefn(fld.name, cls._field_type(fld.kind))
                    if fld.kind == "str":
                        defn.SetWidth(254)
                    # create layer from field definition 
                    rc = layer.CreateField(defn)
                    if rc != 0:
                        raise RuntimeError(
                        f"failed to create field: {fld.name} on {layer_spec.name}")
        finally:
            ds = None
        meta = plan.meta() 
        with plan.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    

