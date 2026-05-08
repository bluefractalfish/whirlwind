

from whirlwind.domain.config.schema import Config 
from whirlwind.commands.selector import pathset 
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
        tree = ctx.run_tree
        shard_cfg = ctx.section("operations", "tesselate")
 
        paths, manifest = pathset(tv, ctx)

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
    def help(self) -> str:
            return """
    usage: build tesselate [selector options] [options]

    purpose:
      Execute tiled raster cutting for selected mosaics using the staged tile plan.
      Writes shard outputs and a tile manifest without full-raster reads.

    selector options:
      --mosaic=ID
          Select one mosaic id. Can be repeated.

      --variant=NAME
          Select mosaics by variant. Can be repeated.

      --date=YYMMDD
          Select mosaics by date. Can be repeated.

      --metamosaic=ID
          Select mosaics by metamosaic id. Can be repeated.

      --limit=N
          Limit the number of selected mosaics.

    options:
      -f, --overwrite
          Overwrite existing shard/tile outputs.
    
      -l, --label
          Attach labels during tesselation.

      -d, --dry
          Dry run. Build request and walk plan without writing heavy outputs.

      -p, --parquet
          Write tile manifest as parquet.

    config:
      operations.tesselate.shard_prefix
          Shard filename prefix.

      operations.tesselate.shard_size
          Number of samples per shard.

      operations.tesselate.manifest_kind
          Default manifest format if -p/--parquet is not used.

      TSpec is read from the active config.

    """.strip()
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

