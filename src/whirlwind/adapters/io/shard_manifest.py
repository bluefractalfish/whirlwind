import csv 
from typing import Any, Protocol, Dict, List 
from dataclasses import asdict  
from pathlib import Path 
from whirlwind.domain.tile import ManifestRow

class ManifestSink(Protocol):
    def write(self, row: ManifestRow) -> None: ...
    def close(self) -> None: ...

class CommaSink:
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


def make_sink(
    kind: str,
    path: Path,
    fieldnames: list[str]= list(ManifestRow.__dataclass_fields__.keys()),
    append: bool = True,
) -> ManifestSink:
    k = (kind or "csv").lower()

    if k == "csv":
        return CommaSink(path, fieldnames, append=append)

    if k == "parquet":
        return ParquetSink(path)

    raise ValueError(f"unknown manifest kind: {kind}")

