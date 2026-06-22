from whirlwind.prompts.tile_classes import FINAL_CLASSES


DETAILED_CLASSES: tuple[str, ...] = (
    # structures
    "residential_roof",
    "large_structure_roof",
    "small_outbuilding_roof",
    "damaged_structure_roof",
    "roofless_structure_remains",

    # roads
    "paved_road",
    "gravel_road",
    "full_width_dirt_road",
    "parking_or_driveway",
    "rural_access_road",
    "damaged_road_surface",

    # vehicle tracks
    "paired_tire_ruts",
    "paired_tire_ruts_in_grass",
    "paired_tire_ruts_in_dirt",
    "paired_tire_ruts_through_crops",

    # trees
    "single_tree_crown",
    "dense_tree_canopy",
    "conifer_tree_canopy",
    "damaged_or_downed_tree",

    # grass
    "mowed_grass",
    "rough_grassland",
    "pasture_or_meadow",

    # dirt
    "bare_soil",
    "disturbed_bare_ground",

    # crops
    "green_crop_rows",
    "bare_soil_crop_rows",

    # debris
    "rubble_or_scattered_debris",
)


DETAILED_TO_FINAL: dict[str, str] = {
    # structures
    "residential_roof": "structures",
    "large_structure_roof": "structures",
    "small_outbuilding_roof": "structures",
    "damaged_structure_roof": "structures",
    "roofless_structure_remains": "structures",

    # roads
    "paved_road": "roads",
    "gravel_road": "roads",
    "full_width_dirt_road": "roads",
    "parking_or_driveway": "roads",
    "rural_access_road": "roads",
    "damaged_road_surface": "roads",

    # vehicle tracks
    "paired_tire_ruts": "vehicle_tracks",
    "paired_tire_ruts_in_grass": "vehicle_tracks",
    "paired_tire_ruts_in_dirt": "vehicle_tracks",
    "paired_tire_ruts_through_crops": "vehicle_tracks",

    # trees
    "single_tree_crown": "trees",
    "dense_tree_canopy": "trees",
    "conifer_tree_canopy": "trees",
    "damaged_or_downed_tree": "trees",

    # grass
    "mowed_grass": "grass",
    "rough_grassland": "grass",
    "pasture_or_meadow": "grass",

    # dirt
    "bare_soil": "dirt",
    "disturbed_bare_ground": "dirt",

    # crops
    "green_crop_rows": "crops",
    "bare_soil_crop_rows": "crops",

    # debris
    "rubble_or_scattered_debris": "debris",
}


