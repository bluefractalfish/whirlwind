
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
from whirlwind._r.commands_r.base import Command
from whirlwind._r.config_r import Config 
from whirlwind.tools.ids import gen_uuid_from_path, gen_fingerprint
from whirlwind.tools.pathfinder import build_path 
from whirlwind.io.metadata import write_catalog

class BuildCommand(Command):
    """ build catalog of mosaic uris and uuid """
    name = "build"
    in_path: Path 
    dest_path: Path 

    def run(self, tokens: list[str], config: Config) -> int:
        this_config = config.parse("catalog","build")
        face.print("building catalog")
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                default_in = Path(this_config["in_dir"])
                in_code, self.in_path = build_path(default_in)

            case 1:
                in_code,self.in_path = build_path(tokens[0])

            case 2:
                in_code, self.in_path = build_path(tokens[0])
                dest_code,self.dest_path = build_path(tokens[1])
            case _: 
                face.error("catalog build usage: catalog build expects 0,1,2 arguments")
                return 3

        dest_code,self.dest_path = build_path(this_config["dest_dir"]) 
        catalog_name = f"{this_config["file_name"]}"
        catalog_path = self.dest_path / catalog_name 
        face.process("/"+str(self.in_path.name),"catalogging", str(self.dest_path.name)+"/"+catalog_name)

        if not catalog_path.exists():
            face.print(f"writing catalog for {self.in_path.name}/")
            return write_catalog(self.in_path, catalog_path)
        elif catalog_path.exists():
            face.info(f"catalog exists for {str(self.in_path)}")
            return 0
        else:
            face.error(f"error encountered")
            return 3
