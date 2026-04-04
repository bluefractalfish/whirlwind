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
from whirlwind.ui import face 

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
            face.error("param init error: tile_size must be > 0")
        if self.stride <= 0:
            face.error("param init error: stride must be > 0")
        if self.shard_size <= 0:
            face.error("param init error: shard_size must be > 0")
    def print_table(self) -> None:
        cols = ["tiling params","value"]
        rows = [
                ["uris",len(self.uris)],
                ["destination",str(self.out_dir)],
                ["tile size",self.tile_size],
                ["stride",self.stride],
                ["drop partials", self.drop_partial],
                ["shard size", self.shard_size],
                ["manifest", self.manifest_kind]
                ]
        face.table(cols,rows)

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
                face.error("param init error: percentile scaling requires 0 <= p_low <p_high <= 100")
        if self.num_samples <= 0:
                face.error("param init error: num_samples must be > 0")
    def print_table(self) -> None:
        cols = ["quant params", "value"]
        rows = [ 
                ["dtype",self.dtype],
                ["scaling", self.scale],
                ["low", self.p_low],
                ["high", self.p_high],
                ["per band", self.per_band],
                ["stats", self.stats],
                ["sampling", self.num_samples]
                ]

        face.table(cols,rows)

