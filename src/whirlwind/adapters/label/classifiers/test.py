from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import rasterio
from pyproj import CRS
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from whirlwind.adapters.label.label_protocol import Labeler
from whirlwind.adapters.label.labels.damage_review_label import DamageReviewLabel
from whirlwind.domain.tile import Tile

from whirlwind.bridges.specs.review_route_spec import DRSpec 
from whirlwind.bridges.specs.path import PreparedPathGeometry

DAMAGE_REVIEW_ROOT = "damage_review"

from dataclasses import dataclass, field
from math import exp
from pathlib import Path
from typing import Any

import geopandas as gpd
import rasterio
from pyproj import CRS
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from whirlwind.adapters.label.label_protocol import Labeler
from whirlwind.domain.tile import Tile


DAMAGE_REVIEW_ROOT = "damage_review"


# ---------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class ContinuousDamageScore:
    """
    Per-tile scoring diagnostics.
    """

    damage_likelihood: float

    area_intersection_score: float
    area_distance_score: float
    centerline_distance_score: float
    semantic_score: float

    debris_score: float
    structure_score: float
    tree_score: float

    def metadata(self) -> dict[str, Any]:
        return {
            "damage_likelihood": self.damage_likelihood,
            "area_intersection_score": self.area_intersection_score,
            "area_distance_score": self.area_distance_score,
            "centerline_distance_score": self.centerline_distance_score,
            "semantic_score": self.semantic_score,
            "debris_score": self.debris_score,
            "structure_score": self.structure_score,
            "tree_score": self.tree_score,
        }


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def gaussian_distance_score(distance: float | None, sigma: float) -> float:
    """
    Smooth distance decay.

    distance = 0       -> 1.0
    distance = sigma   -> ~0.367
    distance = 2*sigma -> ~0.018
    """
    if distance is None:
        return 0.0

    if sigma <= 0:
        return 0.0

    d = max(0.0, float(distance))
    return clamp01(exp(-((d / sigma) ** 2)))


def noisy_or(*weighted_scores: float) -> float:
    """
    Combine positive evidence without letting the sum exceed 1.0.

    This is useful because multiple weak signals should compound:

        near path + near area + debris-looking

    without requiring one signal to dominate.
    """
    p_not = 1.0

    for score in weighted_scores:
        s = clamp01(score)
        p_not *= 1.0 - s

    return clamp01(1.0 - p_not)


# ---------------------------------------------------------------------
# label
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class ContinuousDamageReviewLabel:
    """
    Label compatible with Whirlwind's current Label protocol.

    Important:
        damage_label is intentionally None.

    This router creates review/candidate labels, not final training truth.
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

    mosaic_bounds: tuple[float, float, float, float] | None
    mosaic_crs: str | None
    geometry_clipped_to_mosaic_context: bool

    score: ContinuousDamageScore
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
                "mosaic_bounds": self.mosaic_bounds,
                "mosaic_crs": self.mosaic_crs,
                "geometry_clipped_to_mosaic_context": self.geometry_clipped_to_mosaic_context,
                "score": self.score.metadata(),
                "semantic": self.semantic,
                **self.extra,
            }
        }


# ---------------------------------------------------------------------
# prepared master geometry
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedMasterDamageGeometry:
    """
    Master damage geometry prepared for one mosaic.

    The master GPKG may cover an entire metamosaic. This object contains
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

    mosaic_bounds: tuple[float, float, float, float]
    mosaic_crs: str | None

    clipped_to_mosaic_context: bool

    @property
    def has_geometry(self) -> bool:
        return bool(self.lines or self.areas)


# ---------------------------------------------------------------------
# continuous router / classifier
# ---------------------------------------------------------------------


