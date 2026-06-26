
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import rasterio
from pyproj import CRS
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from whirlwind.adapters.label.label_protocol import Labeler 
from whirlwind.adapters.label.classifiers.semantic_triage import SemanticLabelTriage
from whirlwind.domain.tile import Tile
from whirlwind.bridges.specs.review_route_spec import DRRoutingSpec, DRScoreSpec
from whirlwind.geography.damage_path import CroppedPathGeometry, DamagePath
from whirlwind.adapters.label.labels.damage_review_label import DamageReviewBucket, DamageScore
from whirlwind.operators.scoring_operators import ( 
                                gaussian_distance_score, 
                                clamp01,
                                noisy_or
                 )

from whirlwind.geography.bbox import BBox

DAMAGE_REVIEW_ROOT = "damage_review"

class DamageReviewLabeler(Labeler):
    """
    interface for PODClassifier and Label interface

    """
    def __init__(self, classifier: PODClassifier) -> None: 
        self.classifier = classifier 

    def label(self, tile: Tile) -> DamageReviewBucket:
        if tile.read is None:
            raise ValueError("tile cannot be read: no ReadTile found")
        return self.classifier.classify(tile)

class PODClassifier:  

    """
        spatial-first review-first p_damage classifier 
        
        tile -> P(damaged) derived from: 
            - distance from annotated centerline 
            - damage_area distance/intersection 
            - semantic evidence 
        based upon P(damage), assigns review buckets for manual labeling 


    """

    def __init__(
            self, 
            *, 
            cropped_geometry: CroppedPathGeometry, 
            spec: DRRoutingSpec | None = None, 
            semantic_labeler: SemanticLabelTriage | None = None, 
        ) -> None: 

            self.path_geometry = cropped_geometry 
            if not self.path_geometry.has_geometry:
                raise ValueError("no path gpkg found")

            self.spec = spec or DRRoutingSpec() 
            self.semantic_labeler = semantic_labeler 

    @classmethod
    def from_gpkg(
            cls, 
            *, 
            master_gpkg_path: str | Path, 
            mosaic_path: str | Path, 
            line_layer: str, 
            area_layer: str, 
            spec: DRRoutingSpec | None = None, 
            semantic_labeler: SemanticLabelTriage | None = None, 
            metamosaic_id: str | None = None, 
            line_id_field: str | None = None, 
            area_id_field: str | None = None, 
            ) -> "PODClassifier":

        spec = spec or DRRoutingSpec() 

        damage_path = DamagePath(
                gpkg_path = master_gpkg_path,
                line_layer = line_layer, 
                area_layer = area_layer, 
                line_id_field = line_id_field, 
                area_id_field = area_id_field, 
                metamosaic_id = metamosaic_id, 
                ) 

        cropped = damage_path.crop_to(mosaic_path, spec.geometry_context_distance)
        
        return PODClassifier(
                cropped_geometry=cropped, 
                spec = spec, 
                semantic_labeler = semantic_labeler)

        
    def classify(self, tile: Tile) -> DamageReviewBucket: 
        if tile.geo is None: 
            raise ValueError("tile.geo is None; cannot route spatially")

        semantic_data = self._semantic_metadata(tile)
        spatial_data = self._spatial_metadata(tile)
        
        score = self._score_from(spatial_data=spatial_data, semantic_data=semantic_data)

        bucket, dominant, review_required = self._bucket_by_score(
            score.p_damage
        )

        return self._make_label(
            bucket=bucket,
            dominant=dominant,
            damage_likelihood=score.p_damage,
            route_source="continuous_damage_score",
            review_required=review_required,
            review_reason=f"continuous_damage_likelihood={score.p_damage:.4f}",
            intersects_damage_area=spatial_data["intersects_damage_area"],
            tile_center_inside_damage_area=spatial_data["tile_center_inside_damage_area"],
            distance_to_damage_centerline=spatial_data["distance_to_damage_centerline"],
            distance_to_damage_area=spatial_data["distance_to_damage_area"],
            nearest_damage_line_id=spatial_data["nearest_damage_line_id"],
            nearest_damage_area_id=spatial_data["nearest_damage_area_id"],
            score=score,
            semantic=semantic_data,
        )

    def _semantic_metadata(self, tile: Tile) -> dict[str, Any]:

        if self.semantic_labeler is None:
            return {}
        if not self.spec.use_semantic_metadata:
            return {} 
        return self.semantic_labeler.metadata(tile) 


    def _spatial_metadata(self, tile: Tile) -> dict[str, Any]:
        return self.path_geometry.intersection_stats(tile)

    def _score_from(
        self,
        *,
        spatial_data: dict[str, Any],
        semantic_data: dict[str, Any],
    ) -> DamageScore: 
        
        score_spec = self.spec.score_config

        w_area_intersection = score_spec.area_distance_weight 
        w_area_distance = score_spec.area_distance_weight 
        w_centerline_distance = score_spec.centerline_distance_weight 
        w_semantic = score_spec.semantic_weight
        s_area = score_spec.sigma_area 
        s_centerline = score_spec.sigma_centerline 

        intersects_damage_area = spatial_data["intersects_damage_area"] 
        tile_center_inside_damage_area = spatial_data["tile_center_inside_damage_area"]
        distance_to_damage_area = spatial_data["distance_to_damage_area"]
        distance_to_damage_centerline = spatial_data["distance_to_damage_centerline"]

        
        area_intersection_score = 1.0 if (
            intersects_damage_area or tile_center_inside_damage_area
        ) else 0.0

        area_distance_score = gaussian_distance_score(
            distance_to_damage_area,
            s_area,
        )

        centerline_distance_score = gaussian_distance_score(
            distance_to_damage_centerline,
            s_centerline,
        )

        semantic_score, semantic_parts = self._semantic_positive_score(
            semantic=semantic_data,
            centerline_distance_score=centerline_distance_score,
        )

        damage_likelihood = noisy_or(
            w_area_intersection * area_intersection_score,
            w_area_distance * area_distance_score,
            w_centerline_distance * centerline_distance_score,
            w_semantic * semantic_score,
        )

        return DamageScore(
            p_damage=damage_likelihood,
            area_intersection_score=area_intersection_score,
            area_distance_score=area_distance_score,
            centerline_distance_score=centerline_distance_score,
            semantic_score=semantic_score,
            debris_score=semantic_parts["debris_score"],
            structure_score=semantic_parts["structure_score"],
            tree_score=semantic_parts["tree_score"],
            water_score=semantic_parts["water_score"]
        )

        
    def _semantic_positive_score(
        self,
        *,
        semantic: dict[str, Any],
        centerline_distance_score: float,
    ) -> tuple[float, dict[str, float]]:

        spec = self.spec.score_config

        final_scores = semantic.get("final_scores") or {}

        debris_score = _score_for_class(semantic, final_scores, "debris")
        structure_score = _score_for_class(semantic, final_scores, "structures")
        tree_score = _score_for_class(semantic, final_scores, "trees")

        confidence = semantic.get("confidence")
        margin = float(semantic.get("margin") or 0.0)

        if confidence not in {"medium", "high"}:
            return 0.0, {
                "debris_score": debris_score,
                "structure_score": structure_score,
                "tree_score": tree_score,
            }

        # De-emphasize semantic evidence when the classifier is nearly tied.
        margin_factor = clamp01(margin / 0.10)

        semantic_positive = 0.0

        # Debris can matter anywhere, but should remain weak.
        semantic_positive += spec.debris_bonus * debris_score

        # Structures/trees are not damage by themselves.
        # They only boost if the tile is spatially near the path.
        semantic_positive += (
            spec.structure_near_path_bonus
            * structure_score
            * centerline_distance_score
        )
        semantic_positive += (
            spec.tree_near_path_bonus
            * tree_score
            * centerline_distance_score
        )

        semantic_positive *= margin_factor
        semantic_positive = min(semantic_positive, spec.max_semantic_score)

        return clamp01(semantic_positive), {
            "debris_score": debris_score,
            "structure_score": structure_score,
            "tree_score": tree_score,
        }


    def _bucket_by_score(self, score: float) -> tuple[str, str, bool]:
        score_spec = self.spec.score_config

        if score >= score_spec.likely_damage_min:
            return (
                f"{DAMAGE_REVIEW_ROOT}/01_likely_damage",
                "likely_damage",
                True,
            )

        if score >= score_spec.possible_damage_min:
            return (
                f"{DAMAGE_REVIEW_ROOT}/02_possible_damage",
                "possible_damage",
                True,
            )

        if score >= score_spec.near_context_min:
            return (
                f"{DAMAGE_REVIEW_ROOT}/03_near_context",
                "near_context",
                True,
            )

        return (
            f"{DAMAGE_REVIEW_ROOT}/05_likely_negative_sample",
            "likely_negative_sample",
            False,
        )

    def _make_label(
        self,
        *,
        bucket: str,
        dominant: str,
        damage_likelihood: float,
        route_source: str,
        review_required: bool,
        review_reason: str,
        intersects_damage_area: bool,
        tile_center_inside_damage_area: bool,
        distance_to_damage_centerline: float | None,
        distance_to_damage_area: float | None,
        nearest_damage_line_id: str | None,
        nearest_damage_area_id: str | None,
        score: DamageScore,
        semantic: dict[str, Any],
    ) -> "DamageReviewBucket": 

        return DamageReviewBucket(
            bucket=bucket,
            dominant=dominant,
            damage_likelihood=damage_likelihood,
            damage_label=None,
            route_source=route_source,
            review_required=review_required,
            review_reason=review_reason,
            has_master_damage_geometry=self.path_geometry.has_geometry,
            intersects_damage_area=intersects_damage_area,
            tile_center_inside_damage_area=tile_center_inside_damage_area,
            distance_to_damage_centerline=distance_to_damage_centerline,
            distance_to_damage_area=distance_to_damage_area,
            nearest_damage_line_id=nearest_damage_line_id,
            nearest_damage_area_id=nearest_damage_area_id,
            metamosaic_id=self.path_geometry.metamosaic_id,
            master_gpkg_path=str(self.path_geometry.master_gpkg_path),
            damage_line_layer=self.path_geometry.line_layer,
            damage_area_layer=self.path_geometry.area_layer,
            mosaic_bounds=self.path_geometry.mosaic_bounds,
            mosaic_crs=self.path_geometry.mosaic_crs,
            geometry_clipped_to_mosaic_context=self.path_geometry.clipped_to_mosaic_context,
            score=score,
            semantic=semantic,
            extra={
                "router_version": self.spec.router_version,
                "geometry_context_distance": self.spec.geometry_context_distance,
                "sigma_centerline": self.spec.score_config.sigma_centerline,
                "sigma_area": self.spec.score_config.sigma_area,
            },
        )

def _score_for_class(
        semantic: dict[str, Any],
        final_scores: dict[str, Any],
        class_name: str,
    ) -> float:

        if class_name in final_scores:
            try:
                return clamp01(float(final_scores[class_name]))
            except Exception:
                return 0.0

        if semantic.get("top_class") == class_name:
            return clamp01(float(semantic.get("top_score") or 0.0))

        return 0.0



