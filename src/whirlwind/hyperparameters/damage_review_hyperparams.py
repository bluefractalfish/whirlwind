
DAMAGE_REVIEW_HYPR_PARAMS = {
    # Distance decay in degrees.
    # Roughly:
    #   0.0005 deg ≈ 50–60 m
    #   0.0010 deg ≈ 100–110 m
    #   0.0030 deg ≈ 300–330 m
    #   0.0060 deg ≈ 600–660 m
    #
    # These are approximate because EPSG:4326 degrees are not true meters.

    "sigma_centerline": 0.0010,
    "sigma_area": 0.0007,

    "geometry_context_distance": 0.0060,

    # Evidence weights.
    "area_intersection_weight": 0.90,
    "area_distance_weight": 0.35,
    "centerline_distance_weight": 0.60,
    "semantic_weight": 0.10,

    # Semantic evidence should stay weak.
    "max_semantic_score": 0.20,
    "debris_bonus": 0.20,
    "structure_near_path_bonus": 0.06,
    "tree_near_path_bonus": 0.05,

    # Review-routing thresholds.
    "likely_damage_min": 0.70,
    "possible_damage_min": 0.35,
    "near_context_min": 0.10,
}
