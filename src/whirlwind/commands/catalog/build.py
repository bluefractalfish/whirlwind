
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
from whirlwind.tools.ids import gen_uuid_from_path, gen_fingerprint
from whirlwind.tools.pathfinder import build_path 
from whirlwind.io.metadata import write_catalog

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
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                default_in = Path(global_config["in_dir"])
                _, self.in_path = build_path(default_in)
                _,self.dest_path = build_path(global_config["dest_dir"]) 

            case 1:
                _,self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(global_config["dest_dir"]) 
            case 2:
                _, self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(tokens[1])
            case _: 
                face.error("catalog build usage: catalog build expects 0,1,2 arguments")
                return 3

        face.prog_row("2/4","checking io")

        face.prog_row("3/4","constructing catalog path")
        catalog_name = f"{this_config["file_name"]}"
        catalog_path = self.dest_path / catalog_name 


        if not catalog_path.exists():
            face.prog_row("4/4",f"writing catalog for {self.dest_path.name}/")
            face.process("/"+str(self.in_path.name),"building catalog",str(self.dest_path.name)+"/"+catalog_name)
            return write_catalog(self.in_path, catalog_path)

        face.info(f"catalog exists for {str(self.in_path)}")
        return 0
