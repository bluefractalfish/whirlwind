
"""whirlwind.commands.manifest

PURPOSE: 
    - entrypoint for manifest command 
BEHAVIOR:
    - manifest stats: creates metadata csv of mosaics (legacy `inspect`)
    - manifest stats ... -> creates run_id/metadata/metadata.csv from mnt/
    - manifest stats path/to/mosaics -> creates from path/to/mosaics 
    - manifest stats path/to path/out -> creates both in and out dir

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
from whirlwind.filetrees import RunTree, MosaicBranch
from whirlwind.manifests import IDManifest, RasterMetadataWriter


CAT_EXT = { 

    "-c": "core",
    "-e": "extended",
    "-a": "full",
    "-t": "total"
    }


class BuildMetadataManifests(Command):

    " get stats of mosaic uris "
    name = "stats"
    in_path: Path 
    out_root: Path 
    tokens: list[str]
    flags: list[str]

    def toke(self, tokens, config) -> None: 
        global_config = config.parse("global","io")
        face.info("LOGGING STATS")
        face.prog_row("1/5","discovering stats")
        
        self.flags = [t for t in tokens if t.startswith("-")] 
        self.tokens = [t for t in tokens if t not in self.flags ]
        
        match len(tokens):
            case 0:
                # if no input directory, default to mnt/
                self.in_path = Path(global_config["in_dir"])
            case 1:
                # if one token, assume it is input dir 
                _,self.in_path = build_path(tokens[0])
            case _: 
                face.error("manifest stats usage: manifest stats expects 0,1,2 arguments")
                pass 

        self.out_root = config.out_path() / config.run_id() 

    def run(self, tokens, config) -> int: 

        self.toke(tokens, config)

        face.prog_row("2/5", "checking if file(s) exists") 
        face.prog_row("3/5","building path for metadata")

       
        #####################################
        ## build run tree if doesnt exists ##
        #####################################
        tree = RunTree.plant(self.out_root)
        ####################################

        metadata_path = tree.get_metadata_csv()
        manifest_path = tree.get_manifest_csv()

        manifest = IDManifest(manifest_path)
        

        if manifest.exists():
            face.print("manifest exists for input directory")

        if not manifest.exists():
            ud = input(f"manifest does not exist, create for {self.in_path} now? (y/n) ")
            if ud == "y":
                face.print("creating manifest")
                manifest.write_now(dest=manifest_path, src=self.in_path)
                face.print(f"manifest created for {self.in_path}")
            else:
                face.prog_row("[0/0]", "exiting manifestger")

        if not metadata_path.exists() or "-f" in self.flags:
            face.prog_row("4/5","building metadata file")
            for scope in ["core","extended","full"]:
                
                ###############################################
                ## initilize MosaicMetadatamanifest from tree ##
                ## choose format, and mode                   ##
                ###############################################
                meta_cat = RasterMetadataWriter.init_from_tree(manifest, tree, fmt="csv", mode=scope)
                ###############################################

                face.prog_row("5/5", f"writing metadata manifest for rasters...")
                ###############################################
                ## Write metadata from MosaicMetadatamanifest ##
                ###############################################
                meta_cat.write()
                ########################## 

            face.process("/"+str(self.in_path.name),"stats", str(tree.get_manifest_csv()))

        face.info(f"metadata manifest exists for {str(self.in_path)} at {metadata_path}")
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

