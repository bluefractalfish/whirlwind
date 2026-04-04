
"""whirlwind.commands.catalog

PURPOSE: 
    - entrypoint for catalog command 
BEHAVIOR:
    - catalog stats: creates metadata csv of mosaics (legacy `inspect`)
    - catalog stats ... -> creates run_id/metadata/metadata.csv from mnt/
    - catalog stats path/to/mosaics -> creates from path/to/mosaics 
    - catalog stats path/to path/out -> creates both in and out dir

"""

import csv 
import heapq 
from dataclasses import dataclass, field 
from pathlib import Path 
from typing import Set

from whirlwind.ui import face 
from whirlwind.commands.base import Command
from whirlwind.tools.ids import gen_fingerprint
from whirlwind.tools.pathfinder import build_path 
from whirlwind.io.metadata import write_mosaic_metadata

class StatsCommand(Command):

    " get stats of mosaic uris "
    name = "stats"
    in_path: Path 
    dest_path: Path 

    def run(self, tokens, config) -> int: 
        global_config = config.parse("global","io")
        this_config = config.parse("catalog","stats") 
        face.info("LOGGING STATS")
        face.prog_row("1/4","discovering stats")
        match len(tokens):
            case 0:
                default_in = Path(global_config["in_dir"])
                _, self.in_path = build_path(default_in)
                _,self.dest_path = build_path(global_config["dest_dir"]) 
            case 1:
                _,self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(global_config["dest_dir"]) 
                
            case 2:
                _,self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(tokens[1])
                
            case _: 
                face.error("catalog stats usage: catalog stats expects 0,1,2 arguments")
                return 3

        face.prog_row("2/4", "checking if file exists")
        
        face.prog_row("3/4","building path for metadata")
        metadata_name = f"stats-{gen_fingerprint(str(self.in_path))}.csv"
        metadata_path = self.dest_path / metadata_name

        if not metadata_path.exists():
            face.prog_row("4/4","metadata doesnt exist, writing metadata")
            write_mosaic_metadata(str(self.in_path), metadata_path)
            face.process("/"+str(self.in_path.name),"stats", str(self.dest_path.name)+"/"+metadata_name)

        face.info(f"catalog exists for {str(self.in_path)} in {str(self.dest_path)}")
        stats = inspect_metadata(metadata_path)
        return 0

@dataclass
class ScanStats:
    num_dirs: int = 0
    num_files: int = 0
    total_bytes: int = 0
    largest: list[tuple[int, str, str, str]] = field(default_factory=list)


def inspect_metadata(csv_path: Path) -> ScanStats:
    stats = ScanStats()
    parent_dirs: Set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = (row.get("uri") or "").strip()
            if not uri:
                continue

            byte_size = (row.get("byte_size") or "").strip()
            try:
                size = int(byte_size) if byte_size else 0
            except ValueError:
                size = 0

            dtype = (row.get("dtype") or "").strip()
            band_count = (row.get("band_count") or "").strip()

            stats.num_files += 1
            stats.total_bytes += size
            parent_dirs.add(str(Path(uri).parent))

            item = (size, uri, dtype, band_count)
            # store 500 largest files 
            if len(stats.largest) < 500:
                heapq.heappush(stats.largest, item)
            elif size > stats.largest[0][0]:
                heapq.heapreplace(stats.largest, item)

    stats.num_dirs = len(parent_dirs)
    return stats

