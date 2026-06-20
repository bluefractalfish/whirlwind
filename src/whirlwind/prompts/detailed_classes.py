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
    "parking_or_driveway",
    "damaged_road_surface",

    # vehicle tracks
    "two_rut_vehicle_track",
    "tire_rut_track",
    "field_access_track",
    "woodland_or_logging_track",
    "vehicle_tracks_through_crops",

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
    "parking_or_driveway": "roads",
    "damaged_road_surface": "roads",

    # vehicle tracks
    "two_rut_vehicle_track": "vehicle_tracks",
    "tire_rut_track": "vehicle_tracks",
    "field_access_track": "vehicle_tracks",
    "woodland_or_logging_track": "vehicle_tracks",
    "vehicle_tracks_through_crops": "vehicle_tracks",

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
        "a submeter nadir aerial image centered on an intact residential roof with straight roof edges, roof planes, and visible corners",
        "an overhead orthomosaic crop dominated by a house roof, not a road, driveway, crop row, tire track, grass field, or tree canopy",
        "a remote sensing image of a residential rooftop footprint with rectilinear boundaries and man made geometry",
        "a top down aerial tile where the main object is a single family house roof rather than pavement or parking surface",
    ),
    "large_structure_roof": (
        "an overhead aerial image dominated by a large commercial, industrial, farm, warehouse, or institutional roof",
        "a nadir remote sensing crop of a broad rectilinear rooftop footprint with straight man made boundaries",
        "an orthomosaic patch showing a large roof area distinct from roads, parking lots, bare soil, or fields",
        "a top down aerial tile dominated by building roof geometry rather than road corridor geometry",
    ),
    "small_outbuilding_roof": (
        "an overhead aerial image of a shed, garage, barn annex, pump house, or compact outbuilding roof",
        "a submeter remote sensing crop centered on a small rectangular roofed structure",
        "an orthomosaic patch showing a small roof footprint in a yard, farm lot, field edge, or property parcel",
        "a top down aerial tile dominated by a compact roof with clear corners and man made geometry",
    ),
    "damaged_structure_roof": (
        "an overhead aerial image of a storm damaged building roof with missing sections, exposed framing, torn covering, or displaced roof material",
        "a remote sensing crop of a damaged roof that is still clearly part of a structure footprint",
        "an orthomosaic patch showing a broken building roof with rectilinear remains and attached debris",
        "a top down aerial tile dominated by damaged structure geometry rather than generic rubble, trees, road, or dirt",
    ),
    "roofless_structure_remains": (
        "an overhead aerial image of a roofless structure, wall grid, slab, foundation, or building footprint remains",
        "a remote sensing crop of standing walls, slab, foundation, or footprint remains after a roof was lost",
        "an orthomosaic patch showing structure remains that are still clearly a building layout",
        "a top down aerial tile centered on a destroyed building footprint rather than random debris or road surface",
    ),

    # roads
    "paved_road": (
        "an overhead aerial image of asphalt or concrete road with continuous roadway geometry and road-like width",
        "a remote sensing crop of a paved street, lane, highway, or residential road and not a rooftop or two-rut track",
        "an orthomosaic patch of continuous transportation pavement with clear road alignment and surface width",
        "a top down aerial tile dominated by a paved road corridor rather than narrow paired tire ruts",
    ),
    "gravel_road": (
        "an overhead aerial image of a maintained gravel or compacted unpaved road with full road width and continuous corridor shape",
        "a remote sensing crop of pale gravel roadway or rural lane wide enough to be a road rather than a two-rut vehicle track",
        "an orthomosaic patch of rough road surface extending across the tile with consistent road corridor width and edges",
        "a top down aerial tile dominated by a gravel road or access road, not just wheel ruts through grass or dirt",
    ),
    "parking_or_driveway": (
        "an overhead aerial image of a driveway, parking pad, parking lot, paved apron, or vehicle access surface beside structures",
        "a remote sensing crop of vehicle access pavement connected to a building or road but not itself a roof",
        "an orthomosaic patch centered on man made parking, driveway, or paved access surface",
        "a top down aerial tile dominated by parking or driveway surface rather than a building roof or narrow dirt track",
    ),
    "damaged_road_surface": (
        "an overhead aerial image of a damaged road with washout, cracks, erosion, debris, or blockage while the road corridor remains visible",
        "a remote sensing crop of cracked, broken, blocked, eroded, or partially obstructed roadway",
        "an orthomosaic patch showing transportation surface damage but still clearly a road corridor",
        "a top down aerial tile dominated by damaged road surface rather than bare soil, tire ruts, or scattered debris alone",
    ),

    # vehicle tracks
    "two_rut_vehicle_track": (
        "an overhead aerial image of a two-rut vehicle track with two parallel worn tire paths and vegetation or soil between them",
        "a submeter remote sensing crop centered on a narrow two-track path crossing grass, dirt, crops, or open land",
        "an orthomosaic patch showing paired vehicle ruts that are too narrow and informal to be a road",
        "a top down aerial tile dominated by two parallel wheel paths rather than a maintained gravel road or crop rows",
        "an aerial image tile where the main feature is vehicle-caused paired wheel lines with regular spacing",
    ),
    "tire_rut_track": (
        "an overhead aerial image of tire ruts impressed into dirt, mud, grass, or disturbed soil",
        "a remote sensing crop dominated by wheel rut marks that form a vehicle path with regular linear spacing",
        "an orthomosaic patch showing vehicle tire disturbance and compacted ground rather than bare soil alone",
        "a top down aerial tile centered on tire tracks, rut scars, or vehicle passage marks",
        "an aerial image tile where tire-rut geometry is the dominant evidence, not crop rows, road pavement, or tornado damage marks",
    ),
    "field_access_track": (
        "an overhead aerial image of a farm field access track, service path, or narrow vehicle lane through a field",
        "a remote sensing crop of an informal track crossing crop rows, grassland, pasture, or bare agricultural ground",
        "an orthomosaic patch showing a narrow vehicle access route along a field edge or across cultivated land",
        "a top down aerial tile dominated by a field vehicle track and not by the crop rows themselves",
        "an aerial image tile where a vehicle path interrupts or crosses agricultural texture",
    ),
    "woodland_or_logging_track": (
        "an overhead aerial image of a narrow dirt or gravel vehicle track through trees, brush, forest edge, or woodland",
        "a remote sensing crop of a logging track, woodland access trail, or informal vehicle route partly covered by canopy",
        "an orthomosaic patch showing a narrow linear vehicle path through woody vegetation",
        "a top down aerial tile dominated by an unpaved access track between trees rather than tree canopy alone",
        "an aerial image tile where the main feature is a narrow vehicle corridor through vegetation",
    ),
    "vehicle_tracks_through_crops": (
        "an overhead aerial image of vehicle tire tracks crossing crop rows with paired wheel spacing different from the crop row pattern",
        "a remote sensing crop where vehicle ruts cut across or through agricultural rows rather than following the regular planting geometry",
        "an orthomosaic patch showing tractor or vehicle passage marks superimposed on crops",
        "a top down aerial tile where tire tracks are the main disturbance and crop rows are secondary background texture",
    ),

    # trees
    "single_tree_crown": (
        "a submeter overhead aerial image centered on one isolated tree crown with organic outline and canopy texture",
        "a remote sensing crop of a single woody canopy object separated from surrounding grass, dirt, road, or roof",
        "an orthomosaic patch dominated by one broadleaf tree crown with irregular edges and woody canopy texture",
        "a top down aerial tile centered on one tree crown and not on grass, crop rows, roof, road, or track",
    ),
    "dense_tree_canopy": (
        "a dense continuous stand of trees in overhead aerial imagery with overlapping woody crowns",
        "a remote sensing crop filled mostly by connected tree canopy and canopy shadows",
        "an orthomosaic patch of forest canopy with organic texture, crown boundaries, and irregular woody vegetation",
        "a top down aerial tile dominated by multiple tree canopies rather than low grass, pasture, or crop rows",
    ),
    "conifer_tree_canopy": (
        "an overhead aerial image of conifer or evergreen tree canopy with dark textured crowns and organic outlines",
        "a remote sensing crop of pine, cedar, or evergreen canopy and not smooth grass, crop rows, or dark road surface",
        "an orthomosaic patch dominated by dark evergreen crowns with visible tree texture",
        "a top down aerial tile centered on conifer canopy rather than low herbaceous vegetation",
    ),
    "damaged_or_downed_tree": (
        "an overhead aerial image of snapped, uprooted, or downed trees that are still visibly woody trees",
        "a remote sensing crop of damaged woody canopy, broken crowns, fallen trunks, branches, or uprooted root balls",
        "an orthomosaic patch showing tree damage rather than generic debris, bare soil, road, vehicle tracks, or grass",
        "a top down aerial tile dominated by damaged tree canopy, branches, trunks, or downed woody vegetation",
    ),

    # grass
    "mowed_grass": (
        "an overhead aerial image of maintained lawn or short mowed grass with smooth fine low vegetation texture",
        "a remote sensing crop of uniform low grass near structures, roads, driveways, or yards and not woody tree canopy",
        "an orthomosaic patch dominated by short even herbaceous ground cover without tree crown structure",
        "a top down aerial tile of lawn or mowed grass where roads, vehicle tracks, roofs, crop rows, and trees are not dominant",
    ),
    "rough_grassland": (
        "an overhead aerial image of pasture, meadow, field grass, or rough grassland without crop rows",
        "a remote sensing crop of low herbaceous cover with uneven grass texture and no woody crowns",
        "an orthomosaic patch dominated by rough grassland rather than planted agriculture, bare soil, road, or vehicle track",
        "a top down aerial tile of natural or unmanaged grass cover without dominant tire rut geometry",
    ),
    "pasture_or_meadow": (
        "an overhead aerial image of open pasture, meadow, or low herbaceous field cover",
        "a remote sensing crop dominated by grasslike vegetation without organized crop row spacing",
        "an orthomosaic patch of low vegetation where tree crowns, roads, structures, and vehicle tracks are not primary",
        "a top down aerial tile of open herbaceous cover rather than woody canopy or cultivated rows",
    ),

    # dirt
    "bare_soil": (
        "an overhead aerial image of exposed soil, bare earth, dirt, or dry ground without crop rows or tire-rut geometry",
        "a remote sensing crop of natural bare ground and not pavement, roof, water, road, or vehicle track",
        "an orthomosaic patch dominated by brown or tan exposed earth with irregular natural texture",
        "a top down aerial tile where bare ground is dominant and no clear road or vehicle path is visible",
    ),
    "disturbed_bare_ground": (
        "an overhead aerial image of disturbed, scraped, graded, churned, excavated, or construction-like earth",
        "a remote sensing crop of irregular disturbed dirt without clear road width, paired tire ruts, or crop row geometry",
        "an orthomosaic patch dominated by disturbed soil rather than road, crop rows, or two-rut vehicle track",
        "a top down aerial tile where soil disturbance is the primary subject and not a visible access path",
    ),

    # crops
    "green_crop_rows": (
        "an overhead aerial image of green crops arranged in visible repeated agricultural rows",
        "a remote sensing crop of cultivated vegetation with repeated row spacing and field planting geometry",
        "an orthomosaic patch dominated by planted field geometry and crop lines rather than grass or vehicle tracks",
        "a top down aerial tile centered on green crop rows and not smooth pasture, tree canopy, or tire ruts",
    ),
    "bare_soil_crop_rows": (
        "an overhead aerial image of agricultural rows cut into bare soil",
        "a remote sensing crop of cultivated field with brown soil between evenly spaced planted rows or beds",
        "an orthomosaic patch dominated by repeated planting rows on exposed earth",
        "a top down aerial tile centered on bare soil crop rows rather than tire ruts, access tracks, or random bare dirt",
    ),

    # debris
    "rubble_or_scattered_debris": (
        "an overhead aerial image of scattered debris, rubble, wreckage, fragments, or broken storm material",
        "a remote sensing crop of chaotic broken material without a clear intact structure, road, vehicle track, tree, or crop field",
        "an orthomosaic patch dominated by rubble pile, debris field, or irregular wreckage",
        "a top down aerial tile centered on loose debris and fragmented material rather than crop rows, tire tracks, or bare dirt",
    ),
}


FINAL_TO_DETAILED_CLASSES: dict[str, tuple[str, ...]] = {
    final_class: tuple(
        class_name
        for class_name in DETAILED_CLASSES
        if DETAILED_TO_FINAL[class_name] == final_class
    )
    for final_class in FINAL_CLASSES
}
