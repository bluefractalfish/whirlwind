
from dataclasses import dataclass, field
from typing import Any
from whirlwind.geography.bbox import BBox
from whirlwind.bridges.specs.review_route_spec import DRScoreSpec

@dataclass
class DamageScore:

    p_damage: float

    area_intersection_score: float
    area_distance_score: float
    centerline_distance_score: float
    semantic_score: float

    debris_score: float
    structure_score: float
    tree_score: float

    def metadata(self) -> dict[str, Any]:
        return {
            "damage_likelihood": self.p_damage,
            "area_intersection_score": self.area_intersection_score,
            "area_distance_score": self.area_distance_score,
            "centerline_distance_score": self.centerline_distance_score,
            "semantic_score": self.semantic_score,
            "debris_score": self.debris_score,
            "structure_score": self.structure_score,
            "tree_score": self.tree_score,
        }

@dataclass 
class DamageReviewBucket:
    """

    damage_label is intentionally None. 
    
    this label is for the review of tiles to hand label damage or no damage 

    this router creates review/candidate labels, not final training truth.
    """

    bucket: str
    dominant: str

    damage_likelihood: float
    damage_label: bool | None

    route_source: str
    review_required: bool
    review_reason: str

    has_master_damage_geometry: bool

    intersects_damage_area: bool
    tile_center_inside_damage_area: bool

    distance_to_damage_centerline: float | None
    distance_to_damage_area: float | None

    nearest_damage_line_id: str | None
    nearest_damage_area_id: str | None

    metamosaic_id: str | None
    master_gpkg_path: str | None
    damage_line_layer: str
    damage_area_layer: str

    mosaic_bounds: BBox | None
    mosaic_crs: str | None
    geometry_clipped_to_mosaic_context: bool

    score: DamageScore
    semantic: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "damage_review": {
                "bucket": self.bucket,
                "dominant": self.dominant,
                "damage_likelihood": self.damage_likelihood,
                "damage_label": self.damage_label,
                "route_source": self.route_source,
                "review_required": self.review_required,
                "review_reason": self.review_reason,
                "has_master_damage_geometry": self.has_master_damage_geometry,
                "intersects_damage_area": self.intersects_damage_area,
                "tile_center_inside_damage_area": self.tile_center_inside_damage_area,
                "distance_to_damage_centerline": self.distance_to_damage_centerline,
                "distance_to_damage_area": self.distance_to_damage_area,
                "nearest_damage_line_id": self.nearest_damage_line_id,
                "nearest_damage_area_id": self.nearest_damage_area_id,
                "metamosaic_id": self.metamosaic_id,
                "master_gpkg_path": self.master_gpkg_path,
                "damage_line_layer": self.damage_line_layer,
                "damage_area_layer": self.damage_area_layer,
                "mosaic_bounds": self.mosaic_bounds.to_record() if self.mosaic_bounds 
                                    else "",
                "mosaic_crs": self.mosaic_crs,
                "geometry_clipped_to_mosaic_context": self.geometry_clipped_to_mosaic_context,
                "score": self.score.metadata(),
                "semantic": self.semantic,
                **self.extra,
            }
        }


