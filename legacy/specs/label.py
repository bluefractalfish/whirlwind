from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LabelSpec:
    positive_label: str = "damage"
    negative_label: str = "no_damage"
    predicate: str = "intersects"

    def to_record(self) -> dict[str, object]:
        return asdict(self)
