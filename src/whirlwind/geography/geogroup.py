import csv 
from pathlib import Path 
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from whirlwind.geography.bbox import BBox 
from whirlwind.geography.location import * 


def read_georows(path: Path) -> list["GeoRow"]:
    rows: list[GeoRow] = []

    with path.open("r", newline="", encoding="utf-8") as f: 
        reader = csv.DictReader(f) 
        for row in reader: 
            try: 
                rows.append(GeoRow.from_metadata_row(row))
            except ValueError:
                raise ValueError 
        return rows 


def _clean(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text

@dataclass(frozen=True)
class GeoRow:
    """
    One geolocated mosaic metadata row.

    It should only wrap row metadata + bbox + lightweight parsing.
    """

    mosaic_id: str
    bbox: BBox
    row: dict[str, str]

    @classmethod
    def from_metadata_row(cls, row: Mapping[str, object]) -> "GeoRow":
        mid = (
            _clean(row.get("mosaic_id"))
            or _clean(row.get("file_id"))
            or _clean(row.get("id"))
        )

        if not mid:
            raise ValueError("metadata row is missing mosaic_id/file_id/id")

        bbox = BBox.from_wgs84_row(row)

        return cls(
            mosaic_id=mid,
            bbox=bbox,
            row={str(k): _clean(v) for k, v in row.items()},
        )

    @property
    def source_text(self) -> str:
        return (
            self.row.get("path")
            or self.row.get("source_uri")
            or self.row.get("uri")
            or ""
        )

    def location_hint(self) -> LocationHint:
        return parse_location_hint_from_text(self.source_text)

    def center_lonlat(self) -> tuple[float, float]:
        return self.bbox.center_lonlat()

    def resolve_location(self, resolver: LocationResolver) -> LocationRecord:
        return resolver.resolve_bbox(
            self.bbox,
            hint=self.location_hint(),
        )
    

@dataclass(frozen=True)
class GeoGroup:
    """
    A geolocated collection of mosaics.

    This is the metamosaic-level geographic object:
      - one metamosaic_id
      - many GeoRows
      - one union bbox
      - one resolved location
    """

    group_id: str
    members: tuple[GeoRow, ...]
    bbox: BBox
    location: LocationRecord
    hint: LocationHint

    @classmethod
    def from_members(
        cls,
        group_id: str,
        members: Sequence[GeoRow],
        *,
        resolver: LocationResolver | None = None,
    ) -> "GeoGroup":
        if not members:
            raise ValueError("GeoGroup requires at least one member.")

        resolver = resolver or NullLocationResolver()

        bbox = BBox.union(m.bbox for m in members)
        hint = most_common_location_hint(m.location_hint() for m in members)

        location = resolver.resolve_bbox(bbox, hint=hint)

        return cls(
            group_id=group_id,
            members=tuple(members),
            bbox=bbox,
            location=location,
            hint=hint,
        )

    @property
    def n_members(self) -> int:
        return len(self.members)

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(m.mosaic_id for m in self.members)

    @property
    def site_guess(self) -> str:
        """
        Display label only.

        Prefer resolved location. Fall back to parsed hint. Otherwise unknown.
        """
        if self.location.display_name != "unknown":
            return self.location.display_name
        if self.hint.name:
            if self.hint.state:
                return f"{self.hint.name}, {self.hint.state}"
            return self.hint.name
        return "unknown"

    def to_metamosaic_record(self) -> dict[str, str]:
        return {
            "metamosaic_id": self.group_id,
            "n_mosaics": str(self.n_members),
            "members": ";".join(self.member_ids),
            **self.bbox.to_record(),
            **self.location.to_record(),
            **self.hint.to_record(),
        }

