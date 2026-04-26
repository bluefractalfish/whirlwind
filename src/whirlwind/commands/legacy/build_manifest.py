
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
from whirlwind.commands.bridge import RequestBuilder, TokenView 
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config 
from whirlwind.tools.pathfinder import build_path 
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.filesystem.runtree  import RunTree

from whirlwind.bridges.writemanifest import RequestManifest, BuildManifest, ManifestResult


class BuildManifestRequest(RequestBuilder[RequestManifest]):
    def from_tokens( 
                    self,
                    tokens: list[str], 
                    config: Config,
                    ) -> RequestManifest: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("manifest", "build")

        src_dir = ctx.resolve_path(tv.arg(0) or ctx.in_dir)
        file_types_raw = manifest_cfg.get("file_types", [".tif",".tiff"])
        file_types = tuple(str(x) for x in file_types_raw)

        return RequestManifest(
                src_dir=src_dir, 
                run_tree = ctx.run_tree, 
                manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
                file_types=file_types,
                force=tv.has("-f", "--force"),
                )

# Buildmanifest
class WriteIDManifest(Command):
    """ build manifest of mosaic uris and uuid """
    name = "build"

    def run(self, tokens: list[str], config: Config) -> int: 
        request = self.build_request(tokens, config)
        result = BuildManifest().build(request)
            
        if result.skipped: 
            face.info("manifest already exists")
        else:
            face.info("manifest written")

        face.info(f"files written: {result.files_written}")
        return result.code

 

    def build_request(self, tokens: list[str], config: Config) -> RequestManifest: 
        flags = {t for t in tokens if t.startswith("-")}
        args = [t for t in tokens if not t.startswith("-")]
        force = "-f" in flags or "--force" in flags 
        src_dir = Path(args[0] if args else config.in_path())
        dest_dir = config.out_path()
        run_id = config.run_id()
        run_tree = RunTree.plant(dest_dir/run_id)
    
        return RequestManifest(src_dir=src_dir,
                        run_tree=run_tree, 
                        force=force)
        


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
        manifest = IDManifest(manifest_path)
        manifest = manifest.write_from(manifest_path)
        
        if manifest_path.exists():
            n = tree.mosaic_branches_from_manifest(manifest)
        
            return 2

        return 0


