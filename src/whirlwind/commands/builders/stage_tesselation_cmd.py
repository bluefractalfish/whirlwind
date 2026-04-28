
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.bridges.staging.stage_tesselation import Result, Request, StageTesselationBridge 
from whirlwind.bridges.specs.tiling import TSpec
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.commands.context import CommandContext
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
        manifest_path = run_tree.get_manifest_path_csv()
        manifest = IDManifest(manifest_path)
        paths = manifest.paths()
        
        return Request(
                spec = spec, 
                tree = run_tree, 
                manifest=manifest, 
                paths=paths, 
                force = True if "-f" in tv.flags else False, 
                )

    
class PlanTilingReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        if result.skipped:
            face.info(f"tile plan exists")
            return result.code

        face.info(f"rasters seen: {result.rasters_seen}")
        face.info(f"tiles planned: {result.tiles_written}")
        face.info(f"return code: {result.code}")

        return result.code


StageTesselationCommand = BridgeCommand(
        name = "stage tesselation",
        builder=BuildTileStagingRequest(), 
        bridge=StageTesselationBridge(), 
        reporter=PlanTilingReporter()
        )
