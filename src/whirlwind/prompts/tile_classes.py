
from dataclasses import dataclass
from typing import Literal

from whirlwind.domain.config.schema import Config


# legacy
REVIEW_CLASS = "review" 

TARGET_CLASSES: tuple[str, ...] = (
    "structures",
    "roads",
    "vehicle_tracks",
    "trees",
    "grass",
    "dirt",
    "crops",
    "debris",
)

FINAL_CLASSES: tuple[str, ...] = TARGET_CLASSES + (REVIEW_CLASS,)

TIE_BREAK_ORDER: tuple[str, ...] = TARGET_CLASSES

Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ClassThreshold:
    min_score: float
    min_margin: float
    max_second_score: float

    def confidence(
        self,
        top_score: float,
        margin: float,
        second_score: float,
        top_detail_score: float,
        detail_margin: float,
        detail_agrees: bool,
    ) -> Confidence:
        if (
            top_score >= self.min_score
            and margin >= self.min_margin
            and second_score <= self.max_second_score
            and top_detail_score >= DETAIL_AGREEMENT_MIN_SCORE
            and detail_margin >= DETAIL_AGREEMENT_MIN_MARGIN
            and detail_agrees
        ):
            return "high"

        if (
            top_score >= MEDIUM_CONFIDENCE_MIN_SCORE
            or margin >= MEDIUM_CONFIDENCE_MIN_MARGIN
        ):
            return "medium"

        return "low"


def final_class_rule_from_config(
    class_name: str,
    config: Config,
) -> ClassThreshold:
    raw = config.parse("classification", "rules")
    class_rule = raw[class_name]

    if class_rule:
        min_score = float(class_rule["min_score"])
        min_margin = float(class_rule["min_margin"])
        max_second = float(class_rule["max_second"])
        return ClassThreshold(min_score, min_margin, max_second)

    return ClassThreshold(0.0, 0.0, 0.0)


# Review gates.
# Bad/empty/collar tiles should be skipped before classification.
MIN_TOP_SCORE = 0.26
LOW_EVIDENCE = 0.34
TIE_MARGIN = 0.02

MEDIUM_CONFIDENCE_MIN_SCORE = 0.38
MEDIUM_CONFIDENCE_MIN_MARGIN = 0.035

DETAIL_AGREEMENT_MIN_SCORE = 0.26
DETAIL_AGREEMENT_MIN_MARGIN = 0.04


CLASS_THRESHOLDS: dict[str, ClassThreshold] = {
    "structures": ClassThreshold(
        min_score=0.50,
        min_margin=0.08,
        max_second_score=0.38,
    ),
    "roads": ClassThreshold(
        min_score=0.42,
        min_margin=0.06,
        max_second_score=0.40,
    ),
    "vehicle_tracks": ClassThreshold(
        min_score=0.42,
        min_margin=0.06,
        max_second_score=0.38,
    ),
    "trees": ClassThreshold(
        min_score=0.60,
        min_margin=0.07,
        max_second_score=0.40,
    ),
    "grass": ClassThreshold(
        min_score=0.45,
        min_margin=0.05,
        max_second_score=0.42,
    ),
    "dirt": ClassThreshold(
        min_score=0.45,
        min_margin=0.05,
        max_second_score=0.42,
    ),
    "crops": ClassThreshold(
        min_score=0.60,
        min_margin=0.06,
        max_second_score=0.40,
    ),
    "debris": ClassThreshold(
        min_score=0.60,
        min_margin=0.04,
        max_second_score=0.42,
    ),
}


FINAL_CLASS_PROMPTS: dict[str, tuple[str, ...]] = {
    "structures": (
        "building roof footprint with straight edges and visible corners",
        "house, shed, barn, garage, warehouse, or roofed structure",
        "rectangular man made building geometry with roof planes or walls",
        "damaged building footprint with roof, slab, wall, or foundation evidence",
        "structure remains with rectilinear footprint or man made corners",
    ),

    "roads": (
        "continuous full-width vehicle travel surface with visible corridor shape",
        "paved road, gravel road, compacted dirt road, street, lane, driveway, or parking surface",
        "vehicle route wide enough for cars or trucks with continuous surface width",
        "maintained road corridor with visible edges and full vehicle width",
        "roadway surface with painted lines, pavement, gravel, compacted dirt, or driveway texture",
        "parking lot, parking pad, driveway, street, or full-width access surface",
    ),

    "vehicle_tracks": (
        "parallel lines with visible green ground between paths",
        "paired narrow wheel marks crossing grass, soil, mud, or crops",
        "regularly spaced vehicle rut lines with a visible grass center strip",
        "two thin parallel tire paths through grass, trees, dirt",
        "paired wheel ruts with grass, dirt, crop, or mud texture between the ruts",
        "dirt lines with regular vehicle spacing",
    ),

    "trees": (
        "woody tree canopy with irregular organic dark crown edges",
        "tree crowns, branches, trunks with clear woody features",
        "single tree crown against lighter green or dirt",
        "snapped, uprooted, damaged, or downed trees with woody branches or trunks",
        "fallen tree material, broken crowns, exposed trunks, or damaged canopy",
    ),

    "grass": (
        "low herbaceous vegetation, lawn, pasture, meadow, or grassland",
        "short grass or rough grass cover",
        "smooth low vegetation texture in an open yard, field, pasture, or meadow",
        "continuous herbaceous ground cover without agricultural row pattern",
        "grass cover with fine low texture",
    ),

    "dirt": (
        "exposed soil, bare ground, scraped earth, graded dirt, or dry earth surface",
        "brown or tan bare earth without organized planting rows",
        "disturbed soil, churned ground, irregular bare dirt, or scraped earth",
        "open non-vegetated ground surface with irregular natural dirt texture",
        "bare soil or disturbed ground as the dominant surface",
    ),

    "crops": (
        "agricultural field rows with repeated planted row geometry",
        "green crop rows, crop beds, furrows, or cultivated field pattern",
        "regular farming row spacing across a field",
        "planted agricultural texture with repeated parallel rows",
        "bare soil planting rows or green cultivated crop rows",
    ),

    "debris": (
        "rubble, wreckage, scattered debris, broken structural material",
        "loose material spread across the ground close to structure",
        "debris field, rubble pile, scattered wreckage, or broken structure material",
        "splintered material, or scattered damaged objects",
    ),
}
