
from whirlwind.prompts.tile_classes import REVIEW_CLASS, FINAL_CLASSES


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

    # tracks
    "two_rut_vehicle_track",
    "tire_rut_track",
    "field_access_track",
    "woodland_or_logging_track",
    "damaged_or_eroded_track",

    # trees
    "single_tree_crown",
    "dense_tree_canopy",
    "conifer_tree_canopy",
    "damaged_or_downed_tree",

    # grass
    "mowed_grass",
    "rough_grassland",

    # dirt
    "bare_soil",
    "disturbed_bare_ground",

    # crops
    "green_crop_rows",
    "bare_soil_crop_rows",

    # water
    "water_surface",

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

    # tracks
    "two_rut_vehicle_track": "tracks",
    "tire_rut_track": "tracks",
    "field_access_track": "tracks",
    "woodland_or_logging_track": "tracks",
    "damaged_or_eroded_track": "tracks",

    # trees
    "single_tree_crown": "trees",
    "dense_tree_canopy": "trees",
    "conifer_tree_canopy": "trees",
    "damaged_or_downed_tree": "trees",

    # grass
    "mowed_grass": "grass",
    "rough_grassland": "grass",

    # dirt
    "bare_soil": "dirt",
    "disturbed_bare_ground": "dirt",

    # crops
    "green_crop_rows": "crops",
    "bare_soil_crop_rows": "crops",

    # water
    "water_surface": "water",

    # debris
    "rubble_or_scattered_debris": "debris",

}


