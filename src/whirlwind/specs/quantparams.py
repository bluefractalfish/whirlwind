
from __future__ import annotations
from dataclasses import dataclass, asdict 

@dataclass(frozen=True)
class QParams:
    dtype: str
    scale: str = "none"
    p_low: float = 2.0
    p_high: float = 98.0
    per_band: bool = True
    stats: str = "sample"
    num_samples: int = 2048

    def to_record(self) -> dict[str, object]:
        return asdict(self)
