from whirlwind.face import face 
from whirlwind.bridges.specs.downsample import DSSpec 

from whirlwind.bridges.catalogs.writeidmanifest import IDManifest
from whirlwind.bridges.rasterops.downsample import Request, Result
from whirlwind.commands.context import CommandContext 
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView
from whirlwind.domain.config import Config
from whirlwind.domain.filesystem import runtree 


class BuildDownsampleRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config,
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        spec = DSSpec.from_config(ctx.config)
        run_tree = ctx.run_tree 
        manifest_name = ctx.section("manifest","ids")["file_name"]
        manifest_path = run_tree.get_manifest_path_csv(manifest_name)
        manifest = IDManifest(manifest_path)
        paths = manifest.paths()

        return Request(run_tree = ctx.run_tree, 
                spec = spec, 
                manifest_path = manifest_path, 
                paths = paths, 
                overwrite="-f" in tv.flags or "--overwrite" in tv.flags, 
                display_range="-d" in tv.flags or "--display-range" in tv.flags
                )


class BuildDownsampleReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        face.info(f"downsampling from manifest")
        face.info(f"manifest: {result.manifest_path}")

        for summary in result.summaries:
            face.info(f"{summary.src_path}")

        return result.code 
        
