from typing import Literal 
from whirlwind.face import face 
from whirlwind.bridges.catalogs.discovermetadata import Request, Result
from whirlwind.commands.bridge import ResultReporter, RequestBuilder, TokenView
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
            manifest_cfg = ctx.section("manifest", "ids")

        metadata_cfg = ctx.section("catalog", "metadata")
        if not metadata_cfg:
            metadata_cfg = ctx.section("manifest", "meta")

        return Request(
            run_tree=ctx.run_tree,
            manifest_name=str(manifest_cfg.get("file_name", "manifest.csv")),
            modes=self._resolve_modes(tv, metadata_cfg),
            file_format=str(metadata_cfg.get("format", "csv")),
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

class BuildMetadataReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        face.info(f"manifest: {result.manifest_path}")

        for summary in result.summaries:
            face.info(f"{summary.mode}: {summary.aggregate_path}")
            face.info(f"rasters seen: {summary.rasters_seen}")
            face.info(f"written: {summary.rasters_written}")
            face.info(f"skipped:  {summary.rasters_skipped}")
            face.info(f"errors:  {summary.errors}")

        return result.code
