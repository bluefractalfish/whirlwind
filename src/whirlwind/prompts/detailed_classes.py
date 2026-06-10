

# classes for prompt management 
DETAILED_CLASSES: tuple[str, ...] = (

    # Structures
    "single_family_house_roof",
    "rectangular_building_roof",
    "dark_shingle_roof",
    "light_roof_or_concrete_roof",
    "metal_roof_building",
    "small_shed_or_outbuilding",
    "farm_or_industrial_structure",
    "damaged_or_broken_structure",

    # Roads / paved / tracks
    "asphalt_road",
    "concrete_road",
    "gravel_road",
    "driveway_or_parking_area",
    "linear_track_or_tire_path",

    # Trees / woody vegetation
    "deciduous_tree_canopy",
    "conifer_tree_canopy",
    "individual_tree_crown",
    "dense_tree_stand",
    "shrub_or_brush",

    # Grass / low vegetation
    "mowed_lawn_grass",
    "pasture_grass",
    "rough_rangeland_grass",
    "green_field_low_vegetation",

    # Soil / crops
    "bare_soil",
    "tilled_dirt",
    "dry_bare_ground",
    "crop_rows_on_bare_soil",
    "green_crop_field",

    # Other explicit classes
    "water",
    "deep_shadow",
    "vehicle",
    "debris_or_rubble",
    "unknown_mixed_landcover",
)


FINAL_CLASSES: tuple[str, ...] = (
    "structures",
    "roads",
    "tracks",
    "trees",
    "grass",
    "dirt",
    "crops",
    "water",
    "shadow",
    "vehicles",
    "debris",
    "mixed",
)


DETAILED_TO_FINAL: dict[str, str] = {
    # Structures
    "single_family_house_roof": "structures",
    "rectangular_building_roof": "structures",
    "dark_shingle_roof": "structures",
    "light_roof_or_concrete_roof": "structures",
    "metal_roof_building": "structures",
    "small_shed_or_outbuilding": "structures",
    "farm_or_industrial_structure": "structures",

    "damaged_or_broken_structure": "debris",

    # Roads / paved / tracks
    "asphalt_road": "roads",
    "concrete_road": "roads",
    "gravel_road": "roads",
    "driveway_or_parking_area": "roads",
    "linear_track_or_tire_path": "tracks",

    # Trees
    "deciduous_tree_canopy": "trees",
    "conifer_tree_canopy": "trees",
    "individual_tree_crown": "trees",
    "dense_tree_stand": "trees",
    "shrub_or_brush": "trees",

    # Grass
    "mowed_lawn_grass": "grass",
    "pasture_grass": "grass",
    "rough_rangeland_grass": "grass",
    "green_field_low_vegetation": "grass",

    # Dirt / crops
    "bare_soil": "dirt",
    "tilled_dirt": "dirt",
    "dry_bare_ground": "dirt",
    "crop_rows_on_bare_soil": "crops",
    "green_crop_field": "crops",

    # Other explicit
    "water": "water",
    "deep_shadow": "shadow",
    "vehicle": "vehicles",
    "debris_or_rubble": "debris",
    "unknown_mixed_landcover": "mixed",
}


