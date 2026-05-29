DISCOVER_META_HELP = """
        usage: build discover metadata [selector options] [mode options] [options]

        purpose:
          Discover raster metadata for mosaics selected from the active ID manifest.

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

        mode options:
          -c, --core
              Write core metadata only.

          -e, --extended
              Write extended metadata only.

          -fll, --full
              Write full metadata only.

          -a, --all
              Write core, extended, and full metadata.

        options:
          -f, --force
              Overwrite existing metadata outputs.

        config:
          catalog.metadata.modes
          manifest.meta.modes
              Default metadata modes if no mode flag is passed.

        """

from typing import Literal 
from whirlwind.commands.selector import pathset 
from whirlwind.interface import face 
from whirlwind.bridges.catalogs.discovermetadata import Request, Result, DiscoverMetadataBridge
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView, BridgeCommand
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config 


MetadataMode = Literal["core", "extended", "full"]

_MODE_FLAGS: dict[str, tuple[MetadataMode,...]] = {
        "-c" : ("core",),
         "--core": ("core",),
        "-e": ("extended",),
        "--extended": ("extended",),
        "-a": ("core", "extended", "full"),
        "--all": ("core", "extended", "full"),
        "-fll": ("full",),
        "--full": ("full",),
        }

class BuildMetadataRequest(RequestBuilder[Request]):
    def from_tokens(
        self,
        tokens: list[str],
        config: Config, ) -> Request:


        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_cfg = ctx.section("catalog", "manifest")
        if not manifest_cfg:
            manifest_cfg = ctx.section("manifest", "build")

        metadata_cfg = ctx.section("catalog", "metadata")
        if not metadata_cfg:
            metadata_cfg = ctx.section("manifest", "meta")

        paths, manifest =  pathset(tv, ctx)

        return Request(
            run_tree=ctx.run_tree,
            paths=paths, 
            manifest=manifest,
            modes=self._resolve_modes(tv, metadata_cfg),
            force=tv.has("-f", "--force"),
        )

    def _resolve_modes(
        self,
        tv: TokenView,
        metadata_cfg: dict,
    ) -> tuple[MetadataMode, ...]:
        for flag, modes in _MODE_FLAGS.items():
            if tv.has(flag):
                return modes

        raw_modes = metadata_cfg.get("modes", ["core"])

        if isinstance(raw_modes, str):
            raw_modes = [raw_modes]

        modes = tuple(str(mode).lower() for mode in raw_modes)

        valid = {"core", "extended", "full"}
        invalid = [mode for mode in modes if mode not in valid]

        if invalid:
            raise ValueError(f"unsupported metadata modes: {invalid}")

        return modes  # type: ignore[return-value]

    def help(self) -> str: 
       return  DISCOVER_META_HELP.strip()

class BuildMetadataReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        face.info(f"manifest used: {result.manifest_path}")

        for summary in result.summaries:
            face.print(f"{summary.mode}: {summary.aggregate_path}")
            face.print(f"rasters seen: {summary.rasters_seen}")
            face.print(f"written: {summary.rasters_written}")
            face.print(f"skipped:  {summary.rasters_skipped}")
            face.error(f"errors: {summary.errors}")

        return result.code


DiscoverMetadataCommand = BridgeCommand(
        name="discover metadata", 
        builder=BuildMetadataRequest(), 
        bridge = DiscoverMetadataBridge(), 
        reporter=BuildMetadataReporter(), 
    )
