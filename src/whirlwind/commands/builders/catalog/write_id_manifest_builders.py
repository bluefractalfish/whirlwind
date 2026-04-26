

from whirlwind.face import face 
from whirlwind.commands.bridge import RequestBuilder, TokenView, ResultReporter
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config 

from whirlwind.bridges.catalogs.writeidmanifest import Request, Result


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

        return Request(
                src_dir=src_dir, 
                run_tree = ctx.run_tree, 
                manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
                file_types=file_types,
                force=tv.has("-f", "--force"),
                )



class IDManifestReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        if result.code != 0: 
            face.error(f"manifest not written or no rasters found: {result.manifest_path}")
            face.info(f"files: {result.files_written}")
        if result.skipped:
            face.info(f"manifest exists: {result.manifest_path}")
        else:
            face.info(f"manifest written: {result.manifest_path}")
        face.info(f"files: {result.files_written}")
        return result.code 
