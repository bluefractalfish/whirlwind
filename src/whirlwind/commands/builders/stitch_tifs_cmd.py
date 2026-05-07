
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
                paths=paths, 
                overwrite = force, 
                )


class BuildStitchReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        
        

StitchCommand = BridgeCommand(
    name = "stitch", 
    builder = BuildStitchRequest(), 
    bridge= StitchTifsBridge(), 
    reporter = BuildStitchReporter()
    )
