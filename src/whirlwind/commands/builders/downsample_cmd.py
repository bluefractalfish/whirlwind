DOWNSAMPLE_HELP = """
    usage: build downsample [selector options] [options]

    purpose:
      Create downsampled browse rasters for mosaics selected from the active ID manifest.

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
          Overwrite existing downsampled outputs.

      -d, --display-range
          Include display range behavior during downsample output.

    config:
      DSSpec is read from the active config.

    """
from whirlwind.face import face 
from whirlwind.bridges.specs.downsample import DSSpec 

from whirlwind.bridges.catalogs.writeidmanifest import IDManifest
from whirlwind.bridges.rasterops.downsample import Request, Result, DownsampleBridge
from whirlwind.commands.context import CommandContext 
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.commands.selector import pathset 
from whirlwind.domain.config import Config


class BuildDownsampleRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config,
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        spec = DSSpec.from_config(ctx.config)

        paths, manifest = pathset(tv, ctx)

        return Request(run_tree = ctx.run_tree, 
                spec = spec, 
                manifest = manifest, 
                paths = paths, 
                overwrite="-f" in tv.flags or "--force" in tv.flags, 
                display_range="-d" in tv.flags or "--display-range" in tv.flags
                )

    def help(self) -> str:
            return DOWNSAMPLE_HELP.strip()


class BuildDownsampleReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        if result.exists == result.rasters_seen: 
            face.info("downsampled rasters already exist")
            face.div()
            face.info("run downsample with `-f` or `--force` to overwrite")
            face.div()
            return result.code
        

        face.print(f"rasters seen: {result.rasters_seen}")
        face.print(f"downsampled: {result.downsampled}")
        face.info(f"manifest: {result.manifest_path}")

        return result.code 
        

DownsampleCommand = BridgeCommand(
    name = "downsample", 
    builder = BuildDownsampleRequest(), 
    bridge= DownsampleBridge(), 
    reporter = BuildDownsampleReporter()
        )
