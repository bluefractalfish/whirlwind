import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from whirlwind.domain.tile import EncodedTile
from whirlwind.prompts.tile_classes import TARGET_CLASSES, REVIEW_CLASS


@dataclass(frozen=True)
class LabelMetadataRow:
    tile_id: str
    shard: str
    key: str

    label: str
    bucket: str
    dominant: str

    confidence: str
    confidence_score: float

    top_class: str
    top_score: float
    second_class: str
    second_score: float
    margin: float

    top_detailed_class: str
    detail_agrees: bool

    label_json: str


@dataclass(frozen=True)
class ReviewRow:
    tile_id: str
    shard: str
    key: str

    suggested_label: str
    bucket: str

    confidence: str
    confidence_score: float

    top_class: str
    top_score: float
    second_class: str
    second_score: float
    margin: float

    review_reasons: str
    label_json: str

@dataclass(frozen=True)
class DamageRouteRow:
    tile_id: str
    shard: str
    key: str

    bucket: str
    dominant: str

    damage_label: str
    damage_likelihood: float
    route_source: str

    inside_damage_area: bool
    intersects_damage_area: bool
    distance_to_damage_line: str

    review_required: bool
    review_reason: str

    semantic_top_class: str
    semantic_confidence: str
    semantic_top_score: float
    semantic_second_class: str
    semantic_margin: float

    label_json: str

@dataclass(frozen=True)
class LabelJsonRow:
    tile_id: str
    shard: str
    key: str

    bucket: str
    dominant: str

    damage_likelihood: float
    damage_label: str
    route_source: str

    review_required: bool
    review_reason: str

    has_master_damage_geometry: bool
    intersects_damage_area: bool
    tile_center_inside_damage_area: bool

    distance_to_damage_centerline: str
    distance_to_damage_area: str

    nearest_damage_line_id: str
    nearest_damage_area_id: str

    metamosaic_id: str
    master_gpkg_path: str
    damage_line_layer: str
    damage_area_layer: str

    mosaic_crs: str
    geometry_clipped_to_mosaic_context: bool

    area_intersection_score: float
    area_distance_score: float
    centerline_distance_score: float
    semantic_score: float

    debris_score: float
    structure_score: float
    tree_score: float

    router_version: str
    geometry_context_distance: str
    sigma_centerline: str
    sigma_area: str 

class DataclassCsvSink:
    def __init__(
        self,
        path: Path,
        fieldnames: list[str],
        append: bool = True,
    ) -> None:
        self.path = path
        self.fieldnames = fieldnames

        path.parent.mkdir(parents=True, exist_ok=True)

        file_has_rows = path.exists() and path.stat().st_size > 0
        mode = "a" if append else "w"

        self.f = path.open(mode, newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=fieldnames)

        if not file_has_rows or not append:
            self.w.writeheader()

    def write(self, row: Any) -> None:
        self.w.writerow(asdict(row))
        self.f.flush()

    def close(self) -> None:
        self.f.close()


def make_label_metadata_sink(path: Path, append: bool = True) -> DataclassCsvSink:
    return DataclassCsvSink(
        path,
        fieldnames=list(LabelMetadataRow.__dataclass_fields__.keys()),
        append=append,
    )

def make_damage_route_sink(path: Path, append: bool = True) -> DataclassCsvSink:
    return DataclassCsvSink(
        path,
        fieldnames=list(DamageRouteRow.__dataclass_fields__.keys()),
        append=append,
    )

def make_review_sink(path: Path, append: bool = True) -> DataclassCsvSink:
    return DataclassCsvSink(
        path,
        fieldnames=list(ReviewRow.__dataclass_fields__.keys()),
        append=append,
    )

def make_label_json_sink(path: Path, append: bool = True) -> DataclassCsvSink:
    return DataclassCsvSink(
        path,
        fieldnames=list(LabelJsonRow.__dataclass_fields__.keys()),
        append=append,
    )

def semantic_payload(encoded: EncodedTile) -> dict[str, Any]:
    label = encoded.metadata.get("label", {})
    semantic = label.get("semantic", {})

    if not semantic:
        return {}

    return semantic

