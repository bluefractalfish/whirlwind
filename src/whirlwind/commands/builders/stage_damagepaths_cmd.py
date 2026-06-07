
STAGE_PATHS_HELP =  """
    usage: build stage damage paths [selector options] [options]

    purpose:
      Create empty damage path GeoPackage layers for selected mosaics.
      These are intended to be opened in QGIS and manually edited.

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
          Overwrite existing damage path staging files.

      -nd, --no-default
          Do not populate default fields/values.

    """.strip()

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.bridges.staging.stage_gpkg import GpkgStagingBridge, Request, Result
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.commands.context import CommandContext
from whirlwind.commands.selector import pathset 
from whirlwind.domain.config import Config 
from whirlwind.interface import face 

class BuildGpkgStageRequest(RequestBuilder[Request]):
   def from_tokens(
            self, 
            tokens: list[str],
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config) 

        paths, manifest = pathset(tv, ctx)

        overwrite = "-f" in tv.flags or "--overwrite" in tv.flags 
        set_defaults = False if "--no-default" in tv.flags or "-nd" in tv.flags else True

        return Request(
                tree=ctx.run_tree,
                manifest = manifest, 
                paths = paths, 
                overwrite=overwrite,
                set_defaults=set_defaults ) 

   def help(self) -> str: 
       return STAGE_PATHS_HELP

class BuildDamagePathStageReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        if result.code == 2: 
            face.print(f"path plan already exists")
            face.div()
            face.print("run with `-f` or `--force` to overwrite")
            face.div()
            return result.code

        face.print(f"rasters seen: {result.rasters_seen}")
        face.print(f"rasters skipped: {result.skipped}")
        face.row("manifest", f"{result.manifest_path}")

        return result.code 

StagePathsCommand = BridgeCommand(
        name = "stage gpkgs",
        builder = BuildGpkgStageRequest(), 
        bridge = GpkgStagingBridge(),
        reporter=BuildDamagePathStageReporter()
        )
