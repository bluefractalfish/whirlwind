from dataclasses import replace 
from typing import Any
from pathlib import Path 
import geopandas as gpd 

from shapely.geometry import box, Point
from shapely.strtree import STRtree

from whirlwind.domain.tile import Tile

class BinaryLabelByIntersection:
    """ 
    used to calculate a tile's binary intersection with some geometry, e.g. like damage_path 

    usage 
    ------ 
    labeler = BinaryLabelByIntersection(
        geometry_name="trees" 
        geometry_areas=some_area_geoms,
        geometry_lines=some_line_geoms,
        )

    with WindowReader(raster_path) as reader:
        for tile in reader.tiles_from_rows(rows, masked=True, fill_value=0.0):
            tile = labeler.label(tile)
            encoded = encoder.encode(tile)
    """
    def __init__(self, geometry_name, areas_geometry, lines_geometry) -> None:
        self.areas_geometry = list(areas_geometry)
        self.lines_geometry = list(lines_geometry) 
        self.geometry_name = geometry_name

        self.area_index = STRtree(self.areas_geometry) if self.areas_geometry else None
        self.line_index = STRtree(self.lines_geometry) if self.lines_geometry else None

    @classmethod
    def from_gpkg(
            cls,
            gpkg_path: str | Path,
            *,
            area_layer: str,
            line_layer: str,
            target_crs,
        ) -> "BinaryLabelByIntersection":

            areas = gpd.read_file(gpkg_path, layer=area_layer)
            lines = gpd.read_file(gpkg_path, layer=line_layer)
            
            geo_name = Path(gpkg_path).name

            if areas.crs is not None and target_crs is not None:
                areas = areas.to_crs(target_crs)

            if lines.crs is not None and target_crs is not None:
                lines = lines.to_crs(target_crs)

            area_geoms = [
                geom for geom in areas.geometry
                if geom is not None and not geom.is_empty
            ]

            line_geoms = [
                geom for geom in lines.geometry
                if geom is not None and not geom.is_empty
            ]

            return cls(
                geometry_name=geo_name,
                areas_geometry=area_geoms,
                lines_geometry=line_geoms,
            )

    def label(self, tile: Tile, geometry_name) -> Tile:
        if tile.geo is None:
            return replace(tile, label={
                f"{geometry_name}": False, 
                f"intersects_{self.geometry_name}": False,
                "label_reason": "missing_geodata",
                f"distance_to_{self.geometry_name}_line": None,
            })

        minx, miny, maxx, maxy = tile.geo.bounds
        footprint = box(minx, miny, maxx, maxy)
        center = Point((minx + maxx) / 2.0, (miny + maxy) / 2.0)
        
        area_hits = []
        if self.area_index is not None:
            for idx in self.area_index.query(footprint):
                geom = self.areas_geometry[int(idx)]
                if footprint.intersects(geom):
                    area_hits.append(geom)


        line_dist = None
        if self.lines_geometry:
            line_dist = min(center.distance(line) for line in self.lines_geometry)

        label: dict[str, Any] = {
            f"{geometry_name}": bool(area_hits),
            f"intersects_{self.geometry_name}": bool(area_hits),
            "area_intersects": bool(area_hits),
            f"distance_to_{self.geometry_name}_line": line_dist,
        }

        return replace(tile, label=label)