PROMPTS_BY_DETAILED_CLASS: dict[str, tuple[str, ...]] = {
    # structures
    "residential_roof": (
        "a submeter nadir aerial image of an intact residential roof with straight roof edges and visible corners",
        "an overhead orthomosaic crop centered on a house roof surrounded by yard, driveway, or lawn",
        "a remote sensing image of a residential rooftop footprint and not a road surface, track, crop row, or bare dirt patch",
        "a top down aerial tile dominated by a single family house roof with visible roof planes and rectilinear boundaries",
    ),
    "large_structure_roof": (
        "an overhead aerial image of a large commercial, industrial, farm, warehouse, or institutional roof",
        "a nadir remote sensing crop of a broad rectilinear rooftop footprint with straight man made boundaries",
        "an orthomosaic patch showing a large man made roof area distinct from roads, tracks, bare soil, or fields",
        "a top down aerial tile dominated by a large building roof with rectangular or polygonal roof geometry",
    ),
    "small_outbuilding_roof": (
        "an overhead aerial image of a shed, garage, barn annex, pump house, or other compact outbuilding roof",
        "a submeter remote sensing crop centered on a small rectangular roofed structure",
        "an orthomosaic patch showing a small roof footprint in a yard, farm lot, field edge, or property parcel",
        "a top down aerial tile dominated by a compact roof with clear man made geometry",
    ),
    "damaged_structure_roof": (
        "an overhead aerial image of a storm damaged building roof with missing sections, torn covering, exposed framing, or displaced roof material",
        "a remote sensing crop of a damaged roof that is still clearly part of a structure footprint",
        "an orthomosaic patch showing a broken building roof with rectilinear remains and attached debris",
        "a top down aerial tile dominated by a damaged structure rather than generic rubble, trees, dirt, road, or track",
    ),
    "roofless_structure_remains": (
        "an overhead aerial image of a roofless structure, wall grid, foundation, or building footprint remains with rectilinear layout",
        "a remote sensing crop of standing walls, slab, foundation, or footprint remains after a roof was lost",
        "an orthomosaic patch showing structure remains that are still clearly a building layout",
        "a top down aerial tile centered on a destroyed building footprint rather than a random debris field",
    ),

    # roads
    "paved_road": (
        "an overhead aerial image of asphalt or concrete road with continuous roadway geometry and road-like width",
        "a remote sensing crop of a paved street, lane, highway, or residential road and not a rooftop or track",
        "an orthomosaic patch of continuous transportation pavement with clear road alignment",
        "a top down aerial tile dominated by a paved road corridor rather than narrow tire ruts",
    ),
    "gravel_road": (
        "an overhead aerial image of a maintained gravel or compacted unpaved road with road-like width and continuous transport geometry",
        "a remote sensing crop of pale gravel roadway or rural lane wide enough to be a road rather than a two-rut track",
        "an orthomosaic patch of light rough road surface extending across the tile with consistent road corridor width",
        "a top down aerial tile dominated by a gravel road or access road and not by a narrow field track",
    ),
    "parking_or_driveway": (
        "an overhead aerial image of a driveway, parking pad, parking lot, paved apron, or vehicle access surface beside structures",
        "a remote sensing crop of vehicle access pavement connected to a building or road",
        "an orthomosaic patch centered on man made parking, driveway, or paved access surface",
        "a top down aerial tile dominated by parking or driveway surface and not by a roof or narrow dirt track",
    ),
    "damaged_road_surface": (
        "an overhead aerial image of a damaged road with washout, crack, break, erosion, flooding, or debris while the road shape remains visible",
        "a remote sensing crop of cracked, broken, blocked, eroded, or partially obstructed roadway",
        "an orthomosaic patch showing transportation surface damage but still clearly a road corridor",
        "a top down aerial tile dominated by a damaged road rather than bare soil, track ruts, or scattered debris alone",
    ),

    # tracks
    "two_rut_vehicle_track": (
        "an overhead aerial image of a two-rut vehicle track with two parallel worn tire paths and vegetation or soil between them",
        "a submeter remote sensing crop centered on a narrow two-track path crossing grass, dirt, crops, or open land",
        "an orthomosaic patch showing paired vehicle ruts that are too narrow and informal to be a road",
        "a top down aerial tile dominated by a two-rut access track rather than a maintained gravel road",
        "an aerial image tile where the main feature is two parallel vehicle-worn lines through natural ground cover",
    ),
    "tire_rut_track": (
        "an overhead aerial image of tire ruts impressed into dirt, mud, grass, or disturbed soil",
        "a remote sensing crop dominated by repeated wheel rut marks that form a travel path",
        "an orthomosaic patch showing linear tire disturbance and compacted ground rather than bare soil alone",
        "a top down aerial tile centered on tire tracks, rut scars, or vehicle passage marks",
        "an aerial image tile where tire-rut geometry is the dominant class evidence, not crop rows or a full road",
    ),
    "field_access_track": (
        "an overhead aerial image of a farm field access track, service path, or narrow access lane through a field",
        "a remote sensing crop of an informal track crossing crop rows, grassland, pasture, or bare agricultural ground",
        "an orthomosaic patch showing a narrow vehicle access route along a field edge or across a cultivated field",
        "a top down aerial tile dominated by a field track and not by the crop rows themselves",
        "an aerial image tile where a travel path interrupts or crosses agricultural texture",
    ),
    "woodland_or_logging_track": (
        "an overhead aerial image of a narrow dirt or gravel track through trees, brush, forest edge, or woodland",
        "a remote sensing crop of a logging track, woodland access trail, or informal route partly covered by canopy",
        "an orthomosaic patch showing a narrow linear path through woody vegetation",
        "a top down aerial tile dominated by an unpaved access track between trees rather than the tree canopy alone",
        "an aerial image tile where the main feature is a narrow travel corridor through vegetation",
    ),
    "damaged_or_eroded_track": (
        "an overhead aerial image of an eroded, washed out, muddy, blocked, or storm damaged track where the track path remains visible",
        "a remote sensing crop of a damaged two-rut path or informal access route with erosion, debris, mud, or rutting",
        "an orthomosaic patch showing a rough damaged track that is still visually a vehicle path",
        "a top down aerial tile dominated by a damaged track rather than a full damaged road or random bare dirt",
    ),

    # trees
    "single_tree_crown": (
        "a submeter overhead aerial image centered on one isolated tree crown with organic outline and canopy texture",
        "a remote sensing crop of a single woody canopy object separated from surrounding grass, dirt, road, or roof",
        "an orthomosaic patch dominated by one broadleaf tree crown with irregular edges",
        "a top down aerial tile centered on one tree crown and not on grass, crop rows, roof, road, or track",
    ),
    "dense_tree_canopy": (
        "a dense continuous stand of trees in overhead aerial imagery",
        "a remote sensing crop filled mostly by overlapping woody tree crowns",
        "an orthomosaic patch of forest canopy with connected organic texture and canopy shadows",
        "a top down aerial tile dominated by multiple tree canopies rather than low grass or crops",
    ),
    "conifer_tree_canopy": (
        "an overhead aerial image of conifer or evergreen tree canopy with dark textured crowns",
        "a remote sensing crop of pine, cedar, or evergreen canopy and not smooth grass",
        "an orthomosaic patch dominated by dark evergreen crowns with organic tree texture",
        "a top down aerial tile centered on conifer canopy",
    ),
    "damaged_or_downed_tree": (
        "an overhead aerial image of snapped, uprooted, or downed trees that are still visibly trees",
        "a remote sensing crop of damaged woody canopy, broken crowns, fallen trunks, branches, or uprooted trees",
        "an orthomosaic patch showing tree damage rather than generic debris, bare soil, road, or track",
        "a top down aerial tile dominated by damaged tree canopy or downed woody vegetation",
    ),

    # grass
    "mowed_grass": (
        "an overhead aerial image of maintained lawn or short mowed grass with smooth fine texture",
        "a remote sensing crop of uniform low grass near structures, roads, driveways, or yards and not tree canopy",
        "an orthomosaic patch dominated by short even herbaceous ground cover",
        "a top down aerial tile of lawn or mowed grass where roads, tracks, roofs, and trees are not dominant",
    ),
    "rough_grassland": (
        "an overhead aerial image of pasture, meadow, field grass, or rough grassland without crop rows",
        "a remote sensing crop of low herbaceous cover with uneven grass texture and no woody crowns",
        "an orthomosaic patch dominated by rough grassland rather than planted agriculture, bare soil, road, or track",
        "a top down aerial tile of natural or unmanaged grass cover without a dominant vehicle track",
    ),

    # dirt
    "bare_soil": (
        "an overhead aerial image of exposed soil, bare earth, dirt, or dry ground without crop rows or track ruts",
        "a remote sensing crop of natural bare ground and not pavement, roof, water, road, or vehicle track",
        "an orthomosaic patch dominated by brown or tan exposed earth with irregular natural texture",
        "a top down aerial tile where bare ground is dominant and no clear travel corridor is visible",
    ),
    "disturbed_bare_ground": (
        "an overhead aerial image of disturbed, scraped, graded, churned, excavated, or construction-like earth",
        "a remote sensing crop of irregular disturbed dirt without clear road width, track ruts, or crop row geometry",
        "an orthomosaic patch dominated by disturbed soil rather than road, crop rows, or two-rut vehicle track",
        "a top down aerial tile where soil disturbance is the primary subject and not a visible access path",
    ),

    # crops
    "green_crop_rows": (
        "an overhead aerial image of green crops arranged in visible repeated rows",
        "a remote sensing crop of cultivated vegetation with repeated agricultural row pattern",
        "an orthomosaic patch dominated by planted field geometry and crop lines",
        "a top down aerial tile centered on green crop rows and not smooth pasture or vehicle tracks",
    ),
    "bare_soil_crop_rows": (
        "an overhead aerial image of agricultural rows cut into bare soil",
        "a remote sensing crop of cultivated field with brown soil between evenly spaced planted rows or beds",
        "an orthomosaic patch dominated by repeated planting rows on exposed earth",
        "a top down aerial tile centered on bare soil crop rows rather than tire ruts or an access track",
    ),

    # water
    "water_surface": (
        "an overhead aerial tile dominated by real open water with a visible shoreline, drainage shape, channel boundary, pond edge, creek path, or flood boundary",
        "a remote sensing crop of real water surface, not black nodata padding, not raster collar, not deep shadow, not blank dark imagery",
        "an orthomosaic tile where water has geographic shape or boundary evidence rather than being only a smooth dark texture",
    ),

    # debris
    "rubble_or_scattered_debris": (
        "an overhead aerial image of scattered debris, rubble, wreckage, fragments, or broken storm material",
        "a remote sensing crop of chaotic broken material without a clear intact structure, road, track, tree, or crop field",
        "an orthomosaic patch dominated by rubble pile, debris field, or irregular wreckage",
        "a top down aerial tile centered on loose debris and fragmented material",
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
