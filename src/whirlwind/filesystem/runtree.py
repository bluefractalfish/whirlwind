""" whirlwind.domain.filesystem.runtree 

holds information about this runs files, manifest, and mosaicbranches 

    PUBLIC
    ------- 
    @classmethod 
    RunTree().plant(root: str | Path) -> RunTree
             .from_config(config: Config) -> RunTree 
             .ensure() -> RunTree 

    contains 
    ------- 
    root: Path 
    manifest_dir: Path 

    methods: 
    -------- 
    exists -> bool 
    plant_mosaic_branch(file_id: str) -> MosaicBranch 
    mosaic_branches_from_manifest(manifest) -> int (number of mosaicbranches planted)
    get_manifest_path_csv(name: str = "manifest.csv") -> Path 
    get_metadata_path(name: str = "metadata.csv") -> Path 

    ***CAUTION*** 
    prune(file_id: str) -> int (recursively destroys mosaicbranch at file_id)
    recursively_prune() -> int (recursively destroys itself)

    """


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil 

from whirlwind.filesystem.mosaicbranch import MosaicBranch
from whirlwind.filesystem.metamosaictree import MetamosaicTree
from whirlwind.domain.mosaic import MosaicRecord
from whirlwind.filesystem.files import RasterFile 
from whirlwind.filesystem.spatialbundle import SpatialBundle
from whirlwind.domain.config import Config 

@dataclass
class RunTree:
    """ holds information about this runs files, manifest, and mosaicbranches 

        PUBLIC
        ------- 
        @classmethod 
        RunTree().plant(root: str | Path) -> RunTree
                 .from_config(config: Config) -> RunTree 
                 .ensure() -> RunTree 

        contains 
        ------- 
        root: Path 
        manifest_dir: Path 

        methods: 
        -------- 
        exists -> bool 
        plant_mosaic_branch(file_id: str) -> MosaicBranch 
        get_mosaic_branch(file_id: str ) -> MosaicBranch
        mosaic_branches_from_manifest(manifest) -> int (number of mosaicbranches planted)
        
        get_manifest_path_csv(name: str = "manifest.csv") -> Path 
        get_metadata_path(name: str = "metadata.csv") -> Path 

        **CAUTION**
        prune(file_id) -> int (recursively prunes mosaicbranch at that file_id )
        recursively_prune() -> int (recursively destroys itself)
  
  
        """
    # a reference to the starting path 
    root: Path 
    # the path holding any manifests, 
    manifest_dir: Path 
    layout: TreeLayout 

    def branchlook(
        self, 
        manifest,
        path: str | Path,
    ) -> MosaicBranch:
        """ given an instance of runtree, a manifest, and a path target 
            
            find a mosaicbranch under a metamosaic, if available 
            usage: 
            -------- 
            replace: 

            f = RasterFile(path)
            fid = f.mosaic_id
            branch = MosaicBranch.plant(request.tree.root, fid).ensure()

            with: 
            
            branch = request.tree.branchlook(request.manifest, path)

            """

        target = Path(path).expanduser().resolve()

        for record in manifest.records():
            if record.path.expanduser().resolve() == target:
                return self.branch_for(record).ensure()

        # Fallback for old manifests without metamosaic_id.
        raster = RasterFile(target)
        return MosaicBranch.plant(self.root, raster.mosaic_id).ensure() 

    @classmethod
    def plant(cls, root: str | Path, layout: TreeLayout | None=None) -> "RunTree":
        """ plant a tree at root. checks if root already exists and overwrites if requested, calling ensure() and returning RunTree"""
        root = Path(root).expanduser().resolve()
        layout = layout or TreeLayout()

        tree = cls( root = root, 
                   manifest_dir = layout.manifest_dir(root),
                   layout=layout
                   ) 

        return tree.ensure()

   
    @classmethod 
    def from_config(cls, config: Config) -> "RunTree":
       out_root = config.out_path() / config.run_id()
       return RunTree.plant(out_root)

    @property 
    def exists(self) -> bool:
        return self.root.exists()

    def ensure(self) -> "RunTree":
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        return self

    def plant_mosaic_branch(self, file_id: str) -> MosaicBranch:
        """ plant a MosaicBranch at RunTree root, with file_id"""
        mosaic = MosaicBranch.plant(self.root, file_id)
        return mosaic 

    def branch_for(self, record: MosaicRecord,) -> "MosaicBranch":
        if record.metamosaic_id:
            return self.spatial_branch_for(
                record
            ).mosaic_branch(
                record.mosaic_id
            )

        branch_dir = self.layout.mosaic_branch_dir(
            self.root,
            record.mosaic_id,
        )

        return MosaicBranch.plant_at(
            branch_dir,
            record.mosaic_id,
        )

    def spatial_branch_for( self, record: MosaicRecord) -> "SpatialBundle":
        if not record.metamosaic_id:
            raise ValueError(
                f"{record.mosaic_id} has no metamosaic_id"
            )

        if not record.bundle_id:
            raise ValueError(
                f"{record.mosaic_id} has no branch_id"
            )

        return SpatialBundle.plant_at(
            self.layout.metamosaic_branch_dir(
                self.root,
                record.metamosaic_id,
                record.bundle_id,
            ),
            record.bundle_id,
        )

    def metamosaic_tree(self, metamosaic_id: str) -> MetamosaicTree: 
        return MetamosaicTree.plant(
                self.layout.metamosaic_dir(self.root, metamosaic_id),
                metamosaic_id
            )
    def root_manifest_path(self, name: str = "manifest.csv") -> Path: 
        return self.layout.root_manifest_path(self.root, name) 

    def get_mosaic_branch(self, file_id: str) -> MosaicBranch: 
        return self.plant_mosaic_branch(file_id)

    def mosaic_branches_from_manifest(self, manifest) -> int: 
        """ given a manifest of mosaic ids, plant all the mosaics at current root """
        ids = manifest.get_ids()
        num_mosaics = 0 
        for mid in ids:
            self.plant_mosaic_branch(mid).ensure()
            num_mosaics += 1
        return num_mosaics
    
    def prune(self, file_id: str ) -> int: 
        branch = self.get_mosaic_branch(file_id)
        if branch.exists(): 
            shutil.rmtree(branch.mosaic_dir)
            return 0 
        return 1

    def recursive_prune(self) -> int :
        if self.root.exists() and self.root.is_dir():
            shutil.rmtree(self.root)
            return 0 
        return 1 

    def get_manifest_path_csv(self, name: str = "manifest.csv") -> Path:
        """ return path of manifest directory / manifest.csv""" 
        return self.manifest_dir / name
    
    def get_metadata_path_csv(self, name: str = "metadata.csv") -> Path:
        """ return path of manifest directory / metadata.csv"""
        return self.manifest_dir / name 
    



