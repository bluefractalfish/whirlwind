

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import shutil 

from whirlwind.filesystem import MosaicBranch

@dataclass(frozen=True)
class RunTree:
    """ each RunTree holds a <root> Path and a <manifest_dir> Path """
    root: Path 
    manifest_dir: Path 

    @classmethod
    def plant(cls, root: str | Path) -> "RunTree":
        """ plant a tree at root. checks if root already exists and overwrites if requested, calling ensure() and returning RunTree"""
        root = Path(root).expanduser().resolve()
        #######################################
        ## CHECK IF ROOT EXISTS, OVERWRITE IF NOT EMPTY?  ##
        #######################################

        tree = cls( root = root, manifest_dir = root /"manifest",)

        ############################################
        ## RUN ENSURE(), mkdir for root, manifest ##
        tree.ensure()
        ############################################

        return tree 

    @property 
    def exists(self) -> bool:
        return self.root.exists()

    def ensure(self) -> "RunTree":
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        return self

    def mosaic_branch(self, mosaic_id: str) -> MosaicBranch:
        """ plant a MosaicBranch at RunTree root, with mosaic_id"""
        return MosaicBranch.plant(self.root, mosaic_id)
    
    def mosaic_branches_from_manifest(self, manifest) -> int: 
        """ given a manifest of mosaic ids, plant all the mosaics at current root """
        ids = manifest.get_ids()
        num_mosaics = 0 
        for mid in ids:
            self.mosaic_branch(mid).ensure()
            num_mosaics += 1
        return num_mosaics

    def recursive_prune(self) -> None:
        if self.root.exists() and self.root.is_dir():
            shutil.rmtree(self.root)

    def get_manifest_csv(self, name: str = "manifest.csv") -> Path:
        """ return path of manifest directory / manifest.csv""" 
        return self.manifest_dir / name  

    def get_metadata_csv(self, name: str = "metadata.csv") -> Path:
        """ return path of manifest directory / metadata.csv"""
        return self.manifest_dir / name

    def get_manifest_json(self) -> Path | None: 
        ... 

    def get_metadata_json(self) -> Path | None: 
        ...