class ContinuousDamageReviewLabeler(Labeler):
    """
    Continuous damage-review router.

    This is spatial-first and review-first:

        - centerline distance drives review likelihood
        - damage-area distance/intersection drives review likelihood
        - semantic evidence can only increase likelihood
        - semantic evidence cannot assign no-damage
        - semantic evidence cannot create hard negatives

    It returns review buckets, not final labels.
    """

    def __init__(
        self,
        *,
        prepared_geometry: PreparedMasterDamageGeometry,
        config: ContinuousDamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
    ) -> None:
        self.geometry = prepared_geometry
        self.config = config or ContinuousDamageRoutingConfig()
        self.semantic_labeler = semantic_labeler

    @classmethod
    def from_master_gpkg_for_mosaic(
        cls,
        *,
        master_gpkg_path: str | Path,
        mosaic_path: str | Path,
        line_layer: str = "geom_line",
        area_layer: str = "geom_area",
        config: ContinuousDamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
        metamosaic_id: str | None = None,
        line_id_field: str | None = None,
        area_id_field: str | None = None,
    ) -> "ContinuousDamageReviewLabeler":
        cfg = config or ContinuousDamageRoutingConfig()

        with rasterio.open(mosaic_path) as ds:
            mosaic_bounds = tuple(float(v) for v in ds.bounds)
            mosaic_crs = ds.crs

        prepared = load_master_damage_geometry_for_mosaic(
            master_gpkg_path=master_gpkg_path,
            line_layer=line_layer,
            area_layer=area_layer,
            mosaic_bounds=mosaic_bounds,
            mosaic_crs=mosaic_crs,
            context_distance=cfg.geometry_context_distance,
            metamosaic_id=metamosaic_id,
            line_id_field=line_id_field,
            area_id_field=area_id_field,
        )

        return cls(
            prepared_geometry=prepared,
            config=cfg,
            semantic_labeler=semantic_labeler,
        )

    @classmethod
    def no_geometry(
        cls,
        *,
        mosaic_path: str | Path,
        config: ContinuousDamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
        metamosaic_id: str | None = None,
    ) -> "ContinuousDamageReviewLabeler":
        with rasterio.open(mosaic_path) as ds:
            mosaic_bounds = tuple(float(v) for v in ds.bounds)
            mosaic_crs = _crs_text(ds.crs)

        prepared = PreparedMasterDamageGeometry(
            lines=(),
            areas=(),
            line_ids=(),
            area_ids=(),
            line_union=None,
            area_union=None,
            master_gpkg_path=None,
            line_layer="",
            area_layer="",
            metamosaic_id=metamosaic_id,
            mosaic_bounds=mosaic_bounds,
            mosaic_crs=mosaic_crs,
            clipped_to_mosaic_context=False,
        )

        return cls(
            prepared_geometry=prepared,
            config=config or ContinuousDamageRoutingConfig(),
            semantic_labeler=semantic_labeler,
        )

    def label(self, tile: Tile) -> ContinuousDamageReviewLabel:
        semantic = self._semantic_metadata(tile)

        if tile.geo is None:
            score = self._score(
                intersects_damage_area=False,
                tile_center_inside_damage_area=False,
                distance_to_damage_centerline=None,
                distance_to_damage_area=None,
                semantic=semantic,
            )

            return self._make_label(
                bucket=f"{DAMAGE_REVIEW_ROOT}/no_tile_geo",
                dominant="no_tile_geo",
                damage_likelihood=0.0,
                route_source="missing_tile_geo",
                review_required=True,
                review_reason="tile.geo is None; cannot route spatially",
                intersects_damage_area=False,
                tile_center_inside_damage_area=False,
                distance_to_damage_centerline=None,
                distance_to_damage_area=None,
                nearest_damage_line_id=None,
                nearest_damage_area_id=None,
                score=score,
                semantic=semantic,
            )

        if not self.geometry.has_geometry:
            score = self._score(
                intersects_damage_area=False,
                tile_center_inside_damage_area=False,
                distance_to_damage_centerline=None,
                distance_to_damage_area=None,
                semantic=semantic,
            )

            return self._make_label(
                bucket=f"{DAMAGE_REVIEW_ROOT}/no_master_damage_geometry",
                dominant="no_master_damage_geometry",
                damage_likelihood=0.50,
                route_source="no_master_damage_geometry",
                review_required=True,
                review_reason="no master damage geometry available near this mosaic",
                intersects_damage_area=False,
                tile_center_inside_damage_area=False,
                distance_to_damage_centerline=None,
                distance_to_damage_area=None,
                nearest_damage_line_id=None,
                nearest_damage_area_id=None,
                score=score,
                semantic=semantic,
            )

        spatial = self._tile_spatial_state(tile)

        score = self._score(
            intersects_damage_area=spatial["intersects_damage_area"],
            tile_center_inside_damage_area=spatial["tile_center_inside_damage_area"],
            distance_to_damage_centerline=spatial["distance_to_damage_centerline"],
            distance_to_damage_area=spatial["distance_to_damage_area"],
            semantic=semantic,
        )

        bucket, dominant, review_required = self._bucket_for_score(
            score.damage_likelihood
        )

        return self._make_label(
            bucket=bucket,
            dominant=dominant,
            damage_likelihood=score.damage_likelihood,
            route_source="continuous_damage_score",
            review_required=review_required,
            review_reason=f"continuous_damage_likelihood={score.damage_likelihood:.4f}",
            intersects_damage_area=spatial["intersects_damage_area"],
            tile_center_inside_damage_area=spatial["tile_center_inside_damage_area"],
            distance_to_damage_centerline=spatial["distance_to_damage_centerline"],
            distance_to_damage_area=spatial["distance_to_damage_area"],
            nearest_damage_line_id=spatial["nearest_damage_line_id"],
            nearest_damage_area_id=spatial["nearest_damage_area_id"],
            score=score,
            semantic=semantic,
        )

    def _semantic_metadata(self, tile: Tile) -> dict[str, Any]:
        """
        Semantic output is diagnostic and positive-only.

        It must not set damage_label=False.
        It must not create hard-negative buckets.
        """
        if self.semantic_labeler is None:
            return {}

        if not self.config.use_semantic_metadata:
            return {}

        semantic_label = self.semantic_labeler.label(tile)

        payload = semantic_label.metadata()
        semantic = payload.get("semantic", {})

        return {
            "bucket": semantic.get("bucket"),
            "dominant": semantic.get("dominant"),
            "accepted": semantic.get("accepted"),
            "confidence": semantic.get("confidence"),
            "confidence_score": semantic.get("confidence_score"),
            "top_class": semantic.get("top_class"),
            "top_score": semantic.get("top_score"),
            "second_class": semantic.get("second_class"),
            "second_score": semantic.get("second_score"),
            "margin": semantic.get("margin"),
            "top_detailed_class": semantic.get("top_detailed_class"),
            "top_detailed_score": semantic.get("top_detailed_score"),
            "second_detailed_class": semantic.get("second_detailed_class"),
            "detail_margin": semantic.get("detail_margin"),
            "detail_agrees": semantic.get("detail_agrees"),
            "review_reasons": semantic.get("review_reasons", []),
            "final_scores": semantic.get("final_scores", {}),
            "detailed_scores": semantic.get("detailed_scores", {}),
        }

    def _tile_spatial_state(self, tile: Tile) -> dict[str, Any]:
        assert tile.geo is not None

        minx, miny, maxx, maxy = tile.geo.bounds
        footprint = box(minx, miny, maxx, maxy)
        center = Point((minx + maxx) / 2.0, (miny + maxy) / 2.0)

        intersects_damage_area = False
        tile_center_inside_damage_area = False

        if self.geometry.area_union is not None:
            intersects_damage_area = footprint.intersects(self.geometry.area_union)
            tile_center_inside_damage_area = self.geometry.area_union.contains(center)

        distance_to_area = None
        nearest_area_id = None
        if self.geometry.areas:
            distance_to_area, area_i = min(
                (
                    (center.distance(area), i)
                    for i, area in enumerate(self.geometry.areas)
                ),
                key=lambda x: x[0],
            )
            nearest_area_id = self.geometry.area_ids[area_i]

        distance_to_line = None
        nearest_line_id = None
        if self.geometry.lines:
            distance_to_line, line_i = min(
                (
                    (center.distance(line), i)
                    for i, line in enumerate(self.geometry.lines)
                ),
                key=lambda x: x[0],
            )
            nearest_line_id = self.geometry.line_ids[line_i]

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

    def _score(
        self,
        *,
        intersects_damage_area: bool,
        tile_center_inside_damage_area: bool,
        distance_to_damage_centerline: float | None,
        distance_to_damage_area: float | None,
        semantic: dict[str, Any],
    ) -> ContinuousDamageScore:
        cfg = self.config.score_config

        area_intersection_score = 1.0 if (
            intersects_damage_area or tile_center_inside_damage_area
        ) else 0.0

        area_distance_score = gaussian_distance_score(
            distance_to_damage_area,
            cfg.sigma_area,
        )

        centerline_distance_score = gaussian_distance_score(
            distance_to_damage_centerline,
            cfg.sigma_centerline,
        )

        semantic_score, semantic_parts = self._semantic_positive_score(
            semantic=semantic,
            centerline_distance_score=centerline_distance_score,
        )

        damage_likelihood = noisy_or(
            cfg.area_intersection_weight * area_intersection_score,
            cfg.area_distance_weight * area_distance_score,
            cfg.centerline_distance_weight * centerline_distance_score,
            cfg.semantic_weight * semantic_score,
        )

        return ContinuousDamageScore(
            damage_likelihood=damage_likelihood,
            area_intersection_score=area_intersection_score,
            area_distance_score=area_distance_score,
            centerline_distance_score=centerline_distance_score,
            semantic_score=semantic_score,
            debris_score=semantic_parts["debris_score"],
            structure_score=semantic_parts["structure_score"],
            tree_score=semantic_parts["tree_score"],
        )

    def _semantic_positive_score(
        self,
        *,
        semantic: dict[str, Any],
        centerline_distance_score: float,
    ) -> tuple[float, dict[str, float]]:
        """
        Positive-only semantic score.

        The classifier can increase review priority for debris-looking,
        structure-looking, or tree-looking tiles, especially near the path.

        It cannot reduce review priority.
        """
        cfg = self.config.score_config

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
        semantic_positive += cfg.debris_bonus * debris_score

        # Structures/trees are not damage by themselves.
        # They only boost if the tile is spatially near the path.
        semantic_positive += (
            cfg.structure_near_path_bonus
            * structure_score
            * centerline_distance_score
        )
        semantic_positive += (
            cfg.tree_near_path_bonus
            * tree_score
            * centerline_distance_score
        )

        semantic_positive *= margin_factor
        semantic_positive = min(semantic_positive, cfg.max_semantic_score)

        return clamp01(semantic_positive), {
            "debris_score": debris_score,
            "structure_score": structure_score,
            "tree_score": tree_score,
        }

    def _bucket_for_score(self, score: float) -> tuple[str, str, bool]:
        cfg = self.config.score_config

        if score >= cfg.likely_damage_min:
            return (
                f"{DAMAGE_REVIEW_ROOT}/01_likely_damage",
                "likely_damage",
                True,
            )

        if score >= cfg.possible_damage_min:
            return (
                f"{DAMAGE_REVIEW_ROOT}/02_possible_damage",
                "possible_damage",
                True,
            )

        if score >= cfg.near_context_min:
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
        score: ContinuousDamageScore,
        semantic: dict[str, Any],
    ) -> ContinuousDamageReviewLabel:
        return ContinuousDamageReviewLabel(
            bucket=bucket,
            dominant=dominant,
            damage_likelihood=damage_likelihood,
            damage_label=None,
            route_source=route_source,
            review_required=review_required,
            review_reason=review_reason,
            has_master_damage_geometry=self.geometry.has_geometry,
            intersects_damage_area=intersects_damage_area,
            tile_center_inside_damage_area=tile_center_inside_damage_area,
            distance_to_damage_centerline=distance_to_damage_centerline,
            distance_to_damage_area=distance_to_damage_area,
            nearest_damage_line_id=nearest_damage_line_id,
            nearest_damage_area_id=nearest_damage_area_id,
            metamosaic_id=self.geometry.metamosaic_id,
            master_gpkg_path=_path_text(self.geometry.master_gpkg_path),
            damage_line_layer=self.geometry.line_layer,
            damage_area_layer=self.geometry.area_layer,
            mosaic_bounds=self.geometry.mosaic_bounds,
            mosaic_crs=self.geometry.mosaic_crs,
            geometry_clipped_to_mosaic_context=self.geometry.clipped_to_mosaic_context,
            score=score,
            semantic=semantic,
            extra={
                "router_version": self.config.router_version,
                "geometry_context_distance": self.config.geometry_context_distance,
                "sigma_centerline": self.config.score_config.sigma_centerline,
                "sigma_area": self.config.score_config.sigma_area,
            },
        )


