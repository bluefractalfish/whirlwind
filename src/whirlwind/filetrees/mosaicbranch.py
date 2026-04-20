
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import shutil 

@dataclass(frozen=True)
class MosaicBranch:
    root: Path 
    mosaic_dir: Path 
    browse_dir: Path
    shards_dir: Path 
    manifest_dir: Path 
    metadata_dir: Path 

    @classmethod 
    def plant(cls, root: Path, mosaic_id: str) -> "MosaicBranch":
        """ constructs output tree based upon a canonical structure:
                mosaic_id/
                    browse/
                    shards/ 
                    manifest/ 
                    metadata/
        """
        root = root.expanduser().resolve()
        mosaic_dir = root / mosaic_id 
        return cls(
                root = root, 
                mosaic_dir = mosaic_dir, 
                browse_dir = mosaic_dir / "browse",
                shards_dir = mosaic_dir / "shards",
                manifest_dir = mosaic_dir / "manifest",
                metadata_dir = mosaic_dir / "metadata" )   

    def ensure(self) -> "MosaicBranch":
        for p in (
                self.root, 
                self.browse_dir, 
                self.mosaic_dir, 
                self.shards_dir,
                self.manifest_dir, 
                self.metadata_dir
                ):
            if p is not None:
                p.mkdir(parents=True, exist_ok=True)
        return self
    
    def get_branches(self) -> list[Path]:
        """returns a list of existing subdirectories"""
        if not self.exists or not self.mosaic_dir.is_dir():
            return []
        return sorted(
                (p for p in self.mosaic_dir.iterdir() if p.is_dir()),
                key=lambda p: p.name,)
    
    def get_meta_path(self) -> Path: 
        return self.metadata_dir

    def get_meta_file_path(self, file: str) -> Path: 
        return self.metadata_dir / file

    def exists(self) -> bool:
        return self.mosaic_dir.exists()
    
    def browse_exists(self) -> bool:
        return self.browse_dir.exists() 

    def shards_exist(self) -> bool:
        return self.shards_dir.exists() 

    def manifest_exists(self) -> bool:
        return self.manifest_dir.exists()

    def metadata_exists(self) -> bool:
        return self.metadata_dir.exists()