PROMPTS_BY_DETAILED_CLASS: dict[str, list[str]] = {
    "single_family_house_roof": [
        "a submeter nadir aerial image of a single family house roof with straight roof edges",
        "an overhead orthomosaic crop centered on a residential rooftop with rectangular geometry",
        "a remote sensing image of a house roof surrounded by yard or driveway",
        "an aerial image of a residential building roof with sharp man made corners",
    ],
    "rectangular_building_roof": [
        "an overhead aerial image of a rectangular building roof with clean straight boundaries",
        "a nadir remote sensing crop of a flat man made rooftop footprint",
        "an orthomosaic patch showing a building roof distinct from road and bare ground",
        "a high resolution aerial crop of a roof polygon with right angles",
    ],
    "dark_shingle_roof": [
        "a submeter overhead image of a dark gray shingle roof on a building",
        "an aerial crop of a dark residential rooftop with roof planes and rectangular outline",
        "a remote sensing image of a dark roof, not asphalt road, with building geometry",
        "a nadir orthomosaic crop of a dark house roof with sharp edges",
    ],
    "light_roof_or_concrete_roof": [
        "an overhead aerial image of a light colored building roof with straight edges",
        "a submeter remote sensing crop of a white or pale roof, not bare dirt",
        "an orthomosaic image of a bright rectangular rooftop surface",
        "a nadir aerial crop of a light roof with visible building corners",
    ],
    "metal_roof_building": [
        "an overhead aerial image of a metal roof building with straight seams",
        "a remote sensing crop of a shiny or pale agricultural metal rooftop",
        "an orthomosaic image of a farm shed or barn with metal roof panels",
        "a nadir aerial view of a large rectangular metal roof structure",
    ],
    "small_shed_or_outbuilding": [
        "an overhead aerial image of a small shed roof in a yard",
        "a submeter remote sensing crop of a compact rectangular outbuilding",
        "an orthomosaic patch showing a garage shed or small roofed structure",
        "a nadir aerial image of a small man made structure with straight boundaries",
    ],
    "farm_or_industrial_structure": [
        "an overhead aerial image of a large farm building warehouse or industrial roof",
        "a remote sensing crop of a barn or warehouse structure",
        "an orthomosaic patch of a large non residential building roof",
        "a nadir aerial view of an industrial or agricultural building",
    ],
    "damaged_or_broken_structure": [
        "an overhead aerial image of a damaged building roof with debris and broken edges",
        "an overhead aerial image of the remaining walls of a roofless structure",
        "the areal view of a grid of walls remaining after the roof has been removed",
        "a remote sensing crop of a collapsed or partially destroyed structure",
        "an orthomosaic patch showing roof damage missing panels or scattered building debris",
        "a nadir aerial image of a storm damaged building structure",
    ],

    "asphalt_road": [
        "an overhead aerial image of a dark asphalt road or street",
        "a remote sensing crop of a smooth dark paved road with linear shape",
        "an orthomosaic patch of asphalt pavement, not a rooftop",
        "a nadir aerial view of a road surface with lane-like geometry",
    ],
    "concrete_road": [
        "an overhead aerial image of a light concrete road or paved street",
        "a remote sensing crop of pale concrete pavement with a road shape",
        "an orthomosaic patch of light colored roadway or sidewalk pavement",
        "a nadir image of a concrete road surface",
    ],
    "gravel_road": [
        "an overhead aerial image of a gravel road with light gray rough texture",
        "a remote sensing crop of an unpaved gravel driveway or rural road",
        "an orthomosaic patch of pale gravel path with linear shape",
        "a nadir aerial view of a rough light colored gravel road",
    ],
    "driveway_or_parking_area": [
        "an overhead aerial image of a driveway parking pad or paved apron near buildings",
        "a remote sensing crop of a parking area connected to a structure",
        "an orthomosaic patch of man made pavement around buildings",
        "a nadir aerial image of a driveway or parking lot surface",
    ],
    "linear_track_or_tire_path": [
        "an overhead aerial image of parallel tire tracks across grass or dirt",
        "a remote sensing crop of two narrow parallel vehicle tracks",
        "an orthomosaic patch of linear tracks in a field or bare ground",
        "a nadir aerial image of unpaved tracks with regular parallel spacing",
    ],

    "deciduous_tree_canopy": [
        "a submeter overhead aerial image of broadleaf tree canopy with rounded green crowns",
        "a remote sensing crop of leafy deciduous tree crowns with irregular organic edges",
        "an orthomosaic patch of mature deciduous trees with textured green canopy",
        "a nadir aerial image of broad green tree crowns casting shadows",
    ],
    "conifer_tree_canopy": [
        "an overhead aerial image of conifer evergreen trees with dark green pointed crowns",
        "a remote sensing crop of pine or cedar tree canopy",
        "an orthomosaic patch of dark evergreen trees with compact crown texture",
        "a nadir aerial view of conifer trees darker and rougher than grass",
    ],
    "individual_tree_crown": [
        "a single isolated tree crown in an overhead aerial image",
        "one round tree canopy object separated from surrounding ground",
        "a nadir aerial crop centered on an individual tree crown",
        "a single green or very dark green/black woody vegetation crown with shadow in an orthomosaic",
    ],
    "dense_tree_stand": [
        "a dense continuous stand of trees in overhead aerial imagery",
        "a remote sensing crop filled mostly by connected tree canopy",
        "an orthomosaic patch of forest canopy with overlapping crowns",
        "a high resolution aerial image of dense woody vegetation",
    ],
    "shrub_or_brush": [
        "an overhead aerial image of low shrubs or brush with irregular green woody texture",
        "a remote sensing crop of scrub vegetation, not smooth lawn grass",
        "an orthomosaic patch of bushy vegetation with uneven clumps",
        "a nadir aerial image of scattered shrubs and brushy vegetation",
    ],

    "mowed_lawn_grass": [
        "an overhead aerial image of smooth mowed lawn grass",
        "a remote sensing crop showing uniform short green grass near buildings",
        "an orthomosaic patch of smooth bright lawn with little texture",
        "a nadir aerial image of maintained turf grass with even color",
    ],
    "pasture_grass": [
        "an overhead aerial image of pasture grass or open grassy field",
        "a remote sensing crop of green pasture with low vegetation and no tree crowns",
        "an orthomosaic patch of open grassland with smooth vegetation texture",
        "a nadir aerial view of pasture, not trees and not crop rows",
    ],
    "rough_rangeland_grass": [
        "an overhead aerial image of rough rangeland grass with uneven tan green texture",
        "a remote sensing crop of natural grassland or prairie vegetation",
        "an orthomosaic patch of sparse rough grass and dry vegetation",
        "a nadir image of irregular grass cover without trees or roofs",
    ],
    "green_field_low_vegetation": [
        "an overhead aerial image of low green field vegetation, flat and non woody",
        "a remote sensing crop of green ground cover with no visible tree crowns",
        "an orthomosaic patch of low herbaceous vegetation",
        "a high resolution aerial crop of a flat green field surface",
    ],

    "bare_soil": [
        "an overhead aerial image of exposed bare soil with brown texture",
        "a remote sensing crop of bare earth, not pavement and not roof",
        "an orthomosaic patch of brown soil surface without vegetation",
        "a nadir image of exposed ground with natural irregular texture",
    ],
    "tilled_dirt": [
        "an overhead aerial image of tilled dirt field with rough soil texture",
        "a remote sensing crop of plowed agricultural soil",
        "an orthomosaic patch of brown tilled earth with faint rows",
        "a nadir aerial view of disturbed bare field soil",
    ],
    "dry_bare_ground": [
        "an overhead image of dry tan bare ground",
        "a remote sensing crop of pale dry earth with sparse vegetation",
        "an orthomosaic patch of dry exposed ground, not concrete",
        "a nadir aerial image of tan soil or dry dirt area",
    ],
    "crop_rows_on_bare_soil": [
        "an overhead aerial image of crop rows on bare dirt with regular parallel lines",
        "a remote sensing crop of agricultural rows with brown soil between lines",
        "an orthomosaic patch of field rows forming repeated linear pattern",
        "a nadir aerial view of cultivated crop rows in bare soil",
    ],
    "green_crop_field": [
        "an overhead aerial image of green agricultural crop rows",
        "a remote sensing crop of planted field with regular row structure",
        "an orthomosaic patch of green crops arranged in parallel lines",
        "a nadir aerial view of cultivated green field, not smooth lawn",
    ],

    "water": [
        "an overhead aerial image of water surface such as pond stream or flooded area",
        "a remote sensing crop of dark or reflective water",
        "an orthomosaic patch showing standing water with smooth texture",
        "a nadir aerial image of water, not shadow",
    ],
    "deep_shadow": [
        "an overhead aerial image of deep black shadow cast by trees or buildings",
        "a remote sensing crop of dark shadow with little visible texture",
        "an orthomosaic patch of shadowed ground, not water or asphalt",
        "a nadir aerial image of strong shadow adjacent to objects",
    ],
    "vehicle": [
        "an overhead aerial image of a vehicle car truck or trailer",
        "a remote sensing crop of a parked car or truck",
        "an orthomosaic patch showing a small vehicle with rectangular shape",
        "a nadir aerial view of a car sized object on road or driveway",
    ],
    "debris_or_rubble": [
        "an overhead aerial image of scattered debris or rubble",
        "a remote sensing crop of storm debris broken material or irregular wreckage",
        "an orthomosaic patch of debris field with chaotic texture",
        "a nadir aerial view of damaged scattered objects on ground or in trees",
    ],
    "unknown_mixed_landcover": [
        "an ambiguous overhead aerial image with mixed land cover",
        "a remote sensing crop that is unclear or contains several classes",
        "an orthomosaic patch that is not clearly trees grass road dirt roof or water",
        "a nadir aerial image of mixed background with no dominant class",
    ],
}

