from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from whirlwind.geometry.footprint import FootPrint


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
