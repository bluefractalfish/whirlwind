""" 
PURPOSE: 
        bbox representation for spatial bounding boxes 

"""

from dataclasses import dataclass
from typing import Iterable, Mapping


def _as_float(value: object, *, field_name: str) -> float:
    try:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            raise ValueError
        return float(text)
    except Exception as e:
        raise ValueError(f"invalid float for {field_name}: {value!r}") from e

@dataclass(frozen=True)
class BBox:
    """
    WGS84 bounding box.

    Naming convention:
      minx/maxx = longitude
      miny/maxy = latitude
    """

    minx: float
    miny: float
    maxx: float
    maxy: float

    @classmethod
    def from_wgs84_row(cls, row: Mapping[str, object]) -> "BBox":
        return cls(
            minx=_as_float(row.get("minx_wgs84"), field_name="minx_wgs84"),
            miny=_as_float(row.get("miny_wgs84"), field_name="miny_wgs84"),
            maxx=_as_float(row.get("maxx_wgs84"), field_name="maxx_wgs84"),
            maxy=_as_float(row.get("maxy_wgs84"), field_name="maxy_wgs84"),
        )

    @classmethod
    def union(cls, boxes: Iterable["BBox"]) -> "BBox":
        boxes = list(boxes)
        if not boxes:
            raise ValueError("Cannot compute BBox union from an empty iterable.")

        return cls(
            minx=min(b.minx for b in boxes),
            miny=min(b.miny for b in boxes),
            maxx=max(b.maxx for b in boxes),
            maxy=max(b.maxy for b in boxes),
        )

    def intersects(self, other: "BBox") -> bool:
        return (
            self.minx <= other.maxx
            and self.maxx >= other.minx
            and self.miny <= other.maxy
            and self.maxy >= other.miny
        )

    @property
    def center_lon(self) -> float:
        return (self.minx + self.maxx) / 2.0

    @property
    def center_lat(self) -> float:
        return (self.miny + self.maxy) / 2.0

    def center_lonlat(self) -> tuple[float, float]:
        return self.center_lon, self.center_lat

    def to_record(self, prefix: str = "") -> dict[str, str]:
        return {
            f"{prefix}minx_wgs84": f"{self.minx:.12f}",
            f"{prefix}miny_wgs84": f"{self.miny:.12f}",
            f"{prefix}maxx_wgs84": f"{self.maxx:.12f}",
            f"{prefix}maxy_wgs84": f"{self.maxy:.12f}",
            f"{prefix}center_lon": f"{self.center_lon:.12f}",
            f"{prefix}center_lat": f"{self.center_lat:.12f}",
        }

