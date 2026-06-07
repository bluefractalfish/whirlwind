from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LabelField: 
    name: str  # e.g. path_id, mosaic_id, event_date, ... 
    kind: str # 'str' | 'int' | 'float' | 'date' 

@dataclass(frozen=True)
class LayerSpec: 
    name: str # e.g. damage_path, damage_area 
    geometry: str # LineString | Polygon
    fields: Sequence[LabelField] 

@dataclass(frozen=True)
class PathSpec: 
    layers: Sequence[LayerSpec] 

    @classmethod 
    def default(cls, geom_name: str ="geom") -> "PathSpec":
        common_fields = [
                LabelField("path_id", "str"),
                LabelField("mosaic_id", "str"),
                LabelField("source_uri", "str"),
                LabelField("browse_uri", "str"),
                LabelField("label_type", "str"),
                LabelField("event_date", "str"),
                LabelField("notes", "str"),
                LabelField("created_at", "str"),
                LabelField("updated_at", "str")
                ]
        return cls(
                layers=[
                    LayerSpec(f"{geom_name}_line", "LineString", common_fields), 
                    LayerSpec(f"{geom_name}_area", "Polygon", common_fields)
                    ]
                )


