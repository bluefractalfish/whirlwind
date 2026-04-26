from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from whirlwind.adapters.filesystem.discoverfiles import DiscoverFiles
from whirlwind.domain.filesystem.runtree import RunTree 

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

    def exists(self) -> bool:
        return self.path.exists() and self.path.is_file() and self.path.stat().st_size > 0

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
    
    def ids(self) -> Iterator[str]:
        yield from self._column("id")

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
