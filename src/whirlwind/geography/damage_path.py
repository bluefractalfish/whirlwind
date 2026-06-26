
from pathlib import Path 
from dataclasses import dataclass
from typing import Sequence, Any 

from shapely.geometry.base import BaseGeometry
from whirlwind.geography.bbox import BBox
from whirlwind.bridges.specs.path import PathSpec


import geopandas as gpd
import rasterio
from pyproj import CRS
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from whirlwind.domain.tile import Tile
from whirlwind.geography.bbox import BBox

@dataclass
class DamagePath: 
    spec: PathSpec
    clipped: bool 

    def __init__(self, 
                 gpkg_path: str | Path, 
                 line_layer: str, 
                 area_layer: str, 
                 line_id_field: str | None=None, 
                 area_id_field: str | None=None,
                 metamosaic_id: str | None=None 
                 ) -> None: 

        self.gpkg_path = Path(gpkg_path)
        self.line_layer = line_layer 
        self.area_layer = area_layer 
        self.line_id_field = line_id_field 
        self.area_id_field = area_id_field
        self.metamosaic_id = metamosaic_id 
    
    def crop_to(self, mosaic_path, context_distance: float) -> CroppedPathGeometry: 
 
        with rasterio.open(mosaic_path) as ds: 
            mosaic_bounds = BBox.from_bounds(ds.bounds) 
            mosaic_crs = ds.crs 
     
        return load_cropped_damage_path(
                master_gpkg_path = self.gpkg_path, 
                line_layer = self.line_layer, 
                area_layer = self.area_layer, 
                mosaic_bounds = mosaic_bounds, 
                mosaic_crs = mosaic_crs, 
                context_distance = context_distance, 
                metamosaic_id = self.metamosaic_id, 
                line_id_field = self.line_id_field, 
                area_id_field = self.area_id_field, 
                ) 

@dataclass(frozen=True)
class CroppedPathGeometry:
    """
    damage geometry prepared for one mosaic.

    master GPKG may cover an entire metamosaic. This object contains
    only the parts relevant to one raster/mosaic.
    """

    lines: tuple[BaseGeometry, ...]
    areas: tuple[BaseGeometry, ...]

    line_ids: tuple[str, ...]
    area_ids: tuple[str, ...]

    line_union: BaseGeometry | None
    area_union: BaseGeometry | None

    master_gpkg_path: Path | None
    line_layer: str
    area_layer: str

    metamosaic_id: str | None

    mosaic_bounds: BBox 
    mosaic_crs: str | None

    clipped_to_mosaic_context: bool

    @property
    def has_geometry(self) -> bool:
        return bool(self.lines or self.areas)


    def spatial_status(self, tile: Tile ) -> dict[str, Any]: 
        assert tile.geo is not None
        
        minx, miny, maxx, maxy = tile.geo.bounds
        footprint = box(minx, miny, maxx, maxy)
        center = Point((minx + maxx) / 2.0, (miny + maxy) / 2.0)

        intersects_damage_area = False
        tile_center_inside_damage_area = False

        if self.area_union is not None:
            intersects_damage_area = footprint.intersects(self.area_union)
            tile_center_inside_damage_area = self.area_union.contains(center)

        distance_to_area = None
        nearest_area_id = None
        if self.areas:
            distance_to_area, area_i = min(
                (
                    (center.distance(area), i)
                    for i, area in enumerate(self.areas)
                ),
                key=lambda x: x[0],
            )
            nearest_area_id = self.area_ids[area_i]

        distance_to_line = None
        nearest_line_id = None
        if self.lines:
            distance_to_line, line_i = min(
                (
                    (center.distance(line), i)
                    for i, line in enumerate(self.lines)
                ),
                key=lambda x: x[0],
            )
            nearest_line_id = self.line_ids[line_i]

        return {
            "tile_center_x": center.x,
            "tile_center_y": center.y,
            "intersects_damage_area": bool(intersects_damage_area),
            "tile_center_inside_damage_area": bool(tile_center_inside_damage_area),
            "distance_to_damage_centerline": _float_or_none(distance_to_line),
            "distance_to_damage_area": _float_or_none(distance_to_area),
            "nearest_damage_line_id": nearest_line_id,
            "nearest_damage_area_id": nearest_area_id,
        }

