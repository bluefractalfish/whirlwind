
"""whirlwind.commands.catalog

PURPOSE: 
    - entrypoint for catalog build command 
BEHAVIOR:
    - catalog build: creates a catalog of mosaics with uri uuid table and basic size/dim data 
    - catalog build ... -> creates run_id/metadata/catalog.csv from mnt/ if args = ... 
    - catalog build path/to/mosaics -> creates /metadata/catalog.csv defaults to dest_dir
    - catalog build path/to path/out -> creates both in and out dir

"""

from pathlib import Path 

from whirlwind.ui import face 
from whirlwind.commands.base import Command
from whirlwind.config import Config 
from whirlwind.tools.pathfinder import build_path 
from whirlwind.catalogs import IDCatalog
from whirlwind.filesystem import RunTree, MosaicTree
# BuildCatalog
class BuildCommand(Command):
    """ build catalog of mosaic uris and uuid """
    name = "build"
    in_path: Path
    dest_path: Path 

    def run(self, tokens: list[str], config: Config) -> int:
        global_config = config.parse("global","io")
        this_config = config.parse("catalog","build")
        face.info("BUILDING CATALOG")
        face.prog_row("1/4","building catalog")
        flags = [t for t in tokens if t.startswith("-")]
        tokens = [t for t in tokens if t not in flags]
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                self.in_path = Path(global_config["in_dir"])
            case 1:
                _,self.in_path = build_path(tokens[1]) 
            case _: 
                face.error("catalog build usage: catalog build expects 0,1,2 arguments")
                return 3

        face.prog_row("2/4","checking io")

        face.prog_row("3/4","constructing catalog path")
        catalog_name = f"{this_config["file_name"]}"
        
        out_root = Path(global_config["dest_dir"]) / "run_id"
        tree = RunTree.plant(out_root).ensure() 
        
        catalog_path = tree.catalog_dir / catalog_name 
        
             
        if not catalog_path.exists() or "-f" in flags:  
            face.prog_row("4/4",f"writing catalog for {self.in_path.name}/")
            face.process("/"+str(self.in_path.name),"building catalog",str(tree.catalog_dir)+"/"+catalog_name)
            
            catalog = IDCatalog.write_now(dest=catalog_path, src=self.in_path)
            
            mosaic_ids = catalog.get_ids()

            for mid in mosaic_ids:
                tree.mosaic_tree(mid).ensure()

            return 2

        face.info(f"catalog exists for {str(self.in_path)}")
        return 0
