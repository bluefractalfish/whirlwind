"""whirlwind.commands.inspect 

    PURPOSE:
        - `inspect` command: scan a directory and generate metadata csv 
    BEHAVIOUR:
        - validate command tokens and resolve path 
        - generate deterministic metadata csv name using fingerpreint of input dir 
        - create csv if not present 
        - print simple scan summary 
        - keeps geospatial extraction and CSV writting to lower layers (geo/io)
    PUBLIC: 
        - InspectCommand 
"""

import csv 
import heapq 
from dataclasses import dataclass, field 
from pathlib import Path 
from typing import Any, Dict, Set, Tuple 

from whirlwind.commands.base import Command 
from whirlwind.io.metadata import write_mosaic_metadata 
from whirlwind.tools import ids 
from whirlwind.tools import pathfinder as pf 
from whirlwind.core.interfaces import LoggerProtocol, NullLogger
from whirlwind.ui import face

class InspectCommand(Command):
    name = "inspect"

    def __init__(self, log: LoggerProtocol | None = None) -> None:
        self.log = log

    def run(self, tokens: list[str], config: Dict[str, Any]) -> int:
        cfg = self.configure(config)
        if not tokens:
            print("inspect: more tokens required")
            return 2 

        cfg["root"] = pf.find_home_()/tokens[0]
        root = Path(str(cfg["root"])).expanduser().resolve()

        print(f"running inspect on {root}")
        if not root.exists() or not root.is_dir():
            print(f"not valid path {root}")
            return 2 

        csv_out_name = f"scan-{ids.gen_fingerprint(root)}.csv"
        run_directory = Path(cfg["out"])
        metadata_dir = run_directory/"metadata"
        metadata_dir.mkdir(parents=True,exist_ok=True)
        csv_path = metadata_dir/csv_out_name

        if not csv_path.exists():
            print(f"writing metadata csv to {csv_path}")
            write_mosaic_metadata(str(root), csv_path)

        stats = inspect_metadata(csv_path)
        #stat_report
        face.process(str(root),"inspection",str(csv_path))
        return 0

    def configure(self, config: dict[str, Any]) -> dict[str, Any]:
        global_cfg = config.get("global", {})
        inspect_cfg = config.get("inspect", {})

        if not isinstance(inspect_cfg, dict):
            inspect_cfg = {}
        if not isinstance(global_cfg, dict):
            global_cfg = {}
        
        cfg = {"root": None,}
        cfg.update(global_cfg)
        cfg.update(inspect_cfg)

        return cfg

    def help(self) -> dict[str,str]:
        return { 
                    "inspect": 
                                
                                "the inspect command is for scanning directories and generating csv manifests of the contents. it handles the generation of uris, uids, fingerprints. when referenced with the <ingest> command these csvs are used to produce tesselations of the mosaics located at the given uris"
                                 
              }


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

            item = (size, uri, dtype, band_count)
            # store 500 largest files 
            if len(stats.largest) < 500:
                heapq.heappush(stats.largest, item)
            elif size > stats.largest[0][0]:
                heapq.heapreplace(stats.largest, item)

    stats.num_dirs = len(parent_dirs)
    return stats
