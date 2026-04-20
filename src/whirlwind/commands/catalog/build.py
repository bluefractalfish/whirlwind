
"""whirlwind.commands.manifest

PURPOSE: 
    - entrypoint for manifest build command 
BEHAVIOR:
    - manifest build: creates a manifest of mosaics with uri uuid table and basic size/dim data 
    - manifest build ... -> creates run_id/metadata/manifest.csv from mnt/ if args = ... 
    - manifest build path/to/mosaics -> creates /metadata/manifest.csv defaults to dest_dir
    - manifest build path/to path/out -> creates both in and out dir

"""

from pathlib import Path 

from whirlwind.ui import face 
from whirlwind.commands.base import Command
from whirlwind.config import Config 
from whirlwind.tools.pathfinder import build_path 
from whirlwind.manifests import IDManifest
from whirlwind.filetrees import RunTree, MosaicBranch

# Buildmanifest
class BuildIDManifest(Command):
    """ build manifest of mosaic uris and uuid """
    name = "build"
    in_path: Path
    dest_path: Path 

    def run(self, tokens: list[str], config: Config) -> int:
        run_id = config.parse("global","run_id")
        global_config = config.parse("global","io")
        this_config = config.parse("manifest","build")
        face.info("BUILDING manifest")
        face.prog_row("1/4","building manifest")

        flags = [t for t in tokens if t.startswith("-")]
        tk = [t for t in tokens if t not in flags]
        
        match len(tk):
            case 0:
                # if no input directory default to mnt/
                self.in_path = Path(global_config["in_dir"])
            case 1:
                _,self.in_path = build_path(tk[0]) 
            case _: 
                face.error("usage: manifest build expects 0,1,2 arguments")
                return 3

        face.prog_row("2/4","checking io")

        face.prog_row("3/4","constructing manifest path")
        manifest_name = f"{this_config["file_name"]}"
        
        tree = RunTree.from_config(config) 
        
        manifest_path = tree.get_manifest_path_csv(manifest_name) 
        
             
        if not manifest_path.exists() or "-f" in flags:  
            face.prog_row("4/4",f"writing manifest for {self.in_path.name}/")
            face.process("/"+str(self.in_path.name),"building manifest",str(tree.manifest_dir)+"/"+manifest_name)
            
            manifest = IDManifest.write_now(dest=manifest_path, src=self.in_path)
            
            return 2

        face.info(f"manifest exists for {str(self.in_path)}")
        return 0

class BuildMosaicBranches(Command):
    name = "build branches"
    manifest: IDManifest 

    def run(self, tokens: list[str], config: Config ) -> int: 

        run_id = config.parse("global","run_id")
        global_config = config.parse("global","io")
        this_config = config.parse("manifest","build")

        flags = [t for t in tokens if t.startswith("-")]
        tokens = [t for t in tokens if t not in flags]
        
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                self.in_path = Path(global_config["in_dir"])
            case 1:
                _,self.in_path = build_path(tokens[0]) 
            case _: 
                face.error("usage: manifest build expects 0,1,2 arguments")
                return 3

        face.prog_row("1/4","checking io")

        manifest_name = f"{this_config["file_name"]}"
        
        out_root = Path(global_config["dest_dir"]) / str(run_id)
        tree = RunTree.plant(out_root).ensure() 
     
        manifest_path = tree.manifest_dir / manifest_name 
        
             
        if not manifest_path.exists() or "-f" in flags:  
            face.info(f"manifest does not exist, call buildidmanifest to get mosaic branches")

           # IF THIS FUNCTION SHOULD WRITE MANIFEST 

        manifest = IDManifest.from_path(manifest_path)
        
        if manifest.exists():
            n = tree.mosaic_branches_from_manifest(manifest)
        
            return 2

        return 0


