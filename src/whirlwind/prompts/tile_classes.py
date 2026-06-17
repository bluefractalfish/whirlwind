

from dataclasses import dataclass
from whirlwind.domain.config.schema import Config

REVIEW_CLASS = "review"

FINAL_CLASSES: tuple[str, ...] = (
    "structures",
    "roads",
    "tracks",
    "trees",
    "grass",
    "dirt",
    "crops",
    "water",
    "debris",
    REVIEW_CLASS,
)

TIE_BREAK_ORDER: tuple[str, ...] = FINAL_CLASSES


@dataclass(frozen=True)
class ClassThreshold:
    min_score: float
    min_margin: float
    max_second_score: float
    max_review_score: float

def final_class_rule_from_config(class_name: str, config: Config) -> "ClassThreshold": 
    raw = config.parse("classification", "rules") 
    class_rule = raw[class_name]
    if class_rule: 
        min_score = float(class_rule["min_score"])
        min_margin = float(class_rule["min_margin"]) 
        max_second = float(class_rule["max_second"]) 
        max_review = float(class_rule["max_review"])
        
        return ClassThreshold(min_score, min_margin, max_second, max_review)
    return ClassThreshold(0.0, 0.0, 0.0, 0.0)


CLASS_THRESHOLDS: dict[str, ClassThreshold] = {
    "structures": ClassThreshold(
        min_score=0.55,
        min_margin=0.10,
        max_second_score=0.30,
        max_review_score=0.22,
    ),
    "roads": ClassThreshold(
        min_score=0.59,
        min_margin=0.12,
        max_second_score=0.28,
        max_review_score=0.20,
    ),
    "tracks": ClassThreshold(
        min_score=0.57,
        min_margin=0.11,
        max_second_score=0.29,
        max_review_score=0.21,
    ),
    "trees": ClassThreshold(
        min_score=0.56,
        min_margin=0.10,
        max_second_score=0.30,
        max_review_score=0.22,
    ),
    "grass": ClassThreshold(
        min_score=0.60,
        min_margin=0.12,
        max_second_score=0.26,
        max_review_score=0.20,
    ),
    "dirt": ClassThreshold(
        min_score=0.60,
        min_margin=0.12,
        max_second_score=0.26,
        max_review_score=0.20,
    ),
    "crops": ClassThreshold(
        min_score=0.58,
        min_margin=0.12,
        max_second_score=0.28,
        max_review_score=0.20,
    ),
    "water": ClassThreshold(
        min_score=0.62,
        min_margin=0.10,
        max_second_score=0.24,
        max_review_score=0.18,
    ),
    "debris": ClassThreshold(
        min_score=0.50,
        min_margin=0.08,
        max_second_score=0.32,
        max_review_score=0.24,
    ),
}

DETAIL_AGREEMENT_MIN_SCORE = 0.30
DETAIL_AGREEMENT_MIN_MARGIN = 0.04


