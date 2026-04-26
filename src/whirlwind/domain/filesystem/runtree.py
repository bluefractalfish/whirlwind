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
    plant_mosaic_branch(mosaic_id: str) -> MosaicBranch 
    mosaic_branches_from_manifest(manifest) -> int (number of mosaicbranches planted)
    get_manifest_path_csv(name: str = "manifest.csv") -> Path 
    get_metadata_path(name: str = "metadata.csv") -> Path 

    ***CAUTION*** 
    prune(mosaic_id: str) -> int (recursively destroys mosaicbranch at mosaic_id)
    recursively_prune() -> int (recursively destroys itself)

    """


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path
from typing import List
import shutil 

from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.config import Config 
#from whirlwind.manifests.idmanifest import IDManifest

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
        plant_mosaic_branch(mosaic_id: str) -> MosaicBranch 
        get_mosaic_branch(mosaic_id: str ) -> MosaicBranch
        mosaic_branches_from_manifest(manifest) -> int (number of mosaicbranches planted)
        
        get_manifest_path_csv(name: str = "manifest.csv") -> Path 
        get_metadata_path(name: str = "metadata.csv") -> Path 

        **CAUTION**
        prune(mosaic_id) -> int (recursively prunes mosaicbranch at that mosaic_id )
        recursively_prune() -> int (recursively destroys itself)
  
  
        """
    # a reference to the starting path 
    root: Path 
    # the path holding any manifests, 
    manifest_dir: Path 
    # a dictionary of mosaic branches 
    #branches: dict[str, Any] = {}

    @classmethod
    def plant(cls, root: str | Path) -> "RunTree":
        """ plant a tree at root. checks if root already exists and overwrites if requested, calling ensure() and returning RunTree"""
        root = Path(root).expanduser().resolve()
        #######################################
        ## CHECK IF ROOT EXISTS, OVERWRITE IF NOT EMPTY?  ##
        #######################################

        tree = cls( root = root, 
                   manifest_dir = root /"manifest",
                   ) 

        ############################################
        ## RUN ENSURE(), mkdir for root, manifest ##
        tree.ensure()
        ############################################

        return tree 
    
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

    def plant_mosaic_branch(self, mosaic_id: str) -> MosaicBranch:
        """ plant a MosaicBranch at RunTree root, with mosaic_id"""
        mosaic = MosaicBranch.plant(self.root, mosaic_id)
        return mosaic 

    def get_mosaic_branch(self, mosaic_id: str) -> MosaicBranch: 
        return self.plant_mosaic_branch(mosaic_id)

    def mosaic_branches_from_manifest(self, manifest) -> int: 
        """ given a manifest of mosaic ids, plant all the mosaics at current root """
        ids = manifest.get_ids()
        num_mosaics = 0 
        for mid in ids:
            self.plant_mosaic_branch(mid).ensure()
            num_mosaics += 1
        return num_mosaics
    
    def prune(self, mosaic_id: str ) -> int: 
        branch = self.get_mosaic_branch(mosaic_id)
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
    

