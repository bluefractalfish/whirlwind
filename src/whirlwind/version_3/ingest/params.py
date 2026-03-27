"""whirlwind.ingest.params 
    
    PURPOSE: 
        - typed param objects for ingesting mosaics 
    BEHAVIOR 
        - provide immutable, validated containers for tileing and quantization settings 

    PUBLIC:
        - TParams 
        - QParams 
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class TParams:

    uris: list[str]
    out_dir: Path
    tile_size: int
    stride: int
    drop_partial: bool
    shard_size: int
    shard_prefix: str
    manifest_kind: str

    def validate(self) -> None:
        if self.tile_size <= 0:
            raise ValueError("tile_size must be > 0")
        if self.stride <= 0:
            raise ValueError("stride must be > 0")
        if self.shard_size <= 0:
            raise ValueError("shard_size must be > 0")

@dataclass(frozen=True)
class QParams:

    dtype: str
    scale: str
    p_low: float
    p_high: float
    per_band: bool
    stats: str
    num_samples: int

    def validate(self) -> None:
        if self.scale == "percentile":
            if not (0.0 <= self.p_low < self.p_high <= 100.0):
                raise ValueError("percentile scaling requires 0 <= p_low <p_high <= 100")
        if self.num_samples <= 0:
            raise ValueError("num_samples must be > 0")
