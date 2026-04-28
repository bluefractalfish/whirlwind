
from typing import Literal 
from whirlwind.face import face 
from whirlwind.bridges.staging.stage_damagepaths import Request, Result
from whirlwind.bridges.specs.path import PathSpec
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.config import Config 



class BuildDamagePathStageRequest(RequestBuilder[Request]):
   def from_tokens(
            self, 
            tokens: list[str],
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config) 

        run_tree = ctx.run_tree 
        manifest_path = run_tree.get_manifest_path_csv()
        manifest = IDManifest(manifest_path)
        paths = manifest.paths()
        overwrite = "-f" in tv.flags or "--overwrite" in tv.flags 
        set_defaults = False if "--no-default" in tv.flags or "-nd" in tv.flags else True

        return Request(
                tree=ctx.run_tree,
                manifest_path = manifest_path, 
                paths = paths, 
                overwrite=overwrite,
                set_defaults=set_defaults)


class BuildDamagePathStageReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        face.info(f"staging damage path gpkgs for browse rasters")
        face.info(f"referencing manifest: {result.manifest_path}")

        return result.code 
        
