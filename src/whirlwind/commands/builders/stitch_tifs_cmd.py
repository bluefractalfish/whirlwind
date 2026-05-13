STITCH_TIFS_HELP =  """
usage: build stitch [selector options] [options]

purpose:
  Stitch exported tile GeoTIFFs into per-group mosaic TIFFs.
  Internally builds VRTs and translates them to GeoTIFF outputs.

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
  -f, --force
      Overwrite existing stitched TIFF outputs.

bridge defaults:
  out_dir_name: stitched
  pattern: **/*.tif
  bigtiff: IF_SAFER
  tiled: true
  compress: DEFLATE

""".strip()

from whirlwind.face import face 
from whirlwind.bridges.specs.downsample import DSSpec 

from whirlwind.bridges.catalogs.writeidmanifest import IDManifest
from whirlwind.bridges.tiling.stitch_tifs import Request, Result, StitchTifsBridge
from whirlwind.commands.context import CommandContext 
from whirlwind.commands.selector import pathset
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.domain.config import Config


class BuildStitchRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config,
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)
         
        paths, manifest = pathset(tv, ctx)

        force = tv.has("-f", "--force")
        return Request(
                run_tree = ctx.run_tree, 
                manifest=manifest,
                paths=paths, 
                overwrite = force, 
                ) 
    def help(self) -> str:
        return STITCH_TIFS_HELP

class BuildStitchReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
       return result.code
        

StitchCommand = BridgeCommand(
    name = "stitch", 
    builder = BuildStitchRequest(), 
    bridge= StitchTifsBridge(), 
    reporter = BuildStitchReporter()
    )
