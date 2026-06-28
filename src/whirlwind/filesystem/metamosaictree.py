
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MetamosaicTree:
    metamosaic_id: str
    root: Path
    branches_dir: Path
    manifest_dir: Path
    metadata_dir: Path
    labels_dir: Path 
    staging_dir: Path 

    @classmethod
    def plant(cls, root: Path, metamosaic_id: str) -> "MetamosaicTree":
        root = Path(root).expanduser().resolve()
        return cls(
            metamosaic_id=metamosaic_id,
            root=root,
            branches_dir=root / "branches",
            manifest_dir=root / "manifest",
            metadata_dir=root / "metadata",
            labels_dir=root / "labels", 
            staging_dir=root / "staging"
        )

    def ensure(self) -> "MetamosaicTree":
        for p in (self.root, 
                  self.branches_dir, 
                  self.manifest_dir, 
                  self.metadata_dir, 
                  self.labels_dir, 
                  self.staging_dir, 
                  ):
            p.mkdir(parents=True, exist_ok=True)
        return self
