""" whirlwind.domain.filesystem.mosaicbranch 

PUBLIC  
--------- 
MosaicBranch().plant(root: Path, mosaic_id: str) -> MosaicBranch  
               .ensure() -> MosaicBranch (builds subdirectories if dont exist)

    contains 
    --------
    root: Path 
    mosaic_id: str 
    mosaic_dir: Path 
    browse_dir: Path 
    shards_dir: Path 
    manifest_dir: Path 
    metadata_dir: Path

    methods 
    -------- 
    get_branches() -> list[Path]
    get_meta_file_path(file: str ) -> Path | None 
    exists() -> bool (mosaic_dir.exists())
    browse_exists() -> bool 
    shards_exists() -> bool 
    manifest_exists() -> bool 
    metadata_exists() -> bool 


"""


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import shutil 

@dataclass(frozen=True)
class MosaicBranch:
    """ subtree/branch representing one mosaic and contains metadata, shards, browse tifs 

        PUBLIC  
        --------- 
        MosaicBranch().plant(root: Path, mosaic_id: str) -> MosaicBranch  
                       .ensure() -> MosaicBranch (builds subdirectories if dont exist)

            contains 
            --------
            root: Path 
            mosaic_id: str 
            mosaic_dir: Path 
            browse_dir: Path 
            shards_dir: Path 
            manifest_dir: Path 
            metadata_dir: Path

            methods 
            -------- 
            get_branches() -> list[Path]
            get_meta_file_path(file: str ) -> Path | None 
            exists() -> bool (mosaic_dir.exists())
            browse_exists() -> bool 
            shards_exists() -> bool 
            manifest_exists() -> bool 
            metadata_exists() -> bool 


    """
    root: Path 
    mosaic_id: str 
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
                mosaic_id = mosaic_id,
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
    

    def get_meta_file_path(self, file: str) -> Path | None: 
        return self.metadata_dir / file or None 


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