def damage_payload(encoded: EncodedTile) -> dict[str, Any]:
    label = encoded.metadata.get("label", {})
    damage = label.get("damage_review", {})

    if not damage:
        return {}

    return damage

def label_json(encoded: EncodedTile) -> str:
    return json.dumps(
        encoded.metadata.get("label", {}),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def is_review_tile(encoded: EncodedTile) -> bool:
    bucket = str(encoded.metadata.get("bucket", ""))
    semantic = semantic_payload(encoded)

    label = str(semantic.get("bucket", bucket))

    if label == REVIEW_CLASS:
        return True

    if label not in TARGET_CLASSES:
        return True

    return False


def build_label_metadata_row(
    encoded: EncodedTile,
    shard: str,
) -> LabelMetadataRow:
    s = semantic_payload(encoded)

    return LabelMetadataRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,

        label=str(s.get("bucket", encoded.metadata.get("bucket", ""))),
        bucket=str(encoded.metadata.get("bucket", "")),
        dominant=str(s.get("dominant", "")),

        confidence=str(s.get("confidence", "")),
        confidence_score=float(s.get("confidence_score", 0.0)),

        top_class=str(s.get("top_class", "")),
        top_score=float(s.get("top_score", 0.0)),
        second_class=str(s.get("second_class", "")),
        second_score=float(s.get("second_score", 0.0)),
        margin=float(s.get("margin", 0.0)),

        top_detailed_class=str(s.get("top_detailed_class", "")),
        detail_agrees=bool(s.get("detail_agrees", False)),

        label_json=label_json(encoded),
    )


def build_review_row(
    encoded: EncodedTile,
    shard: str,
) -> ReviewRow:
    s = semantic_payload(encoded)

    reasons = s.get("review_reasons", [])
    if isinstance(reasons, list):
        reasons_str = "|".join(str(r) for r in reasons)
    else:
        reasons_str = str(reasons)

    return ReviewRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,

        suggested_label=str(s.get("dominant", s.get("top_class", ""))),
        bucket=REVIEW_CLASS,

        confidence=str(s.get("confidence", "review")),
        confidence_score=float(s.get("confidence_score", 0.0)),

        top_class=str(s.get("top_class", "")),
        top_score=float(s.get("top_score", 0.0)),
        second_class=str(s.get("second_class", "")),
        second_score=float(s.get("second_score", 0.0)),
        margin=float(s.get("margin", 0.0)),

        review_reasons=reasons_str,
        label_json=label_json(encoded),
    )

def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def build_label_json_row(
    encoded: EncodedTile,
    shard: str,
) -> LabelJsonRow:
    d = damage_payload(encoded)
    score = d.get("score") or {}

    return LabelJsonRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,

        bucket=str(d.get("bucket", encoded.metadata.get("bucket", ""))),
        dominant=str(d.get("dominant", "")),

        damage_likelihood=_float(d.get("damage_likelihood")),
        damage_label=_text(d.get("damage_label")),
        route_source=str(d.get("route_source", "")),

        review_required=bool(d.get("review_required", True)),
        review_reason=str(d.get("review_reason", "")),

        has_master_damage_geometry=bool(d.get("has_master_damage_geometry", False)),
        intersects_damage_area=bool(d.get("intersects_damage_area", False)),
        tile_center_inside_damage_area=bool(
            d.get("tile_center_inside_damage_area", False)
        ),

        distance_to_damage_centerline=_text(
            d.get("distance_to_damage_centerline")
        ),
        distance_to_damage_area=_text(
            d.get("distance_to_damage_area")
        ),

        nearest_damage_line_id=_text(d.get("nearest_damage_line_id")),
        nearest_damage_area_id=_text(d.get("nearest_damage_area_id")),

        metamosaic_id=_text(d.get("metamosaic_id")),
        master_gpkg_path=_text(d.get("master_gpkg_path")),
        damage_line_layer=str(d.get("damage_line_layer", "")),
        damage_area_layer=str(d.get("damage_area_layer", "")),

        mosaic_crs=_text(d.get("mosaic_crs")),
        geometry_clipped_to_mosaic_context=bool(
            d.get("geometry_clipped_to_mosaic_context", False)
        ),

        area_intersection_score=_float(score.get("area_intersection_score")),
        area_distance_score=_float(score.get("area_distance_score")),
        centerline_distance_score=_float(score.get("centerline_distance_score")),
        semantic_score=_float(score.get("semantic_score")),

        debris_score=_float(score.get("debris_score")),
        structure_score=_float(score.get("structure_score")),
        tree_score=_float(score.get("tree_score")),

        router_version=str(d.get("router_version", "")),
        geometry_context_distance=_text(d.get("geometry_context_distance")),
        sigma_centerline=_text(d.get("sigma_centerline")),
        sigma_area=_text(d.get("sigma_area")),
   )