def load_cropped_damage_path(
        *, 
        master_gpkg_path: str | Path, 
        line_layer: str, 
        area_layer: str, 
        mosaic_bounds: BBox, 
        mosaic_crs, 
        context_distance: float, 
        metamosaic_id: str | None = None, 
        line_id_field: str | None = None, 
        area_id_field: str | None = None, 
) -> CroppedPathGeometry: 
        
        gpkg = Path(master_gpkg_path) 
        mosaic_crs_txt = _crs_text(mosaic_crs)
        
        if not gpkg.exists():
            raise FileNotFoundError 

        line_geoframe = _safe_read_layer(gpkg, line_layer)
        area_geoframe = _safe_read_layer(gpkg, area_layer)

        line_geoframe = _to_crs_if_possible(line_geoframe, mosaic_crs)
        area_geoframe = _to_crs_if_possible(area_geoframe, mosaic_crs)
        
        mosaic_poly = box(*mosaic_bounds.as_tuple)
        context_poly = mosaic_poly.buffer(float(context_distance))

        lines, line_ids = _clip_gdf_to_context(
                line_geoframe, 
                context_poly, 
                fallback_prefix="line",
                id_field=line_id_field
                )

        areas, area_ids = _clip_gdf_to_context(
                area_geoframe, 
                context_poly, 
                fallback_prefix="area", 
                id_field=area_id_field
                )

        return CroppedPathGeometry(
                lines = tuple(lines), 
                areas = tuple(areas), 
                line_ids = tuple(line_ids), 
                area_ids = tuple(area_ids), 
                line_union = _union_or_none(lines), 
                area_union = _union_or_none(areas), 
                master_gpkg_path=gpkg, 
                line_layer = line_layer, 
                area_layer = area_layer, 
                metamosaic_id = metamosaic_id, 
                mosaic_bounds = mosaic_bounds, 
                mosaic_crs = mosaic_crs_txt, 
                clipped_to_mosaic_context=True
            )

def _crs_text(crs) -> str | None: 
    if crs is None: 
        return None 
    try: 
        return CRS.from_user_input(crs).to_string()
    except Exception: 
        return str(crs)


def _safe_read_layer(gpkg: Path, layer: str) -> gpd.GeoDataFrame:
    try:
        return gpd.read_file(gpkg, layer=layer)
    except Exception:
        return gpd.GeoDataFrame(geometry=[], crs=None)


def _to_crs_if_possible(gdf: gpd.GeoDataFrame, target_crs) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf

    if target_crs is None:
        return gdf

    if gdf.crs is None:
        return gdf

    try:
        return gdf.to_crs(target_crs)
    except Exception:
        return gdf


def _clip_gdf_to_context(
    gdf: gpd.GeoDataFrame,
    context_poly: BaseGeometry,
    *,
    fallback_prefix: str,
    id_field: str | None,
) -> tuple[list[BaseGeometry], list[str]]:
    geoms: list[BaseGeometry] = []
    ids: list[str] = []

    if gdf.empty:
        return geoms, ids

    for i, row in gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if not geom.intersects(context_poly):
            continue

        clipped = geom.intersection(context_poly)

        if clipped.is_empty:
            continue

        geoms.append(clipped)

        if id_field and id_field in row and row[id_field] is not None:
            ids.append(str(row[id_field]))
        else:
            ids.append(f"{fallback_prefix}_{i}")

    return geoms, ids


def _union_or_none(geoms: list[BaseGeometry]) -> BaseGeometry | None:
    if not geoms:
        return None

    if len(geoms) == 1:
        return geoms[0]

    return unary_union(geoms)

def _float_or_none(value: float | None) -> float | None:
    return None if value is None else float(value)
