
from dataclasses import dataclass 

@dataclass(frozen=True)
class DamageRoutingConfig:
    """
    all distance metrics are in raster CRS units.

    CRS projected in meters -> meters. 

    if CRS is geographic degrees, reproject before using these as meters
    """

    likely_damage_distance: float = 50.0
    possible_damage_distance: float = 150.0
    near_context_distance: float = 500.0

    use_semantic_metadata: bool = True

    semantic_review_subfolders: bool = False

    router_version: str = "damage_review_v1"


class DamageReviewLabeler:
    """
    Damage-oriented router.

    This does not try to solve land-cover classification.
    It answers:

        how likely is this tile to be useful for wind-damage training?

    Spatial labels are primary.
    Semantic labels are secondary metadata / hard-negative hints.
    """

    def __init__(
        self,
        *,
        areas_geometry,
        lines_geometry,
        config: DamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
    ) -> None:
        self.areas_geometry = list(areas_geometry)
        self.lines_geometry = list(lines_geometry)
        self.config = config or DamageRoutingConfig()
        self.semantic_labeler = semantic_labeler

        self.area_index = STRtree(self.areas_geometry) if self.areas_geometry else None
        self.line_index = STRtree(self.lines_geometry) if self.lines_geometry else None

    @classmethod
    def no_geometry(
        cls,
        *,
        config: DamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
    ) -> "DamageReviewLabeler":
        return cls(
            areas_geometry=[],
            lines_geometry=[],
            config=config,
            semantic_labeler=semantic_labeler,
        )

    @classmethod
    def from_gpkg(
        cls,
        gpkg_path: str | Path,
        *,
        area_layer: str,
        line_layer: str,
        target_crs=None,
        config: DamageRoutingConfig | None = None,
        semantic_labeler: Labeler | None = None,
    ) -> "DamageReviewLabeler":
        gpkg_path = Path(gpkg_path)

        if not gpkg_path.exists():
            return cls.no_geometry(
                config=config,
                semantic_labeler=semantic_labeler,
            )

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
            areas_geometry=area_geoms,
            lines_geometry=line_geoms,
            config=config,
            semantic_labeler=semantic_labeler,
        )

    def _semantic_metadata(self, tile: Tile) -> dict[str, Any]:
        if self.semantic_labeler is None:
            return {}

        semantic_label = self.semantic_labeler.label(tile)
        semantic = semantic_label.metadata().get("semantic", {})

        return {
            "semantic_bucket": semantic.get("bucket"),
            "semantic_dominant": semantic.get("dominant"),
            "semantic_confidence": semantic.get("confidence"),
            "semantic_confidence_score": semantic.get("confidence_score"),
            "semantic_top_class": semantic.get("top_class"),
            "semantic_top_score": semantic.get("top_score"),
            "semantic_second_class": semantic.get("second_class"),
            "semantic_second_score": semantic.get("second_score"),
            "semantic_margin": semantic.get("margin"),
            "semantic_raw": semantic,
        }

    def _spatial_state(self, tile: Tile) -> dict[str, Any]:
        if tile.geo is None:
            return {
                "has_geometry": False,
                "footprint": None,
                "center": None,
                "intersects_damage_area": False,
                "inside_damage_area": False,
                "distance_to_damage_line": None,
            }

        minx, miny, maxx, maxy = tile.geo.bounds
        footprint = box(minx, miny, maxx, maxy)
        center = Point((minx + maxx) / 2.0, (miny + maxy) / 2.0)

        area_hits = []
        if self.area_index is not None:
            for idx in self.area_index.query(footprint):
                geom = self.areas_geometry[int(idx)]
                if footprint.intersects(geom):
                    area_hits.append(geom)

        inside_damage_area = any(geom.contains(center) for geom in area_hits)

        distance_to_line = None
        if self.lines_geometry:
            distance_to_line = min(center.distance(line) for line in self.lines_geometry)

        return {
            "has_geometry": bool(self.areas_geometry or self.lines_geometry),
            "footprint": footprint,
            "center": center,
            "intersects_damage_area": bool(area_hits),
            "inside_damage_area": bool(inside_damage_area),
            "distance_to_damage_line": distance_to_line,
        }

    def _hard_negative_bucket(self, semantic: dict[str, Any]) -> str | None:
        if not self.config.use_semantic_hard_negatives:
            return None

        top = semantic.get("semantic_top_class") or semantic.get("semantic_dominant")
        confidence = semantic.get("semantic_confidence")

        if top in self.config.hard_negative_classes and confidence in {"high", "medium"}:
            return f"{HARD_NEGATIVE_ROOT}/{top}"

        return None

    def label(self, tile: Tile) -> DamageReviewLabel:
        spatial = self._spatial_state(tile)
        semantic = self._semantic_metadata(tile)

        has_geometry = bool(spatial["has_geometry"])
        intersects_area = bool(spatial["intersects_damage_area"])
        inside_area = bool(spatial["inside_damage_area"])
        distance = spatial["distance_to_damage_line"]

        # No hand-labeled damage geometry exists.
        # Still route tiles, but force review because there is no spatial truth.
        if not has_geometry:
            hard_negative = self._hard_negative_bucket(semantic)

            if hard_negative is not None:
                return DamageReviewLabel(
                    bucket=hard_negative,
                    dominant="hard_negative",
                    damage_label=False,
                    damage_likelihood=0.05,
                    route_source="semantic_hard_negative_no_geometry",
                    review_required=False,
                    review_reason="no_damage_geometry_semantic_hard_negative",
                    **semantic,
                )

            return DamageReviewLabel(
                bucket=f"{DAMAGE_REVIEW_ROOT}/no_damage_geometry",
                dominant="unknown_damage",
                damage_label=None,
                damage_likelihood=0.50,
                route_source="no_damage_geometry",
                review_required=True,
                review_reason="no damage gpkg or no drawn damage features",
                **semantic,
            )

        # Strongest spatial positive candidate.
        if inside_area or intersects_area:
            return DamageReviewLabel(
                bucket=f"{DAMAGE_REVIEW_ROOT}/01_likely_damage",
                dominant="likely_damage",
                damage_label=None,
                damage_likelihood=0.90,
                route_source="damage_area_intersection",
                inside_damage_area=inside_area,
                intersects_damage_area=intersects_area,
                distance_to_damage_line=distance,
                review_required=True,
                review_reason="tile intersects hand labeled damage area",
                **semantic,
            )

        # Near damage path: likely useful review candidate.
        if distance is not None and distance <= self.config.possible_damage_distance:
            return DamageReviewLabel(
                bucket=f"{DAMAGE_REVIEW_ROOT}/02_possible_damage",
                dominant="possible_damage",
                damage_label=None,
                damage_likelihood=0.65,
                route_source="near_damage_line",
                inside_damage_area=False,
                intersects_damage_area=False,
                distance_to_damage_line=distance,
                review_required=True,
                review_reason=f"distance_to_damage_line <= {self.config.possible_damage_distance}",
                **semantic,
            )

        # Context zone: useful negatives or boundary cases.
        if distance is not None and distance <= self.config.near_context_distance:
            hard_negative = self._hard_negative_bucket(semantic)

            if hard_negative is not None:
                return DamageReviewLabel(
                    bucket=hard_negative,
                    dominant="hard_negative",
                    damage_label=False,
                    damage_likelihood=0.10,
                    route_source="near_context_semantic_hard_negative",
                    inside_damage_area=False,
                    intersects_damage_area=False,
                    distance_to_damage_line=distance,
                    review_required=False,
                    review_reason="near damage path but semantic hard negative",
                    **semantic,
                )

            return DamageReviewLabel(
                bucket=f"{DAMAGE_REVIEW_ROOT}/03_near_context",
                dominant="near_context",
                damage_label=None,
                damage_likelihood=0.30,
                route_source="near_context_distance",
                inside_damage_area=False,
                intersects_damage_area=False,
                distance_to_damage_line=distance,
                review_required=True,
                review_reason=f"distance_to_damage_line <= {self.config.near_context_distance}",
                **semantic,
            )

        # Far from the hand-labeled path/area.
        hard_negative = self._hard_negative_bucket(semantic)

        if hard_negative is not None:
            return DamageReviewLabel(
                bucket=hard_negative,
                dominant="hard_negative",
                damage_label=False,
                damage_likelihood=0.02,
                route_source="far_semantic_hard_negative",
                inside_damage_area=False,
                intersects_damage_area=False,
                distance_to_damage_line=distance,
                review_required=False,
                review_reason="far from damage and semantic hard negative",
                **semantic,
            )

        return DamageReviewLabel(
            bucket=f"{DAMAGE_REVIEW_ROOT}/04_likely_negative",
            dominant="likely_negative",
            damage_label=False,
            damage_likelihood=0.05,
            route_source="far_from_damage_geometry",
            inside_damage_area=False,
            intersects_damage_area=False,
            distance_to_damage_line=distance,
            review_required=False,
            review_reason="far from hand labeled damage path/area",
            **semantic,
        )

