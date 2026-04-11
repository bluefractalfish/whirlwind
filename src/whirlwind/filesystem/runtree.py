

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import shutil 

from whirlwind.filesystem import MosaicTree

@dataclass(frozen=True)
class RunTree:
    root: Path 
    catalog_dir: Path 
    
    @classmethod
    def plant(cls, root: str | Path) -> "RunTree":
        root = Path(root).expanduser().resolve()
        return cls(
                root = root, 
                catalog_dir = root /"catalog",
                )

    def ensure(self) -> "RunTree":
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        return self
    
    def mosaic_tree(self, mosaic_id: str) -> MosaicTree:
        return MosaicTree.plant(self.root, mosaic_id)
    
    def recursive_prune(self) -> None:

        confirm = input(f"are you sure you want to delete everthing in {self.root.name}? (y/n) ")
        
        if confirm == "y":
            if self.root.exists() and self.root.is_dir():
                shutil.rmtree(self.root)
            print("deleting...")
