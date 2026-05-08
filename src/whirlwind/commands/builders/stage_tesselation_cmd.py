
STAGE_TILING_HELP= """
    usage: build tiling [selector options] [options]

    purpose:
      Stage deterministic tile plans for selected mosaics.
      This writes tile metadata/plans without reading full rasters into memory.

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
          Overwrite existing tile plans.

    config:
      TSpec is read from the active config.

    """.strip() 

from whirlwind.bridges.staging.stage_tesselation import Result, Request, StageTesselationBridge 
from whirlwind.bridges.specs.tiling import TSpec
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.commands.context import CommandContext
from whirlwind.commands.selector import pathset 
from whirlwind.domain.config import Config 
from whirlwind.face import face 


class BuildTileStagingRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config) 
        
        spec = TSpec.from_config(ctx.config)
        run_tree = ctx.run_tree 
        
        paths, manifest = pathset(tv, ctx)


        force = "-f" in tv.flags or "--force" in tv.flags
        return Request(
                spec = spec, 
                tree = run_tree, 
                manifest=manifest, 
                paths=paths, 
                force =force, 
                )

    
    def help(self) -> str:
        return STAGE_TILING_HELP

class PlanTilingReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        if result.code == 2:
            face.print(f"tile plan already exists")
            face.div()
            face.print("run with `-f` or `--force` to overwrite")
            face.div()
            return result.code

        face.print(f"rasters seen: {result.rasters_seen}")
        face.print(f"tiles planned: {result.tiles_written}")

        return result.code


StageTesselationCommand = BridgeCommand(
        name = "tiling",
        builder=BuildTileStagingRequest(), 
        bridge=StageTesselationBridge(), 
        reporter=PlanTilingReporter()
        )
