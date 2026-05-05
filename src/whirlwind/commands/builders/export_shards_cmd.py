
from whirlwind.bridges.catalogs.writeidmanifest import IDManifest
from whirlwind.commands.context import CommandContext 
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.domain.config import Config

from whirlwind.bridges.tiling.shards_to_tifs import Request, Result, ExportShardsBridge



class BuildExportShardRequest(RequestBuilder[Request]):
    def from_tokens(
            self, 
            tokens: list[str], 
            config: Config, 
            ) -> Request: 
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        run_tree = ctx.run_tree 
        manifest_name = ctx.section("manifest","ids")["file_name"]
        manifest_path = run_tree.get_manifest_path_csv(manifest_name)
        manifest = IDManifest(manifest_path)
        paths = manifest.paths()

        return Request(
                run_tree=run_tree, 
                manifest=manifest, 
                paths=paths, 
                shard_sub_dir="damage" if "--damage" in tv.flags else None, 
                display_bands=(0,1,2), 
                overwrite="-f" in tv.flags,
                stop_on_error="-r" in tv.flags, 
                )

class BuildReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int: 
        return result.code 
        

ExportShardsCommand = BridgeCommand(
    name = "export shards", 
    builder = BuildExportShardRequest(), 
    bridge= ExportShardsBridge(), 
    reporter = BuildReporter()
    )