PROMPTS_BY_DETAILED_CLASS: dict[str, tuple[str, ...]] = {
    # structures
    "residential_roof": (
        "single family house roof with rectangular footprint",
        "residential rooftop with straight edges, roof planes, and corners",
        "house roof surface with visible man made geometry",
        "small residential building roof footprint",
    ),
    "large_structure_roof": (
        "large commercial, industrial, warehouse, barn, or institutional roof",
        "broad rectilinear rooftop footprint",
        "large building roof with straight man made boundaries",
        "wide roof surface distinct from parking, road, field, or bare ground",
    ),
    "small_outbuilding_roof": (
        "shed, garage, barn annex, pump house, or compact outbuilding roof",
        "small rectangular roofed structure",
        "compact roof footprint with clear corners",
        "small roofed object in a yard, farm lot, or field edge",
    ),
    "damaged_structure_roof": (
        "storm damaged roof with missing sections or torn covering",
        "broken building roof with exposed framing or displaced roof material",
        "damaged structure footprint with roof damage still visible",
        "partially destroyed roof attached to a building footprint",
    ),
    "roofless_structure_remains": (
        "roofless structure with slab, foundation, or wall grid",
        "building footprint remains with rectilinear layout",
        "standing walls, slab, foundation, or destroyed structure outline",
        "structure remains with clear man made geometry",
    ),

    # roads
    "paved_road": (
        "asphalt or concrete road surface",
        "paved street, lane, highway, residential road, or driveway",
        "continuous paved vehicle corridor with visible road width",
        "pavement with road alignment, lane markings, or continuous edges",
    ),
    "gravel_road": (
        "full-width gravel road surface",
        "pale gravel vehicle corridor with continuous surface width",
        "maintained gravel road wide enough for cars or trucks",
        "gravel roadway with visible corridor edges",
    ),
    "full_width_dirt_road": (
        "full-width compacted dirt road surface",
        "continuous dirt vehicle corridor wide enough for cars or trucks",
        "maintained dirt road with visible surface width",
        "dirt roadway with continuous travel surface and corridor shape",
    ),
    "parking_or_driveway": (
        "driveway, parking pad, parking lot, paved apron, or vehicle access surface",
        "parking surface connected to a building or road",
        "man made parking or driveway area",
        "vehicle parking or driveway surface with continuous width",
    ),
    "rural_access_road": (
        "rural access road with full vehicle width",
        "farm road, ranch road, service road, or maintained rural vehicle corridor",
        "continuous unpaved vehicle route through fields, dirt, or trees",
        "rural road surface wide enough for cars or trucks",
    ),
    "damaged_road_surface": (
        "damaged road with washout, cracks, erosion, debris, or blockage",
        "broken or obstructed road corridor",
        "road surface damage while the road alignment remains visible",
        "cracked, blocked, eroded, or partially obstructed vehicle surface",
    ),

    # vehicle tracks
    "paired_tire_ruts": (
        "two separated parallel tire ruts with a visible center strip",
        "paired narrow wheel marks with regular vehicle spacing",
        "left and right tire paths separated by grass, dirt, mud, or crops",
        "two thin parallel rut lines made by vehicle wheels",
    ),
    "paired_tire_ruts_in_grass": (
        "two separated tire ruts pressed through grass",
        "paired wheel paths with grass visible between the ruts",
        "parallel tire marks crossing herbaceous vegetation",
        "vehicle rut pair in pasture, lawn, meadow, or grassland",
    ),
    "paired_tire_ruts_in_dirt": (
        "two separated tire ruts in bare dirt, mud, or soil",
        "paired wheel marks with exposed soil between the ruts",
        "parallel tire-rut geometry in dirt or mud",
        "left and right rut lines impressed into bare ground",
    ),
    "paired_tire_ruts_through_crops": (
        "two vehicle wheel paths cutting across crop rows",
        "paired tire ruts crossing planted agricultural rows",
        "vehicle rut pair superimposed on crop texture",
        "parallel wheel marks with crop rows visible around or between them",
    ),

    # trees
    "single_tree_crown": (
        "isolated tree crown with organic outline",
        "single woody canopy object",
        "one tree crown with irregular branch and canopy texture",
        "individual broadleaf or evergreen tree crown",
    ),
    "dense_tree_canopy": (
        "dense connected tree canopy",
        "overlapping woody crowns and canopy shadows",
        "forest canopy with irregular organic texture",
        "multiple tree crowns forming continuous woody cover",
    ),
    "conifer_tree_canopy": (
        "evergreen or conifer tree canopy",
        "dark textured pine, cedar, or evergreen crowns",
        "conifer crowns with organic pointed canopy texture",
        "dense evergreen woody vegetation",
    ),
    "damaged_or_downed_tree": (
        "snapped, uprooted, or downed tree",
        "broken tree crown, fallen trunk, branches, or root ball",
        "damaged woody canopy or fallen woody material",
        "tree damage with visible branches, trunks, or broken crowns",
    ),

    # grass
    "mowed_grass": (
        "short maintained lawn or mowed grass",
        "smooth uniform low herbaceous cover",
        "fine grass texture in a yard or open lawn",
        "low grass without woody canopy or agricultural row pattern",
    ),
    "rough_grassland": (
        "rough grassland or unmanaged herbaceous cover",
        "pasture, meadow, or field grass with uneven low vegetation",
        "open low vegetation without crop row geometry",
        "continuous grasslike ground cover",
    ),
    "pasture_or_meadow": (
        "open pasture or meadow",
        "low herbaceous field cover",
        "grasslike vegetation without planted row spacing",
        "open non-woody vegetation surface",
    ),

    # dirt
    "bare_soil": (
        "exposed bare soil",
        "brown or tan dirt surface",
        "natural bare ground with irregular earth texture",
        "open non-vegetated soil surface",
    ),
    "disturbed_bare_ground": (
        "scraped, graded, churned, excavated, or disturbed earth",
        "irregular disturbed soil",
        "bare ground with rough disturbed texture",
        "construction-like or storm-disturbed earth surface",
    ),

    # crops
    "green_crop_rows": (
        "green crops arranged in repeated rows",
        "cultivated vegetation with regular agricultural spacing",
        "planted field rows with repeated geometry",
        "green crop row texture across a field",
    ),
    "bare_soil_crop_rows": (
        "agricultural rows cut into bare soil",
        "brown soil planting rows or field beds",
        "cultivated furrow pattern in exposed earth",
        "repeated bare-soil crop row geometry",
    ),

    # debris
    "rubble_or_scattered_debris": (
        "scattered debris, rubble, wreckage, or broken fragments",
        "chaotic broken material on the ground",
        "storm debris field or rubble pile",
        "loose fragmented material with irregular shapes",
    ),
}


FINAL_TO_DETAILED_CLASSES: dict[str, tuple[str, ...]] = {
    final_class: tuple(
        detailed_class
        for detailed_class in DETAILED_CLASSES
        if DETAILED_TO_FINAL.get(detailed_class) == final_class
    )
    for final_class in FINAL_CLASSES
}
