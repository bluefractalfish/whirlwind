from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.bridges.catalogs.buildmetamosaics import (
    BuildMetamosaicBridge,
    Request,
    Result,
)
from whirlwind.commands.bridge import (
    BridgeCommand,
    RequestBuilder,
    ResultReporter,
    TokenView,
)
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config
from whirlwind.face import face


class BuildMetamosaicRequest(RequestBuilder[Request]):
    def from_tokens(self, tokens: list[str], config: Config) -> Request:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        cfg = ctx.section("metamosaic", "build")

        metadata_name = tv.value(
            "--metadata",
            str(cfg.get("metadata_name", "core-metadata.csv")),
        ) or "core-metadata.csv"

        stem = tv.value("--stem", str(cfg.get("stem", "locale"))) or "locale"

        root_manifest_name = str(cfg.get("root_manifest_name", "manifest.csv"))
        metamosaic_manifest_name = str(
            cfg.get("manifest_name", "metamosaic.csv")
        )

        manifest = IDManifest(
            ctx.run_tree.get_manifest_path_csv(root_manifest_name)
        )

        return Request(
            run_tree=ctx.run_tree,
            manifest=manifest,
            metadata_path=ctx.run_tree.manifest_dir / metadata_name ,
            stem=stem,
            metamosaic_manifest_name=metamosaic_manifest_name,
            root_manifest_name=root_manifest_name,
            force=tv.has("-f", "--force"),
        )


class BuildMetamosaicReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        face.info(f"metamosaic manifest: {result.metamosaic_manifest_path}")
        face.info(f"root manifest: {result.root_manifest_path}")
        face.info(f"mosaics seen: {result.mosaics_seen}")
        face.info(f"intersections: {result.intersections}")
        face.info(f"metamosaics written: {result.metamosaics_written}")
        return result.code


BuildMetamosaicCommand = BridgeCommand(
    name="build metamosaic",
    builder=BuildMetamosaicRequest(),
    bridge=BuildMetamosaicBridge(),
    reporter=BuildMetamosaicReporter(),
)
