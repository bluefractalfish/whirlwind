"""whirlwind.specs.tilespecs  

"""

from __future__ import annotations
from dataclasses import dataclass, asdict 
from whirlwind.domain.config.schema import Config 

@dataclass(frozen=True)
class TSpec:
    tile_size: int
    stride: int
    drop_partial: bool = True

    def __post_init__(self) -> None:
        if self.tile_size <= 0:
            raise ValueError("tile_size must be > 0")
        if self.stride <= 0:
            raise ValueError("stride must be > 0")

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_config(cls, config: Config) -> "TSpec":
        raw = config.parse("mosaic","tesselate")
        tile_size = int(raw["tile_size"])
        stride = int(raw["stride"])
        drop_partial = bool(raw["drop_partial"])

        return cls(tile_size=tile_size,
                   stride=stride,
                   drop_partial=drop_partial )


