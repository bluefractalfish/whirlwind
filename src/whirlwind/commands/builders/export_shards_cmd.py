EXPORT_SHARDS_HELP = """
    usage: build export shards [selector options] [options]

    purpose:
      Export tile shards back to GeoTIFF files for visual inspection or GIS use.
      This operates from existing shard/tile artifacts, not from full-raster reads.

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
      --damage
          Export from the damage shard subdirectory. Without this flag it will 
          default to whatever directories exist under shards/

      -c
          Color output by centerline distance.

      -f
          Overwrite existing exported TIFFs.

      -r
          Stop on first export error.

    """

from whirlwind.commands.context import CommandContext 
from whirlwind.commands.selector import pathset 
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.domain.config import Config

from whirlwind.bridges.tiling.shards_to_tifs import Request, Result, ExportShardsBridge



class BuildExportShardRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        run_tree = ctx.run_tree 
        paths, manifest = pathset(tv, ctx) 

        return Request(
                run_tree=run_tree, 
                manifest=manifest, 
                paths=paths, 
                shard_sub_dir="damage" if "--damage" in tv.flags else None, 
                display_bands=(0,1,2), 
                color_by = "centerline_distance" if "-c" in tv.flags else None, 
                overwrite="-f" in tv.flags,
                stop_on_error="-r" in tv.flags, 
                )
    def help(self) -> str:
            return EXPORT_SHARDS_HELP.strip()
class BuildReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        return result.code 
        

ExportShardsCommand = BridgeCommand(
    name = "export shards", 
    builder = BuildExportShardRequest(), 
    bridge= ExportShardsBridge(), 
    reporter = BuildReporter()
    )