# ---------------------------------------------------------------------
# geometry loading
# ---------------------------------------------------------------------


def load_master_damage_geometry_for_mosaic(
    *,
    master_gpkg_path: str | Path,
    line_layer: str,
    area_layer: str,
    mosaic_bounds: tuple[float, float, float, float],
    mosaic_crs,
    context_distance: float,
    metamosaic_id: str | None = None,
    line_id_field: str | None = None,
    area_id_field: str | None = None,
) -> PreparedMasterDamageGeometry:
    gpkg = Path(master_gpkg_path)
    mosaic_crs_text = _crs_text(mosaic_crs)

    if not gpkg.exists():
        return _empty_prepared_geometry(
            gpkg=gpkg,
            line_layer=line_layer,
            area_layer=area_layer,
            metamosaic_id=metamosaic_id,
            mosaic_bounds=mosaic_bounds,
            mosaic_crs=mosaic_crs_text,
            clipped=False,
        )

    line_gdf = _safe_read_layer(gpkg, line_layer)
    area_gdf = _safe_read_layer(gpkg, area_layer)

    line_gdf = _to_crs_if_possible(line_gdf, mosaic_crs)
    area_gdf = _to_crs_if_possible(area_gdf, mosaic_crs)

    mosaic_poly = box(*mosaic_bounds)
    context_poly = mosaic_poly.buffer(float(context_distance))

    lines, line_ids = _clip_gdf_to_context(
        line_gdf,
        context_poly,
        fallback_prefix="line",
        id_field=line_id_field,
    )

    areas, area_ids = _clip_gdf_to_context(
        area_gdf,
        context_poly,
        fallback_prefix="area",
        id_field=area_id_field,
    )

    return PreparedMasterDamageGeometry(
        lines=tuple(lines),
        areas=tuple(areas),
        line_ids=tuple(line_ids),
        area_ids=tuple(area_ids),
        line_union=_union_or_none(lines),
        area_union=_union_or_none(areas),
        master_gpkg_path=gpkg,
        line_layer=line_layer,
        area_layer=area_layer,
        metamosaic_id=metamosaic_id,
        mosaic_bounds=mosaic_bounds,
        mosaic_crs=mosaic_crs_text,
        clipped_to_mosaic_context=True,
    )