def build_damage_route_row(
    encoded: EncodedTile,
    shard: str,
) -> DamageRouteRow:
    d = damage_payload(encoded)

    distance = d.get("distance_to_damage_line")
    distance_text = "" if distance is None else str(distance)

    damage_label = d.get("damage_label")
    damage_label_text = "" if damage_label is None else str(bool(damage_label))

    return DamageRouteRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,

        bucket=str(d.get("bucket", encoded.metadata.get("bucket", ""))),
        dominant=str(d.get("dominant", "")),

        damage_label=damage_label_text,
        damage_likelihood=float(d.get("damage_likelihood", 0.0)),
        route_source=str(d.get("route_source", "")),

        inside_damage_area=bool(d.get("inside_damage_area", False)),
        intersects_damage_area=bool(d.get("intersects_damage_area", False)),
        distance_to_damage_line=distance_text,

        review_required=bool(d.get("review_required", True)),
        review_reason=str(d.get("review_reason", "")),

        semantic_top_class=str(d.get("semantic_top_class", "")),
        semantic_confidence=str(d.get("semantic_confidence", "")),
        semantic_top_score=float(d.get("semantic_top_score") or 0.0),
        semantic_second_class=str(d.get("semantic_second_class", "")),
        semantic_margin=float(d.get("semantic_margin") or 0.0),

        label_json=label_json(encoded),
    )

def build_review_row_from_damage(
    encoded: EncodedTile,
    shard: str,
) -> ReviewRow:
    d = damage_payload(encoded)

    return ReviewRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,

        suggested_label=str(d.get("dominant", "")),
        bucket=str(d.get("bucket", REVIEW_CLASS)),

        confidence=str(d.get("route_source", "damage_review")),
        confidence_score=float(d.get("damage_likelihood", 0.0)),

        top_class=str(d.get("semantic_top_class", "")),
        top_score=float(d.get("semantic_top_score") or 0.0),
        second_class=str(d.get("semantic_second_class", "")),
        second_score=float(d.get("semantic_second_score") or 0.0),
        margin=float(d.get("semantic_margin") or 0.0),

        review_reasons=str(d.get("review_reason", "")),
        label_json=label_json(encoded),
    ) 

def write_label_sidecar(
    *,
    encoded: EncodedTile,
    shard: str,
    label_sink: DataclassCsvSink,
    review_sink: DataclassCsvSink,
    damage_sink: DataclassCsvSink | None = None,
) -> None:
    if damage_sink is not None and damage_payload(encoded):
        damage_sink.write(build_damage_route_row(encoded, shard))

        d = damage_payload(encoded)
        if bool(d.get("review_required", True)):
            review_sink.write(build_review_row_from_damage(encoded, shard))
        return

    if is_review_tile(encoded):
        review_sink.write(build_review_row(encoded, shard))
    else:
        label_sink.write(build_label_metadata_row(encoded, shard))

def write_review_sidecar( 
    *,
    encoded: EncodedTile,
    shard: str,
    review_sink: DataclassCsvSink,
    ) -> None:
    review_sink.write(build_review_row(encoded, shard))


def write_label_json_row(
    *,
    encoded: EncodedTile,
    shard: str,
    sink: DataclassCsvSink,
) -> None:
    if damage_payload(encoded):
        sink.write(build_label_json_row(encoded, shard))
