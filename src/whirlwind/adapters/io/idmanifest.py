from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from whirlwind.adapters.filesystem.discoverfiles import DiscoverFiles
from whirlwind.domain.filesystem.runtree import RunTree 
from whirlwind.domain.geometry.mosaics.mosaic import MosaicRecord 

class IDManifest:
    def __init__(
        self,
        path: str | Path,
        file_types: tuple[str, ...] = (".tif", ".tiff"),
    ) -> None:

        self.path = Path(path).expanduser().resolve()
        self.file_types = file_types
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    @classmethod 
    def from_tree(cls, tree: RunTree) -> "IDManifest": 
        return IDManifest(tree.get_manifest_path_csv())
    
    @property 
    def length(self) -> int:
        return len(list(self.paths()))

    def exists(self) -> bool:
        return self.path.exists() and self.path.is_file() and self.path.stat().st_size > 0
    
    def rows(self) -> Iterator[dict[str, str]]:
        with self.path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield dict(row)
    
    def records(self) -> Iterator[MosaicRecord]:
        for row in self.rows():
            yield MosaicRecord.from_row(row)

    def show_dont_write(self, src: str | Path) -> tuple[list[str], list[list[str]]]: 
        discovery = DiscoverFiles(src) 
        
        records = [f.record() for f in discovery.discover(self.file_types)] 
        
        if not records: 
            return [],[]
                                   
        cols = list(records[0].keys())
        rows = [[record.get(col,"") for col in cols] for record in records]

        return cols, rows 


    def write_from(self, src: str | Path) -> int:
        discovery = DiscoverFiles(src)

        if discovery.is_empty(self.file_types):
            return 1

        rows = [file.record() for file in discovery.discover(self.file_types)]
        if not rows:
            return 1

        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        return 0

    def mosaic_ids(self) -> Iterator[str]:
        try:
            yield from self._column("mosaic_id")
        except ValueError:
            yield from self._column("file_id")

    def ids(self) -> Iterator[str]:
        yield from self.mosaic_ids()

    def mids(self) -> Iterator[str]:
        yield from self.mosaic_ids()

    def uris(self) -> Iterator[str]:
        yield from self._column("uri")

    def paths(self) -> Iterator[Path]:
        for value in self._column("path"):
            yield Path(value)

    def _column(self, name: str) -> Iterator[str]:
        with self.path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if name not in (reader.fieldnames or []):
                raise ValueError(f"manifest missing column {name}: {self.path}")
            for row in reader:
                value = (row.get(name) or "").strip()
                if value:
                    yield value
