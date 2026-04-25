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

from whirlwind.geometry.tile import EncodedTile 
from whirlwind.io.shards import ShardPlacement

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
    def __init__(
        self,
        path: Path,
        fieldnames: list[str],
        append: bool = True,
    ) -> None:

        self.path = path
        self.fieldnames = fieldnames

        path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = path.exists()
        file_has_rows = file_exists and path.stat().st_size > 0

        mode = "a" if append else "w"

        self.f = path.open(mode, newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=fieldnames)

        if not file_has_rows or not append:
            self.w.writeheader()

    def write(self, row: ManifestRow) -> None:
        self.w.writerow(asdict(row))
        self.f.flush()

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

def make_sink(
    kind: str,
    path: Path,
    fieldnames: list[str],
    append: bool = True,
) -> ManifestSink:
    k = (kind or "csv").lower()

    if k == "csv":
        return CSVSink(path, fieldnames, append=append)

    if k == "parquet":
        return ParquetSink(path)

    if k == "none":
        return NullSink()

    raise ValueError(f"unknown manifest kind: {kind}")

def manifest_row_from_encoded(encoded: EncodedTile, shard: str) -> ManifestRow: 
    meta: dict[str, Any] = encoded.metadata 

    window = meta["window"]
    bounds = meta["bounds"]

    return ManifestRow(
        tile_id=encoded.tile_id,
        shard=str(shard),
        key=encoded.key,
        source_uri=str(meta["source_uri"]),
        x_off=int(window["x_off"]),
        y_off=int(window["y_off"]),
        w=int(window["w"]),
        h=int(window["h"]),
        crs=meta.get("crs"),
        minx=float(bounds["minx"]),
        miny=float(bounds["miny"]),
        maxx=float(bounds["maxx"]),
        maxy=float(bounds["maxy"]),
        bands=int(meta["bands"]),
        dtype=str(meta["dtype"]),
    )