def _empty_prepared_geometry(
    *,
    gpkg: Path | None,
    line_layer: str,
    area_layer: str,
    metamosaic_id: str | None,
    mosaic_bounds: tuple[float, float, float, float],
    mosaic_crs: str | None,
    clipped: bool,
) -> PreparedMasterDamageGeometry:
    return PreparedMasterDamageGeometry(
        lines=(),
        areas=(),
        line_ids=(),
        area_ids=(),
        line_union=None,
        area_union=None,
        master_gpkg_path=gpkg,
        line_layer=line_layer,
        area_layer=area_layer,
        metamosaic_id=metamosaic_id,
        mosaic_bounds=mosaic_bounds,
        mosaic_crs=mosaic_crs,
        clipped_to_mosaic_context=clipped,
    )


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


def _score_for_class(
    semantic: dict[str, Any],
    final_scores: dict[str, Any],
    class_name: str,
) -> float:
    """
    Get class evidence without trusting the class as a final label.

    Prefer full final_scores if available.
    Fallback to top_class/top_score.
    """
    if class_name in final_scores:
        try:
            return clamp01(float(final_scores[class_name]))
        except Exception:
            return 0.0

    if semantic.get("top_class") == class_name:
        return clamp01(float(semantic.get("top_score") or 0.0))

    return 0.0


def _crs_text(crs) -> str | None:
    if crs is None:
        return None

    try:
        return CRS.from_user_input(crs).to_string()
    except Exception:
        return str(crs)


def _path_text(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _float_or_none(value: float | None) -> float | None:
    return None if value is None else float(value)

