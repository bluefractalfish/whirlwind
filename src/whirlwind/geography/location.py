
""" 

PURPOSE: 
    all geographic geometric helpers that encode the physical orientation in space of 
    a mosaic, metamosaic, etc

"""


import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol 
from urllib.parse import unquote, urlparse

from whirlwind.geography.bbox import BBox 


def _uri_to_path_text(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return uri


@dataclass(frozen=True)
class LocationHint:
    """
    Parsed folder/path hint.

    This is not authoritative geolocation. It is only a naming-convention hint
    that can be compared against coordinate-derived location.
    """

    event_date: str = ""
    name: str = ""
    state: str = ""
    suffix: str = ""
    source: str = ""

    @property
    def has_location(self) -> bool:
        return bool(self.name or self.state)

    def to_record(self, prefix: str = "hint_") -> dict[str, str]:
        return {
            f"{prefix}event_date": self.event_date,
            f"{prefix}location_name": self.name,
            f"{prefix}state": self.state,
            f"{prefix}suffix": self.suffix,
            f"{prefix}source": self.source,
        }


def parse_location_hint_from_text(text: str) -> LocationHint:
    """
    Parses folder names like:

        2025_06_28_Gary_SD_S2
        2025_03_15_Diaz_AR_Track1
        2025_06_28_ClearLake_SD_Autel125

    This is pattern parsing, not hardcoding specific locations. use to confirm guess
    """

    path_text = _uri_to_path_text(text)
    parts = Path(path_text).parts

    pattern = re.compile(
        r"^(?P<y>20\d{2})_(?P<mo>\d{2})_(?P<d>\d{2})_"
        r"(?P<rest>.+)$"
    )

    for part in reversed(parts):
        m = pattern.match(part)
        if not m:
            continue

        event_date = f"{m.group('y')}-{m.group('mo')}-{m.group('d')}"
        rest = m.group("rest")
        tokens = rest.split("_")

        state_idx: int | None = None
        for i, token in enumerate(tokens):
            if re.match(r"^[A-Z]{2}$", token):
                state_idx = i
                break

        if state_idx is None:
            return LocationHint(
                event_date=event_date,
                name=rest,
                state="",
                suffix="",
                source=part,
            )

        name = "_".join(tokens[:state_idx])
        state = tokens[state_idx]
        suffix = "_".join(tokens[state_idx + 1 :])

        return LocationHint(
            event_date=event_date,
            name=name,
            state=state,
            suffix=suffix,
            source=part,
        )

    return LocationHint()


@dataclass(frozen=True)
class LocationRecord:
    """
    Coordinate-derived or hint-derived location.

      - Census place / county polygons should produce high-confidence records
      - GNIS nearest populated place should produce distance-bearing records
      - Folder hints should be lowest confidence choice
    """

    name: str = ""
    state: str = ""
    county: str = ""
    kind: str = "unknown"
    source: str = "unresolved"
    distance_m: float | None = None
    confidence: float = 0.0
    lon: float | None = None
    lat: float | None = None

    @property
    def display_name(self) -> str:
        if self.name and self.state:
            return f"{self.name}, {self.state}"
        if self.name:
            return self.name
        if self.county and self.state:
            return f"{self.county}, {self.state}"
        if self.state:
            return self.state
        return "unknown"

    def to_record(self, prefix: str = "location_") -> dict[str, str]:
        return {
            f"{prefix}name": self.name,
            f"{prefix}state": self.state,
            f"{prefix}county": self.county,
            f"{prefix}kind": self.kind,
            f"{prefix}source": self.source,
            f"{prefix}distance_m": (
                "" if self.distance_m is None else f"{self.distance_m:.3f}"
            ),
            f"{prefix}confidence": f"{self.confidence:.3f}",
            f"{prefix}lon": "" if self.lon is None else f"{self.lon:.12f}",
            f"{prefix}lat": "" if self.lat is None else f"{self.lat:.12f}",
        }


class LocationResolver(Protocol):
    """
    Anything that can resolve a location from a bbox.
    """

    def resolve_bbox(
        self,
        bbox: BBox,
        *,
        hint: LocationHint | None = None,
    ) -> LocationRecord:
        ...


class NullLocationResolver:
    """
    Safe default.

    It does not guess. It only records the bbox center used for future lookup.
    """

    def resolve_bbox(
        self,
        bbox: BBox,
        *,
        hint: LocationHint | None = None,
    ) -> LocationRecord:
        lon, lat = bbox.center_lonlat()

        return LocationRecord(
            kind="unknown",
            source="bbox_center_unresolved",
            confidence=0.0,
            lon=lon,
            lat=lat,
        )


class FolderHintLocationResolver:
    """
    Lightweight fallback resolver.

    This does not hardcode place names. It only uses your folder naming
    convention. Treat its output as lower-confidence than a gazetteer result.
    """

    def resolve_bbox(
        self,
        bbox: BBox,
        *,
        hint: LocationHint | None = None,
    ) -> LocationRecord:
        lon, lat = bbox.center_lonlat()

        if hint is None or not hint.has_location:
            return LocationRecord(
                kind="unknown",
                source="bbox_center_unresolved",
                confidence=0.0,
                lon=lon,
                lat=lat,
            )

        return LocationRecord(
            name=hint.name,
            state=hint.state,
            county="",
            kind="folder_hint",
            source=hint.source or "folder_hint",
            distance_m=None,
            confidence=0.50,
            lon=lon,
            lat=lat,
        )



def most_common_location_hint(hints: Iterable[LocationHint]) -> LocationHint:
    hints = [h for h in hints if h.has_location or h.event_date]
    if not hints:
        return LocationHint()

    key_counts: Counter[tuple[str, str, str, str]] = Counter(
        (h.event_date, h.name, h.state, h.suffix) for h in hints
    )

    event_date, name, state, suffix = key_counts.most_common(1)[0][0]

    source = ""
    for h in hints:
        if (
            h.event_date == event_date
            and h.name == name
            and h.state == state
            and h.suffix == suffix
        ):
            source = h.source
            break

    return LocationHint(
        event_date=event_date,
        name=name,
        state=state,
        suffix=suffix,
        source=source,
    )


def location_warning(
    *,
    resolved: LocationRecord,
    hint: LocationHint,
) -> str:
    """
    Compares coordinate-derived result against path-derived hint.

    This is useful when a folder or filename says one state but the bbox
    resolves somewhere else.
    """

    warnings: list[str] = []

    if hint.state and resolved.state and hint.state != resolved.state:
        warnings.append("state_hint_mismatch")

    if hint.name and resolved.name:
        a = _norm_name(hint.name)
        b = _norm_name(resolved.name)
        if a != b and a not in b and b not in a:
            warnings.append("location_hint_mismatch")

    return ";".join(warnings)


def _norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def haversine_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    Distance helper for future point-based resolvers.
    """

    r = 6_371_000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lam / 2.0) ** 2
    )

    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
