"""
WGS84 bounding-box representation and overlap measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


def _as_float(value: object, *, field_name: str) -> float:
    try:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            raise ValueError
        return float(text)
    except Exception as error:
        raise ValueError(
            f"invalid float for {field_name}: {value!r}"
        ) from error


@dataclass(frozen=True)
class BBox:
    """A longitude/latitude bounding box.

    ``coverage_similarity`` is deliberately stricter than ordinary
    intersection with rasters covering near the samer area scoring near 1.0
    """

    minx: float
    miny: float
    maxx: float
    maxy: float

    @classmethod
    def from_bounds(cls, bounds: Any) -> "BBox":
        return cls(
            minx=float(bounds.left),
            miny=float(bounds.bottom),
            maxx=float(bounds.right),
            maxy=float(bounds.top),
        )

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
            minx=min(box.minx for box in boxes),
            miny=min(box.miny for box in boxes),
            maxx=max(box.maxx for box in boxes),
            maxy=max(box.maxy for box in boxes),
        )

    @property
    def width(self) -> float:
        return max(0.0, self.maxx - self.minx)

    @property
    def height(self) -> float:
        return max(0.0, self.maxy - self.miny)

    @property
    def area(self) -> float:
        return self.width * self.height

    def intersects(self, other: "BBox") -> bool:
        return (
            self.minx <= other.maxx
            and self.maxx >= other.minx
            and self.miny <= other.maxy
            and self.maxy >= other.miny
        )


    def intersection_area(self, other: "BBox") -> float:
        width = max(
            0.0,
            min(self.maxx, other.maxx)
            - max(self.minx, other.minx),
        )

        height = max(
            0.0,
            min(self.maxy, other.maxy)
            - max(self.miny, other.miny),
        )

        return width * height


    def coverage_similarity(self, other: "BBox") -> float:
        """
        Fraction of the smaller footprint covered by the larger footprint.

        Identical footprints return 1.0.

        A smaller footprint fully contained inside a larger footprint also
        returns 1.0.
        """
        smaller_area = min(self.area, other.area)

        if smaller_area <= 0.0:
            return 0.0

        return min(
            1.0,
            self.intersection_area(other) / smaller_area,
        )

    @property
    def center_lon(self) -> float:
        return (self.minx + self.maxx) / 2.0

    @property
    def center_lat(self) -> float:
        return (self.miny + self.maxy) / 2.0

    def center_lonlat(self) -> tuple[float, float]:
        return self.center_lon, self.center_lat

    @property
    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.minx, self.miny, self.maxx, self.maxy

    def to_record(self, prefix: str = "") -> dict[str, str]:
        return {
            f"{prefix}minx_wgs84": f"{self.minx:.12f}",
            f"{prefix}miny_wgs84": f"{self.miny:.12f}",
            f"{prefix}maxx_wgs84": f"{self.maxx:.12f}",
            f"{prefix}maxy_wgs84": f"{self.maxy:.12f}",
            f"{prefix}center_lon": f"{self.center_lon:.12f}",
            f"{prefix}center_lat": f"{self.center_lat:.12f}",
        }
