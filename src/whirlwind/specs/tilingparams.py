"""whirlwind.specs.tilespecs  

"""

from __future__ import annotations
from dataclasses import dataclass, asdict 

@dataclass(frozen=True)
class TParams:
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
