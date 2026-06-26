
from dataclasses import dataclass, field 
from whirlwind.hyperparameters.damage_review_hyperparams import (
        DAMAGE_REVIEW_HYPR_PARAMS as HYPR_PARAMS
    )


@dataclass(frozen=True)
class DRScoreSpec:
    """
    Damage Review Score threshold specs.
    """

    # distance to annotation decay scales.
    # Smaller sigma => score falls off faster with distance.
    sigma_centerline: float = HYPR_PARAMS["sigma_centerline"]
    sigma_area: float = HYPR_PARAMS["sigma_area"]

    # Positive evidence weights.
    area_intersection_weight: float = HYPR_PARAMS["area_intersection_weight"]
    area_distance_weight: float = HYPR_PARAMS["area_distance_weight"]
    centerline_distance_weight: float = HYPR_PARAMS["centerline_distance_weight"]
    semantic_weight: float = HYPR_PARAMS["semantic_weight"]

    # Semantic evidence is only allowed to increase review priority.
    # It must not decrease damage likelihood.
    max_semantic_score: float = HYPR_PARAMS["max_semantic_score"]

    debris_bonus: float = HYPR_PARAMS["debris_bonus"]
    structure_near_path_bonus: float = HYPR_PARAMS["structure_near_path_bonus"]
    tree_near_path_bonus: float = HYPR_PARAMS["tree_near_path_bonus"]

    # Bucket thresholds on final continuous score.
    likely_damage_min: float = HYPR_PARAMS["likely_damage_min"]
    possible_damage_min: float = HYPR_PARAMS["possible_damage_min"]
    near_context_min: float = HYPR_PARAMS["near_context_min"]


@dataclass(frozen=True)
class DRRoutingSpec:
    
    # effects how much of damage path that extends beyond mosaic is used 
    geometry_context_distance: float = HYPR_PARAMS["geometry_context_distance"]

    router_version: str = "damage_review_v1"

    use_semantic_metadata: bool = True
    score_config: DRScoreSpec = field(
        default_factory=DRScoreSpec
    )



