from __future__ import annotations

from dataclasses import dataclass, field, asdict 
from typing import Any, Sequence, Optional 
from pathlib import Path 

from whirlwind.geometry.footprint import FootPrint
from whirlwind.filetrees.mosaicbranch import MosaicBranch


@dataclass(frozen=True)
class LabelField: 
    name: str  # e.g. path_id, mosaic_id, even_date, ... 
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
    def default(cls) -> "PathSpec":
        common_fields = [
                LabelField("path_id", "str"),
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
