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


def make_review_sink(path: Path, append: bool = True) -> DataclassCsvSink:
    return DataclassCsvSink(
        path,
        fieldnames=list(ReviewRow.__dataclass_fields__.keys()),
        append=append,
    )


def semantic_payload(encoded: EncodedTile) -> dict[str, Any]:
    label = encoded.metadata.get("label", {})
    semantic = label.get("semantic", {})

    if not semantic:
        return {}

    return semantic


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


def write_label_sidecar(
    *,
    encoded: EncodedTile,
    shard: str,
    label_sink: DataclassCsvSink,
    review_sink: DataclassCsvSink,
) -> None:
    if is_review_tile(encoded):
        review_sink.write(build_review_row(encoded, shard))
    else:
        label_sink.write(build_label_metadata_row(encoded, shard))