FINAL_CLASS_PROMPTS: dict[str, tuple[str, ...]] = {
    "structures": (
        "a nadir overhead aerial tile whose primary subject is a man made building roof with straight edges, corners, and rectilinear geometry",
        "a submeter orthomosaic crop dominated by a house, shed, barn, warehouse, garage, or other roofed structure footprint",
        "an overhead remote sensing tile of a damaged building with roof remnant, wall grid, foundation, or rectilinear structure remains",
        "a top down aerial image centered on a structure and not centered on a road, track, tree canopy, crop rows, or bare soil",
        "an aerial image tile where the dominant object is a roof or building footprint, even if partly damaged or surrounded by debris",
    ),
    "roads": (
        "a nadir overhead aerial tile whose primary subject is a maintained road, street, driveway, parking lot, or transportation pavement",
        "a submeter orthomosaic crop dominated by asphalt, concrete, compacted gravel road, driveway, or parking surface and not by roofs",
        "an overhead remote sensing tile of a damaged, cracked, washed out, or debris covered road corridor that is still visibly a road",
        "a top down aerial image centered on a continuous road surface with road-like width, edges, and vehicle access geometry",
        "an aerial image tile dominated by a full road, driveway, parking pad, or lane rather than a narrow two-rut track through grass or dirt",
    ),
    "tracks": (
        "a nadir overhead aerial tile whose primary subject is a narrow vehicle track, two-rut trail, tire rut path, farm track, or informal access route",
        "a submeter orthomosaic crop dominated by paired tire ruts or a narrow linear path through grass, dirt, crops, or woodland",
        "an overhead remote sensing tile of an unpaved track with two parallel worn lines and vegetation or soil between the ruts",
        "a top down aerial image centered on a dirt track, field access path, logging trail, or informal vehicle route that is not a full road",
        "an aerial image tile where the dominant feature is travel disturbance or tire-worn linear tracks rather than bare dirt alone or crop rows",
        "an overhead orthomosaic tile showing parallel wheel ruts, repeated vehicle passage marks, or a narrow access track crossing open land",
    ),
    "trees": (
        "a nadir overhead aerial tile whose primary subject is woody tree canopy or one or more tree crowns with organic irregular edges",
        "a submeter orthomosaic crop dominated by deciduous or conifer canopy and not by lawn, crop rows, roads, tracks, or roofs",
        "an overhead remote sensing tile of damaged, snapped, uprooted, or downed trees that are still visibly tree canopy, branches, trunks, or woody crowns",
        "a top down aerial image centered on woody vegetation and not on pavement, bare soil, crop rows, or low grass",
        "an aerial image tile where the dominant texture is tree crown structure, canopy shadow, branches, or forest cover",
    ),
    "grass": (
        "a nadir overhead aerial tile whose primary subject is low grassy vegetation with smooth, fine, herbaceous texture",
        "a submeter orthomosaic crop dominated by lawn, pasture, meadow, or open grassland and not by woody tree canopy",
        "an overhead remote sensing tile of low green or tan herbaceous cover without agricultural crop row pattern",
        "a top down aerial image centered on grass cover and not on roofs, roads, tracks, exposed soil, or water",
        "an aerial image tile dominated by continuous low vegetation where any tire marks or tracks are minor and not the primary subject",
    ),
    "dirt": (
        "a nadir overhead aerial tile whose primary subject is exposed soil, bare ground, scraped earth, or non vegetated earth surface",
        "a submeter orthomosaic crop dominated by brown or tan bare earth and not by pavement, roofs, water, tracks, or crop rows",
        "an overhead remote sensing tile of disturbed soil, graded earth, or irregular bare ground texture without a clear travel path",
        "a top down aerial image centered on bare ground without organized crop rows, tire-rut geometry, or tree crowns",
        "an aerial image tile where the dominant feature is earth surface itself rather than a road, track, driveway, or agricultural pattern",
    ),
    "crops": (
        "a nadir overhead aerial tile whose primary subject is an agricultural field with visible row structure, planted rows, or repeated crop pattern",
        "a submeter orthomosaic crop dominated by planted rows of green crops or rows cut into bare soil",
        "an overhead remote sensing tile of cultivated agriculture and not smooth lawn, wild grassland, dirt track, or vehicle ruts",
        "a top down aerial image centered on organized farming geometry with repeated rows, bed patterns, or field planting structure",
        "an aerial image tile where repeated agricultural row spacing is the dominant pattern rather than tire tracks crossing a field",
    ),
    "water": (
        "a nadir overhead aerial tile whose primary subject is open water, standing floodwater, pond, stream, ditch water, or smooth water surface",
        "a submeter orthomosaic crop dominated by dark or reflective water and not by deep shadow alone",
        "an overhead remote sensing tile of pond, creek, flooded depression, drainage channel, or water filled low area",
        "a top down aerial image centered on water with smooth low texture rather than canopy, pavement, roof, dirt, or track ruts",
    ),
    "debris": (
        "a nadir overhead aerial tile whose primary subject is rubble, wreckage, scattered storm debris, or chaotic broken material on the ground",
        "a submeter orthomosaic crop dominated by fragmented damaged material rather than an intact building, road, track, tree, or crop field",
        "an overhead remote sensing tile of debris field, rubble pile, scattered wreckage, or broken material without a clear parent object",
        "a top down aerial image centered on loose debris and irregular fragments rather than a damaged but identifiable roof, road, or tree",
        "an aerial image tile where the dominant visual evidence is chaotic storm debris, not simply a dirty surface, crop rows, or tire tracks",
    ),
    REVIEW_CLASS: (
        "an ambiguous overhead aerial tile with mixed land cover and no single dominant class",
        "a heavily shadowed, occluded, overexposed, underexposed, or low evidence aerial tile that should be reviewed by a human",
        "a partial object at the tile edge in top down imagery where the true class is uncertain",
        "an overhead aerial tile containing several competing classes with no clearly dominant subject",
        "a remote sensing crop that should be routed to review instead of forcing a best fit class",
        "an aerial tile where road, track, dirt, crop rows, grass, trees, structures, or debris are too ambiguous to assign safely",
    ),
}

