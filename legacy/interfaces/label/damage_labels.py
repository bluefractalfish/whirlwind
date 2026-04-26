from dataclasses import replace 
from typing import Any
from pathlib import Path 
import geopandas as gpd 

from shapely.geometry import box, Point
from shapely.strtree import STRtree

from whirlwind.geometry.tile import Tile

class DamageLabeler:
    """ 


    usage 
    ------ 
    labeler = DamageLabeler(
        damage_areas=damage_area_geoms,
        damage_lines=damage_line_geoms,
        )

    with WindowReader(raster_path) as reader:
        for tile in reader.tiles_from_rows(rows, masked=True, fill_value=0.0):
            tile = labeler.label(tile)
            encoded = encoder.encode(tile)
    """
    def __init__(self, damage_areas, damage_lines) -> None:
        self.damage_areas = list(damage_areas)
        self.damage_lines = list(damage_lines)

        self.area_index = STRtree(self.damage_areas) if self.damage_areas else None
        self.line_index = STRtree(self.damage_lines) if self.damage_lines else None

    @classmethod
    def from_gpkg(
            cls,
            gpkg_path: str | Path,
            *,
            area_layer: str,
            line_layer: str,
            target_crs,
        ) -> "DamageLabeler":

            areas = gpd.read_file(gpkg_path, layer=area_layer)
            lines = gpd.read_file(gpkg_path, layer=line_layer)

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
                damage_areas=area_geoms,
                damage_lines=line_geoms,
            )

    def label(self, tile: Tile) -> Tile:
        if tile.geo is None:
            return replace(tile, label={
                "damage": False,
                "label_reason": "missing_geodata",
                "distance_to_damage_line": None,
            })

        minx, miny, maxx, maxy = tile.geo.bounds
        footprint = box(minx, miny, maxx, maxy)
        center = Point((minx + maxx) / 2.0, (miny + maxy) / 2.0)
        
        area_hits = []
        if self.area_index is not None:
            for idx in self.area_index.query(footprint):
                geom = self.damage_areas[int(idx)]
                if footprint.intersects(geom):
                    area_hits.append(geom)


        line_dist = None
        if self.damage_lines:
            line_dist = min(center.distance(line) for line in self.damage_lines)

        label: dict[str, Any] = {
            "damage": bool(area_hits),
            "damage_area_intersects": bool(area_hits),
            "distance_to_damage_line": line_dist,
        }

        return replace(tile, label=label)
