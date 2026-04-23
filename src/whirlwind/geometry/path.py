from __future__ import annotations

from dataclasses import dataclass, field, asdict 
from typing import Any, Sequence, Optional 
from pathlib import Path 

from whirlwind.geometry.footprint import FootPrint
from whirlwind.filetrees.mosaicbranch import MosaicBranch


@dataclass(frozen=True)
class DamagePath:
    """
    Metadata-first vector annotation associated with a parent mosaic.

    Store vector geometry as WKT or another lightweight serialized form.
    Avoid storing heavyweight decoded geometry objects here.
    """
    id: str
    parent_id: str
    crs: str
    footprint: FootPrint 

    line_wkt: str | None = None
    polygon_wkt: str | None = None

    annotations: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "crs": self.crs,
            "bounds": self.footprint.to_record(),
            "line_wkt": self.line_wkt,
            "polygon_wkt": self.polygon_wkt,
            "annotations": dict(self.annotations),
        }

    @property
    def confidence(self) -> float | None:
        value = self.annotations.get("confidence")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def damage_level(self) -> str | None:
        value = self.annotations.get("damage_level")
        if value is None:
            return None
        return str(value)


@dataclass(frozen=True)
class LabelField: 
    name: str  # e.g. label_id, mosaic_id, even_date, ... 
    kind: str # 'str' | 'int' | 'float' | 'date' 

@dataclass(frozen=True)
class LayerSpec: 
    name: str # e.g. damage_path, damage_area 
    geometry: str # LineString | Polygon
    fields: Sequence[LabelField] 

@dataclass(frozen=True)
class LabelSpec: 
    layers: Sequence[LayerSpec] 

    @classmethod 
    def default(cls) -> "LabelSpec":
        common_fields = [
                LabelField("label_id", "str"),
                LabelField("mosaic_id", "str"),
                LabelField("source_uri", "str"),
                LabelField("browse_uri", "str"),
                LabelField("label_type", "str"),
                LabelField("even_date", "str"),
                LabelField("notes", "str"),
                LabelField("created_at", "str"),
                LabelField("updated_at", "str")
                ]
        return cls(
                layers=[
                    LayerSpec("damage_path", "LineString", common_fields), 
                    LayerSpec("damage_area", "Polygon", common_fields)
                    ]
                )
@dataclass(frozen=True)
class LabelPlan: 
    mosaic_id: str 
    source_uri: str 
    browse_uri: str 
    out_dir: Path 
    gpkg_path: Path 
    metadata_path: Path 
    crs_wkt: str 
    spec: LabelSpec 

    @classmethod 
    def from_browse(
            cls, 
            branch: MosaicBranch, 
            crs_wkt: str, 
            spec: Optional[LabelSpec] = None 
            ) -> "LabelPlan":
        ... 

    def record(self) -> dict[str, object]:
        out = asdict(self)
        out["browse_uri"] = str(self.browse_uri)
        out["out_dir"] = str(self.out_dir)
        out["gpkg_path"] = str(self.gpkg_path)
        out["metadata_path"] = str(self.metadata_path)
        return out

