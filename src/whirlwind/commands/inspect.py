from __future__ import annotations

import csv
import heapq
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import Command
from ..utils import pathfinder as pf
from ..utils import ids
from ..utils import readwrite as rwr


class InspectCommand(Command):
    name = "inspect"

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:
        
        cfg = self._config(config)
        
        if tokens:
            cfg["root"] = tokens[0]
        root = Path(cfg["root"])

        if not root.exists() or not root.is_dir():
            raise ValueError(f"not a directory: {root}")

        out_name = f"{ids.gen_fingerprint(root)}.csv"
        metadata_dir = pf._find_home_() / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        csv_path = metadata_dir / out_name

        if not csv_path.exists():
            rwr.write_metadata(str(root), out_name)

        stats = inspect_metadata(csv_path, top_n=cfg["top_n"])
        print(f"dirs={stats.num_dirs} files={stats.num_files} bytes={stats.total_bytes}")
        return 0

    def _config(self, config: dict[str, Any]) -> dict[str, Any]:
        inspect_cfg = config.get("inspect", {})
        if not isinstance(inspect_cfg, dict):
            inspect_cfg = {}

        cfg = {
            "root": None,
            "top_n": 500,
        }
        cfg.update(inspect_cfg)


        return cfg


@dataclass
class ScanStats:
    num_dirs: int = 0
    num_files: int = 0
    total_bytes: int = 0
    largest: list[tuple[int, str, str, str]] = field(default_factory=list)


def inspect_metadata(csv_path: Path, top_n: int = 500) -> ScanStats:
    stats = ScanStats()
    parent_dirs: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = (row.get("uri") or "").strip()
            if not uri:
                continue

            size_text = (row.get("byte_size") or "").strip()
            try:
                size = int(size_text) if size_text else 0
            except ValueError:
                size = 0

            dtype = (row.get("dtype") or "").strip()
            band_count = (row.get("band_count") or "").strip()

            stats.num_files += 1
            stats.total_bytes += size
            parent_dirs.add(str(Path(uri).parent))

            if top_n > 0:
                item = (size, uri, dtype, band_count)
                if len(stats.largest) < top_n:
                    heapq.heappush(stats.largest, item)
                elif size > stats.largest[0][0]:
                    heapq.heapreplace(stats.largest, item)

    stats.num_dirs = len(parent_dirs)
    return stats
