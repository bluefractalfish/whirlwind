

from dataclasses import dataclass
from typing import Literal
from whirlwind.domain.config.schema import Config


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
    
    
    def confidence(self, 
             top_score, 
             margin, 
             second_score, 
             top_detail_score, 
             detail_margin, 
             detail_agrees ) -> Confidence:

         if (
                top_score >= self.min_score
                and margin >= self.min_margin 
                and second_score <= self.max_second_score 
                and top_detail_score >= DETAIL_AGREEMENT_MIN_SCORE
                and detail_margin >= DETAIL_AGREEMENT_MIN_MARGIN
                and detail_agrees
                ): 
             return "high"
         if  (
                top_score >= MEDIUM_CONFIDENCE_MIN_SCORE 
                or margin >= MEDIUM_CONFIDENCE_MIN_MARGIN
                ): 
             return "medium" 

         else: 
             return "low" 



def final_class_rule_from_config(class_name: str, config: Config) -> "ClassThreshold": 
    raw = config.parse("classification", "rules") 
    class_rule = raw[class_name]
    if class_rule: 
        min_score = float(class_rule["min_score"])
        min_margin = float(class_rule["min_margin"]) 
        max_second = float(class_rule["max_second"]) 
        
        return ClassThreshold(min_score, min_margin, max_second)
    return ClassThreshold(0.0, 0.0, 0.0)

# model has almost no evidence if less than: 
MIN_TOP_SCORE = 0.26

# send to review if top score less than: 
LOW_EVIDENCE = 0.34 
# and classes are basically tied: 
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
        max_second_score=0.40,
    ),
    "trees": ClassThreshold(
        min_score=0.50,
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
        min_score=0.48,
        min_margin=0.06,
        max_second_score=0.40,
    ),
    "debris": ClassThreshold(
        min_score=0.40,
        min_margin=0.04,
        max_second_score=0.42,
    ),
}


FINAL_CLASS_PROMPTS: dict[str, tuple[str, ...]] = {
    "structures": (
        "a nadir overhead aerial tile dominated by a building roof, wall footprint, foundation, or roofed man made structure",
        "a submeter orthomosaic crop centered on a house, shed, barn, garage, warehouse, outbuilding, or other structure footprint",
        "an overhead remote sensing tile of a damaged building where rectilinear roof, wall, slab, or foundation geometry is still visible",
        "a top down aerial image where the dominant object has straight edges, corners, roof planes, or man made rectangular structure geometry",
        "an aerial image tile dominated by a structure rather than a road surface, driveway, crop row pattern, tree canopy, grass, dirt, or blank raster edge",
    ),
    "roads": (
        "a nadir overhead aerial tile dominated by a full-width road, road with yellow or white lines on it, street, driveway, lane, parking pad, parking lot, access road, dirt road, gravel road, or maintained vehicle surface",
        "a submeter orthomosaic crop of asphalt, concrete, compacted gravel, compacted dirt road, driveway, or parking surface with continuous road-like width and visible edges",
        "an overhead remote sensing tile of a continuous travel corridor wide enough for vehicles, including paved roads, gravel roads, dirt roads, farm roads, ranch roads, logging roads, and access roads",
        "a top down aerial image centered on a continuous road surface or driveway rather than two narrow separated tire ruts",
        "an aerial image tile where the dominant feature is a full-width vehicle surface, even if unpaved, rough, rural, damaged, debris-covered, or partially blocked",
    ),

    "vehicle_tracks": (
        "a nadir overhead aerial tile dominated by two separate parallel vehicle wheel ruts with grass, dirt, crops, or mud visible between the ruts",
        "a submeter orthomosaic crop showing paired tire lines with regular wheel spacing, where the middle strip between the tire paths is visibly different from the ruts",
        "a top down aerial image centered on two narrow vehicle-caused wheel paths, not a full-width road, driveway, lane, access road, or gravel surface or anything paved with lines painted on it",
        "an aerial image tile where the dominant feature is paired tire-rut geometry: two thin parallel tracks separated by undisturbed ground",
        "a remote sensing crop of vehicle tire ruts through grass, dirt, mud, crops, or open land, excluding maintained roads, gravel roads, driveways, parking areas, and full-width dirt roads",
    ),

    "trees": (
        "a nadir overhead aerial tile dominated by woody tree canopy, tree crowns, branches, trunks, or forest cover with organic irregular edges",
        "a submeter orthomosaic crop of deciduous or conifer canopy, including snapped, uprooted, damaged, or downed trees that are still visibly woody vegetation",
        "an overhead remote sensing tile where the dominant texture is tree crown structure, canopy shadow, branches, forest canopy, or fallen woody material",
        "a top down aerial image centered on woody vegetation rather than low grass, lawn, crop rows, road surface, bare soil, roof, or blank raster padding",
        "an aerial image tile where the main subject is one or more tree crowns or damaged trees, not smooth herbaceous grass cover",
    ),

    "grass": (
        "a nadir overhead aerial tile dominated by low herbaceous vegetation, lawn, pasture, meadow, or grassland with fine smooth texture",
        "a submeter orthomosaic crop of short grass, rough grassland, yard, pasture, or open herbaceous ground cover without woody tree crowns",
        "an overhead remote sensing tile of low green or tan vegetation without agricultural row pattern, road surface, roof geometry, or dominant tire tracks",
        "a top down aerial image centered on grass cover where trees, crop rows, roads, structures, bare soil, and vehicle tracks are not dominant",
        "an aerial image tile dominated by continuous low vegetation rather than tall woody canopy, dark tree shadows, crop rows, or paired wheel ruts",
    ),

    "dirt": (
        "a nadir overhead aerial tile dominated by exposed soil, bare ground, scraped earth, graded dirt, or non vegetated earth surface",
        "a submeter orthomosaic crop of brown or tan bare earth without organized crop rows, paired tire rut geometry, road-like width, or roof structure",
        "an overhead remote sensing tile of disturbed soil, churned ground, irregular bare dirt, or scraped earth where no clear vehicle path dominates",
        "a top down aerial image centered on bare ground rather than road, driveway, crop rows, tree canopy, grass, structure, or debris",
        "an aerial image tile where the dominant feature is earth surface itself, not a maintained road, vehicle track, agricultural row pattern, or blank white/black raster edge",
    ),

    "crops": (
        "a nadir overhead aerial tile dominated by agricultural field rows, planted rows, crop beds, or repeated cultivated field pattern",
        "a submeter orthomosaic crop of green crop rows or bare soil planting rows with regular agricultural spacing",
        "an overhead remote sensing tile where the main pattern is organized farming geometry rather than grassland, vehicle tracks, roads, or bare dirt alone",
        "a top down aerial image centered on repeated crop row structure, bed pattern, furrows, or field planting geometry",
        "an aerial image tile where agricultural row spacing is the dominant pattern, not paired tire tracks crossing a field or a road along a field edge",
    ),

    "debris": (
        "a nadir overhead aerial tile dominated by rubble, wreckage, scattered storm debris, broken material, or chaotic fragments on the ground",
        "a submeter orthomosaic crop where loose fragmented material is the primary subject rather than an intact roof, road, track, tree canopy, crop field, or dirt surface",
        "an overhead remote sensing tile of storm debris field, rubble pile, scattered wreckage, broken structure material, or irregular damaged fragments",
        "a top down aerial image centered on chaotic debris and loose broken material rather than a damaged but identifiable structure, road, tree, or vehicle track",
        "an aerial image tile where the dominant visual evidence is irregular storm debris, not simply crop rows, grass, dirt, tire tracks, or blank raster padding",
    ),
}