@dataclass 
class TreeLayout: 
    version: str = "layout-v2"

    def manifest_dir(self, root: Path) -> Path:
        return root / "manifest"

    def root_manifest_path(self, root: Path, name: str) -> Path: 
        return self.manifest_dir(root) / name 

    def loose_mosaics_dir(self, root: Path) -> Path: 
        return root / "mosaics" 

    def mosaic_branch_dir(self, root: Path, mosaic_id: str) -> Path: 
        return self.loose_mosaics_dir(root) / mosaic_id 

    def metamosaics_dir(self, root: Path) -> Path: 
        return root / "metamosaics" 

    def metamosaic_dir(self, root: Path, metamosaic_id: str) -> Path: 
        return self.metamosaics_dir(root) / metamosaic_id 

    def metamosaic_branches_dir(self, root: Path, metamosaic_id: str) -> Path: 
        return self.metamosaic_dir(root, metamosaic_id) / "branches" 

    def metamosaic_branch_dir(self,root: Path, metamosaic_id: str,branch_id: str,) -> Path:
        return (
            self.metamosaic_branches_dir(root,metamosaic_id) / branch_id
        )

    def metamosaic_mosaic_branch_dir(self,
                                     root: Path,
                                     metamosaic_id: str,
                                     branch_id: str,
                                     mosaic_id: str,
                                     ) -> Path:
        return (
            self.metamosaic_branch_dir(root,metamosaic_id,branch_id)/ "mosaics" / mosaic_id
            )
