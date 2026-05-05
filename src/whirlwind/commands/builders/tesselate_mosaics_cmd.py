

from whirlwind.domain.config.schema import Config 
from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.bridges.rasterops.tesselate import TesselationBridge, Request, Result 
from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.domain.config.schema import Config 
from whirlwind.face import face 

from whirlwind.commands.bridge import (
        RequestBuilder, ResultReporter, BridgeCommand, TokenView )
from whirlwind.commands.context import CommandContext


class BuildTesselationRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)
        
        spec = TSpec.from_config(ctx.config)
        print(spec.drop_partial)
        tree = ctx.run_tree
        shard_cfg = ctx.section("operations", "tesselate")
        manifest_name = ctx.section("manifest", "ids")["file_name"]
        manifest_path = tree.get_manifest_path_csv(manifest_name)
        manifest = IDManifest(manifest_path)
        paths = manifest.paths()
        

        return Request(
                spec = spec, 
                tree = tree, 
                manifest = manifest, 
                paths = paths, 
                prefix = f"{spec.tile_size}_{shard_cfg["shard_prefix"]}", 
                shard_size = shard_cfg["shard_size"],
                overwrite = "-f" in tv.flags or "--overwrite" in tv.flags, 
                label = "-l" in tv.flags or "--label" in tv.flags, 
                dry = "-d" in tv.flags or "--dry" in tv.flags, 
                dpath_name = "damage_path.gpkg",
                plan_name = "tile_plan.csv",
                manifest_name="tile_manifest.csv",
                manifest_kind="parquet" if "-p" in tv.flags or "--parquet" in tv.flags 
                                 else shard_cfg["manifest_kind"] 
                )

class BuildTesselationReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        face.info(f"rasters seen: {result.n_rasters_seen}")
        face.info(f"tiles written: {result.n_tiles_written}")
        face.info(f"exit code: {result.code}")
        return result.code 


TesselationCommand = BridgeCommand(
        name = "tesselate", 
        builder = BuildTesselationRequest(), 
        bridge = TesselationBridge(), 
        reporter = BuildTesselationReporter()
    )

