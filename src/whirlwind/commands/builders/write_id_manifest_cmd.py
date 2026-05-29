MANIFEST_HELP =  """
    usage: build manifest [SRC_DIR] [options]

    purpose:
      Build an ID manifest from raster files under SRC_DIR.

    positional:
      SRC_DIR
          Directory to scan for rasters.
          If omitted, uses ctx.in_dir from config.

    options:
      -f, --force
          Overwrite an existing manifest.

      -q, --quiet
          do not Print the manifest table after writing.

    config:
      manifest.build.file_name
          Output manifest filename.
          Default: manifest.csv

      manifest.build.file_types
          File suffixes to include.
          Default: [".tif", ".tiff"]

    """.strip()

from whirlwind.interface import face 
from whirlwind.commands.bridge import RequestBuilder, TokenView, ResultReporter, BridgeCommand
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config 

from whirlwind.bridges.catalogs.writeidmanifest import Request, Result, IDManifestBridge


class IDManifestRequestBuilder(RequestBuilder[Request]):
    def from_tokens( 
                    self,
                    tokens: list[str], 
                    config: Config,
                    ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("manifest", "build")

        src_dir = ctx.resolve_path(tv.arg(0) or ctx.in_dir)
        file_types_raw = manifest_cfg.get("file_types", [".tif",".tiff"])
        file_types = tuple(str(x) for x in file_types_raw)
        
        force = tv.has("-f","--force")
        quiet = tv.has("-q", "--quiet")


        return Request(
                src_dir=src_dir, 
                run_tree = ctx.run_tree, 
                manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
                file_types=file_types,
                verbose = not quiet, 
                exempt = str(manifest_cfg.get("exempt", "artifacts")),
                force=force, 
                )
    def help(self) -> str: 
        return MANIFEST_HELP

class IDManifestReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        if result.code != 0: 
            face.error(f"manifest not written or no rasters found: {result.manifest_path}")
            face.error(f"files: {result.files_written}")
        if result.verbose and result.data is not None: 
            face.header("manifest")
            face.table(result.data[0], result.data[1])
        if result.skipped:
            face.print(f"manifest already exists: {result.manifest_path}")
            face.div()
            face.print(f"run with `-f` or `--force` to overwrite")
            face.div()
        else:
            face.print(f"manifest written: {result.manifest_path}")
        face.info(f"files written: {result.files_written}")
        return result.code 


WriteIDManifestCommand = BridgeCommand(
    name="manifest",
    builder=IDManifestRequestBuilder(),
    bridge=IDManifestBridge(),
    reporter=IDManifestReporter(),
)
