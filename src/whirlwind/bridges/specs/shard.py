from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShardSpec:
    shard_size: int
    prefix: str = ""
    manifest_kind: str = "parquet"

    def to_record(self) -> dict[str, object]:
        return asdict(self)
