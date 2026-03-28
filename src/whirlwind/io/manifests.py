"""whirlwind.io.manifests 

    PURPOSE:
        - persist per-tile manifest rows 

    BEHAVIOR:
        - Defines stable ManifestRow schema for shards 
        - provide sink for CSV and Parquet 
    PUBLIC:
        - ManifestRow 
        - ManifestSink protocol 
        - CSVSink, ParquetSink 
    
        

"""
from __future__ import annotations
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol

@dataclass(frozen=True)
class ManifestRow:
    tile_id: str
    shard: str
    key: str
    source_uri: str
    x_off: int
    y_off: int
    w: int
    h: int
    crs: str | None
    minx: float
    miny: float
    maxx: float
    maxy: float
    bands: int
    dtype: str

class ManifestSink(Protocol):
    def write(self, row: ManifestRow) -> None: ...
    def close(self) -> None: ...

class CSVSink:
    def __init__(self, path: Path, fieldnames: List[str]) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = path.open("w", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=fieldnames)
        self.w.writeheader()
    def write(self, row: ManifestRow) -> None:
        self.w.writerow(asdict(row))
    def close(self) -> None:
        self.f.close()

class ParquetSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.rows: List[Dict[str, Any]] = []
        try:
            import pyarrow as pa # type: ignore
            import pyarrow.parquet as pq # type: ignore
        except Exception as exc:
            raise RuntimeError(f"pyarrow required for parquet manifest: {exc}") from exc
        self.pa = pa
        self.pq = pq

    def write(self, row: ManifestRow) -> None:
        # Convert Path-like values (if any) to strings to avoid Arrow type errors.
        record = {}
        for k, v in asdict(row).items():
            record[k] = str(v) if isinstance(v, Path) else v
            self.rows.append(record)
    def close(self) -> None:
        table = self.pa.Table.from_pylist(self.rows)
        self.pq.write_table(table, str(self.path))

class NullSink:
    def write(self, row: ManifestRow) -> None:
        return
    def close(self) -> None:
        return

def make_sink(kind: str, path: Path, fieldnames: List[str]) -> ManifestSink:
    k = (kind or "csv").lower()
    if k == "csv":
        return CSVSink(path, fieldnames)
    if k == "parquet":
        return ParquetSink(path)
    if k == "none":
        return NullSink()
    raise ValueError(f"unknown manifest kind: {kind}")
